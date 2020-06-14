from functools import wraps
import os
import platform
import pyqrcode
import PySimpleGUI as Sg
import socket
import time
from urllib.parse import urlparse, parse_qs
import uuid
from b64_images import *
from subprocess import PIPE, DEVNULL
import subprocess
import threading
import re
import pychromecast

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = 'hide'
# FUTURE: C++ JPG TO PNG
# https://stackoverflow.com/questions/13739463/how-do-you-convert-a-jpg-to-png-in-c-on-windows-8
# Styling
fg, bg = '#aaaaaa', '#121212'
font_normal = 'SourceSans', 11
font_link = 'SourceSans', 11, 'underline'
LINK_COLOR, ACCENT_COLOR = '#3ea6ff', '#00bfff'
BUTTON_COLOR = ('#000000', ACCENT_COLOR)
Sg.change_look_and_feel('SystemDefault')
# TODO: add right click menus for list boxes


def timing(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        _start = time.time()
        result = f(*args, **kwargs)
        print(f'{f.__name__} ELAPSED TIME:', time.time() - _start)
        return result
    return wrapper


def fix_path(path, by_os=True):
    if by_os and platform.system() == 'Windows': return path.replace('/', '\\')
    else: return path.replace('\\', '/')


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
    # ~0.8 seconds
    # edited from https://stackoverflow.com/a/22914414/7732434
    p = subprocess.run('tasklist', shell=True, stderr=PIPE, stdin=DEVNULL, stdout=PIPE)
    tasks = p.stdout.decode().splitlines()
    for task in tasks:
        m = re.match(r'(.+?) +(\d+) (.+?) +(\d+) +(\d+.* K).*', task)
        if m is not None:
            process = {'name': m.group(1),  # Image name
                       'pid': m.group(2),
                       'session_name': m.group(3),
                       'session_num': m.group(4),
                       'mem_usage': m.group(5)}
            yield process


def is_already_running():
    instances = 0
    for process in get_running_processes():
        process_name = process['name']
        if process_name == 'Music Caster.exe':
            instances += 1
            if instances > 2: return True
    return False


# _nonbmp = re.compile(r'[\U00010000-\U0010FFFF]')
# def _surrogate_pair(match):
#     char = match.group()
#     assert ord(char) > 0xffff
#     encoded = char.encode('utf-16-le')
#     return chr(int.from_bytes(encoded[:2], 'little')) + chr(int.from_bytes(encoded[2:], 'little'))
# def with_surrogates(text):
#     return _nonbmp.sub(_surrogate_pair, text)
MUSIC_FILE_TYPES = 'Audio File (.mp3, .flac, .m4a, .mp4, .aac, .ogg, .opus, .wma, .wav)|' \
                   '*.mp3;*.flac;*.m4a;*.mp4;*.aac;*.ogg;*.opus;*.wma;*.wav'


def valid_music_file(file_path):
    file_path = file_path.lower()
    # NOTE: pygame only supports (mp3, oog, and wav)
    return (file_path.endswith('.mp3') or file_path.endswith('.flac')
            or file_path.endswith('.m4a') or file_path.endswith('.mp4') or file_path.endswith('.aac')
            or file_path.endswith('.ogg') or file_path.endswith('.opus')
            or file_path.endswith('.wma') or file_path.endswith('.wav'))


def find_chromecasts(timeout=0.3, callback=None):
    # assuming subnet mask is 255.255.255.0
    _RANGE = 256
    ipv4_address = get_ipv4()
    base = '.'.join(ipv4_address.split('.')[:-1])
    thread_results = []
    threads = []
    chromecasts = []
    stop_discovery = False

    def _stop_discovery():
        nonlocal stop_discovery
        stop_discovery = True

    def _connect_to_chromecast(ip, port=8009, thread_index=None):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        port_alive = sock.connect_ex((ip, port))
        sock.close()
        if not stop_discovery and port_alive == 0:
            if callback is not None:
                callback(pychromecast.Chromecast(ip))
            elif thread_results:
                assert isinstance(thread_index, int)
                thread_results[thread_index] = ip
        return port_alive == 0

    for i in range(_RANGE):
        possible_ip = f'{base}.{i}'
        kwargs = {'thread_index': i}
        t = threading.Thread(target=_connect_to_chromecast, args=[possible_ip], kwargs=kwargs, daemon=True)
        threads.append(t)
        thread_results.append(False)
        t.start()

    if callback is None:
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
    # fail?
    return None


# GUI RELATED FUNCTIONS
def create_songs_list(music_queue, done_queue, next_queue):
    # TODO: use metadata and song names or just one artist name
    """:returns the formatted song queue, and the selected value (currently playing)"""
    songs = []
    dq_len = len(done_queue)
    mq_start = len(next_queue) + 1
    selected_value = None
    # format: Index. Artists - Song Name
    for i, path in enumerate(done_queue):
        base = os.path.basename(path)
        base = os.path.splitext(base)[0]
        formatted_item = f'-{dq_len - i}. {base}'
        songs.append(formatted_item)
    if music_queue:
        base = os.path.basename(music_queue[0])
        base = os.path.splitext(base)[0]
        formatted_item = f' {0}. {base}'
        songs.append(formatted_item)
        selected_value = formatted_item
    for i, path in enumerate(next_queue):
        base = os.path.basename(path)
        base = os.path.splitext(base)[0]
        formatted_item = f' {i + 1}. {base}'
        songs.append(formatted_item)
    for i, path in enumerate(music_queue[1:]):
        base = os.path.basename(path)
        base = os.path.splitext(base)[0]
        formatted_item = f' {i + mq_start}. {base}'
        songs.append(formatted_item)
    return songs, selected_value


# GUI LAYOUTS
def create_main_gui(music_queue, done_queue, next_queue, playing_status, settings,
                    now_playing_text='Nothing Playing', album_cover_data=None):
    # TODO: Music Library Tab
    # TODO: Play Folder option
    is_muted = settings['muted']
    volume = 0 if is_muted else settings['volume']
    v_slider_img = VOLUME_MUTED_IMG if is_muted else VOLUME_IMG
    repeating_song = settings['repeat']
    pause_resume_img = PAUSE_BUTTON_IMG if playing_status == 'PLAYING' else PLAY_BUTTON_IMG
    # Sg.Button('Shuffle', key='Shuffle'),
    if repeating_song is None:
        repeat_img = REPEAT_OFF_IMG
        repeat_btn_tooltip = 'click to repeat all, click again to repeat one'
    elif repeating_song:
        repeat_img = REPEAT_ONE_IMG
        repeat_btn_tooltip = 'click to turn repeat off, click again to repeat all'
    else:
        repeat_img = REPEAT_ALL_IMG
        repeat_btn_tooltip = 'click to turn repeat one, click again to turn repeat off'
    music_controls = [[Sg.Button(key='prev', image_data=PREVIOUS_BUTTON_IMG),
                       # border_width=0, first add border to images
                       Sg.Button(key='pause/resume', image_data=pause_resume_img),
                       Sg.Button(key='next', image_data=NEXT_BUTTON_IMG),
                       Sg.Button(key='repeat', image_data=repeat_img, tooltip=repeat_btn_tooltip),
                       Sg.Image(data=v_slider_img, tooltip='press to mute/unmute', key='mute', enable_events=True),
                       Sg.Slider((0, 100), default_value=volume, orientation='h', key='volume_slider',
                                 disable_number_display=True, enable_events=True, background_color=ACCENT_COLOR,
                                 text_color='#000000', size=(10, 10), tooltip='scroll your mousewheel')]]
    progress_bar_layout = [[Sg.Text('00:00', font=font_normal, text_color=fg, key='time_elapsed'),
                            Sg.Slider(range=(0, 100), orientation='h', size=(30, 10), key='progressbar',
                                      enable_events=True, relief=Sg.RELIEF_FLAT, background_color=ACCENT_COLOR,
                                      disable_number_display=True, disabled=now_playing_text == 'Nothing Playing',
                                      tooltip='scroll your mousewheel'),
                            # Sg.ProgressBar(100, orientation='h', size=(30, 20), key='progressbar', style='clam'),
                            Sg.Text('00:00', font=font_normal, text_color=fg, key='time_left')]]

    # Now Playing layout
    tab1_layout = [[Sg.Text(now_playing_text, font=font_normal, text_color=fg, key='now_playing',
                            size=(55, 0))],
                   [Sg.Image(data=album_cover_data, pad=(0, 0), size=(50, 50),
                             key='album_cover')] if album_cover_data else [],
                   # [Sg.Image(data=album_cover_data, pad=(0, 0), size=(0, 150), key='album_cover'),
                   #  Sg.Slider((range(0, 100)))] if album_cover_data else [Sg.Slider((range(0, 100)))],
                   # Maybe make volume on its own tab or horizontal?
                   [Sg.Column(music_controls, justification='center', pad=((5, 5), (20, 0)))],
                   [Sg.Column(progress_bar_layout, justification='center', pad=((5, 5), (20, 0)))]]
    # Music Queue layout
    songs, selected_value = create_songs_list(music_queue, done_queue, next_queue)
    mq_controls = [
        [Sg.Button('▲', key='move_up', pad=(2, 5), tooltip='move song up the queue')],
        [Sg.Button('❌', key='remove', pad=(0, 5), tooltip='remove song from the queue')],
        [Sg.Button('▼', key='move_down', pad=(2, 5), tooltip='move song down the queue')]]
    q_controls1 = [
        Sg.Button('Queue File(s)...', font=font_normal, key='queue_file', pad=(5, 5)),
        Sg.Button('Queue Folder...', font=font_normal, key='queue_folder', pad=(5, 5)),
        Sg.Button('Play Next...', font=font_normal, key='play_next', pad=(5, 5)),
        Sg.Button('Clear Queue', font=font_normal, key='clear_queue', pad=(5, 5)),
        Sg.Button('Locate File', font=font_normal, key='locate_file', pad=(5, 5),
                  tooltip='show selected file in explorer')]
    tab2_layout = [q_controls1, [
        Sg.Listbox(songs, default_values=selected_value, size=(58, 5), select_mode=Sg.SELECT_MODE_SINGLE, text_color=fg,
                   key='music_queue', background_color=bg, font=font_normal, bind_return_key=True),
        Sg.Column(mq_controls, pad=(0, 5))]]
    # song_lib = sorted(all_songs.keys())
    # tab3_layout = [[
    #     Sg.Listbox(song_lib, size=(80, 30), default_values=song_lib[0] if song_lib else '', text_color=fg,
    #                background_color=bg, font=font_normal, key='library')
    # ]]
    layout = [[Sg.TabGroup([[Sg.Tab('Now Playing', tab1_layout, background_color=bg, key='tab1'),
                             Sg.Tab('Music Queue', tab2_layout, background_color=bg, key='tab2')]])]]
    # Sg.Tab('Library', tab3_layout, background_color=bg, key='tab3')]])]]
    return layout


def create_settings(version, music_directories, settings, qr_code_data):
    checkbox_col = Sg.Column([
        [Sg.Checkbox('Auto Update', default=settings['auto_update'], key='auto_update', text_color=fg,
                     background_color=bg, font=font_normal, enable_events=True, size=(17, None),
                     pad=((0, 5), (5, 5))),
         Sg.Checkbox('Discord Presence', default=settings['discord_rpc'], key='discord_rpc',
                     text_color=fg, background_color=bg, font=font_normal, enable_events=True, size=(13, None),
                     pad=((0, 5), (5, 5)))],
        [Sg.Checkbox('Notifications', default=settings['notifications'], key='notifications',
                     text_color=fg, background_color=bg, font=font_normal, enable_events=True, size=(17, None),
                     pad=((0, 5), (5, 5))),
         Sg.Checkbox('Run on Startup', default=settings['run_on_startup'], key='run_on_startup', text_color=fg,
                     background_color=bg, font=font_normal, enable_events=True, size=(13, None),
                     pad=((0, 5), (5, 5)))],
        [Sg.Checkbox('Save Window Positions', default=settings['save_window_positions'],
                     key='save_window_positions', size=(17, None), text_color=fg, background_color=bg, font=font_normal,
                     enable_events=True, pad=((0, 5), (5, 5))),
         Sg.Checkbox('Shuffle Playlists', default=settings['shuffle_playlists'], key='shuffle_playlists',
                     text_color=fg, background_color=bg, font=font_normal, enable_events=True, size=(13, None),
                     pad=((0, 5), (5, 5)))]
        ], pad=((0, 0), (5, 0)))
    qr_code_col = Sg.Column([
        [Sg.Button(image_data=qr_code_data, tooltip='Web GUI QR Code (click or scan)', key='web_gui', border_width=0)]],
        pad=(0, 0))
    layout = [
        [Sg.Text(f'Music Caster Version {version} by Elijah Lopez', text_color=fg, font=font_normal),
         Sg.Text('elijahllopezz@gmail.com', text_color=LINK_COLOR, font=font_link, click_submits=True, key='email',
                 tooltip='Click to send me an email')],
        [checkbox_col, qr_code_col],
        # [Sg.Slider((0, 100), default_value=settings['volume'], orientation='h', key='volume', tick_interval=5,
        #            enable_events=True, background_color=ACCENT_COLOR, text_color='#000000', size=(49, 15))],
        [Sg.Listbox(music_directories, size=(40, 5), select_mode=Sg.SELECT_MODE_SINGLE, text_color=fg,
                    key='music_dirs', background_color=bg, font=font_normal, enable_events=True, no_scrollbar=True),
         Sg.Frame('', [
             [Sg.Button('Remove Folder', key='remove_folder', enable_events=True, font=font_normal)],
             [Sg.FolderBrowse('Add Music Folder', font=font_normal, enable_events=True, key='add_folder')],
             [Sg.Button('Open settings.json', key='settings_file', font=font_normal,
                        enable_events=True)]], background_color=bg, border_width=0)]]
    return layout


def create_timer(settings):
    shut_off = settings['timer_shut_off_computer']
    hibernate = settings['timer_hibernate_computer']
    sleep = settings['timer_sleep_computer']
    do_nothing = not (shut_off or hibernate or sleep)
    layout = [
        [Sg.Radio('Shut off computer when timer runs out', 'TIMER', default=shut_off,
                  key='shut_off', text_color=fg, background_color=bg, font=font_normal,
                  enable_events=True)],
        [Sg.Radio('Hibernate computer when timer runs out', 'TIMER', default=hibernate,
                  key='hibernate', text_color=fg, background_color=bg, font=font_normal,
                  enable_events=True)],
        [Sg.Radio('Sleep computer when timer runs out', 'TIMER', default=sleep,
                  key='sleep', text_color=fg, background_color=bg, font=font_normal,
                  enable_events=True)],
        [Sg.Radio('Only stop playback', 'TIMER', default=do_nothing,
                  key='do_nothing', text_color=fg, background_color=bg, font=font_normal,
                  enable_events=True)],
        [Sg.Text('Enter minutes or HH:MM',  tooltip='press enter once done', text_color=fg, font=font_normal)],
        [Sg.Input(key='minutes', font=font_normal), Sg.Submit(font=font_normal)]]
    return layout


def create_playlist_selector(playlists):
    playlists = list(playlists.keys())
    layout = [
        [Sg.Combo(values=playlists, size=(41, 5), key='pl_selector', background_color=bg, font=font_normal,
                  enable_events=True, readonly=True, default_value=playlists[0] if playlists else None),
         Sg.Button(button_text='Edit', key='edit_pl', tooltip='Ctrl + E', enable_events=True, font=font_normal),
         Sg.Button(button_text='Delete', key='del_pl', tooltip='Ctrl + Del', enable_events=True, font=font_normal),
         Sg.Button(button_text='New', key='create_pl', tooltip='Ctrl + N', enable_events=True, font=font_normal)]]
    return layout


def create_playlist_editor(initial_folder, playlists, playlist_name=''):
    paths = playlists.get(playlist_name, [])
    songs = [f'{i+1}. {os.path.basename(path)}' for i, path in enumerate(paths)]
    # TODO: remove .mp3
    layout = [[
        Sg.Text('Playlist name', text_color=fg, font=font_normal),
        Sg.Input(playlist_name, key='playlist_name'),
        Sg.Submit('Save & quit', key='Save', tooltip='Ctrl + S', font=font_normal, pad=(('11px', '11px'), (0, 0))),
        Sg.Button('❌', key='Cancel', tooltip='Cancel (Esc)', font=font_normal, enable_events=True)],
        [Sg.Frame('', [[Sg.FilesBrowse('Add songs', key='Add songs', file_types=(('Audio Files', '*.mp3'),),
                                       pad=(('21px', 0), (5, 5)), initial_folder=initial_folder, font=font_normal,
                                       enable_events=True)],
                       [Sg.Button('Remove song', key='Remove song', tooltip='Ctrl + R', font=font_normal,
                                  enable_events=True)]],
                  background_color=bg, border_width=0),
         Sg.Listbox(songs, size=(41, 5), select_mode=Sg.SELECT_MODE_SINGLE, text_color=fg,
                    key='songs', background_color=bg, font=font_normal, enable_events=True),
         Sg.Frame('', [
             [Sg.Button('Move up', key='move_up', tooltip='Ctrl + U', font=font_normal, enable_events=True)],
             [Sg.Button('Move down ', key='move_down', tooltip='Ctrl + D', font=font_normal, enable_events=True)]
         ], background_color=bg, border_width=0)]]
    return layout


def create_play_url_window():
    layout = [[Sg.Text('Enter url.\nSupports: YouTube', text_color=fg, font=font_normal)],
              [Sg.Input(key='url', font=font_normal), Sg.Submit(font=font_normal)]]
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