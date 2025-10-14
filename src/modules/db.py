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


CONCERT_SCHEMA = '''
CREATE TABLE IF NOT EXISTS concert_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist TEXT NOT NULL,
    event_name TEXT NOT NULL,
    venue TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT,
    country TEXT,
    date TEXT NOT NULL,
    url TEXT,
    last_checked REAL NOT NULL,
    UNIQUE(artist, event_name, venue, city, date)
);
'''

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


def save_metadata_batch(metadata_list, table_name='file_metadata', key_column='file_path'):
    """Batch insert or replace metadata records into the database."""
    if not metadata_list:
        return

    with DatabaseConnection() as conn:
        cur = conn.cursor()
        for i, (uri, metadata) in enumerate(metadata_list):
            values = [uri]
            values.extend((int(x) if isinstance(x, bool) else x for x in metadata.values()))
            columns = ','.join(metadata.keys())
            placeholders = ','.join('?' * len(values))
            sql = f'INSERT OR REPLACE INTO {table_name}({key_column},{columns}) VALUES({placeholders})'
            cur.execute(sql, values)

            if i % 20 == 0:
                conn.commit()
        conn.commit()


def get_url_metadata_from_db(conn, uri):
    cur = conn.cursor()
    result = cur.execute('SELECT * FROM url_metadata WHERE src = ?', (uri,)).fetchone()

    if not result:
        return None

    m = dict(result)
    m.pop('src', None)
    if 'live' in m:
        m['is_live'] = bool(m.pop('live'))

    return m


def init_db(reset=False):
    with DatabaseConnection() as connection:
        if reset:
            connection.executescript('DROP TABLE file_metadata;DROP TABLE url_metadata;DROP TABLE concert_events;')
        connection.executescript(CONCERT_SCHEMA + METADATA_SCHEMA)
        connection.commit()
