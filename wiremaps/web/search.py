import re
from IPy import IP

from nevow import rend, loaders
from nevow import tags as T

from wiremaps.web.common import FragmentMixIn, RenderMixIn
from wiremaps.web.json import JsonPage

class SearchResource(rend.Page):

    addSlash = True
    docFactory = T.html [ T.body [ T.p [ "Nothing here" ] ] ]

    def __init__(self, dbpool):
        self.dbpool = dbpool
        rend.Page.__init__(self)

    def childFactory(self, ctx, name):
        """Dispatch to the correct page to handle the search request.

        We can search:
         - a MAC address
         - an IP address
         - an hostname
        """
        if re.match(r'^(?:[0-9a-fA-F]{1,2}:){5}[0-9a-fA-F]{1,2}$', name):
            return SearchMacResource(self.dbpool, name)
        try:
            ip = IP(name)
        except ValueError:
            pass
        else:
            return SearchIPResource(self.dbpool, str(ip))
        # Should be a hostname then
        return SearchHostnameResource(self.dbpool, name)

class SearchMacResource(JsonPage, RenderMixIn):

    def __init__(self, dbpool, mac):
        self.mac = mac
        self.dbpool = dbpool
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        d = self.dbpool.runQuery("SELECT DISTINCT ip FROM arp WHERE mac=%(mac)s",
                                 {'mac': self.mac})
        d.addCallback(self.gotIPs)
        return d

    def gotIPs(self, ips):
        self.ips = [x[0] for x in ips]
        if not self.ips:
            fragment = T.span [ "I cannot find any IP associated to this MAC address" ]
        elif len(self.ips) == 1:
            fragment = T.span [ "This MAC address is associated with IP ",
                                T.invisible(data=self.ips[0],
                                            render=T.directive("ip")), "." ]
        else:
            fragment = T.span [ "This MAC address is associated with the following IPs: ",
                                T.ul [[ T.li[T.invisible(data=ip,
                                                          render=T.directive("ip")),
                                              " "] for ip in self.ips ] ], "." ]
        fragment = FragmentMixIn(self.dbpool, docFactory=loaders.stan(fragment))
        results = [ fragment ]
        for ip in self.ips:
            results.append(SearchIPInEquipment(self.dbpool, ip))
            results.append(SearchIPInSonmp(self.dbpool, ip))
            results.append(SearchIPInLldp(self.dbpool, ip))
            results.append(SearchIPInCdp(self.dbpool, ip))
        results.append(SearchMacInFdb(self.dbpool, self.mac))
        return results

class SearchIPResource(JsonPage, RenderMixIn):

    def __init__(self, dbpool, ip):
        self.ip = ip
        self.dbpool = dbpool
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        d = self.dbpool.runQuery("SELECT DISTINCT mac FROM arp WHERE ip=%(ip)s",
                                 {'ip': self.ip})
        d.addCallback(self.gotMAC)
        return d

    def gotMAC(self, macs):
        if not macs:
            fragment = T.span [ "I cannot find any MAC associated to this IP address" ]
        else:
            self.mac = macs[0][0]
            fragment = T.span [ "This IP address ",
                                T.invisible(data=self.ip,
                                            render=T.directive("ip")),
                                " is associated with MAC ",
                                T.invisible(data=self.mac,
                                            render=T.directive("mac")), "." ]
        fragment = FragmentMixIn(self.dbpool, docFactory=loaders.stan(fragment))
        return [ fragment,
                 SearchIPInSonmp(self.dbpool, self.ip),
                 SearchIPInLldp(self.dbpool, self.ip),
                 SearchIPInCdp(self.dbpool, self.ip),
                 SearchMacInFdb(self.dbpool, self.mac) ]

class SearchHostnameResource(JsonPage, RenderMixIn):

    def __init__(self, dbpool, name):
        self.name = name
        self.dbpool = dbpool
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        d = self.dbpool.runQuery("SELECT DISTINCT name, ip FROM equipment "
                                 "WHERE name=%(name)s "
                                 "OR name LIKE '%%'||%(name)s||'%%' "
                                 "ORDER BY name",
                                 {'name': self.name})
        d.addCallback(self.gotIP)
        return d

    def gotIP(self, ips):
        if not ips:
            fragment = T.span [ "I cannot find any IP for this host" ]
            fragment = FragmentMixIn(self.dbpool, docFactory=loaders.stan(fragment))
            return [ fragment ]
        fragments = []
        for ip in ips:
            fragment = T.span [ "The hostname ",
                                T.span(_class="data")[ip[0]],
                                " is associated with IP ",
                                T.a(href="equipment/%s/" % ip[1])[ip[1]],
                                ". You can ",
                                T.a(href="search/%s/" % ip[1])["search on it"],
                                " to find more results." ]
            fragment = FragmentMixIn(self.dbpool, docFactory=loaders.stan(fragment))
            fragments.append(fragment)
        return fragments

