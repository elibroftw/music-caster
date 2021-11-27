from deezer import TrackFormats  # 0.259 seconds because of requests
from b64_images import *
import base64
import audioop
from queue import LifoQueue, Empty
from contextlib import suppress
import ctypes
import ctypes.wintypes
import datetime
from functools import wraps, lru_cache
import glob
import io
from itertools import cycle, repeat, chain
import ujson as json
import locale
from math import floor, ceil
import os
from pathlib import Path
import platform
from random import getrandbits
import re
import socket
import time
from threading import Thread
import unicodedata
from urllib.parse import urlparse, parse_qs, urlencode
from uuid import getnode
import winreg as wr

# 3rd party imports
import pypresence
import deemix.utils.localpaths as __lp
__lp.musicdata = '/dz'
# without dz imports:
# helpers: 0.5212428569793701
# Done importing: 4.07397723197937
# with dz imports:
# helpers: 1.3634579181671143
# Done importing: 4.319329738616943
import mutagen
from mutagen import MutagenError
from mutagen.aac import AAC
import mutagen.flac
# noinspection PyProtectedMember
from mutagen.id3 import ID3NoHeaderError
# noinspection PyProtectedMember
from mutagen.mp3 import HeaderNotFoundError
import mutagen.mp4
from mutagen.easyid3 import EasyID3
from mutagen.easymp4 import EasyMP4
import pyaudio
import pyqrcode
import PySimpleGUI as Sg  # 0.11 seconds
from PIL import Image, ImageFile, ImageDraw, ImageFont
import requests
from wavinfo import WavInfoReader, WavInfoEOFError  # until mutagen supports .wav


# CONSTANTS
FONT_NORMAL = 'Segoe UI', 11
FONT_SMALL = 'Segoe UI', 10
FONT_LINK = 'Segoe UI', 11, 'underline'
FONT_TITLE = 'Segoe UI', 14
FONT_MID = 'Segoe UI', 12
FONT_TAB = 'Meiryo UI', 10
LINK_COLOR = '#3ea6ff'
COVER_MINI = (127, 127)
COVER_NORMAL = (255, 255)
PL_COMBO_W = 37
DECRYPT_TRACK = False
USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64; rv:12.0) Gecko/20100101 Firefox/591'
ImageFile.LOAD_TRUNCATED_IMAGES = True
SPOTIFY_API = 'https://api.spotify.com/v1'
# for stealing focus when bring window to front
keybd_event = ctypes.windll.user32.keybd_event
alt_key, extended_key, key_up = 0x12, 0x0001, 0x0002


class Shared:
    """
    variables in Shared are modified by music_caster.py
    """
    lang = ''
    track_format = '&title - &artist'
    PORT = 2001


