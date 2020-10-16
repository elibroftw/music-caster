import time
from contextlib import suppress
import datetime
from functools import wraps
import io
import os
import platform
from math import floor
import winreg as wr
import base64
import pyqrcode
import PySimpleGUI as Sg
from PIL import Image
import socket
from urllib.parse import urlparse, parse_qs
from uuid import getnode
from b64_images import *
from subprocess import PIPE, DEVNULL, Popen
import re
import mutagen
from mutagen import MutagenError
from mutagen.aac import AAC
# noinspection PyProtectedMember
from mutagen.id3 import ID3NoHeaderError
# noinspection PyProtectedMember
from mutagen.mp3 import HeaderNotFoundError
from mutagen.easyid3 import EasyID3
from mutagen.easymp4 import EasyMP4
from wavinfo import WavInfoReader, WavInfoEOFError  # until mutagen supports .wav
# CONSTANTS
FONT_NORMAL = 'SourceSans', 11
FONT_SMALL = 'SourceSans', 10
FONT_TITLE = 'Helvetica', 14
FONT_ARTIST = 'Helvetica', 12
FONT_LINK = 'SourceSans', 11, 'underline'
LINK_COLOR = '#3ea6ff'


def timing(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        _start = time.time()
        result = f(*args, **kwargs)
        print(f'@timing {f.__name__} ELAPSED TIME:', time.time() - _start)
        return result
    return wrapper


class InvalidAudioFile(Exception): pass


def get_length(file_path):  # length in seconds
    # throws InvalidAudioFile if file is invalid
    try:
        if file_path.lower().endswith('.wav'):
            a = WavInfoReader(file_path)
            length = a.data.frame_count / a.fmt.sample_rate
        elif file_path.lower().endswith('.wma'):
            try:
                audio_info = mutagen.File(file_path).info
                length = audio_info.length
            except AttributeError:
                audio_info = AAC(file_path).info
                length = audio_info.length
        elif file_path.lower().endswith('.opus'):
            audio_info = mutagen.File(file_path).info
            length = audio_info.length
        else:
            audio_info = mutagen.File(file_path).info
            length = audio_info.length
        return length
    except (AttributeError, HeaderNotFoundError, MutagenError):
        raise InvalidAudioFile(f'{file_path} is an invalid audio file')


def natural_key(string):
    return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', string)]


def natural_key_file(string):
    string = os.path.splitext(os.path.basename(string))[0]
    return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', string)]


def valid_color_code(code):
    match = re.search(r'^#(?:[0-9a-fA-F]{3}){1,2}$', code)
    return match


def get_track_number(file_path: str):
    """ :raises KeyError, TypeError, MutagenError """
    return mutagen.File(file_path, easy=True)['tracknumber']


def get_metadata(file_path: str, as_dict=False):  # title, artist, album
    file_path = file_path.lower()
    title, artist, album = 'Unknown Title', 'Unknown Artist', 'Unknown Album'
    with suppress(ID3NoHeaderError, HeaderNotFoundError, AttributeError, WavInfoEOFError, StopIteration):
        if file_path.endswith('.mp3'):
            audio = EasyID3(file_path)
        elif file_path.endswith('.m4a') or file_path.endswith('.mp4'):
            audio = EasyMP4(file_path)
        elif file_path.endswith('.wav'):
            a = WavInfoReader(file_path).info.to_dict()
            audio = {'title': [a['title']], 'artist': [a['artist']], 'album': [a['product']]}
        elif file_path.endswith('.wma'):
            audio = {'title': [title], 'artist': [artist], 'album': [album]}
        else:
            audio = mutagen.File(file_path)
        title = audio.get('title', ['Unknown Title'])[0]
        album = audio.get('album', ['Unknown Album'])[0]
        with suppress(KeyError, TypeError): artist = ', '.join(audio['artist'])
    if as_dict:
        return {'title': title, 'artist': artist, 'album': album}
    if title is None: title = 'Unknown Title'
    if artist is None: artist = 'Unknown Artist'
    return title, artist, album


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


def create_qr_code(port, ipv4=None):
    ipv4 = ipv4 or get_ipv4()
    qr_code = pyqrcode.create(f'http://{ipv4}:{port}')
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
    return (file_path.endswith('.mp3') or file_path.endswith('.flac') or file_path.endswith('.m4a')
            or file_path.endswith('.mp4') or file_path.endswith('.aac') or file_path.endswith('.mpeg')
            or file_path.endswith('.ogg') or file_path.endswith('.opus')
            or file_path.endswith('.wma') or file_path.endswith('.wav'))


def parse_youtube_id(url):
    query = urlparse(url)
    if query.hostname == 'youtu.be': return query.path[1:]
    if query.hostname in {'www.youtube.com', 'youtube.com'}:
        if query.path == '/watch': return parse_qs(query.query)['v'][0]
        if query.path[:7] == '/embed/': return query.path.split('/')[2]
        if query.path[:3] == '/v/': return query.path.split('/')[2]
    return None  # invalid YouTube url


def get_repeat_img_et_tooltip(repeat_setting):
    if repeat_setting is None: return REPEAT_OFF_IMG, 'Repeat'
    elif repeat_setting: return REPEAT_ONE_IMG, "Don't repeat"
    else: return REPEAT_ALL_IMG, 'Repeat track'


def create_progress_bar_text(position, length) -> (str, str):  #
    """":return: time_elapsed_text, time_left_text"""
    position = floor(position)
    time_left = round(length) - position
    mins_elapsed, mins_left = floor(position / 60), time_left // 60
    secs_left = time_left % 60
    secs_elapsed = floor(position % 60)
    if secs_left < 10: secs_left = f'0{secs_left}'
    if secs_elapsed < 10: secs_elapsed = f'0{secs_elapsed}'
    return f'{mins_elapsed}:{secs_elapsed}', f'{mins_left}:{secs_left}'


def is_os_64bit():
    return platform.machine().endswith('64')


def get_output_device(pa, look_for):
    for i in range(pa.get_device_count()):
        device_info = pa.get_device_info_by_index(i)
        host_api_info = pa.get_host_api_info_by_index(device_info['hostApi'])
        if (host_api_info['name'] == 'Windows WASAPI' and device_info['maxOutputChannels'] > 0
                and device_info['name'] == look_for):
            channels = min(device_info['maxOutputChannels'], 2)
            return int(device_info['defaultSampleRate']), channels, device_info['index']
    raise RuntimeError('No Output Device Found')


def delete_sub_key(root, current_key):
    access = wr.KEY_ALL_ACCESS | wr.KEY_WOW64_64KEY if is_os_64bit() else wr.KEY_ALL_ACCESS
    with suppress(FileNotFoundError):
        with wr.OpenKeyEx(root, current_key, 0, access) as parent_key:
            info_key = wr.QueryInfoKey(parent_key)
            for x in range(info_key[0]):
                sub_key = wr.EnumKey(parent_key, 0)
                try: wr.DeleteKeyEx(parent_key, sub_key, access)
                except OSError: delete_sub_key(root, '\\'.join([current_key, sub_key]))
            wr.DeleteKeyEx(parent_key, '', access)


def add_reg_handlers(path_to_exe, add_folder_context=True):
    """ Register Music Caster as a program to open audio files and folders """
    # https://docs.microsoft.com/en-us/visualstudio/extensibility/registering-verbs-for-file-name-extensions?view=vs-2019
    path_to_exe = path_to_exe.replace('/', '\\')
    classes_path = 'SOFTWARE\\Classes\\'
    mc_file = 'MusicCaster_file'
    write_access = wr.KEY_WRITE | wr.KEY_WOW64_64KEY if is_os_64bit() else wr.KEY_WRITE
    read_access = wr.KEY_READ | wr.KEY_WOW64_64KEY if is_os_64bit() else wr.KEY_READ

    # create file type
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{classes_path}{mc_file}', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, 'Audio File')
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{classes_path}{mc_file}\\DefaultIcon', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, path_to_exe)  # define icon location

    # create open handler
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{classes_path}{mc_file}\\shell\\open', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, f'Play')
        wr.SetValueEx(key, 'MultiSelectModel', 0, wr.REG_SZ, 'Player')

    command_path = f'{classes_path}{mc_file}\\shell\\open\\command'
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, command_path, 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" "%1"')

    # create queue handler
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{classes_path}{mc_file}\\shell\\queue', 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, f'Queue in Music Caster')
        wr.SetValueEx(key, 'MultiSelectModel', 0, wr.REG_SZ, 'Player')
        # wr.SetValueEx(key, 'Icon', 0, wr.REG_SZ, path_to_exe)

    command_path = f'{classes_path}{mc_file}\\shell\\queue\\command'
    with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, command_path, 0, write_access) as key:
        wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" -q "%1"')

    # set file handlers
    for ext in {'mp3', 'flac', 'm4a', 'mp4', 'aac', 'ogg', 'opus', 'wma', 'wav', 'mpeg'}:
        key_path = f'{classes_path}.{ext}'
        try:  # check if key exists
            with wr.OpenKeyEx(wr.HKEY_CURRENT_USER, key_path, 0, read_access) as _: pass
        except (WindowsError, FileNotFoundError):
            # create key for extension if it does not exist with MC as the default program
            with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, key_path, 0, write_access) as key:
                # set as default program unless .mp4 because that's a video format
                if ext != 'mp4': wr.SetValueEx(key, None, 0, wr.REG_SZ, 'MusicCaster_file')
        # add to Open With (prompts user to set default program when they try playing a file)
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{key_path}\\OpenWithProgids', 0, write_access) as key:
            wr.SetValueEx(key, mc_file, 0, wr.REG_NONE, b'')

    play_folder_key_path = f'{classes_path}\\Directory\\shell\\MusicCasterPlayFolder'
    queue_folder_key_path = f'{classes_path}\\Directory\\shell\\MusicCasterQueueFolder'
    if add_folder_context:
        # set "open folder in Music Caster" command
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, play_folder_key_path, 0, write_access) as key:
            wr.SetValueEx(key, None, 0, wr.REG_SZ, 'Play with Music Caster')
            wr.SetValueEx(key, 'Icon', 0, wr.REG_SZ, path_to_exe)
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{play_folder_key_path}\\command', 0, write_access) as key:
            wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" "%1"')
        # set "queue folder in Music Caster" command

        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, queue_folder_key_path, 0, write_access) as key:
            wr.SetValueEx(key, None, 0, wr.REG_SZ, 'Queue in Music Caster')
            wr.SetValueEx(key, 'Icon', 0, wr.REG_SZ, path_to_exe)
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, f'{queue_folder_key_path}\\command', 0, write_access) as key:
            wr.SetValueEx(key, None, 0, wr.REG_SZ, f'"{path_to_exe}" -q "%1"')
    else:
        # remove commands for folders
        delete_sub_key(wr.HKEY_CURRENT_USER, play_folder_key_path)
        delete_sub_key(wr.HKEY_CURRENT_USER, queue_folder_key_path)


