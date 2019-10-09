import PySimpleGUI as Sg
import os

# Styling
fg = '#aaaaaa'
bg = '#121212'
font_normal = 'SourceSans', 11
font_link = 'SourceSans', 11, 'underline'
button_color = ('black', '#4285f4')

UNFILLED_ICON = b'iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAQAAAD/5HvMAAAABGdBTUEAALGPC/xhBQAAACBjSFJN\nAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAAmJLR0QA/4ePzL8AAAAHdElN\nRQfjBw4ALiA+kkFLAAACWElEQVRo3u2ZsUsbURzHo2Bc0kkMDoYirRkcpEu7NtAubo7ZPXDo6qaL\nkyUIQtshkE6CkA79C4SqWIiLi5N2iBQ7WgRvUNvGj0OG/n737kLt9d476PuOvx9JPnn3e9/v3b1C\nwcvLy8srSQwR0CHEpi7pEDAUhzPBNq60zYS5Ou5w+kh6lQhwrUADHTgH6mig0DlQqIGErO7spN/1\nQB7IA3kg10DObnk8kAf6b4C44ZxTDmmzSp3JXPkQAF9o8oLh/AD1dcYalTwBAdzQ4lGegAB+sk4p\nT0AA35i3CVRkjClqLPKGI24ToN4x6sSHGGeB3Visw3875PcyRqb5EAN1xoxDp+Ypnwyk7zxzGh3M\n0TWQZhwCFQqMsWtcuEq2uyzkhB22WGE29oMjNI3xHrXlQ1024rB4xS9tAjaNsccmD2OQtObtOvU1\nDYqRL2hG3LtkEwjgM+XILOnxXrefZV95EtlxXRW7j7MBKlGlxhL79Mx3WxGkOdV9n7EPUabBlbFK\n+sJJ9/6RxpH+NFwrfDRmqagCRWbcaytOzXIkWBuq21auPWwlOqgrpGvpS0yr3ktLWcayWqNN1ZPb\nv5lFlh3TMv+pmqWeDBQW5ENTdj60RzUy3nLHbai7SnnRJrMzxgueq05Dxq7qHIlOPUunvpCrRFlZ\npbxob0V99Z7PMDEnZ4OiY0/19kVnRdQXRb2dGqgzOMvEeLMk6luiXpO3a6mBgsFArYQf3hH1KVE/\nTQlkHOBFdSx6VVE/Ubn/W+epgGKOOAecXvEgoV6UryT+EihMPAT28vLy8urrDgm99Mb0O5qlAAAA\nJXRFWHRkYXRlOmNyZWF0ZQAyMDE5LTA3LTE0VDAwOjQ2OjMyKzAwOjAwaWwEjwAAACV0RVh0ZGF0\nZTptb2RpZnkAMjAxOS0wNy0xNFQwMDo0NjozMiswMDowMBgxvDMAAAAASUVORK5CYII=\n'
FILLED_ICON = b'iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAQAAAD/5HvMAAAABGdBTUEAALGPC/xhBQAAACBjSFJN\nAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAAmJLR0QA/4ePzL8AAAAHdElN\nRQfjBw4ALiA+kkFLAAACxUlEQVRo3u2ZT0hUURSHn0bjxtpIYqCElLNwEW1yWYO1yF3L2fvARVs3\nqRtX2SAIJTFgK0HQRdJeaBSDaePGlYaoYUtD8C3ScvpaKHTOfe8NOu/fQPe3PGec+bz3nN+57z7H\nsbKysrIKEy24VPFIU8dUcWkJwulihay0Qpd/dbLDOUfSq4RL1nI10JfMgaoayMscyNNAQql2dtjv\nWiAL9N8AJdHfFigWoMvscXMAnTUb0G3G2GkioIuz0iDLTQR08acDVJoKyHEch2dsptX2pxyyxwaL\nTFKkOxQpx2tqKfsQAF8p84TWQKhH7KcPdK4DXtETgHSTj9kAAZwyx10fUivvsgIC+M007T6oseyA\nAL7z3IfkJgeUo4NeCozwhk3+hHzXLG3RV6kBH+IWw6wGYm2YRX71WmrYGOljKQDqgH71qWtX7bho\nw/Uhn3zf+IMBwwT2Ux0dDLHrQ+o3rLKW6iyjg1XfxqlaYiruLvPYpsICE9wPRLpO2VfebapLN5Pz\noV1mgrB4YZwfZ42TQKLGWGOeOwFIWsoqL3teatypTyiRM5DKhnu3qyNcCqPjM51GLenynlbZ5TRm\n2TceGB23q8buPZEbjA+onTwFRlkPcBTPQBpS2ffqcWAndh+ikxI/faukN0669y/pSLxMZrj28MFX\nSzk1UOSMm1LPcWcJOTXjxmAtqeyicu3W2K9jAj9cVEgn0pfoU7mnqQA5DuNqjeZVTrZ/Of4LK48t\n5vz/qaqlmhwoDMuHpuRu0NbIG+UtO25GnSrlpnUnd6V3xGOVKcmxqzJyvhcTvGPkSK4Sncoq5aa9\nFfHJyNdcx/VGx5rKrYvMhIiPiPhiZKBq/VkmyptREV8Q8YI8rkUGcusDzYX8cEXEe0V8LyKQ7wWe\nqS2Ry4v4tpr7/3QYCSjgFWedt1fcCInn5JVEg0Be6EtgKysrK6tz/QVPmZ3Bw5RmTgAAACV0RVh0\nZGF0ZTpjcmVhdGUAMjAxOS0wNy0xNFQwMDo0NjozMiswMDowMGlsBI8AAAAldEVYdGRhdGU6bW9k\naWZ5ADIwMTktMDctMTRUMDA6NDY6MzIrMDA6MDAYMbwzAAAAAElFTkSuQmCC\n'
WINDOW_ICON = b'iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAQAAAD/5HvMAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAAmJLR0QA/4ePzL8AAAAHdElNRQfjBxIQARbl3afoAAACwElEQVRo3u2ZPUxTURiGH2osS3UhNphADFE6MBgXGbVBB9kcu9OEwZVFYGESGxISJaRJnUhIygBxJ7EQTOrC0gkMKRgcMSTcQVDqdejg+c49t1HuXxPPe7fvu7336fl5v3PPASsrKysrX/VQpI6DG+N1Rp0iPSacfjZjRVGvTfq9rZMcThtJa6ViojguLkUJ9ClxoLoEchIHciSQmopTvu+1QBbovwGKYoJboFCA/qaPuwLostuAbjPNQTcBtddKY2x0E1Bbo9S6CwjgGY24gC444ZBdqsxRYMAXKc1rWnH7kIvLZ8o8IWWEesRR/EDt65hXDBqQbvI+GSAXlwsq3PUgpVhOCsjF5ScLZDxQ08kBubh85bkHqRgdUJo+hsgzyRsa/PJ51BK9IbTSFXzoFhNsGbF2PYN8OT5jHGbNAHXMiLjr2j/PuEBO/ZAPngd+Y1QzgaN4S8c4TQ/SiGaVrXhrWR9bno6TY2k+bCCHfWqsMst9I9J1yp7h3StmaSM6H2qyaMR6oa0fl7SVQKTG2GKFOwYkeZe0ylrUTn1OibSGVNbcOyOWcDGUjo9ktbEkh/eCyG7EUcu+8ECbcU1Rdu8pubHwgDLkyDPFjsFRHA1pXGTfic+Bg/B9KEuJ755Wkh2nuvcP4UgvozHGQdY9YyktCopa4+bFd9xlVE49oxXWkshWhWunwt+OMakgkM6FLw2L3NN4gGBG/GBF5NTpXw4fyGGPiuGfrgv3VgvKhPhoimwHbZucNrzVGbcoVpVqpw1Et6V3ymORKYmyq0qt74Uo9xhPRStlhVWqnfZWic8F3uY661Q6tkVuR8nMKvFJJV4NDFTvXMvU4T2lxFeVeF4s14ICFTsDVXxeXFPiQ0r8MCCQ5wBPv2FPyeWU+L6o+3/iJ4GADEecnU6vbvjE02JL4mpAjv8hsJWVlZUVAL8BFtCPUbUhaGYAAAAldEVYdGRhdGU6Y3JlYXRlADIwMTktMDctMThUMTU6NTg6MTArMDA6MDBEk3wFAAAAJXRFWHRkYXRlOm1vZGlmeQAyMDE5LTA3LTE4VDE1OjU4OjEwKzAwOjAwNc7EuQAAAABJRU5ErkJggg=='


