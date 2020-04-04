import socket
import pychromecast
import threading


thread_results = []
threads = []


def connect_threaded(hostname, port, timeout, thread_index):
    result = connect(hostname, port, timeout)
    if result: thread_results[thread_index] = hostname


def connect(hostname, port=8008, timeout=0.1):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    result = sock.connect_ex((hostname, port))
    sock.close()
    return result == 0


def find_chromecasts(timeout=0.2, callback=None):
    hostname = socket.gethostname()
    ipv4_address = socket.gethostbyname(hostname)
    base = '.'.join(ipv4_address.split('.')[:-1])
    for i in range(256):
        thread_results.append(False)
        res_ip = f'{base}.{i}'
        t = threading.Thread(target=connect_threaded, args=[res_ip, 8008, timeout, i])
        t.start()
        threads.append(t)
    chromecasts = []
    for i, t in enumerate(threads):
        t.join()
        ip = thread_results[i]
        if ip:
            cc = pychromecast.Chromecast(ip)
            if callback: callback(cc)
            else: chromecasts.append(cc)
            
    return chromecasts


if __name__ == '__main__':
    import time
    start = time.time()
    ccs = find_chromecasts()
    print(ccs)
    print(time.time() - start)
