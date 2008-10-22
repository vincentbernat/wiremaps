from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.port import PortCollector
from wiremaps.collector.arp import ArpCollector
from wiremaps.collector.fdb import FdbCollector
from wiremaps.collector.cdp import CdpCollector

class Cisco:
    """Collector for Cisco"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return oid.startswith('.1.3.6.1.4.1.9.')

    def collectData(self, ip, proxy, dbpool):
        self.ports = PortCollector(proxy, dbpool)

        # On Cisco, ifName is more revelant than ifDescr, especially
        # on Catalyst switches
        tmp = self.ports.ifDescr
        self.ports.ifDescr = self.ports.ifName
        self.ports.ifName = tmp

        arp = ArpCollector(proxy, dbpool, self.config)
        fdb = FdbCollector(proxy, dbpool, self.config)
        cdp = CdpCollector(proxy, dbpool)
        vlan = CiscoVlanCollector(proxy, dbpool, self.ports)
        d = self.ports.collectData()
        d.addCallback(lambda x: arp.collectData(write=False))
        d.addCallback(lambda x: fdb.collectData(write=False))
        d.addCallback(lambda x: cdp.collectData())
        d.addCallback(lambda x: vlan.collectData())
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: fdb.collectData())
        return d

cisco = Cisco()

class CiscoVlanCollector:
    """Collect VLAN information for Cisco switchs"""

    # Is trunking enabled? trunking(1)
    vlanTrunkPortDynamicStatus = '.1.3.6.1.4.1.9.9.46.1.6.1.1.14'
    # If yes, which VLAN are present on the given trunk
    vlanTrunkPortVlansEnabled = '.1.3.6.1.4.1.9.9.46.1.6.1.1.4'
    # If no, what is the native VLAN?
    vmVlan = '.1.3.6.1.4.1.9.9.68.1.2.2.1.2'
    # Vlan names
    vtpVlanName = '.1.3.6.1.4.1.9.9.46.1.3.1.1.4'

    def __init__(self, proxy, dbpool, ports):
        self.ports = ports
        self.dbpool = dbpool
        self.proxy = proxy

    def gotVlanNames(self, results):
        """Callback handling reception of VLAN names

        @param results: vlan names from C{CISCO-VTP-MIB::vtpVlanName}
        """
        for oid in results:
            vid = int(oid.split(".")[-1])
            self.names[vid] = results[oid]

    def gotTrunkStatus(self, results):
        """Callback handling reception for trunk status for ports

        @param results: trunk status from C{CISCO-VTP-MIB::vlanTrunkPortDynamicStatus}
        """
        for oid in results:
            port = int(oid.split(".")[-1])
            if results[oid] == 1:
                self.trunked.append(port)

    def gotTrunkVlans(self, results):
        """Callback handling reception of VLAN membership for a trunked port
        
        @param results: VLAN enabled for given port from
           C{CISCO-VTP-MIB::vlanTrunkPortVlansEnabled}
        """
        for oid in results:
            port = int(oid.split(".")[-1])
            if port in self.trunked:
                self.vlans[port] = []
                for i in range(0, len(results[oid])):
                    if ord(results[oid][i]) == 0:
                            continue
                    for j in range(0, 8):
                        if ord(results[oid][i]) & (1 << j):
                            self.vlans[port].append(7-j + 8*i)
    
    def gotNativeVlan(self, results):
        """Callback handling reception of native VLAN for a port

        @param results: native VLAN from C{CISCO-VLAN-MEMBERSHIP-MIB::vmVlan}
        """
        for oid in results:
            port = int(oid.split(".")[-1])
            if port not in self.trunked:
                self.vlans[port] = [results[oid]]

    def collectData(self):
        """Collect VLAN data from SNMP"""
    
        def fileVlanIntoDb(txn, names, vlans, ip):
            txn.execute("DELETE FROM vlan WHERE equipment=%(ip)s AND type='local'",
                        {'ip': str(ip)})
            for port in vlans:
                if port not in self.ports.portNames:
                    continue
                for vid in vlans[port]:
                    if vid not in names:
                        continue
                    txn.execute("INSERT INTO vlan VALUES (%(ip)s, "
                                "%(port)s, %(vid)s, %(name)s, "
                                "%(type)s)",
                                {'ip': str(ip),
                                 'port': port,
                                 'vid': vid,
                                 'name': names[vid],
                                 'type': 'local'})

        print "Collecting VLAN information for %s" % self.proxy.ip
        self.trunked = []
        self.vlans = {}
        self.names = {}
        d = self.proxy.walk(self.vtpVlanName)
        d.addCallback(self.gotVlanNames)
        d.addCallback(lambda x: self.proxy.walk(self.vlanTrunkPortDynamicStatus))
        d.addCallback(self.gotTrunkStatus)
        d.addCallback(lambda x: self.proxy.walk(self.vlanTrunkPortVlansEnabled))
        d.addCallback(self.gotTrunkVlans)
        d.addCallback(lambda x: self.proxy.walk(self.vmVlan))
        d.addCallback(self.gotNativeVlan)
        d.addCallback(lambda x: self.dbpool.runInteraction(fileVlanIntoDb,
                                                           self.names,
                                                           self.vlans,
                                                           self.proxy.ip))
        return d
