# flake8: noqa: E402
import audioop
import base64
import ctypes
import glob
import io
import locale
import logging
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import Tuple
import unicodedata
import webbrowser
from base64 import b64decode, b64encode
from contextlib import suppress
from functools import lru_cache, wraps
from itertools import chain, cycle, repeat
from math import floor
from pathlib import Path
from queue import Empty, LifoQueue
from random import getrandbits
from subprocess import DEVNULL, PIPE, CalledProcessError, Popen, check_output
from threading import Lock, Thread
from urllib.parse import parse_qs, urlencode, urlparse
from uuid import getnode
from zipfile import ZipFile

# 3rd party imports
import deemix.utils.localpaths as __lp

# local imports
from b64_images import DEFAULT_ART, REPEAT_ALL_IMG, REPEAT_OFF_IMG, REPEAT_ONE_IMG
from deezer import TrackFormats

__lp.musicdata = '/dz'
import mutagen
import mutagen._file
import mutagen.flac
import mutagen.id3
import pyaudio
import pypresence
import requests
from meta import AUDIO_EXTS, AUDIO_HANDLER_EXTS, COVER_NORMAL, USER_AGENT, State
from mutagen._util import MutagenError
from mutagen.aac import AAC
from mutagen.id3._util import ID3NoHeaderError
from mutagen.mp3 import MP3, EasyMP3, HeaderNotFoundError
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE
from PIL import Image, ImageDraw, ImageFile, ImageFont, UnidentifiedImageError
from pychromecast import CastInfo
from wavinfo import WavInfoEOFError, WavInfoReader  # until mutagen supports .wav
from youtube_comment_downloader import SORT_BY_POPULAR, YoutubeCommentDownloader

# CONSTANTS
IS_FROZEN = getattr(sys, 'frozen', False)
ImageFile.LOAD_TRUNCATED_IMAGES = True
yt_comment_downloader = YoutubeCommentDownloader()
SPOTIFY_API = 'https://api.spotify.com/v1'
# for stealing focus when bring window to front

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
        if not self.alive:
            return  # ensure that start() was called
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
        if self.alive:
            return
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
        if platform.system() == 'Windows':
            if not self.alive:
                if self.pa is None:
                    self.pa = pyaudio.PyAudio()
                # initialization process takes ~0.2 seconds
                Thread(target=self._start_recording, name='SystemAudioRecorder', daemon=True).start()
        else:
            print('TODO: SystemAudioRecorder')


class InvalidAudioFile(Exception):
    pass


class Unknown(str):
    __slots__ = 'property'

    def __new__(cls, _property):
        obj = super(Unknown, cls).__new__(cls)
        obj.property = _property
        return obj

    def __repr__(self):
        return t(f'Unknown {self.property}')

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


