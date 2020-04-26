import time
import subprocess
import os
import shutil
import json
import glob
import zipfile
import sys
from contextlib import suppress

start_time = time.time()
shutil.rmtree('dist/Music Caster', True)
MSBuild = r'C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\MSBuild\Current\Bin\amd64\MSBuild.exe'
starting_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

print('Installing dependencies...')
subprocess.check_call('pip install -r requirements.txt', stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
# subprocess.check_call(f'{MSBuild} "{starting_dir}\\Music Caster Updater\\Music Caster Updater.sln" -t:restore')

s1 = subprocess.Popen('pyinstaller music_caster_portable.spec')
# shutil.rmtree(r'Music Caster Updater\Music Caster Updater\bin\Release\netcoreapp3.1')
# subprocess.check_call(f'{MSBuild} "{starting_dir}\\Music Caster Updater\\Music Caster Updater.sln" /t:Build /p:Configuration=Release')
s2 = subprocess.Popen('pyinstaller updater.spec')
s3 = subprocess.check_call('pyinstaller music_caster_onedir.spec')
s2.wait()
s4 = subprocess.check_call('iscc "Setup Script.iss"')
s1.wait()


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
    # for f in glob.glob(r'Music Caster Updater\Music Caster Updater\bin\Release\netcoreapp3.1\*.*'):
    #     zf.write(f, os.path.basename(f))
    zf.write('static/style.css')
    zf.write('CHANGELOG', 'CHANGELOG.txt')

print('Created dist/Portable.zip')

with zipfile.ZipFile('dist/Source Files Condensed.zip', 'w') as zf:
    zf.write('music_caster.py')
    zf.write('helpers.py')
    zf.write('Music Caster Updater/Music Caster Updater/Program.cs', 'updater.cs')
    zf.write('resources/Music Caster.ico', 'icon.ico')
    zf.write('resources/default.png', 'images/default.png')
    zf.write('templates/home.html')
    zf.write('static/style.css')
    zf.write('requirements.txt')

print('Created dist/Source Files Condensed.zip')
print('Build Time:', time.time() - start_time, 'seconds')