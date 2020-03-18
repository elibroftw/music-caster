set startTime=%time%
pip install -r requirements.txt
pyinstaller music_caster.spec && pyinstaller updater.spec && python after_build.py && iscc "Installer Script.iss"
echo Start Time: %startTime%
echo Finish Time: %time%