import snmp
from snmp import AgentProxy as original_AgentProxy
from twisted.internet import defer

def translateOid(oid):
    return [int(x) for x in oid.split(".") if x]

class AgentProxy(original_AgentProxy):
    """Act like AgentProxy but handles walking itself"""

    use_getbulk = True

    def getbulk(self, oid, *args):
        if self.use_getbulk and self.version == 2:
            return original_AgentProxy.getbulk(self, oid, *args)
        d = self.getnext(oid)
        d.addErrback(lambda x: x.trap(snmp.SNMPEndOfMibView,
                                      snmp.SNMPNoSuchName) and {})
        return d

    def walk(self, oid):
        """Real walking.
        
        Return the list of oid retrieved
        """
        return Walker(self, oid)()
        
class Walker(object):
    """SNMP walker class"""

    def __init__(self, proxy, baseoid):
        self.baseoid = baseoid
        self.lastoid = baseoid
        self.proxy = proxy
        self.results = {}
        self.defer = defer.Deferred()

    def __call__(self):
        d = self.proxy.getbulk(self.baseoid)
        d.addErrback(lambda x: x.trap(snmp.SNMPEndOfMibView,
                                      snmp.SNMPNoSuchName) and {})
        d.addCallback(self.getMore)
        d.addErrback(self.fireError)
        return self.defer

    def getMore(self, x):
        stop = False
        for o in x:
            if o in self.results:
                stop = True
                continue
            if translateOid(o)[:len(translateOid(self.baseoid))] != \
                    translateOid(self.baseoid):
                stop = True
                continue
            self.results[o] = x[o]
            if translateOid(self.lastoid) < translateOid(o):
                self.lastoid = o
        if stop or not x:
            self.defer.callback(self.results)
            self.defer = None
            return
        d = self.proxy.getbulk(self.lastoid)
        d.addErrback(lambda x: x.trap(snmp.SNMPEndOfMibView,
                                      snmp.SNMPNoSuchName) and {})
        d.addCallback(self.getMore)
        d.addErrback(self.fireError)
        return None

    def fireError(self, error):
        self.defer.errback(error)
        self.defer = None

        
