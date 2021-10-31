<h1 align="left">
<img width=30px src="https://raw.githubusercontent.com/elibroftw/music-caster/master/resources/favicons/favicon-32x32.png" alt="Logo" style="vertical-align: bottom; margin-bottom: -4px;">
Music Caster</h1>

[![GitHub Releases](https://img.shields.io/github/downloads/elibroftw/music-caster/latest/total?color=blue&label=github%20downloads%40latest&style=for-the-badge)](https://github.com/elibroftw/music-caster/releases/latest)
[![Source Forge](https://img.shields.io/sourceforge/dt/music-caster?color=orange&label=SourceForge%20downloads&style=for-the-badge)](https://sourceforge.net/projects/music-caster/)

Music Caster is a modern music player that can cast audio files and urls to Google Chromecasts, Home minis, etc.

**Donate**
- monero:84PR6SkYd5zaFLKDjAFrQfbaAg2c7SV3q3XDZ15QCpEZUggrN4YzY7n8m9XC3deXjo41yWHTm1LrsUpPTYGnRQbD9Cwp8En
- https://www.paypal.me/elibroftw.

**Important information**

On the first run, you will need to click the arrow in your taskbar to see the app icon, you can move it for ease of access.
If you have music files in folders other than the home music folder, add them in settings (right click tray icon -> settings).
If you are able and willing to translate to other languages, click [here](https://github.com/elibroftw/music-caster/issues/12#issuecomment-808658776).

## [Download (Windows)](https://github.com/elibroftw/music-caster/releases/latest)
- Install from command line: `winget install "Music Caster"` (auto-updates on launch)
- [VirusTotal scan](https://www.virustotal.com/gui/file/871507ad79e394634b1830802b48b3ebf35c993d6a074cba23fa38b16ed1b740)
- Windows may detect Music Caster as a Trojan even though I built the PyInstaller bootloader myself...
- To restore Music Caster, open "Virus & threat protection", "protection history" and restore all files related to Music Caster
- [Developer Guide](https://github.com/elibroftw/music-caster/wiki/Developer-Guide)
- [Screenshots](https://elijahlopez.herokuapp.com/music-caster/)

## Demo
Clicking the image below takes you to my demo video on YouTube.

<a href=https://youtu.be/5xwHkLPgvtQ>
  <img width=75% src="https://img.youtube.com/vi/5xwHkLPgvtQ/maxresdefault.jpg" alt="demo YouTube video thumbnail" align="center"/>
</a>

## Power User Features
- Global media hot-keys are supported
- Web GUI (QR code in Settings window)
- [Command Line Arguments](https://github.com/elibroftw/music-caster/wiki/Command-Line-Arguments)

Aside from the global media hot-keys, Music Caster has its own keyboard shortcuts as seen below.

| **Shortcut** | **Window** | **Behaviour**
| ------------ |----------- | -------------
| Ctrl + Shift + Alt + M | Global | Activate Main Window
| Ctrl + (Shift) + } | Main | Toggle mini-mode
| Esc | Main | Close Window |
| Scroll | Main | Volume and Progress Bar
| ⬆/A | Main | Decrease Volume by 5%
| ⬇/D | Main | Increase Volume by 5%
| # | Main | Set Volume to # * 10%
| K | Main | Pause / Resume / Start Playing
| J | Main | Rewind 5 seconds
| L | Main | Fast-forward 5 seconds
| Ctrl + R | Main | Cycle Repeat
| Ctrl + M | Main | Mute
| Ctrl + 1 | Main | Go to Tab 1 (Queue)
| Ctrl + 2 | Main | Go to Tab 2 (URL)
| Ctrl + 3 | Main | Go to Tab 3 (Library)
| Ctrl + 4 | Main | Go to Tab 4 (Playlists)
| Ctrl + 5 | Main | Go to Tab 5 (Timer)
| Ctrl + 6 | Main | Go to Tab 6 (Metadata)
| Ctrl + 7 | Main | Go to Tab 7 (Settings)

**Editing settings.json**
- Music Caster will detect changes within 10 seconds of editing `settings.json`
- The music directories is a list of valid directory paths
  - The first path is the default directory MC opens when you click "Play File"
- The playlist setting follows the convention `{'PLAYLIST NAME': ['list of paths to files']}`
- Some settings are there for the future and have no effect

## Limitations
- Chromecasts only support the AAC version of WMA files
- Lack of emoji support (the GUI might not work). There's always settings.json + WEB GUI though
- [Road Map](https://github.com/elibroftw/music-caster/projects/1)

## Data Collection / Privacy Policy
What is sent to me when an error is encountered?
```python
# in handle_exception,
{
  'EXCEPTION TYPE': exc_type.__name__,                  # error name
  'LINE': exc_tb.tb_lineno,                             # error location/line
  'TRACEBACK': trace_back_msg,                          # error message
  'MAC': hashlib.md5(get_mac().encode()).hexdigest(),   # error unqiueness
  'LOG': log_lines,                                     # last 5 lines of log for context
  'FATAL': restart_program,                             # if the error crashed the program
  'CASTING': cast is not None,                          # was user was casting to a chromecast
  'MQ': len(music_queue),                               # queue lengths
  'PLAYING_TYPE': play_uri,                             # what uri type if any was user playing
  'CWD': os.getcwd(),                                   # lets me know if CWD is expected or not
  'VERSION': VERSION,
  'NQ': len(next_queue),
  'DQ': len(done_queue),
  'OS': platform.platform(),
  'TIME': current_time,
}
```
In addition, I collect MD5 hashed MAC addresses and IP addresses in a Google Excel Sheet.
Only I have access to this data, I will NEVER give it to anyone else.
- Hashed MAC so that I know how many users without knowing the actual MAC addresses
- IP because I can do something [cool](https://github.com/elibroftw/music-caster/wiki)
