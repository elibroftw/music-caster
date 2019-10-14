import PySimpleGUI as Sg
import os


# FOR LATER USE...?
# C++ JPG TO PNG
# https://stackoverflow.com/questions/13739463/how-do-you-convert-a-jpg-to-png-in-c-on-windows-8

# Styling
text_color = fg = '#aaaaaa'
bg = '#121212'
font_normal = 'SourceSans', 11
font_link = 'SourceSans', 11, 'underline'
button_color = ('black', '#4285f4')
Sg.SetOptions(button_color=button_color, scrollbar_color='#121212', background_color=bg, element_background_color=bg,
              progress_meter_color=('#4285f4', '#D3D3D3'))
UNFILLED_ICON = b'iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAQAAAD/5HvMAAAABGdBTUEAALGPC/xhBQAAACBjSFJN\nAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAAmJLR0QA/4ePzL8AAAAHdElN\nRQfjBw4ALiA+kkFLAAACWElEQVRo3u2ZsUsbURzHo2Bc0kkMDoYirRkcpEu7NtAubo7ZPXDo6qaL\nkyUIQtshkE6CkA79C4SqWIiLi5N2iBQ7WgRvUNvGj0OG/n737kLt9d476PuOvx9JPnn3e9/v3b1C\nwcvLy8srSQwR0CHEpi7pEDAUhzPBNq60zYS5Ou5w+kh6lQhwrUADHTgH6mig0DlQqIGErO7spN/1\nQB7IA3kg10DObnk8kAf6b4C44ZxTDmmzSp3JXPkQAF9o8oLh/AD1dcYalTwBAdzQ4lGegAB+sk4p\nT0AA35i3CVRkjClqLPKGI24ToN4x6sSHGGeB3Visw3875PcyRqb5EAN1xoxDp+Ypnwyk7zxzGh3M\n0TWQZhwCFQqMsWtcuEq2uyzkhB22WGE29oMjNI3xHrXlQ1024rB4xS9tAjaNsccmD2OQtObtOvU1\nDYqRL2hG3LtkEwjgM+XILOnxXrefZV95EtlxXRW7j7MBKlGlxhL79Mx3WxGkOdV9n7EPUabBlbFK\n+sJJ9/6RxpH+NFwrfDRmqagCRWbcaytOzXIkWBuq21auPWwlOqgrpGvpS0yr3ktLWcayWqNN1ZPb\nv5lFlh3TMv+pmqWeDBQW5ENTdj60RzUy3nLHbai7SnnRJrMzxgueq05Dxq7qHIlOPUunvpCrRFlZ\npbxob0V99Z7PMDEnZ4OiY0/19kVnRdQXRb2dGqgzOMvEeLMk6luiXpO3a6mBgsFArYQf3hH1KVE/\nTQlkHOBFdSx6VVE/Ubn/W+epgGKOOAecXvEgoV6UryT+EihMPAT28vLy8urrDgm99Mb0O5qlAAAA\nJXRFWHRkYXRlOmNyZWF0ZQAyMDE5LTA3LTE0VDAwOjQ2OjMyKzAwOjAwaWwEjwAAACV0RVh0ZGF0\nZTptb2RpZnkAMjAxOS0wNy0xNFQwMDo0NjozMiswMDowMBgxvDMAAAAASUVORK5CYII=\n'
FILLED_ICON = b'iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAQAAAD/5HvMAAAABGdBTUEAALGPC/xhBQAAACBjSFJN\nAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAAmJLR0QA/4ePzL8AAAAHdElN\nRQfjBw4ALiA+kkFLAAACxUlEQVRo3u2ZT0hUURSHn0bjxtpIYqCElLNwEW1yWYO1yF3L2fvARVs3\nqRtX2SAIJTFgK0HQRdJeaBSDaePGlYaoYUtD8C3ScvpaKHTOfe8NOu/fQPe3PGec+bz3nN+57z7H\nsbKysrIKEy24VPFIU8dUcWkJwulihay0Qpd/dbLDOUfSq4RL1nI10JfMgaoayMscyNNAQql2dtjv\nWiAL9N8AJdHfFigWoMvscXMAnTUb0G3G2GkioIuz0iDLTQR08acDVJoKyHEch2dsptX2pxyyxwaL\nTFKkOxQpx2tqKfsQAF8p84TWQKhH7KcPdK4DXtETgHSTj9kAAZwyx10fUivvsgIC+M007T6oseyA\nAL7z3IfkJgeUo4NeCozwhk3+hHzXLG3RV6kBH+IWw6wGYm2YRX71WmrYGOljKQDqgH71qWtX7bho\nw/Uhn3zf+IMBwwT2Ux0dDLHrQ+o3rLKW6iyjg1XfxqlaYiruLvPYpsICE9wPRLpO2VfebapLN5Pz\noV1mgrB4YZwfZ42TQKLGWGOeOwFIWsoqL3teatypTyiRM5DKhnu3qyNcCqPjM51GLenynlbZ5TRm\n2TceGB23q8buPZEbjA+onTwFRlkPcBTPQBpS2ffqcWAndh+ikxI/faukN0669y/pSLxMZrj28MFX\nSzk1UOSMm1LPcWcJOTXjxmAtqeyicu3W2K9jAj9cVEgn0pfoU7mnqQA5DuNqjeZVTrZ/Of4LK48t\n5vz/qaqlmhwoDMuHpuRu0NbIG+UtO25GnSrlpnUnd6V3xGOVKcmxqzJyvhcTvGPkSK4Sncoq5aa9\nFfHJyNdcx/VGx5rKrYvMhIiPiPhiZKBq/VkmyptREV8Q8YI8rkUGcusDzYX8cEXEe0V8LyKQ7wWe\nqS2Ry4v4tpr7/3QYCSjgFWedt1fcCInn5JVEg0Be6EtgKysrK6tz/QVPmZ3Bw5RmTgAAACV0RVh0\nZGF0ZTpjcmVhdGUAMjAxOS0wNy0xNFQwMDo0NjozMiswMDowMGlsBI8AAAAldEVYdGRhdGU6bW9k\naWZ5ADIwMTktMDctMTRUMDA6NDY6MzIrMDA6MDAYMbwzAAAAAElFTkSuQmCC\n'
WINDOW_ICON = b'iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAQAAAD/5HvMAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAAmJLR0QA/4ePzL8AAAAHdElNRQfjBxIQARbl3afoAAACwElEQVRo3u2ZPUxTURiGH2osS3UhNphADFE6MBgXGbVBB9kcu9OEwZVFYGESGxISJaRJnUhIygBxJ7EQTOrC0gkMKRgcMSTcQVDqdejg+c49t1HuXxPPe7fvu7336fl5v3PPASsrKysrX/VQpI6DG+N1Rp0iPSacfjZjRVGvTfq9rZMcThtJa6ViojguLkUJ9ClxoLoEchIHciSQmopTvu+1QBbovwGKYoJboFCA/qaPuwLostuAbjPNQTcBtddKY2x0E1Bbo9S6CwjgGY24gC444ZBdqsxRYMAXKc1rWnH7kIvLZ8o8IWWEesRR/EDt65hXDBqQbvI+GSAXlwsq3PUgpVhOCsjF5ScLZDxQ08kBubh85bkHqRgdUJo+hsgzyRsa/PJ51BK9IbTSFXzoFhNsGbF2PYN8OT5jHGbNAHXMiLjr2j/PuEBO/ZAPngd+Y1QzgaN4S8c4TQ/SiGaVrXhrWR9bno6TY2k+bCCHfWqsMst9I9J1yp7h3StmaSM6H2qyaMR6oa0fl7SVQKTG2GKFOwYkeZe0ylrUTn1OibSGVNbcOyOWcDGUjo9ktbEkh/eCyG7EUcu+8ECbcU1Rdu8pubHwgDLkyDPFjsFRHA1pXGTfic+Bg/B9KEuJ755Wkh2nuvcP4UgvozHGQdY9YyktCopa4+bFd9xlVE49oxXWkshWhWunwt+OMakgkM6FLw2L3NN4gGBG/GBF5NTpXw4fyGGPiuGfrgv3VgvKhPhoimwHbZucNrzVGbcoVpVqpw1Et6V3ymORKYmyq0qt74Uo9xhPRStlhVWqnfZWic8F3uY661Q6tkVuR8nMKvFJJV4NDFTvXMvU4T2lxFeVeF4s14ICFTsDVXxeXFPiQ0r8MCCQ5wBPv2FPyeWU+L6o+3/iJ4GADEecnU6vbvjE02JL4mpAjv8hsJWVlZUVAL8BFtCPUbUhaGYAAAAldEVYdGRhdGU6Y3JlYXRlADIwMTktMDctMThUMTU6NTg6MTArMDA6MDBEk3wFAAAAJXRFWHRkYXRlOm1vZGlmeQAyMDE5LTA3LTE4VDE1OjU4OjEwKzAwOjAwNc7EuQAAAABJRU5ErkJggg=='