def get_default_output_device():
    """ returns the PyAudio formatted name of the default output device """
    read_access = wr.KEY_READ | wr.KEY_WOW64_64KEY if is_os_64bit() else wr.KEY_READ
    audio_path = r'SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render'
    audio_key = wr.OpenKeyEx(wr.HKEY_LOCAL_MACHINE, audio_path, 0, read_access)
    num_devices = wr.QueryInfoKey(audio_key)[0]
    active_last_used, active_device_name = -1, None
    for i in range(num_devices):
        device_key_path = f'{audio_path}\\{wr.EnumKey(audio_key, i)}'
        device_key = wr.OpenKeyEx(wr.HKEY_LOCAL_MACHINE, device_key_path, 0, read_access)
        if wr.QueryValueEx(device_key, 'DeviceState')[0] == 1:  # if enabled
            properties_path = f'{device_key_path}\\Properties'
            properties = wr.OpenKeyEx(wr.HKEY_LOCAL_MACHINE, properties_path, 0, read_access)
            device_name = wr.QueryValueEx(properties, '{b3f8fa53-0004-438e-9003-51a46e139bfc},6')[0]
            device_type = wr.QueryValueEx(properties, '{a45c254e-df1c-4efd-8020-67d146a850e0},2')[0]
            pa_name = f'{device_type} ({device_name})'  # name shown in PyAudio
            last_used = wr.QueryValueEx(device_key, 'Level:0')[0]
            if last_used > active_last_used:  # the bigger the number, the more recent it was used
                active_last_used = last_used
                active_device_name = pa_name
    return active_device_name


