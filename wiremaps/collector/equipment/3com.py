import re

from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.internet import defer

from wiremaps.collector.icollector import ICollector
from wiremaps.collector.datastore import LocalVlan
from wiremaps.collector.helpers.port import PortCollector
from wiremaps.collector.helpers.fdb import CommunityFdbCollector
from wiremaps.collector.helpers.arp import ArpCollector

class SuperStack:
    """Collector for 3Com SuperStack switches"""

    implements(ICollector, IPlugin)

    def handleEquipment(self, oid):
        return (oid in ['.1.3.6.1.4.1.43.10.27.4.1.2.2', # 3Com SuperStack II/3
                        '.1.3.6.1.4.1.43.10.27.4.1.2.4', # 3Com SuperStack 3
                        '.1.3.6.1.4.1.43.10.27.4.1.2.11', # 3Com SuperStack 3
                        ])

    def normPortName(self, descr):
        if descr.startswith("RMON:10/100 "):
            descr = descr[len("RMON:10/100 "):]
        if descr.startswith("RMON "):
            descr = descr[len("RMON "):]
        mo = re.match("^Port (\d+) on Unit (\d+)$", descr)
        if mo:
            return "Unit %s/Port %s" % (mo.group(2),
                                        mo.group(1))
        return descr

    def collectData(self, equipment, proxy):
        proxy.version = 1       # Use SNMPv1
        ports = PortCollector(equipment, proxy, self.normPortName)
        fdb = SuperStackFdbCollector(equipment, proxy, self.config)
        arp = ArpCollector(equipment, proxy, self.config)
        vlan = SuperStackVlanCollector(equipment, proxy)
        d = ports.collectData()
        d.addCallback(lambda x: fdb.collectData())
        d.addCallback(lambda x: arp.collectData())
        d.addCallback(lambda x: vlan.collectData())
        return d

superstack = SuperStack()

class SuperStackFdbCollector(CommunityFdbCollector):

    vlanName = '.1.3.6.1.4.1.43.10.1.14.1.1.1.2' # Not really names
                                                 # but this will work
                                                 # out.
    filterOut = []


class SuperStackVlanCollector:
    """VLAN collector for 3Com SuperStack.

    Here is how this works:
     - a3ComVlanIfGlobalIdentifier.{x} = {vid}
     - a3ComVlanIfDescr.{x} = {description}
     - a3ComVlanEncapsIfTag.{y} = {vid}
     - a3ComVlanEncapsIfType.{y} = vlanEncaps8021q(2)
     - ifStackStatus.{y}.{port} = active(1)

    So, walk a3ComVlanIfGlobalIdentifier to get all possible vid, then
    search for a match in a3ComVlanEncapsIfTag. You should get several
    match. You need to choose the one where a3ComVlanEncapsIfTag is
    equal to 2. Then, get the port using ifStackStatus.

    If the VLAN is untagged, x=y
    """

    ifGlobalIdentifier = '.1.3.6.1.4.1.43.10.1.14.1.2.1.4'
    ifDescr = '.1.3.6.1.4.1.43.10.1.14.1.2.1.2'
    encapsIfTag = '.1.3.6.1.4.1.43.10.1.14.4.1.1.3'
    encapsIfType = '.1.3.6.1.4.1.43.10.1.14.4.1.1.2'
    ifStackStatus = '.1.3.6.1.2.1.31.1.2.1.3'

    def __init__(self, equipment, proxy):
        self.proxy = proxy
        self.equipment = equipment

    def gotVlan(self, results, dic):
        """Callback handling reception of VLAN

        @param results: vlan names or ports
        @param dic: where to store the results
        """
        for oid in results:
            vid = int(oid.split(".")[-1])
            dic[vid] = results[oid]

    def gotStackStatus(self, results):
        """Handle reception of C{IF-MIB::ifStackStatus}.

        We also complete C{self.equipment}
        """
        vlanPorts = {}
        for oid in results:
            if results[oid] == 1: # active
                port = int(oid.split(".")[-1])
                if port > 10000:
                    # Those are logical ports
                    continue
                y = int(oid.split(".")[-2])
                if y not in self.vlanEncapsType:
                    # This VLAN can be untagged
                    if y not in self.vlanVid:
                        continue
                    vid = self.vlanVid[y]
                elif self.vlanEncapsType[y] == 2: # vlanEncaps8021q
                    vid = self.vlanEncapsTag[y]
                if vid not in vlanPorts:
                    vlanPorts[vid] = []
                vlanPorts[vid].append(port)

        # Add all those information in C{self.equipment}
        for x in self.vlanVid:
            if self.vlanVid[x] in vlanPorts:
                for port in vlanPorts[self.vlanVid[x]]:
                    self.equipment.ports[port].vlan.append(
                        LocalVlan(self.vlanVid[x],
                                  self.vlanNames[x]))

    def collectData(self):
        """Collect VLAN data from SNMP"""
        print "Collecting VLAN information for %s" % self.proxy.ip
        self.vlanVid = {}
        self.vlanNames = {}
        self.vlanEncapsTag = {}
        self.vlanEncapsType = {}
        d = self.proxy.walk(self.ifGlobalIdentifier)
        d.addCallback(self.gotVlan, self.vlanVid)
        d.addCallback(lambda x: self.proxy.walk(self.ifDescr))
        d.addCallback(self.gotVlan, self.vlanNames)
        d.addCallback(lambda x: self.proxy.walk(self.encapsIfTag))
        d.addCallback(self.gotVlan, self.vlanEncapsTag)
        d.addCallback(lambda x: self.proxy.walk(self.encapsIfType))
        d.addCallback(self.gotVlan, self.vlanEncapsType)
        d.addCallback(lambda x: self.proxy.walk(self.ifStackStatus))
        d.addCallback(self.gotStackStatus)
        return d
