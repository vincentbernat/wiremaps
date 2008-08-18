"""
Handle collection of data in database with the help of SNMP
"""

import sys

from IPy import IP
from twisted.internet import defer
from twisted.application import internet
from twisted.plugin import getPlugins

import wiremaps.collector
from wiremaps.collector import exception
from wiremaps.collector.proxy import AgentProxy
from wiremaps.collector.icollector import ICollector

class CollectorService(internet.TimerService):
    """Service to collect data from SNMP"""
    
    def __init__(self, config, dbpool, collect=True):
        self.config = config['collector']
        self.dbpool = dbpool
        self.setName("SNMP collector")
        self.exploring = False
        self.collect = collect
        internet.TimerService.__init__(self, self.config['period']*60,
                                       self.startExploration)

    def startExploration(self):
        """Start to explore the range of IP.

        We try to explore several IP in parallel. The parallelism is
        defined in the configuration file.
        """
        if not self.collect:
            return
        if self.exploring:
            print "Exploration still running, don't run it now"
            return
        self.exploring = True
        print "Start exploring %s..." % self.config['ips']
        self.remaining = [x for x in IP(self.config['ips'])]
        dl = []
        for i in range(0, self.config['parallel']):
            dl.append(self.startExplorePool())
        defer.DeferredList(dl).addCallback(self.stopExploration)

    def startExploreIP(self, ip):
        """Start to explore a given IP.

        @param ip: IP to explore
        """
        print "Explore IP %s" % ip
        d = self.guessCommunity(None, None, ip, self.config['community'])
        d.addCallback(self.getBasicInformation)
        d.addCallback(self.handlePlugins)
        d.addCallback(lambda x: x.close())
        return d

    def startExplorePool(self):
        """Start to explore a given pool.

        Each IP in C{self.remaining} is explored one after another.
        """
        if self.remaining:
            ip = self.remaining.pop()
            d = self.startExploreIP(ip)
            d.addErrback(self.reportError, ip)
            d.addCallback(lambda x: self.startExplorePool())
            return d
        return defer.succeed(None)

    def stopExploration(self, ignored):
        """Stop exploration process."""
        print "Exploration of %s finished!" % self.config['ips']
        self.exploring = False

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
            d.addCallback(lambda x: plugin.collectData(proxy.ip, proxy, self.dbpool))
        d.addCallback(lambda x: proxy)
        return d

    def guessCommunity(self, ignored, proxy, ip, communities):
        """Try to guess a community.

        @param proxy: an old proxy to close if different of C{None}
        @param ip: ip of the equipment to test
        @param communities: list of communities to test
        """
        if not communities:
            raise exception.NoCommunity("unable to guess community")
        if proxy:
            proxy.close()
        community = communities[0]
        proxy = AgentProxy(ip=ip,
                           community=community,
                           snmpVersion=2,
                           timeout=2,
                           tries=3,
                           allowCache=True)
        proxy.open()
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
                txn.execute("INSERT INTO equipment (ip, name, oid) VALUES "
                            "(%(ip)s, %(name)s, %(oid)s)",
                            {'ip': str(ip), 'name': result['.1.3.6.1.2.1.1.5.0'],
                             'oid': result['.1.3.6.1.2.1.1.2.0']})
            else:
                txn.execute("UPDATE equipment SET name=%(name)s, oid=%(oid)s "
                            "WHERE ip=%(ip)s",
                            {'name': result['.1.3.6.1.2.1.1.5.0'],
                             'oid': result['.1.3.6.1.2.1.1.2.0'],
                             'ip': str(ip)})
            return result['.1.3.6.1.2.1.1.2.0']

        d = proxy.get(['.1.3.6.1.2.1.1.2.0', # OID
                       '.1.3.6.1.2.1.1.5.0', # name
                       ])
        d.addCallback(lambda x: self.dbpool.runInteraction(fileIntoDb, x, proxy.ip))
        d.addCallback(lambda x: (proxy,x))
        return d
