import base64
import os
import platform
from contextlib import suppress
from datetime import datetime, timedelta
# noinspection PyUnresolvedReferences
import encodings.idna  # DO NOT REMOVE
import io
from glob import glob
import json
import logging
from math import floor
from pathlib import Path
import pprint
from shutil import copyfile, copyfileobj
from random import shuffle
from subprocess import Popen
import sys
import socket
import shutil
import threading
import time
import traceback
import urllib.parse
import webbrowser
import zipfile
import pythoncom
# noinspection PyPackageRequirements
from youtube_dl import YoutubeDL
# helper files
from helpers import fix_path, get_ipv4, get_mac, create_qr_code, valid_music_file, create_play_url_window,\
    is_already_running, find_chromecasts, create_songs_list, create_main_gui, create_settings, create_timer,\
    create_playlist_editor, create_playlist_selector, bg, BUTTON_COLOR, get_youtube_id, timing, MUSIC_FILE_TYPES
import helpers
from b64_images import *
# 3rd party imports
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request, redirect, send_file
import mutagen
import mutagen.id3
# noinspection PyProtectedMember
from mutagen.id3 import ID3NoHeaderError
# noinspection PyProtectedMember
from mutagen.mp3 import HeaderNotFoundError
import mutagen.mp3
import mutagen.mp4
from mutagen.easyid3 import EasyID3
from mutagen.easymp4 import EasyMP4
from mutagen.aac import AAC
# from PIL import Image
import PySimpleGUI as Sg
import PySimpleGUIWx as SgWx
import wx
import pychromecast.controllers.media
from pychromecast.error import UnsupportedNamespace, NotConnected
from pychromecast.config import APP_MEDIA_RECEIVER
import pychromecast
from pygame import mixer as local_music_player
# noinspection PyPep8Naming
from pygame import error as PygameError
import pynput.keyboard
import pypresence
import requests
from uuid import uuid4
from wavinfo import WavInfoReader  # until mutagen supports .wav
import win32com.client
import winshell


# TODO: Refactoring. Move all constants and functions to before the try-except
VERSION = '4.49.5'
MUSIC_CASTER_DISCORD_ID = '696092874902863932'
EMAIL = 'elijahllopezz@gmail.com'
UPDATE_MESSAGE = """
[Feature] Added do nothing to timer
"""
PORT, WAIT_TIMEOUT, IS_FROZEN = 2001, 10, getattr(sys, 'frozen', False)
MC_SECRET = str(uuid4())
show_pygame_error = variable_exception_sent = update_devices = open_pl_selector = update_progress_text = False
settings_last_modified, last_press = 0, time.time()
active_windows = {'main': False, 'settings': False, 'timer': False, 'playlist_selector': False,
                  'playlist_editor': False, 'play_url': False}
main_window = settings_window = timer_window = pl_editor_window = pl_selector_window = play_url_window = None
main_last_event = settings_last_event = pl_editor_last_event = None
cast = None
stop_discovery = None  # function
playlists, tray_playlists, tray_folders = {}, ['Create/Edit a Playlist'], []
music_directories, notifications_enabled, window_locations = [], True, {}
all_songs, all_folders, pl_name, pl_files = {}, ['PF: Select Folder(s)'], '', []
mouse_hover = daemon_command = ''
new_playing_text, timer = 'Nothing Playing', 0
chromecasts, device_names = [], ['✓ Local device']
starting_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
os.chdir(starting_dir)
home_music_dir = f'{Path.home()}/Music'
settings_file = f'{starting_dir}/settings.json'
settings = {  # default settings
    'previous_device': None, 'window_locations': {}, 'update_message': '', 'EXPERIMENTAL': False,
    'auto_update': False, 'run_on_startup': True, 'notifications': True, 'shuffle_playlists': True, 'repeat': False,
    'discord_rpc': False, 'save_window_positions': True, 'default_file_handler': True,
    'accent_color': '#00bfff', 'text_color': '#aaaaaa', 'button_text_color': '#000000', 'background_color': '#121212',
    'volume': 100, 'timer_shut_off_computer': False, 'timer_hibernate_computer': False, 'timer_sleep_computer': False,
    'volume_delta': 5, 'muted': False, 'scrubbing_delta': 5, 'music_directories': [home_music_dir], 'playlists': {}}
with suppress(FileNotFoundError, OSError): os.remove('MC_Installer.exe')
shutil.rmtree('Update', ignore_errors=True)


def save_json():
    global settings, settings_file
    with open(settings_file, 'w') as outfile:
        json.dump(settings, outfile, indent=4)


def refresh_folders():
    tray_folders.clear()
    tray_folders.append('PF: Select Folder(s)')
    for music_dir in music_directories:
        music_dir = music_dir.replace('\\', '/').split('/')
        music_dir = f'PF: .../{"/".join(music_dir[-2:])}' if len(music_dir) > 2 else 'PF: ' + '/'.join(music_dir)
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
    save_json()
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
            main_window['repeat'].is_repeating = repeat_setting
            main_window['repeat'].Update(image_data=repeat_img)
            main_window['repeat'].SetTooltip(new_tooltip)
        if settings['notifications']:
            if new_value is None: tray.ShowMessage('Music Caster', 'Repeat set to Off')
            elif new_value: tray.ShowMessage('Music Caster', 'Repeat set to One')
            else: tray.ShowMessage('Music Caster', 'Repeat set to All')
    return new_value


def update_volume(new_vol):
    """new_vol: float[0, 100]"""
    new_vol = new_vol / 100
    if cast is None:  local_music_player.music.set_volume(new_vol)
    else: cast.set_volume(new_vol)


def cycle_repeat():
    global settings
    if settings['repeat'] is None: _repeat_setting = False  # Repeat All
    elif settings['repeat']: _repeat_setting = None  # Repeat OFF
    else: _repeat_setting = True  # Repeat One
    return change_settings('repeat', _repeat_setting)


def handle_exception(exception, restart_program=False):
    if settings.get('DEBUG', False) and not IS_FROZEN: raise exception
    _current_time = str(datetime.now())
    trace_back_msg = traceback.format_exc()
    exc_type, exc_obj, exc_tb = sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2]
    mac = get_mac()
    payload = {'VERSION': VERSION, 'EXCEPTION TYPE': exc_type.__name__, 'LINE NUMBER': exc_tb.tb_lineno,
               'TRACEBACK': fix_path(trace_back_msg), 'MAC': mac, 'FATAL': restart_program,
               'OS': platform.platform(), 'TIME': _current_time}
    with suppress(requests.ConnectionError):
        requests.post('https://enmuvo35nwiw.x.pipedream.net', json=payload)
    try:
        with open(f'{starting_dir}/error.log', 'r') as _f:
            content = f.read()
    except (FileNotFoundError, ValueError):
        content = ''
    with open(f'{starting_dir}/error.log', 'w') as _f:
        _f.write(pprint.pformat(payload))
        _f.write('\n')
        _f.write(content)
    if restart_program:
        tray.ShowMessage('Music Caster Error', 'An error has occurred, restarting now')
        time.sleep(5)
        stop()
        os.chdir(starting_dir)
        if IS_FROZEN: os.startfile('Music Caster.exe')
        sys.exit()


def get_metadata(file_path: str) -> tuple:  # title, artist, album
    global variable_exception_sent
    file_path = file_path.lower()
    _title, _artist, _album = 'Unknown Title', 'Unknown Artist', 'Unknown Album'
    try:
        if file_path.endswith('.mp3'): audio = EasyID3(file_path)
        elif file_path.endswith('.m4a') or file_path.endswith('.mp4'): audio = EasyMP4(file_path)
        elif file_path.endswith('.wav'):
            a = WavInfoReader(file_path).info.to_dict()
            audio = {'title': [a['title']], 'artist': [a['artist']], 'album': [a['product']]}
        elif file_path.endswith('.wma'): audio = {'title': [_title], 'artist': [_artist], 'album': [_album]}
        else: audio = mutagen.File(file_path)
        _title = audio.get('title', ['Unknown Title'])[0]
        _artist = ', '.join(audio.get('artist', ['Unknown Artist']))
        _album = audio.get('album', ['Unknown Album'])[0]
    except (ID3NoHeaderError, HeaderNotFoundError): pass
    except Exception as _e:
        if variable_exception_sent:
            handle_exception(_e)
            variable_exception_sent = True
    return _title, _artist, _album


def compile_all_songs(update_global=True, ignore_files: list = None) -> dict:
    # TODO: instead of calling this function, thread it and
    #  call .join() if you need to use all_songs
    #  and use a lock
    # song_compilation_lock = threading.Lock()
    global all_songs
    if ignore_files is None: ignore_files = []
    if not update_global:
        temp_songs = all_songs.copy()
        if ignore_files:
            for _file in ignore_files:
                file_info = get_metadata(_file)[:2]
                temp_songs.pop(' - '.join(file_info), None)
        return temp_songs
    all_songs.clear()
    for directory in music_directories:
        for _file in glob(f'{directory}/**/*.*', recursive=True):
            _file = _file.replace('\\', '/')
            if _file not in ignore_files and valid_music_file(_file):
                file_info = ' - '.join(get_metadata(_file)[:2])
                all_songs[file_info] = _file
    return all_songs


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
            save_json()
    window.TKroot.bind('<Destroy>', save_window_position)


