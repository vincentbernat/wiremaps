from wiremaps.collector import exception

class LldpCollector:
    """Collect data using LLDP"""

    lldpRemPortDesc = '.1.0.8802.1.1.2.1.4.1.1.8'
    lldpRemSysName = '.1.0.8802.1.1.2.1.4.1.1.9'
    lldpRemSysDesc = '.1.0.8802.1.1.2.1.4.1.1.10'
    lldpRemManAddrIfId = '.1.0.8802.1.1.2.1.4.2.1.4'
    lldpLocPortId = '.1.0.8802.1.1.2.1.3.7.1.3'

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

    def gotLldpLocPort(self, results):
        """Callback handling reception of LLDP Local Port ID

        @param results: result of walking C{LLDP-MIB::lldpLocPortId}
        """
        self.lldpValidPorts = []
        if not results:
            raise exception.NoLLDP("LLDP does not seem to be running")
        for oid in results:
            port =int(oid.split(".")[-1])
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
        """Collect data from SNMP using s5EnMsTopNmmSegId"""
    
        def fileIntoDb(txn, sysname, sysdesc, portdesc, mgmtip, ip):
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
        d.addCallback(lambda x: self.dbpool.runInteraction(fileIntoDb,
                                                           self.lldpSysName,
                                                           self.lldpSysDesc,
                                                           self.lldpPortDesc,
                                                           self.lldpMgmtIp,
                                                           self.proxy.ip))
        return d
