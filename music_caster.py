VERSION = '4.56.2'
UPDATE_MESSAGE = """
[UI] Added Keyboard Shortcuts
[UI] Added Queue URL
[UI] Use Ctrl + Shift + Alt + M
"""
if __name__ != '__main__': raise RuntimeError(VERSION)  # hack
import time
start = time.time()
# helper file
from helpers import *
import base64
from contextlib import suppress
from datetime import datetime, timedelta
# noinspection PyUnresolvedReferences
import encodings.idna  # DO NOT REMOVE
from functools import cmp_to_key
import io
from glob import glob
import json
import logging
from math import floor
from pathlib import Path
import pprint
from shutil import copyfile, copyfileobj
import argparse
from random import shuffle
import sys
import shutil
import traceback
import urllib.parse
from urllib.parse import urlsplit
import webbrowser  # takes 0.05 seconds
import zipfile
# 3rd party imports
from flask import Flask, jsonify, render_template, request, redirect, send_file
from mutagen.aac import AAC
# from PIL import Image
import PySimpleGUIWx as SgWx
import wx
import pychromecast.controllers.media
from pychromecast.error import UnsupportedNamespace, NotConnected
from pychromecast.config import APP_MEDIA_RECEIVER
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = 'hide'
from pygame import mixer as local_music_player
from pygame import error as pygame_error
import pynput.keyboard
import pypresence
import pythoncom
import requests
from wavinfo import WavInfoReader  # until mutagen supports .wav
import win32com.client
import winshell
from youtube_dl import YoutubeDL
# CONSTANTS
parser = argparse.ArgumentParser(description='Music Caster')
parser.add_argument('path', nargs='?', default='', help='path of file/dir you want to play')
parser.add_argument('--debug', default=False, action='store_true', help='allows > 1 instance + no info sent')
args = parser.parse_args()
DEBUG = args.debug
EMAIL = 'elijahllopezz@gmail.com'
EMAIL_URL = f'mailto:{EMAIL}?subject=Regarding%20Music%20Caster%20v{VERSION}'
MUSIC_CASTER_DISCORD_ID = '696092874902863932'
UNINSTALLER = 'unins000.exe'
PORT, WAIT_TIMEOUT, IS_FROZEN = 2001, 10, getattr(sys, 'frozen', False)
MC_SECRET = str(uuid.uuid4())
PRESSED_KEYS = set()
show_pygame_error = variable_exception_sent = update_devices = settings_file_in_use = False
update_available = False
settings_last_modified, last_press = 0, time.time()
active_windows = {'main': False, 'playlist_selector': False,
                  'playlist_editor': False, 'play_url': False}
main_window = timer_window = pl_editor_window = pl_selector_window = play_url_window = Sg.Window('')
main_last_event = pl_editor_last_event = None
# noinspection PyTypeChecker
cast: pychromecast.Chromecast = None
stop_discovery = None  # function
playlists, all_songs, music_metadata = {}, {}, {}
# playlist_name: [], formatted_name: file path, file: {artist: str, title: str}
tray_playlists, tray_folders = ['Create/Edit a Playlist'], []
all_folders, pl_name, pl_files = ['PF: Select Folder(s)'], '', []
chromecasts, device_names = [], ['✓ Local device']
music_directories, window_locations = [], {}
music_queue, done_queue, next_queue = [], [], []
mouse_hover = ''
daemon_command = None
playing_url = False
progress_bar_last_update = song_position = timer = song_end = song_length = song_start = 0  # seconds but using time()
playing_status = 'NOT PLAYING'
starting_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
thumbs_dir = f'{starting_dir}/images'
# if music caster was launched in some other folder, play all or queue all that folder?
SHORTCUT_PATH = ''
os.chdir(starting_dir)
home_music_dir = f'{Path.home()}/Music'
settings_file = f'{starting_dir}/settings.json'

settings = {  # default settings
    'previous_device': None, 'window_locations': {}, 'update_message': '', 'EXPERIMENTAL': False,
    'auto_update': False, 'run_on_startup': True, 'notifications': True, 'shuffle_playlists': True, 'repeat': False,
    'discord_rpc': False, 'save_window_positions': True, 'populate_queue_startup': False, 'save_queue_sessions': False,
    'default_file_handler': True, 'volume': 100, 'muted': False, 'volume_delta': 5, 'scrubbing_delta': 5,
    'accent_color': '#00bfff', 'text_color': '#d7d7d7', 'button_text_color': '#000000', 'background_color': '#121212',
    'flip_main_window': False, 'timer_shut_off_computer': False, 'timer_hibernate_computer': False,
    'timer_sleep_computer': False, 'music_directories': [home_music_dir], 'playlists': {},
    'queues': {'done': [], 'music': [], 'next': []}}
# noinspection PyTypeChecker
compiling_songs_thread: Thread = None
# noinspection PyTypeChecker
save_queue_thread: Thread = None
# noinspection PyTypeChecker
ydl: YoutubeDL = None
app = Flask(__name__)
logging.getLogger('werkzeug').disabled = True
os.environ['WERKZEUG_RUN_MAIN'] = 'true'


def save_settings():
    global settings, settings_file, settings_file_in_use
    if not settings_file_in_use:
        settings_file_in_use = True
        with open(settings_file, 'w') as outfile:
            json.dump(settings, outfile, indent=4)
        settings_file_in_use = False


def do_nothing(): pass


def refresh_folders():
    tray_folders.clear()
    tray_folders.append('PF: Select Folder(s)')
    for music_dir in music_directories:
        music_dir = music_dir.replace('\\', '/').split('/')
        music_dir = f'PF: ../{"/".join(music_dir[-2:])}' if len(music_dir) > 2 else 'PF: ' + '/'.join(music_dir)
        tray_folders.append(music_dir)


def refresh_tray():
    refresh_folders()
    if playing_status == 'PLAYING': tray.Update(menu=menu_def_2)
    elif playing_status == 'PAUSED': tray.Update(menu=menu_def_3)
    else: tray.Update(menu=menu_def_1)


def change_settings(settings_key, new_value):
    global settings, active_windows, tray
    if settings[settings_key] == new_value: return new_value
    settings[settings_key] = new_value
    save_settings()
    if settings_key == 'repeat':
        repeat_menu[0] = 'Repeat All ✓' if new_value is False else 'Repeat All'
        repeat_menu[1] = 'Repeat One ✓' if new_value else 'Repeat One'
        repeat_menu[2] = 'Repeat Off ✓' if new_value is None else 'Repeat Off'
        refresh_tray()
        if active_windows['main']:
            if new_value is None:
                repeat_img = REPEAT_OFF_IMG
                new_tooltip = 'Repeat'
            elif new_value:
                repeat_img = REPEAT_ONE_IMG
                new_tooltip = "Don't repeat"
            else:
                repeat_img = REPEAT_ALL_IMG
                new_tooltip = "Repeat track"
            main_window['repeat'].Update(image_data=repeat_img)
            main_window['repeat'].SetTooltip(new_tooltip)
        if settings['notifications']:
            if new_value is None: tray.ShowMessage('Music Caster', 'Repeat set to Off')
            elif new_value: tray.ShowMessage('Music Caster', 'Repeat set to One')
            else: tray.ShowMessage('Music Caster', 'Repeat set to All')
    return new_value


def save_queues():
    global save_queue_thread, settings

    def _save_queue():
        settings['queues']['done'] = done_queue
        settings['queues']['music'] = music_queue
        settings['queues']['next'] = next_queue
        save_settings()

    if save_queue_thread is None or not save_queue_thread.isAlive():
        save_queue_thread = Thread(target=_save_queue)
        save_queue_thread.start()


def update_volume(new_vol):
    """new_vol: float[0, 100]"""
    if active_windows['main']: main_window['volume_slider'].Update(value=new_vol)
    new_vol = new_vol / 100
    local_music_player.music.set_volume(new_vol)
    if cast is not None: cast.set_volume(new_vol)


def cycle_repeat():
    global settings
    if settings['repeat'] is None: new_repeat_setting = False  # Repeat All
    elif settings['repeat']: new_repeat_setting = None         # Repeat OFF
    else: new_repeat_setting = True                            # Repeat One
    return change_settings('repeat', new_repeat_setting)


def handle_exception(exception, restart_program=False):
    _current_time = str(datetime.now())
    trace_back_msg = traceback.format_exc()
    exc_type, exc_obj, exc_tb = sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2]
    mac = get_mac()
    payload = {'VERSION': VERSION, 'EXCEPTION TYPE': exc_type.__name__, 'LINE': exc_tb.tb_lineno,
               'TRACEBACK': fix_path(trace_back_msg), 'MAC': mac, 'FATAL': restart_program,
               'OS': platform.platform(), 'TIME': _current_time}
    try:
        with open(f'{starting_dir}/error.log', 'r') as _f:
            content = _f.read()
    except (FileNotFoundError, ValueError):
        content = ''
    with open(f'{starting_dir}/error.log', 'w') as _f:
        _f.write(pprint.pformat(payload))
        _f.write('\n')
        _f.write(content)
    if not IS_FROZEN: raise exception
    with suppress(requests.ConnectionError):
        requests.post('https://enmuvo35nwiw.x.pipedream.net', json=payload)
    if restart_program:
        with suppress(NameError):
            tray.ShowMessage('Music Caster Error', 'An error has occurred, restarting now')
            time.sleep(5)
        with suppress(Exception):
            stop()
        if IS_FROZEN: os.startfile('Music Caster.exe')
        sys.exit()


def get_metadata_wrapped(file_path: str) -> tuple:  # title, artist, album
    global variable_exception_sent
    try:
        try:
            return get_metadata(file_path)
        except mutagen.MutagenError:
            metadata = music_metadata[file_path]
            return metadata['title'], metadata['artist'], metadata['album']
    except Exception as _e:
        _title, _artist, _album = 'Unknown Title', 'Unknown Artist', 'Unknown Album'
        if not variable_exception_sent:
            handle_exception(_e)
            variable_exception_sent = True
    return _title, _artist, _album


def compile_all_songs(update_global=True, ignore_files: list = None):
    # returns the music library dict or starts building the library
    global compiling_songs_thread, all_songs
    if ignore_files is None: ignore_files = []

    def _compile_songs():
        global all_songs
        use_temp = not not all_songs
        all_songs_temp = {}
        for directory in music_directories:
            for _file in glob(f'{directory}/**/*.*', recursive=True):
                _file = _file.replace('\\', '/')
                if _file not in ignore_files and valid_music_file(_file):
                    title, artist, album = get_metadata_wrapped(_file)
                    _file_info = f'{title} - {artist}'
                    if _file not in music_metadata:
                        music_metadata[_file] = {'title': title, 'artist': artist, 'album': album}
                    if use_temp: all_songs_temp[_file_info] = _file
                    else: all_songs[_file_info] = _file
        if use_temp: all_songs = all_songs_temp.copy()
        del all_songs_temp

    if not update_global:
        temp_songs = all_songs.copy()
        if ignore_files:
            for ignore_file in ignore_files:
                file_info = get_metadata_wrapped(ignore_file)[:2]
                temp_songs.pop(' - '.join(file_info), None)
        return temp_songs
    if compiling_songs_thread is None:
        compiling_songs_thread = Thread(target=_compile_songs, daemon=True)
        compiling_songs_thread.start()
    elif not compiling_songs_thread.is_alive():
        compiling_songs_thread = Thread(target=_compile_songs, daemon=True)
        compiling_songs_thread.start()


