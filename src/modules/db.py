from shutil import copy2
import sqlite3
from pathlib import Path
import appdirs
from meta import BUNDLE_IDENTIFIER, USING_TAURI_FRONTEND
import os

user_data_dir = Path(appdirs.user_data_dir(roaming=True))
if not user_data_dir.exists():
    print('warning: roaming app dir does not exist!')
    user_data_dir = Path.home()

class DatabaseConnection:
    OLD_OR_PY_DB_FILE = Path('music_caster.db').absolute()
    DEFAULT_DATABASE_FILE = (Path(user_data_dir) / BUNDLE_IDENTIFIER / 'music_caster.db').absolute()
    DATABASE_FILE = OLD_OR_PY_DB_FILE

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

    def move_to_new_location(self, db_path: str | None=None):
        if db_path is not None and USING_TAURI_FRONTEND:
            DatabaseConnection.DATABASE_FILE = Path(db_path).absolute()
        else:
            DatabaseConnection.DATABASE_FILE = DatabaseConnection.DEFAULT_DATABASE_FILE
        if DatabaseConnection.OLD_OR_PY_DB_FILE.exists():
            DatabaseConnection.DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
            if DatabaseConnection.DATABASE_FILE.exists():
                print('not moving database because file already exists')
            else:
                try:
                    os.rename(DatabaseConnection.OLD_OR_PY_DB_FILE, DatabaseConnection.DATABASE_FILE)
                except OSError as e:
                    if e.winerror == 17:
                        copy2(DatabaseConnection.OLD_OR_PY_DB_FILE, DatabaseConnection.DATABASE_FILE)
                        os.remove(DatabaseConnection.OLD_OR_PY_DB_FILE)
                    else:
                        raise e

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

class FileMetadata:
    @staticmethod
    def cleanup_db_table():
        with DatabaseConnection() as conn:
            tracks = conn.execute('SELECT file_path FROM file_metadata').fetchall()
            missing_dirs = set()
            to_delete = []

            for row in tracks:
                track = row['file_path']
                track_path = Path(track)

                # If the track is under a known-missing directory, skip filesystem check
                if any(track_path.is_relative_to(d) for d in missing_dirs):
                    to_delete.append(track)
                    continue

                if not track_path.exists():
                    to_delete.append(track)
                    parent = track_path.parent
                    if not parent.exists():
                        missing_dirs.add(parent)

            if to_delete:
                conn.executemany(
                    'DELETE FROM file_metadata WHERE file_path = ?',
                    [(t,) for t in to_delete]
                )
                conn.commit()

    _SAVE_SQL = '''INSERT OR REPLACE INTO file_metadata
              (file_path, title, artist, album, length, explicit, track_number, sort_key, time_modified)
              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)'''

    @staticmethod
    def _build_values(file_path, m: dict) -> tuple:
        length = m.get('length', 60)
        return (
            file_path,
            m['title'],
            m['artist'],
            m['album'],
            length,
            m['explicit'],
            m['track_number'],
            m['sort_key'],
            m['time_modified'],
        )

    @staticmethod
    def batch_save_to_db(file_metadata_list: list[dict], cur: sqlite3.Cursor):
        values = [
            FileMetadata._build_values(entry['file_path'], entry)
            for entry in file_metadata_list
        ]
        cur.executemany(FileMetadata._SAVE_SQL, values)

    @staticmethod
    def save_to_db(file_path, m: dict, cur: sqlite3.Cursor):
        cur.execute(FileMetadata._SAVE_SQL, FileMetadata._build_values(file_path, m))

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
