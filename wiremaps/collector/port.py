from twisted.internet import defer

class PortCollector:
    """Collect data about ports"""

    ifDescr = '.1.3.6.1.2.1.2.2.1.2'
    ifName = '.1.3.6.1.2.1.31.1.1.1.1'
    ifAlias = '.1.3.6.1.2.1.31.1.1.1.18'
    ifType = '.1.3.6.1.2.1.2.2.1.3'
    ifOperStatus = '.1.3.6.1.2.1.2.2.1.8'
    ifPhysAddress = '.1.3.6.1.2.1.2.2.1.6'
    ifSpeed = '.1.3.6.1.2.1.2.2.1.5'
    ifHighSpeed = '.1.3.6.1.2.1.31.1.1.1.15'

    @classmethod
    def filePortsIntoDb(cls, txn, names, aliases, status, address, speed, ip):
        # This table is a bit complicated to use because we need
        # to update or insert depending on the fact that the
        # information has changed or not.
        tmp = aliases.copy()
        tmp.update(names)
        names = tmp
        newports = names.keys()
        txn.execute("SELECT index, name, alias, cstate, mac, speed "
                    "FROM port WHERE equipment = %(ip)s "
                    "AND deleted='infinity'",
                    {'ip': str(ip)})
        ports = txn.fetchall()
        for port in ports:
            port, oname, oalias, ocstate, omac, ospeed = port
            port = int(port)
            if port not in newports:
                # Delete port
                txn.execute("UPDATE port SET deleted=CURRENT_TIMESTAMP "
                            "WHERE equipment = %(ip)s "
                            "AND index = %(index)s AND deleted='infinity'",
                            {'ip': str(ip),
                             'index': port})
            else:
                # Refresh port
                txn.execute("SELECT 1 WHERE %(mac1)s::macaddr = %(mac2)s::macaddr",
                            {'mac1': omac,
                             'mac2': address.get(port, None)})
                if not(txn.fetchall()) or \
                        oname != names[port] or oalias != aliases.get(port, None) or \
                        ocstate != status[port] or \
                        ospeed != speed.get(port, None):
                    # Delete the old one
                    txn.execute("UPDATE port SET deleted=CURRENT_TIMESTAMP "
                                "WHERE equipment = %(ip)s "
                                "AND index = %(index)s AND deleted='infinity'",
                                {'ip': str(ip),
                                 'index': port})
                else:
                    newports.remove(port)
                    # We don't need to update it, it is up-to-date
        for port in newports:
            # Add port
            txn.execute("INSERT INTO port "
                        "(equipment, index, name, alias, cstate, mac, speed) "
                        "VALUES (%(ip)s, %(port)s, "
                        "%(name)s, %(alias)s, %(state)s, %(address)s, %(speed)s)",
                        {'ip': str(ip),
                         'port': port,
                         'name': names[port],
                         'alias': aliases.get(port, None),
                         'state': status[port],
                         'address': address.get(port, None),
                         'speed': speed.get(port, None),
                         })


    def __init__(self, proxy, dbpool,
                 normName=None, normPort=None, filter=None, invert=False,
                 trunk=None):
        """Create a collector for port information

        @param proxy: proxy to use to query SNMP
        @param dbpool: pool of database connections
        @param normName: function to normalize port name
        @param normPort: function to normalize port index
        @param filter: filter out those ports
        @param invert: invert ifName and ifDescr
        @param trunk: collected trunk information
        """
        self.proxy = proxy
        self.dbpool = dbpool
        self.normName = normName
        self.normPort = normPort
        self.filter = filter
        self.invert = invert
        self.trunk = trunk

    def gotIfTypes(self, results):
        """Callback handling retrieving of interface types.

        @param result: result of walking on C{IF-MIB::ifType}
        """
        self.ports = []
        for oid in results:
            port = int(oid.split(".")[-1])
            if self.normPort is not None:
                port = self.normPort(port)
                if port is None:
                    continue
            if self.filter is not None and self.filter(port) is None:
                continue
            # Ethernet (ethernetCsmacd or some obsolote values) ?
            if results[oid] in [6,    # ethernetCsmacd
                                62,   # fastEther
                                69,   # fastEtherFX
                                117,  # gigabitEthernet
                                ] or (self.trunk and port in self.trunk):
                self.ports.append(port)

    def gotIfDescrs(self, results):
        """Callback handling retrieving of interface names.

        @param result: result of walking on C{IF-MIB::ifDescr}
        """
        self.portNames = {}
        for oid in results:
            port = int(oid.split(".")[-1])
            if self.normPort is not None:
                port = self.normPort(port)
            if port not in self.ports:
                continue
            descr = str(results[oid]).strip()
            if self.normName is not None:
                descr = self.normName(descr).strip()
            self.portNames[port] = descr

    def gotIfNames(self, results):
        """Callback handling retrieving of interface names.

        @param result: result of walking on C{IF-MIB::ifName}
        """
        self.portAliases = {}
        for oid in results:
            port = int(oid.split(".")[-1])
            if self.normPort is not None:
                port = self.normPort(port)
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
            if self.normPort is not None:
                port = self.normPort(port)
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
            if self.normPort is not None:
                port = self.normPort(port)
            if port not in self.ports:
                continue
            if results[oid] == 1:
                self.portStatus[port] = 'up'
            else:
                self.portStatus[port] = 'down'

    def gotSpeed(self, results):
        """Callback handling retrieving of interface speed.

        @param result: result of walking C{IF-MIB::ifSpeed}
        """
        self.speed = {}
        for oid in results:
            port = int(oid.split(".")[-1])
            if self.normPort is not None:
                port = self.normPort(port)
            if port not in self.ports:
                continue
            s = results[oid]
            if s == 2**32 - 1:
                # Overflow, let's say that it is 10G
                s = 10000
            else:
                s /= 1000000
            if s:
                self.speed[port] = s

    def gotHighSpeed(self, results):
        """Callback handling retrieving of interface high speed.

        @param result: result of walking C{IF-MIB::ifHighSpeed}
        """
        for oid in results:
            port = int(oid.split(".")[-1])
            if self.normPort is not None:
                port = self.normPort(port)
            if port not in self.ports:
                continue
            s = results[oid]
            if s:
                self.speed[port] = s

    def collectData(self):
        """Collect data.

        - Using IF-MIB::ifDescr for port name
          and index
        - Using IF-MIB::ifOperStatus for port status
        """

        def fileTrunkIntoDb(txn, trunk, ip):
            txn.execute("UPDATE trunk SET deleted=CURRENT_TIMESTAMP "
                        "WHERE equipment=%(ip)s AND deleted='infinity'", {'ip': str(ip)})
            for t in trunk:
                for port in trunk[t]:
                    txn.execute("INSERT INTO trunk VALUES (%(ip)s, %(trunk)s, %(port)s)",
                                {'ip': str(ip),
                                 'trunk': t,
                                 'port': port
                                 })

        print "Collecting port information for %s" % self.proxy.ip
        d = self.proxy.walk(self.ifType)
        d.addCallback(self.gotIfTypes)
        d.addCallback(lambda x: self.proxy.walk(self.invert and self.ifName or self.ifDescr))
        d.addCallback(self.gotIfDescrs)
        d.addCallback(lambda x: self.proxy.walk(self.invert and self.ifDescr or self.ifName))
        d.addCallback(self.gotIfNames)
        d.addCallback(lambda x: self.proxy.walk(self.ifOperStatus))
        d.addCallback(self.gotOperStatus)
        d.addCallback(lambda x: self.proxy.walk(self.ifPhysAddress))
        d.addCallback(self.gotPhysAddress)
        d.addCallback(lambda x: self.proxy.walk(self.ifSpeed))
        d.addCallback(self.gotSpeed)
        d.addCallback(lambda x: self.proxy.walk(self.ifHighSpeed))
        d.addCallback(self.gotHighSpeed)
        d.addCallback(lambda x: self.dbpool.runInteraction(self.filePortsIntoDb,
                                                           self.portNames,
                                                           self.portAliases,
                                                           self.portStatus,
                                                           self.portAddress,
                                                           self.speed,
                                                           self.proxy.ip))
        if self.trunk is not None:
            d.addCallback(lambda x: self.dbpool.runInteraction(fileTrunkIntoDb,
                                                               self.trunk,
                                                               self.proxy.ip))
        return d