def create_main_gui(music_queue, done_queue, playing_status, metadata='Nothing Playing', album_cover_data=None, current_progress=0):
    # PLANNING:
    # Title: Music Caster
    # Volume control
    # Show playing queue with controls for moving songs around
    # Show Current playing with it's album art, use default album art if one does not exist
    # Have a scrubber (if the scrubber is 1 sec off from variable, then call play_file() with new value)
    if playing_status == 'PLAYING': pause_play_text = 'Pause'
    elif playing_status == 'PAUSED': pause_play_text = 'Resume'
    else: pause_play_text = 'N/A'
    # Sg.Button('Shuffle', key='Shuffle'),
    col = [[Sg.Button('Prev', key='Prev'), Sg.Button(pause_play_text, key='Pause/Resume'),
            Sg.Button('Next', key='Next'), Sg.Button('Repeat', key='Repeat')]]
    # TODO: use images
    tab1_layout = [[Sg.Text(metadata, font=font_normal, text_color=fg, background_color=bg, key='now_playing',
                            size=(55, 0))],
                   [Sg.Image(data=album_cover_data, pad=(0, 0), size=(0, 150), key='album_cover')] if album_cover_data else [],
                   [Sg.Column(col, justification='center')],
                   # size = (4, 0)
                   [Sg.Text('00:00', font=font_normal, text_color=fg, background_color=bg, key='time_elapsed'),
                    Sg.ProgressBar(100, orientation='h', size=(30, 20), key='progressbar', style='clam'),
                    Sg.Text('00:00', font=font_normal, text_color=fg, background_color=bg, key='time_left')]]
    tab2_layout = [[]]  # should include listbox of songs
    layout = [[Sg.TabGroup([[Sg.Tab('Now Playing', tab1_layout, background_color=bg),
                             Sg.Tab('Music Queue', tab2_layout, background_color=bg)]], background_color=bg)]]
    return layout