def download(url, outfile):
    r = requests.get(url, stream=True)
    if outfile.endswith('.zip'):
        outfile = outfile.replace('.zip', '')
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(outfile)
    else:
        with open(outfile, 'wb') as _f:
            copyfileobj(r.raw, _f)


def set_save_position_callback(window: Sg.Window, _key):
    def save_window_position(event):
        if event.widget is window.TKroot:
            window_locations[_key] = window.CurrentLocation()
            save_settings()
    window.TKroot.bind('<Destroy>', save_window_position)


def get_window_location(window_key):
    if not settings['save_window_positions']: window_key = 'DEFAULT'
    return window_locations.get(window_key, (None, None))


# def get_album_cover(file_path, only_b64=True):
#     file_path_obj = Path(file_path)
#     thumb = thumbs_dir + f'/{file_path_obj.stem}.png'
#     tags = mutagen.File(file_path)
#     pict = None
#     for tag in tags.keys():
#         if 'APIC' in tag:
#             pict = tags[tag]
#             break
#     if pict is not None:
#         raw = pict = pict.data
#         with open(thumb, 'wb') as f: f.write(pict)
#     else:
#         thumb = f'{thumbs_dir}/default.png'
#         with open(thumb, 'rb') as f: raw = f.read()
#     data = io.BytesIO(raw)
#     im = Image.open(data)
#     raw = io.BytesIO()
#     new_h = 150
#     h_percent = (new_h / float(im.size[1]))
#     new_w = int((float(im.size[0]) * float(h_percent)))
#     im = im.resize((new_w, new_h), Image.ANTIALIAS)
#     im.save(raw, optimize=True, format='PNG')
#     return thumb, raw.getvalue()


def load_settings():  # up to 0.4 seconds
    """load (and fix if needed) the settings file"""
    global settings, playlists, music_directories, settings_last_modified, \
        DEFAULT_DIR, window_locations, settings_file_in_use
    if settings_file_in_use: return
    elif os.path.exists(settings_file):
        settings_file_in_use = True
        with open(settings_file) as json_file:
            try: loaded_settings = json.load(json_file)
            except json.decoder.JSONDecodeError: loaded_settings = {}
            overwrite_settings = False
            for setting_name, setting_value in tuple(loaded_settings.items()):
                loaded_settings[setting_name.replace(' ', '_')] = loaded_settings.pop(setting_name)
            for setting_name, setting_value in settings.items():
                if setting_name not in loaded_settings:
                    loaded_settings[setting_name] = setting_value
                    overwrite_settings = True
            settings = loaded_settings
            playlists = settings['playlists']
            tray_playlists.clear()  # global variable
            tray_playlists.append('Create/Edit a Playlist')
            tray_playlists.extend([f'PL: {pl}' for pl in playlists.keys()])
            _temp = music_directories.copy()
            music_directories = settings['music_directories']
            window_locations = settings['window_locations']
            if not music_directories: music_directories = change_settings('music_directories', [home_music_dir])
            if _temp != music_directories or music_directories == [home_music_dir]:
                compile_all_songs()
                refresh_folders()
            del _temp
            DEFAULT_DIR = music_directories[0]
            bg = settings['background_color']
            button_color = settings['button_text_color'], settings['accent_color']
            Sg.SetOptions(button_color=button_color, scrollbar_color=bg, background_color=bg,
                          element_background_color=bg,
                          text_element_background_color=bg, text_color=settings['text_color'])
        settings_file_in_use = False
        if overwrite_settings: save_settings()
    else:
        save_settings()
        load_settings()
    settings_last_modified = os.path.getmtime(settings_file)


# use socket io?
@app.route('/', methods=['GET', 'POST'])
def index():  # web GUI
    global music_queue, playing_status, all_songs, daemon_command
    if request.method == 'POST':
        for k, v in active_windows.items():  # Opens up GUI
            if v:
                {'main': main_window,
                 'playlist_selector': pl_selector_window,
                 'playlist_editor': pl_editor_window,
                 'play_url': play_url_window}[k].bring_to_front()
                return 'true'
        daemon_command = '__ACTIVATED__'
        return 'Music Caster'
    if request.args:
        if 'play' in request.args:
            if playing_status == 'PAUSED': resume()
            elif music_queue: play(music_queue[0])
            else: play_all()
        elif 'pause' in request.args and playing_status == 'PLAYING': pause()
        elif 'next' in request.args: daemon_command = 'Next Song'
        elif 'prev' in request.args: daemon_command = 'Previous Song'
        elif 'repeat' in request.args:
            cycle_repeat()
        elif 'shuffle' in request.args:
            change_settings('shuffle', not settings['shuffle'])
        return redirect('/')
    metadata = {'artist': 'N/A', 'title': 'Nothing Playing', 'album': 'N/A'}
    if playing_status in {'PLAYING', 'PAUSED'}:
        with suppress(KeyError, IndexError):
            metadata = music_metadata[music_queue[0]]
    art = metadata.get('art', f'data:image/png;base64,{DEFAULT_IMG_DATA}')
    repeat_option = settings['repeat']
    repeat_color = 'red' if settings['repeat'] is not None else ''
    shuffle_option = 'red' if settings['shuffle_playlists'] else ''
    list_of_songs = ''  #
    # sort by the formatted title
    sorted_songs = sorted(all_songs.items(), key=lambda item: item[0].lower())
    for formatted_track, filename in sorted_songs:
        filename = urllib.parse.urlencode({'path': filename})
        el = f'<a title="{formatted_track}" class="track" href="/play?{filename}">{formatted_track}</a>\n'
        list_of_songs += el
    _queue = create_songs_list()[0]
    device_index = 0
    for i, device_name in enumerate(device_names):
        if device_name.startswith('✓'):
            device_index = i
            break
    formatted_devices = ['Local Device'] + [cc.name for cc in chromecasts]
    return render_template('index.html', device_name=platform.node(), shuffle=shuffle_option, repeat_color=repeat_color,
                           metadata=metadata, main_button='pause' if playing_status == 'PLAYING' else 'play', art=art,
                           settings=settings, list_of_songs=list_of_songs, repeat_option=repeat_option, queue=_queue,
                           device_index=device_index, devices=formatted_devices)


@app.route('/play/', methods=['GET', 'POST'])
def play_file_page():
    global music_queue, playing_status
    request_args = request.args if request.method == 'GET' else request.form
    if 'path' in request_args:
        _file_or_dir = request_args['path']
        if os.path.isfile(_file_or_dir) and valid_music_file(_file_or_dir):
            play_all([_file_or_dir])
        elif os.path.isdir(_file_or_dir):
            play_folder([_file_or_dir])
    return redirect('/') if request.method == 'GET' else 'true'


@app.route('/metadata/')
def send_metadata():
    if music_queue:
        file_path = music_queue[0]
        metadata = music_metadata[file_path]
    else:
        metadata = {'artist': 'N/A', 'title': 'Nothing Playing', 'album': 'N/A'}
    return jsonify(metadata)


@app.route('/running/')
def running():
    return 'true'


@app.route('/change-setting/', methods=['POST'])
def change_settings_web():
    with suppress(KeyError):
        setting_key = request.json['setting_name']
        if setting_key in settings:
            change_settings(setting_key, request.json['value'])
        if setting_key == 'volume':
            update_volume(0 if settings['muted'] else settings['volume'])
        return 'true'
    return 'false'


@app.route('/change-device/', methods=['POST'])
def change_device_web():
    with suppress(KeyError):
        change_device(int(request.json['device_index']))
        return 'true'
    return 'false'


@app.route('/file/')
def get_file():
    if 'path' in request.args and request.args.get('secret', '') == MC_SECRET:  # security reasons
        _file_or_dir = request.args['path']
        if os.path.isfile(_file_or_dir):
            return send_file(_file_or_dir, conditional=True, as_attachment=True, cache_timeout=360000)
    return '404'


@app.errorhandler(404)
def page_not_found(_):
    return redirect('/')


@cmp_to_key
def chromecast_sorter(cc1: pychromecast.Chromecast, cc2: pychromecast.Chromecast):
    # sort by groups, then by name, then by UUID
    if cc1.device.cast_type == 'group' and cc2.device.cast_type != 'group': return -1
    if cc1.device.cast_type != 'group' and cc2.device.cast_type == 'group': return 1
    if cc1.name < cc2.name: return -1
    if cc1.name > cc2.name: return 1
    if str(cc1.uuid) > str(cc2.uuid): return 1
    return -1


def chromecast_callback(chromecast):
    global update_devices, cast, chromecasts
    previous_device = settings['previous_device']
    if str(chromecast.uuid) == previous_device and cast != chromecast:
        cast = chromecast
        cast.wait(timeout=WAIT_TIMEOUT)
    if chromecast.uuid not in [_cc.uuid for _cc in chromecasts]:
        chromecasts.append(chromecast)
        # chromecasts.sort(key=lambda _cc: (_cc.device.model_name, type, _cc.name, _cc.uuid))
        chromecasts.sort(key=chromecast_sorter)
        device_names.clear()
        for _i, _cc in enumerate(['Local device'] + chromecasts):
            _cc: pychromecast.Chromecast
            device_name = _cc if _i == 0 else _cc.name
            if (previous_device is None and _i == 0) or (type(_cc) != str and str(_cc.uuid) == previous_device):
                device_names.append(f'✓ {device_name}')
            else: device_names.append(f'{_i + 1}. {device_name}')
        refresh_tray()


def start_chromecast_discovery():
    global stop_discovery
    if stop_discovery is not None: stop_discovery()
    chromecasts.clear()
    # stop_discovery = find_chromecasts(callback=chromecast_callback)
    stop_discovery = pychromecast.get_chromecasts(blocking=False, callback=chromecast_callback)
    time.sleep(10.1)
    stop_discovery()
    if not device_names: device_names.append(f'✓ Local device')
    refresh_tray()


def change_device(selected_index):
    global cast
    if selected_index == 0: new_device = None
    else:
        try: new_device = chromecasts[selected_index - 1]
        except IndexError: new_device = None
    device_names.clear()
    for device_index, cc in enumerate(['Local device'] + chromecasts):
        cc: pychromecast.Chromecast = cc if device_index == 0 else cc.name
        if device_index == selected_index: device_names.append(f'✓ {cc}')
        else: device_names.append(f'{device_index + 1}. {cc}')
    refresh_tray()
    if cast != new_device:
        current_pos = 0
        if cast is not None and cast.app_id == APP_MEDIA_RECEIVER:
            mc = cast.media_controller
            with suppress(UnsupportedNamespace):
                mc.update_status()  # Switch device without playback loss
                current_pos = mc.status.adjusted_current_time
                if mc.is_playing or mc.is_paused: mc.stop()
            cast.quit_app()
        elif cast is None and local_music_player.music.get_busy():
            if playing_status == 'PLAYING': current_pos = time.time() - song_start
            else: current_pos = song_position
            local_music_player.music.stop()
        cast = new_device
        volume = 0 if settings['muted'] else settings['volume']
        change_settings('previous_device', None if cast is None else str(cast.uuid))
        # TODO: fix Chromecast is connection error
        with suppress(AttributeError): cast.wait(timeout=WAIT_TIMEOUT)
        update_volume(volume)
        if playing_status in {'PAUSED', 'PLAYING'}:
            do_autoplay = False if playing_status == 'PAUSED' else True
            play(music_queue[0], position=current_pos, autoplay=do_autoplay, switching_device=True)


