<h1 align="left">
<img width=30px src="https://raw.githubusercontent.com/elibroftw/music-caster/master/resources/Music%20Caster%20Icon.png" alt="Logo" style="vertical-align: bottom">
Music Caster</h1>

[![GitHub Releases](https://img.shields.io/github/downloads/elibroftw/music-caster/latest/total?color=blue&label=github%20downloads%40latest&style=for-the-badge)](https://github.com/elibroftw/music-caster/releases/latest)
[![Source Forge](https://img.shields.io/sourceforge/dt/music-caster?color=orange&label=SourceForge%20downloads&style=for-the-badge)](https://sourceforge.net/projects/music-caster/)

Music Caster is a music player which lets you cast your local music files to a Google Cast Device (Chromecast, Home, etc.)

## [Download Here (Windows 64-bit)](https://github.com/elibroftw/music-caster/releases/latest)

Click the image below for a video demo.

[![demo link](https://i3.ytimg.com/vi/y0fWPyhNSB0/maxresdefault.jpg)](https://www.youtube.com/watch?v=y0fWPyhNSB0)

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
- Only supports MP3 files (for now)
- [Roadmap](https://github.com/elibroftw/music-caster/projects/1)

## Data Collection / Privacy Policy
What is sent to me when an error is encountered?
```JS
// As seen in handle_exception(exception)
'TIME': current_time,
'VERSION': VERSION,                   // Music Caster version
'OS': platform.platform(),            // operating system
'EXCEPTION TYPE': exc_type.__name__,  // error name
'LINE NUMBER': exc_tb.tb_lineno,      // error location
'TRACEBACK': trace_back_msg,          // error message
'MAC': MAC                            // error unqiueness
```
In addition, MAC and IP are sent to me on every startup
- MAC so that I know how many users
- IP because I plan on plotting points on a map (for my curiosity)
- Only I have access to this data, I will never give it anyone else.

## UI Keyboard Shortcuts
There exists keyboard shortcuts. I will finish this table later.
Note that the progress bar and the volume slider can be controlled via scrolling.
| Shortcut        | Window           | Behaviour  |
| ------------- |:-------------:| -----:|
| Ctrl + S | | |
| Ctrl + R | | |
| Ctrl + D | | |
| Page Up | | |
| Page Down | | |
| Esc | | |

## Settings.json Guide
- Music Caster will detect changes within 10 seconds of editing `settings.json`
  - Caveat: any color code changes requires a restart
- The music directories is a list of valid directory paths
  - The first path is the default directory MC opens when you click "Play File"
- The playlist setting follows the convention `{'PLAYLIST NAME': ['list of paths to files']}`
- Some settings are there for the future and have no effect

## Build Instructions
1. Have Python 3.6.x installed
2. Have Visual Studio 2019 Installed
3. `pip install -r requirements.txt`
4. Make sure Python scripts folder is on PATH
5. Have Inno Setup installed and `C:\Program Files (x86)\Inno Setup 6\` on PATH
6. You may need to install the dependencies for `Music Caster Updater`
7. run `build` or `build.py`

## Credits
- default album art made by [ivke32](https://pixabay.com/users/ivke32-2526695/?utm_source=link-attribution&amp;utm_medium=referral&amp;utm_campaign=image&amp;utm_content=1413583) from [Pixabay](https://pixabay.com/?utm_source=link-attribution&amp;utm_medium=referral&amp;utm_campaign=image&amp;utm_content=1413583)
- speaker icon in main window made by [Naomi Atkinson](https://thenounproject.com/naomiatkinson/) from [The Noun Project](https://thenounproject.com/term/speaker/5609/) and modified by me
- repeat icon in main window made by [Brandy Bora](https://thenounproject.com/brandy.bora) from [The Noun Project](https://thenounproject.com/search/?q=repeat&i=1555394) and modified by me
- folder icon in main window by [Landan Lloyd](https://thenounproject.com/landan/) from [The Noun Project](https://thenounproject.com/term/folder/1352565/)
