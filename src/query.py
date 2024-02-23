# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

partially based on C++ code from:
 - Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

SPDX-License-Identifier: GPL-2.0

"""

import os
import traceback
import time
import datetime
import random
from collections import defaultdict
import sqlite3
from typing import List, Tuple, Union, Any, Optional, cast, Literal

from mi18n import i18n, i18ncE
from util import Duration
from log import logInfo, logWarning, logException, logError, logDebug
from common import IntDict, Options, Internal, Debug, appdataDir, id4

class QueryException(Exception):

    """as the name says"""

    def __init__(self, msg:str) ->None:
        Exception.__init__(self, msg)


class DBCursor(sqlite3.Cursor):

    """logging wrapper"""

    def __init__(self, dbHandle:'DBHandle') ->None:
        sqlite3.Cursor.__init__(self, dbHandle)
        self.statement:str
        self.parameters:Optional[Tuple[Union[str, int], ...]] = None
        self.failure:Optional[Exception] = None

    def execute(self, statement:str, parameters:Optional[Tuple[Union[str, int], ...]]=None, # type:ignore[override]
                silent:bool=False, failSilent:bool=False, mayFail:bool=False) ->None:
        """logging wrapper, returning all selected data"""
        # pylint: disable=too-many-branches
        self.statement = statement
        self.parameters = parameters
        if not silent:
            logDebug(str(self))
        try:
            for _ in range(10):
                try:
                    with Duration(statement, 60.0 if Debug.neutral else 2.0):
                        if isinstance(parameters, list):
                            sqlite3.Cursor.executemany(
                                self, statement, parameters)
                        elif parameters:
                            sqlite3.Cursor.execute(self, statement, parameters)
                        else:
                            sqlite3.Cursor.execute(self, statement)
                    break
                except sqlite3.OperationalError as exc:
                    logDebug(
                        f"{self} failed after {_} tries:{' '.join(exc.args)}")
                    time.sleep(1)
                else:
                    break
            else:
                raise sqlite3.OperationalError(
                    f'Failed after 10 tries:{self}')
            self.failure = None
        except sqlite3.Error as exc:
            self.failure = exc
            msg = f"ERROR in {DBHandle.dbPath()}: {exc.message if hasattr(exc, 'message') else ''} for {self}"
            if mayFail:
                if not failSilent:
                    logDebug(msg)
            else:
                if not failSilent:
                    logError(msg)
                raise QueryException(msg) from exc
            return

    def __str__(self) ->str:
        """the statement"""
        if self.parameters is not None:
            return f"{self.statement} [{self.parameters}]"
        return self.statement


class DBHandle(sqlite3.Connection):

    """a handle with our preferred configuration"""

    def __init__(self, path: str) ->None:
        assert Internal.db is None, id(self)
        Internal.db = self
        self.inTransaction:Optional[datetime.datetime] = None
        self.path = path
        self.identifier = None
        try:
            sqlite3.Connection.__init__(self, self.path, timeout=10.0)
        except sqlite3.Error as exc:
            if hasattr(exc, 'message'):
                msg = exc.message
            elif hasattr(exc, 'args'):
                msg = ' '.join(exc.args)
            else:
                msg = ''
            logException(f'opening {self.path}: {msg}')
        if self.hasTable('general'):
            cursor = self.cursor()
            cursor.execute('select ident from general')
            self.identifier = cursor.fetchone()[0]
        if Debug.sql:
            logDebug(f'Opened {self.path} with identifier {self.identifier}')

    def __enter__(self) ->'DBHandle':
        self.inTransaction = datetime.datetime.now()
        if Debug.sql:
            logDebug('starting transaction')
        return sqlite3.Connection.__enter__(self)

    def __exit__(self, *args:Any) ->Literal[False]:
        sqlite3.Connection.__exit__(self, *args)
        if Debug.sql:
            logDebug('finished transaction')
        return False

    @staticmethod
    def dbPath() ->str:
        """
        The path for the data base.

        @return: The full path for kajonggserver.db or kajongg.db.
        @rtype: C{str}
        """
        name = 'kajonggserver' if Internal.isServer else 'kajongg'
        name += '3.db'
        return Options.dbPath if Options.dbPath else os.path.join(appdataDir(), name)

    @property
    def debug_name(self) ->str:
        """get name for log messages. Readonly."""
        stack = [x[2] for x in traceback.extract_stack()]
        name = stack[-3]
        if name in ('__exit__', '__init__'):
            name = stack[-4]
        return f'{name} on {self.path}_{id4(self)}'

    def commit(self, silent:bool=False) ->None:
        """commit and log it"""
        try:
            sqlite3.Connection.commit(self)
        except sqlite3.Error as exc:
            if not silent:
                logWarning(
                    f'{DBHandle.dbPath()} cannot commit: {exc} :')

    def rollback(self, silent:bool=False) ->None:
        """rollback and log it"""
        try:
            sqlite3.Connection.rollback(self)
            if not silent and Debug.sql:
                logDebug(f'{id(self):x} rollbacked transaction')
        except sqlite3.Error as exc:
            logWarning(f'{DBHandle.dbPath()} cannot rollback: {exc}')

    def close(self, silent:bool=False) ->None:
        """just for logging"""
        if not silent and (Debug.sql or Debug.quit):
            if self is Internal.db:
                logDebug(f'Closing Internal.db: {self.path}')
            else:
                logDebug(f'Closing DBHandle {self}: {self.path}')
        if self is Internal.db:
            Internal.db = None
        try:
            self.commit(silent=True)
        except sqlite3.Error:
            self.rollback()
        try:
            sqlite3.Connection.close(self)
        except sqlite3.Error as exc:
            logDebug(exc)

    @staticmethod
    def hasTable(table:str) ->bool:
        """does the table contain table?"""
        return len(Query(f'SELECT name FROM sqlite_master WHERE type="table" AND name="{table}"').records) > 0

    def tableHasField(self, table:str, field:str) ->bool:
        """does the table contain a column named field?"""
        cursor = self.cursor()
        cursor.execute(f'select * from {table}')
        return any(x[0] == field for x in cursor.description)


class Query:

    """a wrapper arout python sqlite3, adding logging and some exception handling.
    For selecting queries we fill a list with ALL records which is never much.
    Every record is a list of all fields. q.records[0][1] is record 0, field 1.
    """

    localServerName = i18ncE(
        'kajongg name for local game server',
        'Local Game')

    def __init__(self, statement:str,
                 args:Union[None,Tuple[Union[str, int, float], ...],List[List[Union[str,int,float]]]]=None,
                 silent:bool=False, mayFail:bool=False, failSilent:bool=False) ->None:
        """we take one sql statement.
        Do prepared queries by passing the parameters in args.
        If args is a list of lists, execute the prepared query for every sublist.
        Use Internal.db for db access.
        Else if the default dbHandle (Internal.db) is defined, use it."""
        silent |= not Debug.sql
        self.msg = None
        self.records:List[List[Any]] = []
        self.statement = statement
        self.args = args
        if Internal.db:
            self.cursor = Internal.db.cursor(
                DBCursor)
            self.cursor.execute(
                statement,
                args,
                silent=silent,
                mayFail=mayFail,
                failSilent=failSilent)
            self.failure = self.cursor.failure
            self.records = list(self.cursor.fetchall())
            if not Internal.db.inTransaction:
                Internal.db.commit()
        else:
            # may happen at shutdown
            self.cursor = None
            self.failure = None
            self.records = []
        if self.records and Debug.sql:
            logDebug(f'result set:{self.records}')

    def __str__(self) ->str:
        return f"{self.statement} {'args=' + ','.join(str(x) for x in self.args) if self.args else ''}"

    def rowcount(self) ->int:
        """how many rows were affected?"""
        return self.cursor.rowcount if self.cursor else 0


def initDb() ->bool:
    """open the db, create or update it if needed.
    sets Internal.db."""
    PrepareDB(DBHandle.dbPath())  # create or upgrade
    DBHandle(DBHandle.dbPath())
# if not Internal.db = DBHandle.default:  # had to create it. Close and reopen
#        Internal.db = DBHandle()
#        assert Internal.db = DBHandle.default
#    except sqlite3.Error as exc:
#        logException(exc)
#        return False
    return True


class PrepareDB:

    """create or upgrade DB if needed"""
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
            primary key(ruleset,list,position)"""
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
                ident text,
                schemaversion text"""

    def __init__(self, path:str) ->None:
        self.path = path
        if not os.path.exists(path):
            self.__create()
        else:
            self.__upgrade()

    def __create(self) ->None:
        """create a brand new kajongg database"""
        tmpPath = f'{self.path}.new.{int(os.getpid())}'
        Internal.db = DBHandle(tmpPath)
        try:
            with Internal.db:
                self.createTables()
                self.__generateDbIdent()
                Query(
                    'UPDATE general SET schemaversion=?', (Internal.defaultPort,))
        finally:
            Internal.db.close(silent=True)
        if os.path.exists(self.path):
            # somebody was faster
            os.remove(tmpPath)
        else:
            os.rename(tmpPath, self.path)

    @staticmethod
    def __currentVersion() ->str:
        """
        Get current version of DB schema as a comparable string.

        @returns: The current version from the database.
        @rtype: C{str}
        """
        if Internal.db.tableHasField('general', 'schemaversion'):
            return Query('select schemaversion from general').records[0][0]
        return '1.1.1'

    def __upgrade(self) ->None:
        """upgrade the structure of an existing kajongg database"""
        try:
            Internal.db = DBHandle(self.path)
            allVersions = list(['4.13.0', '8300', '8301'])
            assert allVersions[-1] == str(Internal.defaultPort), f'{allVersions[-1]} != {str(Internal.defaultPort)}'
            # skip versions before current db versions:
            currentVersion = self.__currentVersion()
            while allVersions and allVersions[0] <= currentVersion:
                allVersions = allVersions[1:]
            for version in allVersions:
                currentVersion = self.__currentVersion()
                with Internal.db:  # transaction
                    updateMethodName = f"updateToVersion{version.replace('.', '_')}"
                    if hasattr(self, updateMethodName):
                        getattr(self, updateMethodName)()
                    Query('UPDATE general SET schemaversion=?', (version,))
                logInfo(i18n('Database %1 updated from schema %2 to %3',
                             Internal.db.path, currentVersion, version), showDialog=True)
        except sqlite3.Error as exc:
            logException(f'opening {self.path}: {exc}')
        finally:
            Internal.db.close(silent=True)

    @classmethod
    def sqlForCreateTable(cls, table:str) ->str:
        """the SQL command for creating 'table'"""
        return f"create table {table}({cls.schema[table]})"

    @classmethod
    def createTable(cls, table:str) ->None:
        """create a single table using the predefined schema"""
        if not Internal.db.hasTable(table):
            Query(cls.sqlForCreateTable(table))

    @classmethod
    def createTables(cls) ->None:
        """creates empty tables"""
        for table in ['player', 'game', 'score', 'ruleset', 'rule', 'general']:
            cls.createTable(table)
        cls.createIndex('idxgame', 'score(game)')
        # this makes finding suspended games much faster in the presence
        # of many test games (with autoplay=1)
        cls.createIndex('idxautoplay', 'game(autoplay)')

        if Internal.isServer:
            Query('ALTER TABLE player add password text')
        else:
            cls.createTable('passwords')
            cls.createTable('server')

    @staticmethod
    def createIndex(name:str, cmd:str) ->None:
        """only try to create it if it does not yet exist. Do not use create if not exists because
        we want debug output only if we really create the index"""
        if not Query(
                "select 1 from sqlite_master where type='index' and name=?", (
                    name,),
                silent=True).records:
            Query(f"create index {name} on {cmd}")

    def cleanPlayerTable(self) ->None:
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
            if cast(int, counter) > 1:
                for nameId in nameIds[1:]:
                    Query(
                        f'update score set player={int(keepId)} where player={int(nameId)}')
                    Query(
                        f'update game set p0={int(keepId)} where p0={int(nameId)}')
                    Query(
                        f'update game set p1={int(keepId)} where p1={int(nameId)}')
                    Query(
                        f'update game set p2={int(keepId)} where p2={int(nameId)}')
                    Query(
                        f'update game set p3={int(keepId)} where p3={int(nameId)}')
                    Query(f'delete from player where id={int(nameId)}')
        Query('drop table player')
        self.createTable('player')
        for nameId, name in keep.items():
            Query('insert into player(id,name) values(?,?)', (nameId, name))

    @classmethod
    def removeGameServer(cls) ->None:
        """drops column server from table game. Sqlite3 cannot drop columns"""
        Query(f"create table gameback({cls.schema['game']})")
        Query('insert into gameback '
              'select id,seed,autoplay,starttime,endtime,ruleset,p0,p1,p2,p3 from game')
        Query('drop table game')
        Query(f"create table game({cls.schema['game']})")
        Query('insert into game '
              'select id,seed,autoplay,starttime,endtime,ruleset,p0,p1,p2,p3 from gameback')
        Query('drop table gameback')

    def removeUsedRuleset(self) ->None:
        """eliminate usedruleset and usedrule"""
        if Internal.db.hasTable('usedruleset'):
            if Internal.db.hasTable('ruleset'):
                Query('UPDATE ruleset set id=-id where id>0')
                Query(
                    'INSERT OR IGNORE INTO usedruleset SELECT * FROM ruleset')
                Query('DROP TABLE ruleset')
            Query('ALTER TABLE usedruleset RENAME TO ruleset')
        if Internal.db.hasTable('usedrule'):
            if Internal.db.hasTable('rule'):
                Query('UPDATE rule set ruleset=-ruleset where ruleset>0')
                Query('INSERT OR IGNORE INTO usedrule SELECT * FROM rule')
                Query('DROP TABLE rule')
            Query('ALTER TABLE usedrule RENAME TO rule')
        query = Query("select count(1) from sqlite_master "
                      "where type='table' and tbl_name='ruleset' and sql like '%name text unique,%'", silent=True)
        if int(query.records[0][0]):
            # make name non-unique. Needed for used rulesets: Content may change with identical name
            # and we now have both ruleset templates and copies of used
            # rulesets in the same table
            for statement in list([
                    f"create table temp({self.schema['ruleset']})",
                    'insert into temp select id,name,hash,description from ruleset',
                    'drop table ruleset',
                    self.sqlForCreateTable('ruleset'),
                    'insert into ruleset select * from temp',
                    'drop table temp']):
                Query(statement)
        query = Query("select count(1) from sqlite_master "
                      "where type='table' and tbl_name='rule' and sql like '%unique (ruleset,name)%'", silent=True)
        if int(query.records[0][0]):
            # make ruleset,name non-unique
            for statement in list([
                    f"create table temp({self.schema['rule']})",
                    'insert into temp select * from rule',
                    'drop table rule',
                    self.sqlForCreateTable('rule'),
                    'insert into rule select * from temp',
                    'drop table temp']):
                Query(statement)

    @staticmethod
    def __generateDbIdent() ->None:
        """make sure the database has a unique ident and get it"""
        records = Query('select ident from general').records
        assert len(records) < 2
        if not records:
            dbIdent = str(random.randrange(100000000000))
            Query("INSERT INTO general(ident) values(?)", (dbIdent,))
            if Debug.sql:
                logDebug(
                    f'generated new dbIdent {dbIdent} for {Internal.db.path}')
