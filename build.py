import time
import subprocess
import os
import shutil
from zipfile import ZipFile
import sys
from contextlib import suppress
from datetime import datetime
import argparse
import glob
from distutils.dir_util import copy_tree
try: from music_caster import VERSION
except RuntimeError as e: VERSION = str(e)
import requests


parser = argparse.ArgumentParser(description='Music Caster Build Script')
parser.add_argument('--debug', '-d', default=False, action='store_true')
parser.add_argument('--versioning', '-v', default=False, action='store_true', help="Only update build files' version")
parser.add_argument('--start', '-s', default=False, action='store_true', help='Auto launch portable MC after building')
parser.add_argument('--upload', '-u', '--publish', default=False, action='store_true',
                    help='Upload and Publish to GitHub after building')
args = parser.parse_args()
start_time = time.time()
YEAR = datetime.today().year
SETUP_OUTPUT_NAME = 'Music Caster Setup'
MSBuild = r'C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\MSBuild\Current\Bin\amd64\MSBuild.exe'
starting_dir = os.path.dirname(os.path.abspath(sys.argv[0]))


def read_env(env_file='.env'):
    with open(env_file) as f:
        env_line = f.readline()
        while env_line:
            k, v = env_line.split('=', 1)
            os.environ[k] = v.strip()
            env_line = f.readline()
    return os.environ


def add_new_changes(prev_changes):
    new_changes = ''
    with open('build_files/CHANGELOG.txt') as f:
        line = f.readline().strip()
        break_at_newline = False
        while True:
            if line == VERSION:
                break_at_newline = True
            elif break_at_newline:
                if line == '':
                    break
                elif line not in prev_changes:
                    new_changes += f'\n{line}'
            line = f.readline().strip()
    return prev_changes + new_changes


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


def update_versions():
    """ Update versions of version file and installer script """
    version_file = 'build_files/mc_version_info.txt'
    installer_script = 'build_files/setup_script.iss'
    with open(version_file, 'r+') as f:
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

    with open(installer_script, 'r+') as f:
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


def create_zip(zip_filename, files_to_zip):
    with ZipFile(zip_filename, 'w') as zf:
        for file in files_to_zip:
            try:
                if type(file) == tuple: zf.write(*file)
                else: zf.write(file)
            except FileNotFoundError:
                print(f'{file} not found')


update_versions()
print('Updated versions of build files')
if args.versioning: sys.exit()
if args.debug: update_spec_files(True)
if args.upload: print('Will upload to GitHub after building')

shutil.rmtree('dist/Music Caster', True)
with suppress(FileNotFoundError): os.remove('dist/Music Caster.exe')
with suppress(FileNotFoundError): os.remove(f'dist/{SETUP_OUTPUT_NAME}.exe')

print('Installing dependencies...')
pyaudio_whl = 'PyAudio-0.2.11-cp38-cp38-win32.whl'
pyinstaller_whl = 'pyinstaller-4.0+19fb799a11-py3-none-any.whl'
subprocess.check_call('pip install --upgrade -r requirements.txt', stdout=subprocess.DEVNULL)
try: subprocess.check_call(f'pip install build_files\\{pyaudio_whl}', stdout=subprocess.DEVNULL)
except subprocess.CalledProcessError: print(f'WARNING: {pyaudio_whl} could not be installed with')
try: subprocess.check_call(f'pip install "build_files\\{pyinstaller_whl}"', stdout=subprocess.DEVNULL)
except subprocess.CalledProcessError: print(f'WARNING: "{pyinstaller_whl}" could not be installed with')
print(f'building executables with debug={args.debug}')
py_installer_exe = os.path.dirname(sys.executable) + '\\Scripts\\pyinstaller.exe'
try: s1 = subprocess.Popen('pyinstaller build_files/mc_portable.spec')
except FileNotFoundError: s1 = subprocess.Popen(f'"{py_installer_exe}" build_files/mc_portable.spec')
updater_release_path = r'Music Caster Updater\Music Caster Updater\bin\x86\Release\netcoreapp3.1'
shutil.rmtree(updater_release_path, True)
subprocess.check_call(f'{MSBuild} "{starting_dir}\\Music Caster Updater\\Music Caster Updater.sln" /t:Build '
                      f'/p:Configuration=Release /p:PlatformTarget=x86')