def exception_wrapper(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            f(*args, **kwargs)
        except Exception as e:
            print(f'Handled exception in {f.__name__}:', e)
    return wrapper


class DiscordPresence:
    """
    Exception safe wrapper for pypresence
    """
    rich_presence: pypresence.Presence = None
    MUSIC_CASTER_DISCORD_ID = '696092874902863932'

    @classmethod
    @exception_wrapper
    def init_rpc(cls):
        if cls.rich_presence is None:
            cls.rich_presence = pypresence.Presence(cls.MUSIC_CASTER_DISCORD_ID, timeout=2)

    @classmethod
    @exception_wrapper
    def connect(cls, confirm_connect=True):
        if confirm_connect:
            cls.init_rpc()
            cls.rich_presence.connect()

    @classmethod
    @exception_wrapper
    def update(cls, state: str, details: str, large_text: str, end: int = 0,
               large_image='default', small_image='logo', small_text='Music Caster', confirm_connect=True):
        if confirm_connect:
            cls.init_rpc()
            cls.rich_presence.update(state=state, details=details, large_image=large_image, large_text=large_text,
                                     small_image=small_image, small_text=small_text)

    @classmethod
    @exception_wrapper
    def clear(cls, confirm=True):
        if confirm:
            cls.rich_presence.clear()

    @classmethod
    @exception_wrapper
    def close(cls):
        if cls.rich_presence is not None:
            cls.rich_presence.close()


# friendly interface to create system tray menus out of local device or cast device
#   or in the future, other wireless devices
# otherwise would have to write lots of conditionals to make things work smoothly
# TODO: should be interloped with playback functionalities as well to abstract that PITA
class Device:
    CHECK_MARK = '✓'

    def __init__(self, cast_info_or_none=None):
        self.__device = cast_info_or_none
        self.is_cast_info = isinstance(self.__device, CastInfo)
        self.is_local_device = not self.is_cast_info

    @property
    def id(self):
        return str(self.__device.uuid) if isinstance(self.__device, CastInfo) else None

    @classmethod
    def LOCAL_DEVICE(cls):
        return t('Local device')

    @property
    def name(self):
        if isinstance(self.__device, CastInfo):
            return self.__device.friendly_name
        return self.LOCAL_DEVICE()

    def as_tray_name(self, active_id):
        if active_id == self.id:
            return f'{self.CHECK_MARK} {self.name}'
        return f'    {self.name}'

    @property
    def tray_key(self):
        return f'device:{self.id}' if self.is_cast_info else 'device:0'

    @property
    def gui_key(self):
        return f'device::{self.id}' if self.is_cast_info else 'device::0'

    def as_tray_item(self, active_id) -> tuple:
        return self.as_tray_name(active_id), self.tray_key

    def __eq__(self, other):
        return self.id == other.id

    def __str__(self):
        return self.name

    def __repr__(self):
        return f'Device(id={self.id}, name={self.name})'


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


try:
    LANGUAGES_FOLDER = f'{sys._MEIPASS}/languages'
except AttributeError:
    if os.path.exists('src/languages'):
        print('WARNING 345:  application not running in src directory')
        LANGUAGES_FOLDER = 'src/languages'
    else:
        LANGUAGES_FOLDER = 'languages'


@lru_cache(maxsize=1)
def get_languages():
    return list(chain([''], (get_file_name(lang) for lang in glob.iglob(f'{glob.escape(LANGUAGES_FOLDER)}/*.txt'))))


@lru_cache(maxsize=3)
def get_lang_pack(lang):
    # fails if not in src directory
    en_lang_pack, other_lang_pack = {}, []
    with open(f'{LANGUAGES_FOLDER}/{lang}.txt', encoding='utf-8') as f:
        i = 0
        line = f.readline().strip()
        while line:
            if not line.startswith('#'):
                if lang == 'en':
                    en_lang_pack[line] = i
                else:
                    other_lang_pack.append(line)
                i += 1
            line = f.readline().strip()
    return en_lang_pack if lang == 'en' else other_lang_pack


def get_display_lang():
    if platform.system() == 'Windows':
        kernal32 = ctypes.windll.kernel32
        return locale.windows_locale[kernal32.GetUserDefaultUILanguage()].split('_', 1)[0]
    else:
        return os.environ['LANG'].split('_', 1)[0]


@lru_cache
def log_translation_error(string, lang):
    log = logging.getLogger('music_caster')
    log.error(f'failed to translate `{string}` to {lang}', exc_info=True)


def get_translation(string, lang='', as_title=False):
    """ Translates string from English to lang or display language if valid
    :param string: English string
    :param lang: Optional code to translate to. Defaults to using display language
    :param as_title: The phrase returned has each word capitalized
    :return: string translated to display language """
    try:
        string = get_lang_pack(lang or get_display_lang())[get_lang_pack('en')[string]]
    except (IndexError, KeyError, FileNotFoundError):
        if lang != 'en' and lang != '':
            log_translation_error(string, lang)
    if as_title:
        string = ' '.join(word[0].upper() + word[1:] for word in string.split())
    return string


def t(string, as_title=False):
    return get_translation(string, lang=State.lang, as_title=as_title)


def natural_key_file(filename):
    filename = unicodedata.normalize('NFKD', get_file_name(filename).casefold())
    filename = u''.join([c for c in filename if not unicodedata.combining(c)])
    return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', filename)]


def valid_color_code(code):
    match = re.search(r'^#(?:[\da-fA-F]{3}){1,2}$', code)
    return match


def get_audio_length(file_path) -> int:
    """ throws InvalidAudioFile if file is invalid
    :param file_path:
    :return: length in seconds """
    try:
        if file_path.casefold().endswith('.wav'):
            a = WavInfoReader(file_path)
            length = a.data.frame_count / a.fmt.sample_rate # type:ignore
        elif file_path.casefold().endswith('.wma'):
            try:
                audio_info = mutagen.File(file_path).info  # type:ignore
                length = audio_info.length
            except AttributeError:
                audio_info = AAC(file_path).info
                length = audio_info.length
        elif file_path.casefold().endswith('.opus'):
            audio_info = mutagen.File(file_path).info  # type:ignore
            length = audio_info.length
        else:
            audio_info = mutagen.File(file_path).info  # type:ignore
            length = audio_info.length
        return length
    except (AttributeError, HeaderNotFoundError, MutagenError, WavInfoEOFError, StopIteration) as e:
        raise InvalidAudioFile(f'{file_path} is an invalid audio file') from e


def valid_audio_file(uri) -> bool:
    """
    check if uri has a valid audio extension
    uri does not have to be a file that exists
    """
    return Path(uri).suffix.casefold() in AUDIO_EXTS


def set_metadata(file_path: str, metadata: dict):
    ext = os.path.splitext(file_path)[1].casefold()
    audio: mutagen._file.FileType = mutagen.File(file_path) # type: ignore
    title = metadata['title']
    artists = metadata['artist'].split(', ') if ', ' in metadata['artist'] else metadata['artist'].split(',')
    album = metadata['album']
    track_place = metadata['track_number']      # X/Y
    track_number = track_place.split('/')[0]    # X
    rating = '1' if metadata['explicit'] else '0'
    # b64 album art data should be b64 as a string not as bytes
    if isinstance(metadata.get('art'), bytes):
        metadata['art'] = metadata['art'].decode()
    if '/' not in track_place:
        tracks = max(1, int(track_place))
        track_place = f'{track_place}/{tracks}'
    if isinstance(audio, (MP3, WAVE)) or ext in {'.mp3', '.wav'}:
        if title:
            audio['TIT2'] = mutagen.id3._frames.TIT2(text=metadata['title'])
        if artists:
            audio['TPE1'] = mutagen.id3._frames.TPE1(text=artists)
            audio['TPE2'] = mutagen.id3._frames.TPE1(text=artists[0])  # album artist
        audio['TCMP'] = mutagen.id3._frames.TCMP(text=track_number)
        audio['TRCK'] = mutagen.id3._frames.TRCK(text=track_place)
        audio['TPOS'] = mutagen.id3._frames.TPOS(text=track_place)
        if album:
            audio['TALB'] = mutagen.id3._frames.TALB(text=album)
        # audio['TDRC'] = mutagen.id3.TDRC(text=metadata['year'])
        # audio['TCON'] = mutagen.id3.TCON(text=metadata['genre'])
        # audio['TPUB'] = mutagen.id3.TPUB(text=metadata['publisher'])
        audio['TXXX:RATING'] = mutagen.id3._frames.TXXX(text=rating, desc='RATING')
        audio['TXXX:ITUNESADVISORY'] = mutagen.id3._frames.TXXX(text=rating, desc='ITUNESADVISORY')
        if metadata.get('art') is not None:
            img_data = b64decode(metadata['art'])
            audio['APIC:'] = mutagen.id3._frames.APIC(encoding=0, mime=metadata['mime'], type=3, data=img_data)
        else:  # remove all album art
            for k in tuple(audio.keys()):
                if 'APIC:' in k:
                    audio.pop(k)
    elif isinstance(audio, MP4):
        if title:
            audio['©nam'] = [title]
        if artists:
            audio['©ART'] = artists
        if album:
            audio['©alb'] = [album]
        audio['trkn'] = [tuple((int(x) for x in track_place.split('/')))]
        audio['rtng'] = [int(rating)]
        if metadata.get('art') is not None:
            image_format = 14 if metadata['mime'].endswith('png') else 13
            img_data = b64decode(metadata['art'])
            audio['covr'] = [MP4Cover(img_data, imageformat=image_format)]
        elif 'covr' in audio:
            del audio['covr']
    elif isinstance(audio, (OggOpus, OggVorbis)):
        if title:
            audio['title'] = [title]
        if artists:
            audio['artist'] = artists
        if album:
            audio['album'] = [album]
        audio['rtng'] = [rating]
        audio['trkn'] = track_place
        if metadata.get('art') is not None:
            img_data = metadata['art']  # b64 data
            audio['metadata_block_picture'] = img_data
            audio['mime'] = metadata['mime']
        else:
            audio.pop('APIC:', None)
            audio.pop('metadata_block_picture', None)
    else:  # FLAC?
        if title:
            audio['TITLE'] = title # type: ignore
        if artists:
            audio['ARTIST'] = artists # type: ignore
        if album:
            audio['ALBUM'] = album # type: ignore
        audio['TRACKNUMBER'] = track_number  # type: ignore
        audio['TRACKTOTAL'] = track_place.split('/')[1]  # type: ignore
        audio['ITUNESADVISORY'] = rating  # type: ignore
        if metadata.get('art') is not None:
            if ext == '.flac':
                img_data = b64decode(metadata['art'])
                pic = mutagen.flac.Picture()
                pic.mime = metadata['mime']
                pic.data = img_data
                pic.type = 3
                audio.clear_pictures() # type: ignore
                audio.add_picture(pic) # type: ignore
            else:
                audio['APIC:'] = metadata['art'] # type: ignore
                audio['mime'] = metadata['mime'] # type: ignore
        else:
            # remove existing album art
            if ext == '.flac':
                audio.clear_pictures() # type: ignore
            else:
                # remove all album art
                for k in tuple(audio.keys()):
                    if 'APIC:' in k:
                        audio.pop(k)
    audio.save()


def get_metadata(file_path: str):
    title = unknown_title = Unknown('Title')
    artist = unknown_artist = Unknown('Artist')
    album = unknown_album = Unknown('Album')
    length = None
    try:
        a = mutagen.File(file_path)
        with suppress(AttributeError):
            length = a.info.length
        if isinstance(a, MP3):
            audio = dict(EasyMP3(file_path))
            audio['rating'] = a.get('TXXX:RATING', a.get('TXXX:ITUNESADVISORY', ['0']))
        elif isinstance(a, MP4):
            audio = dict(mutagen.File(file_path))
            audio['rating'] = audio.get('rtng', [0])
            for (tag, normalized) in (('©nam', 'title'), ('©alb', 'album'), ('©ART', 'artist')):
                if tag in audio:
                    audio[normalized] = audio.pop(tag)
            audio['tracknumber'] = audio.get('trkn', [('1', '1')])[0]
        elif isinstance(a, (OggOpus, OggVorbis)):
            audio = dict(a)
            if 'rtng' in audio:
                audio['rating'] = audio.pop('rtng')
            if 'trkn' in audio:
                audio['tracknumber'] = audio.pop('trkn')
        elif isinstance(a, WAVE) or file_path.endswith('.wav'):
            audio = WavInfoReader(file_path).info.to_dict()
            audio = {'title': [audio['title']], 'artist': [audio['artist']], 'album': [audio['product']]}
        elif a is not None:
            audio = dict(a)
            audio = {k.casefold(): audio[k] for k in audio}
            if file_path.endswith('.wma'):
                audio = {k: [audio[k][0].value] for k in audio}
        else:
            audio = {}
    except TypeError as e:
        logging.getLogger('music_caster').error(repr(e))
        logging.getLogger('music_caster').info(f'Could not open {file_path} as audio file')
        raise InvalidAudioFile(f'Is {file_path} a valid audio file?') from e
    except (ID3NoHeaderError, HeaderNotFoundError, AttributeError, WavInfoEOFError, StopIteration):
        logging.getLogger('music_caster').info(f'Metadata not found for {file_path}')
        audio = {}
    title = str(audio.get('title', [title])[0])
    album = str(audio.get('album', [album])[0])
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
    if not title:
        title = unknown_title
    if not artist:
        artist = unknown_artist
    if not album:
        album = unknown_album
    if title == unknown_title or artist == unknown_artist:
        # if title or artist are unknown, use the basename of the URI (excluding extension)
        sort_key = get_file_name(file_path)
    else:
        sort_key = State.track_format.replace('&title', title).replace('&artist', artist)
        sort_key.replace('&album', album if album != unknown_album else '')
        sort_key = sort_key.replace('&trck', track_number or '')
    metadata = {'title': title, 'artist': artist, 'album': album, 'explicit': is_explicit,
                'sort_key': sort_key.casefold(), 'track_number': '1' if track_number is None else track_number,
                # float works with sqlite REAL
                'time_modified': os.path.getmtime(file_path)}
    if length is not None:
        metadata['length'] = length
    return metadata


def open_in_browser(url):
    t = Thread(target=webbrowser.open, daemon=True, args=(url,))
    t.start()
    return t


def get_album_art(file_path: str, folder_cover_override=False) -> Tuple[str, bytes]:  # mime: str, data: str
    with suppress(MutagenError, AttributeError):
        folder = os.path.dirname(file_path)
        if folder_cover_override:
            for ext in ('png', 'jpg', 'jpeg'):
                folder_cover = os.path.join(folder, f'cover.{ext}')
                if os.path.exists(folder_cover):
                    with open(folder_cover, 'rb') as f:
                        return ext, base64.b64encode(f.read())
        audio = mutagen.File(file_path) # type: ignore
        if isinstance(audio, mutagen.flac.FLAC):
            pics = mutagen.flac.FLAC(file_path).pictures
            with suppress(IndexError):
                return pics[0].mime, base64.b64encode(pics[0].data)
        elif isinstance(audio, MP4):
            with suppress(KeyError, IndexError):
                cover = audio['covr'][0]
                image_format = cover.imageformat
                mime = 'image/png' if image_format == 14 else 'image/jpeg'
                return mime, base64.b64encode(cover)
        elif isinstance(audio, (OggOpus, OggVorbis)):
            with suppress(KeyError, IndexError):
                mime = audio.get('mime')
                if mime is None:
                    mime = ['image/jpeg']
                mime = mime[0]
                return mime, audio['metadata_block_picture'][0]
        else:
            # ID3 or something else
            if audio is not None:
                for tag in audio.keys():
                    if 'APIC' in tag:
                        try:
                            return audio[tag].mime, base64.b64encode(audio[tag].data)
                        except AttributeError:
                            mime = audio['mime'][0].value if 'mime' in audio else 'image/jpeg'
                            return mime, base64.b64encode(audio[tag][0].value)
    app_logger = logging.getLogger('music_caster')
    app_logger.info(f'File {Path(file_path).name} does not have album art. Returning image/jpeg, DEFAULT_ART instead')
    return 'image/jpeg', DEFAULT_ART


def fix_path(path, by_os=True): return str(Path(path)) if by_os else path.replace('\\', '/')


def get_first_artist(artists: str) -> str: return artists.split(', ', 1)[0]


def get_ipv6():
    # return next((i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None) if i[0] == socket.AF_INET6))
    if platform.system() == 'Linux':
        for logical_name in os.listdir('/sys/class/net'):
            cmd = f"ip addr show dev {logical_name} | awk '{{if ($1==\"inet6\") {{print $2}}}}'"
            p = Popen(cmd, shell=True,
                      stdout=PIPE, stdin=DEVNULL, stderr=DEVNULL, text=True)
            ip = p.stdout.readline().strip()
            if ip != '':
                return ip
    with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as s:
        try:
            # doesn't even have to be reachable
            s.connect(('fe80::116a:fd0a:4a0a:42a7', 1))
            ip = f'[{s.getsockname()[0]}]'
        except Exception:
            ip = get_ipv4()
    return ip


# https://regex101.com/
IPV4_WIFI_PATTERN = re.compile(r'Wireless LAN adapter Wi-Fi:((.|\n)*?)?\s+IPv4 Address.*:\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')
IPV4_GENERAL_PATTERN = re.compile(r'IPv4 Address.*:\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')


def clean_ipconfig(ipconfig_raw):
    # TODO: there is a way to optimise this and return a single IP, but that requires matching each description
    ipconfig_output_split = ipconfig_raw.split('\n\n')[1:]
    filtered_output = ''
    for i in range(len(ipconfig_output_split) // 2):
        if (
            'WSL' not in ipconfig_output_split[i * 2]
            and 'vEthernet' not in ipconfig_output_split[i * 2]
            and 'Hyper-V' not in ipconfig_output_split[i * 2 + 1]
        ):
            filtered_output += ipconfig_output_split[i * 2] + ipconfig_output_split[i * 2 + 1]
    return filtered_output


def get_ipv4():
    try:
        if platform.system() != 'Windows':
            raise FileNotFoundError
        ipconfig_output = clean_ipconfig(check_output(['ipconfig'], shell=True, text=True, encoding='iso8859-2'))
        wifi_match = IPV4_WIFI_PATTERN.findall(ipconfig_output)
        if wifi_match:
            return wifi_match[-1][-1]
        return IPV4_GENERAL_PATTERN.findall(ipconfig_output)[-1]
    except (IndexError, CalledProcessError, FileNotFoundError):
        # fallback in case the ipv4 cannot be found in ipconfig
        # return next((i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None) if i[0] == socket.AF_INET))
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            try:
                # doesn't even have to be reachable
                s.connect(('192.168.1.2', 1))
                ip = s.getsockname()[0]
            except Exception:
                ip = '127.0.0.1'
        return ip


def get_lan_ip() -> str:
    return get_ipv6()


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


@lru_cache(maxsize=1)
def dz():
    from deemix.__main__ import Deezer  # 1.4 seconds. 0.4 due to Downloader
    return Deezer()


@lru_cache(maxsize=2)
def ydl(proxy=None, quiet=False):
    from yt_dlp import YoutubeDL
    opts = {
        'quiet': quiet,
        'verbose': not quiet,
        'socket_timeout': 10
    }
    if proxy is not None:
        opts['proxy'] = proxy
    return YoutubeDL(opts)


def ydl_extract_info(url, quiet=False):
    """
    Raises IOError instead of YoutubeDL's DownloadError, saving us time on imports
    """
    from yt_dlp.utils import DownloadError
    with suppress(DownloadError):
        return ydl(quiet=quiet).extract_info(url, download=False)
    try:
        return ydl(get_proxy(False)['https'], quiet=quiet).extract_info(url, download=False)
    except DownloadError as e:
        raise IOError from e


@lru_cache(maxsize=1)
def get_yt_id(url, ignore_playlist=False):
    query = urlparse(url)
    if query.hostname == 'youtu.be':
        return query.path[1:]
    if query.hostname in {'www.youtube.com', 'youtube.com', 'music.youtube.com'}:
        if not ignore_playlist:
            with suppress(KeyError):
                return parse_qs(query.query)['list'][0]
        if query.path == '/watch':
            return parse_qs(query.query)['v'][0]
        if query.path[:7] == '/watch/':
            return query.path.split('/')[2]
        if query.path[:7] == '/embed/':
            return query.path.split('/')[2]
        if query.path[:3] == '/v/':
            return query.path.split('/')[2]


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


@lru_cache(maxsize=1)
def is_os_64bit(): return platform.machine().endswith('64')


def delete_sub_key(root, current_key):
    import winreg as wr
    access = wr.KEY_ALL_ACCESS | wr.KEY_WOW64_64KEY
    with suppress(FileNotFoundError):
        with wr.OpenKeyEx(root, current_key, 0, access) as parent_key:
            info_key = wr.QueryInfoKey(parent_key)
            for x in range(info_key[0]):
                sub_key = wr.EnumKey(parent_key, x)
                try:
                    wr.DeleteKeyEx(parent_key, sub_key, access)
                except OSError:
                    delete_sub_key(root, '\\'.join([current_key, sub_key]))
            wr.DeleteKeyEx(parent_key, '', access)


def add_reg_handlers(path_to_exe, add_folder_context=True):
    """ Register Music Caster as a program to open audio files and folders """
    # https://docs.microsoft.com/en-us/visualstudio/extensibility/registering-verbs-for-file-name-extensions?view=vs-2019
    import winreg as wr
    classes_path = r'SOFTWARE\Classes'
    mc_file = 'MusicCaster_file'
    write_access = wr.KEY_WRITE | wr.KEY_WOW64_64KEY
    read_access = wr.KEY_READ | wr.KEY_WOW64_64KEY
    path_to_exe = str(path_to_exe)
    # create URL protocol handler
    url_protocol = fr'{classes_path}\music-caster'
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, url_protocol, 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, 'URL:music-caster Protocol')
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, url_protocol, 0, write_access) as key:
        wr.SetValueEx(key, 'URL Protocol', 0, wr.REG_SZ, '')
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, fr'{url_protocol}\DefaultIcon', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}"')
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, fr'{url_protocol}\shell\open\command', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" --urlprotocol "%1"')

    # create Audio File type
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, fr'{classes_path}\{mc_file}', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, 'Audio File')
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, fr'{classes_path}\{mc_file}\DefaultIcon', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, path_to_exe)  # define icon location

    # create play context | open handler
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, fr'{classes_path}\{mc_file}\shell\open', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, t('Play with Music Caster'))
        wr.SetValueEx(key, 'MultiSelectModel', 0, wr.REG_SZ, 'Player')
        wr.SetValueEx(key, 'Icon', 0, wr.REG_SZ, path_to_exe)
    command_path = fr'{classes_path}\{mc_file}\shell\open\command'
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, command_path, 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" --shell "%1"')

    # create queue context
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, fr'{classes_path}\{mc_file}\shell\queue', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, t('Queue in Music Caster'))
        wr.SetValueEx(key, 'MultiSelectModel', 0, wr.REG_SZ, 'Player')
        wr.SetValueEx(key, 'Icon', 0, wr.REG_SZ, path_to_exe)
    command_path = fr'{classes_path}\{mc_file}\shell\queue\command'
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, command_path, 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" -q --shell "%1"')

    # create play next context
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, fr'{classes_path}\{mc_file}\shell\play_next', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, t('Play next in Music Caster'))
        wr.SetValueEx(key, 'MultiSelectModel', 0, wr.REG_SZ, 'Player')
        wr.SetValueEx(key, 'Icon', 0, wr.REG_SZ, path_to_exe)
    command_path = fr'{classes_path}\{mc_file}\shell\play_next\command'
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, command_path, 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" -n --shell "%1"')

    # set file handlers
    for ext in AUDIO_HANDLER_EXTS:
        key_path = fr'{classes_path}\.{ext}'
        try:  # check if key exists
            with wr.OpenKeyEx(wr.HKEY_CURRENT_USER, key_path, 0, read_access) as _:
                pass
        except (WindowsError, FileNotFoundError):
            # create key for extension if it does not exist with MC as the default program
            with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, key_path, 0, write_access) as key:
                # set as default program unless .mp4 because that's a video format
                wr.SetValueEx(key, None, 0, wr.REG_SZ, mc_file)
        # add to Open With (prompts user to set default program when they try playing a file)
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, fr'{key_path}\\OpenWithProgids', 0, write_access) as key:
            wr.SetValueEx(key, mc_file, 0, wr.REG_NONE, b'')  # type needs to be bytes

    play_folder_key_path = fr'{classes_path}\Directory\shell\MusicCasterPlayFolder'
    queue_folder_key_path = fr'{classes_path}\Directory\shell\MusicCasterQueueFolder'
    play_next_folder_key_path = fr'{classes_path}\Directory\shell\MusicCasterPlayNextFolder'
    if add_folder_context:
        # set "open folder in Music Caster" command
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, play_folder_key_path, 0, write_access) as key:
            wr.SetValueEx(key, None, 0, wr.REG_SZ, t('Play with Music Caster'))
            wr.SetValueEx(key, 'Icon', 0, wr.REG_SZ, path_to_exe)
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, fr'{play_folder_key_path}\\command', 0, write_access) as key:
            wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" --shell "%1"')
        # set "queue folder in Music Caster" command
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, queue_folder_key_path, 0, write_access) as key:
            wr.SetValueEx(key, None, 0, wr.REG_SZ, t('Queue in Music Caster'))
            wr.SetValueEx(key, 'Icon', 0, wr.REG_SZ, path_to_exe)
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, fr'{queue_folder_key_path}\\command', 0, write_access) as key:
            wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" -q --shell "%1"')
        # set "play folder next in Music Caster" command
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, play_next_folder_key_path, 0, write_access) as key:
            wr.SetValueEx(key, None, 0, wr.REG_SZ, t('Play next in Music Caster'))
            wr.SetValueEx(key, 'Icon', 0, wr.REG_SZ, path_to_exe)
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, fr'{play_next_folder_key_path}\\command', 0, write_access) as key:
            wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" -n --shell "%1"')
    else:
        # remove commands for folders
        delete_sub_key(wr.HKEY_CURRENT_USER, play_folder_key_path)
        delete_sub_key(wr.HKEY_CURRENT_USER, queue_folder_key_path)
        delete_sub_key(wr.HKEY_CURRENT_USER, play_next_folder_key_path)


