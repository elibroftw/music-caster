import webview
import platform
import sys
import os
import socket

frameless = platform.system() == 'Windows'

try:
    frontend_entry = f'{sys._MEIPASS}/frontend/index.html'
except AttributeError:
    frontend_entry = 'frontend/index.html'
    if not os.path.exists(frontend_entry):
        # assume running in DEBUG
        frontend_entry = 'http://localhost:5173/'

webview.create_window('Music Caster', frontend_entry, frameless=frameless)
webview.start()
# python -Om PyInstaller webview_demo.py
