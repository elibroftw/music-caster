from helpers import *
import base64
from mutagen.easyid3 import EasyID3
import mutagen.id3

# TODO: Add tests for all GUI's
# Main GUI
MUSIC_FILE_WITH_ALBUM_ART = r'C:\Users\maste\OneDrive\Music\deadmau5 - Faxing Berlin (Radio Edit).mp'
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
r"C:\Users\maste\OneDrive\Music\deadmau5 - So There I Was.mp3",
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

file_path = MUSIC_FILE_WITH_ALBUM_ART
audio_info = mutagen.File(file_path).info
song_length = audio_info.length
try:
    _title = EasyID3(file_path).get('title', ['Unknown'])[0]
    _artist = EasyID3(file_path).get('artist', ['Unknown'])
    _artist = ', '.join(_artist)
    album = EasyID3(file_path).get('album', 'Unknown')[0]
except mutagen.id3.ID3NoHeaderError:
    tags = mutagen.File(file_path)
    tags.add_tags()
    tags.save()
    _title = _artist = album = 'Unknown'
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
    music_meta_data[file_path] = {'artist': _artist, 'title': _title, 'album': album, 'length': song_length,
                                  'art': f'data:image/png;base64,{base64.b64encode(pict).decode("utf-8")}'}
else:
    music_meta_data[file_path] = {'artist': _artist, 'title': _title, 'album': album, 'length': song_length}
music_meta_data[MUSIC_FILE_WITH_ALBUM_ART] = {'artist': _artist, 'title': _title, 'album': album, 'length': song_length,
                                       'art': f'data:image/png;base64,{base64.b64encode(pict).decode("utf-8")}'}
metadata = music_meta_data[file_path]
artist, title = metadata['artist'].split(', ')[0], metadata['title']
new_playing_text = f'{artist} - {title}'
album_cover_data = metadata.get('album_cover_data', None)
done_queue = SAMPLE_MUSIC_FILES[:3]
next_queue = SAMPLE_MUSIC_FILES[3:6]
music_queue = [file_path] + SAMPLE_MUSIC_FILES[6:]
playing_layout = create_main_gui(music_queue, done_queue, next_queue, 'PLAYING',
                                 47, False, {}, new_playing_text,
                                 album_cover_data=album_cover_data)

not_playing_layout = create_main_gui(music_queue, done_queue, next_queue, 'NOT PLAYING',
                                     47, True, {})
# Sg.Window('Main GUI', playing_layout)

# Settings GUI

# Timer GUI

# Playlists GUI