from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.helpers.port import PortCollector
from wiremaps.collector.helpers.fdb import FdbCollector
from wiremaps.collector.helpers.arp import ArpCollector
from wiremaps.collector.helpers.lldp import LldpCollector, LldpSpeedCollector
from wiremaps.collector.helpers.vlan import Rfc2674VlanCollector

class Procurve:
    """Collector for HP Procurve switches"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        # Complete list is in hpicfOid.mib
        return oid.startswith('.1.3.6.1.4.1.11.2.3.7.11.') and \
            not oid.startswith('.1.3.6.1.4.1.11.2.3.7.11.33.4.') # This is a Blade Switch

    def normport(self, port, ports):
        if port not in ports.portNames:
            return None
        return port

    def collectData(self, equipment, proxy):
        t = {}
        trunk = ProcurveTrunkCollector(equipment, proxy, t)
        ports = PortCollector(equipment, proxy, trunk=t)
        ports.ifName = ports.ifAlias
        fdb = FdbCollector(equipment, proxy, self.config,
                           lambda x: self.normport(x, ports))
        arp = ArpCollector(equipment, proxy, self.config)
        lldp = LldpCollector(equipment, proxy)
        speed = LldpSpeedCollector(equipment, proxy)
        vlan = Rfc2674VlanCollector(equipment, proxy,
                                    normPort=lambda x: self.normport(x, ports))
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

    def __init__(self, equipment, proxy, trunk):
        self.proxy = proxy
        self.equipment = equipment
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

