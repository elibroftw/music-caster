import time
from functools import wraps
import os
import platform
import pyqrcode
import PySimpleGUI as Sg
import socket
from urllib.parse import urlparse, parse_qs
import uuid
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
from wavinfo import WavInfoReader  # until mutagen supports .wav
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
    try:
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
        _artist = ', '.join(audio.get('artist', ['Unknown Artist']))
        _album = audio.get('album', ['Unknown Album'])[0]
    except (ID3NoHeaderError, HeaderNotFoundError):
        pass
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


def get_mac(): return ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) for ele in range(0, 8 * 6, 8)][::-1])


def create_qr_code(port):
    qr_code = pyqrcode.create(f'http://{get_ipv4()}:{port}')
    return qr_code.png_as_base64_str(scale=3, module_color=(255, 255, 255, 255), background=(18, 18, 18, 255))


def get_running_processes():
    # edited from https://stackoverflow.com/a/22914414/7732434
    p = Popen('tasklist', shell=True, stdout=PIPE, stdin=DEVNULL, stderr=DEVNULL)
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


def is_already_running():
    threshold = 1
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


def find_chromecasts(timeout=0.3, callback=None):
    # assuming subnet mask is 255.255.255.0
    _RANGE = 256
    ipv4_address = get_ipv4()
    base = '.'.join(ipv4_address.split('.')[:-1])
    thread_results = []
    threads = []
    stop_discovery = False

    def _stop_discovery():
        nonlocal stop_discovery
        stop_discovery = True

    def _connect_to_chromecast(ip, thread_index: int, port=8009):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        port_alive = sock.connect_ex((ip, port))
        sock.close()
        if not stop_discovery and port_alive == 0:
            if callback is not None: callback(pychromecast.Chromecast(ip))
            else: thread_results[thread_index] = ip
        return port_alive == 0

    for i in range(_RANGE):
        possible_ip = f'{base}.{i}'
        t = Thread(target=_connect_to_chromecast, args=[possible_ip, i], daemon=True)
        threads.append(t)
        thread_results.append(False)
        t.start()

    if callback is None:
        chromecasts = []
        for i, t in enumerate(threads):
            t.join()
            result = thread_results[i]  # ip address or False
            if result:
                cc = pychromecast.Chromecast(result)
                if callback: callback(cc)
                else: chromecasts.append(cc)
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


