import datetime
import platform
import time
from math import ceil, floor

import PySimpleGUI as Sg

from b64_images import *
from gui.components import Checkbox, IconButton, StyledButton, QRCode
from meta import (CONTACT_INFO, COVER_NORMAL, FONT_LINK, FONT_MED, FONT_NORMAL, PlayingStatus,
                  FONT_TAB, FONT_TITLE, LINK_COLOR, PL_COMBO_W, VERSION, State)
from resolution_switcher import fmt_res, get_all_resolutions
from utils import Device, get_languages, t, truncate_title, repeat_img_tooltip, get_first_artist, create_progress_bar_texts


def MiniPlayerWindow(playing_status, settings, title: str, artist: str, album_art_data: bytes,
               track_length: float | int, track_position: float | int):
    # album_art_data is 125 x 125
    album_art = Sg.Column([[Sg.Image(data=album_art_data, key='artwork', pad=(0, 0))]],
                          element_justification='left', pad=(0, 0))
    music_controls = MusicControls(settings, playing_status, prev_button_pad=((10, 5, None)))
    progress_bar_layout = ProgressBar(settings, track_position, track_length, playing_status)
    title = truncate_title(title)
    right_side = Sg.Column([
        [Sg.Text(title, font=FONT_TITLE, key='title', pad=((10, 0), 0), size=(28, 1))],
        [Sg.Text(artist, font=FONT_MED, key='artist', pad=((10, 0), 0), size=(28, 2))],
        music_controls, progress_bar_layout], pad=(0, 0))
    return [[album_art, right_side] if settings['show_album_art'] else [right_side]]


def MainWindow(playing_status, settings, title: str, artist: str, album: str, album_art_data: bytes,
               track_length: float | int, track_position: float | int,
               queue, listbox_selected, timer, music_lib, devices, web_ui_url: str):
    # devices: device_names list of (name, device_key)
    accent_color, text_color, background_color = settings['theme']['accent'], settings['theme']['text'], settings['theme']['background']
    alternate_bg = settings['theme']['alternate_background']
    vertical_gui, show_album_art = settings['vertical_gui'], settings['show_album_art']
    music_controls = MusicControls(settings, playing_status)
    progress_bar_layout = ProgressBar(settings, track_position, track_length, playing_status)
    if not show_album_art: album_art_data = ''
    info_top_pad = 10 + 60 * (not album_art_data) - 30 * (vertical_gui and not album_art_data)
    # 10, 110, or 0
    info_bot_pad = 10 + 40 * (not album_art_data) - 20 * (vertical_gui and not album_art_data)
    # 10 or 30
    # default_device = []
    default_device = next(filter(lambda device: device.id == settings['device'], devices), Device())
    combo_devices = [Sg.Combo(devices, key='devices', readonly=True, background_color=background_color, expand_x=True,
                              default_value=default_device, enable_events=True, pad=((5, 10), 10))]
    left_pad = settings['vertical_gui'] * 95 + 5
    main_part = Sg.Column([
        [Sg.Image(data=album_art_data, pad=(0, 0), size=COVER_NORMAL, key='artwork')] if album_art_data else [],
        [Sg.Text(album, font=FONT_MED, key='album', pad=((0, 0), (info_top_pad, 0)), enable_events=True,
                 size=(30, 2), justification='center')],
        [Sg.Text(title, font=FONT_TITLE, key='title', pad=((0, 0), 4), enable_events=True,
                 size=(30, 2), justification='center')],
        [Sg.Text(artist, font=FONT_MED, key='artist', pad=((0, 0), (0, info_bot_pad)), enable_events=True,
                 size=(30, 0), justification='center')],
        music_controls, progress_bar_layout, combo_devices], element_justification='center',
        pad=((left_pad, 5), 5 * vertical_gui))

    LISTBOX_HEIGHT = 21 - 7 * (vertical_gui or not show_album_art)

    tab_group = [[
        QueueTab(queue, listbox_selected, LISTBOX_HEIGHT, accent_color, text_color, background_color),
        URLTab(accent_color, background_color),
        LibraryTab(music_lib, LISTBOX_HEIGHT, accent_color, text_color, background_color, alternate_bg, vertical_gui, show_album_art),
        PlaylistsTab(settings['playlists'], accent_color, text_color,
                     background_color, vertical_gui, show_album_art),
        TimerTab(timer, accent_color, text_color, background_color,
                 settings['timer_shut_down'], settings['timer_hibernate'], settings['timer_sleep']),
        MetadataTab(accent_color, background_color),
        SettingsTab(settings, web_ui_url)
    ]]
    tabs_part = Sg.TabGroup(tab_group, font=FONT_TAB, border_width=0, title_color=text_color, key='tab_group',
                            selected_background_color=accent_color, enable_events=True,
                            tab_background_color=background_color, selected_title_color=background_color, background_color=background_color)
    if vertical_gui: return [[main_part], [tabs_part]]
    return [[main_part, tabs_part]] if settings['flip_main_window'] else [[tabs_part, main_part]]