class SystemAudioRecorder:

    __slots__ = 'STREAM_CHUNK', 'BITS_PER_SAMPLE', 'pa', 'sample_rate', 'channels', 'alive', 'data_stream', 'lag'

    def __init__(self):
        self.STREAM_CHUNK = 1024
        self.BITS_PER_SAMPLE = 16
        self.pa = None
        self.sample_rate = None
        self.channels = None
        self.alive = False
        self.lag = 0.0
        self.data_stream = LifoQueue()

    def get_audio_data(self, delay=0):
        if not self.alive: return  # ensure that start() was called
        silent_wav = b'\x00' * self.STREAM_CHUNK
        yield self.get_wav_header()
        yield silent_wav * delay * 1000
        last_sleep = time.time() + 1
        while self.alive:
            if self.lag and time.time() - last_sleep > 1:
                sleep_for = min(0.2, self.lag)  # sleep for max 0.2 seconds at a time
                self.lag -= sleep_for
                time.sleep(sleep_for)
                last_sleep = time.time()
            try:
                t1 = time.time()
                yield self.data_stream.get(timeout=0.09)
                t2 = time.time() - t1 - 0.05
                if t2 > 0:
                    # account for lag if chunk was recorded in late
                    self.lag = t2
                self.data_stream.task_done()
                # discard old data
                with suppress(Empty):
                    while True:
                        self.data_stream.get(False)
                        self.data_stream.task_done()
            except Empty:
                yield silent_wav

    def _start_recording(self):
        if self.alive: return
        self.alive = True
        selected_device = get_default_output_device()
        stream = self.create_stream(selected_device)
        for chunk in iter(lambda: audioop.mul(stream.read(self.STREAM_CHUNK), 2, 2) if self.alive else None, None):
            self.data_stream.put(chunk)
            default_output = get_default_output_device()  # check if output device has changed
            if selected_device != default_output:
                selected_device = default_output
                stream.close()
                stream = self.create_stream(selected_device)

    def create_stream(self, output_device):
        for i in range(self.pa.get_device_count()):
            device_info = self.pa.get_device_info_by_index(i)
            host_api_info = self.pa.get_host_api_info_by_index(device_info['hostApi'])
            if (host_api_info['name'] == 'Windows WASAPI' and device_info['maxOutputChannels'] > 0
                    and device_info['name'] == output_device):
                self.channels = min(device_info['maxOutputChannels'], 2)
                self.sample_rate = int(device_info['defaultSampleRate'])  # e.g. 48,000 bits
                return self.pa.open(format=pyaudio.paInt16, input=True, as_loopback=True, channels=self.channels,
                                    input_device_index=device_info['index'], rate=self.sample_rate,
                                    frames_per_buffer=self.STREAM_CHUNK)
        raise RuntimeError('Default Output Device Not Found')

    def get_wav_header(self):
        data_size = 2000 * 10 ** 6
        o = bytes('RIFF', 'ascii')  # 4 bytes Marks file as RIFF
        o += (data_size + 36).to_bytes(4, 'little')  # (4 bytes) File size in bytes excluding this and RIFF marker
        o += bytes('WAVE', 'ascii')  # 4 bytes File type
        o += bytes('fmt ', 'ascii')  # 4 bytes Format Chunk Marker
        o += (16).to_bytes(4, 'little')  # 4 bytes Length of above format data
        o += (1).to_bytes(2, 'little')  # 2 bytes Format type (1 - PCM)
        o += self.channels.to_bytes(2, 'little')  # 2 bytes
        o += self.sample_rate.to_bytes(4, 'little')  # 4 bytes
        o += (self.sample_rate * self.channels * self.BITS_PER_SAMPLE // 8).to_bytes(4, 'little')  # 4 bytes
        o += (self.channels * self.BITS_PER_SAMPLE // 8).to_bytes(2, 'little')  # 2 bytes
        o += self.BITS_PER_SAMPLE.to_bytes(2, 'little')  # 2 bytes
        o += bytes('data', 'ascii')  # 4 bytes Data Chunk Marker
        o += data_size.to_bytes(4, 'little')  # 4 bytes Data size in bytes
        return o

    def stop(self):
        self.alive = False

    def start(self):
        if not self.alive:
            if self.pa is None: self.pa = pyaudio.PyAudio()
            # initialization process takes ~0.2 seconds
            Thread(target=self._start_recording, name='SystemAudioRecorder', daemon=True).start()


class InvalidAudioFile(Exception): pass


class PlayingStatus:
    __slots__ = 'NOT_PLAYING', 'PLAYING', 'PAUSED', 'BUSY', 'state'

    def __init__(self):
        self.NOT_PLAYING = 0
        self.PLAYING = 1
        self.PAUSED = 2
        self.BUSY = {self.PLAYING, self.PAUSED}
        self.state = self.NOT_PLAYING

    def busy(self):
        return self.state in self.BUSY

    def stopped(self):
        return self.state == self.NOT_PLAYING

    def playing(self):
        return self.state == self.PLAYING

    def paused(self):
        return self.state == self.PAUSED

    def stop(self):
        self.state = self.NOT_PLAYING

    def play(self):
        self.state = self.PLAYING

    def pause(self):
        self.state = self.PAUSED

    def __repr__(self):
        return {0: 'NOT PLAYING', 1: 'PLAYING', 2: 'PAUSED'}[self.state]

    def __eq__(self, other):
        if not isinstance(other, PlayingStatus): return str(other) == str(self)
        return other.state == self.state


class Unknown(str):
    __slots__ = 'property'

    def __new__(cls, _property):
        obj = super(Unknown, cls).__new__(cls)
        obj.property = _property
        return obj

    def __repr__(self):
        return gt(f'Unknown {self.property}')

    def __str__(self):
        return self.__repr__()

    def __lt__(self, other):
        return str(self).__lt__(other)

    def __le__(self, other):
        return str(self).__le__(other)

    def __gt__(self, other):
        return str(self).__gt__(other)

    def __ge__(self, other):
        return str(self).__ge__(other)

    def __eq__(self, other):
        return str(other) == str(self)

    def __ne__(self, other):
        return not self.__eq__(str(other))

    def split(self, *args, **kwargs):
        return str(self).split(*args, **kwargs)

    def __len__(self):
        return len(str(self))


class DiscordPresence:
    """
    Exception safe wrapper for pypresence
    """
    rich_presence: pypresence.Presence = None
    MUSIC_CASTER_DISCORD_ID = '696092874902863932'

    @classmethod
    def set_rich_presence(cls):
        if cls.rich_presence is None:
            with suppress(Exception):
                cls.rich_presence = pypresence.Presence()

    @classmethod
    def connect(cls, confirm_connect=True):
        if confirm_connect:
            cls.set_rich_presence()
            with suppress(Exception):
                cls.rich_presence.connect()

    @classmethod
    def update(cls, confirm_connect=True, state: str = None, details: str = None, large_text: str = None,
               large_image='default', small_image='logo', small_text='Music Caster'):
        if confirm_connect:
            cls.set_rich_presence()
            with suppress(Exception):
                cls.rich_presence.update(state=state, details=details, large_image=large_image, large_text=large_text,
                                         small_image=small_image, small_text=small_text)

    @classmethod
    def clear(cls, confirm=True):
        if confirm:
            with suppress(Exception):
                cls.rich_presence.clear()

    @classmethod
    def close(cls):
        with suppress(Exception):
            cls.rich_presence.close()


def get_file_name(file_path): return Path(file_path).stem


# decorators
def timing(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        _start = time.monotonic()
        result = f(*args, **kwargs)
        print(f'@timing {f.__name__} = {result} ELAPSED TIME:', time.monotonic() - _start)
        return result
    return wrapper


def time_cache(max_age, maxsize=None, typed=False):
    """Least-recently-used cache decorator with time-based cache invalidation.
    max_age: Time to live for cached results (in seconds).
    maxsize: Maximum cache size (see `functools.lru_cache`).
    typed: Cache on distinct input types (see `functools.lru_cache`)."""
    def _decorator(fn):
        @lru_cache(maxsize=maxsize, typed=typed)
        def _new(*args, __time_salt, **kwargs):
            return fn(*args, **kwargs)

        @wraps(fn)
        def _wrapped(*args, **kwargs):
            return _new(*args, **kwargs, __time_salt=int(time.time() / max_age))
        return _wrapped
    return _decorator


@lru_cache(maxsize=1)
def get_languages():
    return list(chain([''], (get_file_name(lang) for lang in glob.iglob('languages/*.txt'))))


@lru_cache(maxsize=3)
def get_lang_pack(lang):
    lang_pack = {} if lang == 'en' else []
    with suppress(FileNotFoundError):
        with open(f'languages/{lang}.txt', encoding='utf-8') as f:
            i = 0
            line = f.readline().strip()
            while line:
                if not line.startswith('#'):
                    try: lang_pack[line] = i
                    except TypeError: lang_pack.append(line)
                    i += 1
                line = f.readline().strip()
    return lang_pack


def get_display_lang():
    windll = ctypes.windll.kernel32
    return locale.windows_locale[windll.GetUserDefaultUILanguage()].split('_')[0]


def get_translation(string, lang='', as_title=False):
    """ Translates string from English to lang or display language if valid
    :param string: English string
    :param lang: Optional code to translate to. Defaults to using display language
    :param as_title: The phrase returned has each word capitalized
    :return: string translated to display language """
    with suppress(IndexError, KeyError):
        string = get_lang_pack(lang or get_display_lang())[get_lang_pack('en')[string]]
    if as_title: string = ' '.join(word[0].upper() + word[1:] for word in string.split())
    return string


def gt(string, as_title=False):
    return get_translation(string, lang=Shared.lang, as_title=as_title)


def get_length(file_path) -> int:
    """ throws InvalidAudioFile if file is invalid
    :param file_path:
    :return: length in seconds """
    try:
        if file_path.lower().endswith('.wav'):
            a = WavInfoReader(file_path)
            length = a.data.frame_count / a.fmt.sample_rate
        elif file_path.lower().endswith('.wma'):
            try:
                audio_info = mutagen.File(file_path).info
                length = audio_info.length
            except AttributeError:
                audio_info = AAC(file_path).info
                length = audio_info.length
        elif file_path.lower().endswith('.opus'):
            audio_info = mutagen.File(file_path).info
            length = audio_info.length
        else:
            audio_info = mutagen.File(file_path).info
            length = audio_info.length
        return length
    except (AttributeError, HeaderNotFoundError, MutagenError, WavInfoEOFError, StopIteration) as e:
        raise InvalidAudioFile(f'{file_path} is an invalid audio file') from e


def natural_key_file(file_name):
    file_name = unicodedata.normalize('NFKD', get_file_name(file_name).lower())
    file_name = u''.join([c for c in file_name if not unicodedata.combining(c)])
    return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', file_name)]


def valid_color_code(code):
    match = re.search(r'^#(?:[0-9a-fA-F]{3}){1,2}$', code)
    return match


def set_metadata(file_path: str, metadata: dict):
    ext = os.path.splitext(file_path)[1].lower()
    audio = mutagen.File(file_path)
    title = metadata['title']
    artists = metadata['artist'].split(', ') if ', ' in metadata['artist'] else metadata['artist'].split(',')
    album = metadata['album']
    track_place = metadata['track_number']      # X/Y
    track_number = track_place.split('/')[0]    # X
    rating = '1' if metadata['explicit'] else '0'
    if '/' not in track_place:
        tracks = max(1, int(track_place))
        track_place = f'{track_place}/{tracks}'
    if ext in {'.mp3', '.wav'}:
        if title:
            audio['TIT2'] = mutagen.id3.TIT2(text=metadata['title'])
        if artists:
            audio['TPE1'] = mutagen.id3.TPE1(text=artists)
            audio['TPE2'] = mutagen.id3.TPE1(text=artists[0])  # album artist
        audio['TCMP'] = mutagen.id3.TCMP(text=track_number)
        audio['TRCK'] = mutagen.id3.TRCK(text=track_place)
        audio['TPOS'] = mutagen.id3.TPOS(text=track_place)
        if album:
            audio['TALB'] = mutagen.id3.TALB(text=album)
        # audio['TDRC'] = mutagen.id3.TDRC(text=metadata['year'])
        # audio['TCON'] = mutagen.id3.TCON(text=metadata['genre'])
        # audio['TPUB'] = mutagen.id3.TPUB(text=metadata['publisher'])
        audio['TXXX:RATING'] = mutagen.id3.TXXX(text=rating, desc='RATING')
        audio['TXXX:ITUNESADVISORY'] = mutagen.id3.TXXX(text=rating, desc='ITUNESADVISORY')
        if metadata['art'] is not None:
            img_data = b64decode(metadata['art'])
            audio['APIC:'] = mutagen.id3.APIC(encoding=0, mime=metadata['mime'], type=3, data=img_data)
        else:  # remove all album art
            for k in tuple(audio.keys()):
                if 'APIC:' in k: audio.pop(k)
    elif ext in {'.mp4', '.m4a', '.aac'}:
        if title: audio['@nam'] = [title]
        if artists: audio['@ART'] = artists
        if album: audio['@alb'] = [album]
        audio['trkn'] = tuple((int(x) for x in track_place.split('/')))
        audio['rtng'] = [rating]
        if metadata['art'] is not None:
            image_format = 14 if metadata['mime'].endswith('png') else 13
            img_data = b64decode(metadata['art'])
            audio['covr'] = [mutagen.mp4.MP4Cover(img_data, imageformat=image_format)]
        elif 'covr' in audio:
            del audio['covr']
    else:  # FLAC?
        if title: audio['TITLE'] = title
        if artists: audio['ARTIST'] = artists
        if album: audio['ALBUM'] = album
        audio['TRACKNUMBER'] = track_number
        audio['TRACKTOTAL'] = track_place.split('/')[1]
        audio['ITUNESADVISORY'] = rating
        if metadata['art'] is not None:
            if ext == '.flac':
                img_data = b64decode(metadata['art'])
                pic = mutagen.flac.Picture()
                pic.mime = metadata['mime']
                pic.data = img_data
                pic.type = 3
                # noinspection PyUnresolvedReferences
                audio.add_picture(pic)
            else:
                img_data = b64decode(metadata['art'])
                audio['APIC:'] = img_data
                audio['mime'] = metadata['mime']
        else:
            if ext == '.flac':
                # noinspection PyUnresolvedReferences
                audio.clear_pictures()
            else:
                # remove all album art
                for k in tuple(audio.keys()):
                    if 'APIC:' in k: audio.pop(k)
    audio.save()


def get_metadata(file_path: str):
    file_path = file_path.lower()
    unknown_title, unknown_artist, unknown_album = Unknown('Title'), Unknown('Artist'), Unknown('Album')
    title, artist, album = unknown_title, unknown_artist, unknown_album
    try:
        if file_path.endswith('.mp3'):
            audio = dict(EasyID3(file_path))
            _audio = mutagen.File(file_path)
            audio['rating'] = _audio.get('TXXX:RATING', _audio.get('TXXX:ITUNESADVISORY', ['0']))
        elif file_path.endswith('.m4a') or file_path.endswith('.mp4'):
            audio = EasyMP4(file_path)
            _audio = mutagen.File(file_path)
            audio['rating'] = _audio.get('rtng', ['0'])
        elif file_path.endswith('.wav'):
            a = WavInfoReader(file_path).info.to_dict()
            audio = {'title': [a['title']], 'artist': [a['artist']], 'album': [a['product']]}
        else:
            audio = dict(mutagen.File(file_path))
            audio = {k.lower(): audio[k] for k in audio}
            if file_path.endswith('.wma'):
                audio = {k: [audio[k][0].value] for k in audio}
    except (ID3NoHeaderError, HeaderNotFoundError, AttributeError, WavInfoEOFError, StopIteration):
        audio = {}
    title = audio.get('title', [title])[0]
    album = audio.get('album', [album])[0]
    try:
        is_explicit = audio.get('rating', audio.get('itunesadvisory', ['0']))[0] not in {'C', 'T', '0', 0}
    except IndexError:
        is_explicit = False
    track_number = str(audio['tracknumber'][0]).split('/', 1)[0] if 'tracknumber' in audio else None
    with suppress(KeyError, TypeError):
        if len(audio['artist']) == 1:
            # in case the sep char is a slash
            try:
                audio['artist'] = audio['artist'][0].split('/')
            except AttributeError:
                audio['artist'] = [unknown_artist]
        artist = ', '.join(audio['artist'])
    if not title: title = unknown_title
    if not artist: artist = unknown_artist
    if not album: album = unknown_album
    if title == unknown_title or artist == unknown_artist:
        # if title or artist are unknown, use the basename of the URI (excluding extension)
        sort_key = get_file_name(file_path)
    else:
        sort_key = Shared.track_format.replace('&title', title).replace('&artist', artist)
        sort_key.replace('&album', album if album != unknown_album else '')
        sort_key = sort_key.replace('&trck', track_number or '')
    metadata = {'title': title, 'artist': artist, 'album': album, 'explicit': is_explicit, 'sort_key': sort_key.lower(),
                'track_number': '0' if track_number is None else track_number}
    return metadata


def get_album_art(file_path: str, folder_cover_override=False) -> tuple:  # mime: str, data: str
    with suppress(MutagenError):
        folder = os.path.dirname(file_path)
        if folder_cover_override:
            for ext in ('png', 'jpg', 'jpeg'):
                folder_cover = os.path.join(folder, f'cover.{ext}')
                if os.path.exists(folder_cover):
                    with open(folder_cover, 'rb') as f:
                        return ext, base64.b64encode(f.read())
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.flac':
            pics = mutagen.flac.FLAC(file_path).pictures
            with suppress(IndexError): return pics[0].mime, base64.b64encode(pics[0].data).decode()
        elif ext in {'.mp4', '.m4a', '.aac'}:
            with suppress(KeyError, IndexError):
                cover = mutagen.File(file_path)['covr'][0]
                image_format = cover.imageformat
                mime = 'image/png' if image_format == 14 else 'image/jpeg'
                return mime, base64.b64encode(cover).decode()
        else:
            tags = mutagen.File(file_path)
            if tags is not None:
                for tag in tags.keys():
                    if 'APIC' in tag:
                        try:
                            return tags[tag].mime, base64.b64encode(tags[tag].data).decode()
                        except AttributeError:
                            mime = tags['mime'][0].value if 'mime' in tags else 'image/jpeg'
                            return mime, base64.b64encode(tags[tag][0].value).decode()
    return 'image/jpeg', DEFAULT_ART


def fix_path(path, by_os=True): return str(Path(path)) if by_os else Path(path).as_posix()


def get_first_artist(artists: str) -> str: return artists.split(', ', 1)[0]


def get_ipv6():
    return f'[{next((i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None) if i[0] == socket.AF_INET6))}]'


def get_ipv4():
    return next((i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None) if i[0] == socket.AF_INET))


def get_lan_ip() -> str:
    try:
        return get_ipv6()
    except StopIteration:
        # return IPv4 if IPv6 is unavailable
        return get_ipv4()


def get_mac(): return ':'.join(['{:02x}'.format((getnode() >> ele) & 0xff) for ele in range(0, 8 * 6, 8)][::-1])


def better_shuffle(seq, first=0, last=-1):
    """
    Shuffles based on indices
    """
    n = len(seq)
    with suppress(IndexError, ZeroDivisionError):
        first = first % n
        last = last % n
        # use Fisher-Yates shuffle (Durstenfeld method)
        for i in range(first, last + 1):
            size = last - i + 1
            j = getrandbits(size.bit_length()) % size + i
            seq[i], seq[j] = seq[j], seq[i]
        return seq


def create_qr_code():
    try:
        qr_code = pyqrcode.create(f'http://{get_lan_ip()}:{Shared.PORT}')
        return qr_code.png_as_base64_str(scale=3, module_color=(255, 255, 255, 255), background=(18, 18, 18, 255))
    except OSError:
        # Failed?
        return None


def valid_audio_file(uri) -> bool:
    """
    check if uri has a valid audio extension
    uri does not have to be a file that exists
    """
    ext = os.path.splitext(os.path.basename(uri))[1].lower()
    return ext in {'.mp3', '.flac', '.m4a', '.mp4', '.aac', '.mpeg', '.ogg', '.opus', '.wma', '.wav'}


@lru_cache(maxsize=1)
def dz():
    from deemix.__main__ import Deezer  # 1.4 seconds. 0.4 due to Downloader
    return Deezer()


@lru_cache(maxsize=2)
def ydl(proxy=None):
    from youtube_dl import YoutubeDL  # 2 seconds!
    return YoutubeDL() if proxy is None else YoutubeDL({'proxy': proxy})


def ydl_extract_info(url):
    """
    Raises IOError instead of YoutubeDL's DownloadError, saving us time on imports
    """
    from youtube_dl.utils import DownloadError
    with suppress(DownloadError):
        return ydl().extract_info(url, download=False)
    try:
        return ydl(get_proxy(False)['https']).extract_info(url, download=False)
    except DownloadError as e:
        raise IOError from e


# noinspection PyTypeChecker
def get_yt_id(url, ignore_playlist=False):
    query = urlparse(url)
    if query.hostname == 'youtu.be': return query.path[1:]
    if query.hostname in {'www.youtube.com', 'youtube.com', 'music.youtube.com'}:
        if not ignore_playlist:
            with suppress(KeyError):
                return parse_qs(query.query)['list'][0]
        if query.path == '/watch': return parse_qs(query.query)['v'][0]
        if query.path[:7] == '/watch/': return query.path.split('/')[1]
        if query.path[:7] == '/embed/': return query.path.split('/')[2]
        if query.path[:3] == '/v/': return query.path.split('/')[2]


def get_yt_urls(video_id):
    """
    Returns possible youtube URL's for a single video id
    """
    yield f'https://youtu.be/{video_id}'
    for prefix in ('https://', 'https://www.'):
        yield f'{prefix}youtube.com/watch?v={video_id}'
        yield f'{prefix}youtube.com/watch/{video_id}'
        yield f'{prefix}youtube.com/embed/{video_id}'
        yield f'{prefix}youtube.com/v/{video_id}'


def is_os_64bit(): return platform.machine().endswith('64')


def delete_sub_key(root, current_key):
    access = wr.KEY_ALL_ACCESS | wr.KEY_WOW64_64KEY if is_os_64bit() else wr.KEY_ALL_ACCESS
    with suppress(FileNotFoundError):
        with wr.OpenKeyEx(root, current_key, 0, access) as parent_key:
            info_key = wr.QueryInfoKey(parent_key)
            for x in range(info_key[0]):
                sub_key = wr.EnumKey(parent_key, 0)
                try: wr.DeleteKeyEx(parent_key, sub_key, access)
                except OSError: delete_sub_key(root, '\\'.join([current_key, sub_key]))
            wr.DeleteKeyEx(parent_key, '', access)


def add_reg_handlers(path_to_exe, add_folder_context=True):
    """ Register Music Caster as a program to open audio files and folders """
    # https://docs.microsoft.com/en-us/visualstudio/extensibility/registering-verbs-for-file-name-extensions?view=vs-2019
    path_to_exe = path_to_exe.replace('/', '\\')
    classes_path = 'SOFTWARE\\Classes\\'
    mc_file = 'MusicCaster_file'
    write_access = wr.KEY_WRITE | wr.KEY_WOW64_64KEY if is_os_64bit() else wr.KEY_WRITE
    read_access = wr.KEY_READ | wr.KEY_WOW64_64KEY if is_os_64bit() else wr.KEY_READ
    # create URL protocol handler
    url_protocol = f'{classes_path}music-caster'
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, url_protocol, 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, 'URL:music-caster Protocol')
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, url_protocol, 0, write_access) as key:
        wr.SetValueEx(key, 'URL Protocol', 0, wr.REG_SZ, '')
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, fr'{url_protocol}\DefaultIcon', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}"')
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, fr'{url_protocol}\shell\open\command', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" --urlprotocol "%1"')

    # create Audio File type
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{classes_path}{mc_file}', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, 'Audio File')
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{classes_path}{mc_file}\\DefaultIcon', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, path_to_exe)  # define icon location

    # create play context | open handler
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{classes_path}{mc_file}\\shell\\open', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, gt('Play with Music Caster'))
        wr.SetValueEx(key, 'MultiSelectModel', 0, wr.REG_SZ, 'Player')
        wr.SetValueEx(key, 'Icon', 0, wr.REG_SZ, path_to_exe)
    command_path = f'{classes_path}{mc_file}\\shell\\open\\command'
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, command_path, 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" "%1"')

    # create queue context
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{classes_path}{mc_file}\\shell\\queue', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, gt('Queue in Music Caster'))
        wr.SetValueEx(key, 'MultiSelectModel', 0, wr.REG_SZ, 'Player')
        wr.SetValueEx(key, 'Icon', 0, wr.REG_SZ, path_to_exe)
    command_path = f'{classes_path}{mc_file}\\shell\\queue\\command'
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, command_path, 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" -q "%1"')

    # create play next context
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{classes_path}{mc_file}\\shell\\play_next', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, gt('Play next in Music Caster'))
        wr.SetValueEx(key, 'MultiSelectModel', 0, wr.REG_SZ, 'Player')
        wr.SetValueEx(key, 'Icon', 0, wr.REG_SZ, path_to_exe)
    command_path = f'{classes_path}{mc_file}\\shell\\play_next\\command'
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, command_path, 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" -n "%1"')

    # set file handlers
    for ext in {'mp3', 'flac', 'm4a', 'aac', 'ogg', 'opus', 'wma', 'wav', 'mpeg', 'm3u', 'm3u8'}:
        key_path = f'{classes_path}.{ext}'
        try:  # check if key exists
            with wr.OpenKeyEx(wr.HKEY_CURRENT_USER, key_path, 0, read_access) as _: pass
        except (WindowsError, FileNotFoundError):
            # create key for extension if it does not exist with MC as the default program
            with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, key_path, 0, write_access) as key:
                # set as default program unless .mp4 because that's a video format
                wr.SetValueEx(key, None, 0, wr.REG_SZ, mc_file)
        # add to Open With (prompts user to set default program when they try playing a file)
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{key_path}\\OpenWithProgids', 0, write_access) as key:
            # noinspection PyTypeChecker
            wr.SetValueEx(key, mc_file, 0, wr.REG_NONE, b'')  # type needs to be bytes

    play_folder_key_path = f'{classes_path}\\Directory\\shell\\MusicCasterPlayFolder'
    queue_folder_key_path = f'{classes_path}\\Directory\\shell\\MusicCasterQueueFolder'
    play_next_folder_key_path = f'{classes_path}\\Directory\\shell\\MusicCasterPlayNextFolder'
    if add_folder_context:
        # set "open folder in Music Caster" command
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, play_folder_key_path, 0, write_access) as key:
            wr.SetValueEx(key, None, 0, wr.REG_SZ, gt('Play with Music Caster'))
            wr.SetValueEx(key, 'Icon', 0, wr.REG_SZ, path_to_exe)
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{play_folder_key_path}\\command', 0, write_access) as key:
            wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" "%1"')
        # set "queue folder in Music Caster" command
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, queue_folder_key_path, 0, write_access) as key:
            wr.SetValueEx(key, None, 0, wr.REG_SZ, gt('Queue in Music Caster'))
            wr.SetValueEx(key, 'Icon', 0, wr.REG_SZ, path_to_exe)
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{queue_folder_key_path}\\command', 0, write_access) as key:
            wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" -q "%1"')
        # set "play folder next in Music Caster" command
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, play_next_folder_key_path, 0, write_access) as key:
            wr.SetValueEx(key, None, 0, wr.REG_SZ, gt('Play next in Music Caster'))
            wr.SetValueEx(key, 'Icon', 0, wr.REG_SZ, path_to_exe)
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{play_next_folder_key_path}\\command', 0, write_access) as key:
            wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" -n "%1"')
    else:
        # remove commands for folders
        delete_sub_key(wr.HKEY_CURRENT_USER, play_folder_key_path)
        delete_sub_key(wr.HKEY_CURRENT_USER, queue_folder_key_path)
        delete_sub_key(wr.HKEY_CURRENT_USER, play_next_folder_key_path)


