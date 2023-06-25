import sqlite3
from pathlib import Path

DATABASE_FILE = Path('music_caster.db').absolute()


class DatabaseConnection:
    @staticmethod
    def create_connection():
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        return conn

    def __init__(self):
        pass

    def __enter__(self):
        self.conn = self.create_connection()
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()


METADATA_SCHEMA = '''
CREATE TABLE IF NOT EXISTS file_metadata (
    file_path TEXT PRIMARY KEY NOT NULL,
    title TEXT,
    artist TEXT,
    album TEXT,
    length INTEGER UNSIGNED,
    explicit BOOLEAN DEFAULT 0 NOT NULL CHECK (explicit IN (0, 1)),
    track_number INTEGER UNSIGNED DEFAULT 1 NOT NULL,
    sort_key TEXT DEFAULT file_path NOT NULL,
    time_modified REAL
);

CREATE TABLE IF NOT EXISTS url_metadata (
    src TEXT PRIMARY KEY NOT NULL, 
    title TEXT,
    artist TEXT,
    album TEXT,
    length REAL,
    url TEXT,
    audio_url TEXT,
    ext TEXT,
    art TEXT,
    expiry REAL,
    id TEXT,
    pl_src TEXT,
    live BOOLEAN DEFAULT 0 NOT NULL CHECK (live IN (0, 1))
);
'''


def init_db(reset=False):
    with DatabaseConnection() as connection:
        if reset:
            connection.executescript('DROP TABLE file_metadata;DROP TABLE url_metadata;')
        connection.executescript(METADATA_SCHEMA)
        connection.commit()
