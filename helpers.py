import time
from contextlib import suppress
import datetime
from functools import wraps
import os
import platform
from math import floor
import winreg as wr

import pyqrcode
import PySimpleGUI as Sg
import socket
from urllib.parse import urlparse, parse_qs
from uuid import getnode
from b64_images import *
from subprocess import PIPE, DEVNULL, Popen
from threading import Thread
import re
import pychromecast
import mutagen
# noinspection PyProtectedMember
from mutagen.id3 import ID3NoHeaderError
# noinspection PyProtectedMember
from mutagen.mp3 import HeaderNotFoundError
from mutagen.easyid3 import EasyID3
from mutagen.easymp4 import EasyMP4
from wavinfo import WavInfoReader, WavInfoEOFError  # until mutagen supports .wav
# FUTURE: C++ JPG TO PNG
# https://stackoverflow.com/questions/13739463/how-do-you-convert-a-jpg-to-png-in-c-on-windows-8
# Styling
FONT_NORMAL = 'SourceSans', 11
FONT_TITLE = 'Helvetica', 14
FONT_ARTIST = 'Helvetica', 12
FONT_LINK = 'SourceSans', 11, 'underline'
LINK_COLOR = '#3ea6ff'
MUSIC_FILE_TYPES = 'Audio File (.mp3, .flac, .m4a, .mp4, .aac, .ogg, .opus, .wma, .wav)|' \
                   '*.mp3;*.flac;*.m4a;*.mp4;*.aac;*.ogg;*.opus;*.wma;*.wav'
Sg.change_look_and_feel('SystemDefault')
# TODO: add right click menus for list boxes


def timing(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        _start = time.time()
        result = f(*args, **kwargs)
        print(f'@timing {f.__name__} ELAPSED TIME:', time.time() - _start)
        return result
    return wrapper


def get_metadata(file_path: str) -> tuple:  # title, artist, album
    file_path = file_path.lower()
    _title, _artist, _album = 'Unknown Title', 'Unknown Artist', 'Unknown Album'
    with suppress(ID3NoHeaderError, HeaderNotFoundError, AttributeError, WavInfoEOFError):
        if file_path.endswith('.mp3'):
            audio = EasyID3(file_path)
        elif file_path.endswith('.m4a') or file_path.endswith('.mp4'):
            audio = EasyMP4(file_path)
        elif file_path.endswith('.wav'):
            a = WavInfoReader(file_path).info.to_dict()
            audio = {'title': [a['title']], 'artist': [a['artist']], 'album': [a['product']]}
        elif file_path.endswith('.wma'):
            audio = {'title': [_title], 'artist': [_artist], 'album': [_album]}
        else:
            audio = mutagen.File(file_path)
        _title = audio.get('title', ['Unknown Title'])[0]
        with suppress(KeyError, TypeError): _artist = ', '.join(audio['artist'])
        _album = audio.get('album', ['Unknown Album'])[0]
    return _title, _artist, _album


def fix_path(path, by_os=True):
    if by_os and platform.system() == 'Windows':
        return path.replace('/', '\\')
    else:
        return path.replace('\\', '/')


def get_ipv4() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 80))
    ipv4_address = s.getsockname()[0]
    s.close()
    return ipv4_address


def get_mac(): return ':'.join(['{:02x}'.format((getnode() >> ele) & 0xff) for ele in range(0, 8 * 6, 8)][::-1])


def create_qr_code(port):
    qr_code = pyqrcode.create(f'http://{get_ipv4()}:{port}')
    return qr_code.png_as_base64_str(scale=3, module_color=(255, 255, 255, 255), background=(18, 18, 18, 255))


