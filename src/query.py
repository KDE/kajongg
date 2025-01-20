# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

partially based on C++ code from:
 - Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

SPDX-License-Identifier: GPL-2.0-only

"""

import os
import traceback
import datetime
import random
import sqlite3
from collections import namedtuple
from typing import List, Tuple, Union, Any, Optional, Literal, Generator

from mi18n import i18n, i18ncE
from util import Duration
from log import logInfo, logWarning, logException, logError, logDebug
from common import Options, Internal, Debug, appdataDir, ReprMixin

class QueryException(Exception):

    """as the name says"""

    def __init__(self, msg:str) ->None:
        super().__init__(msg)


class DBCursor(sqlite3.Cursor, ReprMixin):

    """logging wrapper"""

    def __init__(self, dbHandle:'DBHandle') ->None:
        super().__init__(dbHandle)
        self.statement:str
        self.parameters:Optional[Tuple[Union[str, int], ...]] = None

    def execute(self, statement:str, parameters:Optional[Tuple[Union[str, int], ...]]=None, # type:ignore[override]
                silent:bool=False, failSilent:bool=False, mayFail:bool=False) ->None:
        """logging wrapper, returning all selected data"""
        self.statement = statement
        self.parameters = parameters
        if not silent:
            logDebug(repr(self))
        try:
            with Duration(f'{self!r}', 60.0 if Debug.neutral else 3.0):
                if isinstance(parameters, list):
                    sqlite3.Cursor.executemany(
                        self, statement, parameters)
                elif parameters:
                    super().execute(statement, parameters)
                else:
                    super().execute(statement)
        except sqlite3.Error as exc:
            msg = f"{self!r}: ERROR {exc}"
            if mayFail:
                if not failSilent and Debug.sql:
                    logDebug(msg)
            else:
                if not failSilent:
                    logError(msg)
                raise

    def __str__(self) ->str:
        """the statement"""
        if self.parameters is not None:
            return f"{self.connection}:{self.statement} [{self.parameters}]"
        return f"{self.connection}:{self.statement}"


class DBHandle(sqlite3.Connection, ReprMixin):

    """a handle with our preferred configuration"""

    def __init__(self, path: str) ->None:
        assert Internal.db is None, id(self)
        Internal.db = self
        self.inTransaction:Optional[datetime.datetime] = None
        self.path = path
        self.identifier = None
        try:
            super().__init__(self.path, timeout=10.0, detect_types=sqlite3.PARSE_DECLTYPES)
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
            logDebug(f'{self} opened with identifier {self.identifier}')

    def __enter__(self) ->'DBHandle':
        self.inTransaction = datetime.datetime.now()
        if Debug.sql:
            logDebug('starting transaction')
        return super().__enter__()

    def __exit__(self, *args:Any) ->Literal[False]:
        super().__exit__(*args)
        if Debug.sql:
            logDebug('finished transaction')
        self.inTransaction = None
        return False

    def __str__(self):
        return f'{self.dbPath()}'

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
        return f'{name} on {self!r}'

    def commit(self, silent:bool=False) ->None:
        """commit and log it"""
        try:
            sqlite3.Connection.commit(self)
        except sqlite3.Error as exc:
            if not silent:
                logWarning(
                    f'{self!r} cannot commit: {exc} :')

    def rollback(self, silent:bool=False) ->None:
        """rollback and log it"""
        try:
            sqlite3.Connection.rollback(self)
            if not silent and Debug.sql:
                logDebug(f'{self!r} rollback')
        except sqlite3.Error as exc:
            logWarning(f'{self!r} cannot rollback: {exc}')

    def close(self, silent:bool=False) ->None:
        """just for logging"""
        if not silent and (Debug.sql or Debug.quit):
            if self is Internal.db:
                logDebug(f'{self!r} closing Internal.db')
            else:
                logDebug(f'{self!r} closing')
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


class Query(ReprMixin):

    """a wrapper arout python sqlite3, adding logging and some exception handling.
    For selecting queries we fill a list with ALL records which is never much.
    Every record is a list of all fields. q.records[0][1] is record 0, field 1.
    """

    localServerName = i18ncE(
        'kajongg name for local game server',
        'Local Game')

    def __init__(self, statement:str,
                 args:Union[None,Tuple[Union[str, int, float], ...],List[List[Union[str,int,float]]]]=None,
                 silent:bool=False, mayFail:bool=False, failSilent:bool=False,
                 fields:Optional[str]=None) ->None:
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
        self.fields = fields  # a field name might be "lastname as playername"
        self.tuplefields:Optional[List[str]] = None
        if fields:
            self.tuplefields = list(self.__tuple_fieldnames())
            self.statement = self.statement.format(fields=fields)

        if Internal.db:
            self.cursor = Internal.db.cursor(
                DBCursor)
            self.cursor.execute(
                self.statement,
                args,
                silent=silent,
                mayFail=mayFail,
                failSilent=failSilent)
            self.records = list(self.cursor.fetchall())
            if not Internal.db.inTransaction:
                Internal.db.commit()
        else:
            # may happen at shutdown
            logDebug(f'Internal.db is None for {self}')
            self.cursor = None
            self.records = []
        if self.records and Debug.sql:
            logDebug(f'result set:{self.records}')

    def __tupleName(self) ->str:
        """the class name of the returned tuples.
           For now:

           - use first table name from statement.
           - If none found: use 'Fields'

           Query might get an arg tupleName which would override this
        """
        lower = self.statement.lower()
        parts = lower.split(' from ')
        if len(parts) > 1:
            return 'Query_' + parts[1].split()[0].strip().capitalize()
        return 'Query_Fields'

    def __tuple_fieldnames(self) ->Generator[str, None, None]:
        """translates 'fieldname as myname' into 'myname' """
        if not isinstance(self.fields, str):
            raise ValueError(f'must be str:{self.fields}')
        for _ in self.fields.split(','):
            words = [x.strip() for x in _.strip().split(' ')]
            if len(words) == 1:
                yield words[0]
            elif len(words) == 3 and words[1] == 'as':
                yield words[2]
            else:
                raise ValueError(f'cannot parse {_} out of {self.fields}, words={words}')

    def tuples(self) -> List[Any]:
        """named tuples for query records"""
        tupleclass = namedtuple(self.__tupleName(), self.tuplefields)  # type: ignore
        return [tupleclass._make(x) for x in self.records]

    def tuple(self) -> Any:
        """Valid only for queries returning exactly one record"""
        if not self.fields:
            raise ValueError
        if len(self.records) != 1:
            raise ValueError(f'{self!r} did not return exactly 1 record but {len(self.records)}')
        tupleclass = namedtuple('Fields', self.tuplefields)  # type: ignore
        return tupleclass._make(self.records[0])

    def record(self) -> Any:
        """Valid only for queries returning exactly one record"""
        if len(self.records) != 1:
            raise ValueError(f'{self!r} did not return exactly 1 record but {len(self.records)}')
        return self.records[0]

    def __str__(self) ->str:
        return f"{Internal.db!r}:{self.statement} {'args=' + ','.join(str(x) for x in self.args) if self.args else ''}"

    def rowcount(self) ->int:
        """how many rows were affected?"""
        return self.cursor.rowcount if self.cursor else 0

    def map(self, namedTuple) ->Optional[List[Any]]:  # FIXME: remove again
        """A list of namedtuple"""
        if self.records is None:
            return None
        return [namedTuple._make(x) for x in self.records]

    def column(self, idx:int) -> List[Any]:
        """A list with only that column"""
        return [x[idx] for x in self.records]

def initDb() ->bool:
    """open the db, create or update it if needed.
    sets Internal.db."""
    PrepareDB(DBHandle.dbPath())  # create or upgrade
    DBHandle(DBHandle.dbPath())
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
            prevailing wind,
            wind wind,
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
            allVersions = list(['4.13.0', '8300', '8301', '8302', '8303'])
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

    def updateToVersion8302(self) ->None:
        """seed now is 0 instead of Null"""
        Query('UPDATE game SET seed=0 WHERE seed IS NULL', silent=True)

    def __needs_type_wind(self) ->bool:
        """helper for updating to 8303"""
        rows = Query("PRAGMA table_info('score')").records
        for row in rows:
            name = row[1]
            typ = row[2]
            if name == 'wind' and typ != 'wind':
                logInfo(f'score.wind has not yet type wind: {typ}')
                return True
            if name == 'prevailing' and typ != 'wind':
                logInfo(f'score.prevailing has not yet type wind: {typ}')
                return True
        return False

    def updateToVersion8303(self) ->None:
        """new type 'wind'"""
        if self.__needs_type_wind():
            with Internal.db:
                Query('ALTER TABLE score add prevailingw wind', mayFail=True)
                Query('ALTER TABLE score add windw wind', mayFail=True)
                Query('UPDATE score set prevailingw = prevailing, windw=wind')
                Query('ALTER TABLE score drop prevailing')
                Query('ALTER TABLE score drop wind')
                Query('ALTER TABLE score rename windw to wind')
                Query('ALTER TABLE score rename prevailingw to prevailing')

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
