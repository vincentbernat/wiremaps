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

class ExtremeFdbCollector(FdbCollector):

    # It is really EXTREME-FDB-MIB::extremeFdbMacFdbMacAddress
    dot1dTpFdbPort = '.1.3.6.1.4.1.1916.1.16.1.1.3'
    vlanOid = '.1.3.6.1.4.1.1916.1.2.6.1.1'
    vlanTagged = '.1.3.6.1.4.1.1916.1.2.6.1.1.1'
    vlanUntagged = '.1.3.6.1.4.1.1916.1.2.6.1.1.2'

    def __init__(self, *args, **kwargs):
        FdbCollector.__init__(self, *args, **kwargs)
        self.vlans = None

    def gotVlans(self, results, fdbresults):
        """Process VLAN results.

        We assume that n/m has index n*1000 + m
        """
        if self.vlans is None:
            self.vlans = {}
        for oid in results:
            slot = int(oid.split(".")[-1])
            vlan = int(oid.split(".")[-2])
            ports = results[oid]
            l = self.vlans.get(vlan, [])
            for i in range(0, len(ports)):
                if ord(ports[i]) == 0:
                    continue
                for j in range(0, 8):
                    if ord(ports[i]) & (1 << j):
                        l.append(8-j + 8*i + 1000*slot)
            self.vlans[vlan] = l
        self.gotFdb(fdbresults)

    def gotFdb(self, results):
        """Callback handling reception of FDB

        @param results: result of walking C{EXTREME-BASE-MIB::extremeFdb}
        """
        if self.vlans is None:
            d = self.proxy.walk(self.vlanOid, results)
            d.addCallback(self.gotVlans, results)
            return d
        for oid in results:
            vlan = int(oid.split(".")[-2])
            mac = results[oid]
            mac = ":".join([("%02x" % ord(m)) for m in mac])
            if mac in ['ff:ff:ff:ff:ff:ff', # Broadcast
                       '01:80:c2:00:00:0e', # LLDP
                       '01:80:c2:00:00:02', # Something like LLDP
                       '00:e0:2b:00:00:02', # Something Extreme
                       '00:e0:2b:00:00:00', # Again, Extreme
                       ]: continue
            # Rather bad assumption: a vlan is a set of ports
            for port in self.vlans.get(vlan, []):
                if self.normport is not None:
                    port = self.normport(port)
                if port is not None:
                    self.fdb[(port, mac)] = 1