def get_default_output_device():
    """ returns the PyAudio formatted name of the default output device """
    import winreg as wr
    read_access = wr.KEY_READ | wr.KEY_WOW64_64KEY
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
            with suppress(FileNotFoundError):
                last_used = wr.QueryValueEx(device_key, 'Level:0')[0]
                if last_used > active_last_used:  # the bigger the number, the more recent it was used
                    active_last_used = last_used
                    active_device_name = pa_name
    return active_device_name


def resize_img(base64data: bytes, bg, new_size=COVER_NORMAL, default_art=None) -> bytes:
    """ Resize and return b64 img data to new_size (w, h). (use .decode() on return statement for str) """

    try:
        img_data = io.BytesIO(b64decode(base64data))
        art_img: Image.Image = Image.open(img_data)
    except UnidentifiedImageError as e:
        if default_art is None:
            raise OSError from e
        img_data = io.BytesIO(b64decode(default_art))
        art_img: Image.Image = Image.open(img_data)
    w, h = art_img.size
    if w == h:
        # resize a square
        img = art_img.resize(new_size, Image.Resampling.LANCZOS)
    else:
        # resize by shrinking the longest side to the new_size
        ratios = (1, h / w) if w > h else (w / h, 1)
        ratio_size = (round(new_size[0] * ratios[0]), round(new_size[1] * ratios[1]))
        art_img = art_img.resize(ratio_size, Image.Resampling.LANCZOS)
        paste_width = (new_size[0] - ratio_size[0]) // 2
        paste_height = (new_size[1] - ratio_size[1]) // 2
        img = Image.new('RGB', new_size, color=bg)
        img.paste(art_img, (paste_width, paste_height))
    data = io.BytesIO()
    if img.mode == 'CMYK':
        img = img.convert('RGB')
    img.save(data, format='png')
    return b64encode(data.getvalue())


