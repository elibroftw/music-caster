import io
import zipfile
from contextlib import suppress
from bs4 import BeautifulSoup
from flask import Flask
from getpass import getuser
from glob import glob
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
import socket
import PySimpleGUI as Sg
# noinspection PyPep8Naming
import PySimpleGUIWx as sg
import wx
from random import shuffle
import requests
from shutil import copyfile
from subprocess import Popen
import sys
from time import time
import threading
import win32api
import win32com.client
import win32event
from winerror import ERROR_ALREADY_EXISTS

# Check if app is running already
mutex = win32event.CreateMutex(None, False, 'name')
last_error = win32api.GetLastError()
if last_error == ERROR_ALREADY_EXISTS: sys.exit()

CURRENT_VERSION = '4.6.4'
starting_dir = os.path.dirname(os.path.realpath(__file__))
images_dir = starting_dir + '/images'
cc_music_dir = starting_dir + '/music files'
if not os.path.exists('music files'): os.mkdir('music files')
if not os.path.exists('images'): os.mkdir('images')
if not os.path.exists('images/default.png'):
    if os.path.exists('resources/default.png'):  # running from source code
        copyfile('resources/default.png', 'images/default.png')
    else:  # just in case the user decided to delete the default image
        response = requests.get('https://raw.githubusercontent.com/elibroftw/music-caster/master/resources/default.png', stream=True)
        with open('images/default.png', 'wb') as handle:
            for data in response.iter_content():
                handle.write(data)
for file in glob('music files/*.*'):
    os.remove(file)
for file in glob('images/*.*'):
    file = file.replace('\\', '/')
    if file != 'images/default.png': os.remove(file)
os.chdir(os.getcwd()[:3])
PORT = 2001
app = Flask(__name__, static_folder='/', static_url_path='/')
while True:
    try:
        threading.Thread(target=app.run, daemon=True, kwargs={'host': '0.0.0.0', 'port': PORT}).start()
        break
    except OSError:
        PORT += 1

home_music_dir = str(Path.home()).replace('\\', '/') + '/Music'
settings = {  # default settings
    'previous device': None,
    'comments': ['Edit only the variables below', 'Restart the program after editing this file!'],
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
    'playlists': {},
    'playlists_example': {'NAME': ['PATHS']}
}
settings_file = f'{starting_dir}/settings.json'


def save_json():
    with open(settings_file, 'w') as outfile:
        json.dump(settings, outfile, indent=4)


def change_settings(name, value):
    settings[name] = value
    save_json()
    return value


# check if settings file is valid
if os.path.exists(settings_file):
    with open(settings_file) as json_file:
        loaded_settings: dict = json.load(json_file)
        save_settings = False
        for setting_name, setting_value in settings.items():
            if setting_name not in loaded_settings:
                loaded_settings[setting_name] = setting_value
                save_settings = True
        for setting_name in loaded_settings:
            if setting_name not in settings: loaded_settings.pop(setting_name)
        settings = loaded_settings
    if save_settings: save_json()
else: save_json()

if settings['auto update']:
    github_url = 'https://github.com/elibroftw/music-caster/releases'
    try:
        github_url = 'https://github.com/elibroftw/music-caster/releases'
        html_doc = requests.get(github_url).text
        soup = BeautifulSoup(html_doc, features='html.parser')
        release_entry = soup.find('div', class_='release-entry')
        latest_version = release_entry.find('a', class_='muted-link css-truncate')['title'][1:]
        major, minor, patch = (int(x) for x in CURRENT_VERSION.split('.'))
        lt_major, lt_minor, lt_patch = (int(x) for x in latest_version.split('.'))
        if (lt_major > major or lt_major == major and lt_minor > minor
                or lt_major == major and lt_minor == minor and lt_patch > patch):
            details = release_entry.find('details', class_='details-reset Details-element border-top pt-3 mt-4 mb-2 mb-md-4')
            download_links = [link['href'] for link in details.find_all('a') if link.get('href')]
            bundle_download_link = f'https://github.com{download_links[1]}'
            source_download_link = f'https://github.com{download_links[-2]}'
            os.chdir(starting_dir)
            if settings.get('DEBUG'): Popen('python updater.py')
            elif os.path.exists('updater.py'):
                r = requests.get(source_download_link, stream=True)
                z = zipfile.ZipFile(io.BytesIO(r.content))
                z.extract(f'music-caster-{latest_version}/updater.py')
                z.close()
                if os.path.exists('updater.py'): os.remove('updater.py')
                os.rename(f'music-caster-{latest_version}/updater.py', 'updater.py')
                os.rmdir(f'music-caster-{latest_version}')
                Popen('pythonw updater.py')
            elif os.path.exists('Updater.exe'):
                r = requests.get(bundle_download_link, stream=True)
                z = zipfile.ZipFile(io.BytesIO(r.content))
                os.remove('Updater.exe')
                z.extract('Updater.exe')
                z.close()
                os.startfile('Updater.exe')
            elif os.path.exists('updater.pyw'):
                r = requests.get(source_download_link, stream=True)
                z = zipfile.ZipFile(io.BytesIO(r.content))
                z.extract(f'music-caster-{latest_version}/updater.py')
                z.close()
                if os.path.exists('updater.pyw'): os.remove('updater.pyw')
                os.rename(f'music-caster-{latest_version}/updater.py', 'updater.pyw')
                os.rmdir(f'music-caster-{latest_version}')
                Popen('pythonw updater.pyw')
            sys.exit()
    except requests.ConnectionError:  # Should handle more errors?
        pass
        # start a thread to check every 20 seconds

