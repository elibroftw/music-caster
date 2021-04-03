# -*- mode: python ; coding: utf-8 -*-
import os
import sys
# noinspection PyPackageRequirements
from PyInstaller.building.api import PYZ, EXE
# noinspection PyPackageRequirements
from PyInstaller.building.build_main import Analysis
# noinspection PyPackageRequirements
from PyInstaller.config import CONF

CONF['distpath'] = './dist'
block_cipher = None
# noinspection PyTypeChecker
sys.modules['FixTk'] = None
a = Analysis([f'{os.getcwd()}/updater.py'],
             pathex=[os.getcwd()],
             binaries=[],
             datas=[],
             hiddenimports=['pkg_resources.py2_warn'],
             hookspath=[],
             runtime_hooks=[],
             excludes=['pandas', 'numpy', 'cryptography', 'simplejson', 'PySide2', 'FixTk', 'tcl', 'tk', '_tkinter',
                       'tkinter', 'Tkinter'],
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
          name='Updater',
          debug=False,
          manifest='build_files/Updater.exe.MANIFEST',
          bootloader_ignore_signals=False,
          strip=False,
          upx=False,
          upx_exclude=['vcruntime140.dll', 'msvcp140.dll', 'python36.dll', 'python37.dll', 'python38.dll'],
          runtime_tmpdir=None,
          console=False,
          icon=os.path.abspath('resources/Updater.ico'),
          version='mcu_version_info.txt')
# ONLY USE FOR DEBUGGING
# noinspection PyUnresolvedReferences
# coll = COLLECT(exe,
#                a.binaries - TOC([('libcrypto-1_1.dll', None, None)]),
#                a.zipfiles,
#                a.datas,
#                strip=False,
#                upx=False,
#                upx_exclude=['vcruntime140.dll', 'msvcp140.dll', 'python36.dll', 'python37.dll', 'python38.dll'],
#                name='updater')