def format_file(path: str):
    try:
        metadata = music_metadata[path]
        artist, title = metadata['artist'], metadata['title']
        if artist.startswith('Unknown') or title.startswith('Unknown'): raise KeyError
        return f'{artist} - {title}'
    except KeyError:
        if path.startswith('http'): return path
        base = os.path.basename(path)
        return os.path.splitext(base)[0]


def create_songs_list():
    """:returns the formatted song queue, and the selected value (currently playing)"""
    songs = []
    dq_len = len(done_queue)
    mq_start = len(next_queue) + 1
    selected_value = None
    # format: Index. Artists - Song Name
    for i, path in enumerate(done_queue):
        formatted_track = format_file(path)
        formatted_item = f'-{dq_len - i}. {formatted_track}'
        songs.append(formatted_item)
    if music_queue:
        formatted_track = format_file(music_queue[0])
        formatted_item = f' {0}. {formatted_track}'
        songs.append(formatted_item)
        selected_value = formatted_item
    for i, path in enumerate(next_queue):
        formatted_track = format_file(path)
        formatted_item = f' {i + 1}. {formatted_track}'
        songs.append(formatted_item)
    for i, path in enumerate(music_queue[1:]):
        formatted_track = format_file(path)
        formatted_item = f' {i + mq_start}. {formatted_track}'
        songs.append(formatted_item)
    return songs, selected_value


def play_url(url, position=0, autoplay=True):
    global cast, playing_url, playing_status, song_length, song_start, song_end, cast_last_checked
    if cast is None:
        tray.ShowMessage('Music Caster', 'ERROR: You are not connected to a cast device')
        return False
    elif valid_music_file(url):
        ext = url[::-1].split('.', 1)[0][::-1]
        url_frags = urlsplit(url)
        _title = url_frags.path.split('/')[-1]
        _artist = url_frags.netloc
        metadata = {'title': _title, 'artist': _artist, 'length': 0, 'album': url_frags.path[1:]}
        music_metadata[url] = metadata
        cast.wait()
        mc = cast.media_controller
        mc.play_media(url, f'audio/{ext}', metadata=metadata, current_time=position, autoplay=autoplay)
        mc.block_until_active()
        while mc.status.player_state not in {'PLAYING', 'PAUSED'}: time.sleep(0.1)
        song_start = time.time() - position
        song_end = time.time() * 2
        song_length = 3600  # 1 hour default
        playing_url, playing_status = True, 'PLAYING'
        if settings['notifications']:
            tray.ShowMessage('Music Caster', f'Playing: {url}', time=500)
        tray.Update(menu=menu_def_2, data_base64=FILLED_ICON, tooltip=f'Playing from {url_frags.netloc}')
        if settings['discord_rpc']:
            with suppress(AttributeError, pypresence.PyPresenceException):
                rich_presence.update(state=_artist, details=url_frags.path, large_image='default',
                                     large_text='Listening', small_image='logo', small_text='Music Caster')
        cast_last_checked = time.time() + 30
        return True
    elif get_youtube_id(url) is not None:
        try:
            if url not in music_metadata:
                r = ydl.extract_info(url, download=False)
                formats = [_f for _f in r['formats'] if _f['acodec'] != 'none' and _f['vcodec'] != 'none']
                if r['track']: _title = r['track']
                else: _title = r['title']
                if r['artist']: _artist = r['artist'].split(', ', 1)[0]
                else: _artist = r['uploader']
                formats.sort(key=lambda _f: _f['width'])
                _f = formats[0]
                song_length = r['duration']
                music_metadata[url] = {'title': _title, 'artist': r['artist'] or r['uploader'], 'album': r['album'],
                                       'length': song_length, 'art': r['thumbnail'], 'src': _f['url'], 'ext': _f['ext']}
            metadata = music_metadata[url]
            _title, _artist, _album = metadata['title'], metadata['artist'].split(', ', 1)[0], metadata['album']
            _metadata = {'metadataType': 3, 'albumName': _album, 'title': _title, 'artist': _artist}
            thumbnail, ext = metadata['art'], metadata['ext']
            cast.wait()
            mc = cast.media_controller
            mc.play_media(metadata['src'], f'video/{ext}', metadata=metadata, thumb=thumbnail,
                          current_time=position, autoplay=autoplay)
            mc.block_until_active()
            while mc.status.player_state not in {'PLAYING', 'PAUSED'}: time.sleep(0.1)
            song_start = time.time() - position
            song_end = song_start + song_length
            playing_url, playing_status = True, 'PLAYING'
            playing_text = f'{_artist} - {_title}'
            if settings['notifications']:
                tray.ShowMessage('Music Caster', 'Playing: ' + playing_text, time=500)
            tray.Update(menu=menu_def_2, data_base64=FILLED_ICON, tooltip=playing_text)
            if settings['discord_rpc']:
                with suppress(AttributeError, pypresence.PyPresenceException):
                    rich_presence.update(state=f'By: {_artist}', details=_title, large_image='default',
                                         large_text='Listening', small_image='logo', small_text='Music Caster')
            return True
        except StopIteration as _e:
            tray.ShowMessage('Music Caster ERROR', 'Could not play URL. Keep MC updated')
            if not IS_FROZEN: raise _e
    return False


def play(file_path, position=0, autoplay=True, switching_device=False):
    global song_start, song_end, playing_status, song_length, song_position,\
        thumbs_dir, cast_last_checked, music_queue, progress_bar_last_update
    while not os.path.exists(file_path):
        if play_url(file_path, position=position, autoplay=autoplay): return
        music_queue.remove(file_path)
        if music_queue: file_path = music_queue[0]
        else: return
        position = 0
    # named_tuple
    if file_path.lower().endswith('.wav'):
        a = WavInfoReader(file_path)
        sample_rate = a.fmt.sample_rate
        song_length = a.data.frame_count / sample_rate
    elif file_path.lower().endswith('.wma'):
        audio_info = AAC(file_path).info
        song_length, sample_rate = audio_info.length, audio_info.sample_rate
    elif file_path.lower().endswith('.opus'):
        audio_info = mutagen.File(file_path).info
        song_length, sample_rate = audio_info.length, 48000
    else:
        audio_info = mutagen.File(file_path).info
        song_length, sample_rate = audio_info.length, audio_info.sample_rate
    _volume = 0 if settings['muted'] else settings['volume'] / 100
    _title, _artist, album = get_metadata_wrapped(file_path)
    # thumb, album_cover_data = get_album_cover(file_path)
    # music_meta_data[file_path] = {'artist': artist, 'title': title, 'album': album, 'length': song_length,
    #                               'album_cover_data': album_cover_data}
    pict = None
    tags = mutagen.File(file_path)
    if tags is not None:
        for tag in tags.keys():
            if 'APIC' in tag:
                pict = tags[tag].data
                break
    if pict:
        music_metadata[file_path] = {'artist': _artist, 'title': _title, 'album': album, 'length': song_length,
                                     'art': f'data:image/png;base64,{base64.b64encode(pict).decode("utf-8")}'}
    else: music_metadata[file_path] = {'artist': _artist, 'title': _title, 'album': album, 'length': song_length}

    if cast is None:  # play locally
        if file_path.lower()[-3:] not in {'mp3', 'ogg'}:
            if settings['notifications']:
                file_format = file_path.split('.')[-1]
                tray.ShowMessage('Music Caster', f'File format {file_format} not supported')
            music_queue.pop(0)
            if music_queue:
                play(music_queue[0])
            return
        if local_music_player.get_init() is None or local_music_player.get_init()[0] != sample_rate:
            local_music_player.quit()
            local_music_player.init(sample_rate, -16, 2, 2048)
        local_music_player.music.load(file_path)
        local_music_player.music.set_volume(_volume)
        local_music_player.music.play(start=position)
        if not autoplay: local_music_player.music.pause()
        song_position = position
        song_start = time.time() - song_position
        song_end = song_start + song_length
    else:
        try:
            ipv4_address = get_ipv4()
            file_path_obj = Path(file_path)
            url_args = urllib.parse.urlencode({'path': file_path, 'secret': MC_SECRET})
            url = f'http://{ipv4_address}:{PORT}/file?{url_args}'
            if pict:
                thumb = thumbs_dir + f'/{file_path_obj.stem}.png'
                with open(thumb, 'wb') as _f: _f.write(pict)
            else: thumb = f'{thumbs_dir}/default.png'
            url_args = urllib.parse.urlencode({'path': thumb, 'secret': MC_SECRET})
            thumb = f'http://{ipv4_address}:{PORT}/file?{url_args}'
            cast.wait(timeout=WAIT_TIMEOUT)
            cast.set_volume(_volume)
            mc = cast.media_controller
            if mc.status.player_is_playing or mc.status.player_is_paused:
                mc.stop()
                mc.block_until_active(5)
            metadata = {'metadataType': 3, 'albumName': album, 'title': _title, 'artist': _artist}
            mc.play_media(url, f'audio/{file_path.split(".")[-1]}', current_time=position,
                          metadata=metadata, thumb=thumb, autoplay=autoplay)
            mc.block_until_active()
            while mc.status.player_state not in {'PLAYING', 'PAUSED'}: time.sleep(0.1)
            progress_bar_last_update = time.time()
            song_position = position
            song_start = time.time() - song_position
            song_end = song_start + song_length
        except (pychromecast.error.NotConnected, OSError) as _e:
            if _e == OSError: handle_exception(_e)
            tray.ShowMessage('Music Caster Error', 'Could not connect to Chromecast device')
            with suppress(pychromecast.error.UnsupportedNamespace): stop()
            return
    playing_text = f"{_artist.split(', ')[0]} - {_title}"
    if settings['notifications'] and not switching_device:
        tray.ShowMessage('Music Caster', 'Playing: ' + playing_text, time=500)
    if autoplay:
        playing_status = 'PLAYING'
        tray.Update(menu=menu_def_2, data_base64=FILLED_ICON, tooltip=playing_text)
    else: tray.Update(menu=menu_def_3, data_base64=UNFILLED_ICON)
    cast_last_checked = time.time()
    if settings['save_queue_sessions']: save_queues()
    if settings['discord_rpc']:
        with suppress(AttributeError, pypresence.PyPresenceException):
            rich_presence.update(state=f'By: {_artist}', details=_title, large_image='default',
                                 large_text='Listening', small_image='logo', small_text='Music Caster')


def play_all(starting_files: list = None, queue_only=False):
    global playing_status, compiling_songs_thread
    music_queue.clear()
    done_queue.clear()
    if starting_files is None: starting_files = []
    starting_files = [_f.replace('\\', '/') for _f in starting_files if valid_music_file(_f)]
    if compiling_songs_thread is not None and compiling_songs_thread.is_alive():
        if settings['notifications']:
            tray.ShowMessage('Music Caster', 'Some files may be missing as music library is still being built')
    if starting_files: music_queue.extend(compile_all_songs(False, starting_files).values())
    else: music_queue.extend(all_songs.values())
    if music_queue: shuffle(music_queue)
    if starting_files:
        for j, _f in enumerate(starting_files):
            music_queue.insert(j, _f)
    if not queue_only:
        if music_queue:
            play(music_queue[0])
        elif next_queue:
            playing_status = 'PLAYING'
            next_song()