def MusicControls(settings, playing_status: PlayingStatus, prev_button_pad=None):
    accent_color, bg = settings['theme']['accent'], settings['theme']['background']
    is_muted = settings['muted']
    volume = 0 if is_muted else settings['volume']
    v_slider_img = VOLUME_MUTED_IMG if is_muted else VOLUME_IMG
    p_r_img = PAUSE_BUTTON_IMG if playing_status.playing() else PLAY_BUTTON_IMG
    repeat_img, repeat_tooltip = repeat_img_tooltip(settings['repeat'])
    repeat_button = {'button_color': (bg, bg), 'tooltip': repeat_tooltip, 'metadata': settings['repeat']}
    shuffle_button = {'button_color': (bg, bg), 'image_data': SHUFFLE_ON if settings['shuffle'] else SHUFFLE_OFF}
    mute_tooltip = t('unmute') if is_muted else t('mute')
    return [Sg.Button(key='prev', image_data=PREVIOUS_BUTTON_IMG, button_color=(bg, bg), tooltip=t('previous track'), pad=prev_button_pad),
            Sg.Button(key='pause/resume', image_data=p_r_img, button_color=(bg, bg)),
            Sg.Button(key='next', image_data=NEXT_BUTTON_IMG, button_color=(bg, bg), tooltip=t('next track')),
            Sg.Button(key='repeat', image_data=repeat_img, **repeat_button),
            Sg.Button(key='shuffle', **shuffle_button, tooltip=t('shuffle')),
            Sg.Button(key='mute', image_data=v_slider_img, button_color=(bg, bg), tooltip=mute_tooltip),
            Sg.Slider((0, 100), default_value=volume, orientation='h', key='volume_slider',
                      disable_number_display=True, enable_events=True, background_color=accent_color,
                      text_color='#000000', size=(10, 10), tooltip=t('scroll mousewheel'), resolution=1)]


def ProgressBar(settings, track_position, track_length, playing_status: PlayingStatus):
    time_elapsed, time_left = create_progress_bar_texts(track_position, track_length)
    text_size = (5, 1)
    bot_pad = (settings['vertical_gui'] and not settings['show_album_art']) * 30
    accent_color, bg = settings['theme']['accent'], settings['theme']['background']
    mini_mode = settings['mini_mode']
    time_elapsed_pad = ((2, 0), (0, 0)) if mini_mode else ((0, 5), (10, bot_pad))
    time_left_pad = ((0, 0), (0, 0)) if mini_mode else ((5, 0), (10, bot_pad))
    progress_layout = [Sg.Text(time_elapsed, key='time_elapsed', pad=time_elapsed_pad, justification='center',
                               size=text_size, font=FONT_NORMAL),
                       Sg.Slider(range=(0, 1 if track_length is None else track_length),
                                 default_value=1 if track_length is None else floor(track_position),
                                 orientation='h', size=(20 if mini_mode else 30, 10), key='progress_bar',
                                 enable_events=True, relief=Sg.RELIEF_FLAT, background_color=accent_color,
                                 disable_number_display=True, disabled=playing_status.stopped() or track_length is None,
                                 tooltip=t('scroll mousewheel'),
                                 pad=((2, 10), (0, 0)) if mini_mode else ((8, 8), (10, bot_pad))),
                       Sg.Text(time_left, key='time_left', pad=time_left_pad, justification='left',
                               size=text_size, font=FONT_NORMAL)]
    if mini_mode:
        progress_layout.append(Sg.Button(key='mini_mode', image_data=RESTORE_WINDOW, size=(1, 1), enable_events=True,
                                         button_color=(bg, bg), tooltip=t('restore window'), pad=(0, 0)))
    return progress_layout