def resize_img(base64data, bg, new_size=(255, 255)) -> bytes:
    """ Resize and return b64 img data to new_size (w, h). (use .decode() on return statement for str) """
    if type(base64data) == str: base64data = base64data.encode()
    img_data = io.BytesIO(base64.b64decode(base64data))
    art_img: Image = Image.open(img_data)
    w, h = art_img.size
    if w == h:
        img = art_img.resize(new_size, Image.ANTIALIAS)
    else:
        ratio = h / w if w > h else w / h
        to_change = 1 if w > h else 0
        ratio_size = list(new_size)
        ratio_size[to_change] = round(new_size[to_change] * ratio)
        art_img = art_img.resize(ratio_size, Image.ANTIALIAS)
        paste_width = (new_size[0] - ratio_size[0]) // 2
        paste_height = (new_size[1] - ratio_size[1]) // 2
        img = Image.new('RGB', new_size, color=bg)
        img.paste(art_img, (paste_width, paste_height))
    data = io.BytesIO()
    img.save(data, format='png', quality=95)
    return base64.b64encode(data.getvalue())


# GUI LAYOUTS
def get_music_controls(settings, playing_status):
    # TODO: stop button
    accent_color, bg = settings['theme']['accent'], settings['theme']['background']
    img_button = {'border_width': 0, 'button_color': (bg, bg)}
    is_muted = settings['muted']
    volume = 0 if is_muted else settings['volume']
    v_slider_img = VOLUME_MUTED_IMG if is_muted else VOLUME_IMG
    pause_resume_img = PAUSE_BUTTON_IMG if playing_status == 'PLAYING' else PLAY_BUTTON_IMG
    repeat_img, repeat_tooltip = get_repeat_img_et_tooltip(settings['repeat'])
    repeat_button = {**img_button, 'tooltip': repeat_tooltip, 'metadata': repeat_tooltip}
    return [Sg.Button(key='prev', image_data=PREVIOUS_BUTTON_IMG, **img_button, tooltip='previous track'),
            Sg.Button(key='pause/resume', image_data=pause_resume_img, **img_button, metadata=playing_status),
            Sg.Button(key='next', image_data=NEXT_BUTTON_IMG, **img_button, tooltip='next track'),
            Sg.Button(key='repeat', image_data=repeat_img, **repeat_button),
            Sg.Button(key='mute', image_data=v_slider_img, **img_button, tooltip='mute' if is_muted else 'unmute'),
            Sg.Slider((0, 100), default_value=volume, orientation='h', key='volume_slider',
                      disable_number_display=True, enable_events=True, background_color=accent_color,
                      text_color='#000000', size=(10, 10), tooltip='Scroll mousewheel')]