def create_settings(version, music_directories, settings):
    layout = [
        [Sg.Text(f'Music Caster Version {version} by Elijah Lopez', text_color=fg, background_color=bg, font=font_normal)],
        [Sg.Text(f'Email:', text_color=fg, background_color=bg, font=font_normal),
         Sg.Text(f'elijahllopezz@gmail.com', text_color='#3ea6ff', background_color=bg, font=font_link, click_submits=True, key='email'),
         Sg.Button(button_text='Copy address', button_color=button_color, key='copy email', enable_events=True, font=font_normal)],
        [Sg.Checkbox('Auto Update', default=settings['auto update'], key='auto update', text_color=fg,
                     background_color=bg, font=font_normal, enable_events=True),
         Sg.Checkbox('Run on Startup', default=settings['run on startup'], key='run on startup', text_color=fg,
                     background_color=bg, font=font_normal, enable_events=True),
         Sg.Checkbox('Enable Notifications', default=settings['notifications'], key='notifications',
                     text_color=fg, background_color=bg, font=font_normal, enable_events=True),
         Sg.Checkbox('Shuffle Playlists', default=settings['shuffle_playlists'], key='shuffle_playlists',
                     text_color=fg, background_color=bg, font=font_normal, enable_events=True)],
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
                  font=font_normal, enable_events=True, readonly=True),
         Sg.Button(button_text='Edit', button_color=button_color, key='edit_pl', enable_events=True, font=font_normal),
         Sg.Button(button_text='Delete', button_color=button_color, key='del_pl', enable_events=True, font=font_normal),
         Sg.Button(button_text='Create New Playlist', button_color=button_color, key='create_pl', enable_events=True, font=font_normal)]]
    return layout


