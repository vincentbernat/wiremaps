from pynetsnmp.twistedsnmp import AgentProxy as original_AgentProxy
from pynetsnmp.twistedsnmp import translateOid

class AgentProxy(original_AgentProxy):
    """Act like AgentProxy but handles walking itself"""

    def walk(self, oid, timeout=None, retryCount=None):
        """Real walking.
        
        Return the list of oid retrieved
        """
        
        def reallyWalk(self, lastresult, results, baseoid, oid, timeout, retryCount):
            """Walk and accumulate results"""
            if not lastresult:
                return
            lastoid = lastresult.keys()[0]
            if lastoid == oid:
                # Looping
                return
            if translateOid(lastoid)[:len(translateOid(baseoid))] != \
                    translateOid(baseoid):
                # No more results
                return results
            # Append the result
            results[lastoid] = lastresult[lastoid]
            d = original_AgentProxy.walk(self, lastoid, timeout, retryCount)
            d.addCallback(lambda x: reallyWalk(self, x, results, baseoid, lastoid,
                                               timeout, retryCount))
            return d
            
        d = original_AgentProxy.walk(self, oid, timeout, retryCount)
        d.addCallback(lambda x: reallyWalk(self, x, {}, oid, oid,
                                           timeout, retryCount))
        return d
        
