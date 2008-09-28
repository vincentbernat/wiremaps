# -*- python -*-

from twisted.application import service
import wiremaps

options = { 'config': "wiremaps.cfg",
            'port': 8087 }
ser = wiremaps.makeService(options)
application = service.Application('Wiremaps')
ser.setServiceParent(service.IServiceCollection(application))
