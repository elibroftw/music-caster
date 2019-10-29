import socket
import pychromecast
import threading


thread_results = []
threads = []


def connect_threaded(hostname, port, thread_index):
    result = connect(hostname, port)
    if result: thread_results[thread_index] = hostname


def connect(hostname, port, timeout=0.1):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    result = sock.connect_ex((hostname, port))
    sock.close()
    return result == 0


def find_chromecasts():
    hostname = socket.gethostname()
    ipv4_address = socket.gethostbyname(hostname)
    base = '.'.join(ipv4_address.split('.')[:-1])
    for i in range(256):
        thread_results.append(False)
        res_ip = f'{base}.{i}'
        t = threading.Thread(target=connect_threaded, args=[res_ip, 8008, i])
        t.start()
        threads.append(t)
    chromecasts = []
    for i, t in enumerate(threads):
        t.join()
        ip = thread_results[i]
        if ip: chromecasts.append(pychromecast.Chromecast(ip))        
    return chromecasts


if __name__ == '__main__':
    import time
    start = time.time()
    print(find_chromecasts())
    print(time.time() - start)