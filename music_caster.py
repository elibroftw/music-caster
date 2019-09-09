from bs4 import BeautifulSoup
from contextlib import suppress
from datetime import datetime, timedelta
from flask import Flask
from getpass import getuser
from glob import glob
import io
import json
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3
import mutagen
import os
from pathlib import Path
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
from time import time
import threading
import traceback
import webbrowser
import win32api
import win32com.client
import win32event
from winerror import ERROR_ALREADY_EXISTS
import zipfile

VERSION = '4.12.2'
starting_dir = os.path.dirname(os.path.realpath(__file__)).replace('\\', '/')
home_music_dir = str(Path.home()).replace('\\', '/') + '/Music'
settings = {  # default settings
        'previous device': None,
        'comments': ['Edit only the variables below', 'Restart Music Caster after editing this file!'],
        'auto update': False,
        'run on startup': True,
        'notifications': True,
        'volume': 100,
        'local volume': 100,
        'music directories': [home_music_dir],
        'sample music directories': [
            'C:/Users/maste/Documents/MEGAsync/Music',
            'Put in a valid path',
            'First path is the default directory when selecting a file to play. FOR NOW'
        ],
        'repeat': False,
        'timer_shut_off_computer': False,
        'playlists': {},
        'playlists_example': {'NAME': ['PATHS']},
        'DEBUG': False
    }