def URLTab(accent_color, bg):
    layout = [[Sg.Text(t('Enter URL'), font=FONT_NORMAL)],
              [Sg.Radio(t('Play Immediately'), 'url_option', key='url_play', default=True),
               Sg.Radio(t('Queue'), 'url_option', key='url_queue'),
               Sg.Radio(t('Play Next'), 'url_option', key='url_play_next')],
              [Sg.Input(key='url_input', font=FONT_NORMAL, enable_events=True, border_width=1),
               StyledButton(t('Submit'), accent_color, bg, key='url_submit', bind_return_key=True)],
              [Sg.Text('', key='url_msg', size=(20, 1))]]
    return Sg.Tab(t('URL'), [[Sg.Column(layout, pad=(5, 20))]], key='tab_url')


def QueueTab(queue, listbox_selected, listbox_height, accent_color, text_color, background_color):
    select_file_values = [t('Play'), t('Queue'), t('Play Next')]
    select_files = t('Select Files')
    select_folder = t('Select Folder')
    biggest_word = len(max(*select_file_values, select_files, select_folder, key=len))
    combo_w = ceil(biggest_word * 0.95)
    queue_controls = [Sg.Column([[
        # fs stands for file system here
        Sg.Combo(select_file_values, default_value=select_file_values[0], key='fs_action', size=(combo_w, 5),
                 enable_events=False, pad=(5, (6, 4)), readonly=True),
        StyledButton(select_files, accent_color, background_color, key='select_files',
                  button_width=biggest_word, pad=(5, (7, 5))),
        StyledButton(select_folder, accent_color, background_color, key='select_folders',
                  button_width=biggest_word),
    ]], justification='center')]
    move_to_next_up = {'image_data': PLAY_NEXT_ICON, 'button_color': (background_color, background_color), 'tooltip': t('Move to next up')}
    listbox_controls = [
        [Sg.Button(key='mini_mode', image_data=RESTORE_WINDOW, button_color=(background_color, background_color), tooltip=t('Launch mini mode'))],
        [Sg.Button(key='queue_all', image_data=QUEUE_ICON, button_color=(background_color, background_color), tooltip=t('queue all'))],
        [Sg.Button(key='clear_queue', image_data=CLEAR_QUEUE, button_color=(background_color, background_color), tooltip=t('Clear the queue'))],
        [Sg.Button(key='save_to_pl', image_data=SAVE_IMG, button_color=(background_color, background_color), tooltip=t('Save to playlist'))],
        [Sg.Button(key='locate_uri', image_data=LOCATE_FILE, button_color=(background_color, background_color), tooltip=t('locate track'))],
        [Sg.Button(key='copy_uri', image_data=COPY_ICON, button_color=(background_color, background_color), tooltip=t('copy uris'))],
        [Sg.Button(key='edit_metadata', image_data=EDIT_ICON, button_color=(background_color, background_color), tooltip=t('edit metadata'))],
        [Sg.Button(key='move_to_next_up', **move_to_next_up)],
        [IconButton(UP_ICON, 'move_up', t('move up'), background_color)],
        [IconButton(X_ICON, 'remove_track', t('remove'), background_color)],
        [IconButton(DOWN_ICON, 'move_down', t('move down'), background_color)]
    ]
    queue_tab_layout = [[
        Sg.Column([[Sg.Listbox(queue, default_values=listbox_selected, size=(64, listbox_height),
                               select_mode=Sg.SELECT_MODE_EXTENDED,
                               text_color=text_color, key='queue', font=FONT_NORMAL,
                               bind_return_key=True)], queue_controls]),
        Sg.Column(listbox_controls, pad=(0, 0), vertical_alignment='center')]]
    return Sg.Tab(t('Queue'), queue_tab_layout, key='tab_queue')


def LibraryTab(music_lib, listbox_height, accent_color, text_color, background_color, alternate_bg, vertical_gui: bool, show_album_art: bool):
    try:
        lib_data = [[track['title'], get_first_artist(track['artist']), track['album'], uri] for uri, track in
                    music_lib.items()]
    except RuntimeError:
        lib_data = []
    lib_headings = ['title', 'artist', 'album']
    if State.using_tcl_theme:
        library_height = listbox_height
        col_widths = [25, 12, 15]
    else:
        library_height = 15 - 4 * (vertical_gui or not show_album_art)
        col_widths = [20, 15, 15]

    library_layout = [[Sg.Table(values=lib_data, headings=lib_headings, row_height=30, auto_size_columns=False,
                                col_widths=col_widths, bind_return_key=True, justification='right',
                                size=(10, 1), selected_row_colors=(background_color, accent_color), num_rows=library_height,
                                right_click_menu=['', ['Play::library', 'Play Next::library',
                                                       'Queue::library', 'Locate::library']],
                                header_text_color=text_color, header_background_color=background_color,
                                alternating_row_color=alternate_bg, key='library')]]
    return Sg.Tab(t('Library'), library_layout, key='tab_library')


