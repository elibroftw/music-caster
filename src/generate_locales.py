#!/usr/bin/env python3

import os

# Read en.yml to get the keys and build dictionary
en_data = {}
with open('app/src-tauri/locales/en.yml', 'r', encoding='utf-8') as f:
    for line in f:
        if ': ' in line:
            key, value = line.strip().split(': ', 1)
            en_data[key] = value

en_keys = list(en_data.keys())

# Language files to process
languages = ['da', 'de', 'es', 'fr', 'it', 'nl', 'pt-br', 'ru', 'sk', 'uk']

for lang in languages:
    txt_file = f'src/languages/{lang}.txt'
    yml_file = f'app/src-tauri/locales/{lang}.yml'

    # Read the translations
    translations = []
    with open(txt_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                translations.append(line)

    # Create the yml data and write manually
    with open(yml_file, 'w', encoding='utf-8') as f:
        for key, translation in zip(en_keys, translations):
            f.write(f"{key}: {translation}\n")

    print(f'Created {yml_file}')