def get_running_processes():
    # edited from https://stackoverflow.com/a/22914414/7732434
    cmd = 'tasklist /NH /FI "IMAGENAME eq Music Caster.exe"'
    p = Popen(cmd, shell=True, stdout=PIPE, stdin=DEVNULL, stderr=DEVNULL)
    task = p.stdout.readline()
    while task != '':
        task = p.stdout.readline().decode().strip()
        m = re.match(r'(.+?) +(\d+) (.+?) +(\d+) +(\d+.* K).*', task)
        if m is not None:
            process = {'name': m.group(1),  # Image name
                       'pid': m.group(2),
                       'session_name': m.group(3),
                       'session_num': m.group(4),
                       'mem_usage': m.group(5)}
            yield process


def is_already_running(threshold=1):
    for process in get_running_processes():
        process_name = process['name']
        if process_name == 'Music Caster.exe':
            threshold -= 1
            if threshold < 0: return True
    return False


def valid_music_file(file_path):
    file_path = file_path.lower()
    # NOTE: pygame only supports (mp3, oog, and wav)
    return (file_path.endswith('.mp3') or file_path.endswith('.flac') or file_path.endswith('.m4a')
            or file_path.endswith('.mp4') or file_path.endswith('.aac')
            or file_path.endswith('.ogg') or file_path.endswith('.opus')
            or file_path.endswith('.wma') or file_path.endswith('.wav'))


def find_chromecasts(timeout=0.3, callback=None):  # OLD unused CODE
    # assuming subnet mask is 255.255.255.0
    _RANGE = 256
    ipv4_address = get_ipv4()
    base = '.'.join(ipv4_address.split('.')[:-1])
    threads = []
    stop_discovery = False
    chromecasts = []

    def _stop_discovery():
        nonlocal stop_discovery
        stop_discovery = True

    def _connect_to_chromecast(ip, port=8009):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        port_alive = sock.connect_ex((ip, port))
        sock.close()
        if not stop_discovery and port_alive == 0:
            cc = pychromecast.Chromecast(ip, port=port)
            if callback is not None: callback(cc)
            else: chromecasts.append(cc)

    for i in range(_RANGE):
        possible_ip = f'{base}.{i}'
        t = Thread(target=_connect_to_chromecast, args=[possible_ip], daemon=True)
        threads.append(t)
        t.start()

    if callback is None:
        for t in threads:
            t.join()
        return chromecasts
    return _stop_discovery


def get_youtube_id(url):
    query = urlparse(url)
    if query.hostname == 'youtu.be': return query.path[1:]
    if query.hostname in ('www.youtube.com', 'youtube.com'):
        if query.path == '/watch': return parse_qs(query.query)['v'][0]
        if query.path[:7] == '/embed/': return query.path.split('/')[2]
        if query.path[:3] == '/v/': return query.path.split('/')[2]
    return None  # invalid url or YouTube url


def get_repeat_img_et_tooltip(repeat_setting):
    if repeat_setting is None: return REPEAT_OFF_IMG, 'Repeat'
    elif repeat_setting: return REPEAT_ONE_IMG, "Don't repeat"
    else: return REPEAT_ALL_IMG, 'Repeat track'


def create_progress_bar_text(position, length) -> (str, str):  #
    """":return: time_elapsed_text, time_left_text"""
    time_left = length - position
    mins_elapsed, mins_left = floor(position / 60), floor(time_left / 60)
    secs_elapsed, secs_left = floor(position % 60), floor(time_left % 60)
    if secs_left < 10: secs_left = f'0{secs_left}'
    if secs_elapsed < 10: secs_elapsed = f'0{secs_elapsed}'
    return f'{mins_elapsed}:{secs_elapsed}', f'{mins_left}:{secs_left}'


