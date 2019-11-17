import PySimpleGUI as Sg
import os

# TODO: C++ JPG TO PNG
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
WINDOW_ICON = b'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'
NEXT_BUTTON_IMG = b'iVBORw0KGgoAAAANSUhEUgAAABkAAAAZCAYAAADE6YVjAAABS2lUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNS42LWMxNDIgNzkuMTYwOTI0LCAyMDE3LzA3LzEzLTAxOjA2OjM5ICAgICAgICAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIi8+CiA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgo8P3hwYWNrZXQgZW5kPSJyIj8+nhxg7wAAAepJREFUSIm1lr9r6lAUxz9ppRpBWrL5BnHRSZ07OUjHbu3gakenIgnuOri4OigiiCAEsZ1cHQqF/gFmUxDhvUFwiYoZ/PGG9xKaPvs0tvlC4J57D+eTc3LuvREkSfoJBHBPcw/ww0UAQMADzPmbSTKZ5OXl5aRIXq+XUChk2dvtltFoBDAXJEnSTchsNqPRaKAoimNIIpGg3+9b9mKxIBwOA8zP3jtut1seHh54e3vj+vraEUQQBNvj9/utNRtkuVwCEIlE6PV6lMvloyG73c5mr1ar/RBBEGyOmUyGwWBAKpU6GrZPZ4ccgsEgnU6HSqWCz+dzB2IqnU6jaRq3t7fuQQCurq5oNpvUajUuLy/dgZi6u7tD0zTu7++tOY/H870QAFEUqVarqKpKNBpF1/V/OuzLEFM3Nzc8Pj5iGAabzcYdSKlUIpvNcnFx8WnJPi/kAb2+vpLL5RgOhwD/bYSTIPl8nnq9bpv7rFSOIf1+H0VRGI/Hjl7qKMh6vUaWZVqtlqPgpg5++F6vRzwePxkAHzJ53+e6riPLMt1u9+TgpmyZBAJ/rnpVVYnFYl8CnJ+fW2NbJpPJhGKxyNPTk+OgH/eIKIr7IYVCgefnZ8cAgOl0SrvdtmzDMKyxIEnS/gPnG+UBfuHyf9dvmm+anYtjY5UAAAAASUVORK5CYII='
PREVIOUS_BUTTON_IMG = b'iVBORw0KGgoAAAANSUhEUgAAABkAAAAZCAYAAADE6YVjAAABS2lUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNS42LWMxNDIgNzkuMTYwOTI0LCAyMDE3LzA3LzEzLTAxOjA2OjM5ICAgICAgICAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIi8+CiA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgo8P3hwYWNrZXQgZW5kPSJyIj8+nhxg7wAAAdhJREFUSIm1lj2vKVEUhp8z0VLIiMRXQSPxUY2oRCGiJUq1QiIRiZbaUWgEvYbePyAamaBAh2bOVUg0EhqJ21xzMzfHdUbMm0wys9Ze69lv9sze82G1Wr8AM8bpZAIcBgIAzCbgBJjtdjsWi0XNXC4XFEV5qavb7cbj8TCZTOCPEwBKpRLZbFYdKMsyuVxON8Dj8dDv91EU5Q5BuCftdjuiKKqXy+XSDSgUCsznc/x+P8fjUY2rTs7ns6bgdDr9uLnP56PVahGNRtXY9XpV74XvivSoUqkwnU41gH9leph5okAgQKfTIRgMPh37kpNarcZoNPoRAHQ6kSSJbreL1+vVNamHEEHQmqzX6+TzeV3Nn0Ku1yuCIJBIJGg2mzgcr28MDyGKohAOhxkMBi83v+vhwrvdbhaLBZlMhu12awzkviaj0YhIJEK73X4/5Ha7aZ5rtRrJZJLlcvk+yHeazWbE43EajYZxkLs+Pz+JxWLIsmwcBGC9XpNKpahWq8ZB7up0OkiSxHg8Ng4CsNvtSKfTlMtl9YUxmf5+girEZrNpCp1Op25Yr9cjFAqxWq0QRVGNq7jhcMjhcFATm81GNwRgv99TLBY1J+uH1Wq9/afmLTIBvzD4v+s3geuMP4PEmxwAAAAASUVORK5CYII='
PLAY_BUTTON_IMG = b'iVBORw0KGgoAAAANSUhEUgAAABkAAAAZCAYAAADE6YVjAAABS2lUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNS42LWMxNDIgNzkuMTYwOTI0LCAyMDE3LzA3LzEzLTAxOjA2OjM5ICAgICAgICAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIi8+CiA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgo8P3hwYWNrZXQgZW5kPSJyIj8+nhxg7wAAAPFJREFUSIm1lrFthTAYBu890b7GuMooMAMWzALjgGABU8EIsEnSuKREIqksISUQg5+vNfrvu46HEOITeBGOJQI+AgoAXk9gCSxZnkcvbdsipXyL5VCilGKaJvI8DycBkFLSNI131anE4lvlJAG/KmeJRSnFPM8URRFOAhDHMXVd03WdU9UtiSXLMqcqLwm4VXlLLGdVb5MAbNvGuq7hJH3fk6YpwzD8eot8jxtjqKrqz+MWrxKt9eH6PbdKjDGUZck4jk7fXy7RWpMkibMALpRcXb/HqeTO+j2nJT7r9xyW+K7f8xBCfHtf+YcI+CLwf9cPX0FmElVF/McAAAAASUVORK5CYII='
PAUSE_BUTTON_IMG = b'iVBORw0KGgoAAAANSUhEUgAAABkAAAAZCAYAAADE6YVjAAABS2lUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNS42LWMxNDIgNzkuMTYwOTI0LCAyMDE3LzA3LzEzLTAxOjA2OjM5ICAgICAgICAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIi8+CiA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgo8P3hwYWNrZXQgZW5kPSJyIj8+nhxg7wAAAGdJREFUSInt1jEKgDAMheG/oWs7pJv3v1cn3bKYCziLgihkEPK2hAdfxhRVXYFGXLwCSyAA0ATwYMTr3dbMTvMY49LpvTPnfOwByNfz3iSRRBJJJJFEfoMUVd0J/lYkGABoFdiCIT8AdVMOh/30v2kAAAAASUVORK5CYII='
# TODO: right click menus for list boxes


