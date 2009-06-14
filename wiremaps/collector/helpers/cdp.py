from wiremaps.collector import exception

class CdpCollector:
    """Collect data using CDP"""

    cdpCacheDeviceId = '.1.3.6.1.4.1.9.9.23.1.2.1.1.6'
    cdpCacheDevicePort = '.1.3.6.1.4.1.9.9.23.1.2.1.1.7'
    cdpCachePlatform = '.1.3.6.1.4.1.9.9.23.1.2.1.1.8'
    cdpCacheAddress = '.1.3.6.1.4.1.9.9.23.1.2.1.1.4'
    cdpCacheAddressType = '.1.3.6.1.4.1.9.9.23.1.2.1.1.3'

    def __init__(self, proxy, dbpool):
        """Create a collector using CDP entries in SNMP.

        @param proxy: proxy to use to query SNMP
        @param dbpool: pool of database connections
        """
        self.proxy = proxy
        self.dbpool = dbpool

    def gotCdp(self, results, dic):
        """Callback handling reception of CDP

        @param results: result of walking C{CISCO-CDP-MIB::cdpCacheXXXX}
        @param dic: dictionary where to store the result
        """
        for oid in results:
            port = int(oid[len(self.cdpCacheDeviceId):].split(".")[1])
            desc = results[oid]
            if desc and port is not None:
                dic[port] = desc

    def collectData(self):
        """Collect CDP data from SNMP"""
    
        def fileIntoDb(txn, sysname, portname, platform, mgmtiptype, mgmtip, ip):
            txn.execute("UPDATE cdp SET deleted=CURRENT_TIMESTAMP "
                        "WHERE equipment=%(ip)s AND deleted='infinity'",
                        {'ip': str(ip)})
            for port in sysname.keys():
                if mgmtiptype[port] != 1:
                    mgmtip[port] = "0.0.0.0"
                else:
                    mgmtip[port] = ".".join(str(ord(i)) for i in mgmtip[port])
                txn.execute("INSERT INTO cdp VALUES (%(ip)s, "
                            "%(port)s, %(sysname)s, %(portname)s, "
                            "%(mgmtip)s, %(platform)s)",
                            {'ip': str(ip),
                             'port': port,
                             'sysname': sysname[port],
                             'portname': portname[port],
                             'platform': platform[port],
                             'mgmtip': mgmtip[port]})

        print "Collecting CDP for %s" % self.proxy.ip
        self.cdpDeviceId = {}
        self.cdpDevicePort = {}
        self.cdpPlatform = {}
        self.cdpAddressType = {}
        self.cdpAddress = {}
        d = self.proxy.walk(self.cdpCacheDeviceId)
        d.addCallback(self.gotCdp, self.cdpDeviceId)
        for y in ["DevicePort", "Platform", "AddressType", "Address"]:
            d.addCallback(lambda x,z: self.proxy.walk(getattr(self, "cdpCache%s" % z)), y)
            d.addCallback(self.gotCdp, getattr(self, "cdp%s" % y))
        d.addCallback(lambda x: self.dbpool.runInteraction(fileIntoDb,
                                                           self.cdpDeviceId,
                                                           self.cdpDevicePort,
                                                           self.cdpPlatform,
                                                           self.cdpAddressType,
                                                           self.cdpAddress,
                                                           self.proxy.ip))
        return d
