from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.port import PortCollector
from wiremaps.collector.fdb import FdbCollector
from wiremaps.collector.arp import ArpCollector
from wiremaps.collector.lldp import LldpCollector, LldpSpeedCollector
from wiremaps.collector.vlan import Rfc2674VlanCollector

class Procurve:
    """Collector for HP Procurve switches"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        # Complete list is in hpicfOid.mib
        return oid.startswith('.1.3.6.1.4.1.11.2.3.7.11.')

    def normport(self, port, ports):
        if port not in ports.portNames:
            return None
        return port

    def collectData(self, ip, proxy, dbpool):
        t = {}
        trunk = ProcurveTrunkCollector(proxy, dbpool, t)
        ports = PortCollector(proxy, dbpool, trunk=t)
        ports.ifName = ports.ifAlias
        fdb = FdbCollector(proxy, dbpool, self.config,
                           lambda x: self.normport(x, ports))
        arp = ArpCollector(proxy, dbpool, self.config)
        lldp = LldpCollector(proxy, dbpool)
        speed = LldpSpeedCollector(proxy, dbpool)
        vlan = Rfc2674VlanCollector(proxy, dbpool,
                                    normPort=lambda x: self.normport(x, ports),
                                    clean=False)
        d = trunk.collectData()
        d.addCallback(lambda x: ports.collectData())
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: lldp.collectData())
        d.addCallback(lambda x: speed.collectData())
        d.addCallback(lambda x: vlan.collectData())
        return d

procurve = Procurve()

class ProcurveTrunkCollector:
    """Collect trunk for HP Procurve Switches.

    A trunk is just an interface of type propMultiplexor(54) and the
    members are found using ifStackStatus.
    """

    ifType = '.1.3.6.1.2.1.2.2.1.3'
    ifStackStatus = '.1.3.6.1.2.1.31.1.2.1.3'

    def __init__(self, proxy, dbpool, trunk):
        self.proxy = proxy
        self.dbpool = dbpool
        self.trunk = trunk

    def gotType(self, results):
        """Callback handling reception of ifType

        @param results: C{IF-MIB::ifType}
        """
        for oid in results:
            if results[oid] == 54:
                port = int(oid.split(".")[-1])
                self.trunk[port] = []

    def gotStatus(self, results):
        """Callback handling reception of stack members

        @param results: C{IF-MIB::ifStackStatus}
        """
        for oid in results:
            physport = int(oid.split(".")[-1])
            trunkport = int(oid.split(".")[-2])
            if trunkport in self.trunk:
                self.trunk[trunkport].append(physport)
        empty = []
        for key in self.trunk:
            if len(self.trunk[key]) == 0:
                empty.append(key)
        for key in empty:
            del self.trunk[key]

    def collectData(self):
        """Collect link aggregation information from HP Procurve"""
        print "Collecting trunk information for %s" % self.proxy.ip
        d = self.proxy.walk(self.ifType)
        d.addCallback(self.gotType)
        d.addCallback(lambda x: self.proxy.walk(self.ifStackStatus))
        d.addCallback(self.gotStatus)
        return d

