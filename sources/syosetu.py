import copy
from datetime import datetime
import re
import sys
import zoneinfo

import anyio
from bs4 import BeautifulSoup
from tqdm import tqdm

from util import Chapter, Episode
from .base import Base
from .tools import *


zygote = BeautifulSoup('<p></p>', 'lxml').find('p')


def make_tag(name):
    tag = copy.copy(zygote)
    tag.name = name
    return tag


class Syosetu(Base):
    source = "syosetu"
    zone = zoneinfo.ZoneInfo('Asia/Tokyo')

    def __init__(self, book_id, limit=2, tries=3):
        super().__init__(book_id, limit, tries, source_unique_episode_id=True)

        self.client.cookies.update({'over18': 'yes'})
        self.is_r18 = False

    confident_re = re.compile(r"(https?://)?(ncode|novel18)\.syosetu\.com/(?P<id>n[0-9]{4}[a-z]{1,2})/?")
    maybe_re = re.compile(r"n[0-9]{4}[a-z]{1,2}")

    @classmethod
    def sniff(cls, source):
        match = cls.confident_re.match(source)
        if match:
            return 10, match.group("id")
        match = cls.maybe_re.search(source)
        if match:
            return 5, match[0]
        return 0, ""

    @property
    def site(self):
        return "novel18" if self.is_r18 else "ncode"

    def incremental_parse_syosetu_menu(self, content: BeautifulSoup):
        menu_el = content.select_one('.p-eplist')
        assert menu_el is not None, "Can't find menu"
        for el in menu_el:
            match el:
                case Tag(attrs={'class': ['p-eplist__chapter-title']}):
                    self.menu.push_item(Chapter('', el.text, 1))
                case Tag(attrs={'class': ['p-eplist__sublist']}):
                    link = el.select_one('a')
                    create = el.select_one('.p-eplist__update').text.strip().removesuffix('（改）').strip()
                    update = el.select_one('.p-eplist__update span')
                    if update is not None:
                        update = update['title'].removesuffix(' 改稿')
                    else:
                        update = create

                    episode_id = link['href'].split('/')[2]
                    title = link.text.strip()
                    version = int(datetime.strptime(update, '%Y/%m/%d %H:%M').replace(tzinfo=self.zone).timestamp())
                    creation = int(datetime.strptime(create, '%Y/%m/%d %H:%M').replace(tzinfo=self.zone).timestamp())

                    self.menu.push_item(Episode(episode_id, title, version, creation))

    async def fetch_metadata_extra(self, page, recv: anyio.Event, send: anyio.Event):
        async with self.limiter:
            page = await self.get_retry(f"https://{self.site}.syosetu.com/{self.book_id}/?p={page}")
        content = BeautifulSoup(page.content, "lxml")

        await recv.wait()
        self.incremental_parse_syosetu_menu(content)
        self.progress.update()
        send.set()

    async def fetch_metadata(self):
        page = await self.get_retry(f"https://{self.site}.syosetu.com/{self.book_id}/")
        if page.has_redirect_location:
            assert "novel18" in page.next_request.url.host
            self.is_r18 = True
            print(f"R18 book detected.")
            page = await self.send_retry(page.next_request)

        assert page.is_success, "unexpected redirect"

        content = BeautifulSoup(page.content, "lxml")
        self.title = content.find('title').text.strip()  # <---
        self.author = content.select_one('meta[name="twitter:creator"]').attrs['content'].strip()
        self.description = content.select_one('#novel_ex').text.strip()
        self.incremental_parse_syosetu_menu(content)

        pager = content.select_one('.c-pager__pager')
        if pager is not None:
            last = pager.select_one('.c-pager__item--last')
            pages = int(last['href'].split('?p=')[-1])
            print(f"Multi page metadata with {pages} pages.")

            with tqdm(desc="Fetching metadata", total=pages, initial=1, file=sys.stdout) as self.progress:
                async with anyio.create_task_group() as tg:
                    recv = anyio.Event()
                    recv.set()
                    self.limiter = anyio.CapacityLimiter(self.limit)

                    for i in range(2, pages + 1):
                        send = anyio.Event()
                        tg.start_soon(self.fetch_metadata_extra, i, recv, send)
                        recv = send
            self.progress = None

    async def fetch_episode(self, episode: Episode):
        async with self.limiter:
            page = await self.get_retry(f"https://{self.site}.syosetu.com/{self.book_id}/{episode.id}/")

        content = BeautifulSoup(page.content, "lxml-xml")
        contents = content.select(".p-novel__text")
        if not contents:
            raise RuntimeError("Can't find content")
        content = contents[0]
        for extra in contents[1:]:
            separator = make_tag('p')
            separator.attrs = {'class': 'split'}
            separator.append(make_tag('hr'))
            content.append(separator)
            content.extend(extra)

        content.attrs = {'class': 'content'}

        # clean id on <p> and mark blank element
        for p in content.select('p'):
            if 'id' in p.attrs:
                del p.attrs['id']
            if all(isinstance(t, Tag) and t.name == 'br' for t in p):
                p.attrs['class'] = 'blank'

        normalize_ruby_emphasis(content)

        content = content.decode()
        return content
