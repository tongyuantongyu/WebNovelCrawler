from typing import Type

import trio

import sources
from util import NovelDB
from .base import Base


class Update(Base):
    command = "update"
    description = "update all books by fetching new episodes"
    parametric = False

    def execute(self, _, _1):
        db = NovelDB()
        books = db.findall_book()

        for book in books:
            fetcher: sources.Base = sources.Base.sources[book.source](book.source_id)
            trio.run(fetcher.fetch)
