# When modifying this class, also update doc/database.sql

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
            d.addCallback(lambda x,ff: log.msg("Upgrade database: %s" %
                                            getattr(self, ff).__doc__), f)
            d.addCallback(lambda x,ff: getattr(self, ff)(), f)
        d.addCallbacks(
            lambda x: log.msg("database upgrade completed"),
            self.upgradeFailure)
        return d

    def upgradeFailure(self, fail):
        """When upgrade fails, just stop the reactor..."""
        log.msg("unable to update database: %s" % str(fail))
        reactor.stop()

    def upgradeDatabase_01(self):
        """check the schema to be compatible with time travel function"""
        # The database schema before time travel function is too
        # different to have a clean upgrade. This is better to start
        # from scratch and ask the user to repopulate the database.

        def upgrade():
            print("""!!! Incompatible database schema.

The  current   schema  is  incompatible  with  the   new  time  travel
function.  Since the schema  has been  updated a  lot to  support this
functionality, there  is no seamless upgrade provided  to upgrade. You
should drop  the current database (with  dropdb) and create  a new one
(with createdb) and populate it with the content of database.sql, like
this was done when installing Wiremaps for the first time.

Alternatively, you  can just create  a new database (and  populate it)
and change wiremaps  configuration to use it. The  old database can be
used by another instance of Wiremaps or as a rollback.

After  this step,  you should  repopulate data  by asking  Wiremaps to
rebrowse all hosts.
""")
            raise NotImplementedError("Incompatible database schema.")

        d = self.pool.runOperation("SELECT created FROM equipment LIMIT 1")
        d.addErrback(lambda x: upgrade())
        return d