# try: s2 = subprocess.Popen('pyinstaller build_files/updater.spec')
# except FileNotFoundError: s2 = subprocess.Popen(f'"{py_installer_exe}" build_files/updater.spec')
try: subprocess.check_call('pyinstaller build_files/mc_onedir.spec')
except FileNotFoundError: subprocess.check_call(f'"{py_installer_exe}" build_files/mc_onedir.spec')
# s2.wait()
try: s4 = subprocess.Popen('iscc build_files/setup_script.iss')
except FileNotFoundError: s4 = None
s1.wait()
if args.debug: update_spec_files(False)

for folder in {'dist/static', 'dist/templates'}:
    with suppress(OSError): os.mkdir(folder)

copy_tree('vlc', 'dist/vlc')

for res_file in ['static/style.css', 'templates/index.html']:
    shutil.copyfile(res_file, 'dist/' + res_file)


portable_files = [('dist/Music Caster.exe', 'Music Caster.exe'), 'templates/index.html', 'static/style.css',
                  ('build_files/CHANGELOG.txt', 'CHANGELOG.txt')] + glob.glob('vlc/**/*.*', recursive=True) + \
                 [(f, os.path.basename(f)) for f in glob.iglob(f'{glob.escape(updater_release_path)}/*.*')]
# [('dist/Updater.exe', 'Updater.exe')]
create_zip('dist/Portable.zip', portable_files)
print('Created dist/Portable.zip')
create_zip('dist/Source Files Condensed.zip', ['music_caster.py', 'helpers.py', 'b64_images.py', 'updater.py',
                                               'requirements.txt', ('resources/Music Caster Icon.ico', 'icon.ico'),
                                               'templates/index.html', 'static/style.css', 'settings.json'])
print('Created dist/Source Files Condensed.zip')
if args.start:
    print('Launching Music Caster.exe')
    subprocess.Popen(r'"dist\Music Caster.exe --debug"')
if s4 is not None: s4.wait()  # Wait for inno script to finish
else: print('WARNING: could not create an installer: iscc is not installed or is not on path')
print(f'v{VERSION} Build Time:', round(time.time() - start_time, 2), 'seconds')
print('Last commit id: ' + subprocess.getoutput('git log --format="%H" -n 1'))
if args.upload:
    github = read_env()['github']
    headers = {'Authorization': f'token {github}', 'Accept': 'application/vnd.github.v3+json'}
    username = 'elibroftw'
    github_api = 'https://api.github.com'

    # check if tag vVERSION does not exist
    r = requests.get(f'{github_api}/repos/{username}/music-caster/releases/tags/v{VERSION}', headers=headers)
    if r.status_code != 404: print(f'ERROR: Tag v{VERSION} already exists')

    old_release = requests.get(f'{github_api}/repos/{username}/music-caster/releases/latest').json()
    old_release_id = old_release['id']
    body = '' if VERSION.endswith('.0') else old_release['body']
    body = add_new_changes(body)
    #  chain changelog if not a major release

    new_release = {
        'tag_name': f'v{VERSION}',
        'target_commitish': 'master',
        'name': f'Music Caster v{VERSION}',
        'body': body,
        'draft': True,
        'prerelease': False
    }
    r = requests.post(f'{github_api}/repos/{username}/music-caster/releases', json=new_release, headers=headers)
    release = r.json()
    upload_url = release['upload_url'][:-13]
    release_id = release['id']
    # upload assets
    for dist_file in ('Music Caster Setup.exe', 'Portable.zip', 'Source Files Condensed.zip'):
        with open(f'dist/{dist_file}', 'rb') as f:
            data = f.read()
        print(f'Uploading {dist_file}...')
        requests.post(upload_url, data=data, params={'name': dist_file},
                      headers={**headers, 'Content-Type': 'application/octet-stream'})
    requests.post(f'{github_api}/repos/{username}/music-caster/releases/{release_id}',
                  headers=headers, json={'body': body, 'draft': False})
    if not VERSION.endswith('.0'):
        # delete old release if not a new major build
        requests.delete(f'{github_api}/repos/{username}/music-caster/releases/{old_release_id}', headers=headers)
    print(f'Published Release v{VERSION}')
    print(f'v{VERSION} Total Time Taken:', round(time.time() - start_time, 2), 'seconds')
