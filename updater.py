from time import time, sleep
from bs4 import BeautifulSoup
import requests
import json
import zipfile
import io
import os
from contextlib import suppress
from subprocess import Popen
from shutil import copyfileobj, rmtree

# "Music Caster x64 Setup.exe" /SILENT /MERGETASKS="!desktopicon"

def download_and_extract(link, infile, outfile=None):
    if os.path.exists(f'Update/{infile}'):
        if not outfile: outfile = infile
        if os.path.exists(outfile): os.remove(outfile)
        os.rename(f'Update/{infile}', outfile)
        rmtree('Update')
    else:
        r = requests.get(link, stream=True)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        if outfile is None: z.extract(infile)
        else:
            new_file = z.open(infile)
            target = open(outfile, 'wb')
            with new_file, target: copyfileobj(new_file, target)


with suppress(FileNotFoundError):
    sleep(1)  # wait for calling script to exit
    os.chdir(os.path.dirname(os.path.realpath(__file__)))  # change working dir
    if os.path.exists('settings.json'):
        with open('settings.json') as json_file:
            debug_setting = json.load(json_file).get('DEBUG', False)
    else: debug_setting = False
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
    bundle_download_link = f'https://github.com{download_links[1]}'
    # updater_download_link = f'https://github.com{download_links[2]}'
    source_download_link = f'https://github.com{download_links[-2]}'
    start = time()
    print('Downloading file...')
    if debug_setting:
        print(bundle_download_link)
        print(source_download_link)
        Popen('python music_caster.py')
    elif os.path.exists('Music Caster.exe'):
        print('downloading Music Caster.exe')
        download_and_extract(bundle_download_link, 'Music Caster.exe')
        os.startfile('Music Caster.exe')
    elif os.path.exists('music_caster.py'):
        download_and_extract(source_download_link, f'music-caster-{latest_version}/music_caster.py', 'music_caster.py')
        Popen('pythonw music_caster.py')
    else:  # Update python file
        download_and_extract(source_download_link, f'music-caster-{latest_version}/music_caster.py', 'music_caster.pyw')
        Popen('pythonw music_caster.pyw')
    print(f'Downloaded and extracted in {time() - start} seconds')
