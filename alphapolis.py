# coding:utf-8

import requests
import itertools
from bs4 import BeautifulSoup
import os
from ebooklib import epub
import base64
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import asyncio
import aiohttp
import yomituki
import bs4

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
dirn = os.getcwd()
hd = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2486.0 Safari/537.36 Edge/13.10586'}
proxy = {}
paio = None
# proxy = {'http': 'http://[::1]:10002', 'https': 'https://[::1]:10002'}
# paio = 'http://[::1]:10002'
fullruby = True
threads = 2

css = '''@namespace h "http://www.w3.org/1999/xhtml";
body {
  display: block;
  margin: 5pt;
  page-break-before: always;
  text-align: justify;
}
h1, h2, h3 {
  font-weight: bold;
  margin-bottom: 1em;
  margin-left: 0;
  margin-right: 0;
  margin-top: 1em;
}
p {
  margin-bottom: 1em;
  margin-left: 0;
  margin-right: 0;
  margin-top: 1em;
}
a {
  color: inherit;
  text-decoration: inherit;
  cursor: default;
}
a[href] {
  color: blue;
  text-decoration: none;
  cursor: pointer;
}
a[href]:hover {
  color: red;
}
.center {
  text-align: center;
}
.cover {
  height: 100%;
}'''


def getpage(link):
    gethtml = requests.get(link, headers=hd, proxies=proxy, verify=False)
    return gethtml


def build_page(content, url):
    page = BeautifulSoup(content, 'lxml')
    subtitle = page.find('h2', class_="episode-title").get_text().replace('\n', '').replace('\t', '')
    content = page.find('div', id="novelBoby", class_="text")
    if fullruby:
        content = yomituki.ruby_div(content)
    else:
        content = content.prettify()
    html = '<html>\n<head>\n' + '<title>' + subtitle + '</title>\n</head>\n<body>\n<div>\n<h3>' + subtitle + '</h3>\n' + content + '</div>\n</body>\n</html>'
    name = url.split('/')[-1]
    built_page = epub.EpubHtml(title=subtitle, file_name=name + '.xhtml', content=html, lang='ja_jp')
    return name, built_page


def build_section(sec):
    head = epub.Section(sec[0])
    main = tuple(sec[1:])
    return head, main


async def load_page(url, session, semaphore):
    with await semaphore:
        async with session.get(url) as response:
            content = await response.read()
            # if b'<div class="dots-indicator" id="LoadingEpisode"></div>' in content:
            #     c = content.decode()
            #     offset1 = c.find("<script>\n        $('div#novelBoby').load('/novel/episode_body?episode=")
            #     offset2 = c.find("', {\n            'episode' : ")
            #     offset3 = c.find(",\n            'token' : '")
            #     load_link = "https://www.alphapolis.co.jp" + c[offset1 + 42: offset2] + "&token="
            #     print("[Debug]", load_link)
            #     load_link += c[offset3 + 25: offset3 + 57]
            #     async with session.get(load_link) as response2:
            #         content = await response2.read()
            print('[Coroutine] Fetch Task Finished for Link: ' + url)
    return url, content


class Novel_Alphapolis:
    def __init__(self, novel_id):
        self.id = novel_id
        self.book = epub.EpubBook()
        self.book.set_identifier(self.id)
        self.book.set_language('jp')
        self.book.spine = ['nav']

    def get_meta(self):
        print('[Main Thread] Fetching Metadata...')
        self.metapage_raw = getpage('https://www.alphapolis.co.jp/novel/' + self.id)
        self.metapage = BeautifulSoup(self.metapage_raw.content, 'lxml')
        self.novel_title = self.metapage.find('h2', class_="title").string[2:]
        self.author = self.metapage.find('div', class_='author').find('a').string
        self.about = self.metapage.find('div', class_='abstract').prettify()
        self.book.set_title(self.novel_title)
        self.book.add_author(self.author)
        self.book.add_metadata('DC', 'description', self.about)

    async def get_pages(self):
        print('[Main Thread] Fetching Pages...')
        self.menu_raw = self.metapage.find('div', class_='episodes')
        async with aiohttp.ClientSession(headers=hd) as session:
            await session.get('https://www.alphapolis.co.jp/novel/' + self.id)
            tasks = []
            semaphore = asyncio.Semaphore(threads)
            for element in self.menu_raw:
                try:
                    if element.name == 'div':
                        t = element.find('a')
                        url = 'https://www.alphapolis.co.jp' + t['href']
                        task = asyncio.ensure_future(load_page(url, session, semaphore))
                        tasks.append(task)
                except TypeError:
                    pass
            scheduled = asyncio.gather(*tasks)
            fetch_pages = await scheduled
            self.fetch_pages = {page[0]: page[1] for page in fetch_pages}

    def build_menu(self):
        print('[Main Thread] Building Menu...')
        self.menu = [['メニュー']]
        for element in self.menu_raw:
            try:
                if element.name == 'div':
                    url = 'https://www.alphapolis.co.jp' + element.find('a')['href']
                    title = element.find('span', class_='title').get_text()
                    filename, epub_page = build_page(self.fetch_pages[url], url)
                    self.book.add_item(epub_page)
                    self.book.spine.append(epub_page)
                    self.menu[-1].append(epub.Link(filename + '.xhtml', title, filename))
                elif element.name == 'h3':
                    title = element.string
                    if title:
                        if self.menu[-1] == ['メニュー']:
                            self.menu[-1] = [title]
                        else:
                            self.menu.append([title])
            except TypeError:
                pass
        self.book.toc = tuple([build_section(sec) for sec in self.menu])

    def post_process(self):
        self.book.add_item(epub.EpubNcx())
        self.book.add_item(epub.EpubNav())
        self.book.add_item(
                epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=css))

    def build_epub(self):
        print('[Main Thread] Building Book...')
        if len(self.novel_title) > 63:
            self.file_name = self.novel_title[:63]
        else:
            self.file_name = self.novel_title[:63]
        epub.write_epub(dirn + '\\' + self.file_name + '.epub', self.book, {})
        print('[Main Thread] Finished. File saved.')


if __name__ == '__main__':
    novel_id = input('[Initial] Input novel id here: ')
    syo = Novel_Alphapolis(novel_id)
    syo.get_meta()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(syo.get_pages())
    loop.close()
    syo.build_menu()
    syo.post_process()
    syo.build_epub()