# GUI LAYOUTS
# noinspection PyUnusedLocal
def create_main(tracks, listbox_selected, playing_status, settings, version, qr_code, timer, title='Nothing Playing',
                artist='', album_cover_data=None, track_length=0, track_position=0):
    is_muted = settings['muted']
    volume = 0 if is_muted else settings['volume']
    v_slider_img = VOLUME_MUTED_IMG if is_muted else VOLUME_IMG
    repeating_track = settings['repeat']
    pause_resume_img = PAUSE_BUTTON_IMG if playing_status == 'PLAYING' else PLAY_BUTTON_IMG
    repeat_img, repeat_tooltip = get_repeat_img_et_tooltip(repeating_track)
    accent_color, fg, bg = settings['accent_color'], settings['text_color'], settings['background_color']
    button_text_color = settings['button_text_color']
    # main side for album cover, track title, track artist, and music controls
    pr_button = {'image_data': pause_resume_img, 'border_width': 0, 'metadata': playing_status}
    next_btn = {'image_data': NEXT_BUTTON_IMG, 'border_width': 0, 'metadata': playing_status, 'tooltip': 'next_track'}
    music_controls = [Sg.Button(key='prev', image_data=PREVIOUS_BUTTON_IMG, border_width=0, tooltip='previous track'),
                      Sg.Button(key='pause/resume', **pr_button),
                      # TODO: stop button
                      Sg.Button(key='next', **next_btn),
                      Sg.Button(key='repeat', image_data=repeat_img, tooltip=repeat_tooltip, border_width=0),
                      Sg.Image(data=v_slider_img, tooltip='Mute/Unmute', key='mute', enable_events=True),
                      Sg.Slider((0, 100), default_value=volume, orientation='h', key='volume_slider',
                                disable_number_display=True, enable_events=True, background_color=accent_color,
                                text_color='#000000', size=(10, 10), tooltip='Scroll mousewheel')]
    time_elapsed, time_left = create_progress_bar_text(track_position, track_length)
    text_size = (5, 1)
    progress_bar_layout = [Sg.Text(time_elapsed, size=text_size, font=FONT_NORMAL, key='time_elapsed',
                                   pad=((0, 5), (10, 0)), justification='right'),
                           Sg.Slider(range=(0, track_length), default_value=track_position,
                                     orientation='h', size=(30, 10), key='progressbar',
                                     enable_events=True, relief=Sg.RELIEF_FLAT, background_color=accent_color,
                                     disable_number_display=True, disabled=artist == '',
                                     tooltip='Scroll mousewheel', pad=((8, 8), (10, 0))),
                           Sg.Text(time_left, size=text_size, font=FONT_NORMAL, key='time_left', pad=((5, 0), (10, 0)))]
    # album_cover = [Sg.Image(data=album_cover_data, pad=(0, 0), size=(255, 255),
    #                         key='album_cover')] if album_cover_data else []
    # album_cover = [Sg.Image(data=WINDOW_ICON, pad=(0, 0), size=(255, 255), key='album_cover')]
    # use album_cover once I get a resizing lib
    main_side = Sg.Column([  # album_cover,
        [Sg.Text(title, font=FONT_TITLE, key='title', pad=((0, 0), (70, 10)), size=(35, 0), justification='center')],
        [Sg.Text(artist, font=FONT_ARTIST, key='artist', pad=((0, 0), (0, 30)), size=(35, 0), justification='center')],
        music_controls, progress_bar_layout], element_justification='center', pad=((5, 5), (5, 5)))
    # tabs side is for music queue, queue controls, and later, the music library
    # tab 1 is the queue, tab 2 will be the library
    file_options = ['Play File(s)', 'Play File(s) Next', 'Queue File(s)']
    folder_opts = ['Play Folder', 'Play Folder Next', 'Queue Folder']  # TODO: queue folders
    playlist_names = list(settings['playlists'].keys())
    queue_controls = [
        Sg.Column([[Sg.Combo(file_options, default_value='Play File(s)', key='file_option', size=(14, None),
                             font=FONT_NORMAL, enable_events=True, readonly=True, pad=(5, (5, 0)))],
                   [Sg.Combo(folder_opts, default_value='Play Folder', key='folder_option', size=(14, None),
                             font=FONT_NORMAL, enable_events=True, readonly=True, pad=(5, (10, 0)))]]),
        Sg.Column([[Sg.Button('Play File(s)', font=FONT_NORMAL, key='file_action',
                              enable_events=True, size=(13, 1))],
                   [Sg.Button('Play Folder', font=FONT_NORMAL, key='folder_action',
                              enable_events=True, size=(13, 1))]]),
        Sg.Column([[Sg.Combo(playlist_names, default_value=playlist_names[0] if playlist_names else None,
                             size=(14, 1), font=FONT_NORMAL, readonly=True, pad=(5, (5, 0)), key='playlists')],
                   [Sg.Button('Play Playlist', font=FONT_NORMAL, key='play_playlist', enable_events=True,
                              size=(14, 1), pad=(5, (9, 0)))]]),
        Sg.Column([[Sg.Button('URL Actions', font=FONT_NORMAL, key='url_actions', pad=(5, 5), enable_events=True)]]),
    ]
    listbox_controls = [
        # TODO: save queue to playlist
        [Sg.Button('CQ', key='clear_queue', tooltip='Clear the queue', size=(3, 1))],
        [Sg.Button('LF', key='locate_file', tooltip='Locate file in explorer', size=(3, 1))],
        [Sg.Button('▲', key='move_up', tooltip='Move track up', size=(3, 1))],
        [Sg.Button('❌', key='remove', tooltip='Remove track', size=(3, 1))],
        [Sg.Button('▼', key='move_down', tooltip='Move track down', size=(3, 1))]]
    queue_tab_layout = [queue_controls, [
        Sg.Listbox(tracks, default_values=listbox_selected, size=(64, 11),
                   select_mode=Sg.SELECT_MODE_SINGLE,
                   text_color=fg, key='queue', background_color=bg, font=FONT_NORMAL,
                   bind_return_key=True),
        Sg.Column(listbox_controls, pad=(0, 5))]]
    queue_tab = Sg.Tab('Queue', queue_tab_layout, background_color=bg, key='tab_queue')
    timer_layout = create_timer(settings, timer)
    timer_tab = Sg.Tab('Timer', timer_layout, background_color=bg, key='tab_timer')
    settings_layout = create_settings(version, settings, qr_code)
    settings_tab = Sg.Tab('Settings', settings_layout, background_color=bg, key='tab_settings')
    # TODO: library_tab = Sg.Tab()
    tabs_side = Sg.TabGroup([[queue_tab, timer_tab, settings_tab]], title_color=fg, border_width=0, key='tab_group',
                            tab_background_color=bg, selected_background_color=accent_color, enable_events=True,
                            selected_title_color=button_text_color)

    return [[main_side, tabs_side]] if settings['flip_main_window'] else [[tabs_side, main_side]]