# GUI LAYOUTS
# noinspection PyUnusedLocal
def create_main_gui(songs, listbox_selected, playing_status, settings, version, qr_code,
                    title='Nothing Playing', artist='', album_cover_data=None):
    is_muted = settings['muted']
    volume = 0 if is_muted else settings['volume']
    v_slider_img = VOLUME_MUTED_IMG if is_muted else VOLUME_IMG
    repeating_song = settings['repeat']
    pause_resume_img = PAUSE_BUTTON_IMG if playing_status == 'PLAYING' else PLAY_BUTTON_IMG
    repeat_img, repeat_tooltip = get_repeat_img_et_tooltip(repeating_song)
    accent_color, fg, bg = settings['accent_color'], settings['text_color'], settings['background_color']
    button_text_color = settings['button_text_color']
    # main side for album cover, track title, track artist, and music controls
    music_controls = [Sg.Button(key='prev', image_data=PREVIOUS_BUTTON_IMG, border_width=0),
                      Sg.Button(key='pause/resume', image_data=pause_resume_img, border_width=0),
                      Sg.Button(key='next', image_data=NEXT_BUTTON_IMG, border_width=0, metadata=playing_status),
                      Sg.Button(key='repeat', image_data=repeat_img, tooltip=repeat_tooltip, border_width=0),
                      # TODO: modify tooltip
                      Sg.Image(data=v_slider_img, tooltip='Mute/Unmute', key='mute', enable_events=True),
                      Sg.Slider((0, 100), default_value=volume, orientation='h', key='volume_slider',
                                disable_number_display=True, enable_events=True, background_color=accent_color,
                                text_color='#000000', size=(10, 10), tooltip='Scroll mousewheel')]
    progress_bar_layout = [Sg.Text('00:00', font=FONT_NORMAL, key='time_elapsed', pad=((5, 5), (10, 0))),
                           Sg.Slider(range=(0, 100), orientation='h', size=(30, 10), key='progressbar',
                                     enable_events=True, relief=Sg.RELIEF_FLAT, background_color=accent_color,
                                     disable_number_display=True, disabled=artist == '',
                                     tooltip='Scroll mousewheel', pad=((5, 5), (10, 0))),
                           Sg.Text('00:00', font=FONT_NORMAL, key='time_left', pad=((5, 5), (10, 0)))]
    # album_cover = [Sg.Image(data=album_cover_data, pad=(0, 0), size=(255, 255),
    #                         key='album_cover')] if album_cover_data else []
    # album_cover = [Sg.Image(data=WINDOW_ICON, pad=(0, 0), size=(255, 255), key='album_cover')]
    # use album_cover once I get a resizing lib
    main_side = Sg.Column([  # album_cover,
        [Sg.Text(title, font=FONT_TITLE, key='title', pad=((0, 0), (100, 0)), size=(35, 0), justification='center')],
        [Sg.Text(artist, font=FONT_ARTIST, key='artist', pad=((0, 0), (0, 10)), size=(35, 0), justification='center')],
        music_controls, progress_bar_layout], element_justification='center', pad=((5, 5), (5, 5)))

    # tabs side is for music queue, queue controls, and later, the music library
    # tab 1 is the queue, tab 2 will be the library
    queue_controls = [
        Sg.Button('Queue File(s)', font=FONT_NORMAL, key='queue_file', pad=(5, 5)),
        Sg.Button('Queue Folder', font=FONT_NORMAL, key='queue_folder', pad=(5, 5)),
        Sg.Button('Play Next', font=FONT_NORMAL, key='play_next', pad=(5, 5)),
        Sg.Button('Clear Queue', font=FONT_NORMAL, key='clear_queue', pad=(5, 5)),
        Sg.Button('Locate File', font=FONT_NORMAL, key='locate_file', pad=(5, 5),
                  tooltip='Show selected file in explorer')]
    listbox_controls = [
        [Sg.Button('▲', key='move_up', tooltip='Move song up the queue', size=(3, 1))],
        [Sg.Button('❌', key='remove', tooltip='Remove song from the queue', size=(3, 1))],
        [Sg.Button('▼', key='move_down', tooltip='Move song down the queue', size=(3, 1))]]
    if settings['EXPERIMENTAL']:
        queue_controls.insert(2, Sg.Button('Queue URL', font=FONT_NORMAL, key='queue_url', pad=(5, 5)))
        listbox_size = (64, 13)
    else:
        listbox_size = (58, 13)
    queue_tab_layout = [queue_controls, [
        Sg.Listbox(songs, default_values=listbox_selected, size=listbox_size,
                   select_mode=Sg.SELECT_MODE_SINGLE,
                   text_color=fg, key='queue', background_color=bg, font=FONT_NORMAL,
                   bind_return_key=True),
        Sg.Column(listbox_controls, pad=(0, 5))]]
    queue_tab = Sg.Tab('Queue', queue_tab_layout, background_color=bg, key='tab_queue')
    # TODO: library tab
    # library_tab = Sg.Tab()
    settings_layout = create_settings(version, settings, qr_code)
    settings_tab = Sg.Tab('Settings', settings_layout, background_color=bg, key='tab_settings')
    tabs_side = Sg.TabGroup([[queue_tab, settings_tab]], key='tab_group', title_color=fg, tab_background_color=bg,
                            selected_title_color=button_text_color, selected_background_color=accent_color,
                            border_width=0)

    return [[main_side, tabs_side]] if settings['flip_main_window'] else [[tabs_side, main_side]]


