import os

from twisted.python import util
from nevow import rend, appserver, loaders, page
from nevow import tags as T
from nevow import static

from wiremaps.web.images import ImageResource
from wiremaps.web.equipment import EquipmentResource
from wiremaps.web.search import SearchResource
from wiremaps.web.complete import CompleteResource
from wiremaps.web.timetravel import PastResource, IPastDate, PastConnectionPool

class MainPage(rend.Page):

    docFactory = loaders.xmlfile(util.sibpath(__file__, "main.xhtml"))

    def __init__(self, config, dbpool, collector):
        self.config = config['web']
        self.dbpool = PastConnectionPool(dbpool)
        self.collector = collector
        rend.Page.__init__(self)

    def render_logo(self, ctx, data):
        if 'logo' in self.config and os.path.exists(self.config['logo']):
            return T.img(src="customlogo")
        return "To place your logo here, see the documentation"

    def child_customlogo(self, ctx):
        return static.File(self.config['logo'])

    def child_static(self, ctx):
        return static.File(util.sibpath(__file__, "static"))

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
