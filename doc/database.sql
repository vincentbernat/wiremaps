-- Database schema for Wire Maps. PostgreSQL.

-- This schema still needs some work to create appropriate indexes.

-- We use ON DELETE CASCADE to be able to simply delete equipment or
-- port without cleaning the other tables. We also heavily rely on ON
-- UPDATE CASCADE for the same reason (i.e updating deleted
-- timestamp). We also rely on the fact that tables are updated into a
-- transaction and therefore now() keeps the same value during all the
-- transaction.

-- Rules are used to intercept INSERT operations on the table to take
-- care of updating the time travel machine. For INSERT, we will
-- search for a row with the same values and with deleted=now() and
-- update it with deleted='infinity'. Otherwise, we will try to insert
-- the new row (with created=now() and deleted='infinity'). For
-- DELETE, we will update corresponding rows with deleted=now()
-- instead when deleted='infinity'. However, this will be done
-- directly in the application since it is believed to be more
-- efficient.
--
-- For tables having an updated column, INSERT will search for
-- deleted='infinity' and update updated=now(), DELETE will update
-- like above.
--
-- For all this to work, we absolutely need that DELETE followed by
-- INSERT be in the same transaction so that the two values of now()
-- match.
--
-- Integrity is quite complex. Foreign keys should include `delete'
-- column. However, this is not as easy as this. For example, as an
-- equipment may still exist from t to infinity, a port could exist
-- from t to t+1 but not from t+1 to infinity. There will be no column
-- with t+1 for the given equipment. The `delete' column in a table
-- should be between `created' and `deleted' (both included) of
-- reference. We don't check all this. However, we provide triggers to
-- update if possible the value of `deleted' if the reference is
-- updated. For example, if an equipment is deleted, its `deleted'
-- column is set to CURRENT_TIMESTAMP and the trigger will update all
-- `deleted' column accordingly.

-- Each table have a _past counterpart that has the same schema but
-- where deleted != 'infinity'. Each table has also a view _full which
-- is the join of the table and the past table. To maintain PostgreSQL
-- 8.1 compatibility, we need to copy indexes by hand (instead of
-- using INCLUDING INDEXES). We don't include DEFAULTS because there
-- is not direct insertion into past tables.

-- The configuration of PostgreSQL should use UTF-8 messages. For example:
-- lc_messages = 'en_US.UTF-8'
-- lc_monetary = 'en_US.UTF-8'
-- lc_numeric = 'en_US.UTF-8'
-- lc_time = 'en_US.UTF-8'

-- !!!!
-- When modifying this file, an upgrade procedure should be done in
-- wiremaps/core/database.py.

DROP RULE IF EXISTS update_equipment ON equipment;
DROP RULE IF EXISTS update_port ON port;
DROP RULE IF EXISTS insert_fdb ON fdb;
DROP RULE IF EXISTS insert_arp ON arp;
DROP RULE IF EXISTS insert_sonmp ON sonmp;
DROP RULE IF EXISTS insert_edp ON edp;
DROP RULE IF EXISTS insert_cdp ON cdp;
DROP RULE IF EXISTS insert_lldp ON lldp;
DROP RULE IF EXISTS insert_vlan ON vlan;
DROP RULE IF EXISTS insert_vlan_duplicate ON vlan;
DROP RULE IF EXISTS insert_trunk ON trunk;
DROP TABLE IF EXISTS equipment CASCADE;
DROP TABLE IF EXISTS equipment_past CASCADE;
DROP VIEW IF EXISTS equipment_full CASCADE;
DROP TABLE IF EXISTS port CASCADE;
DROP TABLE IF EXISTS port_past CASCADE;
DROP VIEW IF EXISTS port_full CASCADE;
DROP TABLE IF EXISTS fdb CASCADE;
DROP TABLE IF EXISTS fdb_past CASCADE;
DROP VIEW IF EXISTS fdb_full CASCADE;
DROP TABLE IF EXISTS arp CASCADE;
DROP TABLE IF EXISTS arp_past CASCADE;
DROP VIEW IF EXISTS arp_full CASCADE;
DROP TABLE IF EXISTS sonmp CASCADE;
DROP TABLE IF EXISTS sonmp_past CASCADE;
DROP VIEW IF EXISTS sonmp_full CASCADE;
DROP TABLE IF EXISTS edp CASCADE;
DROP TABLE IF EXISTS edp_past CASCADE;
DROP VIEW IF EXISTS edp_full CASCADE;
DROP TABLE IF EXISTS cdp CASCADE;
DROP TABLE IF EXISTS cdp_past CASCADE;
DROP VIEW IF EXISTS cdp_full CASCADE;
DROP TABLE IF EXISTS lldp CASCADE;
DROP TABLE IF EXISTS lldp_past CASCADE;
DROP VIEW IF EXISTS lldp_full CASCADE;
DROP TABLE IF EXISTS vlan CASCADE;
DROP TABLE IF EXISTS vlan_past CASCADE;
DROP VIEW IF EXISTS vlan_full CASCADE;
DROP TABLE IF EXISTS trunk CASCADE;
DROP TABLE IF EXISTS trunk_past CASCADE;
DROP VIEW IF EXISTS trunk_full CASCADE;

-- DROP TYPE IF EXISTS state CASCADE;
-- CREATE TYPE state AS ENUM ('up', 'down');

CREATE TABLE equipment (
  ip      inet		   NOT NULL,
  name    text		   NULL,
  oid	  text		   NOT NULL,
  description text	   DEFAULT '',
  location    text	   NULL,
  created abstime	   DEFAULT CURRENT_TIMESTAMP,
  updated abstime	   DEFAULT CURRENT_TIMESTAMP,
  deleted abstime	   DEFAULT 'infinity',
  PRIMARY KEY (ip, deleted)
);
CREATE INDEX equipment_deleted ON equipment (deleted);
-- No INSERT rule for this table. created, updated and deleted fields
-- should be handled by the application.
CREATE TABLE equipment_past (LIKE equipment);
ALTER TABLE equipment_past ADD PRIMARY KEY (ip, deleted);
CREATE INDEX equipment_past_deleted ON equipment_past (deleted);
CREATE VIEW equipment_full AS (SELECT * FROM equipment UNION SELECT * FROM equipment_past);

CREATE TABLE port (
  equipment inet	      NOT NULL,
  index     int		      NOT NULL,
  name	    text	      NOT NULL,
  alias	    text	      NULL,
  cstate    text              NOT NULL,
  mac	    macaddr	      NULL,
  speed	    int		      NULL,
  duplex    text	      NULL,
  autoneg   boolean	      NULL,
  created   abstime	      DEFAULT CURRENT_TIMESTAMP,
  deleted   abstime	      DEFAULT 'infinity',
  PRIMARY KEY (equipment, index, deleted),
  CONSTRAINT cstate_check CHECK (cstate = 'up' OR cstate = 'down'),
  CONSTRAINT duplex_check CHECK (duplex = 'full' OR duplex = 'half')
);
CREATE INDEX port_deleted ON port (deleted);
-- No INSERT rule for this table. created and deleted fields should be
-- handled by the application.
CREATE TABLE port_past (LIKE port);
ALTER TABLE port_past ADD PRIMARY KEY (equipment, index, deleted);
CREATE INDEX port_past_deleted ON port_past (deleted);
CREATE VIEW port_full AS (SELECT * FROM port UNION SELECT * FROM port_past);

-- Just a dump of FDB for a given port
CREATE TABLE fdb (
  equipment inet  	      NOT NULL,
  port      int               NOT NULL,
  mac       macaddr	      NOT NULL,
  created abstime	      DEFAULT CURRENT_TIMESTAMP,
  updated abstime	      DEFAULT CURRENT_TIMESTAMP,
  deleted abstime	      DEFAULT 'infinity',
  UNIQUE (equipment, port, mac, deleted)
);
CREATE INDEX fdb_deleted ON fdb (deleted);
CREATE RULE insert_fdb AS ON INSERT TO fdb
WHERE EXISTS (SELECT 1 FROM fdb
      	      WHERE equipment=new.equipment AND mac=new.mac AND port=new.port
	      AND deleted='infinity')
DO INSTEAD UPDATE fdb SET updated=CURRENT_TIMESTAMP
WHERE equipment=new.equipment AND mac=new.mac AND port=new.port
AND deleted='infinity';
CREATE TABLE fdb_past (LIKE fdb);
ALTER TABLE fdb_past ADD PRIMARY KEY (equipment, port, mac, deleted);
CREATE INDEX fdb_past_deleted ON fdb_past (deleted);
CREATE VIEW fdb_full AS (SELECT * FROM fdb UNION SELECT * FROM fdb_past);

-- Just a dump of ARP for a given port
CREATE TABLE arp (
  equipment inet  	      NOT NULL,
  mac       macaddr           NOT NULL,
  ip	    inet	      NOT NULL,
  created abstime	      DEFAULT CURRENT_TIMESTAMP,
  updated abstime	      DEFAULT CURRENT_TIMESTAMP,
  deleted abstime	      DEFAULT 'infinity',
  UNIQUE (equipment, mac, ip, deleted)
);
CREATE INDEX arp_deleted ON arp (deleted);
CREATE RULE insert_arp AS ON INSERT TO arp
WHERE EXISTS (SELECT 1 FROM arp
      	      WHERE equipment=new.equipment AND mac=new.mac AND ip=new.ip
	      AND deleted='infinity')
DO INSTEAD UPDATE arp SET updated=CURRENT_TIMESTAMP
WHERE equipment=new.equipment AND mac=new.mac AND ip=new.ip
AND deleted='infinity';
CREATE TABLE arp_past (LIKE arp);
ALTER TABLE arp_past ADD PRIMARY KEY (equipment, mac, ip, deleted);
CREATE INDEX arp_past_deleted ON arp_past (deleted);
CREATE VIEW arp_full AS (SELECT * FROM arp UNION SELECT * FROM arp_past);

-- Just a dump of SONMP for a given port
CREATE TABLE sonmp (
  equipment  inet  	       NOT NULL,
  port       int               NOT NULL,
  remoteip   inet	       NOT NULL,
  remoteport int	       NOT NULL,
  created abstime	       DEFAULT CURRENT_TIMESTAMP,
  deleted abstime	       DEFAULT 'infinity',
  PRIMARY KEY (equipment, port, deleted)
);
CREATE INDEX sonmp_deleted ON sonmp (deleted);
CREATE RULE insert_sonmp AS ON INSERT TO sonmp
WHERE EXISTS (SELECT 1 FROM sonmp
      	      WHERE equipment=new.equipment AND port=new.port
	      AND remoteip=new.remoteip AND remoteport=new.remoteport
	      AND deleted=CURRENT_TIMESTAMP::abstime)
DO INSTEAD UPDATE sonmp SET deleted='infinity'
WHERE equipment=new.equipment AND port=new.port
AND remoteip=new.remoteip AND remoteport=new.remoteport
AND deleted=CURRENT_TIMESTAMP::abstime;
CREATE TABLE sonmp_past (LIKE sonmp);
ALTER TABLE sonmp_past ADD PRIMARY KEY (equipment, port, deleted);
CREATE INDEX sonmp_past_deleted ON sonmp_past (deleted);
CREATE VIEW sonmp_full AS (SELECT * FROM sonmp UNION SELECT * FROM sonmp_past);

-- Just a dump of EDP for a given port
CREATE TABLE edp (
  equipment  inet  	       NOT NULL,
  port       int               NOT NULL,
  sysname    text	       NOT NULL,
  remoteslot int	       NOT NULL,
  remoteport int               NOT NULL,
  created abstime	       DEFAULT CURRENT_TIMESTAMP,
  deleted abstime	       DEFAULT 'infinity',
  PRIMARY KEY (equipment, port, deleted)
);
CREATE INDEX edp_deleted ON edp (deleted);
CREATE RULE insert_edp AS ON INSERT TO edp
WHERE EXISTS (SELECT 1 FROM edp
      	      WHERE equipment=new.equipment AND port=new.port
	      AND sysname=new.sysname
	      AND remoteslot=new.remoteslot AND remoteport=new.remoteport
	      AND deleted=CURRENT_TIMESTAMP::abstime)
DO INSTEAD UPDATE edp SET deleted='infinity'
WHERE equipment=new.equipment AND port=new.port
AND sysname=new.sysname
AND remoteslot=new.remoteslot AND remoteport=new.remoteport
AND deleted=CURRENT_TIMESTAMP::abstime;
CREATE TABLE edp_past (LIKE edp);
ALTER TABLE edp_past ADD PRIMARY KEY (equipment, port, deleted);
CREATE INDEX edp_past_deleted ON edp_past (deleted);
CREATE VIEW edp_full AS (SELECT * FROM edp UNION SELECT * FROM edp_past);

-- Just a dump of CDP for a given port
CREATE TABLE cdp (
  equipment  inet  	       NOT NULL,
  port       int               NOT NULL,
  sysname    text	       NOT NULL, -- Remote ID
  portname   text	       NOT NULL, -- Port ID
  mgmtip     inet	       NOT NULL, -- Address
  platform   text	       NOT NULL, -- Platform
  created abstime	       DEFAULT CURRENT_TIMESTAMP,
  deleted abstime	       DEFAULT 'infinity',
  PRIMARY KEY (equipment, port, deleted)
);
CREATE INDEX cdp_deleted ON cdp (deleted);
CREATE RULE insert_cdp AS ON INSERT TO cdp
WHERE EXISTS (SELECT 1 FROM cdp
      	      WHERE equipment=new.equipment AND port=new.port
	      AND sysname=new.sysname AND portname=new.portname
	      AND mgmtip=new.mgmtip AND platform=new.platform
	      AND deleted=CURRENT_TIMESTAMP::abstime)
DO INSTEAD UPDATE cdp SET deleted='infinity'
WHERE equipment=new.equipment AND port=new.port
AND sysname=new.sysname AND portname=new.portname
AND mgmtip=new.mgmtip AND platform=new.platform
AND deleted=CURRENT_TIMESTAMP::abstime;
CREATE TABLE cdp_past (LIKE cdp);
ALTER TABLE cdp_past ADD PRIMARY KEY (equipment, port, deleted);
CREATE INDEX cdp_past_deleted ON cdp_past (deleted);
CREATE VIEW cdp_full AS (SELECT * FROM cdp UNION SELECT * FROM cdp_past);

-- Synthesis of info from LLDP for a given port. Not very detailed.
CREATE TABLE lldp (
  equipment  inet   	       NOT NULL,
  port       int               NOT NULL,
  mgmtip     inet	       NOT NULL, -- Management IP
  portdesc   text	       NOT NULL, -- Port description
  sysname    text	       NOT NULL, -- System name
  sysdesc    text	       NOT NULL, -- System description
  created abstime	       DEFAULT CURRENT_TIMESTAMP,
  deleted abstime	       DEFAULT 'infinity',
  PRIMARY KEY (equipment, port, deleted)
);
CREATE INDEX lldp_deleted ON lldp (deleted);
CREATE RULE insert_lldp AS ON INSERT TO lldp
WHERE EXISTS (SELECT 1 FROM lldp
      	      WHERE equipment=new.equipment AND port=new.port
	      AND sysname=new.sysname AND portdesc=new.portdesc
	      AND mgmtip=new.mgmtip AND sysdesc=new.sysdesc
	      AND deleted=CURRENT_TIMESTAMP::abstime)
DO INSTEAD UPDATE lldp SET deleted='infinity'
WHERE equipment=new.equipment AND port=new.port
AND sysname=new.sysname AND portdesc=new.portdesc
AND mgmtip=new.mgmtip AND sysdesc=new.sysdesc
AND deleted=CURRENT_TIMESTAMP::abstime;
CREATE TABLE lldp_past (LIKE lldp);
ALTER TABLE lldp_past ADD PRIMARY KEY (equipment, port, deleted);
CREATE INDEX lldp_past_deleted ON lldp_past (deleted);
CREATE VIEW lldp_full AS (SELECT * FROM lldp UNION SELECT * FROM lldp_past);

-- Info about vlan
CREATE TABLE vlan (
  equipment inet   	       NOT NULL,
  port	    int		       NOT NULL,
  vid	    int		       NOT NULL,
  name	    text	       NOT NULL,
  type	    text	       NOT NULL,
  created abstime	       DEFAULT CURRENT_TIMESTAMP,
  deleted abstime	       DEFAULT 'infinity',
  PRIMARY KEY (equipment, port, vid, type, deleted),
  CONSTRAINT type_check CHECK (type = 'remote' OR type = 'local')
);
CREATE RULE insert_vlan AS ON INSERT TO vlan
WHERE EXISTS (SELECT 1 FROM vlan
      	      WHERE equipment=new.equipment AND port=new.port
	      AND vid=new.vid AND name=new.name AND type=new.type
	      AND deleted=CURRENT_TIMESTAMP::abstime)
DO INSTEAD UPDATE vlan SET deleted='infinity'
WHERE equipment=new.equipment AND port=new.port
AND vid=new.vid AND name=new.name AND type=new.type
AND deleted=CURRENT_TIMESTAMP::abstime;
CREATE RULE insert_vlan_duplicate AS ON INSERT TO vlan
WHERE EXISTS (SELECT 1 FROM vlan
      	      WHERE equipment=new.equipment AND port=new.port
	      AND vid=new.vid AND type=new.type
	      AND deleted='infinity')
DO INSTEAD NOTHING;
CREATE TABLE vlan_past (LIKE vlan);
ALTER TABLE vlan_past ADD PRIMARY KEY (equipment, port, vid, type, deleted);
CREATE VIEW vlan_full AS (SELECT * FROM vlan UNION SELECT * FROM vlan_past);

-- Info about trunk
CREATE TABLE trunk (
  equipment inet   	       NOT NULL,
  port	    int		       NOT NULL, -- Index of this trunk
  member    int		       NOT NULL, -- Member of this trunk
  created abstime	       DEFAULT CURRENT_TIMESTAMP,
  deleted abstime	       DEFAULT 'infinity',
  PRIMARY KEY (equipment, port, member, deleted)
);
CREATE RULE insert_trunk AS ON INSERT TO trunk
WHERE EXISTS (SELECT 1 FROM trunk
      	      WHERE equipment=new.equipment AND port=new.port
	      AND member=new.member
	      AND deleted=CURRENT_TIMESTAMP::abstime)
DO INSTEAD UPDATE trunk SET deleted='infinity'
WHERE equipment=new.equipment AND port=new.port
AND member=new.member
AND deleted=CURRENT_TIMESTAMP::abstime;
CREATE TABLE trunk_past (LIKE trunk);
ALTER TABLE trunk_past ADD PRIMARY KEY (equipment, port, member, deleted);
CREATE VIEW trunk_full AS (SELECT * FROM trunk UNION SELECT * FROM trunk_past);

-- Special rule to propagate updates. These rules should work when
-- port or equipment `deleted' column is set from infinity to
-- CURRENT_TIMESTAMP.
CREATE RULE update_equipment AS ON UPDATE TO equipment
WHERE old.deleted='infinity' AND new.deleted=CURRENT_TIMESTAMP::abstime
DO ALSO
(UPDATE port SET deleted=CURRENT_TIMESTAMP::abstime
 WHERE equipment=new.ip AND deleted='infinity' ;
 UPDATE arp SET deleted=CURRENT_TIMESTAMP::abstime
 WHERE equipment=new.ip AND deleted='infinity');
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
 WHERE equipment=new.equipment AND member=new.index AND deleted='infinity');
