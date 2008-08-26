from nevow import rend
from nevow import tags as T

class RenderMixIn:
    """Helper class that provide some builtin fragments"""

    def render_ip(self, ctx, ip):
        d = self.dbpool.runQuery("SELECT ip FROM equipment WHERE ip=%(ip)s",
                                 {'ip': ip})
        d.addCallback(lambda x: x and
                      T.a(href="equipment/%s/" % ip) [ ip ] or
                      T.a(href="search/%s/" % ip) [ ip ])
        return d

    def render_mac(self, ctx, mac):
        return T.a(href="search/%s/" % mac) [ mac ]

    def render_hostname(self, ctx, name):
        d = self.dbpool.runQuery("SELECT name FROM equipment WHERE name=%(name)s",
                                 {'name': name})
        d.addCallback(lambda x: x and
                      T.a(href="equipment/%s/" % name) [ name ] or
                      T.a(href="search/%s/" % name) [ name ])
        return d    

    def render_sonmpport(self, ctx, port):
        if port < 64:
            return ctx.tag[port]
        if port < 65536:
            return ctx.tag[int(port/64)+1, "/", port%64]
        return ctx.tag["%02x:%02x:%02x" % (port >> 16, (port & 0xffff) >> 8,
                                           (port & 0xff))]                      

class FragmentMixIn(rend.Fragment, RenderMixIn):
    def __init__(self, dbpool, *args, **kwargs):
        self.dbpool = dbpool
        rend.Fragment.__init__(self, *args, **kwargs)
