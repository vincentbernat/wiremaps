from twisted.internet import defer
from nevow import loaders, rend
from nevow import tags as T

from wiremaps.web.json import JsonPage
from wiremaps.web.common import RenderMixIn

class PortDetailsResource(JsonPage):
    """Give some details on the port.

    Those details contain what is seen from this port but may also
    contain how this port is seen from other systems.
    """

    def __init__(self, ip, index, dbpool):
        self.dbpool = dbpool
        self.ip = ip
        self.index = index
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        return [ PortDetailsMac(self.ip, self.index, self.dbpool),
                 PortDetailsSpeed(self.ip, self.index, self.dbpool),
                 PortDetailsTrunkComponents(self.ip, self.index, self.dbpool),
                 PortDetailsTrunkMember(self.ip, self.index, self.dbpool),
                 PortDetailsLldp(self.ip, self.index, self.dbpool),
                 PortDetailsRemoteLldp(self.ip, self.index, self.dbpool),
                 PortDetailsVlan(self.ip, self.index, self.dbpool),
                 PortDetailsSonmp(self.ip, self.index, self.dbpool),
                 PortDetailsEdp(self.ip, self.index, self.dbpool),
                 PortDetailsFdb(self.ip, self.index, self.dbpool),
                 PortDetailsCdp(self.ip, self.index, self.dbpool),
                 ]

class PortRelatedFragment(rend.Fragment, RenderMixIn):

    def __init__(self, ip, index, dbpool):
        self.dbpool = dbpool
        self.ip = ip
        self.index = index
        rend.Fragment.__init__(self, dbpool)

class PortDetailsRemoteLldp(PortRelatedFragment):

    docFactory = loaders.stan(T.span(render=T.directive("lldp"),
                                     data=T.directive("lldp")))

    def data_lldp(self, ctx, data):
        return self.dbpool.runQuery("SELECT DISTINCT re.ip, re.name, rp.name "
                                    "FROM lldp l, equipment re, equipment le, port lp, port rp "
                                    "WHERE (l.mgmtip=le.ip OR l.sysname=le.name) "
                                    "AND le.ip=%(ip)s AND lp.equipment=le.ip "
                                    "AND l.portdesc=lp.name "
                                    "AND lp.index=%(port)s "
                                    "AND l.equipment=re.ip "
                                    "AND l.port=rp.index AND rp.equipment=re.ip",
                                    {'ip': str(self.ip),
                                     'port': self.index})

    def render_lldp(self, ctx, data):
        if not data:
            return ""
        return ctx.tag["This port was detected on ",
                       T.invisible(data=data[0][1],
                                   render=T.directive("hostname")),
                       " (",
                       T.invisible(data=data[0][0],
                                   render=T.directive("ip")), ") ",
                       "on port ",
                       T.span(_class="data")[ data[0][2] ],
                       " by LLDP."]

class PortDetailsVlan(PortRelatedFragment):

    docFactory = loaders.stan(T.span(render=T.directive("vlans"),
                                     data=T.directive("vlans")))

    def data_vlans(self, ctx, data):
        q = """
SELECT COALESCE(l.vid, r.vid) as vvid, l.name, r.name
FROM
(SELECT * FROM vlan WHERE equipment=%(ip)s AND port=%(port)s AND type='local') l
FULL OUTER JOIN
(SELECT * FROM vlan WHERE equipment=%(ip)s AND port=%(port)s AND type='remote') r
ON l.vid = r.vid
ORDER BY vvid;
"""
        return self.dbpool.runQuery(q,
                                    {'ip': str(self.ip),
                                     'port': self.index})

    def render_vlans(self, ctx, data):
        if not data:
            return ""
        r = []
        i = 0
        notpresent = T.td(_class="notpresent")[
            T.acronym(title="Not present or no information from remote")["N/A"]]
        for row in data:
            vid = T.td[T.span(data=row[0], render=T.directive("vlan"))]
            if row[1] is None:
                r.append(T.tr(_class=(i%2) and "odd" or "even")[
                        vid, notpresent,
                        T.td[row[2]]])
            elif row[2] is None:
                r.append(T.tr(_class=(i%2) and "odd" or "even")
                         [vid, T.td[row[1]], notpresent])
            elif row[1] == row[2]:
                r.append(T.tr(_class=(i%2) and "odd" or "even")
                         [vid, T.td(colspan=2)[row[1]]])
            else:
                r.append(T.tr(_class=(i%2) and "odd" or "even")
                         [vid, T.td[row[1]], T.td[row[2]]])
            i += 1
        return ctx.tag["Here are the VLAN available on this port:",
                       T.table(_class="vlan")[
                T.thead[T.td["VID"], T.td["Local"], T.td["Remote"]], r]]

