from wiremaps.collector import exception
from wiremaps.collector.speed import SpeedCollector

class LldpCollector:
    """Collect data using LLDP"""

    lldpRemPortDesc = '.1.0.8802.1.1.2.1.4.1.1.8'
    lldpRemSysName = '.1.0.8802.1.1.2.1.4.1.1.9'
    lldpRemSysDesc = '.1.0.8802.1.1.2.1.4.1.1.10'
    lldpRemManAddrIfId = '.1.0.8802.1.1.2.1.4.2.1.4'
    lldpLocPortId = '.1.0.8802.1.1.2.1.3.7.1.3'
    lldpLocVlanName = '.1.0.8802.1.1.2.1.5.32962.1.2.3.1.2'
    lldpRemVlanName = '.1.0.8802.1.1.2.1.5.32962.1.3.3.1.2'

    def __init__(self, proxy, dbpool, normport=None):
        """Create a collector using LLDP entries in SNMP.

        @param proxy: proxy to use to query SNMP
        @param dbpool: pool of database connections
        @param nomport: function to use to normalize port index
        """
        self.proxy = proxy
        self.dbpool = dbpool
        self.normport = normport

    def gotLldp(self, results, dic):
        """Callback handling reception of LLDP

        @param results: result of walking C{LLDP-MIB::lldpRemXXXX}
        @param dic: dictionary where to store the result
        """
        for oid in results:
            port = int(oid.split(".")[-2])
            if self.normport is not None:
                port = self.normport(port)
            desc = results[oid].strip()
            if desc and port is not None:
                dic[port] = desc

    def gotLldpMgmtIP(self, results):
        """Callback handling reception of LLDP

        @param results: result of walking C{LLDP-MIB::lldpRemManAddrIfId}
        """
        self.lldpMgmtIp = {}
        for oid in results:
            oid = oid[len(self.lldpRemManAddrIfId):]
            if oid.split(".")[4] != "1":
                continue
            if oid.split(".")[5] == "4":
                # Nortel is encoding the IP address in its binary form
                ip = ".".join([m for m in oid.split(".")[-4:]])
            else:
                # While Extreme is using a human readable string
                oid = "".join([chr(int(m))
                               for m in oid.split(".")[-int(oid.split(".")[5]):]])
            port = int(oid.split(".")[2])
            if self.normport is not None:
                port = self.normport(port)
            if port is not None:
                self.lldpMgmtIp[port] = ip

    def gotLldpLocalVlan(self, results):
        """Callback handling reception of LLDP local vlan

        @param results: result of walking C{LLDP-EXT-DOT1-MIB::lldpXdot1LocVlanName}
        """
        self.lldpLocalVlan = {}
        for oid in results:
            vid = int(oid.split(".")[-1])
            port = int(oid.split(".")[-2])
            if self.normport is not None:
                port = self.normport(port)
            if port is not None:
                self.lldpLocalVlan[vid,port] = results[oid]

    def gotLldpRemoteVlan(self, results):
        """Callback handling reception of LLDP remote vlan

        @param results: result of walking C{LLDP-EXT-DOT1-MIB::lldpXdot1RemVlanName}
        """
        self.lldpRemoteVlan = {}
        for oid in results:
            vid = int(oid.split(".")[-1])
            port = int(oid.split(".")[-3])
            if self.normport is not None:
                port = self.normport(port)
            if port is not None:
                self.lldpRemoteVlan[vid,port] = results[oid]

    def gotLldpLocPort(self, results):
        """Callback handling reception of LLDP Local Port ID

        @param results: result of walking C{LLDP-MIB::lldpLocPortId}
        """
        self.lldpValidPorts = []
        if not results:
            raise exception.NoLLDP("LLDP does not seem to be running")
        for oid in results:
            port = int(oid.split(".")[-1])
            if self.normport is not None:
                port = self.normport(port)
            if port is not None:
                self.lldpValidPorts.append(port)

    def cleanPorts(self):
        """Clean up ports to remove data not present in LLDP"""

        def fileIntoDb(txn, validports, ip):
            txn.execute("SELECT index FROM port WHERE equipment=%(ip)s",
                        {'ip': str(ip)})
            result = txn.fetchall()
            for port in result:
                port = port[0]
                if port not in validports:
                    txn.execute("DELETE FROM port WHERE equipment=%(ip)s "
                                "AND index=%(index)s", {'ip': str(ip),
                                                        'index': port})

        d = self.proxy.walk(self.lldpLocPortId)
        d.addCallback(self.gotLldpLocPort)
        d.addCallback(lambda x: self.dbpool.runInteraction(fileIntoDb,
                                                           self.lldpValidPorts,
                                                           self.proxy.ip))
        return d

    def collectData(self):
        """Collect data from SNMP using LLDP"""
    
        def fileIntoDb(txn, sysname, sysdesc, portdesc, mgmtip,
                       ip):
            txn.execute("DELETE FROM lldp WHERE equipment=%(ip)s",
                        {'ip': str(ip)})
            for port in sysname.keys():
                if port not in sysdesc.keys() or port not in portdesc.keys():
                    continue
                txn.execute("INSERT INTO lldp VALUES (%(ip)s, "
                            "%(port)s, %(mgmtip)s, %(portdesc)s, "
                            "%(sysname)s, %(sysdesc)s)",
                            {'ip': str(ip),
                             'port': port,
                             'mgmtip': mgmtip.get(port, "0.0.0.0"),
                             'portdesc': portdesc[port],
                             'sysname': sysname[port],
                             'sysdesc': sysdesc[port]})

        def fileVlanIntoDb(txn, rvlan, lvlan,
                           ip):
            txn.execute("DELETE FROM vlan WHERE equipment=%(ip)s",
                        {'ip': str(ip)})
            for vid,port in rvlan.keys():
                txn.execute("INSERT INTO vlan VALUES (%(ip)s, "
                            "%(port)s, %(vid)s, %(name)s, "
                            "%(type)s)",
                            {'ip': str(ip),
                             'port': port,
                             'vid': vid,
                             'name': rvlan[vid,port],
                             'type': 'remote'})
            for vid,port in lvlan.keys():
                txn.execute("INSERT INTO vlan VALUES (%(ip)s, "
                            "%(port)s, %(vid)s, %(name)s, "
                            "%(type)s)",
                            {'ip': str(ip),
                             'port': port,
                             'vid': vid,
                             'name': lvlan[vid,port],
                             'type': 'local'})

        print "Collecting LLDP for %s" % self.proxy.ip
        d = self.proxy.walk(self.lldpRemManAddrIfId)
        d.addCallback(self.gotLldpMgmtIP)
        self.lldpSysName = {}
        self.lldpSysDesc = {}
        self.lldpPortDesc = {}
        d.addCallback(lambda x: self.proxy.walk(self.lldpRemSysName))
        d.addCallback(self.gotLldp, self.lldpSysName)
        d.addCallback(lambda x: self.proxy.walk(self.lldpRemSysDesc))
        d.addCallback(self.gotLldp, self.lldpSysDesc)
        d.addCallback(lambda x: self.proxy.walk(self.lldpRemPortDesc))
        d.addCallback(self.gotLldp, self.lldpPortDesc)
        d.addCallback(lambda x: self.proxy.walk(self.lldpRemVlanName))
        d.addCallback(self.gotLldpRemoteVlan)
        d.addCallback(lambda x: self.proxy.walk(self.lldpLocVlanName))
        d.addCallback(self.gotLldpLocalVlan)
        d.addCallback(lambda x: self.dbpool.runInteraction(fileIntoDb,
                                                           self.lldpSysName,
                                                           self.lldpSysDesc,
                                                           self.lldpPortDesc,
                                                           self.lldpMgmtIp,
                                                           self.proxy.ip))
        d.addCallback(lambda x: self.dbpool.runInteraction(fileVlanIntoDb,
                                                           self.lldpRemoteVlan,
                                                           self.lldpLocalVlan,
                                                           self.proxy.ip))
        return d

