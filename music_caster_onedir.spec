# -*- mode: python ; coding: utf-8 -*-
import os
block_cipher = None


a = Analysis(['music_caster.py'],
             pathex=[os.getcwd()],
             binaries=[],
             datas=[('resources/default.png', 'images'),
                    ('templates/home.html', 'templates'),
                    ('static/style.css', 'static')],
             hiddenimports=[],
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
          upx_exclude=['vcruntime140.dll', 'python.dll', 'wxmsw30u_propgrid_vc140_x64.dll', 'wxmsw30u_qa_vc140_x64.dll',
                       'wxmsw30u_ribbon_vc140_x64.dll', 'wxmsw30u_richtext_vc140_x64.dll', 'wxmsw30u_stc_vc140_x64.dll',
                       'wxmsw30u_webview_vc140_x64.dll', 'wxmsw30u_xrc_vc140_x64.dll', 'wxbase30u_net_vc140_x64.dll',
                       'wxbase30u_vc140_x64.dll', 'wxbase30u_xml_vc140_x64.dll', 'wxmsw30u_adv_vc140_x64.dll',
                       'wxmsw30u_aui_vc140_x64.dll', 'wxmsw30u_gl_vc140_x64.dll', 'wxmsw30u_html_vc140_x64.dll',
                       'wxmsw30u_media_vc140_x64.dll', 'MSVCP140.DLL'],
          runtime_tmpdir=None,
          console=False,
          icon='resources/Music Caster.ico',
          version='MC_version_info.txt')

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='Music Caster',
    strip=False,
    upx=True)