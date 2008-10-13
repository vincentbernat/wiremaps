-- Database schema for Wire Maps. PostgreSQL.

-- This schema still needs some work to create appropriate indexes.

-- We use ON DELETE CASCADE to be able to simply delete equipment or
-- port without cleaning the other tables.

-- The configuration of PostgreSQL should use UTF-8 messages. For example:
-- lc_messages = 'en_US.UTF-8'
-- lc_monetary = 'en_US.UTF-8'
-- lc_numeric = 'en_US.UTF-8'
-- lc_time = 'en_US.UTF-8'

DROP RULE  IF EXISTS insert_or_replace_fdb ON fdb;
DROP RULE  IF EXISTS insert_or_replace_arp ON arp;
DROP TABLE IF EXISTS lldp CASCADE;
DROP TABLE IF EXISTS cdp CASCADE;
DROP TABLE IF EXISTS sonmp CASCADE;
DROP TABLE IF EXISTS arp CASCADE;
DROP TABLE IF EXISTS fdb CASCADE;
DROP TABLE IF EXISTS port CASCADE;
DROP TABLE IF EXISTS equipment CASCADE;

-- DROP TYPE IF EXISTS state CASCADE;
-- CREATE TYPE state AS ENUM ('up', 'down');

CREATE TABLE equipment (
  ip      inet		   PRIMARY KEY,
  name    text		   NULL,
  oid	  text		   NOT NULL,
  description text	   DEFAULT '',
  last    timestamp	   DEFAULT CURRENT_TIMESTAMP,
);


CREATE TABLE port (
  equipment inet	      REFERENCES equipment(ip) ON DELETE CASCADE,
  index     int		      NOT NULL,
  name	    text	      NOT NULL,
  alias	    text	      NULL,
--  cstate    state	      NOT NULL,
  cstate    text              NOT NULL,
  mac	    macaddr	      NULL,
  PRIMARY KEY (equipment, index),
  CONSTRAINT cstate_check CHECK (cstate = 'up' OR cstate = 'down')
);

-- Just a dump of FDB for a given port
CREATE TABLE fdb (
  equipment inet  	      REFERENCES equipment(ip) ON DELETE CASCADE,
  port      int               NOT NULL,
  mac       macaddr	      NOT NULL,
  last      timestamp	      DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (equipment, port) REFERENCES port (equipment, index) ON DELETE CASCADE,
  UNIQUE (equipment, port, mac)
);

CREATE RULE insert_or_replace_fdb AS ON INSERT TO fdb
WHERE EXISTS (SELECT 1 FROM fdb WHERE equipment=new.equipment AND mac=new.mac AND port=new.port)
DO INSTEAD UPDATE fdb SET last=CURRENT_TIMESTAMP
WHERE equipment=new.equipment AND mac=new.mac AND port=new.port;

-- Just a dump of ARP for a given port
CREATE TABLE arp (
  equipment inet  	      REFERENCES equipment(ip) ON DELETE CASCADE,
  mac       macaddr           NOT NULL,
  ip	    inet	      NOT NULL,
  last      timestamp	      DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (equipment, mac, ip)
);

CREATE RULE insert_or_replace_arp AS ON INSERT TO arp
WHERE EXISTS (SELECT 1 FROM arp WHERE equipment=new.equipment AND mac=new.mac AND ip=new.ip)
DO INSTEAD UPDATE arp SET last=CURRENT_TIMESTAMP
WHERE equipment=new.equipment AND mac=new.mac AND ip=new.ip;

-- Just a dump of SONMP for a given port
CREATE TABLE sonmp (
  equipment  inet  	       REFERENCES equipment(ip) ON DELETE CASCADE,
  port       int               NOT NULL,
  remoteip   inet	       NOT NULL,
  remoteport int	       NOT NULL,
  FOREIGN KEY (equipment, port) REFERENCES port (equipment, index) ON DELETE CASCADE,
  PRIMARY KEY (equipment, port)
);

-- Just a dump of EDP for a given port
CREATE TABLE edp (
  equipment  inet  	       REFERENCES equipment(ip) ON DELETE CASCADE,
  port       int               NOT NULL,
  sysname    text	       NOT NULL,
  remoteslot int	       NOT NULL,
  remoteport int               NOT NULL,
  FOREIGN KEY (equipment, port) REFERENCES port (equipment, index) ON DELETE CASCADE,
  PRIMARY KEY (equipment, port)
);

-- Just a dump of CDP for a given port
CREATE TABLE cdp (
  equipment  inet  	       REFERENCES equipment(ip) ON DELETE CASCADE,
  port       int               NOT NULL,
  sysname    text	       NOT NULL, -- Remote ID
  portname   text	       NOT NULL, -- Port ID
  mgmtip     inet	       NOT NULL, -- Address
  platform   text	       NOT NULL, -- Platform
  FOREIGN KEY (equipment, port) REFERENCES port (equipment, index) ON DELETE CASCADE,
  PRIMARY KEY (equipment, port)
);

-- Synthesis of info from LLDP for a given port. Not very detailed.
CREATE TABLE lldp (
  equipment  inet   	       REFERENCES equipment(ip) ON DELETE CASCADE,
  port       int               NOT NULL,
  mgmtip     inet	       NOT NULL, -- Management IP
  portdesc   text	       NOT NULL, -- Port description
  sysname    text	       NOT NULL, -- System name
  sysdesc    text	       NOT NULL, -- System description
  FOREIGN KEY (equipment, port) REFERENCES port (equipment, index) ON DELETE CASCADE,
  PRIMARY KEY (equipment, port)
);
