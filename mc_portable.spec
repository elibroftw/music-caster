# -*- mode: python ; coding: utf-8 -*-
import os
block_cipher = None


a = Analysis(['music_caster.py'],
             pathex=[os.getcwd()],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=['pandas', 'simplejson', 'PySide2'],
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
          manifest=None,
          bootloader_ignore_signals=False,
          strip=False,
          upx=False,
          upx_exclude=['VCRUNTIME140.dll', 'python.dll'],
          runtime_tmpdir=None,
          console=False,
          icon='resources/Music Caster.ico',
          version='MC_version_info.txt')
#  coll = COLLECT(
#    exe,
#    a.binaries,
#    a.zipfiles,
#    a.datas,
#    name='Music Caster',
#    strip=False,
#    upx=True)