def get_progress_layout(settings, track_position, track_length, playing_status):
    time_elapsed, time_left = create_progress_bar_text(track_position, track_length)
    text_size = (5, 1)
    bot_pad = (settings['vertical_gui'] and not settings['show_album_art']) * 30
    accent_color, bg = settings['theme']['accent'], settings['theme']['background']
    mini_mode = settings['mini_mode']
    time_elapsed_pad = ((0, 2), (5, 0)) if mini_mode else ((0, 5), (10, bot_pad))
    time_left_pad = ((2, 0), (5, 0)) if mini_mode else ((5, 0), (10, bot_pad))
    progress_layout = [Sg.Text(time_elapsed, key='time_elapsed', pad=time_elapsed_pad, justification='right',
                               size=text_size, font=FONT_NORMAL),
                       Sg.Slider(range=(0, track_length), default_value=track_position,
                                 orientation='h', size=(17 if mini_mode else 30, 10), key='progress_bar',
                                 enable_events=True, relief=Sg.RELIEF_FLAT, background_color=accent_color,
                                 disable_number_display=True, disabled=playing_status == 'NOT PLAYING',
                                 tooltip='Scroll mousewheel',
                                 pad=((7, 7), (5, 0)) if mini_mode else ((8, 8), (10, bot_pad))),
                       Sg.Text(time_left, key='time_left', pad=time_left_pad, justification='left',
                               size=text_size, font=FONT_NORMAL)]
    if mini_mode:
        progress_layout.append(Sg.Button(key='mini_mode', image_data=RESTORE_WINDOW, size=(1, 1), enable_events=True,
                                         border_width=0, button_color=(bg, bg), tooltip='restore window', pad=(0, 0)))
    return progress_layout


