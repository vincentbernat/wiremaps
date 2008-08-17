# -*- python -*-

import os
import sys
import yaml

import pyPgSQL.PgSQL

from twisted.application import service, internet
from twisted.enterprise import adbapi 
from nevow import appserver
from pynetsnmp import twistedsnmp

from wiremaps.collector.core import CollectorService
from wiremaps.web.site import MainPage

# Configuration file
config = os.path.join(os.path.curdir, 'wiremaps.cfg')
config = yaml.load(file(config, 'rb').read())

# Database
dbpool = adbapi.ConnectionPool("pyPgSQL.PgSQL",
                               "%s:%d:%s:%s:%s" % ("localhost", 5432,
                                                   config['database']['database'],
                                                   config['database']['username'],
                                                   config['database']['password']))

application = service.Application("Wire Maps")

# CollectorService(config, dbpool).setServiceParent(application)
internet.TCPServer(8087,
                   appserver.NevowSite(MainPage(config,
                                                dbpool))).setServiceParent(application)