def get_default_output_device():
    """ returns the PyAudio formatted name of the default output device """
    read_access = wr.KEY_READ | wr.KEY_WOW64_64KEY if is_os_64bit() else wr.KEY_READ
    audio_path = r'SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render'
    audio_key = wr.OpenKeyEx(wr.HKEY_LOCAL_MACHINE, audio_path, 0, read_access)
    num_devices = wr.QueryInfoKey(audio_key)[0]
    active_last_used, active_device_name = -1, None
    for i in range(num_devices):
        device_key_path = f'{audio_path}\\{wr.EnumKey(audio_key, i)}'
        device_key = wr.OpenKeyEx(wr.HKEY_LOCAL_MACHINE, device_key_path, 0, read_access)
        if wr.QueryValueEx(device_key, 'DeviceState')[0] == 1:  # if enabled
            properties_path = f'{device_key_path}\\Properties'
            properties = wr.OpenKeyEx(wr.HKEY_LOCAL_MACHINE, properties_path, 0, read_access)
            device_name = wr.QueryValueEx(properties, '{b3f8fa53-0004-438e-9003-51a46e139bfc},6')[0]
            device_type = wr.QueryValueEx(properties, '{a45c254e-df1c-4efd-8020-67d146a850e0},2')[0]
            pa_name = f'{device_type} ({device_name})'  # name shown in PyAudio
            last_used = wr.QueryValueEx(device_key, 'Level:0')[0]
            if last_used > active_last_used:  # the bigger the number, the more recent it was used
                active_last_used = last_used
                active_device_name = pa_name
    return active_device_name


