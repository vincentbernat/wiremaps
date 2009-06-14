from zope.interface import Interface

class ICollector(Interface):
    """Interface for a collector for a given equipment"""

    def handleEquipment(oid):
        """Does this instance handle the given equipment

        @param oid: OID identifying the kind of equipment
        @return: C{True} if the equipment is handled
        """

    def collectData(equipment, proxy):
        """Collect data from the equipment

        @param equipment: equipment to complete with data
        @param proxy: proxy to query the equipment with SNMP

        @return: an object implementing IEquipment interface and
            containing all information for the given equipment.
        """
