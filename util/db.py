import functools
import inspect
import sqlite3
from collections import namedtuple

import zstandard


@functools.cache
def cached_namedtuple(field_names):
    return namedtuple("Row", field_names)


def namedtuple_factory(cursor, row):
    fields = tuple(column[0] for column in cursor.description)
    cls = cached_namedtuple(fields)
    return cls._make(row)


_compress_dict: dict[str, str] = {
    "episode": "episode.dict",
    "episode_ruby": "episode_ruby.dict"
}
_compress_ctx: dict[str, zstandard.ZstdCompressor] = {}
_decompress_ctx: dict[str, zstandard.ZstdDecompressor] = {}
compression_level = 18


def zstd_compress(data: str, category: str):
    global _compress_ctx
    cctx = _compress_ctx.get(category)
    if cctx is None:
        with open(_compress_dict[category], "rb") as d:
            episode_dict = zstandard.ZstdCompressionDict(d.read())
        cctx = zstandard.ZstdCompressor(
            level=compression_level,
            dict_data=episode_dict,
            write_checksum=True,
            write_content_size=True,
            write_dict_id=True,
        )
        _compress_ctx[category] = cctx

    return cctx.compress(data.encode(encoding="utf-8"))


def zstd_decompress(data: bytes, category: str):
    global _decompress_ctx
    dctx = _decompress_ctx.get(category)
    if dctx is None:
        with open(_compress_dict[category], "rb") as d:
            episode_dict = zstandard.ZstdCompressionDict(d.read())
        dctx = zstandard.ZstdDecompressor(
            dict_data=episode_dict,
        )
        _decompress_ctx[category] = dctx

    return dctx.decompress(data).decode('utf-8')


def compress_content(category: str):
    def decorator(func):
        sign = inspect.signature(func)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            binded = sign.bind(*args, **kwargs)
            content = binded.arguments["content"]
            binded.arguments["content"] = zstd_compress(content, category)
            return func(*binded.args, **binded.kwargs)

        return wrapper

    return decorator


def decompress_content(category: str):
    def decorator(func):

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            def decompress_row(row):
                if row and hasattr(row, 'content') and row.content is not None:
                    # noinspection PyProtectedMember
                    return row._replace(content=zstd_decompress(row.content, category))
                return row

            result = func(*args, **kwargs)
            if result is None:
                return None
            if isinstance(result, list):
                return [decompress_row(r) for r in result]
            return decompress_row(result)

        return wrapper

    return decorator


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

    def remove_book(self, book_id):
        self.cur.execute("DELETE FROM book WHERE id == ?", (book_id,))
        self.db.commit()

    # Episode management

    @compress_content("episode")
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

    @decompress_content("episode")
    def findall_episode(self, book_id):
        self.cur.execute("SELECT * FROM episode WHERE book_id == ? AND latest == TRUE",
                         (book_id,))
        episodes = self.cur.fetchall()
        return episodes

    @decompress_content("episode")
    def find_episode(self, book_id, source_id):
        self.cur.execute("SELECT * FROM episode WHERE book_id == ? AND source_id == ? AND latest == TRUE",
                         (book_id, source_id))
        episode = self.cur.fetchone()
        return episode

    @decompress_content("episode")
    def findall_one_episode(self, book_id, source_id):
        self.cur.execute("SELECT * FROM episode WHERE book_id == ? AND source_id == ?",
                         (book_id, source_id))
        episodes = self.cur.fetchall()
        return episodes

    def remove_episode(self, book_id):
        self.cur.execute("DELETE FROM episode WHERE book_id == ?", (book_id,))
        self.db.commit()

    # Episode ruby management

    @compress_content("episode_ruby")
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

    @decompress_content("episode_ruby")
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

    def remove_rubified(self, book_id):
        self.cur.execute("DELETE FROM episode_ruby WHERE book_id == ?", (book_id,))
        self.db.commit()
