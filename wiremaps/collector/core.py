"""
Handle collection of data in database with the help of SNMP
"""

import sys

from IPy import IP
from twisted.internet import defer, task
from twisted.application import internet, service
from twisted.plugin import getPlugins
from twisted.python.failure import Failure

import wiremaps.collector.equipment
from wiremaps.collector.datastore import Equipment
from wiremaps.collector.database import DatabaseWriter
from wiremaps.collector import exception
from wiremaps.collector.proxy import AgentProxy
from wiremaps.collector.icollector import ICollector
from wiremaps.collector.equipment.generic import generic

class CollectorService(service.Service):
    """Service to collect data from SNMP"""
    
    def __init__(self, config, dbpool):
        self.config = config['collector']
        self.dbpool = dbpool
        self.setName("SNMP collector")
        self.exploring = False
        self.ips = []
        AgentProxy.use_getbulk = self.config.get("bulk", True)

    def enumerateIP(self):
        """Enumerate the list of IP to explore.

        @return: a list of tuple (ip, community) that needs to be
           explored.
        """
        self.ips = []
        ipfile = open(self.config['ipfile'], "r")
        for ip in ipfile:
            ip = ip.split("#", 1)[0].strip()
            if not ip:
                continue
            parts = ip.split("@", 1)
            ip = IP(parts[0])
            community = None
            if len(parts) > 1:
                community = parts[1]
            self.ips += [(ip, community)]
        ipfile.close()

    def startExploration(self):
        """Start to explore the range of IP.

        We try to explore several IP in parallel. The parallelism is
        defined in the configuration file.
        """

        def doWork(remaining):
            for ip, community in remaining:
                for x in list(ip):
                    if ip.net() == ip.broadcast() or (x != ip.net() and x != ip.broadcast()):
                        d = self.startExploreIP(x, community)
                        d.addErrback(self.reportError, x)
                        yield d

        # Don't explore if already exploring
        if self.exploring:
            raise exception.CollectorAlreadyRunning(
                "Exploration still running")
        self.exploring = True
        print "Start exploration..."

        # Expand list of IP to explore
        self.enumerateIP()

        # Start exploring
        dl = []
        coop = task.Cooperator()
        work = doWork(self.ips)
        for i in xrange(self.config['parallel']):
            d = coop.coiterate(work)
            dl.append(d)
        defer.DeferredList(dl).addCallback(self.stopExploration)

    def startExploreIP(self, ip, community=None):
        """Start to explore a given IP.

        @param ip: IP to explore

        @param community: community to use for this specific IP. If
           C{True}, we will try to recover the community from the list
           of IP.
        """
        print "Explore IP %s" % ip
        if community is True:
            # We need to take the community from the list of IP, if available
            community = []
            community += [c for i,c in self.ips if str(i) == str(ip) and c]
            community += [c for i,c in self.ips if str(i) == str(IP(ip).net()) and c]
        elif community:
            # A community has been provided, don't try to guess
            community = [community]
        if not community:
            # No community, just try to guess from the defaults
            community = self.config['community']
        d = defer.maybeDeferred(self.guessCommunity,
                                None, None, ip,
                                community)
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
        print "Exploration finished!"
        self.exploring = False
        self.dbpool.runInteraction(self.cleanup)

    def cleanup(self, txn):
        """Clean older entries and move them in _past tables"""
        # Expire old entries
        txn.execute("""
UPDATE equipment SET deleted=CURRENT_TIMESTAMP
WHERE CURRENT_TIMESTAMP - interval '%(expire)s days' > updated
AND deleted='infinity'
""",
                    {'expire': self.config.get('expire', 1)})
        # Move old entries to _past tables
        for table in ["equipment", "port", "fdb", "arp", "sonmp", "edp", "cdp", "lldp",
                      "vlan", "trunk"]:
            txn.execute("INSERT INTO %s_past "
                        "SELECT * FROM %s WHERE deleted != 'infinity'" % ((table,)*2))
            txn.execute("DELETE FROM %s WHERE deleted != 'infinity'" % table)

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

        @param info: C{(proxy, equipment)} tuple
        """
        proxy, equipment = info
        proxy.version = 2       # Switch to version 2. Plugins should
                                # switch back to version 1 if needed.
        # Filter out plugins that do not handle our equipment
        plugins = [ plugin for plugin
                    in getPlugins(ICollector,
                                  wiremaps.collector.equipment)
                    if plugin.handleEquipment(str(equipment.oid)) ]
        if not plugins:
            print "No plugin found for OID %s, using generic one" % str(equipment.oid)
            plugins = [generic]
        print "Using %s to collect data from %s" % ([str(plugin.__class__)
                                                     for plugin in plugins],
                                                    proxy.ip)
        d = defer.succeed(None)
        # Run each plugin to complete C{equipment}
        for plugin in plugins:
            plugin.config = self.config
            d.addCallback(lambda x: plugin.collectData(equipment, proxy))
        # At the end, write C{equipment} to the database
        d.addCallback(lambda _: DatabaseWriter(equipment, self.config).write(self.dbpool))
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
            proxy = AgentProxy(ip=str(ip),
                               community=community,
                               version=1) # Start with version 1 for maximum compatibility
        d = proxy.get(['.1.3.6.1.2.1.1.1.0'])
        d.addCallbacks(callback=lambda x,y: y, callbackArgs=(proxy,),
                       errback=self.guessCommunity, errbackArgs=(proxy, ip,
                                                                 communities[1:]))
        return d

    def getBasicInformation(self, proxy):
        """Get some basic information to file C{equipment} table.

        @param proxy: proxy to use to get our information
        @return: deferred tuple C{(proxy, equipment)} where C{equipment} should
            be completed with additional information
        """
        d = proxy.get(['.1.3.6.1.2.1.1.1.0', # description
                       '.1.3.6.1.2.1.1.2.0', # OID
                       '.1.3.6.1.2.1.1.5.0', # name
                       '.1.3.6.1.2.1.1.6.0', # location
                       ])

        def norm(name):
            # Try to fix some broken system names
            name = name.lower().strip()
            if not name:
                return "unknown"
            name = name.replace(" ", "_")
            return name

        d.addCallback(lambda result: (proxy,
                                      Equipment(proxy.ip,
                                                norm(result['.1.3.6.1.2.1.1.5.0']),
                                                result['.1.3.6.1.2.1.1.2.0'],
                                                result['.1.3.6.1.2.1.1.1.0'],
                                                result['.1.3.6.1.2.1.1.6.0'] or None)))
        return d
