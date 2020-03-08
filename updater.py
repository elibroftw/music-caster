import time
from bs4 import BeautifulSoup
import requests
import json
import zipfile
import io
import os
from contextlib import suppress
from subprocess import Popen
from shutil import copyfileobj, rmtree
from glob import glob


def download(url, outfile):
    r = requests.get(url, stream=True)
    if outfile.endswith('.zip'):
        outfile = outfile.replace('.zip', '')
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(outfile)
    else:
        with open(outfile, 'wb') as f:
            f.write(r.content)


def download_and_extract(link, infile, outfile=None):
    if os.path.exists(f'Update/{infile}'):
        if not outfile: outfile = infile
        if os.path.exists(outfile): os.remove(outfile)
        os.rename(f'Update/{infile}', outfile)
        rmtree('Update', True)
    else:
        r = requests.get(link, stream=True)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        if outfile is None: z.extract(infile)
        else:
            new_file = z.open(infile)
            target = open(outfile, 'wb')
            with new_file, target: copyfileobj(new_file, target)


with suppress(FileNotFoundError):
    time.sleep(1)  # wait for calling script to exit
    os.chdir(os.path.dirname(os.path.realpath(__file__)))  # change working dir
    loaded_settings = {'DEBUG': False, 'PORTABLE': False}
    if os.path.exists('settings.json'):
        with open('settings.json') as json_file:
            loaded_settings = json.load(json_file)
    else: loaded_settings['portable'] = True
    debug_setting = loaded_settings.get('DEBUG', False)
    is_portable = loaded_settings.get('PORTABLE', False)
    github_url = 'https://github.com/elibroftw/music-caster/releases'
    html_doc = requests.get(github_url).text
    soup = BeautifulSoup(html_doc, features='html.parser')
    release_entries = soup.find_all('div', class_='release-entry')
    for release_entry in release_entries:
        latest_version = release_entry.find('a', class_='muted-link css-truncate')['title'][1:]
        release_type = release_entry.find('span').text.strip()
        if release_type == 'Latest release': break
    details = release_entry.find('details', class_='details-reset Details-element border-top pt-3 mt-4 mb-2 mb-md-4')
    download_links = [link['href'] for link in details.find_all('a') if link.get('href')]
    setup_download_link = f'https://github.com{download_links[0]}'
    bundle_download_link = f'https://github.com{download_links[1]}'
    source_download_link = f'https://github.com{download_links[-2]}'
    print('Downloading...')
    start = time.time()
    if debug_setting:
        print('Bundle:', bundle_download_link)
        print('Source code:', source_download_link)
        print('Installer:', setup_download_link)
    elif os.path.exists('Music Caster.exe'):
        if not os.path.exists('unins000.exe'):  # Portable
            if not os.path.exists('Portable'):
                download(bundle_download_link, 'Portable.zip')
            for f in glob('Portable/**/*.*', recursive=True):
                if not f.endswith('Updater.exe'):
                    new_f = f.replace('Portable\\', '')
                    if new_f != 'Updater.exe':
                        with suppress(FileNotFoundError): os.remove(new_f)
                        os.rename(f, f.replace('Portable\\', ''))
            os.remove('Portable')
            os.startfile('Music Caster.exe')
        else:
            download(setup_download_link, 'MC_Installer.exe')
            Popen('MC_Installer.exe /VERYSILENT /CLOSEAPPLICATIONS /FORCECLOSEAPPLICATIONS /MERGETASKS="!desktopicon"')
    elif os.path.exists('music_caster.py'):
        download_and_extract(source_download_link, f'music-caster-{latest_version}/music_caster.py', 'music_caster.py')
        Popen('pythonw music_caster.py')
    else:  # Update python file
        download_and_extract(source_download_link, f'music-caster-{latest_version}/music_caster.py', 'music_caster.pyw')
        Popen('pythonw music_caster.pyw')
    print(f'Downloaded and extracted in {time.time() - start} seconds')
