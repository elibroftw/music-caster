#!/usr/bin/env python3
import argparse
import glob
import math
import os
import platform
import shutil
import sys
import threading
import time
import zipfile
from contextlib import suppress
from datetime import datetime
from subprocess import check_call, Popen, getoutput, DEVNULL

from meta import VERSION

start_time = time.time()
starting_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
os.chdir(starting_dir)
# CONSTANTS
YEAR = datetime.today().year
SETUP_OUTPUT_NAME = 'Music Caster Setup'
UPDATER_DIST_PATH = 'Music Caster Updater/bin/x86/Release/netcoreapp3.1'
VERSION_FILE = 'build_files/mc_version_info.txt'
INSTALLER_SCRIPT = 'build_files/setup_script.iss'
PORTABLE_SPEC = 'build_files/portable.spec'
ONEDIR_SPEC = 'build_files/onedir.spec'
UPDATER_SPEC_FILE = 'build_files/updater.spec'

parser = argparse.ArgumentParser(description='Music Caster Build Script')
parser.add_argument('--debug', '-d', default=False, action='store_true', help='build as console app + debug=True')
parser.add_argument('--ver_update', '-v', default=False, action='store_true', help="Only update build files' version")
parser.add_argument('--clean', '-c', default=False, action='store_true', help='Use pyinstaller --clean flag')
parser.add_argument('--upload', '-u', '--publish', default=False, action='store_true',
                    help='Upload and Publish to GitHub after building')
parser.add_argument('--skip-build', default=False, action='store_true',
                    help='Skip to testing / uploading')
parser.add_argument('--skip-tests', '--st', default=False, action='store_true',
                    help='Skip testing')
parser.add_argument('--force-install', '-f', default=False, action='store_true', help='Force install after build')
parser.add_argument('--deps', '--dry', default=False, action='store_true', help='does not modify anything')
parser.add_argument('--test-autoupdate', default=False, action='store_true', help='use if testing auto update')
parser.add_argument('--skip-deps', '-i', default=False, action='store_true', help='skips installation of dependencies')
parser.add_argument('--no-install', default=False, action='store_true', help='do not install after building')
parser.add_argument('--ytdl', default=False, action='store_true', help='version++ if new youtube-dl available')
parser.add_argument('--keep-finals', default=False, action='store_true', help='keep final pre-packaged files after packaging them')
args = parser.parse_args()
if args.deps:
    print('Building Music Caster (only install dependencies)')
else:
    print('Building Music Caster (only install dependencies)')


def update_versions():
    """ Update versions of version file and installer script """
    with open(VERSION_FILE, 'r+', encoding='utf-8') as version_info_file:
        lines = version_info_file.readlines()
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
        version_info_file.seek(0)
        version_info_file.writelines(lines)
        version_info_file.truncate()

    with open(INSTALLER_SCRIPT, 'r+', encoding='utf-8') as version_info_file:
        lines = version_info_file.readlines()
        for i, line in enumerate(lines):
            if line.startswith('#define MyAppVersion'):
                lines[i] = f'#define MyAppVersion "{VERSION}"\n'
            elif line.startswith('OutputBaseFilename'):
                lines[i] = f'OutputBaseFilename={SETUP_OUTPUT_NAME}\n'
                break
        version_info_file.seek(0)
        version_info_file.writelines(lines)
        version_info_file.truncate()