def load_settings():
    """load (and fix if needed) the settings file"""
    global settings, playlists, notifications_enabled, music_directories,\
        DEFAULT_DIR, settings_last_loaded, window_locations
    if os.path.exists(settings_file):
        with open(settings_file) as json_file:
            try: loaded_settings = json.load(json_file)
            except json.decoder.JSONDecodeError: loaded_settings = {}
            save_settings = False
            for setting_name, setting_value in tuple(loaded_settings.items()):
                loaded_settings[setting_name.replace(' ', '_')] = loaded_settings.pop(setting_name)
            for setting_name, setting_value in settings.items():
                if setting_name not in loaded_settings:
                    loaded_settings[setting_name] = setting_value
                    save_settings = True
            settings = loaded_settings
            playlists = settings['playlists']
            tray_playlists.clear()  # global variable
            tray_playlists.append('Create/Edit a Playlist')
            tray_playlists.extend([f'PL: {pl}' for pl in playlists.keys()])
            notifications_enabled = settings['notifications']
            _temp = music_directories.copy()
            music_directories = settings['music_directories']
            window_locations = settings['window_locations']
            if not music_directories: music_directories = change_settings('music_directories', [home_music_dir])
            if _temp != music_directories or music_directories == [home_music_dir]:
                compile_all_songs()
                refresh_folders()
            DEFAULT_DIR = music_directories[0]
        if save_settings: save_json()
    else: save_json()
    settings_last_loaded = time.time()


def create_shortcut(_shortcut_path):
    def _threaded():
        try:
            run_on_startup = settings['run_on_startup']
            shortcut_exists = os.path.exists(_shortcut_path)
            if run_on_startup and not shortcut_exists:
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
            elif not run_on_startup and shortcut_exists:
                os.remove(_shortcut_path)
        except Exception as _e:
            handle_exception(_e)
    if not settings.get('DEBUG', False): threading.Thread(target=_threaded, daemon=True).start()


def send_info():
    with suppress(requests.exceptions.ConnectionError):
        current_time = datetime.now().strftime('%m/%d/%Y %H:%M:%S')
        requests.post('https://en3ay96poz86qa9.m.pipedream.net',
                      json={'MAC': get_mac(), 'VERSION': VERSION, 'TIME': current_time})


def init_pygame():
    global show_pygame_error
    try: local_music_player.init(44100, -16, 2, 2048)
    except PygameError: show_pygame_error = True


load_settings_thread = threading.Thread(target=load_settings, daemon=True)
load_settings_thread.start()
init_pygame_thread = threading.Thread(target=init_pygame, daemon=True)
init_pygame_thread.start()
exit_program = False
if is_already_running():  # ~0.8 seconds
    r_text, exit_program = '', True
    while PORT <= 2005 and not r_text:
        with suppress(requests.exceptions.InvalidSchema):
            if len(sys.argv) > 1:  # music file was opened with MC
                r_text = requests.post(f'http://127.0.0.1:{PORT}/play/', data={'path': sys.argv[1]}).text
            else: r_text = requests.get(f'http://127.0.0.1:{PORT}/instance/').text
        PORT += 1
load_settings_thread.join()
if exit_program and not settings.get('DEBUG', False): sys.exit()
try:
    if settings['auto_update']:
        with suppress(requests.ConnectionError):
            releases_url = 'https://github.com/elibroftw/music-caster/releases'
            soup = BeautifulSoup(requests.get(releases_url).text, features='html.parser')
            release_entries = soup.find_all('div', class_='release-entry')
            for entry in release_entries:
                latest_ver = entry.find('a', class_='muted-link css-truncate')['title'][1:]
                release_type = entry.find('span').text.strip()
                if release_type == 'Latest release' or settings.get('EXPERIMENTAL', False): break
            major, minor, patch = (int(x) for x in VERSION.split('.'))
            latest_major, latest_minor, latest_patch = (int(x) for x in latest_ver.split('.'))
            if (latest_major > major or latest_major == major and latest_minor > minor
                    or latest_major == major and latest_minor == minor and latest_patch > patch):
                details = entry.find('details',
                                     class_='details-reset Details-element border-top pt-3 mt-4 mb-2 mb-md-4')
                download_links = [link['href'] for link in details.find_all('a') if link.get('href')]
                setup_download_link = f'https://github.com{download_links[0]}'
                os.chdir(starting_dir)
                tray = SgWx.SystemTray(menu=['File', []], data_base64=UNFILLED_ICON, tooltip='Music Caster')
                if settings.get('DEBUG'):
                    print('Installer Link:', setup_download_link)
                elif IS_FROZEN and os.path.exists('unins000.exe') or os.path.exists('Updater.exe'):
                    tray.ShowMessage('Music Caster', f'Downloading update v{latest_ver}')
                    tray.Update(tooltip=f'Downloading update v{latest_ver}')
                    exit_program = True
                    if os.path.exists('unis000.exe'):
                        download(setup_download_link, 'MC_Installer.exe')
                        Popen(f'MC_Installer.exe /VERYSILENT /FORCECLOSEAPPLICATIONS /MERGETASKS="!desktopicon"')
                    else:
                        try:
                            time.sleep(2)
                            os.startfile('Updater.exe')
                        except FileNotFoundError:
                            change_settings('auto_update', False)
                            exit_program = False
                    tray.Hide()
                    if exit_program: sys.exit()
                tray.ShowMessage('Music Caster', f'Update v{latest_ver} Available')
                time.sleep(2)
                tray.Close()
except Exception as e:
    handle_exception(e)


# TODO: Set as default music file handler (See MODIFY REGISTRY in helpers.py)
helpers.ACCENT_COLOR, helpers.fg = settings['accent_color'], settings['text_color']
helpers.bg = settings['background_color']
helpers.BUTTON_COLOR = (settings['button_text_color'], helpers.ACCENT_COLOR)
Sg.SetOptions(button_color=BUTTON_COLOR, scrollbar_color=bg, background_color=bg, element_background_color=bg,
              text_element_background_color=bg)
app = Flask(__name__)


# use socket io?
@app.route('/')
def home():  # web GUI
    global music_queue, playing_status, all_songs, daemon_command
    if request.args:
        if 'play' in request.args:
            if playing_status == 'PAUSED': resume()
            elif music_queue: play_file(music_queue[0])
            else: play_all()
        elif 'pause' in request.args and playing_status == 'PLAYING': pause()
        elif 'next' in request.args: daemon_command = 'Next Song'
        elif 'prev' in request.args: daemon_command = 'Previous Song'
        elif 'repeat' in request.args:
            cycle_repeat()
        elif 'shuffle' in request.args:
            change_settings('shuffle', not settings['shuffle'])
        return redirect('/')
    _metadata = {'artist': 'N/A', 'title': 'Nothing Playing', 'album': 'N/A'}
    if playing_status in {'PLAYING', 'PAUSED'}:
        with suppress(KeyError, IndexError):
            _metadata = music_meta_data[music_queue[0]]
    art = _metadata.get('art', DEFAULT_IMG_DATA)
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
    _queue = create_songs_list(music_queue, done_queue, next_queue)[0]
    return render_template('home.html', device_name=platform.node(), shuffle=shuffle_option, settings=settings, art=art,
                           main_button='pause' if playing_status == 'PLAYING' else 'play', repeat_color=repeat_color,
                           repeat_option=repeat_option, queue=_queue, metadata=_metadata, list_of_songs=list_of_songs)


@app.route('/play/', methods=['GET', 'POST'])
def play_file_page():
    global music_queue, playing_status
    args = request.args if request.method == 'GET' else request.form
    if 'path' in args:
        _file_or_dir = args['path']
        if os.path.isfile(_file_or_dir) and valid_music_file(_file_or_dir):
            play_all([_file_or_dir])
        elif os.path.isdir(_file_or_dir):
            play_folder([_file_or_dir])
    return redirect('/') if request.method == 'GET' else 'true'


@app.route('/metadata/')
def metadata():
    if music_queue:
        file_path = music_queue[0]
        _metadata = music_meta_data[file_path]
    else:
        _metadata = {'artist': 'N/A', 'title': 'Nothing Playing', 'album': 'N/A'}
    return jsonify(_metadata)


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


@app.route('/instance/')
def instance():
    global daemon_command
    for k, v in active_windows.items():  # Opens up GUI
        if v:
            {'main': main_window,
             'settings': settings_window,
             'timer': timer_window,
             'playlist_selector': pl_selector_window,
             'playlist_editor': pl_editor_window,
             'play_url': play_url_window}[k].bring_to_front()
            return 'true'
    daemon_command = '__ACTIVATED__'
    return 'true'


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


def chromecast_callback(chromecast):
    global update_devices, cast, chromecasts
    previous_device = settings['previous_device']
    if str(chromecast.uuid) == previous_device and cast != chromecast:
        cast = chromecast
        cast.wait(timeout=WAIT_TIMEOUT)
    if chromecast.uuid not in [_cc.uuid for _cc in chromecasts]:
        chromecasts.append(chromecast)
        chromecasts.sort(key=lambda _cc: (_cc.name, _cc.uuid))
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
    stop_discovery = find_chromecasts(callback=chromecast_callback)
    # stop_discovery = pychromecast.get_chromecasts(blocking=False, callback=chromecast_callback)
    time.sleep(10.1)
    stop_discovery()
    if not device_names: device_names.append(f'✓ Local device')
    refresh_tray()