class PortDetailsFdb(PortRelatedFragment):

    docFactory = loaders.stan(T.span(render=T.directive("fdb"),
                                     data=T.directive("fdb")))

    def data_fdb(self, ctx, data):
        return self.dbpool.runQuery("SELECT DISTINCT f.mac, a.ip "
                                    "FROM fdb f LEFT OUTER JOIN arp a "
                                    "ON a.mac = f.mac "
                                    "WHERE f.equipment=%(ip)s "
                                    "AND f.port=%(port)s "
                                    "ORDER BY a.ip ASC, f.mac "
                                    "LIMIT 20",
                                    {'ip': str(self.ip),
                                     'port': self.index})

    def render_fdb(self, ctx, data):
        if not data:
            return ""
        r = []
        i = 0
        notpresent = T.td(_class="notpresent")[
            T.acronym(title="Unable to get IP from ARP tables")["N/A"]]
        for row in data:
            mac = T.td[T.span(data=row[0], render=T.directive("mac"))]
            if row[1] is not None:
                r.append(T.tr(_class=(i%2) and "odd" or "even")
                         [mac, T.td[T.invisible(data=row[1],
                                                render=T.directive("ip"))]])
            else:
                r.append(T.tr(_class=(i%2) and "odd" or "even")
                         [mac, notpresent])
            i += 1
        if len(r) == 20:
            intro = "At least the"
        else:
            intro = "The"
        return ctx.tag[intro,
                       " following MAC addresses are present in FDB: ",
                       T.table(_class="mac")[
                T.thead[T.td["MAC"], T.td["IP"]], r]]

class PortDetailsSpeed(PortRelatedFragment):

    docFactory = loaders.stan(T.span(render=T.directive("speed"),
                                     data=T.directive("speed")))

    def data_speed(self, ctx, data):
        return self.dbpool.runQuery("SELECT speed, duplex, autoneg "
                                    "FROM port "
                                    "WHERE equipment=%(ip)s AND index=%(port)s",
                                    {'ip': str(self.ip),
                                     'port': self.index})

    def render_speed(self, ctx, data):
        if not data:
            return ""
        data = data[0]
        if data[0] is None and data[1] is None and data[2] is None:
            return ""
        speed = ""
        if data[0]:
            speed = data[0]
            if speed % 1000 == 0:
                speed = "%d Gbit/s" % (speed/1000)
            else:
                speed = "%d Mbit/s" % speed
            speed = T.invisible["The speed of this port is ",
                                T.span(_class="data")[speed or "unknown"],
                                ". "]
        duplex = data[1] and T.invisible["The port is operating in ",
                                         T.span(_class="data")[data[1]],
                                         " duplex mode. "]
        autoneg = None
        if data[2] is not None:
            autoneg = T.invisible["Autonegotiation is ",
                                  T.span(_class="data")[
                    data[2] and "enabled" or "disabled"], "."]
        return ctx.tag[speed, duplex or "", autoneg or ""]

class PortDetailsMac(PortRelatedFragment):

    docFactory = loaders.stan(T.span(render=T.directive("macaddr"),
                                     data=T.directive("macaddr")))

    def data_macaddr(self, ctx, data):
        return self.dbpool.runQuery("SELECT mac "
                                    "FROM port "
                                    "WHERE equipment=%(ip)s AND index=%(port)s "
                                    "AND mac IS NOT NULL",
                                    {'ip': str(self.ip),
                                     'port': self.index})

    def render_macaddr(self, ctx, data):
        if not data:
            return ""
        return ctx.tag["The MAC address of this port is ",
                       T.invisible(data=data[0][0],
                                   render=T.directive("mac")),
                       "."]

class PortDetailsTrunkComponents(PortRelatedFragment):

    docFactory = loaders.stan(T.span(render=T.directive("trunk"),
                                     data=T.directive("trunk")))

    def data_trunk(self, ctx, data):
        return self.dbpool.runQuery("SELECT p.name "
                                    "FROM trunk t, port p "
                                    "WHERE t.equipment=%(ip)s AND t.port=%(port)s "
                                    "AND p.equipment=t.equipment "
                                    "AND p.index=t.member "
                                    "ORDER BY p.index",
                                    {'ip': str(self.ip),
                                     'port': self.index})

    def render_trunk(self, ctx, data):
        if not data:
            return ""
        return ctx.tag["This port is a trunk containing the following ports:",
                       T.ul [ [ T.li[T.span(_class="data")[x[0]]] for x in data]]]

