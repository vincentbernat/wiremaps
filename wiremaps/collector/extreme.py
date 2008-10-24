from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.port import PortCollector
from wiremaps.collector.fdb import FdbCollector, ExtremeFdbCollector
from wiremaps.collector.arp import ArpCollector
from wiremaps.collector.lldp import LldpCollector
from wiremaps.collector.edp import EdpCollector

class ExtremeSummit:
    """Collector for Extreme switches and routers"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return (oid in ['.1.3.6.1.4.1.1916.2.40', # Extreme Summit 24e
                        '.1.3.6.1.4.1.1916.2.28', # Extreme Summit 48si
                        '.1.3.6.1.4.1.1916.2.54', # Extreme Summit 48e
                        '.1.3.6.1.4.1.1916.2.76', # Extreme Summit 48t
                        '.1.3.6.1.4.1.1916.2.62', # Black Diamond 8810
                        ])

    def collectData(self, ip, proxy, dbpool):
        ports = PortCollector(proxy, dbpool)
        fdb = FdbCollector(proxy, dbpool, self.config)
        arp = ArpCollector(proxy, dbpool, self.config)
        edp = EdpCollector(proxy, dbpool)
        vlan = VlanCollector(proxy, dbpool)
        # LLDP disabled due to unstability
        # lldp = LldpCollector(proxy, dbpool)
        d = ports.collectData()
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: edp.collectData())
        d.addCallback(lambda x: vlan.collectData())
        # d.addCallback(lambda x: lldp.collectData())
        return d

class ExtremeWare:
    """Collector for ExtremeWare chassis"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return (oid in ['.1.3.6.1.4.1.1916.2.11', # Black Diamond 6808 (ExtremeWare)
                        ])

    def collectData(self, ip, proxy, dbpool):
        ports = PortCollector(proxy, dbpool)
        vlan = VlanCollector(proxy, dbpool)
        fdb = ExtremeFdbCollector(vlan, proxy, dbpool, self.config)
        arp = ArpCollector(proxy, dbpool, self.config)
        edp = EdpCollector(proxy, dbpool)
        # LLDP disabled due to unstability
        # lldp = LldpCollector(proxy, dbpool)
        d = ports.collectData()
        d.addCallback(lambda x: vlan.collectData())
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: edp.collectData())
        # d.addCallback(lambda x: lldp.collectData())
        return d

class VlanCollector:
    """Collect local VLAN for Extreme switchs"""

    vlanIfDescr = '.1.3.6.1.4.1.1916.1.2.1.2.1.2'
    vlanIfVlanId = '.1.3.6.1.4.1.1916.1.2.1.2.1.10'
    vlanOpaque = '.1.3.6.1.4.1.1916.1.2.6.1.1'
    extremeSlotNumber = '.1.3.6.1.4.1.1916.1.1.2.2.1.1'

    def __init__(self, proxy, dbpool):
        self.proxy = proxy
        self.dbpool = dbpool

    def gotVlan(self, results, dic):
        """Callback handling reception of VLAN

        @param results: C{EXTREME-VLAN-MIB::extremeVlanXXXX}
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
            for i in range(0, len(ports)):
                if ord(ports[i]) == 0:
                    continue
                for j in range(0, 8):
                    if ord(ports[i]) & (1 << j):
                        if self.slots:
                            l.append(8-j + 8*i + 1000*slot)
                        else:
                            l.append(8-j + 8*i)
            self.vlanPorts[vlan] = l

    def gotSlots(self, results):
        """Callback handling reception of slots

        @param results: C{EXTREME-SYSTEM-MIB::extremeSlotNumber}
        """
        self.slots = len(results)

    def collectData(self):
        """Collect VLAN data from SNMP"""
    
        def fileVlanIntoDb(txn, descr, id, ports, ip):
            txn.execute("DELETE FROM vlan WHERE equipment=%(ip)s AND type='local'",
                        {'ip': str(ip)})
            for vid in descr:
                if vid in id and vid in ports:
                    for port in ports[vid]:
                        txn.execute("INSERT INTO vlan VALUES (%(ip)s, "
                                    "%(port)s, %(vid)s, %(name)s, "
                                    "%(type)s)",
                                    {'ip': str(ip),
                                     'port': port,
                                     'vid': id[vid],
                                     'name': descr[vid],
                                     'type': 'local'})

        print "Collecting VLAN information for %s" % self.proxy.ip
        self.vlanDescr = {}
        self.vlanId = {}
        self.vlanPorts = {}
        self.slots = 0
        d = self.proxy.walk(self.vlanIfDescr)
        d.addCallback(self.gotVlan, self.vlanDescr)
        d.addCallback(lambda x: self.proxy.walk(self.vlanIfVlanId))
        d.addCallback(self.gotVlan, self.vlanId)
        d.addCallback(lambda x: self.proxy.walk(self.extremeSlotNumber))
        d.addCallback(self.gotSlots)
        d.addCallback(lambda x: self.proxy.walk(self.vlanOpaque))
        d.addCallback(self.gotVlanMembers)
        d.addCallback(lambda x: self.dbpool.runInteraction(fileVlanIntoDb,
                                                           self.vlanDescr,
                                                           self.vlanId,
                                                           self.vlanPorts,
                                                           self.proxy.ip))
        return d



summit = ExtremeSummit()
eware = ExtremeWare()
