import json
import math
import re
from datetime import datetime

import httpx
import anyio
from bs4 import BeautifulSoup

from util import Chapter, Episode
from .base import Base
from .tools import *

query_metadata = """query GetWorkPage($workId: ID!) {
  work(id: $workId) {
    id
    title
    catchphrase
    introduction

    author {
      id
      activityName
    }

    tableOfContents {
      chapter {
        id
        title
        level
      }
      episodeUnions {
        ... on Episode {
          id
          title
          publishedAt
          editedAt
        }
      }
    }
  }
}"""


query_episodes = """query GetWorkPage($workId: ID!) {
  work(id: $workId) {
    tableOfContents {
      episodeUnions {
        ... on Episode {
          id
          bodyHTML
        }
      }
    }
  }
}"""


class Kakuyomu(Base):
    source = "kakuyomu"

    def __init__(self, book_id, limit=math.inf, tries=3):
        super().__init__(book_id, limit, tries, source_unique_episode_id=True)

        self.client.headers.update({"X-Requested-With": "XMLHttpRequest"})
        self.client.timeout = httpx.Timeout(60)
        self.episodes = {}
        self.episodes_loaded = None
        self.progress = None

    confident_re = re.compile(r"(https?://)?kakuyomu\.jp/works/(?P<id>[0-9]{19,20})/?")
    maybe_confident_re = re.compile(r"(168[0-9]{17})|(117[0-9]{16})")
    maybe_re = re.compile(r"[0-9]{19,20}")

    @classmethod
    def sniff(cls, source):
        match = cls.confident_re.match(source)
        if match:
            return 10, match.group("id")
        match = cls.maybe_confident_re.search(source)
        if match:
            return 5, match[0]
        match = cls.maybe_re.search(source)
        if match:
            return 1, match[0]
        return 0, ""

    async def load_episodes(self):
        if self.episodes_loaded is None:
            self.episodes_loaded = anyio.Event()
        else:
            await self.episodes_loaded.wait()
            return

        page = await self.post_retry("https://kakuyomu.jp/graphql?opname=GetWorkPage", json={
            "operationName": "GetWorkPage",
            "variables": {"workId": self.book_id},
            "query": query_episodes
        })

        data = json.loads(page.content)
        work = data['data']['work']
        for table in work['tableOfContents']:
            for episode in table['episodeUnions']:
                self.episodes[episode['id']] = episode['bodyHTML']

        self.episodes_loaded.set()

    async def fetch_metadata(self):
        page = await self.post_retry("https://kakuyomu.jp/graphql?opname=GetWorkPage", json={
            "operationName": "GetWorkPage",
            "variables": {"workId": self.book_id},
            "query": query_metadata
        })
        data = json.loads(page.content)

        work = data['data']['work']
        self.title = work['title']
        self.description = f"{work['catchphrase']}\n\n{work['introduction']}"
        self.author = work['author']['activityName']

        for table in work['tableOfContents']:
            if table['chapter'] is not None:
                chapter = table['chapter']
                self.menu.push_item(Chapter(chapter['id'], chapter['title'], chapter['level']))
            for episode in table['episodeUnions']:
                version = int(datetime.fromisoformat(episode['editedAt']).timestamp())
                creation = int(datetime.fromisoformat(episode['publishedAt']).timestamp())
                self.menu.push_item(Episode(episode['id'], episode['title'], version, creation))

    async def fetch_episode(self, episode: Episode):
        if not self.episodes:
            await self.load_episodes()

        content = BeautifulSoup(self.episodes[episode.id], 'lxml')
        content = content.select_one("body")
        content.name = 'div'
        content.attrs = {'class': 'content'}

        # clean id on <p>
        for p in content.select('p'):
            del p.attrs['id']

        # normalize emphasis
        for em in content.select('em.emphasisDots'):
            em.attrs = {'class': 'dot'}
            text = NavigableString(em.text.strip())
            em.clear(True)
            em.append(text)

        normalize_ruby_emphasis(content)

        content = content.decode()
        return content

