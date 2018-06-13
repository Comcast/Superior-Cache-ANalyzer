SCAN
====

| |License|
| |Build Status|

Superior Cache ANalyzer

F.A.Q
-----

-  Q: *Scan says it can't find my cache file, but I know it's there.
   What do?*

   A: Sometimes, ATS installs point to cache files that are installed
   *relative to the ATS root directory*. This is pretty common in test
   setups right after a basic install. There's not really any way for
   SCAN to 'detect' when this is happening (though it will try), so the
   best solution is often just to try running ``scan`` *from that ATS
   root directory*. For example, if you have a directory
   ``/opt/trafficserver`` that holds all of the trafficserver files, try
   going to that directory before running ``scan``.

-  Q: *Scan is giving me an error, and I don't know what it means/how to
   fix it. How fix?*

   A: Congratulations, you've just been drafted! Try running scan like
   this:
   ``scan --debug <other options that you specified last time> 2>scan.err``
   (you may not see the error message this time) and then create a
   `github
   issue <https://github.com/comcast/Superior-Cache-ANalyzer/issues/new>`__
   and upload/pastebin/^C^V the scan.err file that should've been
   created and link/paste it into the box, along with a description of
   what you were trying to do and what went wrong. I'll fix it as soon
   as I can.

-  Q: *Why can't Scan see the thing that I KNOW is in the cache?*

   A: It's possible that you ``scan``\ ed for 'thing' before it was
   written. The Apache Traffic ServerTM will only sync directories every
   60 seconds by default (effectively, this means ``scan`` can only see
   cache changes at that frequency). You could either wait a bit, or set
   the ATS configuration parameter
   ``proxy.config.cache.dir.sync_frequency`` to a lower value (in
   seconds). If that doesn't work, check out the above question.

User Guide
----------

SCAN's primary use is as a library for inspecting Apache Traffic
ServerTM (ATS) caches. SCAN also provides a command-line utility
(``scan``), which is described here.

Installation
~~~~~~~~~~~~

Prerequisites
^^^^^^^^^^^^^

``scan`` requires the following dependencies:

-  ``numpy`` - A highly-performant library for working with vectorized
   functions on huge data structures (used for reading/manipulating
   cache directories) `link <https://pypi.org/project/numpy/>`__.
-  ``psutil`` - A cross-platform process and system interface library
   (used for ionice setting)
   `link <https://pypi.org/project/psutil/>`__.
-  ``setuptools`` - "Easily download, build, install, upgrade, and
   uninstall Python packages"
   `link <https://pypi.org/project/setuptools/>`__.
-  ``typing`` - Provides a backport of type-hinting for old versions of
   Python (< v3.5) `link <https://pypi.org/project/typing/>`__.

If you have Python version 3.5 or greater, you already have ``typing``.
If you have ``pip3`` (for any Python version > 3.4.0), you likely
already have ``setuptools``. To install a dependency "``DEP``" on Python
versions < 3.5, simply run ``sudo -H pip3 install DEP``. If you don't
have ``pip3``, then to install either dependency on CentOS/Fedora/RHEL
distros, do ``sudo yum install -y python34-DEP``, on Ubuntu/Mint/Debian
distros do ``sudo apt-get install python3-DEP``, and on
Arch/Manjaro/Gentoo(?) do ``sudo pacman -S python3-DEP``. If you need
the dependencies and you're on MacOS/BSD/Windows, then gods help you - I
can't.

Installing 'scan'
^^^^^^^^^^^^^^^^^

Via ``pip``
'''''''''''

    By far the easiest way to install SCAN is to simply use ``pip`` like
    so:

::

    pip install Superior-Cache-ANalyzer

    Note that you'll probably need to run that command as an
    administrator (Windows), with ``sudo`` (Everything Else), or with
    the ``--user`` option (Everything Including Windows)

From a Release
''''''''''''''

    On the `Releases
    page <https://github.com/Comcast/Superior-Cache-ANalyzer/releases>`__
    you can download the wheel (the ``.whl`` file) and install that
    manually with

.. code:: bash

    sudo -H python3 -m pip install -y /path/to/Superior-Cache-ANalyzer.<version stuff>.whl

    Note that this may require you to upgrade/install the ``pip``
    module, so if you get an error like ``No module named 'pip'`` try
    installing the ``python3-pip`` package (``python34-pip`` on
    RedHat/CentOS/Fedora) or running ``sudo -H python3 -m ensurepip``.
    Other errors could possibly be fixed by running
    ``sudo -H python3 -m pip install -yU pip`` and then trying the
    install again. If all else fails, then you can probably install from
    source.

From Source
'''''''''''

    To install from source, you'll first want to download the source
    from `the Comcast
    Github <https://github.com/Comcast/Superior-Cache-ANalyzer.git>`__.
    Once you've done that, go to the downloaded folder and run