def create_settings(version, settings, qr_code):
    fg, bg = settings['text_color'], settings['background_color']
    checkbox_col = Sg.Column([
        [Sg.Checkbox('Auto Update', default=settings['auto_update'], key='auto_update', background_color=bg,
                     font=FONT_NORMAL, enable_events=True, size=(20, 5), pad=((0, 5), (5, 5))),
         Sg.Checkbox('Discord Presence', default=settings['discord_rpc'], key='discord_rpc', background_color=bg,
                     font=FONT_NORMAL, enable_events=True, size=(13, 5), pad=((0, 5), (5, 5)))],
        [Sg.Checkbox('Notifications', default=settings['notifications'], key='notifications', background_color=bg,
                     font=FONT_NORMAL, enable_events=True, size=(20, 5), pad=((0, 5), (5, 5))),
         Sg.Checkbox('Run on Startup', default=settings['run_on_startup'], key='run_on_startup', background_color=bg,
                     font=FONT_NORMAL, enable_events=True, size=(13, 5), pad=((0, 5), (5, 5)))],
        [Sg.Checkbox('Save Window Positions', default=settings['save_window_positions'], key='save_window_positions',
                     size=(20, 5), background_color=bg, font=FONT_NORMAL, enable_events=True, pad=((0, 5), (5, 5))),
         Sg.Checkbox('Shuffle Playlists', default=settings['shuffle_playlists'], key='shuffle_playlists',
                     background_color=bg, font=FONT_NORMAL, enable_events=True, size=(13, 5), pad=((0, 5), (5, 5)))],
        [Sg.Checkbox('Populate Queue on Startup', default=settings['populate_queue_startup'],
                     tooltip='Populates Queue From Folders on Startup', key='populate_queue_startup',
                     size=(20, 5), background_color=bg, font=FONT_NORMAL, enable_events=True, pad=((0, 5), (5, 5))),
         Sg.Checkbox('Save Queue Between Sessions', default=settings['save_queue_sessions'], key='save_queue_sessions',
                     background_color=bg, font=FONT_NORMAL, enable_events=True, size=(23, 5), pad=((0, 5), (5, 5)))]
    ], pad=((0, 0), (5, 0)))
    qr_code__params = {'tooltip': 'Web GUI QR Code (click or scan)', 'image_data': qr_code, 'border_width': 0}
    qr_code_col = Sg.Column([[Sg.Button(**qr_code__params, key='web_gui')]], pad=(0, 0))
    email_params = {'text_color': LINK_COLOR, 'font': FONT_LINK, 'tooltip': 'Send me an email'}
    add_music_folder = {'button_text': 'Add Music Folder', 'font': FONT_NORMAL, 'enable_events': True, 'size': (15, 1)}
    open_settings_file = {'font': FONT_NORMAL, 'enable_events': True, 'size': (15, 1)}
    layout = [
        [Sg.Text(f'Music Caster Version {version} by Elijah Lopez', font=FONT_NORMAL),
         Sg.Text('elijahllopezz@gmail.com', **email_params, click_submits=True, key='email')],
        [checkbox_col, qr_code_col],
        [Sg.Listbox(settings['music_directories'], size=(52, 5), select_mode=Sg.SELECT_MODE_SINGLE, text_color=fg,
                    key='music_dirs', background_color=bg, font=FONT_NORMAL, bind_return_key=True, no_scrollbar=True),
         Sg.Frame('', [
             [Sg.Button('Remove Folder', key='remove_folder', enable_events=True, font=FONT_NORMAL, size=(15, 1))],
             [Sg.FolderBrowse(**add_music_folder, key='add_folder')],
             [Sg.Button('Open settings.json', **open_settings_file, key='settings_file')]],
                  background_color=bg, border_width=0)]]
    return layout


