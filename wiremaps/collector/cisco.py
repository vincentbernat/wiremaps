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
        ports = PortCollector(proxy, dbpool)
        arp = ArpCollector(proxy, dbpool, self.config)
        fdb = FdbCollector(proxy, dbpool, self.config)
        cdp = CdpCollector(proxy, dbpool)
        d = ports.collectData()
        d.addCallback(lambda x: arp.collectData(write=False))
        d.addCallback(lambda x: fdb.collectData(write=False))
        d.addCallback(lambda x: cdp.collectData())
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: fdb.collectData())
        return d

cisco = Cisco()