if 'ModuleNotFoundError' not in VERSION:
    if args.ytdl:
        import requests
        latest_ytdl = 'https://api.github.com/repos/ytdl-org/youtube-dl/releases/latest'
        latest_mc = 'https://api.github.com/repos/elibroftw/music-caster/releases/latest'
        ytdl_publish = requests.get(latest_ytdl).json()['published_at']
        t = datetime.strptime(ytdl_publish, '%Y-%m-%dT%H:%M:%SZ')
        mc_publish = requests.get(latest_mc).json()['published_at']
        t2 = datetime.strptime(mc_publish, '%Y-%m-%dT%H:%M:%SZ')
        if t2 < t:  # latest youtube-dl not used in latest MC
            print('New YouTube-dl found, updating Music Caster version')
            # if youtube-dl was released after the latest music-caster, update version and publish
            maj, _min, fix = VERSION.split('.')
            fix = int(fix) + 1
            new_version = f'{maj}.{_min}.{fix}'
            with open('music_caster.py', 'r+', encoding='utf-8') as f:
                # VERSION = latest_version = '5.0.0'
                new_txt = f.read().replace(f"VERSION = latest_version = '{VERSION}'",
                                           f"VERSION = latest_version = '{new_version}'")
                f.seek(0)
                f.write(new_txt)
            # TODO: update CHANGELOG
            with open('build_files/CHANGELOG.txt', 'r+', encoding='utf-8') as f:
                content = ''.join((f.readline(), f'\n{VERSION}\n- [Fix] URL\n', f.read()))
                f.seek(0)
                f.write(content)

            VERSION = new_version
            update_versions()
            # commit and push change
            from git import Repo
            repo = Repo('.git')
            repo.git.add(update=True)
            origin = repo.remote(name='origin')
            origin.push()
            repo.index.commit('Updated youtube-dl')
    else:
        update_versions()
    print('Updated versions of build files')
    if args.ver_update: sys.exit()
    pip_cmd = f'"{sys.executable}" -m pip install --upgrade --user -r requirements.txt -r requirements-dev.txt'
else:
    args.deps = True
    pip_cmd = f'"{sys.executable}" -m pip install --upgrade --user -r requirements.txt -r requirements-dev.txt --force-reinstall --force'
    print('INFO: could not get version, this build will only install the required modules')
if args.deps or (not args.skip_build and not args.skip_deps):
    print('Installing and/or upgrading dependencies...')
    if platform.system() == 'Windows':
        # install tkdnd custom way
        sys_dir_name = os.path.dirname(sys.executable)
        shutil.copytree('build_files/tkdnd2.9.2', f'{sys_dir_name}/tcl/tkdnd2.9.2', dirs_exist_ok=True)
        shutil.copytree('build_files/TkinterDnD2', f'{sys_dir_name}/Lib/site-packages/TkinterDnD2', dirs_exist_ok=True)
    if args.deps:
        Popen(pip_cmd, stdin=DEVNULL, stdout=None, text=True).wait()
        print('Finished installing dependencies. Try something else if errors occurred.')
        sys.exit()
    else:
        # suppress output if not dry
        getoutput(pip_cmd)


# import third party libraries
import requests
import traceback
from git import Repo
sys.argv = sys.argv[:1]
from music_caster import is_already_running, get_running_processes


def read_env(env_file='.env'):
    with open(env_file, encoding='utf-8') as env_file:
        env_line = env_file.readline()
        while env_line:
            k, v = env_line.split('=', 1)
            os.environ[k] = v.strip()
            env_line = env_file.readline()
    return os.environ


def add_new_changes(prev_changes: str):
    changes = set(prev_changes.split('\n'))
    with open('build_files/CHANGELOG.txt', encoding='utf-8') as changelog_file:
        add_changes = False
        line = changelog_file.readline()
        while line:
            line = line.strip()
            if line == VERSION:
                add_changes = True
            elif add_changes:
                if line == '': break
                changes.add(line)
            line = changelog_file.readline()
    if not add_changes:
        print(f'CHANGELOG does not contain changes for {VERSION}...')
        input('Press enter to try again...')
        return add_new_changes(prev_changes)
    return '\n'.join(sorted(changes, key=lambda item: item.casefold()))


def set_spec_debug(debug_option):
    for file_name in (ONEDIR_SPEC, PORTABLE_SPEC, UPDATER_SPEC_FILE):
        with open(file_name, 'r+', encoding='utf-8') as _f:
            new_spec = _f.read().replace(f'debug={not debug_option}', f'debug={debug_option}')
            new_spec = new_spec.replace(f'console={not debug_option}', f'console={debug_option}')
            _f.seek(0)
            _f.write(new_spec)
            _f.truncate()


def create_zip(zip_filename, files_to_zip, compression=zipfile.ZIP_BZIP2):
    with zipfile.ZipFile(zip_filename, 'w', compression=compression) as zf:
        for file_to_zip in files_to_zip:
            try:
                if type(file_to_zip) == tuple: zf.write(*file_to_zip)
                else: zf.write(file_to_zip)
            except FileNotFoundError:
                print(f'{file_to_zip} not found')


