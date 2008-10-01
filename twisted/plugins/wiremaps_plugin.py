from zope.interface import implements
from twisted.python import usage
from twisted.application.service import IServiceMaker
from twisted.plugin import IPlugin
from wiremaps.core import service

class Options(usage.Options):
    synopsis = "[options]"
    longdesc = "Make a wiremaps server."
    optParameters = [
        ['config', 'c', '/etc/wiremaps/wiremaps.cfg'],
        ['port', 'p', 8087],
        ]
    
class WiremapsServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    
    tapname = "wiremaps"
    description = "Wiremaps server."
    options = Options
    
    def makeService(self, config):
        return service.makeService(config)

wiremapsServer = WiremapsServiceMaker()
