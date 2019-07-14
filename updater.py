from bs4 import BeautifulSoup
import requests
import json
import zipfile
import io
import os
from time import sleep


try:
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
    download_link = [link['href'] for link in details.find_all('a') if link.get('href')][1]
    download_link = f'https://github.com{download_link}'

    with open('settings.json', 'w') as outfile:
        settings['version'] = latest_version
        json.dump(settings, outfile, indent=4)

    if settings.get('DEBUG'):
        print(download_link)
        from subprocess import Popen
        Popen('python music_caster.py')
    else:
        print('Downloading New Exe...')
        r = requests.get(download_link, stream=True)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extract('Music Caster.exe')
        z.close()
        os.startfile('Music Caster.exe')
except Exception as e:
    print(e)
    print(os.getcwd())
    input('Press Enter to exit...')
