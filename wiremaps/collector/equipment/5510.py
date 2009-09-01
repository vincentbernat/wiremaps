from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.helpers.port import PortCollector
from wiremaps.collector.helpers.fdb import FdbCollector
from wiremaps.collector.helpers.arp import ArpCollector
from wiremaps.collector.helpers.sonmp import SonmpCollector
from wiremaps.collector.helpers.lldp import LldpCollector
from wiremaps.collector.helpers.vlan import VlanCollector
from wiremaps.collector.helpers.nortel import NortelSpeedCollector

class Nortel5510:
    """Collector for Nortel Baystack-like switchs (55xx, 425, etc.)"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return oid.startswith('.1.3.6.1.4.1.45.3.')

    def normPortName(self, port):
        try:
            return port.split(" - ")[1].strip()
        except:
            return port

    def collectData(self, equipment, proxy):
        ports = PortCollector(equipment, proxy, self.normPortName)
        speed = NortelSpeedCollector(equipment, proxy)
        fdb = FdbCollector(equipment, proxy, self.config)
        arp = ArpCollector(equipment, proxy, self.config)
        lldp = LldpCollector(equipment, proxy)
        sonmp = SonmpCollector(equipment, proxy)
        vlan = NortelVlanCollector(equipment, proxy,
                                   normPort=lambda x: x-1)
        d = ports.collectData()
        d.addCallback(lambda x: speed.collectData())
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: lldp.collectData())
        d.addCallback(lambda x: sonmp.collectData())
        d.addCallback(lambda x: vlan.collectData())
        return d

n5510 = Nortel5510()

class NortelVlanCollector(VlanCollector):
    """Collect VLAN information for Nortel switchs without LLDP"""
    oidVlanNames = '.1.3.6.1.4.1.2272.1.3.2.1.2' # rcVlanName
    oidVlanPorts = '.1.3.6.1.4.1.2272.1.3.2.1.13' # rcVlanStaticMembers
