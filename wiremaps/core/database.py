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
            lambda x: log.msg("unable to update database: %s" % str(x)))
        return d

    def upgradeDatabase_01(self):
        """add 'last' column to 'equipment' table"""
        d = self.pool.runOperation("SELECT last FROM equipment LIMIT 1")
        d.addErrback(lambda x: self.pool.runOperation(
                "ALTER TABLE equipment "
                "ADD COLUMN last TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
        return d

    def upgradeDatabase_02(self):
        """add 'last' column to 'fdb' table"""
        d  = self.pool.runOperation("SELECT last FROM fdb LIMIT 1")
        d.addErrback(lambda x: self.pool.runOperation(
                "ALTER TABLE fdb "
                "ADD COLUMN last TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
        return d

    def upgradeDatabase_03(self):
        """add 'last' column to 'arp' table"""
        d  = self.pool.runOperation("SELECT last FROM arp LIMIT 1")
        d.addErrback(lambda x: self.pool.runOperation(
                "ALTER TABLE arp "
                "ADD COLUMN last TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
        return d

    def upgradeDatabase_04(self):
        """add rule for updating 'last' column in 'fdb' table"""
        d  = self.pool.runQuery("SELECT 1 FROM pg_catalog.pg_rules "
                                "WHERE tablename='fdb' AND rulename='insert_or_replace_fdb'")
        d.addCallback(lambda x: x or self.pool.runOperation(
                "CREATE RULE insert_or_replace_fdb AS ON INSERT TO fdb "
                "WHERE EXISTS (SELECT 1 FROM fdb WHERE equipment=new.equipment "
                "AND mac=new.mac AND port=new.port) "
                "DO INSTEAD UPDATE fdb SET last=CURRENT_TIMESTAMP "
                "WHERE equipment=new.equipment AND mac=new.mac AND port=new.port"))
        return d

    def upgradeDatabase_05(self):
        """add rule for updating 'last' column in 'arp' table"""
        d  = self.pool.runQuery("SELECT 1 FROM pg_catalog.pg_rules "
                                "WHERE tablename='arp' AND rulename='insert_or_replace_arp'")
        d.addCallback(lambda x: x or self.pool.runOperation(
                "CREATE RULE insert_or_replace_arp AS ON INSERT TO arp "
                "WHERE EXISTS (SELECT 1 FROM arp WHERE equipment=new.equipment AND "
                "mac=new.mac AND ip=new.ip) "
                "DO INSTEAD UPDATE arp SET last=CURRENT_TIMESTAMP "
                "WHERE equipment=new.equipment AND mac=new.mac AND ip=new.ip "))
        return d

    def upgradeDatabase_06(self):
        """add 'vlan' table"""
        d = self.pool.runOperation("SELECT 1 FROM vlan LIMIT 1")
        d.addErrback(lambda x: self.pool.runOperation("""
  CREATE TABLE vlan (
  equipment inet   	       REFERENCES equipment(ip) ON DELETE CASCADE,
  port	    int		       NOT NULL,
  vid	    int		       NOT NULL,
  name	    text	       NOT NULL,
  type	    text	       NOT NULL,
  FOREIGN KEY (equipment, port) REFERENCES port (equipment, index) ON DELETE CASCADE,
  PRIMARY KEY (equipment, port, vid, type),
  CONSTRAINT type_check CHECK (type = 'remote' OR type = 'local')
)"""))
        return d

    def upgradeDatabase_07(self):
        """add rule for updating 'vlan' table"""
        d  = self.pool.runQuery("SELECT 1 FROM pg_catalog.pg_rules "
                                "WHERE tablename='vlan' AND "
                                "rulename='insert_or_replace_vlan'")
        d.addCallback(lambda x: x or self.pool.runOperation("""
CREATE RULE insert_or_replace_vlan AS ON INSERT TO vlan
WHERE EXISTS
(SELECT 1 FROM vlan
WHERE equipment=new.equipment AND port=new.port AND vid=new.vid AND type=new.type)
DO INSTEAD NOTHING;
"""))
        return d
