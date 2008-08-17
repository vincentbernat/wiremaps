from zope.interface import Interface

class ICollector(Interface):
    """Interface for a collector"""

    def handleEquipment(oid):
        """Does this instance handle the given equipment

        @param oid: OID identifying the kind of equipment
        @return: C{True} if the equipment is handled
        """

    def collectData(ip, proxy, dbpool):
        """Collect data from the equipment

        @param ip: IP of the equipment
        @param proxy: proxy to query the equipment with SNMP
        @param dbpool: pool of database connections to use to query
            database
        """
