import argparse
from contextlib import suppress
from datetime import datetime
import glob
import math
import os
import re
import shutil
from shutil import copytree
from subprocess import check_call, Popen, getoutput, DEVNULL
import sys
import threading
import time
import winreg
import zipfile


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
parser.add_argument('--force-install', '-f', default=False, action='store_true', help='Force install')
parser.add_argument('--dry', default=False, action='store_true', help='skips the building part')
parser.add_argument('--test-autoupdate', default=False, action='store_true', help='use if testing auto update')
parser.add_argument('--skip-deps', '-i', default=False, action='store_true', help='skips installation of dependencies')
args = parser.parse_args()
if args.dry: print('Dry Build')


def update_versions():
    """ Update versions of version file and installer script """
    with open(VERSION_FILE, 'r+') as f:
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

    with open(INSTALLER_SCRIPT, 'r+') as f:
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


VERSION = getoutput('music_caster.py --version')
if 'ModuleNotFoundError' not in VERSION:
    update_versions()
    print('Updated versions of build files')
    if args.ver_update: sys.exit()
    pip_cmd = f'"{sys.executable}" -m pip install --upgrade --user -r requirements.txt'
else:
    args.dry = True
    args.skip_deps = args.skip_build = False
    pip_cmd = f'"{sys.executable}" -m pip install --upgrade --user -r requirements.txt --force'
    print('Warning: could not get version, will install modules')
if not args.skip_build and not args.skip_deps:
    print('Installing / Updating dependencies...')
    # install tkdnd
    sys_dir_name = os.path.dirname(sys.executable)
    shutil.copytree('build_files/tkdnd2.9.2', f'{sys_dir_name}/tcl/tkdnd2.9.2', dirs_exist_ok=True)
    shutil.copytree('build_files/TkinterDnD2', f'{sys_dir_name}/Lib/site-packages/TkinterDnD2', dirs_exist_ok=True)
    if args.dry:
        Popen(pip_cmd, stdin=DEVNULL, stdout=None, text=True).wait()
    else:
        # surpress output if not dry
        getoutput(pip_cmd)


# import third party libraries
try:
    import requests
    import traceback
    from git import Repo
except ImportError as e:
    print(e)
    print('Run build again or install from requirements.txt')
sys.argv = sys.argv[:1]
from music_caster import is_already_running, get_running_processes


def read_env(env_file='.env'):
    with open(env_file) as f:
        env_line = f.readline()
        while env_line:
            k, v = env_line.split('=', 1)
            os.environ[k] = v.strip()
            env_line = f.readline()
    return os.environ


def get_msbuild():
    reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
    root_key = winreg.OpenKey(reg, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall',
                              0, winreg.KEY_READ | winreg.KEY_WOW64_32KEY)
    num_sub_keys = winreg.QueryInfoKey(root_key)[0]
    vs = {}
    for i in range(num_sub_keys):
        with suppress(EnvironmentError):
            software: dict = {}
            software_key = winreg.EnumKey(root_key, i)
            software_key = winreg.OpenKey(root_key, software_key)
            info_key = winreg.QueryInfoKey(software_key)
            for value in range(info_key[1]):
                value = winreg.EnumValue(software_key, value)
                software[value[0]] = value[1]
            display_name = software.get('DisplayName', '')
            if re.search(r'Visual Studio (Community|Professional|Enterprise)', display_name):
                software['ver'] = int(software['DisplayName'].rsplit(maxsplit=1)[1])
                vs_ver = vs.get('ver', 0)
                if software['ver'] > vs_ver:
                    vs = software
    if vs is None: raise RuntimeWarning('No installation of Visual Studio could be found')
    ms_build_path = vs['InstallLocation'] + r'\MSBuild\Current\Bin\MSBuild.exe'
    return ms_build_path


def add_new_changes(prev_changes: str):
    changes = set(prev_changes.split('\n'))
    with open('build_files/CHANGELOG.txt') as f:
        add_changes = False
        line = f.readline()
        while line:
            line = line.strip()
            if line == VERSION:
                add_changes = True
            elif add_changes:
                if line == '': break
                changes.add(line)
            line = f.readline()
    if not add_changes:
        print(f'CHANGELOG does not contain changes for {VERSION}...')
        input('Press enter to try again...')
        return add_new_changes(prev_changes)
    return '\n'.join(sorted(changes, key=lambda item: item.lower()))


