VERSION = latest_version = '5.8.8'
UPDATE_MESSAGE = """
[MISC] Battery Resolution Switcher
[MSG] Language translators wanted
""".strip()
IMPORTANT_INFORMATION = """
""".strip()
# some constants
DEFAULT_THEME = {'accent': '#00bfff', 'background': '#121212', 'text': '#d7d7d7', 'alternate_background': '#222222'}
TOGGLEABLE_SETTINGS = {'auto_update', 'notifications', 'discord_rpc', 'run_on_startup', 'folder_cover_override',
                       'folder_context_menu', 'save_window_positions', 'populate_queue_startup', 'lang',
                       'smart_queue', 'show_track_number', 'persistent_queue', 'flip_main_window', 'vertical_gui',
                       'use_last_folder', 'show_album_art', 'reversed_play_next', 'scan_folders',
                       'show_queue_index', 'queue_library', 'show_queue_length', 'show_queue_time', 'gui_exits_app'}
PID_FILENAME = 'music_caster.pid'
LOCK_FILENAME = 'music_caster.lock'
UNINSTALLER = 'unins000.exe'
WAIT_TIMEOUT = 5
STREAM_CHUNK = 1024
EMAIL = 'elijahllopezz@gmail.com'
SUBMIT_EVENTS = {'\r', 'special 16777220', 'special 16777221', 'timer_submit'}
AUDIO_EXTS = ('mp3', 'mp4', 'mpeg', 'm4a', 'flac', 'aac', 'ogg', 'opus', 'wma', 'wav')
AUDIO_FILE_TYPES = (('Audio File', '*.' + ' *.'.join(AUDIO_EXTS) + ' *.m3u *.m3u8'),)
IMG_FILE_TYPES = (('Image', '*.gif *.pdf *.png *.tiff *.webp *.' + ' *.'.join(AUDIO_EXTS)),)
