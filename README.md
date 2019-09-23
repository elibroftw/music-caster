# Music Caster
[![Download Count](https://img.shields.io/github/downloads/elibroftw/music-caster/total?color=blue&label=Downloads&style=for-the-badge)](https://github.com/elibroftw/music-caster/releases)

Music Caster is a music player which lets you cast your local music files to a Google Cast Device (Chromecast, Home, etc...)
[Download Page](https://github.com/elibroftw/music-caster/releases)

# Screenshots
<p align="center">
  <img width=470px src="https://github.com/elibroftw/music-caster/blob/master/resources/Settings%20Screenshot.jpg?raw=true" alt="Settings window screenshot">
  <img src="https://github.com/elibroftw/music-caster/blob/master/resources/Tray%20Startup.png?raw=true" alt="Tray startup screenshot">
</p>
<p align="center">
  <img src="https://github.com/elibroftw/music-caster/blob/master/resources/Tray%20Playing.png?raw=true" alt="Tray playing screenshot">
  <img src="https://github.com/elibroftw/music-caster/blob/master/resources/Tray%20Paused.png?raw=true" alt="Settings window screenshot">
</p>

# Usage
On the first startup, the app will be in your hidden tray. You can move it onto the Taskbar and it'll stay in sight for future launches.
If you right click the icon, a menu will pop up. Click Settings to open settings (no longer a file).
Now you may add or remove music directories. By default, your home music directory is put into the music directories list.
When you click Play All, all the music from these directories all shuffled into a list and played.
When you click Play File, you can select a file to play and all of the music in your music directories are shuffled into the music queue.

TLDR: If you have music files in different folders, right click icon in tray and open settings

This app supports media keys.

# Limitations and known issues
- The GUI library I use does have a memory leak issue, I'm planning on porting to wxPython
- So restart if you feel the app is laggy
- If you find a bug, please create an issue or email me, I am very fast at pushing fixes if the issues are huge

# Build Instructions
1. Make sure all the required modules are installed
2. Download [PySimpleGUIWx.py](https://github.com/PySimpleGUI/PySimpleGUI/blob/master/PySimpleGUIWx/PySimpleGUIWx.py) (Place in root)
3. Make sure you do not have the pypi version of PySimpleGuiwx installed.
4. Make sure Python scripts folder is on path
5. OPTIONAL: Having Inno Setup installed and `C:\Program Files (x86)\Inno Setup 6\` on path
6. Run build.bat


# Credits
default.png made by <a href="https://pixabay.com/users/ivke32-2526695/?utm_source=link-attribution&amp;utm_medium=referral&amp;utm_campaign=image&amp;utm_content=1413583">ivke32</a> from <a href="https://pixabay.com/?utm_source=link-attribution&amp;utm_medium=referral&amp;utm_campaign=image&amp;utm_content=1413583">Pixabay</a>
