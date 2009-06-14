from wiremaps.collector.datastore import Sonmp

class SonmpCollector:
    """Collect data using SONMP"""

    s5EnMsTopNmmSegId = '.1.3.6.1.4.1.45.1.6.13.2.1.1.4'

    def __init__(self, equipment, proxy, normport=None):
        """Create a collector using SONMP entries in SNMP.

        @param proxy: proxy to use to query SNMP
        @param equipment: equipment to complete
        """
        self.proxy = proxy
        self.equipment = equipment
        self.normport = normport

    def gotSonmp(self, results):
        """Callback handling reception of SONMP

        @param results: result of walking C{S5-ETH-MULTISEG-TOPOLOGY-MIB::s5EnMsTopNmmSegId}
        """
        for oid in results:
            ip = ".".join([m for m in oid.split(".")[-5:-1]])
            segid = int(oid.split(".")[-1])
            if segid > 0x10000:
                # Don't want to handle this case
                continue
            if segid > 0x100:
                segid = segid / 256 * 64 + segid % 256 - 64
            port = int(oid.split(".")[-6]) + (int(oid.split(".")[-7]) - 1)*64
            if self.normport:
                port = self.normport(port)
            if port is not None and port > 0:
                self.equipment.ports[port].sonmp = Sonmp(ip, segid)

    def collectData(self):
        """Collect data from SNMP using s5EnMsTopNmmSegId"""
        print "Collecting SONMP for %s" % self.proxy.ip
        d = self.proxy.walk(self.s5EnMsTopNmmSegId)
        d.addCallback(self.gotSonmp)
        return d
