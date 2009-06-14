from zope.interface import implements
from twisted.plugin import IPlugin

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.port import PortCollector
from wiremaps.collector.arp import ArpCollector

class NetscreenISG:
    """Collector for Netscreen ISG"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return (oid in ['.1.3.6.1.4.1.3224.1.16', # ISG-2000
                        '.1.3.6.1.4.1.3224.1.28', # ISG-1000
                        '.1.3.6.1.4.1.3224.1.10', # Netscreen 208
                        ])

    def collectData(self, ip, proxy, dbpool):
        ports = PortCollector(proxy, dbpool)
        arp = ArpCollector(proxy, dbpool, self.config)
        d = ports.collectData()
        d.addCallback(lambda x: arp.collectData())
        return d

netscreen = NetscreenISG()
