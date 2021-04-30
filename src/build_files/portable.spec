# -*- mode: python ; coding: utf-8 -*-
import os
# noinspection PyPackageRequirements
from PyInstaller.building.api import PYZ, EXE
# noinspection PyPackageRequirements
from PyInstaller.building.build_main import Analysis
# noinspection PyPackageRequirements
from PyInstaller.config import CONF
from glob import iglob

CONF['distpath'] = './dist'
tkdnd = [(os.path.abspath(file), 'tkdnd2.9.2') for file in iglob('build_files/tkdnd2.9.2/*.*')]
block_cipher = None
a = Analysis([f'{os.getcwd()}/music_caster.py'],
             pathex=[os.getcwd()],
             binaries=[],
             datas=tkdnd,
             hiddenimports=['pkg_resources.py2_warn', 'pystray._win32'],
             hookspath=[],
             runtime_hooks=[],
             excludes=['crypto', 'cryptography', 'pycryptodome', 'pandas',
                       'numpy', 'simplejson', 'PySide2', 'PyQt5', 'greenlet'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
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
          upx_exclude=['vcruntime140.dll', 'msvcp140.dll', 'python36.dll', 'python37.dll', 'python38.dll'],
          runtime_tmpdir=None,
          console=False, version='mc_version_info.txt', icon=os.path.abspath('../resources/Music Caster Icon.ico'))
