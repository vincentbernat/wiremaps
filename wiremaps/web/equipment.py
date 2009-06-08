from nevow import rend, loaders, tags as T
from wiremaps.web.common import RenderMixIn
from wiremaps.web.json import JsonPage
from wiremaps.web import ports

class EquipmentResource(JsonPage):
    """Give the list of equipments"""

    def __init__(self, dbpool, collector):
        self.dbpool = dbpool
        self.collector = collector
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        return self.dbpool.runQuery("SELECT name,ip FROM equipment "
                                    "WHERE deleted='infinity' "
                                    "ORDER BY name")

    def child_refresh(self, ctx):
        self.collector.startExploration()
        p = rend.Page(docFactory=loaders.stan(T.p["Refresh started..."]))
        p.addSlash = True
        return p

    def childFactory(self, ctx, name):
        return EquipmentDetailResource(name, self.dbpool, self.collector)

class EquipmentDescriptionResource(JsonPage):
    """Give the description of a given equipment"""

    def __init__(self, ip, dbpool):
        self.dbpool = dbpool
        self.ip = ip
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        return self.dbpool.runQuery("SELECT description FROM equipment "
                                    "WHERE ip=%(ip)s AND deleted='infinity'",
                                    {'ip': str(self.ip)})

class EquipmentVlansResource(rend.Page, RenderMixIn):
    """Give the list of vlans for a given equipment (as an HTML table)"""

    docFactory = loaders.stan(T.span(render=T.directive("vlans"),
                                     data=T.directive("vlans")))
    addSlash = True

    def __init__(self, ip, dbpool):
        self.dbpool = dbpool
        self.ip = ip
        rend.Page.__init__(self)

    def render_vlans(self, ctx, data):
        if not data:
            return ctx.tag["No VLAN information available for this host."]
        vlans = {}
        for row in data:
            if (row[0], row[1]) not in vlans:
                vlans[row[0], row[1]] = []
            vlans[row[0], row[1]].append(row[2])
        r = []
        i = 0
        vlans = list(vlans.iteritems())
        vlans.sort()
        for (vid, name), ports in vlans:
            r.append(T.tr(_class=(i%2) and "odd" or "even")[
                    T.td[T.span(data=vid, render=T.directive("vlan"))],
                    T.td[name],
                    T.td(render=T.directive("ports"),
                         data=ports)])
            i += 1
        return T.table(_class="vlan")[
            T.thead[T.td["VID"], T.td["Name"], T.td["Ports"]], r]

    def data_vlans(self, ctx, data):
        return self.dbpool.runQuery("SELECT v.vid, v.name, p.name "
                                    "FROM vlan v, port p "
                                    "WHERE v.equipment=%(ip)s AND v.type='local' "
                                    "AND v.port = p.index "
                                    "AND p.equipment = v.equipment "
                                    "AND deleted='infinity' "
                                    "ORDER BY v.vid, p.index",
                                    {'ip': str(self.ip)})

class EquipmentDetailResource(JsonPage):
    """Give the list of ports for a given equipment or allow refresh"""

    def __init__(self, ip, dbpool, collector):
        self.dbpool = dbpool
        self.ip = ip
        self.collector = collector
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        return self.dbpool.runQuery("SELECT index, name, alias, cstate, speed, duplex, autoneg "
                                    "FROM port WHERE equipment=%(ip)s "
                                    "AND deleted='infinity' "
                                    "ORDER BY index",
                                    {'ip': str(self.ip)})

    def child_refresh(self, ctx):
        return RefreshEquipmentResource(self.ip, self.dbpool, self.collector)

    def child_descr(self, ctx):
        return EquipmentDescriptionResource(self.ip, self.dbpool)

    def child_vlans(self, ctx):
        return EquipmentVlansResource(self.ip, self.dbpool)

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
        d = self.dbpool.runQuery("SELECT ip FROM equipment "
                                 "WHERE ip=%(ip)s AND deleted='infinity'",
                                 {'ip': str(self.ip)})
        d.addCallback(self.gotEquipment)
        return d
