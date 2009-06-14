from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.helpers.port import PortCollector
from wiremaps.collector.helpers.fdb import FdbCollector
from wiremaps.collector.helpers.arp import ArpCollector
from wiremaps.collector.helpers.sonmp import SonmpCollector
from wiremaps.collector.helpers.nortel import MltCollector, NortelSpeedCollector
from wiremaps.collector.helpers.vlan import VlanCollector

class NortelPassport:
    """Collector for ERS8600 Nortel Passport routing switches"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return (oid in ['.1.3.6.1.4.1.2272.30', # ERS-8610
                        ])

    def normPortIndex(self, port, mlt):
        """Normalize port index.
        
        Port 0 is just itself and port >= 1024 are VLAN and co
        """
        if port < 1:
            return None
        if port < 2048:
            return port
        if port > 4095:
            mltid = port - 4095
            if mltid in mlt.mlt and mlt.mlt[mltid]:
                return mlt.mlt[mltid][0]
        return None

    def collectData(self, equipment, proxy):
        ports = PortCollector(equipment, proxy)
        ports.ifDescr = ports.ifName
        ports.ifName = ".1.3.6.1.4.1.2272.1.4.10.1.1.35"
        speed = NortelSpeedCollector(equipment, proxy)
        mlt = MltCollector(proxy)
        fdb = FdbCollector(equipment, proxy, self.config,
                           lambda x: self.normPortIndex(x, mlt))
        arp = ArpCollector(equipment, proxy, self.config)
        sonmp = SonmpCollector(equipment, proxy, lambda x: x+63)
        vlan = NortelVlanCollector(equipment, proxy, lambda x: x-1)
        d = ports.collectData()
        d.addCallback(lambda x: speed.collectData())
        d.addCallback(lambda x: mlt.collectData())
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: sonmp.collectData())
        d.addCallback(lambda x: vlan.collectData())
        return d

passport = NortelPassport()

class NortelVlanCollector(VlanCollector):
    """Collect VLAN information for Nortel Passport switchs without LLDP"""
    oidVlanNames = '.1.3.6.1.4.1.2272.1.3.2.1.2' # rcVlanName
    oidVlanPorts = '.1.3.6.1.4.1.2272.1.3.2.1.11' # rcVlanPortMembers