try:
    if not settings.get('DEBUG', False): threading.Thread(target=send_info, daemon=True).start()
    # Access startup folder by entering "Startup" in Explorer address bar
    SHORTCUT_PATH = f'{winshell.startup()}\\Music Caster.lnk'
    create_shortcut(SHORTCUT_PATH)
    temp = (settings['timer_shut_off_computer'], settings['timer_hibernate_computer'], settings['timer_sleep_computer'])
    if temp.count(True) > 1:  # Only one of the below can be True
        if settings['timer_shut_off_computer']: change_settings('timer_hibernate_computer', False)
        change_settings('timer_sleep_computer', False)

    thumbs_dir = f'{starting_dir}/images'
    if not os.path.exists(thumbs_dir): os.mkdir(thumbs_dir)
    if not os.path.exists(f'{thumbs_dir}/default.png'):  # in case the user decided to delete the default image
        if os.path.exists('resources/default.png'):  # running from source code
            copyfile('resources/default.png', 'images/default.png')
        else:  # download the default image
            with suppress(requests.ConnectionError):
                default_img = 'https://raw.githubusercontent.com/elibroftw/music-caster/master/resources/default.png'
                response = requests.get(default_img, stream=True)
                with open(f'{thumbs_dir}/default.png', 'wb') as f: copyfileobj(response.raw, f)
    for file in glob(f'{thumbs_dir}/*.*'):
        if not file.endswith('default.png'): os.remove(file)
    with open(f'{thumbs_dir}/default.png', 'rb') as f:
        DEFAULT_IMG_DATA = base64.b64encode(f.read())
        DEFAULT_IMG_DATA = f'data:image/png;base64,{DEFAULT_IMG_DATA.decode()}'
    logging.getLogger('werkzeug').disabled = True
    os.environ['WERKZEUG_RUN_MAIN'] = 'true'
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.1)
        while True:
            if not s.connect_ex(('localhost', PORT)) == 0:  # if port is not occupied
                try:  # start server with the unoccupied PORT
                    server_kwargs = {'host': '0.0.0.0', 'port': PORT, 'threaded': True}
                    threading.Thread(target=app.run, daemon=True, kwargs=server_kwargs).start()
                    break
                except OSError: PORT += 1
            else: PORT += 1

    repeat_setting = settings['repeat']
    repeat_menu = ['Repeat All ✓' if repeat_setting is False else 'Repeat All',
                   'Repeat One ✓' if repeat_setting else 'Repeat One',
                   'Repeat Off ✓' if repeat_setting is None else 'Repeat Off']

    if settings['EXPERIMENTAL']:
        menu_def_1 = ['', ['Settings', 'Refresh Devices', 'Select Device', device_names,
                           'Timer', ['Set Timer', 'Cancel Timer'], 'Play',
                           ['URL', 'Folders', tray_folders, 'Playlists', tray_playlists, 'Play File(s)', 'Play All'],
                           'Exit']]
        menu_def_2 = ['', ['Settings', 'Refresh Devices', 'Select Device', device_names,
                           'Timer', ['Set Timer', 'Cancel Timer'], 'Play',
                           ['URL', 'Folders', tray_folders, 'Playlists', tray_playlists, 'Play File(s)',
                            'Play File Next', 'Play All'], 'Controls',
                           ['Locate File', 'Repeat Options', repeat_menu, 'Stop', 'Previous Song', 'Next Song',
                            'Pause'], 'Exit']]
        menu_def_3 = ['', ['Settings', 'Refresh Devices', 'Select Device', device_names,
                           'Timer', ['Set Timer', 'Cancel Timer'], 'Play',
                           ['URL', 'Folders', tray_folders, 'Playlists', tray_playlists, 'Play File(s)',
                            'Play File Next', 'Play All'], 'Controls',
                           ['Locate File', 'Repeat Options', repeat_menu, 'Stop', 'Previous Song', 'Next Song',
                            'Resume'], 'Exit']]
    else:
        menu_def_1 = ['', ['Settings', 'Refresh Devices', 'Select Device', device_names,
                           'Timer', ['Set Timer', 'Cancel Timer'], 'Play',
                           ['Folders', tray_folders, 'Playlists', tray_playlists, 'Play File(s)', 'Play All'], 'Exit']]
        menu_def_2 = ['', ['Settings', 'Refresh Devices', 'Select Device', device_names,
                           'Timer', ['Set Timer', 'Cancel Timer'], 'Play',
                           ['Folders', tray_folders, 'Playlists', tray_playlists, 'Play File(s)', 'Play File Next',
                            'Play All'], 'Controls',
                           ['Locate File', 'Repeat Options', repeat_menu, 'Stop', 'Previous Song', 'Next Song',
                            'Pause'], 'Exit']]
        menu_def_3 = ['', ['Settings', 'Refresh Devices', 'Select Device', device_names,
                           'Timer', ['Set Timer', 'Cancel Timer'], 'Play',
                           ['Folders', tray_folders, 'Playlists', tray_playlists, 'Play File(s)', 'Play File Next',
                            'Play All'], 'Controls',
                           ['Locate File', 'Repeat Options', repeat_menu, 'Stop', 'Previous Song', 'Next Song',
                            'Resume'], 'Exit']]

    tooltip = 'Music Caster [DEBUG]' if settings.get('DEBUG', False) else 'Music Caster'
    tray = SgWx.SystemTray(menu=menu_def_1, data_base64=UNFILLED_ICON, tooltip=tooltip)
    init_pygame_thread.join()
    if settings.get('notifications') and show_pygame_error:
        tray.ShowMessage('Music Caster Error', 'No local audio device found')
    if settings['update_message'] != UPDATE_MESSAGE:
        if notifications_enabled:
            tray.ShowMessage('Music Caster Updated', UPDATE_MESSAGE)
        change_settings('update_message', UPDATE_MESSAGE)
    if notifications_enabled:
        tray.ShowMessage('Music Caster', 'Music Caster is running in the tray', time=500)
    if not music_directories:
        music_directories = change_settings('music_directories', [home_music_dir])
        compile_all_songs()
    DEFAULT_DIR = music_directories[0]
    music_queue, done_queue, next_queue = [], [], []
    music_meta_data = {}  # file: {artist: str, title: str}
    song_end = song_length = song_start = 0  # seconds but using time()
    progress_bar_last_update = song_position = 0  # also seconds but relative to length of song
    mc, playing_status, time_left = None, 'NOT PLAYING', 0
    playing_url = False
    settings_last_loaded = cast_last_checked = time.time()
    rich_presence = pypresence.Presence(MUSIC_CASTER_DISCORD_ID)
    with suppress(pypresence.InvalidPipe, RuntimeError): rich_presence.connect()
    threading.Thread(target=start_chromecast_discovery, daemon=True).start()

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

    def play_url(url):
        global cast, mc, playing_url, playing_status
        if cast is not None:
            video_id = get_youtube_id(url)  # check if youtube video
            if video_id is not None:  # Youtube Video
                ydl = YoutubeDL()
                r = ydl.extract_info(url, download=False)
                formats = [_f for _f in r['formats'] if _f['acodec'] != 'none' and _f['vcodec'] != 'none']
                try:
                    formats.sort(key=lambda _f: _f['width'])
                    cast.wait()
                    mc = cast.media_controller
                    _f = formats[0]
                    mc.play_media(_f['url'], f'video/{_f["ext"]}')
                    mc.block_until_active()
                    playing_url = True
                    playing_status = 'PLAYING'
                    if r['track'] and r['artist']:
                        _title, _artist = r['track'], r['artist'].split(', ', 1)[0]
                        playing_text = f'{_artist} - {_title}'
                    else:
                        _title, _artist = r['title'], r['uploader']
                        playing_text = f'{_artist} - {_title}'
                    if notifications_enabled:
                        tray.ShowMessage('Music Caster', 'Playing: ' + playing_text, time=500)
                    # tray.Update(menu=menu_def_2, data_base64=FILLED_ICON, tooltip=playing_text)
                    # TODO: song_length, song_end, song_start

                    if settings['discord_rpc']:
                        with suppress(AttributeError, pypresence.InvalidID):
                            rich_presence.update(state=f'By: {_artist}', details=_title, large_image='default',
                                                 large_text='Listening', small_image='logo', small_text='Music Caster')
                    # Set tray tooltip to f'Youtube: {mc.title}'
                except StopIteration as _e:
                    tray.ShowMessage('Music Caster ERROR', 'Could not play URL. Keep MC updated')
                    if settings.get('DEBUG', False): raise _e


    def play_file(file_path, position=0, autoplay=True, switching_device=False):
        global mc, song_start, song_end, playing_status, song_length, song_position,\
            thumbs_dir, cast_last_checked, music_queue
        while not os.path.exists(file_path):
            music_queue.remove(file_path)
            if music_queue: file_path = music_queue[0]
            else: return
            position = 0
        song_position = position
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
        _title, _artist, album = get_metadata(file_path)
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
            music_meta_data[file_path] = {'artist': _artist, 'title': _title, 'album': album, 'length': song_length,
                                          'art': f'data:image/png;base64,{base64.b64encode(pict).decode("utf-8")}'}
        else: music_meta_data[file_path] = {'artist': _artist, 'title': _title, 'album': album, 'length': song_length}
        if cast is None:  # play locally
            if file_path.lower()[-3:] not in {'mp3', 'ogg', 'wav'}:
                if settings['notifications']:
                    file_format = file_path.split('.')[-1]
                    tray.ShowMessage('Music Caster', f'File format {file_format} not supported')
                music_queue.pop(0)
                if music_queue:
                    play_file(music_queue[0])
                return
            mc = None
            if local_music_player.get_init() is None or local_music_player.get_init()[0] != sample_rate:
                local_music_player.quit()
                local_music_player.init(sample_rate, -16, 2, 2048)
            local_music_player.music.load(file_path)
            local_music_player.music.set_volume(_volume)
            local_music_player.music.play(start=song_position)
            if not autoplay: local_music_player.music.pause()
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
                music_metadata = {'metadataType': 3, 'albumName': album, 'title': _title, 'artist': _artist}
                mc.play_media(url, f'audio/{file_path.split(".")[-1]}', current_time=song_position,
                              metadata=music_metadata, thumb=thumb, autoplay=autoplay)
                mc.block_until_active()
                while mc.status.player_state not in {'PLAYING', 'PAUSED'}: time.sleep(0.1)
                song_start = time.time() - song_position
                song_end = song_start + song_length
            except (pychromecast.error.NotConnected, OSError) as _e:
                if _e == OSError: handle_exception(_e)
                tray.ShowMessage('Music Caster Error', 'Could not connect to Chromecast device')
                with suppress(pychromecast.error.UnsupportedNamespace): stop()
                return
        playing_text = f"{_artist.split(', ')[0]} - {_title}"
        if notifications_enabled and not switching_device:
            tray.ShowMessage('Music Caster', 'Playing: ' + playing_text, time=500)
        if autoplay:
            playing_status = 'PLAYING'
            tray.Update(menu=menu_def_2, data_base64=FILLED_ICON, tooltip=playing_text)
        cast_last_checked = time.time()
        if settings['discord_rpc']:
            with suppress(AttributeError, pypresence.InvalidID):
                rich_presence.update(state=f'By: {_artist}', details=_title, large_image='default',
                                     large_text='Listening', small_image='logo', small_text='Music Caster')

    def play_all(starting_files: list = None):
        global playing_status
        music_queue.clear()
        done_queue.clear()
        if starting_files is None: starting_files = []
        starting_files = [_f.replace('\\', '/') for _f in starting_files if valid_music_file(_f)]
        if starting_files: music_queue.extend(compile_all_songs(False, starting_files).values())
        else: music_queue.extend(all_songs.values())
        if music_queue: shuffle(music_queue)
        if starting_files:
            for j, _f in enumerate(starting_files):
                music_queue.insert(j, _f)
        if music_queue:
            play_file(music_queue[0])
            tray.Update(menu=menu_def_2, data_base64=FILLED_ICON)
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
        if music_queue:
            play_file(music_queue[0])
            tray.Update(menu=menu_def_2, data_base64=FILLED_ICON)
        elif next_queue:
            playing_status = 'PLAYING'
            next_song()

    def play_next():
        global music_directories, DEFAULT_DIR, playing_status
        if music_directories: DEFAULT_DIR = music_directories[0]
        else: DEFAULT_DIR = home_music_dir
        _fd = wx.FileDialog(None, 'Select Music File(s)', defaultDir=DEFAULT_DIR, wildcard=MUSIC_FILE_TYPES,
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE)
        if _fd.ShowModal() != wx.ID_CANCEL:
            file_paths = _fd.GetPaths()
            next_queue.extend([file_path for file_path in file_paths if valid_music_file(file_path)])
            if playing_status == 'NOT PLAYING':
                if cast is not None and cast.app_id != APP_MEDIA_RECEIVER: cast.wait(timeout=WAIT_TIMEOUT)
                playing_status = 'PLAYING'
                next_song()

    def update_song_position():
        global tray, song_position, cast, mc
        if cast is not None:
            mc = cast.media_controller
            if mc is not None:
                try:
                    mc.update_status()
                    song_position = mc.status.adjusted_current_time
                except (UnsupportedNamespace, NotConnected): song_position = time.time() - song_start
        elif playing_status == 'PLAYING': song_position = time.time() - song_start
        return song_position

    def pause():
        global tray, playing_status, song_position
        tray.Update(menu=menu_def_3, data_base64=UNFILLED_ICON)
        try:
            if mc is not None:
                mc.update_status()
                mc.pause()
                while not mc.status.player_is_paused: time.sleep(0.1)
                song_position = mc.status.adjusted_current_time
            else:
                song_position = time.time() - song_start
                local_music_player.music.pause()
            playing_status = 'PAUSED'
            if music_queue:
                _title, _artist = get_metadata(music_queue[0])[:2]
                if settings['discord_rpc']:
                    with suppress(AttributeError, pypresence.InvalidID):
                        rich_presence.update(state=f'By: {_artist}', details=_title, large_image='default',
                                             large_text='Paused', small_image='logo', small_text='Music Caster')
        except UnsupportedNamespace:
            stop()

    def resume():
        global tray, playing_status, song_end, song_position, song_start
        tray.Update(menu=menu_def_2, data_base64=FILLED_ICON)
        try:
            if mc is not None:
                mc.update_status()
                mc.play()
                mc.block_until_active()
                while not mc.status.player_state == 'PLAYING': time.sleep(0.1)
                song_position = mc.status.adjusted_current_time
            else: local_music_player.music.unpause()
            song_start = time.time() - song_position
            song_end = song_start + song_length
            playing_status = 'PLAYING'
            _title, _artist = get_metadata(music_queue[0])[:2]
            if settings['discord_rpc']:
                with suppress(AttributeError, pypresence.InvalidID):
                    rich_presence.update(state=f'By: {_artist}', details=_title, large_image='default',
                                         large_text='Playing', small_image='logo', small_text='Music Caster')
        except UnsupportedNamespace:
            play_file(music_queue[0], position=song_position)

    def stop():
        global playing_status, cast, song_position, time_left
        playing_status = 'NOT PLAYING'
        if settings['discord_rpc']:
            with suppress(AttributeError, pypresence.InvalidID, RuntimeError): rich_presence.clear()
        if mc is not None and cast is not None and cast.app_id == APP_MEDIA_RECEIVER:
            mc.stop()
            while mc.is_playing or mc.is_paused: time.sleep(0.1)
        elif local_music_player.music.get_busy():
            local_music_player.music.stop()
            # local_music_player.music.unload()  # only in 2.0
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
            if music_queue: play_file(music_queue[0])
            else: stop()  # repeat is off / no songs in queue

    def prev_song():
        global playing_status
        if cast is not None and cast.app_id != APP_MEDIA_RECEIVER: playing_status = 'NOT PLAYING'
        elif playing_status != 'NOT PLAYING':
            if done_queue:
                if settings['repeat']: change_settings('repeat', False)
                song = done_queue.pop()
                music_queue.insert(0, song)
                play_file(song)
            elif music_queue: play_file(music_queue[0])

    def background_tasks():
        global mc, cast, cast_last_checked, song_start, song_end, song_position, daemon_command, settings_last_modified

        while True:
            # SETTINGS_LAST_MODIFIED
            if os.path.getmtime(settings_file) != settings_last_modified:
                settings_last_modified = os.path.getmtime(settings_file)
                load_settings()
            refresh_tray()
            if mc is not None:
                with suppress(UnsupportedNamespace):
                    if cast is not None and time.time() - cast_last_checked > 5:
                        if cast.app_id == APP_MEDIA_RECEIVER:
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
            time.sleep(10)

    def on_press(key):
        global last_press, daemon_command
        if str(key) not in {'<179>', '<176>', '<177>', '<178>'} or time.time() - last_press < 0.15: return
        if str(key) == '<179>':
            if playing_status == 'PLAYING': daemon_command = 'Pause'
            elif playing_status == 'PAUSED': daemon_command = 'Resume'
        elif str(key) == '<176>' and playing_status != 'NOT PLAYING': daemon_command = 'Next Song'
        elif str(key) == '<177>' and playing_status != 'NOT PLAYING': daemon_command = 'Previous Song'
        elif str(key) == '<178>': stop()
        last_press = time.time()

    pynput.keyboard.Listener(on_press=on_press).start()  # daemon=True by default
    threading.Thread(target=background_tasks, daemon=True).start()
    if len(sys.argv) > 1:
        file_or_dir = sys.argv[1]
        if os.path.isfile(file_or_dir): play_file(file_or_dir)
        elif os.path.isdir(file_or_dir): play_folder([file_or_dir])
    if settings.get('DEBUG', False):
        print('Running in tray')
    while True:
        tray_item = tray.Read(timeout=30 if any(active_windows.values()) else 100)
        if tray_item == 'Refresh Devices':
            threading.Thread(target=start_chromecast_discovery, daemon=True).start()
        if '__ACTIVATED__' in {tray_item, daemon_command}:
            if not active_windows['main']:
                active_windows['main'] = True
                repeat_setting = settings['repeat']
                if settings['save_window_positions']:
                    window_location = window_locations.get('main', (None, None))
                else:
                    window_location = (None, None)
                if playing_status in {'PAUSED', 'PLAYING'} and music_queue:
                    current_song = music_queue[0]
                    metadata = music_meta_data[current_song]
                    artist, title = metadata['artist'].split(', ')[0], metadata['title']
                    new_playing_text = f'{artist} - {title}'
                    album_cover_data = metadata.get('album_cover_data', None)
                    main_gui_layout = create_main_gui(music_queue, done_queue, next_queue, playing_status,
                                                      settings, new_playing_text, album_cover_data=album_cover_data)
                else:
                    main_gui_layout = create_main_gui(music_queue, done_queue, next_queue, playing_status,
                                                      settings)
                main_window = Sg.Window('Music Caster', main_gui_layout, background_color=bg, icon=WINDOW_ICON,
                                        return_keyboard_events=True, use_default_focus=False, location=window_location)
                main_window.Finalize()
                main_window['music_queue'].Update(set_to_index=len(done_queue), scroll_to_index=len(done_queue))
                main_window.playing_status = playing_status
                main_window['repeat'].is_repeating = repeat_setting
                main_window['volume_slider'].bind('<Enter>', '_mouse_enter')
                main_window['volume_slider'].bind('<Leave>', '_mouse_leave')
                main_window['progressbar'].bind('<Enter>', '_mouse_enter')
                main_window['progressbar'].bind('<Leave>', '_mouse_leave')
                main_window['tab2'].bind('<Enter>', '_mouse_enter')
                main_window['tab2'].bind('<Leave>', '_mouse_leave')
                set_save_position_callback(main_window, 'main')
            main_window.TKroot.focus_force()
            main_window.Normal()
        elif tray_item.split('.')[0].isdigit():  # if user selected a different device
            i = device_names.index(tray_item)
            if i == 0: new_cast = None
            else:
                try: new_cast = chromecasts[i - 1]
                except IndexError: new_cast = None
            device_names.clear()
            for index, cc in enumerate(['Local device'] + chromecasts):
                cc: pychromecast.Chromecast = cc if index == 0 else cc.name
                if index == i: device_names.append(f'✓ {cc}')
                else: device_names.append(f'{index + 1}. {cc}')
            refresh_tray()
            if cast != new_cast:
                cast = new_cast
                volume = 0 if settings['muted'] else settings['volume']
                if cast is None: change_settings('previous_device', None)
                else:
                    change_settings('previous_device', str(cast.uuid))
                    cast.wait(timeout=WAIT_TIMEOUT)  # TODO: fix Chromecast is connection error
                update_volume(volume)
                current_pos = 0
                if local_music_player.music.get_busy():
                    if playing_status == 'PLAYING': current_pos = time.time() - song_start
                    else: current_pos = song_position
                    local_music_player.music.stop()
                elif mc is not None:
                    with suppress(UnsupportedNamespace):
                        mc.update_status()  # Switch device without playback loss
                        current_pos = mc.status.adjusted_current_time
                        if mc.is_playing or mc.is_paused: mc.stop()
                mc = None if cast is None else cast.media_controller
                if playing_status in {'PAUSED', 'PLAYING'}:
                    do_autoplay = False if playing_status == 'PAUSED' else True
                    play_file(music_queue[0], position=current_pos, autoplay=do_autoplay, switching_device=True)
        elif tray_item == 'Settings':
            if not active_windows['settings']:
                active_windows['settings'] = True
                # RELIEFS: RELIEF_RAISED RELIEF_SUNKEN RELIEF_FLAT RELIEF_RIDGE RELIEF_GROOVE RELIEF_SOLID
                # TODO: test if no internet connection
                qr_data = create_qr_code(PORT)
                settings_layout = create_settings(VERSION, music_directories, settings, qr_data)
                if settings['save_window_positions']: window_location = window_locations.get('settings', (None, None))
                else: window_location = (None, None)
                settings_window = Sg.Window('Music Caster Settings', settings_layout, background_color=bg,
                                            icon=WINDOW_ICON, return_keyboard_events=True, use_default_focus=False,
                                            location=window_location)
                settings_window.Finalize()
                set_save_position_callback(settings_window, 'settings')
            settings_window.TKroot.focus_force()
            settings_window.Normal()
        elif tray_item == 'Create/Edit a Playlist':
            if active_windows['playlist_editor']:
                pl_editor_window.TKroot.focus_force()
                pl_editor_window.Normal()
                continue
            elif not active_windows['playlist_selector']:
                active_windows['playlist_selector'] = True
                if settings['save_window_positions']:
                    window_location = window_locations.get('playlist_selector', (None, None))
                else: window_location = (None, None)
                pl_selector_window = Sg.Window('Playlist Selector', create_playlist_selector(playlists),
                                               background_color=bg, icon=WINDOW_ICON, return_keyboard_events=True,
                                               location=window_location)
                pl_selector_window.Finalize()
                set_save_position_callback(pl_selector_window, 'playlist_selector')
            pl_selector_window.TKroot.focus_force()
            pl_selector_window.Normal()
        elif tray_item.startswith('PL: '):  # playlist
            playlist = tray_item[4:]
            music_queue.clear()
            music_queue.extend(playlists[playlist])
            if music_queue:
                done_queue.clear()
                if settings['shuffle_playlists']: shuffle(music_queue)
                play_file(music_queue[0])
                tray.Update(menu=menu_def_2, data_base64=FILLED_ICON)
        elif tray_item.startswith('PF: '):  # play folder  # TODO
            if tray_item == 'PF: Select Folder(s)':
                dlg = wx.FileDialog(None, 'Choose folder to play', DEFAULT_DIR, style=wx.DD_DIR_MUST_EXIST)
                if dlg.ShowModal() != wx.ID_CANCEL:
                    path_to_folder = dlg.GetPath()
                    play_folder([path_to_folder])
            else: play_folder([music_directories[tray_folders.index(tray_item) - 1]])
        elif 'URL' in {tray_item}:
            if not active_windows['play_url']:
                active_windows['play_url'], play_url_layout = True, create_play_url_window()
                if settings['save_window_positions']: window_location = window_locations.get('play_url', (None, None))
                else: window_location = (None, None)
                play_url_window = Sg.Window('Music Caster - Play URL', play_url_layout, icon=WINDOW_ICON,
                                            return_keyboard_events=True, location=window_location)
                play_url_window.Finalize()
                set_save_position_callback(play_url_window, 'play_url')
            play_url_window.TKroot.focus_force()
            play_url_window.Normal()
            play_url_window['url'].SetFocus()
        elif tray_item == 'Set Timer':
            if not active_windows['timer']:
                active_windows['timer'], timer_layout = True, create_timer(settings)
                if settings['save_window_positions']: window_location = window_locations.get('timer', (None, None))
                else: window_location = (None, None)
                timer_window = Sg.Window('Music Caster - Timer', timer_layout, icon=WINDOW_ICON,
                                         return_keyboard_events=True, grab_anywhere=True, location=window_location)
                timer_window.Finalize()
                set_save_position_callback(timer_window, 'timer')
            timer_window.TKroot.focus_force()
            timer_window.Normal()
            timer_window['minutes'].SetFocus()
        elif tray_item == 'Cancel Timer':
            # TODO: cancel timer should not be an option if no timer is active
            timer = 0
            if notifications_enabled: tray.ShowMessage('Music Caster', 'Timer stopped')
        elif tray_item == 'Play File(s)':
            if music_directories: DEFAULT_DIR = music_directories[0]
            else: DEFAULT_DIR = home_music_dir
            fd = wx.FileDialog(None, 'Select Music File(s)', defaultDir=DEFAULT_DIR, wildcard=MUSIC_FILE_TYPES,
                               style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE)
            if fd.ShowModal() != wx.ID_CANCEL:
                play_all(fd.GetPaths())
        elif daemon_command == 'Play File(s)':
            # TODO
            pass
        elif tray_item == 'Play All': play_all()
        elif tray_item == 'Play File Next': play_next()
        elif 'Pause' in {tray_item, daemon_command}: pause()
        elif 'Resume' in {tray_item, daemon_command}: resume()
        elif ('Next Song' in {tray_item, daemon_command} and playing_status != 'NOT PLAYING'
              or playing_status == 'PLAYING' and time.time() > song_end):
            next_song(from_timeout=time.time() > song_end)
        elif 'Previous Song' in {tray_item, daemon_command} and playing_status != 'NOT PLAYING': prev_song()
        elif 'Stop' in {tray_item, daemon_command}: stop()
        elif timer and time.time() > timer:
            stop()
            timer = 0
            if settings['timer_shut_off_computer']:
                if platform.system() == 'Windows': os.system('shutdown /p /f')
                else: os.system('sudo shutdown now')
            elif settings['timer_hibernate_computer']:
                if platform.system() == 'Windows': os.system(r'rundll32.exe powrprof.dll,SetSuspendState Hibernate')
                else: pass
            elif settings['timer_sleep_computer']:
                if platform.system() == 'Windows': os.system('rundll32.exe powrprof.dll,SetSuspendState 0,1,0')
                else: pass
        elif tray_item == 'Repeat One': repeat_setting = change_settings('repeat', True)
        elif tray_item == 'Repeat All': repeat_setting = change_settings('repeat', False)
        elif tray_item == 'Repeat Off': repeat_setting = change_settings('repeat', None)
        elif tray_item == 'Locate File' and music_queue: Popen(f'explorer /select,"{fix_path(music_queue[0])}"')
        elif tray_item == 'Exit':
            tray.Hide()
            with suppress(UnsupportedNamespace):
                stop()
                if cast is not None and cast.app_id == APP_MEDIA_RECEIVER and playing_status != 'NOT PLAYING':
                    cast.quit_app()
            with suppress(AttributeError, pypresence.InvalidID, RuntimeError):
                rich_presence.close()
                # Commented because I am unsure if it is effective
            sys.exit()
        # MAIN WINDOW
        if active_windows['main']:
            main_event, main_values = main_window.Read(timeout=10)
            not_file_pick = main_last_event not in {'queue_folder', 'play_next', 'queue_file'}
            if main_event in {None, 'q', 'Q'} or main_event == 'Escape:27' and not_file_pick:
                active_windows['main'] = False
                main_window.Close()
                continue
            if 'mouse_leave' not in main_event and 'mouse_enter' not in main_event:
                main_last_event = main_event
            p_r_button = main_window['pause/resume']
            now_playing_text = main_window['now_playing']
            update_text = update_repeat_img = False  # text refers to now playing text

            if main_event.startswith('MouseWheel'):
                main_event = main_event.split(':', 1)[1]
                delta = {'Up': 5, 'Down': -5}.get(main_event, 0)
                if mouse_hover == 'progressbar':
                    if playing_status in {'PLAYING', 'PAUSED'}:
                        main_event = 'progressbar'
                        update_song_position()
                        new_position = min(max(song_position + delta, 0), song_length) / song_length * 100
                        main_window['progressbar'].Update(value=new_position)
                        main_values['progressbar'] = new_position
                elif mouse_hover == '':  # not in another tab
                    main_event = 'volume_slider'
                    new_volume = min(max(0, main_values['volume_slider'] + delta), 100)
                    main_window['volume_slider'].Update(value=new_volume)
                    main_values['volume_slider'] = new_volume
                main_window.Refresh()
            if main_event == 'progressbar_mouse_enter': mouse_hover = 'progressbar'
            elif main_event == 'progressbar_mouse_leave': mouse_hover = ''
            elif main_event == 'tab2_mouse_enter': mouse_hover = 'tab2'
            elif main_event == 'tab2_mouse_leave': mouse_hover = ''
            elif main_event == 'tab3_mouse_enter': mouse_hover = 'tab3'
            elif main_event == 'tab3_mouse_leave': mouse_hover = ''
            elif main_event in {'locate_file', 'e:69'}:
                try:
                    index = int(main_values['music_queue'][0].split('.', 1)[0])
                except IndexError:
                    index = 0
                if index < 0:
                    Popen(f'explorer /select,"{fix_path(done_queue[index])}"')
                elif (index == 0 or index > len(next_queue)) and music_queue:
                    Popen(f'explorer /select,"{fix_path(music_queue[index])}"')
                elif 0 < index <= len(next_queue):
                    Popen(f'explorer /select,"{fix_path(next_queue[index - 1])}"')
            elif main_event == 'pause/resume':
                if playing_status == 'PAUSED': resume()
                elif playing_status == 'PLAYING': pause()
                elif playing_status == 'NOT PLAYING' and music_queue: play_file(music_queue[0])
                else: play_all()
            elif main_event == 'next' and playing_status != 'NOT PLAYING': next_song(); progress_bar_last_update = 0
            elif main_event == 'prev' and playing_status != 'NOT PLAYING': prev_song(); progress_bar_last_update = 0
            elif main_event == 'shuffle':
                # TODO: just shuffle music queue
                pass
            elif main_event == 'repeat': cycle_repeat()
            elif main_event in {'volume_slider', 'a', 'd'} or main_event.isdigit():
                delta = 0
                if main_event.isdigit():
                    update_slider = True
                    new_volume = int(main_event) * 10
                else:
                    update_slider = False
                    if main_event == 'a': delta = -5
                    elif main_event == 'd': delta = 5
                    new_volume = main_values['volume_slider'] + delta
                change_settings('volume', new_volume)
                if update_slider or delta != 0: main_window['volume_slider'].Update(value=new_volume)
                update_volume(new_volume)
            elif main_event == 'mute':
                muted = change_settings('muted', not settings['muted'])
                if muted:
                    main_window['mute'].Update(data=VOLUME_MUTED_IMG)
                    main_window['volume_slider'].Update(0)
                    local_music_player.music.set_volume(0)
                    if cast is not None: cast.set_volume(0)
                else:
                    main_window['mute'].Update(data=VOLUME_IMG)
                    main_window['volume_slider'].Update(settings['volume'])
                    local_music_player.music.set_volume(settings['volume'] / 100)
                    if cast is not None: cast.set_volume(settings['volume'] / 100)
            elif main_event in {'Up:38', 'Down:40', 'Prior:33', 'Next:34'}:
                with suppress(AttributeError, IndexError):
                    if main_window.FindElementWithFocus() == main_window['music_queue']:
                        move = {'Up:38': -1, 'Down:40': 1, 'Prior:33': -3, 'Next:34': 3}[main_event]
                        new_i = main_window['music_queue'].GetListValues().index(main_values['music_queue'][0]) + move
                        new_i = min(max(new_i, 0), len(music_queue) - 1)
                        main_window['music_queue'].Update(set_to_index=new_i, scroll_to_index=new_i)
            elif main_event == 'music_queue' and main_values['music_queue']:
                song_to_play = main_values['music_queue'][0]
                index = main_window['music_queue'].GetListValues().index(main_values['music_queue'][0])
                if done_queue and index < len(done_queue):
                    while next_queue:  # design decision to empty next queue
                        music_queue.insert(1, next_queue.pop())
                    for i in range(len(done_queue) - index):
                        music_queue.insert(0, done_queue.pop())
                else:
                    for i in range(index - len(done_queue)):
                        if not music_queue: break
                        done_queue.append(music_queue.pop(0))
                        if next_queue:
                            music_queue.insert(0, next_queue.pop(0))
                play_file(music_queue[0])
                updated_list = create_songs_list(music_queue, done_queue, next_queue)[0]
                dq_len = len(done_queue)
                main_window['music_queue'].Update(values=updated_list, set_to_index=dq_len, scroll_to_index=dq_len)
            elif main_event == 'move_up' and main_values['music_queue']:
                # index_to_move = int(main_values['music_queue'][0].split('.', 1)[0])
                index_to_move = main_window['music_queue'].GetListValues().index(main_values['music_queue'][0])
                new_i = index_to_move - 1
                dq_len = len(done_queue)
                nq_len = len(next_queue)
                if index_to_move < dq_len:  # move within dq
                    done_queue.insert(new_i, done_queue.pop(index_to_move))
                elif index_to_move == dq_len and done_queue:  # move index -1 to 1
                    if next_queue: next_queue.insert(1, done_queue.pop())
                    else: music_queue.insert(1, done_queue.pop())
                elif index_to_move == dq_len + 1:  # move 1 to -1
                    if next_queue: done_queue.append(next_queue.pop(0))
                    else: done_queue.append(music_queue.pop(1))
                elif next_queue and index_to_move < dq_len + nq_len + 1:  # within next_queue
                    nq_i = new_i - dq_len - 1
                    next_queue.insert(nq_i, next_queue.pop(nq_i + 1))
                elif next_queue and index_to_move == dq_len + nq_len + 1:  # moving into next queue
                    next_queue.insert(nq_len - 1, music_queue.pop(1))
                else:  # moving within mq
                    mq_i = new_i - dq_len - nq_len
                    music_queue.insert(mq_i, music_queue.pop(mq_i + 1))
                updated_list = create_songs_list(music_queue, done_queue, next_queue)[0]
                main_window['music_queue'].Update(values=updated_list, set_to_index=new_i, scroll_to_index=new_i)
            elif main_event == 'move_down' and main_values['music_queue']:
                index_to_move = main_window['music_queue'].GetListValues().index(main_values['music_queue'][0])
                dq_len, nq_len, mq_len = len(done_queue), len(next_queue), len(music_queue)
                if index_to_move < dq_len + nq_len + mq_len - 1:
                    new_i = index_to_move + 1
                    if index_to_move == dq_len - 1:  # move index -1 to 1
                        if next_queue: next_queue.insert(0, done_queue.pop())
                        else: music_queue.insert(1, done_queue.pop())
                    elif index_to_move < dq_len:  # move within dq
                        done_queue.insert(new_i, done_queue.pop(index_to_move))
                    elif index_to_move == dq_len:  # move 1 to -1
                        if next_queue: done_queue.append(next_queue.pop(0))
                        else: done_queue.append(music_queue.pop(1))
                    elif next_queue and index_to_move == dq_len + nq_len:  # moving into music_queue
                        music_queue.insert(2, next_queue.pop())
                    elif index_to_move < dq_len + nq_len + 1:  # within next_queue
                        nq_i = index_to_move - dq_len - 1
                        next_queue.insert(nq_i, next_queue.pop(nq_i - 1))
                    else:  # within music_queue
                        mq_i = new_i - dq_len - nq_len
                        music_queue.insert(mq_i, music_queue.pop(mq_i - 1))
                    updated_list = create_songs_list(music_queue, done_queue, next_queue)[0]
                    main_window['music_queue'].Update(values=updated_list, set_to_index=new_i, scroll_to_index=new_i)
            elif main_event == 'remove' and main_values['music_queue']:
                index_to_remove = main_window['music_queue'].GetListValues().index(main_values['music_queue'][0])
                dq_len, nq_len, mq_len = len(done_queue), len(next_queue), len(music_queue)
                if index_to_remove < dq_len:
                    done_queue.pop(index_to_remove)
                elif index_to_remove == dq_len:
                    music_queue.pop(0)
                    if music_queue: play_file(music_queue[0])
                elif index_to_remove <= nq_len + dq_len:
                    next_queue.pop(index_to_remove - dq_len - 1)
                elif index_to_remove < nq_len + mq_len + dq_len:
                    music_queue.pop(index_to_remove - dq_len - nq_len)
                updated_list = create_songs_list(music_queue, done_queue, next_queue)[0]
                new_i = min(len(updated_list), index_to_remove)
                main_window['music_queue'].Update(values=updated_list, set_to_index=new_i, scroll_to_index=new_i)
            elif main_event == 'queue_file':
                if music_directories: DEFAULT_DIR = music_directories[0]
                else: DEFAULT_DIR = home_music_dir
                fd = wx.FileDialog(None, 'Select Music File(s)', defaultDir=DEFAULT_DIR,
                                   wildcard=MUSIC_FILE_TYPES, style=wx.FD_MULTIPLE | wx.FD_FILE_MUST_EXIST)
                if fd.ShowModal() != wx.ID_CANCEL:
                    start_playing = not music_queue
                    music_queue.extend([_f for _f in fd.GetPaths() if valid_music_file(_f)])
                    if start_playing and music_queue: play_file(music_queue[0])
                main_window.TKroot.focus_force()
            elif main_event == 'queue_folder':
                path_to_folder = Sg.PopupGetFolder('Select Folder', default_path=DEFAULT_DIR, no_window=True)
                if os.path.exists(path_to_folder):
                    temp_queue = []
                    for file in glob(f'{path_to_folder}/**/*.*', recursive=True):
                        if valid_music_file(file): temp_queue.append(file)
                    if settings['shuffle_playlists']: shuffle(temp_queue)
                    start_playing = not music_queue
                    for file in temp_queue: music_queue.append(file)
                    updated_list = create_songs_list(music_queue, done_queue, next_queue)[0]
                    main_window['music_queue'].Update(values=updated_list)
                    if start_playing and music_queue: play_file(music_queue[0])
                main_window.TKroot.focus_force()
            elif main_event == 'clear_queue':
                if playing_status in {'PLAYING', 'PAUSED'}: stop()
                music_queue.clear()
                next_queue.clear()
                done_queue.clear()
                main_window['music_queue'].Update(values=[])
            elif main_event == 'play_next':
                play_next()
                main_window.TKroot.focus_force()
            elif main_event == 'locate_file': Popen(f'explorer /select,"{fix_path(music_queue[0])}"')
            elif main_event == 'library': play_all([all_songs[main_values['library']]])
            if main_event == 'progressbar':
                if playing_status == 'NOT PLAYING':
                    main_window['progressbar'].Update(disabled=True)
                    # maybe even make it invisible?
                    continue
                new_position = main_values['progressbar'] / 100 * song_length
                song_position = new_position
                if cast is not None:
                    cast.media_controller.seek(new_position)
                    playing_status = 'PLAYING'
                else:
                    local_music_player.music.rewind()
                    local_music_player.music.set_pos(new_position)
                    # local_music_player.music.set_pos(new_position - song_position)
                    # song_position = new_position
                time_left = song_length - song_position
                song_end = time.time() + time_left
                song_start = song_end - song_length
                update_progress_text = True
            if playing_status in {'PLAYING', 'PAUSED'} and time.time() - progress_bar_last_update > 1:
                # TODO: progressbar visible if playing?
                if music_queue:
                    metadata = music_meta_data[music_queue[0]]
                    artist, title = metadata['artist'].split(', ')[0], metadata['title']
                    new_playing_text = f'{artist} - {title}'
                    update_text = now_playing_text.DisplayText != new_playing_text
                    progress_bar = main_window['progressbar']
                    update_song_position()
                    progress_bar.Update(song_position / song_length * 100, disabled=False)
                    time_left = song_length - song_position
                    update_progress_text = True
                    progress_bar_last_update = time.time()
                else: playing_status = 'NOT PLAYING'
            if update_progress_text:
                mins_elapsed, mins_left = floor(song_position / 60), floor(time_left / 60)
                secs_elapsed, secs_left = floor(song_position % 60), floor(time_left % 60)
                if secs_left < 10: secs_left = f'0{secs_left}'
                if secs_elapsed < 10: secs_elapsed = f'0{secs_elapsed}'
                main_window['time_elapsed'].Update(value=f'{mins_elapsed}:{secs_elapsed}')
                main_window['time_left'].Update(value=f'{mins_left}:{secs_left}')
                metadata = music_meta_data[music_queue[0]]
                # main_window['album_cover'].Update(data=metadata['album_cover_data'])
                update_progress_text = False
            lb_music_queue: Sg.Listbox = main_window['music_queue']
            dq_len = len(done_queue)
            update_lb_mq = len(lb_music_queue.get_list_values()) != len(music_queue) + len(next_queue) + dq_len
            if playing_status == 'PLAYING' and main_window.playing_status != 'PLAYING':
                main_window.playing_status = 'PLAYING'
                p_r_button.Update(image_data=PAUSE_BUTTON_IMG)
            elif playing_status == 'PAUSED' and main_window.playing_status != 'PAUSED':
                main_window.playing_status = 'PAUSED'
                p_r_button.Update(image_data=PLAY_BUTTON_IMG)
            elif playing_status == 'NOT PLAYING' and main_window.playing_status != 'NOT PLAYING':
                if main_window.playing_status == 'PLAYING': p_r_button.Update(image_data=PLAY_BUTTON_IMG)
                main_window.playing_status, new_playing_text, update_text = 'NOT PLAYING', 'Nothing Playing', True
                main_window['time_elapsed'].Update(value='00:00')
                main_window['time_left'].Update(value='00:00')
            if update_text: now_playing_text.Update(value=new_playing_text)
            if update_text or update_lb_mq:
                lb_music_queue_songs = create_songs_list(music_queue, done_queue, next_queue)[0]
                lb_music_queue.Update(values=lb_music_queue_songs, set_to_index=dq_len, scroll_to_index=dq_len)

        # SETTINGS WINDOW
        if active_windows['settings']:
            settings_event, settings_values = settings_window.Read(timeout=10)
            if (settings_event in {None, 'q', 'Q'} or settings_event == 'Escape:27'
                    and settings_last_event != 'add_folder'):
                active_windows['settings'] = False
                settings_window.Close()
                continue
            settings_value = settings_values.get(settings_event)
            if settings_event == 'email':
                webbrowser.open(f'mailto:{EMAIL}?subject=Regarding%20Music%20Caster%20v{VERSION}')
            if settings_event == 'web_gui':
                webbrowser.open(f'http://{get_ipv4()}:{PORT}')
            elif settings_event in {'auto_update', 'discord_rpc', 'notifications', 'run_on_startup',
                                    'shuffle_playlists', 'save_window_positions'}:
                change_settings(settings_event, settings_value)
                if settings_event == 'run_on_startup': create_shortcut(SHORTCUT_PATH)
                elif settings_event == 'notifications': notifications_enabled = settings_value
                elif settings_event == 'discord_rpc':
                    with suppress(AttributeError, pypresence.InvalidID, RuntimeError):
                        if settings_value and playing_status in {'PAUSED', 'PLAYING'}:
                            title, artist = get_metadata(music_queue[0])[:2]
                            rich_presence.connect()
                            rich_presence.update(state=f'By: {artist}', details=title, large_image='default',
                                                 large_text='Listening', small_image='logo', small_text='Music Caster')
                        elif not settings_value: rich_presence.clear()
            elif settings_event == 'remove_folder' and settings_values['music_dirs']:
                selected_item = settings_values['music_dirs'][0]
                if selected_item in music_directories:
                    music_directories.remove(selected_item)
                    settings_window['music_dirs'].Update(music_directories)
                    refresh_tray()
                    save_json()
                    compile_all_songs()
            elif settings_event == 'add_folder':
                if settings_value not in music_directories and os.path.exists(settings_value):
                    music_directories.append(settings_value)
                    settings_window['music_dirs'].Update(music_directories)
                    refresh_tray()
                    save_json()
                    compile_all_songs()
            elif settings_event == 'settings_file':
                try: os.startfile(settings_file)
                except OSError: Popen(f'explorer /select,"{fix_path(settings_file)}"')
            settings_last_event = settings_event
        if active_windows['playlist_selector']:
            pl_selector_event, pl_selector_values = pl_selector_window.Read(timeout=10)
            if pl_selector_event in {None, 'Escape:27', 'q', 'Q'}:
                active_windows['playlist_selector'] = False
                pl_selector_window.Close()
                continue
            if pl_selector_event in {'del_pl', 'Delete:46'}:
                pl_name = pl_selector_values.get('pl_selector', '')
                if pl_name in playlists: del playlists[pl_name]
                pl_selector_window.Close()
                if settings['save_window_positions']:
                    window_location = window_locations.get('playlist_selector', (None, None))
                else: window_location = (None, None)
                pl_selector_window = Sg.Window('Playlist Selector', create_playlist_selector(playlists),
                                               background_color=bg, icon=WINDOW_ICON, return_keyboard_events=True,
                                               location=window_location)
                pl_selector_window.Read(timeout=10)
                pl_selector_window.TKroot.focus_force()
                pl_selector_window.Normal()
                save_json()
                tray_playlists.clear()
                tray_playlists.append('Create/Edit a Playlist')
                tray_playlists += [f'PL: {pl}' for pl in playlists.keys()]
                if playing_status == 'PLAYING': tray.Update(menu=menu_def_2)
                elif playing_status == 'PAUSED': tray.Update(menu=menu_def_3)
                else: tray.Update(menu=menu_def_1)
            elif pl_selector_event in {'edit_pl', 'create_pl', 'e', 'n', 'e:69', 'n:78'}:
                if pl_selector_event in {'edit_pl', 'e', 'e:69'}: pl_name = pl_selector_values.get('pl_selector', '')
                else: pl_name = ''
                # https://github.com/PySimpleGUI/PySimpleGUI/issues/845#issuecomment-443862047
                if settings['save_window_positions']:
                    window_location = window_locations.get('playlist_editor', (None, None))
                else: window_location = (None, None)
                pl_editor_window = Sg.Window('Playlist Editor', create_playlist_editor(DEFAULT_DIR, playlists, pl_name),
                                             background_color=bg, icon=WINDOW_ICON, return_keyboard_events=True,
                                             location=window_location)
                pl_files = playlists.get(pl_name, [])
                pl_selector_window.Close()
                pl_editor_window.Finalize()
                pl_editor_window.TKroot.focus_force()
                pl_editor_window.Normal()
                set_save_position_callback(pl_editor_window, 'playlist_editor')
                if pl_selector_event == 'create_pl': pl_editor_window['playlist_name'].SetFocus()
                else:
                    pl_editor_window['songs'].SetFocus()
                    pl_editor_window['songs'].Update(set_to_index=0)
                active_windows['playlist_editor'], active_windows['playlist_selector'] = True, False
        if active_windows['playlist_editor']:
            pl_editor_event, pl_editor_values = pl_editor_window.Read(timeout=10)
            if pl_editor_event in {None, 'Escape:27', 'q:81', 'Cancel'} and pl_editor_last_event != 'Add songs':
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
                save_json()
                active_windows['playlist_editor'] = False
                pl_editor_window.Close()
                open_pl_selector = True
                tray_playlists.clear()
                tray_playlists.append('Create/Edit a Playlist')
                tray_playlists += [f'PL: {pl}' for pl in playlists.keys()]
                if playing_status == 'PLAYING': tray.Update(menu=menu_def_2)
                elif playing_status == 'PAUSED': tray.Update(menu=menu_def_3)
                else: tray.Update(menu=menu_def_1)
            elif pl_editor_event in {'move_up', 'u:85'}:  # u:85 is Ctrl + U
                if pl_editor_values['songs']:
                    to_move = pl_editor_window['songs'].GetListValues().index(pl_editor_values['songs'][0])
                    if to_move > 0:
                        new_i = to_move - 1
                        pl_files.insert(new_i, pl_files.pop(to_move))
                        formatted_songs = [f'{i+1}. {os.path.basename(path)}' for i, path in enumerate(pl_files)]
                        pl_editor_window['songs'].Update(values=formatted_songs, set_to_index=new_i,
                                                         scroll_to_index=new_i)
            elif pl_editor_event in {'move_down', 'd:68'}:  # d:68 is Ctrl + D
                if pl_editor_values['songs']:
                    to_move = pl_editor_window['songs'].GetListValues().index(pl_editor_values['songs'][0])
                    if to_move < len(pl_files) - 1:
                        new_i = to_move + 1
                        pl_files.insert(new_i, pl_files.pop(to_move))
                        formatted_songs = [f'{i+1}. {os.path.basename(path)}' for i, path in enumerate(pl_files)]
                        pl_editor_window['songs'].Update(values=formatted_songs, set_to_index=new_i,
                                                         scroll_to_index=new_i)
            elif pl_editor_event == 'Add songs':
                selected_songs = pl_editor_values['Add songs']
                if selected_songs:
                    new_files = [file for file in selected_songs.split(';') if valid_music_file(file)]
                    pl_files += new_files
                    pl_editor_window.TKroot.focus_force()
                    pl_editor_window.Normal()
                    formatted_songs = [f'{i+1}. {os.path.basename(path)}' for i, path in enumerate(pl_files)]
                    new_i = len(formatted_songs) - 1  # - len(new_files)
                    pl_editor_window['songs'].Update(formatted_songs, set_to_index=new_i, scroll_to_index=new_i)
            elif pl_editor_event in {'Remove song', 'r:82'}:  # r:82 is Ctrl + R
                if pl_editor_values['songs']:
                    index_to_rm = pl_editor_window['songs'].GetListValues().index(pl_editor_values['songs'][0])
                    with suppress(ValueError): pl_files.pop(index_to_rm)
                    formatted_songs = [f'{i+1}. {os.path.basename(path)}' for i, path in enumerate(pl_files)]
                    new_i = max(index_to_rm - 1, 0)
                    pl_editor_window['songs'].Update(formatted_songs, set_to_index=new_i, scroll_to_index=new_i)
            elif pl_editor_event in {'Up:38', 'Down:40', 'Prior:33', 'Next:34'} and pl_editor_values['songs']:
                move = {'Up:38': -1, 'Down:40': 1, 'Prior:33': -3, 'Next:34': 3}[pl_editor_event]
                new_i = pl_editor_window['songs'].GetListValues().index(pl_editor_values['songs'][0]) + move
                new_i = min(max(new_i, 0), len(pl_files) - 1)
                pl_editor_window['songs'].Update(set_to_index=new_i, scroll_to_index=new_i)
            if open_pl_selector:
                open_pl_selector = False
                active_windows['playlist_selector'] = True
                if settings['save_window_positions']:
                    window_location = window_locations.get('playlist_selector', (None, None))
                else: window_location = (None, None)
                pl_selector_window = Sg.Window('Playlist Selector', create_playlist_selector(playlists),
                                               background_color=bg, icon=WINDOW_ICON, return_keyboard_events=True,
                                               location=window_location)
                pl_selector_window.Finalize()
                pl_selector_window.TKroot.focus_force()
                pl_selector_window.Normal()
                set_save_position_callback(pl_selector_window, 'playlist_selector')
            pl_editor_last_event = pl_editor_event
        if active_windows['timer']:
            timer_event, timer_values = timer_window.Read(timeout=10)
            if timer_event in {None, 'Escape:27', 'q', 'Q'}:
                active_windows['timer'] = False
                timer_window.Close()
            elif timer_event in {'\r', 'special 16777220', 'special 16777221', 'Submit'}:
                try:
                    timer_value = timer_values['minutes']
                    if timer_value.isdigit():
                        minutes = abs(float(timer_values['minutes']))
                    elif timer_value.count(':') == 1:
                        now = datetime.now()
                        if timer_value[-3:].strip().upper() in ('PM', 'AM'): timer_value = timer_value[timer_value:-3]
                        elif timer_value[-2:].upper() in ('PM', 'AM'): timer_value = timer_value[timer_value:-2]
                        to_stop = datetime.strptime(timer_value + time.strftime(',%Y,%m,%d,%p'), '%I:%M,%Y,%m,%d,%p')
                        delta = (to_stop - datetime.now()).total_seconds()
                        if delta < 0: delta += 43200
                        minutes = delta // 60
                    else: continue
                    timer = time.time() + 60 * minutes
                    if notifications_enabled:
                        timer_set_to = datetime.now() + timedelta(minutes=minutes)
                        timer_set_to = timer_set_to.strftime('%#I:%M %p')
                        # timer_set_to = timer_set_to.strftime('%-I:%M %p')  # Linux
                        tray.ShowMessage('Music Caster', f'Timer set for {timer_set_to}', time=500)
                    active_windows['timer'] = False
                    timer_window.Close()
                except ValueError:
                    Sg.PopupOK('Input a number!')
            elif timer_event in {'shut_off', 'hibernate', 'sleep', 'do_nothing'}:
                change_settings('timer_hibernate_computer', timer_values['hibernate'])
                change_settings('timer_sleep_computer', timer_values['sleep'])
                change_settings('timer_shut_off_computer', timer_values['shut_off'])
        if active_windows['play_url']:
            play_url_event, play_url_values = play_url_window.Read(timeout=10)
            if play_url_event in {None, 'Escape:27', 'q', 'Q'}:
                active_windows['play_url'] = False
                play_url_window.Close()
            if play_url_event in {'\r', 'special 16777220', 'special 16777221', 'Submit'}:
                active_windows['play_url'] = False
                play_url_window.Close()
                play_url(play_url_values['url'])
        daemon_command = ''
except Exception as e:
    handle_exception(e, True)