def create_timer(settings, timer):
    shut_off = settings['timer_shut_off_computer']
    hibernate = settings['timer_hibernate_computer']
    sleep = settings['timer_sleep_computer']
    fg, bg = settings['text_color'], settings['background_color']
    do_nothing = not (shut_off or hibernate or sleep)
    timer_date = datetime.datetime.fromtimestamp(timer)
    timer_date = timer_date.strftime('%#I:%M %p')
    timer_text = f'Timer set for {timer_date}' if timer else 'No Timer Set'
    # wait for last track to finish setting
    cancel_button = Sg.Button('Cancel Timer', key='cancel_timer', visible=timer != 0)
    layout = [
        [Sg.Radio('Shut off computer when timer runs out', 'TIMER', default=shut_off, key='shut_off', text_color=fg,
                  background_color=bg, font=FONT_NORMAL, enable_events=True, pad=((5, 5), (20, 5)))],
        [Sg.Radio('Hibernate computer when timer runs out', 'TIMER', default=hibernate, key='hibernate',
                  text_color=fg, background_color=bg, font=FONT_NORMAL, enable_events=True)],
        [Sg.Radio('Sleep computer when timer runs out', 'TIMER', default=sleep, key='sleep',
                  text_color=fg, background_color=bg, font=FONT_NORMAL, enable_events=True)],
        [Sg.Radio('Only stop playback', 'TIMER', default=do_nothing, key='do_nothing',
                  text_color=fg, background_color=bg, font=FONT_NORMAL, enable_events=True)],
        [Sg.Text('Enter minutes or HH:MM', tooltip='Press enter once done', font=FONT_NORMAL),
         Sg.Input(key='minutes', font=FONT_NORMAL, size=(11, 1)),
         Sg.Button('Submit', font=FONT_NORMAL, key='timer_submit')],
        [Sg.Text('Invalid Input (enter minutes or HH:MM)', font=FONT_NORMAL, visible=False, key='timer_error')],
        [Sg.Text(timer_text, font=FONT_NORMAL, key='timer_text', size=(18, 1)), cancel_button]
    ]
    return layout


