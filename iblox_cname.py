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
        Adding: iblox.py --host test-foo01.bar.com --alias foo.bar.com
        Removing: iblox.py --alias foo.bar.com --destroy
        Hint: If you add an alias, you will implicitly replace any existing entry which is
              different from the one provided to the script
         """
    parser = argparse.ArgumentParser(
        formatter_class=lambda prog:
        argparse.RawDescriptionHelpFormatter(prog, max_help_position=29),
        description=textwrap.dedent(intro),
        epilog="Author: Massimiliano Adamo <massimiliano.adamo@geant.org>")

    parser.add_argument('--host', help='existing host name, mandatory when you create an alias', required=False)
    parser.add_argument('--alias', help='alias to create, mandatory', required=True)
    parser.add_argument('--destroy', help='destroy alias', action='store_true')

    return parser.parse_args()


def byebye(status=0):
    """ say good bye """
    os.sys.exit(status)


class Iblox(object):
    """manage infoblox entries"""
    config = ConfigParser.RawConfigParser()

    def __init__(self, record, alias):
        self.record = record
        self.cname = cname
        self.config.readfp(open(IBLOX_CONF))
        self.opts = {
            'host': self.config.get('iblox', 'iblox_server'),
            'username': self.config.get('iblox', 'iblox_username'),
            'password': self.config.get('iblox', 'iblox_password')
            }
        self.conn = connector.Connector(self.opts)

    def query_alias(self):
        """ query for CNAME record: return None if it does not exist or
            if self.ipv4 matches the existing one """
        try:
            cname_rec = self.conn.get_object('record:cname', {'name': self.alias})[0]
        except TypeError:
            return None
        else:
            if self.record == str(cname_rec['canonical']):
                return 'already_there'
            else:
                return cname_rec

    def destroy_conditional(self):
        """ clean up host entries """
        cname_entry = self.query_alias()
        if cname_entry and cname_entry != 'already_there':
            self.conn.delete_object(cname_entry['_ref'])
            print "destroyed CNAME record {}".format(self.alias)
            return 'did something'
        elif cname_entry == 'already_there':
            return 'already_there'
        else:
            return None

    def rebuild(self):
        """ - destroy alias record (if it is not matchinh)
            - create a new alias record if there isn't one already
        """

        try_destroy = self.destroy_conditional()

        if try_destroy and try_destroy != 'already_there':
            try:
                # create alias
                objects.ARecord.create(self.conn, view='External',
                                       name=self.record, ip=self.ipv4)
            except Exception as err:
                print "couldn't create CNAME {} to Record {}: {}".format(
                    self.alias, self.record, err)
                byebye(1)
            else:
                print "created A Record {} with IP {}".format(
                    self.record, self.ipv4)
        else:
            print "A Record {} with IPv4 {} was already there".format(
                self.record, self.ipv4)

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
        if not ARGS.host:
            print "  --host is mandatory when you create a new record"
            print "  You can use --help to check the options"
            os.sys.exit()
        else:
            HOST = ARGS.host
    else:
        if not ARGS.ipv4:
            IPV4 = 'blah'

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
