import sqlite3
from pathlib import Path
import appdirs
from meta import BUNDLE_IDENTIFIER

user_data_dir = Path(appdirs.user_data_dir(roaming=True))
if not user_data_dir.exists():
    print('warning: roaming app dir does not exist!')
    user_data_dir = Path.home()

class DatabaseConnection:
    OLD_DATABASE_FILE = Path('music_caster.db').absolute()
    DEFAULT_DATABASE_FILE = (Path(user_data_dir) / BUNDLE_IDENTIFIER / 'music_caster.db').absolute()
    DATABASE_FILE = OLD_DATABASE_FILE

    @staticmethod
    def create_connection():
        conn = sqlite3.connect(DatabaseConnection.DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        return conn

    def __init__(self, db_override=None):
        if db_override is not None:
            self.DATABASE_FILE = db_override

    def __enter__(self):
        self.conn = self.create_connection()
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()


SCHEMA_2 = """
DROP TABLE IF EXISTS concert_events;
DROP TABLE IF EXISTS url_metadata;
CREATE TABLE IF NOT EXISTS url_metadata (
    src TEXT PRIMARY KEY NOT NULL,
    title TEXT,
    artist TEXT,
    album TEXT,
    length REAL,
    url TEXT,
    audio_url TEXT,
    ext TEXT,
    album_cover_url TEXT,
    expiry REAL,
    id TEXT,
    type TEXT,
    playlist_url TEXT,
    live BOOLEAN DEFAULT 0 NOT NULL CHECK (live IN (0, 1)),
    timestamps TEXT
);
"""

SCHEMA_1 = """
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
"""

MIGRATIONS = [SCHEMA_1, SCHEMA_2]


def init_db():
    RESET_DB = False
    with DatabaseConnection() as connection:
        current_version = connection.execute('PRAGMA user_version').fetchone()[0]

        if RESET_DB:
            connection.executescript(
                'DROP TABLE IF EXISTS file_metadata;DROP TABLE IF EXISTS url_metadata;DROP TABLE IF EXISTS concert_events;'
            )
            connection.executescript('PRAGMA user_version = 0;')
            current_version = 0

        for i, schema_migration in enumerate(MIGRATIONS):
            version = i + 1
            if current_version < version:
                connection.executescript(schema_migration)
                connection.execute(f'PRAGMA user_version = {version};')
        connection.commit()
