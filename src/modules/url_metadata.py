import time
from pathlib import Path
from typing import Self
from audio_player import AudioPlayer
import requests
import hashlib
import appdirs
from base64 import b64encode, b64decode
from utils import custom_art
import ujson as json
from utils import get_yt_id
from meta import BUNDLE_IDENTIFIER
from PIL import Image
from io import BytesIO

def tbr_audio_key(item):
    return (item.get('tbr', 0) or 0) * (item.get('vcodec', 'none') == 'none')

def tbr_video_key(item):
    return (item.get('height', 0) or 0), (item.get('tbr', 0) or 0)

def ydl_get_metadata(item, duration_helper=True):
    if 'formats' in item:
        audio_url = max(item['formats'], key=tbr_audio_key)['url']
        try:
            formats = [_f for _f in item['formats'] if _f.get('acodec') != 'none' and _f.get('vcodec') != 'none']
            selected_format = max(formats, key=tbr_video_key)
            ext, _url = selected_format['ext'], selected_format['url']
        except ValueError:
            # url is audio only
            ext, _url = item['ext'] if item['ext'] != 'unknown_video' else item['format_id'], audio_url
    else:
        ext = item['ext']
        _url = audio_url = item['url']
    if item.get('is_live', False) and 'duration' not in item and duration_helper:
        helper_ap = AudioPlayer()
        helper_ap.play(audio_url, False)
        item['duration'] = helper_ap.get_length()
    expiry_time = time.time() + max(1800, item.get('duration', 0))
    length = item['duration'] if item.get('duration', 0) else None
    src_url = item['webpage_url']
    split_url = src_url.rsplit('/', 2)
    backup_artist = split_url[-1] if split_url[-1] != '' else split_url[-2]
    artist = item.get('artist', item.get('uploader', backup_artist))
    album = item.get('album', item.get('playlist'))
    if album is None:
        album = item['extractor_key']
    album_cover_url = item.get('thumbnail')
    url_type = item.get('extractor_key', 'unknown')

    return URLMetadata(
        src=src_url,
        url=_url,
        title=item.get('track', item['title']),
        artist=artist,
        album=album,
        live=item.get('is_live', False),
        length=length,
        audio_url=audio_url,
        ext=ext,
        url_type=url_type,
        expiry=expiry_time,
        id=item['id'],
        album_cover_url=album_cover_url,
    )


