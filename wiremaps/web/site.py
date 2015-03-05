import os

from pkg_resources import resource_string, resource_filename
from twisted.python import util
from zope.interface import implements
from nevow import rend, loaders
from nevow import tags as T
from nevow import static, inevow

from wiremaps.web.api import ApiResource


class MainPage(rend.Page):

    docFactory = loaders.xmlstr(resource_string(__name__, "main.xhtml"))

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
        return static.File(resource_filename(__name__, "static"))

    def child_api(self, ctx):
        return ApiResource(self.config, self.dbpool, self.collector)

    def childFactory(self, ctx, node):
        """Backward compatibility with previous API"""
        if node in ["equipment", "search", "complete", "past", "images"]:
            inevow.IRequest(ctx).rememberRootURL()
            return RedirectApi()
        return None


class RedirectApi(object):
    """Redirect to new API.

    rememberRootURL() should be done at root!
    """
    implements(inevow.IResource)

    def locateChild(self, ctx, segments):
        return self, ()

    def renderHTTP(self, ctx):
        request = inevow.IRequest(ctx)
        request.redirect("%sapi/1.0%s" % (request.getRootURL(), request.uri))
        request.setResponseCode(301)
        return ''
