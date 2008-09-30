from snmp import AgentProxy as original_AgentProxy
from twisted.internet import defer

def translateOid(oid):
    return [int(x) for x in oid.split(".") if x]

class AgentProxy(original_AgentProxy):
    """Act like AgentProxy but handles walking itself"""

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
        d = original_AgentProxy.getnext(self.proxy, self.baseoid)
        d.addCallback(self.getMore)
        d.addErrback(self.fireError)
        return self.defer

    def getMore(self, x):
        lastoid = x.keys()[0]
        if (translateOid(lastoid) <= translateOid(self.lastoid)) or \
                translateOid(lastoid)[:len(translateOid(self.baseoid))] != \
                translateOid(self.baseoid):
            self.defer.callback(self.results)
            self.defer = None
            return
        self.lastoid = lastoid
        self.results[lastoid] = x[lastoid]
        d = original_AgentProxy.getnext(self.proxy, self.lastoid)
        d.addCallback(self.getMore)
        d.addErrback(self.fireError)
        return None

    def fireError(self, error):
        self.defer.errback(error)
        self.defer = None

        
