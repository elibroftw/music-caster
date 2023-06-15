import webview
import platform
import Crypto.Math

frameless = platform.system() == 'Windows'

webview.create_window('Hello world', '../src-frontend/dist/index.html', frameless=frameless)
webview.start()
# python -Om PyInstaller webview_demo.py
