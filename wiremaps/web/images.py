import os.path
import re

from twisted.python import util
from twisted.enterprise import adbapi
from twisted.internet import defer

from nevow import rend, appserver, static
from IPy import IP

class ImageResource(rend.Page):

    image_dir = util.sibpath(__file__, "images")

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

        # Is it really an OID?
        try:
            ip = IP(oid)
            d = self.dbpool.runQuery(ctx,
                                     "SELECT oid FROM equipment "
                                     "WHERE ip=%(ip)s AND deleted='infinity'",
                                     {'ip': str(ip)})
        except ValueError:
            # Well, this is not an IP
            if not re.match(r"[0-9\.]+", oid):
                # This should be an hostname
                d = self.dbpool.runQuery(ctx,
                                         "SELECT oid FROM equipment "
                                         "WHERE deleted='infinity' "
                                         "AND (name=%(name)s "
                                         "OR name ILIKE %(name)s||'.%%')",
                                         {'name': oid})
            else:
                d = defer.succeed([[oid]])
        d.addCallback(self.getOid)
        return d

    def getOid(self, oid):
        """Return the static file containing the image corresponding to OID.
        
        @param oid: OID to use to locate image (can be C{[[oid],...]})
        @return: C{static.File} of the corresponding image
        """
        if oid:
            if type([]) == list:
                oid = oid[0][0]
            if oid.startswith("."):
                oid = oid[1:]
            if oid.endswith("."):
                oid = oid[:-1]
            target = os.path.join(self.image_dir, "%s.png" % oid)
        if not oid or not os.path.exists(target):
            return static.File(os.path.join(self.image_dir, "unknown.png")), ()
        return static.File(target), ()
