from base64 import b64decode
from contextlib import suppress
import io
from itertools import chain
import os
import platform
from pathlib import Path
import time

from mutagen._util import MutagenError
from PIL import Image
import pytest

from b64_images import DEFAULT_ART
from meta import COVER_MINI, COVER_NORMAL, VERSION
from shared import get_running_processes, is_already_running
from test_cases.ipconfig import IPCONFIG_ELIBROFTW, IPCONFIG_ERICCHAN1989, IPCONFIG_ERICCHAN1989_ALL
from utils import (
    IPV4_GENERAL_PATTERN,
    IPV4_WIFI_PATTERN,
    REPEAT_ALL_IMG,
    REPEAT_OFF_IMG,
    REPEAT_ONE_IMG,
    InvalidAudioFile,
    State,
    SystemAudioRecorder,
    Unknown,
    better_shuffle,
    create_progress_bar_texts,
    custom_art,
    export_playlist,
    clean_ipconfig,
    fix_path,
    get_album_art,
    get_audio_length,
    get_deezer_tracks,
    get_default_output_device,
    get_display_lang,
    get_file_name,
    get_first_artist,
    get_ipv4,
    get_ipv6,
    get_lang_pack,
    get_languages,
    get_latest_release,
    get_mac,
    get_metadata,
    get_proxy,
    get_spotify_tracks,
    get_translation,
    get_youtube_comments,
    get_yt_id,
    natural_key_file,
    parse_m3u,
    repeat_img_tooltip,
    resize_img,
    t,
    valid_audio_file,
    valid_color_code,
    ydl_extract_info,
)

MUSIC_FILE_WITH_ALBUM_ART = (
    r'C:\Users\maste\OneDrive\Music\6ixbuzz, Pressa, Houdini - Up & Down.mp3'
)
TEST_MUSIC_FILES = [
    r'C:\Users\maste\OneDrive\Music\deadmau5 - My Pet Coelacanth.mp3',
    r'C:\Users\maste\OneDrive\Music\deadmau5 - Not Exactly.mp3',
    r"C:\Users\maste\OneDrive\Music\deadmau5 - Phantoms Can't Hang.mp3",
    r'C:\Users\maste\OneDrive\Music\deadmau5 - Rio.mp3',
    r'C:\Users\maste\OneDrive\Music\deadmau5 - SATRN.mp3',
    r'C:\Users\maste\OneDrive\Music\deadmau5 - Saved.mp3',
    r'C:\Users\maste\OneDrive\Music\deadmau5 - Slip.mp3',
    r'C:\Users\maste\OneDrive\Music\deadmau5 - So There I Was.mp3',  # DNE
    r'C:\Users\maste\OneDrive\Music\deadmau5 - Sofi Needs a Ladder.mp3',
    r'C:\Users\maste\OneDrive\Music\deadmau5 - Some Kind of Blue.mp3',
    r'C:\Users\maste\OneDrive\Music\deadmau5 - Sometimes Things Get, Whatever.mp3',
    r'C:\Users\maste\OneDrive\Music\deadmau5 - Three Pound Chicken Wing.mp3',
    r'C:\Users\maste\OneDrive\Music\deadmau5 & Kaskade - I Remember.mp3',
    r'C:\Users\maste\OneDrive\Music\deadmau5, Grabbitz - Let Go.mp3',
    r'C:\Users\maste\OneDrive\Music\Diplo, Trippie Redd - Wish.mp3',
    r'C:\Users\maste\OneDrive\Music\Dirty South, Alesso, Ruben Haze - City Of Dreams.mp3',
    r"C:\Users\maste\OneDrive\Music\Dogzilla - Without You (John O'Callaghan Extended Remix).mp3",
    r'C:\Users\maste\OneDrive\Music\Dogzilla - Without You (Ronald van Gelderen Extended Remix).mp3',
    r'C:\Users\maste\OneDrive\Music\Dogzilla - Without You (Will Atkinson Remix).mp3',
    r"C:\Users\maste\OneDrive\Music\Drake - Hold On, We're Going Home.mp3",
    r'C:\Users\maste\OneDrive\Music\Drake - Over (Ayobi Remix).mp3',
    r'C:\Users\maste\OneDrive\Music\Drake - Passionfruit.mp3',
]

