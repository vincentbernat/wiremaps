from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.helpers.port import PortCollector
from wiremaps.collector.helpers.arp import ArpCollector

class NameCollector:
    """Get real name of DRAC"""

    name = '.1.3.6.1.4.1.674.10892.2.1.1.10.0' # DELL-RAC-MIB::drsProductChassisName.0
    product1 = '.1.3.6.1.4.1.674.10892.2.1.1.1.0' # DELL-RAC-MIB::drsProductName.0
    product2 = '.1.3.6.1.4.1.674.10892.2.1.1.2.0' # DELL-RAC-MIB::drsProductShortName.0

    def __init__(self, equipment, proxy):
        self.proxy = proxy
        self.equipment = equipment

    def gotName(self, results):
        """Callback handling reception of name

        @param results: result of getting C{DELL-RAC-MIB::drsProductChassisName.0}
        """
        self.equipment.name = results[self.name]
        self.equipment.description = "%s %s" % (results[self.product1],
                                                results[self.product2])

    def collectData(self):
        """Collect data from SNMP using DELL-RAC-MIB.
        """
        print "Collecting real name for %s" % self.proxy.ip
        d = self.proxy.get((self.name, self.product1, self.product2))
        d.addCallback(self.gotName)
        return d

class DellRAC:
    """Collector for Dell DRAC"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return oid == '.1.3.6.1.4.1.674.10892.2'

    def collectData(self, equipment, proxy):
        name = NameCollector(equipment, proxy)
        ports = PortCollector(equipment, proxy)
        arp = ArpCollector(equipment, proxy, self.config)
        d = name.collectData()
        d.addCallback(lambda x: ports.collectData())
        d.addCallback(lambda x: arp.collectData())
        return d

drac = DellRAC()
