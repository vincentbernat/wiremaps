from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.port import PortCollector
from wiremaps.collector.fdb import FdbCollector
from wiremaps.collector.arp import ArpCollector
from wiremaps.collector.alteon import AlteonVlanCollector, AlteonSpeedCollector
from wiremaps.collector.vlan import VlanCollector

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
        speed = AlteonSpeedCollector(proxy, dbpool, lambda x: x-128)
        fdb = FdbCollector(proxy, dbpool, self.config)
        arp = ArpCollector(proxy, dbpool, self.config)
        vlan = AlteonVlanCollector(proxy, dbpool, lambda x: x+127)
        d = ports.collectData()
        d.addCallback(lambda x: speed.collectData())
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: vlan.collectData())
        return d

blade1 = NortelEthernetSwitch()

class BladeEthernetSwitch:
    """Collector for Nortel Blade Ethernet Switch, new generation.

    This seems almost identical to precedent generation but OID are
    not rooted in the same tree...
    """

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return (oid in ['.1.3.6.1.4.1.26543.1.18.5', # Nortel 1/10Gb Uplink Ethernet Switch Module
                        ])

    def collectData(self, ip, proxy, dbpool):
        ports = PortCollector(proxy, dbpool)
        speed = BladeSpeedCollector(proxy, dbpool, lambda x: x-128)
        fdb = FdbCollector(proxy, dbpool, self.config)
        arp = ArpCollector(proxy, dbpool, self.config)
        vlan = BladeVlanCollector(proxy, dbpool, lambda x: x+127)
        d = ports.collectData()
        d.addCallback(lambda x: speed.collectData())
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: vlan.collectData())
        return d

blade2 = BladeEthernetSwitch()

class BladeVlanCollector(VlanCollector):
    oidVlanNames = '.1.3.6.1.4.1.26543.2.5.2.1.1.3.1.2' # vlanNewCfgVlanName
    oidVlanPorts = '.1.3.6.1.4.1.26543.2.5.2.1.1.3.1.3' # vlanNewCfgPorts

class BladeSpeedCollector(AlteonSpeedCollector):
    oidDuplex = '.1.3.6.1.4.1.26543.2.5.1.3.2.1.1.3'
    oidSpeed = '.1.3.6.1.4.1.26543.2.5.1.3.2.1.1.2'
    oidAutoneg = '.1.3.6.1.4.1.26543.2.5.1.1.2.2.1.11'
