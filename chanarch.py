#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2014 diatomic.ge
#
# This file is part of chanarch.
#
# Chanarch is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of that License, or
# (at your option) any later version.
#
# Chanarch is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with chanarch. If not, see <http://www.gnu.org/licenses/>

# Compatibility
from __future__ import division, print_function, unicode_literals

import argparse
import json
import logging
import os.path
import re
import sys
import textwrap

# Program information
progname = 'Chanarch'
version = '0.1.1'
version_string = ''.join([progname, ' ', version])
copyright = 'Copyright (C) 2014 diatomic.ge'
licensenotice = textwrap.dedent('''\
    License GPLv3+: GNU GPL version 3 or later <http://gnu.org/licenses/gpl.html>
    This is free software: you are free to change and redistribute it.
    There is NO WARRANTY, to the extent permitted by law.''')

# Python 3 renamed modules
if sys.version_info.major == 2:
    from urllib2 import Request, urlopen, HTTPError
    from httplib import HTTPConnection, HTTPSConnection
else:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    from http.client import HTTPConnection, HTTPSConnection

class InvalidURLError(ValueError):
    """
    This exception is raised for invalid URLs

    Attributes:
      url (str): The invalid URL
      urldesc (str): A description of the expected valid URL, or None
    """

    def __init__(self, url, urldesc=None):
        """
        Initialize the invalid URL exception

        Arguments:
          url (str): The invalid URL
          urldesc (str): A description of the expected valid URL
        """

        # Save values
        self.url = url
        self.urldesc = urldesc

        # Initialize exception stuff
        if urldesc:
            ValueError.__init__(self, 'Invalid URL: \'%s\', expected %s' %
                                (url, urldesc))
        else:
            ValueError.__init__(self, 'Invalid URL: \'%s\'' % url)

