#!/usr/bin/env bash
set -ex

echo "(music-caster) Updating..."
# git fetch
# git reset --hard "@{u}"

PYTHON=python3.12
./scripts/pre-req.sh $PYTHON

echo "(music-caster) Creating $PYTHON virtual environment"
# if .venv DNE or has wrong Python version, delete old .venv and install new .venv
if [ ! -d .venv ] || [ "$(.venv/bin/python -V)" != "$($PYTHON -V)" ]; then
    rm -rf .venv src/.venv src/venv venv
    $PYTHON -m venv .venv
fi
. .venv/bin/activate

echo "(music-caster) Installing dependencies"
python -m pip install --upgrade -r requirements.txt
python -m pip install -i https://PySimpleGUI.net/install PySimpleGUI==4.60.5
# restore
cd ~/bin/music-caster

# copy icons
mkdir -p ~/Downloads/music-caster-tmp
mkdir -p ~/.local/share/icons/hicolor/32x32/apps
mkdir -p ~/.local/share/icons/hicolor/128x128/apps
mkdir -p ~/.local/share/icons/hicolor/256x256/apps
mkdir -p ~/.local/share/icons/hicolor/512x512/apps

# 32x32
cp -rf resources/icons/32x32.png ~/Downloads/music-caster-tmp
mv -f ~/Downloads/music-caster-tmp/32x32.png ~/.local/share/icons/hicolor/32x32/apps/music_caster.png
# 128x128
cp -rf resources/icons/128x128.png ~/Downloads/music-caster-tmp
mv -f ~/Downloads/music-caster-tmp/128x128.png ~/.local/share/icons/hicolor/128x128/apps/music_caster.png
# 256x256
cp -rf resources/icons/128x128@2x.png ~/Downloads/music-caster-tmp
mv -f ~/Downloads/music-caster-tmp/128x128@2x.png ~/.local/share/icons/hicolor/256x256/apps/music_caster.png
# 512x512
cp -rf resources/icons/icon.png ~/Downloads/music-caster-tmp
mv -f ~/Downloads/music-caster-tmp/icon.png ~/.local/share/icons/hicolor/512x512/apps/music_caster.png

rm -rf ~/Downloads/music-caster-tmp

# install .desktop file
echo "(music-caster) Registering as desktop application"
cp -rf music_caster.desktop ~/.local/share/applications

# delete old files
rm -rf ~/.icons/music_caster.png
