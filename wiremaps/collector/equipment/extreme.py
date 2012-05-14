from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.datastore import LocalVlan
from wiremaps.collector.helpers.port import PortCollector
from wiremaps.collector.helpers.fdb import FdbCollector, ExtremeFdbCollector
from wiremaps.collector.helpers.arp import ArpCollector
from wiremaps.collector.helpers.lldp import LldpCollector
from wiremaps.collector.helpers.edp import EdpCollector
from wiremaps.collector.helpers.vlan import IfMibVlanCollector

class ExtremeSummit:
    """Collector for Extreme switches and routers"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return (oid in ['.1.3.6.1.4.1.1916.2.28', # Extreme Summit 48si
                        '.1.3.6.1.4.1.1916.2.54', # Extreme Summit 48e
                        '.1.3.6.1.4.1.1916.2.76', # Extreme Summit 48t
                        '.1.3.6.1.4.1.1916.2.62', # Black Diamond 8810
                        ])

    def vlanFactory(self):
        return ExtremeVlanCollector

    def collectData(self, equipment, proxy):
        ports = PortCollector(equipment, proxy,
                              names="ifDescr", descrs="ifName")
        fdb = FdbCollector(equipment, proxy, self.config)
        arp = ArpCollector(equipment, proxy, self.config)
        edp = EdpCollector(equipment, proxy)
        vlan = self.vlanFactory()(equipment, proxy)
        # LLDP disabled due to unstability
        # lldp = LldpCollector(equipment, proxy)
        d = ports.collectData()
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: edp.collectData())
        d.addCallback(lambda x: vlan.collectData())
        # d.addCallback(lambda x: lldp.collectData())
        return d

class OldExtremeSummit(ExtremeSummit):
    """Collector for old Extreme summit switches"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return (oid in ['.1.3.6.1.4.1.1916.2.40', # Extreme Summit 24e
                        ])

    def vlanFactory(self):
        return IfMibVlanCollector

class ExtremeWare:
    """Collector for ExtremeWare chassis"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return (oid in ['.1.3.6.1.4.1.1916.2.11', # Black Diamond 6808 (ExtremeWare)
                        ])

    def collectData(self, equipment, proxy):
        ports = PortCollector(equipment, proxy,
                              names="ifDescr", descrs="ifName")
        vlan = ExtremeVlanCollector(equipment, proxy)
        fdb = ExtremeFdbCollector(vlan, equipment, proxy, self.config)
        arp = ArpCollector(equipment, proxy, self.config)
        edp = EdpCollector(equipment, proxy)
        # LLDP disabled due to unstability
        # lldp = LldpCollector(equipment, proxy)
        d = ports.collectData()
        d.addCallback(lambda x: vlan.collectData())
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: edp.collectData())
        # d.addCallback(lambda x: lldp.collectData())
        return d

class ExtremeVlanCollector:
    """Collect local VLAN for Extreme switchs"""

    vlanIfDescr = '.1.3.6.1.4.1.1916.1.2.1.2.1.2'
    vlanIfVlanId = '.1.3.6.1.4.1.1916.1.2.1.2.1.10'
    vlanOpaque = '.1.3.6.1.4.1.1916.1.2.6.1.1'
    extremeSlotNumber = '.1.3.6.1.4.1.1916.1.1.2.2.1.1'

    def __init__(self, equipment, proxy):
        self.proxy = proxy
        self.equipment = equipment

    def gotVlan(self, results, dic):
        """Callback handling reception of VLAN

        @param results: C{EXTREME-VLAN-MIB::extremeVlanXXXX}
        @param dic: where to store the results
        """
        for oid in results:
            vid = int(oid.split(".")[-1])
            dic[vid] = results[oid]

    def gotVlanMembers(self, results):
        """Callback handling reception of VLAN members

        @param results: C{EXTREME-VLAN-MIB::ExtremeVlanOpaqueEntry}
        """
        for oid in results:
            slot = int(oid.split(".")[-1])
            vlan = int(oid.split(".")[-2])
            ports = results[oid]
            l = self.vlanPorts.get(vlan, [])
            for i in range(0, len(ports)):
                if ord(ports[i]) == 0:
                    continue
                for j in range(0, 8):
                    if ord(ports[i]) & (1 << j):
                        if self.slots:
                            l.append(8-j + 8*i + 1000*slot)
                        else:
                            l.append(8-j + 8*i)
            self.vlanPorts[vlan] = l

        # Add all this to C{self.equipment}
        for vid in self.vlanDescr:
            if vid in self.vlanId and vid in self.vlanPorts:
                for port in self.vlanPorts[vid]:
                    self.equipment.ports[port].vlan.append(
                        LocalVlan(self.vlanId[vid],
                                  self.vlanDescr[vid]))

    def gotSlots(self, results):
        """Callback handling reception of slots

        @param results: C{EXTREME-SYSTEM-MIB::extremeSlotNumber}
        """
        self.slots = len(results)

    def collectData(self):
        """Collect VLAN data from SNMP"""
        print "Collecting VLAN information for %s" % self.proxy.ip
        self.vlanDescr = {}
        self.vlanId = {}
        self.vlanPorts = {}
        self.slots = 0
        d = self.proxy.walk(self.vlanIfDescr)
        d.addCallback(self.gotVlan, self.vlanDescr)
        d.addCallback(lambda x: self.proxy.walk(self.vlanIfVlanId))
        d.addCallback(self.gotVlan, self.vlanId)
        d.addCallback(lambda x: self.proxy.walk(self.extremeSlotNumber))
        d.addCallback(self.gotSlots)
        d.addCallback(lambda x: self.proxy.walk(self.vlanOpaque))
        d.addCallback(self.gotVlanMembers)
        return d

osummit = OldExtremeSummit()
summit = ExtremeSummit()
eware = ExtremeWare()