def PlaylistsTab(playlists, accent_color, text_color, background_color, vertical_gui: bool, show_album_art: bool):
    playlists_names = list(playlists.keys())
    default_pl_name = playlists_names[0] if playlists_names else None
    playlist_selector = [
        [IconButton(PLUS_ICON, 'new_pl', t('new playlist'), background_color),
         Sg.Button(image_data=EXPORT_PL, key='export_pl', tooltip=t('export playlist'), button_color=(background_color, background_color)),
         Sg.Button(image_data=DELETE_ICON, key='delete_pl', tooltip=t('delete playlist'), button_color=(background_color, background_color)),
         Sg.Button(image_data=PLAY_ICON, key='play_pl', tooltip=t('play playlist'), button_color=(background_color, background_color)),
         Sg.Button(image_data=QUEUE_ICON, key='queue_pl', tooltip=t('queue playlist'), button_color=(background_color, background_color)),
         Sg.Button(image_data=PLAY_NEXT_ICON, key='add_next_pl', tooltip=t('add to next up'), button_color=(background_color, background_color)),
         Sg.Combo(values=playlists_names, size=(PL_COMBO_W, 1), key='playlist_combo', font=FONT_NORMAL,
                  enable_events=True, default_value=default_pl_name, readonly=True)]]
    playlist_name = playlists_names[0] if playlists_names else ''
    url_input = [Sg.Input('', key='pl_url_input', size=(15, 1), font=FONT_NORMAL, border_width=1, enable_events=True)]
    add_url = [StyledButton(t('Add URL'), accent_color, background_color, key='pl_add_url', button_width=13)]
    add_tracks = [StyledButton(t('Add files'), accent_color, background_color, key='pl_add_tracks', button_width=13)]
    lb_height = 17 - 6 * (vertical_gui or not show_album_art)
    pl_name_text = t('Playlist name')
    name_text_w = max(13, len(pl_name_text))
    layout = [[Sg.Column(playlist_selector, pad=(5, 20))],
              [Sg.Text(pl_name_text, font=FONT_NORMAL, size=(name_text_w, 1), justification='center', pad=(4, (5, 10))),
               Sg.Input(playlist_name, key='pl_name', size=(60 - name_text_w, 1), font=FONT_NORMAL,
                        pad=((22, 5), (5, 10)), border_width=1),
               Sg.Button(key='pl_save', image_data=SAVE_IMG, tooltip='Ctrl + S', button_color=(background_color, background_color))],
              [Sg.Column([add_tracks, url_input, add_url]),
               Sg.Listbox([], size=(45, lb_height), select_mode=Sg.SELECT_MODE_EXTENDED, text_color=text_color,
                          key='pl_tracks', background_color=background_color, font=FONT_NORMAL, bind_return_key=True),
               Sg.Column(
                   [[IconButton(UP_ICON, 'pl_move_up', t('move up'), background_color)],
                    [IconButton(X_ICON, 'pl_rm_items', t('remove'), background_color)],
                    [IconButton(DOWN_ICON, 'pl_move_down', t('move down'), background_color)],
                    [Sg.Button(image_data=PLAY_ICON, key='play_pl_selected', tooltip=t('play selected'),
                               button_color=(background_color, background_color))],
                    [Sg.Button(image_data=QUEUE_ICON, key='queue_pl_selected', tooltip=t('queue selected'),
                               button_color=(background_color, background_color))],
                    [Sg.Button(image_data=PLAY_NEXT_ICON, key='add_next_pl_selected',
                               tooltip=t('add selected to next up'), button_color=(background_color, background_color))],
                    [Sg.Button(image_data=LOCATE_FILE, key='pl_locate_selected', button_color=(background_color, background_color),
                               tooltip=t('locate selected'), size=(2, 1))],
                    [Sg.Button(image_data=COPY_ICON, key='pl_copy_selected', button_color=(background_color, background_color),
                               tooltip=t('copy URIs'), size=(2, 1))]
                    ],
                   background_color=background_color)]]
    return Sg.Tab(t('Playlists'), layout, key='tab_playlists')


