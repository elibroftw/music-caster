# -*- mode: python ; coding: utf-8 -*-
import os
from glob import iglob
# noinspection PyPackageRequirements
from PyInstaller.building.api import PYZ, EXE, COLLECT
# noinspection PyPackageRequirements
from PyInstaller.building.build_main import Analysis
# noinspection PyPackageRequirements
from PyInstaller.config import CONF
import platform

CONF['distpath'] = './dist'
block_cipher = None
# TODO: test on MAC OSX
vlc_ext = 'dll' if platform.system() == 'Windows' else 'so'
vlc_files = [(os.path.abspath(file), os.path.dirname(file)) for file in iglob(f'vlc_lib/**/*.{vlc_ext}', recursive=True)]
lang_packs = [(os.path.abspath(file), os.path.dirname(file)) for file in iglob('languages/*.txt')]
tkdnd = [(os.path.abspath(file), 'tkdnd2.9.2') for file in iglob('build_files/tkdnd2.9.2/*.*')]
data_files = [('Music Caster.VisualElementsManifest.xml', '.'),
              (os.path.abspath('templates/index.html'), 'templates'),
              (os.path.abspath('static/style.css'), 'static')] + vlc_files + lang_packs + tkdnd
a = Analysis([f'{os.getcwd()}/music_caster.py'],
             pathex=[os.getcwd()],
             binaries=[],
             datas=data_files,
             hiddenimports=['pystray._win32'],
             hookspath=[],
             runtime_hooks=[],
             excludes=['crypto', 'cryptography', 'pycryptodome', 'pandas', 'gevent',
                       'numpy', 'simplejson', 'PySide2', 'PyQt5', 'greenlet'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='Music Caster',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=False,
          console=False, version='mc_version_info.txt', icon=os.path.abspath('../resources/Music Caster Icon.ico'))
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=False,
               name='Music Caster OneDir')