args.upload = args.upload and not args.test_autoupdate
try:
    player_state = requests.get('http://[::1]:2001/state').json()
    requests.get('http://[::1]:2001/exit')
    time.sleep(1)  # wait for MC to exit
except requests.exceptions.RequestException:
    player_state = {}
for process in get_running_processes('Music Caster.exe'):
    # force close any other instances of MC
    pid = process['pid']
    os.kill(pid, 9)
if args.debug: set_spec_debug(True)
else: set_spec_debug(False)
if args.upload: print('Will upload to GitHub after building')
if args.test_autoupdate: print("This test should test auto update and won't publish to GitHub")

if not args.skip_build:
    # remove existing builds
    try:
        with suppress(FileNotFoundError):
            shutil.rmtree('dist/Music Caster OneDir', False)
    except PermissionError:
        print('Files in "dist/Music Caster OneDir" are in use somehow')
        sys.exit()
    main_file = 'Music Caster'
    if platform.system() == 'Windows':
        main_file += '.exe'
    for dist_file in (main_file, f'{SETUP_OUTPUT_NAME}.exe', 'Portable.zip'):
        with suppress(FileNotFoundError):
            dist_file = os.path.join('dist', dist_file)
            print(f'Removing {dist_file}')
            os.remove(dist_file)
    shutil.rmtree(UPDATER_DIST_PATH, True)

if args.clean:
    shutil.rmtree('dist', True)
    shutil.rmtree('build', True)
    for file in glob.iglob('*.log'):
        os.remove(file)

if not args.skip_build:
    print(f'building executables with debug={args.debug}')
    additional_args = '--log=DEBUG' if args.debug else ''
    if args.clean:
        additional_args += ' --clean'
    if platform.system() == 'Windows':
        s1 = Popen(f'{sys.executable} -OO -m PyInstaller -y {additional_args} {PORTABLE_SPEC}', shell=True)
    else:
        s1 = None
    try:
        # build Updater
        # install go dependencies
        check_call('go install github.com/akavel/rsrc@latest')
        check_call('rsrc -manifest build_files/Updater.exe.MANIFEST -ico build_files/updater.ico')
        check_call('go build -ldflags "-s -w -H windowsgui" -o dist/Updater.exe')
    except Exception as e:
        print(f'WARNING: {e}')
    check_call(f'{sys.executable} -OO -m PyInstaller -y {additional_args} {ONEDIR_SPEC}', shell=True)
    try:
        if platform.system() == 'Windows':
            s4 = Popen('iscc build_files/setup_script.iss')
        else:
            s4 = None
    except FileNotFoundError:
        s4 = None
        print('WARNING: could not create an installer because iscc is not installed or is not on PATH')

    try:
        portable_failed = s1.wait()
    except AttributeError:
        portable_failed = False
    if args.debug: set_spec_debug(False)
    if portable_failed:
        print('Portable installation failed')
        print(s1.communicate()[1])
        sys.exit()

    # Portable
    if platform.system() == 'Windows':
        res_files = ['static/style.css', 'templates/index.html']
        lang_packs = glob.glob('languages/*.txt')
        music_caster_portable = ('dist/Music Caster.exe', 'Music Caster.exe')
        updater_portable = ('dist/Updater.exe', 'Updater.exe')
        portable_files = [music_caster_portable, ('build_files/CHANGELOG.txt', 'CHANGELOG.txt'), updater_portable]
        vlc_ext = 'dll' if platform.system() == 'Windows' else 'so'
        portable_files.extend(res_files)
        portable_files.extend(glob.iglob(f'vlc_lib/**/*.{vlc_ext}', recursive=True))
        portable_files.extend(glob.iglob(f'theme/**/*.*', recursive=True))
        portable_files.extend(lang_packs)
        print('Creating dist/Portable.zip')
        create_zip('dist/Portable.zip', portable_files, compression=zipfile.ZIP_DEFLATED)
        if args.keep_finals:
            for res_file in res_files:
                dst_file = f'dist/{res_file}'
                os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                shutil.copyfile(res_file, dst_file)
            shutil.copytree('vlc_lib', 'dist/vlc_lib', dirs_exist_ok=True)
            shutil.copytree('languages', 'dist/languages', dirs_exist_ok=True)
        else:
            for file in (music_caster_portable, updater_portable):
                os.remove(file[0])
            for directory in ('vlc_lib', 'languages', 'static', 'templates'):
                shutil.rmtree(f'dist/{directory}', ignore_errors=True)
    # zip directory for Linux or Darwin
    elif platform.system() == 'Darwin':
        pass
    else:
        shutil.rmtree('dist/Music Caster OneDir/share/')
        linux_dist = 'dist/Music Caster (Linux)'
        print(f'Creating {linux_dist}.zip')
        shutil.make_archive(linux_dist, 'zip', 'dist/Music Caster OneDir')
    with suppress(AttributeError): s4.wait()  # Wait for InnoSetup script to finish
    print(f'v{VERSION} Build Time:', round(time.time() - start_time, 2), 'seconds')
    print('Last commit: ' + getoutput('git log --format="%H" -n 1'))

