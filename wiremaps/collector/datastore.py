# Datastore for equipment related information

from zope.interface import Interface, Attribute, implements

def ascii(s):
    """Convert to ASCII a string"""
    if s is None:
        return None
    return s.decode("ascii", "replace")

class IEquipment(Interface):
    """Interface for object containing complete description of an equipment"""

    ip = Attribute('IP of this equipment.')
    name = Attribute('Name of this equipment.')
    oid = Attribute('OID of this equipment.')
    description = Attribute('Description of this equipment.')
    location = Attribute('Location of the equipment.')

    ports = Attribute('List of ports for this equipment as a mapping with index as key')
    arp = Attribute('ARP mapping (IP->MAC) for this equipment.')

class Equipment:
    implements(IEquipment)

    def __init__(self, ip, name, oid, description, location):
        self.ip = ip
        self.name = ascii(name)
        self.oid = oid
        self.description = ascii(description)
        self.location = ascii(location)
        self.ports = {}
        self.arp = {}

class IPort(Interface):
    """Interface for object containing port information"""

    name = Attribute('Name of this port.')
    state = Attribute('State of this port (up/down).')
    alias = Attribute('Alias for this port.')
    mac = Attribute('MAC address of this port.')
    speed = Attribute('Speed of this port.')
    duplex = Attribute('Duplex of this port.')
    autoneg = Attribute('Autoneg for this port.')

    fdb = Attribute('MAC on this port.')
    sonmp = Attribute('SONMP information for this port.')
    edp = Attribute('EDP information for this port.')
    cdp = Attribute('CDP information for this port.')
    lldp = Attribute('LLDP information for this port.')
    vlan = Attribute('List of VLAN attached to this port.')
    trunk = Attribute('Trunk information for this port.')

class Port:
    implements(IPort)

    def __init__(self, name, state,
                 alias=None, mac=None, speed=None, duplex=None, autoneg=None):
        self.name = ascii(name)
        self.state = state
        self.alias = ascii(alias)
        self.mac = mac
        self.speed = speed
        self.duplex = duplex
        self.autoneg = autoneg
        self.fdb = []
        self.sonmp = None
        self.edp = None
        self.cdp = None
        self.lldp = None
        self.vlan = []
        self.trunk = None

class ISonmp(Interface):
    """Interface for object containing SONMP data"""

    ip = Attribute('Remote IP')
    port = Attribute('Remote port')

class Sonmp:
    implements(ISonmp)

    def __init__(self, ip, port):
        self.ip = ip
        self.port = port

class IEdp(Interface):
    """Interface for object containing EDP data"""

    sysname = Attribute('Remote system name')
    slot = Attribute('Remote slot')
    port = Attribute('Remote port')

class Edp:
    implements(IEdp)

    def __init__(self, sysname, slot, port):
        self.sysname = ascii(sysname)
        self.slot = slot
        self.port = port

class ICdp(Interface):
    """Interface for object containing CDP data"""

    sysname = Attribute('Remote sysname')
    port = Attribute('Remote port name')
    ip = Attribute('Remote management IP')
    platform = Attribute('Remote platform name')

class Cdp:
    implements(ICdp)

    def __init__(self, sysname, port, ip, platform):
        self.sysname = ascii(sysname)
        self.port = port
        self.ip = ip
        self.platform = ascii(platform)

class ILldp(Interface):
    """Interface for object containing LLDP data"""

    sysname = Attribute('Remote system name')
    sysdesc = Attribute('Remote system description')
    portdesc = Attribute('Remote port description')
    ip = Attribute('Remote management IP')

class Lldp:
    implements(ILldp)

    def __init__(self, sysname, sysdesc, portdesc, ip=None):
        self.sysname = ascii(sysname)
        self.sysdesc = ascii(sysdesc)
        self.portdesc = ascii(portdesc)
        self.ip = ip

class IVlan(Interface):
    """Interface for object containing information for one VLAN"""

    vid = Attribute('VLAN ID')
    name = Attribute('Vlan name')

class ILocalVlan(IVlan):
    """Interface for a local VLAN"""
class IRemoteVlan(IVlan):
    """Interface for a remote VLAN"""

class Vlan:
    def __init__(self, vid, name):
        self.vid = vid
        self.name = ascii(name)

class LocalVlan(Vlan):
    implements(ILocalVlan)
class RemoteVlan(Vlan):
    implements(IRemoteVlan)

class ITrunk(Interface):
    """Interface for an object containing information about one trunk on a port"""

    parent = Attribute('Parent of this port')

class Trunk:
    implements(ITrunk)

    def __init__(self, parent):
        self.parent = parent
