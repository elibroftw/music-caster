import time
from subprocess import DEVNULL, check_call, Popen, CalledProcessError, getoutput
import os
import shutil
import zipfile
import sys
from contextlib import suppress
from datetime import datetime
import argparse
import glob
from distutils.dir_util import copy_tree
import requests
import win32com.client
from win32comext.shell import shell, shellcon
import traceback

parser = argparse.ArgumentParser(description='Music Caster Build Script')
parser.add_argument('--debug', '-d', default=False, action='store_true', help='build as console app + debug=True')
parser.add_argument('--ver_update', '-v', default=False, action='store_true', help="Only update build files' version")
parser.add_argument('--clean', '-c', default=False, action='store_true', help='Use pyinstaller --clean flag')
parser.add_argument('--upload', '-u', '--publish', default=False, action='store_true',
                    help='Upload and Publish to GitHub after building')
parser.add_argument('--skip_build', '-t', default=False, action='store_true',
                    help='Skip to testing / uploading')
parser.add_argument('--dry', default=False, action='store_true', help='skips the building part')
parser.add_argument('--skip_deps', '-i', default=False, action='store_true', help='skips installation of depencencies')
args = parser.parse_args()
start_time = time.time()
YEAR = datetime.today().year
SETUP_OUTPUT_NAME = 'Music Caster Setup'
starting_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
os.chdir(starting_dir)
MSBuild = r'C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\MSBuild\Current\Bin\MSBuild.exe'
PORTABLE_SPEC_FILE = 'build_files/portable.spec'
ONEDIR_SPEC_FILE = 'build_files/onedir.spec'
UPDATER_SPEC_FILE = 'build_files/updater.spec'
UPDATER_DIST_PATH = r'Music Caster Updater\bin\x86\Release\netcoreapp3.1'
sys.argv = sys.argv[:1]
from music_caster import is_already_running, get_running_processes, VERSION


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


def set_spec_debug(debug_option):
    with open(PORTABLE_SPEC_FILE, 'r+') as _f:
        new_spec = _f.read().replace(f'debug={not debug_option}', f'debug={debug_option}')
        new_spec = new_spec.replace(f'console={not debug_option}', f'console={debug_option}')
        _f.seek(0)
        _f.write(new_spec)
        _f.truncate()
    with open(ONEDIR_SPEC_FILE, 'r+') as _f:
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


def create_zip(zip_filename, files_to_zip, compression=zipfile.ZIP_BZIP2):
    with zipfile.ZipFile(zip_filename, 'w', compression=compression) as zf:
        for file_to_zip in files_to_zip:
            try:
                if type(file_to_zip) == tuple: zf.write(*file_to_zip)
                else: zf.write(file_to_zip)
            except FileNotFoundError:
                print(f'{file_to_zip} not found')


if args.dry: print('Dry Build')
else:
    for process in get_running_processes('Music Caster.exe'):
        pid = process['pid']
        os.kill(pid, 9)
if not args.skip_build:
    update_versions()
    print('Updated versions of build files')
if args.ver_update: sys.exit()
if args.debug and not args.dry: set_spec_debug(True)
else: set_spec_debug(False)
if args.upload and not args.dry: print('Will upload to GitHub after building')

if not args.skip_build:
    # remove existing builds
    try:
        with suppress(FileNotFoundError):
            shutil.rmtree('dist/Music Caster', False)
    except PermissionError:
        print('files in dist/Music caster are in use somehow')
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

if not args.skip_build and not args.skip_deps:
    print('Installing / Updating dependencies...')
    pyaudio_whl = 'PyAudio-0.2.11-cp38-cp38-win32.whl'
    pyinstaller_whl = 'pyinstaller-4.0+19fb799a11-py3-none-any.whl'
    py_exe = sys.executable
    getoutput(f'{py_exe} -m pip install --upgrade -r requirements.txt')
    for whl in (pyaudio_whl, pyinstaller_whl):
        try: check_call(f'{py_exe} -m pip install build_files\\{whl}'.split(), stdout=DEVNULL)
        except CalledProcessError: print(f'WARNING: {whl} could not be installed with')