LIST_TO_NAT_SORT_1 = [
    '1. Hello World',
    '3. Hello World',
    '10. Hello World',
    '2. Hello World',
    '9. Hello World',
    '11. Hello World',
    '12. Hello World',
]
NAT_SORTED_LIST_1 = [
    '1. Hello World',
    '2. Hello World',
    '3. Hello World',
    '9. Hello World',
    '10. Hello World',
    '11. Hello World',
    '12. Hello World',
]

LIST_TO_NAT_SORT_2 = [
    'C:/Users/maste/Documents/MEGA/Music/1. Hello World',
    'C:/Users/maste/Documents/MEGA/Music/3. Hello World',
    'C:/Users/maste/Documents/MEGA/Music/10. Hello World',
    'C:/Users/maste/Documents/MEGA/Music/2. Hello World',
    'C:/Users/maste/Documents/MEGA/Music/9. Hello World',
    'C:/Users/maste/Documents/MEGA/Music/11. Hello World',
    'C:/Users/maste/Documents/MEGA/Music/12. Hello World',
]
NAT_SORTED_LIST_2 = [
    'C:/Users/maste/Documents/MEGA/Music/1. Hello World',
    'C:/Users/maste/Documents/MEGA/Music/2. Hello World',
    'C:/Users/maste/Documents/MEGA/Music/3. Hello World',
    'C:/Users/maste/Documents/MEGA/Music/9. Hello World',
    'C:/Users/maste/Documents/MEGA/Music/10. Hello World',
    'C:/Users/maste/Documents/MEGA/Music/11. Hello World',
    'C:/Users/maste/Documents/MEGA/Music/12. Hello World',
]

GET_METADATA_FROM = [
    r'C:\Users\maste\Documents\MEGA\Music\$teven Cannon - Inxanity.mp3',
    r'C:\Users\maste\Documents\MEGA\Music\6ixbuzz, Pressa, Houdini - Up & Down.mp3',
    r'C:\Users\maste\Documents\MEGA\Music\88GLAM, Lil Yachty - Lil Boat.mp3',
    r'C:\Users\maste\Documents\MEGA\Music\Adam K & Soha - Twilight.mp3',
]
EXPECTED_METADATA = [
    {
        'album': 'Inxanity',
        'artist': '$teven Cannon',
        'explicit': True,
        'sort_key': 'inxanity - $teven cannon',
        'title': 'Inxanity',
        'track_number': '1',
    },
    {
        'album': '6ixupsidedown',
        'artist': '6ixbuzz, Pressa, Houdini',
        'explicit': True,
        'title': 'Up & Down',
        'sort_key': 'up & down - 6ixbuzz, pressa, houdini',
        'track_number': '1',
    },
    {
        'album': '88GLAM2.5',
        'artist': '88GLAM, Lil Yachty',
        'explicit': True,
        'title': 'Lil Boat',
        'sort_key': 'lil boat - 88glam, lil yachty',
        'track_number': '6',
    },
    {
        'album': 'Rebirth Classics - Ibiza',
        'artist': 'Adam K & Soha',
        'explicit': False,
        'title': 'Twilight',
        'sort_key': 'twilight - adam k & soha',
        'track_number': '4',
    },
]
EXPECTED_FIRST_ARTIST = ['$teven Cannon', '6ixbuzz', '88GLAM', 'Adam K & Soha']
AUDIO_FILE_AND_NAMES = [
    (
        r'C:\Users\maste\Documents\MEGA\Music\Alesso, Matthew Koma - Years.mp3',
        'Alesso, Matthew Koma - Years',
    ),
    (
        'C:/Users/maste/Documents/MEGA/Music/Alesso, Matthew Koma - Years.mp3',
        'Alesso, Matthew Koma - Years',
    ),
    (
        r'Music\Afrojack, Steve Aoki, Miss Palmer - No Beef.mp3',
        'Afrojack, Steve Aoki, Miss Palmer - No Beef',
    ),
    (
        'Music/Afrojack, Steve Aoki, Miss Palmer - No Beef.mp3',
        'Afrojack, Steve Aoki, Miss Palmer - No Beef',
    ),
]


def test_get_running_processes():
    assert len(list(get_running_processes())) > 0
    for process in get_running_processes():
        # 5 keys
        assert len(process) == 5
        assert isinstance(process['pid'], int)


