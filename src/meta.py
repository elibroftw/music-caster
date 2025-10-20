VERSION = latest_version = '5.25.0'
UPDATE_MESSAGE = """
[NEW] Support "System Audio" in CLI
[MSG] Language translators wanted
""".strip()
IMPORTANT_INFORMATION = """
""".strip()

# Constants
DEFAULT_THEME = {
    'accent': '#00bfff',
    'background': '#121212',
    'text': '#d7d7d7',
    'alternate_background': '#222222',
}
TOGGLEABLE_SETTINGS = {
    'auto_update',
    'notifications',
    'discord_rpc',
    'run_on_startup',
    'folder_cover_override',
    'folder_context_menu',
    'save_window_positions',
    'populate_queue_startup',
    'lang',
    'smart_queue',
    'show_track_number',
    'persistent_queue',
    'flip_main_window',
    'vertical_gui',
    'use_last_folder',
    'show_album_art',
    'reversed_play_next',
    'scan_folders',
    'show_queue_index',
    'queue_library',
    'show_queue_length',
    'show_queue_time',
    'gui_exits_app',
    'experimental_features',
}
PID_FILENAME = 'music_caster.pid'
LOCK_FILENAME = 'music_caster.lock'
UNINSTALLER = 'unins000.exe'
WAIT_TIMEOUT = 5
STREAM_CHUNK = 1024
EMAIL = 'elijahllopezz@gmail.com'
CONTACT_INFO = f'Elijah Lopez <{EMAIL}>'
SUBMIT_EVENTS = {'\r', 'special 16777220', 'special 16777221', 'timer_submit'}
AUDIO_EXTS = ('mp3', 'mp4', 'mpeg', 'm4a', 'flac', 'aac', 'ogg', 'opus', 'wma', 'wav', 'aiff')
IMG_FILE_TYPES = (
    ('Image', '*.gif *.pdf *.png *jpg *jpeg *.tiff *.webp *.' + ' *.'.join(AUDIO_EXTS)),
)
AUDIO_FILE_TYPES = (('Audio File', '*.' + ' *.'.join(AUDIO_EXTS) + ' *.m3u *.m3u8'),)
VIDEO_FILE_TYPES = (('Media Container File', '*.' + ' *.'.join(('mp2t', 'mp3', 'mp4', 'ogg', 'wav', 'webm'))))
# re-define AUDIO_EXTS
AUDIO_EXTS = {f'.{ext}' for ext in AUDIO_EXTS}
AUDIO_EXTS.add('.m3u')
AUDIO_HANDLER_EXTS = ('mp3', 'flac', 'm4a', 'aac', 'ogg', 'opus', 'aiff', 'wma', 'wav', 'mpeg', 'm3u', 'm3u8')

FONT_NORMAL = 'Segoe UI', 11
FONT_SMALL = 'Segoe UI', 10
FONT_LINK = 'Segoe UI', 11, 'underline'
FONT_TITLE = 'Segoe UI', 14
FONT_MED = 'Segoe UI', 12
FONT_TAB = 'Meiryo UI', 10
LINK_COLOR = '#3ea6ff'
COVER_MINI = (127, 127)
COVER_NORMAL = (255, 255)
PL_COMBO_W = 37
USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64; rv:12.0) Gecko/20100101 Firefox/591'
SUN_VALLEY_TCL = 'theme/sun-valley.tcl'

TKDND_ENABLED = False

USING_TAURI_FRONTEND = True
BUNDLE_IDENTIFIER = 'ca.elijahlopez.music-caster'

class State:
    """
    attributes in State are modified by music_caster.py
    """

    lang = ''
    track_format = '&title - &artist'
    PORT = 2001
    # experimental setting
    using_tcl_theme = False
    theme_sourced = False
    settings = {}
    update_available = False
    installing_update = True
