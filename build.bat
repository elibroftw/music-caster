pyinstaller music_caster.spec
pyinstaller updater.spec
python after_build.py
iscc "Installer Script.iss"