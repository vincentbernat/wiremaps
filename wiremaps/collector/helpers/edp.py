from wiremaps.collector import exception

class EdpCollector:
    """Collect data using EDP"""

    edpNeighborName = '.1.3.6.1.4.1.1916.1.13.2.1.3'
    edpNeighborSlot = '.1.3.6.1.4.1.1916.1.13.2.1.5'
    edpNeighborPort = '.1.3.6.1.4.1.1916.1.13.2.1.6'
    edpNeighborVlanId = '.1.3.6.1.4.1.1916.1.13.3.1.2'

    def __init__(self, proxy, dbpool, normport=None):
        """Create a collector using EDP entries in SNMP.

        @param proxy: proxy to use to query SNMP
        @param dbpool: pool of database connections
        @param nomport: function to use to normalize port index
        """
        self.proxy = proxy
        self.dbpool = dbpool
        self.normport = normport

    def gotEdp(self, results, dic):
        """Callback handling reception of EDP

        @param results: result of walking C{EXTREME-EDP-MIB::extremeEdpNeighborXXXX}
        @param dic: dictionary where to store the result
        """
        for oid in results:
            port = int(oid[len(self.edpNeighborName):].split(".")[1])
            if self.normport is not None:
                port = self.normport(port)
            desc = results[oid]
            if desc and port is not None:
                dic[port] = desc

    def gotEdpVlan(self, results):
        """Callback handling reception of EDP vlan

        @param results: result of walking C{EXTREME-EDP-MIB::extremeEdpNeighborVlanId}
        """
        for oid in results:
            port = int(oid[len(self.edpNeighborVlanId):].split(".")[1])
            if self.normport is not None:
                port = self.normport(port)
            vlan = [chr(int(x))
                    for x in oid[len(self.edpNeighborVlanId):].split(".")[11:]]
            self.vlan[results[oid], port] = "".join(vlan)

    def collectData(self):
        """Collect EDP data from SNMP"""
    
        def fileIntoDb(txn, sysname, remoteslot, remoteport, ip):
            txn.execute("UPDATE edp SET deleted=CURRENT_TIMESTAMP "
                        "WHERE equipment=%(ip)s AND deleted='infinity'",
                        {'ip': str(ip)})
            for port in sysname.keys():
                txn.execute("INSERT INTO edp VALUES (%(ip)s, "
                            "%(port)s, %(sysname)s, %(remoteslot)s, "
                            "%(remoteport)s)",
                            {'ip': str(ip),
                             'port': port,
                             'sysname': sysname[port],
                             'remoteslot': int(remoteslot[port]),
                             'remoteport': int(remoteport[port])})

        def fileVlanIntoDb(txn, vlan, ip):
            txn.execute("UPDATE vlan SET deleted=CURRENT_TIMESTAMP "
                        "WHERE equipment=%(ip)s AND type='remote' AND deleted='infinity'",
                        {'ip': str(ip)})
            for vid,port in vlan.keys():
                txn.execute("INSERT INTO vlan VALUES (%(ip)s, "
                            "%(port)s, %(vid)s, %(name)s, "
                            "%(type)s)",
                            {'ip': str(ip),
                             'port': port,
                             'vid': vid,
                             'name': vlan[vid,port],
                             'type': 'remote'})

        print "Collecting EDP for %s" % self.proxy.ip
        self.edpSysName = {}
        self.edpRemoteSlot = {}
        self.edpRemotePort = {}
        self.vlan = {}
        d = self.proxy.walk(self.edpNeighborName)
        d.addCallback(self.gotEdp, self.edpSysName)
        d.addCallback(lambda x: self.proxy.walk(self.edpNeighborSlot))
        d.addCallback(self.gotEdp, self.edpRemoteSlot)
        d.addCallback(lambda x: self.proxy.walk(self.edpNeighborPort))
        d.addCallback(self.gotEdp, self.edpRemotePort)
        d.addCallback(lambda x: self.proxy.walk(self.edpNeighborVlanId))
        d.addCallback(self.gotEdpVlan)
        d.addCallback(lambda x: self.dbpool.runInteraction(fileIntoDb,
                                                           self.edpSysName,
                                                           self.edpRemoteSlot,
                                                           self.edpRemotePort,
                                                           self.proxy.ip))
        d.addCallback(lambda x: self.dbpool.runInteraction(fileVlanIntoDb,
                                                           self.vlan,
                                                           self.proxy.ip))
        return d