def create_settings(version, music_directories, settings):
    layout = [
        [Sg.Text(f'Music Caster Version {version} by Elijah Lopez', text_color=fg, background_color=bg, font=font_normal)],
        [Sg.Text(f'Email:', text_color=fg, background_color=bg, font=font_normal),
         Sg.Text(f'elijahllopezz@gmail.com', text_color='#3ea6ff', background_color=bg, font=font_link, click_submits=True, key='email'),
         Sg.Button(button_text='Copy address', key='copy email', enable_events=True, font=font_normal)],
        [Sg.Checkbox('Auto Update', default=settings['auto update'], key='auto update', text_color=fg,
                     background_color=bg, font=font_normal, enable_events=True),
         Sg.Checkbox('Run on Startup', default=settings['run on startup'], key='run on startup', text_color=fg,
                     background_color=bg, font=font_normal, enable_events=True),
         Sg.Checkbox('Enable Notifications', default=settings['notifications'], key='notifications',
                     text_color=fg, background_color=bg, font=font_normal, enable_events=True),
         Sg.Checkbox('Shuffle Playlists', default=settings['shuffle_playlists'], key='shuffle_playlists',
                     text_color=fg, background_color=bg, font=font_normal, enable_events=True)],
        [Sg.Slider((0, 100), default_value=settings['volume'], orientation='h', key='volume', tick_interval=5,
                   enable_events=True, background_color='#4285f4', text_color='black', size=(50, 15))],
        [Sg.Listbox(music_directories, size=(41, 5), select_mode=Sg.SELECT_MODE_SINGLE, text_color=fg,
                    key='music_dirs', background_color=bg, font=font_normal, enable_events=True),
         Sg.Frame('', [
             [Sg.Button('Remove Selected Folder', key='Remove Folder',
                        enable_events=True, font=font_normal)],
             [Sg.FolderBrowse('Add Folder', font=font_normal, enable_events=True)],
             [Sg.Button('Open settings.json', key='Open Settings', font=font_normal,
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
        [Sg.Input(key='minutes'), Sg.Submit(font=font_normal)]]
    return layout


def playlist_selector(playlists):
    layout = [
        [Sg.Combo(values=list(playlists.keys()), size=(41, 5), key='pl_selector', background_color=bg,
                  font=font_normal, enable_events=True, readonly=True),
         Sg.Button(button_text='Edit', key='edit_pl', enable_events=True, font=font_normal),
         Sg.Button(button_text='Delete', key='del_pl', enable_events=True, font=font_normal),
         Sg.Button(button_text='Create New Playlist', key='create_pl', enable_events=True, font=font_normal)]]
    return layout


def playlist_editor(playlists, playlist_name=''):
    paths = playlists.get(playlist_name, [])
    songs = [
        f'{i+1}. {os.path.basename(path)}' for i, path in enumerate(paths)]
    layout = [[
        Sg.Text('Playlist name', text_color=fg,
                background_color=bg, font=font_normal),
        Sg.Input(playlist_name, key='playlist_name'),
        Sg.Submit('Save', font=font_normal, pad=(('11px', '11px'), (0, 0))),
        Sg.Button('Cancel', key='Cancel', font=font_normal, enable_events=True)],
        [Sg.Frame('', [[Sg.FilesBrowse('Add files', key='Add files', font=font_normal, enable_events=True, pad=(('21px', 0), (5, 5)))],
                       [Sg.Button('Remove file', key='Remove file',
                                  font=font_normal, enable_events=True)]], background_color=bg, border_width=0),
         Sg.Listbox(songs, size=(41, 5), select_mode=Sg.SELECT_MODE_SINGLE, text_color=fg,
                    key='songs', background_color=bg, font=font_normal, enable_events=True),
         Sg.Frame('', [
             [Sg.Button('Move up', key='Move up', font=font_normal, enable_events=True)],
             [Sg.Button('Move down ', key='Move down', font=font_normal, enable_events=True)]
         ], background_color=bg, border_width=0)]]
    return layout


if __name__ == "__main__":
    # TESTS
    import time
    metadata = 'Gabriel & Dresden - This Love Kills Me (Gabriel & Dresden Club Mix - Above & Beyond Respray)'
    music_queue = [r"C:\Users\maste\Music\Adam K & Soha - Twilight.mp3",
                   r"C:\Users\maste\Music\Arkham Knights - Knightvision.mp3"]
    done_queue = [r"C:\Users\maste\Music\Afrojack, Eva Simons - Take Over Control.mp3",
                  r"C:\Users\maste\Music\Alex H - And There I Was.mp3"]
    p_status = 'NOT_PLAYING'  # PLAYING, PAUSED
    main_window = Sg.Window('Music Caster', create_main_gui(music_queue, done_queue, 'NOT_PLAYING', metadata),
                            background_color=bg, icon=WINDOW_ICON, return_keyboard_events=True, use_default_focus=False)
    main_last_event = ''
    update_times = 0
    progress_start = 0
    start = time.time()
    progress_bar = main_window.FindElement('progressbar')
    # main gui test for max of 1 minute
    while time.time() - start < 60:
        main_event, main_values = main_window.Read(timeout=5)
        if main_event is None:
            main_active = False
            main_window.CloseNonBlocking()
            break
        if main_event in {'q', 'Q'} or main_event == 'Escape:27' and main_last_event != 'Add Folder':
            main_active = False
            main_window.CloseNonBlocking()
            break
        if time.time() - progress_start > 1.5:
            progress_bar.UpdateBar(10 * (min(10, update_times)))
            update_times += 1
            progress_start = time.time()
        main_last_event = main_event
