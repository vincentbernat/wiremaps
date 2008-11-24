from cStringIO import StringIO

from twisted.internet import defer
from twisted.python import failure

from nevow import rend, flat
from nevow import json, inevow, context
from nevow import tags as T

from pyPgSQL import PgSQL

class JsonPage(rend.Page):

    flattenFactory = lambda self, *args: flat.flattenFactory(*args)
    addSlash = True

    def renderHTTP(self, ctx):
        request = inevow.IRequest(ctx)
        if inevow.ICurrentSegments(ctx)[-1] != '':
            request.redirect(request.URLPath().child(''))
            return ''
        request.setHeader("Content-Type",
                          "application/json; charset=UTF-8")
        d = defer.maybeDeferred(self.data_json, ctx, None)
        d.addCallback(lambda x: self.render_json(ctx, x))
        return d

    def render_json(self, ctx, data):
        """Render the given data in a proper JSON string"""

        def sanitize(data, d=None):
            """Nevow JSON serializer is not able to handle some types.

            We convert those types in proper types:
             - string to unicode string
             - PgSQL result set into list
             - handling of deferreds
            """
            if type(data) in [list, tuple] or isinstance(data, PgSQL.PgResultSet):
                return [sanitize(x, d) for x in data]
            if isinstance(data, PgSQL.PgBooleanType):
                if data:
                    return u"true"
                return u"false"
            if type(data) == str:
                return unicode(data, errors='ignore')
            if isinstance(data, rend.Fragment):
                io = StringIO()
                writer = io.write
                finisher = lambda result: io.getvalue()
                newctx = context.PageContext(parent=ctx, tag=data)
                data.rememberStuff(newctx)
                doc = data.docFactory.load()
                newctx = context.WovenContext(newctx, T.invisible[doc])
                fl = self.flattenFactory(doc, newctx, writer, finisher)
                fl.addCallback(sanitize, None)
                d.append(fl)
                return fl
            if isinstance(data, defer.Deferred):
                if data.called:
                    return sanitize(data.result)
                return data
            if isinstance(data, failure.Failure):
                return unicode(
                    "<span class='error'>An error occured (%s)</span>" % data.getErrorMessage(),
                    errors='ignore')
            return data

        def serialize(data):
            return json.serialize(sanitize(data))

        d = []
        data = sanitize(data, d)
        d = defer.DeferredList(d)
        d.addCallback(lambda x: serialize(data))
        return d