class SearchMacInFdb(rend.Fragment, RenderMixIn):

    docFactory = loaders.stan(T.span(render=T.directive("macfdb"),
                                     data=T.directive("macfdb")))

    def __init__(self, dbpool, mac):
        self.mac = mac
        self.dbpool = dbpool
        rend.Fragment.__init__(self)

    def data_macfdb(self, ctx, data):
        # We filter out port with too many MAC
        return self.dbpool.runQuery("SELECT DISTINCT e.name, e.ip, p.name, p.index "
                                    "FROM fdb f, equipment e, port p "
                                    "WHERE f.mac=%(mac)s "
                                    "AND f.port=p.index AND f.equipment=e.ip "
                                    "AND p.equipment=e.ip "
                                    "AND (SELECT COUNT(*) FROM fdb WHERE port=p.index "
                                    "AND equipment=e.ip) <= 60"
                                    "ORDER BY e.name, p.index",
                                    {'mac': self.mac})

    def render_macfdb(self, ctx, data):
        if not data:
            return ctx.tag["I did not find this MAC on any FDB entry."]
        return ctx.tag["This MAC was found on the following equipments: ",
                       T.ul [ [ T.li[
                    T.invisible(data=l[0],
                                render=T.directive("hostname")),
                    " (", T.invisible(data=l[1],
                                      render=T.directive("ip")), ") "
                    "on port ", T.span(_class="data") [ l[2] ] ]
                         for l in data] ] ]

class SearchIPInEquipment(rend.Fragment, RenderMixIn):

    docFactory = loaders.stan(T.span(render=T.directive("ipeqt"),
                                     data=T.directive("ipeqt")))

    def __init__(self, dbpool, ip):
        self.ip = ip
        self.dbpool = dbpool
        rend.Fragment.__init__(self)

    def data_ipeqt(self, ctx, data):
        return self.dbpool.runQuery("SELECT e.name FROM equipment e "
                                    "WHERE e.ip=%(ip)s",
                                    {'ip': self.ip})

    def render_ipeqt(self, ctx, data):
        if not data:
            return ctx.tag["The IP ",
                           T.span(data=self.ip,
                                  render=T.directive("ip")),
                           " is not owned by a known equipment."]
        return ctx.tag["The IP ",
                       T.span(data=self.ip,
                              render=T.directive("ip")),
                       " belongs to ",
                       T.span(data=data[0][0],
                              render=T.directive("hostname")),
                       "."]

class SearchIPInSonmp(rend.Fragment, RenderMixIn):

    docFactory = loaders.stan(T.span(render=T.directive("sonmp"),
                                     data=T.directive("sonmp")))

    def __init__(self, dbpool, ip):
        self.ip = ip
        self.dbpool = dbpool
        rend.Fragment.__init__(self)

    def data_sonmp(self, ctx, data):
        return self.dbpool.runQuery("SELECT e.name, p.name, s.remoteport "
                                    "FROM equipment e, port p, sonmp s "
                                    "WHERE s.remoteip=%(ip)s "
                                    "AND s.port=p.index AND p.equipment=e.ip "
                                    "AND s.equipment=e.ip "
                                    "ORDER BY e.name", {'ip': self.ip})

    def render_sonmp(self, ctx, data):
        if not data:
            return ctx.tag["This IP has not been seen with SONMP."]
        return ctx.tag["This IP has been seen with SONMP: ",
                       T.ul[ [ T.li [
                    "from port ",
                    T.span(_class="data") [d[1]],
                    " of ",
                    T.span(data=d[0],
                           render=T.directive("hostname")),
                    " connected to port ",
                    T.span(data=d[2], _class="data",
                           render=T.directive("sonmpport")) ] for d in data] ] ]

class SearchIPInDiscovery(rend.Fragment, RenderMixIn):

    docFactory = loaders.stan(T.span(render=T.directive("discovery"),
                                     data=T.directive("discovery")))
    discovery_name = "unknown"

    def __init__(self, dbpool, ip):
        self.ip = ip
        self.dbpool = dbpool
        rend.Fragment.__init__(self)

    def render_discovery(self, ctx, data):
        if not data:
            return ctx.tag["This IP has not been seen with %s." % self.discovery_name]
        return ctx.tag["This IP has been seen with %s: " % self.discovery_name,
                       T.ul [ [ T.li [
                    "from port ",
                    T.span(_class="data") [d[1]],
                    " of ",
                    T.span(data=d[0],
                           render=T.directive("hostname")),
                    " connected to port ",
                    T.span(_class="data") [d[2]],
                    " of ",
                    T.span(data=d[3],
                           render=T.directive("hostname"))] for d in data] ] ]

class SearchIPInLldp(SearchIPInDiscovery):

    discovery_name = "LLDP"

    def data_discovery(self, ctx, data):
        return self.dbpool.runQuery("SELECT e.name, p.name, l.portdesc, l.sysname "
                                    "FROM equipment e, port p, lldp l "
                                    "WHERE l.mgmtip=%(ip)s "
                                    "AND l.port=p.index AND p.equipment=e.ip "
                                    "AND l.equipment=e.ip "
                                    "ORDER BY e.name", {'ip': self.ip})

class SearchIPInCdp(SearchIPInDiscovery):

    discovery_name = "CDP"

    def data_discovery(self, ctx, data):
        return self.dbpool.runQuery("SELECT e.name, p.name, c.portname, c.sysname "
                                    "FROM equipment e, port p, cdp c "
                                    "WHERE c.mgmtip=%(ip)s "
                                    "AND c.port=p.index AND p.equipment=e.ip "
                                    "AND c.equipment=e.ip "
                                    "ORDER BY e.name", {'ip': self.ip})
