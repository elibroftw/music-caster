VERSION = latest_version = '4.74.5'
UPDATE_MESSAGE = """
[Important] You will need to re-add your music folders
[Feature] Album Title
[Optimized] Metadata scanning
""".strip()
if __name__ != '__main__': raise RuntimeError(VERSION)  # hack
import argparse

parser = argparse.ArgumentParser(description='Music Caster')
parser.add_argument('--debug', '-d', default=False, action='store_true', help='allows > 1 instance + no info sent')
parser.add_argument('--queue', '-q', default=False, action='store_true', help='supplied paths are queued')
parser.add_argument('--update', '-u', default=False, action='store_true', help='allow updating')
parser.add_argument('--exit', '-x', default=False, action='store_true',
                    help='exits any existing instance (including self)')
parser.add_argument('paths', nargs='*', default=[], help='list of files/dirs/playlists to play/queue')
args = parser.parse_args()
from helpers import *
from audio_player import AudioPlayer
import base64

from contextlib import suppress
from datetime import datetime, timedelta
import errno
# noinspection PyUnresolvedReferences
import encodings.idna  # DO NOT REMOVE
from functools import cmp_to_key
import glob
import hashlib
import io
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import pprint
from queue import Queue
from random import shuffle
from shutil import copyfileobj, rmtree
import sys
from threading import Thread
from win32com.universal import com_error
import traceback
import urllib.parse
from urllib.parse import urlsplit
import webbrowser  # takes 0.05 seconds
import zipfile
# 3rd party imports
from flask import Flask, jsonify, render_template, request, redirect, send_file, Response
from werkzeug.exceptions import InternalServerError
import PySimpleGUIWx as SgWx
import pyaudio
import wx
# import wx.lib.agw.multidirdialog as mdd
import pychromecast.controllers.media
from pychromecast.error import UnsupportedNamespace, NotConnected
from pychromecast.config import APP_MEDIA_RECEIVER
from pychromecast import Chromecast
import pynput.keyboard
import pyperclip
import pypresence
import threading
import pythoncom
from PIL import UnidentifiedImageError
import requests
import win32com.client
from win32comext.shell import shell, shellcon
from youtube_dl import YoutubeDL
from youtube_dl.utils import DownloadError

music_file_exts = ('mp3', 'mp4', 'mpeg', 'm4a', 'flac', 'aac', 'ogg', 'opus', 'wma', 'wav')
MUSIC_FILE_TYPES = 'Audio File (.' + ', .'.join(music_file_exts) + ')|*.' + ';*.'.join(music_file_exts)
DEBUG = args.debug
main_window = timer_window = play_url_window = Sg.Window('')
working_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
os.chdir(working_dir)
EMAIL = 'elijahllopezz@gmail.com'
MUSIC_CASTER_DISCORD_ID = '696092874902863932'
UNINSTALLER = 'unins000.exe'
PORT, WAIT_TIMEOUT, IS_FROZEN = 2001, 15, getattr(sys, 'frozen', False)
STREAM_CHUNK = 1024
PRESSED_KEYS = set()
update_devices = settings_file_in_use = False
update_available = exit_flag = False
last_play_command = 0  # last call to /play/
settings_last_modified, last_press = 0, time.time() + 5
update_last_checked = time.time()  # check every hour
active_windows = {'main': False, 'play_url': False}

main_last_event = None
# noinspection PyTypeChecker
cast: Chromecast = None
playlists, all_tracks, url_metadata = {}, {}, {}
all_tracks_sorted_filename = []
all_tracks_sorted_sort_key = []
# playlist_name: [], formatted_name: file path, file: {artist: str, title: str}
tray_playlists, tray_folders = ['Create/Edit a Playlist'], []
pl_name = ''
pl_files = []  # keep track of paths when editing playlists
CHECK_MARK = '✓'
chromecasts, device_names = [], [f'{CHECK_MARK} Local device']
music_folders = []
music_queue, done_queue, next_queue = [], [], []
update_gui_queue = update_volume_slider = False
mouse_hover = ''
daemon_commands = Queue()
files_to_scan = Queue()
# files_to_scan is read by the background tasks thread in order to scan unread files in the queue
playing_url = playing_live = False
live_lag = 0.0
progress_bar_last_update = track_position = timer = track_end = track_length = track_start = 0
# seconds but using time()
playing_status = 'NOT PLAYING'  # or PLAYING or PAUSED
# if music caster was launched in some other folder, play all or queue all that folder?
DEFAULT_FOLDER = home_music_folder = f'{Path.home()}/Music'.replace('\\', '/')
settings_file = f'{working_dir}/settings.json'

DEFAULT_THEME = {'accent': '#00bfff', 'background': '#121212', 'text': '#d7d7d7', 'alternate_background': '#222222'}
settings = {  # default settings
    'previous_device': None, 'window_locations': {}, 'update_message': '', 'EXPERIMENTAL': False,
    'auto_update': True, 'run_on_startup': True, 'notifications': True, 'shuffle': False, 'repeat': None,
    'discord_rpc': False, 'save_window_positions': True, 'populate_queue_startup': False, 'save_queue_sessions': False,
    'volume': 100, 'muted': False, 'volume_delta': 5, 'scrubbing_delta': 5, 'flip_main_window': False,
    'show_track_number': False, 'folder_cover_override': False, 'show_album_art': True, 'folder_context_menu': True,
    'vertical_gui': False, 'mini_mode': False, 'mini_on_top': True, 'scan_folders': True, 'update_check_hours': 1,
    'timer_shut_down': False, 'timer_hibernate': False, 'timer_sleep': False,
    'theme': DEFAULT_THEME.copy(), 'track_format': '&artist - &title', 'reversed_play_next': False,
    'music_folders': [home_music_folder], 'playlists': {}, 'queues': {'done': [], 'music': [], 'next': []}}
# noinspection PyTypeChecker
indexing_tracks_thread: Thread = None
# noinspection PyTypeChecker
save_queue_thread: Thread = None
# noinspection PyTypeChecker
ydl: YoutubeDL = None
app = Flask(__name__)
app.jinja_env.lstrip_blocks = True
app.jinja_env.trim_blocks = True
logging.getLogger('werkzeug').disabled = True
os.environ['WERKZEUG_RUN_MAIN'] = 'true'
stop_discovery = lambda: None  # this is for the chromecast discover function


def save_settings():
    global settings, settings_file, settings_file_in_use
    if not settings_file_in_use:
        settings_file_in_use = True
        with open(settings_file, 'w') as outfile:
            json.dump(settings, outfile, indent=4)
        settings_file_in_use = False


def refresh_folders():
    tray_folders.clear()
    tray_folders.append('Select Folder(s)::PF')
    for folder in settings['music_folders']:
        folder = folder.replace('\\', '/').split('/')
        folder = f'../{"/".join(folder[-2:])}::PF' if len(folder) > 2 else ('/'.join(folder) + '::PF')
        tray_folders.append(folder)


def refresh_playlists():
    tray_playlists.clear()
    tray_playlists.append('Create/Edit a Playlist')
    tray_playlists.extend([f'{pl}::PL'.replace('&', '&&&') for pl in settings['playlists'].keys()])


def refresh_tray():
    refresh_folders()
    refresh_playlists()
    tray.update(menu={'PLAYING': tray_menu_playing, 'PAUSED': tray_menu_paused}.get(playing_status, tray_menu_default))


def change_settings(settings_key, new_value):
    """ can be called from non-main thread """
    global settings, active_windows, tray
    if settings[settings_key] != new_value:
        settings[settings_key] = new_value
        save_settings()
        if settings_key == 'repeat':
            repeat_menu[0] = f'Repeat All {CHECK_MARK}' if new_value is False else 'Repeat All'
            repeat_menu[1] = f'Repeat One {CHECK_MARK}' if new_value else 'Repeat One'
            repeat_menu[2] = f'Repeat Off {CHECK_MARK}' if new_value is None else 'Repeat Off'
            refresh_tray()
            if settings['notifications']:
                msg = {None: 'Repeat set to Off', True: 'Repeat set to One', False: 'Repeat set to All'}[new_value]
                tray.show_message('Music Caster', msg, time=5000)
    return new_value


def save_queues():
    global save_queue_thread, settings

    def _save_queue():
        settings['queues']['done'] = done_queue
        settings['queues']['music'] = music_queue
        settings['queues']['next'] = next_queue
        save_settings()

    if save_queue_thread is None or not save_queue_thread.is_alive():
        save_queue_thread = Thread(target=_save_queue, name='SaveQueue')
        save_queue_thread.start()


def update_volume(new_vol):
    """new_vol: float[0, 100]"""
    if active_windows['main']: main_window['volume_slider'].update(value=new_vol)
    new_vol = new_vol / 100
    audio_player.set_volume(new_vol)
    if cast is not None:
        with suppress(NotConnected): cast.set_volume(new_vol)


def update_repeat_button():
    """ updates repeat button of main window """
    repeat_value = settings['repeat']
    repeat_button: Sg.Button = main_window['repeat']
    if repeat_value is None:
        repeat_img = REPEAT_OFF_IMG
        new_tooltip = 'Repeat'
    elif repeat_value:
        repeat_img = REPEAT_ONE_IMG
        new_tooltip = "Don't repeat"
    else:
        repeat_img = REPEAT_ALL_IMG
        new_tooltip = 'Repeat track'
    repeat_button.metadata = repeat_value
    repeat_button.update(image_data=repeat_img)
    repeat_button.set_tooltip(new_tooltip)


def cycle_repeat(update_main=False):
    """
    :param update_main: Only set to True on main Thread
    :return: new repeat value
    """
    # Repeat Off (None) becomes All (False) becomes One (True) becomes Off
    new_repeat_setting = {None: False, True: None, False: True}[settings['repeat']]
    if update_main and active_windows['main']: update_repeat_button()  # update main window if it is active
    return change_settings('repeat', new_repeat_setting)


def create_email_url():
    try:
        with open('music_caster.log') as f:
            log_lines = f.read().splitlines()[-10:]  # get last 10 lines of the log
    except FileNotFoundError:
        log_lines = []
    log_lines = '%0D%0A'.join(log_lines)
    email_body = f'body=%0D%0A%23%20Last%20Few%20Lines%20of%20the%20Log%0D%0A%0D%0A{log_lines}'
    mail_to = f'mailto:{EMAIL}?subject=Regarding%20Music%20Caster%20v{VERSION}&{email_body}'
    return mail_to


def handle_exception(exception, restart_program=False):
    current_time = str(datetime.now())
    trace_back_msg = traceback.format_exc()
    exc_type, exc_tb = sys.exc_info()[0], sys.exc_info()[2]
    playing_uri = 'url' if playing_url else ('file' if music_queue else 'none', 'live')[playing_live]
    try:
        with open('music_caster.log') as f:
            log_lines = f.read().splitlines()[-5:]  # get last 5 lines of the log
    except FileNotFoundError:
        log_lines = []
    payload = {'VERSION': VERSION, 'EXCEPTION TYPE': exc_type.__name__, 'LINE': exc_tb.tb_lineno,
               'PORTABLE': not os.path.exists(UNINSTALLER),
               'TRACEBACK': fix_path(trace_back_msg), 'MAC': hashlib.md5(get_mac().encode()).hexdigest(),
               'FATAL': restart_program, 'LOG': log_lines,
               'OS': platform.platform(), 'TIME': current_time, 'PLAYING_TYPE': playing_uri}
    try:
        with open('error.log', 'r') as _f:
            content = _f.read()
    except (FileNotFoundError, ValueError):
        content = ''
    with open(f'error.log', 'w') as _f:
        _f.write(pprint.pformat(payload))
        _f.write('\n')
        _f.write(content)
    if not IS_FROZEN: raise exception  # raise exception if running in script rather than executable
    change_settings('auto_update', True)  # turn auto update on so user will get the update down the line
    with suppress(requests.ConnectionError):
        requests.post('https://dc19f29a6822522162e00f0b4bee7632.m.pipedream.net', json=payload)
    if restart_program:
        with suppress(NameError):
            tray.show_message('Music Caster', 'An error occurred, restarting now', time=5000)
            with suppress(Exception): stop('error handling')
            time.sleep(5)
            if IS_FROZEN: os.startfile('Music Caster.exe')
            sys.exit()


def get_album_art(file_path: str) -> tuple:  # mime: str, data: str / (None, None)
    app_log.info('get_album_art called')
    folder = os.path.dirname(file_path)
    if settings['folder_cover_override']:
        for ext in ('png', 'jpg', 'jpeg'):
            folder_cover = os.path.join(folder, f'cover.{ext}')
            if os.path.exists(folder_cover):
                data = io.BytesIO()
                im = Image.open(folder_cover)
                im.save(data, format='png', quality=95)
                return ext, base64.b64encode(data.getvalue())
    tags = mutagen.File(file_path)
    if tags is not None:
        for tag in tags.keys():
            if 'APIC' in tag:
                return tags[tag].mime, base64.b64encode(tags[tag].data).decode()  # 'utf-8'
    return None, None


def get_current_album_art():
    if playing_live: return LIVE_AUDIO_ART
    art = None
    if playing_status != 'NOT PLAYING' and music_queue:
        uri = music_queue[0]
        if uri.startswith('http'):
            try:
                # use 'art_data' else download 'art' link and cache to 'art_data'
                if 'art_data' in url_metadata[uri]: return url_metadata[uri]['art_data']
                art_src = url_metadata[uri]['art']  # 'art' is a key to a value of a link
                url_metadata[uri]['art_data'] = art_data = base64.b64encode(requests.get(art_src).content)
                return art_data
            except KeyError:
                return DEFAULT_ART
        with suppress(MutagenError):
            art = get_album_art(uri)[1]  # get_album_art(uri)[1] can be None
    return DEFAULT_ART if art is None else art


def get_metadata_wrapped(file_path: str) -> dict:  # keys: title, artist, album, sort_key
    try:
        return get_metadata(file_path)
    except mutagen.MutagenError:
        try:
            metadata = all_tracks[file_path]
            return metadata
        except KeyError:
            return {'title': 'Unknown Title', 'artist': 'Unknown Artist',
                    'album': 'Unknown Album', 'sort_key': 'Unknown - Unknown'}


def get_uri_metadata(uri, read_file=True):
    """
    get metadata from all_track and resort to url_metadata if not found in all_tracks
      if file/url is not in all_track. e.g. links
    if read_file is False, raise a KeyError instead of reading metadata from file.
    """
    uri = uri.replace('\\', '/')
    try:
        return all_tracks[uri]
    except KeyError:
        try:
            # if uri is a url
            return url_metadata[uri]
        except KeyError:
            # uri is probably a file that has not been cached yet
            if not read_file: raise KeyError
            metadata = get_metadata_wrapped(uri)
            if uri.startswith('http'): return metadata
            all_tracks[uri] = metadata
            return metadata


