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
DROP RULE IF EXISTS insert_extendedport ON extendedport;
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
DROP TABLE IF EXISTS port CASCADE;
DROP TABLE IF EXISTS extendedport CASCADE;
DROP TABLE IF EXISTS fdb CASCADE;
DROP TABLE IF EXISTS arp CASCADE;
DROP TABLE IF EXISTS sonmp CASCADE;
DROP TABLE IF EXISTS edp CASCADE;
DROP TABLE IF EXISTS cdp CASCADE;
DROP TABLE IF EXISTS lldp CASCADE;
DROP TABLE IF EXISTS vlan CASCADE;
DROP TABLE IF EXISTS trunk CASCADE;

-- DROP TYPE IF EXISTS state CASCADE;
-- CREATE TYPE state AS ENUM ('up', 'down');

CREATE TABLE equipment (
  ip      inet		   NOT NULL,
  name    text		   NULL,
  oid	  text		   NOT NULL,
  description text	   DEFAULT '',
  created abstime	   DEFAULT CURRENT_TIMESTAMP,
  updated abstime	   DEFAULT CURRENT_TIMESTAMP,
  deleted abstime	   DEFAULT 'infinity',
  PRIMARY KEY (ip, deleted)
);
-- No INSERT rule for this table. created, updated and deleted fields
-- should be handled by the application.

CREATE TABLE port (
  equipment inet	      NOT NULL,
  index     int		      NOT NULL,
  name	    text	      NOT NULL,
  alias	    text	      NULL,
  cstate    text              NOT NULL,
  mac	    macaddr	      NULL,
  speed	    int		      NULL,
  created   abstime	      DEFAULT CURRENT_TIMESTAMP,
  deleted   abstime	      DEFAULT 'infinity',
  PRIMARY KEY (equipment, index, deleted),
  CONSTRAINT cstate_check CHECK (cstate = 'up' OR cstate = 'down')
);
-- No INSERT rule for this table. created and deleted fields should be
-- handled by the application.

-- More optional info about a port
CREATE TABLE extendedport (
  equipment inet	      NOT NULL,
  index     int		      NOT NULL,
  duplex    text	      NULL,
  speed	    int		      NULL, -- if not NULL, this is better than port.speed
  autoneg   boolean	      NULL,
  created   abstime	      DEFAULT CURRENT_TIMESTAMP,
  deleted   abstime	      DEFAULT 'infinity',
  PRIMARY KEY (equipment, index, deleted),
  CONSTRAINT duplex_check CHECK (duplex = 'full' OR duplex = 'half')
);
CREATE RULE insert_extendedport AS ON INSERT TO extendedport
WHERE EXISTS (SELECT 1 FROM extendedport
      	      WHERE equipment=new.equipment AND index=new.index
	      AND duplex=new.duplex AND speed=new.speed AND autoneg=new.autoneg
	      AND deleted=CURRENT_TIMESTAMP::abstime)
DO INSTEAD UPDATE extendedport SET deleted='infinity'
WHERE equipment=new.equipment AND index=new.index
AND duplex=new.duplex AND speed=new.speed AND autoneg=new.autoneg
AND deleted=CURRENT_TIMESTAMP::abstime;

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
CREATE RULE insert_fdb AS ON INSERT TO fdb
WHERE EXISTS (SELECT 1 FROM fdb
      	      WHERE equipment=new.equipment AND mac=new.mac AND port=new.port
	      AND deleted='infinity')
DO INSTEAD UPDATE fdb SET updated=CURRENT_TIMESTAMP
WHERE equipment=new.equipment AND mac=new.mac AND port=new.port
AND deleted='infinity';

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
CREATE RULE insert_arp AS ON INSERT TO arp
WHERE EXISTS (SELECT 1 FROM arp
      	      WHERE equipment=new.equipment AND mac=new.mac AND ip=new.ip
	      AND deleted='infinity')
DO INSTEAD UPDATE arp SET updated=CURRENT_TIMESTAMP
WHERE equipment=new.equipment AND mac=new.mac AND ip=new.ip
AND deleted='infinity';

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
CREATE RULE insert_sonmp AS ON INSERT TO sonmp
WHERE EXISTS (SELECT 1 FROM sonmp
      	      WHERE equipment=new.equipment AND port=new.port
	      AND remoteip=new.remoteip AND remoteport=new.remoteport
	      AND deleted=CURRENT_TIMESTAMP::abstime)
DO INSTEAD UPDATE sonmp SET deleted='infinity'
WHERE equipment=new.equipment AND port=new.port
AND remoteip=new.remoteip AND remoteport=new.remoteport
AND deleted=CURRENT_TIMESTAMP::abstime;

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
(UPDATE extendedport SET deleted=CURRENT_TIMESTAMP::abstime
 WHERE equipment=new.equipment AND index=new.index AND deleted='infinity' ;
 UPDATE fdb SET deleted=CURRENT_TIMESTAMP::abstime
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
