from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.port import PortCollector
from wiremaps.collector.fdb import FdbCollector
from wiremaps.collector.arp import ArpCollector

class NortelEthernetSwitch:
    """Collector for Nortel Ethernet Switch Module for BladeCenter"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return (oid in ['.1.3.6.1.4.1.1872.1.18.1', # Nortel Layer2-3 GbE Switch Module(Copper)
                        '.1.3.6.1.4.1.1872.1.18.3', # Nortel 10Gb Uplink Ethernet Switch Module
                        ])

    def collectData(self, ip, proxy, dbpool):
        proxy.use_getbulk = False # Some Blade have bogus GETBULK
        ports = PortCollector(proxy, dbpool)
        fdb = FdbCollector(proxy, dbpool, self.config)
        arp = ArpCollector(proxy, dbpool, self.config)
        d = ports.collectData()
        d.addCallback(lambda x: fdb.collectData(write=False))
        d.addCallback(lambda x: arp.collectData(write=False))
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        return d

blade = NortelEthernetSwitch()