if not args.dry and not args.skip_build:
    print(f'building executables with debug={args.debug}')
    py_installer_exe = f'{os.path.dirname(sys.executable)}\\Scripts\\pyinstaller.exe'
    try: s1 = Popen(f'pyinstaller {"--clean" if args.clean else ""} {PORTABLE_SPEC_FILE}')
    except FileNotFoundError: s1 = Popen(f'"{py_installer_exe}" {PORTABLE_SPEC_FILE}')
    check_call(f'{MSBuild} "{starting_dir}\\Music Caster Updater\\Music Caster Updater.sln"'
               f' /t:Build /p:Configuration=Release /p:PlatformTarget=x86')
    # try: s2 = subprocess.Popen('pyinstaller {UPDATER_SPEC_FILE}')
    # except FileNotFoundError: s2 = subprocess.Popen(f'"{py_installer_exe}" {UPDATER_SPEC_FILE}')
    try: check_call(f'pyinstaller {"--clean" if args.clean else ""} {ONEDIR_SPEC_FILE}')
    except FileNotFoundError: check_call(f'"{py_installer_exe}" {ONEDIR_SPEC_FILE}')
    # s2.wait()
    try: s4 = Popen('iscc build_files/setup_script.iss')
    except FileNotFoundError: s4 = None
    portable_failed = s1.wait()
    if args.debug: set_spec_debug(False)
    if portable_failed:
        print('Portable installation failed')
        print(s1.communicate()[1])
        sys.exit()

    for folder in {'dist/static', 'dist/templates'}:
        with suppress(OSError): os.mkdir(folder)

    copy_tree('vlc_lib', 'dist/vlc_lib')
    copy_tree('languages', 'dist/languages')

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
    create_zip('dist/Source Files Condensed.zip', ['music_caster.py', 'helpers.py', 'b64_images.py',
                                                   'requirements.txt', 'settings.json',
                                                   ('../resources/Music Caster Icon.ico', 'icon.ico')
                                                   ] + res_files + lang_packs)
    if s4 is not None: s4.wait()  # Wait for inno script to finish
    else: print('WARNING: could not create an installer: iscc is not installed or is not on path')
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


if not args.dry and tests_passed:
    try:
        sys.argv = sys.argv[:1]
        from test_harness import run_tests
        run_tests(uploading_after=args.upload)
    except AssertionError as e:
        print('TESTS FAILED: test_helpers()')
        raise e
    # Test if executable can be run
    p = Popen('"dist/Music Caster/Music Caster.exe"', shell=True)
    time.sleep(2)
    test('Music Caster Should Be Running', lambda: is_already_running(threshold=1), True)
    time.sleep(2)
    test('Music Caster Exit API', lambda: requests.get('http://127.0.0.1:2001/exit'))
    time.sleep(2)
    test('Music Caster Should Have Exited', lambda: not is_already_running(), True)


if args.upload and tests_passed and not args.dry:
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
    r = requests.post(f'{github_api}/repos/{USERNAME}/music-caster/releases', json=new_release, headers=headers)
    release = r.json()
    upload_url = release['upload_url'][:-13]
    release_id = release['id']
    # upload assets
    for dist_file in dist_files:
        with open(f'dist/{dist_file}', 'rb') as f:
            print(f'Uploading {dist_file}...')
            requests.post(upload_url, data=f, params={'name': dist_file},
                          headers={**headers, 'Content-Type': 'application/octet-stream'})
    requests.post(f'{github_api}/repos/{USERNAME}/music-caster/releases/{release_id}',
                  headers=headers, json={'body': body, 'draft': False})
    if not VERSION.endswith('.0'):
        # delete old release if not a new major build
        requests.delete(f'{github_api}/repos/{USERNAME}/music-caster/releases/{old_release_id}', headers=headers)
    print(f'Published Release v{VERSION}')
    print(f'v{VERSION} Total Time Taken:', round(time.time() - start_time, 2), 'seconds')
if tests_passed and not args.dry:
    print('Installing Music Caster [Will Launch After]')
    startup_dir = shell.SHGetFolderPath(0, (shellcon.CSIDL_STARTUP, shellcon.CSIDL_COMMON_STARTUP)[0], None, 0)
    shortcut_path = startup_dir + '\\Music Caster.lnk'
    shell = win32com.client.Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(shortcut_path)
    exe = shortcut.Targetpath
    install_cmd = '"dist\\Music Caster Setup.exe" /FORCECLOSEAPPLICATIONS /VERYSILENT /MERGETASKS="!desktopicon"'
    cmd = f'{install_cmd} && "{exe}"'
    Popen(cmd, shell=True)