shortcut_path = f'C:/Users/{getuser()}/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/Music Caster.lnk'


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


startup_setting()

update_devices = False
chromecasts = []
device_names = ['1. Local Device']
cast = None


def chromecast_callback(chromecast):
    global update_devices, cast
    previous_device = settings['previous device']
    if str(chromecast.device.uuid) == previous_device and cast != chromecast:
        cast = chromecast
        cast.wait()
    chromecasts.append(chromecast)
    devices = len(device_names)
    device_names.append(f'{devices + 1}. {chromecast.device.friendly_name}')
    update_devices = True


local_music_player.init(44100, -16, 2, 2048)
stop_discovery = pychromecast.get_chromecasts(blocking=False, callback=chromecast_callback)
menu_def_1 = ['', ['Refresh Devices', 'Select &Device', device_names, 'Settings', 'Play &File', 'Play All', 'E&xit']]

menu_def_2 = ['', ['Refresh Devices', 'Select &Device', device_names, 'Settings', 'Play &File', 'Play All',
                   'Next Song', 'Previous Song', 'Repeat', 'Pause', 'Stop', 'E&xit']]

menu_def_3 = ['', ['Refresh Devices', 'Select &Device', device_names, 'Settings', 'Play &File', 'Play All',
                   'Next Song', 'Previous Song', 'Repeat', 'Resume', 'Stop', 'E&xit']]

