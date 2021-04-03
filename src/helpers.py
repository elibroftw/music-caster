from b64_images import *
from base64 import b64encode, b64decode
from bs4 import BeautifulSoup
from contextlib import suppress
import ctypes
import concurrent.futures
import datetime
from functools import wraps, lru_cache
import glob
import io
import json
import locale
from math import floor, ceil
import os
import platform
from random import getrandbits
import re
import socket
import time
from urllib.parse import urlparse, parse_qs
from uuid import getnode
import winreg as wr
# 3rd party imports
import mutagen
from mutagen import MutagenError
from mutagen.aac import AAC
# noinspection PyProtectedMember
from mutagen.id3 import ID3NoHeaderError
# noinspection PyProtectedMember
from mutagen.mp3 import HeaderNotFoundError
from mutagen.easyid3 import EasyID3
from mutagen.easymp4 import EasyMP4
import pyperclip
import pyqrcode
import PySimpleGUI as Sg
from PIL import Image, ImageFile
import requests
from wavinfo import WavInfoReader, WavInfoEOFError  # until mutagen supports .wav
from youtubesearchpython import VideosSearch

# CONSTANTS
FONT_NORMAL = 'Segoe UI', 11
FONT_BTN = 'Segoe UI', 10
FONT_SMALL = 'Segoe UI', 10
FONT_LINK = 'Segoe UI', 11, 'underline'
FONT_TITLE = 'Segoe UI', 14
FONT_MID = 'Segoe UI', 12
FONT_TAB = 'Meiryo UI', 10
LINK_COLOR = '#3ea6ff'
COVER_MINI = (125, 125)
COVER_NORMAL = (255, 255)
ImageFile.LOAD_TRUNCATED_IMAGES = True
SPOTIFY_API = 'https://api.spotify.com/v1'
# for stealing focus when bring window to front
keybd_event = ctypes.windll.user32.keybd_event
alt_key, extended_key, key_up = 0x12, 0x0001, 0x0002


class Shared:
    """
    variables in Shared are modifed by music_caster.py
    """
    lang = ''


def timing(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        _start = time.time()
        result = f(*args, **kwargs)
        print(f'@timing {f.__name__} ELAPSED TIME:', time.time() - _start)
        return result
    return wrapper


class InvalidAudioFile(Exception): pass


class PlayingStatus:
    NOT_PLAYING = 'NOT PLAYING'
    PLAYING = 'PLAYING'
    PAUSED = 'PAUSED'
    BUSY = {PLAYING, PAUSED}


class Unknown:
    __slots__ = 'property'

    def __init__(self, _property):
        self.property = _property

    def __repr__(self):
        return gt(f'Unknown {self.property}')

    def __eq__(self, other):
        return str(other) == str(self)

    def __ne__(self, other):
        return not self.__eq__(str(other))

    def split(self, *args, **kwargs):
        return str(self).split(*args, **kwargs)


def get_file_name(file_path): return os.path.splitext(os.path.basename(file_path))[0]


@lru_cache(maxsize=1)
def get_languages():
    return [''] + [get_file_name(lang) for lang in glob.iglob('languages/*.txt')]


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


def get_translation(string, lang=''):
    """
    Returns the translation of the string in the display language
    If lang pack does not exist, use original string
    :param string: English string
    :param lang: Optional code to translate to. Defaults to using display language
    :return: string translated to display language
    """
    lang = lang or get_display_lang()
    try:
        return get_lang_pack(lang)[get_lang_pack('en')[string]]
    except (IndexError, KeyError):
        return string


def gt(string):
    return get_translation(string, Shared.lang)


def get_length(file_path) -> int:
    """
    throws InvalidAudioFile if file is invalid
    :param file_path:
    :return: length in seconds
    """
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
    except (AttributeError, HeaderNotFoundError, MutagenError, WavInfoEOFError, StopIteration):
        raise InvalidAudioFile(f'{file_path} is an invalid audio file')


def natural_key(string):
    return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', string)]


def natural_key_file(file_name):
    file_name = get_file_name(file_name)
    return natural_key(file_name.lower())


def valid_color_code(code):
    match = re.search(r'^#(?:[0-9a-fA-F]{3}){1,2}$', code)
    return match


def get_metadata(file_path: str, sort_key_template='&title - &artist'):
    file_path = file_path.lower()
    unknown_title, unknown_artist, unknown_album = Unknown('Title'), Unknown('Artist'), Unknown('Album')
    title, artist, album = unknown_title, unknown_artist, unknown_album
    track_number, is_explicit = None, False
    with suppress(ID3NoHeaderError, HeaderNotFoundError, AttributeError, WavInfoEOFError, StopIteration):
        if file_path.endswith('.mp3'):
            audio = dict(EasyID3(file_path))
            _audio = mutagen.File(file_path)
            audio['rating'] = str(_audio.get('TXXX:RATING', _audio.get('TXXX:ITUNESADVISORY', '0')))
        elif file_path.endswith('.m4a') or file_path.endswith('.mp4'):
            audio = EasyMP4(file_path)
        elif file_path.endswith('.wav'):
            a = WavInfoReader(file_path).info.to_dict()
            audio = {'title': [a['title']], 'artist': [a['artist']], 'album': [a['product']]}
        elif file_path.endswith('.wma'):
            audio = {'title': [title], 'artist': [artist], 'album': [album]}
        else:
            audio = mutagen.File(file_path)
        title = audio.get('title', [title])[0]
        album = audio.get('album', [album])[0]
        is_explicit = audio.get('rating', '0') not in {'C', 'T', '0', 0}
        with suppress(KeyError, TypeError, MutagenError):
            track_number = audio.get('tracknumber')[0].split('/', 1)[0]
        with suppress(KeyError, TypeError):
            if len(audio['artist']) == 1:
                # in case the sep char is a slash
                audio['artist'] = audio['artist'][0].split('/')
            artist = ', '.join(audio['artist'])
    if title is None: title = unknown_title
    if artist is None: artist = unknown_artist
    if title == unknown_title or artist == unknown_artist:
        # if title or artist are unknown, use the basename of the URI (excluding extension)
        sort_key = get_file_name(file_path)
    else:
        sort_key = sort_key_template.replace('&title', title).replace('&artist', artist).replace('&album', album)
        sort_key = sort_key.replace('&trck', track_number or '')
    metadata = {'title': title, 'artist': artist, 'album': album, 'explicit': is_explicit, 'sort_key': sort_key.lower()}
    if track_number is not None: metadata['track_number'] = track_number
    return metadata


def fix_path(path, by_os=True):
    return path.replace('/', '\\') if by_os and platform.system() == 'Windows' else path.replace('\\', '/')


def get_first_artist(artists: str) -> str:
    return artists.split(', ', 1)[0]


def get_ipv4() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 80))
    ipv4_address = s.getsockname()[0]
    s.close()
    return ipv4_address


