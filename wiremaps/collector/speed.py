class SpeedCollector:
    """Collect speed/duplex/autoneg from 3 OID.

    Methods C{gotSpeed}, C{gotDuplex} and C{gotAutoneg} should be
    implemented. c{oidDuplex}, c{oidSpeed} and c{oidAutoneg}
    attributes should be defined.
    """

    def gotSpeed(self, results):
        raise NotImplementedError
    def gotAutoneg(self, results):
        raise NotImplementedError
    def gotDuplex(self, results):
        raise NotImplementedError

    def __init__(self, proxy, dbpool, normPort=None):
        self.proxy = proxy
        self.dbpool = dbpool
        self.normport = normPort

    def collectData(self):

        def filePortIntoDb(txn, duplex, speed, autoneg, ip):
            txn.execute("SELECT index FROM port WHERE equipment=%(ip)s",
                        {'ip': str(ip)})
            for (port,) in txn.fetchall():
                if self.normport:
                    oport = self.normport(port)
                else:
                    oport = port
                if oport:
                    txn.execute("UPDATE port "
                                "SET duplex=%(duplex)s, autoneg=%(autoneg)s, speed=%(speed)s "
                                "WHERE equipment=%(ip)s AND index=%(port)s",
                                {'ip': str(ip),
                                 'port': port,
                                 'duplex': duplex.get(oport, None),
                                 'speed': speed.get(oport, None),
                                 'autoneg': autoneg.get(oport, None)})

        print "Collecting port speed/duplex for %s" % self.proxy.ip
        self.speed = {}
        self.duplex = {}
        self.autoneg = {}
        d = self.proxy.walk(self.oidDuplex)
        d.addCallback(self.gotDuplex)
        d.addCallback(lambda x: self.proxy.walk(self.oidSpeed))
        d.addCallback(self.gotSpeed)
        d.addCallback(lambda x: self.proxy.walk(self.oidAutoneg))
        d.addCallback(self.gotAutoneg)
        d.addCallback(lambda x: self.dbpool.runInteraction(filePortIntoDb,
                                                           self.duplex,
                                                           self.speed,
                                                           self.autoneg,
                                                           self.proxy.ip))
        return d
        