def create_settings(version, settings, qr_code):
    fg, bg = settings['text_color'], settings['background_color']
    checkbox_col = Sg.Column([
        [Sg.Checkbox('Auto Update', default=settings['auto_update'], key='auto_update',
                     background_color=bg, font=FONT_NORMAL, enable_events=True, size=(20, 5),
                     pad=((0, 5), (5, 5))),
         Sg.Checkbox('Discord Presence', default=settings['discord_rpc'], key='discord_rpc',
                     background_color=bg, font=FONT_NORMAL, enable_events=True, size=(13, 5),
                     pad=((0, 5), (5, 5)))],
        [Sg.Checkbox('Notifications', default=settings['notifications'], key='notifications',
                     background_color=bg, font=FONT_NORMAL, enable_events=True, size=(20, 5),
                     pad=((0, 5), (5, 5))),
         Sg.Checkbox('Run on Startup', default=settings['run_on_startup'], key='run_on_startup',
                     background_color=bg, font=FONT_NORMAL, enable_events=True, size=(13, 5),
                     pad=((0, 5), (5, 5)))],
        [Sg.Checkbox('Save Window Positions', default=settings['save_window_positions'],
                     key='save_window_positions', size=(20, 5), background_color=bg, font=FONT_NORMAL,
                     enable_events=True, pad=((0, 5), (5, 5))),
         Sg.Checkbox('Shuffle Playlists', default=settings['shuffle_playlists'], key='shuffle_playlists',
                     background_color=bg, font=FONT_NORMAL, enable_events=True, size=(13, 5),
                     pad=((0, 5), (5, 5)))],
        [Sg.Checkbox('Populate Queue on Startup', default=settings['populate_queue_startup'],
                     tooltip='Populates Queue From Folders on Startup',
                     key='populate_queue_startup', size=(20, 5), background_color=bg, font=FONT_NORMAL,
                     enable_events=True, pad=((0, 5), (5, 5))),
         Sg.Checkbox('Save Queue Between Sessions', default=settings['save_queue_sessions'], key='save_queue_sessions',
                     background_color=bg, font=FONT_NORMAL, enable_events=True, size=(23, 5),
                     pad=((0, 5), (5, 5)))]
    ], pad=((0, 0), (5, 0)))
    qr_code_col = Sg.Column([
        [Sg.Button(image_data=qr_code, tooltip='Web GUI QR Code (click or scan)', key='web_gui', border_width=0)]],
        pad=(0, 0))
    layout = [
        [Sg.Text(f'Music Caster Version {version} by Elijah Lopez', font=FONT_NORMAL),
         Sg.Text('elijahllopezz@gmail.com', text_color=LINK_COLOR, font=FONT_LINK, click_submits=True, key='email',
                 tooltip='Click to send me an email')],
        [checkbox_col, qr_code_col],
        [Sg.Listbox(settings['music_directories'], size=(52, 5), select_mode=Sg.SELECT_MODE_SINGLE, text_color=fg,
                    key='music_dirs', background_color=bg, font=FONT_NORMAL, bind_return_key=True, no_scrollbar=True),
         Sg.Frame('', [
             [Sg.Button('Remove Folder', key='remove_folder', enable_events=True, font=FONT_NORMAL, size=(15, 1))],
             [Sg.FolderBrowse('Add Music Folder', font=FONT_NORMAL, enable_events=True, key='add_folder',
                              size=(15, 1))],
             [Sg.Button('Open settings.json', key='settings_file', font=FONT_NORMAL, enable_events=True,
                        size=(15, 1))]],
                  background_color=bg, border_width=0)]]
    return layout


def create_timer(settings):
    shut_off = settings['timer_shut_off_computer']
    hibernate = settings['timer_hibernate_computer']
    sleep = settings['timer_sleep_computer']
    fg, bg = settings['text_color'], settings['background_color']
    do_nothing = not (shut_off or hibernate or sleep)
    layout = [
        [Sg.Radio('Shut off computer when timer runs out', 'TIMER', default=shut_off,
                  key='shut_off', text_color=fg, background_color=bg, font=FONT_NORMAL,
                  enable_events=True)],
        [Sg.Radio('Hibernate computer when timer runs out', 'TIMER', default=hibernate,
                  key='hibernate', text_color=fg, background_color=bg, font=FONT_NORMAL,
                  enable_events=True)],
        [Sg.Radio('Sleep computer when timer runs out', 'TIMER', default=sleep,
                  key='sleep', text_color=fg, background_color=bg, font=FONT_NORMAL,
                  enable_events=True)],
        [Sg.Radio('Only stop playback', 'TIMER', default=do_nothing,
                  key='do_nothing', text_color=fg, background_color=bg, font=FONT_NORMAL,
                  enable_events=True)],
        [Sg.Text('Enter minutes or HH:MM', tooltip='Press enter once done', font=FONT_NORMAL)],
        [Sg.Input(key='minutes', font=FONT_NORMAL), Sg.Submit(font=FONT_NORMAL)],
        [Sg.Text('Invalid Input (enter minutes or HH:MM)', font=FONT_NORMAL, visible=False, key='error')]]
    return layout


