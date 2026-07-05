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
import traceback
import zipfile
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from subprocess import DEVNULL, CalledProcessError, Popen, check_call, getoutput
from multiprocessing import freeze_support

if __name__ == '__main__':
    freeze_support()

from src.meta import VERSION, USING_TAURI_FRONTEND

# build constants
script_dir = Path(__file__).parent
SRC_DIR = script_dir / 'src'
DIST_DIR = script_dir / 'dist'
build_files = script_dir / 'build_files'
SETUP_OUTPUT_NAME = 'Music Caster Setup'
VERSION_FILE = build_files / 'mc_version_info.txt'
INSTALLER_SCRIPT = build_files / 'setup_script.iss'
PORTABLE_SPEC = build_files / 'portable.spec'
DAEMON_SPEC = build_files / 'daemon.spec'
ONEDIR_SPEC = build_files / 'onedir.spec'
UPDATER_SPEC_FILE = build_files / 'updater.spec'
CHANGELOG_FILE = script_dir / 'CHANGELOG.txt'
TKDND_FILES = (build_files / 'tkdnd2.9.2', build_files / 'TkinterDnD2')
UPDATER_MANIFEST_FILE = build_files / 'Updater.exe.MANIFEST'
UPDATER_ICO = build_files / 'updater.ico'
UPDATER_DIST = DIST_DIR / 'Updater.exe'
REQUIREMENTS_FILE = script_dir / 'requirements.txt'
REQUIREMENTS_DEV_FILE = script_dir / 'requirements-dev.txt'
SRC_FRONTEND = script_dir / 'src-frontend'

IS_VENV = sys.prefix != sys.base_prefix

error_inno_missing = False
updater_build_failed = False
updater_build_error = None

class ProgressUpload:
    # 1MB chunk size
    def __init__(self, filename, chunk_size=1_024_000):
        self.filename = filename
        self.chunk_size = chunk_size
        self.file_size = os.path.getsize(filename)
        self.size_read = 0
        self.divisor = min(math.floor(math.log(self.file_size, 1000)) * 3,
                           9)  # cap unit at a GB
        self.unit = {0: 'B', 3: 'KB', 6: 'MB', 9: 'GB'}[self.divisor]
        self.divisor = 10**self.divisor

    def __iter__(self):
        progress_str = f'0 / {self.file_size / self.divisor:.2f} {self.unit} (0 %)'
        sys.stderr.write(f'\rUploading {self.filename}: {progress_str}')
        with open(self.filename, 'rb') as file_to_upload:
            for chunk in iter(lambda: file_to_upload.read(self.chunk_size),
                              b''):
                self.size_read += len(chunk)
                yield chunk
                sys.stderr.write('\b' * len(progress_str))
                percentage = self.size_read / self.file_size * 100
                completed_str = f'{self.size_read / self.divisor:.2f}'
                to_complete_str = f'{self.file_size / self.divisor:.2f} {self.unit}'
                progress_str = (
                    f'{completed_str} / {to_complete_str} ({percentage:.2f} %)'
                )
                sys.stderr.write(progress_str)
                sys.stderr.flush()
        sys.stderr.write('\n')

    def __len__(self):
        return self.file_size


def read_env(env_file='.env'):
    if not args.ci:
        with open(env_file, encoding='utf-8') as env_file:
            env_line = env_file.readline()
            while env_line:
                k, v = env_line.split('=', 1)
                os.environ[k] = v.strip()
                env_line = env_file.readline()
    return os.environ


def get_latest_changelog():
    """Return the changelog entries for the latest (top-most) version in CHANGELOG.txt"""
    changes = []
    with open(CHANGELOG_FILE, encoding='utf-8') as _file:
        found_version = False
        for line in _file:
            line = line.rstrip()
            if not found_version:
                # the first non-empty line after the title that isn't the title is the latest version
                if line and line != 'Music Caster Changelog':
                    found_version = True
            elif line == '':
                break
            else:
                changes.append(line)
    return '\n'.join(changes)


