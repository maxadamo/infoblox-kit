#!/usr/bin/python
#
"""
  esoteric requirements:
    - infoblox-client (installable through pip)
  TODO:
    - add External/Internal view for Infoblox (now we've hardcoded External)
"""
import os
import getpass
import argparse
import textwrap
from datetime import datetime
from infoblox_client import connector
from infoblox_client import objects
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning


def parse():
    """ parse arguments """

    intro = """\
         With this script you can add/destroy A and AAAA record on Infoblox
         ------------------------------------------------------------------
           Usage Add: iblox.py --host foo.bar.com --ipv4 192.168.0.10 --ipv6 2a00:1450:4009:810::2009 --username massimiliano.adamo
           Usage Remove: iblox.py --host foo.bar.com --username massimiliano.adamo --destroy
           - If you add, you will implicitly replace any existing entry which is different form the one provided to the script
         """
    parser = argparse.ArgumentParser(
        formatter_class=lambda prog:
        argparse.RawDescriptionHelpFormatter(prog, max_help_position=29),
        description=textwrap.dedent(intro),
        epilog="Author: Massimiliano Adamo <massimiliano.adamo@geant.org>")

    parser.add_argument('--host', help='host name', required=True)
    parser.add_argument('--ipv6', help='adds IPv6, optional', required=False)
    parser.add_argument('--ipv4', help='adds IPv4, mandatory when you create a record', required=False)
    parser.add_argument('--username', help='infoblox username', required=True)
    parser.add_argument('--server', default='infoblox.foor.bar.com', help='infoblox server')
    parser.add_argument('--destroy', help='destroy record', action='store_true')

    return parser.parse_args()


def byebye(status=0):
    """ remove main.tf and say good bye """
    os.sys.exit(status)


class Iblox(object):
    """manage infoblox entries"""
    def __init__(self, username, password, server, record, ipv4, ipv6=None):
        self.username = username
        self.server = server
        self.record = record
        self.ipv4 = ipv4
        self.ipv6 = ipv6
        self.opts = {
            'host': server,
            'username': username,
            'password': password
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
            self.conn.delete_object(
                self.conn.get_object('record:aaaa', {'name': self.record})[0]['_ref'])
        except TypeError:
            pass
        else:
            print "destroyed AAAA Record {}".format(self.record)

    def destroy_conditional(self):
        """ clean up host entries """
        host_entry = self.query_host()
        a_entry = self.query_a()
        aaaa_entry = self.query_aaaa()

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

    def rebuild(self):
        """ - destroy host record (always)
            - destroy A and AAA records only if they don't match
            - create new A and AAA records
        """

        self.destroy_conditional()
        a_entry = self.query_a()
        aaaa_entry = self.query_aaaa()

        if a_entry != 'already_there':
            try:
                objects.ARecord.create(self.conn, view='External',
                                       name=self.record, ip=self.ipv4)
            except Exception as err:
                print "couldn't create A Record for {} with IP {}: {}".format(
                    self.record, self.ipv4, err)
                byebye(1)
            else:
                print "created A Record {} with IP {}".format(
                    self.record, self.ipv4)
        else:
            print "A Record {} with IPv4 {} was already there".format(
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
                print "AAAA Record {} with IPv6 {} was already there".format(self.record, self.ipv6)

        print '='*80


if __name__ == '__main__':
    print '='*80
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    START_TIME = datetime.now()

    ARGS = parse()

    if not ARGS.destroy:
        if not ARGS.ipv4:
            print "  --ipv4 is mandatory when you create a new record"
            print "  You can use --help to check the options"
            os.sys.exit()
        else:
            ipv4 = ARGS.ipv4
    else:
        if not ARGS.ipv4:
            ipv4 = 'blah'

    PASSWD = getpass.getpass(prompt='Your Infoblox password: ')


    if ARGS.ipv6:
        if ARGS.destroy:
            Iblox(ARGS.username, PASSWD, ARGS.server, ARGS.host,
                  ipv4, ARGS.ipv6).destroy()
        else:
            Iblox(ARGS.username, PASSWD, ARGS.server, ARGS.host,
                  ipv4, ARGS.ipv6).rebuild()
    else:
        if ARGS.destroy:
            Iblox(ARGS.username, PASSWD, ARGS.server, ARGS.host, ipv4).destroy()
        else:
            Iblox(ARGS.username, PASSWD, ARGS.server, ARGS.host, ipv4).rebuild()

    SPENT = (datetime.now() - START_TIME).seconds
    print "======== Script processed in {} seconds ========\n".format(SPENT)
    byebye()