def get_mac(): return ':'.join(['{:02x}'.format((getnode() >> ele) & 0xff) for ele in range(0, 8 * 6, 8)][::-1])


def better_shuffle(seq, first=0, last=-1):
    """
    Shuffles based on indices
    :param seq:
    :param first:
    :param last:
    :return:
    """
    n = len(seq)
    _, __ = seq[first], seq[last]  # check for IndexError
    first = first % n
    last = last % n
    # use Fisher-Yates shuffle (Durstenfeld method)
    for i in range(first, last + 1):
        size = last - i + 1
        j = getrandbits(size.bit_length()) % size + i
        seq[i], seq[j] = seq[j], seq[i]
    return seq


def create_qr_code(port, ipv4=None):
    ipv4 = ipv4 or get_ipv4()
    qr_code = pyqrcode.create(f'http://{ipv4}:{port}')
    return qr_code.png_as_base64_str(scale=3, module_color=(255, 255, 255, 255), background=(18, 18, 18, 255))


def valid_audio_file(file_path):
    """
    check if file_path ends with a valid extension
    file_path does not have to exist
    :param file_path:
    :return:
    """
    file_path = file_path.lower()
    return (file_path.endswith('.mp3') or file_path.endswith('.flac') or file_path.endswith('.m4a')
            or file_path.endswith('.mp4') or file_path.endswith('.aac') or file_path.endswith('.mpeg')
            or file_path.endswith('.ogg') or file_path.endswith('.opus')
            or file_path.endswith('.wma') or file_path.endswith('.wav'))


# noinspection PyTypeChecker
def parse_youtube_id(url):
    query = urlparse(url)
    if query.hostname == 'youtu.be': return query.path[1:]
    if query.hostname in {'www.youtube.com', 'youtube.com'}:
        if query.path == '/watch': return parse_qs(query.query)['v'][0]
        if query.path[:7] == '/watch/': return query.path.split('/')[1]
        if query.path[:7] == '/embed/': return query.path.split('/')[2]
        if query.path[:3] == '/v/': return query.path.split('/')[2]
        if query.path[:9] == '/playlist': return parse_qs(query.query)['list'][0]
    return None  # invalid YouTube url


def is_os_64bit():
    return platform.machine().endswith('64')