def create_playlist_selector(settings):
    bg = settings['background_color']
    playlists = list(settings['playlists'].keys())
    layout = [
        [Sg.Combo(values=playlists, size=(41, 5), key='pl_selector', background_color=bg, font=FONT_NORMAL,
                  enable_events=True, readonly=True, default_value=playlists[0] if playlists else None),
         Sg.Button(button_text='Edit', key='edit_pl', tooltip='Ctrl + E', enable_events=True, font=FONT_NORMAL),
         Sg.Button(button_text='Delete', key='del_pl', tooltip='Ctrl + Del', enable_events=True, font=FONT_NORMAL),
         Sg.Button(button_text='New', key='create_pl', tooltip='Ctrl + N', enable_events=True, font=FONT_NORMAL)]]
    return layout


def create_playlist_editor(initial_folder, settings, playlist_name=''):
    paths = settings['playlists'].get(playlist_name, [])
    fg, bg = settings['text_color'], settings['background_color']
    songs = [f'{i + 1}. {os.path.splitext(os.path.basename(path))[0]}' for i, path in enumerate(paths)]
    layout = [[
        Sg.Text('Playlist name', font=FONT_NORMAL, size=(12, 1), justification='center'),
        Sg.Input(playlist_name, key='playlist_name', size=(39, 1), font=FONT_NORMAL),
        Sg.Submit('Save', key='Save', tooltip='Ctrl + S', font=FONT_NORMAL, size=(6, 1), pad=((14, 5), (5, 5))),
        Sg.Button('❌', key='Cancel', tooltip='Cancel (Esc)', font=FONT_NORMAL, enable_events=True, size=(3, 1))],
        [Sg.Frame('', [[Sg.FilesBrowse('Add songs', key='Add songs', file_types=(('Audio Files', '*.mp3'),),
                                       size=(11, 1), initial_folder=initial_folder, font=FONT_NORMAL,
                                       enable_events=True)],
                       [Sg.Button('Remove song', key='Remove song', tooltip='Ctrl + R', font=FONT_NORMAL,
                                  enable_events=True, size=(11, 1))]],
                  background_color=bg, border_width=0),
         Sg.Listbox(songs, size=(37, 5), select_mode=Sg.SELECT_MODE_SINGLE, text_color=fg,
                    key='songs', background_color=bg, font=FONT_NORMAL, enable_events=True),
         Sg.Frame('', [
             [Sg.Button('Move up', size=(11, 1), key='move_up', tooltip='Ctrl + U', font=FONT_NORMAL,
                        enable_events=True)],
             [Sg.Button('Move down', size=(11, 1), key='move_down', tooltip='Ctrl + D', font=FONT_NORMAL,
                        enable_events=True)]
         ], background_color=bg, border_width=0)]]
    return layout


def create_play_url_window():
    layout = [[Sg.Text('Enter url.\nSupports: YouTube', font=FONT_NORMAL)],
              [Sg.Input(key='url', font=FONT_NORMAL), Sg.Submit(font=FONT_NORMAL)]]
    return layout


# TODO: REGISTRY MODIFICATION to set as default music file handler
# https://docs.microsoft.com/en-us/visualstudio/extensibility/registering-verbs-for-file-name-extensions?view=vs-2019
# if not settings.get('DEBUG', False) and getattr(sys, 'frozen', False) and settings['default_file_handler']:
#     menu_name = 'Open With Music Caster'
#     import winreg as wr
#     for ext in ['Folder', '.mp3']:
#         # Check for extension handler override
#         key_val = 'SOFTWARE\\Classes\\' + ext + '\\shell\\' + menu_name + '\\command'
#         try:
#             key = wr.OpenKey(wr.HKEY_LOCAL_MACHINE, key_val, 0, wr.KEY_ALL_ACCESS)
#         except WindowsError:
#             key = wr.CreateKey(wr.HKEY_LOCAL_MACHINE, key_val)
#         path_to_exe = f'{starting_dir}\\Music Caster.exe'
#         wr.SetValueEx(key, '', 0, wr.REG_SZ, f'"{path_to_exe}"' + '\\"%1"\\')
#         wr.CloseKey(key)
