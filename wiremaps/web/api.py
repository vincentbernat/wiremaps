from nevow import rend, tags as T, loaders

from wiremaps.web.images import ImageResource
from wiremaps.web.equipment import EquipmentResource
from wiremaps.web.search import SearchResource
from wiremaps.web.complete import CompleteResource
from wiremaps.web.timetravel import PastResource, IPastDate, PastConnectionPool
from wiremaps.web.common import IApiVersion

class ApiResource(rend.Page):
    """Web service for Wiremaps.
    """

    addSlash = True
    versions = [ "1.0" ]        # Valid versions
    docFactory = loaders.stan(T.html [ T.body [ T.p [ "Valid versions are:" ],
                                   T.ul [ [ T.li[v] for v in versions ] ] ] ])

    def __init__(self, config, dbpool, collector):
        self.config = config
        self.dbpool = dbpool
        self.collector = collector
        rend.Page.__init__(self)

    def childFactory(self, ctx, version):
        if version in ApiResource.versions:
            ctx.remember(version, IApiVersion)
            return ApiVersionedResource(self.config, self.dbpool, self.collector)
        return None

class ApiVersionedResource(rend.Page):
    """Versioned web service for Wiremaps."""

    addSlash = True
    docFactory = loaders.stan(T.html [ T.body [ T.p [ "Nothing here" ] ] ])

    def __init__(self, config, dbpool, collector):
        self.config = config
        self.dbpool = PastConnectionPool(dbpool)
        self.collector = collector
        rend.Page.__init__(self)

    def child_images(self, ctx):
        return ImageResource(self.dbpool)

    def child_equipment(self, ctx):
        return EquipmentResource(self.dbpool, self.collector)

    def child_search(self, ctx):
        return SearchResource(self.dbpool)

    def child_complete(self, ctx):
        return CompleteResource(self.dbpool)

    def child_past(self, ctx):
        try:
            # Check if we already got a date
            ctx.locate(IPastDate)
        except KeyError:
            return PastResource(self)
        return None