if platform.system() == 'Windows':
    dist_files = ('Music Caster Setup.exe', 'Portable.zip')
elif platform.system() == 'Darwin':
    dist_files = ('Music Caster (OSX).zip',)
else:
    dist_files = ('Music Caster (Linux).zip',)

# check if all files were built
dist_files_exist = True
for dist_file in dist_files:
    dist_file_path = f'dist/{dist_file}'
    if os.path.exists(dist_file_path):
        file_size = os.path.getsize(dist_file_path) // 1000  # KB
        file_exists_str = f'EXISTS {file_size:,} KB'.rjust(12)
    else:
        file_exists_str = 'DOES NOT EXIST!'
        dist_files_exist = False
    print((dist_file + ':').ljust(30) + file_exists_str)


if dist_files_exist and platform.system() == 'Windows':
    with zipfile.ZipFile('dist/Portable.zip') as portable_zip:
        if 'Updater.exe' in portable_zip.namelist():
            print('Portable.zip/Updater.exe:'.ljust(30) + 'EXISTS')
        else:
            print('Portable.zip/Updater.exe:'.ljust(30) + 'DOES NOT EXIST!')
            dist_files_exist = False


def test(title, fn, assert_statement=False):
    try:
        if assert_statement:
            assert fn()
        else:
            fn()
    except Exception as _e:
        print('---')
        print('TEST FAILED', title)
        print('TEST TRACEBACK', traceback.format_exc())
        print('---')
        raise _e


if not args.skip_tests and dist_files_exist:
    try:
        sys.argv = sys.argv[:1]
        from test_harness import run_tests
        run_tests(uploading_after=args.upload, testing_autoupdate=args.test_autoupdate)
    except AssertionError as e:
        print('TESTS FAILED: test_helpers()')
        raise e
    # Test if executable can be run
    p = Popen('"dist/Music Caster OneDir/Music Caster" -m --debug', shell=True)
    time.sleep(5)
    test('Music Caster Should Be Running', lambda: is_already_running(threshold=1), True)
    time.sleep(2)
    test('Music Caster Exit API', lambda: requests.post('http://[::1]:2001/exit'))
    time.sleep(2)
    test('Music Caster Should Have Exited', lambda: not is_already_running(), True)
if not args.keep_finals:
    shutil.rmtree('dist/Music Caster OneDir', ignore_errors=True)


class ProgressUpload:
    def __init__(self, filename, chunk_size=1250):
        self.filename = filename
        self.chunk_size = chunk_size
        self.file_size = os.path.getsize(filename)
        self.size_read = 0
        self.divisor = min(math.floor(math.log(self.file_size, 1000)) * 3, 9)  # cap unit at a GB
        self.unit = {0: 'B', 3: 'KB', 6: 'MB', 9: 'GB'}[self.divisor]
        self.divisor = 10 ** self.divisor

    def __iter__(self):
        progress_str = f'0 / {self.file_size / self.divisor:.2f} {self.unit} (0 %)'
        sys.stderr.write(f'\rUploading {self.filename}: {progress_str}')
        with open(self.filename, 'rb') as file_to_upload:
            for chunk in iter(lambda: file_to_upload.read(self.chunk_size), b''):
                self.size_read += len(chunk)
                yield chunk
                sys.stderr.write('\b' * len(progress_str))
                percentage = self.size_read / self.file_size * 100
                completed_str = f'{self.size_read / self.divisor:.2f}'
                to_complete_str = f'{self.file_size / self.divisor:.2f} {self.unit}'
                progress_str = f'{completed_str} / {to_complete_str} ({percentage:.2f} %)'
                sys.stderr.write(progress_str)
                sys.stderr.flush()
        sys.stderr.write('\n')

    def __len__(self):
        return self.file_size


