import ctypes
import multiprocessing as mp
from contextlib import suppress
from functools import lru_cache

import pystray
from PIL import Image
from pystray import MenuItem as item

# for cross platform https://stackoverflow.com/a/20996948/7732434?

CHANGE_DPI_SCALE = True
MENU_SHOW_HEIGHT = False


@lru_cache(maxsize=1)
def win_imports():
    import pywintypes
    import win32api
    import win32con


def is_plugged_in():
    """
    Returns True if laptop or PC is plugged in
    might throw ImportError on Linux
    throws RuntimeError
    """
    from ctypes import wintypes

    class SYSTEM_POWER_STATUS(ctypes.Structure):
        _fields_ = [
            ('ACLineStatus', ctypes.c_ubyte),
            ('BatteryFlag', ctypes.c_ubyte),
            ('BatteryLifePercent', ctypes.c_ubyte),
            ('SystemStatusFlag', ctypes.c_ubyte),
            ('BatteryLifeTime', wintypes.DWORD),
            ('BatteryFullLifeTime', wintypes.DWORD),
        ]

    SYSTEM_POWER_STATUS_P = ctypes.POINTER(SYSTEM_POWER_STATUS)

    GetSystemPowerStatus = ctypes.windll.kernel32.GetSystemPowerStatus
    GetSystemPowerStatus.argtypes = [SYSTEM_POWER_STATUS_P]
    GetSystemPowerStatus.restype = wintypes.BOOL

    status = SYSTEM_POWER_STATUS()
    if not GetSystemPowerStatus(ctypes.pointer(status)):
        raise RuntimeError('could not get power status')
    return status.ACLineStatus == 1


def get_aspect_ratio(width, height):
    return round(width / height, 2)


def get_current_res(w=None, h=None):
    with suppress(Exception):
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        res = (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
        if w is not None:
            w.value = res[0]
        if h is not None:
            h.value = res[1]
        return res


@lru_cache(maxsize=1)
def get_initial_res():
    w = mp.Value(ctypes.c_int, 0)
    h = mp.Value(ctypes.c_int, 0)
    # use setProcessDPIAware in only child process
    p = mp.Process(target=get_current_res, args=[w, h])
    p.start()
    p.join()
    return w.value, h.value


@lru_cache(maxsize=1)
def get_initial_dpi_scale():
    with suppress(ImportError):
        import win32api
        transformed_res = (win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1))
        raw_res = get_initial_res()
        return raw_res[0] / transformed_res[0]  # 125% is 1.25
    # TODO: Linux
    return 1


@lru_cache(maxsize=2)
def get_all_resolutions():
    i = 0
    resolutions = []
    seen = set()
    max_width = 0
    max_height = 0
    with suppress(Exception):
        import win32api
        while True:
            ds = win32api.EnumDisplaySettings(None, i)
            res = (ds.PelsWidth, ds.PelsHeight)
            if res not in seen:
                seen.add(res)
                if ds.PelsWidth > max_width:
                    max_width = ds.PelsWidth
                if ds.PelsHeight > max_height:
                    max_height = ds.PelsHeight
                resolutions.append((ds.PelsWidth, ds.PelsHeight))
            i += 1
    aspect_ratio = get_aspect_ratio(max_width, max_height)
    # return resolutions with same aspect ratio as max resolution
    lst = sorted(filter(lambda res: get_aspect_ratio(*res) == aspect_ratio, resolutions))
    return {fmt_res(*res): {'w': res[0], 'h': res[1], 'dpi_scale': calc_dpi_scale(*res)} for res in lst}


dpi_vals = [1.00, 1.25, 1.50, 1.75, 2.00, 2.25, 2.50, 3.00, 3.50, 4.00, 4.50, 5.00]
dpi_vals_map = {dpi: i for i, dpi in enumerate(dpi_vals)}


def get_recommended_dpi_idx():
    dpi = ctypes.c_int(0)
    if ctypes.windll.user32.SystemParametersInfoA(0x009E, 0, ctypes.byref(dpi), 1) != 0:
        return -1 * dpi.value
    raise IndexError


def calc_dpi_scale(new_w, _):
    # assume constant aspect ratios
    dpi_scale = get_initial_dpi_scale()
    initial_w = get_initial_res()[0]
    res_change = 1 - min(new_w, initial_w) / max(new_w, initial_w)
    dpi_scale += res_change if new_w > initial_w else -res_change
    return dpi_scale


def set_resolution(width: int, height: int, dpi_scale: int):
    with suppress(ImportError):
        import pywintypes
        import win32api
        import win32con
        # adapted from Peter Wood: https://stackoverflow.com/a/54262365
        devmode = pywintypes.DEVMODEType()
        devmode.PelsWidth = width
        devmode.PelsHeight = height
        devmode.Fields = win32con.DM_PELSWIDTH | win32con.DM_PELSHEIGHT

        win32api.ChangeDisplaySettings(devmode, 0)

        if CHANGE_DPI_SCALE:
            # https://stackoverflow.com/a/62916586/7732434
            # dpi_scale = calc_dpi_scale(width, height)
            with suppress(KeyError, IndexError):
                ref_idx = get_recommended_dpi_idx()
                # dpi of 1.5 -> 2 - 1 = rel index of 1
                # dpi of 1 -> 0 - 1 = rel index of -1
                rel_idx = dpi_vals_map[dpi_scale] - ref_idx
                ctypes.windll.user32.SystemParametersInfoA(0x009F, rel_idx, 0, 1)


def set_res_curry(width, height, dpi_scale):
    # ensure correct values are used when lambda executes
    return lambda: set_resolution(width, height, dpi_scale)


def fmt_res(width, height, show_width=False):
    # formats either W x H or Wp
    return f'{width} x {height}' if show_width else f'{height}p'


def on_exit():
    icon.visible = False
    icon.stop()


if __name__ == '__main__':
    mp.freeze_support()
    # save cache
    get_initial_dpi_scale()
    image = Image.open('icon.png')
    menu = [item(k, set_res_curry(v['w'], v['h'], v['dpi_scale'])) for k, v in get_all_resolutions().items()]
    menu.append(item('Exit', on_exit))
    icon = pystray.Icon('Resolution Switcher', image, 'Resolution Switcher', menu)
    icon.run()