def resize_img(base64data, bg, new_size=COVER_NORMAL) -> bytes:
    """ Resize and return b64 img data to new_size (w, h). (use .decode() on return statement for str) """
    img_data = io.BytesIO(b64decode(base64data))
    art_img: Image = Image.open(img_data)
    w, h = art_img.size
    if w == h:
        img = art_img.resize(new_size, Image.ANTIALIAS)
    else:
        ratio = h / w if w > h else w / h
        to_change = 1 if w > h else 0
        ratio_size = list(new_size)
        ratio_size[to_change] = round(new_size[to_change] * ratio)
        art_img = art_img.resize(ratio_size, Image.ANTIALIAS)
        paste_width = (new_size[0] - ratio_size[0]) // 2
        paste_height = (new_size[1] - ratio_size[1]) // 2
        img = Image.new('RGB', new_size, color=bg)
        img.paste(art_img, (paste_width, paste_height))
    data = io.BytesIO()
    img.save(data, format='png')
    return b64encode(data.getvalue())


def export_playlist(playlist_name, uris):
    # location should be downloads folder
    playlist_name = re.sub(r'(?u)[^-\w.]', '', playlist_name)  # clean name
    playlist_path = Path.home() / 'Downloads'
    playlist_path.mkdir(parents=True, exist_ok=True)
    playlist_path /= f'{playlist_name}.m3u'
    with open(playlist_path, 'w') as f:
        f.write('#EXTM3U\n')
        for uri in uris:
            if uri.replace('\\', '/') != playlist_path:
                f.write(uri + '\n')
    return str(playlist_path)


def parse_m3u(playlist_file):
    playlist_file = playlist_file.replace('\\', '/')
    with open(playlist_file, errors='ignore') as f:
        for line in iter(lambda: f.readline(), ''):
            if not line.startswith('#'):
                line = line.lstrip('file:').lstrip('/').rstrip().replace('\\', '/')
                # an m3u file cannot contain itself
                if line != playlist_file: yield line


def get_latest_release(ver, this_version, force=False):
    """
    returns {'version': latest_ver, 'setup': 'setup_link'} if the latest release version is newer (>) than VERSION
    if latest release version <= VERSION, returns false
    if force: return latest release even if latest version <= VERSION """
    releases_url = 'https://api.github.com/repos/elibroftw/music-caster/releases/latest'
    with suppress(requests.RequestException):
        release = requests.get(releases_url)
        if release.status_code >= 400:
            release = requests.get(releases_url, proxies=get_proxy(False))
        release = release.json()
        latest_ver = release.get('tag_name', f'v{this_version}')[1:]
        _version = [int(x) for x in ver.split('.')]
        compare_ver = [int(x) for x in latest_ver.split('.')]
        if compare_ver > _version or force:
            for asset in release.get('assets', []):
                # check if setup exists
                if 'exe' in asset['name']:
                    return {'version': latest_ver, 'setup': asset['browser_download_url']}
    return False


@time_cache(600, maxsize=1)
def get_proxies(add_local=True):
    from bs4 import BeautifulSoup  # 0.32 seconds if at top level, here it is 0.1 seconds
    try:
        response = requests.get('https://free-proxy-list.net/', headers={'user-agent': USER_AGENT})
        scraped_proxies = set()
        soup = BeautifulSoup(response.text, 'lxml')
        table = soup.find('table')
        # noinspection PyUnresolvedReferences
        for row in table.find_all('tr'):
            count = 0
            proxy = ''
            try:
                is_https = row.find('td', {'class': 'hx'}).text == 'yes'
            except AttributeError:
                is_https = False
            if is_https:
                for cell in row.find_all('td'):
                    if count == 1:
                        proxy += ':' + cell.text.replace('&nbsp;', '')
                        scraped_proxies.add(proxy)
                        break
                    proxy += cell.text.replace('&nbsp;', '')
                    count += 1
        proxies: list = [None, None, None, None, None] if add_local else []
        for proxy in sorted(scraped_proxies): proxies.extend(repeat(proxy, 3))
    except (requests.RequestException, AttributeError):
        return cycle([None])
    return cycle(proxies)


def get_proxy(add_local=True):
    proxy = next(get_proxies(add_local))
    return {'http': proxy, 'https': proxy}


@time_cache(max_age=3500, maxsize=1)
def get_spotify_headers():
    # access token key expires in ~1 hour
    r = requests.get('https://open.spotify.com/', headers={'user-agent': USER_AGENT})
    m = re.search('"accessToken":"[^"]*', r.text)
    access_token = m.group().split(':"')[1]
    return {'Authorization': f'Bearer {access_token}'}


def parse_spotify_track(track_obj) -> dict:
    """
    Returns a metadata dict for a given Spotify track
    """
    try:
        artist = ', '.join((artist['name'] for artist in track_obj['artists'] if artist['type'] == 'artist'))
    except KeyError:
        artist = Unknown('Artist')
    title = track_obj['name']
    is_explicit = track_obj['explicit']
    album = track_obj['album']['name']
    src_url = track_obj['external_urls']['spotify']
    track_number = str(track_obj['track_number'])
    sort_key = Shared.track_format.replace('&title', title).replace('&artist', artist).replace('&album', str(album))
    sort_key = sort_key.replace('&trck', track_number).lower()
    metadata = {'src': src_url, 'title': title, 'artist': artist, 'album': album,
                'explicit': is_explicit, 'sort_key': sort_key, 'track_number': track_number}
    with suppress(IndexError):
        metadata['art'] = track_obj['album']['images'][0]['url']
    return metadata


def get_spotify_track(url):
    try:
        track_id = urlparse(url).path.split('/track/', 1)[1]
    except IndexError:
        # e.g. */album/*?highlight=spotify:track:587w9pOR9UNvFJOwkW7NgD
        track_id = re.search(r'track:.*', url).group()[6:]
    track = requests.get(f'{SPOTIFY_API}/tracks/{track_id}', headers=get_spotify_headers()).json()
    return {**parse_spotify_track(track), 'src': url}


def get_spotify_album(url):
    album_id = urlparse(url).path.split('/album/', 1)[1]
    r = requests.get(f'{SPOTIFY_API}/albums/{album_id}', headers=get_spotify_headers()).json()
    return [parse_spotify_track({**track, 'album': r}) for track in r['tracks']['items']]


def get_spotify_playlist(url):
    playlist_id = urlparse(url).path.split('/playlist/', 1)[1]
    response = requests.get(f'{SPOTIFY_API}/playlists/{playlist_id}/tracks', headers=get_spotify_headers()).json()
    results = response['items']
    while len(results) < response['total']:
        response = requests.get(f'{SPOTIFY_API}/playlists/{playlist_id}/tracks?offset={len(results)}',
                                headers=get_spotify_headers()).json()
        results.extend(response['items'])
    return [parse_spotify_track(result['track']) for result in results]


@lru_cache
def get_spotify_tracks(url):
    """
    Returns a list of spotify track objects stemming from a Spotify url
    Could raise: AttributeError, RequestException, KeyError, more?
    """
    if 'track' in url:
        return [get_spotify_track(url)]
    if 'album' in url:
        return get_spotify_album(url)
    if 'playlist' in url:
        return get_spotify_playlist(url)
    return []


