import pyaudio

from helpers import *
import base64
from pathlib import Path
from contextlib import suppress
import mutagen.id3
from helpers import get_metadata
import argparse


parser = argparse.ArgumentParser(description='Music Caster Test Harness')
parser.add_argument('--pyaudio', '-p', default=False,
                    action='store_true', help='test pyaudio')
parser.add_argument('--helpers', '-f', default=False,
                    action='store_true', help='test helper functions')
args = parser.parse_args()

if args.pyaudio:
    p = pyaudio.PyAudio()
    print('Default Audio Device:', get_default_output_device())
    print('Sleeping for 1 second...')
    time.sleep(1)

with suppress(InvalidAudioFile):
    # should raise an error but not crash program
    get_length('audio_player.py')
music_metadata = {}
timer = time.time()

if args.helpers:
    print('is_already_running():', is_already_running(threshold=1), f'({round(time.time() - timer, 2)}s)')
    print('get_mac():', get_mac())


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


def get_uri_info(uri):
    # get metadata from all_track and resort to url_metadata if not found in music_metadata
    #   if file/url is not in all_track. e.g. links
    uri = uri.replace('\\', '/')
    try:
        return music_metadata[uri]
    except KeyError:
        metadata = get_metadata_wrapped(uri)
        with suppress(InvalidAudioFile):
            length = get_length(uri)
            metadata['length'] = length
        music_metadata[uri] = metadata
        return metadata


def format_file(uri: str):
    try:
        metadata = get_uri_info(uri)
        title, artist = metadata['title'], metadata['artist']
        if artist.startswith('Unknown') or title.startswith('Unknown'):
            raise KeyError
        return f'{artist} - {title}'
    except (TypeError, KeyError):  # show something useful instead of Unknown - Unknown
        if uri.startswith('http'):
            return uri
        base = os.path.basename(uri)
        return os.path.splitext(base)[0]


def create_track_list():
    """:returns the formatted tracks queue, and the selected value (currently playing)"""
    tracks = []
    dq_len = len(done_queue)
    mq_start = len(next_queue) + 1
    selected_value = None
    # format: Index. Artists - Title
    for i, uri in enumerate(done_queue):
        formatted_track = format_file(uri)
        formatted_item = f'-{dq_len - i}. {formatted_track}'
        tracks.append(formatted_item)
    if music_queue:
        formatted_track = format_file(music_queue[0])
        formatted_item = f' {0}. {formatted_track}'
        tracks.append(formatted_item)
        selected_value = formatted_item
    for i, uri in enumerate(next_queue):
        formatted_track = format_file(uri)
        formatted_item = f' {i + 1}. {formatted_track}'
        tracks.append(formatted_item)
    for i, uri in enumerate(music_queue[1:]):
        formatted_track = format_file(uri)
        formatted_item = f' {i + mq_start}. {formatted_track}'
        tracks.append(formatted_item)
    return tracks, selected_value


MUSIC_FILE_WITH_ALBUM_ART = r"C:\Users\maste\OneDrive\Music\6ixbuzz, Pressa, Houdini - Up & Down.mp3"
# MUSIC_FILE_WITHOUT_ALBUM_ART = r''
SAMPLE_MUSIC_FILES = [
    r"C:\Users\maste\OneDrive\Music\deadmau5 - My Pet Coelacanth.mp3",
    r"C:\Users\maste\OneDrive\Music\deadmau5 - Not Exactly.mp3",
    r"C:\Users\maste\OneDrive\Music\deadmau5 - Phantoms Can't Hang.mp3",
    r"C:\Users\maste\OneDrive\Music\deadmau5 - Rio.mp3",
    r"C:\Users\maste\OneDrive\Music\deadmau5 - SATRN.mp3",
    r"C:\Users\maste\OneDrive\Music\deadmau5 - Saved.mp3",
    r"C:\Users\maste\OneDrive\Music\deadmau5 - Slip.mp3",
    r"C:\Users\maste\OneDrive\Music\deadmau5 - So There I Was.mp3",  # DNE
    r"C:\Users\maste\OneDrive\Music\deadmau5 - Sofi Needs a Ladder.mp3",
    r"C:\Users\maste\OneDrive\Music\deadmau5 - Some Kind of Blue.mp3",
    r"C:\Users\maste\OneDrive\Music\deadmau5 - Sometimes Things Get, Whatever.mp3",
    r"C:\Users\maste\OneDrive\Music\deadmau5 - Three Pound Chicken Wing.mp3",
    r"C:\Users\maste\OneDrive\Music\deadmau5 & Kaskade - I Remember.mp3",
    r"C:\Users\maste\OneDrive\Music\deadmau5, Grabbitz - Let Go.mp3",
    r"C:\Users\maste\OneDrive\Music\Diplo, Trippie Redd - Wish.mp3",
    r"C:\Users\maste\OneDrive\Music\Dirty South, Alesso, Ruben Haze - City Of Dreams.mp3",
    r"C:\Users\maste\OneDrive\Music\Dogzilla - Without You (John O'Callaghan Extended Remix).mp3",
    r"C:\Users\maste\OneDrive\Music\Dogzilla - Without You (Ronald van Gelderen Extended Remix).mp3",
    r"C:\Users\maste\OneDrive\Music\Dogzilla - Without You (Will Atkinson Remix).mp3",
    r"C:\Users\maste\OneDrive\Music\Drake - Hold On, We're Going Home.mp3",
    r"C:\Users\maste\OneDrive\Music\Drake - Over (Ayobi Remix).mp3",
    r"C:\Users\maste\OneDrive\Music\Drake - Passionfruit.mp3"]

