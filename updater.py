from bs4 import BeautifulSoup
import requests
import json
import zipfile
import io
import os
from time import sleep

sleep(1)  # wait for calling script to exit
with open('settings.json') as json_file:
    settings = json.load(json_file)
    current_version = settings['version']


github_url = 'https://github.com/elibroftw/music-caster/releases'
html_doc = requests.get(github_url).text
soup = BeautifulSoup(html_doc, features='html.parser')
release_entry = soup.find('div', class_='release-entry')
latest_version = release_entry.find('a', class_='muted-link css-truncate')['title'][1:]
details = release_entry.find('details', class_='details-reset Details-element border-top pt-3 mt-4 mb-2 mb-md-4')
download_link = next(link['href'] for link in details.find_all('a') if link.get('href'))
download_link = f'https://github.com{download_link}'

if not settings.get('DEBUG'):
    r = requests.get(download_link, stream=True)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    z.extract('Music Caster.exe')
    z.close()
    settings['version'] = latest_version
    with open('settings.json', 'w') as outfile:
        json.dump(settings, outfile, indent=4)
    os.startfile('Music Caster.exe')
