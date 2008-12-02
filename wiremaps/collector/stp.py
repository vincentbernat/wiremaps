class StpCollector:
    """Collect information from STP.
    """

    dot1dBasePortIfIndex = '.1.3.6.1.2.1.17.1.4.1.2'
    dot1dStpDesignatedRoot = '.1.3.6.1.2.1.17.2.5.0'
    dot1dBaseBridgeAddress = '.1.3.6.1.2.1.17.1.1.0'
    dot1dStpPortState = '.1.3.6.1.2.1.17.2.15.1.3'
    dot1dStpRootPort = '.1.3.6.1.2.1.17.2.7.0'
    dot1dStpPortDesignatedBridge = '.1.3.6.1.2.1.17.2.15.1.8'

    def __init__(self, proxy, dbpool, normport=None):
        """Create a collector for STP information using BRIDGE-MIB

        @param proxy: proxy to use to query SNMP
        @param dbpool: pool of database connections
        """
        self.proxy = proxy
        self.dbpool = dbpool
        self.normport = normport

    def gotPortIf(self, results):
        """Callback handling reception of port<->ifIndex translation for STP

        @param results: result of walking C{BRIDGE-MIB::dot1dBasePortIfIndex}
        """
        for oid in results:
            self.portif[int(oid.split(".")[-1])] = int(results[oid])

    def gotPortState(self, results):
        """Callback handling reception of STP port state

        @param results: result of walking C{BRIDGE-MIB::dot1dStpPortState}
        """
        self.states = {}
        for oid in results:
            port = int(oid.split(".")[-1])
            try:
                port = self.portif[port]
            except KeyError:
                continue        # Ignore the port
            if self.normport is not None:
                port = self.normport(port)
            if port is not None:
                if results[oid] == 2:
                    self.states[port] = 'blocking'
                elif results[oid] == 3:
                    self.states[port] = 'listening'
                elif results[oid] == 4:
                    self.states[port] = 'learning'
                elif results[oid] == 5:
                    self.states[port] = 'forwarding'

    def gotPortDB(self, results):
        """Callback handling reception of STP designated bridge for each port

        @param results: result of walking C{BRIDGE-MIB::dot1dStpPortDesignatedBridge}
        """
        self.bridges = {}
        for oid in results:
            port = int(oid.split(".")[-1])
            try:
                port = self.portif[port]
            except KeyError:
                continue        # Ignore the port
            if self.normport is not None:
                port = self.normport(port)
            if port is not None:
                self.bridges[port] = ":".join([ "%x" % ord(a) for a in str(results[oid][2:])])

    def collectData(self):

        def fileIntoDb(txn, bridgeid, root, rootport, states, bridges, ip):
            txn.execute("DELETE FROM stp WHERE equipment=%(ip)s AND vlan=0",
                        {'ip': str(ip)})
            txn.execute("DELETE FROM stpport WHERE equipment=%(ip)s AND vlan=0",
                        {'ip': str(ip)})
            if bridgeid is not None and root is not None:
                if rootport == -1 or rootport == 0:
                    rootport = None
                if rootport is not None:
                    try:
                        rootport = self.portif[rootport]
                    except KeyError:
                        rootport = None
                if self.normport is not None and rootport is not None:
                    rootport = self.normport(rootport)
                txn.execute("INSERT INTO stp VALUES (%(ip)s, %(bridgeid)s, %(root)s, %(rootport)s)",
                            {'ip': str(ip),
                             'bridgeid': bridgeid,
                             'root': root,
                             'rootport': rootport})
                for port in states:
                    txn.execute("INSERT INTO stpport "
                                "VALUES (%(ip)s, %(port)s, %(state)s, %(bridge)s)",
                                {'ip': str(ip),
                                 'port': port,
                                 'bridge': bridges[port],
                                 'state': states[port]})

        print "Collecting STP information for %s" % self.proxy.ip
        self.portif = {}
        d = self.proxy.get([self.dot1dStpDesignatedRoot])
        d.addCallbacks(lambda x: setattr(self, "root",
                                         ":".join(
                    [ "%x" % ord(a)
                      for a in str(x[self.dot1dStpDesignatedRoot][2:])])),
                       lambda x: setattr(self, "root", None))
        d.addCallback(lambda x: self.proxy.get([self.dot1dBaseBridgeAddress]))
        d.addCallbacks(lambda x: setattr(self, "bridgeid",
                                         ":".join(
                    [ "%x" % ord(a)
                      for a in str(x[self.dot1dBaseBridgeAddress])])),
                       lambda x: setattr(self, "bridgeid", None))
        d.addCallback(lambda x: self.proxy.get([self.dot1dStpRootPort]))
        d.addCallbacks(lambda x: setattr(self, "rootport", x[self.dot1dStpRootPort]),
                       lambda x: setattr(self, "rootport", None))
        d.addCallback(lambda x: self.proxy.walk(self.dot1dBasePortIfIndex))
        d.addCallback(self.gotPortIf)
        d.addCallback(lambda x: self.proxy.walk(self.dot1dStpPortState))
        d.addCallback(self.gotPortState)
        d.addCallback(lambda x: self.proxy.walk(self.dot1dStpPortDesignatedBridge))
        d.addCallback(self.gotPortDB)
        d.addCallback(lambda x: self.dbpool.runInteraction(fileIntoDb,
                                                           self.bridgeid,
                                                           self.root,
                                                           self.rootport,
                                                           self.states,
                                                           self.bridges,
                                                           self.proxy.ip))
        return d
