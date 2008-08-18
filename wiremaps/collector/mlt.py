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
                        # What port is bit j? See this from RAPID-CITY MIB:

                        # "The string is 88 octets long, for a total
                        # of 704 bits. Each bit corresponds to a port,
                        # as represented by its ifIndex value . When a
                        # bit has the value one(1), the corresponding
                        # port is a member of the set. When a bit has
                        # the value zero(0), the corresponding port is
                        # not a member of the set. The encoding is
                        # such that the most significant bit of octet
                        # #1 corresponds to ifIndex 0, while the least
                        # significant bit of octet #88 corresponds to
                        # ifIndex 703."

                        l.append(7-j + 8*i)
            self.mlt[mlt] = l

    def collectData(self, write=True):
        """Collect data from SNMP using rcMltPortMembers
        """
    
        print "Collecting MLT for %s" % self.proxy.ip
        d = self.proxy.walk(self.rcMltPortMembers)
        d.addCallback(self.gotMlt)
        return d
