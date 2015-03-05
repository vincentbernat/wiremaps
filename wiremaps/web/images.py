import os.path
import re

from pkg_resources import resource_filename
from twisted.python import util
from twisted.enterprise import adbapi
from twisted.internet import defer

from nevow import rend, appserver, static, inevow
from nevow.url import URLRedirectAdapter
from IPy import IP

class ImageResource(rend.Page):

    image_dir = resource_filename(__name__, "images")

    def __init__(self, dbpool):
        self.dbpool = dbpool
        rend.Page.__init__(self)

    def locateChild(self, ctx, segments):
        """Child can either be:
         - an OID (better started with a dot)
         - an IP
         - an hostname (should at least contains a character)
        """
        if segments == ('',):
            return appserver.NotFound
        oid = segments[0]

        # Is it an IP?
        try:
            ip = IP(oid)
            d = self.dbpool.runQueryInPast(ctx,
                                     "SELECT oid FROM equipment_full "
                                     "WHERE ip=%(ip)s AND deleted='infinity'",
                                     {'ip': str(ip)})
        except ValueError:
            # Is it an hostname or an OID?
            if not re.match(r"[0-9\.]+", oid):
                # This should be an hostname
                d = self.dbpool.runQueryInPast(ctx,
                                         "SELECT oid FROM equipment_full "
                                         "WHERE deleted='infinity' "
                                         "AND (name=%(name)s "
                                         "OR name ILIKE %(name)s||'.%%')",
                                         {'name': oid})
            else:
                # It's an OID!
                if oid.startswith("."):
                    oid = oid[1:]
                if oid.endswith("."):
                    oid = oid[:-1]
                target = os.path.join(self.image_dir, "%s.png" % oid)
                if os.path.exists(target):
                    return static.File(target), ()
                return static.File(os.path.join(self.image_dir, "unknown.png")), ()
        d.addCallback(self.getOid, ctx)
        return d

    def getOid(self, oid, ctx):
        """
        Return a redirect to the appropriate file

        @param oid: OID to use to locate image (can be C{[[oid],...]})
        @return: C{static.File} of the corresponding image
        """
        if oid:
            if type(oid) == list:
                oid = oid[0][0]
            request = inevow.IRequest(ctx)
            print request.URLPath().child(oid)
            return URLRedirectAdapter(request.URLPath().child(oid)), ()
        return appserver.NotFound
