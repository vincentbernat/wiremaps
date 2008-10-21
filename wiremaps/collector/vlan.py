class VlanCollector:
    """Collect VLAN information.

    This class supports any switch that stores VLAN information in tow
    OID. The first OID contains VLAN names (with VLAN ID as index) and
    the second contains VLAN ports as a bitmask with VLAN ID as index.

    This class should be inherited and instance or class variables
    C{oidVlanNames} and C{oidVlanPorts} should be defined.
    """

    def __init__(self, proxy, dbpool, normPort=None):
        self.proxy = proxy
        self.dbpool = dbpool
        self.normPort = normPort

    def gotVlan(self, results, dic):
        """Callback handling reception of VLAN

        @param results: vlan names or ports
        @param dic: where to store the results
        """
        for oid in results:
            vid = int(oid.split(".")[-1])
            dic[vid] = results[oid]

    def collectData(self):
        """Collect VLAN data from SNMP"""
    
        def fileVlanIntoDb(txn, names, ports, ip):
            txn.execute("DELETE FROM vlan WHERE equipment=%(ip)s AND type='local'",
                        {'ip': str(ip)})
            for vid in names:
                if vid in ports:
                    for i in range(0, len(ports[vid])):
                        if ord(ports[vid][i]) == 0:
                            continue
                        for j in range(0, 8):
                            if ord(ports[vid][i]) & (1 << j):
                                port = 8-j + 8*i
                                if self.normPort is not None:
                                    port = self.normPort(port)
                                if port is not None:
                                    txn.execute("INSERT INTO vlan VALUES (%(ip)s, "
                                                "%(port)s, %(vid)s, %(name)s, "
                                                "%(type)s)",
                                                {'ip': str(ip),
                                                 'port': port,
                                                 'vid': vid,
                                                 'name': names[vid],
                                                 'type': 'local'})

        print "Collecting VLAN information for %s" % self.proxy.ip
        self.vlanNames = {}
        self.vlanPorts = {}
        d = self.proxy.walk(self.oidVlanNames)
        d.addCallback(self.gotVlan, self.vlanNames)
        d.addCallback(lambda x: self.proxy.walk(self.oidVlanPorts))
        d.addCallback(self.gotVlan, self.vlanPorts)
        d.addCallback(lambda x: self.dbpool.runInteraction(fileVlanIntoDb,
                                                           self.vlanNames,
                                                           self.vlanPorts,
                                                           self.proxy.ip))
        return d