UNFILLED_ICON = b'iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAQAAAD/5HvMAAAABGdBTUEAALGPC/xhBQAAACBjSFJN\nAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAAmJLR0QA/4ePzL8AAAAHdElN\nRQfjBw4ALiA+kkFLAAACWElEQVRo3u2ZsUsbURzHo2Bc0kkMDoYirRkcpEu7NtAubo7ZPXDo6qaL\nkyUIQtshkE6CkA79C4SqWIiLi5N2iBQ7WgRvUNvGj0OG/n737kLt9d476PuOvx9JPnn3e9/v3b1C\nwcvLy8srSQwR0CHEpi7pEDAUhzPBNq60zYS5Ou5w+kh6lQhwrUADHTgH6mig0DlQqIGErO7spN/1\nQB7IA3kg10DObnk8kAf6b4C44ZxTDmmzSp3JXPkQAF9o8oLh/AD1dcYalTwBAdzQ4lGegAB+sk4p\nT0AA35i3CVRkjClqLPKGI24ToN4x6sSHGGeB3Visw3875PcyRqb5EAN1xoxDp+Ypnwyk7zxzGh3M\n0TWQZhwCFQqMsWtcuEq2uyzkhB22WGE29oMjNI3xHrXlQ1024rB4xS9tAjaNsccmD2OQtObtOvU1\nDYqRL2hG3LtkEwjgM+XILOnxXrefZV95EtlxXRW7j7MBKlGlxhL79Mx3WxGkOdV9n7EPUabBlbFK\n+sJJ9/6RxpH+NFwrfDRmqagCRWbcaytOzXIkWBuq21auPWwlOqgrpGvpS0yr3ktLWcayWqNN1ZPb\nv5lFlh3TMv+pmqWeDBQW5ENTdj60RzUy3nLHbai7SnnRJrMzxgueq05Dxq7qHIlOPUunvpCrRFlZ\npbxob0V99Z7PMDEnZ4OiY0/19kVnRdQXRb2dGqgzOMvEeLMk6luiXpO3a6mBgsFArYQf3hH1KVE/\nTQlkHOBFdSx6VVE/Ubn/W+epgGKOOAecXvEgoV6UryT+EihMPAT28vLy8urrDgm99Mb0O5qlAAAA\nJXRFWHRkYXRlOmNyZWF0ZQAyMDE5LTA3LTE0VDAwOjQ2OjMyKzAwOjAwaWwEjwAAACV0RVh0ZGF0\nZTptb2RpZnkAMjAxOS0wNy0xNFQwMDo0NjozMiswMDowMBgxvDMAAAAASUVORK5CYII=\n'
FILLED_ICON = b'iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAQAAAD/5HvMAAAABGdBTUEAALGPC/xhBQAAACBjSFJN\nAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAAmJLR0QA/4ePzL8AAAAHdElN\nRQfjBw4ALiA+kkFLAAACxUlEQVRo3u2ZT0hUURSHn0bjxtpIYqCElLNwEW1yWYO1yF3L2fvARVs3\nqRtX2SAIJTFgK0HQRdJeaBSDaePGlYaoYUtD8C3ScvpaKHTOfe8NOu/fQPe3PGec+bz3nN+57z7H\nsbKysrIKEy24VPFIU8dUcWkJwulihay0Qpd/dbLDOUfSq4RL1nI10JfMgaoayMscyNNAQql2dtjv\nWiAL9N8AJdHfFigWoMvscXMAnTUb0G3G2GkioIuz0iDLTQR08acDVJoKyHEch2dsptX2pxyyxwaL\nTFKkOxQpx2tqKfsQAF8p84TWQKhH7KcPdK4DXtETgHSTj9kAAZwyx10fUivvsgIC+M007T6oseyA\nAL7z3IfkJgeUo4NeCozwhk3+hHzXLG3RV6kBH+IWw6wGYm2YRX71WmrYGOljKQDqgH71qWtX7bho\nw/Uhn3zf+IMBwwT2Ux0dDLHrQ+o3rLKW6iyjg1XfxqlaYiruLvPYpsICE9wPRLpO2VfebapLN5Pz\noV1mgrB4YZwfZ42TQKLGWGOeOwFIWsoqL3teatypTyiRM5DKhnu3qyNcCqPjM51GLenynlbZ5TRm\n2TceGB23q8buPZEbjA+onTwFRlkPcBTPQBpS2ffqcWAndh+ikxI/faukN0669y/pSLxMZrj28MFX\nSzk1UOSMm1LPcWcJOTXjxmAtqeyicu3W2K9jAj9cVEgn0pfoU7mnqQA5DuNqjeZVTrZ/Of4LK48t\n5vz/qaqlmhwoDMuHpuRu0NbIG+UtO25GnSrlpnUnd6V3xGOVKcmxqzJyvhcTvGPkSK4Sncoq5aa9\nFfHJyNdcx/VGx5rKrYvMhIiPiPhiZKBq/VkmyptREV8Q8YI8rkUGcusDzYX8cEXEe0V8LyKQ7wWe\nqS2Ry4v4tpr7/3QYCSjgFWedt1fcCInn5JVEg0Be6EtgKysrK6tz/QVPmZ3Bw5RmTgAAACV0RVh0\nZGF0ZTpjcmVhdGUAMjAxOS0wNy0xNFQwMDo0NjozMiswMDowMGlsBI8AAAAldEVYdGRhdGU6bW9k\naWZ5ADIwMTktMDctMTRUMDA6NDY6MzIrMDA6MDAYMbwzAAAAAElFTkSuQmCC\n'
WINDOW_ICON = b'iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAYAAABV7bNHAAAAAXNSR0IArs4c6QAABV9JREFUeAHt\nWUtsVUUYvhQsG0qMDaQQTUPwEVkQN7gsTXGhG+JO9zRhwZaN1o1xISEkJmIISWVDQoILG1iXtNfY\nUBe6MRrAR1OjK+MjqSaK2ML3lU47d/J/M+fce8+B9s6ffDlzvvlf83fOPG4bjSy5ArkCuQK5ArkC\nuQK5ArkCuQIlKrANuuPAPPAXcH+LYmltjBwrx1xIhqA1DWzVoqhxccwce1RYxV4sjisaxx6dSZxq\nTrlXn6yBlC/Q06uFcePmursu4XTigrxrvbc3G39j2ANu6GGBWEVLQj1LZzNyyfH2bcZR1ZlzLlCi\n2rlAuUCJCiS68wxKFGhHoj/VrXaBlF3d/W3vwnkGJf5UuUCJAoWfWNtTMRFn03Z3OoOWN+3ICybe\naYGeQZwJ4MeC8XpWjZ/mGDAFuFvx4/RUfxiVo9LvCv8yvMwCKvij4NXAVC5Kv6v8q/D2NaCSqJNX\nA1M5rOuHu9Zd9PA3IeIP4HvgDnALmAN+AcpIP5TfA04Dna53ZeKGuuE4XT8LZInST/61v4O3i8Ax\noMyAR6C/CKi/WNU8Qpui4prKJJWBxf8M/fcB7mRFZDeUrgGWr6o5lZ+Kq/TbSp6f5SRwUHrd6OCs\nuwCoxKriNzJobal4rVremzIowt+Dn3NAkd+034ZeEZ/d0vGG2NJU/luU/BdlUIbnQv6671S0x8GX\n8duJrkhBxlf6De46g8ABYBQ4CXwIcLteAcok+RH0dwIxqWsmqRzUeJR+lN+D3hNAEyharK+gm1rE\n61iTkIYpXS2QH+E5vHwCFCkUd7tDvnHQ3o73qne3IOT6a2UFchGOoDEDqECO/x06vIIo4RFgEXD6\n3X6quCqO0m+bfw2WC4AKSJ5Fis2kEfQvJ3zE/Mf64NYUZWMqd0pycW8CKih5fm6xNelMwj7mO9YH\nt6YoG1OZJO9gvHvNAleAd4DDQFF5Aoq8iqjA5Llwq92Nu2gVF1y4NUXlaSqTVAb8fD4AihbrFHT/\nj/jjEUAJfwVQebTLq1jKn9JPJsY14jIwLD1sdLBIKgHyscPkbMI25tfq28iqtWXpkpOiDEL+X3g4\nC/CTiEnsc+OJW11LuOOFMTt5Vzkqn0q/dFJz8LRXems0uCY1AZUI725KptCh7MryKobyo/TbSugn\neHtJenx4dVFHAF5wnxW2Y+DVAMryIoT0r/RXp/zz6B0F+Cvg50CRswl3v1iReE5Sg/oYfZbwV70f\nAGVXhrf8k1M+lL7J8xPievMPoByS50yKfW4zwv4/8Ops9JawieVh9cGNKZYuubaEg/gUUE7Jc01S\nCzevJSvCngdES/aBjB0XYrn4fZZvcr6O31b6hfgJaKmBMghnm5Kr6PATcW2esPuUUYW8ix8+Ow75\nJjyoIvEIMCwi8FcAZfeKsKmSDgvj3rsSkzPJOQyfPEwqaaIj1Oc7z0x1i5UHOSncjW4Dk0CRv6ha\nk7jzqWvJCfRZifFfSnWLlUe0QKHBZ8iY274SLtxqd+PdzRL+Mqk+s6ctgwq5cLzuXYZ0Cv7zT2gf\nlRYPF2Vf37UXIjbqxs61rU5xuYZPmUOo6N5ZJDWTePbhJ+V0/af6zM4L/XfBK/H9Vtle8hMourU+\nCSOuS5b8CvKm1QHuuOC/EfwLgq+T/tYPVrRAtBkB1MJ93XfqtV/02n6TP8pZwmPAo5ZLfgJlCkS7\nN3xjr/2l1/ab+/0Xr81riSVPWWSN3A3EailQGDv1bfMIYAnXJ8tWzZRBof+b5XyNs/x3k5tGnKFI\n/NWuVECekywZAGnZKv1+oX/Xcr7GWf475ZjfPDAObFuLkx+5ArkCuQK5ArkCuQK5ArkCuQLpCjwA\nMCQ8Gt1a8k0AAAAASUVORK5CYII=\n'