class URLMetadata:
    __slots__ = ('title', 'artist', 'album', 'length', 'src', 'url', 'audio_url', 'ext', 'album_cover_url',
                 'expiry', 'id', 'playlist_url', 'type', 'live', 'timestamps')

    DB_COLUMNS = {'title', 'artist', 'album', 'length', 'url', 'audio_url', 'ext', 'art', 'expiry', 'id', 'pl_src', 'live', 'type'}
    MAPPED_FIELDS = {'url': 'src', 'ytid': 'id', 'is_live': 'live', 'art': 'album_cover_url'}
    FIELDS_TO_IGNORE = set()
    ALBUM_COVER_CACHE_DIR = Path(appdirs.user_cache_dir()) / BUNDLE_IDENTIFIER / 'Cache' / 'Album Covers'

    def __init__(self, src: str, url_type: str, title: str, artist: str, album: str, live: bool | None = None, length: float | None = None,
                 url: str | None = None, audio_url: str | None  = None, ext: str | None = None, expiry=None, id=None, album_cover_url=None,
                 timestamps: None | list = None, playlist_url=None):
        self.src = src
        # for displays
        self.url = url
        # for speakers
        self.audio_url = audio_url
        self.title = title
        self.artist = artist
        self.album = album
        self.length = length
        self.ext = ext
        self.album_cover_url = album_cover_url
        self.expiry = expiry
        self.id = id
        self.playlist_url = playlist_url
        self.type = url_type.lower()
        self.live = live
        self.timestamps = [] if timestamps is None else timestamps

    def __hash__(self) -> int:
        return int(self.hash(), 16)

    def __getitem__(self, key):
        if key == 'art_data':
            return self.get_cover_image()
        if key == 'ytid' and self.type == 'youtube':
            return self.id
        attr = self.MAPPED_FIELDS.get(key, key)
        if attr not in self.__slots__:
            raise KeyError(key)
        return getattr(self, attr, None)

    def __setitem__(self, key, value):
        if key == 'art_data':
            self.image_cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.image_cache_path, 'wb') as f:
                f.write(b64decode(value))
            return
        attr = self.MAPPED_FIELDS.get(key, key)
        if attr not in self.__slots__:
            raise KeyError(key)
        setattr(self, attr, value)

    def __delitem__(self, key):
        attr = self.MAPPED_FIELDS.get(key, key)
        if attr not in self.__slots__:
            raise KeyError(key)
        setattr(self, attr, None)

    def __iter__(self):
        return iter(self.__slots__)

    def __len__(self):
        return len(self.__slots__)

    def keys(self):
        return self.__slots__

    def values(self):
        return (getattr(self, attr, None) for attr in self.__slots__)

    def items(self):
        return ((attr, getattr(self, attr, None)) for attr in self.__slots__)

    def get(self, key, default=None):
        if key not in self.__slots__:
            return default
        return getattr(self, key, default)

    def save_to_db(self, cur):
        """Return SQL statement and values for database insertion."""
        sql = '''INSERT OR REPLACE INTO url_metadata
                 (src, title, artist, album, length, url, audio_url, ext, album_cover_url, expiry, id, type, playlist_url, live, timestamps)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''

        values = (
            self.src,
            self.title,
            self.artist,
            self.album,
            self.length,
            self.url,
            self.audio_url,
            self.ext,
            self.album_cover_url,
            self.expiry,
            self.id,
            self.type,
            self.playlist_url,
            int(self.live) if isinstance(self.live, bool) else self.live,
            json.dumps(self.timestamps, escape_forward_slashes=False)
        )
        cur.execute(sql, values)

    @classmethod
    def from_db(cls, conn, url) -> Self | None:
        cur = conn.cursor()
        ytid = get_yt_id(url)
        if ytid is not None and not ytid.startswith('PL'):
            url = f"https://www.youtube.com/watch?v={ytid}"
        result = cur.execute('SELECT * FROM url_metadata WHERE src = ?', (url,)).fetchone()
        if not result:
            return None

        row = dict(result)
        return cls(
            url=row['url'],
            title=row['title'],
            artist=row['artist'],
            album=row['album'],
            live=bool(row['live']),
            length=row['length'],
            audio_url=row['audio_url'],
            ext=row['ext'],
            url_type=row['type'],
            expiry=row['expiry'],
            id=row['id'],
            album_cover_url=row.get('art'),
            playlist_url=row.get('pl_src'),
            src=url,
            timestamps=json.loads(row.get('timestamps', '[]'))
        )

    @classmethod
    def from_dict(cls, data):
        """Create URLMetadata instance from dictionary."""
        metadata = data.copy()
        if 'live' in metadata:
            metadata['is_live'] = bool(metadata.pop('live'))
        return cls(**metadata)

    def hash(self) -> str:
        return hashlib.md5(self.src.encode('utf-8')).hexdigest()

    @property
    def image_cache_path(self):
        return self.ALBUM_COVER_CACHE_DIR / f'{self.hash()}.jpg'

    @property
    def is_expired(self):
        if self.expiry is None:
            return False
        return self.expiry < time.time()

    def get_cover_image(self) -> bytes:
        if not self.image_cache_path.exists():
            if not self.album_cover_url:
                return custom_art('URL')
            Image.open(BytesIO(requests.get(self.album_cover_url).content)).convert('RGB').save(self.image_cache_path, 'JPEG', quality=95)
        with open(self.image_cache_path, 'rb') as f:
            return b64encode(f.read())


# only run once to reduce OS calls
URLMetadata.ALBUM_COVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
