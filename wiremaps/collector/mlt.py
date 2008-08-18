from twisted.internet import defer

class MltCollector:
    """Collect data using MLT.

    No data is written to database.
    """

    rcMltPortMembers = '.1.3.6.1.4.1.2272.1.17.10.1.3'

    def __init__(self, proxy):
        """Create a collector using MLT entries in SNMP.

        @param proxy: proxy to use to query SNMP
        """
        self.proxy = proxy
        self.mlt = {}

    def gotMlt(self, results):
        """Callback handling reception of MLT

        @param results: result of walking C{RC-MLT-MIB::rcMltPortMembers}
        """
        for oid in results:
            mlt = int(oid.split(".")[-1])
            ports = results[oid]
            l = []
            for i in range(0, len(ports)):
                if ord(ports[i]) == 0:
                    continue
                for j in range(0, 8):
                    if ord(ports[i]) & (1 << j):
                        # What port is bit j?
                        l.append(7-j + 8*i)
            self.mlt[mlt] = l

    def collectData(self, write=True):
        """Collect data from SNMP using rcMltPortMembers
        """
    
        print "Collecting MLT for %s" % self.proxy.ip
        d = self.proxy.walk(self.rcMltPortMembers)
        d.addCallback(self.gotMlt)
        return d