def add_new_changes(prev_changes: str):
    changes = set(prev_changes.split('\n'))
    with open(CHANGELOG_FILE, encoding='utf-8') as _file:
        add_changes = False
        line = _file.readline()
        while line:
            line = line.strip()
            if line == VERSION:
                add_changes = True
            elif add_changes:
                if line == '':
                    break
                changes.add(line)
            line = _file.readline()
    if not add_changes:
        # TODO: generate changelog from commits
        #       could use AI/LLM for summarizing subjects
        #       see modern-desktop-app
        print(f'CHANGELOG does not contain changes for {VERSION}...')
        if args.ci:
            sys.exit(3)
        input('Press enter to try again...')
        return add_new_changes(prev_changes)
    return '\n'.join(sorted(changes, key=lambda item: item.casefold()))


def set_spec_debug(debug_option):
    for file_name in (ONEDIR_SPEC, PORTABLE_SPEC, UPDATER_SPEC_FILE):
        with open(file_name, 'r+', encoding='utf-8', newline='\n') as _f:
            new_spec = _f.read().replace(f'debug={not debug_option}',
                                         f'debug={debug_option}')
            new_spec = new_spec.replace(f'console={not debug_option}',
                                        f'console={debug_option}')
            _f.seek(0)
            _f.write(new_spec)
            _f.truncate()


def create_zip(zip_filename, files_to_zip, compression=zipfile.ZIP_BZIP2):
    with zipfile.ZipFile(zip_filename, 'w', compression=compression) as zf:
        for file_to_zip in files_to_zip:
            try:
                if type(file_to_zip) == tuple:
                    zf.write(*file_to_zip)
                else:
                    zf.write(file_to_zip)
            except FileNotFoundError:
                print(f'{file_to_zip} not found')


def update_versions(version):
    """Update versions of version file and installer script"""
    with open(VERSION_FILE, 'r+', encoding='utf-8', newline='\n') as version_info_file:
        lines = version_info_file.readlines()
        for i, line in enumerate(lines):
            if line.startswith('    prodvers'):
                version_tuple = ', '.join(version.split('.'))
                lines[i] = f'    prodvers=({version_tuple}, 0),\n'
            elif line.startswith('    filevers'):
                version_tuple = ', '.join(version.split('.'))
                lines[i] = f'    filevers=({version_tuple}, 0),\n'
            elif line.startswith("        StringStruct('FileVersion"):
                lines[
                    i] = f"        StringStruct('FileVersion', '{version}.0'),\n"
            elif line.startswith("        StringStruct('LegalCopyright'"):
                lines[
                    i] = f"        StringStruct('LegalCopyright', 'Copyright (c) 2019 - {YEAR}, Elijah Lopez'),\n"
            elif line.startswith("        StringStruct('ProductVersion"):
                lines[
                    i] = f"        StringStruct('ProductVersion', '{version}.0')])\n"
                break
        version_info_file.seek(0)
        version_info_file.writelines(lines)
        version_info_file.truncate()

    with open(INSTALLER_SCRIPT, 'r+', encoding='utf-8', newline='\n') as version_info_file:
        lines = version_info_file.readlines()
        for i, line in enumerate(lines):
            if line.startswith('#define MyAppVersion'):
                lines[i] = f'#define MyAppVersion "{version}"\n'
            elif line.startswith('OutputBaseFilename'):
                lines[i] = f'OutputBaseFilename={SETUP_OUTPUT_NAME}\n'
                break
        version_info_file.seek(0)
        version_info_file.writelines(lines)
        version_info_file.truncate()


def local_install():
    exe = os.getenv('LOCALAPPDATA') + '/Programs/Music Caster/Music Caster.exe'
    cmd = [
        str(DIST_DIR / 'Music Caster Setup.exe'),
        '/FORCECLOSEAPPLICATIONS',
        '/VERYSILENT',
        '/MERGETASKS="!desktopicon"',
    ]
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


