from wiremaps.collector import exception
from wiremaps.collector.datastore import Edp, RemoteVlan

class EdpCollector:
    """Collect data using EDP"""

    edpNeighborName = '.1.3.6.1.4.1.1916.1.13.2.1.3'
    edpNeighborSlot = '.1.3.6.1.4.1.1916.1.13.2.1.5'
    edpNeighborPort = '.1.3.6.1.4.1.1916.1.13.2.1.6'
    edpNeighborVlanId = '.1.3.6.1.4.1.1916.1.13.3.1.2'

    def __init__(self, equipment, proxy, normport=None):
        """Create a collector using EDP entries in SNMP.

        @param proxy: proxy to use to query SNMP
        @param equipment: equipment to complete with data from EDP
        @param nomport: function to use to normalize port index
        """
        self.proxy = proxy
        self.equipment = equipment
        self.normport = normport

    def gotEdp(self, results, dic):
        """Callback handling reception of EDP

        @param results: result of walking C{EXTREME-EDP-MIB::extremeEdpNeighborXXXX}
        @param dic: dictionary where to store the result
        """
        for oid in results:
            port = int(oid[len(self.edpNeighborName):].split(".")[1])
            if self.normport is not None:
                port = self.normport(port)
            desc = results[oid]
            if desc and port is not None:
                dic[port] = desc

    def gotEdpVlan(self, results):
        """Callback handling reception of EDP vlan

        @param results: result of walking C{EXTREME-EDP-MIB::extremeEdpNeighborVlanId}
        """
        for oid in results:
            port = int(oid[len(self.edpNeighborVlanId):].split(".")[1])
            if self.normport is not None:
                port = self.normport(port)
            vlan = [chr(int(x))
                    for x in oid[len(self.edpNeighborVlanId):].split(".")[11:]]
            self.vlan[results[oid], port] = "".join(vlan)

    def completeEquipment(self):
        """Complete C{self.equipment} with data from EDP."""
        # Core EDP
        for port in self.edpSysName:
            self.equipment.ports[port].edp = \
                Edp(self.edpSysName[port],
                    int(self.edpRemoteSlot[port]),
                    int(self.edpRemotePort[port]))
        # Vlans
        for vid, port in self.vlan:
            self.equipment.ports[port].vlan.append(
                RemoteVlan(vid, self.vlan[vid, port]))

    def collectData(self):
        """Collect EDP data from SNMP"""
        print "Collecting EDP for %s" % self.proxy.ip
        self.edpSysName = {}
        self.edpRemoteSlot = {}
        self.edpRemotePort = {}
        self.vlan = {}
        d = self.proxy.walk(self.edpNeighborName)
        d.addCallback(self.gotEdp, self.edpSysName)
        d.addCallback(lambda x: self.proxy.walk(self.edpNeighborSlot))
        d.addCallback(self.gotEdp, self.edpRemoteSlot)
        d.addCallback(lambda x: self.proxy.walk(self.edpNeighborPort))
        d.addCallback(self.gotEdp, self.edpRemotePort)
        d.addCallback(lambda x: self.proxy.walk(self.edpNeighborVlanId))
        d.addCallback(self.gotEdpVlan)
        d.addCallback(lambda _: self.completeEquipment())
        return d
