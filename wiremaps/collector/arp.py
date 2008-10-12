from pyPgSQL import PgSQL
from twisted.python import log
from twisted.internet import defer, reactor

class ArpCollector:
    """Collect data using ARP"""

    ipNetToMediaPhysAddress = '.1.3.6.1.2.1.4.22.1.2'

    def __init__(self, proxy, dbpool, config):
        """Create a collector using ARP entries in SNMP.

        @param proxy: proxy to use to query SNMP
        @param dbpool: pool of database connections
        @param config: configuration
        """
        self.proxy = proxy
        self.dbpool = dbpool
        self.config = config
        self.arp = {}

    def gotArp(self, results):
        """Callback handling reception of ARP

        @param results: result of walking C{IP-MIB::ipNetToMediaPhysAddress}
        """
        for oid in results:
            ip = ".".join([m for m in oid.split(".")[-4:]])
            mac = ":".join("%02x" % ord(m) for m in results[oid])
            self.arp[(mac, ip)] = 1

    def collectData(self, write=True):
        """Collect data from SNMP using ipNetToMediaPhysAddress.

        @param write: when C{False}, do not write the result to
           database. It is intended to be called later with C{True} to
           accumulate results of successive runs.
        """
    
        def fileIntoDb(txn, arp, ip):
            for mac, rip in arp.keys():
                # Some magic here: PostgreSQL will take care of
                # updating the record if it already exists.
                txn.execute("INSERT INTO arp (equipment, mac, ip) VALUES (%(ip)s, "
                            "%(mac)s, %(rip)s)",
                            {'ip': str(ip),
                             'mac': mac,
                             'rip': rip})
            # Expire oldest entries
            txn.execute("DELETE FROM arp WHERE "
                       "timestamp 'now' - interval '%(expire)s hours' > last "
                       "AND equipment=%(ip)s",
                       {'ip': str(ip),
                        'expire': self.config.get('arpexpire', 24)})

        print "Collecting ARP for %s" % self.proxy.ip
        d = self.proxy.walk(self.ipNetToMediaPhysAddress)
        d.addCallback(self.gotArp)
        if write:
            d.addCallback(lambda x: self.dbpool.runInteraction(fileIntoDb,
                                                               self.arp,
                                                               self.proxy.ip))
        return d
