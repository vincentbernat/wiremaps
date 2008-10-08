from twisted.python import log
from twisted.internet import reactor, defer
from twisted.enterprise import adbapi

class Database:
    
    def __init__(self, config):
        p = adbapi.ConnectionPool("pyPgSQL.PgSQL",
                                  "%s:%d:%s:%s:%s" % (
                config['database'].get('host', 'localhost'),
                config['database'].get('port', 5432),
                config['database']['database'],
                config['database']['username'],
                config['database']['password']))
        self.pool = p
        reactor.callLater(0, self.upgradeDatabase)

    def upgradeDatabase(self):
        """Try to upgrade database by running various upgrade_* functions.

        Those functions should be run as sooner as possible. However,
        to keep the pattern simple, we don't make them exclusive: the
        application can run while the upgrade is in progress.
        """
        fs = [x for x in dir(self) if x.startswith("upgradeDatabase_")]
        fs.sort()
        d = defer.succeed(None)
        for f in fs:
            d.addCallback(lambda x: log.msg("Upgrade database: %s" %
                                            getattr(self, f).__doc__))
            d.addCallback(lambda x: getattr(self, f)())
        d.addCallbacks(
            lambda x: log.msg("database upgrade completed"),
            lambda x: log.err("unable to update database: %s" % str(x)))
        return d

    def upgradeDatabase_01(self):
        """add 'last' column to 'equipment' table"""
        d = self.pool.runOperation("SELECT last FROM equipment LIMIT 1")
        d.addErrback(lambda x: self.pool.runOperation(
                "ALTER TABLE equipment "
                "ADD COLUMN last TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
        return d
