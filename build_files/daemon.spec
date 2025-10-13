# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.building.api import PYZ, EXE
from PyInstaller.building.build_main import Analysis, Tree # type: ignore
from PyInstaller.config import CONF
import platform

CONF['distpath'] = './dist' # type: ignore
# CONF['workpath'] = './build'
block_cipher = None
a = Analysis([f'{os.getcwd()}/src/music_caster.py'],
             pathex=[os.getcwd()],
             binaries=[],
             datas=[('../CHANGELOG.TXT', '.')],
             hiddenimports=['pystray._win32', 'zeroconf._utils.ipaddress', 'zeroconf._handlers.answers'],
             hookspath=[],
             runtime_hooks=[],
             excludes=['crypto', 'cryptography', 'pycryptodome', 'pandas', 'gevent',
                       'numpy', 'simplejson', 'PySide2', 'PyQt5', 'greenlet'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

a.datas.extend(Tree('src/templates', 'templates'))
a.datas.extend(Tree('src/static', 'static'))
VLC_EXCLUDES = ['*.dll', '*.so', '*.so*', '*.dylib*', '*.dylib']
if platform.system() == 'Windows':
    VLC_EXCLUDES.remove('*.dll')
elif platform.system() == 'Darwin':
    VLC_EXCLUDES.remove('*.dylib*')
    VLC_EXCLUDES.remove('*.dylib')
elif platform.system() == 'Linux':
    VLC_EXCLUDES.remove('*.so*')
    VLC_EXCLUDES.remove('*.so')
a.datas.extend(Tree('src/vlc_lib', 'vlc_lib', excludes=VLC_EXCLUDES))
a.datas.extend(Tree('src/languages', 'languages'))
a.datas.extend(Tree('build_files/tkdnd2.9.2', 'tkdnd2.9.2'))
a.datas.extend(Tree('src/theme', 'theme'))
# a.datas.extend(Tree('src-frontend/dist', 'frontend'))

pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='Music Caster Daemon',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=False,
          runtime_tmpdir=None,
          # TODO: use ENV variable
          console=True, version='mc_version_info.txt', icon=os.path.abspath('resources/Music Caster Icon.ico'))
