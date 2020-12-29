from contextlib import suppress
from glob import glob
import io
import json
import os
from shutil import rmtree
from subprocess import Popen
import zipfile
import sys

import requests

try: run_after_install = int(sys.argv[1])
except IndexError: run_after_install = True


def download(url, outfile):
    r = requests.get(url, stream=True)
    if outfile.endswith('.zip'):
        outfile = outfile.replace('.zip', '')
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(outfile)
    else:
        with open(outfile, 'wb') as _f:
            _f.write(r.content)


os.chdir(os.path.dirname(os.path.realpath(__file__)))  # change working dir
try:
    with open('settings.json') as json_file:
        loaded_settings = json.load(json_file)
except (FileNotFoundError, json.decoder.JSONDecodeError):
    loaded_settings = {'DEBUG': False}
DEBUG = loaded_settings.get('DEBUG', False)
releases_url = 'https://api.github.com/repos/elibroftw/music-caster/releases/latest'
release = requests.get(releases_url).json()
setup_dl_link = portable_dl_link = ''
for asset in release['assets']:
    if 'exe' in asset['name']:
        setup_dl_link = asset['browser_download_url']
    elif 'portable' in asset['name'].lower():
        portable_dl_link = asset['browser_download_url']
if DEBUG:
    print('Bundle:', portable_dl_link)
    print('Installer:', setup_dl_link)
elif os.path.exists('unins000.exe'):
    download(setup_dl_link, 'MC_Installer.exe')
    Popen('MC_Installer.exe /VERYSILENT /FORCECLOSEAPPLICATIONS /MERGETASKS="!desktopicon" && "Music Caster.exe"',
          shell=True)
else:  # Portable
    if not os.path.exists('Portable'):
        download(portable_dl_link, 'Portable.zip')
    for f in glob('Portable/**/*.*', recursive=True):
        if not f.endswith('Updater.exe'):
            new_f = f.replace('Portable\\', '')
            with suppress(FileNotFoundError): os.remove(new_f)
            os.renames(f, new_f)
    rmtree('Portable', ignore_errors=True)
    if run_after_install: os.startfile('Music Caster.exe')
