from nevow import rend, loaders, tags as T
from wiremaps.web.json import JsonPage
from wiremaps.web import ports

class EquipmentResource(JsonPage):
    """Give the list of equipments"""

    def __init__(self, dbpool, collector):
        self.dbpool = dbpool
        self.collector = collector
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        return self.dbpool.runQuery("SELECT name,ip FROM equipment ORDER BY name")

    def child_refresh(self, ctx):
        self.collector.startExploration()
        return rend.Page(docFactory=loaders.stan(T.p["Refresh started..."]))

    def childFactory(self, ctx, name):
        return EquipmentDetailResource(name, self.dbpool, self.collector)

class EquipmentDetailResource(JsonPage):
    """Give the list of ports for a given equipment or allow refresh"""

    def __init__(self, ip, dbpool, collector):
        self.dbpool = dbpool
        self.ip = ip
        self.collector = collector
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        return self.dbpool.runQuery("SELECT index, name, alias, cstate "
                                    "FROM port WHERE equipment=%(ip)s "
                                    "ORDER BY index",
                                    {'ip': str(self.ip)})

    def child_refresh(self, ctx):
        return RefreshEquipmentResource(self.ip, self.dbpool, self.collector)

    def childFactory(self, ctx, name):
        return ports.PortDetailsResource(self.ip, int(name), self.dbpool)

class RefreshEquipmentResource(JsonPage):
    """Refresh an equipment page with the help of the collector"""

    def __init__(self, ip, dbpool, collector):
        self.ip = ip
        self.collector = collector
        self.dbpool = dbpool
        JsonPage.__init__(self)

    def gotEquipment(self, result):
        if not result:
            return {u"status": 0, u"message": u"Cannot find the equipment to refresh"}
        d = self.collector.startExploreIP(self.ip)
        d.addCallback(lambda x: {u"status": 1})
        return d

    def data_json(self, ctx, data):
        d = self.dbpool.runQuery("SELECT ip FROM equipment WHERE ip=%(ip)s",
                                 {'ip': str(self.ip)})
        d.addCallback(self.gotEquipment)
        return d
