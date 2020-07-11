<h1 align="left">
<img width=30px src="https://raw.githubusercontent.com/elibroftw/music-caster/master/resources/Music%20Caster%20Icon.png" alt="Logo" style="vertical-align: bottom">
Music Caster</h1>

[![GitHub Releases](https://img.shields.io/github/downloads/elibroftw/music-caster/latest/total?color=blue&label=github%20downloads%40latest&style=for-the-badge)](https://github.com/elibroftw/music-caster/releases/latest)
[![Source Forge](https://img.shields.io/sourceforge/dt/music-caster?color=orange&label=SourceForge%20downloads&style=for-the-badge)](https://sourceforge.net/projects/music-caster/)

Music Caster is a music player which lets you cast your local music files to a Google Cast Device (Chromecast, Home, etc.).
If you enjoyed this product a lot feel free to donate at http://elopez.me/donate.

## [Download Here (Windows 64-bit)](https://github.com/elibroftw/music-caster/releases/latest)

## Demo

[![Watch the demo](https://img.youtube.com/vi/MtkhqV1w3WE/maxresdefault.jpg)](https://youtu.be/MtkhqV1w3WE)

## [Click Here For Screenshots](http://www.elopez.me/music-caster/)

## Usage
**TL;DR**:
When running the app for the first time, if you have music files in different folders, right click the tray icon and open settings.

On the first startup, the app will be in your hidden tray. You can move it onto the "Taskbar" and it'll stay there on future launches.
Right click the icon and then click Settings.
Add or remove music dirs. The home music directory is there by default.

When you click Play All, all the music from these directories are shuffled and played.

When you click Play File, you can select a file to play and then the music in your directories are shuffled into the music queue.

Music Caster supports media keys.

There is a web GUI accessible through the settings window (click or scan the QR code)

## Limitations and Known Issues
- For now, the local playback only supports MP3 files (you can still play other file types on your Google devices)
- [Roadmap](https://github.com/elibroftw/music-caster/projects/1)

## Data Collection / Privacy Policy
What is sent to me when an error is encountered?
```JS
// As seen in handle_exception(exception)
'TIME': current_time,
'VERSION': VERSION,
'OS': platform.platform(),
'EXCEPTION TYPE': exc_type.__name__,  // error name
'LINE': exc_tb.tb_lineno,             // error location
'FATAL': restart_program,             // if the error crashed the program
'TRACEBACK': trace_back_msg,          // error message
'MAC': MAC                            // error unqiueness
```
In addition, I collect MAC and IP addresses in a Google Excel Sheet.
Only I have access to this data, I will NEVER give it to anyone else.
- MAC so that I know how many users (450+)
- IP because I can do something [cool](https://github.com/elibroftw/music-caster/wiki)

## UI Keyboard Shortcuts
I love keyboard shortcuts, they make us more productive.

| **Shortcut** | **Window** | **Behaviour**
| ------------ |----------- | -------------
| Ctrl + Shift + Alt + M | Global | Activate Main Window
| Esc | ALL | Close Window |
| Scroll | Main | Volume and Progress Bar
| A | Main | Decrease Volume by 5%
| D | Main | Increase Volume by 5%
| # | Main | Set Volume to # * 10%
| K / \<Space\> | Main | Pause / Resume / Start Playing 
| J | Main | Rewind 5 seconds
| L | Main | Fast-forward 5 seconds
| Ctrl + R | Main | Cycle Repeat
| Ctrl + M | Main | Mute
| Ctrl + 1 | Main | Go to Tab 1 (Queue)
| Ctrl + 2 | Main | Go to Tab 2 (Timer)
| Ctrl + 3 | Main | Go to Tab 3 (Settings)
| Ctrl + N | Playlist Selector | Create New Playlist
| Ctrl + E | Playlist Selector | Edit Selected Playlist
| Del | Playlist Selector | Delete Selected Playlist
| Up / Down | Playlist Selector | Change Selected Playlist
| Ctrl + S | Playlist Editor | Save and Quit
| Ctrl + F | Playlist Editor | Add Songs
| Ctrl + R | Playlist Editor | Remove Song
| Ctrl + U | Playlist Editor | Move Song Up
| Ctrl + D | Playlist Editor | Move Song Down


## Settings.json Guide
- Music Caster will detect changes within 10 seconds of editing `settings.json`
  - Caveat: any color code changes requires a restart
- The music directories is a list of valid directory paths
  - The first path is the default directory MC opens when you click "Play File"
- The playlist setting follows the convention `{'PLAYLIST NAME': ['list of paths to files']}`
- Some settings are there for the future and have no effect

## Development Guide
1. Have Python >=3.6.8 installed
2. `pip install -r requirements.txt`
3. Make sure Python scripts folder is on PATH
4. Have Inno Setup installed and `C:\Program Files (x86)\Inno Setup 6\` on PATH
5. run `build` or `build.py`
[Detailed guide](https://github.com/elibroftw/music-caster/wiki/Development-Guide)

## Credits
- default album art made by [ivke32](https://pixabay.com/users/ivke32-2526695/?utm_source=link-attribution&amp;utm_medium=referral&amp;utm_campaign=image&amp;utm_content=1413583) from [Pixabay](https://pixabay.com/?utm_source=link-attribution&amp;utm_medium=referral&amp;utm_campaign=image&amp;utm_content=1413583)
- speaker icon in main window made by [Naomi Atkinson](https://thenounproject.com/naomiatkinson/) from [The Noun Project](https://thenounproject.com/term/speaker/5609/) and modified by me
- repeat icon in main window made by [Brandy Bora](https://thenounproject.com/brandy.bora) from [The Noun Project](https://thenounproject.com/search/?q=repeat&i=1555394) and modified by me
- folder icon in main window by [Landan Lloyd](https://thenounproject.com/landan/) from [The Noun Project](https://thenounproject.com/term/folder/1352565/)
