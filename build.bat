REM venv\Scripts\pyinstaller music_caster.spec
REM venv\Scripts\pyinstaller updater.spec
pyinstaller music_caster.spec
pyinstaller updater.spec
python after_build.py
iscc "Installer Script.iss"