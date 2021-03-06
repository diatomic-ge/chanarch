========
Chanarch
========

Chanarch is a program for downloading the files from 4chan threads.

See the file ``ChangeLog.rst`` for a user-friendly list of changes, or run ``git log`` in
a git clone of the chanarch repository for a more developer-friendly list of
changes.

See the file ``AUTHORS.rst`` for a list of contributers.

See the file ``LICENSE`` for the license (GPLv3)

Note that chanarch is beta-quality software at best, and is still under
development. Keep in mind some options and arguments are still subject to
change. Please report bugs or suggest features on `chanarch's GitHub
<https://github.com/diatomic-ge/chanarch>`_

Features
--------

- Thread file downloading

- File download resuming

- Server connection reusage (greatly speeds multiple file downloads)

Usage
-----

Chanarch allows several methods of specifying threads to download.

In order to download a single 4chan thread, run:

  ``./chanarch.py URL``

URL should be something like:

  ``http(s)://boards.4chan.org/[BOARD]/thread/[THREAD_NUMBER]``

Essentially, the URLs are just the same URL you would find a 4chan thread at in
a web browser.

This will download all of the files from this thread into a subdirectory of the
current directory, based on the thread number.

If you want to download multiple 4chan threads, run:

  ``./chanarch.py URL URL ...``

Each thread will be downloaded into its own subdirectory.

If you want to download to another directory, instead of the current directory,
run:

  ``./chanarch.py -d DIRECTORY URL ...``

This will create the subdirectories in ``DIRECTORY``.

Chanarch can also read a list of threads from files. In order to do this, create
a file, or multiple files, with one URL per line. For instance:

  ``./chanarch.py -f FILE``

This will read URLs from ``FILE``, one per line.

Multiple types of arguments can be used simultaneously, such as:

  ``./chanarch.py -f FILE1 -f FILE2 -d DIRECTORY URL1 URL2``

In order to get a full list of arguments, as well as their corresponding
long-argument versions, run:

  ``./chanarch.py --help``

For instance, it may be helpful to add the ``-v`` or ``--verbose`` flag to be
assured that threads are being downloaded.

In most shells, you can also run something similar to:

  ``while true; do ./chanarch.py -d DIR -f FILE; sleep 5m; done``

This will repeatedly download threads, waiting for 5 minutes in between.
Essentially, this is an ad-hoc thread watcher.

Requirements
------------

Chanarch requires Python. It was written with both Python 2 and Python 3 in
mind, and should work equally on any recent version of Python, though Python
versions before 2.7 are not currently tested.

Downloading
-----------

The latest versioned releases of chanarch can be obtained from its `GitHub
release page <https://github.com/diatomic-ge/chanarch/releases>`_

The latest development version of Chanarch can be obtained from its `GitHub
page <https://github.com/diatomic-ge/chanarch>`_ or directly cloned with:

  ``git clone https://github.com/diatomic-ge/chanarch.git``

The master branch will always point to the latest stable version, if one exists.
Other branches may contain more up-to-date, but unstable, versions.

Copyright
---------

Copyright (C) 2014 diatomic.ge

This file is part of chanarch.

Chanarch is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of that License, or
(at your option) any later version.

Chanarch is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with chanarch. If not, see <http://www.gnu.org/licenses/>
