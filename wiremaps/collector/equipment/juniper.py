from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.datastore import LocalVlan
from wiremaps.collector.helpers.port import PortCollector
from wiremaps.collector.helpers.fdb import FdbCollector
from wiremaps.collector.helpers.arp import ArpCollector
from wiremaps.collector.helpers.lldp import LldpCollector, LldpSpeedCollector

class Juniper:
    """Collector for Juniper devices"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return oid.startswith('.1.3.6.1.4.1.2636.')

    def normport(self, port, ports, parents):
        if port in parents.parent:
            return parents.parent[port]
        if port not in ports.portNames:
            return None
        return port

    def collectData(self, equipment, proxy):
        ports = PortCollector(equipment, proxy,
                              names="ifAlias", descrs="ifName")
        parents = JuniperStackCollector(equipment, proxy)
        arp = ArpCollector(equipment, proxy, self.config)
        lldp = LldpCollector(equipment, proxy,
                             lambda x: self.normport(x, ports, parents))
        speed = LldpSpeedCollector(equipment, proxy,
                                   lambda x: self.normport(x, ports, parents))
        fdb = JuniperFdbCollector(equipment, proxy, self.config,
                                  lambda x: self.normport(x, ports, parents))
        vlan = JuniperVlanCollector(equipment, proxy,
                                    lambda x: self.normport(x, ports, parents))
        
        d = ports.collectData()
        d.addCallback(lambda x: parents.collectData())
        d.addCallback(lambda x: vlan.collectData())
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: lldp.collectData())
        d.addCallback(lambda x: speed.collectData())
        return d

juniper = Juniper()

class JuniperStackCollector(object):
    """Retrieve relation between logical ports and physical ones using C{IF-MIB::ifStackStatus}"""
    ifStackStatus = '.1.3.6.1.2.1.31.1.2.1.3'

    def __init__(self, equipment, proxy):
        self.proxy = proxy
        self.equipment = equipment
        self.parent = {}

    def gotIfStackStatus(self, results):
        """Handle reception of C{IF-MIB::ifStackStatus}."""
        for oid in results:
            if results[oid] != 1: continue
            port = int(oid.split(".")[-1])
            y = int(oid.split(".")[-2])
            if y == 0: continue
            if port == 0: continue
            if y in self.parent: continue
            self.parent[y] = port
        # Remove indirections
        change = True
        while change:
            change = False
            for y in self.parent:
                if self.parent[y] in self.parent:
                    self.parent[y] = self.parent[self.parent[y]]
                    change = True

    def collectData(self):
        print "Collecting additional port information for %s" % self.proxy.ip
        d = self.proxy.walk(self.ifStackStatus)
        d.addCallback(self.gotIfStackStatus)
        return d

class JuniperVlanCollector(object):
    oidVlanID        = '.1.3.6.1.4.1.2636.3.40.1.5.1.5.1.5' # jnxExVlanTag
    oidVlanNames     = '.1.3.6.1.4.1.2636.3.40.1.5.1.5.1.2' # jnxExVlanName
    oidVlanPortGroup = '.1.3.6.1.4.1.2636.3.40.1.5.1.7.1.3' # jnxExVlanPortStatus
    oidRealIfID      = '.1.3.6.1.2.1.17.1.4.1.2'            # dot1dBasePortIfIndex

    def __init__(self, equipment, proxy, normport):
        self.proxy = proxy
        self.equipment = equipment
        self.normport = normport

    def gotVlanID(self, results, dic):
        for oid in results:
            vid = int(oid.split(".")[-1])
            dic[vid] = results[oid]

    def gotVlanName(self, results, dic):
        for oid in results:
            vid = int(oid.split(".")[-1])
            self.names[self.vlanVid[vid]] = results[oid]

    def gotRealIfID(self, results, dic):
        for oid in results:
            vid = int(oid.split(".")[-1])
            dic[vid] = results[oid]

    def gotPorts(self, results):
        for oid in results:
            port = int(oid.split(".")[-1])
            port = self.normport(self.realifId[port])
            vid = int(oid.split(".")[-2])
            vid = self.vlanVid[vid]
            if port is not None:
                self.equipment.ports[port].vlan.append(LocalVlan(vid,self.names[vid]))
                               
    def collectData(self):
        """Collect VLAN data from SNMP"""
        print "Collecting VLAN information for %s" % self.proxy.ip
        self.realifId = {}
        self.vlanVid = {}
        self.names = {}

        # Get list of VLANs
        d = self.proxy.walk(self.oidVlanID)
        d.addCallback(self.gotVlanID, self.vlanVid)
        # Get vlan Names
        d.addCallback(lambda x: self.proxy.walk(self.oidVlanNames))
        d.addCallback(self.gotVlanName,self.vlanVid)
        # Get list of ifMib to jnxMib interface index association
        d.addCallback(lambda x: self.proxy.walk(self.oidRealIfID))
        d.addCallback(self.gotRealIfID, self.realifId)
        # Get list of interfaces in vlans
        d.addCallback(lambda x: self.proxy.walk(self.oidVlanPortGroup))
        d.addCallback(self.gotPorts)

        return d

class JuniperFdbCollector(FdbCollector):
    """Collect data using FDB"""

    # BRIDGE-MIB::dot1dBridge.7.1.2.2.1.2.<vlan>.<mac1>.<mac2>.<mac3>.<mac4>.<mac5>.<mac6> = INTEGER: interface
    dot1dTpFdbPort = '.1.3.6.1.2.1.17.7.1.2.2.1.2'
    dot1dBasePortIfIndex = '.1.3.6.1.2.1.17.1.4.1.2'
