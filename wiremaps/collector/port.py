from twisted.internet import defer

class PortCollector:
    """Collect data about ports"""

    ifDescr = '.1.3.6.1.2.1.2.2.1.2'
    ifName = '.1.3.6.1.2.1.31.1.1.1.1'
    ifType = '.1.3.6.1.2.1.2.2.1.3'
    ifOperStatus = '.1.3.6.1.2.1.2.2.1.8'
    ifPhysAddress = '.1.3.6.1.2.1.2.2.1.6'


    def __init__(self, proxy, dbpool, norm=None, filter=None):
        """Create a collector for port information

        @param proxy: proxy to use to query SNMP
        @param dbpool: pool of database connections
        @param norm: function to normalize port name
        @param filter: filter out those ports
        """
        self.proxy = proxy
        self.dbpool = dbpool
        self.norm = norm
        self.filter = filter

    def gotIfTypes(self, results):
        """Callback handling retrieving of interface types.

        @param result: result of walking on C{IF-MIB::ifType}
        """
        self.ports = []
        for oid in results:
            port = int(oid.split(".")[-1])
            if self.filter is not None and self.filter(port) is None:
                continue
            # Ethernet ?
            if results[oid] == 6:
                self.ports.append(port)

    def gotIfDescrs(self, results):
        """Callback handling retrieving of interface names.

        @param result: result of walking on C{IF-MIB::ifDescr}
        """
        self.portNames = {}
        for oid in results:
            port = int(oid.split(".")[-1])
            if port not in self.ports:
                continue
            descr = str(results[oid]).strip()
            if self.norm is not None:
                descr = self.norm(descr).strip()
            self.portNames[port] = descr

    def gotIfNames(self, results):
        """Callback handling retrieving of interface names.

        @param result: result of walking on C{IF-MIB::ifName}
        """
        self.portAliases = {}
        for oid in results:
            port = int(oid.split(".")[-1])
            if port not in self.ports:
                continue
            name = str(results[oid]).strip()
            if name:
                self.portAliases[port] = name

    def gotPhysAddress(self, results):
        """Callback handling retrieving of physical addresses.

        @param result: result of walking on C{IF-MIB::ifPhysAddress}
        """
        self.portAddress = {}
        for oid in results:
            port = int(oid.split(".")[-1])
            if port not in self.ports:
                continue
            address = [ "%x" % ord(a) for a in str(results[oid])]
            if address and len(address) == 6:
                self.portAddress[port] = ":".join(address)

    def gotOperStatus(self, results):
        """Callback handling retrieving of interface status.

        @param result: result of walking C{IF-MIB::ifOperStatus}
        """
        self.portStatus = {}
        for oid in results:
            port = int(oid.split(".")[-1])
            if port not in self.ports:
                continue
            if results[oid] == 2:
                self.portStatus[port] = 'down'
            else:
                self.portStatus[port] = 'up'

    def collectData(self):
        """Collect data.

        - Using IF-MIB::ifDescr for port name
          and index
        - Using IF-MIB::ifOperStatus for port status
        """

        def fileIntoDb(txn, names, aliases, status, address, ip):
            newports = names.keys()
            txn.execute("SELECT index FROM port WHERE equipment = %(ip)s",
                        {'ip': str(ip)})
            ports = txn.fetchall()
            for port in ports:
                port = int(port[0])
                alias = None
                if port not in address:
                    continue
                if port in aliases:
                    alias = aliases[port]
                if port not in newports:
                    txn.execute("DELETE FROM port WHERE equipment = %(ip)s "
                                "AND index = %(index)s", {'ip': str(ip),
                                                          'index': port})
                else:
                    newports.remove(port)
                    txn.execute("UPDATE port SET name=%(name)s, alias=%(alias)s, "
                                "cstate=%(state)s, mac=%(address)s WHERE equipment = %(ip)s "
                                "AND index = %(index)s", {'ip': str(ip),
                                                          'index': port,
                                                          'name': names[port],
                                                          'alias': alias,
                                                          'address': address[port],
                                                          'state': status[port]})
            for port in newports:
                alias = None
                if port not in address:
                    continue
                if port in aliases:
                    alias = aliases[port]
                txn.execute("INSERT INTO port VALUES (%(ip)s, %(port)s, "
                            "%(name)s, %(alias)s, %(state)s, %(address)s)",
                            {'ip': str(ip),
                             'port': port,
                             'name': names[port],
                             'alias': alias,
                             'state': status[port],
                             'address': address[port],
                             })

        print "Collecting port information for %s" % self.proxy.ip
        d = self.proxy.walk(self.ifType)
        d.addCallback(self.gotIfTypes)
        d.addCallback(lambda x: self.proxy.walk(self.ifDescr))
        d.addCallback(self.gotIfDescrs)
        d.addCallback(lambda x: self.proxy.walk(self.ifName))
        d.addCallback(self.gotIfNames)
        d.addCallback(lambda x: self.proxy.walk(self.ifOperStatus))
        d.addCallback(self.gotOperStatus)
        d.addCallback(lambda x: self.proxy.walk(self.ifPhysAddress))
        d.addCallback(self.gotPhysAddress)
        d.addCallback(lambda x: self.dbpool.runInteraction(fileIntoDb,
                                                           self.portNames,
                                                           self.portAliases,
                                                           self.portStatus,
                                                           self.portAddress,
                                                           self.proxy.ip))
        return d
