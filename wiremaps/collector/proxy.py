from pynetsnmp.twistedsnmp import AgentProxy as original_AgentProxy
from pynetsnmp.twistedsnmp import translateOid
from twisted.internet import defer

class AgentProxy(original_AgentProxy):
    """Act like AgentProxy but handles walking itself"""

    def walk(self, oid, timeout=None, retryCount=None):
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
        d = original_AgentProxy.walk(self.proxy, self.baseoid)
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
        d = original_AgentProxy.walk(self.proxy, self.lastoid)
        d.addCallback(self.getMore)
        d.addErrback(self.fireError)
        return None

    def fireError(self, error):
        self.defer.errback(error)
        self.defer = None

        
