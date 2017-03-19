from zope.interface import implements
from twisted.plugin import IPlugin

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.helpers.port import PortCollector
from wiremaps.collector.helpers.fdb import QFdbCollector
from wiremaps.collector.helpers.arp import ArpCollector
from wiremaps.collector.helpers.lldp import LldpCollector, LldpSpeedCollector
from wiremaps.collector.helpers.vlan import Rfc2674StaticVlanCollector


class HH3C:
    """Collector for Hangzhou H3C switches switches"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return oid.startswith('.1.3.6.1.4.1.25506.11.1.')

    def normport(self, port, ports):
        if port not in ports.portNames:
            return None
        return port

    def collectData(self, equipment, proxy):
        ports = PortCollector(equipment, proxy)
        fdb = QFdbCollector(equipment, proxy, self.config,
                            lambda x: self.normport(x, ports))
        arp = ArpCollector(equipment, proxy, self.config)
        lldp = LldpCollector(equipment, proxy)
        speed = LldpSpeedCollector(equipment, proxy)
        vlan = Rfc2674StaticVlanCollector(
            equipment, proxy,
            normPort=lambda x: self.normport(x, ports))
        d = ports.collectData()
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: lldp.collectData())
        d.addCallback(lambda x: speed.collectData())
        d.addCallback(lambda x: vlan.collectData())
        return d


hh3c = HH3C()
