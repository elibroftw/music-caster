import zipfile
import shutil
import os
import json
from contextlib import suppress

files = ['images/default.png', 'static/style.css', 'templates/home.html']
for _dir in {'dist/images', 'dist/static', 'dist/templates'}:
    with suppress(OSError): os.mkdir(_dir)
    
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