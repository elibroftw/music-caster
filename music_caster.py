from bs4 import BeautifulSoup
from contextlib import suppress
import ctypes
import getpass
from glob import glob
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
import os
from pathlib import Path
import pychromecast.controllers.media
from pychromecast.error import *
import pychromecast
from pygame import mixer as local_music_player  # https://www.pygame.org/docs/ref/music.html
from pynput.keyboard import Listener
import PySimpleGUIQt as sg
# import PySide2
from random import shuffle
import requests
from subprocess import Popen
import threading
from time import time
import win32api
import win32com.client
import win32event
from winerror import ERROR_ALREADY_EXISTS
import sys

# TODO: repeat and repeat all
# TODO: set volume
# TODO: test auto update. Need to create github repo
# TODO: refresh list menu option
# TODO: toast notifications
# TODO: seeking
# TODO: make a list view of all music files when play file is selected
# TODO: playlist support
# TODO: Add gui for settings
# TODO: virtual env

mutex = win32event.CreateMutex(None, False, 'name')
last_error = win32api.GetLastError()

if last_error == ERROR_ALREADY_EXISTS:
    sys.exit()

starting_dir = os.path.dirname(os.path.realpath(__file__))
os.chdir('C:/')
PORT = 2001
while True:
    try:
        httpd = HTTPServer(('0.0.0.0', PORT), SimpleHTTPRequestHandler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        print('Running server')
        break
    except OSError:
        PORT += 1

user32 = ctypes.windll.user32
SCREEN_WIDTH, SCREEN_HEIGHT = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
sg.ChangeLookAndFeel('Black')
home_music_dir = str(Path.home()).replace('\\', '/') + '/Music'
settings = {  # default settings
    'version': '0.0.0',
    'previous device': None,
    'comments': ['Edit only the variables below', 'Restart the program after editing this file!'],
    'auto update': True,
    'run on startup': True,
    'music directories': [home_music_dir],
    'sample music directories': [
        'C:/Users/maste/Documents/MEGAsync/Music',
        'Put in a valid path',
        'First path is the default directory when selecting a file to play. FOR NOW'
    ],
    'playlists': {},
    'playlists_example': {'NAME': ['PATHS']}
}
settings_file = f'{starting_dir}/settings.json'


def save_json():
    with open(settings_file, 'w') as outfile:
        json.dump(settings, outfile, indent=4)


# check if settings file is valid
try:
    with open(settings_file) as json_file:
        loaded_settings = json.load(json_file)
        for k in settings.keys():
            if k not in loaded_settings:
                raise KeyError
        settings = loaded_settings
except (FileNotFoundError, KeyError):
    save_json()


if settings['auto update']:
    github_url = 'https://github.com/elibroftw/music-caster/releases'
    html_doc = requests.get(github_url).text
    soup = BeautifulSoup(html_doc, features='html.parser')
    release_entry = soup.find('div', class_='release-entry')
    current_version = settings['version']
    latest_version = release_entry.find('a', class_='muted-link css-truncate')['title'][1:]
    major, minor, patch = (int(x) for x in current_version.split('.'))
    lt_major, lt_minor, lt_patch = (int(x) for x in latest_version.split('.'))
    if (lt_major > major or lt_major == major and lt_minor > minor
            or lt_major == major and lt_minor == minor and lt_patch > patch):
        os.chdir(starting_dir)
        if settings.get('DEBUG'):
            Popen('python updater.py')
        else:
            os.startfile('Updater.exe')
        sys.exit()

USER_NAME = getpass.getuser()
shortcut_path = f'C:/Users/{USER_NAME}/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/Music Caster.lnk'
shortcut_exists = os.path.exists(shortcut_path)
if settings['run on startup'] and not shortcut_exists and not settings.get('DEBUG'):
    # C:\Users\maste\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup
    target = f'{starting_dir}\\Music Caster.exe'
    shell = win32com.client.Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.Targetpath = target
    shortcut.WorkingDirectory = starting_dir
    shortcut.WindowStyle = 1  # 7 - Minimized, 3 - Maximized, 1 - Normal
    shortcut.save()
elif not settings['run on startup'] and shortcut_exists:
    os.remove(shortcut_path)

previous_device = settings['previous device']
local_music_player.init()
print('Retrieving chromecasts...')
chromecasts = pychromecast.get_chromecasts()
print('Retrieved chromecasts')

# device_names = [f'{i + 1}. {cc.device.friendly_name}' for i, cc in enumerate(chromecasts)]
device_names = ['1. Local Device'] + [f'{i + 2}. {cc.device.friendly_name}' for i, cc in enumerate(chromecasts)]
menu_def_1 = ['File', ['Select &Device', device_names, 'Settings', 'Play &File', 'Play All', 'E&xit']]

menu_def_2 = ['File', ['Select &Device', device_names, 'Settings', 'Play &File', 'Play All',
                       'Next Song', 'Previous Song', 'Pause', 'E&xit']]

menu_def_3 = ['File', ['Select &Device', device_names, 'Settings', 'Play &File', 'Play All',
                       'Next Song', 'Previous Song', 'Resume', 'E&xit']]


unfilled_logo_path = f'{starting_dir}/Icons/White Cast Icon.png'
filled_logo_path = f'{starting_dir}/Icons/White Cast Icon Filled.png'

try: cast = next(cc for cc in chromecasts if str(cc.device.uuid) == previous_device)
except StopIteration: cast = None

unfilled_logo_data = b'iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAYAAABV7bNHAAAAAXNSR0IArs4c6QAABMpJREFUeAHt\nWztrFFEY3ZXEKoooBvGBiC98IDZaCGqKINiInTZWESwstfMHKCKkUCEQbbRRRFBLkWgwWKmFKL4g\nIIqKoIIKvrOeIzu7d8bvzJ01O/u8Hxzmzve49/tOZu69M5spFIIEBgIDgYHAQGAgMBAYCAwEBgwG\nioauUCqVqB8qYz2OfZZfB+g+o4ZHwFmiWCyWkjX9QxDIWQCn88Bg0rnDz2+gvn0g6a1bZ4yg8pVz\nHQ7dRk7ECUna4V5JMyJL+cjbqlvJIQWsnRxUJEnQ/oqlexsxgpK3GCetTp2Qs/7Jv+AWmxU5Jwn6\nZxanIwJiflFwux8x53rrTd5i7V5z3fMPBHkoDQQFgjwMeMzhCgoEeRjwmMMVFAjyMOAx97j2Tt0Q\nujXW2g63mIexQFAgyMOAxxyuoECQhwGPObaK4en/O/z5Toj4ADwHngKPgQmscq9w7CqJvedR70cc\nRkjYGHAJuAnCphxb2zVVvXK7w4Aa5CV8jwJL2o6ZcsKqVlmPCvDov8M+CiyXHbeoQdUl01UBGfU/\n4XcCaJt32qquvAiKxnuFxm45SAsZooSTRzfF5CQ9E0a+0Z8NLAVWA+uAAYA/Qcf8cZ4mp2E8hAmP\nK2NLComxEpOTtOUc6dDXfGAIuAVMAVnkHpxadhJXBUQ1//cRHa8ELgJZiOJqt/a/B8sxEHmZUrch\n0fsmYMwcJa58j9PNdRu4Th3FU6ye1an7ajfoeicwWR3CbJGklrqSzCyhrFZWxxb6nQdwfkoT3m4t\nMyepRF1aYqsSAvgM9toBn8GuYVZ/4AapNuJ7YTsJHFA+0N8HtrTC6kaCrDzlKsYAIbx9hoENVodJ\nHfwOAr8AJaeSMc04V8nJXFSAo/+N9jmAe6RUgQ9JSpOmbyZVcrIwFWDov0F3HODGUgrsI0ZspOKO\nu6mPJVEiyWNaQUlf3/kEHPpVh7D1AmkT9wkV2wi9Kk6OrQI8+hewb1SdwsbVTW0B+IC7QsXmrcfY\npshx4d0HrAIGgMPAbYDzjk8+wyGNJO6TlJyRCeVsUAnVNCw66Qc433xVHZb1vJLSbje14/6BuKbs\njVQ9NREUObMI4LLqtKznnGRO3NDzsWSq7Jc8HIvGaeQxmUR0Pq0c0MkRQBXKMY6rAWC7QAdDuMNu\n+E9QRh5/VSr/zHr0shdQJHELYO6ToOdbABU3mDmBOjkiF1Pq0j165pWk5JwaBAFq2R9RMXnpVfJy\nPARwNXoCjALevyh81JzElc98LIF+CLDkmUwsJ4OVBHVyOCNgHLpVKgA2TtxqdRu24uDPN5PqNlts\nxeSlQx6myPFM71LpI/TbVRBs3AJYMpkS88AKgG6vislDL3KIXUFZVo45SO4KOlNXEh8XrF9YlyHG\nvM3gPy4KXiP0BVXMdPRiLL7yqUgWguhMkkYrUU4D707e4fSOo3Kbu9wTp/3QabtN/orSbOEHdhXJ\nShADtuGvpSbuq5Ue4w11RfAfIixZaSkbrDvrjlcLQYzb4wY77btO220udE+c9gun7TbnuidNaPOD\numkRtFUk/VroFUGfhH/lMyRhz1NNcvhJZmyS7qlxxEXC/43QK4JiE6ET22iCvmBszoe8asyPep3c\nQjMwEBgIDAQGAgOBgcBAYCAwUGXgD8G4G3+pxN+sAAAAAElFTkSuQmCC\n'
filled_logo_data = b'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\n'

tray_1 = sg.SystemTray(menu=menu_def_1, data_base64=unfilled_logo_data, tooltip='Music Caster')
tray_2 = sg.SystemTray(menu=menu_def_2, data_base64=filled_logo_data, tooltip='Music Caster')
tray_3 = sg.SystemTray(menu=menu_def_3, data_base64=filled_logo_data, tooltip='Music Caster')
# TODO: tray.Update()
tray_2.Hide()
tray_3.Hide()
tray = tray_1

music_directories = settings['music directories']
if not music_directories:
    music_directories = settings['music directories'] = [home_music_dir]
    save_json()
DEFAULT_DIR = music_directories[0]

music_queue = []
done_queue = []
# noinspection PyTypeChecker
mc: pychromecast.controllers.media.MediaController = None
song_end = song_length = song_position = song_start = 0
playing_status = 'NOT PLAYING'

# select_file_layout = [[sg.InputText(default_text='Audio File', disabled=True),
#                        sg.FileBrowse(button_text='Select File', initial_folder=MUSIC_DIR, size=(10, 1),
#                                      file_types=(('Audio', '*mp3'),), button_color=('black', 'cyan'))],
#                       [sg.Button('Play!', button_color=('black', 'cyan'), size=(10, 1)),
#                       sg.Cancel(button_color=('black', 'cyan'), size=(10, 1))]]


def play_file(filename, position=0):
    global mc, song_start, song_end, playing_status, song_length, song_position
    song_position = position
    if cast is None:
        mc = None
        song_length = MP3(filename).info.length
        if local_music_player.music.get_busy():
            local_music_player.music.stop()
        local_music_player.music.load(filename)
        local_music_player.music.play(start=position)
        song_start = time()
        song_end = song_start + song_length - position
        playing_status = 'PLAYING'
    else:
        title = artist = 'Unknown'
        song_length = MP3(filename).info.length
        with suppress(Exception):
            title = EasyID3(filename)['title'][0]
            artist = EasyID3(filename)['artist']
            artist = ', '.join(artist)
            # album = EasyID3(filename)['album']

        uri_safe = Path(filename).as_uri()[11:]
        url = f'http://192.168.2.17:{PORT}/{uri_safe}'
        cast.wait()
        mc = cast.media_controller
        if mc.is_playing or mc.is_paused: mc.stop()
        mc.play_media(url, 'audio/mp3', title=f'{artist} - {title}', current_time=position)
        # NOTE: tested on Google Home Mini. # TODO: test on chromecast
        mc.block_until_active()
        if position > 0:
            mc.seek(position)
        song_start = time()
        song_end = song_start + song_length - position
        playing_status = 'PLAYING'


# NOTE: there might be a bug if the media has been paused for a while
def pause():
    global tray, playing_status, song_position
    if playing_status == 'PLAYING':
        tray.Hide()
        tray = tray_3
        tray.UnHide()
        try:
            if mc is not None:
                mc.update_status()
                mc.pause()
                song_position = mc.status.adjusted_current_time
            else:
                song_position += local_music_player.music.get_pos()/1000
                local_music_player.music.pause()
            playing_status = 'PAUSED'
        except UnsupportedNamespace:
            song_position = 0
            playing_status = 'NOT PLAYING'


def resume():
    global tray, playing_status, song_end, song_position
    if playing_status == 'PAUSED':
        tray.Hide()
        tray = tray_2
        tray.UnHide()
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


def play_pause_media_key():
    global playing_status
    if playing_status == 'PLAYING': pause()
    elif playing_status == 'PAUSED': resume()


def next_song():
    global playing_status
    if music_queue:
        playing_status = 'NOT PLAYING'
        song = music_queue.pop(0)
        done_queue.append(song)
        if music_queue:
            play_file(music_queue[0])


def previous():
    global playing_status
    # NOTE: restart song if current_time > 5?
    if done_queue:
        playing_status = 'NOT PLAYING'
        song = done_queue.pop()
        music_queue.insert(0, song)
        play_file(song)


def switch_tray(hide_tray, show_tray):
    if hide_tray != show_tray:
        hide_tray.Hide()
        show_tray.UnHide()
    return show_tray


def on_press(key):
    if str(key) == '<179>':
        play_pause_media_key()
    if str(key) == '<176>':
        next_song()
    if str(key) == '<177>':
        previous()


listener_thread = Listener(on_press=on_press)
listener_thread.start()


while True:
    menu_item = tray.Read(timeout=100)
    # if menu_item != '__TIMEOUT__':
    #     print(menu_item)
    if menu_item == 'Exit':
        if cast is not None and cast.app_id == 'CC1AD845':
            cast.media_controller.stop()
            # TODO: implement fadeout?
        elif local_music_player.music.get_busy():
            # local_music_player.music.fadeout(3)  # needs to be threaded
            local_music_player.music.stop()
        break
    elif menu_item == 'Play File':
        tray.Hide()
        tray = tray_2
        tray_2.UnHide()
        # maybe add *flac compatibility https://mutagen.readthedocs.io/en/latest/api/flac.html
        path_to_file = sg.PopupGetFile('Select Music file', file_types=(('Audio', '*mp3'),), initial_folder=DEFAULT_DIR,
                                       no_window=True)
        if os.path.exists(path_to_file):
            play_file(path_to_file)
            for directory in music_directories:
                music_queue.extend([file for file in glob(f'{directory}/*.mp3')])
            if path_to_file in music_queue: music_queue.remove(path_to_file)
            shuffle(music_queue)
            music_queue.insert(0, path_to_file)
    elif menu_item.split('.')[0].isdigit():  # if user selected a device
        device = ' '.join(menu_item.split('.')[1:])[1:]
        try:
            new_cast = next(cc for cc in chromecasts if cc.device.friendly_name == device)
        except StopIteration:
            new_cast = None
        if cast != new_cast:
            cast = new_cast
            if cast is None:
                settings['previous device'] = None
            else:
                settings['previous device'] = str(cast.uuid)
            save_json()
            current_pos = 0
            if playing_status in ('PLAYING', 'PAUSED'):
                if local_music_player.music.get_busy():
                    current_pos = song_position + local_music_player.music.get_pos()/1000
                    local_music_player.music.stop()
                    play_file(music_queue[0], position=current_pos)
                elif mc is not None:
                    mc.update_status()  # Switch device without playback loss
                    current_pos = mc.status.adjusted_current_time
                    mc.stop()
                    play_file(music_queue[0], position=current_pos)
    elif menu_item == 'Settings':
        os.startfile(settings_file)
    elif menu_item == 'Next Song':
        next_song()
    elif menu_item == 'Previous Song':
        previous()
    elif menu_item == 'Resume':
        resume()
    elif menu_item == 'Pause':
        pause()
    elif menu_item == 'Play All':
        music_queue.clear()
        for directory in music_directories:
            music_queue.extend(file for file in glob(f'{directory}/*.mp3'))
        if music_queue:
            shuffle(music_queue)
            done_queue.clear()
            play_file(music_queue[0])
            if tray != tray_2:
                tray.Hide()
                tray = tray_2
                tray.UnHide()
    elif playing_status == 'PLAYING' and time() > song_end:
        next_song()
    elif menu_item == 'Stop':
        if playing_status in ('PLAYING', 'PAUSED'):
            if mc is not None:
                mc.stop()
            elif local_music_player.music.get_busy():
                local_music_player.music.stop()
            playing_status = 'STOPPED'