def get_output_device(pa, look_for):
    for i in range(pa.get_device_count()):
        device_info = pa.get_device_info_by_index(i)
        host_api_info = pa.get_host_api_info_by_index(device_info['hostApi'])
        if (host_api_info['name'] == 'Windows WASAPI' and device_info['maxOutputChannels'] > 0
                and device_info['name'] == look_for):
            channels = min(device_info['maxOutputChannels'], 2)
            return int(device_info['defaultSampleRate']), channels, device_info['index']
    raise RuntimeError('No Output Device Found')


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

    # create file type
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{classes_path}{mc_file}', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, 'Audio File')
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{classes_path}{mc_file}\\DefaultIcon', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, path_to_exe)  # define icon location

    # create open handler
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{classes_path}{mc_file}\\shell\\open', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, f'Play')
        wr.SetValueEx(key, 'MultiSelectModel', 0, wr.REG_SZ, 'Player')

    command_path = f'{classes_path}{mc_file}\\shell\\open\\command'
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, command_path, 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" "%1"')

    # create queue handler
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{classes_path}{mc_file}\\shell\\queue', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, f'Queue in Music Caster')
        wr.SetValueEx(key, 'MultiSelectModel', 0, wr.REG_SZ, 'Player')
        # wr.SetValueEx(key, 'Icon', 0, wr.REG_SZ, path_to_exe)

    command_path = f'{classes_path}{mc_file}\\shell\\queue\\command'
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, command_path, 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" -q "%1"')

    # set file handlers
    for ext in {'mp3', 'flac', 'm4a', 'mp4', 'aac', 'ogg', 'opus', 'wma', 'wav', 'mpeg'}:
        key_path = f'{classes_path}.{ext}'
        try:  # check if key exists
            with wr.OpenKeyEx(wr.HKEY_CURRENT_USER, key_path, 0, read_access) as _: pass
        except (WindowsError, FileNotFoundError):
            # create key for extension if it does not exist with MC as the default program
            with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, key_path, 0, write_access) as key:
                # set as default program unless .mp4 because that's a video format
                if ext != 'mp4': wr.SetValueEx(key, None, 0, wr.REG_SZ, 'MusicCaster_file')
        # add to Open With (prompts user to set default program when they try playing a file)
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{key_path}\\OpenWithProgids', 0, write_access) as key:
            # noinspection PyTypeChecker
            wr.SetValueEx(key, mc_file, 0, wr.REG_NONE, b'')  # type needs to be bytes

    play_folder_key_path = f'{classes_path}\\Directory\\shell\\MusicCasterPlayFolder'
    queue_folder_key_path = f'{classes_path}\\Directory\\shell\\MusicCasterQueueFolder'
    if add_folder_context:
        # set "open folder in Music Caster" command
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, play_folder_key_path, 0, write_access) as key:
            wr.SetValueEx(key, None, 0, wr.REG_SZ, 'Play with Music Caster')
            wr.SetValueEx(key, 'Icon', 0, wr.REG_SZ, path_to_exe)
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{play_folder_key_path}\\command', 0, write_access) as key:
            wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" "%1"')
        # set "queue folder in Music Caster" command

        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, queue_folder_key_path, 0, write_access) as key:
            wr.SetValueEx(key, None, 0, wr.REG_SZ, 'Queue in Music Caster')
            wr.SetValueEx(key, 'Icon', 0, wr.REG_SZ, path_to_exe)
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{queue_folder_key_path}\\command', 0, write_access) as key:
            wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" -q "%1"')
    else:
        # remove commands for folders
        delete_sub_key(wr.HKEY_CURRENT_USER, play_folder_key_path)
        delete_sub_key(wr.HKEY_CURRENT_USER, queue_folder_key_path)


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
    img.save(data, format='png', quality=95)
    return b64encode(data.getvalue())


# GUI LAYOUTS
def repeat_img_tooltip(repeat_setting):
    if repeat_setting is None: return REPEAT_OFF_IMG, gt('Repeat All')
    elif repeat_setting: return REPEAT_ONE_IMG, gt('Repeat Off')
    else: return REPEAT_ALL_IMG, gt('Repeat One')


def get_music_controls(settings, playing_status):
    accent_color, bg = settings['theme']['accent'], settings['theme']['background']
    img_button = {'border_width': 0, 'button_color': (bg, bg)}
    is_muted = settings['muted']
    volume = 0 if is_muted else settings['volume']
    v_slider_img = VOLUME_MUTED_IMG if is_muted else VOLUME_IMG
    pause_resume_img = PAUSE_BUTTON_IMG if playing_status == 'PLAYING' else PLAY_BUTTON_IMG
    repeat_img, repeat_tooltip = repeat_img_tooltip(settings['repeat'])
    prev_button = {'pad': ((10, 5), None) if settings['mini_mode'] else None, 'tooltip': gt('previous track')}
    repeat_button = {**img_button, 'tooltip': repeat_tooltip, 'metadata': settings['repeat']}
    shuffle_button = {**img_button, 'image_data': SHUFFLE_ON if settings['shuffle'] else SHUFFLE_OFF}
    mute_tooltip = gt('unmute') if is_muted else gt('mute')
    return [Sg.Button(key='prev', image_data=PREVIOUS_BUTTON_IMG, **img_button, **prev_button),
            Sg.Button(key='pause/resume', image_data=pause_resume_img, **img_button, metadata=playing_status),
            Sg.Button(key='next', image_data=NEXT_BUTTON_IMG, **img_button, tooltip=gt('next track')),
            Sg.Button(key='repeat', image_data=repeat_img, **repeat_button),
            Sg.Button(key='shuffle', **shuffle_button, tooltip=gt('shuffle'), metadata=settings['shuffle']),
            Sg.Button(key='mute', image_data=v_slider_img, **img_button, tooltip=mute_tooltip),
            Sg.Slider((0, 100), default_value=volume, orientation='h', key='volume_slider',
                      disable_number_display=True, enable_events=True, background_color=accent_color,
                      text_color='#000000', size=(10, 10), tooltip=gt('scroll mousewheel'), resolution=1)]


