import sqlite3

from .base import Base


class Init(Base):
    command = "init"
    description = "init database"
    parametric = False

    def execute(self, _, _1):
        db = sqlite3.connect("novel.db")
        cur = db.cursor()

        cur.execute(
            """CREATE TABLE IF NOT EXISTS book(
                id INTEGER PRIMARY KEY,
                source_id TEXT,
                source TEXT,
                title TEXT,
                author TEXT,
                description TEXT,
                old_data TEXT,
                menu BLOB -- pickle
            )""")

        cur.execute("""CREATE INDEX IF NOT EXISTS book_id ON book(source_id, source)""")

        cur.execute(
            """CREATE TABLE IF NOT EXISTS episode(
                id INTEGER PRIMARY KEY,
                book_id INTEGER,
                source_id TEXT,
                title TEXT,
                content BLOB,
                version INTEGER, --date
                creation INTEGER, --date
                latest INTEGER,  --bool
                FOREIGN KEY(book_id) REFERENCES book(id)
            )""")

        cur.execute("""CREATE INDEX IF NOT EXISTS episode_book ON episode(book_id) WHERE (latest == TRUE)""")

        cur.execute(
            """CREATE TABLE IF NOT EXISTS episode_ruby(
                id INTEGER PRIMARY KEY,
                book_id INTEGER,
                source_id TEXT,
                title TEXT,
                content BLOB,
                version INTEGER, --date
                creation INTEGER, --date
                latest INTEGER,  --bool
                FOREIGN KEY(book_id) REFERENCES book(id)
            )""")

        cur.execute("""CREATE INDEX IF NOT EXISTS episode_ruby_book ON episode_ruby(book_id) WHERE (latest == TRUE)""")