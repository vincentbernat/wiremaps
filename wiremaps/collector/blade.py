from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.port import PortCollector
from wiremaps.collector.fdb import FdbCollector
from wiremaps.collector.arp import ArpCollector
from wiremaps.collector.alteon import AlteonVlanCollector, AlteonSpeedCollector
from wiremaps.collector.vlan import VlanCollector

class BladeEthernetSwitch:
    """Collector for various Blade Ethernet Switch based on AlteonOS"""

    implements(ICollector, IPlugin)

    baseoid = None
    ifDescr = None
    def handleEquipment(self, oid):
        raise NotImplementedError

    def collectData(self, ip, proxy, dbpool):
        ports = PortCollector(proxy, dbpool, normPort=lambda x: x%128)
        if self.ifDescr is not None:
            ports.ifDescr = self.ifDescr

        speed = AlteonSpeedCollector(proxy, dbpool, lambda x: x%128)
        speed.oidDuplex = '%s.1.3.2.1.1.3' % self.baseoid
        speed.oidSpeed = '%s.1.3.2.1.1.2' % self.baseoid
        speed.oidAutoneg = '%s.1.1.2.2.1.11'% self.baseoid

        fdb = FdbCollector(proxy, dbpool, self.config, normport=lambda x: x%128)
        arp = ArpCollector(proxy, dbpool, self.config)

        vlan = AlteonVlanCollector(proxy, dbpool, lambda x: x%128 - 1)
        vlan.oidVlanNames = '%s.2.1.1.3.1.2' % self.baseoid
        vlan.oidVlanPorts = '%s.2.1.1.3.1.3' % self.baseoid

        d = ports.collectData()
        d.addCallback(lambda x: speed.collectData())
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: vlan.collectData())
        return d

class NortelEthernetSwitch(BladeEthernetSwitch):
    """Collector for Nortel Ethernet Switch Module for BladeCenter"""

    baseoid = '.1.3.6.1.4.1.1872.2.5'
    def handleEquipment(self, oid):
        return (oid in [
                '.1.3.6.1.4.1.1872.1.18.1', # Nortel Layer2-3 GbE Switch Module(Copper)
                '.1.3.6.1.4.1.1872.1.18.2', # Nortel Layer2-3 GbE Switch Module(Fiber)
                '.1.3.6.1.4.1.1872.1.18.3', # Nortel 10Gb Uplink Ethernet Switch Module
                ])

blade1 = NortelEthernetSwitch()

class IbmBladeEthernetSwitch(BladeEthernetSwitch):
    """Collector for Nortel Blade Ethernet Switch, new generation (BNT)
    """

    baseoid = '.1.3.6.1.4.1.26543.2.5'
    def handleEquipment(self, oid):
        return (oid in ['.1.3.6.1.4.1.26543.1.18.5', # Nortel 1/10Gb Uplink Ethernet Switch Module
                        ])

blade2 = IbmBladeEthernetSwitch()

class HpBladeEthernetSwitch(BladeEthernetSwitch):
    """Collector for HP Blade Ether Switch, based on AlteonOS
    """

    baseoid = '.1.3.6.1.4.1.11.2.3.7.11.33.4.2'
    ifDescr = '%s.1.1.2.2.1.15' % baseoid

    def handleEquipment(self, oid):
        return (oid in ['.1.3.6.1.4.1.11.2.3.7.11.33.4.1.1', # GbE2c L2/L3 Ethernet Blade Switch
                        ])

blade3 = HpBladeEthernetSwitch()