settings_file = f'{starting_dir}/settings.json'
try:    
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
        if outfile is None: z.extract(infile)
        else:
            new_file = z.open(infile)
            target = open(outfile, 'wb')
            with new_file, target: copyfileobj(new_file, target)


    def startup_setting():
        run_on_startup = settings['run on startup']
        shortcut_exists = os.path.exists(shortcut_path)
        if run_on_startup and not shortcut_exists and not settings.get('DEBUG'):
            shell = win32com.client.Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(shortcut_path)
            if getattr(sys, 'frozen', False):  # Running in a bundle
                # C:\Users\maste\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup
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


    # check if settings file is valid
    if os.path.exists(settings_file):
        with open(settings_file) as json_file:
            loaded_settings: dict = json.load(json_file)
            save_settings = False
            for setting_name, setting_value in settings.items():
                if setting_name not in loaded_settings:
                    loaded_settings[setting_name] = setting_value
                    save_settings = True
            for setting_name in list(loaded_settings.keys()):
                if setting_name not in settings: loaded_settings.pop(setting_name)
            settings = loaded_settings
        if save_settings: save_json()
    else: save_json()
    # Check if app is running already
    mutex = win32event.CreateMutex(None, False, 'name')
    last_error = win32api.GetLastError()
    if last_error == ERROR_ALREADY_EXISTS and not settings.get('DEBUG', False): sys.exit()
    UNFILLED_ICON = b'iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAQAAAD/5HvMAAAABGdBTUEAALGPC/xhBQAAACBjSFJN\nAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAAmJLR0QA/4ePzL8AAAAHdElN\nRQfjBw4ALiA+kkFLAAACWElEQVRo3u2ZsUsbURzHo2Bc0kkMDoYirRkcpEu7NtAubo7ZPXDo6qaL\nkyUIQtshkE6CkA79C4SqWIiLi5N2iBQ7WgRvUNvGj0OG/n737kLt9d476PuOvx9JPnn3e9/v3b1C\nwcvLy8srSQwR0CHEpi7pEDAUhzPBNq60zYS5Ou5w+kh6lQhwrUADHTgH6mig0DlQqIGErO7spN/1\nQB7IA3kg10DObnk8kAf6b4C44ZxTDmmzSp3JXPkQAF9o8oLh/AD1dcYalTwBAdzQ4lGegAB+sk4p\nT0AA35i3CVRkjClqLPKGI24ToN4x6sSHGGeB3Visw3875PcyRqb5EAN1xoxDp+Ypnwyk7zxzGh3M\n0TWQZhwCFQqMsWtcuEq2uyzkhB22WGE29oMjNI3xHrXlQ1024rB4xS9tAjaNsccmD2OQtObtOvU1\nDYqRL2hG3LtkEwjgM+XILOnxXrefZV95EtlxXRW7j7MBKlGlxhL79Mx3WxGkOdV9n7EPUabBlbFK\n+sJJ9/6RxpH+NFwrfDRmqagCRWbcaytOzXIkWBuq21auPWwlOqgrpGvpS0yr3ktLWcayWqNN1ZPb\nv5lFlh3TMv+pmqWeDBQW5ENTdj60RzUy3nLHbai7SnnRJrMzxgueq05Dxq7qHIlOPUunvpCrRFlZ\npbxob0V99Z7PMDEnZ4OiY0/19kVnRdQXRb2dGqgzOMvEeLMk6luiXpO3a6mBgsFArYQf3hH1KVE/\nTQlkHOBFdSx6VVE/Ubn/W+epgGKOOAecXvEgoV6UryT+EihMPAT28vLy8urrDgm99Mb0O5qlAAAA\nJXRFWHRkYXRlOmNyZWF0ZQAyMDE5LTA3LTE0VDAwOjQ2OjMyKzAwOjAwaWwEjwAAACV0RVh0ZGF0\nZTptb2RpZnkAMjAxOS0wNy0xNFQwMDo0NjozMiswMDowMBgxvDMAAAAASUVORK5CYII=\n'
    FILLED_ICON = b'iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAQAAAD/5HvMAAAABGdBTUEAALGPC/xhBQAAACBjSFJN\nAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAAmJLR0QA/4ePzL8AAAAHdElN\nRQfjBw4ALiA+kkFLAAACxUlEQVRo3u2ZT0hUURSHn0bjxtpIYqCElLNwEW1yWYO1yF3L2fvARVs3\nqRtX2SAIJTFgK0HQRdJeaBSDaePGlYaoYUtD8C3ScvpaKHTOfe8NOu/fQPe3PGec+bz3nN+57z7H\nsbKysrIKEy24VPFIU8dUcWkJwulihay0Qpd/dbLDOUfSq4RL1nI10JfMgaoayMscyNNAQql2dtjv\nWiAL9N8AJdHfFigWoMvscXMAnTUb0G3G2GkioIuz0iDLTQR08acDVJoKyHEch2dsptX2pxyyxwaL\nTFKkOxQpx2tqKfsQAF8p84TWQKhH7KcPdK4DXtETgHSTj9kAAZwyx10fUivvsgIC+M007T6oseyA\nAL7z3IfkJgeUo4NeCozwhk3+hHzXLG3RV6kBH+IWw6wGYm2YRX71WmrYGOljKQDqgH71qWtX7bho\nw/Uhn3zf+IMBwwT2Ux0dDLHrQ+o3rLKW6iyjg1XfxqlaYiruLvPYpsICE9wPRLpO2VfebapLN5Pz\noV1mgrB4YZwfZ42TQKLGWGOeOwFIWsoqL3teatypTyiRM5DKhnu3qyNcCqPjM51GLenynlbZ5TRm\n2TceGB23q8buPZEbjA+onTwFRlkPcBTPQBpS2ffqcWAndh+ikxI/faukN0669y/pSLxMZrj28MFX\nSzk1UOSMm1LPcWcJOTXjxmAtqeyicu3W2K9jAj9cVEgn0pfoU7mnqQA5DuNqjeZVTrZ/Of4LK48t\n5vz/qaqlmhwoDMuHpuRu0NbIG+UtO25GnSrlpnUnd6V3xGOVKcmxqzJyvhcTvGPkSK4Sncoq5aa9\nFfHJyNdcx/VGx5rKrYvMhIiPiPhiZKBq/VkmyptREV8Q8YI8rkUGcusDzYX8cEXEe0V8LyKQ7wWe\nqS2Ry4v4tpr7/3QYCSjgFWedt1fcCInn5JVEg0Be6EtgKysrK6tz/QVPmZ3Bw5RmTgAAACV0RVh0\nZGF0ZTpjcmVhdGUAMjAxOS0wNy0xNFQwMDo0NjozMiswMDowMGlsBI8AAAAldEVYdGRhdGU6bW9k\naWZ5ADIwMTktMDctMTRUMDA6NDY6MzIrMDA6MDAYMbwzAAAAAElFTkSuQmCC\n'
    WINDOW_ICON = b'iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAQAAAD/5HvMAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAAmJLR0QA/4ePzL8AAAAHdElNRQfjBxIQARbl3afoAAACwElEQVRo3u2ZPUxTURiGH2osS3UhNphADFE6MBgXGbVBB9kcu9OEwZVFYGESGxISJaRJnUhIygBxJ7EQTOrC0gkMKRgcMSTcQVDqdejg+c49t1HuXxPPe7fvu7336fl5v3PPASsrKysrX/VQpI6DG+N1Rp0iPSacfjZjRVGvTfq9rZMcThtJa6ViojguLkUJ9ClxoLoEchIHciSQmopTvu+1QBbovwGKYoJboFCA/qaPuwLostuAbjPNQTcBtddKY2x0E1Bbo9S6CwjgGY24gC444ZBdqsxRYMAXKc1rWnH7kIvLZ8o8IWWEesRR/EDt65hXDBqQbvI+GSAXlwsq3PUgpVhOCsjF5ScLZDxQ08kBubh85bkHqRgdUJo+hsgzyRsa/PJ51BK9IbTSFXzoFhNsGbF2PYN8OT5jHGbNAHXMiLjr2j/PuEBO/ZAPngd+Y1QzgaN4S8c4TQ/SiGaVrXhrWR9bno6TY2k+bCCHfWqsMst9I9J1yp7h3StmaSM6H2qyaMR6oa0fl7SVQKTG2GKFOwYkeZe0ylrUTn1OibSGVNbcOyOWcDGUjo9ktbEkh/eCyG7EUcu+8ECbcU1Rdu8pubHwgDLkyDPFjsFRHA1pXGTfic+Bg/B9KEuJ755Wkh2nuvcP4UgvozHGQdY9YyktCopa4+bFd9xlVE49oxXWkshWhWunwt+OMakgkM6FLw2L3NN4gGBG/GBF5NTpXw4fyGGPiuGfrgv3VgvKhPhoimwHbZucNrzVGbcoVpVqpw1Et6V3ymORKYmyq0qt74Uo9xhPRStlhVWqnfZWic8F3uY661Q6tkVuR8nMKvFJJV4NDFTvXMvU4T2lxFeVeF4s14ICFTsDVXxeXFPiQ0r8MCCQ5wBPv2FPyeWU+L6o+3/iJ4GADEecnU6vbvjE02JL4mpAjv8hsJWVlZUVAL8BFtCPUbUhaGYAAAAldEVYdGRhdGU6Y3JlYXRlADIwMTktMDctMThUMTU6NTg6MTArMDA6MDBEk3wFAAAAJXRFWHRkYXRlOm1vZGlmeQAyMDE5LTA3LTE4VDE1OjU4OjEwKzAwOjAwNc7EuQAAAABJRU5ErkJggg=='
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
            release_entry = soup.find('div', class_='release-entry')
            latest_version = release_entry.find('a', class_='muted-link css-truncate')['title'][1:]
            major, minor, patch = (int(x) for x in VERSION.split('.'))
            lt_major, lt_minor, lt_patch = (int(x) for x in latest_version.split('.'))
            if (lt_major > major or lt_major == major and lt_minor > minor
                    or lt_major == major and lt_minor == minor and lt_patch > patch):
                details = release_entry.find('details',
                                            class_='details-reset Details-element border-top pt-3 mt-4 mb-2 mb-md-4')
                download_links = [link['href'] for link in details.find_all('a') if link.get('href')]
                bundle_download_link = f'https://github.com{download_links[1]}'
                source_download_link = f'https://github.com{download_links[-2]}'
                os.chdir(starting_dir)
                tray = sg.SystemTray(menu=['File', []], data_base64=UNFILLED_ICON, tooltip='Music Caster')
                tray.ShowMessage('Music Caster', 'Downloading Update...')
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

    shortcut_path = f'C:/Users/{getuser()}/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/Music Caster.lnk'

    startup_setting()
    update_devices = False
    chromecasts = []
    device_names = ['1. Local Device']
    cast = None
    local_music_player.init(44100, -16, 2, 2048)
    stop_discovery = pychromecast.get_chromecasts(blocking=False, callback=chromecast_callback)
    discovery_started = time()
    menu_def_1 = ['', ['Settings', 'Refresh Devices', 'Select &Device', device_names, 'Play &File', 'Play All', 'E&xit']]

    menu_def_2 = ['', ['Settings', 'Refresh Devices', 'Select &Device', device_names, 'Set timer', 'Play &File',
                    'Play Next...', 'Play All', 'Repeat', 'Stop', 'Pause', 'Previous Song', 'Next Song', 'E&xit']]

    menu_def_3 = ['', ['Settings', 'Refresh Devices', 'Select &Device', device_names, 'Set timer', 'Play &File',
                    'Play Next...', 'Play All', 'Repeat', 'Stop', 'Resume', 'Previous Song', 'Next Song', 'E&xit']]
    tray = sg.SystemTray(menu=menu_def_1, data_base64=UNFILLED_ICON, tooltip='Music Caster')
    notifications_enabled = settings['notifications']
    if notifications_enabled: tray.ShowMessage('Music Caster', 'Music Caster is running in the tray', time=500)
    music_directories = settings['music directories']
    if not music_directories: music_directories = change_settings('music directories', [home_music_dir])
    DEFAULT_DIR = music_directories[0]

    music_queue = []
    done_queue = []
    next_queue = []
    mc = None
    song_end = song_length = song_position = song_start = 0
    playing_status = 'NOT PLAYING'
    cast_last_checked = time()
    # Styling
    fg = '#aaaaaa'
    bg = '#121212'
    font_normal = 'SourceSans', 11
    font_link = 'SourceSans', 11, 'underline'
    button_color = ('black', '#4285f4')


    def play_file(file_path, position=0, autoplay=True):
        global mc, song_start, song_end, playing_status, song_length, song_position, volume, images_dir, cast_last_checked, music_queue
        while not os.path.exists(file_path): 
            music_queue.remove(file_path)
            file_path = music_queue[0]
            position=0
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
        if cast is None:
            mc = None
            sampling_rate = audio_info.sample_rate
            local_music_player.quit()
            local_music_player.init(sampling_rate, -16, 2, 2048)
            local_music_player.music.load(file_path)
            local_music_player.music.set_volume(volume)
            local_music_player.music.play(start=position)
            if not autoplay: local_music_player.music.pause()
            song_start = time()
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
            cast.set_volume(volume)
            mc = cast.media_controller
            if mc.is_playing or mc.is_paused:
                mc.stop()
                mc.block_until_active(5)
            music_metadata = {'metadataType': 3, 'albumName': album, 'title': title, 'artist': artist}
            mc.play_media(url, 'audio/mp3', current_time=position, metadata=music_metadata, thumb=thumb, autoplay=autoplay)
            mc.block_until_active()
            while not mc.is_playing: pass
            song_start = time()
            song_end = song_start + song_length - position
        if notifications_enabled and not settings['repeat']:
            tray.ShowMessage('Music Caster', f"Playing: {artist.split(', ')[0]} - {title}", time=500)
        if autoplay:
            playing_status = 'PLAYING'
            tray.Update(menu=menu_def_2, data_base64=FILLED_ICON)
        cast_last_checked = time()


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
            else:
                local_music_player.music.unpause()
            song_end = time() + song_length - song_position
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


    keyboard_command = settings_window = timer_window = None
    timer = 0
    settings_active = timer_window_active = False
    listener_thread = Listener(on_press=on_press)
    listener_thread.start()
    while True:
        menu_item = tray.Read(timeout=30)
        if discovery_started and time() - discovery_started > 5:
            discovery_started = 0
            stop_discovery()
        if menu_item == 'Refresh Devices':
            update_devices = True
            stop_discovery()
            chromecasts.clear()
            device_names.clear()
            device_names.append('1. Local Device')
            stop_discovery = pychromecast.get_chromecasts(blocking=False, callback=chromecast_callback)
            discovery_started = time()
        if update_devices:
            update_devices = False
            if playing_status == 'PLAYING': tray.Update(menu=menu_def_2)
            elif playing_status == 'PAUSED': tray.Update(menu=menu_def_3)
            else: tray.Update(menu=menu_def_1)
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
                    play_file(music_queue[0], position=current_pos, autoplay=False if playing_status == 'PAUSED' else True)
        elif menu_item == 'Settings' and not settings_active:
            settings_active = True
            # RELIEFS: RELIEF_RAISED RELIEF_SUNKEN RELIEF_FLAT RELIEF_RIDGE RELIEF_GROOVE RELIEF_SOLID
            settings_layout = [
                [Sg.Text(f'Music Caster Version {VERSION} by Elijah Lopez', text_color=fg, background_color=bg,
                        font=font_normal)],
                [Sg.Text(f'Email:', text_color='#3ea6ff', background_color=bg, font=font_normal),
                Sg.Text(f'elijahllopezz@gmail.com', text_color='#3ea6ff', background_color=bg, font=font_link, click_submits=True, key='email'),
                Sg.Button(button_text='Copy address', button_color=button_color, key='copy email', enable_events=True, font=font_normal)],
                [Sg.Checkbox('Auto Update', default=settings['auto update'], key='auto update', text_color=fg,
                            background_color=bg, font=font_normal, enable_events=True)],
                [Sg.Checkbox('Run on Startup', default=settings['run on startup'], key='run on startup', text_color=fg,
                            background_color=bg, font=font_normal, enable_events=True)],
                [Sg.Checkbox('Enable Notifications', default=settings['notifications'], key='notifications', text_color=fg,
                            background_color=bg, font=font_normal, enable_events=True)],
                [Sg.Slider((0, 100), default_value=settings['volume'], orientation='horizontal', key='volume',
                        tick_interval=5, enable_events=True, background_color='#4285f4', text_color='black',
                        size=(50, 15))],
                [Sg.Listbox(music_directories, size=(41, 5), select_mode=Sg.SELECT_MODE_SINGLE, text_color=fg,
                            key='music_dirs', background_color=bg, font=font_normal, enable_events=True),
                Sg.Frame('', [
                    [Sg.Button(button_text='Remove Selected Folder', button_color=button_color, key='Remove Folder',
                                enable_events=True, font=font_normal)],
                    [Sg.FolderBrowse('Add Folder', button_color=button_color, font=font_normal, enable_events=True)],
                    [Sg.Button('Open Settings File', key='Open Settings', button_color=button_color, font=font_normal,
                                enable_events=True)]], background_color=bg, border_width=0)]
            ]
            settings_window = Sg.Window('Music Caster Settings', settings_layout, background_color=bg, icon=WINDOW_ICON,
                                        return_keyboard_events=True, use_default_focus=False)
            settings_window.Finalize()
            settings_window.TKroot.focus_force()
            # settings_window.GrabAnyWhereOn()
        elif menu_item == 'Set timer' and not timer_window_active:
            timer_window_active = True
            settings_layout = [
                [Sg.Checkbox('Shut off computer', default=settings['timer_shut_off_computer'], key='shut_off',
                             text_color=fg, background_color=bg, font=font_normal, enable_events=True)],
                [Sg.Text(f'Enter minutes', text_color=fg, background_color=bg, font=font_normal)],
                [Sg.Input(key='minutes', focus=True), Sg.Submit()]
            ]
            timer_window = Sg.Window('Music Caster Set Timer', settings_layout, background_color=bg, icon=WINDOW_ICON,
                                     return_keyboard_events=True, use_default_focus=False)
            timer_window.Finalize()
            timer_window.TKroot.focus_force()
        elif menu_item == 'Play File':
            # maybe add *flac compatibility https://mutagen.readthedocs.io/en/latest/api/flac.html
            # path_to_file = sg.PopupGetFile('', title='Select Music File', file_types=(('Audio', '*mp3'),),
            #                                initial_folder=DEFAULT_DIR, no_window=True)
            if music_directories: DEFAULT_DIR = music_directories[0]
            fd = wx.FileDialog(None, 'Select Music File', defaultDir=DEFAULT_DIR, wildcard='Audio File (*.mp3)|*mp3',
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
            if fd.ShowModal() != wx.ID_CANCEL:
                path_to_file = fd.GetPath()
                # if os.path.exists(path_to_file):
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
        elif menu_item == 'Play Next...':
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
        elif timer and time() > timer:
            stop()
            timer = None
            if settings['timer_shut_off_computer']:
                if sys.platform == 'win32':
                    os.system('shutdown /p /f')
                else: os.system('sudo shutdown now')
        elif 'Next Song' in {menu_item, keyboard_command} or playing_status == 'PLAYING' and time() > song_end:
            next_song(from_timeout=time() > song_end)
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
                if cast is not None and cast.app_id == 'CC1AD845': cast.quit_app()
                elif local_music_player.music.get_busy(): local_music_player.music.stop()
            break
        # SETTINGS WINDOW
        if settings_active:
            settings_event, settings_values = settings_window.Read(timeout=10)
            if settings_event is None: settings_active = False; continue
            settings_value = settings_values.get(settings_event)
            if settings_event in {'Esc', 'q'}:
                settings_active = False
                settings_window.CloseNonBlocking()
            elif settings_event == 'email':
                webbrowser.open('mailto:elijahllopezz@gmail.com?subject=REGARDING%20Music%20Caster')
            elif settings_event == 'copy email':
                pyperclip.copy('elijahllopezz@gmail.com')
                if settings['notifications']: tray.ShowMessage('Music Caster', f'Email address copied', time=500)
            elif settings_event in {'auto update', 'run on startup', 'notifications'}:
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
        if timer_window_active:
            timer_event, timer_values = timer_window.Read(timeout=10)
            if timer_event is None: timer_window_active = False
            elif timer_event in {'Esc', 'q'}:
                timer_window_active = False
                timer_window.CloseNonBlocking()
            elif timer_event == 'Submit':
                try:
                    minutes = abs(float(timer_values['minutes']))
                    timer = time() + 60 * minutes
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
                change_settings('timer_shut_off_computer', timer_values['shut_off'])
        keyboard_command = None
        if mc is not None and time() - cast_last_checked > 2:
            with suppress(UnsupportedNamespace):
                if cast is not None:
                    if cast.app_id == 'CC1AD845':
                        mc.update_status()
                        if mc.is_paused and playing_status != 'PAUSED': pause()
                        elif mc.is_playing and playing_status != 'PLAYING': resume()
                        elif not (mc.is_paused or mc.is_playing) and playing_status != 'NOT PLAYING': stop()
                        # TODO: check if playback was scrubbed
                        volume = settings['volume']
                        cast_volume = int(cast.status.volume_level * 100)  # TODO: remove int
                        if volume != cast_volume:
                            volume = change_settings('volume', cast_volume)
                    elif playing_status in {'PAUSED', 'PLAYING'}: stop()
            cast_last_checked = time()
except Exception as e:
    if settings.get('DEBUG', False): raise e
    with open(f'{starting_dir}/error.log', 'a+') as f:
        f.write(str(datetime.now()))
        f.write('\n')
        f.write(traceback.format_exc())
        f.write('\n')
    tray.ShowMessage('Music Caster', 'An error has occured. Email author.')
    stop()
