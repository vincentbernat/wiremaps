from twisted.internet import defer

class FdbCollector:
    """Collect data using FDB"""

    dot1dTpFdbPort = '.1.3.6.1.2.1.17.4.3.1.2'
    dot1dBasePortIfIndex = '.1.3.6.1.2.1.17.1.4.1.2'

    def __init__(self, proxy, dbpool, config, normport=None):
        """Create a collector using FDB entries in SNMP.

        @param proxy: proxy to use to query SNMP
        @param dbpool: pool of database connections
        @param config: configuration
        @param nomport: function to use to normalize port index
        """
        self.proxy = proxy
        self.dbpool = dbpool
        self.normport = normport
        self.config = config
        self.fdb = {}
        self.portif = {}

    def gotFdb(self, results):
        """Callback handling reception of FDB

        @param results: result of walking C{BRIDGE-MIB::dot1dTpFdbPort}
        """
        for oid in results:
            mac = ":".join(["%02x" % int(m) for m in oid.split(".")[-6:]])
            port = int(results[oid])
            try:
                port = self.portif[port]
            except KeyError:
                continue        # Ignore the port
            if self.normport is not None:
                port = self.normport(port)
            if port is not None:
                self.fdb[(port, mac)] = 1

    def gotPortIf(self, results):
        """Callback handling reception of port<->ifIndex translation from FDB

        @param results: result of walking C{BRIDGE-MIB::dot1dBasePortIfIndex}
        """
        for oid in results:
            self.portif[int(oid.split(".")[-1])] = int(results[oid])

    def collectFdbData(self):
        d = self.proxy.walk(self.dot1dBasePortIfIndex)
        d.addCallback(self.gotPortIf)
        d.addCallback(lambda x: self.proxy.walk(self.dot1dTpFdbPort))
        d.addCallback(self.gotFdb)
        return d

    def collectData(self, write=True):
        """Collect data from SNMP using dot1dTpFdbPort.

        @param write: when C{False}, do not write the result to
           database. It is intended to be called later with C{True} to
           accumulate results of successive runs.
        """
    
        def fileIntoDb(txn, fdb, ip):
            for port, mac in fdb.keys():
                # Some magic here: PostgreSQL will take care of
                # updating the record if it already exists.
                txn.execute("INSERT INTO fdb (equipment, port, mac) "
                            "VALUES (%(ip)s, %(port)s, %(mac)s)",
                            {'ip': str(ip),
                             'port': port,
                             'mac': mac})
            # Expire oldest entries
            txn.execute("UPDATE fdb SET deleted=CURRENT_TIMESTAMP WHERE "
                       "CURRENT_TIMESTAMP - interval '%(expire)s hours' > updated "
                       "AND equipment=%(ip)s AND deleted='infinity'",
                       {'ip': str(ip),
                        'expire': self.config.get('fdbexpire', 24)})


        print "Collecting FDB for %s" % self.proxy.ip
        d = self.collectFdbData()
        if write:
            d.addCallback(lambda x: self.dbpool.runInteraction(fileIntoDb,
                                                               self.fdb,
                                                               self.proxy.ip))
        return d

class CommunityFdbCollector(FdbCollector):
    """Collect FDB for switch using indexed community

    On Cisco, FDB is retrieved one VLAN at a time using mechanism
    called CSI (Community String Indexing):
     U{http://www.cisco.com/en/US/tech/tk648/tk362/technologies_tech_note09186a00801576ff.shtml}

    So, we need to change the community string of the proxy. The
    resulting string is still valid, so we don't have concurrency
    problem.
    """

    def getFdbForVlan(self, community):
        self.proxy.community = community
        d = self.proxy.walk(self.dot1dBasePortIfIndex)
        d.addCallback(self.gotPortIf)
        d.addCallback(lambda x: self.proxy.walk(self.dot1dTpFdbPort))
        return d

    def gotVlans(self, results):
        vlans = []
        for oid in results:
            vid = int(oid.split(".")[-1])
            # Some VLAN seem special
            if results[oid] not in self.filterOut:
                vlans.append(vid)
        # We ask FDB for each VLAN
        origcommunity = self.proxy.community
        d = defer.succeed(None)
        for vlan in vlans:
            d.addCallback(lambda x,y: self.getFdbForVlan("%s@%d" % (origcommunity,
                                                                    y)), vlan)
            d.addCallbacks(self.gotFdb, lambda x: None) # Ignore FDB error
        # Reset original community when done (errors have been ignored)
        d.addBoth(lambda x: setattr(self.proxy, "community", origcommunity))
        return d

    def collectFdbData(self):
        d = self.proxy.walk(self.vlanName)
        d.addCallback(self.gotVlans)
        return d

class ExtremeFdbCollector(FdbCollector):
    """Collect FDB for some Extreme switch.

    Some Extreme switches need VLAN information to interpret FDB correctly. We use this.
    """

    # It is really EXTREME-FDB-MIB::extremeFdbMacFdbMacAddress
    dot1dTpFdbPort = '.1.3.6.1.4.1.1916.1.16.1.1.3'

    def __init__(self, vlan, *args, **kwargs):
        FdbCollector.__init__(self, *args, **kwargs)
        self.vlan = vlan

    def gotFdb(self, results):
        """Callback handling reception of FDB

        @param results: result of walking C{EXTREME-BASE-MIB::extremeFdb}
        """
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
            for port in self.vlan.vlanPorts.get(vlan, []):
                if self.normport is not None:
                    port = self.normport(port)
                if port is not None:
                    self.fdb[(port, mac)] = 1
