# http-tunnel
### Description
http-tunnel is a service, which allows you to create TCP tunnels over HTTP proxy servers, such as corporate proxy, in environments, where outgoing connections are somehow restricted.

Be aware, that HTTP proxy server must be configured to allow CONNECT requests to specified destination port.

### Requirements
http-tunnel requires Python 3.5+ and PyYAML module installed.

### Installation
To install http-tunnel as a systemd service, just run `make install` command.

### Configuration
Configuration file is a simple YAML file consisting of two sections: __proxy__ and __tunnels__.

__proxy__ section describes your connection to the proxy server. If _user_ parameter is defined in __proxy__ section, basic authorization will be used.

__tunnels__ sections describes TCP tunnels. Each key in this section describes port number, on which connections will be accepted. Each value is a string to be sent to proxy server with CONNECT request. Typically, it should be in form of "hostname:port".

Configuration example:
```
proxy:
  host: 'proxy.company.tld'
  port: 8080
  user: 'lorem'
  password: 'ipsum'
tunnels:
  2222: 'remote.server.tld:22'
  2223: 'other.server.tld:22'
```
