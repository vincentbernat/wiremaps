import os
import sys
import yaml

from twisted.application import service, internet
from nevow import appserver

from wiremaps.collector.core import CollectorService
from database import Database
from wiremaps.web.site import MainPage

def makeService(config):
    # configuration file
    configfile = yaml.load(file(config['config'], 'rb').read())
    # database
    dbpool = Database(configfile).pool
    application = service.MultiService()

    collector = CollectorService(configfile, dbpool)
    collector.setServiceParent(application)

    web = internet.TCPServer(config['port'],
                             appserver.NevowSite(MainPage(configfile,
                                                      dbpool,
                                                      collector)))
    web.setServiceParent(application)
    return application