class ChanThread(object):
    """
    This class implements a downloader for a 4chan thread.

    Attributes:
      board (str): Which 4chan board the thread is on
      downdir (str): Download directory for this thread
      jsonurl (str): URL of the thread's JSON
      thread_is_dead (bool): If true, thread 404'd
      threadinfo (dict): Parsed JSON as a dictionary
      usehttps (bool): If true, use HTTPS rather than HTTP
    """

    def __init__(self, thread, downdir, mksubdir=True):
        """
        Initialize a ChanThread object.

        Set up a ChanThread object with its thread information, i.e. its board
        and threadnumber, both parsed from the string thread.

        Raise InvalidURLError if threadurl is not a valid 4chan thread URL

        Args:
          thread (str): A 4chan thread URL
          downdir (str): The directory to download files to
          mksubdir (bool): If true, download into downdir/[THREAD_NUMBER]
        """

        self.board = None
        self.downdir = None
        self.jsonurl = None
        self.thread_is_dead = None
        self.threadinfo = None
        self.usehttps = None

        self.set_thread(thread, downdir, mksubdir)

    def set_thread(self, threadurl, downdir, mksubdir=True):
        """
        (Re)set the thread info

        Given a 4chan thread URL and a download directory, parse and set the
        components of the thread URL, as well as the download directory.

        Raise InvalidURLError if threadurl is not a valid 4chan thread URL

        Args:
          threadurl (str): A 4chan thread URL
          downdir (str): The download directory
          mksubdir (bool): If true, download into downdir/[THREAD_NUMBER]
        """

        # Parse thread URL
        threadinfo = self.parse_url(threadurl)

        self.usehttps = threadinfo[0]
        self.board = threadinfo[1]
        self.threadid = threadinfo[2]

        # Build JSON URL
        if self.usehttps == True:
            jserver = 'https://a.4cdn.org/'
        else:
            jserver = 'http://a.4cdn.org/'

        boardurl = ''.join([jserver, self.board])
        self.jsonurl = ''.join([boardurl, '/thread/', self.threadid, '.json'])

        # Set download directory
        downdir = os.path.expanduser(downdir)

        if mksubdir:
            downdir = os.path.join(downdir, self.threadid)

        self.downdir = downdir

    def parse_url(self, threadurl):
        """
        Parse a 4chan thread URL.

        Given a string with a 4chan URL, return a tuple of whether or not HTTPS
        is used, and the board and thread number as strings.

        Raise InvalidURLError if threadurl is not a valid 4chan thread URL

        Args:
          threadurl (str): A 4chan thread URL

        Returns:
          tuple(usehttps, board, threadnum):
            usehttps (bool): If true, https was specified, else http
            board (str): The board
            threadnum (str): The thread number
        """

        # URL regular expression
        urlregex = 'http(s?)://boards\.4chan\.org/([^/]+)/thread/([0-9]+)'

        # Parse the URL with a regex
        m = re.search(urlregex, threadurl)

        # Check for invalid URL
        if m is None:
            raise InvalidURLError(threadurl, '4chan thread URL')

        # Get the components
        if m.group(1) == 's':
            usehttps = True
        else:
            usehttps = False

        board = m.group(2)
        threadnum = m.group(3)

        return (usehttps, board, threadnum)

    def update_info(self):
        """
        Update the thread info

        Reconnects to the 4chan server to retrieve and parse the thread JSON
        """

        logging.debug('Downloading /%s/thread/%s JSON' %
                      (self.board, self.threadid))

        # Download the JSON
        req = Request(self.jsonurl)

        # Catch 404s
        try:
            resp = urlopen(req)
        except HTTPError as err:
            if err.getcode() == 404:
                logging.info('/%s/thread/%s 404\'d' %
                             (self.board, self.threadid))
                self.thread_is_dead = True
                return
            else:
                raise

        jsontxt = resp.read()

        # Decode the JSON
        self.threadinfo = json.loads(jsontxt.decode())

    def download_files(self):
        """
        Download all files in the thread.

        Parse out the file names in the JSON, and download all files to downdir
        """

        # Check if thread is 404'd
        if self.thread_is_dead:
            logging.info('Skipping dead thread: /%s/thread/%s' %
                         (self.board, self.threadid))
            return

        logging.info('Downloading /%s/thread/%s to %s' %
                     (self.board, self.threadid, self.downdir))

        # Check if we're using HTTPS or HTTP for the server
        imgserver = 'i.4cdn.org'

        down = Downloader(imgserver, self.usehttps)

        # Loop over each post
        for post in self.threadinfo['posts']:
            tim = post.get('tim')
            ext = post.get('ext')
            filedeleted = post.get('filedeleted')
            filesz = post.get('fsize')

            # If there's a file in this post, download it
            if (ext is not None) and (filedeleted != 1):
                # Build the download location
                filename = ''.join([str(tim), ext])
                filepath = os.path.join(self.downdir, filename)
                url = ''.join(['/', self.board, '/', filename])

                # Download the file
                down.download(url, filepath, totsz=filesz)

        # Close the connection
        down.close()

