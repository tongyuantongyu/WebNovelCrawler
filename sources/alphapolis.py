import copy
import re
import zoneinfo
from datetime import datetime

from bs4 import BeautifulSoup

from util import Chapter, Episode
from .base import Base
from .tools import *


class Alphapolis(Base):
    source = "alphapolis"
    zone = zoneinfo.ZoneInfo('Asia/Tokyo')
    p = BeautifulSoup('<p></p>', 'lxml').find('p')

    def __init__(self, book_id, limit=2, retry=3):
        super().__init__(book_id, limit, retry, source="alphapolis", source_unique_episode_id=True)

    confident_re = re.compile(r"(https?://)?www\.alphapolis\.co\.jp/novel/(?P<id>[0-9]{8,9}/[0-9]{8,9})/?")
    maybe_confident_re = re.compile(r"[0-9]{8,9}/[0-9]{8,9}")
    maybe_re = re.compile(r"[0-9]+/[0-9]+")

    @classmethod
    def sniff(cls, source):
        match = cls.confident_re.match(source)
        if match:
            return 10, match.group("id")
        match = cls.maybe_confident_re.search(source)
        if match:
            return 3, match[0]
        match = cls.maybe_re.search(source)
        if match:
            return 1, match[0]
        return 0, ""

    async def fetch_metadata(self):
        print(f"Loading metadata of book {self.book_id}...")
        page = await self.get_retry(f"https://www.alphapolis.co.jp/novel/{self.book_id}")
        content = BeautifulSoup(page.content, 'lxml')

        self.title = content.select_one('h1.title').text.strip()
        self.author = content.select_one('.author a').text.strip()
        self.description = content.select_one('.abstract').text.strip()

        menu_el = content.select_one('.episodes')
        assert menu_el is not None, "Can't find menu"
        for el in menu_el:
            match el:
                case Tag(name='h3', contents=[]):
                    pass
                case Tag(name='h3'):
                    self.menu.push_item(Chapter('', el.text.strip(), 1))
                case Tag(name='div', attrs={'class': ['episode']}):
                    episode_id = el.select_one('a')['href'].split('/')[-1]
                    update = el.select_one('.open-date').text.strip()
                    episode_title = el.select_one('.title').text.strip()
                    date = datetime.strptime(update, '%Y.%m.%d %H:%M')
                    version = int(date.replace(tzinfo=self.zone).timestamp())

                    # TODO: differ update time and creation time
                    self.menu.push_item(Episode(episode_id, episode_title, version, version))

    async def fetch_episode(self, episode: Episode):
        async with self.limiter:
            page = await self.get_retry(f"https://www.alphapolis.co.jp/novel/{self.book_id}/episode/{episode.id}")

        content = BeautifulSoup(page.content, "lxml")
        content = content.select_one("#novelBody")
        content.attrs = {'class': 'content'}

        # Rewrite to p-based formatting
        contents = []
        line = copy.copy(self.p)
        all_br = True
        for el in list(content):
            el = el.extract()
            if isinstance(el, NavigableString) and not el.strip():
                continue
            if isinstance(el, Tag) and el.name == 'br':
                if all_br:
                    line.append(el)
                else:
                    contents.append(line)
                    line = copy.copy(self.p)
                    all_br = True
            else:
                if all_br and line.contents:
                    line.attrs['class'] = 'blank'
                    contents.append(line)
                    line = copy.copy(self.p)
                if isinstance(el, NavigableString):
                    el = NavigableString(el.removeprefix('\n'))
                all_br = False
                line.append(el)
        if all_br:
            line.attrs['class'] = 'blank'
        if line.contents:
            contents.append(line)

        newlines = [NavigableString('\n') for _ in range(len(contents))]
        contents = [i for pair in zip(contents, newlines) for i in pair]
        content.clear(True)
        content.extend(contents)

        normalize_ruby_emphasis(content)

        content = content.decode()
        return content

