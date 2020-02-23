# -*- mode: python ; coding: utf-8 -*-
import os
block_cipher = None


a = Analysis(['updater.py'],
             pathex=[os.getcwd()],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
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
          name='Music Caster Downloader',
          debug=False,
          manifest=None,
          bootloader_ignore_signals=False,
          strip=False,
          upx=False,
          upx_exclude=['vcruntime140.dll', 'python36.dll'],
          runtime_tmpdir=None,
          console=False,
          icon='resources/Updater.ico',
          version='version_info.txt')