def create_mini_mode(playing_status, settings, title, artist, album_art_data, track_length, track_position):
    # album_art_data is 125 x 125
    album_art = Sg.Col([[Sg.Image(data=album_art_data, key='album_art', pad=(0, 0))]],
                       element_justification='left', pad=(0, 0))
    music_controls = get_music_controls(settings, playing_status)
    progress_bar_layout = get_progress_layout(settings, track_position, track_length, playing_status)
    right_side = Sg.Col([
        [Sg.Text(title, font=FONT_TITLE, key='title', pad=(0, 0), size=(26, 0), justification='right')],
        [Sg.Text(artist, font=FONT_ARTIST, key='artist', pad=(0, 0), size=(26, 0), justification='right')],
        music_controls, progress_bar_layout], element_justification='right', pad=(0, 0))
    return [[album_art, right_side] if settings['show_album_art'] else [right_side]]


def create_main(tracks, listbox_selected, playing_status, settings, version, timer, title='Nothing Playing',
                artist='', qr_code=None, album_art_data: str = None, track_length=0, track_position=0):
    if settings['mini_mode']:
        return create_mini_mode(playing_status, settings, title, artist, album_art_data, track_length, track_position)
    accent_color, fg, bg = settings['theme']['accent'], settings['theme']['text'], settings['theme']['background']
    img_button = {'border_width': 0, 'button_color': (bg, bg)}
    music_controls = get_music_controls(settings, playing_status)
    progress_bar_layout = get_progress_layout(settings, track_position, track_length, playing_status)
    if not settings['show_album_art']: album_art_data = None
    title_top_pad = 10 + (album_art_data is None) * 100 - (settings['vertical_gui'] and album_art_data is None) * 30
    # 10, 110, or 0
    artist_bot_pad = 10 + (album_art_data is None) * 20 - 20 * (album_art_data is None and settings['vertical_gui'])
    # 10 or 30
    left_pad = settings['vertical_gui'] * 95 + 5
    main_part = Sg.Column([
        [Sg.Image(data=album_art_data, pad=(0, 0), size=(255, 255), key='album_art')] if album_art_data else [],
        [Sg.Text(title, font=FONT_TITLE, key='title', pad=((0, 0), (title_top_pad, 10)),
                 size=(26, 0), justification='center')],
        [Sg.Text(artist, font=FONT_ARTIST, key='artist', pad=((0, 0), (0, artist_bot_pad)),
                 size=(26, 0), justification='center')],
        music_controls, progress_bar_layout], element_justification='center', pad=((left_pad, 5), (5, 5)))
    # tabs side is for music queue, queue controls, and later, the music library
    # tab 1 is the queue, tab 2 will be the library
    file_options = ['Play File(s)', 'Play File(s) Next', 'Queue File(s)']
    folder_opts = ['Play Folder', 'Play Folder Next', 'Queue Folder']  # TODO: queue folders
    # TODO: Move to controls tab
    queue_controls = [
        Sg.Column([[Sg.Combo(file_options, default_value='Play File(s)', key='file_option', size=(14, None),
                             font=FONT_NORMAL, enable_events=True, pad=(5, (5, 0)))],
                   [Sg.Combo(folder_opts, default_value='Play Folder', key='folder_option', size=(14, None),
                             font=FONT_NORMAL, enable_events=True, pad=(5, (10, 0)))]]),
        Sg.Column([[Sg.Button('Play File(s)', font=FONT_NORMAL, key='file_action', enable_events=True, size=(13, 1))],
                   [Sg.Button('Play Folder', font=FONT_NORMAL, k='folder_action', enable_events=True, size=(13, 1))]]),
        Sg.Column([[Sg.Button('URL', font=FONT_NORMAL, key='url_actions', size=(5, 1), enable_events=True)],
                   [Sg.Button('Queue All', font=FONT_NORMAL, key='queue_all', size=(9, 1), enable_events=True)]])
    ]
    listbox_controls = [
        [Sg.Button(key='mini_mode', image_data=RESTORE_WINDOW, **img_button, tooltip='Launch mini mode')],
        [Sg.Button(key='clear_queue', image_data=CLEAR_QUEUE, **img_button, tooltip='Clear the queue')],
        [Sg.Button(key='save_queue', image_data=SAVE_QUEUE, **img_button, tooltip='Save queue to playlist')],
        [Sg.Button(key='locate_file', image_data=LOCATE_FILE, **img_button, tooltip='Locate file in explorer')],
        [Sg.Button('▲', key='move_up', tooltip='Move track up', size=(3, 1))],
        [Sg.Button('❌', key='remove', tooltip='Remove track', size=(3, 1))],
        [Sg.Button('▼', key='move_down', tooltip='Move track down', size=(3, 1))]]
    listbox_height = 14 + (album_art_data is not None) * 4  # 11 or 21
    queue_tab_layout = [queue_controls, [
        # TODO: add right click menus for list boxes
        Sg.Listbox(tracks, default_values=listbox_selected, size=(64, listbox_height),
                   select_mode=Sg.SELECT_MODE_SINGLE,
                   text_color=fg, key='queue', font=FONT_NORMAL,
                   bind_return_key=True),
        Sg.Column(listbox_controls, pad=(0, 5))]]
    queue_tab = Sg.Tab('Queue', queue_tab_layout, key='tab_queue', background_color=bg)
    timer_layout = create_timer(settings, timer)
    timer_tab = Sg.Tab('Timer', timer_layout, key='tab_timer', background_color=bg)
    settings_layout = create_settings(version, settings, qr_code)
    settings_tab = Sg.Tab('Settings', settings_layout, key='tab_settings')
    playlists_layout = create_playlists_tab(settings)
    playlists_tab = Sg.Tab('Playlists', playlists_layout, key='tab_playlists')
    # TODO: library_tab = Sg.Tab()
    tabs_part = Sg.TabGroup([[queue_tab, timer_tab, playlists_tab, settings_tab]],
                            title_color=fg, border_width=0, key='tab_group',
                            selected_background_color=accent_color, enable_events=True,
                            tab_background_color=bg, selected_title_color=bg, background_color=bg)
    if settings['vertical_gui']: return [[main_part], [tabs_part]]
    return [[main_part, tabs_part]] if settings['flip_main_window'] else [[tabs_part, main_part]]


