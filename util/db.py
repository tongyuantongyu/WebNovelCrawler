import functools
import sqlite3
from collections import namedtuple


@functools.cache
def cached_namedtuple(field_names):
    return namedtuple("Row", field_names)


def namedtuple_factory(cursor, row):
    fields = tuple(column[0] for column in cursor.description)
    cls = cached_namedtuple(fields)
    return cls._make(row)


class NovelDB:
    _db: sqlite3.Connection = None

    @classmethod
    def _get_db(cls):
        if cls._db is None:
            cls._db = sqlite3.connect("novel.db")
            cls._db.row_factory = namedtuple_factory

        return cls._db

    @property
    def db(self):
        return self._get_db()

    def __init__(self):
        self.cur = self.db.cursor()

    def vacuum(self):
        self.db.execute("VACUUM")

    # Book management

    def add_book(self, source_id, source, title, author, description, menu):
        self.cur.execute(
            "INSERT INTO "
            "book(source_id, source, title, author, description, menu, old_data)"
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (source_id, source, title, author, description, menu, "{}"))
        book_id = self.find_book_id(source_id, source)
        self.db.commit()
        return book_id

    def find_book_id(self, source_id, source):
        self.cur.execute("SELECT id FROM book WHERE source_id == ? AND source == ?",
                         (source_id, source))
        book = self.cur.fetchone()
        return None if book is None else book.id

    def find_book(self, source_id, source):
        self.cur.execute("SELECT * FROM book WHERE source_id == ? AND source == ?",
                         (source_id, source))
        book = self.cur.fetchone()
        return book

    def update_book(self, book_id, title, author, description, menu, old_data):
        self.cur.execute("UPDATE book "
                         "SET title = ?, author = ?, description = ?, menu = ?, old_data = ?"
                         "WHERE id == ?",
                         (title, author, description, menu, old_data, book_id))
        self.db.commit()

    def findall_book(self):
        self.cur.execute("SELECT source, source_id FROM book")
        books = self.cur.fetchall()
        return books

    # Episode management

    def add_episode(self, book_id, source_id, title, content, version, creation):
        self.cur.execute("UPDATE episode "
                         "SET latest = FALSE "
                         "WHERE book_id == ? AND source_id == ?",
                         (book_id, source_id))
        self.cur.execute("INSERT INTO "
                         "episode(book_id, source_id, title, content, version, creation, latest) "
                         "VALUES(?, ?, ?, ?, ?, ?, TRUE)",
                         (book_id, source_id, title, content, version, creation))
        self.db.commit()

    def findall_episode_meta(self, book_id):
        self.cur.execute("SELECT source_id, version FROM episode "
                         "WHERE book_id == ? AND latest == TRUE",
                         (book_id,))
        episodes = self.cur.fetchall()
        return episodes

    def findall_episode(self, book_id):
        self.cur.execute("SELECT * FROM episode WHERE book_id == ? AND latest == TRUE",
                         (book_id,))
        episodes = self.cur.fetchall()
        return episodes

    def find_episode(self, book_id, source_id):
        self.cur.execute("SELECT * FROM episode WHERE book_id == ? AND source_id == ? AND latest == TRUE",
                         (book_id, source_id))
        episode = self.cur.fetchone()
        return episode

    def findall_one_episode(self, book_id, source_id):
        self.cur.execute("SELECT * FROM episode WHERE book_id == ? AND source_id == ?",
                         (book_id, source_id))
        episodes = self.cur.fetchall()
        return episodes

    # Episode ruby management

    def add_rubified(self, book_id, source_id, title, content, version, creation):
        self.cur.execute("UPDATE episode_ruby "
                         "SET latest = FALSE "
                         "WHERE book_id == ? AND source_id == ?",
                         (book_id, source_id))
        self.cur.execute("INSERT INTO "
                         "episode_ruby(book_id, source_id, title, content, version, creation, latest) "
                         "VALUES(?, ?, ?, ?, ?, ?, TRUE)",
                         (book_id, source_id, title, content, version, creation))
        self.db.commit()

    def findall_rubified(self, book_id):
        self.cur.execute("SELECT * FROM episode_ruby WHERE book_id == ? AND latest == TRUE",
                         (book_id,))
        episodes = self.cur.fetchall()
        return episodes

    def findall_episode_rubified_stale(self, book_id):
        self.cur.execute("SELECT vanilla.source_id FROM "
                         "(SELECT * FROM episode WHERE book_id == ? AND latest == true) AS vanilla "
                         "LEFT JOIN "
                         "(SELECT * FROM episode_ruby WHERE book_id == ? AND latest == true) AS rubified "
                         "ON vanilla.source_id == rubified.source_id "
                         "WHERE rubified.version IS NULL OR vanilla.version > rubified.version"
                         , (book_id, book_id))
        episodes = self.cur.fetchall()
        return episodes
