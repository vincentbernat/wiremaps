from twisted.python import util
from nevow import rend, appserver, loaders, page
from nevow import tags as T
from nevow import static

from wiremaps.web.images import ImageResource
from wiremaps.web.equipment import EquipmentResource
from wiremaps.web.search import SearchResource

class MainPage(rend.Page):

    docFactory = loaders.xmlfile(util.sibpath(__file__, "main.xhtml"))

    def __init__(self, config, dbpool, collector):
        self.config = config['web']
        self.dbpool = dbpool
        self.collector = collector
        rend.Page.__init__(self)

    def render_logo(self, ctx, data):
        return T.img(src="static/%s" % self.config['logo'])

    def child_static(self, ctx):
        return static.File(util.sibpath(__file__, "static"))

    def child_images(self, ctx):
        return ImageResource(self.dbpool)

    def child_equipment(self, ctx):
        return EquipmentResource(self.dbpool, self.collector)

    def child_search(self, ctx):
        return SearchResource(self.dbpool)

