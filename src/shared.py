"""
Shared functions between app and build
"""
import os
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
        p = Popen(
            cmd,
            shell=True,
            stdout=PIPE,
            stdin=DEVNULL,
            stderr=DEVNULL,
            text=True,
            encoding='iso8859-2',
        )
        p.stdout.readline()
        for task in iter(lambda: p.stdout.readline().strip(), ''):
            m = re.match(r'(.+?) +(\d+) (.+?) +(\d+) +(\d+.* K).*', task)
            if m is not None:
                yield {
                    'name': m.group(1),
                    'pid': int(m.group(2)),
                    'session_name': m.group(3),
                    'session_num': m.group(4),
                    'mem_usage': m.group(5),
                }
    elif platform.system() == 'Linux':
        # `comm` may itself contain spaces, so ask only for pid + full command
        # line: the pid is numeric and first, which makes the split unambiguous
        cmd = ['ps', '-eo', 'pid=,args=']
        if pid is not None:
            cmd = ['ps', '-o', 'pid=,args=', '-p', str(pid)]
        try:
            p = Popen(cmd, stdout=PIPE, stdin=DEVNULL, stderr=DEVNULL, text=True)
        except FileNotFoundError:
            # procps-ng is absent from minimal containers; report nothing running
            # rather than taking down the caller (startup instance check, build)
            return
        look_for_cf = look_for.casefold()
        for task in iter(lambda: p.stdout.readline().strip(), ''):
            process_id, _, args = task.partition(' ')
            if not process_id.isdigit():
                continue
            args = args.strip()
            # the executable name, e.g. "music-caster" for "/opt/mc/music-caster -m"
            name = args.split(' ', 1)[0].rsplit('/', 1)[-1]
            # match against the whole command line so a script started via the
            # interpreter (python .../music_caster.py) is found too
            if look_for and look_for_cf not in args.casefold():
                continue
            yield {
                'name': name,
                'pid': int(process_id),
                'session_name': '',
                'session_num': '',
                'mem_usage': '',
            }


def is_already_running(look_for='Music Caster', threshold=1, pid=None) -> bool:
    """
    Returns True if more processes than `threshold` were found
    """
    if platform.system() not in {'Windows', 'Linux'}:
        return False
    own_pid = os.getpid()
    for process in get_running_processes(look_for=look_for, pid=pid):
        if platform.system() == 'Linux' and process['pid'] == own_pid:
            # ps sees this process too, tasklist filters are applied by name
            continue
        threshold -= 1
        if threshold < 0:
            return True
    return False