def create_progress_bar_text(position, length) -> (str, str):  #
    """":return: time_elapsed_text, time_left_text"""
    position = floor(position)
    time_left = round(length) - position
    mins_elapsed, mins_left = floor(position / 60), time_left // 60
    secs_left = time_left % 60
    secs_elapsed = floor(position % 60)
    if secs_left < 10: secs_left = f'0{secs_left}'
    if secs_elapsed < 10: secs_elapsed = f'0{secs_elapsed}'
    return f'{mins_elapsed}:{secs_elapsed}', f'{mins_left}:{secs_left}'


def get_progress_layout(settings, track_position, track_length, playing_status):
    time_elapsed, time_left = create_progress_bar_text(track_position, track_length)
    text_size = (5, 1)
    bot_pad = (settings['vertical_gui'] and not settings['show_album_art']) * 30
    accent_color, bg = settings['theme']['accent'], settings['theme']['background']
    mini_mode = settings['mini_mode']
    time_elapsed_pad = ((2, 0), (0, 0)) if mini_mode else ((0, 5), (10, bot_pad))
    time_left_pad = ((0, 0), (0, 0)) if mini_mode else ((5, 0), (10, bot_pad))
    progress_layout = [Sg.Text(time_elapsed, key='time_elapsed', pad=time_elapsed_pad, justification='center',
                               size=text_size, font=FONT_NORMAL),
                       Sg.Slider(range=(0, track_length), default_value=track_position,
                                 orientation='h', size=(20 if mini_mode else 30, 10), key='progress_bar',
                                 enable_events=True, relief=Sg.RELIEF_FLAT, background_color=accent_color,
                                 disable_number_display=True, disabled=playing_status == 'NOT PLAYING',
                                 tooltip=gt('scroll mousewheel'),
                                 pad=((2, 10), (0, 0)) if mini_mode else ((8, 8), (10, bot_pad))),
                       Sg.Text(time_left, key='time_left', pad=time_left_pad, justification='left',
                               size=text_size, font=FONT_NORMAL)]
    if mini_mode:
        progress_layout.append(Sg.Button(key='mini_mode', image_data=RESTORE_WINDOW, size=(1, 1), enable_events=True,
                                         border_width=0, button_color=(bg, bg), tooltip=gt('restore window'),
                                         pad=(0, 0)))
    return progress_layout


def truncate_title(title):
    """ truncate title for mini mode """
    if len(title) > 34:
        return title[:31] + '...'
    return title


def create_mini_mode(playing_status, settings, title, artist, album_art_data, track_length, track_position):
    # album_art_data is 125 x 125
    album_art = Sg.Column([[Sg.Image(data=album_art_data, key='album_art', pad=(0, 0))]],
                          element_justification='left', pad=(0, 0))
    music_controls = get_music_controls(settings, playing_status)
    progress_bar_layout = get_progress_layout(settings, track_position, track_length, playing_status)
    title = truncate_title(title)
    right_side = Sg.Column([
        [Sg.Text(title, font=FONT_TITLE, key='title', pad=((10, 0), (0, 0)), size=(26, 1), justification='left')],
        [Sg.Text(artist, font=FONT_MID, key='artist', pad=((10, 0), (0, 0)), size=(26, 2), justification='left')],
        music_controls, progress_bar_layout], element_justification='left', pad=(0, 0))
    return [[album_art, right_side] if settings['show_album_art'] else [right_side]]


