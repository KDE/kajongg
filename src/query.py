# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

partially based on C++ code from:
    Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

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
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.


"""

import os, sys, time, datetime, traceback, random
from collections import defaultdict
from PyQt4.QtCore import QVariant, QString
from util import logInfo, logWarning, logException, logDebug, appdataDir, m18ncE, xToUtf8
from common import InternalParameters, Debug, IntDict
from PyQt4.QtSql import QSqlQuery, QSqlDatabase, QSql


class DBHandle(QSqlDatabase):
    """a handle with our preferred configuration"""
    default = None
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
            ruleset integer references ruleset(id),
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
            notrotated integer,
            player integer constraint fk_player references player(id),
            scoretime text,
            won integer,
            penalty integer default 0,
            prevailing text,
            wind text,
            points integer,
            payments integer,
            balance integer"""
    schema['ruleset'] = """
            id integer primary key,
            name text,
            hash text,
            description text"""
    schema['rule'] = """
            ruleset integer,
            list integer,
            position integer,
            name text,
            definition text,
            points text,
            doubles text,
            limits text,
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
    schema['general'] = """
                ident text"""

    def sqlForCreateTable(self, table):
        """the SQL command for creating 'table'"""
        return "create table %s(%s)" % (table, self.schema[table])

    def createTable(self, table):
        """create a single table using the predefined schema"""
        if not self.hasTable(table):
            Query(self.sqlForCreateTable(table), mayFail=True)

    def createTables(self):
        """creates empty tables"""
        for table in ['player', 'game', 'score', 'ruleset', 'rule']:
            self.createTable(table)
        self.createIndex('idxgame', 'score(game)')

        if InternalParameters.isServer:
            Query('ALTER TABLE player add password text')
        else:
            self.createTable('passwords')
            self.createTable('server')

    def createIndex(self, name, cmd):
        """only try to create it if it does not yet exist. Do not use create if not exists because
        we want debug output only if we really create the index"""
        if not Query("select 1 from sqlite_master where type='index' and name='%s'" % name,
                silent=True, dbHandle=self).records:
            Query("create index %s on %s" % (name, cmd))

    def cleanPlayerTable(self):
        """remove now unneeded columns host, password and make names unique"""
        playerCounts = IntDict()
        names = {}
        keep = {}
        for nameId, name in Query('select id,name from player').records:
            playerCounts[name] += 1
            names[int(nameId)] = name
        for name, counter in defaultdict.items(playerCounts):
            nameIds = [x[0] for x in names.items() if x[1] == name]
            keepId = nameIds[0]
            keep[keepId] = name
            if counter > 1:
                for nameId in nameIds[1:]:
                    Query('update score set player=%d where player=%d' % (keepId, nameId))
                    Query('update game set p0=%d where p0=%d' % (keepId, nameId))
                    Query('update game set p1=%d where p1=%d' % (keepId, nameId))
                    Query('update game set p2=%d where p2=%d' % (keepId, nameId))
                    Query('update game set p3=%d where p3=%d' % (keepId, nameId))
                    Query('delete from player where id=%d' % nameId)
        Query('drop table player')
        self.createTable('player')
        for nameId, name in keep.items():
            Query('insert into player(id,name) values(?,?)', list([nameId, name]))

    def removeGameServer(self):
        """drops column server from table game. Sqlite3 cannot drop columns"""
        Query('create table gameback(%s)' % self.schema['game'])
        Query('insert into gameback '
            'select id,seed,autoplay,starttime,endtime,ruleset,p0,p1,p2,p3 from game')
        Query('drop table game')
        Query('create table game(%s)' % self.schema['game'])
        Query('insert into game '
            'select id,seed,autoplay,starttime,endtime,ruleset,p0,p1,p2,p3 from gameback')
        Query('drop table gameback')

    def stopGamesWithRegex(self):
        """we do not support Regex rules anymore.
        Mark all games using them as finished - until somebody
        complains. So for now always return False"""
        if not self.hasTable('usedrule'):
            return
        usedRegexRulesets = Query("select distinct ruleset from usedrule "
            "where definition not like 'F%' "
            "and definition not like 'O%' "
            "and definition not like 'int%' "
            "and definition not like 'bool%' "
            "and definition<>'' "
            "and definition not like 'XEAST9X%'").records
        usedRegexRulesets = list(unicode(x[0]) for x in usedRegexRulesets)
        if not usedRegexRulesets:
            return
        openRegexGames = Query("select id from game "
            "where endtime is null "
            "and ruleset in (%s)" % ','.join(usedRegexRulesets)).records
        openRegexGames = list(x[0] for x in openRegexGames)
        if not openRegexGames:
            return
        logInfo('Marking games using rules with regular expressions as finished: %s' % openRegexGames)
        for openGame in openRegexGames:
            endtime = datetime.datetime.now().replace(microsecond=0).isoformat()
            Query('update game set endtime=? where id=?',
                list([endtime, openGame]))

    def removeUsedRuleset(self):
        """eliminate usedruleset and usedrule"""
        if self.hasTable('usedruleset'):
            if self.hasTable('ruleset'):
                Query('UPDATE ruleset set id=-id where id>0')
                Query('INSERT OR IGNORE INTO usedruleset SELECT * FROM ruleset')
                Query('DROP TABLE ruleset')
            Query('ALTER TABLE usedruleset RENAME TO ruleset')
        if self.hasTable('usedrule'):
            if self.hasTable('rule'):
                Query('UPDATE rule set ruleset=-ruleset where ruleset>0')
                Query('INSERT OR IGNORE INTO usedrule SELECT * FROM rule')
                Query('DROP TABLE rule')
            Query('ALTER TABLE usedrule RENAME TO rule')
        query = Query("select count(1) from sqlite_master "
            "where type='table' and tbl_name='ruleset' and sql like '%name text unique,%'", silent=True)
        if int(query.records[0][0]):
            # make name non-unique. Needed for used rulesets: Content may change with identical name
            # and we now have both ruleset templates and copies of used rulesets in the same table
            Query([
                    'create table temp(%s)' % self.schema['ruleset'],
                    'insert into temp select id,name,hash,description from ruleset',
                    'drop table ruleset',
                    self.sqlForCreateTable('ruleset'),
                    'insert into ruleset select * from temp',
                    'drop table temp'])

    def upgradeDb(self):
        """upgrade any version to current schema"""
        self.createIndex('idxgame', 'score(game)')
        if not self.tableHasField('game', 'autoplay'):
            Query('ALTER TABLE game add autoplay integer default 0')
        if not self.tableHasField('score', 'penalty'):
            Query('ALTER TABLE score add penalty integer default 0')
            Query("UPDATE score SET penalty=1 WHERE manualrules LIKE "
                    "'False Naming%' OR manualrules LIKE 'False Decl%'")
        if self.tableHasField('player', 'host'):
            self.cleanPlayerTable()
        if InternalParameters.isServer:
            if not self.tableHasField('player', 'password'):
                Query('ALTER TABLE player add password text')
        else:
            self.createTable('passwords')
            if not self.tableHasField('server', 'lastruleset'):
                Query('alter table server add lastruleset integer')
        if self.tableHasField('game', 'server'):
            self.removeGameServer()
        if not self.tableHasField('score', 'notrotated'):
            Query('ALTER TABLE score add notrotated integer default 0')
        self.removeUsedRuleset()
        self.stopGamesWithRegex()
        self.__generateDbIdent()

    def __generateDbIdent(self):
        """make sure the database has a unique ident and get it"""
        self.createTable('general')
        records = Query('select ident from general').records
        assert len(records) < 2
        if records:
            InternalParameters.dbIdent = records[0][0]
            if Debug.sql:
                logDebug('found dbIdent for %s: %s' % (self.name, InternalParameters.dbIdent))
        else:
            InternalParameters.dbIdent = str(random.randrange(100000000000))
            Query("INSERT INTO general(ident) values('%s')" % InternalParameters.dbIdent)

    def __init__(self):
        QSqlDatabase.__init__(self, "QSQLITE")
        if not DBHandle.default:
            DBHandle.default = self
        if not os.path.exists(self.dbPath()):
            self.createDatabase()
        self.setDatabaseName(self.dbPath())
        if not self.open():
            self.default = None
            logException('opening %s: %s' % (self.dbPath(), self.lastError()))
        # timeout in msec:
        self.setConnectOptions("QSQLITE_BUSY_TIMEOUT=2000")
        with Transaction(silent=True):
            self.upgradeDb()

    def createDatabase(self):
        """use a temp file name. When done, rename to final file name,
        thusly avoiding races if two processes want to build the same
        database"""
        tempName = '%s.new.%d' % (self.dbPath(), os.getpid())
        self.setDatabaseName(tempName)
        if not self.open():
            logException('creating %s: %s' % (tempName, self.lastError()))
        with Transaction(silent=True):
            self.createTables()
            self.__generateDbIdent()
        QSqlDatabase.close(self)
        newName = self.dbPath()
        if os.path.exists(newName):
            os.remove(tempName)
        else:
            os.rename(tempName, newName)

    @staticmethod
    def dbPath():
        """the path for the data base"""
        name = 'kajonggserver.db' if InternalParameters.isServer else 'kajongg.db'
        return InternalParameters.dbPath.decode('utf-8') if InternalParameters.dbPath else appdataDir() + name

    def __del__(self):
        """really free the handle"""
        QSqlDatabase.close(self)
        if Debug.sql:
            logDebug('closed DBHandle %s' % self.name)

    @apply
    def name():
        """get name for log messages. Readonly."""
        def fget(self):
            # pylint: disable=W0212
            stack = list(x[2] for x in traceback.extract_stack())
            name = stack[-3]
            if name in ('__exit__', '__init__'):
                name = stack[-4]
            return '%s on %s (%x)' % (name , self.databaseName(), id(self))
        return property(**locals())

    def transaction(self, silent=None):
        """commit and log it"""
        if QSqlDatabase.transaction(self):
            if not silent and Debug.sql:
                logDebug('%x started transaction' % id(self))
        else:
            logWarning('%s cannot start transaction: %s' % (self.name, self.lastError()))

    def commit(self, silent=None):
        """commit and log it"""
        result = QSqlDatabase.commit(self)
        if result:
            if not silent and Debug.sql:
                logDebug('%x committed transaction' % id(self))
        else:
            logWarning('%s cannot commit: %s :' % (self.name, self.lastError()))

    def lastError(self):
        """converted to unicode"""
        return unicode(QSqlDatabase.lastError(self).text())

    def rollback(self, silent=None):
        """rollback and log it"""
        if QSqlDatabase.rollback(self):
            if not silent and Debug.sql:
                logDebug('%x rollbacked transaction' % id(self))
        else:
            logWarning('%s cannot rollback: %s' % (self.name, self.lastError()))

    def close(self):
        """__del__ closes"""
        assert False, '%s: You may not call close on a DBHandle, just delete it' % self.name

    def hasTable(self, table):
        """does the table contain table?"""
        return table in self.driver().tables(QSql.Tables)

    def tableHasField(self, table, field):
        """does the table contain a column named field?"""
        query = QSqlQuery(self)
        query.exec_('select * from %s' % table)
        record = query.record()
        for idx in range(record.count()):
            if record.fieldName(idx) == field:
                return True

class Transaction(object):
    """a helper class for SQL transactions. Use as 'with Transaction():'"""
    def __init__(self, dbHandle=None, silent=False):
        """start a transaction.
        silent=True suppresses transaction messages but not the query messages within the transaction."""
        self.silent = silent
        self.dbhandle = dbHandle or DBHandle.default
        self.dbhandle.transaction(silent=self.silent)
        self.active = True
        self.startTime = datetime.datetime.now()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trback):
        """end the transaction"""
        diff = datetime.datetime.now() - self.startTime
        if diff > datetime.timedelta(seconds=1.0):
            logWarning('%s took %d.%06d seconds' % (
                    self.dbhandle.name, diff.seconds, diff.microseconds))
        if self.active and trback is None:
            self.dbhandle.commit(silent=self.silent)
        else:
            self.dbhandle.rollback(silent=self.silent)
            if exc_type:
                exc_type(exc_value)

    def rollback(self):
        """explicit rollback by the caller"""
        self.dbhandle.rollback() # never silent
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

    localServerName = m18ncE('kajongg name for local game server', 'Local Game')

    def __init__(self, cmdList, args=None, dbHandle=None, silent=False, mayFail=False):
        """we take a list of sql statements. Only the last one is allowed to be
        a select statement.
        Do prepared queries by passing a single query statement in cmdList
        and the parameters in args. If args is a list of lists, execute the
        prepared query for every sublist.
        If dbHandle is passed, use that for db access.
        Else if the default dbHandle (DBHandle.default) is defined, use it."""
        # pylint: disable=R0912
        # pylint says too many branches
        silent |= not Debug.sql
        self.dbHandle = dbHandle or DBHandle.default
        preparedQuery = not isinstance(cmdList, list) and bool(args)
        self.query = QSqlQuery(self.dbHandle)
        self.msg = None
        self.records = []
        if not isinstance(cmdList, list):
            cmdList = list([cmdList])
        self.cmdList = cmdList
        for cmd in cmdList:
            retryCount = 0
            while retryCount < 100:
                self.lastError = None
                if preparedQuery:
                    self.query.prepare(cmd)
                    if not isinstance(args[0], list):
                        args = list([args])
                    for dataSet in args:
                        if not silent:
                            _, utf8Args = xToUtf8(u'', dataSet)
                            logDebug("{cmd} [{args}]".format(cmd=cmd, args=", ".join(utf8Args)))
                        for value in dataSet:
                            self.query.addBindValue(QVariant(value))
                        self.success = self.query.exec_()
                        if not self.success:
                            break
                else:
                    if not silent:
                        logDebug('%s %s' % (self.dbHandle.name, cmd))
                    self.success = self.query.exec_(cmd)
                if self.success or self.query.lastError().number() not in (5, 6):
                    # 5: database locked, 6: table locked. Where can we get symbols for this?
                    break
                time.sleep(0.1)
                retryCount += 1
            if not self.success:
                self.lastError = unicode(self.query.lastError().text())
                self.msg = 'ERROR in %s: %s' % (self.dbHandle.databaseName(), self.lastError)
                if mayFail:
                    if not silent:
                        logDebug(self.msg)
                else:
                    logException(self.msg)
                return
        self.records = None
        self.fields = None
        if self.query.isSelect():
            self.retrieveRecords()

    def rowcount(self):
        """how many rows were affected?"""
        return self.query.numRowsAffected()

    def retrieveRecords(self):
        """get all records from SQL into a python list"""
        record = self.query.record()
        self.fields = [record.field(x) for x in range(record.count())]
        self.records = []
        while self.query.next():
            self.records.append([self.__convertField(x) for x in range(record.count())])

    def __convertField(self, idx):
        """convert a QSqlQuery field into a python value"""
        result = self.query.value(idx).toPyObject()
        if isinstance(result, QString):
            result = unicode(result)
        if isinstance(result, long) and -sys.maxint -1 <= result <= sys.maxint:
            result = int(result)
        return result

def initDb():
    """open the db, create or update it if needed.
    sets DBHandle.default."""
    try:
        DBHandle() # sets DBHandle.default
    except BaseException, exc:
        DBHandle.default = None
        logException(exc)
        return False
    return True
