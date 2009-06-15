from wiremaps.collector.datastore import ILocalVlan, IRemoteVlan

class DatabaseWriter:
    """Write an equipment datastore to the database."""

    def __init__(self, equipment, config):
        """Create an instance of database writer.

        @param equipment: equipment to dump to the database
        """
        self.equipment = equipment
        self.config = config

    def write(self, dbpool, txn=None):
        """Write the equipment to the database.

        @param dbpool: dbpool to use for write
        @param txn: transaction, used internally
        """
        # We run everything in a transaction
        if txn is None:
            return dbpool.runInteraction(lambda x: self.write(dbpool, x))
        self._equipment(txn)
        self._port(txn)
        self._fdb(txn)
        self._arp(txn)
        self._trunk(txn)
        self._sonmp(txn)
        self._edp(txn)
        self._cdp(txn)
        self._lldp(txn)
        self._vlan(txn)

    def _equipment(self, txn):
        """Write equipment to the database."""
        # We need to check if this equipment exists and if something has changed
        txn.execute("SELECT ip, name, oid, description "
                    "FROM equipment WHERE ip = %(ip)s AND deleted='infinity'",
                    {'ip': self.equipment.ip})
        id = txn.fetchall()
        target = {'name': self.equipment.name,
                  'oid': self.equipment.oid,
                  'description': self.equipment.description,
                  'ip': self.equipment.ip}
        if not id:
            txn.execute("INSERT INTO equipment (ip, name, oid, description) VALUES "
                        "(%(ip)s, %(name)s, %(oid)s, %(description)s)",
                        target)
        else:
            # Maybe something changed
            if id[0][1] != target["name"] or id[0][2] != target["oid"] or \
                    id[0][3] != target["description"]:
                txn.execute("UPDATE equipment SET deleted=CURRENT_TIMESTAMP "
                            "WHERE ip=%(ip)s AND deleted='infinity'",
                            target)
                txn.execute("INSERT INTO equipment (ip, name, oid, description) VALUES "
                            "(%(ip)s, %(name)s, %(oid)s, %(description)s)",
                            target)
            else:
                # Nothing changed, update `updated' column
                txn.execute("UPDATE equipment SET updated=CURRENT_TIMESTAMP "
                            "WHERE ip=%(ip)s AND deleted='infinity'", target)

    def _port(self, txn):
        """Write port related information to the database."""
        uptodate = []      # List of ports that are already up-to-date
        # Try to get existing ports
        txn.execute("SELECT index, name, alias, cstate, mac, speed, duplex, autoneg "
                    "FROM port WHERE equipment = %(ip)s "
                    "AND deleted='infinity'",
                    {'ip': self.equipment.ip})
        for port, name, alias, cstate, mac, speed, duplex, autoneg in txn.fetchall():
            if port not in self.equipment.ports:
                # Delete port
                txn.execute("UPDATE port SET deleted=CURRENT_TIMESTAMP "
                            "WHERE equipment = %(ip)s "
                            "AND index = %(index)s AND deleted='infinity'",
                            {'ip': self.equipment.ip,
                             'index': port})
            else:
                # Refresh port
                nport = self.equipment.ports[port]
                # We ask PostgreSQL to compare MAC addresses for us
                txn.execute("SELECT 1 WHERE %(mac1)s::macaddr = %(mac2)s::macaddr",
                            {'mac1': mac,
                             'mac2': nport.mac})
                if not(txn.fetchall()) or \
                        name != nport.name or \
                        alias != nport.alias or \
                        cstate != nport.state or \
                        speed != nport.speed or \
                        duplex != nport.duplex or \
                        autoneg != nport.autoneg:
                    # Delete the old one
                    txn.execute("UPDATE port SET deleted=CURRENT_TIMESTAMP "
                                "WHERE equipment = %(ip)s "
                                "AND index = %(index)s AND deleted='infinity'",
                                {'ip': self.equipment.ip,
                                 'index': port})
                else:
                    # We don't need to update it, it is up-to-date
                    uptodate.append(port)
        for port in self.equipment.ports:
            if port in uptodate: continue
            # Add port
            nport = self.equipment.ports[port]
            txn.execute("""
INSERT INTO port
(equipment, index, name, alias, cstate, mac, speed, duplex, autoneg)
VALUES (%(ip)s, %(port)s, %(name)s, %(alias)s, %(state)s, %(address)s,
        %(speed)s, %(duplex)s, %(autoneg)s)
""",
                        {'ip': self.equipment.ip,
                         'port': port,
                         'name': nport.name,
                         'alias': nport.alias,
                         'state': nport.state,
                         'address': nport.mac,
                         'speed': nport.speed,
                         'duplex': nport.duplex,
                         'autoneg': nport.autoneg,
                         })

    def _fdb(self, txn):
        """Write FDB to database"""
        for port in self.equipment.ports:
            for mac in self.equipment.ports[port].fdb:
                # Some magic here: PostgreSQL will take care of
                # updating the record if it already exists.
                txn.execute("INSERT INTO fdb (equipment, port, mac) "
                            "VALUES (%(ip)s, %(port)s, %(mac)s)",
                            {'ip': self.equipment.ip,
                             'port': port,
                             'mac': mac})
        # Expire oldest entries
        txn.execute("UPDATE fdb SET deleted=CURRENT_TIMESTAMP WHERE "
                    "CURRENT_TIMESTAMP - interval '%(expire)s hours' > updated "
                    "AND equipment=%(ip)s AND deleted='infinity'",
                       {'ip': self.equipment.ip,
                        'expire': self.config.get('fdbexpire', 24)})

    def _arp(self, txn):
        """Write ARP table to database"""
        for ip in self.equipment.arp:
            # Some magic here: PostgreSQL will take care of
            # updating the record if it already exists.
            txn.execute("INSERT INTO arp (equipment, mac, ip) VALUES (%(ip)s, "
                        "%(mac)s, %(rip)s)",
                        {'ip': self.equipment.ip,
                         'mac': self.equipment.arp[ip],
                         'rip': ip})
        # Expire oldest entries
        txn.execute("UPDATE arp SET deleted=CURRENT_TIMESTAMP WHERE "
                    "CURRENT_TIMESTAMP - interval '%(expire)s hours' > updated "
                    "AND equipment=%(ip)s AND deleted='infinity'",
                    {'ip': self.equipment.ip,
                     'expire': self.config.get('arpexpire', 24)})

    def _trunk(self, txn):
        """Write trunk related information into database"""
        txn.execute("UPDATE trunk SET deleted=CURRENT_TIMESTAMP "
                    "WHERE equipment=%(ip)s AND deleted='infinity'",
                    {'ip': self.equipment.ip})
        for port in self.equipment.ports:
            if self.equipment.ports[port].trunk is not None:
                txn.execute("INSERT INTO trunk VALUES (%(ip)s, %(trunk)s, %(port)s)",
                            {'ip': self.equipment.ip,
                             'trunk': self.equipment.ports[port].trunk.parent,
                             'port': port
                             })

    def _sonmp(self, txn):
        """Write SONMP related information into database"""
        txn.execute("UPDATE sonmp SET deleted=CURRENT_TIMESTAMP "
                    "WHERE equipment=%(ip)s AND deleted='infinity'",
                    {'ip': self.equipment.ip})
        for port in self.equipment.ports:
            nport = self.equipment.ports[port]
            if nport.sonmp is None: continue
            txn.execute("INSERT INTO sonmp VALUES (%(ip)s, "
                        "%(port)s, %(rip)s, %(rport)s)",
                        {'ip': self.equipment.ip,
                         'port': port,
                         'rip': nport.sonmp.ip,
                         'rport': nport.sonmp.port})

    def _edp(self, txn):
        """Write EDP related information into database"""
        txn.execute("UPDATE edp SET deleted=CURRENT_TIMESTAMP "
                    "WHERE equipment=%(ip)s AND deleted='infinity'",
                    {'ip': self.equipment.ip})
        for port in self.equipment.ports:
            nport = self.equipment.ports[port]
            if nport.edp is None: continue
            txn.execute("INSERT INTO edp VALUES (%(ip)s, "
                        "%(port)s, %(sysname)s, %(remoteslot)s, "
                        "%(remoteport)s)",
                        {'ip': self.equipment.ip,
                         'port': port,
                         'sysname': nport.edp.sysname,
                         'remoteslot': nport.edp.slot,
                         'remoteport': nport.edp.port})

    def _cdp(self, txn):
        """Write CDP related information into database"""
        txn.execute("UPDATE cdp SET deleted=CURRENT_TIMESTAMP "
                    "WHERE equipment=%(ip)s AND deleted='infinity'",
                    {'ip': self.equipment.ip})
        for port in self.equipment.ports:
            nport = self.equipment.ports[port]
            if nport.cdp is None: continue
            txn.execute("INSERT INTO cdp VALUES (%(ip)s, "
                        "%(port)s, %(sysname)s, %(portname)s, "
                        "%(mgmtip)s, %(platform)s)",
                        {'ip': self.equipment.ip,
                         'port': port,
                         'sysname': nport.cdp.sysname,
                         'portname': nport.cdp.port,
                         'platform': nport.cdp.platform,
                         'mgmtip': nport.cdp.ip})

    def _lldp(self, txn):
        """Write LLDP related information into database"""
        txn.execute("UPDATE lldp SET deleted=CURRENT_TIMESTAMP "
                    "WHERE equipment=%(ip)s AND deleted='infinity'",
                    {'ip': self.equipment.ip})
        for port in self.equipment.ports:
            nport = self.equipment.ports[port]
            if nport.lldp is None: continue
            txn.execute("INSERT INTO lldp VALUES (%(ip)s, "
                        "%(port)s, %(mgmtip)s, %(portdesc)s, "
                        "%(sysname)s, %(sysdesc)s)",
                        {'ip': self.equipment.ip,
                         'port': port,
                         'mgmtip': nport.lldp.ip,
                         'portdesc': nport.lldp.portdesc,
                         'sysname': nport.lldp.sysname,
                         'sysdesc': nport.lldp.sysdesc})

    def _vlan(self, txn):
        """Write VLAN information into database"""
        txn.execute("UPDATE vlan SET deleted=CURRENT_TIMESTAMP "
                    "WHERE equipment=%(ip)s AND deleted='infinity'",
                    {'ip': self.equipment.ip})
        for port in self.equipment.ports:
            for vlan in self.equipment.ports[port].vlan:
                if ILocalVlan.providedBy(vlan):
                    type = 'local'
                elif IRemoteVlan.providedBy(vlan):
                    type = 'remote'
                else:
                    raise ValueError, "%r is neither a local or a remote VLAN"
                txn.execute("INSERT INTO vlan VALUES (%(ip)s, "
                            "%(port)s, %(vid)s, %(name)s, "
                            "%(type)s)",
                            {'ip': self.equipment.ip,
                             'port': port,
                             'vid': vlan.vid,
                             'name': vlan.name,
                             'type': type})
