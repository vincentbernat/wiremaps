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

VERSION='0.1'

def makeService(config):
    # configuration file
    configfile = yaml.load(file(config['config'], 'rb').read())
    # database
    dbpool = adbapi.ConnectionPool("pyPgSQL.PgSQL",
                                   "%s:%d:%s:%s:%s" % ("localhost", 5432,
                                                       configfile['database']['database'],
                                                       configfile['database']['username'],
                                                       configfile['database']['password']))
    application = service.MultiService()

    collector = CollectorService(configfile, dbpool)
    collector.setServiceParent(application)

    web = internet.TCPServer(config['port'],
                             appserver.NevowSite(MainPage(configfile,
                                                      dbpool,
                                                      collector)))
    web.setServiceParent(application)
    return application