def get_cookies(domain_contains, cookie_name='', return_first=True, return_value=True):
    """
    get_cookies('.youtube.com', '', False, False)
    """
    import browser_cookie3 as bc3  # 0.388 seconds if on top level, 0.06 here
    import sqlite3
    for cookie_storage in (bc3.chrome, bc3.firefox, bc3.opera, bc3.edge, bc3.chromium):
        cookies = []
        with suppress(bc3.BrowserCookieError, sqlite3.OperationalError):
            cookie_storage = cookie_storage()
            for cookie in cookie_storage:
                if cookie.domain.count(domain_contains):
                    formatted_cookie = f'{cookie.name}={cookie.value}'
                    if (not cookie_name or cookie.name == cookie_name) and not cookie.is_expired():
                        cookie_to_use = cookie.value if return_value else formatted_cookie
                        if return_first: return cookie_to_use
                        cookies.append(cookie_to_use)
        if cookies:
            return 'Cookie: ' + '; '.join(cookies)
    return ''


@lru_cache
def parse_deezer_page(url):
    if 'page.link' in url:
        r = requests.get(url)
        url = r.url
    if '/track/' in url:
        _type = 'track'
    elif '/album/' in url:
        _type = 'album'
    elif '/playlist/' in url:
        _type = 'playlist'
    elif '/user/' in url:
        _type = 'user'
    else:
        raise ValueError('Unknown URL')
    _id = re.search(r'\d+', urlparse(url).path).group()
    return {'type': _type, 'sng_id': _id}


def parse_deezer_track(track_obj) -> dict:
    from deemix.decryption import generateBlowfishKey, generateStreamURL
    artists = []
    try:
        main_artists = track_obj['SNG_CONTRIBUTORS']['main_artist']
    except KeyError:
        main_artists = track_obj['SNG_CONTRIBUTORS']['mainartist']
    for artist in main_artists + track_obj['SNG_CONTRIBUTORS'].get('featuring', []):
        include = True
        for added_artist in artists:
            if added_artist in artist:
                include = False
                break
        if include: artists.append(artist)
    artist_str = ', '.join(artists)
    art = f"https://cdns-images.dzcdn.net/images/cover/{track_obj['ALB_PICTURE']}/1000x1000-000000-80-0-0.jpg"
    title, album = track_obj['SNG_TITLE'], track_obj['ALB_TITLE']
    length = int(track_obj['DURATION'])
    is_explicit = track_obj['EXPLICIT_TRACK_CONTENT']['EXPLICIT_LYRICS_STATUS'] == '1'
    is_expired = lambda: time.time() > track_obj['TRACK_TOKEN_EXPIRE']
    sng_id = track_obj['SNG_ID']
    metadata = {
        'art': art, 'title': title, 'ext': 'mp3', 'artist': artist_str, 'album': album,
        'length': length, 'sng_id': sng_id, 'explicit': is_explicit
    }
    with suppress(KeyError):
        md5 = track_obj.get('FALLBACK', track_obj)['MD5_ORIGIN']
        file_url = generateStreamURL(sng_id, md5, track_obj['MEDIA_VERSION'], TrackFormats.MP3_320)
        bf_key = generateBlowfishKey(sng_id)
        metadata['file_url'] = file_url
        metadata['bf_key'] = bf_key
        metadata['expired'] = is_expired
    return metadata


def set_dz_url(metadata):
    if DECRYPT_TRACK:
        src_url = metadata['src']
        metadata['url'] = f'http://{get_ipv4()}:{Shared.PORT}/dz?{urlencode({"url": src_url})}'
    else:
        metadata['url'] = metadata['file_url']


def get_deezer_track(url):
    sng_id = parse_deezer_page(url)['sng_id']
    metadata = parse_deezer_track(dz().gw.get_track(sng_id))
    metadata['src'] = url
    set_dz_url(metadata)
    return metadata


def get_deezer_album(url):
    alb_id = parse_deezer_page(url)['sng_id']
    tracks = []
    for track in dz().gw.get_album_tracks(alb_id):
        metadata = parse_deezer_track(track)
        sng_id = metadata['sng_id']
        metadata['src'] = f'https://www.deezer.com/track/{sng_id}'
        set_dz_url(metadata)
        tracks.append(metadata)
    return tracks


def get_deezer_playlist(url):
    pl_id = parse_deezer_page(url)['sng_id']
    tracks = []
    for track in dz().gw.get_playlist_tracks(pl_id):
        metadata = parse_deezer_track(track)
        sng_id = metadata['sng_id']
        metadata['src'] = f'https://www.deezer.com/track/{sng_id}'
        set_dz_url(metadata)
        tracks.append(metadata)
    return tracks


@lru_cache
def get_deezer_tracks(url, login=True):
    if login:
        if not dz().logged_in:
            if not dz().login_via_arl(get_cookies('.deezer.com', cookie_name='arl')):
                raise LookupError('Not logged into deezer.com')
    dz_type = parse_deezer_page(url)['type']
    if dz_type == 'track':
        return [get_deezer_track(url)]
    elif dz_type == 'album':
        return get_deezer_album(url)
    elif dz_type == 'playlist':
        return get_deezer_playlist(url)
    return []


@lru_cache
def custom_art(text):
    img_data = io.BytesIO(b64decode(DEFAULT_ART))
    art_img: Image = Image.open(img_data)
    size = art_img.size
    x1 = y1 = size[0] * 0.95
    x0 = x1 - len(text) * 0.0625 * size[0]
    y0 = y1 - 0.11 * size[0]
    d = ImageDraw.Draw(art_img)
    try:
        username = os.getenv('USERNAME')
        fnt = ImageFont.truetype(f"C:/Users/{username}/AppData/Local/Microsoft/Windows/Fonts/MYRIADPRO-BOLD.OTF", 80)
        shift = 5
    except OSError:
        try:
            fnt = ImageFont.truetype('gadugib.ttf', 80)
            shift = -5
        except OSError:
            fnt = ImageFont.truetype('arial.ttf', 80)
            shift = 0
    d.rounded_rectangle((x0, y0, x1, y1), fill='#cc1a21', radius=7)
    d.text(((x0 + x1) / 2, (y0 + y1) / 2 + shift), text, fill='#fff', font=fnt, align='center', anchor='mm')
    data = io.BytesIO()
    art_img.save(data, format='png', quality=95)
    return b64encode(data.getvalue())


def search_dict(partial: [dict, list], key):
    """ Searches for `key` in a dict/list `partial` """
    if isinstance(partial, dict):
        for k, v in partial.items():
            if k == key: yield v
            else: yield from search_dict(v, key)
    elif isinstance(partial, list):
        for item in partial: yield from search_dict(item, key)


def get_youtube_comments(url, limit=-1):
    """
    raises ValueError if comments are disabled
    Modified from https://github.com/egbertbouman/youtube-comment-downloader
    """
    session = requests.Session()
    YT_CFG_RE = r'ytcfg\.set\s*\(\s*({.+?})\s*\)\s*;'
    YT_INITIAL_DATA_RE = r'(?:window\s*\[\s*["\']ytInitialData["\']\s*\]|ytInitialData)\s*=\s*({.+?})\s*;\s*(' \
                         r'?:var\s+meta|</script|\n)'
    renderer = None
    proxies = get_proxy()
    for _ in range(6):
        with suppress(AttributeError):
            res = session.get(url, headers={'user-agent': USER_AGENT, 'referer': 'https://google.com/'},
                              proxies=proxies)
            ytcfg = json.loads(re.search(YT_CFG_RE, res.text).group(1))
            if ytcfg:
                data = json.loads(re.search(YT_INITIAL_DATA_RE, res.text).group(1))
                section = next(search_dict(data, 'itemSectionRenderer'), None)
                renderer = next(search_dict(section, 'continuationItemRenderer'), None) if section else None
                break
            proxies = get_proxy()
    if not isinstance(renderer, dict): return  # Comments disabled?

    continuations = [renderer['continuationEndpoint']]
    while continuations:
        continuation = continuations.pop()
        response = {}
        comments_url = 'https://www.youtube.com' + continuation['commandMetadata']['webCommandMetadata']['apiUrl']
        # noinspection PyUnboundLocalVariable
        data = {'context': ytcfg['INNERTUBE_CONTEXT'], 'continuation': continuation['continuationCommand']['token']}
        for _ in range(5):  # 5 retries
            try:
                response = session.post(comments_url, params={'key': ytcfg['INNERTUBE_API_KEY']}, proxies=proxies,
                                        json=data)
                if response.status_code == 200:
                    response = response.json()
                    break
                elif response.status_code in {403, 413}:
                    response = {}
                    break
                else: time.sleep(20)
            except requests.exceptions.ProxyError:
                proxies = get_proxy()
        if not response: break
        with suppress(StopIteration):
            raise RuntimeError('Error returned from server: ' + next(search_dict(response, 'externalErrorMessage')))
        actions = chain(search_dict(response, 'reloadContinuationItemsCommand'),
                        search_dict(response, 'appendContinuationItemsAction'))
        for action in actions:
            for item in action.get('continuationItems', []):
                if action['targetId'] == 'comments-section':
                    # Process continuations for comments and replies.
                    continuations[:0] = [ep for ep in search_dict(item, 'continuationEndpoint')]
                if action['targetId'].startswith('comment-replies-item') and 'continuationItemRenderer' in item:
                    # Process the 'Show more replies' button
                    continuations.append(next(search_dict(item, 'buttonRenderer'))['command'])
        for comment in reversed(list(search_dict(response, 'commentRenderer'))):
            yield {'cid': comment['commentId'],
                   'text': ''.join([c['text'] for c in comment['contentText'].get('runs', [])]),
                   'time': comment['publishedTimeText']['runs'][0]['text'],
                   'author': comment.get('authorText', {}).get('simpleText', ''),
                   'channel': comment['authorEndpoint']['browseEndpoint'].get('browseId', ''),
                   'votes': comment.get('voteCount', {}).get('simpleText', '0'),
                   'photo': comment['authorThumbnail']['thumbnails'][-1]['url'],
                   'heart': next(search_dict(comment, 'isHearted'), False)}
            limit -= 1
            if limit == 0:
                continuations.clear()
                break
        time.sleep(0.1)


