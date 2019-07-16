from bs4 import BeautifulSoup
import requests
import json
import zipfile
import io
import os
import sys
from time import sleep
from contextlib import suppress
from subprocess import Popen


with suppress(FileNotFoundError):
    sleep(1)  # wait for calling script to exit
    os.chdir(os.path.dirname(os.path.realpath(__file__)))  # just in case
    with open('settings.json') as json_file:
        settings = json.load(json_file)

    github_url = 'https://github.com/elibroftw/music-caster/releases'
    html_doc = requests.get(github_url).text
    soup = BeautifulSoup(html_doc, features='html.parser')
    release_entry = soup.find('div', class_='release-entry')
    latest_version = release_entry.find('a', class_='muted-link css-truncate')['title'][1:]
    details = release_entry.find('details', class_='details-reset Details-element border-top pt-3 mt-4 mb-2 mb-md-4')
    download_links = [link['href'] for link in details.find_all('a') if link.get('href')]
    bundle_download_link = f'https://github.com{download_links[1]}'
    source_download_link = f'https://github.com{download_links[-2]}'

    with open('settings.json', 'w') as outfile:  # TODO: remove completely
        settings['version'] = latest_version
        json.dump(settings, outfile, indent=4)

    if settings.get('DEBUG'):
        print(bundle_download_link)
        print(source_download_link)
        Popen('python music_caster.py')
    elif os.path.exists('music_caster.pyw'):  # Update python file
        r = requests.get(source_download_link, stream=True)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extract(f'music-caster-{latest_version}/music_caster.py')
        z.close()
        if os.path.exists('music_caster.pyw'):
            os.remove('music_caster.pyw')
        os.rename(f'music-caster-{latest_version}/music_caster.py', 'music_caster.pyw')
        os.rmdir(f'music-caster-{latest_version}')
        Popen('pythonw music_caster.pyw')
    elif os.path.exists('Music Caster.exe'):  # Update the bundle
        r = requests.get(bundle_download_link, stream=True)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extract('Music Caster.exe')
        z.close()
        os.startfile('Music Caster.exe')
        # music_caster