def TimerTab(timer, accent_color, text_color, background_color, is_shut_down: bool, is_hibernate: bool, is_sleep: bool):
    do_nothing = not (is_shut_down or is_hibernate or is_sleep)
    # if timer is valid
    if time.time() < timer:
        timer_date = datetime.fromtimestamp(timer)
        timer_date = timer_date.strftime('%#I:%M %p')
        timer_text = t('Timer set for $TIME').replace('$TIME', timer_date)
    else:
        timer_text = t('No Timer Set')
    # wait for last track to finish setting
    cancel_button = StyledButton(t('Cancel Timer'), accent_color, background_color, key='cancel_timer', visible=timer != 0)
    defaults = {'text_color': text_color, 'background_color': background_color, 'font': FONT_NORMAL, 'enable_events': True}
    layout = [
        [Sg.Radio(t('Shut down when timer runs out'), 'TIMER', default=is_shut_down, key='shut_down', **defaults)],
        [Sg.Radio(t('Sleep when timer runs out'), 'TIMER', default=is_sleep, key='sleep', **defaults)],
        [Sg.Radio(t('Hibernate when timer runs out'), 'TIMER', default=is_hibernate, key='hibernate', **defaults)],
        [Sg.Radio(t('Only Stop Playback').capitalize(), 'TIMER', default=do_nothing, key='timer_stop', **defaults)],
        [Sg.Text(t('Enter minutes or HH:MM'), font=FONT_NORMAL),
         Sg.Input(key='timer_input', size=(11, 1), border_width=1),
         StyledButton(t('Submit'), accent_color, background_color, key='timer_submit')],
        [Sg.Text(t('Invalid Input (enter minutes or HH:MM)'), font=FONT_NORMAL, visible=False, key='timer_error')],
        [Sg.Text(timer_text, font=FONT_NORMAL, key='timer_text', size=(20, 1), metadata=timer != 0), cancel_button]
    ]
    return Sg.Tab(t('Timer'), [[Sg.Column(layout, pad=(0, (50, 0)), justification='center')]], key='tab_timer')


def MetadataTab(accent_color, background_color):
    layout = [[Sg.Column([
        [StyledButton(t('Select File'), accent_color, background_color, key='metadata_browse'),
         StyledButton(t('Save'), accent_color, background_color, key='metadata_save'),
         Sg.Text('', size=(45, 1), key='metadata_file', border_width=1, relief='sunken', click_submits=True)]],
        pad=(0, (20, 10)))],
        [Sg.Column([[Sg.Text(t(text), size=(20, 1)), Sg.Input(key=f'metadata_{key}', border_width=1, size=(25, 1))]
                    for (text, key) in
                    (('Title', 'title'), ('Artist', 'artist'), ('Album', 'album'), ('Track Number', 'track_num'))]),
         Sg.Image(key='metadata_art')],
        [Sg.Checkbox(t('Explicit'), key='metadata_explicit', enable_events=True),
         StyledButton(t('Select artwork'), accent_color, background_color, key='metadata_select_art', pad=(5, 10)),
         StyledButton(t('Search artwork'), accent_color, background_color, key='metadata_search_art', pad=(5, 10)),
         StyledButton(t('Remove artwork'), accent_color, background_color, key='metadata_remove_art', pad=(5, 10))],
        [Sg.Text('', key='metadata_msg', text_color='green', size=(60, 1))]]
    return Sg.Tab(t('Metadata'), [[Sg.Column(layout, pad=(5, 5))]], key='tab_metadata')


