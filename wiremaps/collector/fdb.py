from twisted.internet import reactor, defer

class FdbCollector:
    """Collect data using FDB"""

    dot1dTpFdbPort = '.1.3.6.1.2.1.17.4.3.1.2'

    def __init__(self, proxy, dbpool, normport=None):
        """Create a collector using FDB entries in SNMP.

        @param proxy: proxy to use to query SNMP
        @param dbpool: pool of database connections
        @param nomport: function to use to normalize port index
        """
        self.proxy = proxy
        self.dbpool = dbpool
        self.normport = normport
        self.fdb = {}

    def gotFdb(self, results):
        """Callback handling reception of FDB

        @param results: result of walking C{BRIDGE-MIB::dot1dTpFdbPort}
        """
        for oid in results:
            mac = ":".join(["%02x" % int(m) for m in oid.split(".")[-6:]])
            port = int(results[oid])
            if self.normport is not None:
                port = self.normport(port)
            if port is not None:
                self.fdb[(port, mac)] = 1

    def collectData(self, write=True):
        """Collect data from SNMP using dot1dTpFdbPort.

        @param write: when C{False}, do not write the result to
           database. It is intended to be called later with C{True} to
           accumulate results of successive runs.
        """
    
        def fileIntoDb(txn, fdb, ip):
            txn.execute("DELETE FROM fdb WHERE equipment=%(ip)s",
                        {'ip': str(ip)})
            for port, mac in fdb.keys():
                txn.execute("INSERT INTO fdb VALUES (%(ip)s, "
                            "%(port)s, %(mac)s)",
                            {'ip': str(ip),
                             'port': port,
                             'mac': mac})

        print "Collecting FDB for %s" % self.proxy.ip
        d = self.proxy.walk(self.dot1dTpFdbPort)
        d.addCallback(self.gotFdb)
        if write:
            d.addCallback(lambda x: self.dbpool.runInteraction(fileIntoDb,
                                                               self.fdb,
                                                               self.proxy.ip))
        return d
