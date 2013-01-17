from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.helpers.port import PortCollector
from wiremaps.collector.helpers.fdb import FdbCollector
from wiremaps.collector.helpers.arp import ArpCollector
from wiremaps.collector.helpers.lldp import LldpCollector, LldpSpeedCollector
from wiremaps.collector.helpers.vlan import Rfc2674VlanCollector

class Foundry:
    """
    Foundry/Brocade switches
    """

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return oid.startswith('.1.3.6.1.4.1.1991.1.3.35') # snFWSXFamily

    def collectData(self, equipment, proxy):
        ports = PortCollector(equipment, proxy, names="ifAlias", descrs="ifDescr")
        fdb = FdbCollector(equipment, proxy, self.config)
        arp = ArpCollector(equipment, proxy, self.config)
        lldp = LldpCollector(equipment, proxy)
        speed = LldpSpeedCollector(equipment, proxy)
        vlan = Rfc2674VlanCollector(equipment, proxy)
        d = ports.collectData()
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: lldp.collectData())
        d.addCallback(lambda x: speed.collectData())
        d.addCallback(lambda x: vlan.collectData())
        return d

foundry = Foundry()
