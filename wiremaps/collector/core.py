"""
Handle collection of data in database with the help of SNMP
"""

import sys

from IPy import IP
from twisted.internet import defer
from twisted.application import internet, service
from twisted.plugin import getPlugins
from twisted.python.failure import Failure

import wiremaps.collector
from wiremaps.collector import exception
from wiremaps.collector.proxy import AgentProxy
from wiremaps.collector.icollector import ICollector

class CollectorService(service.Service):
    """Service to collect data from SNMP"""
    
    def __init__(self, config, dbpool):
        self.config = config['collector']
        self.dbpool = dbpool
        self.setName("SNMP collector")
        self.exploring = False
        AgentProxy.use_getbulk = self.config.get("bulk", True)

    def startExploration(self):
        """Start to explore the range of IP.

        We try to explore several IP in parallel. The parallelism is
        defined in the configuration file.
        """

        class Explorer(object):

            def __init__(self, collector, remaining):
                self.defer = defer.Deferred()
                self.collector = collector
                self.remaining = remaining

            def __call__(self):
                self.exploreNext()
                return self.defer

            def exploreNext(self):
                if self.remaining:
                    ip = self.remaining.pop()
                    d = self.collector.startExploreIP(ip)
                    d.addErrback(self.collector.reportError, ip)
                    d.addCallback(lambda x: self.exploreNext())
                else:
                    self.defer.callback(None)

        if self.exploring:
            raise exception.CollectorAlreadyRunning(
                "Exploration still running")
        self.exploring = True
        print "Start exploring %s..." % self.config['ips']
        if type(self.config['ips']) in [list, tuple]:
            remaining = []
            for ip in self.config['ips']:
                remaining += [x for x in IP(ip)]
        else:
            remaining = [x for x in IP(self.config['ips'])]
        dl = []
        for i in range(0, self.config['parallel']):
            dl.append(Explorer(self, remaining)())
        defer.DeferredList(dl).addCallback(self.stopExploration)

    def startExploreIP(self, ip):
        """Start to explore a given IP.

        @param ip: IP to explore
        """
        print "Explore IP %s" % ip
        d = self.guessCommunity(None, None, ip, self.config['community'])
        d.addCallback(self.getInformations)
        return d

    def getInformations(self, proxy):
        """Get informations for a given host

        @param proxy: proxy to host
        """
        d = self.getBasicInformation(proxy)
        d.addCallback(self.handlePlugins)
        d.addBoth(lambda x: self.closeProxy(proxy, x))
        return d

    def closeProxy(self, proxy, obj):
        """Close the proxy and reraise error if obj is a failure.

        @param proxy: proxy to close
        @param obj: object from callback
        """
        del proxy
        if isinstance(obj, Failure):
            return obj
        return None

    def stopExploration(self, ignored):
        """Stop exploration process."""
        print "Exploration of %s finished!" % self.config['ips']
        self.exploring = False
        self.cleanUp()
        self.dbpool.runOperation("DELETE FROM equipment "
                                 "WHERE timestamp 'now' - interval '%(expire)s days' "
                                 "> last", {'expire': self.config.get('expire', 1)})

    def cleanUp(self):
        """Clean older entries"""

    def reportError(self, failure, ip):
        """Generic method to report an error on failure

        @param failure: failure that happened
        @param ip: IP that were explored when the failure happened
        """
        if isinstance(failure.value, exception.CollectorException):
            print "An error occured while exploring %s: %s" % (ip, str(failure.value))
        else:
            print "The following error occured while exploring %s:\n%s" % (ip,
                                                                           str(failure))

    def handlePlugins(self, info):
        """Give control to plugins.

        @param info: C{(proxy, oid)} tuple
        """
        proxy, oid = info
        plugins = [ plugin for plugin in getPlugins(ICollector, wiremaps.collector)
                    if plugin.handleEquipment(str(oid)) ]
        if not plugins:
            raise exception.UnknownEquipment("unknown equipment with OID %s" % oid)
        print "Using %s to collect data from %s" % ([str(plugin.__class__)
                                                     for plugin in plugins],
                                                    proxy.ip)
        d = defer.succeed(None)
        for plugin in plugins:
            plugin.config = self.config
            d.addCallback(lambda x: plugin.collectData(proxy.ip, proxy, self.dbpool))
        return d

    def guessCommunity(self, ignored, proxy, ip, communities):
        """Try to guess a community.

        @param proxy: an old proxy to close if different of C{None}
        @param ip: ip of the equipment to test
        @param communities: list of communities to test
        """
        if not communities:
            raise exception.NoCommunity("unable to guess community")
        community = communities[0]
        if proxy:
            proxy.community=community
        else:
            try:
                proxy = AgentProxy(ip=str(ip),
                                   community=community,
                                   version=2)
            except e:
                return defer.fail(e)
        d = proxy.get(['.1.3.6.1.2.1.1.1.0'])
        d.addCallbacks(callback=lambda x,y: y, callbackArgs=(proxy,),
                       errback=self.guessCommunity, errbackArgs=(proxy, ip,
                                                                 communities[1:]))
        return d

    def getBasicInformation(self, proxy):
        """Get some basic information to file C{equipment} table.

        @param proxy: proxy to use to get our information
        @return: deferred tuple C{(proxy, oid)} where C{oid} is the OID
            of the equipment.
        """

        def fileIntoDb(txn, result, ip):
            txn.execute("SELECT ip FROM equipment WHERE ip = %(ip)s",
                        {'ip': str(ip)})
            id = txn.fetchall()
            if not id:
                txn.execute("INSERT INTO equipment (ip, name, oid, description) VALUES "
                            "(%(ip)s, %(name)s, %(oid)s, %(description)s)",
                            {'ip': str(ip), 'name': result['.1.3.6.1.2.1.1.5.0'].lower(),
                             'oid': result['.1.3.6.1.2.1.1.2.0'],
                             'description': result['.1.3.6.1.2.1.1.1.0']})
            else:
                txn.execute("UPDATE equipment SET name=%(name)s, oid=%(oid)s, "
                            "description=%(description)s, last=CURRENT_TIMESTAMP "
                            "WHERE ip=%(ip)s",
                            {'name': result['.1.3.6.1.2.1.1.5.0'].lower(),
                             'oid': result['.1.3.6.1.2.1.1.2.0'],
                             'description': result['.1.3.6.1.2.1.1.1.0'],
                             'ip': str(ip)})
            return result['.1.3.6.1.2.1.1.2.0']

        d = proxy.get(['.1.3.6.1.2.1.1.1.0', # description
                       '.1.3.6.1.2.1.1.2.0', # OID
                       '.1.3.6.1.2.1.1.5.0', # name
                       ])
        d.addCallback(lambda x: self.dbpool.runInteraction(fileIntoDb, x, proxy.ip))
        d.addCallback(lambda x: (proxy,x))
        return d