def create_playlist_selector(settings):
    bg = settings['background_color']
    playlists = list(settings['playlists'].keys())
    layout = [
        [Sg.Combo(values=playlists, size=(41, 5), key='playlist_combo', background_color=bg, font=FONT_NORMAL,
                  enable_events=True, readonly=True, default_value=playlists[0] if playlists else None),
         Sg.Button('Edit', key='edit_pl', tooltip='Ctrl + E', enable_events=True, font=FONT_NORMAL),
         Sg.Button('Delete', key='del_pl', tooltip='Ctrl + Del', enable_events=True, font=FONT_NORMAL),
         Sg.Button('New', key='create_pl', tooltip='Ctrl + N', enable_events=True, font=FONT_NORMAL)]]
    return layout


def create_playlist_editor(settings, playlist_name=''):
    paths = settings['playlists'].get(playlist_name, [])
    fg, bg = settings['text_color'], settings['background_color']
    tracks = [f'{i + 1}. {os.path.splitext(os.path.basename(path))[0]}' for i, path in enumerate(paths)]
    move_up_params = {'size': (11, 1), 'tooltip': 'Ctrl + U', 'font': FONT_NORMAL, 'enable_events': True}
    move_down_params = {'size': (11, 1), 'tooltip': 'Ctrl + D', 'font': FONT_NORMAL, 'enable_events': True}
    add_tracks = [Sg.Button('Add track', key='Add tracks', tooltip='Ctrl + F',
                            size=(11, 1), font=FONT_NORMAL, enable_events=True)]
    layout = [[
        Sg.Text('Playlist name', font=FONT_NORMAL, size=(12, 1), justification='center'),
        Sg.Input(playlist_name, key='playlist_name', size=(39, 1), font=FONT_NORMAL),
        Sg.Submit('Save', key='Save', tooltip='Ctrl + S', font=FONT_NORMAL, size=(6, 1), pad=((14, 5), (5, 5))),
        Sg.Button('❌', key='Cancel', tooltip='Cancel (Esc)', font=FONT_NORMAL, enable_events=True, size=(3, 1))],
        [Sg.Frame('', [add_tracks,
                       [Sg.Button('Remove track', key='Remove track', tooltip='Ctrl + R', font=FONT_NORMAL,
                                  enable_events=True, size=(11, 1))]], background_color=bg, border_width=0),
         Sg.Listbox(tracks, size=(37, 5), select_mode=Sg.SELECT_MODE_SINGLE, text_color=fg,
                    key='tracks', background_color=bg, font=FONT_NORMAL, enable_events=True),
         Sg.Frame('', [[Sg.Button('Move up', **move_up_params, key='move_up')],
                       [Sg.Button('Move down', **move_down_params, key='move_down')]],
                  background_color=bg, border_width=0)]]
    return layout


def create_play_url_window(combo_value='Play Immediately'):
    # checkbox for queue/play immediately https://www.youtube.com/watch?v=kPC_evpbwDM
    combo_values = ['Play Immediately', 'Queue', 'Play Next']
    layout = [[Sg.Text('Enter URL (YouTube or *.ext src)', font=FONT_NORMAL),
               Sg.Combo(combo_values, default_value=combo_value, key='combo_choice', readonly=True)],
              [Sg.Input(key='url', font=FONT_NORMAL), Sg.Submit(font=FONT_NORMAL)]]
    return layout


