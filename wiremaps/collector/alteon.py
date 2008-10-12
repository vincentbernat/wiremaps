from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.port import PortCollector
from wiremaps.collector.fdb import FdbCollector
from wiremaps.collector.arp import ArpCollector
from wiremaps.collector.sonmp import SonmpCollector

class Alteon2208:
    """Collector for Nortel Alteon 2208 and related"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return (oid in ['.1.3.6.1.4.1.1872.1.13.1.5', # Alteon 2208
                        '.1.3.6.1.4.1.1872.1.13.1.9', # Alteon 2208 E
                        '.1.3.6.1.4.1.1872.1.13.2.1', # Alteon 3408
                        ])

    def normPortName(self, descr):
        try:
            port = int(descr)
        except:
            return descr
        if port == 999:
            return "Management"
        return "Port %d" % (port - 256)

    def normPortIndex(self, port):
        """Normalize port index.
        """
        if port >= 1:
            return port + 256
        return None

    def collectData(self, ip, proxy, dbpool):
        ports = PortCollector(proxy, dbpool, self.normPortName)
        ports.ifName = ports.ifDescr
        ports.ifDescr = '.1.3.6.1.2.1.2.2.1.1' # ifIndex
        fdb = FdbCollector(proxy, dbpool, self.config)
        arp = ArpCollector(proxy, dbpool, self.config)
        sonmp = SonmpCollector(proxy, dbpool, self.normPortIndex)
        d = ports.collectData()
        d.addCallback(lambda x: fdb.collectData(write=False))
        d.addCallback(lambda x: arp.collectData(write=False))
        d.addCallback(lambda x: sonmp.collectData())
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        return d

alteon = Alteon2208()
