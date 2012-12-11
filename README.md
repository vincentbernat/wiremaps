Wiremaps
========

Wiremaps is an application to gather wiring (aka L2) information on a
network using protocols like [LLDP][1], EDP, CDP and SONMP. It also gathers
information from the FDB (MAC-port table on switches), the ARP table
(MAC-IP table) and some miscellaneous information like interface
names.

The ARP table is only used to link IP addresses to MAC addresses (and
vice-versa). We don't use the information about the interface where
this information came from.

GNU/Linux workstations need an [LLDP daemon using SNMP][2] to export
information gathered. Otherwise, almost no information can be
extracted from those hosts.

The situation is the same for Windows. However, there exists a
[commercial one][3].

[1]: http://en.wikipedia.org/wiki/LLDP
[2]: https://trac.luffy.cx/lldpd/
[3]: http://www.hanewin.net/lldp-e.htm

Installation
------------

To use this application, you need the following Debian packages:
 - postgresql-8.2 ([PostgreSQL 8.2][4])
 - python-psycopg2 ([Psycopg][5])
   (or alternatively, python-pgsql ([PyPgSQL Python bindings][6]))
 - python-twisted-core ([Twisted][7])
 - python-twisted-names ([Twisted Names][8])
 - python-nevow ([Nevow][9])
 - python-ipy ([iPy][10])
 - python-yaml ([PyYAML][11])
 - python-dev
 - libsnmp-dev

[4]: http://www.postgresql.org
[5]: http://initd.org/psycopg/
[6]: http://pypgsql.sourceforge.net/
[7]: http://twistedmatrix.com
[8]: http://twistedmatrix.com
[9]: http://divmod.org/trac/wiki/DivmodNevow
[10]: http://c0re.23.nu/c0de/IPy/
[11]: http://pyyaml.org/

You then need to create a database and install the corresponding
schema. As postgres user (`su - postgres`), you can use the following:

    createuser -P wiremaps
    createdb -O wiremaps wiremaps

Then load the content of `doc/database.sql`:

    psql -h localhost -U wiremaps -W < doc/database.sql

You need to write a `wiremaps.cfg` file. See `doc/wiremaps.cfg.sample`
for an example. The default path for this file is
`/etc/wiremaps/wiremaps.cfg`. You can alter it with `--config` option.

You can install the application with:

    python setup.py build
    sudo python setup.py install

Errors about missing `twisted/plugins/__init__.py` can be ignored. You
need to have the appropriate libraries and development tools to be
able to compile Python modules. On Debian/Ubuntu, this is `python-dev`
package.

If you do not wish to install the application, you still need to
compile the module to build SNMP queries. This can be done with:

    python setup.py build_ext --inplace

You can launch the application by hand

    twistd -no wiremaps

or

    twistd -no wiremaps --config=/etc/wiremaps/wiremaps.cfg

By default, wiremaps only listens on localhost. You can change this using:

    twistd -no wiremaps --interface=0.0.0.0

You can also use `debian/init.d` as a base for an init script (work
only if the application is installed). The init.d script also allows
to use older version of Twisted (2.4).

Indexation is not done automatically. You must browse
`http://localhost:8087/api/1.0/equipment/refresh` to initiate a whole
refresh. Put this command in a crontab.

In the git repository (`git clone git://trac.luffy.cx/wiremaps.git`),
there is a `debian/` directory that builds a Debian package (with
`dpkg-buildpackage -us -uc`). It does not setup the database.

License
-------

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 3, or (at your option)
any later version.

See LICENSE file for the complete text. Moreover, to avoid any problem
with SNMP bindings using NetSNMP which may be linked with OpenSSL,
there is an exception for OpenSSL:

> In addition, as a special exception, a permission to link the code
> with the OpenSSL project's "OpenSSL" library (or with modified
> versions of it that use the same license as the "OpenSSL" library),
> and distribute the linked executables is given.  You must obey the
> GNU General Public License in all respects for all of the code used
> other than "OpenSSL".  If you modify this file, you may extend this
> exception to your version of the file, but you are not obligated to
> do so.  If you do not wish to do so, delete this exception statement
> from your version.

The SVG files are licensed under Creative Commons Attribution 3.0. See
LICENSE-CC for the complete license.

snmp.c is licensed under MIT/X11 license. See the license at the top
of the file.
