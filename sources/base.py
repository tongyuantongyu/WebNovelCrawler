from __future__ import annotations

import abc
import base64
import json
import pickle
import sys
from typing import Tuple, Dict, Type

import trio
import httpx
from tqdm import tqdm

from util import NovelDB, Episode, LinearMenu, make_track_sub_meta


def create_or_append(dict_, key, value):
    if key in dict_:
        dict_[key].append(value)
    else:
        dict_[key] = [value]


class Base(metaclass=make_track_sub_meta("source")):
    sources: Dict[str, Type[Base]] = {}

    def __init__(self, book_id, limit=2, retry=3, source_unique_episode_id=True):
        self.client = httpx.AsyncClient(
            http2=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/126.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,'
                          '*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'ja;ja-JP,q=0.9',
                'Priority': 'u=0, i',
                'Sec-Ch-Ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
            }
        )
        self.db = NovelDB()

        self.limit = limit
        self.retry = retry

        self.retry_count = 0

        self.book_id = book_id
        self.book_db_id = None
        self.source_unique_episode_id = source_unique_episode_id

        self.title = None
        self.author = None
        self.description = None
        self.menu = LinearMenu()

    async def send_retry(self, request: httpx.Request):
        result = None
        for i in range(self.retry):
            try:
                result = await self.client.send(request)
            except httpx.TimeoutException as e:
                print(f"Failed {request.method} {request.url} (Attempt #{i + 1}): Exception {e.__class__.__name__}")
            else:
                if result.is_success or result.has_redirect_location:
                    return result
                print(f"Failed {request.method} {request.url} (Attempt #{i + 1}): {result.reason_phrase}")
            if i + 1 != self.retry:
                self.retry_count += 1
                if self.progress is not None:
                    self.progress.set_postfix({"retry": self.retry_count})
                await trio.sleep(1)
        result.raise_for_status()

    async def get_retry(self, url, *args, **kwargs):
        return await self.send_retry(self.client.build_request("GET", url, *args, **kwargs))

    async def post_retry(self, url, *args, **kwargs):
        return await self.send_retry(self.client.build_request("POST", url, *args, **kwargs))

    @staticmethod
    def common_normalize(content: str):
        return (content
                .replace('\u309b', '\u3099')
                .replace('\u309c', '\u309a')
                .replace('\u301d', '\u3099')
                .replace('\uff9e', '\u3099')
                .replace('\uff9f', '\u309a')
                )

    @property
    def composite_source(self):
        return f"{self.source}:{self.book_id}"

    @property
    @abc.abstractmethod
    def source(self):
        pass

    @classmethod
    @abc.abstractmethod
    def sniff(cls, source) -> Tuple[int, str]:
        pass

    @classmethod
    def detect_source(cls, desc) -> Tuple[Type[Base], str]:
        Source = None
        source_id = ""

        if ':' in desc:
            name, source_id = desc.split(':', maxsplit=2)
            Source = cls.sources.get(name, None)

        if Source is None:
            (score, source_id), Source = max(((source.sniff(desc), source) for source in cls.sources.values()),
                                             key=lambda r: r[0][0])
            if score == 0:
                raise ValueError(f"Bad desc: {desc}, cannot find handler for it")

        return Source, source_id

    @abc.abstractmethod
    async def fetch_metadata(self):
        pass

    @abc.abstractmethod
    async def fetch_episode(self, episode: Episode):
        pass

    async def save_episode(self, episode: Episode):
        content = await self.fetch_episode(episode)
        content = self.common_normalize(content)

        self.db.add_episode(self.book_db_id, episode.id, episode.title, content, episode.version, episode.creation)
        self.progress.update()

    async def fetch(self):
        print(f"Loading metadata of book {self.composite_source}...")
        await self.fetch_metadata()

        print(f"Book {self.composite_source} metadata loaded.")
        print(f"《{self.title}》 by {self.author}.")

        episodes = self.menu.get_episodes()
        print(f"There are {len(episodes)} episodes.")

        book = self.db.find_book(self.book_id, self.source)

        if book is not None:
            old_data = json.loads(book.old_data)
            if self.title != book.title:
                create_or_append(old_data, "title", book.title)
            if self.author != book.author:
                create_or_append(old_data, "author", book.author)
            if self.description != book.description:
                create_or_append(old_data, "description", book.description)

            if self.source_unique_episode_id:
                # Only backup old menu when new menu will cause orphan episode:
                # (author removed some episodes)
                old_menu: LinearMenu = pickle.loads(book.menu)
                old_episodes = {episode.id for episode in old_menu.get_episodes()}
                different = old_episodes.difference(episode.id for episode in episodes)
                if different:
                    create_or_append(old_data, "menu", str(base64.b64encode(book.menu)))
                new_menu = pickle.dumps(self.menu)
            else:
                # episode id is not unique, be conservative
                new_menu = pickle.dumps(self.menu)
                if book.menu != new_menu:
                    create_or_append(old_data, "menu", str(base64.b64encode(book.menu)))
            self.db.update_book(book.id, self.title, self.author, self.description,
                                new_menu, json.dumps(old_data))

            self.book_db_id = book.id
            fetched = {meta.source_id: meta.version
                       for meta in self.db.findall_episode_meta(self.book_db_id)}
        else:
            self.book_db_id = self.db.add_book(self.book_id, self.source,
                                               self.title, self.author, self.description,
                                               pickle.dumps(self.menu))
            fetched = dict()

        episodes = [episode for episode in episodes
                    if episode.version != fetched.get(episode.id, -1)]

        print(f"There are {len(episodes)} new or updated episodes.")

        if episodes:
            with tqdm(desc="Fetching episodes", total=len(episodes), file=sys.stdout) as self.progress:
                async with trio.open_nursery() as nursery:
                    self.limiter = trio.CapacityLimiter(self.limit)
                    for episode in episodes:
                        nursery.start_soon(self.save_episode, episode)
            self.progress = None

        print(f"Book {self.composite_source} done.")
