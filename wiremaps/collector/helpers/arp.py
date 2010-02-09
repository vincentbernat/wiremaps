from twisted.python import log
from twisted.internet import defer, reactor

class ArpCollector:
    """Collect data using ARP"""

    ipNetToMediaPhysAddress = '.1.3.6.1.2.1.4.22.1.2'

    def __init__(self, equipment, proxy, config):
        """Create a collector using ARP entries in SNMP.

        @param proxy: proxy to use to query SNMP
        @param equipment: equipment to complete with ARP entries
        @param config: configuration
        """
        self.proxy = proxy
        self.equipment = equipment
        self.config = config

    def gotArp(self, results):
        """Callback handling reception of ARP

        @param results: result of walking C{IP-MIB::ipNetToMediaPhysAddress}
        """
        for oid in results:
            ip = ".".join([m for m in oid.split(".")[-4:]])
            mac = ":".join("%02x" % ord(m) for m in results[oid])
            self.equipment.arp[ip] = mac

    def collectData(self):
        """Collect data from SNMP using ipNetToMediaPhysAddress.
        """
        print "Collecting ARP for %s" % self.proxy.ip
        d = self.proxy.walk(self.ipNetToMediaPhysAddress)
        d.addCallback(self.gotArp)
        return d