.. code:: bash

    sudo -H pip3 install .

    ... or, if you don't have ``pip3``:

.. code:: bash

    sudo python3 setup.py install

    | Note that SCAN is only guaranteed to work for Python versions
      3.4.1 and greater.
    | If you want to run the tests see 'Tests' below.

Usage
~~~~~

The basic usage of ``scan`` is pretty simple at the moment; to start the
utility simply run:

.. code:: bash

    scan [ --debug ] [ -f --fips ] [ -d --dump [ SPAN ] ] [ -c --config-dir DIR ]
    scan [ --debug ] [ -f --fips ] [ -D --dump-breakdown [ SPAN ] ] [ -c --config-dir DIR ]

where the options have the following meanings:

-  ``-c`` or ``--config-dir`` ``DIR``

   This option allows you to directly specify the config dir of your ATS
   install. This allows you to skip the prompt when ``scan`` first
   starts where you must input your configuration directory. In
   non-interactive mode (``-d``/``--dump`` given), this option must be
   used if ATS is not installed under ``/opt/trafficserver``.

-  ``--debug``

   When provided, this flag causes ``scan`` to output some verbose
   debugging information and exception stack traces. It also causes it
   to be run *without optimization*, which - depending on your Python
   interpreter - can have a serious impact on performance.

-  ``-d`` or ``--dump`` ``[SPAN]``

   Dumps the contents of the cache in Tabular YAML format to ``stdout``,
   then exits. This will cause any ``-D``/``--dupm-breakdown`` flags
   given to be ignored. If specified, ``SPAN`` should be the path to a
   cache span to dump as specified in ``storage.config`` e.g.
   ``/dev/sdk``. WARNING: As of the time of this writing, ``scan``'s
   "ionice" value is being set to the lowest possible value on startup,
   which means that this operation could take several hours to complete
   if you do not specify a single span. Currently, if you do not use the
   ``-l`` or ``--loadavg`` option, it takes about 400-500 seconds to
   dump a 1TB hard disk cache and about 3-7 seconds to dump an 8GB RAM
   cache. Use of this option with ``-l`` or ``--loadavg`` is not
   recommended at this time, as it will radically increase the time it
   takes to complete.

-  ``-D`` or ``--dump-breakdown`` ``[SPAN]``

   Dumps the usage of the cache to ``stdout`` in Tabular YAML format,
   broken down by host, then exits. If ``-d``/``--dump`` was given on
   the command line, this flag will be ignored if present. If specified,
   ``SPAN`` should be the path to a cache span to dump as specified in
   ``storage.config`` e.g. ``/dev/sdk``. WARNING: As of the time of this
   writing, ``scan``'s "ionice" value is being set to the lowest
   possible value on startup, which means that this operation could take
   several hours to complete if you do not specify a single span.
   Currently, if you do not use the ``-l`` or ``--loadavg`` option, it
   takes about 400-500 seconds to dump a 1TB hard disk cache and about
   3-7 seconds to dump an 8GB RAM cache. Use of this option with ``-l``
   or ``--loadavg`` is not recommended at this time, as it will
   radically increase the time it takes to complete.

-  ``-f`` or ``--fips``

   You **must** use this option if the ATS running on your system was
   compiled with ``ENABLE_FIPS`` enabled. If you don't, everything will
   be messed up. Actually, some things will still be messed up even if
   you do.

