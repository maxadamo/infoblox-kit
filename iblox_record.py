#!/usr/bin/python
#
"""
  esoteric requirements:
    - infoblox-client (installable through pip)
  TODO:
    - add External/Internal view for Infoblox (now we've hardcoded External)
"""
import os
import argparse
import textwrap
import platform
import ConfigParser
from infoblox_client import connector
from infoblox_client import objects
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning


OS = platform.system()
if OS == 'Windows':
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


def parse():
    """ parse arguments """

    intro = """\
        With this script you can add/replace/destroy A and AAAA record on Infoblox
        --------------------------------------------------------------------------
        Adding: iblox.py --host foo.bar.com --ipv4 192.168.0.10 --ipv6 2a00:1450:4009:810::2009
        Removing: iblox.py --host foo.bar.com --destroy
        Hint: If you add a record, you will implicitly replace any existing entry which is
              different from the one provided to the script
         """
    parser = argparse.ArgumentParser(
        formatter_class=lambda prog:
        argparse.RawDescriptionHelpFormatter(prog, max_help_position=29),
        description=textwrap.dedent(intro),
        epilog="Author: Massimiliano Adamo <massimiliano.adamo@geant.org>")

    parser.add_argument('--host', help='host name', required=True)
    parser.add_argument('--ipv6', help='IPv6, optional', required=False)
    parser.add_argument('--ipv4', help='IPv4, mandatory when you create a record', required=False)
    parser.add_argument('--destroy', help='destroy record', action='store_true')

    return parser.parse_args()


def byebye(status=0):
    """ say good bye """
    os.sys.exit(status)


