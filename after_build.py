import json
import zipfile

default_settings = {
    'previous device': None,
    'comments': ['Edit only the variables below', 'Restart the program after editing this file!'],
    'auto update': True,
    'run on startup': True,
    'music directories': [],
    'sample music directories': [
        'C:/Users/maste/Documents/MEGAsync/Music',
        'Put in a valid path',
        'First path is the default directory when selecting a file to play. FOR NOW'
    ],
    'playlists': {},
    'playlists_example': {'NAME': ['PATHS']},
}

with open('dist/settings.json', 'w') as outfile:
    json.dump(default_settings, outfile, indent=4)

with zipfile.ZipFile('dist/Portable.zip', 'w') as zf:
    zf.write('dist/Music Caster.exe', 'Music Caster.exe')
    zf.write('dist/Updater.exe', 'Updater.exe')

print('Created dist/Portable.zip')

with zipfile.ZipFile('dist/Python Files.zip', 'w') as zf:
    zf.write('music_caster.py', 'music_caster.pyw')
    zf.write('updater.py', 'updater.pyw')
    zf.write('Icons/icon.ico', 'icon.ico')

print('Created dist/Python Files.zip')

# TODO: add a file check to check if versions are same
print('ARE THE FILES PROPERLY VERSIONED?')