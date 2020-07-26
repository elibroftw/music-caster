from helpers import *
import base64
from mutagen.easyid3 import EasyID3
from contextlib import suppress
import mutagen.id3
from helpers import get_metadata

print(find_chromecasts())
music_metadata = {}
timer = time.time()
print('is_already_running():', is_already_running(0), time.time() - timer)
print('get_mac():', get_mac())


def format_file(path: str):
    try:
        metadata = music_metadata[path]
        artist, title = metadata['artist'], metadata['title']
        if artist.startswith('Unknown') or title.startswith('Unknown'): raise KeyError
        return f'{artist} - {title}'
    except KeyError:
        if path.startswith('http'): return path
        base = os.path.basename(path)
        return os.path.splitext(base)[0]


def create_songs_list():
    # TODO: use metadata and song names or just one artist name
    """:returns the formatted song queue, and the selected value (currently playing)"""
    songs = []
    dq_len = len(done_queue)
    mq_start = len(next_queue) + 1
    selected_value = None
    # format: Index. Artists - Song Name
    for i, path in enumerate(done_queue):
        formatted_track = format_file(path)
        formatted_item = f'-{dq_len - i}. {formatted_track}'
        songs.append(formatted_item)
    if music_queue:
        formatted_track = format_file(music_queue[0])
        formatted_item = f' {0}. {formatted_track}'
        songs.append(formatted_item)
        selected_value = formatted_item
    for i, path in enumerate(next_queue):
        formatted_track = format_file(path)
        formatted_item = f' {i + 1}. {formatted_track}'
        songs.append(formatted_item)
    for i, path in enumerate(music_queue[1:]):
        formatted_track = format_file(path)
        formatted_item = f' {i + mq_start}. {formatted_track}'
        songs.append(formatted_item)
    return songs, selected_value


MUSIC_FILE_WITH_ALBUM_ART = r"C:\Users\maste\OneDrive\Music\6ixbuzz, Pressa, Houdini - Up & Down.mp3"
# MUSIC_FILE_WITHOUT_ALBUM_ART = r''
SAMPLE_MUSIC_FILES = [
    r"C:\Users\maste\OneDrive\Music\Dreamville, J. Cole, Lute, DaBaby - Under The Sun.mp3",
    r"C:\Users\maste\OneDrive\Music\deadmau5 - Jaded.mp3",
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

for file in SAMPLE_MUSIC_FILES:
    with suppress(mutagen.MutagenError):
        assert len(get_metadata(file)) == 3

file_path = MUSIC_FILE_WITH_ALBUM_ART
audio_info = mutagen.File(file_path).info
song_length = audio_info.length
_title, _artist, _album = get_metadata(file_path)
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
    music_meta_data[file_path] = {'artist': _artist, 'title': _title, 'album': _album, 'length': song_length,
                                  'art': f'{base64.b64encode(pict).decode("utf-8")}'}
else:
    music_meta_data[file_path] = {
        'artist': _artist, 'title': _title, 'album': _album, 'length': song_length}
music_meta_data[MUSIC_FILE_WITH_ALBUM_ART] = {'artist': _artist, 'title': _title, 'album': _album,
                                              'length': song_length,
                                              'art': f'{base64.b64encode(pict).decode("utf-8")}'}
metadata = music_meta_data[file_path]
artist, title = metadata['artist'].split(', ')[0], metadata['title']
now_playing_text = f'{artist} - {title}'
album_cover_data = metadata.get('art', None)
done_queue = SAMPLE_MUSIC_FILES[:3]
next_queue = SAMPLE_MUSIC_FILES[3:6]
music_queue = [file_path] + SAMPLE_MUSIC_FILES[6:]
settings = {  # default settings
    'previous_device': None, 'window_locations': {}, 'update_message': '', 'EXPERIMENTAL': True,
    'auto_update': False, 'run_on_startup': True, 'notifications': True, 'shuffle_playlists': True, 'repeat': False,
    'discord_rpc': False, 'save_window_positions': True, 'populate_queue_startup': False, 'save_queue_sessions': False,
    'default_file_handler': True, 'volume': 100, 'muted': False, 'volume_delta': 5, 'scrubbing_delta': 5,
    'accent_color': '#00bfff', 'text_color': '#d7d7d7', 'button_text_color': '#000000', 'background_color': '#121212',
    'flip_main_window': False, 'timer_shut_off_computer': False, 'timer_hibernate_computer': False,
    'timer_sleep_computer': False, 'music_directories': ['C:/test'], 'playlists': {'test': SAMPLE_MUSIC_FILES},
    'queues': {'done': [], 'music': [], 'next': []}}
bg = settings['background_color']
button_color = settings['button_text_color'], settings['accent_color']
Sg.SetOptions(button_color=button_color, scrollbar_color=bg, background_color=bg, element_background_color=bg,
              text_element_background_color=bg, text_color=settings['text_color'])
songs_list, selected_value = create_songs_list()
QR_CODE = create_qr_code(2001)
really_long_tile = 'extremely long convoluted title that tests max length'
other_main_layout = create_main(songs_list, selected_value, 'PLAYING', settings, 'TEST', QR_CODE, time.time() + 999,
                                really_long_tile, 'Martin')

main_window1 = Sg.Window('Music Caster - Main Window V2 Test', other_main_layout, background_color=bg, icon=WINDOW_ICON,
                         return_keyboard_events=True, use_default_focus=False)
for main_window in {main_window1}:
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

# Sg.Window('Main GUI', playing_layout)

# Settings GUI

# Timer GUI

# Playlists GUI

pl_editor_layout = create_playlist_editor(settings, 'test')
pl_editor_window = Sg.Window('Playlist Editor', pl_editor_layout, background_color=bg, return_keyboard_events=True)

pl_editor_window.Finalize()
pl_editor_window.TKroot.focus_force()
window_active = True
while window_active:
    pl_editor_event, pl_editor_values = pl_editor_window.Read()
    if pl_editor_event is None or pl_editor_event == 'Escape:27':
        pl_editor_window.Close()
        window_active = False
