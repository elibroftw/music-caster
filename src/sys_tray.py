import multiprocessing as mp
import platform
import io
import sys
from itertools import islice
import threading
import time
import os
from base64 import b64decode
import ctypes


def system_tray(main_queue: mp.Queue, child_queue: mp.Queue):
    from b64_images import FILLED_ICON, UNFILLED_ICON

    if platform.system() == 'Linux':
        os.environ['PYSTRAY_BACKEND'] = 'appindicator'
    elif platform.system() == 'Windows' and getattr(sys, 'frozen', False):
        my_app_id = 'elijahlopez.music_caster'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(my_app_id)
    import pystray
    from PIL import Image

    filled_icon = Image.open(io.BytesIO(b64decode(FILLED_ICON)))
    unfilled_icon = Image.open(io.BytesIO(b64decode(UNFILLED_ICON)))

    def create_menu(lst, root=True):
        # e.g. ['Item 1', ('Item 2 Display', 'item_2_key'), ['Sub Menu Title', ('Sub Menu Item 1 Display', 'KEY')]]
        items = []
        if root:
            items.append(
                pystray.MenuItem(
                    '', get_tray_action('__ACTIVATED__'), default=True, visible=False
                )
            )
        for element in lst:
            if isinstance(element, list):
                items.append(
                    pystray.MenuItem(
                        element[0], create_menu(islice(element, 1, None), root=False)
                    )
                )
            elif isinstance(element, tuple) and len(element) == 2:
                element, key = element
                items.append(pystray.MenuItem(element, get_tray_action(element, key)))
            else:
                items.append(pystray.MenuItem(element, get_tray_action(element)))
        return pystray.Menu(*items)

    def get_tray_action(string, key=''):
        def tray_action():
            try:
                main_queue.put(key) if key else main_queue.put(string)
                if key == '__EXIT__':
                    child_queue.put({'close': None})
            except ValueError:
                child_queue.put({'close': None})

        return tray_action

    def background():
        while True:
            while not child_queue.empty():
                for parent_cmd, arguments in child_queue.get().items():
                    if parent_cmd == 'tooltip':
                        tray.title = arguments
                    elif parent_cmd == 'menu':  # set icon to unfilled
                        if tray.HAS_MENU:
                            tray.menu = create_menu(arguments)
                            tray.update_menu()
                        else:
                            print('pystray: menu not supported')
                    elif parent_cmd == 'filled':  # set icon to filled
                        tray.icon = filled_icon
                    elif parent_cmd == 'unfilled':  # set icon to unfilled
                        tray.icon = unfilled_icon
                    elif parent_cmd == 'notify':
                        if tray.HAS_NOTIFICATION:
                            tray.notify(
                                arguments['message'], title=arguments.get('title')
                            )  # msg, title
                        else:
                            print('pystray: notify not supported')
                    elif parent_cmd == 'hide':
                        tray.visible = False
                    elif parent_cmd in {'close', 'exit', '__EXIT__'}:
                        tray.stop()
                        sys.exit()
            time.sleep(0.1)

    tray = pystray.Icon(
        'Music Caster SystemTray', unfilled_icon, title='Music Caster [LOADING]'
    )
    threading.Thread(target=background, daemon=True).start()
    tray.run()
