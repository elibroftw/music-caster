# Music Caster
[![Download Count](https://img.shields.io/github/downloads/elibroftw/music-caster/total?color=blue&label=Downloads&style=for-the-badge)](https://github.com/elibroftw/music-caster/releases)

Music Caster is a music player which lets you cast your local music files to a Google Cast Device (Chromecast, Home, etc.)

Click image below for a video demo.

[![demo link](https://i3.ytimg.com/vi/y0fWPyhNSB0/maxresdefault.jpg)](https://www.youtube.com/watch?v=y0fWPyhNSB0)


## [Download Page (Windows 64-bit + Python Files)](https://github.com/elibroftw/music-caster/releases)

## Screenshots (Slightly Outdated)
<p align="center">
  <img width=470px src="https://github.com/elibroftw/music-caster/blob/master/resources/Settings%20Screenshot.jpg?raw=true" alt="Settings window screenshot">
  <img src="https://github.com/elibroftw/music-caster/blob/master/resources/Tray%20Startup.png?raw=true" alt="Tray startup screenshot">
</p>
<p align="center">
  <img src="https://github.com/elibroftw/music-caster/blob/master/resources/Tray%20Playing.png?raw=true" alt="Tray playing screenshot">
  <img src="https://github.com/elibroftw/music-caster/blob/master/resources/Tray%20Paused.png?raw=true" alt="Settings window screenshot">
</p>

## Usage
TLDR: If you have music files in different folders, right click the tray icon and open settings

On the first startup, the app will be in your hidden tray. You can move it onto the Taskbar and it'll stay in sight for future launches.
If you right click the icon, a menu will pop up. Click Settings to open settings (no longer a file).
Now you may add or remove music directories. By default, your home music directory is put into the music directories list.
When you click Play All, all the music from these directories all shuffled into a list and played.
When you click Play File, you can select a file to play and all of the music in your music directories are shuffled into the music queue.

Music Caster supports media keys.

## Limitations and known issues
- Only supports MP3 files (for now)
- A major bug will result in a toast message + a error message output in an error.log.

## Dealing With an Error
You will have to email this to me yourself.
The error.log file can be found in the installation folder of music caster.
An easy way to find it is to right click Music Caster's Shortcut and then click Open file location.
After doing this twice to the shortcut's, you will end up at the installation directory.

## Settings.json Guide
- Music Caster will detect changes within 10 seconds of editing the settings.json file
- The music directories is a list of directory paths ['C:/Users/maste/MEGAsync/Music', 'Put in a valid path']
- The first path in music directories is the default directory you want to play a file
- The playlist variable follows the convention {'PLAYLIST NAME': ['paths to files']}
- Do not remove a setting variable as something might break.

## Build Instructions
1. Make sure all the required modules are installed (`pip install -r requirements.txt`)
2. Make sure Python scripts folder is on PATH
3. If you have Inno Setup installed and `C:\Program Files (x86)\Inno Setup 6\` on PATH and want to build a setup.exe, run build.bat
4. Otherwise, use `pyinstaller music_caster.spec && pyinstaller updater.spec && python after_build.py`

# Credits
- default.png made by [ivke32](https://pixabay.com/users/ivke32-2526695/?utm_source=link-attribution&amp;utm_medium=referral&amp;utm_campaign=image&amp;utm_content=1413583) from [Pixabay](https://pixabay.com/?utm_source=link-attribution&amp;utm_medium=referral&amp;utm_campaign=image&amp;utm_content=1413583)
- speaker icon in main window made by [Naomi Atkinson](https://thenounproject.com/naomiatkinson/) from [The Noun Project](https://thenounproject.com/term/speaker/5609/) and modified by me
- repeat icon in main window made by [Brandy Bora](https://thenounproject.com/brandy.bora) from [The Noun Project](https://thenounproject.com/search/?q=repeat&i=1555394) and modified by me