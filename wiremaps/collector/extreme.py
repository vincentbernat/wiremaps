from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.port import PortCollector
from wiremaps.collector.fdb import FdbCollector, ExtremeFdbCollector
from wiremaps.collector.arp import ArpCollector
from wiremaps.collector.lldp import LldpCollector

class ExtremeSummit:
    """Collector for Extreme Summit and BlackDiamond 8810 switches"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return (oid in ['.1.3.6.1.4.1.1916.2.40', # Extreme Summit 24e
                        '.1.3.6.1.4.1.1916.2.54', # Extreme Summit 48e
                        '.1.3.6.1.4.1.1916.2.62', # Black Diamond 8810
                        '.1.3.6.1.4.1.1916.2.76', # Extreme Summit 48t
                        ])

    def collectData(self, ip, proxy, dbpool):
        ports = PortCollector(proxy, dbpool)
        fdb = FdbCollector(proxy, dbpool)
        arp = ArpCollector(proxy, dbpool)
        # LLDP disabled due to unstability
        # lldp = LldpCollector(proxy, dbpool)
        d = ports.collectData()
        d.addCallback(lambda x: fdb.collectData(write=False))
        d.addCallback(lambda x: arp.collectData(write=False))
        # d.addCallback(lambda x: lldp.collectData())
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        return d

class ExtremeWare:
    """Collector for BlackDiamond 6808"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return (oid in ['.1.3.6.1.4.1.1916.2.11', # Black Diamond 6808 (ExtremeWare)
                        ])

    def collectData(self, ip, proxy, dbpool):
        ports = PortCollector(proxy, dbpool)
        fdb = ExtremeFdbCollector(proxy, dbpool)
        arp = ArpCollector(proxy, dbpool)
        # LLDP disabled due to unstability
        # lldp = LldpCollector(proxy, dbpool)
        d = ports.collectData()
        d.addCallback(lambda x: fdb.collectData(write=False))
        d.addCallback(lambda x: arp.collectData(write=False))
        # d.addCallback(lambda x: lldp.collectData())
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        return d

summit = ExtremeSummit()
blackdiamond = ExtremeWare()
