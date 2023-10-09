"""
Shared functions between app and build
"""
import platform
import re
from subprocess import DEVNULL, PIPE, Popen


def get_running_processes(look_for='', pid=None, add_exe=True):
    if platform.system() == 'Windows':
        cmd = f'tasklist /NH'
        if look_for:
            if not look_for.endswith('.exe') and add_exe:
                look_for += '.exe'
            cmd += f' /FI "IMAGENAME eq {look_for}"'
        if pid is not None:
            cmd += f' /FI "PID eq {pid}"'
        p = Popen(cmd, shell=True, stdout=PIPE, stdin=DEVNULL, stderr=DEVNULL, text=True, encoding='iso8859-2')
        p.stdout.readline()
        for task in iter(lambda: p.stdout.readline().strip(), ''):
            m = re.match(r'(.+?) +(\d+) (.+?) +(\d+) +(\d+.* K).*', task)
            if m is not None:
                yield {'name': m.group(1), 'pid': int(m.group(2)), 'session_name': m.group(3),
                       'session_num': m.group(4), 'mem_usage': m.group(5)}
    elif platform.system() == 'Linux':
        cmd = ['ps', 'h']
        if look_for:
            cmd.extend(('-C', look_for))
        p = Popen(cmd, stdout=PIPE, stdin=PIPE, stderr=DEVNULL, text=True)
        for task in iter(lambda: p.stdout.readline().strip(), ''):
            m = task.split(maxsplit=4)
            yield {'name': m[-1], 'pid': int(m[0])}


def is_already_running(look_for='Music Caster', threshold=1, pid=None) -> bool:
    """
    Returns True if more processes than `threshold` were found
    # TODO: threshold feature for Linux
    """
    if platform.system() == 'Windows':
        for _ in get_running_processes(look_for=look_for, pid=pid):
            threshold -= 1
            if threshold < 0:
                return True
    else:  # Linux
        p = Popen(['ps', 'h', '-C', look_for, '-o', 'comm'], stdout=PIPE, stdin=PIPE, stderr=DEVNULL, text=True)
        return p.stdout.readline().strip() != ''
    return False
