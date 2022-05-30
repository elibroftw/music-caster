#!/usr/bin/env bash
# install virtualenv to avoid global dependdency issues
# cd into our directory
cd ~/bin/music-caster/src
echo "(music-caster) creating Python virtual environment"
python3 -m pip install virtualenv
python3 -m virtualenv venv
source venv/bin/activate
echo "(music-caster) Installing dependencies"
python -m pip install -r requirements.txt
# restore
cd -
echo "(music-caster) Registering as desktop application"
mkdir -p ~/.icons
cp -rf ~/bin/music-caster/resources/favicons/android-chrome-256x256.png ~/Downloads
mv -f ~/Downloads/android-chrome-256x256.png ~/.icons/music_caster.png
cp -rf ~/bin/music-caster/music_caster.desktop ~/.local/share/applications