def set_spec_debug(debug_option):
    with open(PORTABLE_SPEC, 'r+') as _f:
        new_spec = _f.read().replace(f'debug={not debug_option}', f'debug={debug_option}')
        new_spec = new_spec.replace(f'console={not debug_option}', f'console={debug_option}')
        _f.seek(0)
        _f.write(new_spec)
        _f.truncate()
    with open(ONEDIR_SPEC, 'r+') as _f:
        new_spec = _f.read().replace(f'debug={not debug_option}', f'debug={debug_option}')
        new_spec = new_spec.replace(f'console={not debug_option}', f'console={debug_option}')
        _f.seek(0)
        _f.write(new_spec)
        _f.truncate()
    with open(UPDATER_SPEC_FILE, 'r+') as _f:
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
player_state = {}
if not args.dry:
    with suppress(requests.RequestException):
        player_state = requests.get('http://[::1]:2001/state').json()
        requests.get('http://[::1]:2001/exit')
        time.sleep(1)  # wait for MC to exit
    for process in get_running_processes('Music Caster.exe'):
        # force close any other instances of MC
        pid = process['pid']
        os.kill(pid, 9)
if args.debug and not args.dry: set_spec_debug(True)
else: set_spec_debug(False)
if args.upload and not args.dry: print('Will upload to GitHub after building')
if args.test_autoupdate and not args.dry: print("This test should test auto update and won't publish to GitHub")

if not args.skip_build:
    # remove existing builds
    try:
        with suppress(FileNotFoundError):
            shutil.rmtree('dist/Music Caster', False)
    except PermissionError:
        print('Files in dist/Music caster are in use somehow')
        sys.exit()
    for dist_file in ('Music Caster.exe', f'{SETUP_OUTPUT_NAME}.exe', 'Portable.zip', 'Source Files Condensed.zip'):
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

if not args.dry and not args.skip_build:
    # Useful if any errors occur: C:\Users\maste\AppData\Roaming\pyinstaller
    print(f'building executables with debug={args.debug}')
    additional_args = '--log=DEBUG' if args.debug else ''
    if args.clean:
        additional_args += ' --clean'
    s1 = Popen(f'{sys.executable} -OO -m PyInstaller -y {additional_args} {PORTABLE_SPEC}')
    try:
        ms_build = get_msbuild()
        check_call(f'{ms_build} "{starting_dir}/Music Caster Updater/Music Caster Updater.sln"'
                   f' /t:Build /p:Configuration=Release /p:PlatformTarget=x86')
    except RuntimeWarning as e:
        print(f'WARNING: {e}')
    check_call(f'{sys.executable} -OO -m PyInstaller -y {additional_args} {ONEDIR_SPEC}')
    try:
        s4 = Popen('iscc build_files/setup_script.iss')
    except FileNotFoundError:
        s4 = None
        print('WARNING: could not create an installer because iscc is not installed or is not on PATH')
    portable_failed = s1.wait()
    if args.debug: set_spec_debug(False)
    if portable_failed:
        print('Portable installation failed')
        print(s1.communicate()[1])
        sys.exit()

    for folder in {'dist/static', 'dist/templates'}:
        with suppress(OSError): os.mkdir(folder)

    copytree('vlc_lib', 'dist/vlc_lib', dirs_exist_ok=True)
    copytree('languages', 'dist/languages', dirs_exist_ok=True)

    res_files = ['static/style.css', 'templates/index.html']
    for res_file in res_files:
        shutil.copyfile(res_file, 'dist/' + res_file)
    lang_packs = glob.glob('languages/*.txt')
    # noinspection PyTypeChecker
    portable_files = [('dist/Music Caster.exe', 'Music Caster.exe'), ('build_files/CHANGELOG.txt', 'CHANGELOG.txt')]
    portable_files.extend(res_files + glob.glob('vlc_lib/**/*.*', recursive=True))
    portable_files.extend(lang_packs)
    portable_files.extend([(f, os.path.basename(f)) for f in glob.iglob(f'{glob.escape(UPDATER_DIST_PATH)}/*.*')])
    print('Creating dist/Portable.zip')
    create_zip('dist/Portable.zip', portable_files, compression=zipfile.ZIP_DEFLATED)
    print('Creating dist/Source Files Condensed.zip')
    create_zip('dist/Source Files Condensed.zip', ['music_caster.py', 'helpers.py'])
    with suppress(AttributeError): s4.wait()  # Wait for inno script to finish
    print(f'v{VERSION} Build Time:', round(time.time() - start_time, 2), 'seconds')
    print('Last commit id: ' + getoutput('git log --format="%H" -n 1'))