def parse_timestamps(text):
    times = re.findall(r'\d+:(?:\d+:)*\d+', text)
    times = sorted({sum(int(x) * 60 ** i for i, x in enumerate(reversed(_time.split(':')))) for _time in times})
    return times


def get_video_timestamps(video_info):
    # try parsing chapters
    with suppress(KeyError):
        chapters = video_info['chapters']
        times = set()
        for chapter in chapters:
            times.add(chapter['start_time'])
            times.add(chapter['end_time'])
        return sorted(times)
    # try parsing description
    description_timestamps = parse_timestamps(video_info['description'])
    if len(description_timestamps) > 1: return description_timestamps
    # try parsing comments
    url = video_info['webpage_url']
    with suppress(ValueError, RuntimeError):
        for count, comment in enumerate(get_youtube_comments(url, limit=10)):
            times = parse_timestamps(comment['text'])
            if len(times) > 2: return times
    return []


# GUI Methods
def icon_btn(image_data, key, tooltip, bg):
    return Sg.Button(image_data=image_data, key=key, tooltip=tooltip, enable_events=True, button_color=(bg, bg))


def round_btn(button_text, fill, text_color, tooltip=None, key=None, visible=True,
              pad=None, bind_return_key=False, button_width=None):
    multi = 4
    btn_w = ((len(button_text) if button_width is None else button_width) * 5 + 20) * multi
    height = 18 * multi
    btn_img = Image.new('RGBA', (btn_w, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(btn_img)
    x0 = y0 = 0
    radius = 10 * multi
    d.ellipse((x0, y0, x0 + radius * 2, height), fill=fill)
    d.ellipse((btn_w - radius * 2 - 1, y0, btn_w - 1, height), fill=fill)
    d.rectangle((x0 + radius, y0, btn_w - radius, height), fill=fill)
    data = io.BytesIO()
    btn_img.thumbnail((btn_w // 3, height // 3), resample=Image.LANCZOS)
    btn_img.save(data, format='png', quality=100)
    btn_img = b64encode(data.getvalue())
    return Sg.Button(button_text=button_text, image_data=btn_img, button_color=(text_color, text_color),
                     tooltip=tooltip, key=key, pad=pad, enable_events=False, size=(button_width, 1),
                     bind_return_key=bind_return_key, font=FONT_NORMAL, visible=visible)


def repeat_img_tooltip(repeat_setting):
    if repeat_setting is None: return REPEAT_OFF_IMG, gt('Repeat All')
    elif repeat_setting: return REPEAT_ONE_IMG, gt('Repeat Off')
    else: return REPEAT_ALL_IMG, gt('Repeat One')


def get_music_controls(settings, playing_status: PlayingStatus):
    accent_color, bg = settings['theme']['accent'], settings['theme']['background']
    is_muted = settings['muted']
    volume = 0 if is_muted else settings['volume']
    v_slider_img = VOLUME_MUTED_IMG if is_muted else VOLUME_IMG
    p_r_img = PAUSE_BUTTON_IMG if playing_status.playing() else PLAY_BUTTON_IMG
    repeat_img, repeat_tooltip = repeat_img_tooltip(settings['repeat'])
    prev_button = {'pad': ((10, 5), None) if settings['mini_mode'] else None, 'tooltip': gt('previous track')}
    repeat_button = {'button_color': (bg, bg), 'tooltip': repeat_tooltip, 'metadata': settings['repeat']}
    shuffle_button = {'button_color': (bg, bg), 'image_data': SHUFFLE_ON if settings['shuffle'] else SHUFFLE_OFF}
    mute_tooltip = gt('unmute') if is_muted else gt('mute')
    return [Sg.Button(key='prev', image_data=PREVIOUS_BUTTON_IMG, button_color=(bg, bg), **prev_button),
            Sg.Button(key='pause/resume', image_data=p_r_img, button_color=(bg, bg)),
            Sg.Button(key='next', image_data=NEXT_BUTTON_IMG, button_color=(bg, bg), tooltip=gt('next track')),
            Sg.Button(key='repeat', image_data=repeat_img, **repeat_button),
            Sg.Button(key='shuffle', **shuffle_button, tooltip=gt('shuffle')),
            Sg.Button(key='mute', image_data=v_slider_img, button_color=(bg, bg), tooltip=mute_tooltip),
            Sg.Slider((0, 100), default_value=volume, orientation='h', key='volume_slider',
                      disable_number_display=True, enable_events=True, background_color=accent_color,
                      text_color='#000000', size=(10, 10), tooltip=gt('scroll mousewheel'), resolution=1)]


def create_progress_bar_text(position, length) -> (str, str):  #
    """":return: time_elapsed_text, time_left_text"""
    position = floor(position)
    mins_elapsed, secs_elapsed = floor(position / 60), floor(position % 60)
    if secs_elapsed < 10: secs_elapsed = f'0{secs_elapsed}'
    elapsed_text = f'{mins_elapsed}:{secs_elapsed}'
    try:
        time_left = round(length) - position
        mins_left, secs_left = time_left // 60, time_left % 60
        if secs_left < 10: secs_left = f'0{secs_left}'
        time_left_text = f'{mins_left}:{secs_left}'
    except TypeError:
        time_left_text = '∞'
    return elapsed_text, time_left_text


def get_progress_layout(settings, track_position, track_length, playing_status: PlayingStatus):
    time_elapsed, time_left = create_progress_bar_text(track_position, track_length)
    text_size = (5, 1)
    bot_pad = (settings['vertical_gui'] and not settings['show_album_art']) * 30
    accent_color, bg = settings['theme']['accent'], settings['theme']['background']
    mini_mode = settings['mini_mode']
    time_elapsed_pad = ((2, 0), (0, 0)) if mini_mode else ((0, 5), (10, bot_pad))
    time_left_pad = ((0, 0), (0, 0)) if mini_mode else ((5, 0), (10, bot_pad))
    progress_layout = [Sg.Text(time_elapsed, key='time_elapsed', pad=time_elapsed_pad, justification='center',
                               size=text_size, font=FONT_NORMAL),
                       Sg.Slider(range=(0, 1 if track_length is None else track_length),
                                 default_value=1 if track_length is None else floor(track_position),
                                 orientation='h', size=(20 if mini_mode else 30, 10), key='progress_bar',
                                 enable_events=True, relief=Sg.RELIEF_FLAT, background_color=accent_color,
                                 disable_number_display=True, disabled=playing_status.stopped() or track_length is None,
                                 tooltip=gt('scroll mousewheel'),
                                 pad=((2, 10), (0, 0)) if mini_mode else ((8, 8), (10, bot_pad))),
                       Sg.Text(time_left, key='time_left', pad=time_left_pad, justification='left',
                               size=text_size, font=FONT_NORMAL)]
    if mini_mode:
        progress_layout.append(Sg.Button(key='mini_mode', image_data=RESTORE_WINDOW, size=(1, 1), enable_events=True,
                                         button_color=(bg, bg), tooltip=gt('restore window'), pad=(0, 0)))
    return progress_layout


def truncate_title(title):
    """ truncate title for mini mode """
    if len(title) > 29:
        return title[:26] + '...'
    return title


def create_mini_mode(playing_status, settings, title, artist, album_art_data, track_length, track_position):
    # album_art_data is 125 x 125
    album_art = Sg.Column([[Sg.Image(data=album_art_data, key='artwork', pad=(0, 0))]],
                          element_justification='left', pad=(0, 0))
    music_controls = get_music_controls(settings, playing_status)
    progress_bar_layout = get_progress_layout(settings, track_position, track_length, playing_status)
    title = truncate_title(title)
    right_side = Sg.Column([
        [Sg.Text(title, font=FONT_TITLE, key='title', pad=((10, 0), 0), size=(28, 1))],
        [Sg.Text(artist, font=FONT_MID, key='artist', pad=((10, 0), 0), size=(28, 2))],
        music_controls, progress_bar_layout], pad=(0, 0))
    return [[album_art, right_side] if settings['show_album_art'] else [right_side]]


def create_main(queue, listbox_selected, playing_status, settings, version, timer, music_lib,
                title=gt('Nothing Playing'), artist='', album='', album_art_data: str = '',
                track_length=0, track_position=0):
    if settings['mini_mode']:
        return create_mini_mode(playing_status, settings, title, artist, album_art_data, track_length, track_position)
    accent_color, fg, bg = settings['theme']['accent'], settings['theme']['text'], settings['theme']['background']
    alternate_bg = settings['theme']['alternate_background']
    vertical_gui = settings['vertical_gui']
    music_controls = get_music_controls(settings, playing_status)
    progress_bar_layout = get_progress_layout(settings, track_position, track_length, playing_status)
    if not settings['show_album_art']: album_art_data = ''
    info_top_pad = 10 + 60 * (not album_art_data) - 30 * (vertical_gui and not album_art_data)
    # 10, 110, or 0
    info_bot_pad = 10 + 40 * (not album_art_data) - 20 * (not album_art_data and vertical_gui)
    # 10 or 30
    left_pad = settings['vertical_gui'] * 95 + 5
    main_part = Sg.Column([
        [Sg.Image(data=album_art_data, pad=(0, 0), size=COVER_NORMAL, key='artwork')] if album_art_data else [],
        [Sg.Text(album, font=FONT_MID, key='album', pad=((0, 0), (info_top_pad, 0)), enable_events=True,
                 size=(30, 2), justification='center')],
        [Sg.Text(title, font=FONT_TITLE, key='title', pad=((0, 0), 4), enable_events=True,
                 size=(30, 2), justification='center')],
        [Sg.Text(artist, font=FONT_MID, key='artist', pad=((0, 0), (0, info_bot_pad)), enable_events=True,
                 size=(30, 0), justification='center')],
        music_controls, progress_bar_layout], element_justification='center', pad=((left_pad, 5), 5 * vertical_gui))
    # tabs side is for music queue, queue controls, and later, the music library
    # tab 1 is the queue, tab 2 will be the library
    file_options = [gt('Play File(s)'), gt('Queue File(s)'), gt('Play File(s) Next')]
    folder_opts = [gt('Play Folder'), gt('Queue Folder'), gt('Play Folder Next')]
    biggest_word = len(max(*file_options, *folder_opts, key=len))
    combo_w = ceil(biggest_word * 0.95)
    queue_controls = [
        Sg.Column([[Sg.Combo(file_options, default_value=file_options[0], key='file_option', size=(combo_w, 5),
                             font=FONT_NORMAL, enable_events=True, pad=(5, (5, 0)), readonly=True)],
                   [Sg.Combo(folder_opts, default_value=folder_opts[0], key='folder_option', size=(combo_w, 5),
                             font=FONT_NORMAL, enable_events=True, pad=(5, (10, 0)), readonly=True)]]),
        Sg.Column([[round_btn(file_options[0], accent_color, bg, key='file_action',
                              button_width=biggest_word, pad=(5, (7, 5)))],
                   [round_btn(folder_opts[0], accent_color, bg, key='folder_action',
                              button_width=biggest_word)]]),
    ]
    move_to_next_up = {'image_data': PLAY_NEXT_ICON, 'button_color': (bg, bg), 'tooltip': gt('Move to next up')}
    listbox_controls = [
        [Sg.Button(key='mini_mode', image_data=RESTORE_WINDOW, button_color=(bg, bg), tooltip=gt('Launch mini mode'))],
        [Sg.Button(key='queue_all', image_data=QUEUE_ICON, button_color=(bg, bg), tooltip=gt('queue all'))],
        [Sg.Button(key='clear_queue', image_data=CLEAR_QUEUE, button_color=(bg, bg), tooltip=gt('Clear the queue'))],
        [Sg.Button(key='save_queue', image_data=SAVE_IMG, button_color=(bg, bg), tooltip=gt('Save queue to playlist'))],
        [Sg.Button(key='locate_uri', image_data=LOCATE_FILE, button_color=(bg, bg), tooltip=gt('locate track'))],
        [Sg.Button(key='move_to_next_up', **move_to_next_up)],
        [icon_btn(UP_ICON, 'move_up', gt('move up'), bg)],
        [icon_btn(X_ICON, 'remove_track', gt('remove'), bg)],
        [icon_btn(DOWN_ICON, 'move_down', gt('move down'), bg)]
    ]
    listbox_height = 18 - 5 * settings['vertical_gui']
    queue_tab_layout = [queue_controls, [
        Sg.Listbox(queue, default_values=listbox_selected, size=(64, listbox_height),
                   select_mode=Sg.SELECT_MODE_EXTENDED,
                   text_color=fg, key='queue', font=FONT_NORMAL,
                   bind_return_key=True),
        Sg.Column(listbox_controls, pad=(0, 0))]]
    queue_tab = Sg.Tab(gt('Queue'), queue_tab_layout, key='tab_queue')
    url_tab = create_url_tab(accent_color, bg)
    # library tab will be good to use once I'm using Python 3.10 which will have tk 8.10
    try:
        lib_data = [[track['title'], get_first_artist(track['artist']), track['album'], uri] for uri, track in
                    music_lib.items()]
    except RuntimeError:
        lib_data = []
    lib_headings = ['title', 'artist', 'album']
    library_layout = [[Sg.Table(values=lib_data, headings=lib_headings, row_height=30, auto_size_columns=False,
                                col_widths=[25, 15, 15], bind_return_key=True, select_mode=Sg.SELECT_MODE_EXTENDED,
                                justification='right', num_rows=14 - 3 * settings['vertical_gui'],
                                selected_row_colors=(bg, accent_color),
                                right_click_menu=['', ['Play::library', 'Play Next::library',
                                                       'Queue::library', 'Locate::library']],
                                header_text_color=fg, header_background_color=bg,
                                alternating_row_color=alternate_bg, key='library')]]
    library_tab = Sg.Tab(gt('Library'), library_layout, key='tab_library')
    playlists_tab = create_playlists_tab(settings)
    timer_tab = create_timer(settings, timer)
    metadata_tab = create_metadata_tab(settings)
    settings_tab = create_settings(version, settings)
    tab_group = [[queue_tab, url_tab, library_tab, playlists_tab, timer_tab, metadata_tab, settings_tab]]
    tabs_part = Sg.TabGroup(tab_group, font=FONT_TAB, border_width=0, title_color=fg, key='tab_group',
                            selected_background_color=accent_color, enable_events=True,
                            tab_background_color=bg, selected_title_color=bg, background_color=bg)
    if settings['vertical_gui']: return [[main_part], [tabs_part]]
    return [[main_part, tabs_part]] if settings['flip_main_window'] else [[tabs_part, main_part]]


def create_url_tab(accent_color, bg):
    layout = [[Sg.Text(gt('Enter URL'), font=FONT_NORMAL)],
              [Sg.Radio(gt('Play Immediately'), 'url_option', key='url_play', default=True),
               Sg.Radio(gt('Queue'), 'url_option', key='url_queue'),
               Sg.Radio(gt('Play Next'), 'url_option', key='url_play_next')],
              [Sg.Input(key='url_input', font=FONT_NORMAL, enable_events=True, border_width=1),
               round_btn(gt('Submit'), accent_color, bg, key='url_submit', bind_return_key=True)],
              [Sg.Text('', key='url_msg', size=(20, 1))]]
    return Sg.Tab(gt('URL'), [[Sg.Column(layout, pad=(5, 20))]], key='tab_url')


def create_playlists_tab(settings):
    fg, bg = settings['theme']['text'], settings['theme']['background']
    accent = settings['theme']['accent']
    playlists = settings['playlists']
    playlists_names = list(playlists.keys())
    default_pl_name = playlists_names[0] if playlists_names else None
    playlist_selector = [
        [icon_btn(PLUS_ICON, 'new_pl', gt('new playlist'), bg),
         Sg.Button(image_data=EXPORT_PL, key='export_pl', tooltip=gt('export playlist'), button_color=(bg, bg)),
         Sg.Button(image_data=DELETE_ICON, key='delete_pl', tooltip=gt('delete playlist'), button_color=(bg, bg)),
         Sg.Button(image_data=PLAY_ICON, key='play_pl', tooltip=gt('play playlist'), button_color=(bg, bg)),
         Sg.Button(image_data=QUEUE_ICON, key='queue_pl', tooltip=gt('queue playlist'), button_color=(bg, bg)),
         Sg.Button(image_data=PLAY_NEXT_ICON, key='add_next_pl', tooltip=gt('add to next up'), button_color=(bg, bg)),
         Sg.Combo(values=playlists_names, size=(PL_COMBO_W, 1), key='playlist_combo', font=FONT_NORMAL,
                  enable_events=True, default_value=default_pl_name, readonly=True)]]
    playlist_name = playlists_names[0] if playlists_names else ''
    url_input = [Sg.Input('', key='pl_url_input', size=(15, 1), font=FONT_NORMAL, border_width=1, enable_events=True)]
    add_url = [round_btn(gt('Add URL'), accent, bg, key='pl_add_url', button_width=13)]
    add_tracks = [round_btn(gt('Add tracks'), accent, bg, key='pl_add_tracks', button_width=13)]
    lb_height = 14 - 3 * settings['vertical_gui']
    pl_name_text = gt('Playlist name')
    name_text_w = max(13, len(pl_name_text))
    layout = [[Sg.Column(playlist_selector, pad=(5, 20))],
              [Sg.Text(pl_name_text, font=FONT_NORMAL, size=(name_text_w, 1), justification='center', pad=(4, (5, 10))),
               Sg.Input(playlist_name, key='pl_name', size=(60 - name_text_w, 1), font=FONT_NORMAL,
                        pad=((22, 5), (5, 10)), border_width=1),
               Sg.Button(key='pl_save', image_data=SAVE_IMG, tooltip='Ctrl + S', button_color=(bg, bg))],
              [Sg.Column([url_input, add_url, add_tracks]),
               Sg.Listbox([], size=(45, lb_height), select_mode=Sg.SELECT_MODE_EXTENDED, text_color=fg,
                          key='pl_tracks', background_color=bg, font=FONT_NORMAL, bind_return_key=True),
               Sg.Column(
                   [[icon_btn(UP_ICON, 'pl_move_up', gt('move up'), bg)],
                    [icon_btn(X_ICON, 'pl_rm_items', gt('remove'), bg)],
                    [icon_btn(DOWN_ICON, 'pl_move_down', gt('move down'), bg)],
                    [Sg.Button(image_data=PLAY_ICON, key='play_pl_selected', tooltip=gt('play selected'),
                               button_color=(bg, bg))],
                    [Sg.Button(image_data=QUEUE_ICON, key='queue_pl_selected', tooltip=gt('queue selected'),
                               button_color=(bg, bg))],
                    [Sg.Button(image_data=PLAY_NEXT_ICON, key='add_next_pl_selected',
                               tooltip=gt('add selected to next up'), button_color=(bg, bg))],
                    [Sg.Button(image_data=LOCATE_FILE, key='pl_locate_selected', button_color=(bg, bg),
                               tooltip=gt('locate selected'), size=(2, 1))]],
                   background_color=bg)]]
    return Sg.Tab(gt('Playlists'), layout, key='tab_playlists')


def create_checkbox(name, key, settings, on_right=False):
    bg = settings['theme']['background']
    size = (23, 5) if on_right else (23, 5)
    checkbox = {'background_color': bg, 'font': FONT_NORMAL, 'enable_events': True, 'pad': ((0, 5), (5, 5))}
    return Sg.Checkbox(name, default=settings[key], key=key, tooltip=name, size=size, **checkbox)


def create_settings(version, settings):
    qr_code = create_qr_code()
    accent_color, fg, bg = settings['theme']['accent'], settings['theme']['text'], settings['theme']['background']
    general_tab = Sg.Tab(gt('General'), [
        [create_checkbox(gt('Auto update'), 'auto_update', settings),
         create_checkbox(gt('Discord presence'), 'discord_rpc', settings, True)],
        [create_checkbox(gt('Notifications'), 'notifications', settings),
         create_checkbox(gt('Run on startup'), 'run_on_startup', settings, True)],
        [create_checkbox(gt('Folder context menu'), 'folder_context_menu', settings),
         create_checkbox(gt('Scan folders'), 'scan_folders', settings, True)],
        [create_checkbox(gt('Remember last folder'), 'use_last_folder', settings),
         Sg.Text('🌐', tooltip=gt('language', True)),
         Sg.Combo(values=get_languages(), size=(3, 1), default_value=settings['lang'], key='lang', readonly=True,
                  enable_events=True, tooltip=gt('language'))],
        [Sg.Text(gt('System Audio Delay:')),
         Sg.Input(settings['delay'], size=(10, 1), key='delay', tooltip=gt('seconds'), border_width=1, pad=(70, 1))]
    ], background_color=bg)
    queuing_tab = Sg.Tab(gt('Queueing'), [
        [create_checkbox(gt('Reversed play next'), 'reversed_play_next', settings),
         create_checkbox(gt('Always queue library'), 'queue_library', settings, True)],
        [create_checkbox(gt('Populate queue on startup'), 'populate_queue_startup', settings),
         create_checkbox(gt('Persistent queue'), 'persistent_queue', settings, True)],
        [create_checkbox(gt('Smart queue'), 'smart_queue', settings)]
    ])
    ui_tab = Sg.Tab(gt('UI'), [
        [create_checkbox(gt('Save window positions'), 'save_window_positions', settings),
         create_checkbox(gt('Show track number'), 'show_track_number', settings, True)],
        [create_checkbox(gt('Left-side music controls'), 'flip_main_window', settings),
         create_checkbox(gt('Vertical GUI'), 'vertical_gui', settings, True)],
        [create_checkbox(gt('Show album art'), 'show_album_art', settings),
         create_checkbox(gt('Mini mode on top'), 'mini_on_top', settings, True)],
        [create_checkbox(gt('Use cover.* for album art'), 'folder_cover_override', settings),
         create_checkbox(gt('Show index in queue'), 'show_queue_index', settings, True)]
    ], background_color=bg)
    settings_tab_group = Sg.TabGroup([[general_tab, queuing_tab, ui_tab]], title_color=fg,
                                     border_width=0, selected_background_color=accent_color, font=FONT_TAB,
                                     tab_background_color=bg, selected_title_color=bg, background_color=bg)
    checkbox_col = Sg.Column([[settings_tab_group]], pad=((0, 0), (5, 0)))
    qr_code_params = {'tooltip': gt('Open Web GUI'), 'button_color': (bg, bg)}
    right_settings_col = Sg.Column([
        [Sg.Button(key='web_gui', image_data=qr_code, **qr_code_params)],
        [round_btn('settings.json', accent_color, bg, key='settings_file', pad=((15, 0), 5), button_width=10)],
        [round_btn('Changelog', accent_color, bg, key='changelog_file', pad=((15, 0), 5), button_width=10)]
    ], pad=(0, 0))
    link_params = {'text_color': LINK_COLOR, 'font': FONT_LINK, 'click_submits': True}
    layout = [
        [Sg.Text(f'Music Caster v{version} by', font=FONT_NORMAL),
         Sg.Text('Elijah Lopez <elijahllopezzgmail.com>', tooltip=gt('Send me an email'), key='open_email', **link_params),
         Sg.Text(f'GitHub', **link_params, key='open_github')],
        [checkbox_col, right_settings_col] if qr_code else [checkbox_col],
        [Sg.Listbox(settings['music_folders'], size=(62, 5), select_mode=Sg.SELECT_MODE_EXTENDED, text_color=fg,
                    key='music_folders', background_color=bg, font=FONT_NORMAL, bind_return_key=True,
                    no_scrollbar=True),
         Sg.Column([
             [icon_btn(X_ICON, 'remove_music_folder', gt('remove selected folder'), bg)],
             [icon_btn(PLUS_ICON, 'add_music_folder', gt('add folder'), bg)]])]]
    return Sg.Tab(gt('Settings'), layout, key='tab_settings')


def create_timer(settings, timer):
    shut_down = settings['timer_shut_down']
    hibernate = settings['timer_hibernate']
    sleep = settings['timer_sleep']
    fg, bg = settings['theme']['text'], settings['theme']['background']
    accent = settings['theme']['accent']
    do_nothing = not (shut_down or hibernate or sleep)
    # if timer is valid
    if time.time() < timer:
        timer_date = datetime.datetime.fromtimestamp(timer)
        timer_date = timer_date.strftime('%#I:%M %p')
        timer_text = gt('Timer set for $TIME').replace('$TIME', timer_date)
    else:
        timer_text = gt('No Timer Set')
    # wait for last track to finish setting
    cancel_button = round_btn(gt('Cancel Timer'), accent, bg, key='cancel_timer', visible=timer != 0)
    defaults = {'text_color': fg, 'background_color': bg, 'font': FONT_NORMAL, 'enable_events': True}
    layout = [
        [Sg.Radio(gt('Shut down when timer runs out'), 'TIMER', default=shut_down, key='shut_down', **defaults)],
        [Sg.Radio(gt('Sleep when timer runs out'), 'TIMER', default=sleep, key='sleep', **defaults)],
        [Sg.Radio(gt('Hibernate when timer runs out'), 'TIMER', default=hibernate, key='hibernate', **defaults)],
        [Sg.Radio(gt('Only Stop Playback').capitalize(), 'TIMER', default=do_nothing, key='timer_stop', **defaults)],
        [Sg.Text(gt('Enter minutes or HH:MM'), font=FONT_NORMAL),
         Sg.Input(key='timer_input', size=(11, 1), border_width=1),
         round_btn(gt('Submit'), accent, bg, key='timer_submit')],
        [Sg.Text(gt('Invalid Input (enter minutes or HH:MM)'), font=FONT_NORMAL, visible=False, key='timer_error')],
        [Sg.Text(timer_text, font=FONT_NORMAL, key='timer_text', size=(20, 1), metadata=timer != 0), cancel_button]
    ]
    return Sg.Tab(gt('Timer'), [[Sg.Column(layout, pad=(0, (50, 0)), justification='center')]], key='tab_timer')


def create_metadata_tab(settings):
    accent, bg = settings['theme']['accent'], settings['theme']['background']
    layout = [
        [Sg.Text('', size=(40, 1), key='metadata_file'),
         round_btn(gt('Select File'), accent, bg, key='metadata_browse'),
         round_btn(gt('Save'), accent, bg, key='metadata_save')],
        [Sg.Text(gt('Title'), size=(20, 1)), Sg.Input(key='metadata_title', border_width=1)],
        [Sg.Text(gt('Artist'), size=(20, 1)), Sg.Input(key='metadata_artist', border_width=1)],
        [Sg.Text(gt('Album'), size=(20, 1)), Sg.Input(key='metadata_album', border_width=1)],
        [Sg.Text(gt('Track Number'), size=(20, 1)), Sg.Input(key='metadata_track_num', border_width=1)],
        [Sg.Checkbox(gt('Explicit'), key='metadata_explicit', enable_events=True)],
        [Sg.Column([[round_btn(gt('Select artwork'), accent, bg, key='metadata_select_art', pad=(5, 10))],
                    [round_btn(gt('Search artwork'), accent, bg, key='metadata_search_art', pad=(5, 10))],
                    [round_btn(gt('Remove artwork'), accent, bg, key='metadata_remove_art', pad=(5, 10))]],
                   pad=((0, 20), 5)),
         Sg.Image(key='metadata_art')],
        [Sg.Text('', key='metadata_msg', text_color='green', size=(30, 1))]
    ]
    return Sg.Tab(gt('Metadata'), [[Sg.Column(layout, pad=(5, 5))]], key='tab_metadata')


def focus_window(window: Sg.Window):
    # makes window the top-most application via windows API (breaks if already in foreground)
    keybd_event(alt_key, 0, extended_key | 0, 0)
    ctypes.windll.user32.SetForegroundWindow.argtypes = (ctypes.wintypes.HWND,)
    ctypes.windll.user32.SetForegroundWindow(window.TKroot.winfo_id())
    keybd_event(alt_key, 0, extended_key | key_up, 0)
    window.normal()
    window.force_focus()


def window_is_foreground(window: Sg.Window):
    width, height, x, y = window.TKroot.winfo_width(), window.TKroot.winfo_height(), \
                          window.TKroot.winfo_rootx(), window.TKroot.winfo_rooty()
    if (width, height, x, y) != (1, 1, 0, 0):
        return window.TKroot.winfo_containing(x + (width // 2), y + (height // 2)) is not None
    return False


# TKDnD
# noinspection PyProtectedMember
def drop_target_register(widget, *dndtypes):
    widget.tk.call('tkdnd::drop_target', 'register', widget._w, dndtypes)


# noinspection PyProtectedMember
def dnd_bind(widget, sequence=None, func=None, add=None, need_cleanup=True):
    """Internal function."""
    what = ('bind', widget._w)
    if isinstance(func, str):
        widget.tk.call(what + (sequence, func))
    elif func:
        func_id = widget._register(func, widget._substitute_dnd, need_cleanup)
        cmd = '%s%s %s' % (add and '+' or '', func_id, widget._subst_format_str_dnd)
        widget.tk.call(what + (sequence, cmd))
        return func_id
    elif sequence:
        return widget.tk.call(what + (sequence,))
    else:
        return widget.tk.splitlist(widget.tk.call(what))


def get_cut_text(window, key):
    # fix for weird GUI cut/copy behaviour
    cut_text = ''
    new_text = window[key].get()
    if not new_text: return window.metadata[key]
    i = 0
    for v in window.metadata[key]:
        if i >= len(new_text) or v != new_text[i]: cut_text += v
        else: i += 1
    return cut_text