class PortDetailsTrunkMember(PortRelatedFragment):

    docFactory = loaders.stan(T.span(render=T.directive("trunk"),
                                     data=T.directive("trunk")))

    def data_trunk(self, ctx, data):
        return self.dbpool.runQuery("SELECT p.name "
                                    "FROM trunk t, port p "
                                    "WHERE t.equipment=%(ip)s AND t.member=%(port)s "
                                    "AND p.equipment=t.equipment "
                                    "AND p.index=t.port LIMIT 1",
                                    {'ip': str(self.ip),
                                     'port': self.index})

    def render_trunk(self, ctx, data):
        if not data:
            return ""
        return ctx.tag["This port is a member of trunk ",
                       T.span(_class="data")[data[0][0]], "." ]

class PortDetailsSonmp(PortRelatedFragment):

    docFactory = loaders.stan(T.span(render=T.directive("sonmp"),
                                     data=T.directive("sonmp")))

    def data_sonmp(self, ctx, data):
        return self.dbpool.runQuery("SELECT DISTINCT remoteip, remoteport "
                                    "FROM sonmp WHERE equipment=%(ip)s "
                                    "AND port=%(port)s",
                                    {'ip': str(self.ip),
                                     'port': self.index})

    def render_sonmp(self, ctx, data):
        if not data:
            return ""
        return ctx.tag[
            "A device with IP ",
            T.invisible(data=data[0][0],
                        render=T.directive("ip")),
            " was found with SONMP. The remote port is ",
            T.span(_class="data", data=data[0][1],
                   render=T.directive("sonmpport")), "."]

class PortDetailsEdp(PortRelatedFragment):

    docFactory = loaders.stan(T.span(render=T.directive("edp"),
                                     data=T.directive("edp")))

    def data_edp(self, ctx, data):
        return self.dbpool.runQuery("SELECT DISTINCT sysname, remoteslot, remoteport "
                                    "FROM edp WHERE equipment=%(ip)s "
                                    "AND port=%(port)s",
                                    {'ip': str(self.ip),
                                     'port': self.index})

    def render_edp(self, ctx, data):
        if not data:
            return ""
        return ctx.tag[
            "A device named ",
            T.invisible(data=data[0][0],
                        render=T.directive("hostname")),
            " was found with EDP. The remote port is ",
            T.span(_class="data")["%d/%d" % (data[0][1], data[0][2])], "."]

class PortDetailsDiscovery(PortRelatedFragment):

    docFactory = loaders.stan(T.span(render=T.directive("discovery"),
                                     data=T.directive("discovery")))

    def render_discovery(self, ctx, data):
        if not data:
            return ""
        return ctx.tag[
            "The device ",
            T.invisible(data=data[0][2],
                        render=T.directive("hostname")),
            data[0][0] != "0.0.0.0" and T.invisible[
            " with IP ",
            T.invisible(data=data[0][0],
                        render=T.directive("ip")) ] or T.invisible[""],
            " was found with %s. Its description is " % self.discovery_name,
            T.span(_class="data") [data[0][1]],
            " and the remote port is ",
            T.span(_class="data") [data[0][3]],
            "."]

class PortDetailsLldp(PortDetailsDiscovery):

    discovery_name = "LLDP"

    def data_discovery(self, ctx, data):
        return self.dbpool.runQuery("SELECT DISTINCT mgmtip, sysdesc, "
                                    "sysname, portdesc "
                                    "FROM lldp WHERE equipment=%(ip)s "
                                    "AND port=%(port)s",
                                    {'ip': str(self.ip),
                                     'port': self.index})

class PortDetailsCdp(PortDetailsDiscovery):
    
    discovery_name = "CDP"

    def data_discovery(self, ctx, data):
        return self.dbpool.runQuery("SELECT DISTINCT mgmtip, platform, "
                                    "sysname, portname "
                                    "FROM cdp WHERE equipment=%(ip)s "
                                    "AND port=%(port)s",
                                    {'ip': str(self.ip),
                                     'port': self.index})