def create_main(tracks, listbox_selected, playing_status, settings, version, timer, sorted_tracks,
                title=gt('Nothing Playing'), artist='', album='', qr_code=None, album_art_data: str = '',
                track_length=0, track_position=0):
    if settings['mini_mode']:
        return create_mini_mode(playing_status, settings, title, artist, album_art_data, track_length, track_position)
    accent_color, fg, bg = settings['theme']['accent'], settings['theme']['text'], settings['theme']['background']
    alternate_bg = settings['theme']['alternate_background']
    vertical_gui = settings['vertical_gui']
    img_button = {'border_width': 0, 'button_color': (bg, bg)}
    music_controls = get_music_controls(settings, playing_status)
    progress_bar_layout = get_progress_layout(settings, track_position, track_length, playing_status)
    if not settings['show_album_art']: album_art_data = ''
    info_top_pad = 10 + 60 * (not album_art_data) - 30 * (vertical_gui and not album_art_data)
    # 10, 110, or 0
    info_bot_pad = 10 + 40 * (not album_art_data) - 20 * (not album_art_data and vertical_gui)
    # 10 or 30
    left_pad = settings['vertical_gui'] * 95 + 5
    main_part = Sg.Column([
        [Sg.Image(data=album_art_data, pad=(0, 0), size=COVER_NORMAL, key='album_art')] if album_art_data else [],
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
    biggest_word = max((len(x) for x in file_options + folder_opts))
    combo_w = ceil(biggest_word * 0.95)
    btn_defaults = {'font': FONT_BTN, 'border_width': 0, 'highlight_colors': ('#fff', fg),
                    'enable_events': True, 'size': (combo_w, 1), 'image_subsample': 4, 'use_ttk_buttons': True}
    queue_controls = [
        Sg.Column([[Sg.Combo(file_options, default_value=file_options[0], key='file_option', size=(combo_w, None),
                             font=FONT_NORMAL, enable_events=True, pad=(5, (5, 0)), readonly=True)],
                   [Sg.Combo(folder_opts, default_value=folder_opts[0], key='folder_option', size=(combo_w, None),
                             font=FONT_NORMAL, enable_events=True, pad=(5, (10, 0)), readonly=True)]]),
        Sg.Column([[Sg.Button(file_options[0], key='file_action', **btn_defaults, pad=(0, (5, 4)))],
                   [Sg.Button(folder_opts[0], k='folder_action', **btn_defaults, pad=(0, 4))]]),
    ]
    listbox_controls = [
        [Sg.Button(key='mini_mode', image_data=RESTORE_WINDOW, **img_button, tooltip=gt('Launch mini mode'))],
        [Sg.Button(key='queue_all', image_data=QUEUE_ICON, **img_button, tooltip=gt('queue all'))],
        [Sg.Button(key='clear_queue', image_data=CLEAR_QUEUE, **img_button, tooltip=gt('Clear the queue'))],
        [Sg.Button(key='save_queue', image_data=SAVE_IMG, **img_button, tooltip=gt('Save queue to playlist'))],
        [Sg.Button(key='locate_uri', image_data=LOCATE_FILE, **img_button, tooltip=gt('Locate track'))],
        [Sg.Button('▲', key='move_up', button_color=('#fff', bg), border_width=0,
                   tooltip=gt('move up'), size=(2, 1))],
        [Sg.Button('❌', key='remove_track', button_color=('#fff', bg), border_width=0,
                   tooltip=gt('remove'), size=(2, 1))],
        [Sg.Button('▼', key='move_down', button_color=('#fff', bg), border_width=0,
                   tooltip=gt('move down'), size=(2, 1))],
        [Sg.Button(key='move_to_next_up', image_data=MOVE_TO_NEXT_QUEUE, **img_button,
                   tooltip=gt('Move to next up'))]
    ]
    listbox_height = 18 - 5 * settings['vertical_gui']
    queue_tab_layout = [queue_controls, [
        # TODO: add right click menus for list boxes
        Sg.Listbox(tracks, default_values=listbox_selected, size=(64, listbox_height),
                   select_mode=Sg.SELECT_MODE_SINGLE,
                   text_color=fg, key='queue', font=FONT_NORMAL,
                   bind_return_key=True),
        Sg.Column(listbox_controls, pad=(0, 0))]]
    queue_tab = Sg.Tab(gt('Queue'), queue_tab_layout, key='tab_queue')
    url_tab = Sg.Tab(gt('URL'), create_url_tab(), key='tab_url')
    playlists_tab = Sg.Tab(gt('Playlists'), create_playlists_tab(settings), key='tab_playlists')
    timer_tab = Sg.Tab(gt('Timer'), create_timer(settings, timer), key='tab_timer')
    settings_tab = Sg.Tab(gt('Settings'), create_settings(version, settings, qr_code), key='tab_settings')
    # library tab will be good to use once I'm using Python 3.10 which will have tk 8.10
    if settings['EXPERIMENTAL']:
        lib_data = [[track['title'], get_first_artist(track['artist']), track['album']] for _, track in sorted_tracks]
        if not lib_data: lib_data = [['', '', '']]
        lib_headings = ['title', 'artist', 'album']
        library_layout = [[Sg.Table(values=lib_data, headings=lib_headings, max_col_width=25,
                                    # background_color='light blue',
                                    auto_size_columns=False, display_row_numbers=False,
                                    def_col_width=20, bind_return_key=True,
                                    select_mode=Sg.TABLE_SELECT_MODE_BROWSE,
                                    justification='right', num_rows=10, row_height=30,
                                    right_click_menu=['', ['Play::library', 'Play Next::library', 'Queue::library']],
                                    header_text_color=fg, header_background_color=bg,
                                    alternating_row_color=alternate_bg, key='library')]]
        library_tab = Sg.Tab(gt('Library'), library_layout, key='tab_library')
        tab_group = [[queue_tab, library_tab, url_tab, playlists_tab, timer_tab, settings_tab]]
    else: tab_group = [[queue_tab, url_tab, playlists_tab, timer_tab, settings_tab]]
    tabs_part = Sg.TabGroup(tab_group, font=FONT_TAB,
                            title_color=fg, border_width=0, key='tab_group',
                            selected_background_color=accent_color, enable_events=True,
                            tab_background_color=bg, selected_title_color=bg, background_color=bg)
    if settings['vertical_gui']: return [[main_part], [tabs_part]]
    return [[main_part, tabs_part]] if settings['flip_main_window'] else [[tabs_part, main_part]]


def create_url_tab():
    default_text: str = pyperclip.paste()
    if not default_text.startswith('http'): default_text = ''
    layout = [[Sg.Text(gt('Enter URL'), font=FONT_NORMAL)],
              [Sg.Radio(gt('Play Immediately'), 'url_option', key='url_play', default=True),
               Sg.Radio(gt('Queue'), 'url_option', key='url_queue'),
               Sg.Radio(gt('Play Next'), 'url_option', key='url_play_next')],
              [Sg.Input(key='url_input', font=FONT_NORMAL, default_text=default_text, border_width=1),
               Sg.Button(gt('Submit'), key='url_submit', font=FONT_BTN, border_width=0,
                         bind_return_key=True, use_ttk_buttons=True)]]
    return [[Sg.Column(layout, pad=(5, 20))]]


def create_playlists_tab(settings):
    fg, bg = settings['theme']['text'], settings['theme']['background']
    playlists = settings['playlists']
    playlists_names = list(playlists.keys())
    default_pl_name = playlists_names[0] if playlists_names else None
    btn_defaults = {'enable_events': True, 'font': FONT_BTN, 'use_ttk_buttons': True}
    img_button = {'border_width': 0, 'button_color': (bg, bg)}
    playlist_selector = [
        [Sg.Button('➕', key='new_pl', tooltip=gt('new playlist'), button_color=('#fff', bg)),
         Sg.Button(image_data=EXPORT_PL, key='export_pl', tooltip=gt('export playlist'), **img_button),
         Sg.Button(image_data=DELETE_ICON, key='del_pl', tooltip=gt('delete playlist'), **img_button),
         Sg.Button(image_data=PLAY_ICON, key='play_pl', tooltip=gt('play playlist'),
                   pad=((12, 5), 5), disabled=default_pl_name is None, **img_button),
         Sg.Button(image_data=QUEUE_ICON, key='queue_pl', tooltip=gt('queue playlist'),
                   disabled=default_pl_name is None, **img_button),
         Sg.Combo(values=playlists_names, size=(37, 5), key='playlist_combo', font=FONT_NORMAL,
                  enable_events=True, default_value=default_pl_name, readonly=True)]]
    playlist_name = playlists_names[0] if playlists_names else ''
    uris = playlists.get(playlist_name, [])
    tracks = [f'{i + 1}. {uri if uri.startswith("http") else get_file_name(uri)}' for i, uri in enumerate(uris)]
    url_input = [Sg.Input('', key='pl_url_input', size=(12, 1), font=FONT_NORMAL, enable_events=True, border_width=1)]
    add_url = [Sg.Button(gt('Add URL'), key='pl_add_url', size=(13, 1), disabled=True, **btn_defaults)]
    add_tracks = [Sg.Button(gt('Add tracks'), key='pl_add_tracks', size=(13, 1), **btn_defaults)]
    lb_height = 14 - 3 * settings['vertical_gui']
    layout = [[Sg.Column(playlist_selector, pad=(5, 20))],
              [Sg.Text(gt('Playlist name'), font=FONT_NORMAL, size=(13, 1), justification='center', pad=(4, (5, 10))),
               Sg.Input(playlist_name, key='playlist_name', size=(48, 1), font=FONT_NORMAL, enable_events=True,
                        pad=((6, 5), (5, 10)), border_width=1),
               Sg.Button(key='pl_save', image_data=SAVE_IMG, tooltip='Ctrl + S',
                         border_width=0, button_color=(bg, bg), disabled=playlist_name == '')],
              [Sg.Frame('', [url_input, add_url, add_tracks], background_color=bg, border_width=0),
               Sg.Listbox(tracks, size=(45, lb_height), select_mode=Sg.SELECT_MODE_MULTIPLE, text_color=fg,
                          key='pl_tracks', background_color=bg, font=FONT_NORMAL, enable_events=True),
               Sg.Frame('', [[Sg.Button('▲', key='pl_move_up', button_color=('#fff', bg), border_width=0,
                                        tooltip=gt('move up'), size=(2, 1))],
                             [Sg.Button('❌', key='pl_rm_items', button_color=('#fff', bg), border_width=0,
                                        tooltip=gt('Ctrl + R'), size=(2, 1))],
                             [Sg.Button('▼', key='pl_move_down', button_color=('#fff', bg), border_width=0,
                                        tooltip=gt('move down'), size=(2, 1))]],
                        background_color=bg, border_width=0)]]
    return layout


def create_checkbox(name, key, settings, on_right=False):
    bg = settings['theme']['background']
    size = (23, 5) if on_right else (23, 5)
    checkbox = {'background_color': bg, 'font': FONT_NORMAL, 'enable_events': True, 'pad': ((0, 5), (5, 5))}
    return Sg.Checkbox(name, default=settings[key], key=key, tooltip=name, size=size, **checkbox)


def create_settings(version, settings, qr_code):
    accent_color, fg, bg = settings['theme']['accent'], settings['theme']['text'], settings['theme']['background']
    general_tab = Sg.Tab(gt('General'), [
        [create_checkbox(gt('Auto update'), 'auto_update', settings),
         create_checkbox(gt('Discord presence'), 'discord_rpc', settings, True)],
        [create_checkbox(gt('Notifications'), 'notifications', settings),
         create_checkbox(gt('Run on startup'), 'run_on_startup', settings, True)],
        [create_checkbox(gt('Folder context menu'), 'folder_context_menu', settings),
         create_checkbox(gt('Scan folders'), 'scan_folders', settings, True)],
        [create_checkbox(gt('Populate queue on startup'), 'populate_queue_startup', settings),
         create_checkbox(gt('Persistent queue'), 'save_queue_sessions', settings, True)],
        [create_checkbox(gt('Reversed play next'), 'reversed_play_next', settings),
         Sg.Text('🌐'),
         Sg.Combo(values=get_languages(), size=(3, 1), default_value=settings['lang'],
                  key='lang', readonly=True, enable_events=True)]
    ], key='settings_tab_general', background_color=bg)
    ui_tab = Sg.Tab(gt('UI'), [
        [create_checkbox(gt('Save window positions'), 'save_window_positions', settings),
         create_checkbox(gt('Show track number'), 'show_track_number', settings, True)],
        [create_checkbox(gt('Left-side music controls'), 'flip_main_window', settings),
         create_checkbox(gt('Vertical GUI'), 'vertical_gui', settings, True)],
        [create_checkbox(gt('Show album art'), 'show_album_art', settings),
         create_checkbox(gt('Mini mode on top'), 'mini_on_top', settings, True)],
        [create_checkbox(gt('Use cover.* for album art'), 'folder_cover_override', settings),
         create_checkbox(gt('Show index in queue'), 'show_queue_index', settings, True)]
    ], key='settings_tab_ui', background_color=bg)
    settings_tab_group = Sg.TabGroup([[general_tab, ui_tab]], title_color=fg, border_width=0, key='tab_group_settings',
                                     selected_background_color=accent_color, enable_events=True, font=FONT_TAB,
                                     tab_background_color=bg, selected_title_color=bg, background_color=bg)
    checkbox_col = Sg.Column([[settings_tab_group]], pad=((0, 0), (5, 0)))
    qr_code_params = {'tooltip': gt('Web GUI QR Code (click or scan)'), 'border_width': 0, 'button_color': (bg, bg)}
    right_settings_col = Sg.Column([
        [Sg.Button(key='web_gui', image_data=qr_code, **qr_code_params)],
        [Sg.Button('settings.json', key='settings_file', font=FONT_BTN, pad=((15, 0), (5, 5)), use_ttk_buttons=True)],
        [Sg.Button('Changelog', key='changelog_file', font=FONT_BTN, pad=((15, 0), (5, 5)), use_ttk_buttons=True)]
    ], pad=(0, 0))
    email_params = {'text_color': LINK_COLOR, 'font': FONT_LINK, 'tooltip': gt('Send me an email')}
    folder_btn = {'font': FONT_NORMAL, 'size': (3, 1), 'enable_events': True, 'button_color': ('#fff', bg)}
    layout = [
        [Sg.Text(f'Music Caster v{version} by Elijah Lopez', font=FONT_NORMAL),
         Sg.Text('elijahllopezz@gmail.com', click_submits=True, key='email', **email_params)],
        [checkbox_col, right_settings_col] if qr_code else [checkbox_col],
        [Sg.Listbox(settings['music_folders'], size=(62, 5), select_mode=Sg.SELECT_MODE_SINGLE, text_color=fg,
                    key='music_folders', background_color=bg, font=FONT_NORMAL, bind_return_key=True,
                    no_scrollbar=True),
         Sg.Column([
             [Sg.Button('❌', key='remove_music_folder', tooltip=gt('remove selected folder'), **folder_btn)],
             [Sg.FolderBrowse('➕', key='add_music_folder', tooltip=gt('add folder'), **folder_btn)]])]]
    return layout


def create_timer(settings, timer):
    shut_down = settings['timer_shut_down']
    hibernate = settings['timer_hibernate']
    sleep = settings['timer_sleep']
    fg, bg = settings['theme']['text'], settings['theme']['background']
    do_nothing = not (shut_down or hibernate or sleep)
    # if timer is valid
    if time.time() < timer:
        timer_date = datetime.datetime.fromtimestamp(timer)
        timer_date = timer_date.strftime('%#I:%M %p')
        timer_text = gt('Timer set for $TIME').replace('$TIME', timer_date)
    else:
        timer_text = gt('No Timer Set')
    # wait for last track to finish setting
    cancel_button = Sg.Button(gt('Cancel Timer'), key='cancel_timer', visible=timer != 0)
    defaults = {'text_color': fg, 'background_color': bg, 'font': FONT_NORMAL, 'enable_events': True}
    layout = [
        [Sg.Radio(gt('Shut down when timer runs out'), 'TIMER', default=shut_down, key='shut_down', **defaults)],
        [Sg.Radio(gt('Sleep when timer runs out'), 'TIMER', default=sleep, key='sleep', **defaults)],
        [Sg.Radio(gt('Hibernate when timer runs out'), 'TIMER', default=hibernate, key='hibernate', **defaults)],
        [Sg.Radio(gt('Only stop playback'), 'TIMER', default=do_nothing, key='timer_only_stop', **defaults)],
        [Sg.Text(gt('Enter minutes or HH:MM'), font=FONT_NORMAL),
         Sg.Input(key='timer_minutes', font=FONT_NORMAL, size=(11, 1), border_width=1),
         Sg.Button(gt('Submit'), font=FONT_BTN, key='timer_submit', border_width=0, use_ttk_buttons=True)],
        [Sg.Text(gt('Invalid Input (enter minutes or HH:MM)'), font=FONT_NORMAL, visible=False, key='timer_error')],
        [Sg.Text(timer_text, font=FONT_NORMAL, key='timer_text', size=(18, 1), metadata=timer != 0), cancel_button]
    ]
    return [[Sg.Column(layout, pad=(0, (50, 0)), justification='center')]]


def steal_focus(window: Sg.Window):
    # makes window the top-most application
    keybd_event(alt_key, 0, extended_key | 0, 0)
    ctypes.windll.user32.SetForegroundWindow(window.TKroot.winfo_id())
    keybd_event(alt_key, 0, extended_key | key_up, 0)


def youtube_search(query):
    results: list = VideosSearch(query, limit=1).result()['result']
    return results[0]['link']


def get_spotify_headers(url):
    url = url[:url.find('?')]  # get rid of query parameters
    r = requests.get(url, headers={'user-agent': 'Firefox/78.0'})
    soup = BeautifulSoup(r.text, 'html.parser')
    s = soup.find('script', {'id': 'config'})
    spotify_config = json.loads(s.string)
    return {'Authorization': 'Bearer ' + spotify_config['accessToken']}


def spotify_track_to_youtube(url):
    try:
        track_id = urlparse(url).path.split('/track/', 1)[1]
    except IndexError:
        # e.g. */album/*?highlight=spotify:track:587w9pOR9UNvFJOwkW7NgD
        track_id = re.search(r'track:.*', url).group()[6:]
    r = requests.get(f'{SPOTIFY_API}/tracks/{track_id}', headers=get_spotify_headers(url)).json()
    track_name = r['name']
    track_artist = r['artists'][0]['name']
    search_query = f'{track_artist} - {track_name}'
    result = youtube_search(search_query)
    return result


def spotify_album_to_youtube(url):
    album_id = urlparse(url).path.split('/album/', 1)[1]
    r = requests.get(f'{SPOTIFY_API}/albums/{album_id}/tracks', headers=get_spotify_headers(url)).json()
    tracks = ['' for _ in r['items']]
    with concurrent.futures.ThreadPoolExecutor(max_workers=35) as executor:
        futures = {}
        for i, track in enumerate(r['items']):
            track_title = track['name']
            track_artist = track['artists'][0]['name']
            query = f'{track_artist} - {track_title}'
            futures[executor.submit(youtube_search, query)] = i
        for future in concurrent.futures.as_completed(futures):
            tracks[futures[future]] = future.result()
    return tracks


def spotify_playlist_to_youtube(url):
    playlist_id = urlparse(url).path.split('/playlist/', 1)[1]
    r = requests.get(f'{SPOTIFY_API}/playlists/{playlist_id}/tracks', headers=get_spotify_headers(url)).json()
    tracks = ['' for _ in r['items']]
    with concurrent.futures.ThreadPoolExecutor(max_workers=35) as executor:
        futures = {}
        for i, track in enumerate(r['items']):
            track = track['track']
            track_title = track['name']
            track_artist = track['artists'][0]['name']
            query = f'{track_artist} - {track_title}'
            futures[executor.submit(youtube_search, query)] = i
        for future in concurrent.futures.as_completed(futures):
            tracks[futures[future]] = future.result()
    return tracks


@lru_cache
def spotify_to_youtube(url):
    if 'track' in url:
        return [spotify_track_to_youtube(url)]
    elif 'album' in url:
        return spotify_album_to_youtube(url)
    elif 'playlist' in url:
        return spotify_playlist_to_youtube(url)
    return []


def export_playlist(playlist_name, uris):
    # location should be downloads folder
    from pathlib import Path
    playlist_name = re.sub('[^A-Za-z0-9]+', '', playlist_name)
    playlist_path = f'{Path.home()}/Downloads/{playlist_name}.m3u'
    with open(playlist_path, 'w') as f:
        f.write('#EXTM3U\n')
        for uri in uris: f.write(uri + '\n')
    return playlist_path


def parse_m3u(playlist_file):
    with open(playlist_file) as f:
        for line in iter(lambda: f.readline(), ''):
            if not line.startswith('#'):
                yield line.lstrip('file:').lstrip('/').rstrip()
