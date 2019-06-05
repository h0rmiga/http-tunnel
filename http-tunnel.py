#!/usr/bin/env python3

import argparse
import asyncio
import base64
import logging
import logging.handlers
import signal
import socket
import yaml


class TunnelServer:
    def __init__(self, config_path, logger):
        self.log = logger
        self.proxy = {}
        self.tunnels = {}
        self.load_config(config_path)
        self.loop = asyncio.get_event_loop()

    def load_config(self, path):
        self.log.info('Using config file: %s', path)
        with open(path, 'r') as config_file:
            config = yaml.safe_load(config_file) or {}

        valid = True

        proxy_config = config.get('proxy', {})
        if not isinstance(proxy_config, dict):
            self.log.critical(
                'proxy must be dict, %s found',
                type(proxy_config).__name__,
            )
            valid = False

        tunnels_config = config.get('tunnels', {})
        if not isinstance(tunnels_config, dict):
            self.log.critical(
                'tunnels must be dict, %s found',
                type(tunnels_config).__name__,
            )

        if not valid:
            raise TypeError

        for option_name, option_type, option_default in [
                ('host', str, '127.0.0.1'),
                ('port', int, 3128),
                ('user', str, ''),
                ('password', str, ''),
        ]:
            option_value = proxy_config.get(option_name, option_default)
            if isinstance(option_value, option_type):
                self.proxy[option_name] = option_value
            else:
                self.log.critical(
                    'proxy.%s must be %s, %s found',
                    option_name,
                    option_type.__name__,
                    type(option_value).__name__,
                )
                valid = False

        for local_port, remote in tunnels_config.items():
            if not isinstance(local_port, int):
                self.log.critical(
                    'tunnels key must be int (port number), %s found',
                    type(local_port).__name__,
                )
                valid = False
                continue
            if not isinstance(remote, str):
                self.log.critical(
                    'tunnels value must be string (host:port), %s found',
                    type(remote).__name__,
                )
                valid = False
                continue
            self.tunnels[local_port] = remote

        if not valid:
            raise TypeError

    async def data_transfer(self, reader, writer, client_name, side):
        while True:
            buf = await reader.read(4096)
            if not buf:
                break
            self.log.debug('%s - %s data: %s', client_name, side, str(buf))
            writer.write(buf)
        writer.close()
        self.log.info('%s - %s connection closed', client_name, side)

    def get_connection_callback(self, remote):
        async def connection_callback(client_reader, client_writer):
            _, server_port = client_reader._transport.get_extra_info('sockname')
            client_name = '{}:{}'.format(*client_reader._transport.get_extra_info('peername'))
            self.log.info('%s - Conection to port %s (%s)', client_name, server_port, remote)

            try:
                proxy_reader, proxy_writer = await asyncio.open_connection(
                    host=self.proxy['host'],
                    port=self.proxy['port'],
                )
                proxy_request = 'CONNECT {} HTTP/1.1\r\n'.format(remote)
                proxy_request += 'Proxy-Connection: keep-alive\r\n'
                if self.proxy['user']:
                    auth = base64.b64encode(bytearray('{user}:{password}'.format(**self.proxy), 'ascii')).decode('ascii')
                    proxy_request += 'Proxy-Authorization: Basic {}\r\n'.format(auth)
                proxy_request += '\r\n'
                proxy_writer.write(bytearray(proxy_request, 'ascii'))

                proxy_reply = (await proxy_reader.readuntil(b'\r\n\r\n')).split(b'\r\n')[0].decode('ascii')
                self.log.info('%s - Proxy reply: %s', client_name, proxy_reply)
                if proxy_reply.split()[1] == '200':
                    self.loop.create_task(self.data_transfer(client_reader, proxy_writer, client_name, 'Client'))
                    self.loop.create_task(self.data_transfer(proxy_reader, client_writer, client_name, 'Server'))
                else:
                    client_writer.close()
            except OSError as exc:
                self.log.error('%s - %s: %s', client_name, exc.__class__.__name__, str(exc))
                client_writer.close()
        return connection_callback

    def start(self):
        for signum in (signal.SIGINT, signal.SIGTERM):
            self.loop.add_signal_handler(signum, self.loop.stop)
        for port, remote in self.tunnels.items():
            self.log.info('Starting server on port %s (%s)', port, remote)
            self.loop.run_until_complete(
                asyncio.start_server(
                    self.get_connection_callback(remote),
                    port=port,
                    family=socket.AF_INET,
                )
            )
        self.loop.run_forever()
        self.log.info('Shutdown')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('config', nargs='?', default='http-tunnel.yml')
    parser.add_argument('--syslog', action='store_true')
    parser.add_argument('--debug', dest='log_level', action='store_const', const='DEBUG', default='INFO')
    args = parser.parse_args()

    logger = logging.getLogger()
    if args.syslog:
        syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
        syslog_handler.ident = 'http-tunnel: '
        syslog_handler.setFormatter(logging.Formatter('%(message)s'))
        syslog_handler.setLevel(args.log_level)
        logger.addHandler(syslog_handler)
    else:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        stream_handler.setLevel(args.log_level)
        logger.addHandler(stream_handler)
    logger.setLevel(args.log_level)

    server = TunnelServer(config_path=args.config, logger=logger)
    server.start()


if __name__ == '__main__':
    main()