class Downloader(object):
    """
    Implements resumable downloading and connection reuse for HTTP(S)

    Attributes:
      conn (HTTP(S)Connection): The current connection
      server (str): The server to connnect to
      usehttps (bool): Whether to use HTTPS instead of HTTP
    """

    def __init__(self, server, usehttps):
        """
        Initialize the downloader

        Set the downloader URL and filepath

        Args:
          server (str): The server to connect to
          usehttps (bool): Whether to use HTTPS instead of HTTP
        """

        self.conn = None
        self.server = None
        self.usehttps = None
        self.set_server(server, usehttps)

    def __del__(self):
        """
        Destroy the downloader

        Close the connection
        """

        self.close()

    def set_server(self, server, usehttps):
        """
        (Re)set the server info

        Set the server address and HTTP/HTTPS selection, closing any active
        connection

        Args:
          server (str): The server to connect to
          usehttps (bool): Whether to use HTTPS instead of HTTP
        """

        self.close()
        self.server = server
        self.usehttps = usehttps

    def close(self):
        """
        Close active connection, if open
        """

        if self.conn:
            self.conn.close()

        self.conn = None

    def download(self, servpath, filepath, totsz=None):
        """
        Download a file from the server

        Download servpath to filepath, opening a connection if one isn't
        already open, otherwise reuse the current one. If the file exists,
        resume downloading, otherwise start downloading.

        Args:
          servpath (str): The path to the file on the server
          filepath (str): The path to download the file as
          totsz (int): The total size of the file, if known
        """

        # Create the download directory if it doesn't exist already
        outdir = os.path.dirname(filepath)
        if not os.path.exists(outdir):
            logging.debug('Creating directory: %s' % (outdir))
            os.makedirs(outdir)

        # Open the file and get the current position
        outfile = open(filepath, 'ab')
        filepos = os.path.getsize(filepath)

        # Check if the file is already downloaded (if total size is known)
        if totsz:
            if filepos == totsz:
                # Download already completed
                logging.debug('Requested length already downloaded')
                return

        # Open a connection
        if (self.conn is None):
            if self.usehttps:
                self.conn = HTTPSConnection(self.server)
            else:
                self.conn = HTTPConnection(self.server)
        else:
            logging.debug('Reusing existing connection to %s' % (self.server))

        self.conn.request('GET', servpath, headers =
                          {'Connection': ' keep-alive',
                           'Range': ' bytes=%d-' % (filepos)})

        resp = self.conn.getresponse()

        # If we got code 416, the file's already downloaded completely
        # Read whatever might be left and return
        if resp.status == 416:
            logging.debug('File already downloaded')
            resp.read()
            return

        # Download the file incrementally (it's more resumable)
        block_sz = 16384

        logging.debug('Downloading %s to %s, starting at byte %d' %
                      (servpath, filepath, filepos))

        # Download/write loop
        while True:
            buff = resp.read(block_sz)

            # Check if we're done downloading
            if not buff:
                break

            # Write
            outfile.write(buff)

        logging.debug('File download completed')

        # Close the file
        outfile.close()

# Only run if called as a script
if __name__ == '__main__':

    # Argument parsing
    parser = argparse.ArgumentParser(description='Download the files of 4chan'
                                     'threads')
    parser.add_argument('-f', '--file', help='list of threads in a file',
                        type=argparse.FileType('r'), action='append')
    parser.add_argument('-d', '--directory',
                        help='download directory (defaults to .)', default='.')
    parser.add_argument('thread', help='thread URLs', nargs='*')

    g = parser.add_mutually_exclusive_group()
    g.add_argument('-q', '--quiet', help='be quiet', action='store_true')
    g.add_argument('-v', '--verbose', help='increase verbosity',
                   action='store_true')
    g.add_argument('--debug', help='debug-level verbosity',
                   action='store_true')

    parser.add_argument('-V', '--version', help='print version and exit',
                        action='store_true')

    args = parser.parse_args()

    # Version printing
    if args.version:
        # Print version, copyright, and license notice and exit
        print(version_string)
        print(copyright)
        print(licensenotice)
        sys.exit()

    # If we didn't read any 'actions' or threads, print help
    if (not args.file) and (not args.thread):
        parser.print_help()
        sys.exit()

    # Logging mode, go!
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    elif args.verbose:
        logging.basicConfig(level=logging.INFO)
    elif args.quiet:
        logging.basicConfig(level=logging.ERROR)
    else:
        logging.basicConfig(level=logging.WARN)

    # Read the download directory
    downdir = args.directory

    # Build thread list
    threads = []

    # Read the file(s)
    try:
        if args.file:
            for f in args.file:
                for thread in f:
                    threads.append(ChanThread(thread.strip(), downdir))

        # Read threads from the arguments
        for thread in args.thread:
            threads.append(ChanThread(thread.strip(), downdir))

    except (InvalidURLError) as err:
        sys.exit('Invalid URL: \'%s\', expected %s' %
                 (err.url, err.urldesc))

    # Download each thread
    for thread in threads:
        thread.update_info()
        thread.download_files()

    logging.info('Completed all downloads')
