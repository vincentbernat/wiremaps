from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.datastore import LocalVlan
from wiremaps.collector.helpers.port import PortCollector
from wiremaps.collector.helpers.arp import ArpCollector
from wiremaps.collector.helpers.fdb import CommunityFdbCollector
from wiremaps.collector.helpers.cdp import CdpCollector

class Cisco:
    """Collector for Cisco (including Cisco CSS)"""

    implements(ICollector, IPlugin)

    def __init__(self, css=False):
        self.css = css

    def handleEquipment(self, oid):
        if oid.startswith('.1.3.6.1.4.1.9.'):
            # Cisco
            if oid.startswith('.1.3.6.1.4.1.9.9.368.'):
                # Css
                return self.css
            # Not a Css
            return not(self.css)
        return False


    def collectData(self, equipment, proxy):
        # On Cisco, ifName is more revelant than ifDescr, especially
        # on Catalyst switches. This is absolutely not the case for a CSS.
        t = {}
        trunk = CiscoTrunkCollector(equipment, proxy, t)
        if self.css:
            ports = PortCollector(equipment, proxy, trunk=t)
        else:
            ports = PortCollector(equipment, proxy, trunk=t,
                                  names="ifDescr", descrs="ifName")
            ports.ifDescr = ports.ifAlias
        fdb = CiscoFdbCollector(equipment, proxy, self.config)
        arp = ArpCollector(equipment, proxy, self.config)
        cdp = CdpCollector(equipment, proxy)
        vlan = CiscoVlanCollector(equipment, proxy, ports)
        d = trunk.collectData()
        d.addCallback(lambda x: ports.collectData())
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: cdp.collectData())
        d.addCallback(lambda x: vlan.collectData())
        return d

cisco = Cisco()
ciscoCss = Cisco(True)

class CiscoFdbCollector(CommunityFdbCollector):

    vlanName = '.1.3.6.1.4.1.9.9.46.1.3.1.1.4'
    filterOut = ["fddi-default", "token-ring-default",
                 "fddinet-default", "trnet-default"]

class CiscoTrunkCollector:
    """Collect trunk (i.e ether channel) information for Cisco switchs.

    This class uses C{CISCO-PAGP-MIB} which happens to provide
    necessary information.
    """

    pagpEthcOperationMode = '.1.3.6.1.4.1.9.9.98.1.1.1.1.1'
    pagpGroupIfIndex = '.1.3.6.1.4.1.9.9.98.1.1.1.1.8'

    def __init__(self, equipment, proxy, trunk):
        self.proxy = proxy
        self.equipment = equipment
        self.trunk = trunk

    def gotOperationMode(self, results):
        """Callback handling reception for port operation mode

        @param results: C{CISCO-PAGP-MIB::pagpEthcOperationMode}
        """
        self.trunked = []
        for oid in results:
            port = int(oid.split(".")[-1])
            if results[oid] != 1: # 1 = off
                self.trunked.append(port)

    def gotGroup(self, results):
        """Callback handling reception for port trunk group
        
        @param results: C{CISCO-PAGP-MIB::pagpGroupIfIndex}
        """
        for oid in results:
            port = int(oid.split(".")[-1])
            if port in self.trunked:
                if results[oid] not in self.trunk:
                    self.trunk[results[oid]] = [port]
                else:
                    self.trunk[results[oid]].append(port)
        # Filter out bogus results: trunk that are not yet trunks and trunk 0
        for k in self.trunk.keys():
            if k == 0:
                del self.trunk[0]
                continue
            if self.trunk[k] == [k]:
                del self.trunk[k]

    def collectData(self):
        """Collect cisco trunk information using C{CISCO-PAGP-MIB}"""
        print "Collecting trunk information for %s" % self.proxy.ip
        d = self.proxy.walk(self.pagpEthcOperationMode)
        d.addCallback(self.gotOperationMode)
        d.addCallback(lambda x: self.proxy.walk(self.pagpGroupIfIndex))
        d.addCallback(self.gotGroup)
        return d

