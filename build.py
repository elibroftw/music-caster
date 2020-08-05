import time
import subprocess
import os
import shutil
import zipfile
import sys
from contextlib import suppress
from datetime import datetime
import argparse
from glob import glob
from distutils.dir_util import copy_tree
try: from music_caster import VERSION
except RuntimeError as e: VERSION = str(e)

parser = argparse.ArgumentParser(description='Music Caster Build Script')
parser.add_argument('--debug', default=False, action='store_true')
parser.add_argument('--versioning', default=False, action='store_true')
parser.add_argument('--start', default=False, action='store_true', help='Auto launch portable MC after building')
args = parser.parse_args()
start_time = time.time()
YEAR = datetime.today().year
SETUP_OUTPUT_NAME = 'Music Caster Setup'
# https://stackoverflow.com/questions/418896/how-to-redirect-output-to-a-file-and-stdout
shutil.rmtree('dist/Music Caster', True)
with suppress(FileNotFoundError): os.remove('dist/Music Caster.exe')
with suppress(FileNotFoundError): os.remove(f'dist/{SETUP_OUTPUT_NAME}.exe')
MSBuild = r'C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\MSBuild\Current\Bin\amd64\MSBuild.exe'
starting_dir = os.path.dirname(os.path.abspath(sys.argv[0]))


def update_spec_files(debug_option):
    with open('build_files/mc_portable.spec', 'r+') as _f:
        new_spec = _f.read().replace(f'debug={not debug_option}', f'debug={debug_option}')
        new_spec = new_spec.replace(f'console={not debug_option}', f'console={debug_option}')
        _f.seek(0)
        _f.write(new_spec)
        _f.truncate()
    with open('build_files/mc_onedir.spec', 'r+') as _f:
        new_spec = _f.read().replace(f'debug={not debug_option}', f'debug={debug_option}')
        new_spec = new_spec.replace(f'console={not debug_option}', f'console={debug_option}')
        _f.seek(0)
        _f.write(new_spec)
        _f.truncate()
    with open('build_files/updater.spec', 'r+') as _f:
        new_spec = _f.read().replace(f'debug={not debug_option}', f'debug={debug_option}')
        new_spec = new_spec.replace(f'console={not debug_option}', f'console={debug_option}')
        _f.seek(0)
        _f.write(new_spec)
        _f.truncate()


print('Updating versions of build files')
# UPDATE VERSIONS OF version file and installer script
with open('build_files/mc_version_info.txt', 'r+') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if line.startswith('    prodvers'):
            version = ', '.join(VERSION.split('.'))
            lines[i] = f'    prodvers=({version}, 0),\n'
        elif line.startswith('    filevers'):
            version = ', '.join(VERSION.split('.'))
            lines[i] = f'    filevers=({version}, 0),\n'
        elif line.startswith("        StringStruct('FileVersion"):
            lines[i] = f"        StringStruct('FileVersion', '{VERSION}.0'),\n"
        elif line.startswith("        StringStruct('LegalCopyright'"):
            lines[i] = f"        StringStruct('LegalCopyright', 'Copyright (c) 2019 - {YEAR}, Elijah Lopez'),\n"
        elif line.startswith("        StringStruct('ProductVersion"):
            lines[i] = f"        StringStruct('ProductVersion', '{VERSION}.0')])\n"
            break
    f.seek(0)
    f.writelines(lines)
    f.truncate()

with open('build_files/setup_script.iss', 'r+') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if line.startswith('#define MyAppVersion'):
            lines[i] = f'#define MyAppVersion "{VERSION}"\n'
        elif line.startswith('OutputBaseFilename'):
            lines[i] = f'OutputBaseFilename={SETUP_OUTPUT_NAME}\n'
            break
    f.seek(0)
    f.writelines(lines)
    f.truncate()
if args.versioning: sys.exit()
if args.debug: update_spec_files(True)
print('Installing dependencies...')
subprocess.check_call('pip install --upgrade -r requirements.txt', stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
subprocess.check_call('pip install build_files\PyAudio-0.2.11-cp38-cp38-win32.whl --force', stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
print(f'building executables with debug={args.debug}')
py_installer_exe = os.path.dirname(sys.executable) + '\\Scripts\\pyinstaller.exe'
try: s1 = subprocess.Popen('pyinstaller build_files/mc_portable.spec')
except FileNotFoundError: s1 = subprocess.Popen(f'"{py_installer_exe}" build_files/mc_portable.spec')
try: s2 = subprocess.Popen('pyinstaller build_files/updater.spec')
except FileNotFoundError: s2 = subprocess.Popen(f'"{py_installer_exe}" build_files/updater.spec')
try: subprocess.check_call('pyinstaller build_files/mc_onedir.spec')
except FileNotFoundError: subprocess.check_call(f'"{py_installer_exe}" build_files/mc_onedir.spec')
s2.wait()
try: s4 = subprocess.Popen('iscc build_files/setup_script.iss')
except FileNotFoundError: s4 = None
s1.wait()
if args.debug: update_spec_files(False)

files = ['static/style.css', 'templates/index.html']
for _dir in {'dist/static', 'dist/templates'}:
    with suppress(OSError): os.mkdir(_dir)

copy_tree('vlc', 'dist/vlc')

for file in files:
    shutil.copyfile(file, 'dist/' + file)

with zipfile.ZipFile('dist/Portable.zip', 'w') as zf:
    zf.write('dist/Music Caster.exe', 'Music Caster.exe')
    zf.write('dist/Updater.exe', 'Updater.exe')
    zf.write('templates/index.html')
    zf.write('static/style.css')
    zf.write('build_files/CHANGELOG.txt', 'CHANGELOG.txt')
    for f in glob('vlc/**/*.*', recursive=True):
        zf.write(f)

print('Created dist/Portable.zip')

with zipfile.ZipFile('dist/Source Files Condensed.zip', 'w') as zf:
    zf.write('music_caster.py')
    zf.write('helpers.py')
    zf.write('b64_images.py')
    zf.write('updater.py')
    zf.write('resources/Music Caster.ico', 'icon.ico')
    zf.write('templates/index.html')
    zf.write('static/style.css')
    zf.write('requirements.txt')
    with suppress(FileNotFoundError): zf.write('settings.json')

print('Created dist/Source Files Condensed.zip')
if args.start:
    print('Launching Music Caster.exe')
    subprocess.Popen(r'"dist\Music Caster.exe --debug"')
if s4 is not None: s4.wait()  # Wait for inno script to finish
else: print('WARNING: could not create an installer: iscc is not installed or is not on path')
print('Build Time:', round(time.time() - start_time, 2), 'seconds')
