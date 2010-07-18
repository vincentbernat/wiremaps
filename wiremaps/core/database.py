# When modifying this class, also update doc/database.sql

import warnings

from twisted.python import log
from twisted.internet import reactor, defer
from twisted.enterprise import adbapi

class Database:
    
    def __init__(self, config):
        try:
            import psycopg2
        except ImportError:
            warnings.warn("psycopg2 was not found, try pyPgSQL instead",
                          DeprecationWarning)
            try:
                import pyPgSQL
            except ImportError:
                raise ImportError("Neither psycopg2 or pyPgSQL is present on your system")
            p = adbapi.ConnectionPool("pyPgSQL.PgSQL",
                                      "%s:%d:%s:%s:%s" % (
                    config['database'].get('host', 'localhost'),
                    config['database'].get('port', 5432),
                    config['database']['database'],
                    config['database']['username'],
                    config['database']['password']))
        else:
            p = adbapi.ConnectionPool("psycopg2",
                                      "host=%s port=%d dbname=%s "
                                      "user=%s password=%s" % (
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

            txn.execute("DROP TABLE extendedport CASCADE")

        d = self.pool.runOperation("SELECT 1 FROM extendedport LIMIT 1")
        d.addCallbacks(lambda _: self.pool.runInteraction(merge),
                       lambda _: None)
        return d

    def upgradeDatabase_03(self):
        """add indexes to enhance completion speed"""

        def addindex(txn):
            txn.execute("CREATE INDEX port_deleted ON port (deleted)")
            txn.execute("CREATE INDEX fdb_deleted ON fdb (deleted)")
            txn.execute("CREATE INDEX arp_deleted ON arp (deleted)")
            txn.execute("CREATE INDEX sonmp_deleted ON sonmp (deleted)")
            txn.execute("CREATE INDEX edp_deleted ON edp (deleted)")
            txn.execute("CREATE INDEX cdp_deleted ON cdp (deleted)")
            txn.execute("CREATE INDEX lldp_deleted ON lldp (deleted)")

        d = self.pool.runOperation("CREATE INDEX equipment_deleted ON equipment (deleted)")
        d.addCallbacks(lambda _: self.pool.runInteraction(addindex),
                       lambda _: None)
        return d

    def upgradeDatabase_04(self):
        """add past tables"""

        def addpast(txn):
            for table in ["equipment", "port", "fdb", "arp", "sonmp", "edp", "cdp", "lldp",
                          "vlan", "trunk"]:
                # Copy table schema
                txn.execute("CREATE TABLE %s_past (LIKE %s)" % ((table,)*2))
                # Create view
                txn.execute("CREATE VIEW %s_full AS "
                            "(SELECT * FROM %s UNION SELECT * FROM %s_past)" % ((table,)*3))
                # Add index on `deleted'
                if table not in ["vlan", "trunk"]:
                    txn.execute("CREATE INDEX %s_past_deleted ON %s_past (deleted)" % ((table,)*2))
            # Primary keys
            for table in ["sonmp", "edp", "cdp", "lldp"]:
                txn.execute("ALTER TABLE %s_past ADD PRIMARY KEY (equipment, port, deleted)" % table)
            txn.execute("ALTER TABLE equipment_past ADD PRIMARY KEY (ip, deleted)")
            txn.execute("ALTER TABLE port_past ADD PRIMARY KEY (equipment, index, deleted)")
            txn.execute("ALTER TABLE fdb_past ADD PRIMARY KEY (equipment, port, mac, deleted)")
            txn.execute("ALTER TABLE arp_past ADD PRIMARY KEY (equipment, mac, ip, deleted)")
            txn.execute("ALTER TABLE vlan_past ADD PRIMARY KEY (equipment, port, vid, type, deleted)")
            txn.execute("ALTER TABLE trunk_past ADD PRIMARY KEY (equipment, port, member, deleted)")

        d = self.pool.runOperation("SELECT 1 FROM equipment_past LIMIT 1")
        d.addCallbacks(lambda _: None,
                       lambda _: self.pool.runInteraction(addpast))
        return d

    def upgradeDatabase_05(self):
        """add update_equipment rule"""
        # This rule may have been dropped when we dropped old port table

        def cleanup(txn):
            # Since we succesfully added the rule, this may mean we
            # need to delete some orphaned ports/arp entries
            txn.execute("""
UPDATE port SET deleted=CURRENT_TIMESTAMP::abstime
WHERE deleted = 'infinity'
AND equipment NOT IN (SELECT ip FROM equipment WHERE deleted='infinity')
""")
            txn.execute("""
UPDATE arp SET deleted=CURRENT_TIMESTAMP::abstime
WHERE deleted = 'infinity'
AND equipment NOT IN (SELECT ip FROM equipment WHERE deleted='infinity')
""")

        d = self.pool.runOperation("""
CREATE RULE update_equipment AS ON UPDATE TO equipment
WHERE old.deleted='infinity' AND new.deleted=CURRENT_TIMESTAMP::abstime
DO ALSO
(UPDATE port SET deleted=CURRENT_TIMESTAMP::abstime
 WHERE equipment=new.ip AND deleted='infinity' ;
 UPDATE arp SET deleted=CURRENT_TIMESTAMP::abstime
 WHERE equipment=new.ip AND deleted='infinity')
""")
        d.addCallbacks(lambda _: self.pool.runInteraction(cleanup),
                       lambda _: None)
        return d