class CiscoVlanCollector:
    """Collect VLAN information for Cisco switchs"""

    # Is trunking enabled? trunking(1)
    vlanTrunkPortDynamicStatus = '.1.3.6.1.4.1.9.9.46.1.6.1.1.14'
    # If yes, which VLAN are present on the given trunk
    vlanTrunkPortVlansEnabled = ['.1.3.6.1.4.1.9.9.46.1.6.1.1.4',
                                 '.1.3.6.1.4.1.9.9.46.1.6.1.1.17',
                                 '.1.3.6.1.4.1.9.9.46.1.6.1.1.18',
                                 '.1.3.6.1.4.1.9.9.46.1.6.1.1.19']
    vlanTrunkPortNativeVlan = '.1.3.6.1.4.1.9.9.46.1.6.1.1.5'
    # If no, maybe the interface has a vlan?
    vmVlan = '.1.3.6.1.4.1.9.9.68.1.2.2.1.2'
    # Vlan names
    vtpVlanName = '.1.3.6.1.4.1.9.9.46.1.3.1.1.4'

    def __init__(self, equipment, proxy, ports):
        self.ports = ports
        self.equipment = equipment
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

    def gotTrunkVlans(self, results, index=0):
        """Callback handling reception of VLAN membership for a trunked port
        
        @param results: VLAN enabled for given port from
           C{CISCO-VTP-MIB::vlanTrunkPortVlansEnabledXX}
        @param index: which range the vlan are in (0 for 0 to 1023,
           1 for 1024 to 2047, 2 for 2048 to 3071 and 3 for 3072 to
           4095)
        """
        for oid in results:
            port = int(oid.split(".")[-1])
            if port in self.trunked:
                if port not in self.vlans:
                    self.vlans[port] = []
                for i in range(0, len(results[oid])):
                    if ord(results[oid][i]) == 0:
                            continue
                    for j in range(0, 8):
                        if ord(results[oid][i]) & (1 << j):
                            self.vlans[port].append(7-j + 8*i + index*1024)
    
    def gotNativeVlan(self, results):
        """Callback handling reception of native VLAN for a port

        @param results: native VLAN from
           C{CISCO-VTP-MIB::vlanTrunkPortNativeVlan} or
           C{CISCO-VLAN-MEMBERSHIP-MIB::vmVlan}
        """
        for oid in results:
            port = int(oid.split(".")[-1])
            if port not in self.vlans:
                self.vlans[port] = [results[oid]]

    def completeEquipment(self):
        """Use collected data to populate C{self.equipments}"""
        for port in self.vlans:
            if port not in self.ports.portNames:
                continue
            for vid in self.vlans[port]:
                if vid not in self.names:
                    continue
                self.equipment.ports[port].vlan.append(
                    LocalVlan(vid, self.names[vid]))

    def collectData(self):
        """Collect VLAN data from SNMP"""
        print "Collecting VLAN information for %s" % self.proxy.ip
        self.trunked = []
        self.vlans = {}
        self.names = {}
        d = self.proxy.walk(self.vtpVlanName)
        d.addCallback(self.gotVlanNames)
        d.addCallback(lambda x: self.proxy.walk(self.vlanTrunkPortDynamicStatus))
        d.addCallback(self.gotTrunkStatus)
        for v in self.vlanTrunkPortVlansEnabled:
            d.addCallback(lambda x,vv: self.proxy.walk(vv), v)
            d.addCallback(self.gotTrunkVlans, self.vlanTrunkPortVlansEnabled.index(v))
        d.addCallback(lambda x: self.proxy.walk(self.vmVlan))
        d.addCallback(self.gotNativeVlan)
        d.addCallback(lambda x: self.proxy.walk(self.vlanTrunkPortNativeVlan))
        d.addCallback(self.gotNativeVlan)
        d.addCallback(lambda _: self.completeEquipment())
        return d