class LldpSpeedCollector(SpeedCollector):
    """Collect speed/duplex and autoneg with the help of LLDP"""

    oidDuplex = '.1.0.8802.1.1.2.1.5.4623.1.2.1.1.4'
    oidAutoneg = '.1.0.8802.1.1.2.1.5.4623.1.2.1.1.2'

    mau = { # From RFC3636
        2:  (10, None), # 10BASE-5

        4:  (10, None), # 10BASE-2
        5:  (10, None), # 10BASE-T duplex mode unknown
        6:  (10, None), # 10BASE-FP
        7:  (10, None), # 10BASE-FB
        8:  (10, None), # 10BASE-FL duplex mode unknown

        8:  (10, None), # 10BASE-FL duplex mode unknown
        9:  (10, None), # 10BROAD36
        10: (10, "half"), # 10BASE-T  half duplex mode
        11: (10, "full"), # 10BASE-T  full duplex mode
        12: (10, "half"), # 10BASE-FL half duplex mode
        13: (10, "full"), # 10BASE-FL full duplex mode

        14: (100, None), # 100BASE-T4
        15: (100, "half"), # 100BASE-TX half duplex mode
        16: (100, "full"), # 100BASE-TX full duplex mode
        17: (100, "half"), # 100BASE-FX half duplex mode
        18: (100, "full"), # 100BASE-FX full duplex mode
        19: (100, "half"), # 100BASE-T2 half duplex mode
        20: (100, "full"), # 100BASE-T2 full duplex mode

        21: (1000, "half"), # 1000BASE-X half duplex mode
        22: (1000, "full"), # 1000BASE-X full duplex mode
        23: (1000, "half"), # 1000BASE-LX half duplex mode
        24: (1000, "full"), # 1000BASE-LX full duplex mode
        25: (1000, "half"), # 1000BASE-SX half duplex mode
        26: (1000, "full"), # 1000BASE-SX full duplex mode
        27: (1000, "half"), # 1000BASE-CX half duplex mode
        28: (1000, "full"), # 1000BASE-CX full duplex mode
        29: (1000, "half"), # 1000BASE-T half duplex mode
        30: (1000, "full"), # 1000BASE-T full duplex mode

        31: (10000, "full"), # 10GBASE-X
        32: (10000, "full"), # 10GBASE-LX4
        33: (10000, "full"), # 10GBASE-R
        34: (10000, "full"), # 10GBASE-ER
        35: (10000, "full"), # 10GBASE-LR
        36: (10000, "full"), # 10GBASE-SR
        37: (10000, "full"), # 10GBASE-W
        38: (10000, "full"), # 10GBASE-EW
        39: (10000, "full"), # 10GBASE-LW
        40: (10000, "full"), # 10GBASE-SW
        }

    def gotDuplex(self, results):
        """Got MAU type which contains speed and duplex"""
        for oid in results:
            port = int(oid.split(".")[-1])
            mau = results[oid]
            if mau in self.mau:
                self.speed[port] = self.mau[mau][0]
                if self.mau[mau][1]:
                    self.duplex[port] = self.mau[mau][1]

    def gotAutoneg(self, results):
        """Callback handling autoneg"""
        for oid in results:
            port = int(oid.split(".")[-1])
            self.autoneg[port] = bool(results[oid] == 1)
