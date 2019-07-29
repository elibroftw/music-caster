# Music Caster
[![Download Count](https://img.shields.io/github/downloads/elibroftw/music-caster/total?color=blue&label=Downloads&style=for-the-badge)](https://github.com/elibroftw/music-caster/releases)

Music Caster is a music player which lets you cast your local music files to a Google Cast Device (Chromecast, Home, etc...)

[Download Page](https://github.com/elibroftw/music-caster/releases)
# Usage
On the first startup, the app will be in your hidden tray. You can move it onto the Taskbar and it'll stay in sight for future launches.
If you right click the icon, a menu will pop up. Click Settings to open settings (no longer a file).
Now you may add or remove music directories. By default, your home music directory is put into the music directories list.
When you click Play All, all the music from these directories all shuffled into a list and played.
When you click Play File, you can select a file to play and all of the music in your music directories are shuffled into the music queue.

TLDR: If you have music all over the place, right click icon in tray and open settings

This app supports media keys. There might be an issue with skipping though so please let me know!

# Limitations and known issues
- Music control limited to exit if next/previous song is spammed
- The GUI library I use does have a memory leak issue which will be fixed soon

# Build Instructions
1. Make sure all the required modules are installed
2. Make sure Python scripts folder is on path
3. OPTIONAL: Having Inno Setup installed and `C:\Program Files (x86)\Inno Setup 6\` on path
4. Run build.bat


# Credits
default.png made by <a href="https://pixabay.com/users/ivke32-2526695/?utm_source=link-attribution&amp;utm_medium=referral&amp;utm_campaign=image&amp;utm_content=1413583">ivke32</a> from <a href="https://pixabay.com/?utm_source=link-attribution&amp;utm_medium=referral&amp;utm_campaign=image&amp;utm_content=1413583">Pixabay</a>
