from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.port import PortCollector
from wiremaps.collector.fdb import FdbCollector
from wiremaps.collector.arp import ArpCollector
from wiremaps.collector.lldp import LldpCollector

class Procurve:
    """Collector for HP Procurve switches"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        # Complete list is in hpicfOid.mib
        return oid.startswith('.1.3.6.1.4.1.11.2.3.7.11.')

    def collectData(self, ip, proxy, dbpool):
        ports = PortCollector(proxy, dbpool)
        fdb = FdbCollector(proxy, dbpool, self.config)
        arp = ArpCollector(proxy, dbpool, self.config)
        lldp = LldpCollector(proxy, dbpool)
        d = ports.collectData()
        d.addCallback(lambda x: fdb.collectData(write=False))
        d.addCallback(lambda x: arp.collectData(write=False))
        d.addCallback(lambda x: lldp.collectData())
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        return d

procurve = Procurve()