dist_files = ('Music Caster Setup.exe', 'Portable.zip', 'Source Files Condensed.zip')

# check if all files were built
tests_passed = True
for dist_file in dist_files:
    file_name = f'dist/{dist_file}'
    file_exists = os.path.exists(file_name)
    file_exists_str = 'EXISTS' if file_exists else 'DOES NOT EXIST!'
    if file_exists:
        file_size = os.path.getsize(file_name) // 1000  # KB
        file_exists_str += f' {file_size:,} KB'.rjust(12)
    output_string = (dist_file + ':').ljust(30) + file_exists_str
    print(output_string)
    if not file_exists: tests_passed = False


if tests_passed:
    with zipfile.ZipFile('dist/Portable.zip') as portable_zip:
        if 'Updater.exe' in portable_zip.namelist():
            print('Portable.zip/Updater.exe:'.ljust(30) + 'EXISTS')
        else:
            print('Portable.zip/Updater.exe:'.ljust(30) + 'DOES NOT EXIST!')
            tests_passed = False


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


if not args.dry and not args.skip_tests and tests_passed:
    try:
        sys.argv = sys.argv[:1]
        from test_harness import run_tests
        run_tests(uploading_after=args.upload, testing_autoupdate=args.test_autoupdate)
    except AssertionError as e:
        print('TESTS FAILED: test_helpers()')
        raise e
    # Test if executable can be run [disables auto update or some shit]
    p = Popen('"dist/Music Caster/Music Caster.exe" -m --debug', shell=True)
    time.sleep(2)
    test('Music Caster Should Be Running', lambda: is_already_running(threshold=1), True)
    time.sleep(2)
    test('Music Caster Exit API', lambda: requests.get('http://[::1]:2001/exit'))
    time.sleep(2)
    test('Music Caster Should Have Exited', lambda: not is_already_running(), True)


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
        with open(self.filename, 'rb') as f:
            for chunk in iter(lambda: f.read(self.chunk_size), b''):
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
    cmd = ['dist/Music Caster Setup.exe', '/FORCECLOSEAPPLICATIONS', '/VERYSILENT', '/MERGETASKS="!desktopicon"', '&&', exe]
    if not player_state.get('gui_open', False):
        cmd.append('--minimized')
    if player_state.get('status', 'NOT PLAYING') in ('PLAYING', 'PAUSED'):
        cmd.append('--start-playing')
        if player_state['status'] == 'PAUSED':
            cmd.append('--queue')
    if position := player_state.get('position', 0) > 0:
        cmd.append(f'--position={position}')
    Popen(cmd, shell=True)


if args.upload and tests_passed and not args.dry and not args.debug:
    # upload to GitHub
    github = read_env()['github']
    headers = {'Authorization': f'token {github}', 'Accept': 'application/vnd.github.v3+json'}
    USERNAME = 'elibroftw'
    github_api = 'https://api.github.com'

    # check if tag vVERSION does not exist
    r = requests.get(f'{github_api}/repos/{USERNAME}/music-caster/releases/tags/v{VERSION}', headers=headers)
    if r.status_code != 404: print(f'ERROR: Tag v{VERSION} already exists')

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
elif args.force_install or (tests_passed and not args.dry and not args.debug and not args.skip_tests):
    print('Installing Music Caster [Will Launch After]')
    local_install()
