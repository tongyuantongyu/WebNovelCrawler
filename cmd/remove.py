from typing import Type

import sources
from util import NovelDB
from .base import Base


class Remove(Base):
    command = "remove"
    description = "remove book"
    parametric = True

    def execute(self, source: Type[sources.Base], source_id: str):
        db = NovelDB()
        book = db.find_book(source_id, source.source)

        db.remove_rubified(book.id)
        db.remove_episode(book.id)
        db.remove_book(book.id)

        print(f"Removed book 《{book.title}》 by {book.author} ({source.source}:{source_id}).")