def is_os_64bit():
    return platform.machine().endswith('64')


def add_reg_handlers(path_to_exe):
    """ Register Music Caster as a program to open audio files and folders """
    # https://docs.microsoft.com/en-us/visualstudio/extensibility/registering-verbs-for-file-name-extensions?view=vs-2019
    # TODO: use arg parser
    # TODO: queue file option
    # TODO: queue folder option
    path_to_exe = path_to_exe.replace('/', '\\')
    classes_path = 'SOFTWARE\\Classes\\'
    key_name_ext = 'MusicCaster_file'
    write_access = wr.KEY_WRITE | wr.KEY_WOW64_64KEY if is_os_64bit() else wr.KEY_WRITE
    read_access = wr.KEY_READ | wr.KEY_WOW64_64KEY if is_os_64bit() else wr.KEY_READ
    # create handlers
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{classes_path}{key_name_ext}', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, 'Audio File')
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{classes_path}{key_name_ext}\\DefaultIcon', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, path_to_exe)  # define icon location
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{classes_path}{key_name_ext}\\shell\\open', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, f'Play')
        wr.SetValueEx(key, 'MultiSelectModel', 0, wr.REG_SZ, 'Player')
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{classes_path}{key_name_ext}\\shell\\open\\command', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" "%1"')
    # with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{classes_path}{key_name_ext}\\shell\\queue', 0, write_access) as key:
    #     wr.SetValueEx(key, None, 0, wr.REG_SZ, f'Queue file in Music Caster')
    #     wr.SetValueEx(key, 'Icon', 0, wr.REG_SZ, path_to_exe)
    #     wr.SetValueEx(key, 'MultiSelectModel', 0, wr.REG_SZ, 'Player')
    # with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{classes_path}{key_name_ext}\\shell\\queue\\command', 0, write_access) as key:
    #     wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" "%1"')
    # set file handlers
    for ext in {'.mp3', '.flac', '.m4a', '.mp4', '.aac', '.ogg', '.opus', '.wma', '.wav'}:
        key_path = f'{classes_path}{ext}'
        try:
            # check if key exists
            with wr.OpenKeyEx(wr.HKEY_CURRENT_USER, key_path, 0, read_access) as key: pass
        except (WindowsError, FileNotFoundError):
            # create key if it does not exist
            with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, key_path, 0, write_access) as key:
                # set as default program unless .mp4 because that's a video format
                if ext != '.mp4':
                    wr.SetValueEx(key, None, 0, wr.REG_SZ, 'MusicCaster_file')
        # add to Open With (prompts user to set default program)
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{key_path}\\OpenWithProgids', 0, write_access) as key:
            wr.SetValueEx(key, key_name_ext, 0, wr.REG_NONE, b'')
    # set open folder in Music Caster
    play_folder_key_path = f'{classes_path}\\Directory\\shell\\MusicCasterPlayFolder'
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, play_folder_key_path, 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, 'Play with Music Caster')
        wr.SetValueEx(key, 'Icon', 0, wr.REG_SZ, path_to_exe)
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{play_folder_key_path}\\command', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" "%1"')
    # queue_folder_key_path = f'{classes_path}\\Directory\\shell\\MusicCasterQueueFolder'
    # with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, queue_folder_key_path, 0, access) as key:
    #     wr.SetValueEx(key, None, 0, wr.REG_SZ, 'Queue Folder in Music Caster')
    #     wr.SetValueEx(key, 'Icon', 0, wr.REG_SZ, path_to_exe)
    # with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{queue_folder_key_path}\\command', 0, access) as key:
    #     wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" --queue_folders "%1"')

