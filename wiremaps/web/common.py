import re

from twisted.names import client
from zope.interface import Interface

from nevow import rend
from nevow import tags as T, entities as E
from nevow.stan import Entity

class IApiVersion(Interface):
    """Remember the version used for API"""
    pass

class RenderMixIn:
    """Helper class that provide some builtin fragments"""

    def render_apiurl(self, ctx, data):
        return ctx.tag(href= "api/%s/%s" % (".".join([str(x) for x in IApiVersion(ctx)]),
                                            ctx.tag.attributes["href"]))

    def render_ip(self, ctx, ip):
        d = self.dbpool.runQueryInPast(ctx,
                                 "SELECT ip FROM equipment_full WHERE ip=%(ip)s "
                                 "AND deleted='infinity'",
                                 {'ip': ip})
        d.addCallback(lambda x: T.invisible[
                x and
                T.a(href="equipment/%s/" % ip, render=self.render_apiurl) [ ip ] or
                T.a(href="search/%s/" % ip, render=self.render_apiurl) [ ip ],
                T.invisible(data=self.data_solvedip, # Dunno why we can't use T.directive here
                            render=T.directive("solvedip"))])
        return d

    def data_solvedip(self, ctx, ip):
        ptr = '.'.join(ip.split('.')[::-1]) + '.in-addr.arpa'
        d = client.lookupPointer(ptr)
        d.addErrback(lambda x: None)
        return d

    def render_zwsp(self, name):
        return T.span(_class="wrap")[name]

    def render_solvedip(self, ctx, name):
        try:
            name = str(name[0][0].payload.name)
        except:
            return ctx.tag
        return ctx.tag[" ", E.harr, " ",
                       self.render_zwsp(name)]

    def render_mac(self, ctx, mac):
        return T.a(href="search/%s/" % mac, render=self.render_apiurl) [ mac ]

    def render_hostname(self, ctx, name):
        d = self.dbpool.runQueryInPast(ctx,
                                 "SELECT name FROM equipment_full "
                                 "WHERE lower(name)=lower(%(name)s) "
                                 "AND deleted='infinity'",
                                 {'name': name})
        d.addCallback(lambda x: x and
                      T.a(href="equipment/%s/" % name,
                          render=self.render_apiurl) [ self.render_zwsp(name) ] or
                      T.a(href="search/%s/" % name,
                          render=self.render_apiurl) [ self.render_zwsp(name) ])
        return d    

    def render_vlan(self, ctx, vlan):
        return T.a(href="search/%s/" % vlan,
                   render=self.render_apiurl) [ vlan ]

    def render_sonmpport(self, ctx, port):
        if port < 64:
            return ctx.tag[port]
        if port < 65536:
            return ctx.tag[int(port/64)+1, "/", port%64]
        return ctx.tag["%02x:%02x:%02x" % (port >> 16, (port & 0xffff) >> 8,
                                           (port & 0xff))]

    lastdigit = re.compile("^(.*?)(\d+-)?(\d+)$")
    def render_ports(self, ctx, ports):
        results = []
        for p in ports:
            if not results:
                results.append(p)
                continue
            lmo = self.lastdigit.match(results[-1])
            if not lmo:
                results.append(p)
                continue
            cmo = self.lastdigit.match(p)
            if not cmo:
                results.append(p)
                continue
            if int(lmo.group(3)) + 1 != int(cmo.group(3)) or \
                    lmo.group(1) != cmo.group(1):
                results.append(p)
                continue
            if lmo.group(2):
                results[-1] = "%s%s%s" % (lmo.group(1),
                                          lmo.group(2),
                                          cmo.group(3))
            else:
                results[-1] = "%s%s-%s" % (lmo.group(1),
                                           lmo.group(3),
                                           cmo.group(3))
        return ctx.tag[", ".join(results)]

    def render_tooltip(self, ctx, data):
        return T.invisible[
            T.a(_class="tt")[" [?] "],
            T.span(_class="tooltip")[
                T.div(_class="tooltipactions")[
                    T.ul[
                        T.li(_class="closetooltip")[
                            " [ ",
                            T.a(href="#")["close"],
                            " ]"]]],
                data]]

class FragmentMixIn(rend.Fragment, RenderMixIn):
    def __init__(self, dbpool, *args, **kwargs):
        self.dbpool = dbpool
        rend.Fragment.__init__(self, *args, **kwargs)
