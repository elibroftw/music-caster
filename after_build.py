import json
import zipfile

default_settings = {
    'version': '1.1.1',
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

print('Created dist/settings.json!')

with zipfile.ZipFile('dist/Portable.zip', 'w') as zf:
    zf.write('dist/Music Caster.exe', 'Music Caster.exe')
    zf.write('dist/Updater.exe', 'Updater.exe')
    zf.write('dist/settings.json', 'settings.json')

print('Created dist/Portable.zip')