def create_songs_list(music_queue, done_queue, next_queue):
    # TODO: use metadata and song names or just one artist name
    """:returns the formatted song queue, and the selected value (currently playing)"""
    songs = []
    dq_len = len(done_queue)
    mq_start = len(next_queue) + 1
    selected_value = None
    # format: Index. Artists - Song Name
    for i, path in enumerate(done_queue):
        base = os.path.basename(path)
        base = os.path.splitext(base)[0]
        formatted_item = f'-{dq_len - i}. {base}'
        songs.append(formatted_item)
    if music_queue:
        base = os.path.basename(music_queue[0])
        base = os.path.splitext(base)[0]
        formatted_item = f' {0}. {base}'
        songs.append(formatted_item)
        selected_value = formatted_item
    for i, path in enumerate(next_queue):
        base = os.path.basename(path)
        base = os.path.splitext(base)[0]
        formatted_item = f' {i + 1}. {base}'
        songs.append(formatted_item)
    for i, path in enumerate(music_queue[1:]):
        base = os.path.basename(path)
        base = os.path.splitext(base)[0]
        formatted_item = f' {i + mq_start}. {base}'
        songs.append(formatted_item)
    return songs, selected_value


def create_main_gui(music_queue, done_queue, next_queue, playing_status,
                    now_playing_text='Nothing Playing', album_cover_data=None):
    # PLANNING:
    # Title: Music Caster
    # Volume control
    # Show playing queue with controls for moving songs around
    # Show Current playing with it's album art, use default album art if one does not exist
    # Have a scrubber (if the scrubber is 1 sec off from variable, then call play_file() with new value)
    pause_resume_img = PAUSE_BUTTON_IMG if playing_status == 'PLAYING' else PLAY_BUTTON_IMG
    # Sg.Button('Shuffle', key='Shuffle'),
    music_controls = [[Sg.Button(key='Prev', image_data=PREVIOUS_BUTTON_IMG),
                       Sg.Button(key='Pause/Resume', image_data=pause_resume_img, size=(10, 10)),
                       Sg.Button(key='Next', image_data=NEXT_BUTTON_IMG), Sg.Button('Repeat', key='Repeat')]]
    # TODO: use images
    progress_bar_layout = [[Sg.Text('00:00', font=font_normal, text_color=fg, background_color=bg, key='time_elapsed'),
                            Sg.Slider(range=(0, 100), orientation='h', size=(30, 10), key='progressbar', enable_events=True,
                                      relief=Sg.RELIEF_FLAT, background_color='#4285f4', disable_number_display=True),
                            # Sg.ProgressBar(100, orientation='h', size=(30, 20), key='progressbar', style='clam'),
                            Sg.Text('00:00', font=font_normal, text_color=fg, background_color=bg, key='time_left')]]
    
    # Now Playing layout
    tab1_layout = [[Sg.Text(now_playing_text, font=font_normal, text_color=fg, background_color=bg, key='now_playing',
                            size=(55, 0))],
                   [Sg.Image(data=album_cover_data, pad=(0, 0), size=(0, 150), key='album_cover')] if album_cover_data else [],
                   [Sg.Column(music_controls, justification='center')],
                   [Sg.Column(progress_bar_layout, justification='center')]]
    # Music Queue layout
    songs, selected_value = create_songs_list(music_queue, done_queue, next_queue)
    tab2_layout = [[
        Sg.Listbox(songs, default_values=selected_value, size=(45, 5), select_mode=Sg.SELECT_MODE_SINGLE, text_color=fg,
                   key='music_queue', background_color=bg, font=font_normal, enable_events=True),
    ]]
    col_3 = [
        [Sg.Button()],
        [Sg.Button()],
        [Sg.Button()],
        [Sg.Button()]
    ]
    # TODO: move up, move down, clear, add file, add to up next, remove in a Column
    layout = [[Sg.TabGroup([[Sg.Tab('Now Playing', tab1_layout, background_color=bg),
                             Sg.Tab('Music Queue', tab2_layout, background_color=bg)]])]]
    return layout