def get_current_metadata():
    if playing_live: return url_metadata['LIVE']
    if music_queue: return get_uri_metadata(music_queue[0])
    return {'artist': '', 'title': 'Nothing Playing', 'album': ''}


def index_all_tracks(update_global=True, ignore_files: list = None):
    """
    returns the music library dict if update_global is False
    starts scanning and building the music library/database if update_global is True
    ignore_files is a list (converted to set) of files to not include in the return value / scan
        usually used with update_global=False (think about it)
    """
    global indexing_tracks_thread, all_tracks
    if ignore_files is None: ignore_files = set()

    def _index_library():
        global all_tracks, update_gui_queue, all_tracks_sorted_sort_key, all_tracks_sorted_filename
        """
        Scans folders provided in settings and adds them to a dictionary
        Does not ignore the files that in ignore_files by design
        """
        use_temp = not not all_tracks  # use temp if all_tracks is not empty
        all_tracks_temp = {}
        for folder in music_folders:
            for file_path in glob.iglob(f'{glob.escape(folder)}/**/*.*', recursive=True):
                file_path = file_path.replace('\\', '/')
                if valid_music_file(file_path):
                    metadata = get_metadata_wrapped(file_path)
                    if use_temp:
                        all_tracks_temp[file_path] = metadata
                    else:
                        all_tracks[file_path] = metadata
        if use_temp: all_tracks = all_tracks_temp.copy()
        del all_tracks_temp
        all_tracks_sorted_sort_key = sorted(all_tracks.items(), key=lambda item: item[1]['sort_key'].lower())
        all_tracks_sorted_filename = sorted(all_tracks.items(), key=lambda item: item[0].lower())
        update_gui_queue = True

    if not update_global:
        temp_tracks = all_tracks.copy()
        for ignore_file in ignore_files: temp_tracks.pop(ignore_file, None)
        return temp_tracks
    if indexing_tracks_thread is None:
        indexing_tracks_thread = Thread(target=_index_library, daemon=True, name='IndexLibrary')
        indexing_tracks_thread.start()
    elif not indexing_tracks_thread.is_alive():  # force reindex
        indexing_tracks_thread = Thread(target=_index_library, daemon=True, name='IndexLibrary')
        indexing_tracks_thread.start()


def download(url, outfile):
    # throws ConnectionAbortedError
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
            settings['window_locations'][_key] = window.CurrentLocation()
            save_settings()

    window.TKroot.bind('<Destroy>', save_window_position)


def get_window_location(window_key):
    if not settings['save_window_positions']: window_key = 'DEFAULT'
    return settings['window_locations'].get(window_key, (None, None))


def load_settings():  # up to 0.4 seconds
    """load (and fix if needed) the settings file"""
    global settings, playlists, music_folders, settings_last_modified, settings_file_in_use, DEFAULT_FOLDER
    if settings_file_in_use:
        return
    elif os.path.exists(settings_file):
        settings_file_in_use = True
        with open(settings_file) as json_file:
            try:
                loaded_settings = json.load(json_file)
            except json.decoder.JSONDecodeError:
                loaded_settings = {}
            _save_settings = False
            for setting_name, setting_value in tuple(loaded_settings.items()):
                loaded_settings[setting_name.replace(' ', '_')] = loaded_settings.pop(setting_name)
            for setting_name, setting_value in settings.items():
                does_not_exist = setting_name not in loaded_settings
                if does_not_exist or isinstance(type(setting_value), type(loaded_settings[setting_name])):
                    loaded_settings[setting_name] = setting_value
                    _save_settings = True
                elif type(setting_value) == dict:
                    # for theme key
                    for k, v in setting_value.items():
                        if k not in loaded_settings[setting_name]:
                            loaded_settings[setting_name][k] = v
                            _save_settings = True
            settings = loaded_settings
            playlists = settings['playlists']
            refresh_playlists()
            _temp = music_folders.copy()
            music_folders = settings['music_folders']
            if _temp != music_folders:
                if settings['scan_folders']: index_all_tracks()
                refresh_folders()
            del _temp
            DEFAULT_FOLDER = music_folders[0] if music_folders else home_music_folder
            theme = settings['theme']
            for k, v in theme.copy().items():
                # validate settings file color codes
                if not valid_color_code(v):
                    _save_settings = True
                    theme[k] = DEFAULT_THEME[k]
            Sg.SetOptions(text_color=theme['text'], input_text_color=theme['text'], element_text_color=theme['text'],
                          background_color=theme['background'], text_element_background_color=theme['background'],
                          element_background_color=theme['background'], scrollbar_color=theme['background'],
                          input_elements_background_color=theme['background'], progress_meter_color=theme['accent'],
                          button_color=(theme['background'], theme['accent']),
                          border_width=1, slider_border_width=1, progress_meter_border_depth=0)
        settings_file_in_use = False
        if _save_settings: save_settings()
    else:
        save_settings()
        load_settings()
    settings_last_modified = os.path.getmtime(settings_file)


def human_readable_repeat():
    if settings['repeat'] is None:
        return 'off'
    elif settings['repeat']:
        return 'one'
    else:
        return 'all'


@app.errorhandler(404)
def page_not_found(_):
    return redirect('/')


# use socket io?
@app.route('/', methods=['GET', 'POST'])
def web_index():  # web GUI
    global music_queue, playing_status, all_tracks
    if request.method == 'POST':
        daemon_commands.put('Bring to Front')  # tells main loop to bring to front all GUI's
        return 'true' if any(active_windows.values()) else 'Music Caster'
    if request.args:
        api_msg = 'Invalid Command'
        if 'play' in request.args:
            if resume():
                api_msg = 'resumed playback'
            else:
                if music_queue:
                    play(music_queue[0])
                    api_msg = 'started playing first track in queue'
                else:
                    play_all()
                    api_msg = 'shuffled all and started playing'
        elif 'pause' in request.args:
            pause()  # resume == play
            api_msg = 'pause called'
        elif 'next' in request.args:
            next_track()
            api_msg = 'next track called'
        elif 'prev' in request.args:
            prev_track()
            api_msg = 'prev track called'
        elif 'repeat' in request.args:
            cycle_repeat()
            api_msg = 'cycled repeat to ' + human_readable_repeat()
        elif 'shuffle' in request.args:
            shuffle_option = change_settings('shuffle', not settings['shuffle'])
            api_msg = f'shuffle set to {shuffle_option}'
        if 'is_api' in request.args:
            return api_msg
        return redirect('/')
    metadata = get_current_metadata()
    art = get_current_album_art()
    if type(art) == bytes: art = art.decode()
    art = f'data:image/png;base64,{art}'
    repeat_option = settings['repeat']
    repeat_color = 'red' if settings['repeat'] is not None else ''
    shuffle_option = 'red' if settings['shuffle'] else ''
    # sort by the formatted title
    list_of_tracks = []
    if all_tracks_sorted_sort_key:
        sorted_tracks = all_tracks_sorted_sort_key
    else:
        sorted_tracks = sorted(all_tracks.items(), key=lambda item: item[1]['sort_key'].lower())

    for filename, data in sorted_tracks:
        filename = urllib.parse.urlencode({'path': filename})
        list_of_tracks.append({'title': data['sort_key'], 'href': f'/play?{filename}'})
    _queue = create_track_list()[0]
    device_index = 0
    for i, device_name in enumerate(device_names):
        if device_name.startswith(CHECK_MARK):
            device_index = i
            break
    formatted_devices = ['Local Device'] + [cc.name for cc in chromecasts]

    return render_template('index.html', device_name=platform.node(), shuffle=shuffle_option, repeat_color=repeat_color,
                           metadata=metadata, main_button='pause' if playing_status == 'PLAYING' else 'play', art=art,
                           settings=settings, list_of_tracks=list_of_tracks, repeat_option=repeat_option, queue=_queue,
                           device_index=device_index, devices=formatted_devices, version=VERSION)


@app.route('/play/', methods=['GET', 'POST'])
def api_play():
    global music_queue, playing_status, last_play_command
    from_explorer = time.time() - last_play_command < 0.5
    queue_only = request.values.get('queue', 'false').lower() == 'true' or from_explorer
    # < 0.5 because that's how fast Windows would open each instance of MC
    last_play_command = time.time()
    if 'paths' in request.values:
        play_paths(request.values.getlist('paths'), queue_only=queue_only,
                   from_explorer=from_explorer)
    elif 'path' in request.values:
        play_paths([request.values['path']], queue_only=queue_only,
                   from_explorer=from_explorer)
        # Since its the web GUI, we can queue all as well
        already_queueing = False
        for thread in threading.enumerate():
            if thread.name in {'QueueAll', 'PlayAll'} and thread.is_alive():
                already_queueing = True
                break
        if not already_queueing: Thread(target=queue_all, name='QueueAll', daemon=True).start()
    return redirect('/') if request.method == 'GET' else 'true'


@app.route('/metadata/')
def api_get_metadata():
    return jsonify(get_current_metadata())


@app.errorhandler(InternalServerError)
def handle_500(_e):
    original = getattr(_e, "original_exception", None)

    if original is None:
        # direct 500 error, such as abort(500)
        handle_exception(_e)
        return f'An InternalServerError occurred: {_e}'

    # wrapped unhandled error
    handle_exception(original)
    return f'An InternalServerError occurred: {original}'


@app.route('/debug/')
def api_get_debug_info():
    if settings.get('DEBUG'):
        return jsonify({'pressed_keys': list(PRESSED_KEYS),
                        'last_press': datetime.fromtimestamp(last_press),
                        'keyboardListener.is_alive()': keyboardListener.is_alive(),
                        'last_traceback': sys.exc_info(),
                        'mac': get_mac()})
    return 'set DEBUG to true in settings.json to use this page'


@app.route('/running/')
def api_running():
    return 'true'


@app.route('/exit/', methods=['GET', 'POST'])
def api_exit():
    daemon_commands.put('Exit')
    return 'true'


@app.route('/change-setting/', methods=['POST'])
def api_change_setting():
    with suppress(KeyError):
        setting_key = request.json['setting_name']
        if setting_key in settings or setting_key in {'timer_only_stop'}:
            val = request.json['value']
            change_settings(setting_key, val)
            timer_settings = {'timer_hibernate', 'timer_sleep',
                              'timer_shut_down', 'timer_only_stop'}
            if val and setting_key in timer_settings:
                for timer_setting in timer_settings.difference({setting_key, 'timer_only_stop'}):
                    change_settings(timer_setting, False)
            if setting_key == 'volume':
                update_volume(0 if settings['muted'] else settings['volume'])
        return 'true'
    return 'false'


@app.route('/refresh-devices/')
def api_refresh_devices():
    Thread(target=start_chromecast_discovery, daemon=True, name='CCDiscovery').start()
    return 'true'


@app.route('/rescan-library/')
def api_rescan_library():
    index_all_tracks()
    return 'true'


@app.route('/change-device/', methods=['POST'])
def api_change_device():
    with suppress(KeyError):
        change_device(int(request.json['device_index']))
        return 'true'
    return 'false'


