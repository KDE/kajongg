#!/usr/bin/env python
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


"""the player table has those fields:

host, name, password

host: is empty for names used in manual games, scoring only.

host contains the name of a remote game server for remote games. This
can also be localhost.

host contains Query.serverName: Those entries are to be used only by the game server.
If the game server and the client both run on the same data base, the client
must ignore those entries.

the combination server, name must be unique.

the password is used by the client for login and by the server for authentication.
The server will accept only names which are stored with host=Query.serverName.

"""

import os
from PyQt4.QtCore import QVariant
from util import logMessage, debugMessage, InternalParameters
from syslog import LOG_ERR
from PyQt4.QtSql import QSqlQuery,  QSqlDatabase
from PyKDE4.kdecore import KGlobal

class Query(object):
    """a more pythonic interface to QSqlQuery. We could instead use
    the python sqlite3 module but then we would either have to do
    more programming for the model/view tables, or we would have
    two connections to the same database.
    For selecting queries we read ALL records into a list of records.
    Every record is a list of all fields. q.data[0][1] is row 0, field 1.
    For select, we also convert to python data
    types - as far as we need them"""
    dbhandle = None
    lastError = None

    serverName = 'KMJSERKMJVERKMJ'     # this should be something that is not used
                                                                    # for a real server
    def __init__(self, cmdList, args=None):
        """we take a list of sql statements. Only the last one is allowed to be
        a select statement.
        Do prepared queries by passing a single query statement in cmdList
        and the parameters in args. If args is a list of lists, execute the
       prepared query for every sublist """
        preparedQuery = not isinstance(cmdList, list) and bool(args)
        self.query = QSqlQuery(Query.dbhandle)
        self.msg = None
        self.data = []
        if  not isinstance(cmdList, list):
            cmdList = list([cmdList])
        self.cmdList = cmdList
        for cmd in cmdList:
            if preparedQuery:
                self.query.prepare(cmd)
                if not isinstance(args[0], list):
                    args = list([args])
                for dataSet in args:
                    if InternalParameters.showSql:
                        debugMessage('%s %s' % (cmd, dataSet))
                    for value in dataSet:
                        self.query.addBindValue(QVariant(value))
                    self.success = self.query.exec_()
                    if not self.success:
                        break
            else:
                if InternalParameters.showSql:
                    debugMessage(cmd)
                self.success = self.query.exec_(cmd)
            if not self.success:
                Query.lastError = unicode(self.query.lastError().text())
                self.msg = 'ERROR: %s' % Query.lastError
                logMessage(self.msg, prio=LOG_ERR)
                return
        if self.query.isSelect():
            self.data = []
            record = self.query.record()
            qFields = [record.field(x) for x in range(record.count())]
            while self.query.next():
                reclist = [None] * len(qFields)
                for idx in range(len(qFields)):
                    name = str(qFields[idx].name())
                    valType = qFields[idx].type()
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
                        raise Exception('Query: variant type not implemented for field %s ' % name)
                    reclist[idx] = value
                self.data.append(reclist)
        else:
            self.data = None

    @staticmethod
    def tableHasField(table, field):
        query = QSqlQuery(Query.dbhandle)
        query.exec_('select * from %s' % table)
        if query.first():
            record = query.record()
            for idx in range(record.count()):
                if record.fieldName(idx) == field:
                    return True

    @staticmethod
    def createTables():
        """creates empty tables"""
        Query(["""CREATE TABLE player (
            id INTEGER PRIMARY KEY,
            host TEXT,
            name TEXT,
            password TEXT,
            unique(host, name))""",
        """CREATE TABLE game (
            id integer primary key,
            seed text,
            starttime text default current_timestamp,
            endtime text,
            server text,
            ruleset integer references usedruleset(id),
            p0 integer constraint fk_p0 references player(id),
            p1 integer constraint fk_p1 references player(id),
            p2 integer constraint fk_p2 references player(id),
            p3 integer constraint fk_p3 references player(id))""",
        """CREATE TABLE score(
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
            balance integer)""",
        """CREATE TABLE ruleset(
            id integer primary key,
            name text unique,
            hash text,
            lastused text,
            description text)""",
        """CREATE TABLE rule(
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
            unique (ruleset,name))""",
        """CREATE TABLE usedruleset(
            id integer primary key,
            name text,
            hash text,
            lastused text,
            description text)""",
        """CREATE TABLE server(
            url text,
            lastname text,
            lasttime text,
            primary key(url))""",
        """CREATE TABLE usedrule(
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
            unique (ruleset,name))"""])

    @staticmethod
    def addTestData():
        """adds test data to an empty data base"""
        # test players for manual scoring:
        Query('insert into player(name) values(?)',
              [list([x]) for x in ['Wolfgang',  'Petra',  'Klaus',  'Heide']])

        # test players for remote games:
        for host in ['localhost', Query.serverName]:
            Query('insert into player(host,name,password) values(?,?,?)',
                [list([host, x, x]) for x in ['guest 1', 'guest 2', 'guest 3', 'guest 4']])

        # default for login to the game server:
        Query(['insert into server(url,lastname) values("localhost","guest 1")'])

def InitDb():
    Query.dbhandle = QSqlDatabase("QSQLITE")
    dbpath = KGlobal.dirs().locateLocal("appdata","kajongg.db")
    Query.dbhandle.setDatabaseName(dbpath)
    dbExisted = os.path.exists(dbpath)
    if not Query.dbhandle.open():
        logMessage(Query.dbhandle.lastError().text())
        sys.exit(1)
    if not dbExisted:
        Query.createTables()
        Query.addTestData()
