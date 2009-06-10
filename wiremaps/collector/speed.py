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
            txn.execute("UPDATE extendedport SET deleted=CURRENT_TIMESTAMP "
                        "WHERE equipment=%(ip)s AND deleted='infinity'",
                        {'ip': str(ip)})
            for port in speed:
                txn.execute("INSERT INTO extendedport "
                            "VALUES (%(ip)s, %(index)s, %(duplex)s, %(speed)s, %(autoneg)s)",
                            {'ip': str(ip),
                             'index': port,
                             'duplex': duplex.get(port, None),
                             'speed': speed[port],
                             'autoneg': autoneg.get(port, None)})

        print "Collecting port speed/duplex for %s" % self.proxy.ip
        self.speed = {}
        self.duplex = {}
        self.autoneg = {}
        d = self.proxy.walk(self.oidDuplex)
        d.addCallback(self.gotDuplex)
        if hasattr(self, "oidSpeed"):
            # Sometimes, speed comes with duplex
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
        
