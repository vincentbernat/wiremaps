from twisted.internet import defer
from nevow import loaders, rend
from nevow import tags as T

from wiremaps.web.json import JsonPage
from wiremaps.web.common import FragmentMixIn

class PortDetailsResource(JsonPage):
    """Give some details on the port.

    Those details contain what is seen from this port but may also
    contain how this port is seen from other systems.

    The data returned is a JSON array. Each element is a triple
    C{column, value, sortable}, where C{column} is the column name,
    C{value} is HTML code to put into this column and C{sortable} is
    either C{None} or a string/int value to sort on.
    """

    def __init__(self, ip, index, dbpool):
        self.dbpool = dbpool
        self.ip = ip
        self.index = index
        JsonPage.__init__(self)

    def flattenList(self, data):
        result = []
        errors = []
        for (success, value) in data:
            if success:
                for r in value:
                    result.append(r)
            else:
                print "While getting details for %s, port %d:" % (self.ip, self.index)
                value.printTraceback()
                errors.append(T.span(_class="error")
                              ["%s" % value.getErrorMessage()])
        if errors:
            result.append(("Errors",
                           rend.Fragment(
                        docFactory=loaders.stan(errors))))
        return result

    def data_json(self, ctx, data):
        l = []
        for c in [ PortDetailsMac,
                   PortDetailsSpeed,
                   PortDetailsTrunkComponents,
                   PortDetailsTrunkMember,
                   PortDetailsLldp,
                   PortDetailsRemoteLldp,
                   PortDetailsVlan,
                   PortDetailsSonmp,
                   PortDetailsEdp,
                   PortDetailsFdb,
                   PortDetailsCdp,
                   ]:
            detail = c(ctx, self.ip, self.index, self.dbpool)
            l.append(detail.collectDetails())
        d = defer.DeferredList(l, consumeErrors=True)
        d.addCallback(self.flattenList)
        return d

class PortRelatedDetails:
    """Return a list of port related details.

    This list is built from one SQL query. The result of this query is
    passed to C{render} method which should output a list of triple
    C{column, value, sort} where C{value} will be turned into a
    C{rend.Fragment}.
    """

    def __init__(self, ctx, ip, index, dbpool):
        self.ctx = ctx
        self.dbpool = dbpool
        self.ip = ip
        self.index = index

    def render(self, data):
        raise NotImplementedError

    def convertFragments(self, data):
        result = []
        if not data:
            return []
        for column, value, sort in data:
            result.append((column,
                           FragmentMixIn(self.dbpool,
                                         docFactory=loaders.stan(value)),
                           sort))
        return result

    def collectDetails(self):
        d = self.dbpool.runQueryInPast(self.ctx,
                                 self.query,
                                 { 'ip': str(self.ip),
                                   'port': self.index })
        d.addCallback(lambda x: x and self.render(x) or None)
        d.addCallback(self.convertFragments)
        return d

class PortDetailsRemoteLldp(PortRelatedDetails):

    query = """
SELECT DISTINCT re.name, rp.name
FROM lldp_full l, equipment_full re, equipment_full le, port_full lp, port_full rp
WHERE (l.mgmtip=le.ip OR l.sysname=le.name)
AND le.ip=%(ip)s AND lp.equipment=le.ip
AND l.portdesc=lp.name
AND lp.index=%(port)s
AND l.equipment=re.ip
AND l.port=rp.index AND rp.equipment=re.ip
AND l.deleted='infinity' AND re.deleted='infinity'
AND le.deleted='infinity' AND lp.deleted='infinity'
AND rp.deleted='infinity'
"""

    def render(self, data):
        return [
            ('LLDP (remote) / Host',
             T.invisible(data=data[0][0],
                         render=T.directive("hostname")),
             data[0][0]),
            ('LLDP (remote) / Port',
             data[0][1], None)
            ]

class PortDetailsVlan(PortRelatedDetails):

    
    query = """
SELECT COALESCE(l.vid, r.vid) as vvid, l.name, r.name
FROM
(SELECT * FROM vlan_full
 WHERE deleted='infinity' AND equipment=%(ip)s AND port=%(port)s AND type='local') l
FULL OUTER JOIN
(SELECT * FROM vlan_full
 WHERE deleted='infinity' AND equipment=%(ip)s AND port=%(port)s AND type='remote') r
ON l.vid = r.vid
ORDER BY vvid
"""

    def render(self, data):
        r = []
        i = 0
        vlanlist = []
        notpresent = T.td(_class="notpresent")[
            T.acronym(title="Not present or no information from remote")["N/A"]]
        for row in data:
            if row[1] is not None:
                vlanlist.append(str(row[0]))
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
        vlantable = T.table(_class="vlan")[
            T.thead[T.td["VID"], T.td["Local"], T.td["Remote"]], r]
        return [('VLAN',
                 [[ [T.span(data=v, render=T.directive("vlan")), " "]
                    for v in vlanlist ],
                  T.span(render=T.directive("tooltip"),
                         data=vlantable)],
                 ", ".join(vlanlist))]

