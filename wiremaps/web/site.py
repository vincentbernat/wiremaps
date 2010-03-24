import os

from twisted.python import util
from nevow import rend, appserver, loaders, page
from nevow import tags as T
from nevow import static

from wiremaps.web.api import ApiResource

class MainPage(rend.Page):

    docFactory = loaders.xmlfile(util.sibpath(__file__, "main.xhtml"))

    def __init__(self, config, dbpool, collector):
        self.config = config['web']
        self.dbpool = dbpool
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

    def child_api(self, ctx):
        return ApiResource(self.config, self.dbpool, self.collector)
