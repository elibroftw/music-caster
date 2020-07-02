import time
import subprocess
import os
import shutil
import zipfile
import sys
from contextlib import suppress
from datetime import datetime
import argparse
try: from music_caster import VERSION
except RuntimeError as e: VERSION = str(e)

parser = argparse.ArgumentParser(description='Music Caster Build Script')
parser.add_argument('--debug', default=False, action='store_true')
parser.add_argument('--nostart', default=False, action='store_true', help='Disable auto launch of MC after building')
args = parser.parse_args()
start_time = time.time()
YEAR = datetime.today().year
SETUP_OUTPUT_NAME = 'Music Caster x64 Setup'
# https://stackoverflow.com/questions/418896/how-to-redirect-output-to-a-file-and-stdout
shutil.rmtree('dist/Music Caster', True)
with suppress(FileNotFoundError): os.remove('dist/Music Caster.exe')
with suppress(FileNotFoundError): os.remove(f'dist/{SETUP_OUTPUT_NAME}.exe')
MSBuild = r'C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\MSBuild\Current\Bin\amd64\MSBuild.exe'
starting_dir = os.path.dirname(os.path.abspath(sys.argv[0]))


def update_spec_files(debug_option):
    with open('mc_portable.spec', 'r+') as f:
        new_spec = f.read().replace(f'debug={not debug_option}', f'debug={debug_option}')
        new_spec = new_spec.replace(f'console={not debug_option}', f'console={debug_option}')
        f.seek(0)
        f.write(new_spec)
        f.truncate()
    with open('mc_onedir.spec', 'r+') as f:
        new_spec = f.read().replace(f'debug={not debug_option}', f'debug={debug_option}')
        new_spec = new_spec.replace(f'console={not debug_option}', f'console={debug_option}')
        f.seek(0)
        f.write(new_spec)
        f.truncate()


print('Updating versions of build files')
# UPDATE VERSIONS OF version file and installer script
with open('mc_version_info.txt', 'r+') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if line.startswith('    prodvers'):
            version = ', '.join(VERSION.split('.'))
            lines[i] = f'    prodvers=({version}, 0),\n'
        elif line.startswith('    filevers'):
            version = ', '.join(VERSION.split('.'))
            lines[i] = f'    filevers=({version}, 0),\n'
        elif line.startswith("        StringStruct('FileVersion'"):
            lines[i] = f"        StringStruct('FileVersion', '{VERSION}.0'),\n"
        elif line.startswith("        StringStruct('ProductVersion'"):
            lines[i] = f"        StringStruct('ProductVersion', '{VERSION}.0')])\n"
        elif line.startswith("        StringStruct('LegalCopyright'"):
            lines[i] = f"        StringStruct('LegalCopyright', 'Copyright (c) 2019 - {YEAR}, Elijah Lopez'),\n"
            break
    f.seek(0)
    f.writelines(lines)
    f.truncate()

with open('setup_script.iss', 'r+') as f:
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

if args.debug: update_spec_files(True)
print('Installing dependencies...')
subprocess.check_call('pip install --upgrade -r requirements.txt', stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
print(f'building executables with debug={args.debug}')
py_installer_exe = os.path.dirname(sys.executable) + '\\Scripts\\pyinstaller.exe'
try: s1 = subprocess.Popen('pyinstaller mc_portable.spec')
except FileNotFoundError: s1 = subprocess.Popen(f'"{py_installer_exe}" mc_portable.spec')
try: s2 = subprocess.Popen('pyinstaller updater.spec')
except FileNotFoundError: s2 = subprocess.Popen(f'"{py_installer_exe}" updater.spec')
try: subprocess.check_call('pyinstaller mc_onedir.spec')
except FileNotFoundError: subprocess.check_call(f'"{py_installer_exe}" mc_onedir.spec')
s2.wait()
try: s4 = subprocess.Popen('iscc setup_script.iss')
except FileNotFoundError: s4 = None
s1.wait()

files = ['images/default.png', 'static/style.css', 'templates/index.html']
for _dir in {'dist/images', 'dist/static', 'dist/templates'}:
    with suppress(OSError): os.mkdir(_dir)

for file in files:
    shutil.copyfile(file, 'dist/' + file)

with zipfile.ZipFile('dist/Portable.zip', 'w') as zf:
    zf.write('dist/Music Caster.exe', 'Music Caster.exe')
    zf.write('dist/Updater.exe', 'Updater.exe')
    zf.write('resources/default.png', 'images/default.png')
    zf.write('templates/index.html')
    zf.write('static/style.css')
    zf.write('CHANGELOG', 'CHANGELOG.txt')
    # for f in glob.glob(r'Music Caster Updater\Music Caster Updater\bin\Release\netcoreapp3.1\*.*'):
    #     zf.write(f, os.path.basename(f))

print('Created dist/Portable.zip')

with zipfile.ZipFile('dist/Source Files Condensed.zip', 'w') as zf:
    zf.write('music_caster.py')
    zf.write('helpers.py')
    zf.write('b64_images.py')
    zf.write('updater.py')
    zf.write('resources/Music Caster.ico', 'icon.ico')
    zf.write('resources/default.png', 'images/default.png')
    zf.write('templates/index.html')
    zf.write('static/style.css')
    zf.write('requirements.txt')
    with suppress(FileNotFoundError): zf.write('settings.json')

print('Created dist/Source Files Condensed.zip')
if s4 is not None: s4.wait()  # Wait for inno script to finish
else: print('WARNING: could not create an installer: iscc is not installed or is not on path')
if args.debug: update_spec_files(False)
print('Build Time:', time.time() - start_time, 'seconds')
if not args.nostart:
    print('Launching Music Caster.exe')
    subprocess.Popen(r'"dist\Music Caster.exe"')
