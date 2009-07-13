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
        reactor.callLater(0, self.checkDatabase)

    def checkDatabase(self):
        """Check if the database is running. Otherwise, stop the reactor.

        If the database is running, launch upgrade process.
        """
        d = self.pool.runOperation("SELECT 1 FROM equipment LIMIT 1")
        d.addCallbacks(lambda _: self.upgradeDatabase(),
                       self.databaseFailure)
        return d

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

    def databaseFailure(self, fail):
        """Unable to connect to the database"""
        log.msg("unable to connect to database:\n%s" % str(fail))
        reactor.stop()

    def upgradeFailure(self, fail):
        """When upgrade fails, just stop the reactor..."""
        log.msg("unable to update database:\n%s" % str(fail))
        reactor.stop()

    def upgradeDatabase_01(self):
        """check the schema to be compatible with time travel function"""
        # The database schema before time travel function is too
        # different to have a clean upgrade. This is better to start
        # from scratch and ask the user to repopulate the database.

        def upgrade(err):
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
            raise NotImplementedError("Incompatible database schema:\n %s" % str(err))

        d = self.pool.runOperation("SELECT created FROM equipment LIMIT 1")
        d.addErrback(upgrade)
        return d

    def upgradeDatabase_02(self):
        """merge port and extendedport tables"""

        def merge(txn):
            """Merge extendedport into port.

            A whole new table is created and renamed. Dropping the old
            table drop the update rule as well. We recreate it.
            """
            txn.execute("""
CREATE TABLE newport (
  equipment inet	      NOT NULL,
  index     int		      NOT NULL,
  name	    text	      NOT NULL,
  alias	    text	      NULL,
  cstate    text		  NOT NULL,
  mac	    macaddr	      NULL,
  speed	    int		      NULL,
  duplex    text	      NULL,
  autoneg   boolean	      NULL,
  created   abstime	      DEFAULT CURRENT_TIMESTAMP,
  deleted   abstime	      DEFAULT 'infinity',
  CONSTRAINT cstate_check CHECK (cstate = 'up' OR cstate = 'down'),
  CONSTRAINT duplex_check CHECK (duplex = 'full' OR duplex = 'half')
)""")
            txn.execute("""
INSERT INTO newport
SELECT DISTINCT ON (p.equipment, p.index, p.deleted)
p.equipment, p.index, p.name, p.alias, p.cstate, p.mac,
CASE WHEN ep.speed IS NOT NULL THEN ep.speed ELSE p.speed END,
ep.duplex, ep.autoneg, p.created, p.deleted
FROM port p
LEFT JOIN extendedport ep
ON ep.equipment=p.equipment AND ep.index = p.index
AND ep.created >= p.created AND ep.deleted <= p.deleted
""")
            txn.execute("DROP TABLE port CASCADE")
            txn.execute("ALTER TABLE newport RENAME TO port")
            txn.execute("""
ALTER TABLE port
ADD PRIMARY KEY (equipment, index, deleted)
""")
            txn.execute("""
CREATE RULE update_port AS ON UPDATE TO port
WHERE old.deleted='infinity' AND new.deleted=CURRENT_TIMESTAMP::abstime
DO ALSO
(UPDATE fdb SET deleted=CURRENT_TIMESTAMP::abstime
 WHERE equipment=new.equipment AND port=new.index AND deleted='infinity' ;
 UPDATE sonmp SET deleted=CURRENT_TIMESTAMP::abstime
 WHERE equipment=new.equipment AND port=new.index AND deleted='infinity' ;
 UPDATE edp SET deleted=CURRENT_TIMESTAMP::abstime
 WHERE equipment=new.equipment AND port=new.index AND deleted='infinity' ;
 UPDATE cdp SET deleted=CURRENT_TIMESTAMP::abstime
 WHERE equipment=new.equipment AND port=new.index AND deleted='infinity' ;
 UPDATE lldp SET deleted=CURRENT_TIMESTAMP::abstime
 WHERE equipment=new.equipment AND port=new.index AND deleted='infinity' ;
 UPDATE vlan SET deleted=CURRENT_TIMESTAMP::abstime
 WHERE equipment=new.equipment AND port=new.index AND deleted='infinity' ;
 UPDATE trunk SET deleted=CURRENT_TIMESTAMP::abstime
 WHERE equipment=new.equipment AND port=new.index AND deleted='infinity' ;
 UPDATE trunk SET deleted=CURRENT_TIMESTAMP::abstime
 WHERE equipment=new.equipment AND member=new.index AND deleted='infinity')
""")

        d = self.pool.runOperation("SELECT 1 FROM extendedport LIMIT 1")
        d.addCallbacks(lambda _: self.pool.runInteraction(merge),
                       lambda _: None)
        return d
