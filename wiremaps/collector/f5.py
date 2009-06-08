from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.arp import ArpCollector

class F5:
    """Collector for F5.

    F5 BigIP are Linux appliance running Net-SNMP. However, network
    interfaces are linked to some switch. Switch ports are not
    displayed in IF-MIB but in some proprietary MIB.

    Here are the revelant parts:

    F5-BIGIP-SYSTEM-MIB::sysInterfaceName."1.1" = STRING: 1.1
    F5-BIGIP-SYSTEM-MIB::sysInterfaceMediaActiveSpeed."1.1" = INTEGER: 1000
    F5-BIGIP-SYSTEM-MIB::sysInterfaceMediaActiveDuplex."1.1" = INTEGER: full(2)
    F5-BIGIP-SYSTEM-MIB::sysInterfaceMacAddr."1.1" = STRING: 0:1:d7:48:a7:94
    F5-BIGIP-SYSTEM-MIB::sysInterfaceEnabled."1.1" = INTEGER: true(1)
    F5-BIGIP-SYSTEM-MIB::sysInterfaceStatus."1.1" = INTEGER: up(0)
    F5-BIGIP-SYSTEM-MIB::sysTrunkName."TrunkIf" = STRING: TrunkIf
    F5-BIGIP-SYSTEM-MIB::sysTrunkStatus."TrunkIf" = INTEGER: up(0)
    F5-BIGIP-SYSTEM-MIB::sysTrunkAggAddr."TrunkIf" = STRING: 0:1:d7:48:a7:a0
    F5-BIGIP-SYSTEM-MIB::sysTrunkOperBw."TrunkIf" = INTEGER: 2000
    F5-BIGIP-SYSTEM-MIB::sysTrunkCfgMemberName."TrunkIf"."1.15" = STRING: 1.15
    F5-BIGIP-SYSTEM-MIB::sysTrunkCfgMemberName."TrunkIf"."1.16" = STRING: 1.16
    F5-BIGIP-SYSTEM-MIB::sysVlanVname."DMZ" = STRING: DMZ
    F5-BIGIP-SYSTEM-MIB::sysVlanId."DMZ" = INTEGER: 99
    F5-BIGIP-SYSTEM-MIB::sysVlanMemberVmname."DMZ"."TrunkIf" = STRING: TrunkIf

    The main problem is that everything is indexed using strings
    instead of numerical index. This does not fit our database scheme
    and does not allow collectors to work independently. Therefore, we
    will have an unique collector.

    We keep ARP collector, though.
    """

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return oid.startswith('.1.3.6.1.4.1.3375.2.1.3.4.') # F5 BigIP

    def collectData(self, ip, proxy, dbpool):
        ports = F5PortCollector(proxy, dbpool)
        arp = ArpCollector(proxy, dbpool, self.config)
        d = ports.collectData()
        d.addCallback(lambda x: arp.collectData())
        return d

