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

    def normport(self, port):
        if port not in self.ports.portNames:
            return None
        return port

    def collectData(self, ip, proxy, dbpool):
        self.ports = PortCollector(proxy, dbpool)
        fdb = FdbCollector(proxy, dbpool, self.config, self.normport)
        arp = ArpCollector(proxy, dbpool, self.config)
        lldp = LldpCollector(proxy, dbpool)
        d = self.ports.collectData()
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: lldp.collectData())
        return d

procurve = Procurve()
