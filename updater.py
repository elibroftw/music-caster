from time import sleep
from bs4 import BeautifulSoup
import requests
import json
import zipfile
import io
import os
from contextlib import suppress
from subprocess import Popen
from shutil import copyfileobj


def download_and_extract(link, infile, outfile=None):
    r = requests.get(link, stream=True)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    # NOTE: I'm unsure weather I need to delete the file before extracting. Test the exe
    if outfile is None: z.extract(infile)
    else:
        new_file = z.open(infile)
        # f'music-caster-{latest_version}/music_caster.py'
        target = open(outfile, 'wb')
        with new_file, target: copyfileobj(new_file, target)


with suppress(FileNotFoundError):
    sleep(1)  # wait for calling script to exit
    os.chdir(os.path.dirname(os.path.realpath(__file__)))  # just in case
    if os.path.exists('settings.json'):
        with open('settings.json') as json_file:
            debug_setting = json.load(json_file).get('DEBUG', False)
    else: debug_setting = False
    github_url = 'https://github.com/elibroftw/music-caster/releases'
    html_doc = requests.get(github_url).text
    soup = BeautifulSoup(html_doc, features='html.parser')
    release_entry = soup.find('div', class_='release-entry')
    latest_version = release_entry.find('a', class_='muted-link css-truncate')['title'][1:]
    details = release_entry.find('details', class_='details-reset Details-element border-top pt-3 mt-4 mb-2 mb-md-4')
    download_links = [link['href'] for link in details.find_all('a') if link.get('href')]
    bundle_download_link = f'https://github.com{download_links[1]}'
    source_download_link = f'https://github.com{download_links[-2]}'
    if debug_setting:
        print(bundle_download_link)
        print(source_download_link)
        Popen('python music_caster.py')
    # add .py case

    elif os.path.exists('music_caster.pyw'):  # Update python file
        # download_and_extract(source_download_link, f'music-caster-{latest_version}/music_caster.py', 'music_caster.pyw')
        r = requests.get(source_download_link, stream=True)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extract(f'music-caster-{latest_version}/music_caster.py')
        z.close()
        if os.path.exists('music_caster.pyw'): os.remove('music_caster.pyw')
        os.rename(f'music-caster-{latest_version}/music_caster.py', 'music_caster.pyw')
        os.rmdir(f'music-caster-{latest_version}')
        Popen('pythonw music_caster.pyw')
    else:  # Update Music Caster.exe;  Change if statements so that .pyw is last
        # download_and_extract(bundle_download_link, 'Music Caster.exe')
        r = requests.get(bundle_download_link, stream=True)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        if os.path.exists('Music Caster.exe'): os.remove('Music Caster.exe')
        z.extract('Music Caster.exe')
        z.close()
        os.startfile('Music Caster.exe')
