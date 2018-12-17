#!/usr/bin/env python3
from argparse import ArgumentParser, FileType
from yaml import safe_load
from time import sleep
from threading import Thread
from socket import socket, setdefaulttimeout, SOL_SOCKET, SO_REUSEADDR, SHUT_RDWR
from base64 import b64encode
import logging


class TunnelServer(object):
    def __init__(self, proxy, tunnels):
        if type(proxy) is not dict:
            raise TypeError('proxy must be dict, %s found' % type(proxy))

        self.proxy_host = proxy.get('host', '127.0.0.1')
        if type(self.proxy_host) is not str:
            raise TypeError('proxy.host must be string, %s found' % type(self.proxy_host))

        self.proxy_port = proxy.get('port', 3128)
        if type(self.proxy_port) is not int:
            raise TypeError('proxy.port must be int, %s found' % type(self.proxy_port))

        proxy_user = proxy.get('user')
        if type(proxy_user) is not str and proxy_user is not None:
            raise TypeError('proxy.user must be string, %s found' % type(proxy_user))
        if proxy_user is not None:
            proxy_password = proxy.get('password', '')
            if type(proxy_password) is not str:
                raise TypeError('proxy.password must be string, %s found' % type(proxy_password))
            self.proxy_auth = b64encode(bytearray('%s:%s' % (proxy_user, proxy_password), 'ascii')).decode('ascii')
        else:
            self.proxy_auth = None

        if type(tunnels) is not dict:
            raise TypeError('tunnels must be a dict')
        self.tunnels = {}

        for local_port, remote in tunnels.items():
            if type(local_port) is not int:
                raise TypeError('tunnels key must be int (port number), %s found' % type(local_port))
            if type(remote) is not str:
                raise TypeError('tunnels value must be string (host:port), %s found' % type(remote))
            self.tunnels[local_port] = remote

    def _transfer_loop(self, socket1, socket2, client_addr, side):
        try:
            while True:
                buf = socket1.recv(4096)
                if not len(buf):
                    break
                socket2.send(buf)
        except (ConnectionError, OSError):
            pass
        try:
            socket2.shutdown(SHUT_RDWR)
        except OSError:
            pass
        logging.info('%s - %s connection closed', client_addr, side)
        socket1.close()

    def _accept_loop(self, local_port, remote):
        listen_sock = socket()
        listen_sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        listen_sock.bind(('0.0.0.0', local_port))
        listen_sock.listen(10)
        while True:
            try:
                client_sock, client_addr = listen_sock.accept()
                client_addr = ':'.join(map(str, client_addr))
                logging.info('%s - Conection to port %s', client_addr, local_port)

                proxy_sock = socket()
                proxy_sock.connect((self.proxy_host, self.proxy_port))

                request = 'CONNECT %s HTTP/1.1\r\nProxy-Connection: keep-alive\r\n' % remote
                if self.proxy_auth:
                    request += 'Proxy-Authorization: Basic %s\r\n' % self.proxy_auth
                request += '\r\n'
                proxy_sock.send(bytearray(request, 'ascii'))

                reply_head, reply_body = proxy_sock.recv(4096).split(b'\r\n\r\n', 1)
                reply_head = reply_head.decode('ascii').split('\r\n')[0]
                logging.info('%s - %s', client_addr, reply_head)

                if reply_head.split()[1]=='200':
                    if len(reply_body)>0:
                        client_sock.send(reply_body)
                    Thread(target=self._transfer_loop, args=(client_sock, proxy_sock, client_addr, 'Client')).start()
                    Thread(target=self._transfer_loop, args=(proxy_sock, client_sock, client_addr, 'Server')).start()
                else:
                    client_sock.close()
                    proxy_sock.close()
            except OSError as e:
                logging.error('Failed to accept connection: %s - %s', e.__class__.__name__, str(e))
                client_sock.close()
                proxy_sock.close()

    def start(self):
        accept_threads = []
        for local_port, remote in self.tunnels.items():
            accept_threads.append(Thread(target=self._accept_loop, args=(local_port, remote), daemon=True))
            accept_threads[-1].start()
        logging.info('Service started')
        try:
            while all([t.isAlive() for t in accept_threads]):
                sleep(1)
        except (InterruptedError, KeyboardInterrupt):
            pass
        logging.info('Service stopped')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    parser = ArgumentParser()
    parser.add_argument('config', nargs='?', default = 'http-tunnel.yml')
    with open(parser.parse_args().config) as config_file:
        config = safe_load(config_file) or {}
    server = TunnelServer(config.get('proxy', {}), config.get('tunnels', {}))
    server.start()
