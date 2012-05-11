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

    def __init__(self):
        print "Loaded Juniper Plugin"
    
    def handleEquipment(self, oid):
        return True #oid.startswith('.1.3.6.1.4.1.2636.')

    def normport(self, port, ports):
        if port not in ports.portNames:
            return None
        return port

    def collectData(self, equipment, proxy):
        proxy.version = 1       # Use SNMPv1
        ports = JuniperPortCollector(equipment, proxy)
        arp = ArpCollector(equipment, proxy, self.config)
        lldp = LldpCollector(equipment, proxy,
                             lambda x: self.normport(x, ports))
        speed = LldpSpeedCollector(equipment, proxy,
                                   lambda x: self.normport(x, ports))

        fdb = JuniperFdbCollector(equipment, proxy,
                                   lambda x: self.normport(x, ports))
        vlan = JuniperVlanCollector(equipment, proxy)
        
        d = ports.collectData()
        d.addCallback(lambda x: vlan.collectData())
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: lldp.collectData())
        d.addCallback(lambda x: speed.collectData())
        return d



juniper = Juniper()

class JuniperVlanCollector():
    oidVlanID     = '.1.3.6.1.4.1.2636.3.40.1.5.1.5.1.5' # jnxExVlanTag
    oidVlanNames  = '.1.3.6.1.4.1.2636.3.40.1.5.1.5.1.2' # jnxExVlanName

    oidVlanTagnes = '.1.3.6.1.4.1.2636.3.40.1.5.1.7.1.4' # jnxExVlanPortTagness
    oidRealIfID   = '.1.3.6.1.2.1.17.1.4.1.2'            # dot1dBasePortIfIndex

    def __init__(self, equipment, proxy):
        self.proxy = proxy
        self.equipment = equipment

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

    def gotTrunkStatus(self, results,index=0):
        for oid in results:
            port = int(oid.split(".")[-1])
            port = self.realifId[port]
            vid = int(oid.split(".")[-2])
            vid = self.vlanVid[vid]
            if port is not None and self.equipment.ports.has_key(port):
                self.equipment.ports[port].vlan.append(LocalVlan(vid,self.names[vid])) 
#                if results[oid] == 1:
#                    self.trunked.append(port)
                    
                               
    def collectData(self):
        """Collect VLAN data from SNMP"""
        print "Collecting VLAN information for %s" % self.proxy.ip
        self.realifId = {}
        self.vlanVid = {}
        self.trunked = {}
        self.mibidx = {}
        self.vlans = {}
        self.names = {}

        # Get list of VLANs
        d = self.proxy.walk(self.oidVlanID)
        d.addCallback(self.gotVlanID, self.vlanVid)
        # Get vlan Names
        d.addCallback(lambda x: self.proxy.walk(self.oidVlanNames))
        d.addCallback(self.gotVlanName,self.vlanVid)
        # Get list of ifMib to jnxMib interface index asotiation
        d.addCallback(lambda x: self.proxy.walk(self.oidRealIfID))
        d.addCallback(self.gotRealIfID, self.realifId)
        # Get list of interfaces in vlans
        d.addCallback(lambda x: self.proxy.walk(self.oidVlanTagnes))
        d.addCallback(self.gotTrunkStatus, self.trunked)

        return d
"""
        d.addCallback(lambda x: self.proxy.walk(self.ifDescr)
        d.addCallback(self.gotVlan, self.vlanNames)
        d.addCallback(lambda x: self.proxy.walk(self.encapsIfTag))
        d.addCallback(self.gotVlan, self.vlanEncapsTag)
        d.addCallback(lambda x: self.proxy.walk(self.encapsIfType))
        d.addCallback(self.gotVlan, self.vlanEncapsType)
        d.addCallback(lambda x: self.proxy.walk(self.ifStackStatus))
        d.addCallback(self.gotStackStatus)
"""

class JuniperPortCollector(PortCollector):
    def collectData(self):
        """Collect data.

        - Using IF-MIB::ifAlias for port name
          and index
        - Using IF-MIB::ifOperStatus for port status
        """
        print "Collecting port information for %s" % self.proxy.ip
        d = self.proxy.walk(self.ifType)
        d.addCallback(self.gotIfTypes)
        d.addCallback(lambda x: self.proxy.walk(self.ifName))
        d.addCallback(self.gotIfDescrs)
        d.addCallback(lambda x: self.proxy.walk(self.ifAlias))
        d.addCallback(self.gotIfNames)
        d.addCallback(lambda x: self.proxy.walk(self.ifOperStatus))
        d.addCallback(self.gotOperStatus)
        d.addCallback(lambda x: self.proxy.walk(self.ifPhysAddress))
        d.addCallback(self.gotPhysAddress)
        d.addCallback(lambda x: self.proxy.walk(self.ifSpeed))
        d.addCallback(self.gotSpeed)
        d.addCallback(lambda x: self.proxy.walk(self.ifHighSpeed))
        d.addCallback(self.gotHighSpeed)
        d.addCallback(lambda _: self.completeEquipment())
        return d
    
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
                                53,   # propVirtual
                                62,   # fastEther
                                69,   # fastEtherFX
                                117,  # gigabitEthernet
                                161,  # ieee8023adLag
                                ] or (self.trunk and port in self.trunk):
                self.ports.append(port)



class JuniperFdbCollector(FdbCollector):
    """Collect data using FDB"""

    # BRIDGE-MIB::dot1dBridge.7.1.2.2.1.2.<vlan>.<mac1>.<mac2>.<mac3>.<mac4>.<mac5>.<mac6> = INTEGER: interface
    dot1dTpFdbPort = '.1.3.6.1.2.1.17.7.1.2.2.1.2'
    dot1dBasePortIfIndex = '.1.3.6.1.2.1.17.1.4.1.2'
