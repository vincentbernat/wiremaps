from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.port import PortCollector
from wiremaps.collector.fdb import FdbCollector
from wiremaps.collector.arp import ArpCollector
from wiremaps.collector.sonmp import SonmpCollector
from wiremaps.collector.vlan import VlanCollector
from wiremaps.collector.speed import SpeedCollector

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
        speed = AlteonSpeedCollector(proxy, dbpool)
        fdb = FdbCollector(proxy, dbpool, self.config)
        arp = ArpCollector(proxy, dbpool, self.config)
        vlan = AlteonVlanCollector(proxy, dbpool, lambda x: self.normPortIndex(x-1))
        sonmp = SonmpCollector(proxy, dbpool, self.normPortIndex)
        d = ports.collectData()
        d.addCallback(lambda x: speed.collectData())
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: vlan.collectData())
        d.addCallback(lambda x: sonmp.collectData())
        return d

alteon = Alteon2208()

class AlteonVlanCollector(VlanCollector):
    # We use "NewCfg" because on some Alteon, there seems to have a
    # bug with "CurCfg".
    oidVlanNames = '.1.3.6.1.4.1.1872.2.5.2.1.1.3.1.2' # vlanNewCfgVlanName
    oidVlanPorts = '.1.3.6.1.4.1.1872.2.5.2.1.1.3.1.3' # vlanNewCfgPorts

class AlteonSpeedCollector(SpeedCollector):

    oidDuplex = '.1.3.6.1.4.1.1872.2.5.1.3.2.1.1.3'
    oidSpeed = '.1.3.6.1.4.1.1872.2.5.1.3.2.1.1.2'
    oidAutoneg = '.1.3.6.1.4.1.1872.2.5.1.1.2.2.1.11'

    def gotDuplex(self, results):
        """Callback handling duplex"""
        for oid in results:
            port = int(oid.split(".")[-1])
            if results[oid] == 3:
                self.duplex[port] = "half"
            elif results[oid] == 2:
                self.duplex[port] = "full"

    def gotSpeed(self, results):
        """Callback handling speed"""
        for oid in results:
            port = int(oid.split(".")[-1])
            if results[oid] == 2:
                self.speed[port] = 10
            elif results[oid] == 3:
                self.speed[port] = 100
            elif results[oid] == 4:
                self.speed[port] = 1000
            elif results[oid] == 6:
                self.speed[port] = 10000

    def gotAutoneg(self, results):
        """Callback handling autoneg"""
        for oid in results:
            port = int(oid.split(".")[-1])
            self.autoneg[port] = bool(results[oid] == 2)

