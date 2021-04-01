from subprocess import Popen, PIPE, DEVNULL
import re


class Shared:
    """
    Variables to be shared between music_caster.py and helpers.py
    """
    lang = ''


def get_running_processes(look_for=''):
    if look_for:
        cmd = f'tasklist /NH /FI "IMAGENAME eq {look_for}"'
    else:
        cmd = f'tasklist /NH'
    p = Popen(cmd, shell=True, stdout=PIPE, stdin=DEVNULL, stderr=DEVNULL, text=True)
    task = p.stdout.readline()
    while task != '':
        task = p.stdout.readline().strip()
        m = re.match(r'(.+?) +(\d+) (.+?) +(\d+) +(\d+.* K).*', task)
        if m is not None:
            process = {'name': m.group(1), 'pid': int(m.group(2)), 'session_name': m.group(3),
                       'session_num': m.group(4), 'mem_usage': m.group(5)}
            yield process


def is_already_running(look_for='Music Caster.exe', threshold=1):
    for process in get_running_processes(look_for=look_for):
        if process['name'] == look_for:
            threshold -= 1
            if threshold < 0: return True
    return False
