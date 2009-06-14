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

    def __init__(self, equipment, proxy, normPort=None):
        self.proxy = proxy
        self.equipment = equipment
        self.normport = normPort

    def completeEquipment(self):
        """Complete the equipment with data collected"""
        for port in self.speed:
            if self.normport and self.normport(port) is not None:
                nport = self.equipment.ports[self.normport(port)]
            else:
                nport = self.equipment.ports[port]
            nport.speed = self.speed[port]
            nport.autoneg = self.autoneg.get(port, None)
            nport.duplex = self.duplex.get(port, None)

    def collectData(self):
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
        d.addCallback(lambda _: self.completeEquipment())
        return d
        
