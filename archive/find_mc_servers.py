import socket
import threading


thread_results = []
threads = []


def connect_threaded(hostname, port, timeout, thread_index):
    result = connect(hostname, port, timeout)
    if result: thread_results[thread_index] = hostname


def connect(hostname, port, timeout=0.1):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        result = sock.connect_ex((hostname, port))
    except socket.gaierror:
        result = 1
    sock.close()
    return result == 0


def find_music_caster_servers(timeout=0.2, callback=None):
    hostname = socket.gethostname()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ipv4 = s.getsockname()[0]
    # ipv4_address = socket.gethostbyname(hostname)
    base = ipv4.split('.')[:-1]
    s_last = base.pop()
    base = '.'.join(base)
    seconds_lasts = [s_last]
    _RANGE = 20
    for j in range(_RANGE):
        if j != s_last: seconds_lasts.append(j + int(s_last) - _RANGE//2)
    for second_last in seconds_lasts:
        for i in range(256):
            thread_results.append(False)
            res_ip = f'{base}.{second_last}.{i}'
            t = threading.Thread(target=connect_threaded, args=[res_ip, 2001, timeout, i])
            t.start()
            threads.append(t)
    chromecasts = []
    for i, t in enumerate(threads):
        t.join()
        ip = thread_results[i]
        if ip:
         cc = ip
         if callback: callback(cc)
         else: chromecasts.append(cc)     
    return chromecasts


if __name__ == '__main__':
    import time
    start = time.time()
    servers = find_music_caster_servers()
    if servers: print('Servers Found\n----------------------------')
    for server in servers:
        print(f'http://{server}:2001')
    print('----------------------------')
    print('Seconds taken:', time.time() - start)