def create_settings(version, music_directories, settings):
    layout = [
        [Sg.Text(f'Music Caster Version {version} by Elijah Lopez', text_color=fg, background_color=bg, font=font_normal)],
        [Sg.Text('Email:', text_color=fg, background_color=bg, font=font_normal),
         Sg.Text('elijahllopezz@gmail.com', text_color='#3ea6ff', background_color=bg, font=font_link, click_submits=True, key='email'),
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
                   enable_events=True, background_color='#4285f4', text_color='black', size=(53, 15))],
        [Sg.Listbox(music_directories, size=(41, 5), select_mode=Sg.SELECT_MODE_SINGLE, text_color=fg,
                    key='music_dirs', background_color=bg, font=font_normal, enable_events=True, no_scrollbar=True),
         Sg.Frame('', [
             [Sg.Button('Remove Selected Folder', key='Remove Folder', enable_events=True, font=font_normal)],
             [Sg.FolderBrowse('Add Folder', font=font_normal, enable_events=True)],
             [Sg.Button('Open settings.json', key='Open Settings', font=font_normal, enable_events=True)]], background_color=bg, border_width=0)]]
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
    playlists = list(playlists.keys())
    layout = [
        [Sg.Combo(values=playlists, size=(41, 5), key='pl_selector', background_color=bg,
                  font=font_normal, enable_events=True, readonly=True, default_value=playlists[0] if playlists else None),
         Sg.Button(button_text='Edit', key='edit_pl', enable_events=True, font=font_normal),
         Sg.Button(button_text='Delete', key='del_pl', enable_events=True, font=font_normal),
         Sg.Button(button_text='New', key='create_pl', enable_events=True, font=font_normal)]]
    return layout


def playlist_editor(initial_folder, playlists, playlist_name=''):
    paths = playlists.get(playlist_name, [])
    songs = [
        f'{i+1}. {os.path.basename(path)}' for i, path in enumerate(paths)]
    layout = [[
        Sg.Text('Playlist name', text_color=fg,
                background_color=bg, font=font_normal),
        Sg.Input(playlist_name, key='playlist_name'),
        Sg.Submit('Save', font=font_normal, pad=(('11px', '11px'), (0, 0))),
        Sg.Button('Cancel', key='Cancel', font=font_normal, enable_events=True)],
        [Sg.Frame('', [[Sg.FilesBrowse('Add songs', key='Add songs', file_types=(('Audio Files', '*.mp3'),), pad=(('21px', 0), (5, 5)), initial_folder=initial_folder, font=font_normal, enable_events=True)],
                       [Sg.Button('Remove song', key='Remove song', font=font_normal, enable_events=True)]], background_color=bg, border_width=0),
         Sg.Listbox(songs, size=(41, 5), select_mode=Sg.SELECT_MODE_SINGLE, text_color=fg,
                    key='songs', background_color=bg, font=font_normal, enable_events=True),
         Sg.Frame('', [
             [Sg.Button('Move up', key='Move up', font=font_normal, enable_events=True)],
             [Sg.Button('Move down ', key='Move down', font=font_normal, enable_events=True)]
         ], background_color=bg, border_width=0)]]
    return layout


if __name__ == '__main__':
    # TESTS
    import time
    metadata = 'Gabriel & Dresden - This Love Kills Me (Gabriel & Dresden Club Mix - Above & Beyond Respray)'
    mq = [r"C:\Users\maste\Music\Adam K & Soha - Twilight.mp3",
                   r"C:\Users\maste\Music\Arkham Knights - Knightvision.mp3"]
    dq = [r"C:\Users\maste\Music\Afrojack, Eva Simons - Take Over Control.mp3",
                  r"C:\Users\maste\Music\Alex H - And There I Was.mp3"]
    p_status = 'NOT_PLAYING'  # PLAYING, PAUSED
    main_window = Sg.Window('Music Caster', create_main_gui(mq, dq, 'NOT_PLAYING', metadata),
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
        elif main_event != '__TIMEOUT__': print(main_event)
        if time.time() - progress_start > 1.5:
            progress_bar.Update(value=10 * (min(10, update_times)))
            # progress_bar.UpdateBar(10 * (min(10, update_times)))
            update_times += 1
            progress_start = time.time()
        main_last_event = main_event
