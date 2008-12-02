class VlanCollector:
    """Collect VLAN information.

    This class supports any switch that stores VLAN information in tow
    OID. The first OID contains VLAN names (with VLAN ID as index) and
    the second contains VLAN ports as a bitmask with VLAN ID as index.

    This class should be inherited and instance or class variables
    C{oidVlanNames} and C{oidVlanPorts} should be defined.
    """

    def __init__(self, proxy, dbpool, normPort=None, clean=True):
        self.proxy = proxy
        self.dbpool = dbpool
        self.normPort = normPort
        self.clean = clean

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
            if self.clean:
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

class Rfc2674VlanCollector(VlanCollector):
    """Collect VLAN information for switch that respects RFC 2674"""
    oidVlanNames = '.1.3.6.1.2.1.17.7.1.4.3.1.1' # dot1qVlanStaticName
    oidVlanPorts = '.1.3.6.1.2.1.17.7.1.4.2.1.4' # dot1qVlanCurrentEgressPorts

class IfMibVlanCollector:
    """Collect VLAN information using IF-MIB.

    To use this collector, VLAN should be enumerated in IF-MIB with
    ifType equal to l2vlan, ifDescr containing the tag number and
    ifStackStatus allowing to link those VLAN to real ports.

    There seems to be no way to get VLAN names.

    For example, on old Extreme Summit:
      IF-MIB::ifDescr.29 = STRING: 802.1Q Encapsulation Tag 0103
      IF-MIB::ifType.29 = INTEGER: l2vlan(135)
      IF-MIB::ifStackStatus.29.4 = INTEGER: active(1)
      IF-MIB::ifStackStatus.29.5 = INTEGER: active(1)
    """

    ifStackStatus = '.1.3.6.1.2.1.31.1.2.1.3'
    ifType = '.1.3.6.1.2.1.2.2.1.3'
    ifDescr = '.1.3.6.1.2.1.2.2.1.2'

    def __init__(self, proxy, dbpool, normPort=None, clean=True):
        self.proxy = proxy
        self.dbpool = dbpool
        self.normPort = normPort
        self.clean = clean

    def gotIfType(self, results):
        """Callback handling reception of interface types

        @param results: walking C{IF-MIB::ifType}
        """
        for oid in results:
            if results[oid] == 135:
                self.vlans[int(oid.split(".")[-1])] = []

    def gotIfDescr(self, results):
        """Callback handling reception of interface descriptions

        @param results: walking C{IF-MIB::ifDescr}
        """
        for oid in results:
            port = int(oid.split(".")[-1])
            if port in self.vlans:
                tag = results[oid].split(" ")[-1]
                try:
                    self.vids[port] = int(tag)
                except ValueError:
                    continue

    def gotIfStackStatus(self, results):
        """Callback handling reception of stack information for vlans

        @param results: walking C{IF-MIB::ifStackStatus}
        """
        for oid in results:
            physport = int(oid.split(".")[-1])
            if physport == 0:
                continue
            vlanport = int(oid.split(".")[-2])
            if vlanport in self.vlans:
                self.vlans[vlanport].append(physport)

    def collectData(self):
        """Collect VLAN data from SNMP"""
    
        def fileVlanIntoDb(txn, vids, vlans, ip):
            if self.clean:
                txn.execute("DELETE FROM vlan WHERE equipment=%(ip)s AND type='local'",
                            {'ip': str(ip)})
            for id in vids:
                if id not in vlans:
                    continue
                for port in vlans[id]:
                    if self.normPort is not None:
                        port = self.normPort(port)
                    if port is not None:
                        txn.execute("INSERT INTO vlan VALUES (%(ip)s, "
                                    "%(port)s, %(vid)s, %(name)s, "
                                    "%(type)s)",
                                    {'ip': str(ip),
                                     'port': port,
                                     'vid': vids[id],
                                     'name': "VLAN %d" % vids[id],
                                     'type': 'local'})

        print "Collecting VLAN information for %s" % self.proxy.ip
        self.vids = {}
        self.vlans = {}
        d = self.proxy.walk(self.ifType)
        d.addCallback(self.gotIfType)
        d.addCallback(lambda x: self.proxy.walk(self.ifDescr))
        d.addCallback(self.gotIfDescr)
        d.addCallback(lambda x: self.proxy.walk(self.ifStackStatus))
        d.addCallback(self.gotIfStackStatus)
        d.addCallback(lambda x: self.dbpool.runInteraction(fileVlanIntoDb,
                                                           self.vids,
                                                           self.vlans,
                                                           self.proxy.ip))
        return d
