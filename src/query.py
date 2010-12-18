# -*- coding: utf-8 -*-

"""
Copyright (C) 2008,2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

partially based on C++ code from:
    Copyright (C) 2006 Mauricio Piacentini  <mauricio@tabuleiro.com>

kajongg is free software you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.


"""

import sys, os
from collections import defaultdict
from PyQt4.QtCore import QVariant
from util import logWarning, logError, logDebug, appdataDir, m18ncE
from common import InternalParameters, IntDict
from PyQt4.QtSql import QSqlQuery, QSqlDatabase, QSql

class Transaction(object):
    """a helper class for SQL transactions"""
    def __init__(self, dbhandle=None):
        """start a transaction"""
        self.dbhandle = dbhandle or Query.dbhandle
        if not self.dbhandle.transaction():
            logWarning('Cannot start transaction on %s' % self.dbhandle.databaseName())
        self.active = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trback):
        """end the transaction"""
        if self.active and trback is None:
            if not self.dbhandle.commit():
                logWarning('Cannot commit transaction on %s' % self.dbhandle.databaseName())
        else:
            if not self.dbhandle.rollback():
                logWarning('Cannot commit transaction on %s' % self.dbhandle.databaseName())
            if exc_type:
                exc_type(exc_value)

    def rollback(self):
        """explicit rollback by the caller"""
        self.dbhandle.rollback()
        self.active = False

