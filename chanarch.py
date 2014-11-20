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
import ssl
import sys
import textwrap
import time

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
    from httplib import HTTPConnection, HTTPSConnection
else:
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
      jserver (str): The server hosting the thread JSON
      jsonpath (str): The path to the thread's JSON on jserver
      linkfile (str): Name of the file to scrape links into
      thread_is_dead (bool): If true, thread 404'd
      threadid (str): The thread number as a string
      threadinfo (dict): Parsed JSON as a dictionary
      timeout (int): Timeout value for connections
      usehttps (bool): If true, use HTTPS rather than HTTP
    """

    def __init__(self, thread, downdir, mksubdir=True, linkfile=None,
                 timeout=None):
        """
        Initialize a ChanThread object.

        Set up a ChanThread object with its thread information, i.e. its board
        and threadnumber, both parsed from the string thread.

        Raise InvalidURLError if threadurl is not a valid 4chan thread URL

        Args:
          thread (str): A 4chan thread URL
          downdir (str): The directory to download files to
          mksubdir (bool): If true, download into downdir/[THREAD_NUMBER]
          linkfile (str): The file to scrape links into
          timeout (int): Timeout value for connections
        """

        self.board = None
        self.downdir = None
        self.jserver = None
        self.jsonpath = None
        self.linkfile = None
        self.thread_is_dead = None
        self.threadinfo = None
        self.timeout = timeout
        self.usehttps = None

        self.set_thread(thread, downdir, mksubdir=mksubdir, linkfile=linkfile)

    def get_threadid(self):
        """
        Return a thread identifier.

        Return a tuple (board, threadnumber) which identifies that 4chan thread
        uniquely. This can be used to remove duplicate threads, or index them in
        a dictionary.

        Returns:
          tuple(board, threadnumber):
            board (str): The name of the 4chan board
            threadnumber (str): The thread number
        """

        return (self.board, self.threadid)          

    def set_thread(self, threadurl, downdir, mksubdir=True, linkfile=None):
        """
        (Re)set the thread info

        Given a 4chan thread URL and a download directory, parse and set the
        components of the thread URL, as well as the download directory.

        Raise InvalidURLError if threadurl is not a valid 4chan thread URL

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

        # Build JSON URL parts
        self.jserver = 'a.4cdn.org'
        self.jsonpath = ''.join(['/', self.board, '/thread/', self.threadid,
                                 '.json'])

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

        # Establish proper type of connection
        if self.usehttps:
            conntype = HTTPSConnection
        else:
            conntype = HTTPConnection

        if self.timeout:
            conn = conntype(self.jserver, timeout=self.timeout)
        else:
            conn = conntype(self.jserver, timeout=self.timeout)

        # Request the JSON
        conn.request('GET', self.jsonpath)
        resp = conn.getresponse()

        # Catch 404s
        if resp.status == 404:
            logging.debug('/%s/thread/%s 404\'d' % (self.board, self.threadid))
            self.thread_is_dead = True
            conn.close()
            return

        # Read and close the connection
        jsontxt = resp.read()
        conn.close()

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

        down = Downloader(imgserver, self.usehttps, timeout=self.timeout)

        # Loop over each post
        for post in self.threadinfo['posts']:
            tim = post.get('tim')
            ext = post.get('ext')
            filedeleted = post.get('filedeleted')

            # If there's a file in this post, download it
            if (ext is not None) and (filedeleted != 1):
                # Build the download location
                filename = ''.join([str(tim), ext])
                filepath = os.path.join(self.downdir, filename)
                url = ''.join(['/', self.board, '/', filename])

                # Download the file
                down.download(url, filepath)

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
      timeout (int): Timeout value for connections (seconds)
      usehttps (bool): Whether to use HTTPS instead of HTTP
    """

    def __init__(self, server, usehttps, timeout=None):
        """
        Initialize the downloader

        Set the downloader URL and filepath

        Args:
          server (str): The server to connect to
          usehttps (bool): Whether to use HTTPS instead of HTTP
          timeout (int): Timeout value for connections (seconds)
        """

        self.conn = None
        self.server = None
        self.timeout = timeout
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

        # Set connection parameters
        if usehttps:
            conntype = HTTPSConnection
        else:
            conntype = HTTPConnection

        if self.timeout:
            self.conn = conntype(server, timeout=self.timeout)
        else:
            self.conn = conntype(server)

    def close(self):
        """
        Close active connection, if open
        """

        if self.conn:
            self.conn.close()

        self.conn = None

    def download(self, servpath, filepath):
        """
        Download a file from the server

        Download servpath to filepath, opening a connection if one isn't
        already open, otherwise reuse the current one. If the file exists,
        resume downloading, otherwise start downloading.

        Args:
          servpath (str): The path to the file on the server
          filepath (str): The path to download the file as
        """

        # Create the download directory if it doesn't exist already
        outdir = os.path.dirname(filepath)
        if not os.path.exists(outdir):
            logging.debug('Creating directory: %s' % (outdir))
            os.makedirs(outdir)

        # Open the file and get the current position
        outfile = open(filepath, 'ab')

        # Get the file size from the server
        self.conn.request('HEAD', servpath,
                          headers = {'Connection': 'keep-alive'})
        resp = self.conn.getresponse()
        filesize = int(resp.getheader('Content-Length'))

        # Make sure to read the response, or else httplib will error
        resp.read()

        # Check if the file is already downloaded (if total size is known)
        if outfile.tell() == filesize:
            # Download already completed
            logging.debug('File already downloaded')
            return
        if outfile.tell() > filesize:
            # Our downloaded file is larger than the reported size
            logging.warn('File \'%s\' is larger than the server copy!'
                         'Truncating...' % (filepath))
            # Seek to the beginning of the file and truncate
            outfile.seek(0)
            outfile.truncate()

        logging.debug('Downloading %s to %s, starting at byte %d' %
                      (servpath, filepath, outfile.tell()))

        # Download the file
        while outfile.tell() < filesize:
            try:
                # Request the file
                self.conn.request('GET', servpath, headers =
                                  {'Connection': ' keep-alive',
                                   'Range': ' bytes=%d-' %
                                            (outfile.tell())})

                resp = self.conn.getresponse()

                # Download the file incrementally (it's more resumable)
                block_sz = 16384


                # Download/write loop
                while True:
                    buff = resp.read(block_sz)

                    # Check if we're done downloading
                    if not buff:
                        break

                    # Write
                    outfile.write(buff)

            except ssl.SSLError as err:
                # If the SSL connection timed out, notify and continue
                if err.args[0] == 'The read operation timed out':
                    logging.debug('Connection timed out. Retrying.')
                else:
                    raise

        logging.debug('File download completed')

        # Close the file
        outfile.close()

# Only run if called as a script
if __name__ == '__main__':

    # Argument parsing
    parser = argparse.ArgumentParser(description='Download the files of 4chan'
                                     'threads')

    # Download options
    parser.add_argument('-f', '--file', help='list of threads in a file',
                        type=argparse.FileType('r'), action='append')
    parser.add_argument('-d', '--directory',
                        help='download directory (defaults to .)', default='.')
    parser.add_argument('-l', '--linkfile', help='file to scrape links into')
    parser.add_argument('thread', help='thread URLs', nargs='*')

    # Behavior options
    parser.add_argument('--timeout', type=int, default=15,
                        help='Connection timeout in seconds')

    # Verbosity
    g = parser.add_mutually_exclusive_group()
    g.add_argument('-q', '--quiet', help='be quiet', action='store_true')
    g.add_argument('-v', '--verbose', help='increase verbosity',
                   action='store_true')
    g.add_argument('--debug', help='debug-level verbosity',
                   action='store_true')

    # Actions
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

    # Build thread dictionary
    threads = {}

    # Read the file(s)
    try:
        if args.file:
            for f in args.file:
                for thread in f:
                    t = ChanThread(thread.strip(), downdir,
                                   linkfile=args.linkfile,
                                   timeout=args.timeout)

                    # Check if thread is already present before adding
                    tid = t.get_threadid()
                    if not tid in threads:
                        threads[tid] = t
                    else:
                        logging.debug('Duplicate thread: \'/%s/thread/%s\'' %
                                      (tid[0], tid[1]))

        # Read threads from the arguments
        for thread in args.thread:
            t = ChanThread(thread.strip(), downdir,
                       linkfile=args.linkfile,
                       timeout=args.timeout)

            # Check if thread is already present before adding
            tid = t.get_threadid()
            if not tid in threads:
                threads[tid] = t
            else:
                logging.debug('Duplicate thread: \'/%s/thread/%s\'' %
                              (tid[0], tid[1]))

    except (InvalidURLError) as err:
        sys.exit('Invalid URL: \'%s\', expected %s' %
                 (err.url, err.urldesc))

    # Download each thread
    starttime = time.time()

    for tnum, threadid in enumerate(threads, start=1):
        thread = threads[threadid]

        # Get thread info
        thread.update_info()

        # Scrape links
        if args.linkfile:
            logging.info('Scraping links: %d/%d' % (tnum, len(threads)))
            thread.scrape_links()

        # Download files
        logging.info('Downloading thread: %d/%d' % (tnum, len(threads)))
        thread.download_files()

    logging.info('Completed all downloads in %ds' % (time.time() - starttime))
