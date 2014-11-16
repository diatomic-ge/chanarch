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
version = '0.2.x-beta'
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

class ChanThread(object):
    """
    This class implements a downloader for a 4chan thread.

    Attributes:
      board (str): Which 4chan board the thread is on
      downdir (str): Download directory for this thread
      jsonurl (str): URL of the thread's JSON
      linkfile (str): Name of the file to scrape links into
      thread_is_dead (bool): If true, thread 404'd
      threadinfo (dict): Parsed JSON as a dictionary
      usehttps (bool): If true, use HTTPS rather than HTTP
    """

    def __init__(self, thread, downdir, mksubdir=True, linkfile=None):
        """
        Initialize a ChanThread object.

        Set up a ChanThread object with its thread information, i.e. its board
        and threadnumber, both parsed from the string thread.

        Args:
          thread (str): A 4chan thread URL
          downdir (str): The directory to download files to
          mksubdir (bool): If true, download into downdir/[THREAD_NUMBER]
          linkfile (str): The file to scrape links into
        """

        self.board = None
        self.downdir = None
        self.jsonurl = None
        self.linkfile = None
        self.thread_is_dead = None
        self.threadinfo = None
        self.usehttps = None


        self.set_thread(thread, downdir, mksubdir=mksubdir, linkfile=linkfile)

    def set_thread(self, threadurl, downdir, mksubdir=True, linkfile=None):
        """
        (Re)set the thread info

        Given a 4chan thread URL and a download directory, parse and set the
        components of the thread URL, as well as the download directory.

        Args:
          threadurl (str): A 4chan thread URL
          downdir (str): The download directory
          mksubdir (bool): If true, download into downdir/[THREAD_NUMBER]
          linkfile (str): The file to scrape links into
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

        # Set link scrape location
        self.linkfile = linkfile

    def parse_url(self, threadurl):
        """
        Parse a 4chan thread URL.

        Given a string with a 4chan URL, return a tuple of whether or not HTTPS
        is used, and the board and thread number as strings.

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
                logging.debug('/%s/thread/%s 404\'d' %
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

        logging.debug('Downloading /%s/thread/%s to %s' %
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

    def scrape_links(self):
        """
        Scrapes all links from the thread and saves them.

        If a linkfile was supplied, read it, then use regular expressions to
        find any links in the thread. Sort and remove duplicates, before writing
        them back to the link file.
        """

        # Check if thread is 404'd
        if self.thread_is_dead:
            logging.debug('Not scraping dead thread')
            return

        links = []

        # Read existing links (if they exist)
        if os.path.exists(self.linkfile):
            linkfile = open(self.linkfile, 'r')
            # If the file is empty, linenum isn't assigned
            linenum = 0
            for linenum, line in enumerate(linkfile, start=1):
                links.append(line.rstrip())
            else:
                logging.debug('Read %d links from %s' % (linenum, self.linkfile))
            linkfile.close()

        # Scrape links from each post

        # WARN: Herein lies the realm of madness: finding URLs by regex.
        # We do this because 4chan's JSON doesn't put links into nice, parsable
        # <a> tags

        for post in self.threadinfo['posts']:
            # Iä! Iä! Cthulhu Fhtagn!
            # This regex matches all (?) legal http(s) and ftp URLs. Modify
            # carefully.
            urlregex = '(?:http[s]?|ftp)://(?:[A-Za-z0-9]|[-._~:\/?#\[\]@!\$&\'\(\)*+,;=]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'

            # Make sure there is a comment, before trying to scrape
            com = post.get('com')
            if com:
                # Strip any special tags, such as the word break tag, that might
                # appear in the middle of URLs.
                com = re.sub('<wbr(?:[ ]?/)?>', '', com)

                # Scrape the links
                postlinks = re.findall(urlregex, com)
                links.extend(postlinks)

        # Remove duplicates (sets only allow one of each, so convert to remove
        # duplicates
        links = list(set(links))

        # Sort and write
        links.sort()

        linkfile = open(self.linkfile, 'w')

        # If we don't write links, we linknum isn't assigned
        linknum = 0
        for linknum, link in enumerate(links, start=1):
            linkfile.write(''.join([link, '\n']))
        else:
            logging.debug('Wrote %d links into %s' % (linknum, self.linkfile))
        linkfile.close()

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

# Argument parsing
parser = argparse.ArgumentParser(description='Download the files of 4chan threads')
parser.add_argument('-f', '--file', help='list of threads in a file',
                    type=argparse.FileType('r'), action='append')
parser.add_argument('-d', '--directory',
                    help='download directory (defaults to .)', default='.')
parser.add_argument('-l', '--linkfile', help='file to scrape links into')
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
if args.file:
    for f in args.file:
        for thread in f:
            threads.append(ChanThread(thread.strip(), downdir,
                                      linkfile=args.linkfile))

# Read threads from the arguments
for thread in args.thread:
    threads.append(ChanThread(thread.strip(), downdir, linkfile=args.linkfile))

# Download each thread
for tnum, thread in enumerate(threads, start=1):
    # Get thread info
    thread.update_info()

    # Scrape links
    if args.linkfile:
        logging.info('Scraping links: %d/%d' % (tnum, len(threads)))
        thread.scrape_links()

    # Download files
    logging.info('Downloading thread: %d/%d' % (tnum, len(threads)))
    thread.download_files()

logging.info('Completed all downloads')
