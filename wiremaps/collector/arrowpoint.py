from zope.interface import implements
from twisted.plugin import IPlugin

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.port import PortCollector
from wiremaps.collector.arp import ArpCollector

class ArrowPoint:
    """Collector for Arrowpoint Content Switch (no FDB)"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return (oid in ['.1.3.6.1.4.1.2467.4.2', # CS-800
                        '.1.3.6.1.4.1.2467.4.3', # CS-1100
                        ])

    def normPortName(self, port):
        return "Port %s" % port

    def collectData(self, ip, proxy, dbpool):
        ports = PortCollector(proxy, dbpool, self.normPortName)
        arp = ArpCollector(proxy, dbpool, self.config)
        d = ports.collectData()
        d.addCallback(lambda x: arp.collectData(write=False))
        d.addCallback(lambda x: arp.collectData())
        return d

arrow = ArrowPoint()