def create_checkbox(name, key, settings, on_left=False):
    bg = settings['theme']['background']
    size = (20, 5) if on_left else (23, 5)
    checkbox = {'background_color': bg, 'font': FONT_NORMAL, 'enable_events': True, 'pad': ((0, 5), (5, 5))}
    return Sg.Checkbox(name, default=settings[key], key=key, **checkbox, size=size)


def create_playlists_tab(settings):
    fg, bg = settings['theme']['text'], settings['theme']['background']
    playlists = settings['playlists']
    playlists_names = list(playlists.keys())
    default_pl_name = playlists_names[0] if playlists_names else None
    playlist_selector = [
        [Sg.Button('New', key='new_pl', tooltip='Ctrl + N', size=(5, 1), enable_events=True, font=FONT_NORMAL),
         Sg.Button('Delete', key='del_pl', tooltip='Ctrl + Del ', enable_events=True, font=FONT_NORMAL),
         Sg.Combo(values=playlists_names, size=(38, 5), key='playlist_combo', font=FONT_NORMAL,
                  enable_events=True, default_value=default_pl_name),
         Sg.Button('Play', key='play_pl', pad=((12, 5), None), disabled=default_pl_name is None,
                   enable_events=True, font=FONT_NORMAL),
         Sg.Button('Queue', key='queue_pl', disabled=default_pl_name is None,
                   enable_events=True, font=FONT_NORMAL)]]
    playlist_name = playlists_names[0] if playlists_names else ''
    paths = playlists.get(playlist_name, [])
    tracks = [f'{i + 1}. {os.path.splitext(os.path.basename(path))[0]}' for i, path in enumerate(paths)]
    move_up_params = {'size': (11, 1), 'disabled': True, 'font': FONT_NORMAL, 'enable_events': True}
    move_down_params = {'size': (11, 1), 'disabled': True, 'font': FONT_NORMAL, 'enable_events': True}
    url_input = [Sg.Input('', key='pl_url_input', size=(13, 1), font=FONT_NORMAL, enable_events=True)]
    add_url = [Sg.Button('Add URL', key='pl_add_url', size=(12, 1), disabled=True,
                         font=FONT_NORMAL, enable_events=True)]
    add_tracks = [Sg.Button('Add tracks', key='pl_add_tracks', size=(12, 1), font=FONT_NORMAL, enable_events=True)]
    layout = [[Sg.Column(playlist_selector, pad=(5, (40, 20)))],
              [Sg.Text('Playlist name', font=FONT_NORMAL, size=(13, 1), justification='center', pad=(5, (5, 10))),
               Sg.Input(playlist_name, key='playlist_name', size=(39, 1), font=FONT_NORMAL, enable_events=True,
                        pad=(5, (5, 10))),

               Sg.Submit('Save', key='pl_save', tooltip='Ctrl + S', font=FONT_NORMAL, disabled=playlist_name == '',
                         size=(6, 1), pad=((14, 5), (5, 10)))],
              [Sg.Frame('', [url_input, add_url, add_tracks,
                             [Sg.Button('Remove item(s)', key='pl_rm_items', tooltip='Ctrl + R', font=FONT_NORMAL,
                                        enable_events=True, size=(12, 1))]],
                        background_color=bg, border_width=0),
               Sg.Listbox(tracks, size=(37, 10), select_mode=Sg.SELECT_MODE_MULTIPLE, text_color=fg,
                          key='pl_tracks', background_color=bg, font=FONT_NORMAL, enable_events=True),
               Sg.Frame('', [[Sg.Button('Move up', **move_up_params, key='pl_move_up')],
                             [Sg.Button('Move down', **move_down_params, key='pl_move_down')]],
                        background_color=bg, border_width=0)]]
    return layout


