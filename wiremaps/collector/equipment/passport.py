from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.helpers.port import PortCollector
from wiremaps.collector.helpers.fdb import CommunityFdbCollector
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

    def collectData(self, equipment, proxy):
        ports = PortCollector(equipment, proxy)
        ports.ifDescr = ports.ifName
        ports.ifName = ".1.3.6.1.4.1.2272.1.4.10.1.1.35"
        speed = NortelSpeedCollector(equipment, proxy)
        mlt = MltCollector(proxy)
        fdb = PassportFdbCollector(equipment, proxy, self.config, mlt)
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

class PassportFdbCollector(CommunityFdbCollector):
    vlanName = '.1.3.6.1.4.1.2272.1.3.2.1.2'
    filterOut = []

    # We need to redefine gotPortIf because while dot1dTpFdbPort will
    # return MLT ID, dot1dBasePortIfIndex does not. Therefore, we need
    # to normalize port at this point.
    def __init__(self, equipment, proxy, config, mlt):
        CommunityFdbCollector.__init__(self, equipment,
                                       proxy, config, self.normPortIndex)
        self.mlt = mlt

    def normPortIndex(self, port):
        """Normalize port index.

        Port 0 is just itself and port >= 2048 are VLAN, while port >
        4095 are MLT ID.
        """
        if port < 1:
            return None
        if port < 2048:
            return port
        if port > 4095:
            if port not in self.mlt.mltindex:
                return None
            mltid = self.mlt.mltindex[port]
            if mltid in self.mlt.mlt and self.mlt.mlt[mltid]:
                return self.mlt.mlt[mltid][0]
        return None

    def gotPortIf(self, results):
        CommunityFdbCollector.gotPortIf(self, results)
        for i in self.mlt.mltindex:
            self.portif[i] = i
