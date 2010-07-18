import re

from nevow import rend, tags as T, loaders

from wiremaps.web.json import JsonPage

COMPLETE_LIMIT = 10

class CompleteResource(rend.Page):

    addSlash = True
    docFactory = loaders.stan(T.html [ T.body [ T.p [ "Nothing here" ] ] ])

    def __init__(self, dbpool):
        self.dbpool = dbpool
        rend.Page.__init__(self)

    MACSTART = re.compile("^(?:[0-9A-Fa-f]){1,2}:")
    IPSTART = re.compile("^(?:[0-9]){1,3}\.")

    def childFactory(self, ctx, name):
        """Dispatch to the correct completer.

        If the search term is less than 3 characters, then we return
        an empty set. Otherwise:
         - it can be a MAC (two digits, a double colon)
         - it can be an IP (digits and dots)
         - it can be an equipment name
        """
        if len(name) < 3:
            return CompleteEmptyResource()
        if self.MACSTART.match(name):
            return CompleteMacResource(self.dbpool, name)
        if self.IPSTART.match(name):
            return CompleteIpResource(self.dbpool, name)
        return CompleteEquipmentResource(self.dbpool, name)

class CompleteEmptyResource(JsonPage):
    """Return an empty set"""

    def data_json(self, ctx, data):
        return []

class CompleteMacResource(JsonPage):
    """Try to complete a MAC address.

    We can get a MAC address from:
     - port.mac
     - fdb.mac
     - arp.mac
    """

    def __init__(self, dbpool, mac):
        # Try to normalize MAC address: 0:12:2a:3: becomes 00:12:2a:03:
        # and 0:12:2a:3 becomes 00:12:2a:3
        self.mac = ":".join([len(x) and "%2s" % x or ""
                             for x in mac.split(":")[:-1]] +
                            [mac.split(":")[-1]]).replace(" ","0")
        self.dbpool = dbpool
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        d = self.dbpool.runQueryInPast(ctx,
                                 """SELECT t.mac, COUNT(t.mac) as c FROM
((SELECT mac FROM port_full WHERE deleted='infinity') UNION ALL
(SELECT mac FROM fdb_full WHERE deleted='infinity') UNION ALL
(SELECT mac FROM arp_full WHERE deleted='infinity')) AS t
WHERE CAST(t.mac AS text) ILIKE %(name)s||'%%'
GROUP BY t.mac ORDER BY c DESC LIMIT %(limit)s""",
                                 {'name': self.mac,
                                  'limit': COMPLETE_LIMIT})
        d.addCallback(lambda x: [y[0] for y in x])
        return d

class CompleteIpResource(JsonPage):
    """Try to complete an IP address.

    We can get IP address from:
     - equipment.ip
     - arp.ip
     - sonmp.remoteip
     - cdp.mgmtip
     - lldp.mgmtip
    """

    def __init__(self, dbpool, ip):
        self.ip = ip
        self.dbpool = dbpool
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        # We favour equipment.ip, then sonmp/cdp/lldp then arp
        d = self.dbpool.runQueryInPast(ctx,
                                 """SELECT ip FROM
((SELECT DISTINCT ip FROM equipment_full WHERE deleted='infinity'
  AND CAST(ip AS text) LIKE %(ip)s||'%%' LIMIT %(l)s) UNION
(SELECT DISTINCT mgmtip FROM lldp_full WHERE deleted='infinity'
 AND CAST(mgmtip AS text) LIKE %(ip)s||'%%' LIMIT %(l)s) UNION
(SELECT DISTINCT mgmtip FROM cdp_full WHERE deleted='infinity'
 AND CAST(mgmtip AS text) LIKE %(ip)s||'%%' LIMIT %(l)s) UNION
(SELECT DISTINCT remoteip FROM sonmp_full WHERE deleted='infinity'
 AND CAST(remoteip AS text) LIKE %(ip)s||'%%' LIMIT %(l)s) UNION
(SELECT DISTINCT ip FROM arp_full WHERE deleted='infinity'
 AND CAST(ip AS text) LIKE %(ip)s||'%%' LIMIT %(l)s)) AS foo
ORDER BY ip LIMIT %(l)s""", {'ip': self.ip,
                             'l': COMPLETE_LIMIT})
        d.addCallback(lambda x: [y[0] for y in x])
        return d

class CompleteEquipmentResource(JsonPage):
    """Try to complete a name.

    We can get names from:
     - equipment.name
     - edp.sysname
     - cdp.sysname
     - lldp.sysname
    """

    def __init__(self, dbpool, name):
        self.name = name
        self.dbpool = dbpool
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        # We favour equipment.name
        d = self.dbpool.runQueryInPast(ctx,
                                 """SELECT name FROM
((SELECT DISTINCT name FROM equipment_full WHERE deleted='infinity' AND name ILIKE %(name)s||'%%'
ORDER BY name LIMIT %(l)s) UNION
(SELECT DISTINCT sysname FROM
 ((SELECT sysname FROM lldp_full WHERE deleted='infinity') UNION
  (SELECT sysname FROM edp_full WHERE deleted='infinity') UNION
  (SELECT sysname FROM cdp_full WHERE deleted='infinity')) AS foo WHERE sysname ILIKE %(name)s||'%%' ORDER BY sysname LIMIT %(l)s))
AS bar ORDER BY name""", {'name': self.name,
                   'l': COMPLETE_LIMIT})
        d.addCallback(lambda x: [y[0] for y in x])
        return d
