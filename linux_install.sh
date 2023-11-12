#!/usr/bin/env bash
# install virtualenv to avoid global dependdency issues
# cd into our directory
cd ~/bin/music-caster
git fetch
git reset --hard ORIG_HEAD
cd -
cd ~/bin/music-caster/src
echo "(music-caster) Creating Python virtual environment"
python3 -m pip install virtualenv
python3 -m virtualenv venv
source venv/bin/activate
echo "(music-caster) Installing dependencies"
python -m pip install -r requirements.txt
# restore
cd -
echo "(music-caster) Registering as desktop application"

# copy icons
mkdir -p ~/Downloads/music-caster-tmp

# 32x32
cp -rf ~/bin/music-caster/resources/icons/32x32.png ~/Downloads/music-caster-tmp
mv -f ~/Downloads/music-caster-tmp/32x32.png ~/.local/share/icons/hicolor/32x32/apps/music_caster.png
# 128x128
cp -rf ~/bin/music-caster/resources/icons/128x128.png ~/Downloads
mv -f ~/Downloads/music-caster-tmp/128x128.png ~/.local/share/icons/hicolor/128x128/apps/music_caster.png
# 256x256
cp -rf ~/bin/music-caster/resources/icons/128x128@2x.png ~/Downloads
mv -f ~/Downloads/music-caster-tmp/128x128@2x.png ~/.local/share/icons/hicolor/256x256/apps/music_caster.png
# 512x512
cp -rf ~/bin/music-caster/resources/icons/icon.png ~/Downloads
mv -f ~/Downloads/music-caster-tmp/icon.png ~/.local/share/icons/hicolor/512x512/apps/music_caster.png

rm -rf ~/Downloads/music-caster-tmp

# install .desktop file
cp -rf ~/bin/music-caster/music_caster.desktop ~/.local/share/applications

# delete old files
rm -rf ~/.icons/music_caster.png
