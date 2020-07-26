# -*- mode: python ; coding: utf-8 -*-
import os
from glob import glob
block_cipher = None

vlc_files = [(file, os.path.dirname(file)) for file in glob('vlc/**/*.*', recursive=True)]
data_files = [('resources/default.png', 'images'),
              ('templates/index.html', 'templates'),
              ('static/style.css', 'static')] + vlc_files

a = Analysis(['music_caster.py'],
             pathex=[os.getcwd()],
             binaries=[],
             datas=data_files,
             hiddenimports=['pkg_resources.py2_warn'],
             hookspath=[],
             runtime_hooks=[],
             excludes=['pandas', 'numpy', 'cryptography', 'simplejson', 'PySide2'],
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
          console=False , version='mc_version_info.txt', icon='resources/Music Caster.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=False,
               upx_exclude=['vcruntime140.dll', 'msvcp140.dll', 'python36.dll'],
               name='Music Caster')