def test(title, fn, assert_statement=False):
    try:
        if assert_statement:
            assert fn(), title
        else:
            fn()
    except Exception as _e:
        print('---')
        print('TEST FAILED', title)
        print('TEST TRACEBACK', traceback.format_exc())
        print('---')
        raise _e


def upgrade_yt_dlp():
    """Bump Music Caster's version if yt-dlp has a commit newer than our latest release,
    unless a bump PR is already open or a previous bump is still awaiting release."""
    import json
    import requests

    # don't propose another bump if one is already open and unmerged - the workflow
    # only deletes this branch on merge/close, so its existence means a bump PR is
    # already awaiting a decision
    branch_check = requests.get(
        'https://api.github.com/repos/elibroftw/music-caster/branches/auto/yt-dlp-upgrade')
    if branch_check.status_code == 200:
        print('A yt-dlp bump PR is already open, skipping')
        return

    latest_mc = requests.get('https://api.github.com/repos/elibroftw/music-caster/releases/latest').json()
    latest_release_version = latest_mc['tag_name'].lstrip('v')
    mc_release_time = datetime.strptime(latest_mc['published_at'], '%Y-%m-%dT%H:%M:%SZ')

    # meta.VERSION is being deprecated; app/package.json is the source of truth
    package_json = script_dir / 'app' / 'package.json'
    with open(package_json, encoding='utf-8') as f:
        package_json_content = f.read()
    current_version = json.loads(package_json_content)['version']
    # if package.json is already ahead of the latest release, a bump has already been
    # merged and is just waiting to be released - don't propose another one
    if tuple(map(int, current_version.split('.'))) > tuple(map(int, latest_release_version.split('.'))):
        return

    latest_ytdl = 'https://api.github.com/repos/yt-dlp/yt-dlp/commits/master'
    yt_dlp_master = requests.get(latest_ytdl).json()
    yt_dlp_release_time = datetime.strptime(yt_dlp_master['commit']['author']['date'], '%Y-%m-%dT%H:%M:%SZ')
    if mc_release_time >= yt_dlp_release_time:  # latest yt-dlp already used in latest MC
        return
    print('New yt-dlp commit found, bumping Music Caster version')
    maj, _min, fix = current_version.split('.')
    new_version = f'{maj}.{_min}.{int(fix) + 1}'
    with open(package_json, 'w', encoding='utf-8', newline='\n') as f:
        f.write(package_json_content.replace(f'"version": "{current_version}"', f'"version": "{new_version}"'))
    with open(CHANGELOG_FILE, 'r+', encoding='utf-8', newline='\n') as f:
        content = ''.join(
            (f.readline(), f'\n{new_version}\n- Upgrade yt-dlp\n',
             f.read()))
        f.seek(0)
        f.write(content)