@pytest.mark.parametrize('file_path,expected', AUDIO_FILE_AND_NAMES)
def test_get_file_name(file_path, expected):
    assert get_file_name(file_path) == expected


def test_display_lang():
    lang = get_display_lang()
    assert isinstance(lang, str)
    assert len(lang) > 0


def test_internationalization():
    assert isinstance(get_languages(), list)
    # check if cache works
    assert isinstance(get_languages(), list)
    for code in get_languages():
        assert isinstance(code, str)


@pytest.mark.parametrize('code', ('en', 'es'))
def test_get_lang_pack(code):
    pack = get_lang_pack(code)
    assert len(pack) > 0
    if code == 'en':
        assert isinstance(pack, dict)
    else:
        assert isinstance(pack, list)


@pytest.mark.parametrize('code', ('es', 'de', 'en'))
def test_get_translation(code):
    State.lang = code
    for line in get_lang_pack('en'):
        get_translation(line, code)
    unknown_title = Unknown('Title')
    assert isinstance(unknown_title > 'unknown title', bool)
    assert isinstance(unknown_title < 'unknown title', bool)
    assert isinstance(unknown_title <= 'unknown title', bool)
    assert isinstance(unknown_title >= 'unknown title', bool)


@pytest.mark.parametrize(
    'ext',
    (
        '.mp3',
        '.flac',
        '.m4a',
        '.mp4',
        '.aac',
        '.mpeg',
        '.ogg',
        '.opus',
        '.wma',
        '.wav',
    ),
)
def test_valid_audio_file(ext):
    assert valid_audio_file(f'x{ext}')


@pytest.mark.parametrize(
    'file',
    chain(
        TEST_MUSIC_FILES,
        ['https://audio.tv', 'https://audio.com', 'audio.mp3', 'https://audio.mp4'],
    ),
)
def test_audio_length(file):
    try:
        assert get_audio_length(file) > 0
        assert valid_audio_file(file)
    except InvalidAudioFile:
        assert not os.path.exists(file)


@pytest.mark.parametrize('file', ('audio_player.py', 'file.mp4', 'README.txt'))
def test_audio_length_fail(file):
    # the music players expects bad files to only raise InvalidAudioFile
    with pytest.raises(InvalidAudioFile):
        get_audio_length(file)


@pytest.mark.skipif(
    platform.system() != 'Windows',
    reason='get_default_output_device only implemented on Windows',
)
@pytest.mark.no_ci
def test_default_output_device():
    assert get_default_output_device()
    print('Default Audio Device:', get_default_output_device())
    sar = SystemAudioRecorder()
    sar.start()  # start system audio recording
    time.sleep(0.5)
    sar.stop()  # stop system audio recording


@pytest.mark.parametrize(
    'unsorted,expected',
    [(LIST_TO_NAT_SORT_1, NAT_SORTED_LIST_1), (LIST_TO_NAT_SORT_2, NAT_SORTED_LIST_2)],
)
def test_natural_sort(unsorted, expected):
    assert sorted(unsorted, key=natural_key_file) == expected


@pytest.mark.parametrize(
    'color_code',
    (
        '#fff',
        '#ffffff',
        '#aaa',
        '#abc',
        '#999',
        '#000',
        '#010',
        '#000000',
        '#999999',
        '#aaaaaa',
    ),
)
def test_valid_color_code(color_code):
    assert valid_color_code(color_code)


@pytest.mark.parametrize(
    'color_code',
    (
        'fff',
        '000',
        'abcdef',
        '999999',
        '.',
        'czc/z',
        '#...',
        '#/.;ads',
        '#fff.aa',
        '#999999a',
        '#ggg',
    ),
)
def test_invalid_color_codes(color_code):
    assert not valid_color_code(color_code)


@pytest.mark.parametrize(
    'file,expected,expected_first_artist',
    zip(GET_METADATA_FROM, EXPECTED_METADATA, EXPECTED_FIRST_ARTIST),
)
@pytest.mark.no_ci
def test_get_metadata(file, expected, expected_first_artist):
    assert os.path.exists(file)
    with suppress(MutagenError):
        metadata = get_metadata(file)
        assert metadata.pop('length') > 0
        assert metadata.pop('time_modified') > 0
        assert metadata == expected
        assert get_first_artist(metadata['artist']) == expected_first_artist


def test_ipv4():
    assert get_ipv4().count('.') == 3


