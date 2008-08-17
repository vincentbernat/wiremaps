from wiremaps.web.json import JsonPage
from wiremaps.web import ports

class EquipmentResource(JsonPage):
    """Give the list of equipments"""

    def __init__(self, dbpool):
        self.dbpool = dbpool
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        return self.dbpool.runQuery("SELECT name,ip FROM equipment ORDER BY name")

    def childFactory(self, ctx, name):
        return PortResource(name, self.dbpool)

class PortResource(JsonPage):
    """Give the list of ports for a given equipment"""

    def __init__(self, ip, dbpool):
        self.dbpool = dbpool
        self.ip = ip
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        return self.dbpool.runQuery("SELECT index, name, alias, cstate "
                                    "FROM port WHERE equipment=%(ip)s "
                                    "ORDER BY index",
                                    {'ip': str(self.ip)})

    def childFactory(self, ctx, name):
        return ports.PortDetailsResource(self.ip, int(name), self.dbpool)

