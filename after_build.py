import zipfile
import shutil
import os
import json

files = ['images/default.png', 'static/style.css', 'templates/home.html']
for file in files:
    shutil.copyfile(file, 'dist/' + file)

portable_settings = {  # default settings
        'previous_device': None, 'PORTABLE': True, 'accent_color': '#00bfff', 'text_color': '#aaaaaa', 'button_text_color': '#000000',
        'background_color': '#121212', 'volume': 100, 'scrubbing_delta': 5, 'volume_delta': 5, 'auto_update': False,
        'run_on_startup': True, 'notifications': True, 'shuffle_playlists': True, 'repeat': False,
        'timer_shut_off_computer': False, 'timer_hibernate_computer': False, 'timer_sleep_computer': False,
        'EXPERIMENTAL': False, 'music_directories': [], 'playlists': {}}

with open('dist/default_settings.json', 'w') as outfile:
    json.dump(portable_settings, outfile, indent=4)


with zipfile.ZipFile('dist/Portable.zip', 'w') as zf:
    zf.write('dist/Music Caster.exe', 'Music Caster.exe')
    zf.write('dist/Updater.exe', 'Updater.exe')
    zf.write('resources/default.png', 'images/default.png')
    zf.write('templates/home.html')
    zf.write('static/style.css')
    zf.write('CHANGELOG', 'CHANGELOG.txt')
    zf.write('dist/default_settings.json', 'settings.json')
    os.remove('dist/default_settings.json')

print('Created dist/Portable.zip')

with zipfile.ZipFile('dist/Python Files.zip', 'w') as zf:
    zf.write('music_caster.py', 'music_caster.pyw')
    zf.write('updater.py', 'updater.pyw')
    zf.write('helpers.py', 'helpers.py')
    zf.write('resources/Music Caster.ico', 'icon.ico')
    zf.write('resources/default.png', 'images/default.png')
    zf.write('templates/home.html')
    zf.write('static/style.css')
    zf.write('requirements.txt')
    zf.write('CHANGELOG', 'CHANGELOG.txt')

print('Created dist/Python Files.zip')