def test_ipv6():
    assert get_ipv6().count(':') > 0


def test_mac():
    assert get_mac().count(':') == 5


def test_ipv4_wifi_match():
    ipconfig_cleaned = clean_ipconfig(IPCONFIG_ELIBROFTW)
    wifi_match = IPV4_WIFI_PATTERN.findall(ipconfig_cleaned)
    assert len(wifi_match) > 0
    assert wifi_match[-1][-1] == '192.168.0.89'


def test_ipv4_general_match():
    ipconfig_cleaned = clean_ipconfig(IPCONFIG_ERICCHAN1989_ALL)
    assert len(IPV4_WIFI_PATTERN.findall(ipconfig_cleaned)) == 0
    matches = IPV4_GENERAL_PATTERN.findall(ipconfig_cleaned)
    assert matches[-1] == '192.168.2.2'
    ipconfig_cleaned = clean_ipconfig(IPCONFIG_ERICCHAN1989)
    assert len(IPV4_WIFI_PATTERN.findall(ipconfig_cleaned)) == 0
    matches = IPV4_GENERAL_PATTERN.findall(ipconfig_cleaned)
    assert matches[-1] == '192.168.2.2'


def test_better_shuffle():
    test_better_shuffle = list(range(10000))
    better_shuffle(test_better_shuffle, 1, -2)
    # shuffle everything except for the first and last element
    assert test_better_shuffle[0] == 0
    assert test_better_shuffle[-1] == 9999


def test_is_already_running():
    assert isinstance(is_already_running(), bool)


@pytest.mark.parametrize(
    'url,expected_id',
    (
        ('https://youtu.be/Dlxu28sQfkE', 'Dlxu28sQfkE'),
        ('https://www.youtube.com/watch?v=Dlxu28sQfkE&feature=youtu.be', 'Dlxu28sQfkE'),
        ('https://www.youtube.com/watch/Dlxu28sQfkE', 'Dlxu28sQfkE'),
        ('https://www.youtube.com/embed/Dlxu28sQfkE', 'Dlxu28sQfkE'),
        ('https://www.youtube.com/v/Dlxu28sQfkE', 'Dlxu28sQfkE'),
        (
            'https://www.youtube.com/playlist?list=PLRbcUrcJVEmX_eaAsubNOWfE4SlhGqjW4',
            'PLRbcUrcJVEmX_eaAsubNOWfE4SlhGqjW4',
        ),
    ),
)
def test_yt_id(url, expected_id):
    assert get_yt_id(url) == expected_id


def test_custom_art():
    assert custom_art('sys')


@pytest.mark.parametrize('file', TEST_MUSIC_FILES + ['DEFAULT_ART'])
def test_album_art(file):
    _mime, img_data = get_album_art(file)
    assert isinstance(img_data, bytes)


@pytest.mark.parametrize(
    'option,expected_img,expected_label',
    (
        (None, REPEAT_OFF_IMG, 'Repeat All'),
        (True, REPEAT_ONE_IMG, 'Repeat Off'),
        (False, REPEAT_ALL_IMG, 'Repeat One'),
    ),
)
def test_repeat_img_tooltip(option, expected_img, expected_label):
    assert repeat_img_tooltip(option) == (expected_img, t(expected_label))


@pytest.mark.parametrize('size', ((125, 425), COVER_MINI, COVER_NORMAL))
def test_resize_img(size):
    base64data = resize_img(DEFAULT_ART, '#121212', new_size=size)
    img_data = io.BytesIO(b64decode(base64data))
    img: Image.Image = Image.open(img_data)
    assert img.size == size


@pytest.mark.parametrize(
    'url',
    (
        'https://open.spotify.com/track/0Memc4WL8oO0xUnkXCsNnV?si=Mg58OQxeTj6lTkvNV919wg',  # spotify track
        'https://open.spotify.com/album/2JSiQ1wnqVEdaf6Y39DsAJ?highlight=spotify:track:0Memc4WL8oO0xUnkXCsNnV',
        'https://open.spotify.com/album/47MVgO7XNmxzoYSJIvqxAG',  # spotify album
        'https://open.spotify.com/playlist/37i9dQZF1DXarRysLJmuju',  # spotify playlist
    ),
)
@pytest.mark.skipif(True, reason='spotify web API access removal')
def test_spotify(url):
    try:
        metadata_list = get_spotify_tracks(url)
        assert isinstance(metadata_list, list)
        for metadata in metadata_list:
            assert metadata['src']
            assert 'explicit' in metadata
    except AssertionError:
        print('WARNING: Spotify down')
        time.sleep(0.5)


