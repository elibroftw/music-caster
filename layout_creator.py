import PySimpleGUI as Sg
import os

fg = '#aaaaaa'
bg = '#121212'
font_normal = 'SourceSans', 11
font_link = 'SourceSans', 11, 'underline'
button_color = ('black', '#4285f4')


def create_settings(version, music_directories, settings):
    layout = [
        [Sg.Text(f'Music Caster Version {version} by Elijah Lopez', text_color=fg, background_color=bg,
                 font=font_normal)],
        [Sg.Text(f'Email:', text_color=fg, background_color=bg, font=font_normal),
         Sg.Text(f'elijahllopezz@gmail.com', text_color='#3ea6ff', background_color=bg, font=font_link,
                 click_submits=True, key='email'),
         Sg.Button(button_text='Copy address', button_color=button_color, key='copy email', enable_events=True,
                   font=font_normal)],
        [Sg.Checkbox('Auto Update', default=settings['auto update'], key='auto update', text_color=fg,
                     background_color=bg, font=font_normal, enable_events=True),
         Sg.Checkbox('Run on Startup', default=settings['run on startup'], key='run on startup', text_color=fg,
                     background_color=bg, font=font_normal, enable_events=True),
         Sg.Checkbox('Enable Notifications', default=settings['notifications'], key='notifications',
                     text_color=fg, background_color=bg, font=font_normal, enable_events=True)],
        # Sg.Checkbox('Shuffle Playlists', default=settings['shuffle_playlists'], key='shuffle_playlists',
        #              text_color=fg, background_color=bg, font=font_normal, enable_events=True)],
        [Sg.Slider((0, 100), default_value=settings['volume'], orientation='horizontal', key='volume',
                   tick_interval=5, enable_events=True, background_color='#4285f4', text_color='black',
                   size=(50, 15))],
        [Sg.Listbox(music_directories, size=(41, 5), select_mode=Sg.SELECT_MODE_SINGLE, text_color=fg,
                    key='music_dirs', background_color=bg, font=font_normal, enable_events=True),
         Sg.Frame('', [
             [Sg.Button('Remove Selected Folder', button_color=button_color, key='Remove Folder',
                        enable_events=True, font=font_normal)],
             [Sg.FolderBrowse('Add Folder', button_color=button_color, font=font_normal, enable_events=True)],
             [Sg.Button('Open settings.json', key='Open Settings', button_color=button_color, font=font_normal,
                        enable_events=True)]], background_color=bg, border_width=0)]]
    return layout


def create_timer(settings):
    layout = [
        [Sg.Checkbox('Shut off computer when timer runs out', default=settings['timer_shut_off_computer'],
                     key='shut_off', text_color=fg, background_color=bg, font=font_normal,
                     enable_events=True)],
        [Sg.Checkbox('Hibernate computer when timer runs out', default=settings['timer_hibernate_computer'],
                     key='hibernate', text_color=fg, background_color=bg, font=font_normal,
                     enable_events=True)],
        [Sg.Checkbox('Sleep computer when timer runs out', default=settings['timer_sleep_computer'],
                     key='sleep', text_color=fg, background_color=bg, font=font_normal,
                     enable_events=True)],
        [Sg.Text('Enter minutes', text_color=fg, background_color=bg, font=font_normal)],
        [Sg.Input(key='minutes'), Sg.Submit(button_color=button_color, font=font_normal)]]
    return layout


def playlist_selector(playlists):
    layout = [
        [Sg.Combo(values=list(playlists.keys()), size=(41, 5), text_color=fg, key='pl_selector', background_color=bg,
                  font=font_normal, enable_events=True),
         Sg.Button(button_text='Edit', button_color=button_color, key='edit_pl', enable_events=True,
                   font=font_normal),
         Sg.Button(button_text='Create New Playlist', button_color=button_color, key='create_pl', enable_events=True,
                   font=font_normal)]]
    return layout


def playlist_editor(playlists, playlist_name=''):
    paths = playlists.get(playlist_name, [])
    songs = [os.path.basename(path) for path in paths]
    layout = [[
        Sg.Text('Playlist name', text_color=fg, background_color=bg, font=font_normal),
        Sg.Input(playlist_name, key='playlist_name')],
        [Sg.Listbox(songs, size=(41, 5), select_mode=Sg.SELECT_MODE_SINGLE, text_color=fg,
                    key='music_dirs', background_color=bg, font=font_normal, enable_events=True),
         Sg.Frame('', [
             [Sg.Button('Move up', key='move_up', button_color=button_color,
                        font=font_normal, enable_events=True)],
             [Sg.Button('Move down', key='move_down', button_color=button_color,
                        font=font_normal, enable_events=True)],
             [Sg.FilesBrowse('Add Files', button_color=button_color, font=font_normal, enable_events=True)]
         ])],
        [Sg.Submit('Save', button_color=button_color, font=font_normal)]]
    return layout