# test get_track_number
double_digit_track_num = r"C:\Users\maste\OneDrive\Music\Armin van Buuren - Mirage (Assaf Remix).mp3"
for sample in SAMPLE_MUSIC_FILES + [double_digit_track_num]:
    with suppress(MutagenError, KeyError):
        assert int(get_track_number(sample))

all_tracks = {}
all_tracks_sorted = []
for file_path in SAMPLE_MUSIC_FILES:
    with suppress(mutagen.MutagenError):
        assert len(get_metadata(file_path)) == 4
    file_path = file_path.replace('\\', '/')
    if valid_music_file(file_path) and os.path.exists(file_path):
        with suppress(HeaderNotFoundError):
            metadata = get_metadata_wrapped(file_path)
            with suppress(KeyError, TypeError, MutagenError):
                track_number = get_track_number(file_path)
                metadata['track_number'] = track_number
            all_tracks[file_path] = metadata
            all_tracks_sorted = sorted(all_tracks.items(), key=lambda item: item[1]['sort_key'].lower())

file_path = MUSIC_FILE_WITH_ALBUM_ART
audio_info = mutagen.File(file_path).info
track_length = audio_info.length
pict = None
try:
    tags = mutagen.id3.ID3(file_path)
except mutagen.id3.ID3NoHeaderError:
    tags = mutagen.File(file_path)
    tags.add_tags()
    tags.save()
for tag in tags.keys():
    if 'APIC' in tag:
        pict = tags[tag].data
        break
music_meta_data = {}

if pict:
    music_meta_data[file_path] = {**get_metadata(file_path), 'length': track_length,
                                  'art': f'{base64.b64encode(pict).decode("utf-8")}'}
else:
    music_meta_data[file_path] = {**get_metadata(file_path), 'length': track_length}
music_meta_data[MUSIC_FILE_WITH_ALBUM_ART] = {**get_metadata(file_path), 'length': track_length,
                                              'art': f'{base64.b64encode(pict).decode("utf-8")}'}
metadata = music_meta_data[file_path]
artist, title = metadata['artist'].split(', ')[0], metadata['title']
now_playing_text = f'{artist} - {title}'
album_art_data = metadata.get('art', None)
done_queue = SAMPLE_MUSIC_FILES[:3]
next_queue = SAMPLE_MUSIC_FILES[3:6]
music_queue = [file_path] + SAMPLE_MUSIC_FILES[6:]
home_music_dir = f'{Path.home()}/Music'
DEFAULT_THEME = {'accent': '#00bfff', 'alternate_background': '#222222',
                 'background': '#121212', 'text': '#d7d7d7'}