if __name__ == '__main__':
    start_time = time.time()
    starting_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    os.chdir(starting_dir)
    # CONSTANTS
    YEAR = datetime.today().year

    parser = argparse.ArgumentParser(description='Music Caster Build Script')
    parser.add_argument(
        '--debug',
        '-d',
        default=False,
        action='store_true',
        help='build as console app + debug=True',
    )
    parser.add_argument(
        '--ver_update',
        '-v',
        default=False,
        action='store_true',
        help="Only update build files' version",
    )
    parser.add_argument(
        '--clean',
        '-c',
        default=False,
        action='store_true',
        help='Use pyinstaller --clean flag',
    )
    parser.add_argument(
        '--upload',
        '-u',
        '--publish',
        default=False,
        action='store_true',
        help='Upload and Publish to GitHub after building',
    )
    parser.add_argument(
        '--skip-build',
        '--no-build',
        default=False,
        action='store_true',
        help='Skip to testing / uploading',
    )
    parser.add_argument('--skip-tests',
                        '--no-tests',
                        '--st',
                        default=False,
                        action='store_true',
                        help='Skip testing')
    parser.add_argument(
        '--force-install',
        '-f',
        default=False,
        action='store_true',
        help='Force install after build',
    )
    parser.add_argument(
        '--deps',
        '--dry',
        default=False,
        action='store_true',
        help='does not modify anything',
    )
    parser.add_argument(
        '--test-auto-update',
        default=False,
        action='store_true',
        help='use if testing auto update',
    )
    parser.add_argument(
        '--skip-deps',
        '--no-deps',
        '-i',
        default=False,
        action='store_true',
        help='skips installation of dependencies',
    )
    parser.add_argument(
        '--no-install',
        default=False,
        action='store_true',
        help='do not install after building',
    )
    parser.add_argument(
        '--ytdl',
        default=False,
        action='store_true',
        help='version++ if new youtube-dl available',
    )
    parser.add_argument(
        '--ci',
        default=False,
        action='store_true',
        help='if running in a CI do not prompt just fail',
    )
    parser.add_argument(
        '--changelog',
        default=False,
        action='store_true',
        help="print the latest version's changelog and exit",
    )
    parser.add_argument(
        '--target',
        default=None,
        help='Rust target triplet for the daemon artifact name '
             '(default: {architecture}-pc-windows-msvc)',
    )
    args = parser.parse_args()

    if args.changelog:
        print(get_latest_changelog())
        sys.exit()

    if args.clean:
        shutil.rmtree(DIST_DIR, True)
        shutil.rmtree('build', True)
        for file in glob.iglob('*.log'):
            os.remove(file)
        sys.exit()

    if args.deps:
        print('Installing Music Caster dependencies')
    else:
        print('Building Music Caster')

    if args.ytdl:
        upgrade_yt_dlp()
        sys.exit(0)
    else:
        update_versions(VERSION)
    print('Updated versions of build files')
    if args.ver_update:
        sys.exit()
    # In CI the workflow sets up the venv and installs dependencies (with
    # caching), so skip dependency installation here for the Tauri frontend.
    if args.ci and USING_TAURI_FRONTEND:
        args.skip_deps = True
    install_to_user = '' if IS_VENV else '--user'
    pip_cmd = f'"{sys.executable}" -m pip install --upgrade {install_to_user} --upgrade-strategy eager -r "{REQUIREMENTS_FILE}" -r "{REQUIREMENTS_DEV_FILE}"'
    if args.deps or (not args.skip_build and not args.skip_deps):
        print('Installing and/or upgrading dependencies...')
        if platform.system() == 'Windows':
            # install tkdnd custom way
            sys_dir_name = Path(sys.executable).parent
            if IS_VENV:
                shutil.copytree(
                    TKDND_FILES[0],
                    f'{sys_dir_name}/tcl/tkdnd2.9.2',
                    dirs_exist_ok=True,
                )
                shutil.copytree(
                    TKDND_FILES[1],
                    f'{sys_dir_name.parent}/Lib/site-packages/TkinterDnD2',
                    dirs_exist_ok=True,
                )
            else:
                shutil.copytree(TKDND_FILES[0],
                                f'{sys_dir_name}/tcl/tkdnd2.9.2',
                                dirs_exist_ok=True)
                shutil.copytree(
                    TKDND_FILES[1],
                    f'{sys_dir_name}/Lib/site-packages/TkinterDnD2',
                    dirs_exist_ok=True,
                )
        install_time_start = time.time()
        p = Popen(pip_cmd, stdin=DEVNULL, stdout=None if args.deps else DEVNULL, text=True)
        if p.wait() > 0:
            print(
                'ERROR: pip install failed\n',
                pip_cmd,
            )
            sys.exit(1)
        if args.ci:
            print('Dumping pip freeze...')
            Popen(f'"{sys.executable}" -m pip freeze', stdin=DEVNULL, text=True).wait()
        if args.deps:
            print(f'Dependencies installed ({time.time() - install_time_start:.0} seconds)')
            sys.exit()
    assert IS_VENV
    # import third party libraries
    import requests
    from git import Repo

    sys.argv = sys.argv[:1]
    from src.shared import get_running_processes, is_already_running

    args.upload = args.upload and not args.test_auto_update
    try:
        player_state = requests.get('http://[::1]:2001/state').json()
        requests.get('http://[::1]:2001/exit')
        time.sleep(1)  # wait for MC to exit
    except requests.exceptions.RequestException:
        player_state = {}
    for process in get_running_processes('Music Caster.exe'):
        # force close any other instances of MC
        pid = process['pid']
        with suppress(PermissionError):
            os.kill(pid, 9)
    if args.debug:
        set_spec_debug(True)
    else:
        set_spec_debug(False)
    if args.upload:
        print('Will upload to GitHub after building')
    if args.test_auto_update:
        print("This test should test auto update and won't publish to GitHub")

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
        for dist_file in (main_file, f'{SETUP_OUTPUT_NAME}.exe',
                          'Portable.zip'):
            with suppress(FileNotFoundError):
                dist_file = DIST_DIR / dist_file
                print(f'Removing {dist_file}')
                os.remove(dist_file)

    if not args.skip_build:
        print(f'building executables with debug={args.debug}')
        additional_args = '--log=DEBUG' if args.debug else ''
        if args.clean:
            additional_args += ' --clean'

        if USING_TAURI_FRONTEND:
            # Only build daemon for Tauri frontend
            print('Building daemon for Tauri frontend...')
            check_call(
                f'{sys.executable} -O -m PyInstaller -y {additional_args} {DAEMON_SPEC}',
                shell=True,
            )
            s1 = None
            s4 = None
        else:
            # build frontend
            # check_call('yarn build', cwd=SRC_FRONTEND, shell=True)
            if platform.system() == 'Windows':
                s1 = Popen(
                    f'{sys.executable} -O -m PyInstaller -y {additional_args} {PORTABLE_SPEC}',
                    shell=True,
                )
            else:
                s1 = None
            try:
                # build Updater
                # install go dependencies
                check_call('go install github.com/akavel/rsrc@latest')
                check_call(
                    f'rsrc -manifest "{UPDATER_MANIFEST_FILE}" -ico "{UPDATER_ICO}"'
                )
                check_call(
                    f'go build -ldflags "-s -w -H windowsgui" -o "{UPDATER_DIST}"',
                    cwd=SRC_DIR)
            except Exception as e:
                updater_build_failed = True
                updater_build_error = e
                if args.upload:
                    raise Exception('failed to build updater') from e
                print(f'WARNING: {e}')
            check_call(
                f'{sys.executable} -O -m PyInstaller -y {additional_args} {ONEDIR_SPEC}',
                shell=True,
            )
            try:
                if platform.system() == 'Windows' and not USING_TAURI_FRONTEND:
                    s4 = Popen(f'iscc "{INSTALLER_SCRIPT}"')
                else:
                    s4 = None
            except FileNotFoundError:
                s4 = None
                error_inno_missing = True

            try:
                portable_failed = s1.wait()
            except AttributeError:
                portable_failed = False
            if args.debug:
                set_spec_debug(False)
            if portable_failed:
                print('Portable installation failed')
                print(s1.communicate()[1])
                sys.exit()

        # Portable
        if platform.system() == 'Windows':
            music_caster_portable = (DIST_DIR / 'Music Caster.exe',
                                     'Music Caster.exe')
            updater_portable = (DIST_DIR / 'Updater.exe', 'Updater.exe')
            portable_files = [
                music_caster_portable,
                (CHANGELOG_FILE, 'CHANGELOG.txt'),
                updater_portable,
            ]
            vlc_ext = 'dll' if platform.system() == 'Windows' else 'so'
            print('Creating dist/Portable.zip')
            create_zip(
                DIST_DIR / 'Portable.zip',
                portable_files,
                compression=zipfile.ZIP_DEFLATED,
            )
        # zip directory for Linux or Darwin
        elif platform.system() == 'Darwin':
            pass
        else:
            shutil.rmtree(DIST_DIR / 'Music Caster OneDir/share/')
            linux_dist = DIST_DIR / 'Music Caster (Linux)'
            print(f'Creating {linux_dist}.zip')
            shutil.make_archive(linux_dist, 'zip', 'dist/Music Caster OneDir')
        with suppress(AttributeError):
            s4.wait()  # Wait for InnoSetup script to finish
        print(f'v{VERSION} Build Time:', round(time.time() - start_time, 2),
              'seconds')
        print('Last commit: ' + getoutput('git log --format="%H" -n 1'))

    daemon_dist = DIST_DIR / 'Music Caster Daemon.exe'
    dist_files = []

    if platform.system() == 'Windows':
        if USING_TAURI_FRONTEND:
            dist_files.append(daemon_dist.name)
        else:
            dist_files.extend(('Music Caster Setup.exe', 'Portable.zip'))
    elif platform.system() == 'Darwin':
        dist_files.append('Music Caster (OSX).zip')
    else:
        dist_files.append('Music Caster (Linux).zip')

    # check if all files were built
    dist_files_exist = True
    for dist_file in dist_files:
        dist_file_path = DIST_DIR / dist_file
        if os.path.exists(dist_file_path):
            file_size = os.path.getsize(dist_file_path) // 1000  # KB
            file_exists_str = f'EXISTS {file_size:,} KB'.rjust(12)
        else:
            file_exists_str = 'DOES NOT EXIST!'
            dist_files_exist = False
        print((dist_file + ':').ljust(30) + file_exists_str)
    if error_inno_missing:
        print('WARNING: installer not created because Inno Setup iscc is not installed or is not on PATH')
    if updater_build_failed:
        print(updater_build_error)
        if isinstance(updater_build_error, FileNotFoundError):
            print('WARNING: Updater build failed because Go (or rsrc) is not installed or is not on PATH')

    if dist_files_exist and platform.system() == 'Windows' and not USING_TAURI_FRONTEND:
        with zipfile.ZipFile(DIST_DIR / 'Portable.zip') as portable_zip:
            if 'Updater.exe' in portable_zip.namelist():
                print('Portable.zip/Updater.exe:'.ljust(30) + 'EXISTS')
            else:
                print('Portable.zip/Updater.exe:'.ljust(30) +
                      'DOES NOT EXIST!')
                dist_files_exist = False

    if USING_TAURI_FRONTEND:
        architecture = 'aarch64' if platform.machine() == 'ARM64' else 'x86_64'
        if platform.system() == 'Windows':
            target = args.target or f'{architecture}-pc-windows-msvc'
            ext = 'exe'
        else:
            ext = daemon_dist.stem
            if platform.system() == 'Linux':
                target = args.target or f'{architecture}-unknown-linux-gnu'
            else:
                target = args.target
                if target is None:
                    raise Exception(f'target was not supplied for "{platform.system()}" platform')
        shutil.copy2(daemon_dist, DIST_DIR / f'music-caster-daemon-{target}.{ext}')
        print(f'copied daemon to target triplet {target}')

    if not args.skip_tests and dist_files_exist and not USING_TAURI_FRONTEND:
        try:
            sys.argv = sys.argv[:1]
            pytest_args = ['pytest']
            if args.upload:
                pytest_args.append('--upload')
            if args.test_auto_update:
                pytest_args.append('--test-auto-update')
            if args.ci:
                pytest_args.append('--ci')
            pytest_args.append('--capture=no')
            check_call(pytest_args, cwd=SRC_DIR)
        except CalledProcessError:
            print('pytest: failed')
            sys.exit(1)
        # Test if executable can be run
        import appdirs
        user_data_dir = Path(appdirs.user_data_dir(roaming=True))
        test(
            'User data dir exists',
            lambda: user_data_dir.exists(),
            True,
        )
        p = Popen(
            f'"{DIST_DIR}/Music Caster OneDir/Music Caster" -m --debug',
            shell=True)
        time.sleep(5)
        p.poll()
        if p.returncode is not None:
            print('got return code', p.returncode)
        test(
            'No return code',
            lambda: p.returncode is None,
            True,
        )
        test(
            'Music Caster Should Be Running',
            lambda: is_already_running(threshold=1),
            True,
        )
        time.sleep(2)
        test('Music Caster Should Accept Exit API',
             lambda: requests.post('http://[::1]:2001/exit'))
        time.sleep(2)
        test('Music Caster Should Have Exited',
             lambda: not is_already_running(), True)

    if args.debug or not dist_files_exist:
        print(
            'Exiting early to avoid upload or installation of possibly broken build'
        )
        sys.exit(0 if args.dist_files_exist else 2)
    print(f'Build v{VERSION} complete')
    print('Time taken:', round(time.time() - start_time, 2), 'seconds')
    print('Last commit: ' + getoutput('git log --format="%H" -n 1'))
    if args.upload:
        if USING_TAURI_FRONTEND:
            print('USING_TAURI_FRONTEND is true; exiting.')
            sys.exit(0)
        if VERSION[0] == '6':
            print('Major version is not 5; exiting.')
            sys.exit(0)
        print('Will try to upload to GitHub')
        # upload to GitHub
        github = read_env()['github']
        headers = {
            'Authorization': f'token {github}',
            'Accept': 'application/vnd.github.v3+json',
        }
        USERNAME = 'elibroftw'
        github_api = 'https://api.github.com'

        # check if tag vVERSION does not exist
        r = requests.get(
            f'{github_api}/repos/{USERNAME}/music-caster/releases/tags/v{VERSION}',
            headers=headers,
        )
        if r.status_code != 404:
            if args.ci:
                print('INFO: not uploading build since tag already exists')
                sys.exit(0)
            print(f'ERROR: Release for tag "v{VERSION}" already exists')
            sys.exit(1)

        old_release = requests.get(
            f'{github_api}/repos/{USERNAME}/music-caster/releases/latest'
        ).json()
        try:
            old_release_id = old_release['id']
        except KeyError:
            print(
                'rate limit exceeded, upload manually at https://github.com/elibroftw/music-caster/releases'
            )
            sys.exit()
        # keep changes of current major version if new version is a minor update
        body = '' if VERSION.endswith('.0') else old_release['body']
        body = add_new_changes(body)
        if any(Repo('.git').index.diff(None)):
            # possible if build.cmd -v wasn't run before
            print('Warning: Changes detected.')
            print(Repo('.git').index.diff(None))
            if not args.ci:
                input(
                    'Changed (not committed) files detected. Press enter to confirm upload.\n'
                )
        print('Will upload and install at the same time!')
        t = threading.Thread(target=local_install)
        t.start()

        new_release = {
            'tag_name': f'v{VERSION}',
            'target_commitish': 'master',
            'name': f'Music Caster v{VERSION}',
            'body': body,
            'draft': True,
            'prerelease': False,
        }
        r = requests.post(
            f'{github_api}/repos/{USERNAME}/music-caster/releases',
            json=new_release,
            headers=headers,
        )
        release = r.json()
        upload_url = release['upload_url'][:-13]
        release_id = release['id']
        # upload assets
        for dist_file in dist_files:
            requests.post(
                upload_url,
                data=ProgressUpload(DIST_DIR / dist_file),
                params={'name': dist_file},
                headers={
                    **headers, 'Content-Type': 'application/octet-stream'
                },
            )
        requests.post(
            f'{github_api}/repos/{USERNAME}/music-caster/releases/{release_id}',
            headers=headers,
            json={
                'body': body,
                'draft': False
            },
        )
        # since winget is slower on the PR's, it's better to not delete anything
        # if not VERSION.endswith('.0'):
        #     # delete old release if not a new major build
        #     requests.delete(f'{github_api}/repos/{USERNAME}/music-caster/releases/{old_release_id}', headers=headers)
        print(f'Published Release v{VERSION}')
        print(
            f'v{VERSION} Total Time Taken:',
            round(time.time() - start_time, 2),
            'seconds',
        )
        t.join()
    elif not args.no_install and (not args.skip_tests or args.force_install):
        print(
            'Installing Music Caster and it will be launched after installation.'
        )
        local_install()
