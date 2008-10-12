from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.port import PortCollector
from wiremaps.collector.arp import ArpCollector
from wiremaps.collector.lldp import LldpCollector

class Linux:
    """Collector for Linux.

    It is assumed that they are running an LLDP agent. This agent will
    tell us which ports to use.
    """

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return (oid in ['.1.3.6.1.4.1.8072.3.2.10', # Net-SNMP Linux
                        '.1.3.6.1.4.1.3375.2.1.3.4.10', # F5 BIG IP 6400
                        ])

    def collectData(self, ip, proxy, dbpool):
        ports = PortCollector(proxy, dbpool)
        arp = ArpCollector(proxy, dbpool, self.config)
        lldp = LldpCollector(proxy, dbpool)
        d = ports.collectData()
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: lldp.collectData())
        d.addCallback(lambda x: lldp.cleanPorts())
        return d

linux = Linux()