-  ``-l`` or ``--loadavg`` ``LOADAVG``

   This flag allows the specification of a maximum system load average
   to be respected by the program. This is expected to be a
   comma-separated list of floating-point numbers (see
   ```man uptime`` <https://linux.die.net/man/1/uptime>`__). For
   example: ``scan -l "25.0, 25.0, 25.0"`` ensures that no more than 25
   processes will be waiting for CPU time or disk I/O on average ever 1,
   5 or 15 minutes. Note that this option assumes that the system's
   loadavg at the time ``scan`` starts is representative of the system's
   loadavg for the entirety of its execution; if you start a very long
   scan job on e.g. a 1TB span, and then decide to play Crisis 1 on
   Medium settings using integrated graphics, your system may very well
   exceed a specified maximum loadavg, through no fault of ``scan``
   itself. Note that if your system is already at or above the
   ``LOADAVG`` specified, ``scan`` will immediately exit as it cannot
   possibly run. (Implementation note: effectively this controls the
   number of sub-processes that can be used to scan a stripe at once,
   since each sub-process is potentially another process that will wait
   for CPU time or Disk I/O.) Note that this is only available on
   POSIX-compliant systems. Usage of this flag alongside ``-d`` or
   ``--dump`` is discouraged.

-  ``-V`` or ``--version``

   Prints the version information and exits. This will print both
   ``scan``'s version and then on the next line the version and
   implementation of the Python interpreter used to run it. This second
   line would - for example - usually look like the follow on CentOS7.x
   systems: ``Running on CPython v3.4.5``.

Once the utility is started (provided the ``-d``/``--dump`` or
``-c``/``--config`` flags are not given) you'll be faced with a pretty
basic prompt. At first, your only option will be
``[1] Read Storage Config``. After you select this option, you'll be
prompted to enter the location of your ATS configuration files.
"Tab-completion" is supported for most interactive prompts, including
the ATS configuration file prompt. SCAN will expect all of them to be in
the same directory, and will guess that they are in
``/opt/trafficserver/etc/trafficserver/`` by default. **Note that the
use of FIPS at compilation time cannot be determined from the config
files, and MUST be given on the command line.** Once the configuration
has been read, all menu options will be unlocked. They are as follows:

``[1] Show Cache Setup``
^^^^^^^^^^^^^^^^^^^^^^^^

This option will print out the spans and volumes declared in the
configuration. Output will look like:

::

    Cache files:
    /path/to/a/span Span of <n> stripes XXX.XB

    Volumes:
    #1  <type>  XXX.XB

where ``<n>`` is the number of stripes in the span on that line, and
XXX.XB is the size of a span/volume (but it will be displayed in
human-readable approximations in units of B, kB, MB, or GB as
appropriate). Volumes defined as a percent of total storage will have
their size calculated at runtime, and displayed in absolute terms.
``<type>`` will be the type of volume declared. In nearly all cases,
this will be ``http``, but certain plugins could define other volume
types. Finally, it should be noted that while this example shows one
volume on one span, this menu option will display *all* volumes and
*all* spans, in no particular order and with no distinction between
cache spans on files, block devices, or ram devices.

``[2] List Settings``
^^^^^^^^^^^^^^^^^^^^^

This option will list the settings declared in ``records.config``, in
proper ATS syntax. An example:

::

    proxy.config.log.collation_host STRING NULL
    proxy.config.ssl.compression INT 1

Only one or two of these settings actually has any impact on the
function of ``scan``, but all values are read in to facilitate future
extension.

``[3] Search for Setting``
^^^^^^^^^^^^^^^^^^^^^^^^^^

This option will bring up a prompt to type a search string for a
specific setting from ``records.config``. Python-syntax regex is
supported and enabled by default (meaning searching for 'proxy.config'
will match 'proxyZconfig' as well as the exact string typed).

``[4] List Stripes in a Span``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This option will prompt you to enter a span (which is the **full** path
to the span file) and then list all stripes within it. The output is in
the format:

::

    XXX.XB stripe, created Www Mmm D hh:mm:ss (version XX.X)

