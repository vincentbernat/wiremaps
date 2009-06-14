from wiremaps.collector import exception
from wiremaps.collector.datastore import Cdp

class CdpCollector:
    """Collect data using CDP"""

    cdpCacheDeviceId = '.1.3.6.1.4.1.9.9.23.1.2.1.1.6'
    cdpCacheDevicePort = '.1.3.6.1.4.1.9.9.23.1.2.1.1.7'
    cdpCachePlatform = '.1.3.6.1.4.1.9.9.23.1.2.1.1.8'
    cdpCacheAddress = '.1.3.6.1.4.1.9.9.23.1.2.1.1.4'
    cdpCacheAddressType = '.1.3.6.1.4.1.9.9.23.1.2.1.1.3'

    def __init__(self, equipment, proxy):
        """Create a collector using CDP entries in SNMP.

        @param proxy: proxy to use to query SNMP
        @param equipment: equipment to complete with data from CDP
        """
        self.proxy = proxy
        self.equipment = equipment

    def gotCdp(self, results, dic):
        """Callback handling reception of CDP

        @param results: result of walking C{CISCO-CDP-MIB::cdpCacheXXXX}
        @param dic: dictionary where to store the result
        """
        for oid in results:
            port = int(oid[len(self.cdpCacheDeviceId):].split(".")[1])
            desc = results[oid]
            if desc and port is not None:
                dic[port] = desc

    def completeEquipment(self):
        """Add collected data to equipment."""
        for port in self.cdpDeviceId:
            if self.cdpAddressType[port] != 1:
                ip = "0.0.0.0"
            else:
                ip = ".".join(str(ord(i)) for i in self.cdpAddress[port])
            self.equipment.ports[port].cdp = \
                Cdp(self.cdpDeviceId[port],
                    self.cdpDevicePort[port],
                    ip,
                    self.cdpPlatform[port])

    def collectData(self):
        """Collect CDP data from SNMP"""
        print "Collecting CDP for %s" % self.proxy.ip
        self.cdpDeviceId = {}
        self.cdpDevicePort = {}
        self.cdpPlatform = {}
        self.cdpAddressType = {}
        self.cdpAddress = {}
        d = self.proxy.walk(self.cdpCacheDeviceId)
        d.addCallback(self.gotCdp, self.cdpDeviceId)
        for y in ["DevicePort", "Platform", "AddressType", "Address"]:
            d.addCallback(lambda x,z: self.proxy.walk(getattr(self, "cdpCache%s" % z)), y)
            d.addCallback(self.gotCdp, getattr(self, "cdp%s" % y))
        d.addCallback(lambda _: self.completeEquipment())
        return d
