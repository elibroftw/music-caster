import json

default_settings = {
    'comments': ['Restart the program after editing this file!'],
    'version': '1.1.0',
    'previous device': None,
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
