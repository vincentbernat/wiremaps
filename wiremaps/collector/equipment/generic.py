from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.port import PortCollector
from wiremaps.collector.fdb import FdbCollector
from wiremaps.collector.arp import ArpCollector
from wiremaps.collector.lldp import LldpCollector, LldpSpeedCollector
from wiremaps.collector.vlan import Rfc2674VlanCollector, IfMibVlanCollector

class Generic:
    """Generic class for equipments not handled by another class.

    We collect port information, FDB information, LLDP related
    information, VLAN information using first LLDP, then RFC2674 and
    at least ifStackStatus.

    If an information is missing for a given port, it is just ignored.
    """

    def normport(self, port, ports):
        if port not in ports.portNames:
            return None
        return port

    def collectData(self, ip, proxy, dbpool):
        proxy.version = 1       # Use SNMPv1
        ports = PortCollector(proxy, dbpool)
        fdb = FdbCollector(proxy, dbpool, self.config,
                           lambda x: self.normport(x, ports))
        arp = ArpCollector(proxy, dbpool, self.config)
        lldp = LldpCollector(proxy, dbpool,
                             lambda x: self.normport(x, ports))
        speed = LldpSpeedCollector(proxy, dbpool,
                                   lambda x: self.normport(x, ports))
        vlan1 = Rfc2674VlanCollector(proxy, dbpool,
                                     normPort=lambda x: self.normport(x, ports),
                                     clean=False)
        vlan2 = IfMibVlanCollector(proxy, dbpool,
                                   normPort=lambda x: self.normport(x, ports),
                                   clean=False)
        d = ports.collectData()
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: lldp.collectData())
        d.addCallback(lambda x: speed.collectData())
        d.addCallback(lambda x: vlan1.collectData())
        d.addCallback(lambda x: vlan2.collectData())
        return d

generic = Generic()