tray = sg.SystemTray(menu=menu_def_1, data_base64=UNFILLED_ICON, tooltip='Music Caster')
notifications_enabled = settings['notifications']
if notifications_enabled: tray.ShowMessage('Music Caster', 'Music Caster is running in the tray', time=500)
music_directories = settings['music directories']
if not music_directories: music_directories = change_settings('music directories', [home_music_dir])
DEFAULT_DIR = music_directories[0]

music_queue = []
done_queue = []
mc = None
song_end = song_length = song_position = song_start = 0
playing_status = 'NOT PLAYING'
cast_last_checked = time()
# Styling
fg = '#aaaaaa'
bg = '#121212'
font_family = 'SourceSans', 11
button_color = ('black', '#4285f4')


def play_file(file_path, position=0, autoplay=True):
    global mc, song_start, song_end, playing_status, song_length, song_position, volume, images_dir
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
        print(e)
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
        cast.wait()
        cast.set_volume(volume)
        mc = cast.media_controller
        if mc.is_playing or mc.is_paused:
            mc.stop()
            mc.block_until_active(5)
        music_metadata = {'metadataType': 3, 'albumName': album, 'title': title, 'artist': artist}
        mc.play_media(url, 'audio/mp3', current_time=position, metadata=music_metadata, thumb=thumb, autoplay=autoplay)
        mc.block_until_active()
        song_start = time()
        song_end = song_start + song_length - position
    if notifications_enabled: tray.ShowMessage('Music Caster', f"Playing: {artist.split(', ')[0]} - {title}", time=500)
    if autoplay: playing_status = 'PLAYING'


