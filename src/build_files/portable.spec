# -*- mode: python ; coding: utf-8 -*-
import os
# noinspection PyPackageRequirements
from PyInstaller.building.api import PYZ, EXE
# noinspection PyPackageRequirements
from PyInstaller.building.build_main import Analysis, Tree
# noinspection PyPackageRequirements
from PyInstaller.config import CONF
import platform

CONF['distpath'] = './dist'
# CONF['workpath'] = './build'
block_cipher = None
a = Analysis([f'{os.getcwd()}/music_caster.py'],
             pathex=[os.getcwd()],
             binaries=[],
             datas=[('CHANGELOG.TXT', '.')],
             hiddenimports=['pystray._win32'],
             hookspath=[],
             runtime_hooks=[],
             excludes=['crypto', 'cryptography', 'pycryptodome', 'pandas', 'gevent',
                       'numpy', 'simplejson', 'PySide2', 'PyQt5', 'greenlet'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

a.datas.extend(Tree('templates', 'templates'))
a.datas.extend(Tree('static', 'static'))
VLC_EXCLUDES = ['*.dll', '*.so*', '*.dylib*']
if platform.system() == 'Windows':
    VLC_EXCLUDES.remove('*.dll')
elif platform.system() == 'Darwin':
    VLC_EXCLUDES.remove('*.dylib*')
elif platform.system() == 'Linux':
    VLC_EXCLUDES.remove('*.so*')
a.datas.extend(Tree('vlc_lib', 'vlc_lib', excludes=VLC_EXCLUDES))
a.datas.extend(Tree('languages', 'languages'))

a.datas.extend(Tree('build_files/tkdnd2.9.2', 'tkdnd2.9.2'))
a.datas.extend(Tree('theme', 'theme'))
a.datas.extend(Tree('../src-frontend/dist', 'frontend'))

pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='Music Caster',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=False,
          runtime_tmpdir=None,
          # TODO: use ENV variable
          console=False, version='mc_version_info.txt', icon=os.path.abspath('../resources/Music Caster Icon.ico'))
