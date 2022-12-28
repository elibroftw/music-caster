import PySimpleGUI as Sg
import platform
from .views import *
import ctypes
import ctypes.wintypes
import sys

ALT_KEY, EXTENDED_KEY, KEY_UP = 0x12, 0x0001, 0x0002
keybd_event = ctypes.windll.user32.keybd_event


def focus_window(window: Sg.Window, is_frozen=getattr(sys, 'frozen', False)):
    # raises TclError [window_is_foreground]
    # use bring_to_front when frozen and in Python use other method
    if platform.system() == 'Windows':
        if is_frozen and window_is_foreground(window):
            window.bring_to_front()
        else:
            keybd_event(ALT_KEY, 0, EXTENDED_KEY | 0, 0)
            ctypes.windll.user32.SetForegroundWindow.argtypes = (ctypes.wintypes.HWND,)
            ctypes.windll.user32.SetForegroundWindow(window.TKroot.winfo_id())
            keybd_event(ALT_KEY, 0, EXTENDED_KEY | KEY_UP, 0)
        if window.TKroot.state() == 'iconic':
            window.normal()
        window.force_focus()
    else:
        window.force_focus()
        window.bring_to_front()


def window_is_foreground(window: Sg.Window):
    # raises TclError
    width, height = window.TKroot.winfo_width(), window.TKroot.winfo_height()
    x, y = window.TKroot.winfo_rootx(), window.TKroot.winfo_rooty()
    if (width, height, x, y) != (1, 1, 0, 0):
        return window.TKroot.winfo_containing(x + (width // 2), y + (height // 2)) is not None
    return False
