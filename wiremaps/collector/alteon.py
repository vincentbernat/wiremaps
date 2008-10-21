from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.port import PortCollector
from wiremaps.collector.fdb import FdbCollector
from wiremaps.collector.arp import ArpCollector
from wiremaps.collector.sonmp import SonmpCollector

class Alteon2208:
    """Collector for Nortel Alteon 2208 and related"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return (oid in ['.1.3.6.1.4.1.1872.1.13.1.5', # Alteon 2208
                        '.1.3.6.1.4.1.1872.1.13.1.9', # Alteon 2208 E
                        '.1.3.6.1.4.1.1872.1.13.2.1', # Alteon 3408
                        ])

    def normPortName(self, descr):
        try:
            port = int(descr)
        except:
            return descr
        if port == 999:
            return "Management"
        return "Port %d" % (port - 256)

    def normPortIndex(self, port):
        """Normalize port index.
        """
        if port >= 1:
            return port + 256
        return None

    def collectData(self, ip, proxy, dbpool):
        ports = PortCollector(proxy, dbpool, self.normPortName)
        ports.ifName = ports.ifDescr
        ports.ifDescr = '.1.3.6.1.2.1.2.2.1.1' # ifIndex
        fdb = FdbCollector(proxy, dbpool, self.config)
        arp = ArpCollector(proxy, dbpool, self.config)
        vlan = VlanCollector(proxy, dbpool, self.normPortIndex)
        sonmp = SonmpCollector(proxy, dbpool, self.normPortIndex)
        d = ports.collectData()
        d.addCallback(lambda x: fdb.collectData(write=False))
        d.addCallback(lambda x: arp.collectData(write=False))
        d.addCallback(lambda x: vlan.collectData())
        d.addCallback(lambda x: sonmp.collectData())
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        return d

class VlanCollector:
    """Collect VLAN information for Alteon switchs"""

    vlanNewCfgVlanName = '.1.3.6.1.4.1.1872.2.5.2.1.1.3.1.2'
    vlanNewCfgPorts = '.1.3.6.1.4.1.1872.2.5.2.1.1.3.1.3'

    def __init__(self, proxy, dbpool, normPort=None):
        self.proxy = proxy
        self.dbpool = dbpool
        self.normPort = normPort

    def gotVlan(self, results, dic):
        """Callback handling reception of VLAN

        @param results: C{ALTEON-CS-PHYSICAL-MIB::vlanNewCfgXXXX}
        @param dic: where to store the results
        """
        for oid in results:
            vid = int(oid.split(".")[-1])
            dic[vid] = results[oid]

    def gotVlanMembers(self, results):
        """Callback handling reception of VLAN members

        @param results: C{EXTREME-VLAN-MIB::ExtremeVlanOpaqueEntry}
        """
        for oid in results:
            slot = int(oid.split(".")[-1])
            vlan = int(oid.split(".")[-2])
            ports = results[oid]
            l = self.vlanPorts.get(vlan, [])
            self.vlanPorts[vlan] = l

    def collectData(self):
        """Collect VLAN data from SNMP"""
    
        def fileVlanIntoDb(txn, names, ports, ip):
            txn.execute("DELETE FROM vlan WHERE equipment=%(ip)s AND type='local'",
                        {'ip': str(ip)})
            for vid in names:
                if vid in ports:
                    for i in range(0, len(ports[vid])):
                        if ord(ports[vid][i]) == 0:
                            continue
                        for j in range(0, 8):
                            if ord(ports[vid][i]) & (1 << j):
                                port = 7-j + 8*i
                                if self.normPort is not None:
                                    port = self.normPort(port)
                                if port is not None:
                                    txn.execute("INSERT INTO vlan VALUES (%(ip)s, "
                                                "%(port)s, %(vid)s, %(name)s, "
                                                "%(type)s)",
                                                {'ip': str(ip),
                                                 'port': port,
                                                 'vid': vid,
                                                 'name': names[vid],
                                                 'type': 'local'})

        print "Collecting VLAN information for %s" % self.proxy.ip
        self.vlanNames = {}
        self.vlanPorts = {}
        d = self.proxy.walk(self.vlanNewCfgVlanName)
        d.addCallback(self.gotVlan, self.vlanNames)
        d.addCallback(lambda x: self.proxy.walk(self.vlanNewCfgPorts))
        d.addCallback(self.gotVlan, self.vlanPorts)
        d.addCallback(lambda x: self.dbpool.runInteraction(fileVlanIntoDb,
                                                           self.vlanNames,
                                                           self.vlanPorts,
                                                           self.proxy.ip))
        return d

alteon = Alteon2208()