class Iblox(object):
    """manage infoblox entries"""
    config = ConfigParser.RawConfigParser()

    def __init__(self, record, ipv4, ipv6=None):
        self.record = record
        self.ipv4 = ipv4
        self.ipv6 = ipv6
        self.config.readfp(open(IBLOX_CONF))
        self.opts = {
            'host': self.config.get('iblox', 'iblox_server'),
            'username': self.config.get('iblox', 'iblox_username'),
            'password': self.config.get('iblox', 'iblox_password')
            }
        self.conn = connector.Connector(self.opts)

    def query_host(self):
        """ query for host record: return None if it does not exist """
        try:
            host_rec = self.conn.get_object('record:host', {'name': self.record})[0]
        except TypeError:
            return None
        else:
            return host_rec

    def query_a(self):
        """ query for A record: return None if it does not exist or
            if self.ipv4 matches the existing one """
        try:
            a_rec = self.conn.get_object('record:a', {'name': self.record})[0]
        except TypeError:
            return None
        else:
            if self.ipv4 == str(a_rec['ipv4addr']):
                return 'already_there'
            else:
                return a_rec

    def query_aaaa(self):
        """ query for AAAA record: return None if it does not exist or
            if self.ipv6 matches the existing one """
        try:
            aaaa_rec = self.conn.get_object('record:aaaa', {'name': self.record})[0]
        except TypeError:
            return None
        else:
            if self.ipv6 == str(aaaa_rec['ipv6addr']):
                return 'already_there'
            else:
                return aaaa_rec

    def query_ptr4(self):
        """ query for PTR4 record: return None if it does not exist or
            if self.ptr matches the existing one """
        reverse_ipv4 = "{}.in-addr.arpa".format(('.').join(list(reversed(self.ipv4.split('.')))))
        try:
            ptr4_rec = self.conn.get_object('record:ptr', {'name': reverse_ipv4})[0]
        except TypeError:
            return None
        else:
            if self.record == str(ptr4_rec['ptrdname']):
                return 'already_there'
            else:
                return ptr4_rec


    def destroy(self):
        """ clean up host entries """
        host_entry = self.query_host()
        if host_entry:
            self.conn.delete_object(host_entry['_ref'])
            print "destroyed host record {}".format(self.record)

        try:
            self.conn.delete_object(self.conn.get_object(
                'record:a', {'name': self.record})[0]['_ref'])
        except TypeError:
            pass
        else:
            print "destroyed A Record {}".format(self.record)

        try:
            self.conn.delete_object(self.conn.get_object(
                'record:aaaa', {'name': self.record})[0]['_ref'])
        except TypeError:
            pass
        else:
            print "destroyed AAAA Record {}".format(self.record)

        try:
            self.conn.delete_object(self.conn.get_object(
                'record:ptr', {'ptrdname': self.record})[0]['_ref'])
        except TypeError:
            pass
        else:
            print "destroyed PTR Record for {}".format(self.record)


    def destroy_conditional(self):
        """ clean up host entries """
        host_entry = self.query_host()
        a_entry = self.query_a()
        aaaa_entry = self.query_aaaa()
        ptr4_entry = self.query_ptr4()

        if host_entry:
            self.conn.delete_object(host_entry['_ref'])
            print "destroyed host record {}".format(self.record)
        if a_entry and a_entry != 'already_there':
            self.conn.delete_object(a_entry['_ref'])
            print "destroyed A Record {} with IP {}".format(
                self.record, self.ipv4)
        if aaaa_entry and aaaa_entry != 'already_there':
            self.conn.delete_object(aaaa_entry['_ref'])
            print "destroyed AAAA record {} with IPv6 {}".format(
                self.record, self.ipv6)
        if ptr4_entry and ptr4_entry != 'already_there':
            self.conn.delete_object(ptr4_entry['_ref'])
            print "destroyed PTR record {}".format(self.ipv4)

    def rebuild(self):
        """ - destroy host record (always)
            - destroy A and AAA records only if they don't match
            - create new A and AAA records
        """

        self.destroy_conditional()
        a_entry = self.query_a()
        aaaa_entry = self.query_aaaa()
        ptr4_entry = self.query_ptr4()

        if a_entry != 'already_there':
            try:
                objects.ARecord.create(self.conn, view='External',
                                       update_if_exists=True,
                                       name=self.record, ip=self.ipv4)
            except Exception as err:
                print "couldn't create A Record for {} with IP {}: {}".format(
                    self.record, self.ipv4, err)
                byebye(1)
            else:
                print "created A Record {} with IP {}".format(
                    self.record, self.ipv4)
        else:
            print "A Record {} with IPv4 {} is already there".format(
                self.record, self.ipv4)

        if not self.ipv6:
            print "skipping AAAA Record"
        else:
            if aaaa_entry != 'already_there':
                try:
                    objects.AAAARecord.create(self.conn, view='External',
                                              name=self.record, ip=self.ipv6)
                except Exception as err:
                    print "couldn't create AAAA Record {} with IPv6 {}: {}".format(
                        self.record, self.ipv6, err)
                    byebye(1)
                else:
                    print "created AAAA Record {} with IP {}".format(
                        self.record, self.ipv6)
            else:
                print "AAAA Record {} with IPv6 {} is already there".format(self.record, self.ipv6)

        if ptr4_entry != 'already_there':
            try:
                objects.PtrRecordV4.create(self.conn, view='External',
                                           update_if_exists=True, ip=self.ipv4,
                                           ptrdname=self.record)
            except Exception as err:
                print "couldn't create PTR Record {} for host {}: {}".format(
                    self.ipv4, self.record, err)
                byebye(1)
            else:
                print "created PTR Record {} for host {}".format(
                    self.ipv4, self.record)
        else:
            print "PTR Record {} for host {} is already there".format(
                self.ipv4, self.record)

        print '-'*74


if __name__ == '__main__':
    print '-'*74
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    if not os.access(IBLOX_CONF, os.W_OK):
        CONF_FILE = open(IBLOX_CONF, 'w+')
        CONF_FILE.write(IBLOX_CONF_CONTENT)
        CONF_FILE.close()
        print "\nThe following file has been created: {0}\n".format(IBLOX_CONF)
        print "Fill it with proper values and run the script again\n"
        byebye(1)

    ARGS = parse()

    if not ARGS.destroy:
        if not ARGS.ipv4:
            print " --ipv4 is mandatory when you create a new record"
            print " You can use --help to check the options"
            os.sys.exit()
        else:
            IPV4 = ARGS.ipv4
    else:
        if not ARGS.ipv4:
            IPV4 = 'blah'
        else:
            IPV4 = ARGS.ipv4

    if ARGS.ipv6:
        if ARGS.destroy:
            Iblox(ARGS.host, IPV4, ARGS.ipv6).destroy()
        else:
            Iblox(ARGS.host, IPV4, ARGS.ipv6).rebuild()
    else:
        if ARGS.destroy:
            Iblox(ARGS.host, IPV4).destroy()
        else:
            Iblox(ARGS.host, IPV4).rebuild()

    byebye()