def SettingsTab(settings, web_ui_url):
    qr_code = QRCode(web_ui_url)
    accent_color, fg, bg = settings['theme']['accent'], settings['theme']['text'], settings['theme']['background']
    general_tab = Sg.Tab(t('General'), [
        [Sg.Text('🌐' if platform.system() == 'Windows' else 'g', tooltip=t('language', True)),
         Sg.Combo(values=get_languages(), size=(3, 1), default_value=settings['lang'], key='lang',
                  readonly=True, enable_events=True, tooltip=t('language'))],
        [Checkbox(t('Auto update'), 'auto_update', settings),
         Checkbox(t('Discord presence'), 'discord_rpc', settings, True)],
        [Checkbox(t('Notifications'), 'notifications', settings),
         Checkbox(t('Run on startup'), 'run_on_startup', settings, True)],
        [Checkbox(t('Folder context menu'), 'folder_context_menu', settings),
         Checkbox(t('Scan folders'), 'scan_folders', settings, True)],
        [Checkbox(t('Remember last folder'), 'use_last_folder', settings),
         Checkbox(t('Exit app on GUI close'), 'gui_exits_app', settings, True)],
        [Sg.Text(t('System Audio Delay:')),
         Sg.Input(settings['sys_audio_delay'], size=(10, 1), key='sys_audio_delay', tooltip=t('seconds'),
                  border_width=1, pad=(70, 1), enable_events=True)]
    ], background_color=bg)
    queuing_tab = Sg.Tab(t('Queueing'), [
        [Checkbox(t('Reversed play next'), 'reversed_play_next', settings),
         Checkbox(t('Always queue library'), 'queue_library', settings, True)],
        [Checkbox(t('Populate queue on startup'), 'populate_queue_startup', settings),
         Checkbox(t('Persistent queue'), 'persistent_queue', settings, True)],
        [Checkbox(t('Smart queue'), 'smart_queue', settings)]
    ])
    ui_tab = Sg.Tab(t('UI'), [
        [Checkbox(t('Save window positions'), 'save_window_positions', settings),
         Checkbox(t('Show track number'), 'show_track_number', settings, True)],
        [Checkbox(t('Left-side music controls'), 'flip_main_window', settings),
         Checkbox(t('Vertical GUI'), 'vertical_gui', settings, True)],
        [Checkbox(t('Show album art'), 'show_album_art', settings),
         Checkbox(t('Mini mode on top'), 'mini_on_top', settings, True)],
        [Checkbox(t('Use cover.* for album art'), 'folder_cover_override', settings),
         Checkbox(t('Show index in queue'), 'show_queue_index', settings, True)],
        [Sg.Text(t('Track Format:'), tooltip='&alb, &trck, &artist, &title'),
         Sg.Input(settings['track_format'], size=(30, 1), key='track_format', enable_events=True,
                  border_width=1, pad=(70, 1), tooltip='&alb, &trck, &artist, &title')]
    ], background_color=bg)
    tabs = [general_tab, queuing_tab, ui_tab]

    if platform.system() == 'Windows':
        res_values = list(get_all_resolutions().keys())
        misc_tab = Sg.Tab(t('Misc'),[
            [Sg.Text(t('On battery resolution')),
             Sg.Combo(values=res_values, size=(6, 1), default_value=fmt_res(*settings['on_battery_res']),
                       key='on_battery_res', readonly=True, enable_events=True)],
            [Sg.Text(t('Plugged in resolution')),
             Sg.Combo(values=res_values, size=(6, 1), default_value=fmt_res(*settings['plugged_in_res']),
                        key='plugged_in_res', readonly=True, enable_events=True)],
            [Checkbox(t('Experimental features'), 'experimental_features', settings)]
            ],
            background_color=bg)
        tabs.append(misc_tab)
    settings_tab_group = Sg.TabGroup([tabs], title_color=fg,
                                     border_width=0, selected_background_color=accent_color, font=FONT_TAB,
                                     tab_background_color=bg, selected_title_color=bg, background_color=bg)
    checkbox_col = Sg.Column([[settings_tab_group]], pad=((0, 0), (5, 0)))
    qr_code_params = {'tooltip': t('Open Web GUI'), 'button_color': (bg, bg)}
    right_settings_col = Sg.Column([
        [Sg.Button(key='web_gui', image_data=qr_code, **qr_code_params)],
        [StyledButton('settings.json', accent_color, bg, key='settings_file', pad=((15, 0), 5), button_width=12)],
        [StyledButton('Changelog', accent_color, bg, key='changelog_file', pad=((15, 0), 5), button_width=12)]
    ], pad=(0, 0))
    link_params = {'text_color': LINK_COLOR, 'font': FONT_LINK, 'click_submits': True}
    layout = [
        [Sg.Text(f'Music Caster v{VERSION} by', font=FONT_NORMAL),
         Sg.Text(CONTACT_INFO, tooltip=t('Send me an email'), key='open_email', **link_params),
         Sg.Text(f'GitHub', **link_params, key='open_github')],
        [checkbox_col, right_settings_col] if qr_code else [checkbox_col],
        [Sg.Listbox(settings['music_folders'], size=(62, 5), select_mode=Sg.SELECT_MODE_EXTENDED, text_color=fg,
                    key='music_folders', background_color=bg, font=FONT_NORMAL, bind_return_key=True,
                    no_scrollbar=True),
         Sg.Column([
             [IconButton(X_ICON, 'remove_music_folder', t('remove selected folder'), bg)],
             [IconButton(PLUS_ICON, 'add_music_folder', t('add folder'), bg)]])]]
    return Sg.Tab(t('Settings'), layout, key='tab_settings')
