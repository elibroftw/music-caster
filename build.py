import time
import subprocess
import os
import shutil
import json
import zipfile
from contextlib import suppress

start_time = time.time()
shutil.rmtree('dist/Music Caster', True)

print('Installing dependencies...')
subprocess.check_call('pip install -r requirements.txt', stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
s1 = subprocess.Popen('pyinstaller music_caster_portable.spec')
s2 = subprocess.Popen('pyinstaller updater.spec')
s3 = subprocess.call('pyinstaller music_caster_onedir.spec')
s2.wait()
s4 = subprocess.call('iscc Installer Script NEW.iss')
s1.wait()


files = ['images/default.png', 'static/style.css', 'templates/home.html']
for _dir in {'dist/images', 'dist/static', 'dist/templates'}:
    with suppress(OSError): os.mkdir(_dir)

shutil.copyfile('settings.json', 'dist/Music Caster/settings.json')

for file in files:
    shutil.copyfile(file, 'dist/' + file)

with zipfile.ZipFile('dist/Portable.zip', 'w') as zf:
    zf.write('dist/Music Caster.exe', 'Music Caster.exe')
    zf.write('dist/Updater.exe', 'Updater.exe')
    zf.write('resources/default.png', 'images/default.png')
    zf.write('templates/home.html')
    zf.write('static/style.css')
    zf.write('CHANGELOG', 'CHANGELOG.txt')

print('Created dist/Portable.zip')

with zipfile.ZipFile('dist/Python Files.zip', 'w') as zf:
    zf.write('music_caster.py', 'music_caster.pyw')
    zf.write('updater.py', 'updater.pyw')
    zf.write('helpers.py', 'helpers.py')
    zf.write('resources/Music Caster.ico', 'icon.ico')
    zf.write('resources/default.png', 'images/default.png')
    zf.write('templates/home.html')
    zf.write('static/style.css')
    zf.write('requirements.txt')
    zf.write('CHANGELOG', 'CHANGELOG.txt')

print('Created dist/Python Files.zip')
print('Time taken:', time.time() - start_time, 'seconds')