def play_folder(folders):
    global playing_status
    music_queue.clear()
    done_queue.clear()
    for _folder in folders:
        for _file in glob(f'{_folder}/**/*.*', recursive=True):
            if valid_music_file(_file): music_queue.append(_file)
    if settings['shuffle_playlists']: shuffle(music_queue)
    if music_queue: play(music_queue[0])
    elif next_queue:
        playing_status = 'PLAYING'
        next_song()


def select_and_play_folder():
    dlg = wx.DirDialog(None, 'Choose folder to play', DEFAULT_DIR, style=wx.DD_DIR_MUST_EXIST)
    if dlg.ShowModal() != wx.ID_CANCEL:
        path_to_folder = dlg.GetPath()
        play_folder([path_to_folder])


def file_action(action='Play File(s)'):
    # actions = 'Play File(s)', 'Play File(s) Next', 'Queue File(s)'
    global DEFAULT_DIR, music_queue, next_queue, playing_status, main_last_event
    DEFAULT_DIR = music_directories[0] if music_directories else home_music_dir
    fd = wx.FileDialog(None, 'Select Music File(s)', defaultDir=DEFAULT_DIR, wildcard=MUSIC_FILE_TYPES,
                       style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE)
    if fd.ShowModal() != wx.ID_CANCEL:
        if action == 'Play File(s)':
            play_all(fd.GetPaths())
        elif action == 'Queue File(s)':
            _start_playing = not music_queue
            music_queue += [_f for _f in fd.GetPaths() if valid_music_file(_f)]
            if _start_playing and music_queue: play(music_queue[0])
        elif action == 'Play File(s) Next':
            next_queue += [_f for _f in fd.GetPaths() if valid_music_file(_f)]
            if playing_status == 'NOT PLAYING' and not music_queue and next_queue:
                if cast is not None and cast.app_id != APP_MEDIA_RECEIVER: cast.wait(timeout=WAIT_TIMEOUT)
                playing_status = 'PLAYING'
                next_song()
        else: raise ValueError('Expected one of: "Play File(s)", "Play File(s) Next", or "Queue File(s)"')
        main_last_event = '__TIMEOUT__'
    else: main_last_event = 'file_action'


def play_file():
    file_action()


def queue_file():
    file_action('Queue File(s)')


def play_next():
    file_action('Play File(s) Next')


def folder_action(action='Play Folder'):
    global DEFAULT_DIR, music_queue, next_queue, playing_status, main_last_event
    # actions: 'Play Folder', 'Play Folder Next', 'Queue Folder'
    DEFAULT_DIR = music_directories[0] if music_directories else home_music_dir
    dlg = wx.DirDialog(None, 'Select Folder', DEFAULT_DIR, style=wx.DD_DIR_MUST_EXIST)
    if dlg.ShowModal() != wx.ID_CANCEL and os.path.exists(dlg.GetPath()):
        folder_path = dlg.GetPath()
        temp_queue = []
        for _f in glob(f'{folder_path}/**/*.*', recursive=True):
            if valid_music_file(_f): temp_queue.append(_f)
        if settings['shuffle_playlists']: shuffle(temp_queue)
        if action == 'Play Folder':
            music_queue.clear()
            done_queue.clear()
            music_queue += temp_queue
            if music_queue: play(music_queue[0])
        elif action == 'Play Folder Next':
            next_queue += temp_queue
            if playing_status == 'NOT PLAYING' and not music_queue and next_queue:
                if cast is not None and cast.app_id != APP_MEDIA_RECEIVER: cast.wait(timeout=WAIT_TIMEOUT)
                playing_status = 'PLAYING'
                next_song()
        elif action == 'Queue Folder':
            start_playing = not music_queue
            music_queue += temp_queue
            if start_playing and music_queue: play(music_queue[0])
        else: raise ValueError('Expected one of: "Play Folder", "Play Folder Next", or "Queue Folder"')
        if active_windows['main']:
            gui_queue = create_songs_list()[0]
            main_window['queue'].Update(values=gui_queue)
        del temp_queue
        main_last_event = '__TIMEOUT__'
    else: main_last_event = 'folder_action'


def update_song_position():
    global tray, song_position, cast
    if cast is not None:
        try:
            mc = cast.media_controller
            mc.update_status()
            song_position = mc.status.adjusted_current_time
        except (UnsupportedNamespace, NotConnected):
            song_position = time.time() - song_start
    elif playing_status == 'PLAYING': song_position = time.time() - song_start
    return song_position


def pause():
    global tray, playing_status, song_position
    tray.Update(menu=menu_def_3, data_base64=UNFILLED_ICON)
    try:
        if cast is None:
            song_position = time.time() - song_start
            local_music_player.music.pause()
        else:
            mc = cast.media_controller
            mc.update_status()
            mc.pause()
            while not mc.status.player_is_paused: time.sleep(0.1)
            song_position = mc.status.adjusted_current_time
        playing_status = 'PAUSED'
        if music_queue:
            _title, _artist = get_metadata_wrapped(music_queue[0])[:2]
            if settings['discord_rpc']:
                with suppress(AttributeError, pypresence.PyPresenceException):
                    rich_presence.update(state=f'By: {_artist}', details=_title, large_image='default',
                                         large_text='Paused', small_image='logo', small_text='Music Caster')
    except UnsupportedNamespace:
        stop()


def resume():
    global tray, playing_status, song_end, song_position, song_start
    tray.Update(menu=menu_def_2, data_base64=FILLED_ICON)
    try:
        if cast is None: local_music_player.music.unpause()
        else:
            mc = cast.media_controller
            mc.update_status()
            mc.play()
            mc.block_until_active()
            while not mc.status.player_state == 'PLAYING': time.sleep(0.1)
            song_position = mc.status.adjusted_current_time
        song_start = time.time() - song_position
        song_end = song_start + song_length
        playing_status = 'PLAYING'
        _title, _artist = get_metadata_wrapped(music_queue[0])[:2]
        if settings['discord_rpc']:
            with suppress(AttributeError, pypresence.PyPresenceException):
                rich_presence.update(state=f'By: {_artist}', details=_title, large_image='default',
                                     large_text='Playing', small_image='logo', small_text='Music Caster')
    except (UnsupportedNamespace, NotConnected):
        play(music_queue[0], position=song_position)


def stop():
    global playing_status, cast, song_position
    playing_status = 'NOT PLAYING'
    if settings['discord_rpc']:
        with suppress(AttributeError, RuntimeError, pypresence.PyPresenceException): rich_presence.clear()
    if cast is not None and cast.app_id == APP_MEDIA_RECEIVER:
        mc = cast.media_controller
        mc.stop()
        while mc.is_playing or mc.is_paused: time.sleep(0.1)
    elif local_music_player.music.get_busy():
        local_music_player.music.stop()
        # local_music_player.music.unload()  # only in 2.0
    song_position = 0
    tray.Update(menu=menu_def_1, data_base64=UNFILLED_ICON, tooltip='Music Caster')


def next_song(from_timeout=False):
    global playing_status
    if cast is not None and cast.app_id != APP_MEDIA_RECEIVER:
        playing_status = 'NOT PLAYING'
    elif playing_status != 'NOT PLAYING' and next_queue or music_queue:
        if not settings['repeat'] or not music_queue or not from_timeout:
            if settings['repeat']: change_settings('repeat', False)
            if music_queue: done_queue.append(music_queue.pop(0))
            if next_queue: music_queue.insert(0, next_queue.pop(0))
            if not music_queue and settings['repeat'] is False and done_queue:
                music_queue.extend(done_queue)
                done_queue.clear()
        if music_queue: play(music_queue[0])
        else: stop()  # repeat is off / no songs in queue


def prev_song():
    global playing_status
    if cast is not None and cast.app_id != APP_MEDIA_RECEIVER: playing_status = 'NOT PLAYING'
    elif playing_status != 'NOT PLAYING':
        if done_queue:
            if settings['repeat']: change_settings('repeat', False)
            song = done_queue.pop()
            music_queue.insert(0, song)
            play(song)
        elif music_queue: play(music_queue[0])


def background_tasks():
    global cast, cast_last_checked, song_start, song_end, song_position, daemon_command, settings_last_modified

    while True:
        # SETTINGS_LAST_MODIFIED
        if os.path.getmtime(settings_file) != settings_last_modified: load_settings()  # updates last modified
        refresh_tray()
        if cast is not None and time.time() - cast_last_checked > 5:
            with suppress(UnsupportedNamespace):
                if cast.app_id == APP_MEDIA_RECEIVER:
                    mc = cast.media_controller
                    mc.update_status()
                    is_playing, is_paused = mc.status.player_is_playing, mc.status.player_is_paused
                    new_song_position = mc.status.adjusted_current_time
                    _volume = settings['volume']
                    cast_volume = cast.status.volume_level * 100
                    song_start = time.time() - new_song_position  # if music was scrubbed on the home app
                    song_end = time.time() + song_length - new_song_position
                    song_position = new_song_position
                    if is_paused and playing_status not in {'PAUSED', 'NOT PLAYING'}: daemon_command = 'Pause'
                    elif is_playing and playing_status not in {'PLAYING', 'NOT PLAYING'}:
                        daemon_command = 'Resume'
                    elif not (is_playing or is_paused) and playing_status != 'NOT PLAYING':
                        daemon_command = 'Stop'
                    if _volume != cast_volume:
                        if cast_volume or cast_volume == 0 and not settings['muted']:
                            _volume = change_settings('volume', cast_volume)
                            if _volume and settings['muted']: change_settings('muted', not settings['muted'])
                            if active_windows['main']:
                                if _volume and settings['muted']:
                                    main_window['mute'].Update(data=VOLUME_IMG)
                                main_window['volume_slider'].Update(_volume)
                elif playing_status in {'PAUSED', 'PLAYING'}: daemon_command = 'Stop'
            cast_last_checked = time.time()
        time.sleep(5)


def on_press(key):
    global last_press, daemon_command
    key = str(key)
    PRESSED_KEYS.add(key)
    if (len(PRESSED_KEYS) == 4 and "'m'" in PRESSED_KEYS and
            ('Key.ctrl_l' in PRESSED_KEYS or 'Key.ctrl_r' in PRESSED_KEYS) and
            ('Key.shift' in PRESSED_KEYS or 'Key.shift_r' in PRESSED_KEYS) and
            ('Key.alt_l' in PRESSED_KEYS or 'Key.alt_r' in PRESSED_KEYS)):
        daemon_command = '__ACTIVATED__'
    if key not in {'<179>', '<176>', '<177>', '<178>'} or time.time() - last_press < 0.15: return
    if key == '<179>':
        if playing_status == 'PLAYING': daemon_command = 'Pause'
        elif playing_status == 'PAUSED': daemon_command = 'Resume'
    elif key == '<176>' and playing_status != 'NOT PLAYING': daemon_command = 'Next Song'
    elif key == '<177>' and playing_status != 'NOT PLAYING': daemon_command = 'Previous Song'
    elif key == '<178>': stop()
    last_press = time.time()


def on_release(key):
    with suppress(KeyError): PRESSED_KEYS.remove(str(key))


