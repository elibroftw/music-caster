# -*- mode: python ; coding: utf-8 -*-
import os
from glob import glob
# noinspection PyPackageRequirements
from PyInstaller.building.api import PYZ, EXE, COLLECT
# noinspection PyPackageRequirements
from PyInstaller.building.build_main import Analysis
# noinspection PyPackageRequirements
from PyInstaller.config import CONF

CONF['distpath'] = './dist'
block_cipher = None
vlc_files = [(os.path.abspath(file), os.path.dirname(file)) for file in glob('vlc/**/*.*', recursive=True)]
data_files = [('Music Caster.VisualElementsManifest.xml', '.'),
              (os.path.abspath('templates/index.html'), 'templates'),
              (os.path.abspath('templates/files.html'), 'templates'),
              (os.path.abspath('static/style.css'), 'static')] + vlc_files
a = Analysis([f'{os.getcwd()}/music_caster.py'],
             pathex=[os.getcwd()],
             binaries=[],
             datas=data_files,
             hiddenimports=['pkg_resources.py2_warn'],
             hookspath=[],
             runtime_hooks=[],
             excludes=['crypto', 'cryptography', 'pycryptodome', 'pycryptodomex', 'Cryptodome',
                       'pandas', 'numpy', 'simplejson', 'PySide2', 'PyQt5', 'greenlet'],
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
          console=False, version='mc_version_info.txt', icon=os.path.abspath('resources/Music Caster Icon.ico'))
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=False,
               upx_exclude=['vcruntime140.dll', 'msvcp140.dll', 'python36.dll', 'python37.dll', 'python38.dll'],
               name='Music Caster')