where XXX.XB is the size of a stripe (but it will be displayed in
human-readable approximations in units of B, kB, MB, or GB as
appropriate), ``Www Mmm D hh:mm:ss`` is the date of the stripe's
creation (in the system's ``ctime(3)`` format) and XX.X is the
decimal-separated major and minor version numbers of the cache system
that created it. Note that this version is **not** the same as the
version of ATS using the cache. Also note that as of this time **only
version 24.0+ is supported by** ``scan``, and using lower versions with
``scan`` **will cause to crash and/or give incorrect output**.

``[5] View URLs of objects in a Span``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When selected, this option will first prompt you for a span. It will
then search all of the stripes on that span for stored objects, and
catalog their URLs, printing them to the screen as they are found. Each
URL is printed in the format:

::

    protocol://[[user]:password@]host/path/to/content    - XXX.XB -     x<Y>

where ``protocol`` is the protocol used to retrieve the content (nearly
always ``http`` or ``https``), ``[[user]:password@]`` is the username
(if used, usually not) 'colon' password (if used, usually not) used to
access the content 'at' the ``host`` - which is the fully-qualified
domain name of the content host, and ``path/to/content`` is the location
on that host of the content stored in the cache. A typical example of a
path is ``images/test/testquest.png``. XXX.XB is the size of this
content (but it will be displayed in human-readable approximations in
units of B, kB, MB, or GB as appropriate). Finally, ``<Y>`` will be the
number of times this same URL is stored in the cache (typically in
'alternate' forms). For example, if a given item is stored only once in
the cache span, its line will end in ``x1``, and if it is encountered 42
times, then it will end in ``x42``. Note that the size of a given object
is reported as the size of *one* instance of this item, regardless of
the number actually stored.

**Warning:** When tested on a span of a single, roughly 830GB stripe,
this operation took between 39 and 44 seconds to complete. Be aware that
the time this takes is directly proportional to the size of the spans,
and the number of spans that it is searching. However, results are
cached so that subsequent searches (or uses of menu option 6) on the
same span should be significantly quicker. To help recognize that the
program has not frozen, findings are printed to the screen as they are
found, and the main menu will display upon completion.

``[6] View Usage of a Span broken down by host``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This option will first prompt for a span, then it will list the hosts
that have content stored in that span, as well as the total storage size
used, the storage size as a percent of the total available storage, and
the storage size as a percent of the storage currently in use. The
output format for each host is as follows:

::

    <host>   - XXX.XB -     YY.YY% of available space -     ZZ.ZZ% of used space

where ``<host>`` is the fully-qualified domain name of the host, XXX.XB
is the total size of that host's content on disk (but it will be
displayed in human-readable approximations in units of B, kB, MB, or GB
as appropriate), YY.YY is the percent of available space taken up by
this host's content, and ZZ.ZZ is the percent of space currently being
used to store objects that is taken up by this host's content.

**Warning:** When tested on a span of a single, roughly 830GB stripe,
this operation took between 39 and 44 seconds to complete. Be aware that
the time this takes is directly proportional to the size of the spans,
and the number of spans that it is searching. However, results are
cached so that subsequent searches (or uses of menu option 5) on the
same span should be significantly quicker. To help recognize that the
program has not frozen, findings are printed to the screen as they are
found, and the main menu will display upon completion.

``[7] Dump cache usage stats to file (Tabular YAML format)``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This option will ask you to first name a file for output (relative or
absolute paths - doesn't matter which), then it will dump the output of
a call to the 'View URLs of objects in a Span' for **ALL** spans in the
cache system to the named file in Tabular YAML (TYAML) format (which is
just YAML but indented with tabs instead of spaces and accepts ``None``
as a null value.)

Tests
~~~~~

If you want to run the tests, be sure you're in the project's root
directory and run the ``test.sh`` script. Note that the unit tests will
*download and attempt to build Apache Traffic Server from source* and as
such will also require all of the dependencies of Apache Traffic Server.
A minimal linting test (Good for auditing your contribution at a glance)
can be run with ``pylint`` by just running
``pylint --rcfile=./.pylintrc scan/`` from the project's root directory.
A ``pylint`` score above 9.5 and with no erros (e.g. E001: SyntaxError)
is considered "passing".

Tabular YAML Format
-------------------

The output of the interactive mode's 7th option and the ``-d`` or
``--dump`` option are given in what's been referred to as "Tabular YAML
Format". As the name implies, this is similar to YAML. In fact, it
should be considered syntactically identical to YAML but for one
exception: indentation is *always done via the tab character, **never
with spaces***. This was done because without harming its human
readability, it allows for much easier pipelining of output e.g. via
``cut``.

.. |License| image:: https://img.shields.io/badge/License-Apache%202.0-blue.svg
   :target: https://opensource.org/licenses/Apache-2.0
.. |Build Status| image:: https://travis-ci.org/Comcast/Superior-Cache-ANalyzer.svg?branch=master
   :target: https://travis-ci.org/Comcast/Superior-Cache-ANalyzer
