#!/usr/bin/env bash
cd ~/bin/music-caster/src && python3 -m pip install -r requirements.txt && cd -
mkdir -p ~/.icons
cp ~/bin/music-caster/resources/favicons/android-chrome-256x256.png ~/Downloads
mv ~/Downloads/android-chrome-256x256.png ~/.icons/music_caster.png
cp ~/bin/music-caster/music_caster.desktop ~/.local/share/applications