class Query(object):
    """a more pythonic interface to QSqlQuery. We could instead use
    the python sqlite3 module but then we would either have to do
    more programming for the model/view tables, or we would have
    two connections to the same database.
    For selecting queries we fill a list with ALL records.
    Every record is a list of all fields. q.records[0][1] is record 0, field 1.
    For select, we also convert to python data
    types - as far as we need them"""
    dbhandle = None
    lastError = None

    localServerName = m18ncE('kajongg name for local game server', 'Local Game')

    def __init__(self, cmdList, args=None, dbHandle=None, silent=False):
        """we take a list of sql statements. Only the last one is allowed to be
        a select statement.
        Do prepared queries by passing a single query statement in cmdList
        and the parameters in args. If args is a list of lists, execute the
        prepared query for every sublist.
        If dbHandle is passed, use that for db access.
        Else if the default dbHandle (Query.dbhandle) is defined, use it."""
        silent |= not InternalParameters.showSql
        self.dbHandle = dbHandle or Query.dbhandle
        preparedQuery = not isinstance(cmdList, list) and bool(args)
        self.query = QSqlQuery(self.dbHandle)
        self.msg = None
        self.records = []
        scFlag = 'S' if InternalParameters.isServer else 'C'
        if not isinstance(cmdList, list):
            cmdList = list([cmdList])
        self.cmdList = cmdList
        for cmd in cmdList:
            if preparedQuery:
                self.query.prepare(cmd)
                if not isinstance(args[0], list):
                    args = list([args])
                for dataSet in args:
                    if not silent:
                        logDebug('%s:%s %s' % (scFlag, cmd, dataSet))
                    for value in dataSet:
                        self.query.addBindValue(QVariant(value))
                    self.success = self.query.exec_()
                    if not self.success:
                        break
            else:
                if not silent:
                    logDebug('%s:%s' %(scFlag, cmd))
                self.success = self.query.exec_(cmd)
            if not self.success:
                Query.lastError = unicode(self.query.lastError().text())
                self.msg = '%s:ERROR in %s: %s' % (scFlag, self.dbHandle.databaseName(), Query.lastError)
                logError(self.msg)
                return
        self.records = None
        self.fields = None
        if self.query.isSelect():
            self.retrieveRecords()

    def retrieveRecords(self):
        """get all records from SQL into a python list"""
        record = self.query.record()
        self.fields = [record.field(x) for x in range(record.count())]
        self.records = []
        while self.query.next():
            self.records.append([self.__convertField(x) for x in range(record.count())])

    def __convertField(self, idx):
        """convert a QSqlQuery field into a python value"""
        field = self.fields[idx]
        name = str(field.name())
        valType = field.type()
        if valType == QVariant.String:
            value = unicode(self.query.value(idx).toString())
        elif valType == QVariant.Double:
            value = self.query.value(idx).toDouble()[0]
        elif valType == QVariant.Int:
            value = self.query.value(idx).toInt()[0]
        elif valType == QVariant.UInt:
            value = self.query.value(idx).toUInt()[0]
        elif valType == QVariant.LongLong:
            value = self.query.value(idx).toLongLong()[0]
        elif valType == QVariant.ULongLong:
            value = self.query.value(idx).toULongLong()[0]
        else:
            raise Exception('Query: variant type %s not implemented for field %s ' % \
                (QVariant.typeToName(valType), name))
        return value

    @staticmethod
    def tableHasField(dbhandle, table, field):
        """does the table contain a column named field?"""
        query = QSqlQuery(dbhandle)
        query.exec_('select * from %s' % table)
        record = query.record()
        for idx in range(record.count()):
            if record.fieldName(idx) == field:
                return True

    schema = {}
    schema['player'] = """
        id INTEGER PRIMARY KEY,
        name TEXT unique"""
    schema['game'] = """
            id integer primary key,
            seed text,
            autoplay integer default 0,
            starttime text default current_timestamp,
            endtime text,
            ruleset integer references usedruleset(id),
            p0 integer constraint fk_p0 references player(id),
            p1 integer constraint fk_p1 references player(id),
            p2 integer constraint fk_p2 references player(id),
            p3 integer constraint fk_p3 references player(id)"""
    schema['score'] = """
            game integer constraint fk_game references game(id),
            hand integer,
            data text,
            manualrules text,
            rotated integer,
            player integer constraint fk_player references player(id),
            scoretime text,
            won integer,
            prevailing text,
            wind text,
            points integer,
            payments integer,
            balance integer"""
    schema['ruleset'] = """
            id integer primary key,
            name text unique,
            hash text,
            lastused text,
            description text"""
    schema['rule'] = """
            ruleset integer,
            list integer,
            position integer,
            name text,
            definition text,
            points text,
            doubles integer,
            limits integer,
            parameter text,
            primary key(ruleset,list,position),
            unique (ruleset,name)"""
    schema['usedruleset'] = """
            id integer primary key,
            name text,
            hash text,
            lastused text,
            description text"""
    schema['usedrule'] = """
            ruleset integer,
            list integer,
            position integer,
            name text,
            definition text,
            points text,
            doubles integer,
            limits integer,
            parameter text,
            primary key(ruleset,list,position),
            unique (ruleset,name)"""
    schema['server'] = """
                url text,
                lastname text,
                lasttime text,
                lastruleset integer,
                primary key(url)"""
    schema['passwords'] = """
                url text,
                player integer,
                password text"""

    @staticmethod
    def createTable(dbhandle, table):
        """create a single table using the predefined schema"""
        if table not in dbhandle.driver().tables(QSql.Tables):
            Query("create table %s(%s)" % (table, Query.schema[table]), dbHandle=dbhandle)

    @staticmethod
    def createTables(dbhandle):
        """creates empty tables"""
        for table in ['player', 'game', 'score', 'ruleset', 'rule', 'usedruleset', 'usedrule']:
            Query.createTable(dbhandle, table)
        Query.createIndex(dbhandle, 'idxgame', 'score(game)')

        if  InternalParameters.isServer:
            Query('ALTER TABLE player add password text', dbHandle=dbhandle)
        else:
            Query.createTable(dbhandle, 'passwords')
            Query.createTable(dbhandle, 'server')

    @staticmethod
    def createIndex(dbhandle, name, cmd):
        """only try to create it if it does not yet exist. Do not use create if not exists because
        we want debug output only if we really create the index"""
        if not Query("select 1 from sqlite_master where type='index' and name='%s'" % name,
                dbHandle=dbhandle, silent=True).records:
            Query("create index %s on %s" % (name, cmd), dbHandle=dbhandle)

    @staticmethod
    def cleanPlayerTable(dbhandle):
        """remove now unneeded columns host, password and make names unique"""
        playerCounts = IntDict()
        names = {}
        keep = {}
        for nameId, name in Query('select id,name from player', dbHandle=dbhandle).records:
            playerCounts[name] += 1
            names[int(nameId)] = name
        for name, counter in defaultdict.items(playerCounts):
            nameIds = [x[0] for x in names.items() if x[1] == name]
            keepId = nameIds[0]
            keep[keepId] = name
            if counter > 1:
                for nameId in nameIds[1:]:
                    Query('update score set player=%d where player=%d' % (keepId, nameId), dbHandle=dbhandle)
                    Query('update game set p0=%d where p0=%d' % (keepId, nameId), dbHandle=dbhandle)
                    Query('update game set p1=%d where p1=%d' % (keepId, nameId), dbHandle=dbhandle)
                    Query('update game set p2=%d where p2=%d' % (keepId, nameId), dbHandle=dbhandle)
                    Query('update game set p3=%d where p3=%d' % (keepId, nameId), dbHandle=dbhandle)
                    Query('delete from player where id=%d' % nameId, dbHandle=dbhandle)
        Query('drop table player', dbHandle=dbhandle)
        Query.createTable(dbhandle, 'player')
        for nameId, name in keep.items():
            Query('insert into player(id,name) values(?,?)',  list([nameId, name]), dbHandle=dbhandle)

    @staticmethod
    def removeGameServer(dbhandle):
        """drops column server from table game. Sqlite3 cannot drop columns"""
        Query('create table gameback(%s)' % Query.schema['game'], dbHandle=dbhandle)
        Query('insert into gameback '
            'select id,seed,autoplay,starttime,endtime,ruleset,p0,p1,p2,p3 from game', dbHandle=dbhandle)
        Query('drop table game', dbHandle=dbhandle)
        Query('create table game(%s)' % Query.schema['game'], dbHandle=dbhandle)
        Query('insert into game '
            'select id,seed,autoplay,starttime,endtime,ruleset,p0,p1,p2,p3 from gameback', dbHandle=dbhandle)
        Query('drop table gameback', dbHandle=dbhandle)

    @staticmethod
    def upgradeDb(dbhandle):
        """upgrade any version to current schema"""
        Query.createIndex(dbhandle, 'idxgame', 'score(game)')
        if not Query.tableHasField(dbhandle, 'game', 'autoplay'):
            Query('ALTER TABLE game add autoplay integer default 0', dbHandle=dbhandle)
        if Query.tableHasField(dbhandle, 'player', 'host'):
            Query.cleanPlayerTable(dbhandle)
        if InternalParameters.isServer:
            if not Query.tableHasField(dbhandle, 'player', 'password'):
                Query('ALTER TABLE player add password text', dbHandle=dbhandle)
        else:
            Query.createTable(dbhandle, 'passwords')
            if not Query.tableHasField(dbhandle, 'server', 'lastruleset'):
                Query('alter table server add lastruleset integer', dbHandle=dbhandle)
        if Query.tableHasField(dbhandle, 'game', 'server'):
            Query.removeGameServer(dbhandle)

def initDb():
    """open the db, create or update it if needed.
    Returns a dbHandle."""
    dbhandle = QSqlDatabase("QSQLITE")
    if InternalParameters.isServer:
        name = 'kajonggserver.db'
    else:
        name = 'kajongg.db'
    dbpath = InternalParameters.dbPath or appdataDir() + name
    dbhandle.setDatabaseName(dbpath)
    dbExisted = os.path.exists(dbpath)
    if InternalParameters.showSql:
        logDebug('%s database %s' % \
            ('using' if dbExisted else 'creating', dbpath))
    if not dbhandle.open():
        logError('%s %s' % (str(dbhandle.lastError().text()), dbpath))
        sys.exit(1)
    with Transaction(dbhandle):
        if not dbExisted:
            Query.createTables(dbhandle)
        else:
            Query.upgradeDb(dbhandle)
    return dbhandle
