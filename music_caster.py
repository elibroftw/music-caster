from bs4 import BeautifulSoup
import base64
from contextlib import suppress
from datetime import datetime, timedelta
from flask import Flask
from getpass import getuser
from glob import glob
import io
import json
import logging
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3
import mutagen
import os
from pathlib import Path
# from PIL import Image
import pychromecast.controllers.media
from pychromecast.error import UnsupportedNamespace
import pychromecast
from pygame import mixer as local_music_player
from pynput.keyboard import Listener
import pyperclip
import socket
import PySimpleGUI as Sg
# noinspection PyPep8Naming
import PySimpleGUIWx as sg
import wx
from random import shuffle
import requests
from shutil import copyfile, copyfileobj
from subprocess import Popen
import sys
import time
import threading
import traceback
import webbrowser
import win32api
import win32com.client
import win32event
from winerror import ERROR_ALREADY_EXISTS
import zipfile
from helpers import *


# TODO: maybe add *.flac compatibility https://mutagen.readthedocs.io/en/latest/api/flac.html
VERSION = '4.18.0'
update_devices = False
chromecasts = []
device_names = ['1. Local Device']
cast = None
local_music_player.init(44100, -16, 2, 2048)
starting_dir = os.path.dirname(os.path.realpath(__file__)).replace('\\', '/')
home_music_dir = str(Path.home()).replace('\\', '/') + '/Music'
settings = {  # default settings
        'previous device': None,
        'auto update': False,
        'run on startup': True,
        'notifications': True,
        'shuffle_playlists': False,
        'volume': 100,
        'local volume': 100,
        'repeat': False,
        'timer_shut_off_computer': False,
        'timer_hibernate_computer': False,
        'timer_sleep_computer': False,
        'music directories': [home_music_dir],
        'playlists': {},
        'playlists_example': {'NAME': ['PATHS']},
    }
settings_file = f'{starting_dir}/settings.json'
playlists = {}
tray_playlists = ['Create/Edit a Playlist']
music_directories = []
notifications_enabled = True


def save_json():
    with open(settings_file, 'w') as outfile:
        json.dump(settings, outfile, indent=4)


def change_settings(name, value):
    settings[name] = value
    save_json()
    return value


def download_and_extract(link, infile, outfile=None):
    r = requests.get(link, stream=True)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    z.extractall(f'{starting_dir}/Update')  # extract to a folder called Update
    if outfile is None: outfile = infile
    with suppress(FileNotFoundError): os.remove(outfile)
    os.rename(f'{starting_dir}/Update/{infile}', outfile)


def load_settings():
    """load (and fix if needed) the settings file"""
    global settings, playlists, notifications_enabled, music_directories, tray_playlists, DEFAULT_DIR
    if os.path.exists(settings_file):
        with open(settings_file) as json_file:
            try: loaded_settings = json.load(json_file)
            except json.decoder.JSONDecodeError as e: loaded_settings = {}
            save_settings = False
            for setting_name, setting_value in settings.items():
                if setting_name not in loaded_settings:
                    loaded_settings[setting_name] = setting_value
                    save_settings = True
            settings = loaded_settings
            playlists = settings['playlists']
            tray_playlists.clear()
            tray_playlists.append('Create/Edit a Playlist')
            tray_playlists += [f'PL: {pl}' for pl in playlists.keys()]
            notifications_enabled = settings['notifications']
            music_directories = settings['music directories']
            if not music_directories: music_directories = change_settings('music directories', [home_music_dir])
            DEFAULT_DIR = music_directories[0]
        if save_settings: save_json()
    else: save_json()


def chromecast_callback(chromecast):
    global update_devices, cast
    previous_device = settings['previous device']
    if str(chromecast.device.uuid) == previous_device and cast != chromecast:
        cast = chromecast
        cast.wait(timeout=5)
    chromecasts.append(chromecast)
    devices = len(device_names)
    device_names.append(f'{devices + 1}. {chromecast.device.friendly_name}')
    update_devices = True