def playlist_editor(playlists, playlist_name=''):
    paths = playlists.get(playlist_name, [])
    songs = [
        f'{i+1}. {os.path.basename(path)}' for i, path in enumerate(paths)]
    layout = [[
        Sg.Text('Playlist name', text_color=fg,
                background_color=bg, font=font_normal),
        Sg.Input(playlist_name, key='playlist_name'),
        Sg.Submit('Save', button_color=button_color,
                  font=font_normal, pad=(('11px', '11px'), (0, 0))),
        Sg.Button('Cancel', key='Cancel', button_color=button_color, font=font_normal, enable_events=True)],
        [Sg.Frame('', [[Sg.FilesBrowse('Add files', key='Add files', button_color=button_color, font=font_normal, enable_events=True, pad=(('21px', 0), (5, 5)))],
                       [Sg.Button('Remove file', key='Remove file', button_color=button_color,
                                  font=font_normal, enable_events=True)]], background_color=bg, border_width=0),
         Sg.Listbox(songs, size=(41, 5), select_mode=Sg.SELECT_MODE_SINGLE, text_color=fg,
                    key='songs', background_color=bg, font=font_normal, enable_events=True),
         Sg.Frame('', [
             [Sg.Button('Move up', key='Move up', button_color=button_color, font=font_normal, enable_events=True)],
             [Sg.Button('Move down ', key='Move down', button_color=button_color, font=font_normal, enable_events=True)]
         ], background_color=bg, border_width=0)]]
    return layout


if __name__ == "__main__":
    import music_caster
