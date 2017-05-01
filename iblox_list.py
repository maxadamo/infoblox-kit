#!/usr/bin/python
#
"""
  esoteric requirements:
    - infoblox-client (installable through pip)
"""
import os
import platform
import ConfigParser
from infoblox_client import connector
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning


if platform.system() == 'Windows':
    IBLOX_CONF = os.path.join(os.path.expanduser('~'), 'iblox.cfg')
else:
    IBLOX_CONF = os.path.join(os.environ['HOME'], '.ibloxrc')

IBLOX_CONF_CONTENT = """[iblox]\n
# Infoblox server <string>: infblox server fqdn
iblox_server = infoblox.foo.bar.com\n
# Infoblox username <string>: your_username
iblox_username = your_username\n
# Infoblox password <string>: your_password
iblox_password = your_secret_pass_here\n
"""


def span_ipv4(start=96):
    """ span IPv4 from 62.40.96.1 to 62.40.127.254 """
    net_prefix = '62.40.'
    config = ConfigParser.RawConfigParser()
    config.readfp(open(IBLOX_CONF))
    opts = {
        'host': config.get('iblox', 'iblox_server'),
        'username': config.get('iblox', 'iblox_username'),
        'password': config.get('iblox', 'iblox_password')
        }
    conn = connector.Connector(opts)

    def yield_ipv4(scope):
        """ return generator with IPv4 """
        _host_types = conn.get_object('record:host', {'ipv4addr~': scope})
        host_types = [str(s['ipv4addrs'][0]['ipv4addr']) for s in _host_types]
        _a_types = conn.get_object('record:a', {'ipv4addr~': scope})
        a_types = [str(s['ipv4addr']) for s in _a_types]
        _merged_types = host_types + a_types
        merged_types = [s.split('.')[-1] for s in _merged_types]
        for ipv4_addr in merged_types:
            yield int(ipv4_addr)

    while start < 128:
        ip_items = []
        net_scope = '{}{}.'.format(net_prefix, start)
        ip_generator = yield_ipv4(net_scope)
        try:
            pre_ip_items = sorted(list(ip_generator))
        except TypeError:
            pre_ip_items = []
            os.sys.stdout.write("Free IPs WITHIN {}0 => WHOLE NETWORK".format(net_scope))
        else:
            os.sys.stdout.write("Free IPs within {}0 => ".format(net_scope))

        # removing possible duplicates and weird records that I have seen
        for i in pre_ip_items:
            if i not in ip_items and i != 0:
                ip_items.append(i)

        free_ip = []
        for octet in ip_items:
            index_number = ip_items.index(octet) + 1
            if index_number != octet:
                free_ip.append("{}{}".format(net_scope, index_number))
                # os.sys.stdout.write("{}{}, ".format(net_scope, index_number))
                # break
        joined_free_ip = ", ".join(free_ip)
        print "{}\n".format(joined_free_ip)
        start += 1


if __name__ == '__main__':
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    print "searching free IPs v4 available on each network from 62.40.96.1 to 62.40.127.254"
    print '-'*80

    span_ipv4()

    print "\nsearching free IPs v6 available on each network from 62.40.96.1 to 62.40.127.254"
    print '-'*80
