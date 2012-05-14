from twisted.internet import defer
from wiremaps.collector.datastore import Port, Trunk

class PortCollector:
    """Collect data about ports"""

    ifDescr = '.1.3.6.1.2.1.2.2.1.2'
    ifName = '.1.3.6.1.2.1.31.1.1.1.1'
    ifAlias = '.1.3.6.1.2.1.31.1.1.1.18'
    ifType = '.1.3.6.1.2.1.2.2.1.3'
    ifOperStatus = '.1.3.6.1.2.1.2.2.1.8'
    ifPhysAddress = '.1.3.6.1.2.1.2.2.1.6'
    ifSpeed = '.1.3.6.1.2.1.2.2.1.5'
    ifHighSpeed = '.1.3.6.1.2.1.31.1.1.1.15'

    def __init__(self, equipment, proxy,
                 normName=None, normPort=None, filter=None,
                 trunk=None, names="ifName", descrs="ifDescr"):
        """Create a collector for port information

        @param proxy: proxy to use to query SNMP
        @param equipment: equipment to complete
        @param normName: function to normalize port name
        @param normPort: function to normalize port index
        @param filter: filter out those ports
        @param trunk: collected trunk information (mapping trunk index -> list of members)
        @param names: MIB name for port names
        @param descrs: MIB name for port descriptions
        """
        self.proxy = proxy
        self.equipment = equipment
        self.normName = normName
        self.normPort = normPort
        self.filter = filter
        self.trunk = trunk
        self.names = names
        self.descrs = descrs

    def gotIfTypes(self, results):
        """Callback handling retrieving of interface types.

        @param result: result of walking on C{IF-MIB::ifType}
        """
        self.ports = []
        for oid in results:
            port = int(oid.split(".")[-1])
            if self.normPort is not None:
                port = self.normPort(port)
                if port is None:
                    continue
            if self.filter is not None and self.filter(port) is None:
                continue
            # Ethernet (ethernetCsmacd or some obsolote values) ?
            if results[oid] in [6,    # ethernetCsmacd
                                62,   # fastEther
                                69,   # fastEtherFX
                                117,  # gigabitEthernet
                                ] or (self.trunk and port in self.trunk):
                self.ports.append(port)

    def gotIfDescrs(self, results):
        """Callback handling retrieving of interface names.

        @param result: result of walking on C{IF-MIB::ifDescr}
        """
        self.portNames = {}
        for oid in results:
            port = int(oid.split(".")[-1])
            if self.normPort is not None:
                port = self.normPort(port)
            if port not in self.ports:
                continue
            descr = str(results[oid]).strip()
            if self.normName is not None:
                descr = self.normName(descr).strip()
            self.portNames[port] = descr

    def gotIfNames(self, results):
        """Callback handling retrieving of interface names.

        @param result: result of walking on C{IF-MIB::ifName}
        """
        self.portAliases = {}
        for oid in results:
            port = int(oid.split(".")[-1])
            if self.normPort is not None:
                port = self.normPort(port)
            if port not in self.ports:
                continue
            name = str(results[oid]).strip()
            if name:
                self.portAliases[port] = name

    def gotPhysAddress(self, results):
        """Callback handling retrieving of physical addresses.

        @param result: result of walking on C{IF-MIB::ifPhysAddress}
        """
        self.portAddress = {}
        for oid in results:
            port = int(oid.split(".")[-1])
            if self.normPort is not None:
                port = self.normPort(port)
            if port not in self.ports:
                continue
            address = [ "%x" % ord(a) for a in str(results[oid])]
            if address and len(address) == 6:
                self.portAddress[port] = ":".join(address)

    def gotOperStatus(self, results):
        """Callback handling retrieving of interface status.

        @param result: result of walking C{IF-MIB::ifOperStatus}
        """
        self.portStatus = {}
        for oid in results:
            port = int(oid.split(".")[-1])
            if self.normPort is not None:
                port = self.normPort(port)
            if port not in self.ports:
                continue
            if results[oid] == 1:
                self.portStatus[port] = 'up'
            else:
                self.portStatus[port] = 'down'

    def gotSpeed(self, results):
        """Callback handling retrieving of interface speed.

        @param result: result of walking C{IF-MIB::ifSpeed}
        """
        self.speed = {}
        for oid in results:
            port = int(oid.split(".")[-1])
            if self.normPort is not None:
                port = self.normPort(port)
            if port not in self.ports:
                continue
            s = results[oid]
            if s == 2**32 - 1:
                # Overflow, let's say that it is 10G
                s = 10000
            else:
                s /= 1000000
            if s:
                self.speed[port] = s

    def gotHighSpeed(self, results):
        """Callback handling retrieving of interface high speed.

        @param result: result of walking C{IF-MIB::ifHighSpeed}
        """
        for oid in results:
            port = int(oid.split(".")[-1])
            if self.normPort is not None:
                port = self.normPort(port)
            if port not in self.ports:
                continue
            s = results[oid]
            if s:
                self.speed[port] = s

    def completeEquipment(self):
        """Complete C{self.equipment} with data collected"""
        tmp = self.portAliases.copy()
        tmp.update(self.portNames)
        self.portNames = tmp
        for port in self.portNames:
            self.equipment.ports[port] = Port(self.portNames[port],
                                              self.portStatus[port],
                                              self.portAliases.get(port, None),
                                              self.portAddress.get(port, None),
                                              self.speed.get(port, None))
        if self.trunk:
            for t in self.trunk:
                for port in self.trunk[t]:
                    self.equipment.ports[port].trunk = Trunk(t)

    def collectData(self):
        """Collect data.

        - Using IF-MIB::ifDescr for port name
          and index
        - Using IF-MIB::ifOperStatus for port status
        """
        print "Collecting port information for %s" % self.proxy.ip
        d = self.proxy.walk(self.ifType)
        d.addCallback(self.gotIfTypes)
        d.addCallback(lambda x: self.proxy.walk(getattr(self,self.descrs)))
        d.addCallback(self.gotIfDescrs)
        d.addCallback(lambda x: self.proxy.walk(getattr(self,self.names)))
        d.addCallback(self.gotIfNames)
        d.addCallback(lambda x: self.proxy.walk(self.ifOperStatus))
        d.addCallback(self.gotOperStatus)
        d.addCallback(lambda x: self.proxy.walk(self.ifPhysAddress))
        d.addCallback(self.gotPhysAddress)
        d.addCallback(lambda x: self.proxy.walk(self.ifSpeed))
        d.addCallback(self.gotSpeed)
        d.addCallback(lambda x: self.proxy.walk(self.ifHighSpeed))
        d.addCallback(self.gotHighSpeed)
        d.addCallback(lambda _: self.completeEquipment())
        return d