@app.route('/timer/', methods=['GET', 'POST'])
def api_set_timer():
    global timer
    if request.method == 'POST':
        val = request.data.decode()
        val = val.lower()
        if val == 'cancel':
            cancel_timer()
        else:
            val = int(val)
            timer = val + time.time()
            timer_set_to = datetime.now() + timedelta(minutes=val // 60)
            if platform.system() == 'Windows':
                timer_set_to = timer_set_to.strftime('%#I:%M %p')
            else:
                timer_set_to = timer_set_to.strftime('%-I:%M %p')  # Linux
            return timer_set_to
        return 'timer cancelled'
    else:  # GET request
        return str(timer)


@app.route('/file/')
def api_get_file():
    if 'path' in request.args:
        file_path = request.args['path']
        if os.path.isfile(file_path) and valid_music_file(file_path):
            if request.args.get('thumbnail_only', False):
                mime_type, img_data = get_album_art(file_path)
                if mime_type is None:
                    mime_type, img_data = 'image/png', DEFAULT_ART
                else:
                    img_data = base64.b64decode(img_data)
                try:
                    ext = mime_type.split('/')[1]
                except IndexError:
                    ext = 'png'
                return send_file(io.BytesIO(img_data), attachment_filename=f'cover.{ext}',
                                 mimetype=mime_type, as_attachment=True, cache_timeout=360000, conditional=True)
            return send_file(file_path, conditional=True, as_attachment=True, cache_timeout=360000)
    return '401'


@app.route('/files/')
def api_all_files():
    device_name = platform.node()
    # sort by filename
    if all_tracks_sorted_filename:
        sorted_tracks = all_tracks_sorted_filename
    else:
        sorted_tracks = sorted(all_tracks.items(), key=lambda item: item[0].lower())
    list_of_tracks = []
    for filename, metadata in sorted_tracks:
        query = urllib.parse.urlencode({'path': filename})
        list_of_tracks.append({'title': metadata['sort_key'], 'href': f'/file?{query}'})
    return render_template('files.html', files=list_of_tracks, device_name=device_name)


def gen_header(sample_rate, bits_per_sample, channels):
    data_size = 2000 * 10 ** 6
    o = bytes('RIFF', 'ascii')  # 4 bytes Marks file as RIFF
    o += (data_size + 36).to_bytes(4, 'little')  # (4 bytes) File size in bytes excluding this and RIFF marker
    o += bytes('WAVE', 'ascii')  # 4 bytes File type
    o += bytes('fmt ', 'ascii')  # 4 bytes Format Chunk Marker
    o += (16).to_bytes(4, 'little')  # 4 bytes Length of above format data
    o += (1).to_bytes(2, 'little')  # 2 bytes Format type (1 - PCM)
    o += channels.to_bytes(2, 'little')  # 2 bytes
    o += sample_rate.to_bytes(4, 'little')  # 4 bytes
    o += (sample_rate * channels * bits_per_sample // 8).to_bytes(4, 'little')  # 4 bytes
    o += (channels * bits_per_sample // 8).to_bytes(2, 'little')  # 2 bytes
    o += bits_per_sample.to_bytes(2, 'little')  # 2 bytes
    o += bytes('data', 'ascii')  # 4 bytes Data Chunk Marker
    o += data_size.to_bytes(4, 'little')  # 4 bytes Data size in bytes
    return o


def create_stream(pa, sample_rate, channels, input_device_index, chunk=1024):
    _format = pyaudio.paInt16
    return pa.open(format=_format, channels=channels, as_loopback=True, rate=sample_rate, input=True,
                   input_device_index=input_device_index, frames_per_buffer=chunk)


@app.route('/live/')
def api_live_audio():
    # send system live audio to chromecast

    def system_sound():
        global live_lag
        # TODO: detect and send silence
        # live system sound generator
        p = pyaudio.PyAudio()
        _format = pyaudio.paInt16
        bits_per_sample = 16
        # get output device
        look_for_device = get_default_output_device()
        sample_rate, channels, device_index = get_output_device(p, look_for_device)
        stream = create_stream(p, sample_rate, channels, device_index, STREAM_CHUNK)
        last_sleep = 0  # doubles as a first_run
        while True:
            if last_sleep == 0:
                wav_header = gen_header(sample_rate, bits_per_sample, channels)
                data = wav_header + stream.read(STREAM_CHUNK)
                last_sleep = time.time()
            else:
                if live_lag > 0.3 and time.time() - last_sleep > 1:
                    # don't sleep consecutively
                    sleep_for = min(live_lag * 0.9, 0.3)
                    live_lag -= sleep_for
                    time.sleep(sleep_for)
                    last_sleep = time.time()
                temp_device = get_default_output_device()  # check if output device has changed
                if look_for_device != temp_device:
                    look_for_device = temp_device
                    stream.close()
                    stream = create_stream(p, *get_output_device(p, look_for_device), STREAM_CHUNK)
                data = stream.read(STREAM_CHUNK)  # gets the live system audio
            yield data

    return Response(system_sound())


@app.route('/live/thumbnail.png')
def api_live_thumbnail():
    return send_file(io.BytesIO(base64.b64decode(LIVE_AUDIO_ART)), attachment_filename=f'thumbnail.png',
                     mimetype='image/png', as_attachment=True, cache_timeout=360000, conditional=True)


@cmp_to_key
def chromecast_sorter(cc1: Chromecast, cc2: Chromecast):
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
        cast.wait()
    if chromecast.uuid not in [_cc.uuid for _cc in chromecasts]:
        chromecasts.append(chromecast)
        # chromecasts.sort(key=lambda _cc: (_cc.device.model_name, type, _cc.name, _cc.uuid))
        chromecasts.sort(key=chromecast_sorter)
        device_names.clear()
        for _i, _cc in enumerate(['Local device'] + chromecasts):
            _cc: Chromecast
            device_name = _cc if _i == 0 else _cc.name
            if (previous_device is None and _i == 0) or (type(_cc) != str and str(_cc.uuid) == previous_device):
                device_names.append(f'{CHECK_MARK} {device_name}::device')
            else:
                device_names.append(f'    {device_name}::device')
        refresh_tray()


def start_chromecast_discovery():
    global stop_discovery
    if stop_discovery is not None: stop_discovery()
    chromecasts.clear()
    stop_discovery = pychromecast.get_chromecasts(blocking=False, callback=chromecast_callback)
    time.sleep(WAIT_TIMEOUT + 1)
    stop_discovery()
    stop_discovery = None
    if not device_names: device_names.append(f'{CHECK_MARK} Local device')
    refresh_tray()


def change_device(new_idx):
    # new_idx is the index of the new device
    global cast, playing_status
    new_device: Chromecast = None if (new_idx == 0 or new_idx > len(chromecasts)) else chromecasts[new_idx - 1]

    if cast != new_device:
        device_names.clear()
        for idx, cc in enumerate(['Local device'] + chromecasts):
            cc: Chromecast = cc if idx == 0 else cc.name
            tray_device_name = f'{CHECK_MARK} {cc}::device' if idx == new_idx else f'    {cc}::device'
            device_names.append(tray_device_name)
        refresh_tray()

        current_pos = 0
        if cast is not None and cast.app_id == APP_MEDIA_RECEIVER:
            if playing_status in {'PLAYING', 'PAUSED'}:
                mc = cast.media_controller
                with suppress(UnsupportedNamespace):
                    mc.update_status()  # Switch device without playback loss
                    current_pos = mc.status.adjusted_current_time
                    if mc.is_playing or mc.is_paused: mc.stop()
            with suppress(NotConnected):
                cast.quit_app()
        elif cast is None and audio_player.is_busy():
            current_pos = audio_player.stop()
        cast = new_device
        change_settings('previous_device', None if cast is None else str(cast.uuid))
        if playing_status in {'PAUSED', 'PLAYING'} and (music_queue or playing_live):
            if not playing_live:
                autoplay = False if playing_status == 'PAUSED' else True
                play(music_queue[0], position=current_pos, autoplay=autoplay, switching_device=True)
            elif not stream_live_audio(True):
                playing_status = 'NOT PLAYING'
        else:
            if cast is not None: cast.wait(timeout=WAIT_TIMEOUT)
            volume = 0 if settings['muted'] else settings['volume']
            update_volume(volume)


def format_file(uri: str):
    try:
        metadata = get_uri_metadata(uri, read_file=False)
        title, artist = metadata['title'], metadata['artist']
        if artist.startswith('Unknown') or title.startswith('Unknown'): raise KeyError
        formatted = settings['track_format'].replace('&artist', artist).replace('&title', title)
        number = metadata.get('track_number', '')
        if '&trck' in formatted:
            formatted = formatted.replace('&trck', number)
        elif settings['show_track_number'] and number:
            formatted = f'[{number}] {formatted}'
        return formatted
    except (TypeError, KeyError):  # show something useful instead of Unknown - Unknown
        if uri.startswith('http'): return uri
        base = os.path.basename(uri)
        return os.path.splitext(base)[0]


def create_track_list():
    """:returns the formatted tracks queue, and the selected value (currently playing)"""
    tracks = []
    mq_start = len(next_queue) + 1
    selected_value = None
    # format: Index. Artists - Title
    for i, uri in enumerate(done_queue):
        formatted_track = format_file(uri)
        i = len(done_queue) - i
        formatted_item = f'-{i}. {formatted_track}'
        tracks.append(formatted_item)
    if music_queue:
        formatted_track = format_file(music_queue[0])
        formatted_item = f' {0}. {formatted_track}'
        tracks.append(formatted_item)
        selected_value = formatted_item
    for i, uri in enumerate(next_queue):
        formatted_track = format_file(uri)
        i += 1
        spacing = ' ' if i < 10 else ''
        formatted_item = f'{spacing}{i}. {formatted_track}'
        tracks.append(formatted_item)
    for i, uri in enumerate(music_queue[1:]):
        formatted_track = format_file(uri)
        i += mq_start
        spacing = ' ' if i < 10 else ''
        formatted_item = f'{spacing}{i}. {formatted_track}'
        tracks.append(formatted_item)
    return tracks, selected_value


def after_play(title, artists: str, autoplay, switching_device):
    global playing_status, cast_last_checked
    app_log.info(f'after_play: autoplay={autoplay}, switching_device={switching_device}')
    # artists is comma separated string
    playing_text = f"{get_first_artist(artists)} - {title}"
    if autoplay:
        if settings['notifications'] and not switching_device and not active_windows['main']:
            tray.show_message('Music Caster', 'Playing: ' + playing_text, time=500)
        playing_status = 'PLAYING'
        tray.update(menu=tray_menu_playing, data_base64=FILLED_ICON, tooltip=playing_text.replace('&', '&&&'))
    else:
        tray.update(menu=tray_menu_paused, data_base64=UNFILLED_ICON)
    cast_last_checked = time.time()
    if settings['save_queue_sessions']: save_queues()
    if settings['discord_rpc']:
        with suppress(Exception):
            rich_presence.update(state=f'By: {artists}', details=title, large_image='default',
                                 large_text='Listening', small_image='logo', small_text='Music Caster')


def stream_live_audio(switching_device=False):
    global track_position, track_start, track_end, track_length, playing_live, live_lag
    if cast is None:
        tray.show_message('Music Caster', 'ERROR: Not connected to a cast device', time=5000)
        playing_live = False
        return False
    else:
        url = f'http://{get_ipv4()}:{PORT}/live/'
        _volume = 0 if settings['muted'] else settings['volume'] / 100
        cast.wait(timeout=WAIT_TIMEOUT)
        try:
            cast.set_volume(_volume)
            mc = cast.media_controller
            if mc.status.player_is_playing or mc.status.player_is_paused:
                mc.stop()
                mc.block_until_active(WAIT_TIMEOUT)
            title = 'Live Audio'
            artist = platform.node()
            album = 'Music Caster'
            metadata = {'metadataType': 3, 'albumName': album, 'title': title, 'artist': artist}
            url_metadata['LIVE'] = {'artist': artist, 'title': title, 'album': album}
            # mc.play_media(f'{url}', 'audio/wav', metadata=metadata, thumb=f'{url}thumbnail.png', stream_type='LIVE')
            mc.play_media(f'{url}', 'audio/wav', metadata=metadata, thumb=f'{url}thumbnail.png')
            mc.block_until_active(WAIT_TIMEOUT)
            start_time = time.time()
            playing_live = True
            while not mc.status.player_is_playing:
                time.sleep(0.1)
                with suppress(UnsupportedNamespace): mc.update_status()
            mc.play()  # force chromecast device to start playing
            live_lag = time.time() - start_time
            track_length = 108800  # 3 hour default
            track_position = 0
            track_start = time.time() - track_position
            track_end = track_start + track_length
            after_play(title, artist, True, switching_device)
            return True
        except NotConnected:
            if internet_available():
                tray.show_message('Music Caster', 'ERROR: No Internet Connection')
            else:
                tray.show_message('Music Caster', 'ERROR: Could not connect to Chromecast')
            return False


def play_url_generic(src, ext, title, artist, album, length, position=0,
                     thumbnail=None, autoplay=True, switching_device=False):
    global track_position, track_start, track_end, playing_url, track_length, progress_bar_last_update
    _metadata = {'metadataType': 3, 'albumName': album, 'title': title, 'artist': artist}
    cast.wait(timeout=WAIT_TIMEOUT)
    cast.set_volume(0 if settings['muted'] else settings['volume'] / 100)
    mc = cast.media_controller
    if mc.status.player_is_playing or mc.status.player_is_paused:
        mc.stop()
        mc.block_until_active(WAIT_TIMEOUT)
    mc.play_media(src, f'video/{ext}', metadata=_metadata, thumb=thumbnail,
                  current_time=position, autoplay=autoplay)
    mc.block_until_active(WAIT_TIMEOUT)
    start_time = time.time()
    while mc.status.player_state not in {'PLAYING', 'PAUSED'}:
        time.sleep(0.2)
        if time.time() - start_time > 5: break  # show error?
    progress_bar_last_update = time.time()
    track_position = position
    track_length = length
    track_start = time.time() - track_position
    track_end = track_start + track_length
    playing_url = True
    after_play(title, artist, autoplay, switching_device)
    return True


def play_url(url, position=0, autoplay=True, switching_device=False):
    global cast, playing_url, playing_status, track_length, track_start, track_end, cast_last_checked
    if cast is None:
        tray.show_message('Music Caster', 'ERROR: Not connected to a cast device', time=5000)
        return False
    elif url.startswith('http') and valid_music_file(url):  # source url e.g. http://...radio.mp3
        ext = url[::-1].split('.', 1)[0][::-1]
        url_frags = urlsplit(url)
        title, artist, album = url_frags.path.split('/')[-1], url_frags.netloc, url_frags.path[1:]
        metadata = {'title': title, 'artist': artist, 'length': 108000, 'album': album, 'src': url}
        url_metadata[url.replace('\\', '/')] = metadata
        track_length = 108000  # 3 hour default
        return play_url_generic(url, ext, title, artist, album, track_length, position=position,
                                thumbnail=None, autoplay=autoplay, switching_device=switching_device)
    elif 'soundcloud.com' in url:
        if url not in url_metadata:
            r = ydl.extract_info(url, download=False)
            url = url.replace('\\', '/')
            url_metadata[url] = {'title': r['title'], 'artist': r['uploader'], 'album': 'Unknown Album',
                                 'length': r['duration'], 'art': r['thumbnail'], 'src': r['url'], 'ext': r['ext']}
        metadata = url_metadata[url]
        return play_url_generic(metadata['src'], metadata['ext'], metadata['title'], metadata['artist'],
                                metadata['album'], metadata['length'], position=position,
                                thumbnail=metadata['art'], autoplay=autoplay, switching_device=switching_device)
    elif parse_youtube_id(url) is not None:
        try:
            if url not in url_metadata:
                r = ydl.extract_info(url, download=False)
                formats = [_f for _f in r['formats'] if _f['acodec'] != 'none' and _f['vcodec'] != 'none']
                formats.sort(key=lambda _f: _f['width'])
                _f = formats[0]
                url = url.replace('\\', '/')
                url_metadata[url] = {'title': r['track'] or r['title'], 'artist': r['artist'] or r['uploader'],
                                     'album': r['album'], 'length': r['duration'], 'art': r['thumbnail'],
                                     'src': _f['url'], 'ext': _f['ext']}
            metadata = url_metadata[url]
            artist = metadata['artist']
            return play_url_generic(metadata['src'], metadata['ext'], metadata['title'], artist, metadata['album'],
                                    metadata['length'], position=position, thumbnail=metadata['art'],
                                    autoplay=autoplay, switching_device=switching_device)
        except (StopIteration, DownloadError, KeyError) as _e:
            tray.show_message('Music Caster', 'ERROR: Could not play URL.\nAn update will fix this...', time=5000)
            app_log.info(_e)
            if not IS_FROZEN: raise _e
    return False


def play(uri, position=0, autoplay=True, switching_device=False):
    global track_start, track_end, track_length, track_position, music_queue, progress_bar_last_update, playing_live, \
        cast_last_checked, playing_url
    while not os.path.exists(uri):
        if play_url(uri, position=position, autoplay=autoplay, switching_device=switching_device): return
        music_queue.remove(uri)
        if music_queue:
            uri = music_queue[0]
        else:
            return
        position = 0
    uri = uri.replace('\\', '/')
    playing_url = playing_live = False
    cleaned_uri = 'some_file.' + uri.split('.')[-1]  # clean uri for log
    app_log.info(f'play: {cleaned_uri}, position={position}, autoplay={autoplay}, switching_device={switching_device}')
    try:
        track_length = get_length(uri)
    except InvalidAudioFile:
        tray.show_message('Music Caster', f"ERROR: can't play {music_queue.pop(0)}")
        if music_queue: play(music_queue[0])
        return
    metadata = get_metadata_wrapped(uri)
    # update metadata of track in case something changed
    try:
        all_tracks[uri] = metadata
    except KeyError:
        all_tracks[uri] = metadata
    _volume = 0 if settings['muted'] else settings['volume'] / 100
    if cast is None:  # play locally
        audio_player.play(uri, volume=_volume, start_playing=autoplay, start_from=position)
    else:
        try:
            cast_last_checked = time.time() + 60  # make sure background_tasks doesn't interfere
            url_args = urllib.parse.urlencode({'path': uri})
            url = f'http://{get_ipv4()}:{PORT}/file?{url_args}'
            with suppress(RuntimeError):
                cast.wait(timeout=WAIT_TIMEOUT)
            cast.set_volume(_volume)
            mc = cast.media_controller
            metadata = {'title': metadata['title'], 'artist': metadata['artist'],
                        'albumName': metadata['album'], 'metadataType': 3}
            ext = uri.split('.')[-1]
            mc.play_media(url, f'audio/{ext}', current_time=position,
                          metadata=metadata, thumb=url + '&thumbnail_only=true', autoplay=autoplay)
            t1 = time.time()
            mc.block_until_active(WAIT_TIMEOUT + 1)
            if time.time() - t1 > WAIT_TIMEOUT:
                app_log.info('play: FAILED TO BLOCK UNTIL ACTIVE')
            start_time = time.time()
            while mc.status.player_state not in {'PLAYING', 'PAUSED'}:
                time.sleep(0.2)
                if time.time() - start_time > WAIT_TIMEOUT: break
            app_log.info(f'play: mc.status.player_state={mc.status.player_state}')
            progress_bar_last_update = time.time()
        except (UnsupportedNamespace, NotConnected, OSError):
            tray.show_message('Music Caster', 'ERROR: Could not connect to Chromecast device', time=5000)
            with suppress(UnsupportedNamespace):
                stop('play')
            return
    track_position = position
    track_start = time.time() - track_position
    track_end = track_start + track_length
    after_play(metadata['title'], metadata['artist'], autoplay, switching_device)


def play_all(starting_files: list = None, queue_only=False):
    global playing_status, indexing_tracks_thread
    """
    Clears done queue, music queue,
    Adds starting files to music queue,
    [shuffle] queues files in the "library" with index_all_tracks (ignores starting_files)
    """
    if not queue_only:
        music_queue.clear()
        done_queue.clear()
    if starting_files is None: starting_files = []
    starting_files = [_f.replace('\\', '/') for _f in starting_files if valid_music_file(_f)]
    if indexing_tracks_thread is not None and indexing_tracks_thread.is_alive() and settings['notifications']:
        tray.show_message('Music Caster', 'Some files may be missing as music library is still being built')
    if starting_files:
        music_queue.extend(index_all_tracks(False, starting_files).keys())
    else:
        music_queue.extend(all_tracks.keys())
    if music_queue: shuffle(music_queue)
    if starting_files:
        for j, _f in enumerate(starting_files):
            music_queue.insert(j, _f)
    if not queue_only:
        if music_queue:
            play(music_queue[0])
        elif next_queue:
            playing_status = 'PLAYING'
            next_track()


def queue_all():
    global update_gui_queue
    temp_lst = list(index_all_tracks(update_global=False, ignore_files=music_queue).keys())
    shuffle(temp_lst)
    music_queue.extend(temp_lst)
    update_gui_queue = True


def play_paths(paths: list, queue_only=False, from_explorer=False):
    global playing_status, update_gui_queue
    """
    Appends all music files in the provided paths/names (folders, files, playlist names) to a temp list,
        which is shuffled if shuffled is enabled in settings, and then extends music_queue.
        Note: file/folder paths take precedence over playlist name
    If queue_only is false, the music queue and done queue are cleared,
        before files are added to the music_queue
    If from_explorer is true, then the whole music queue is shuffled (if setting enabled),
        except for the track that is currently playing
    """
    if not queue_only:
        music_queue.clear()
        done_queue.clear()
    app_log.info(f'play_paths: len(paths) = {len(paths)}, queue_only = {queue_only}')
    temp_queue = []
    for path in paths:
        invalid_path = True
        if os.path.exists(path):
            invalid_path = False
            path = path.rstrip('\\').rstrip('/')
            if os.path.isfile(path):
                if valid_music_file(path): temp_queue.append(path)
            else:
                for _file in glob.iglob(f'{glob.escape(path)}/**/*.*', recursive=True):
                    if valid_music_file(_file):
                        temp_queue.append(_file)
        if invalid_path: temp_queue.extend(settings['playlists'].get(path, []))
    update_gui_queue = True
    if settings['shuffle']:
        # if from_explorer make temp_queue all files already in queue
        temp_queue = music_queue[1:] * from_explorer + temp_queue
        shuffle(temp_queue)
        # remove all but first track if from_explorer
        for _ in range(1, len(music_queue) * from_explorer): music_queue.pop()
    music_queue.extend(temp_queue)
    if not queue_only:
        if music_queue:
            play(music_queue[0])
        elif next_queue:
            playing_status = 'PLAYING'
            next_track()


def file_action(action='Play File(s)'):
    # actions = 'Play File(s)', 'Play File(s) Next', 'Queue File(s)'
    global music_queue, next_queue, playing_status, main_last_event, update_gui_queue
    fd = wx.FileDialog(None, 'Select Music File(s)', defaultDir=DEFAULT_FOLDER, wildcard=MUSIC_FILE_TYPES,
                       style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE)
    if fd.ShowModal() != wx.ID_CANCEL:
        paths = fd.GetPaths()
        app_log.info(f'file_action(action={action}), len(lst) is {len(paths)}')
        update_gui_queue = True
        main_last_event = Sg.TIMEOUT_KEY
        if action == 'Play File(s)':
            music_queue.clear()
            done_queue.clear()
            for file_path in fd.GetPaths():
                if valid_music_file(file_path):
                    music_queue.append(file_path)
                    if file_path not in all_tracks: files_to_scan.put(file_path)
            if music_queue: play(music_queue[0])
        elif action == 'Queue File(s)':
            _start_playing = not music_queue
            for file_path in fd.GetPaths():
                if valid_music_file(file_path):
                    music_queue.append(file_path)
                    if file_path not in all_tracks: files_to_scan.put(file_path)
            if _start_playing and music_queue: play(music_queue[0])
        elif action == 'Play File(s) Next':
            if settings['reversed_play_next']:
                for file_path in fd.GetPaths():
                    if valid_music_file(file_path):
                        next_queue.insert(0, file_path)
                        if file_path not in all_tracks: files_to_scan.put(file_path)
            else:
                for file_path in fd.GetPaths():
                    if valid_music_file(file_path):
                        next_queue.append(file_path)
                        if file_path not in all_tracks: files_to_scan.put(file_path)
            if playing_status == 'NOT PLAYING' and not music_queue and next_queue:
                if cast is not None and cast.app_id != APP_MEDIA_RECEIVER: cast.wait(timeout=WAIT_TIMEOUT)
                playing_status = 'PLAYING'
                next_track()
        else:
            raise ValueError('Expected one of: "Play File(s)", "Play File(s) Next", or "Queue File(s)"')
    else:
        main_last_event = 'file_action'


def play_file():
    file_action()


def queue_file():
    # TODO: add to tray menu
    file_action('Queue File(s)')


def play_next():
    file_action('Play File(s) Next')


def folder_action(action='Play Folder'):
    global music_queue, next_queue, playing_status, main_last_event, update_gui_queue
    # actions: 'Play Folder', 'Play Folder Next', 'Queue Folder'
    # multi dir support code. Issues with it though
    # dlg = mdd.MultiDirDialog(None, title='Select Folders', defaultPath=DEFAULT_DIR, pos=wx.GetMousePosition(),
    #                          agwStyle=mdd.DD_MULTIPLE | mdd.DD_DIR_MUST_EXIST)
    # half_way = wx.GetMousePosition()[1] - dlg.GetSize()[1] // 2
    # dlg.SetPosition((dlg.GetPosition()[0], half_way))
    # dlg.SetSize(dlg.GetSize()[0] * 3, dlg.GetSize()[1])
    # issues with multi dir support: freezes any open windows, that's why I have to close them and then reopen
    # open_main = False
    # for window in active_windows:
    #     if active_windows[window]:
    #         active_windows[window] = False
    #         if window == 'main': open_main = True
    #         {'main': main_window, 'play_url': play_url_window}[window].close()
    dlg = wx.DirDialog(None, 'Select Folder', DEFAULT_FOLDER, style=wx.DD_DIR_MUST_EXIST)
    if dlg.ShowModal() != wx.ID_CANCEL and os.path.exists(dlg.GetPath()):
        temp_queue = []
        # folder_paths = dlg.GetPaths()
        folder_paths = [dlg.GetPath()]
        for folder_path in folder_paths:
            # multi support
            # drive, rest = folder_path.split('\\', 1)
            # drive = drive.split('(')[-1][:-1]
            # folder_path = drive + '/' + rest
            if os.path.exists(folder_path):
                for file_path in glob.iglob(f'{glob.escape(folder_path)}/**/*.*', recursive=True):
                    if valid_music_file(file_path):
                        temp_queue.append(file_path)
                        if file_path not in all_tracks: files_to_scan.put(file_path)
        if settings['shuffle']: shuffle(temp_queue)
        else: temp_queue.sort(key=natural_key_file)
        app_log.info(f'folder_action: action={action}), len(lst) is {len(temp_queue)}')
        update_gui_queue = True
        main_last_event = Sg.TIMEOUT_KEY
        if action == 'Play Folder':
            music_queue.clear()
            done_queue.clear()
            music_queue += temp_queue
            if music_queue: play(music_queue[0])
        elif action == 'Play Folder Next':
            if settings['reversed_play_next']:
                for _f in temp_queue:
                    next_queue.insert(0, _f)
            else:
                next_queue.extend(temp_queue)
            if playing_status == 'NOT PLAYING' and not music_queue and next_queue:
                if cast is not None and cast.app_id != APP_MEDIA_RECEIVER: cast.wait(timeout=WAIT_TIMEOUT)
                playing_status = 'PLAYING'
                next_track()
        elif action == 'Queue Folder':
            start_playing = not music_queue
            music_queue.extend(temp_queue)
            if start_playing and music_queue: play(music_queue[0])
        else:
            raise ValueError('Expected one of: "Play Folder", "Play Folder Next", or "Queue Folder"')
        del temp_queue
    else:
        main_last_event = 'folder_action'


def internet_available(host='8.8.8.8', port=53, timeout=3):
    """
    Host: 8.8.8.8 (google-public-dns-a.google.com)
    OpenPort: 53/tcp
    Service: domain (DNS/TCP)
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error:
        return False


def get_track_position():
    global track_position
    if cast is not None:
        if internet_available():
            try:
                mc = cast.media_controller
                mc.update_status()
                if not mc.status.player_is_idle:
                    track_position = mc.status.adjusted_current_time
            except (UnsupportedNamespace, NotConnected):
                if playing_status == 'PLAYING':
                    track_position = time.time() - track_start
                # don't calculate if playing status is NOT PLAYING or PAUSED
        elif playing_status == 'PLAYING':
            # don't calculate if playing status is NOT PLAYING or PAUSED
            track_position = time.time() - track_start
    elif playing_status in {'PLAYING', 'PAUSED'}:
        track_position = audio_player.get_pos()
    return track_position


def pause():
    """ can be called from a non-main thread """
    global tray, playing_status, track_position
    if playing_status == 'PLAYING':
        try:
            if cast is None:
                track_position = time.time() - track_start
                if audio_player.pause():
                    app_log.info('paused local audio player')
                else:
                    app_log.info('could not pause local audio player')
            elif internet_available():
                mc = cast.media_controller
                mc.update_status()
                mc.pause()
                while not mc.status.player_is_paused: time.sleep(0.1)
                track_position = mc.status.adjusted_current_time
                app_log.info('paused cast device')
            playing_status = 'PAUSED'
            if settings['discord_rpc'] and (music_queue or playing_live):
                metadata = url_metadata['LIVE'] if playing_live else get_uri_metadata(music_queue[0])
                title, artist = metadata['title'], metadata['artist']
                with suppress(Exception):
                    rich_presence.update(state=f'By: {artist}', details=title, large_image='default',
                                         large_text='Paused', small_image='logo', small_text='Music Caster')
        except UnsupportedNamespace:
            stop('pause')
        tray.update(menu=tray_menu_paused, data_base64=UNFILLED_ICON)
        return True
    return False


def resume():
    global tray, playing_status, track_end, track_position, track_start
    if playing_status == 'PAUSED':
        try:
            if cast is None:
                if audio_player.resume():
                    app_log.info('resumed playback')
                else:
                    app_log.info('failed to resume')
            else:
                mc = cast.media_controller
                mc.update_status()
                mc.play()
                mc.block_until_active(WAIT_TIMEOUT)
                while not mc.status.player_state == 'PLAYING': time.sleep(0.1)
                track_position = mc.status.adjusted_current_time
            track_start = time.time() - track_position
            track_end = track_start + track_length
            playing_status = 'PLAYING'
            metadata = get_current_metadata()
            title, artist = metadata['title'], get_first_artist(metadata['artist'])
            if settings['discord_rpc']:
                with suppress(Exception):
                    rich_presence.update(state=f'By: {artist}', details=title, large_image='default',
                                         large_text='Playing', small_image='logo', small_text='Music Caster')
            tray.update(menu=tray_menu_playing, data_base64=FILLED_ICON)
        except (UnsupportedNamespace, NotConnected):
            if music_queue: play(music_queue[0], position=track_position)
        return True
    return False


def stop(stopped_from: str, stop_cast=True):
    """
    can be called from a non-main thread
    does not check if playing_status is not 'NOT PLAYING'
    """
    global playing_status, cast, track_position, playing_live, playing_url
    app_log.info(f'Stop reason: {stopped_from}')
    playing_status = 'NOT PLAYING'
    playing_live = playing_url = False
    if settings['discord_rpc']:
        with suppress(Exception): rich_presence.clear()
    if cast is not None:
        if internet_available() and cast.app_id == APP_MEDIA_RECEIVER:
            mc = cast.media_controller
            if stop_cast:
                mc.stop()
                until_time = time.time() + 5  # 5 seconds
                status = mc.status
                while ((status.player_is_playing or status.player_is_paused)
                       and time.time() > until_time): time.sleep(0.1)
                if status.player_is_playing or status.player_is_paused: cast.quit_app()
            else:  # only when background tasks calls stop()
                # check if background tasks is wrong
                mc.update_status()
                if mc.is_playing:
                    playing_status = 'PLAYING'
                elif mc.is_paused:
                    playing_status = 'PAUSED'
                return
    else:
        audio_player.stop()
    track_position = 0
    if not exit_flag: tray.update(menu=tray_menu_default, data_base64=UNFILLED_ICON, tooltip='Music Caster')


def next_track(from_timeout=False):
    global playing_status
    app_log.info(f'next_track(from_timeout={from_timeout})')
    if cast is not None and cast.app_id != APP_MEDIA_RECEIVER:
        playing_status = 'NOT PLAYING'
    elif playing_status != 'NOT PLAYING' and not playing_live and (next_queue or music_queue):
        # if repeat all or repeat is off or empty queue or not manual next
        if not settings['repeat'] or not music_queue or not from_timeout:
            if settings['repeat']: change_settings('repeat', False)
            if music_queue: done_queue.append(music_queue.pop(0))
            if next_queue: music_queue.insert(0, next_queue.pop(0))
            # if queue is empty but repeat is all AND there are tracks in the done_queue
            if not music_queue and settings['repeat'] is False and done_queue:
                music_queue.extend(done_queue)
                done_queue.clear()
        if music_queue:
            play(music_queue[0])
        else:
            stop('next track')  # repeat is off / no tracks in queue


def prev_track():
    global playing_status
    app_log.info('prev_track()')
    if playing_status != 'NOT PLAYING' and not playing_live:
        if cast is not None and cast.app_id != APP_MEDIA_RECEIVER:
            playing_status = 'NOT PLAYING'
        else:
            if done_queue:
                if settings['repeat']: change_settings('repeat', False)
                track = done_queue.pop()
                music_queue.insert(0, track)
                play(track)
            elif music_queue:
                play(music_queue[0])


def background_tasks():
    global cast_last_checked, track_position, track_start, track_end, settings_last_modified
    global update_last_checked, latest_version, exit_flag, update_volume_slider, update_gui_queue
    while not exit_flag:
        # SETTINGS_LAST_MODIFIED
        if os.path.getmtime(settings_file) != settings_last_modified: load_settings()  # last modified gets updated here
        # Check cast every 5 seconds
        if cast is not None and time.time() - cast_last_checked > 5 and internet_available():
            with suppress(UnsupportedNamespace):
                if cast.app_id == APP_MEDIA_RECEIVER:
                    mc = cast.media_controller
                    mc.update_status()
                    is_playing, is_paused = mc.status.player_is_playing, mc.status.player_is_paused
                    is_stopped = mc.status.player_is_idle
                    if not is_stopped:
                        # handle scrubbing of music from the home app / out of date time position
                        if abs(mc.status.adjusted_current_time - track_position) > 0.5:
                            track_position = mc.status.adjusted_current_time
                            track_start = time.time() - track_position
                            track_end = track_start + track_length
                    if is_paused:
                        pause()  # pause() checks if playing status equals 'PLAYING'
                    elif is_playing:
                        resume()
                    elif is_stopped and playing_status != 'NOT PLAYING' and time.time() - track_end > 1:
                        # if cast says nothing is playing, only stop if we are not at the end of the track
                        #  this will prevent false positives
                        stop('background tasks', False)
                    _volume = settings['volume']
                    cast_volume = round(cast.status.volume_level * 100, 1)
                    if _volume != cast_volume:
                        if cast_volume > 0.5 or cast_volume <= 0.5 and not settings['muted']:
                            # if volume was changed via Google Home App
                            _volume = change_settings('volume', cast_volume)
                            if _volume and settings['muted']: change_settings('muted', False)
                            if active_windows['main']: update_volume_slider = True
                elif playing_status == 'PLAYING':
                    stop('background tasks; app not running')
            cast_last_checked = time.time()
            # don't check cast around the time the next track will start playing
            if track_end - cast_last_checked < 10: cast_last_checked += 5
        if time.time() - update_last_checked > 216000:
            # never show a notification for the same latest version
            release = get_latest_release(latest_version)
            if release:
                latest_version = release['version']
                tray.show_message('Music Caster', f'Update v{latest_version} is available')
            update_last_checked = time.time()
        # scan at most 500 files per loop.
        # Testing on an i7-7700k, scanning ~1000 files would block for 5 seconds
        files_scanned = 0
        while files_scanned < 500 and not files_to_scan.empty():
            file_path = files_to_scan.get().replace('\\', '/')
            all_tracks[file_path] = get_metadata_wrapped(file_path)
            files_to_scan.task_done()
            files_scanned += 1
        if files_scanned: update_gui_queue = True
        # if no files were scanned, pause for 5 seconds
        else: time.sleep(5)


def on_press(key):
    global last_press
    key = str(key)
    PRESSED_KEYS.add(key)
    valid_shortcut = len(PRESSED_KEYS) == 4 and "'m'" in PRESSED_KEYS
    ctrl_clicked = 'Key.ctrl_l' in PRESSED_KEYS or 'Key.ctrl_r' in PRESSED_KEYS
    shift_clicked = 'Key.shift' in PRESSED_KEYS or 'Key.shift_r' in PRESSED_KEYS
    alt_clicked = 'Key.alt_l' in PRESSED_KEYS or 'Key.alt_r' in PRESSED_KEYS
    # Ctrl + Alt + Shift + M open up main window
    if valid_shortcut and ctrl_clicked and shift_clicked and alt_clicked:
        daemon_commands.put('__ACTIVATED__')
    if key not in {'<179>', '<176>', '<177>', '<178>'} or time.time() - last_press < 0.15: return
    if key == '<179>' and playing_status != 'NOT PLAYING':
        if not pause(): resume()
    elif key == '<176>' and playing_status != 'NOT PLAYING':
        next_track()
    elif key == '<177>' and playing_status != 'NOT PLAYING':
        prev_track()
    elif key == '<178>':
        stop('keyboard shortcut')
    last_press = time.time()


def on_release(key):
    with suppress(KeyError): PRESSED_KEYS.remove(str(key))


def bring_to_front():
    # bring an active window to front by priority or open the main window
    if active_windows['play_url'] and not active_windows['main']: activate_play_url()
    else: activate_main_window()


def activate_main_window(selected_tab='tab_queue'):
    global active_windows, main_window
    # selected_tab can be 'tab_queue', ['tab_library'], 'tab_playlists', 'tab_timer', or 'tab_settings'
    app_log.info(f'activate_main_window: selected_tab={selected_tab}, already_active={active_windows["main"]}')
    if not active_windows['main']:
        active_windows['main'] = True
        lb_tracks, selected_value = create_track_list()
        mini_mode = settings['mini_mode']
        save_window_loc_key = 'main' + '_mini_mode' if mini_mode else ''
        window_location = get_window_location(save_window_loc_key)
        size = COVER_MINI if mini_mode else (255, 255)
        album_art_data = resize_img(get_current_album_art(), settings['theme']['background'],
                                    size).decode() if settings['show_album_art'] else None
        window_margins = (0, 0) if mini_mode else (None, None)
        try:
            qr_code = create_qr_code(PORT)
        except OSError:
            qr_code = None  # long time without internet
        if playing_status in {'PAUSED', 'PLAYING'} and (music_queue or playing_live):
            if playing_live:
                metadata = url_metadata['LIVE']
                position = track_length
            else:
                metadata = get_uri_metadata(music_queue[0])
                position = get_track_position()
            title, artist, album = metadata['title'], get_first_artist(metadata['artist']), metadata['album']
            main_gui_layout = create_main(lb_tracks, selected_value, playing_status, settings, VERSION, timer,
                                          all_tracks_sorted_sort_key, title, artist, album, track_length=track_length,
                                          qr_code=qr_code, album_art_data=album_art_data, track_position=position)
        else:
            main_gui_layout = create_main(lb_tracks, selected_value, playing_status, settings, VERSION, timer,
                                          all_tracks_sorted_sort_key, qr_code=qr_code, album_art_data=album_art_data)
        main_window = Sg.Window('Music Caster', main_gui_layout, grab_anywhere=mini_mode, no_titlebar=mini_mode,
                                finalize=True, icon=WINDOW_ICON, return_keyboard_events=True, use_default_focus=False,
                                margins=window_margins, keep_on_top=mini_mode and settings['mini_on_top'],
                                location=window_location)
        if not settings['mini_mode']:
            main_window['queue'].update(set_to_index=len(done_queue), scroll_to_index=len(done_queue))
            main_window['queue'].bind('<Enter>', '_mouse_enter')
            main_window['queue'].bind('<Leave>', '_mouse_leave')
            main_window['pl_tracks'].bind('<Enter>', '_mouse_enter')
            main_window['pl_tracks'].bind('<Leave>', '_mouse_leave')
            if settings['EXPERIMENTAL']:
                main_window['library'].bind('<Enter>', '_mouse_enter')
                main_window['library'].bind('<Leave>', '_mouse_leave')
        main_window['volume_slider'].bind('<Enter>', '_mouse_enter')
        main_window['volume_slider'].bind('<Leave>', '_mouse_leave')
        main_window['progress_bar'].bind('<Enter>', '_mouse_enter')
        main_window['progress_bar'].bind('<Leave>', '_mouse_leave')
        set_save_position_callback(main_window, save_window_loc_key)
    else:
        # window already active so steal focus in case tray was not clicked
        steal_focus(main_window)
        # set selected_tab to what is already selected to prevent the tab from switching
        if not settings['mini_mode']: selected_tab = main_window['tab_group'].get()
    if not settings['mini_mode']:
        main_window[selected_tab].select()
        if selected_tab == 'tab_timer': main_window['timer_minutes'].set_focus()
    main_window.TKroot.focus_force()
    main_window.normal()


def activate_play_url(combo_value='Play Immediately'):
    # combo_values = ['Play Immediately', 'Queue', 'Play Next']
    global play_url_window
    if not active_windows['play_url']:
        clipboard_txt: str = pyperclip.paste()
        if not clipboard_txt.startswith('http'): clipboard_txt = ''
        play_url_layout = create_play_url(combo_value=combo_value, default_text=clipboard_txt)
        active_windows['play_url'] = True
        window_location = get_window_location('play_url')
        play_url_window = Sg.Window('Music Caster - Play URL', play_url_layout, icon=WINDOW_ICON,
                                    finalize=True, return_keyboard_events=True, location=window_location)
        set_save_position_callback(play_url_window, 'play_url')
    else:
        # play url window already active, so bring it to front
        steal_focus(play_url_window)
    play_url_window.TKroot.focus_force()
    play_url_window.normal()
    play_url_window['url'].set_focus()


def cancel_timer():
    global timer
    timer = 0
    if settings['notifications']: tray.show_message('Music Caster', 'Timer stopped', time=5000)


def locate_track(selected_track_index=0):
    with suppress(IndexError):
        if selected_track_index < 0:
            uri = done_queue[selected_track_index]
        elif (selected_track_index == 0 or selected_track_index > len(next_queue)) and music_queue:
            uri = music_queue[selected_track_index]
        elif 0 < selected_track_index <= len(next_queue):
            uri = next_queue[selected_track_index - 1]
        else:
            uri = ''
        if uri.startswith('http'):
            if uri.startswith('http'): Thread(target=webbrowser.open, daemon=True, args=[uri]).start()
        else:
            Popen(f'explorer /select,"{fix_path(uri)}"')


def exit_program():
    global exit_flag
    exit_flag = True
    for window in (main_window, play_url_window): window.close()
    tray.hide()
    with suppress(UnsupportedNamespace, NotConnected):
        if cast is None:
            stop('exit program')
        elif cast is not None and cast.app_id == APP_MEDIA_RECEIVER:
            cast.quit_app()
    with suppress(Exception):
        rich_presence.close()
    if settings['auto_update']: auto_update(False)
    sys.exit()  # since auto_update might not sys.exit()


def play_playlist(playlist_name):
    if playlist_name in playlists:
        music_queue.clear()
        done_queue.clear()
        music_queue.extend(playlists.get(playlist_name, []))
        if music_queue:
            if settings['shuffle']: shuffle(music_queue)
            play(music_queue[0])


def other_daemon_actions(command_name):
    if command_name.startswith('Show Notification: '):
        title, msg = command_name[19:].split(', ', 1)
        tray.show_message(title, msg, time=5000)


def other_tray_actions(_tray_item):
    global cast, cast_last_checked, timer
    # this code checks if its time to go to the next track
    # this code checks if its time to stop playing music if a timer was set
    # if _tray_item.split('.', 1)[0].isdigit():  # if user selected a different device
    if _tray_item.endswith('::device') and not _tray_item.startswith(CHECK_MARK):
        with suppress(ValueError):
            change_device(device_names.index(tray_item))
    elif _tray_item.endswith('::PL'):  # playlist
        play_playlist(tray_item[:-4].replace('&&', '&'))
    elif _tray_item.endswith('::PF'):  # play folder
        if tray_item == 'Select Folder(s)::PF':
            wx.CallAfter(folder_action)
        else:
            Thread(target=play_paths, name='PlayFolder', daemon=True,
                   args=[[music_folders[tray_folders.index(tray_item) - 1]]]).start()
    elif playing_status == 'PLAYING' and time.time() > track_end:
        next_track(from_timeout=time.time() > track_end)
    elif timer and time.time() > timer:
        stop('timer')
        timer = 0
        if settings['timer_shut_down']:
            if platform.system() == 'Windows':
                os.system('shutdown /p /f')
            else:
                os.system('shutdown -h now')
        elif settings['timer_hibernate']:
            if platform.system() == 'Windows': os.system(r'rundll32.exe powrprof.dll,SetSuspendState Hibernate')
        elif settings['timer_sleep']:
            if platform.system() == 'Windows': os.system('rundll32.exe powrprof.dll,SetSuspendState 0,1,0')


def reset_mouse_hover():
    global mouse_hover
    mouse_hover = ''


def reset_progress():
    # NOTE: needs to be in main thread
    main_window['progress_bar'].update(value=0)
    main_window['time_elapsed'].update('0:00')
    main_window['time_left'].update('0:00')
    main_window.refresh()


def read_main_window():
    global main_last_event, mouse_hover, playing_status, update_volume_slider, progress_bar_last_update
    global track_position, track_start, track_end, timer, main_window, update_gui_queue
    global tray_playlists, pl_files, pl_name, playlists
    # make if statements into dict mapping
    main_event, main_values = main_window.read(timeout=1)
    if (main_event in {None, 'Escape:27'} and
            main_last_event not in {'file_action', 'folder_action', 'pl_add_tracks', 'add_music_folder'}
            or main_values is None):
        active_windows['main'] = False
        main_window.close()
        return False
    main_value = main_values.get(main_event)
    if 'mouse_leave' not in main_event and 'mouse_enter' not in main_event and main_event != Sg.TIMEOUT_KEY:
        main_last_event = main_event
    p_r_button = main_window['pause/resume']
    gui_title = main_window['title'].DisplayText
    update_progress_bar_text, title, artist, album = False, 'Nothing Playing', '', ''
    if playing_status in {'PAUSED', 'PLAYING'} and (playing_live or music_queue):
        metadata = url_metadata['LIVE'] if playing_live else get_uri_metadata(music_queue[0])
        title, artist, album = metadata['title'], get_first_artist(metadata['artist']), metadata['album']
        if settings['show_track_number']:
            with suppress(KeyError):
                track_number = metadata['track_number']
                title = f'{track_number}. {title}'
    # usually if music stops playing or another track starts playing
    if gui_title != title:
        if settings['mini_mode']: title = truncate_title(title)
        main_window['title'].update(title)
        main_window['artist'].update(artist)
        # update album title if not in mini-mode
        if not settings['mini_mode']: main_window['album'].update(album)
        if settings['show_album_art']:
            size = COVER_MINI if settings['mini_mode'] else (255, 255)
            try:
                album_art_data = resize_img(get_current_album_art(), settings['theme']['background'], size).decode()
            except (UnidentifiedImageError, OSError):
                album_art_data = resize_img(DEFAULT_ART, settings['theme']['background'], size).decode()
            main_window['album_art'].update(data=album_art_data)
        update_gui_queue = True
    # update timer text if timer is old
    if timer == 0 and main_window['timer_text'].metadata:
        main_window['timer_text'].update('No Timer Set')
        main_window['timer_text'].metadata = False
        main_window['cancel_timer'].update(visible=False)
    # check updates from global variables
    if update_gui_queue and not settings['mini_mode']:
        update_gui_queue = False
        dq_len = len(done_queue)
        lb_music_queue: Sg.Listbox = main_window['queue']
        lb_tracks = create_track_list()[0]
        lb_music_queue.update(values=lb_tracks, set_to_index=dq_len, scroll_to_index=dq_len)
    if update_volume_slider:
        if settings['volume'] and settings['muted']:
            main_window['mute'].update(image_data=VOLUME_IMG)
            main_window['mute'].set_tooltip('mute')
        main_window['volume_slider'].update(settings['volume'])
        update_volume_slider = False
    # update repeat button (image) if button metadata differs from settings
    if settings['repeat'] != main_window['repeat'].metadata: update_repeat_button()
    # update shuffle button (image) if button metadata differs from settings
    if settings['shuffle'] != main_window['shuffle'].metadata:
        shuffle_image_data = SHUFFLE_ON if settings['shuffle'] else SHUFFLE_OFF
        main_window['shuffle'].update(image_data=shuffle_image_data)
        main_window['shuffle'].metadata = settings['shuffle']
    # handle events here
    if main_event.startswith('MouseWheel'):
        main_event = main_event.split(':', 1)[1]
        delta = {'Up': 5, 'Down': -5}.get(main_event, 0)
        if mouse_hover == 'progress_bar':
            if playing_status in {'PLAYING', 'PAUSED'}:
                get_track_position()
                new_position = min(max(track_position + delta, 0), track_length)
                main_window['progress_bar'].update(value=new_position)
                main_values['progress_bar'] = new_position
                main_event = 'progress_bar'
        elif mouse_hover in {'', 'volume_slider'}:  # not in another tab
            new_volume = min(max(0, main_values['volume_slider'] + delta), 100)
            change_settings('volume', new_volume)
            if settings['muted']:
                main_window['mute'].update(image_data=VOLUME_IMG)
                main_window['mute'].set_tooltip('mute')
                change_settings('muted', False)
            update_volume(new_volume)
        main_window.refresh()
    # needs to be in its own if statement because it tell the progress bar to update later on
    if main_event in {'j', 'l'} and (settings['mini_mode'] or
                                     main_values['tab_group'] not in {'tab_timer', 'tab_playlists'}):
        if playing_status in {'PLAYING', 'PAUSED'}:
            delta = {'j': -settings['scrubbing_delta'], 'l': settings['scrubbing_delta']}[main_event]
            get_track_position()
            new_position = min(max(track_position + delta, 0), track_length)
            main_window['progress_bar'].update(value=new_position)
            main_values['progress_bar'] = new_position
            main_event = 'progress_bar'
            main_window.refresh()
    if main_event == Sg.TIMEOUT_KEY:
        pass
    elif main_event == 'tab_group' and main_values['tab_group'] == 'tab_queue':
        main_window['file_action'].set_focus()
    # change tabs with hot keys
    elif main_event == '1:49' and not settings['mini_mode']:
        main_window['tab_queue'].select()  # Ctrl + 1
    elif main_event == '2:50' and not settings['mini_mode']:
        main_window['tab_playlists'].select()  # Ctrl + 2
    elif (main_event == '3:51' and not settings['mini_mode'] or
          main_event == 'tab_group' and main_values['tab_group'] == 'tab_timer'):  # Ctrl + 3
        main_window['tab_timer'].select()
        main_window['timer_minutes'].set_focus()
    elif main_event == '4:52' and not settings['mini_mode']:
        main_window['tab_settings'].select()  # Ctrl + 4
    elif main_event in {'progress_bar_mouse_enter', 'queue_mouse_enter', 'pl_tracks_mouse_enter',
                        'volume_slider_mouse_enter', 'library_mouse_enter'}:
        if main_event in {'progress_bar_mouse_enter', 'volume_slider_mouse_enter'} and settings['mini_mode']:
            main_window.grab_any_where_off()
        mouse_hover = '_'.join(main_event.split('_')[:-2])
    elif main_event in {'progress_bar_mouse_leave', 'queue_mouse_leave', 'pl_tracks_mouse_leave',
                        'volume_slider_mouse_leave', 'library_mouse_leave'}:
        if main_event in {'progress_bar_mouse_leave', 'volume_slider_mouse_leave'} and settings['mini_mode']:
            main_window.grab_any_where_on()
        mouse_hover = '' if main_event != 'volume_slider_mouse_leave' else mouse_hover
    elif main_event in {'locate_track', 'e:69'}:
        with suppress(IndexError):
            selected_track_index = int(main_values['queue'][0].split('.', 1)[0])
            locate_track(selected_track_index)
    elif (main_event == 'pause/resume' or main_event == 'k' and (
            settings['mini_mode'] or main_values['tab_group'] not in {'tab_timer', 'tab_playlists'})):
        if playing_status == 'PAUSED': resume()
        elif playing_status == 'PLAYING': pause()
        elif music_queue: play(music_queue[0])
        else: play_all()
    elif main_event == 'next' and playing_status != 'NOT PLAYING':
        reset_progress()
        next_track()
    elif main_event == 'prev' and playing_status != 'NOT PLAYING':
        reset_progress()
        prev_track()
    elif main_event == 'shuffle':
        shuffle_option = change_settings('shuffle', not settings['shuffle'])
        shuffle_image_data = SHUFFLE_ON if shuffle_option else SHUFFLE_OFF
        main_window['shuffle'].update(image_data=shuffle_image_data)
        main_window['shuffle'].metadata = shuffle_option
    elif main_event in {'repeat', 'r:82'}:
        cycle_repeat(True)
    elif (main_event == 'volume_slider' or ((main_event in {'a', 'd'} or main_event.isdigit())
          and (settings['mini_mode'] or main_values['tab_group'] not in {'tab_timer', 'tab_playlists'}))):
        # User scrubbed volume bar or pressed (while on Tab 1 or in mini mode)
        delta = 0
        if main_event.isdigit():
            new_volume = int(main_event) * 10
        else:
            if main_event == 'a':
                delta = -5
            elif main_event == 'd':
                delta = 5
            new_volume = main_values['volume_slider'] + delta
        change_settings('volume', new_volume)
        if settings['muted'] and new_volume:
            main_window['mute'].update(image_data=VOLUME_IMG)
            main_window['mute'].set_tooltip('mute')
            change_settings('muted', False)
        update_volume(new_volume)
    elif main_event in {'mute', 'm:77'}:  # toggle mute
        muted = change_settings('muted', not settings['muted'])
        if muted:
            main_window['mute'].update(image_data=VOLUME_MUTED_IMG)
            main_window['mute'].set_tooltip('unmute')
            update_volume(0)
        else:
            main_window['mute'].update(image_data=VOLUME_IMG)
            main_window['mute'].set_tooltip('mute')
            update_volume(settings['volume'])
    elif main_event in {'Up:38', 'Down:40', 'Prior:33', 'Next:34'}:
        if not settings['mini_mode']:
            focused_element = main_window.FindElementWithFocus()
            move = {'Up:38': -1, 'Down:40': 1, 'Prior:33': -3, 'Next:34': 3}[main_event]
            if focused_element == main_window['queue']:
                new_i = main_window['queue'].get_list_values().index(main_values['queue'][0]) + move
                new_i = min(max(new_i, 0), len(music_queue) - 1)
                main_window['queue'].update(set_to_index=new_i, scroll_to_index=max(new_i - 3, 0))
            elif focused_element == main_window['pl_tracks']:
                new_i = main_window['pl_tracks'].get_list_values().index(main_values['pl_tracks'][0]) + move
                new_i = min(max(new_i, 0), len(pl_files) - 1)
                main_window['pl_tracks'].update(set_to_index=new_i, scroll_to_index=max(new_i - 3, 0))
    elif main_event == 'queue' and main_value:
        with suppress(ValueError):
            selected_track_index = main_window['queue'].get_list_values().index(main_value[0])
            if done_queue and selected_track_index < len(done_queue):
                while next_queue:  # design decision to empty next queue
                    music_queue.insert(1, next_queue.pop())
                for _ in range(len(done_queue) - selected_track_index):
                    music_queue.insert(0, done_queue.pop())
            else:
                for _ in range(selected_track_index - len(done_queue)):
                    if not music_queue: break
                    done_queue.append(music_queue.pop(0))
                    if next_queue:
                        music_queue.insert(0, next_queue.pop(0))
            if music_queue: play(music_queue[0])
            updated_list = create_track_list()[0]
            dq_len = len(done_queue)
            main_window['queue'].update(values=updated_list, set_to_index=dq_len, scroll_to_index=dq_len)
            reset_progress()
    elif main_event == 'move_up' and main_values['queue']:
        # index_to_move = int(main_values['queue'][0].split('.', 1)[0])
        index_to_move = main_window['queue'].get_list_values().index(main_values['queue'][0])
        new_i = index_to_move - 1
        dq_len = len(done_queue)
        nq_len = len(next_queue)
        if index_to_move < dq_len and new_i >= 0:  # move within dq
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
        elif next_queue and index_to_move > dq_len and index_to_move - dq_len < nq_len:  # within next_queue
            nq_i = new_i - dq_len - 1
            next_queue.insert(nq_i, next_queue.pop(nq_i + 1))
        elif next_queue and index_to_move == dq_len + nq_len + 1:  # moving into next queue
            next_queue.insert(nq_len - 1, music_queue.pop(1))
        elif new_i >= 0:  # moving within mq
            mq_i = new_i - dq_len - nq_len
            music_queue.insert(mq_i, music_queue.pop(mq_i + 1))
        else:
            new_i = max(new_i, 0)
        updated_list = create_track_list()[0]
        main_window['queue'].update(values=updated_list, set_to_index=new_i, scroll_to_index=max(new_i - 7, 0))
    elif main_event == 'move_down' and main_values['queue']:
        index_to_move = main_window['queue'].get_list_values().index(main_values['queue'][0])
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
            updated_list = create_track_list()[0]
            main_window['queue'].update(values=updated_list, set_to_index=new_i, scroll_to_index=max(new_i - 3, 0))
    elif main_event == 'remove_track' and main_values['queue']:
        index_to_remove = main_window['queue'].get_list_values().index(main_values['queue'][0])
        dq_len, nq_len, mq_len = len(done_queue), len(next_queue), len(music_queue)
        if index_to_remove < dq_len:
            done_queue.pop(index_to_remove)
        elif index_to_remove == dq_len:
            # remove the "0. XXXX" track that could be playing right now
            music_queue.pop(0)
            if next_queue: music_queue.insert(0, next_queue.pop(0))
            # if queue is empty but repeat is all AND there are tracks in the done_queue
            if not music_queue and settings['repeat'] is False and done_queue:
                music_queue.extend(done_queue)
                done_queue.clear()
            # start playing new track if and only if we were playing before
            if music_queue and playing_status != 'NOT PLAYING':
                play(music_queue[0])
            else:
                stop('remove_track')
        elif index_to_remove <= nq_len + dq_len:
            next_queue.pop(index_to_remove - dq_len - 1)
        elif index_to_remove < nq_len + mq_len + dq_len:
            music_queue.pop(index_to_remove - dq_len - nq_len)
        updated_list = create_track_list()[0]
        new_i = min(len(updated_list), index_to_remove)
        main_window['queue'].update(values=updated_list, set_to_index=new_i, scroll_to_index=max(new_i - 3, 0))
    elif main_event == 'file_option':
        main_window['file_action'].update(text=main_values['file_option'])
    elif main_event == 'folder_option':
        main_window['folder_action'].update(text=main_values['folder_option'])
    elif main_event == 'file_action':
        Thread(target=file_action, name='FileAction', daemon=True,
               kwargs={'action': main_values['file_option']}).start()
    elif main_event == 'folder_action':
        wx.CallAfter(folder_action, action=main_values['folder_option'])
    elif main_event == 'play_playlist':
        play_playlist(main_values['playlists'])
    elif main_event == 'url_actions':
        activate_play_url()
    elif main_event == 'play_all':
        already_queueing = False
        for thread in threading.enumerate():
            if thread.name in {'QueueAll', 'PlayAll'} and thread.is_alive():
                already_queueing = True
                break
        if not already_queueing: Thread(target=play_all, name='PlayAll', daemon=True).start()
    elif main_event == 'queue_all':
        already_queueing = False
        for thread in threading.enumerate():
            if thread.name in {'QueueAll', 'PlayAll'} and thread.is_alive():
                already_queueing = True
                break
        if not already_queueing: Thread(target=queue_all, name='QueueAll', daemon=True).start()
    elif main_event == 'mini_mode':
        change_settings('mini_mode', not settings['mini_mode'])
        active_windows['main'] = False
        main_window.close()
        activate_main_window()
    elif main_event == 'clear_queue':
        reset_progress()
        main_window['queue'].update(values=[])
        if playing_status in {'PLAYING', 'PAUSED'}: stop('clear queue')
        music_queue.clear()
        next_queue.clear()
        done_queue.clear()
    elif main_event == 'save_queue':
        pl_files = done_queue + ([music_queue[0]] if music_queue else []) + next_queue + music_queue[1:]
        formatted_tracks = [f'{i + 1}. {format_file(path)}' for i, path in enumerate(pl_files)]
        pl_name = ''
        main_window['tab_playlists'].select()
        main_window['playlist_name'].set_focus()
        main_window['playlist_name'].update(value=pl_name)
        main_window['pl_tracks'].update(values=formatted_tracks, set_to_index=0)
    elif main_event == 'play_next':
        play_next()
        main_window.TKroot.focus_force()
    elif main_event == 'locate_track':
        Popen(f'explorer /select,"{fix_path(music_queue[0])}"')
    # elif main_event == 'library':  # TODO
    elif main_event == 'progress_bar':
        if playing_status == 'NOT PLAYING':
            main_window['progress_bar'].update(disabled=True, value=0)
            return
        else:
            new_position = main_values['progress_bar']
            track_position = new_position
            if cast is not None:
                cast.media_controller.seek(new_position)
                playing_status = 'PLAYING'
            else:
                audio_player.set_pos(new_position)
            update_progress_bar_text = True
            track_start = time.time() - track_position
            track_end = track_start + track_length
    # main window settings tab
    elif main_event == 'email':
        Thread(target=webbrowser.open, daemon=True, args=[create_email_url()]).start()
    elif main_event == 'web_gui':
        Thread(target=webbrowser.open, daemon=True, args=[f'http://{get_ipv4()}:{PORT}']).start()
    elif main_event in {'auto_update', 'notifications', 'discord_rpc', 'run_on_startup', 'folder_cover_override',
                        'folder_context_menu', 'shuffle', 'save_window_positions', 'populate_queue_startup',
                        'show_track_number', 'save_queue_sessions', 'flip_main_window', 'vertical_gui',
                        'show_album_art', 'reversed_play_next', 'scan_folders'}:
        change_settings(main_event, main_value)
        if main_event == 'run_on_startup':
            create_shortcut(SHORTCUT_PATH)
        elif main_event == 'save_queue_sessions':
            if main_value: save_queues()
            else: change_settings('queues', {'done': [], 'music': [], 'next': []})
            change_settings('populate_queue_startup', False)
            main_window['populate_queue_startup'].update(value=False)
        elif main_event in 'populate_queue_startup':
            main_window['save_queue_sessions'].update(value=False)
            change_settings('save_queue_sessions', False)
        elif main_event == 'discord_rpc':
            with suppress(Exception):
                if main_value and playing_status in {'PAUSED', 'PLAYING'}:
                    metadata = url_metadata['LIVE'] if playing_live else get_uri_metadata(music_queue[0])
                    title, artist = metadata['title'], get_first_artist(metadata['artist'])
                    rich_presence.connect()
                    rich_presence.update(state=f'By: {artist}', details=title, large_image='default',
                                         large_text='Listening', small_image='logo', small_text='Music Caster')
                elif not main_value:
                    rich_presence.clear()
        elif main_event in {'show_album_art', 'vertical_gui', 'flip_main_window'}:
            # re-render main GUI
            active_windows['main'] = False
            main_window.close()
            activate_main_window('tab_settings')
        elif main_event == 'show_track_number':
            update_gui_queue = True
        elif main_event == 'scan_folders' and main_value:
            index_all_tracks()
    elif main_event == 'remove_music_folder' and main_values['music_dirs']:
        selected_item = main_values['music_dirs'][0]
        if selected_item in music_folders:
            music_folders.remove(selected_item)
            main_window['music_dirs'].update(music_folders)
            refresh_folders()
            save_settings()
            if settings['scan_folders']: index_all_tracks()
    elif main_event == 'add_music_folder':
        main_value = main_value.replace('\\', '/')  # sanitize
        if main_value not in music_folders and os.path.exists(main_value):
            music_folders.append(main_value)
            main_window['music_dirs'].update(music_folders)
            refresh_folders()
            save_settings()
            if settings['scan_folders']: index_all_tracks()
    elif main_event in {'settings_file', 'o:79'}:
        try:
            os.startfile(settings_file)
        except OSError:
            Popen(f'explorer /select,"{fix_path(settings_file)}"')
    elif main_event == 'changelog_file':
        with suppress(FileNotFoundError):
            os.startfile('changelog.txt')
    elif main_event == 'music_dirs':
        with suppress(IndexError):
            Popen(f'explorer "{fix_path(main_values["music_dirs"][0])}"')
    # timer
    elif main_event == 'cancel_timer':
        main_window['timer_text'].update('No Timer Set')
        main_window['timer_text'].metadata = False
        main_window['timer_error'].update(visible=False)
        main_window['cancel_timer'].update(visible=False)
    # TODO: disable/enable submit button
    elif (main_event in {'\r', 'special 16777220', 'special 16777221', 'timer_submit'}
          and not settings['mini_mode'] and main_values['tab_group'] == 'tab_timer'):
        try:
            timer_value: str = main_values['timer_minutes']
            if timer_value.isdigit():
                seconds = abs(float(main_values['timer_minutes'])) * 60
            elif timer_value.count(':') == 1:
                # parse out any PM and AM's
                timer_value = timer_value.strip().upper().replace(' ', '').replace('PM', '').replace('AM', '')
                to_stop = datetime.strptime(timer_value + time.strftime(',%Y,%m,%d,%p'), '%I:%M,%Y,%m,%d,%p')
                current_time = datetime.now()
                current_time = current_time.replace(second=0)
                seconds_delta = (to_stop - current_time).total_seconds()
                if seconds_delta < 0: seconds_delta += 43200  # add 12 hours
                seconds = seconds_delta
            else:
                raise ValueError()
            timer = time.time() + seconds
            timer_set_to = datetime.now().replace(second=0) + timedelta(seconds=seconds)
            if platform.system() == 'Windows':
                timer_set_to = timer_set_to.strftime('%#I:%M %p')
            else:
                timer_set_to = timer_set_to.strftime('%-I:%M %p')  # Linux
            main_window['timer_text'].update(f'Timer set for {timer_set_to}')
            main_window['timer_text'].metadata = True
            main_window['cancel_timer'].update(visible=True)
            main_window['timer_error'].update(visible=False)
        except ValueError:
            for i in range(3):
                main_window['timer_error'].update(visible=True, text_color='#ffcccb')
                main_window.read(10)
                main_window['timer_error'].update(text_color='red')
                main_window.read(10)
    elif main_event in {'shut_down', 'hibernate', 'sleep', 'timer_only_stop'}:
        change_settings('timer_hibernate', main_values['hibernate'])
        change_settings('timer_sleep', main_values['sleep'])
        change_settings('timer_shut_down', main_values['shut_down'])
    # playlist tab
    elif main_event == 'playlist_combo':
        # user selected a playlist from the drop-down
        pl_name = main_value if main_value in playlists else ''
        pl_files = playlists.get(pl_name, []).copy()
        main_window['playlist_name'].update(value=pl_name)
        formatted_tracks = [f'{i + 1}. {format_file(path)}' for i, path in enumerate(pl_files)]
        main_window['pl_tracks'].update(values=formatted_tracks, set_to_index=0)
        main_window['pl_save'].update(disabled=pl_name == '')
        main_window.refresh()
    elif main_event in {'new_pl', 'n:78'}:
        pl_name, pl_files = '', []
        main_window['playlist_name'].update(value=pl_name)
        main_window['playlist_name'].set_focus()
        main_window['pl_tracks'].update(values=pl_files, set_to_index=0)
        main_window['pl_save'].update(disabled=pl_name == '')
        main_window.refresh()
    elif main_event == 'del_pl':
        pl_name = main_values.get('playlist_combo', '')
        if pl_name in playlists:
            del playlists[pl_name]
        playlist_names = tuple(settings['playlists'].keys())
        pl_name = playlist_names[0] if playlist_names else ''
        main_window['playlist_combo'].update(value=pl_name, values=playlist_names)
        pl_files = playlists.get(pl_name, []).copy()
        formatted_tracks = [f'{i + 1}. {format_file(path)}' for i, path in enumerate(pl_files)]
        # update playlist editor
        main_window['playlist_name'].update(value=pl_name)
        main_window['pl_tracks'].update(values=formatted_tracks, set_to_index=0)
        main_window['pl_save'].update(disabled=pl_name == '')
        main_window['play_pl'].update(disabled=pl_name == '')
        main_window['queue_pl'].update(disabled=pl_name == '')
        main_window.refresh()
        save_settings()
        refresh_playlists()
    elif main_event == 'play_pl':
        temp_lst = playlists.get(main_values['playlist_combo'], [])
        if temp_lst:
            done_queue.clear()
            music_queue.clear()
            music_queue.extend(temp_lst)
            if settings['shuffle']: shuffle(music_queue)
            play(music_queue[0])
    elif main_event == 'queue_pl':
        temp_lst = playlists.get(main_values['playlist_combo'], []).copy()
        if settings['shuffle']: shuffle(temp_lst)
        if temp_lst:
            play_after = len(music_queue) == 0
            music_queue.extend(temp_lst)
            if play_after: play(music_queue[0])
            else: update_gui_queue = True
    elif main_event in {'pl_save', 's:83'}:  # save playlist
        if main_values['playlist_name']:
            save_name = main_values['playlist_name']
            if pl_name != save_name:
                # if user is renaming a playlist, remove old data
                if pl_name in playlists: del playlists[pl_name]
                pl_name = save_name
            playlists[pl_name] = pl_files
            # sort playlists alphabetically
            playlists = settings['playlists'] = {k: playlists[k] for k in sorted(playlists.keys())}
            playlist_names = tuple(playlists.keys())
            main_window['playlist_combo'].update(value=pl_name, values=playlist_names, visible=True)
            main_window['play_pl'].update(disabled=False)
            main_window['queue_pl'].update(disabled=False)
            main_window.refresh()
        save_settings()
        refresh_playlists()
    elif main_event == 'playlist_name':
        main_window['pl_save'].update(disabled=main_values['playlist_name'] == '')
    elif main_event in {'pl_rm_items', 'r:82'}:  # remove item from playlist
        if main_values['pl_tracks']:
            pl_items = main_window['pl_tracks'].get_list_values()
            smallest_i = len(pl_items)
            # remove tracks from bottom to top so that we don't have to worry about adjusting other indices
            for item_name in reversed(main_values['pl_tracks']):
                index_to_rm = int(item_name.split('.', 1)[0]) - 1
                if index_to_rm < len(pl_files) and pl_items[index_to_rm] == item_name.split('. ', 1)[1]:
                    if index_to_rm < smallest_i: smallest_i = index_to_rm
                    pl_files.pop(index_to_rm)
            formatted_tracks = [f'{i + 1}. {format_file(path)}' for i, path in enumerate(pl_files)]
            scroll_to_index = max(smallest_i - 3, 0)
            main_window['pl_tracks'].update(formatted_tracks, set_to_index=smallest_i, scroll_to_index=scroll_to_index)
            main_window.refresh()
    elif main_event == 'pl_add_tracks':
        fd = wx.FileDialog(None, 'Select Music File(s)', defaultDir=DEFAULT_FOLDER, wildcard=MUSIC_FILE_TYPES,
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE)
        if fd.ShowModal() != wx.ID_CANCEL:
            file_paths = fd.GetPaths()
            pl_files += [file_path for file_path in file_paths if valid_music_file(file_path)]
            main_window.TKroot.focus_force()
            main_window.normal()
            formatted_tracks = [f'{i + 1}. {format_file(path)}' for i, path in enumerate(pl_files)]
            new_i = len(formatted_tracks) - 1
            main_window['pl_tracks'].update(formatted_tracks, set_to_index=new_i, scroll_to_index=max(new_i - 3, 0))
    elif main_event == 'pl_url_input':
        # disable or enable add URL button if the text in the URL input is almost a valid link
        link = main_values['pl_url_input']
        valid_link = link.count('.') and (link.startswith('http://') or link.startswith('https://'))
        main_window['pl_add_url'].update(disabled=not valid_link)
    elif main_event == 'pl_add_url':
        link = main_values['pl_url_input']
        if link.startswith('http://') or link.startswith('https://'):
            pl_files.append(link)
            formatted_tracks = [f'{i + 1}. {format_file(path)}' for i, path in enumerate(pl_files)]
            new_i = len(formatted_tracks) - 1
            main_window['pl_tracks'].update(formatted_tracks, set_to_index=new_i, scroll_to_index=max(new_i - 3, 0))
        else:
            tray.show_message('Music Caster', "ERROR: invalid url. URL's have to start with http:// or https://")
    elif main_event == 'pl_tracks':
        main_window['pl_move_up'].update(disabled=len(main_value) != 1)
        main_window['pl_move_down'].update(disabled=len(main_value) != 1)
    elif main_event == 'pl_move_up':
        # only allow moving up if 1 item is selected
        if len(main_values['pl_tracks']) == 1:
            to_move = main_window['pl_tracks'].get_list_values().index(main_values['pl_tracks'][0])
            if to_move > 0:
                new_i = to_move - 1
                pl_files.insert(new_i, pl_files.pop(to_move))
                formatted_tracks = [f'{i + 1}. {os.path.basename(path)}' for i, path in enumerate(pl_files)]
                main_window['pl_tracks'].update(values=formatted_tracks, set_to_index=new_i,
                                                scroll_to_index=max(new_i - 3, 0))
    elif main_event == 'pl_move_down':
        # only allow moving down if 1 item is selected
        if len(main_values['pl_tracks']) == 1:
            to_move = main_window['pl_tracks'].get_list_values().index(main_values['pl_tracks'][0])
            if to_move < len(pl_files) - 1:
                new_i = to_move + 1
                pl_files.insert(new_i, pl_files.pop(to_move))
                formatted_tracks = [f'{i + 1}. {os.path.basename(path)}' for i, path in enumerate(pl_files)]
                main_window['pl_tracks'].update(values=formatted_tracks, set_to_index=new_i,
                                                scroll_to_index=max(new_i - 3, 0))
    # other GUI updates
    if time.time() - progress_bar_last_update > 0.5:
        # update progress bar every 0.5 seconds
        progress_bar: Sg.Slider = main_window['progress_bar']
        if playing_status == 'NOT PLAYING':
            progress_bar.update(0, disabled=True)
        elif music_queue:
            with suppress(ZeroDivisionError):
                get_track_position()
                progress_bar.update(track_position, range=(0, track_length), disabled=False)
            update_progress_bar_text = True
            progress_bar_last_update = time.time()
        elif not playing_live:
            playing_status = 'NOT PLAYING'
    if update_progress_bar_text:
        elapsed_time_text, time_left_text = create_progress_bar_text(track_position, track_length)
        main_window['time_elapsed'].update(elapsed_time_text)
        main_window['time_left'].update(time_left_text)
    if playing_status == 'PLAYING' and p_r_button.metadata != 'PLAYING':
        p_r_button.update(image_data=PAUSE_BUTTON_IMG)
    elif playing_status == 'PAUSED' and p_r_button.metadata != 'PAUSED':
        p_r_button.update(image_data=PLAY_BUTTON_IMG)
    elif playing_status == 'NOT PLAYING' and p_r_button.metadata != 'NOT PLAYING':
        if p_r_button.metadata == 'PLAYING': p_r_button.update(image_data=PLAY_BUTTON_IMG)
        main_window['time_elapsed'].update('0:00')
        main_window['time_left'].update('0:00')
    p_r_button.metadata = playing_status
    return True


def read_play_url_window():
    global update_gui_queue
    play_url_event, play_url_values = play_url_window.read(timeout=5)
    if play_url_event in {None, 'Escape:27', 'q'}:
        active_windows['play_url'] = False
        play_url_window.close()
    elif play_url_event in {'\r', 'special 16777220', 'special 16777221', 'Submit'}:
        active_windows['play_url'] = False
        play_url_window.close()
        url_to_play = play_url_values['url']
        if play_url_values['play_immediately'] or not music_queue and not next_queue:
            music_queue.insert(0, url_to_play)
            play(url_to_play)
        elif play_url_values['queue']:
            music_queue.append(url_to_play)
            if len(music_queue) == 1: play(url_to_play)
        else:
            # Add to Next Queue
            if settings['reversed_play_next']:
                next_queue.insert(0, url_to_play)
            else:
                next_queue.append(url_to_play)
        update_gui_queue = True


def create_shortcut(shortcut_path):
    """ creates shortcut if run_on_startup else removes existing shortcut """

    def _create_shortcut():
        app_log.info('create_shortcut called')
        with suppress(com_error):
            shortcut_exists = os.path.exists(shortcut_path)
            if settings['run_on_startup'] and not shortcut_exists:
                # noinspection PyUnresolvedReferences
                pythoncom.CoInitialize()
                _shell = win32com.client.Dispatch('WScript.Shell')
                shortcut = _shell.CreateShortCut(shortcut_path)
                if IS_FROZEN:
                    target = f'{working_dir}\\Music Caster.exe'
                else:
                    target = f'{working_dir}\\music_caster.bat'
                    if os.path.exists(target):
                        with open('music_caster.bat', 'w') as f:
                            f.write(f'pythonw {os.path.basename(sys.argv[0])}')
                    shortcut.IconLocation = f'{working_dir}\\resources\\Music Caster Icon.ico'
                shortcut.Targetpath = target
                shortcut.WorkingDirectory = working_dir
                shortcut.WindowStyle = 1  # 7 - Minimized, 3 - Maximized, 1 - Normal
                shortcut.save()
                if settings.get('DEBUG', False):
                    # removes startup shortcut if running in DEBUG (Python)
                    os.remove(shortcut_path)
            elif not settings['run_on_startup'] and shortcut_exists:
                os.remove(shortcut_path)

    Thread(target=_create_shortcut, name='CreateShortcut').start()


def get_latest_release(ver, force=False):
    """ Returns either False or {ver: cached link to the latest setup} """
    releases_url = 'https://api.github.com/repos/elibroftw/music-caster/releases/latest'
    release = requests.get(releases_url).json()
    latest_ver = release['tag_name'][1:]
    _version = [int(x) for x in ver.split('.')]
    compare_ver = [int(x) for x in latest_ver.split('.')]
    if compare_ver > _version or force:
        for asset in release['assets']:
            # check if setup exists
            if 'exe' in asset['name']:
                return {'version': latest_ver, 'setup': asset['browser_download_url']}
    return False


def auto_update(auto_start=True):
    global update_available
    """
    auto_start is True on Startup, false on exit
    """
    with suppress(requests.ConnectionError):
        app_log.info(f'Function called: auto_update(auto_start={auto_start})')
        release = get_latest_release(VERSION, force=(not IS_FROZEN or settings.get('DEBUG', False)))
        if release:
            latest_ver = release['version']
            setup_dl_link = release['setup']
            app_log.info(f'Update found: v{latest_ver}')
            print('Installer Link:', setup_dl_link)
            if settings.get('DEBUG', False) or not setup_dl_link: return
            if IS_FROZEN and (os.path.exists(UNINSTALLER) or os.path.exists('Updater.exe')):
                if os.path.exists(UNINSTALLER):
                    # only show message on startup to not confuse the user
                    cmd = 'MC_Installer.exe /VERYSILENT /FORCECLOSEAPPLICATIONS /MERGETASKS="!desktopicon"'
                    if auto_start:
                        cmd_args = ' '.join(sys.argv[1:])
                        cmd += f' && "Music Caster.exe" {cmd_args}'  # auto start is True when updating on startup
                        temp_tray = SgWx.SystemTray(menu=[], data_base64=UNFILLED_ICON)
                        temp_tray.show_message('Music Caster', f'Downloading update v{latest_ver}', time=5000)
                        temp_tray.update(tooltip=f'Downloading update v{latest_ver}')
                    else:
                        temp_tray = tray
                    try:
                        download(setup_dl_link, 'MC_Installer.exe')
                        if auto_start:
                            temp_tray.hide()
                            temp_tray.close()
                        Popen(cmd, shell=True)
                    except OSError as _e:
                        if _e.errno == errno.ENOSPC:
                            temp_tray.show_message('Music Caster', 'ERROR: No space left on device to auto-update')
                        if auto_start:
                            temp_tray.hide()
                            temp_tray.close()
                        return False
                    except ConnectionAbortedError:
                        temp_tray.show_message('Music Caster', f'Update v{latest_ver} is available')
                        if auto_start:
                            temp_tray.hide()
                            temp_tray.close()
                        return False
                else:
                    # portable installation
                    try:
                        os.startfile('Updater.exe')
                    except OSError as _e:
                        if _e == errno.ECANCELED:
                            change_settings('auto_update', False)
                        return False
                    time.sleep(2)
                sys.exit()
            else:
                update_available = f'Update v{latest_ver} is available'


def send_info():
    with suppress(requests.ConnectionError):
        mac = hashlib.md5(get_mac().encode()).hexdigest()
        requests.post('https://en3ay96poz86qa9.m.pipedream.net', json={'MAC': mac, 'VERSION': VERSION})


def init_youtube_dl():  # 1 - 1.4 seconds
    global ydl
    app_log.info('Initializing YTDL')
    ydl = YoutubeDL()


def activate_instance(port):
    r_text = ''
    while port <= 2004 and not r_text:
        with suppress(requests.exceptions.InvalidSchema, requests.ConnectionError):
            endpoint = f'http://localhost:{port}'
            if args.exit:  # --exit argument
                r_text = requests.post(f'{endpoint}/exit/').text
            elif args.paths:  # MC was supplied at least one path to a folder/file
                r_text = requests.post(f'{endpoint}/play/', data={'paths': args.paths, 'queue': args.queue}).text
            else:  # neither --exit nor paths was supplied
                r_text = requests.post(f'{endpoint}/').text
        port += 1


try:
    os.remove('music_caster.log')
except FileNotFoundError:
    pass
except PermissionError:
    # music_caster.log being open for write implies that an instance is already running
    if IS_FROZEN:
        activate_instance(PORT)
        sys.exit()
log_format = logging.Formatter('%(asctime)s %(levelname)s (%(lineno)d): %(message)s')
log_handler = RotatingFileHandler('music_caster.log', maxBytes=5242880, backupCount=1, encoding='UTF-8')
log_handler.setFormatter(log_format)
app_log = logging.getLogger('music_caster')
app_log.setLevel(logging.INFO)
app_log.addHandler(log_handler)
app_log.propagate = False  # disable console output
try:
    # if an instance is already running, open that one's GUI and exit this instance
    if is_already_running(threshold=1 if os.path.exists(UNINSTALLER) else 2):
        app_log.info('Another instance of Music Caster was found')
        activate_instance(PORT)
        if IS_FROZEN and not DEBUG: sys.exit()
    # quit if --exit was supplied to command line
    if args.exit: sys.exit()
    load_settings()  # starts indexing all tracks
    init_ydl_thread = Thread(target=init_youtube_dl, daemon=True, name='InitYoutubeDL')
    init_ydl_thread.start()
    audio_player = AudioPlayer()
    # check for update and update if no starting arguments were supplied or if the update flag was used
    if len(sys.argv) == 1 and settings['auto_update'] or args.update: auto_update()
    if not settings.get('DEBUG', False): Thread(target=send_info, daemon=True, name='SendInfo').start()
    # Access startup folder by entering "Startup" in Explorer address bar
    startup_dir = shell.SHGetFolderPath(0, (shellcon.CSIDL_STARTUP, shellcon.CSIDL_COMMON_STARTUP)[0], None, 0)
    SHORTCUT_PATH = f"{startup_dir}\\Music Caster{' (DEBUG)' if settings.get('DEBUG', False) else ''}.lnk"
    create_shortcut(SHORTCUT_PATH)
    # set file handlers only if installed from Setup (Not a portable installation)
    if os.path.exists(UNINSTALLER):
        add_reg_handlers(f'{working_dir}/Music Caster.exe', add_folder_context=settings['folder_context_menu'])
    with suppress(FileNotFoundError, OSError):
        os.remove('MC_Installer.exe')
    rmtree('Update', ignore_errors=True)
    # find a port to bind to
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.05)
        while True:
            if not s.connect_ex(('localhost', PORT)) == 0:  # if port is not occupied
                try:  # start server with the unoccupied PORT
                    server_kwargs = {'host': '0.0.0.0', 'port': PORT, 'threaded': True}
                    Thread(target=app.run, name='FlaskServer', daemon=True, kwargs=server_kwargs).start()
                    break
                except OSError:
                    PORT += 1
            else:
                PORT += 1
    print(f'Running on http://localhost:{PORT}/')
    repeat_menu = [f'Repeat All {CHECK_MARK}' if settings['repeat'] is False else 'Repeat All',
                   f'Repeat One {CHECK_MARK}' if settings['repeat'] else 'Repeat One',
                   f'Repeat Off {CHECK_MARK}' if settings['repeat'] is None else 'Repeat Off']
    tray_menu_default = ['', ['Settings', 'Rescan Library', 'Refresh Devices', 'Select Device', device_names,
                              'Timer', ['Set Timer', 'Cancel Timer'], 'Play',
                              ['Live System Audio', 'URL', ['Play URL', 'Queue URL', 'Play URL Next'],
                               'Folders', tray_folders,
                               'Playlists', tray_playlists, 'Play File(s)', 'Play All'], 'Exit']]
    tray_menu_playing = ['', ['Settings', 'Rescan Library', 'Refresh Devices', 'Select Device', device_names,
                              'Timer', ['Set Timer', 'Cancel Timer'], 'Controls',
                              ['Locate Track', 'Repeat Options', repeat_menu, 'Stop', 'Previous Track', 'Next Track',
                               'Pause'], 'Play',
                              ['Live System Audio', 'URL', ['Play URL', 'Queue URL', 'Play URL Next'],
                               'Folders', tray_folders,
                               'Playlists', tray_playlists, 'Play File(s)', 'Play File Next', 'Play All'], 'Exit']]
    tray_menu_paused = ['', ['Settings', 'Rescan Library', 'Refresh Devices', 'Select Device', device_names,
                             'Timer', ['Set Timer', 'Cancel Timer'], 'Controls',
                             ['Locate Track', 'Repeat Options', repeat_menu, 'Stop', 'Previous Track', 'Next Track',
                              'Resume'], 'Play',
                             ['Live System Audio', 'URL', ['Play URL', 'Queue URL', 'Play URL Next'],
                              'Folders', tray_folders,
                              'Playlists', tray_playlists, 'Play File(s)', 'Play File Next', 'Play All'], 'Exit']]
    keyboardListener = pynput.keyboard.Listener(on_press=on_press, on_release=on_release)  # daemon=True by default
    keyboardListener.start()
    rich_presence = pypresence.Presence(MUSIC_CASTER_DISCORD_ID)
    if settings['discord_rpc']:
        with suppress(Exception): rich_presence.connect()
    init_ydl_thread.join()
    tooltip = 'Music Caster [DEBUG]' if settings.get('DEBUG', False) else 'Music Caster'
    tray = SgWx.SystemTray(menu=tray_menu_default, data_base64=UNFILLED_ICON, tooltip=tooltip)
    if settings['notifications']:
        if settings['update_message'] == '':
            welcome_msg = 'Thanks for installing Music Caster.\nMusic Caster is running in the tray.'
            tray.show_message('Music Caster', welcome_msg, time=5000)
        elif settings['update_message'] != UPDATE_MESSAGE:
            tray.show_message('Music Caster Updated', UPDATE_MESSAGE, time=5000)
        if update_available and IS_FROZEN:
            tray.show_message('Music Caster', update_available, time=5000)
    change_settings('update_message', UPDATE_MESSAGE)
    temp = (settings['timer_shut_down'], settings['timer_hibernate'], settings['timer_sleep'])
    if temp.count(True) > 1:  # Only one of the below can be True
        if settings['timer_shut_down']: change_settings('timer_hibernate', False)
        change_settings('timer_sleep', False)
    if settings['save_queue_sessions'] and settings['populate_queue_startup']:  # mutually exclusive
        change_settings('populate_queue_startup', False)
    cast_last_checked = time.time()
    Thread(target=background_tasks, daemon=True, name='BackgroundTasks').start()
    Thread(target=start_chromecast_discovery, daemon=True, name='CCDiscovery').start()
    if args.paths:
        # wait until previous device has been found or if it hasn't been found
        while all((settings['previous_device'], cast is None, stop_discovery)): time.sleep(0.3)
        play_paths(args.paths, queue_only=args.queue)
    elif settings['save_queue_sessions']:
        for queue_name in ('done', 'music', 'next'):
            queue = {'done': done_queue, 'music': music_queue, 'next': next_queue}[queue_name]
            for file in settings['queues'].get(queue_name, []):
                if valid_music_file(file):
                    queue.append(file)
                    files_to_scan.put(file)
    elif settings['populate_queue_startup']:
        indexing_tracks_thread.join()
        play_all(queue_only=True)
    print(f'Running in tray, DEBUG={settings.get("DEBUG", False) or DEBUG}, EXPERIMENTAL={settings["EXPERIMENTAL"]}')
    tray_actions = {
        '__ACTIVATED__': activate_main_window,
        'Rescan Library': index_all_tracks,
        'Refresh Devices': lambda: Thread(target=start_chromecast_discovery, daemon=True, name='CCDiscovery').start(),
        # isdigit should be an if statement
        'Settings': lambda: activate_main_window('tab_settings'),
        'Create/Edit a Playlist': lambda: activate_main_window('tab_playlists'),
        # PL should be an if statement
        'Set Timer': lambda: activate_main_window('tab_timer'),
        'Cancel Timer': cancel_timer,
        'Live System Audio': stream_live_audio,
        'Play URL': activate_play_url,
        'Queue URL': lambda: activate_play_url('Queue'),
        'Play URL Next': lambda: activate_play_url('Play Next'),
        'Play File(s)': lambda: Thread(target=file_action, daemon=True, name='PlayFile').start(),
        'Play All': play_all,
        'Play File Next': lambda: Thread(target=play_next, name='PlayNext', daemon=True).start(),
        'Pause': pause,
        'Resume': resume,
        'Next Track': next_track,
        'Previous Track': prev_track,
        'Stop': lambda: stop('tray'),
        'web_play_files': lambda: 'pass',
        'Repeat One': lambda: change_settings('repeat', True),
        'Repeat All': lambda: change_settings('repeat', False),
        'Repeat Off': lambda: change_settings('repeat', None),
        'Locate Track': locate_track,
        'Exit': exit_program,
        'Bring to Front': bring_to_front,
        '': lambda: None,
    }
    while True:
        tray_item = tray.Read(timeout=1 if any(active_windows.values()) else 100)
        tray_actions.get(tray_item, lambda: other_tray_actions(tray_item))()
        while not daemon_commands.empty():
            daemon_command = daemon_commands.get()
            tray_actions.get(daemon_command, lambda: other_tray_actions(daemon_command))()
            daemon_commands.task_done()
        if active_windows['main']: read_main_window()
        if active_windows['play_url']: read_play_url_window()
except Exception as e:
    handle_exception(e, True)
