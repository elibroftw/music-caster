from contextlib import suppress
from glob import glob
import io
import json
import os
from shutil import rmtree
from subprocess import Popen
import time
import zipfile
import sys

from bs4 import BeautifulSoup
import requests


try:
    run_after_install = bool(sys.argv[1])
except IndexError:
    run_after_install = True


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
loaded_settings = {'DEBUG': False}
if os.path.exists('settings.json'):
    with open('settings.json') as json_file:
        loaded_settings = json.load(json_file)
debug_setting = loaded_settings.get('DEBUG', False)
github_url = 'https://github.com/elibroftw/music-caster/releases'
html_doc = requests.get(github_url).text
soup = BeautifulSoup(html_doc, features='html.parser')
release_entries = soup.find_all('div', class_='release-entry')
release_entry = None
for release_entry in release_entries:
    latest_version = release_entry.find('a', class_='muted-link css-truncate')['title'][1:]
    release_type = release_entry.find('span').text.strip()
    if release_type == 'Latest release': break
details = release_entry.find('details', class_='details-reset Details-element border-top pt-3 mt-4 mb-2 mb-md-4')
download_links = [link['href'] for link in details.find_all('a')]
setup_download_link = f'https://github.com{download_links[0]}'
portable_download_link = f'https://github.com{download_links[1]}'
start = time.time()
if debug_setting:
    print('Bundle:', portable_download_link)
    print('Installer:', setup_download_link)
elif os.path.exists('Music Caster.exe'):
    if not os.path.exists('unins000.exe'):  # Portable
        if not os.path.exists('Portable'):
            download(portable_download_link, 'Portable.zip')
        for f in glob('Portable/**/*.*', recursive=True):
            if not f.endswith('Updater.exe'):
                new_f = f.replace('Portable\\', '')
                with suppress(FileNotFoundError): os.remove(new_f)
                os.renames(f, new_f)
        rmtree('Portable', ignore_errors=True)
        if run_after_install: os.startfile('Music Caster.exe')
    else:
        download(setup_download_link, 'MC_Installer.exe')
        Popen('MC_Installer.exe /VERYSILENT /CLOSEAPPLICATIONS /FORCECLOSEAPPLICATIONS /MERGETASKS="!desktopicon"')