class F5PortCollector:
    """Collect data about ports for F5.

    We also collect trunk and vlan data. This is a all-in-one data
    collector because the way data are indexed.
    """

    def __init__(self, proxy, dbpool):
        self.proxy = proxy
        self.dbpool = dbpool
        self.data = {}
        self.association = {}

    def gotData(self, results, kind, prefix):
        """Callback handling the reception of some data indexed with a string.

        @param results: data received
        @param kind: key of C{self.data} to store the result
        @param prefix: prefix OID; the string index is the remaining of this prefix
        """
        if kind not in self.data:
            self.data[kind] = {}
        for oid in results:
            # We convert the end of the OID to a string. We don't take
            # the length as important.
            string = "".join([chr(int(c))
                              for c in oid[len(prefix):].split(".")[2:]])
            self.data[kind][string] = results[oid]

    def gotAssociation(self, results, kind, prefix):
        """Callback handling the reception of some data indexed by an
        association of 2 strings.

        @param results: data received
        @param kind: key of C{self.data} to store the association
        @param prefix: prefix OID
        """
        if kind not in self.association:
            self.association[kind] = []
        for oid in results:
            strings = oid[len(prefix):].split(".")[1:]
            string1 = "".join([chr(int(c)) for c in strings[1:(int(strings[0])+1)]])
            string2 = "".join([chr(int(c)) for c in strings[(len(string1)+2):]])
            self.association[kind].append((string1, string2))

    def collectData(self):

        def fileIntoDb(txn, data, association, ip):
            # Interfaces
            interfaces = []
            for p in data["status"]:
                interfaces.append([x.isdigit() and int(x) or x for x in p.split(".")])
            interfaces.sort()
            interfaces = [".".join([str(y) for y in x]) for x in interfaces]
            txn.execute("UPDATE port SET deleted=CURRENT_TIMESTAMP "
                        "WHERE equipment=%(ip)s AND deleted='infinity'", {'ip': str(ip)})
            for p in data["status"]:
                txn.execute("""
INSERT INTO port
(equipment, index, name, cstate, mac, duplex, speed)
VALUES(%(ip)s, %(index)s, %(name)s, %(state)s, %(mac)s, %(duplex)s, %(speed)s)
""",
                            {'ip': str(ip),
                             'index': interfaces.index(p) + 1,
                             'name': p,
                             'state': data["status"][p] == 0 and 'up' or 'down',
                             'mac': data["mac"].get(p, None) and \
                                 ":".join([("%02x" % ord(m)) for m in data["mac"][p]]),
                             'duplex': {0: None,
                                        1: 'half',
                                        2: 'full'}[data["duplex"].get(p, 0)],
                             'speed': data["speed"].get(p, None)})
            # Trunk
            txn.execute("UPDATE trunk SET deleted=CURRENT_TIMESTAMP "
                        "WHERE equipment=%(ip)s AND deleted='infinity'", {'ip': str(ip)})
            for trunk, port in association["trunk"]:
                txn.execute("INSERT INTO trunk VALUES (%(ip)s, %(trunk)s, %(port)s)",
                            {'ip': str(ip),
                             'trunk': interfaces.index(trunk) + 1,
                             'port': interfaces.index(port) + 1})
            # VLAN
            txn.execute("UPDATE vlan SET deleted=CURRENT_TIMESTAMP "
                        "WHERE equipment=%(ip)s AND deleted='infinity'", {'ip': str(ip)})
            for vlan, port in association["vlan"]:
                if vlan not in data["vid"]: continue
                txn.execute(
                    "INSERT INTO vlan VALUES (%(ip)s, %(port)s, %(vid)s, %(name)s, %(type)s)",
                    {'ip': str(ip),
                     'port': interfaces.index(port) + 1,
                     'vid': data["vid"][vlan],
                     'name': vlan,
                     'type': 'local'})

        print "Collecting port, trunk and vlan information for %s" % self.proxy.ip
        d = defer.succeed(None)
        for oid, what in [
            # Interfaces
            (".1.3.6.1.4.1.3375.2.1.2.4.1.2.1.4", "speed"),
            (".1.3.6.1.4.1.3375.2.1.2.4.1.2.1.5", "duplex"),
            (".1.3.6.1.4.1.3375.2.1.2.4.1.2.1.6", "mac"),
            (".1.3.6.1.4.1.3375.2.1.2.4.1.2.1.17", "status"),
            # Trunk
            (".1.3.6.1.4.1.3375.2.1.2.12.1.2.1.2", "status"),
            (".1.3.6.1.4.1.3375.2.1.2.12.1.2.1.3", "mac"),
            (".1.3.6.1.4.1.3375.2.1.2.12.1.2.1.5", "speed"),
            (".1.3.6.1.4.1.3375.2.1.2.13.1.2.1.2", "vid")]:
            d.addCallback(lambda x,y: self.proxy.walk(y), oid)
            d.addCallback(self.gotData, what, oid)
        for oid, what in [
            (".1.3.6.1.4.1.3375.2.1.2.12.3.2.1.2", "trunk"),
            (".1.3.6.1.4.1.3375.2.1.2.13.2.2.1.1", "vlan")]:
            d.addCallback(lambda x,y: self.proxy.walk(y), oid)
            d.addCallback(self.gotAssociation, what, oid)
        d.addCallback(lambda x: self.dbpool.runInteraction(fileIntoDb,
                                                           self.data,
                                                           self.association,
                                                           self.proxy.ip))
        return d



f5 = F5()
