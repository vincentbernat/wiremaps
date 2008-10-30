from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.port import PortCollector
from wiremaps.collector.fdb import FdbCollector
from wiremaps.collector.arp import ArpCollector

class SuperStack:
    """Collector for 3Com SuperStack switches"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return (oid in ['.1.3.6.1.4.1.43.10.27.4.1.2.2', # 3Com SuperStack II/3
                        '.1.3.6.1.4.1.43.10.27.4.1.2.4', # 3Com SuperStack 3
                        '.1.3.6.1.4.1.43.10.27.4.1.2.11', # 3Com SuperStack 3
                        ])

    def normPortName(self, descr):
        if descr.startswith("RMON:10/100 "):
            return descr[len("RMON:10/100 "):]
        return descr

    def collectData(self, ip, proxy, dbpool):
        proxy.version = 1       # Use SNMPv1
        ports = PortCollector(proxy, dbpool, self.normPortName)
        fdb = FdbCollector(proxy, dbpool, self.config)
        arp = ArpCollector(proxy, dbpool, self.config)
        d = ports.collectData()
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        return d

superstack = SuperStack()