def pause():
    global tray, playing_status, song_position
    tray.Update(menu=menu_def_3, data_base64=UNFILLED_ICON)
    try:
        if mc is not None:
            mc.update_status()
            mc.pause()
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
    elif local_music_player.music.get_busy():
        local_music_player.music.stop()
    playing_status = 'NOT PLAYING'


def next_song(from_timeout=False):
    global playing_status
    if cast is not None and cast.app_id != 'CC1AD845':
        playing_status = 'NOT PLAYING'
    elif music_queue:
        if not settings['repeat'] or not from_timeout:
            settings['repeat'] = False
            save_json()
            done_queue.append(music_queue.pop(0))
        with suppress(IndexError):
            play_file(music_queue[0])


def previous():
    global playing_status
    if cast is not None and cast.app_id != 'CC1AD845':
        playing_status = 'NOT PLAYING'
    elif done_queue:
        song = done_queue.pop()
        music_queue.insert(0, song)
        play_file(song)
    elif music_queue:
        play_file(music_queue[0])


def on_press(key):
    global keyboard_command
    if str(key) == '<179>':
        if playing_status == 'PLAYING':
            keyboard_command = 'Pause'
        elif playing_status == 'PAUSED':
            keyboard_command = 'Resume'
    elif str(key) == '<176>':
        keyboard_command = 'Next Song'
    elif str(key) == '<177>':
        keyboard_command = 'Previous Song'
    elif str(key) == '<178>':
        keyboard_command = 'Stop'


keyboard_command = None
settings_window = None
settings_active = False
listener_thread = Listener(on_press=on_press)
listener_thread.start()