def local_install():
    exe = os.getenv('LOCALAPPDATA') + '/Programs/Music Caster/Music Caster.exe'
    cmd = ['dist/Music Caster Setup.exe', '/FORCECLOSEAPPLICATIONS', '/VERYSILENT', '/MERGETASKS="!desktopicon"']
    cmd.extend(('&&', exe))
    if not player_state.get('gui_open', False):
        cmd.append('--minimized')
    if player_state.get('status', 'NOT PLAYING') in ('PLAYING', 'PAUSED'):
        cmd.append('--start-playing')
        if player_state['status'] == 'PAUSED':
            cmd.append('--queue')
    if position := player_state.get('position', 0) > 0:
        cmd.append(f'--position={position}')
    Popen(cmd, shell=True)


if args.debug or not dist_files_exist:
    print('Exiting early to avoid upload or installation of possibly broken build')
    sys.exit()
print(f'Build v{VERSION} complete')
print('Time taken:', round(time.time() - start_time, 2), 'seconds')
print('Last commit: ' + getoutput('git log --format="%H" -n 1'))
if args.upload:
    print('Will try to upload to GitHub')
    # upload to GitHub
    github = read_env()['github']
    headers = {'Authorization': f'token {github}', 'Accept': 'application/vnd.github.v3+json'}
    USERNAME = 'elibroftw'
    github_api = 'https://api.github.com'

    # check if tag vVERSION does not exist
    r = requests.get(f'{github_api}/repos/{USERNAME}/music-caster/releases/tags/v{VERSION}', headers=headers)
    if r.status_code != 404:
        print(f'ERROR: Tag v{VERSION} already exists')
        sys.exit(1)

    old_release = requests.get(f'{github_api}/repos/{USERNAME}/music-caster/releases/latest').json()
    try:
        old_release_id = old_release['id']
    except KeyError:
        print('rate limit exceeded, upload manually at https://github.com/elibroftw/music-caster/releases')
        sys.exit()
    # keep changes of current major version if new version is a minor update
    body = '' if VERSION.endswith('.0') else old_release['body']
    body = add_new_changes(body)
    if any(Repo('../.git').index.diff(None)):
        input('Changed (not committed) files detected. Press enter to confirm upload.\n')
    print('Will upload and install at the same time!')
    t = threading.Thread(target=local_install)
    t.start()

    new_release = {
        'tag_name': f'v{VERSION}',
        'target_commitish': 'master',
        'name': f'Music Caster v{VERSION}',
        'body': body,
        'draft': True,
        'prerelease': False
    }
    r = requests.post(f'{github_api}/repos/{USERNAME}/music-caster/releases', json=new_release, headers=headers)
    release = r.json()
    upload_url = release['upload_url'][:-13]
    release_id = release['id']
    # upload assets
    for dist_file in dist_files:
        requests.post(upload_url, data=ProgressUpload(f'dist/{dist_file}'), params={'name': dist_file},
                      headers={**headers, 'Content-Type': 'application/octet-stream'})
    requests.post(f'{github_api}/repos/{USERNAME}/music-caster/releases/{release_id}',
                  headers=headers, json={'body': body, 'draft': False})
    # since winget is slower on the PR's, it's better to not delete anything
    # if not VERSION.endswith('.0'):
    #     # delete old release if not a new major build
    #     requests.delete(f'{github_api}/repos/{USERNAME}/music-caster/releases/{old_release_id}', headers=headers)
    print(f'Published Release v{VERSION}')
    print(f'v{VERSION} Total Time Taken:', round(time.time() - start_time, 2), 'seconds')
    t.join()
elif not args.no_install and (not args.skip_tests or args.force_install):
    print('Installing Music Caster and it will be launched after installation.')
    local_install()
