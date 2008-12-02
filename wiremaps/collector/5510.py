from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.port import PortCollector
from wiremaps.collector.fdb import FdbCollector
from wiremaps.collector.arp import ArpCollector
from wiremaps.collector.sonmp import SonmpCollector
from wiremaps.collector.lldp import LldpCollector
from wiremaps.collector.vlan import VlanCollector
from wiremaps.collector.nortel import NortelSpeedCollector

class Nortel5510:
    """Collector for Nortel 55x0 and Nortel 425"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return (oid in ['.1.3.6.1.4.1.45.3.52.1', # 5510-24T
                        '.1.3.6.1.4.1.45.3.53.1', # 5510-48T
                        '.1.3.6.1.4.1.45.3.59.1', # 5520-24T-PWR
                        '.1.3.6.1.4.1.45.3.59.2', # 5520-48T-PWR
                        '.1.3.6.1.4.1.45.3.57.1', # 425-48T
                        '.1.3.6.1.4.1.45.3.57.2', # 425-24T
                        '.1.3.6.1.4.1.45.3.65', # 5530-24TFD
                        ])

    def normPortName(self, port):
        try:
            return port.split(" - ")[1].strip()
        except:
            return port

    def collectData(self, ip, proxy, dbpool):
        ports = PortCollector(proxy, dbpool, self.normPortName)
        speed = NortelSpeedCollector(proxy, dbpool)
        fdb = FdbCollector(proxy, dbpool, self.config)
        arp = ArpCollector(proxy, dbpool, self.config)
        lldp = LldpCollector(proxy, dbpool)
        sonmp = SonmpCollector(proxy, dbpool)
        vlan = NortelVlanCollector(proxy, dbpool,
                                   normPort=lambda x: x-1,
                                   clean=False) # cleaning is done by LLDP
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