while True:
    menu_item = tray.Read(timeout=30)
    # if menu_item != '__TIMEOUT__':
    #     print(menu_item)
    if menu_item == 'Refresh Devices':
        update_devices = True
        stop_discovery()
        chromecasts.clear()
        device_names.clear()
        device_names.append('1. Local Device')
        stop_discovery = pychromecast.get_chromecasts(blocking=False, callback=chromecast_callback)
    if update_devices:
        update_devices = False
        if playing_status == 'PLAYING':
            tray.Update(menu=menu_def_2)
        elif playing_status == 'PAUSED':
            tray.Update(menu=menu_def_3)
        else:
            tray.Update(menu=menu_def_1)
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
            if playing_status in ('PAUSED', 'PLAYING'):
                play_file(music_queue[0], position=current_pos, autoplay=False if playing_status == 'PAUSED' else True)

    elif menu_item == 'Settings' and not settings_active:
        settings_active = True
        # RELIEFS: RELIEF_RAISED RELIEF_SUNKEN RELIEF_FLAT RELIEF_RIDGE RELIEF_GROOVE RELIEF_SOLID
        settings_layout = [
            [Sg.Text(f'Music Caster Version {CURRENT_VERSION} by Elijah Lopez', text_color=fg, background_color=bg,
                     font=font_family)],
            [Sg.Checkbox('Auto Update', default=settings['auto update'], key='auto update', text_color=fg,
                         background_color=bg, font=font_family, enable_events=True)],
            [Sg.Checkbox('Run on Startup', default=settings['run on startup'], key='run on startup', text_color=fg,
                         background_color=bg, font=font_family, enable_events=True)],
            [Sg.Checkbox('Enable Notifications', default=settings['notifications'], key='notifications', text_color=fg,
                         background_color=bg, font=font_family, enable_events=True)],
            [Sg.Slider((0, 100), default_value=settings['volume'], orientation='horizontal', key='volume',
                       tick_interval=5, enable_events=True, background_color='#4285f4', text_color='black',
                       size=(50, 15))],
            [Sg.Listbox(music_directories, size=(41, 5), select_mode=Sg.SELECT_MODE_SINGLE, text_color=fg,
                        key='music_dirs', background_color=bg, font=font_family, enable_events=True),
             Sg.Frame('', [
                 [Sg.Button(button_text='Remove Selected Folder', button_color=button_color, key='Remove Folder',
                            enable_events=True, font=font_family)],
                 [Sg.FolderBrowse('Add Folder', button_color=button_color, font=font_family, enable_events=True)],
                 [Sg.Button('Open Settings File', key='Open Settings', button_color=button_color, font=font_family,
                            enable_events=True)]], background_color=bg, border_width=0)]
        ]
        settings_window = Sg.Window('Music Caster Settings', settings_layout, background_color=bg, icon=WINDOW_ICON,
                                    return_keyboard_events=True, use_default_focus=False)
        settings_window.Finalize()
        settings_window.TKroot.focus_force()
        # settings_window.GrabAnyWhereOn()
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
    elif 'Stop' in (menu_item, keyboard_command): stop()
    elif 'Next Song' in (menu_item, keyboard_command) or playing_status == 'PLAYING' and time() > song_end:
        next_song(from_timeout=time() > song_end)
    elif 'Previous Song' in (menu_item, keyboard_command): previous()
    elif menu_item == 'Repeat':
        repeat_setting = change_settings('repeat', not settings['repeat'])
        if notifications_enabled:
            if repeat_setting: tray.ShowMessage('Music Caster', 'Repeating current song')
            else: tray.ShowMessage('Music Caster', 'Not repeating current song')
    elif 'Resume' in (menu_item, keyboard_command): resume()
    elif 'Pause' in (menu_item, keyboard_command): pause()
    elif menu_item == 'Exit':
        tray.Hide()
        with suppress(UnsupportedNamespace):
            if cast is not None and cast.app_id == 'CC1AD845': cast.quit_app()
            elif local_music_player.music.get_busy(): local_music_player.music.stop()
        break
    # SETTINGS WINDOW
    if settings_active:
        settings_event, settings_values = settings_window.Read(timeout=10)
        if settings_event is None:
            settings_active = False
            continue
        settings_value = settings_values.get(settings_event)
        # if settings_event != '__TIMEOUT__':
        #     print(settings_event)
        if settings_event in ('Esc', 'q'):
            settings_active = False
            settings_window.CloseNonBlocking()
        elif settings_event in ('auto update', 'run on startup', 'notifications'):
            change_settings(settings_event, settings_value)
            if settings_event == 'run on startup':
                startup_setting()
            elif settings_event == 'notifications':
                notifications_enabled = settings_value
                if settings_value: tray.ShowMessage('Music Caster', 'Notifications have been enabled', time=500)
        elif settings_event in ('volume', 'a', 'd') or settings_event.isdigit():
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
                music_directories.append(settings_value)
                save_json()
                settings_window.Element('music_dirs').Update(music_directories)
        elif settings_event == 'Open Settings':
            os.startfile(settings_file)

    if keyboard_command is not None: keyboard_command = None
    if mc is not None and time() - cast_last_checked > 5:
        with suppress(UnsupportedNamespace):
            if cast is not None and cast.app_id == 'CC1AD845':
                mc.update_status()
                # if mc.is_paused and playing_status != 'PAUSED': playing_status = 'PAUSED'
                # elif mc.is_playing and playing_status != 'PLAYING': playing_status = 'PLAYING'
                # elif not mc.is_paused and not mc.is_playing: playing_status = 'NOT PLAYING'
                volume = settings['volume']
                cast_volume = int(cast.status.volume_level * 100)
                if volume != cast_volume:
                    volume = change_settings('volume', cast_volume)
        cast_last_checked = time()