try:
    user = getuser()
    shortcut_path = f'C:/Users/{user}/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/Music Caster.lnk'
    # Mine is C:\Users\maste\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup


    def startup_setting():
        run_on_startup = settings['run on startup']
        shortcut_exists = os.path.exists(shortcut_path)
        if run_on_startup and not shortcut_exists and not settings.get('DEBUG', False):
            shell = win32com.client.Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(shortcut_path)
            if getattr(sys, 'frozen', False):  # Running in a bundle
                target = f'{starting_dir}\\Music Caster.exe'
            else:  # set shortcut to python script; __file__
                bat_file = f'{starting_dir}\\music_caster.bat'
                if os.path.exists(bat_file):
                    with open('music_caster.bat', 'w') as f:
                        f.write(f'pythonw {os.path.basename(__file__)}')
                target = bat_file
                shortcut.IconLocation = f'{starting_dir}\\icon.ico'
            shortcut.Targetpath = target
            shortcut.WorkingDirectory = starting_dir
            shortcut.WindowStyle = 1  # 7 - Minimized, 3 - Maximized, 1 - Normal
            shortcut.save()
        elif not run_on_startup and shortcut_exists: os.remove(shortcut_path)


    load_settings()
    # Only one of the below can be True
    temp = (settings['timer_shut_off_computer'], settings['timer_hibernate_computer'], settings['timer_sleep_computer'])
    if temp.count(True) > 1:
        if settings['timer_shut_off_computer']: change_settings('timer_hibernate_computer', False)
        change_settings('timer_sleep_computer', False)
    # Check if app is running already
    mutex = win32event.CreateMutex(None, False, 'name')
    last_error = win32api.GetLastError()
    if last_error == ERROR_ALREADY_EXISTS and not settings.get('DEBUG', False): sys.exit()

    images_dir = starting_dir + '/images'
    cc_music_dir = starting_dir + '/music files'
    if not os.path.exists(cc_music_dir): os.mkdir(cc_music_dir)
    if not os.path.exists(images_dir): os.mkdir(images_dir)
    if not os.path.exists(f'{images_dir}/default.png'):  # in case the user decided to delete the default image
        if os.path.exists('resources/default.png'):  # running from source code
            copyfile('resources/default.png', 'images/default.png')
        else:  # download the default image
            with suppress(requests.ConnectionError):
                default_img_url = 'https://raw.githubusercontent.com/elibroftw/music-caster/master/resources/default.png'
                response = requests.get(default_img_url, stream=True)
                with open(f'{images_dir}/default.png', 'wb') as handle:
                    for data in response.iter_content(): handle.write(data)
    for file in glob(f'{cc_music_dir}/*.*') + glob(f'{images_dir}/*.*'):
        file = file.replace('\\', '/')
        if file != f'{images_dir}/default.png': os.remove(file)
    os.chdir(os.getcwd()[:3])  # set drive as the working dir
    PORT = 2001
    app = Flask(__name__, static_folder='/', static_url_path='/')
    logging.getLogger('werkzeug').disabled = True
    os.environ['WERKZEUG_RUN_MAIN'] = 'true'
    while True:
        try:
            threading.Thread(target=app.run, daemon=True, kwargs={'host': '0.0.0.0', 'port': PORT}).start()
            break
        except OSError: PORT += 1
    if settings['auto update']:
        with suppress(requests.ConnectionError):
            github_url = 'https://github.com/elibroftw/music-caster/releases'
            html_doc = requests.get(github_url).text
            soup = BeautifulSoup(html_doc, features='html.parser')
            release_entries = soup.find_all('div', class_='release-entry')
            for entry in release_entries:
                latest_version = entry.find('a', class_='muted-link css-truncate')['title'][1:]
                release_type = entry.find('span').text.strip()
                if release_type == 'Latest release': break
            major, minor, patch = (int(x) for x in VERSION.split('.'))
            lt_major, lt_minor, lt_patch = (int(x) for x in latest_version.split('.'))
            if (lt_major > major or lt_major == major and lt_minor > minor
                    or lt_major == major and lt_minor == minor and lt_patch > patch):
                details = entry.find('details',
                                     class_='details-reset Details-element border-top pt-3 mt-4 mb-2 mb-md-4')
                download_links = [link['href'] for link in details.find_all('a') if link.get('href')]
                bundle_download_link = f'https://github.com{download_links[1]}'
                source_download_link = f'https://github.com{download_links[-2]}'
                os.chdir(starting_dir)
                tray = sg.SystemTray(menu=['File', []], data_base64=UNFILLED_ICON, tooltip='Music Caster')
                tray.ShowMessage('Music Caster', f'Downloading Update v{latest_version}')
                tray.Hide()
                if settings.get('DEBUG'): Popen('python updater.py')
                elif os.path.exists('updater.py') or os.path.exists('music_caster.py'):
                    download_and_extract(source_download_link, f'music-caster-{latest_version}/updater.py', 'updater.py')
                    Popen('pythonw updater.py')
                elif os.path.exists('Updater.exe') or os.path.exists('Music Caster.exe'):
                    download_and_extract(bundle_download_link, 'Updater.exe')
                    os.startfile('Updater.exe')
                elif os.path.exists('updater.pyw') or os.path.exists('music_caster.pyw'):
                    download_and_extract(source_download_link, f'music-caster-{latest_version}/updater.py', 'updater.pyw')
                    Popen('pythonw updater.pyw')
                sys.exit()
    startup_setting()
    stop_discovery = pychromecast.get_chromecasts(blocking=False, callback=chromecast_callback)
    discovery_started = time.time()
    
    menu_def_1 = ['', ['Settings', 'Refresh Devices', 'Select &Device', device_names, 'Playlists', tray_playlists,
                       'Timer', ['Set Timer', 'Stop Timing'], 'Play &File', 'Play All', 'E&xit']]

    menu_def_2 = ['', ['Settings', 'Refresh Devices', 'Select &Device', device_names, 'Playlists', tray_playlists,
                       'Timer', ['Set Timer', 'Stop Timing'], 'Play &File', 'Play a File Next', 'Play All', 'Repeat', 'Stop', 'Pause', 'Previous Song', 'Next Song', 'E&xit']]

    menu_def_3 = ['', ['Settings', 'Refresh Devices', 'Select &Device', device_names, 'Playlists', tray_playlists,
                       'Timer', ['Set Timer', 'Stop Timing'], 'Play &File', 'Play a File Next', 'Play All', 'Repeat', 'Stop', 'Resume', 'Previous Song', 'Next Song', 'E&xit']]
    tray = sg.SystemTray(menu=menu_def_1, data_base64=UNFILLED_ICON, tooltip='Music Caster')
    if notifications_enabled: tray.ShowMessage('Music Caster', 'Music Caster is running in the tray', time=500)
    if not music_directories: music_directories = change_settings('music directories', [home_music_dir])
    DEFAULT_DIR = music_directories[0]
    music_queue = []
    done_queue = []
    next_queue = []
    music_meta_data = {}  # file: {artist: str, title: str}
    mc = None
    song_end = song_length = song_start = 0  # seconds but using time()
    song_position = 0  # also seconds but relative to length of song
    playing_status = 'NOT PLAYING'
    cast_last_checked = time.time()
    settings_last_loaded = time.time()


    def play_file(file_path, position=0, autoplay=True, switching_device=False):
        global mc, song_start, song_end, playing_status, song_length, song_position, volume, images_dir, cast_last_checked, music_queue
        while not os.path.exists(file_path): 
            music_queue.remove(file_path)
            file_path = music_queue[0]
            position = 0
        hostname = socket.gethostname()
        ipv4_address = socket.gethostbyname(hostname)
        song_position = position
        audio_info = mutagen.File(file_path).info
        song_length = audio_info.length
        volume = settings['volume'] / 100
        try:
            title = EasyID3(file_path).get('title', ['Unknown'])[0]
            artist = EasyID3(file_path).get('artist', ['Unknown'])
            artist = ', '.join(artist)
            album = EasyID3(file_path).get('album', 'Unknown')
        except Exception as e:
            title = artist = album = 'Unknown'
        # thumb, album_cover_data = get_album_cover(file_path)
        # music_meta_data[file_path] = {'artist': artist, 'title': title, 'album': album, 'length': song_length,
        #                               'album_cover_data': album_cover_data}
        music_meta_data[file_path] = {'artist': artist, 'title': title, 'album': album, 'length': song_length}
        # TODO: add album_art to it as well
        if cast is None:
            mc = None
            sampling_rate = audio_info.sample_rate
            local_music_player.quit()
            local_music_player.init(sampling_rate, -16, 2, 2048)
            local_music_player.music.load(file_path)
            local_music_player.music.set_volume(volume)
            local_music_player.music.play(start=position)
            if not autoplay: local_music_player.music.pause()
            song_start = time.time()
            song_end = song_start + song_length - position
        else:
            drive = file_path[:3]
            file_path_obj = Path(file_path)
            if drive != os.getcwd().replace('\\', '/'):
                new_file_path = f'{cc_music_dir}/{file_path_obj.name}'
                copyfile(file_path, new_file_path)
            else: new_file_path = file_path
            uri_safe = Path(new_file_path).as_uri()[11:]
            url = f'http://{ipv4_address}:{PORT}/{uri_safe}'
            thumb = images_dir + f'/{file_path_obj.stem}.png'
            tags = ID3(file_path)
            pict = None
            for tag in tags.keys():
                if 'APIC' in tag:
                    pict = tags[tag]
                    break
            if pict is not None:
                pict = pict.data
                with open(thumb, 'wb') as f: f.write(pict)
            else: thumb = images_dir + f'/default.png'
            thumb = f'http://{ipv4_address}:{PORT}/{Path(thumb).as_uri()[11:]}'
            # cast: pychromecast.Chromecast
            cast.wait(timeout=10)
            try:
                cast.set_volume(volume)
                mc = cast.media_controller
                if mc.is_playing or mc.is_paused:
                    mc.stop()
                    mc.block_until_active(5)
                music_metadata = {'metadataType': 3, 'albumName': album, 'title': title, 'artist': artist}
                mc.play_media(url, 'audio/mp3', current_time=position, metadata=music_metadata, thumb=thumb, autoplay=autoplay)
                mc.block_until_active()
                while not mc.is_playing: pass
                song_start = time.time()
                song_end = song_start + song_length - position
            except pychromecast.error.NotConnected:
                tray.ShowMessage('Music Caster', 'Could not connect to Chromecast device')
                with suppress(pychromecast.error.UnsupportedNamespace): stop()
                return
        if notifications_enabled and not settings['repeat'] and not switching_device:
            tray.ShowMessage('Music Caster', f"Playing: {artist.split(', ')[0]} - {title}", time=500)
        if autoplay:
            playing_status = 'PLAYING'
            tray.Update(menu=menu_def_2, data_base64=FILLED_ICON)
        cast_last_checked = time.time()


    # def get_album_cover(file_path):
    #     file_path_obj = Path(file_path)
    #     thumb = images_dir + f'/{file_path_obj.stem}.png'
    #     tags = ID3(file_path)
    #     pict = None
    #     for tag in tags.keys():
    #         if 'APIC' in tag:
    #             pict = tags[tag]
    #             break
    #     if pict is not None:
    #         raw = pict = pict.data
    #         with open(thumb, 'wb') as f: f.write(pict)
    #     else:
    #         thumb = images_dir + f'/default.png'
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

    def update_song_position():
        global tray, song_position
        if mc is not None:
            mc.update_status()
            song_position = mc.status.adjusted_current_time
        else: song_position = local_music_player.music.get_pos() / 1000
        return song_position


    def pause():
        global tray, playing_status, song_position
        tray.Update(menu=menu_def_3, data_base64=UNFILLED_ICON)
        try:
            if mc is not None:
                mc.update_status()
                mc.pause()
                while not mc.is_paused: pass
                song_position = mc.status.adjusted_current_time
            else:
                song_position += local_music_player.music.get_pos() / 1000
                local_music_player.music.pause()
            playing_status = 'PAUSED'
        except UnsupportedNamespace:
            playing_status = 'NOT PLAYING'


    def resume():
        global tray, playing_status, song_end, song_position
        tray.Update(menu=menu_def_2, data_base64=FILLED_ICON)
        try:
            if mc is not None:
                mc.update_status()
                mc.play()
                mc.block_until_active()
                while not mc.is_playing: pass
                song_position = mc.status.adjusted_current_time
            else: local_music_player.music.unpause()
            song_end = time.time() + song_length - song_position
            playing_status = 'PLAYING'
        except UnsupportedNamespace:
            play_file(music_queue[0], position=song_position)


    def stop():
        global playing_status, song_position, cast
        tray.Update(menu=menu_def_1, data_base64=UNFILLED_ICON)
        if mc is not None and cast is not None and cast.app_id == 'CC1AD845': mc.stop()
        elif local_music_player.music.get_busy(): local_music_player.music.stop()
        playing_status = 'NOT PLAYING'


    def next_song(from_timeout=False):
        global playing_status
        if cast is not None and cast.app_id != 'CC1AD845': playing_status = 'NOT PLAYING'
        elif playing_status != 'NOT PLAYING' and next_queue or music_queue:
            if not settings['repeat'] or not from_timeout or not music_queue:
                settings['repeat'] = False
                save_json()
                if music_queue: done_queue.append(music_queue.pop(0))
                if next_queue: music_queue.insert(0, next_queue.pop(0))
            if music_queue: play_file(music_queue[0])
            else: stop()


    def previous():
        global playing_status
        if cast is not None and cast.app_id != 'CC1AD845': playing_status = 'NOT PLAYING'
        elif playing_status != 'NOT PLAYING':
            if done_queue:
                song = done_queue.pop()
                music_queue.insert(0, song)
                play_file(song)
            elif music_queue: play_file(music_queue[0])


    def on_press(key):
        global keyboard_command
        if str(key) == '<179>':
            if playing_status == 'PLAYING': keyboard_command = 'Pause'
            elif playing_status == 'PAUSED': keyboard_command = 'Resume'
        elif str(key) == '<176>': keyboard_command = 'Next Song'
        elif str(key) == '<177>': keyboard_command = 'Previous Song'
        elif str(key) == '<178>': keyboard_command = 'Stop'


    keyboard_command = main_window = settings_window = timer_window = pl_editor_window = pl_selector_window = None
    main_last_event = settings_last_event = None
    open_pl_selector = False
    timer = 0
    main_active = settings_active = timer_window_active = playlist_selector_active = playlist_editor_active = False
    pl_name = ''
    pl_files = []
    listener_thread = Listener(on_press=on_press)
    listener_thread.start()
    while True:
        menu_item = tray.Read(timeout=10)
        if discovery_started and time.time() - discovery_started > 5:
            discovery_started = 0
            stop_discovery()
        if menu_item == 'Refresh Devices':
            load_settings()
            update_devices = True
            stop_discovery()
            chromecasts.clear()
            device_names.clear()
            device_names.append('1. Local Device')
            stop_discovery = pychromecast.get_chromecasts(blocking=False, callback=chromecast_callback)
            discovery_started = time.time()
        if update_devices:
            update_devices = False
            if playing_status == 'PLAYING': tray.Update(menu=menu_def_2)
            elif playing_status == 'PAUSED': tray.Update(menu=menu_def_3)
            else: tray.Update(menu=menu_def_1)
        if menu_item == '__ACTIVATED__' and settings.get('DEBUG', False):
            if main_active:
                main_window.TKroot.focus_force()
                continue
            main_active = True
            if playing_status in {'PAUSED', 'PLAYING'}:
                current_song = music_queue[0]
                metadata = music_meta_data[current_song]
                # album_cover_data = metadata['album_cover_data']
                artist, title = metadata['artist'].split(', ')[0], metadata['title']
                new_playing_text = f'{artist} - {title}'
                # main_gui_layout = create_main_gui(music_queue, done_queue, playing_status, new_playing_text, album_cover_data=album_cover_data)
                main_gui_layout = create_main_gui(music_queue, done_queue, playing_status, new_playing_text)
            else: main_gui_layout = create_main_gui(music_queue, done_queue, playing_status)
            main_window = Sg.Window('Music Caster', main_gui_layout, background_color=bg, icon=WINDOW_ICON,
                                    return_keyboard_events=True, use_default_focus=False)
            main_window.Read(timeout=1)
            main_window.TKroot.focus_force()                                
        elif menu_item.split('.')[0].isdigit():  # if user selected a device
            temp = menu_item.split('. ')
            number = temp[0]
            device = ' '.join(temp[1:])
            if number == '1': new_cast = None
            else:
                try: new_cast = next(cc for cc in chromecasts if cc.device.friendly_name == device)
                except StopIteration: new_cast = None
            if cast != new_cast:
                cast = new_cast
                volume = settings['volume'] / 100
                if cast is None:
                    change_settings('previous device', None)
                    local_music_player.music.set_volume(volume)
                else:
                    change_settings('previous device', str(cast.uuid))
                    cast.wait()
                    cast.set_volume(volume)
                current_pos = 0
                if local_music_player.music.get_busy():
                    current_pos = song_position + local_music_player.music.get_pos() / 1000
                    local_music_player.music.stop()
                elif mc is not None:
                    with suppress(UnsupportedNamespace):
                        mc.update_status()  # Switch device without playback loss
                        current_pos = mc.status.adjusted_current_time
                        mc.stop()
                mc = None if cast is None else cast.media_controller
                if playing_status in {'PAUSED', 'PLAYING'}:
                    do_autoplay = False if playing_status == 'PAUSED' else True
                    play_file(music_queue[0], position=current_pos, autoplay=do_autoplay, switching_device=True)
        elif menu_item == 'Settings':
            if settings_active:
                settings_window.TKroot.focus_force()
                continue
            load_settings()
            settings_active = True
            # RELIEFS: RELIEF_RAISED RELIEF_SUNKEN RELIEF_FLAT RELIEF_RIDGE RELIEF_GROOVE RELIEF_SOLID
            settings_layout = create_settings(VERSION, music_directories, settings)
            settings_window = Sg.Window('Music Caster Settings', settings_layout, background_color=bg, icon=WINDOW_ICON,
                                        return_keyboard_events=True, use_default_focus=False)
            settings_window.Read(timeout=1)
            settings_window.TKroot.focus_force()
        elif menu_item == 'Create/Edit a Playlist':
            if playlist_selector_active:
                pl_selector_window.TKroot.focus_force()
                continue
            elif playlist_editor_active:
                pl_editor_window.TKroot.focus_force()
                continue
            load_settings()
            playlist_selector_active = True
            pl_selector_window = Sg.Window('Playlist Selector', playlist_selector(playlists), background_color=bg,
                                           icon=WINDOW_ICON, return_keyboard_events=True)
            pl_selector_window.Read(timeout=1)
            pl_selector_window.TKroot.focus_force()
        elif menu_item.startswith('PL: '):
            playlist = menu_item[4:]
            music_queue.clear()
            music_queue.extend(playlists[playlist])
            if music_queue:
                done_queue.clear()
                if settings['shuffle_playlists']: shuffle(music_queue)
                play_file(music_queue[0])
                tray.Update(menu=menu_def_2, data_base64=FILLED_ICON)
        elif menu_item == 'Set Timer':
            if timer_window_active:
                timer_window.TKroot.focus_force()
                continue
            timer_window_active = True
            timer_layout = create_timer(settings)
            timer_window = Sg.Window('Music Caster Set Timer', timer_layout, background_color=bg, icon=WINDOW_ICON,
                                     return_keyboard_events=True)
                                    
            timer_window.Read(timeout=1)
            timer_window.TKroot.focus_force()
            timer_window.Element('minutes').SetFocus()
        elif menu_item == 'Stop Timing':
            timer = 0
            if notifications_enabled: tray.ShowMessage('Music Caster', 'Timer stopped')
        elif menu_item == 'Play File':
            
            if music_directories: DEFAULT_DIR = music_directories[0]
            fd = wx.FileDialog(None, 'Select Music File', defaultDir=DEFAULT_DIR, wildcard='Audio File (*.mp3)|*mp3',
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
            if fd.ShowModal() != wx.ID_CANCEL:
                path_to_file = fd.GetPath()
                play_file(path_to_file)
                music_queue.clear()
                done_queue.clear()
                for directory in music_directories:
                    music_queue.extend([file for file in glob(f'{directory}/*.mp3') if file != path_to_file])
                shuffle(music_queue)
                music_queue.insert(0, path_to_file)
                tray.Update(menu=menu_def_2, data_base64=FILLED_ICON)
        elif menu_item == 'Play All':
            music_queue.clear()
            for directory in music_directories:
                music_queue.extend(file for file in glob(f'{directory}/*.mp3'))
            if music_queue:
                shuffle(music_queue)
                done_queue.clear()
                play_file(music_queue[0])
                tray.Update(menu=menu_def_2, data_base64=FILLED_ICON)
        elif menu_item == 'Play a File Next':
            if music_directories: DEFAULT_DIR = music_directories[0]
            fd = wx.FileDialog(None, 'Select Music File', defaultDir=DEFAULT_DIR, wildcard='Audio File (*.mp3)|*mp3',
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
            if fd.ShowModal() != wx.ID_CANCEL:
                path_to_file = fd.GetPath()
                next_queue.append(path_to_file)
                if playing_status == 'NOT PLAYING':
                    if cast is not None and cast.app_id != 'CC1AD845': cast.wait()
                    next_song()
        elif 'Stop' in {menu_item, keyboard_command}: stop()
        elif timer and time.time() > timer:
            stop()
            timer = 0
            if settings['timer_shut_off_computer']:
                if sys.platform == 'win32': os.system('shutdown /p /f')
                else: os.system('sudo shutdown now')
            elif settings['timer_hibernate_computer']:
                if sys.platform == 'win32': os.system(r'rundll32.exe powrprof.dll,SetSuspendState Hibernate')
                else: pass  # NOTE: Music Caster is developed on Windows, mainly for Windows
            elif settings['timer_sleep_computer']:
                if sys.platform == 'win32': os.system('rundll32.exe powrprof.dll,SetSuspendState 0,1,0')
                else: pass  # NOTE: Music Caster is developed on Windows, mainly for Windows
        elif 'Next Song' in {menu_item, keyboard_command} or playing_status == 'PLAYING' and time.time() > song_end:
            next_song(from_timeout=time.time() > song_end)
        elif 'Previous Song' in {menu_item, keyboard_command}: previous()
        elif menu_item == 'Repeat':
            repeat_setting = change_settings('repeat', not settings['repeat'])
            if notifications_enabled:
                if repeat_setting: tray.ShowMessage('Music Caster', 'Repeating current song')
                else: tray.ShowMessage('Music Caster', 'Not repeating current song')
        elif 'Resume' in {menu_item, keyboard_command}: resume()
        elif 'Pause' in {menu_item, keyboard_command}: pause()
        elif menu_item == 'Exit':
            tray.Hide()
            with suppress(UnsupportedNamespace):
                stop()
                # if cast is not None and cast.app_id == 'CC1AD845': cast.quit_app()
                # Commented because I am unsure if it is effective
            break
        
        # MAIN WINDOW
        if main_active:
            main_event, main_values = main_window.Read(timeout=5)
            if main_event is None:
                main_active = False
                main_window.CloseNonBlocking()
                continue
            if main_event in {'q', 'Q'} or main_event == 'Escape:27' and main_last_event != 'Add Folder':
                main_active = False
                main_window.CloseNonBlocking()
            main_last_event = main_event
            if main_event == 'Pause/Resume':
                # TODO: use images
                if playing_status == 'PAUSED': resume()
                elif playing_status == 'PLAYING': pause()
            elif main_event == 'Next': next_song()
            elif main_event == 'Prev': previous()
            elif main_event == 'Shuffle':
                shuffle_setting = change_settings('shuffle_playlists', not settings['shuffle_playlists'])
                if notifications_enabled:
                    if shuffle_setting: tray.ShowMessage('Music Caster', 'Playlist shuffling on')
                    else: tray.ShowMessage('Music Caster', 'Playlist shuffling off')
            elif main_event == 'Repeat':
                repeat_setting = change_settings('repeat', not settings['repeat'])
                if notifications_enabled:
                    if repeat_setting: tray.ShowMessage('Music Caster', 'Repeating on')
                    else: tray.ShowMessage('Music Caster', 'Repeating off')

            p_r_button = main_window.FindElement('Pause/Resume')
            now_playing_text: Sg.Text = main_window.FindElement('now_playing')
            if playing_status == 'PLAYING' and p_r_button.GetText() == 'Resume': p_r_button.Update(text='Pause')
            if playing_status == 'PAUSED' and p_r_button.GetText() == 'Pause': p_r_button.Update(text='Resume')

            if playing_status == 'PLAYING':
                metadata = music_meta_data[music_queue[0]]
                artist, title = metadata['artist'].split(', ')[0], metadata['title']
                new_playing_text = f'{artist} - {title}'
                if now_playing_text.DisplayText != new_playing_text:
                    now_playing_text.Update(value=new_playing_text)
                    # main_window.FindElement('album_cover').Update(data=metadata['album_cover_data'])
                progress_bar = main_window.FindElement('progressbar')
                update_song_position()
                progress_bar.UpdateBar(song_position / song_length * 100)
                time_left = song_length - song_position
                mins_elasped, mins_left = round(song_position / 60), round(time_left / 60)
                secs_elapsed, secs_left = round(song_position % 60), round(time_left % 60)
                if secs_left < 10: secs_left = f'0{secs_left}'
                if secs_elapsed < 10: secs_elapsed = f'0{secs_elapsed}'
                main_window.FindElement('time_elapsed').Update(value=f'{mins_elasped}:{secs_elapsed}')
                main_window.FindElement('time_left').Update(value=f'{mins_left}:{secs_left}')

        # SETTINGS WINDOW
        if settings_active:
            settings_event, settings_values = settings_window.Read(timeout=5)
            if settings_event is None:
                settings_active = False
                settings_window.CloseNonBlocking()
                continue
            settings_value = settings_values.get(settings_event)
            if settings_event in {'q', 'Q'} or settings_event == 'Escape:27' and settings_last_event != 'Add Folder':
                settings_active = False
                settings_window.CloseNonBlocking()
            elif settings_event == 'email':
                webbrowser.open('mailto:elijahllopezz@gmail.com?subject=REGARDING%20Music%20Caster')
            elif settings_event == 'copy email':
                pyperclip.copy('elijahllopezz@gmail.com')
                if settings['notifications']: tray.ShowMessage('Music Caster', f'Email address copied', time=500)
            elif settings_event in {'auto update', 'run on startup', 'notifications', 'shuffle_playlists'}:
                change_settings(settings_event, settings_value)
                if settings_event == 'run on startup': startup_setting()
                elif settings_event == 'notifications': notifications_enabled = settings_value
            elif settings_event in {'volume', 'a', 'd'} or settings_event.isdigit():
                update_slider = False
                delta = 0
                if settings_event.isdigit():
                    update_slider = True
                    new_volume = int(settings_event) * 10
                else:
                    if settings_event == 'a':
                        delta = -5
                    elif settings_event == 'd':
                        delta = 5
                    new_volume = settings_values['volume'] + delta
                change_settings('volume', new_volume)
                volume = new_volume / 100
                if update_slider or delta != 0: settings_window.Element('volume').Update(value=new_volume)
                if cast is None:
                    local_music_player.music.set_volume(volume)
                else:
                    cast.set_volume(volume)
            elif settings_event == 'Remove Folder' and settings_values['music_dirs']:
                selected_item = settings_values['music_dirs'][0]
                if selected_item in music_directories:
                    music_directories.remove(selected_item)
                    save_json()
                    settings_window.Element('music_dirs').Update(music_directories)
            elif settings_event == 'Add Folder':
                if settings_value not in music_directories and os.path.exists(settings_value):
                    music_directories.append(settings_value.replace('\\', '/'))
                    save_json()
                    settings_window.Element('music_dirs').Update(music_directories)
            elif settings_event == 'Open Settings': os.startfile(settings_file)
            settings_last_event = settings_event
        if playlist_selector_active:
            # TODO: delete key
            pl_selector_event, pl_selector_values = pl_selector_window.Read()
            if pl_selector_event in {None, 'Escape:27', 'q', 'Q'}:
                playlist_selector_active = False
                pl_selector_window.CloseNonBlocking()
                continue
            if pl_selector_event == 'del_pl':
                pl_name = pl_selector_values.get('pl_selector', '')
                if pl_name in playlists: del playlists[pl_name]
                new_values = list(playlists.keys())
                value = new_values[0] if new_values else ''
                # pl_selector_window.Element('pl_selector').Update(value=value, values=new_values)
                pl_selector_window.CloseNonBlocking()
                pl_selector_window = Sg.Window('Playlist Selector', playlist_selector(playlists), background_color=bg,
                                           icon=WINDOW_ICON, return_keyboard_events=True)
                pl_selector_window.Read(timeout=1)
                pl_selector_window.TKroot.focus_force()
                save_json()
                tray_playlists.clear()
                tray_playlists.append('Create/Edit a Playlist')
                tray_playlists += [f'PL: {pl}' for pl in playlists.keys()]
                if playing_status == 'PLAYING': tray.Update(menu=menu_def_2)
                elif playing_status == 'PAUSED': tray.Update(menu=menu_def_3)
                else: tray.Update(menu=menu_def_1)
            elif pl_selector_event in {'edit_pl', 'create_pl'}:
                pl_name = pl_selector_values.get('pl_selector', '') if pl_selector_event == 'edit_pl' else ''
                # https://github.com/PySimpleGUI/PySimpleGUI/issues/845#issuecomment-443862047
                pl_editor_window = Sg.Window('Playlist Editor', playlist_editor(DEFAULT_DIR, playlists, pl_name),
                                             background_color=bg, icon=WINDOW_ICON, return_keyboard_events=True)
                pl_files = playlists.get(pl_name, [])
                pl_selector_window.CloseNonBlocking()
                pl_editor_window.Read(timeout=1)
                pl_editor_window.TKroot.focus_force()
                if pl_selector_event == 'create_pl': pl_editor_window.Element('playlist_name').SetFocus()
                else:
                    pl_editor_window.Element('songs').SetFocus()
                    pl_editor_window.Element('songs').Update(set_to_index=0)
                playlist_selector_active = False
                playlist_editor_active = True
        if playlist_editor_active:
            # TODO: delete key
            pl_editor_event, pl_editor_values = pl_editor_window.Read(timeout=1)
            # if pl_editor_event != '__TIMEOUT__':
            #     print(pl_editor_event)
            if pl_editor_event in {None, 'Escape:27', 'q', 'Q', 'Cancel'}:
                playlist_editor_active = False
                pl_editor_window.CloseNonBlocking()
                open_pl_selector = True
            elif pl_editor_event == 'Save':
                new_name = pl_editor_values['playlist_name']
                pl_files = pl_files.copy()
                if pl_name != new_name:
                    if pl_name in playlists: del playlists[pl_name]
                    pl_name = new_name
                playlists[pl_name] = pl_files
                save_json()
                playlist_editor_active = False
                pl_editor_window.CloseNonBlocking()
                open_pl_selector = True
                tray_playlists.clear()
                tray_playlists.append('Create/Edit a Playlist')
                tray_playlists += [f'PL: {pl}' for pl in playlists.keys()]
                if playing_status == 'PLAYING': tray.Update(menu=menu_def_2)
                elif playing_status == 'PAUSED': tray.Update(menu=menu_def_3)
                else: tray.Update(menu=menu_def_1)
            elif pl_editor_event == 'Move up':
                if pl_editor_values['songs']:
                    index_to_move = pl_editor_window.Element('songs').GetListValues().index(pl_editor_values['songs'][0])
                    if index_to_move > 0:
                        new_i = index_to_move - 1
                        pl_files.insert(new_i, pl_files.pop(index_to_move))
                        formatted_songs = [f'{i+1}. {os.path.basename(path)}' for i, path in enumerate(pl_files)]
                        pl_editor_window.Element('songs').Update(values=formatted_songs, set_to_index=new_i, scroll_to_index=new_i)
            elif pl_editor_event == 'Move down':
                if pl_editor_values['songs']:
                    index_to_move = pl_editor_window.Element('songs').GetListValues().index(pl_editor_values['songs'][0])
                    if index_to_move < len(pl_files) - 1:
                        new_i = index_to_move + 1
                        pl_files.insert(new_i, pl_files.pop(index_to_move))
                        formatted_songs = [f'{i+1}. {os.path.basename(path)}' for i, path in enumerate(pl_files)]
                        pl_editor_window.Element('songs').Update(values=formatted_songs, set_to_index=new_i, scroll_to_index=new_i)
            elif pl_editor_event == 'Add files':
                new_files = [file.replace('\\', '/') for file in pl_editor_values['Add files'].split(';') if file.endswith('.mp3')]
                pl_files += new_files
                pl_editor_window.TKroot.focus_force()
                # current_songs = pl_editor_window.Element('songs').GetListValues()
                formatted_songs = [f'{i+1}. {os.path.basename(path)}' for i, path in enumerate(pl_files)]
                new_i = len(formatted_songs) - 1  # - len(new_files)
                pl_editor_window.Element('songs').Update(formatted_songs, set_to_index=new_i, scroll_to_index=new_i)
            elif pl_editor_event == 'Remove file':
                if pl_editor_values['songs']:
                    index_to_rm = pl_editor_window.Element('songs').GetListValues().index(pl_editor_values['songs'][0])
                    with suppress(ValueError): pl_files.pop(index_to_rm)
                    formatted_songs = [f'{i+1}. {os.path.basename(path)}' for i, path in enumerate(pl_files)]
                    new_i = max(index_to_rm - 1, 0)
                    pl_editor_window.Element('songs').Update(formatted_songs, set_to_index=new_i, scroll_to_index=new_i)
            elif pl_editor_event in {'Up:38', 'Down:40', 'Prior:33', 'Next:34'}:
                move = {'Up:38': -1, 'Down:40': 1, 'Prior:33': -3, 'Next:34': 3}[pl_editor_event]
                new_i = pl_editor_window.Element('songs').GetListValues().index(pl_editor_values['songs'][0]) + move
                new_i = min(max(new_i, 0), len(pl_files) - 1)
                pl_editor_window.Element('songs').Update(set_to_index=new_i, scroll_to_index=new_i)
            if open_pl_selector:
                open_pl_selector = False
                playlist_selector_active = True
                pl_selector_window = Sg.Window('Playlist Selector', playlist_selector(playlists), background_color=bg,
                                           icon=WINDOW_ICON, return_keyboard_events=True)
                pl_selector_window.Read(timeout=1)
                pl_selector_window.TKroot.focus_force()
                # bring back the playlist selector
        if timer_window_active:
            timer_event, timer_values = timer_window.Read(timeout=1)
            if timer_event is None:
                timer_window_active = False
                timer_window.CloseNonBlocking()
                continue
            timer_value = timer_values.get(timer_event, None)
            if timer_event in {'Escape:27', 'q', 'Q'}:
                timer_window_active = False
                timer_window.CloseNonBlocking()
            elif timer_event in {'\r', 'special 16777220', 'special 16777221', 'Submit'}:
                try:
                    timer_value = timer_values['minutes']
                    if timer_value.isdigit():
                        minutes = abs(float(timer_values['minutes']))
                    elif timer_value.count(':') == 1:
                        now = datetime.now()
                        # meridiem = time.strftime('%p')
                        if timer_value[-3:].strip().upper() in ('PM', 'AM'): timer_value = timer_value[timer_value:-3]
                        elif timer_value[-2:].upper() in ('PM', 'AM'): timer_value = timer_value[timer_value:-2]
                        to_stop = datetime.strptime(timer_value + time.strftime(',%Y,%m,%d,%p'), '%I:%M,%Y,%m,%d,%p')
                        delta = (to_stop - datetime.now()).total_seconds()
                        # Suppose you want to stop music at at 12:00 AM, but it's 11:00 PM.
                        # 12:00 AM -> would make delta = -39,600 seconds (-11 Hours)
                        # We want this to be 3600 seconds
                        # 43,200 - 39,600 = 3600
                        if delta < 0: delta += 43200
                        minutes = delta // 60
                    else: continue
                    timer = time.time() + 60 * minutes
                    if notifications_enabled:
                        timer_set_to = datetime.now() + timedelta(minutes=minutes)
                        timer_set_to = timer_set_to.strftime('%#I:%M %p')
                        # timer_set_to = timer_set_to.strftime('%-I:%M %p')  # Linux
                        tray.ShowMessage('Music Caster', f'Timer set for {timer_set_to}', time=500)
                    timer_window_active = False
                    timer_window.CloseNonBlocking()
                except ValueError:
                    Sg.PopupOK('Input a number!')
            elif timer_event == 'shut_off':
                if timer_value:
                    # Maybe use if statements? e.g. if timer_values['hibernate']:
                    timer_window.Element('hibernate').Update(False)
                    timer_window.Element('sleep').Update(False)
                    change_settings('timer_hibernate_computer', False)
                    change_settings('timer_sleep_computer', False)
                change_settings('timer_shut_off_computer', timer_value)
            elif timer_event == 'hibernate':
                if timer_value:
                    timer_window.Element('shut_off').Update(False)
                    timer_window.Element('sleep').Update(False)
                    change_settings('timer_shut_off_computer', False)
                    change_settings('timer_sleep_computer', False)
                change_settings('timer_hibernate_computer', timer_value)
            elif timer_event == 'sleep':
                if timer_value:
                    timer_window.Element('shut_off').Update(False)
                    timer_window.Element('hibernate').Update(False)
                    change_settings('timer_shut_off_computer', False)
                    change_settings('timer_hibernate_computer', False)
                change_settings('timer_sleep_computer', timer_value)
        keyboard_command = None
        if mc is not None and time.time() - cast_last_checked > 5:
            with suppress(UnsupportedNamespace):
                if cast is not None:
                    if cast.app_id == 'CC1AD845':
                        mc.update_status()
                        if mc.is_paused and playing_status != 'PAUSED': pause()
                        elif mc.is_playing and playing_status != 'PLAYING': resume()
                        elif not (mc.is_paused or mc.is_playing) and playing_status != 'NOT PLAYING': stop()
                        # TODO: check if playback was scrubbed +- 0.2 secs
                        volume = settings['volume']
                        cast_volume = cast.status.volume_level * 100
                        if volume != cast_volume:
                            volume = change_settings('volume', cast_volume)
                    elif playing_status in {'PAUSED', 'PLAYING'}: stop()
            cast_last_checked = time.time()
        if time.time() - settings_last_loaded > 10:
            load_settings()
            if playing_status == 'PLAYING': tray.Update(menu=menu_def_2)
            elif playing_status == 'PAUSED': tray.Update(menu=menu_def_3)
            else: tray.Update(menu=menu_def_1)
except Exception as e:
    if settings.get('DEBUG', False): raise e
    with open(f'{starting_dir}/error.log', 'a+') as f:
        f.write(str(datetime.now()))
        f.write('\n')
        f.write(traceback.format_exc())
        f.write('\n')
    tray.ShowMessage('Music Caster', 'An error has occured. Please check error.log and email the author.')
    # noinspection PyUnboundLocalVariable
    stop()
