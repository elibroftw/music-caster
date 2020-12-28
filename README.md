<h1 align="left">
<img width=30px src="https://raw.githubusercontent.com/elibroftw/music-caster/master/resources/Music%20Caster%20Icon.png" alt="Logo" style="vertical-align: bottom">
Music Caster</h1>

[![GitHub Releases](https://img.shields.io/github/downloads/elibroftw/music-caster/latest/total?color=blue&label=github%20downloads%40latest&style=for-the-badge)](https://github.com/elibroftw/music-caster/releases/latest)
[![Source Forge](https://img.shields.io/sourceforge/dt/music-caster?color=orange&label=SourceForge%20downloads&style=for-the-badge)](https://sourceforge.net/projects/music-caster/)

Music Caster is a modern music player that lets you cast local music files to a Google Cast Device (Chromecast, Home, etc.).

If you enjoyed this product a lot feel free to donate (ironic) at https://elijahlopez.herokuapp.com//donate.

**Important information**

On the first run, you will need to click the arrow in your taskbar to see the app icon, you can move it for ease of access.
If you have music files in folders other than the home music folder, add them in settings (right click tray icon -> settings).

## [Download (Windows)](https://github.com/elibroftw/music-caster/releases/latest)

[VirusTotal scan](https://www.virustotal.com/gui/file/cdc549d0ec0d40e7703e168723a452b90c282c2d461c56c10373bed770c919ae/detection)

## Demo
The image below directs to my demo video on YouTube. [Screenshots](http://www.elijahlopez.herokuapp.com/music-caster/) are also available.

<a href=https://youtu.be/MtkhqV1w3WE>
  <img width=75% src="https://img.youtube.com/vi/MtkhqV1w3WE/maxresdefault.jpg" alt="Demo on Youtube" align="center"/>
</a>

## Usage
Left click to open up the main window.

Play All: all the music files from the chosen directories (in settings) are shuffled and played.

Play File: select a file to start playing. Music files in the chosen directories are optionally shuffled and added to the queue.

## Power User Features
- Media keys are supported (with more keyboard shortcuts below)
- Web GUI (QR code in Settings window)
- [Command Line Arguments](https://github.com/elibroftw/music-caster/wiki/Command-Line-Arguments)

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
| K | Main | Pause / Resume / Start Playing
| J | Main | Rewind 5 seconds
| L | Main | Fast-forward 5 seconds
| Ctrl + R | Main | Cycle Repeat
| Ctrl + M | Main | Mute
| Ctrl + 1 | Main | Go to Tab 1 (Queue)
| Ctrl + 2 | Main | Go to Tab 2 (Playlists)
| Ctrl + 3 | Main | Go to Tab 3 (Timer)
| Ctrl + 4 | Main | Go to Tab 4 (Settings)

## Limitations and Known Issues
- Chromecasts only support the AAC version of WMA files
- Lack of emoji support (the GUI might not work). There's always settings.json + WEB GUI though
- Queuing from explorer is not support yet
- [Road Map](https://github.com/elibroftw/music-caster/projects/1)

## Settings.json Guide
- Music Caster will detect changes within 10 seconds of editing `settings.json`
  - Caveat: any color code changes requires a restart
- The music directories is a list of valid directory paths
  - The first path is the default directory MC opens when you click "Play File"
- The playlist setting follows the convention `{'PLAYLIST NAME': ['list of paths to files']}`
- Some settings are there for the future and have no effect

## Data Collection / Privacy Policy
What is sent to me when an error is encountered?
```JS
// As seen in handle_exception(exception)
'VERSION': VERSION,
'EXCEPTION TYPE': exc_type.__name__,  // error name
'LINE': exc_tb.tb_lineno,             // error location
'TRACEBACK': trace_back_msg,          // error message
'MAC': MAC,                           // error unqiueness
'LOG': log_lines,                     // last 5 lines of the log file so I have more context
'FATAL': restart_program,             // if the error crashed the program
'OS': platform.platform(),
'TIME': current_time
```
In addition, I collect MAC and IP addresses in a Google Excel Sheet.
Only I have access to this data, I will NEVER give it to anyone else.
- MAC so that I know how many users (450+)
- IP because I can do something [cool](https://github.com/elibroftw/music-caster/wiki)

## Development Guide
1. Use Python 3.6 or 3.8. 32-bit is fine.
2. `pip install -r requirements.txt`
3. Make sure Python scripts folder is on PATH
4. Have Inno Setup installed and `C:\Program Files (x86)\Inno Setup 6\` on PATH
5. run `build` or `build.py`

[Wiki](https://github.com/elibroftw/music-caster/wiki/Development-Guide)

## Credits
- default album art made by [ivke32](https://pixabay.com/users/ivke32-2526695/?utm_source=link-attribution&amp;utm_medium=referral&amp;utm_campaign=image&amp;utm_content=1413583) from [Pixabay](https://pixabay.com/?utm_source=link-attribution&amp;utm_medium=referral&amp;utm_campaign=image&amp;utm_content=1413583)
- speaker icon in main window made by [Naomi Atkinson](https://thenounproject.com/naomiatkinson/) from [The Noun Project](https://thenounproject.com/term/speaker/5609/) and modified by me
- repeat icon in main window made by [Brandy Bora](https://thenounproject.com/brandy.bora) from [The Noun Project](https://thenounproject.com/search/?q=repeat&i=1555394) and modified by me
