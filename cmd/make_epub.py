import os
import pickle
from abc import ABC
from typing import Type

import ebooklib.epub as epub

import sources
from util import NovelDB, LinearMenu, NChapter, Episode
from .base import Base

page_style = """
/**
p {
    line-height: 1.6em;
    margin: 0.4em 0;
}

p.blank {
    margin-bottom: -0.5em;
}
**/
em.dot {
    font-style: normal;
    text-emphasis: filled;
    -webkit-text-emphasis: filled;
    text-emphasis-position: over right;
    -webkit-text-emphasis-position: over right;
}
"""

page_css = epub.EpubItem(uid="page_style",
                         file_name="style/page.css",
                         media_type="text/css",
                         content=page_style.strip().encode())


def render_episode(episode):
    html = f"""
<h3>{episode.title}</h3>
{episode.content}
"""

    page = epub.EpubHtml(title=episode.title,
                         file_name=episode.source_id + '.xhtml',
                         content=html.encode(),
                         lang='ja')
    page.add_item(page_css)

    return page


class MakeEpubCommon(Base, ABC):
    parametric = True
    db_method = None
    target_folder = ""

    @classmethod
    def execute(cls, source: Type[sources.Base], source_id: str):
        book_id = f"{source.source}:{source_id}"

        db = NovelDB()
        book = db.find_book(source_id, source.source)
        linear_menu: LinearMenu = pickle.loads(book.menu)
        menu = linear_menu.build_menu()
        episodes = {i.source_id: i for i in cls.db_method(db, book.id)}

        ebook = epub.EpubBook()
        ebook.set_identifier(book_id)
        ebook.set_language('ja')
        ebook.spine = ['nav']
        ebook.set_title(book.title)
        ebook.add_author(book.author)
        ebook.add_metadata('DC', 'description', book.description)
        ebook.add_item(page_css)

        def build_item(item):
            if isinstance(item, Episode):
                page = render_episode(episodes[item.id])
                ebook.add_item(page)
                ebook.spine.append(page)
                return epub.Link(page.file_name, item.title, item.id)
            elif isinstance(item, NChapter):
                return epub.Section(item.title), [build_item(sub_item) for sub_item in item.items]

        ebook.toc = [build_item(item) for item in menu.items]
        ebook.add_item(epub.EpubNcx())
        ebook.add_item(epub.EpubNav())

        epub_file = book.title[:40]
        for char in "\\/?*:\"|<>":
            epub_file = epub_file.replace(char, '_')
        target = f"{cls.target_folder}/{epub_file}.epub"
        os.makedirs(cls.target_folder, exist_ok=True)
        epub.write_epub(target, ebook)
        print(f"Book {book_id} saved to {target}")


class MakeEpub(MakeEpubCommon):
    command = "epub"
    description = "build book EPUB"
    db_method = NovelDB.findall_episode
    target_folder = "epubfile"


class MakeEpubRuby(MakeEpubCommon):
    command = "epub_ruby"
    description = "build book EPUB use Rubified episode"
    db_method = NovelDB.findall_rubified
    target_folder = "epub_ruby_file"
