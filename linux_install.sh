#!/usr/bin/env bash
# install virtualenv to avoid global dependdency issues
# cd into our directory
cd ~/bin/music-caster/src
echo "creating venv"
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
# restore
cd -
mkdir -p ~/.icons
cp -rf ~/bin/music-caster/resources/favicons/android-chrome-256x256.png ~/Downloads
mv -f ~/Downloads/android-chrome-256x256.png ~/.icons/music_caster.png
cp -rf ~/bin/music-caster/music_caster.desktop ~/.local/share/applications