def activate_main_window(selected_tab='tab_queue'):
    global active_windows, main_window, IPV4, QR_CODE
    # selected_tab can be 'tab_queue', 'tab_settings', or 'tab_timer'
    if not active_windows['main']:
        active_windows['main'] = True
        window_location = get_window_location('main')
        songs_list, selected_value = create_songs_list()
        if playing_status in {'PAUSED', 'PLAYING'} and music_queue:
            current_song = music_queue[0]
            metadata = music_metadata[current_song]
            artist, title = metadata['artist'].split(', ')[0], metadata['title']
            album_cover_data = metadata.get('album_cover_data', None)
            # album_cover_data = DEFAULT_IMG_DATA
            if get_ipv4() != IPV4:
                IPV4 = get_ipv4()
                QR_CODE = create_qr_code(PORT)
            main_gui_layout = create_main(songs_list, selected_value, playing_status, settings, VERSION, QR_CODE,
                                          timer, title, artist, album_cover_data=album_cover_data)
        else:
            main_gui_layout = create_main(songs_list, selected_value, playing_status, settings,
                                          VERSION, QR_CODE, timer)
        main_window = Sg.Window('Music Caster', main_gui_layout, background_color=settings['background_color'],
                                icon=WINDOW_ICON, return_keyboard_events=True,
                                use_default_focus=False, location=window_location)
        main_window.Finalize()
        main_window['queue'].Update(set_to_index=len(done_queue), scroll_to_index=len(done_queue))
        main_window['volume_slider'].bind('<Enter>', '_mouse_enter')
        main_window['volume_slider'].bind('<Leave>', '_mouse_leave')
        main_window['progressbar'].bind('<Enter>', '_mouse_enter')
        main_window['progressbar'].bind('<Leave>', '_mouse_leave')
        main_window['queue'].bind('<Enter>', '_mouse_enter')
        main_window['queue'].bind('<Leave>', '_mouse_leave')
        set_save_position_callback(main_window, 'main')
    main_window[selected_tab].Select()
    if selected_tab == 'tab_timer':
        main_window['minutes'].SetFocus()
    main_window.TKroot.focus_force()
    main_window.Normal()


def create_edit_playlists():
    global active_windows, pl_selector_window
    if active_windows['playlist_editor']:
        pl_editor_window.TKroot.focus_force()
        pl_editor_window.Normal()
        return
    elif not active_windows['playlist_selector']:
        active_windows['playlist_selector'] = True
        window_location = get_window_location('playlist_selector')
        pl_selector_window = Sg.Window('Playlist Selector', create_playlist_selector(settings),
                                       background_color=settings['background_color'],
                                       icon=WINDOW_ICON, return_keyboard_events=True, location=window_location)
        pl_selector_window.Finalize()
        set_save_position_callback(pl_selector_window, 'playlist_selector')
    pl_selector_window.TKroot.focus_force()
    pl_selector_window.Normal()


def activate_play_url(combo_value='Play Immediately'):
    global play_url_window
    if not active_windows['play_url']:
        active_windows['play_url'], play_url_layout = True, create_play_url_window(combo_value=combo_value)
        window_location = get_window_location('play_url')
        play_url_window = Sg.Window('Music Caster - Play URL', play_url_layout, icon=WINDOW_ICON,
                                    return_keyboard_events=True, location=window_location)
        play_url_window.Finalize()
        set_save_position_callback(play_url_window, 'play_url')
    play_url_window.TKroot.focus_force()
    play_url_window.Normal()
    play_url_window['url'].SetFocus()


def cancel_timer():
    global timer
    timer = 0
    if settings['notifications']: tray.ShowMessage('Music Caster', 'Timer stopped')


def locate_file():
    if music_queue: Popen(f'explorer /select,"{fix_path(music_queue[0])}"')


def exit_program():
    tray.Hide()
    with suppress(UnsupportedNamespace):
        if cast is None:
            stop()
        elif cast is not None and cast.app_id == APP_MEDIA_RECEIVER and playing_status != 'NOT PLAYING':
            cast.quit_app()
    with suppress(AttributeError, RuntimeError, pypresence.PyPresenceException):
        rich_presence.close()
    sys.exit()


def play_playlist(playlist_name):
    if playlist_name in playlists:
        music_queue.clear()
        done_queue.clear()
        music_queue.extend(playlists.get(playlist_name, []))
        if music_queue:
            if settings['shuffle_playlists']: shuffle(music_queue)
            play(music_queue[0])


def other_tray_actions(_tray_item):
    global cast, cast_last_checked, timer
    if _tray_item.split('.', 1)[0].isdigit():  # if user selected a different device
        with suppress(ValueError):
            change_device(device_names.index(tray_item))
    elif _tray_item.startswith('PL: '):  # playlist
        play_playlist(tray_item[4:])
    elif _tray_item.startswith('PF: '):  # play folder
        if tray_item == 'PF: Select Folder(s)':
            Thread(target=select_and_play_folder).start()
        else:
            play_folder([music_directories[tray_folders.index(tray_item) - 1]])
    elif playing_status == 'PLAYING' and time.time() > song_end:
        next_song(from_timeout=time.time() > song_end)
    elif timer and time.time() > timer:
        stop()
        timer = 0
        if settings['timer_shut_off_computer']:
            if platform.system() == 'Windows': os.system('shutdown /p /f')
            else: os.system('shutdown -h now')
        elif settings['timer_hibernate_computer']:
            if platform.system() == 'Windows': os.system(r'rundll32.exe powrprof.dll,SetSuspendState Hibernate')
        elif settings['timer_sleep_computer']:
            if platform.system() == 'Windows': os.system('rundll32.exe powrprof.dll,SetSuspendState 0,1,0')


def next_song_command():
    if playing_status != 'NOT PLAYING': next_song()


def previous_song():
    if playing_status != 'NOT PLAYING': prev_song()


def reset_mouse_hover():
    global mouse_hover
    mouse_hover = ''


def reset_progress():
    # NOTE: needs to be in main thread
    main_window['progressbar'].Update(value=0)
    main_window['time_elapsed'].Update(value='00:00')
    main_window['time_left'].Update(value='00:00')
    main_window.Refresh()