settings = {
    'previous_device': None, 'window_locations': {}, 'update_message': '', 'EXPERIMENTAL': True,
    'auto_update': True, 'run_on_startup': True, 'notifications': True, 'shuffle_playlists': True, 'repeat': False,
    'discord_rpc': False, 'save_window_positions': True, 'populate_queue_startup': False, 'save_queue_sessions': False,
    'volume': 100, 'muted': False, 'volume_delta': 5, 'scrubbing_delta': 5, 'flip_main_window': False,
    'show_track_number': False, 'folder_cover_override': False, 'show_album_art': True, 'folder_context_menu': True,
    'vertical_gui': False, 'mini_mode': False, 'mini_on_top': True, 'update_check_hours': 1,
    'timer_shut_off_computer': False, 'timer_hibernate_computer': False, 'timer_sleep_computer': False,
    'theme': DEFAULT_THEME.copy(), 'track_format': '&artist - &title', 'reversed_play_next': False,
    'music_directories': [home_music_dir], 'playlists': {'sample': SAMPLE_MUSIC_FILES},
    'queues': {'done': [], 'music': [], 'next': []}}

theme = settings['theme']
Sg.SetOptions(text_color=theme['text'], input_text_color=theme['text'], element_text_color=theme['text'],
              background_color=theme['background'], text_element_background_color=theme['background'],
              element_background_color=theme['background'], scrollbar_color=theme['background'],
              input_elements_background_color=theme['background'], progress_meter_color=theme['accent'],
              button_color=(theme['background'], theme['accent']),
              border_width=1, slider_border_width=1, progress_meter_border_depth=0)

tracks_list, selected_value = create_track_list()
qr_code = create_qr_code(2001)
really_long_tile = 'extremely long convoluted title that tests max length'

# album cover test
mini_mode = False
size = (125, 125) if mini_mode else (255, 255)
settings['mini_mode'] = mini_mode
default_album_art = resize_img(
    DEFAULT_ART, settings['theme']['background'], size).decode()

main_attrs = {'title': really_long_tile, 'artist': 'Artist Name',
              'album_art_data': default_album_art, 'qr_code': qr_code}

other_main_layout = create_main(tracks_list, selected_value, 'PLAYING', settings, 'TEST', time.time() + 999,
                                all_tracks_sorted, **main_attrs)
main_window1 = Sg.Window('Music Caster - Main Window Test', other_main_layout, grab_anywhere=mini_mode,
                         icon=WINDOW_ICON, return_keyboard_events=True, no_titlebar=mini_mode,
                         use_default_focus=False, margins=(0, 0) if mini_mode else (None, None))
mini_mode = settings['mini_mode'] = not mini_mode
size = (125, 125) if mini_mode else (255, 255)
default_album_art = resize_img(
    DEFAULT_ART, settings['theme']['background'], size).decode()
main_attrs = {'title': really_long_tile, 'artist': 'Artist Name',
              'album_art_data': default_album_art, 'qr_code': qr_code}
other_main_layout = create_main(tracks_list, selected_value, 'PLAYING', settings, 'TEST', time.time() + 999,
                                all_tracks_sorted, **main_attrs)
mini_window = Sg.Window('Music Caster - Main Window Test', other_main_layout, grab_anywhere=mini_mode,
                        icon=WINDOW_ICON, return_keyboard_events=True, no_titlebar=mini_mode,
                        use_default_focus=False, margins=(0, 0) if mini_mode else (None, None))
for main_window in {main_window1, mini_window}:
    main_window.Finalize()
    main_window.TKroot.focus_force()
    window_active = True
    while window_active:
        main_event, main_values = main_window.Read()
        if main_event in {None, 'q', 'Q'} or main_event == 'Escape:27':
            main_window.Close()
            window_active = False
        if main_event == 'repeat':
            if settings['repeat'] is None:
                repeat_setting = False  # Repeat All
            elif settings['repeat']:
                repeat_setting = None  # Repeat OFF
            else:
                repeat_setting = True  # Repeat One
            settings['repeat'] = repeat_setting
            repeat_img, new_tooltip = get_repeat_img_et_tooltip(repeat_setting)
            main_window['repeat'].Update(image_data=repeat_img)
            main_window['repeat'].SetTooltip(new_tooltip)

# Settings GUI

# Timer GUI

# URL GUI
play_url_window = Sg.Window(
    'Play URL', create_play_url(), finalize=True, return_keyboard_events=True)
play_url_window.TKroot.focus_force()
play_url_window.Read(timeout=1500)  # 1.5 second timeout
play_url_window.Close()