class PortDetailsFdb(PortRelatedDetails):

    query = """
SELECT DISTINCT f.mac, MIN(a.ip::text)::inet AS minip
FROM fdb_full f LEFT OUTER JOIN arp_full a
ON a.mac = f.mac AND a.deleted='infinity'
WHERE f.equipment=%(ip)s
AND f.port=%(port)s
AND f.deleted='infinity'
GROUP BY f.mac
ORDER BY minip ASC, f.mac
LIMIT 20
"""

    def render(self, data):
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
        if len(r) == 1:
            return [('FDB',
                     [T.span(data=data[0][0], render=T.directive("mac")),
                      data[0][1] and [", ", T.span(data=data[0][1],
                                                   render=T.directive("ip"))] or ""],
                     1)]
        return [('FDB',
                 [len(r) == 20 and "20+" or len(r),
                  T.span(render=T.directive("tooltip"),
                         data=T.table(_class="mac")[
                        T.thead[T.td["MAC"], T.td["IP"]], r])],
                 len(r) == 20 and 21 or len(r))]

class PortDetailsSpeed(PortRelatedDetails):

    query = """
SELECT p.speed, p.duplex, p.autoneg
FROM port_full p
WHERE p.equipment=%(ip)s AND p.index=%(port)s
AND p.deleted='infinity'
"""

    def render(self, data):
        result = []
        speed, duplex, autoneg = data[0]
        if speed is None and duplex is None and autoneg is None:
            return None
        if speed:
            if speed >= 1000:
                sspeed = "%s Gbit/s" % (str(speed/1000.))
            else:
                sspeed = "%d Mbit/s" % speed
            result.append(("Speed / Speed",
                           sspeed,
                           speed))
        if duplex:
            result.append(("Speed / Duplex",
                           duplex, None))
        if autoneg is not None:
            result.append(("Speed / Autoneg",
                            autoneg and "enabled" or "disabled",
                            autoneg))
        return result

class PortDetailsMac(PortRelatedDetails):

    query = """
SELECT mac
FROM port_full
WHERE equipment=%(ip)s AND index=%(port)s
AND mac IS NOT NULL
AND deleted='infinity'
"""

    def render(self, data):
        return [("MAC", T.invisible(data=data[0][0],
                                    render=T.directive("mac")),
                 data[0][0])]

class PortDetailsTrunkComponents(PortRelatedDetails):

    query = """
SELECT p.name
FROM trunk_full t, port_full p
WHERE t.equipment=%(ip)s AND t.port=%(port)s
AND p.equipment=t.equipment
AND p.index=t.member
AND t.deleted='infinity'
AND p.deleted='infinity'
ORDER BY p.index
"""

    def render(self, data):
        return [("Trunk / Ports",
                 [[x[0], " "] for x in data],
                 len(data))]

class PortDetailsTrunkMember(PortRelatedDetails):

    query = """
SELECT p.name
FROM trunk_full t, port_full p
WHERE t.equipment=%(ip)s AND t.member=%(port)s
AND p.equipment=t.equipment
AND p.index=t.port
AND p.deleted='infinity'
AND t.deleted='infinity'
LIMIT 1
"""

    def render(self, data):
        return [("Trunk / Member of",
                 data[0][0], None)]

class PortDetailsSonmp(PortRelatedDetails):

    query = """
SELECT DISTINCT remoteip, remoteport
FROM sonmp_full WHERE equipment=%(ip)s
AND port=%(port)s
AND deleted='infinity'
"""

    def render(self, data):
        return [("SONMP / IP",
                 T.invisible(data=data[0][0],
                             render=T.directive("ip")),
                 data[0][0]),
                ("SONMP / Port",
                 data[0][1], None)]

class PortDetailsEdp(PortRelatedDetails):

    query = """
SELECT DISTINCT sysname, remoteslot, remoteport
FROM edp_full WHERE equipment=%(ip)s
AND port=%(port)s
And deleted='infinity'
"""

    def render(self, data):
        return [("EDP / Host",
                 T.invisible(data=data[0][0],
                             render=T.directive("hostname")),
                 data[0][0]),
                ("EDP / Port",
                 "%d/%d" % (data[0][1], data[0][2]),
                 data[0][1]*1000 + data[0][2])]
    
class PortDetailsDiscovery(PortRelatedDetails):

    def render(self, data):
        return [("%s  / Host" % self.discovery_name,
                 T.invisible(data=data[0][2],
                             render=T.directive("hostname")),
                 data[0][2]),
                ("%s  / IP" % self.discovery_name,
                 T.invisible(data=data[0][0],
                             render=T.directive("ip")),
                 data[0][0]),
                ("%s  / Description" % self.discovery_name,
                 data[0][1], None),
                ("%s  / Port" % self.discovery_name,
                 data[0][3], None)]

class PortDetailsLldp(PortDetailsDiscovery):

    discovery_name = "LLDP"
    query = """
SELECT DISTINCT mgmtip, sysdesc, sysname, portdesc
FROM lldp_full WHERE equipment=%(ip)s
AND port=%(port)s
AND deleted='infinity'
"""

class PortDetailsCdp(PortDetailsDiscovery):
    
    discovery_name = "CDP"
    query = """
SELECT DISTINCT mgmtip, platform, sysname, portname
FROM cdp_full WHERE equipment=%(ip)s
AND port=%(port)s
AND deleted='infinity'
"""