def export_playlist(playlist_name, uris):
    # exports uris to ~/Downloads/safe(playlist_name).m3u
    playlist_name = re.sub(r'(?u)[^-\w. ]', '', playlist_name)  # clean name
    playlist_path = Path.home() / 'Downloads'
    playlist_path.mkdir(parents=True, exist_ok=True)
    playlist_path /= f'{playlist_name}.m3u'
    with open(playlist_path, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for uri in uris:
            if uri.replace('\\', '/') != playlist_path:
                f.write(uri + '\n')
    return str(playlist_path)


def parse_m3u(playlist_file):
    with open(playlist_file, errors='ignore', encoding='utf-8') as f:
        for line in iter(lambda: f.readline(), ''):
            if not line.startswith('#'):
                line = line.lstrip('file:').lstrip('/').rstrip()
                # an m3u file cannot contain itself
                if line != playlist_file:
                    yield line


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
    from bs4 import (
        BeautifulSoup,  # 0.32 seconds if at top level, here it is 0.1 seconds
    )
    try:
        response = requests.get('https://free-proxy-list.net/', headers={'user-agent': USER_AGENT})
        scraped_proxies = set()
        soup = BeautifulSoup(response.text, 'lxml')
        table = soup.find('table')
        for row in table.find_all('tr'): # type: ignore
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
        for proxy in sorted(scraped_proxies):
            proxies.extend(repeat(proxy, 3))
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
    access_token = re.search('"accessToken":"([^"]*)', r.text).group(1)
    return {'Authorization': f'Bearer {access_token}'}


# TODO: main_event == 'metadata_search_art' and gui_window['metadata_file'].get():
def search_album_art_spotify(title, artist, mkt):
    for mkt in {'MX', 'CA', 'US', 'UK', 'HK'}:
        url = f'https://api.spotify.com/v1/search?q={title}'
        if artist:
            url += f'+artist:{artist}'
        url += f'&type=track&market={mkt}'
        r = requests.get(url, headers=get_spotify_headers()).json()
        if 'tracks' in r:
            for art_link in (item['album']['images'][0]['url'] for item in r['tracks']['items']):
                original_art = base64.b64encode(requests.get(art_link).content).decode()
                return original_art


def parse_spotify_track(track_obj, parent_url='') -> dict:
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
    try:
        src_url = track_obj['external_urls']['spotify']
    except KeyError:
        src_url = parent_url
    track_number = str(track_obj['track_number'])
    sort_key = State.track_format.replace('&title', title).replace('&artist', artist).replace('&album', str(album))
    sort_key = sort_key.replace('&trck', track_number).casefold()
    metadata = {'src': src_url, 'title': title, 'artist': artist, 'album': album,
                'explicit': is_explicit, 'sort_key': sort_key, 'track_number': track_number}
    with suppress(IndexError):
        metadata['art'] = track_obj['album']['images'][0]['url']
    return metadata


@lru_cache
def get_spotify_track(url):
    try:
        track_id = urlparse(url).path.split('/track/', 1)[1]
    except IndexError:
        # e.g. */album/*?highlight=spotify:track:587w9pOR9UNvFJOwkW7NgD
        track_id = re.search(r'track:.*', url).group()[6:]
    track = requests.get(f'{SPOTIFY_API}/tracks/{track_id}', headers=get_spotify_headers()).json()
    return {**parse_spotify_track(track), 'src': url}


@lru_cache
def get_spotify_album(url):
    album_id = urlparse(url).path.split('/album/', 1)[1]
    api_url = f'{SPOTIFY_API}/albums/{album_id}'
    r = requests.get(api_url, headers=get_spotify_headers()).json()
    return [parse_spotify_track({**track, 'album': r}, parent_url=url) for track in r['tracks']['items']]


def get_spotify_playlist(url):
    playlist_id = urlparse(url).path.split('/playlist/', 1)[1]
    api_url = f'{SPOTIFY_API}/playlists/{playlist_id}/tracks'
    response = requests.get(api_url, headers=get_spotify_headers()).json()
    results = response['items']
    while response['next'] is not None:
        response = requests.get(response['next'], headers=get_spotify_headers()).json()
        results.extend(response['items'])
    return [parse_spotify_track(result['track'], url) for result in results if isinstance(result['track'], dict)]


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
    import sqlite3

    import browser_cookie3 as bc3  # 0.388 seconds if on top level, 0.06 here
    for cookie_storage in (bc3.chrome, bc3.firefox, bc3.opera, bc3.edge, bc3.chromium):
        cookies = []
        with suppress(bc3.BrowserCookieError, sqlite3.OperationalError):
            cookie_storage = cookie_storage()
            for cookie in cookie_storage:
                if cookie.domain.count(domain_contains):
                    formatted_cookie = f'{cookie.name}={cookie.value}'
                    if (not cookie_name or cookie.name == cookie_name) and not cookie.is_expired():
                        cookie_to_use = cookie.value if return_value else formatted_cookie
                        if return_first:
                            return cookie_to_use
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
    from deemix.decryption import generateBlowfishKey, generateCryptedStreamURL
    artists = []
    sng_contributors = track_obj['SNG_CONTRIBUTORS']
    if isinstance(sng_contributors, list):
        sng_contributors = {'main_artist': sng_contributors}
    try:
        main_artists = sng_contributors['main_artist']
    except KeyError:
        main_artists = sng_contributors['mainartist']
    for artist in main_artists + sng_contributors.get('featuring', []):
        include = True
        for added_artist in artists:
            if added_artist in artist:
                include = False
                break
        if include:
            artists.append(artist)
    artist_str = ', '.join(artists)
    art = f"https://cdns-images.dzcdn.net/images/cover/{track_obj['ALB_PICTURE']}/1000x1000-000000-80-0-0.jpg"
    title, album = track_obj['SNG_TITLE'], track_obj['ALB_TITLE']
    length = int(track_obj['DURATION'])
    is_explicit = track_obj['EXPLICIT_TRACK_CONTENT']['EXPLICIT_LYRICS_STATUS'] == '1'
    sng_id = track_obj['SNG_ID']
    metadata = {
        'art': art, 'title': title, 'ext': 'mp3', 'artist': artist_str or Unknown('Artist'), 'album': album,
        'length': length, 'sng_id': sng_id, 'explicit': is_explicit
    }
    with suppress(KeyError):
        md5 = track_obj.get('FALLBACK', track_obj)['MD5_ORIGIN']
        file_url = generateCryptedStreamURL(sng_id, md5, track_obj['MEDIA_VERSION'], TrackFormats.MP3_128)
        bf_key = generateBlowfishKey(sng_id)
        metadata['file_url'] = file_url
        metadata['bf_key'] = bf_key
        expiry_time = time.time() + 1800  # 30 minute expiry
        metadata['expiry'] = expiry_time
    return metadata


def set_dz_url(metadata):
    src_url = metadata['src']
    metadata['url'] = f'http://{get_ipv4()}:{State.PORT}/dz?{urlencode({"url": src_url})}'
    # metadata['url'] = metadata['file_url']


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
    art_img: Image.Image = Image.open(img_data)
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
            try:
                fnt = ImageFont.truetype('arial.ttf', 80)
                shift = 0
            except OSError:
                # Linux
                fnt = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeMono.ttf', 80, encoding='unic')
                shift = 0
    d.rounded_rectangle((x0, y0, x1, y1), fill='#cc1a21', radius=7)
    d.text(((x0 + x1) / 2, (y0 + y1) / 2 + shift), text, fill='#fff', font=fnt, align='center', anchor='mm')
    data = io.BytesIO()
    art_img.save(data, format='png', quality=95)
    return b64encode(data.getvalue())


def get_youtube_comments(url, limit=-1):  # -> generator
    # TODO: use proxies = get_proxy()
    return yt_comment_downloader.get_comments_from_url(url, sort_by=SORT_BY_POPULAR, limit=limit)


def timestamp_to_time(text):
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
    description_timestamps = timestamp_to_time(video_info['description'])
    if len(description_timestamps) > 1:
        return description_timestamps
    # try parsing comments
    url = video_info['webpage_url']
    with suppress(ValueError, RuntimeError):
        for count, comment in enumerate(get_youtube_comments(url, limit=10)):
            times = timestamp_to_time(comment['text'])
            if len(times) > 2:
                return times
    return []

# GUI utilitiies

def repeat_img_tooltip(repeat_setting):
    if repeat_setting is None:
        return REPEAT_OFF_IMG, t('Repeat All')
    elif repeat_setting:
        return REPEAT_ONE_IMG, t('Repeat Off')
    return REPEAT_ALL_IMG, t('Repeat One')


def create_progress_bar_texts(position, length):
    """":return: time_elapsed_text, time_left_text"""
    position = floor(position)
    mins_elapsed, secs_elapsed = floor(position / 60), floor(position % 60)
    if secs_elapsed < 10:
        secs_elapsed = f'0{secs_elapsed}'
    elapsed_text = f'{mins_elapsed}:{secs_elapsed}'
    try:
        time_left = round(length) - position
        mins_left, secs_left = time_left // 60, time_left % 60
        if secs_left < 10:
            secs_left = f'0{secs_left}'
        time_left_text = f'{mins_left}:{secs_left}'
    except TypeError:
        time_left_text = '∞'
    return elapsed_text, time_left_text


def truncate_title(title):
    """ truncate title for mini mode """
    if len(title) > 29:
        return title[:26] + '...'
    return title


# TKDnD
def drop_target_register(widget, *dndtypes):
    widget.tk.call('tkdnd::drop_target', 'register', widget._w, dndtypes)


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
    if not new_text:
        return window.metadata[key]
    i = 0
    for v in window.metadata[key]:
        if i >= len(new_text) or v != new_text[i]:
            cut_text += v
        else:
            i += 1
    return cut_text


def start_on_login_win32(working_dir, create_key=True, is_debug=True):
    import winreg as wr
    classes_path = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run'
    access = wr.KEY_ALL_ACCESS | wr.KEY_WOW64_64KEY
    path_to_exe = working_dir / 'Music Caster.exe' if IS_FROZEN else working_dir / 'music_caster.bat'
    if not IS_FROZEN and not os.path.exists(path_to_exe):
        with open('music_caster.bat', 'w') as f:
            f.write(f'pythonw "{os.path.basename(sys.argv[0])}" -m')
    with wr.OpenKeyEx(wr.HKEY_CURRENT_USER, classes_path, 0, access) as key:
        if create_key and (IS_FROZEN or is_debug):
            wr.SetValueEx(key, 'Music Caster', 0, wr.REG_SZ, f'"{path_to_exe}" -m')
        if not create_key or (not IS_FROZEN and is_debug):
            with suppress(FileNotFoundError):
                wr.DeleteValue(key, 'Music Caster')


def rm_old_startup_shortcuts():
    if platform.system() == 'Windows':
        from knownpaths import FOLDERID, sh_get_known_folder_path
        startup_dir = sh_get_known_folder_path(FOLDERID.Startup)
        shortcut_paths = (f"{startup_dir}\\{item}.lnk" for item in ('Music Caster', 'Music Caster (Python)', 'Music Caster  [DEBUG]'))
        for shortcut_path in shortcut_paths:
            with suppress(FileNotFoundError):
                os.remove(shortcut_path)


def startfile(file):
    if platform.system() == 'Windows':
        try:
            return os.startfile(file)
        except OSError:
            return Popen(f'explorer "{fix_path(file)}"')
    elif platform.system() == 'Darwin':
        return Popen(['open', file])
    # Linux
    return Popen(['xdg-open', file])


def add_to_path(path):
    if platform.system() == 'Windows':
        os.environ['PATH'] += f'{path};'
    else:
        os.environ['PATH'] += f':{path}'


def cmd_exists(cmd):
    if platform.system() == 'Windows':
        return subprocess.call(f'where {cmd}', shell=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0
    return subprocess.call(f'type {cmd}', shell=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0


_deno_install_lock = Lock()


def install_deno():
    if not _deno_install_lock.acquire(blocking=False):
        return
    if subprocess.call(['deno', '-v'], stdout=subprocess.PIPE, stderr=subprocess.PIPE) != 0:
        print('Installing Deno...')
        if platform.system() == 'Windows':
            subprocess.call('irm https://deno.land/install.ps1 | iex', shell=True)
        else:
            subprocess.call('curl -fsSL https://deno.land/install.sh | sh -s -- -y', shell=True)


def install_phantomjs(install_directory):
    """Downloads PhantomJS zip, extracts to install_dir. Does not bin dir to path
    Raises multiple exceptions!

    Args:
        install_directory (Pathlike): path to extract phantomjs to
    """
    # download phantomJS
    tags = requests.get('https://api.github.com/repos/ariya/phantomjs/tags').json()
    latest_tag = tags[0]['name']

    if platform.system() == 'Windows':
        dir_name = f'phantomjs-{latest_tag}-windows'
        dl_link = f'https://bitbucket.org/ariya/phantomjs/downloads/{dir_name}.zip'
    elif platform.system() == 'Linux':
        dir_name = f'phantomjs-{latest_tag}-linux'
        dl_link = f'https://bitbucket.org/ariya/phantomjs/downloads/phantomjs-{latest_tag}-linux-x86_64.tar.bz2'
    elif platform.system() == 'Darwin':  # Mac OSX
        dir_name = f'phantomjs-{latest_tag}-windows'
        dl_link = f'https://bitbucket.org/ariya/phantomjs/downloads/phantomjs-{latest_tag}-macosx.zip'
    r = requests.get(dl_link, stream=True)
    temp_dir = tempfile.mkdtemp()
    if dl_link.endswith('zip'):
        with ZipFile(io.BytesIO(r.content)) as zf:
            zf.extractall(temp_dir)
    else:
        with tarfile.open(fileobj=r.raw, mode='r|bz2') as tf:
            tf.extractall(temp_dir)
    shutil.move(Path(temp_dir) / dir_name, install_directory)
