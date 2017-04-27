#!/usr/bin/python
#
"""
  NOTE: THIS IS STILL BROKEN
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

# since the script is broken let's print a message and say good bye
print "this script is still not working"
os.sys.exit()

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


def parse():
    """ parse arguments """

    intro = """\
        With this script you can add/replace/destroy a CNAME record on Infoblox
        -----------------------------------------------------------------------
        Adding: iblox.py --host test-foo01.bar.com --txt "txt string here"
        Removing: iblox.py --txt foo.bar.com --destroy
        Hint: If you add a txt, you will implicitly replace any existing entry which is
              different from the one provided to the script
         """
    parser = argparse.ArgumentParser(
        formatter_class=lambda prog:
        argparse.RawDescriptionHelpFormatter(prog, max_help_position=29),
        description=textwrap.dedent(intro),
        epilog="Author: Massimiliano Adamo <massimiliano.adamo@geant.org>")

    parser.add_argument('--host', help='existing host name. Mandatory when creating a txt')
    parser.add_argument('--txt', help='txt to create. Mandatory', required=True)
    parser.add_argument('--destroy', help='destroy txt', action='store_true')

    return parser.parse_args()


class Iblox(object):
    """manage infoblox entries"""
    config = ConfigParser.RawConfigParser()

    def __init__(self, record, txt):
        self.record = record
        self.txt = txt
        self.config.readfp(open(IBLOX_CONF))
        self.opts = {
            'host': self.config.get('iblox', 'iblox_server'),
            'username': self.config.get('iblox', 'iblox_username'),
            'password': self.config.get('iblox', 'iblox_password')
            }
        self.conn = connector.Connector(self.opts)

    def query_txt(self):
        """ query for CNAME record: return None if it does not exist or
            if self.txt matches the existing one """
        try:
            txt_rec = self.conn.get_object('record:txt', {'name': self.txt})[0]
        except TypeError:
            return None
        else:
            if self.record == str(txt_rec['canonical']):
                return 'already_there'
            else:
                return txt_rec

    def destroy(self):
        """ clean up CNAME entry """
        try:
            self.conn.delete_object(self.conn.get_object(
                'record:cname', {'name': self.txt})[0]['_ref'])
        except TypeError:
            print "cound not find CNAME {}".format(self.txt)
        else:
            print "destroyed CNAME {}".format(self.txt)

    def destroy_conditional(self):
        """ clean up host entries """
        txt_entry = self.query_txt()
        if txt_entry and txt_entry != 'already_there':
            self.conn.delete_object(txt_entry['_ref'])
            print "destroyed CNAME record {}".format(self.txt_entry)
            return 'did something'
        elif txt_entry == 'already_there':
            return 'already_there'
        else:
            return None

    def rebuild(self):
        """ - destroy txt record (if it is not matching)
            - create a new txt record if there isn't one already
        """

        try_destroy = self.destroy_conditional()

        if try_destroy == 'already_there':
            print "A TXT {} associated to {} is already there".format(
                self.txt, self.record)
        else:
            try:
                objects.InfobloxObject.create(self.conn, view='External',
                                              name=self.record, text=self.txt)
            except Exception as err:
                print "couldn't create TXT record \"{}\" associated to {}: {}".format(
                    self.txt, self.record, err)
                os.sys.exit(1)
            else:
                print "created TXT record {} associated to {}".format(
                    self.txt, self.record)

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
        os.sys.exit(1)

    ARGS = parse()

    if not ARGS.destroy:
        if not ARGS.host:
            print " --host is mandatory when you create a new record"
            print " You can use --help to check the options"
            os.sys.exit()
        else:
            HOST = ARGS.host
    else:
        if not ARGS.host:
            HOST = 'blah'

    if ARGS.destroy:
        Iblox(HOST, ARGS.txt).destroy()
    else:
        Iblox(HOST, ARGS.txt).rebuild()

    os.sys.exit()