def create_settings(version, settings, qr_code):
    # TODO: reorganize
    fg, bg = settings['theme']['text'], settings['theme']['background']
    checkbox_col = Sg.Column([
        [create_checkbox('Auto Update', 'auto_update', settings, True),
         create_checkbox('Discord Presence', 'discord_rpc', settings)],
        [create_checkbox('Notifications', 'notifications', settings, True),
         create_checkbox('Run on Startup', 'run_on_startup', settings)],
        [create_checkbox('Save Window Positions', 'save_window_positions', settings, True),
         create_checkbox('Shuffle Playlists', 'shuffle_playlists', settings)],
        [create_checkbox('Populate Queue on Startup', 'populate_queue_startup', settings, True),
         create_checkbox('Persistent Queue', 'save_queue_sessions', settings)],
        [create_checkbox('Left-Side Music Controls', 'flip_main_window', settings, True),
         create_checkbox('Vertical Main GUI', 'vertical_gui', settings)],
        [create_checkbox('Show Album Art', 'show_album_art', settings, True),
         create_checkbox('Mini Mode on Top', 'mini_on_top', settings)],
        [create_checkbox('Use cover.* for album art', 'folder_cover_override', settings, True),
         create_checkbox('Folder context menu', 'folder_context_menu', settings)],
        [create_checkbox('Show track number', 'show_track_number', settings, True)],
    ], pad=((0, 0), (5, 0)))
    qr_code__params = {'tooltip': 'Web GUI QR Code (click or scan)', 'border_width': 0, 'button_color': (bg, bg)}
    qr_code_col = Sg.Column([[Sg.Button(key='web_gui', image_data=qr_code, **qr_code__params)]], pad=(0, 0))
    email_params = {'text_color': LINK_COLOR, 'font': FONT_LINK, 'tooltip': 'Send me an email'}
    add_music_folder = {'button_text': 'Add Music Folder', 'font': FONT_NORMAL, 'enable_events': True, 'size': (15, 1)}
    open_settings_file = {'font': FONT_NORMAL, 'enable_events': True, 'size': (15, 1)}
    layout = [
        [Sg.Text(f'Music Caster Version {version} by Elijah Lopez', font=FONT_NORMAL),
         Sg.Text('elijahllopezz@gmail.com', **email_params, click_submits=True, key='email')],
        [checkbox_col, qr_code_col] if qr_code else [checkbox_col],
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
    fg, bg = settings['theme']['text'], settings['theme']['background']
    do_nothing = not (shut_off or hibernate or sleep)
    timer_date = datetime.datetime.fromtimestamp(timer)
    timer_date = timer_date.strftime('%#I:%M %p')
    timer_text = f'Timer set for {timer_date}' if timer else 'No Timer Set'
    # wait for last track to finish setting
    cancel_button = Sg.Button('Cancel Timer', key='cancel_timer', visible=timer != 0)
    defaults = {'text_color': fg, 'background_color': bg, 'font': FONT_NORMAL, 'enable_events': True}
    layout = [
        [Sg.Radio('Shut off computer when timer runs out', 'TIMER', default=shut_off, key='shut_off', **defaults)],
        [Sg.Radio('Hibernate computer when timer runs out', 'TIMER', default=hibernate, key='hibernate', **defaults)],
        [Sg.Radio('Sleep computer when timer runs out', 'TIMER', default=sleep, key='sleep', **defaults)],
        [Sg.Radio('Only stop playback', 'TIMER', default=do_nothing, key='other_daemon_actions', **defaults)],
        [Sg.Text('Enter minutes or HH:MM', tooltip='Press enter once done', font=FONT_NORMAL),
         Sg.Input(key='minutes', font=FONT_NORMAL, size=(11, 1)),
         Sg.Button('Submit', font=FONT_NORMAL, key='timer_submit')],
        [Sg.Text('Invalid Input (enter minutes or HH:MM)', font=FONT_NORMAL, visible=False, key='timer_error')],
        [Sg.Text(timer_text, font=FONT_NORMAL, key='timer_text', size=(18, 1)), cancel_button]
    ]
    return [[Sg.Column(layout, pad=(0, (50, 0)), justification='center')]]


def create_play_url(combo_value='Play Immediately', default_text=''):
    # TODO: integrate into main window
    layout = [[Sg.Text('Enter URL (YouTube or *.ext src)', font=FONT_NORMAL)],
              [Sg.Radio('Play Immediately', 'url_option', combo_value == 'Play Immediately', key='play_immediately'),
              Sg.Radio('Queue', 'url_option', combo_value == 'Queue', key='queue'),
              Sg.Radio('Play Next', 'url_option', combo_value == 'Play Next', key='play_next')],
              [Sg.Input(key='url', font=FONT_NORMAL, default_text=default_text), Sg.Submit(font=FONT_NORMAL)]]
    return layout