@pytest.mark.parametrize(
    'url',
    (
        'https://www.deezer.com/track/65404135?utm_campaign=clipboard-generic',  # deezer track
        'https://deezer.page.link/NTW1c5cRdkzy28P19',
        'https://deezer.page.link/Prw6jnAYCNe8VrV17',
        'https://www.deezer.com/album/217794942',  # deezer album
        'https://deezer.page.link/XGPUgE6HN5LryeBE7',
        'https://www.deezer.com/playlist/1963962142',  # deezer playlist
        'https://deezer.page.link/URU2yh1GX1wyaoZy9',
    ),
)
@pytest.mark.no_ci
def test_deezer(url):
    with suppress(LookupError):
        metadata_list = get_deezer_tracks(url)
        assert isinstance(metadata_list, list)
        for metadata in metadata_list:
            assert metadata['src']
            assert 'explicit' in metadata
            assert isinstance(metadata['expiry'], (int, float))
            assert metadata['url']


@pytest.fixture
def running_in_ci(request):
    return request.config.getoption('--ci')


@pytest.mark.parametrize(
    'url',
    ('https://www.youtube.com/watch?v=PNP0hku7hSo', 'https://youtu.be/5XADIh_mJM4'),
)
def test_ydl(running_in_ci, url):
    try:
        info = ydl_extract_info(url)
        assert isinstance(info, dict)
    except Exception:
        if not running_in_ci:
            raise


def test_get_proxies():
    for _ in range(3):
        get_proxy()


@pytest.mark.parametrize(
    'path,expected', ((r'C:\Users\maste\OneDrive', 'C:/Users/maste/OneDrive'),)
)
def test_fix_path(path, expected):
    assert fix_path(path, False) == expected


@pytest.mark.parametrize(
    'path,expected', (('C:/Users/maste/OneDrive', r'C:\Users\maste\OneDrive'),)
)
@pytest.mark.skipif(
    platform.system() != 'Windows',
    reason='this test checks if a posix path gets converted into a windows path',
)
def test_fix_path_win32(path, expected):
    assert fix_path(path) == expected


# expected is (time elapse, time remaining)
@pytest.mark.parametrize(
    'position,length,expected',
    (
        (30, 300, ('0:30', '4:30')),
        (60, 300, ('1:00', '4:00')),
        (90, 300, ('1:30', '3:30')),
        (90, 180, ('1:30', '1:30')),
        (180, 180, ('3:00', '0:00')),
        (45, 125, ('0:45', '1:20')),
        (105, 125, ('1:45', '0:20')),
        (105, 300, ('1:45', '3:15')),
    ),
)
def test_progress_bar_texts(position, length, expected):
    assert create_progress_bar_texts(position, length) == expected


def test_export_playlist():
    test_uris = TEST_MUSIC_FILES + ['https://www.youtube.com/watch?v=_jh9lMUjBLo']
    path = export_playlist('test_playlist_support', test_uris)
    for expected_uri, actual_uri in zip(test_uris, parse_m3u(path)):
        print(expected_uri, actual_uri)
        assert Path(expected_uri) == Path(actual_uri)
    os.remove(path)


@pytest.mark.parametrize('url', ('https://www.youtube.com/watch?v=MTk-Hwr15ao',))
def test_youtube_comments(url):
    comments = list(get_youtube_comments(url, 10))
    assert len(comments) > 0


@pytest.fixture
def uploading_after(request):
    return request.config.getoption('--upload')


@pytest.fixture
def test_auto_update(request):
    return request.config.getoption('--test-auto-update')


def test_get_latest_release(uploading_after, test_auto_update):
    version = [int(x) for x in VERSION.split('.')]
    latest_release = get_latest_release(VERSION, VERSION, True)
    assert isinstance(latest_release, dict)
    compare_ver = latest_release['version']
    compare_ver = [int(x) for x in compare_ver.split('.')]
    if test_auto_update:
        assert version < compare_ver
    elif uploading_after:
        assert compare_ver < version
    else:
        assert compare_ver <= version
