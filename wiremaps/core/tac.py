from twisted.application import service
from wiremaps.core import service as ws

application = service.Application('wiremaps')
ws.makeService({"config": "/etc/wiremaps/wiremaps.cfg",
                "interface": '127.0.0.1',
                "port": 8087}).setServiceParent(
    service.IServiceCollection(application))