def read_main_window():
    global main_last_event, mouse_hover, playing_status, song_position, progress_bar_last_update,\
        song_start, song_end, timer, main_window
    # make if statements into dict mapping
    main_event, main_values = main_window.Read(timeout=10)
    if main_event in {None, 'Escape:27'} and main_last_event not in {'file_action', 'folder_action'}:
        active_windows['main'] = False
        main_window.Close()
        return False
    main_value = main_values.get(main_event)
    if 'mouse_leave' not in main_event and 'mouse_enter' not in main_event and main_event != '__TIMEOUT__':
        main_last_event = main_event
    p_r_button = main_window['pause/resume']
    gui_title = main_window['title'].DisplayText
    time_left = None
    artist, title = '', 'Nothing Playing'
    with suppress(KeyError, IndexError):
        if playing_status in {'PAUSED', 'PLAYING'}:
            metadata = music_metadata[music_queue[0]]
            artist, title = metadata['artist'].split(', ', 1)[0], metadata['title']
    if main_event.startswith('MouseWheel'):
        main_event = main_event.split(':', 1)[1]
        delta = {'Up': 5, 'Down': -5}.get(main_event, 0)
        if mouse_hover == 'progressbar':
            if playing_status in {'PLAYING', 'PAUSED'}:
                update_song_position()
                new_position = min(max(song_position + delta, 0), song_length) / song_length * 100
                main_window['progressbar'].Update(value=new_position)
                main_values['progressbar'] = new_position
                main_event = 'progressbar'
        elif mouse_hover in {'', 'volume_slider'}:  # not in another tab
            new_volume = min(max(0, main_values['volume_slider'] + delta), 100)
            change_settings('volume', new_volume)
            update_volume(new_volume)
        main_window.Refresh()
    if main_event in {'j', 'l'} and main_values['tab_group'] != 'tab_timer':
        if playing_status in {'PLAYING', 'PAUSED'}:
            delta = {'j': -settings['scrubbing_delta'], 'l': settings['scrubbing_delta']}[main_event]
            update_song_position()
            new_position = min(max(song_position + delta, 0), song_length) / song_length * 100
            main_window['progressbar'].Update(value=new_position)
            main_values['progressbar'] = new_position
            main_event = 'progressbar'
            main_window.Refresh()
    if main_event == '__TIMEOUT__': pass
    elif main_event == '1:49': main_window['tab_queue'].Select()
    elif main_event == '2:50' or main_event == 'tab_group' and main_values['tab_group'] == 'tab_timer':
        main_window['tab_timer'].Select()
        main_window['minutes'].SetFocus()
    elif main_event == 'tab_group' and main_values['tab_group'] == 'tab_queue': main_window['file_action'].SetFocus()
    elif main_event == 'tab_group' and main_values['tab_group'] == 'tab_settings': main_window['auto_update'].SetFocus()
    elif main_event == '3:51': main_window['tab_settings'].Select()
    elif main_event.endswith('mouse_enter'):
        mouse_hover = '_'.join(main_event.split('_')[:-2])
    elif main_event in {'progressbar_mouse_leave', 'queue_mouse_leave'}:
        mouse_hover = ''
    elif main_event in {'locate_file', 'e:69'}:
        with suppress(IndexError):
            selected_file_index = int(main_values['queue'][0].split('.', 1)[0])
            if selected_file_index < 0:
                Popen(f'explorer /select,"{fix_path(done_queue[selected_file_index])}"')
            elif (selected_file_index == 0 or selected_file_index > len(next_queue)) and music_queue:
                Popen(f'explorer /select,"{fix_path(music_queue[selected_file_index])}"')
            elif 0 < selected_file_index <= len(next_queue):
                Popen(f'explorer /select,"{fix_path(next_queue[selected_file_index - 1])}"')
    elif main_event == 'pause/resume' or main_event == 'k' and main_values['tab_group'] != 'tab_timer':
        try:
            pause_resume[playing_status]()
        except KeyError:
            if music_queue: play(music_queue[0])
            else: play_all()
    elif main_event == 'next' and playing_status != 'NOT PLAYING':
        reset_progress()
        next_song()
    elif main_event == 'prev' and playing_status != 'NOT PLAYING':
        reset_progress()
        prev_song()
    elif main_event == 'shuffle':
        # TODO: just shuffle music queue
        pass
    elif main_event in {'repeat', 'r:82'}:
        cycle_repeat()
    elif ((main_event in {'volume_slider', 'a', 'd'} or main_event.isdigit())
          and main_values['tab_group'] == 'tab_queue'):
        delta = 0
        if main_event.isdigit():
            new_volume = int(main_event) * 10
        else:
            if main_event == 'a': delta = -5
            elif main_event == 'd': delta = 5
            new_volume = main_values['volume_slider'] + delta
        change_settings('volume', new_volume)
        update_volume(new_volume)
    elif main_event in {'mute', 'm:77'}:
        muted = change_settings('muted', not settings['muted'])
        if muted:
            main_window['mute'].Update(data=VOLUME_MUTED_IMG)
            update_volume(0)
        else:
            main_window['mute'].Update(data=VOLUME_IMG)
            main_window['volume_slider'].Update(settings['volume'])
            local_music_player.music.set_volume(settings['volume'] / 100)
            if cast is not None: cast.set_volume(settings['volume'] / 100)
    elif main_event in {'Up:38', 'Down:40', 'Prior:33', 'Next:34'}:
        with suppress(AttributeError, IndexError):
            if main_window.FindElementWithFocus() == main_window['queue']:
                move = {'Up:38': -1, 'Down:40': 1, 'Prior:33': -3, 'Next:34': 3}[main_event]
                new_i = main_window['queue'].GetListValues().index(main_values['queue'][0]) + move
                new_i = min(max(new_i, 0), len(music_queue) - 1)
                main_window['queue'].Update(set_to_index=new_i, scroll_to_index=new_i)
    elif main_event == 'queue' and main_value:
        selected_file_index = main_window['queue'].GetListValues().index(main_value[0])
        if done_queue and selected_file_index < len(done_queue):
            while next_queue:  # design decision to empty next queue
                music_queue.insert(1, next_queue.pop())
            for i in range(len(done_queue) - selected_file_index):
                music_queue.insert(0, done_queue.pop())
        else:
            for i in range(selected_file_index - len(done_queue)):
                if not music_queue: break
                done_queue.append(music_queue.pop(0))
                if next_queue:
                    music_queue.insert(0, next_queue.pop(0))
        play(music_queue[0])
        updated_list = create_songs_list()[0]
        dq_len = len(done_queue)
        main_window['queue'].Update(values=updated_list, set_to_index=dq_len, scroll_to_index=dq_len)
    elif main_event == 'move_up' and main_values['queue']:
        # index_to_move = int(main_values['queue'][0].split('.', 1)[0])
        index_to_move = main_window['queue'].GetListValues().index(main_values['queue'][0])
        new_i = index_to_move - 1
        dq_len = len(done_queue)
        nq_len = len(next_queue)
        if index_to_move < dq_len:  # move within dq
            done_queue.insert(new_i, done_queue.pop(index_to_move))
        elif index_to_move == dq_len and done_queue:  # move index -1 to 1
            if next_queue:
                next_queue.insert(1, done_queue.pop())
            else:
                music_queue.insert(1, done_queue.pop())
        elif index_to_move == dq_len + 1:  # move 1 to -1
            if next_queue:
                done_queue.append(next_queue.pop(0))
            else:
                done_queue.append(music_queue.pop(1))
        elif next_queue and index_to_move < dq_len + nq_len + 1:  # within next_queue
            nq_i = new_i - dq_len - 1
            next_queue.insert(nq_i, next_queue.pop(nq_i + 1))
        elif next_queue and index_to_move == dq_len + nq_len + 1:  # moving into next queue
            next_queue.insert(nq_len - 1, music_queue.pop(1))
        else:  # moving within mq
            mq_i = new_i - dq_len - nq_len
            music_queue.insert(mq_i, music_queue.pop(mq_i + 1))
        updated_list = create_songs_list()[0]
        main_window['queue'].Update(values=updated_list, set_to_index=new_i, scroll_to_index=new_i)
    elif main_event == 'move_down' and main_values['queue']:
        index_to_move = main_window['queue'].GetListValues().index(main_values['queue'][0])
        dq_len, nq_len, mq_len = len(done_queue), len(next_queue), len(music_queue)
        if index_to_move < dq_len + nq_len + mq_len - 1:
            new_i = index_to_move + 1
            if index_to_move == dq_len - 1:  # move index -1 to 1
                if next_queue:
                    next_queue.insert(0, done_queue.pop())
                else:
                    music_queue.insert(1, done_queue.pop())
            elif index_to_move < dq_len:  # move within dq
                done_queue.insert(new_i, done_queue.pop(index_to_move))
            elif index_to_move == dq_len:  # move 1 to -1
                if next_queue:
                    done_queue.append(next_queue.pop(0))
                else:
                    done_queue.append(music_queue.pop(1))
            elif next_queue and index_to_move == dq_len + nq_len:  # moving into music_queue
                music_queue.insert(2, next_queue.pop())
            elif index_to_move < dq_len + nq_len + 1:  # within next_queue
                nq_i = index_to_move - dq_len - 1
                next_queue.insert(nq_i, next_queue.pop(nq_i - 1))
            else:  # within music_queue
                mq_i = new_i - dq_len - nq_len
                music_queue.insert(mq_i, music_queue.pop(mq_i - 1))
            updated_list = create_songs_list()[0]
            main_window['queue'].Update(values=updated_list, set_to_index=new_i, scroll_to_index=new_i)
    elif main_event == 'remove' and main_values['queue']:
        index_to_remove = main_window['queue'].GetListValues().index(main_values['queue'][0])
        dq_len, nq_len, mq_len = len(done_queue), len(next_queue), len(music_queue)
        if index_to_remove < dq_len:
            done_queue.pop(index_to_remove)
        elif index_to_remove == dq_len:
            music_queue.pop(0)
            if music_queue: play(music_queue[0])
        elif index_to_remove <= nq_len + dq_len:
            next_queue.pop(index_to_remove - dq_len - 1)
        elif index_to_remove < nq_len + mq_len + dq_len:
            music_queue.pop(index_to_remove - dq_len - nq_len)
        updated_list = create_songs_list()[0]
        new_i = min(len(updated_list), index_to_remove)
        main_window['queue'].Update(values=updated_list, set_to_index=new_i, scroll_to_index=new_i)
    elif main_event == 'file_option': main_window['file_action'].Update(text=main_values['file_option'])
    elif main_event == 'folder_option': main_window['folder_action'].Update(text=main_values['folder_option'])
    elif main_event == 'file_action':
        Thread(target=file_action, kwargs={'action': main_values['file_option']}).start()
    elif main_event == 'folder_action':
        Thread(target=folder_action, kwargs={'action': main_values['folder_option']}).start()
    elif main_event == 'play_playlist': play_playlist(main_values['playlists'])
    elif main_event == 'url_actions': activate_play_url()
    elif main_event == 'clear_queue':
        reset_progress()
        main_window['queue'].Update(values=[])
        if playing_status in {'PLAYING', 'PAUSED'}: stop()
        music_queue.clear()
        next_queue.clear()
        done_queue.clear()
    elif main_event == 'play_next':
        play_next()
        main_window.TKroot.focus_force()
    elif main_event == 'locate_file':
        Popen(f'explorer /select,"{fix_path(music_queue[0])}"')
    elif main_event == 'library':
        play_all([all_songs[main_value]])
    elif main_event == 'progressbar':
        if playing_status == 'NOT PLAYING':
            main_window['progressbar'].Update(disabled=True, value=0)
            # maybe even make it invisible?
            return
        else:
            new_position = main_values['progressbar'] / 100 * song_length
            song_position = new_position
            if cast is not None:
                cast.media_controller.seek(new_position)
                playing_status = 'PLAYING'
            else:
                local_music_player.music.rewind()
                local_music_player.music.set_pos(new_position)
            time_left = song_length - song_position
            song_end = time.time() + time_left
            song_start = song_end - song_length
    # settings
    elif main_event == 'email': Thread(target=webbrowser.open, args=[EMAIL_URL]).start()
    elif main_event == 'web_gui':
        Thread(target=webbrowser.open, args=[f'http://{get_ipv4()}:{PORT}']).start()
    elif main_event in {'auto_update', 'notifications', 'discord_rpc', 'run_on_startup',
                        'shuffle_playlists', 'save_window_positions', 'populate_queue_startup',
                        'save_queue_sessions'}:
        change_settings(main_event, main_value)
        if main_event == 'run_on_startup': create_shortcut(SHORTCUT_PATH)
        elif main_event == 'save_queue_sessions':
            if main_value: save_queues()
            else: change_settings('queues', {'done': [], 'music': [], 'next': []})
            change_settings('populate_queue_startup', False)
            main_window['populate_queue_startup'].Update(value=False)
        elif main_event in 'populate_queue_startup':
            main_window['save_queue_sessions'].Update(value=False)
            change_settings('save_queue_sessions', False)
        elif main_event == 'discord_rpc':
            with suppress(AttributeError, RuntimeError, pypresence.PyPresenceException):
                if main_value and playing_status in {'PAUSED', 'PLAYING'}:
                    title, artist = get_metadata_wrapped(music_queue[0])[:2]
                    rich_presence.connect()
                    rich_presence.update(state=f'By: {artist}', details=title, large_image='default',
                                         large_text='Listening', small_image='logo', small_text='Music Caster')
                elif not main_value: rich_presence.clear()
    elif main_event == 'remove_folder' and main_values['music_dirs']:
        selected_item = main_values['music_dirs'][0]
        if selected_item in music_directories:
            music_directories.remove(selected_item)
            main_window['music_dirs'].Update(music_directories)
            refresh_tray()
            save_settings()
            compile_all_songs()
    elif main_event == 'add_folder':
        if main_value not in music_directories and os.path.exists(main_value):
            music_directories.append(main_value)
            main_window['music_dirs'].Update(music_directories)
            refresh_tray()
            save_settings()
            compile_all_songs()
    elif main_event in {'settings_file', 'o:79'}:
        try: os.startfile(settings_file)
        except OSError: Popen(f'explorer /select,"{fix_path(settings_file)}"')
    elif main_event == 'music_dirs':
        with suppress(IndexError):
            Popen(f'explorer "{fix_path(main_values["music_dirs"][0])}"')
    # timer
    elif main_event == 'cancel_timer':
        main_window['timer_text'].Update(value='No Timer Set')
        main_window['timer_error'].Update(visible=False)
        main_window['cancel_timer'].Update(visible=False)
    elif (main_event in {'\r', 'special 16777220', 'special 16777221', 'timer_submit'}
          and main_values['tab_group'] == 'tab_timer'):
        try:
            timer_value = main_values['minutes']
            if timer_value.isdigit():
                seconds = abs(float(main_values['minutes'])) * 60
            elif timer_value.count(':') == 1:
                if timer_value[-3:].strip().upper() in ('PM', 'AM'):
                    timer_value = timer_value[timer_value:-3]
                elif timer_value[-2:].upper() in ('PM', 'AM'):
                    timer_value = timer_value[timer_value:-2]
                to_stop = datetime.strptime(timer_value + time.strftime(',%Y,%m,%d,%p'), '%I:%M,%Y,%m,%d,%p')
                seconds_delta = (to_stop - datetime.now()).total_seconds()
                if seconds_delta < 0: seconds_delta += 43200
                seconds = seconds_delta
            else:
                raise ValueError()
            timer = time.time() + seconds
            timer_set_to = datetime.now() + timedelta(minutes=seconds // 60)
            if platform.system() == 'Windows': timer_set_to = timer_set_to.strftime('%#I:%M %p')
            else: timer_set_to = timer_set_to.strftime('%-I:%M %p')  # Linux
            main_window['timer_text'].Update(value=f'Timer set for {timer_set_to}')
            main_window['cancel_timer'].Update(visible=True)
        except ValueError:
            for i in range(3):
                main_window['timer_error'].Update(visible=True, text_color='#ffcccb')
                main_window.Refresh()
                main_window['timer_error'].Update(text_color='red')
                main_window.Refresh()
    elif main_event in {'shut_off', 'hibernate', 'sleep', 'do_nothing'}:
        change_settings('timer_hibernate_computer', main_values['hibernate'])
        change_settings('timer_sleep_computer', main_values['sleep'])
        change_settings('timer_shut_off_computer', main_values['shut_off'])

    if playing_status in {'PLAYING', 'PAUSED'} and time.time() - progress_bar_last_update > 1:
        if music_queue:
            progress_bar = main_window['progressbar']
            with suppress(ZeroDivisionError):
                update_song_position()
                progress_bar.Update(song_position / song_length * 100, disabled=False)
            time_left = song_length - song_position
            progress_bar_last_update = time.time() - song_position + int(song_position)
        else:
            playing_status = 'NOT PLAYING'
    if time_left is not None:
        mins_elapsed, mins_left = floor(song_position / 60), floor(time_left / 60)
        secs_elapsed, secs_left = floor(song_position % 60), floor(time_left % 60)
        if secs_left < 10: secs_left = f'0{secs_left}'
        if secs_elapsed < 10: secs_elapsed = f'0{secs_elapsed}'
        main_window['time_elapsed'].Update(value=f'{mins_elapsed}:{secs_elapsed}')
        main_window['time_left'].Update(value=f'{mins_left}:{secs_left}')
        # metadata = music_meta_data[music_queue[0]]
        # main_window['album_cover'].Update(data=metadata['album_cover_data'])
    lb_music_queue: Sg.Listbox = main_window['queue']
    dq_len = len(done_queue)
    update_lb_mq = len(lb_music_queue.get_list_values()) != len(music_queue) + len(next_queue) + dq_len
    if playing_status == 'PLAYING' and p_r_button.metadata != 'PLAYING':
        p_r_button.Update(image_data=PAUSE_BUTTON_IMG)
    elif playing_status == 'PAUSED' and p_r_button.metadata != 'PAUSED':
        p_r_button.Update(image_data=PLAY_BUTTON_IMG)
    elif playing_status == 'NOT PLAYING' and p_r_button.metadata != 'NOT PLAYING':
        if p_r_button.metadata == 'PLAYING': p_r_button.Update(image_data=PLAY_BUTTON_IMG)
        main_window['time_elapsed'].Update(value='00:00')
        main_window['time_left'].Update(value='00:00')
    p_r_button.metadata = playing_status
    if gui_title != title:
        main_window['title'].Update(value=title)
        main_window['artist'].Update(value=artist)
        update_lb_mq = True
    if update_lb_mq:
        lb_music_queue_songs = create_songs_list()[0]
        lb_music_queue.Update(values=lb_music_queue_songs, set_to_index=dq_len, scroll_to_index=dq_len)
    return True


def read_playlist_selector_window():
    global pl_selector_window, tray_playlists, pl_files, pl_name, pl_editor_window
    pl_selector_event, pl_selector_values = pl_selector_window.Read(timeout=10)
    if pl_selector_event in {None, 'Escape:27', 'q'}:
        active_windows['playlist_selector'] = False
        pl_selector_window.Close()
        return
    if pl_selector_event in {'del_pl', 'Delete:46'}:
        pl_name = pl_selector_values.get('playlist_combo', '')
        if pl_name in playlists:
            del playlists[pl_name]
            save_settings()
        playlist_names = tuple(settings['playlists'].keys())
        default_playlist_name = playlist_names[0] if playlist_names else ''
        pl_selector_window['playlist_combo'].Update(value=default_playlist_name, values=playlist_names)
        pl_selector_window.Refresh()
        if active_windows['main']:
            main_window['playlists'].Update(value=default_playlist_name, values=playlist_names)
        tray_playlists.clear()
        tray_playlists.append('Create/Edit a Playlist')
        tray_playlists += [f'PL: {pl}' for pl in playlists.keys()]
    elif pl_selector_event in {'edit_pl', 'create_pl', 'e', 'n', 'e:69', 'n:78'}:
        if pl_selector_event in {'edit_pl', 'e', 'e:69'}:
            pl_name = pl_selector_values.get('playlist_combo', '')
        else:
            pl_name = ''
        window_location = get_window_location('playlist_editor')
        pl_editor_window = Sg.Window('Playlist Editor', create_playlist_editor(settings, pl_name),
                                     background_color=settings['background_color'], icon=WINDOW_ICON,
                                     return_keyboard_events=True, location=window_location)
        pl_files = playlists.get(pl_name, [])
        pl_selector_window.Close()
        pl_editor_window.Finalize()
        pl_editor_window.TKroot.focus_force()
        pl_editor_window.Normal()
        set_save_position_callback(pl_editor_window, 'playlist_editor')
        if pl_name == '': pl_editor_window['playlist_name'].SetFocus()
        else:
            pl_editor_window['tracks'].SetFocus()
            pl_editor_window['tracks'].Update(set_to_index=0)
        active_windows['playlist_editor'], active_windows['playlist_selector'] = True, False
    elif pl_selector_event in {'Up:38', 'Down:40'}:
        with suppress(KeyError, IndexError, ValueError):
            pl_selector_combo = pl_selector_window['playlist_combo']
            pl_index = pl_selector_combo.Values.index(pl_selector_values['playlist_combo'])
            new_index = max(pl_index + {'Up:38': -1, 'Down:40': 1}[pl_selector_event], 0)
            pl_selector_combo.Update(value=pl_selector_combo.Values[new_index])


def read_playlist_editor_window():
    global pl_files, pl_editor_last_event, pl_name, tray_playlists, pl_selector_window
    pl_editor_event, pl_editor_values = pl_editor_window.Read(timeout=10)
    open_pl_selector = False
    if pl_editor_event == '__TIMEOUT__': pass
    elif pl_editor_event in {None, 'Escape:27', 'Cancel'} and pl_editor_last_event not in {'Add tracks', 'f:70'}:
        active_windows['playlist_editor'] = False
        pl_editor_window.Close()
        open_pl_selector = True
    elif pl_editor_event in {'Save', 's:83'}:
        new_name = pl_editor_values['playlist_name']
        pl_files = pl_files.copy()
        if pl_name != new_name:
            if pl_name in playlists: del playlists[pl_name]
            pl_name = new_name
        playlists[pl_name] = pl_files
        if active_windows['main']:
            playlist_names = tuple(playlists.keys())
            main_window['playlists'].Update(value=playlist_names[0], values=playlist_names)
        save_settings()
        active_windows['playlist_editor'] = False
        pl_editor_window.Close()
        open_pl_selector = True
        tray_playlists.clear()
        tray_playlists.append('Create/Edit a Playlist')
        tray_playlists += [f'PL: {pl}' for pl in playlists.keys()]
    elif pl_editor_event in {'move_up', 'u:85'}:  # u:85 is Ctrl + U
        if pl_editor_values['tracks']:
            to_move = pl_editor_window['tracks'].GetListValues().index(pl_editor_values['tracks'][0])
            if to_move > 0:
                new_i = to_move - 1
                pl_files.insert(new_i, pl_files.pop(to_move))
                formatted_songs = [f'{i + 1}. {os.path.basename(path)}' for i, path in enumerate(pl_files)]
                pl_editor_window['tracks'].Update(values=formatted_songs, set_to_index=new_i,
                                                  scroll_to_index=new_i)
    elif pl_editor_event in {'move_down', 'd:68'}:  # d:68 is Ctrl + D
        if pl_editor_values['tracks']:
            to_move = pl_editor_window['tracks'].GetListValues().index(pl_editor_values['tracks'][0])
            if to_move < len(pl_files) - 1:
                new_i = to_move + 1
                pl_files.insert(new_i, pl_files.pop(to_move))
                formatted_songs = [f'{i + 1}. {os.path.basename(path)}' for i, path in enumerate(pl_files)]
                pl_editor_window['tracks'].Update(values=formatted_songs, set_to_index=new_i,
                                                  scroll_to_index=new_i)
    elif pl_editor_event in {'Add tracks', 'f:70'}:
        fd = wx.FileDialog(None, 'Select Music File(s)', defaultDir=DEFAULT_DIR, wildcard=MUSIC_FILE_TYPES,
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE)
        if fd.ShowModal() != wx.ID_CANCEL:
            file_paths = fd.GetPaths()
            pl_files += [file_path for file_path in file_paths if valid_music_file(file_path)]
            pl_editor_window.TKroot.focus_force()
            pl_editor_window.Normal()
            formatted_songs = [f'{i + 1}. {os.path.basename(path)}' for i, path in enumerate(pl_files)]
            new_i = len(formatted_songs) - 1  # - len(new_files)
            pl_editor_window['tracks'].Update(formatted_songs, set_to_index=new_i, scroll_to_index=new_i)
    elif pl_editor_event in {'Remove track', 'r:82'}:  # r:82 is Ctrl + R
        if pl_editor_values['tracks']:
            index_to_rm = pl_editor_window['tracks'].GetListValues().index(pl_editor_values['tracks'][0])
            with suppress(ValueError): pl_files.pop(index_to_rm)
            formatted_songs = [f'{i + 1}. {os.path.basename(path)}' for i, path in enumerate(pl_files)]
            new_i = max(index_to_rm - 1, 0)
            pl_editor_window['tracks'].Update(formatted_songs, set_to_index=new_i, scroll_to_index=new_i)
    elif pl_editor_event in {'Up:38', 'Down:40', 'Prior:33', 'Next:34'} and pl_editor_values['tracks']:
        move = {'Up:38': -1, 'Down:40': 1, 'Prior:33': -3, 'Next:34': 3}[pl_editor_event]
        new_i = pl_editor_window['tracks'].GetListValues().index(pl_editor_values['tracks'][0]) + move
        new_i = min(max(new_i, 0), len(pl_files) - 1)
        pl_editor_window['tracks'].Update(set_to_index=new_i, scroll_to_index=new_i)
    if open_pl_selector:
        active_windows['playlist_selector'] = True
        window_location = get_window_location('playlist_selector')
        pl_selector_window = Sg.Window('Playlist Selector', create_playlist_selector(settings),
                                       background_color=settings['background_color'], icon=WINDOW_ICON,
                                       return_keyboard_events=True, location=window_location)
        pl_selector_window.Finalize()
        pl_selector_window.TKroot.focus_force()
        pl_selector_window.Normal()
        set_save_position_callback(pl_selector_window, 'playlist_selector')
    pl_editor_last_event = pl_editor_event


def read_play_url_window():
    play_url_event, play_url_values = play_url_window.Read(timeout=10)
    if play_url_event in {None, 'Escape:27', 'q'}:
        active_windows['play_url'] = False
        play_url_window.Close()
    elif play_url_event in {'\r', 'special 16777220', 'special 16777221', 'Submit'}:
        active_windows['play_url'] = False
        play_url_window.Close()
        url_to_play = play_url_values['url']
        if play_url_values['combo_choice'] == 'Play Immediately' or not music_queue and not next_queue:
            music_queue.insert(0, url_to_play)
            play(url_to_play)
        elif play_url_values['combo_choice'] == 'Queue':
            music_queue.append(url_to_play)
            if len(music_queue) == 1: play(url_to_play)
        else: next_queue.append(url_to_play)  # Add to Next Queue


def create_shortcut(_shortcut_path):
    def _threaded():
        try:
            shortcut_exists = os.path.exists(_shortcut_path)
            if settings['run_on_startup'] and not shortcut_exists:
                # noinspection PyUnresolvedReferences
                pythoncom.CoInitialize()
                shell = win32com.client.Dispatch('WScript.Shell')
                shortcut = shell.CreateShortCut(_shortcut_path)
                if IS_FROZEN:
                    target = f'{starting_dir}\\Music Caster.exe'
                else:
                    bat_file = f'{starting_dir}\\music_caster.bat'
                    if os.path.exists(bat_file):
                        with open('music_caster.bat', 'w') as _f:
                            _f.write(f'pythonw {os.path.basename(sys.argv[0])}')
                    target = bat_file
                    shortcut.IconLocation = f'{starting_dir}\\icon.ico'
                shortcut.Targetpath = target
                shortcut.WorkingDirectory = starting_dir
                shortcut.WindowStyle = 1  # 7 - Minimized, 3 - Maximized, 1 - Normal
                shortcut.save()
            elif not settings['run_on_startup'] and shortcut_exists:
                os.remove(_shortcut_path)
        except Exception as _e:
            handle_exception(_e)
    if IS_FROZEN and not DEBUG: Thread(target=_threaded, daemon=True).start()


def auto_update():
    global update_available
    try:
        if not settings['auto_update'] and not DEBUG and IS_FROZEN: return
        releases_url = 'https://api.github.com/repos/elibroftw/music-caster/releases/latest'
        release = requests.get(releases_url).json()
        latest_ver = release['tag_name'][1:]
        _version = [int(x) for x in VERSION.split('.')]
        compare_ver = [int(x) for x in latest_ver.split('.')]
        if compare_ver > _version or not IS_FROZEN or DEBUG:
            setup_dl_link = ''
            for asset in release['assets']:
                if 'exe' in asset['name']:
                    setup_dl_link = asset['browser_download_url']
                    break
            print('Installer Link:', setup_dl_link)
            if not IS_FROZEN or DEBUG or not setup_dl_link: return
            if IS_FROZEN and (os.path.exists(UNINSTALLER) or os.path.exists('Updater.exe')):
                if os.path.exists(UNINSTALLER):
                    temp_tray = SgWx.SystemTray(menu=[], data_base64=UNFILLED_ICON)
                    temp_tray.ShowMessage('Music Caster', f'Downloading update v{latest_ver}')
                    temp_tray.Update(tooltip=f'Downloading update v{latest_ver}')
                    download(setup_dl_link, 'MC_Installer.exe')
                    temp_tray.Hide()
                    temp_tray.Close()
                    Popen(f'MC_Installer.exe /VERYSILENT /FORCECLOSEAPPLICATIONS /MERGETASKS="!desktopicon"')
                else:
                    os.startfile('Updater.exe')
                    time.sleep(2)
                sys.exit()
            else:
                update_available = f'Update v{latest_ver} is available'
    except requests.ConnectionError: pass
    except Exception as _e: handle_exception(_e)


def send_info():
    with suppress(requests.exceptions.ConnectionError):
        requests.post('https://en3ay96poz86qa9.m.pipedream.net', json={'MAC': get_mac(), 'VERSION': VERSION})


def init_youtube_dl():  # 1 - 1.4 seconds
    global ydl
    ydl = YoutubeDL()


def init_pygame():  # 1 - 1.4 seconds
    global show_pygame_error
    try: local_music_player.init(44100, -16, 2, 2048)
    except pygame_error: show_pygame_error = True


def quit_if_running():
    if is_already_running() or DEBUG:
        print('Another instance of Music Caster was found' if not DEBUG else '')
        r_text = ''
        port = PORT
        while port <= 2003 and not r_text:
            with suppress(requests.exceptions.InvalidSchema, requests.exceptions.ConnectionError):
                if args.path:  # a file was opened with MC
                    r_text = requests.post(f'http://127.0.0.1:{port}/play/', data={'path': args.path}).text
                else: r_text = requests.post(f'http://127.0.0.1:{port}/').text
            port += 1
        if IS_FROZEN and not DEBUG: sys.exit()


quit_if_running()
load_settings()
init_ydl_thread = Thread(target=init_youtube_dl, daemon=True)
init_ydl_thread.start()
init_pygame_thread = Thread(target=init_pygame, daemon=True)
init_pygame_thread.start()
auto_update()
if IS_FROZEN and not DEBUG: Thread(target=send_info, daemon=True).start()
# Access startup folder by entering "Startup" in Explorer address bar
SHORTCUT_PATH = f'{winshell.startup()}\\Music Caster.lnk'
create_shortcut(SHORTCUT_PATH)
with suppress(FileExistsError): os.mkdir(thumbs_dir)
with suppress(FileNotFoundError, OSError): os.remove('MC_Installer.exe')
shutil.rmtree('Update', ignore_errors=True)
try:
    # TODO: Set as default music file handler (See MODIFY REGISTRY in helpers.py)
    for img in glob(f'{thumbs_dir}/*.*'):
        if not img.endswith('default.png'): os.remove(img)
    if not os.path.exists(f'{thumbs_dir}/default.png'):  # in case the user decided to delete the default image
        if os.path.exists('resources/default.png'):  # running from source code
            copyfile('resources/default.png', 'images/default.png')
        else:  # download the default image
            with suppress(requests.ConnectionError):
                default_img = 'https://raw.githubusercontent.com/elibroftw/music-caster/master/resources/default.png'
                response = requests.get(default_img, stream=True)
                with open(f'{thumbs_dir}/default.png', 'wb') as f: copyfileobj(response.raw, f)
    with open(f'{thumbs_dir}/default.png', 'rb') as f: DEFAULT_IMG_DATA = base64.b64encode(f.read()).decode()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.05)
        while True:
            if not s.connect_ex(('localhost', PORT)) == 0:  # if port is not occupied
                try:  # start server with the unoccupied PORT
                    server_kwargs = {'host': '0.0.0.0', 'port': PORT, 'threaded': True}
                    Thread(target=app.run, daemon=True, kwargs=server_kwargs).start()
                    break
                except OSError: PORT += 1
            else: PORT += 1
    repeat_menu = ['Repeat All ✓' if settings['repeat'] is False else 'Repeat All',
                   'Repeat One ✓' if settings['repeat'] else 'Repeat One',
                   'Repeat Off ✓' if settings['repeat'] is None else 'Repeat Off']

    menu_def_1 = ['', ['Settings', 'Refresh Library', 'Refresh Devices', 'Select Device', device_names,
                       'Timer', ['Set Timer', 'Cancel Timer'], 'Play',
                       ['Play URL', 'Folders', tray_folders, 'Playlists', tray_playlists,
                        'Play File(s)', 'Play All'], 'Exit']]
    menu_def_2 = ['', ['Settings', 'Refresh Library', 'Refresh Devices', 'Select Device', device_names,
                       'Timer', ['Set Timer', 'Cancel Timer'], 'Controls',
                       ['Locate File', 'Repeat Options', repeat_menu, 'Stop', 'Previous Song', 'Next Song',
                        'Pause'], 'Play',
                       ['Play URL', 'Folders', tray_folders, 'Playlists', tray_playlists, 'Play File(s)',
                        'Play File Next', 'Play All'], 'Exit']]
    menu_def_3 = ['', ['Settings', 'Refresh Library', 'Refresh Devices', 'Select Device', device_names,
                       'Timer', ['Set Timer', 'Cancel Timer'], 'Controls',
                       ['Locate File', 'Repeat Options', repeat_menu, 'Stop', 'Previous Song', 'Next Song',
                        'Resume'], 'Play',
                       ['Play URL', 'Folders', tray_folders, 'Playlists', tray_playlists, 'Play File(s)',
                        'Play File Next', 'Play All'], 'Exit']]
    IPV4 = get_ipv4()
    QR_CODE = create_qr_code(PORT)
    rich_presence = pypresence.Presence(MUSIC_CASTER_DISCORD_ID)
    with suppress(RuntimeError, pypresence.PyPresenceException): rich_presence.connect()
    pynput.keyboard.Listener(on_press=on_press, on_release=on_release).start()  # daemon=True by default
    init_pygame_thread.join()
    init_ydl_thread.join()
    tooltip = 'Music Caster [DEBUG]' if (DEBUG or not IS_FROZEN) else 'Music Caster'
    tray = SgWx.SystemTray(menu=menu_def_1, data_base64=UNFILLED_ICON, tooltip=tooltip)
    if not music_directories:
        music_directories = change_settings('music_directories', [home_music_dir])
        compile_all_songs()
    DEFAULT_DIR = music_directories[0]
    if settings['notifications']:
        if show_pygame_error:
            tray.ShowMessage('Music Caster Error', 'No local audio device found')
        if settings['update_message'] != UPDATE_MESSAGE:
            tray.ShowMessage('Music Caster Updated', UPDATE_MESSAGE)
    if update_available:
        tray.ShowMessage('Music Caster', update_available)
    change_settings('update_message', UPDATE_MESSAGE)
    temp = (settings['timer_shut_off_computer'], settings['timer_hibernate_computer'], settings['timer_sleep_computer'])
    if temp.count(True) > 1:  # Only one of the below can be True
        if settings['timer_shut_off_computer']: change_settings('timer_hibernate_computer', False)
        change_settings('timer_sleep_computer', False)
    if settings['save_queue_sessions'] and settings['populate_queue_startup']:  # mutually exclusive
        change_settings('populate_queue_startup', False)
    cast_last_checked = time.time()
    Thread(target=background_tasks, daemon=True).start()
    Thread(target=start_chromecast_discovery, daemon=True).start()
    if args.path is not None:
        if os.path.isfile(args.path): play(args.path)
        elif os.path.isdir(args.path): play_folder([args.path])
    elif settings['save_queue_sessions']:
        queues = settings['queues']
        done_queue.extend(queues.get('done', []))
        music_queue.extend(queues.get('music', []))
        next_queue.extend(queues.get('next', []))
    elif settings['populate_queue_startup']:
        compiling_songs_thread.join()
        play_all(queue_only=True)
    print('Running in tray')
    pause_resume = {'PAUSED': resume, 'PLAYING': pause}
    tray_actions = {
        '__ACTIVATED__': activate_main_window,
        'Refresh Library': compile_all_songs,
        'Refresh Devices': lambda: Thread(target=start_chromecast_discovery, daemon=True),
        # isdigit should be an if statement
        'Settings': lambda: activate_main_window('tab_settings'),
        'Create/Edit a Playlist': create_edit_playlists,
        # PL should be an if statement
        'Set Timer': lambda: activate_main_window('tab_timer'),
        'Cancel Timer': cancel_timer,
        'Play URL': activate_play_url,
        'Play File(s)': lambda: Thread(target=play_file).start(),
        'Play All': play_all,
        'Play File Next': lambda: Thread(target=play_next).start(),
        'Pause': pause,
        'Resume': resume,
        'Next Song': next_song_command,
        'Previous Song': previous_song,
        'Stop': stop,
        'web_play_files': lambda: 'pass',
        'Repeat One': lambda: change_settings('repeat', True),
        'Repeat All': lambda: change_settings('repeat', False),
        'Repeat Off': lambda: change_settings('repeat', None),
        'Locate File': locate_file,
        'Exit': exit_program,
    }
    while True:
        tray_item = tray.Read(timeout=30 if any(active_windows.values()) else 100)
        if daemon_command is not None:
            tray_actions.get(daemon_command, do_nothing)()
            daemon_command = None
        tray_actions.get(tray_item, lambda: other_tray_actions(tray_item))()
        if active_windows['main']: read_main_window()
        if active_windows['playlist_selector']: read_playlist_selector_window()
        if active_windows['playlist_editor']: read_playlist_editor_window()
        if active_windows['play_url']: read_play_url_window()
except Exception as e:
    handle_exception(e, True)
