#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2009 Wolfgang Rohdewald <wolfgang@rohdewald.de>

kmj is free software you can redistribute it and/or modify
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

The DBPasswordChecker is based on an example from the book
Twisted Network Programming Essentials by Abe Fettig. Copyright 2006
O'Reilly Media, Inc., ISBN 0-596-10032-9
"""
from twisted.spread import pb
from twisted.internet import defer
from zope.interface import implements
from twisted.cred import checkers,  portal, credentials, error as credError
import random
from PyKDE4.kdecore import KCmdLineArgs
from PyKDE4.kdeui import KApplication
from about import About
from game import Game, Players,  Player
from query import Query,  InitDb
import predefined  # make predefined rulesets known
from scoringengine import Ruleset,  PredefinedRuleset
from util import m18n, m18nE,  SERVERMARK

TABLEID = 0

def srvError(cls, *args):
    """send all args needed for m18n encoded in one string.
    For an explanation see util.translateServerString"""
    raise cls(SERVERMARK+SERVERMARK.join(list([str(x) for x in args])))

class DBPasswordChecker(object):
    """checks against our sqlite3 databases"""
    implements(checkers.ICredentialsChecker)
    credentialInterfaces = (credentials.IUsernamePassword,
                            credentials.IUsernameHashedPassword)

    def requestAvatarId(self, cred):
        """get user id from data base"""
        query = Query(['select id, password from player where name="%s"' % \
                       cred.username])
        if not len(query.data):
            raise srvError(credError.UnauthorizedLogin, m18nE('Wrong username or password'))
        userid,  password = query.data[0]
        defer1 = defer.maybeDeferred(cred.checkPassword,  password)
        defer1.addCallback(self._checkedPassword,  userid)
        return defer1

    def _checkedPassword(self, matched, userid):
        if not matched:
            raise srvError(credError.UnauthorizedLogin, m18nE('Wrong username or password'))
        return userid

class RobotUser(object):
    def __init__(self,  number):
        self.name = m18n('Computer player <numid>%1</numid>', number)
        self.remote = None
        self.idx4 = None
        self.tiles = None

class Table(object):
    TableId = 0
    def __init__(self,  server, owner):
        self.server = server
        self.owner = owner
        Table.TableId = Table.TableId + 1
        self.tableid = Table.TableId
        self.users = [owner]
        self.game = None
    def addUser(self,  user):
        if user.name in list(x.name for x in self.users):
            raise srvError(pb.Error, m18nE('You already joined this table'))
        if len(self.users) == 4:
            raise srvError(pb.Error, m18nE('All seats are already taken'))
        self.users.append(user)
        if len(self.users) == 4:
            self.ready()

    def delUser(self,  user):
        if user in self.users:
            self.users.remove(user)
            if user is self.owner:
                self.owner = user
    def humanUsers(self):
        return filter(lambda x: not isinstance(x, RobotUser), self.users)
    def __repr__(self):
        return str(self.tableid) + ':' + ','.join(x.name for x in self.users)
    def broadcast(self, *args):
        for user in self.humanUsers():
            self.server.callRemote(user, *args)

    def sendMove(self, user,  command,  **args):
        """send move. If user is given, only to user. Otherwise to all humans."""
        if user in self.humanUsers():
            self.server.callRemote(user, 'move', self.tableid, user.name, command, args)

    def broadcastMove(self, fromUser, command, **args):
        for user in self.humanUsers():
            self.server.callRemote(user, 'move', self.tableid, fromUser.name, command, args)

    def ready(self, user):
        if len(self.users) < 4 and self.owner != user:
            raise srvError(pb.Error, m18nE('Only the initiator %1 can start this game'), self.owner.name)
        while len(self.users) < 4:
            self.users.append(RobotUser(4 - len(self.users)))
        self.broadcast('readyForStart', self.tableid, '//'.join(x.name for x in self.users))

    def allPlayersReady(self):
        for user in self.users:
            if not isinstance(user, RobotUser) and not user.ready:
                return False
        return True

    def start(self):
        random.shuffle(self.users)
        players = Players([Player() for idx in range(4)])
        winds = list(['E', 'S',  'W',  'N'])
        random.shuffle(winds)
        for idx,  player in enumerate(players):
            player.idx4 = idx
            player.host = 'SERVER'
            player.name = self.users[idx].name
            Players.createIfUnknown('SERVER', player.name)
            self.users[idx].player = player
            player.wind = winds[idx]
        rulesets = Ruleset.availableRulesets() + PredefinedRuleset.rulesets()
        self.game = Game(players,  ruleset=rulesets[0])
        self.broadcastMove(self.owner, 'setDiceSum', source=self.game.diceSum)
        for idx, user in enumerate(self.users):
            self.broadcastMove(user, 'setWind', source=user.player.wind)
            self.sendMove(user,'setTiles', source=''.join(player.tiles))

class MJServer(object):
    """the real mah jongg server"""
    def __init__(self):
        self.tables = {}
        self.users = list()
        Players.load()
    def login(self, user):
        """accept a new user and send him the current table list"""
        if not user in self.users:
            self.users.append(user)
            # send current tables only to new user
            self.callRemote(user, 'tablesChanged', self.tableMsg())

    def callRemote(self, user, *args):
        """if we still have a connection, call remote, otherwise clean up"""
        if user.remote:
            try:
                user.remote.callRemote(*args)
            except pb.DeadReferenceError:
                user.remote = None
                self.logout(user)

    def broadcast(self, *args):
        """call remote function for all users of this server"""
        for user in self.users:
            self.callRemote(user, *args)

    def tableMsg(self):
        """build a message containing table info"""
        msg = list()
        for table in self.tables.values():
            msg.append(tuple([table.tableid, tuple(x.name for x in table.users)]))
        return msg

    def broadcastTables(self):
        """tell all users about changed tables"""
        self.broadcast('tablesChanged', self.tableMsg())

    def _lookupTable(self, tableid):
        """return table by id or raise exception"""
        if tableid not in self.tables:
            raise srvError(pb.Error, m18nE('table with id <numid>%1</numid> not found'),  tableid)
        return self.tables[tableid]

    def newTable(self, user):
        """user creates new table and joins it"""
        table = Table(self, user)
        self.tables[table.tableid] = table
        self.broadcastTables()
        return table.tableid

    def joinTable(self, user, tableid):
        """user joins table"""
        self._lookupTable(tableid).addUser(user)
        self.broadcastTables()
        return True

    def leaveTable(self, user, tableid):
        """user leaves table. If no human user is left on table, delete it"""
        table = self._lookupTable(tableid)
        table.delUser(user)
        if not table.humanUsers():
            del self.tables[tableid]
        self.broadcastTables()
        return True

    def startGame(self, user, tableid):
        """try to start the game"""
        return self._lookupTable(tableid).ready(user)

    def ready(self, user, tableid):
        user.ready = True
        table = self._lookupTable(tableid)
        if table.allPlayersReady():
            table.start()

    def logout(self, user):
        """remove user from all tables"""
        if user in self.users:
            self.callRemote(user,'serverDisconnects')
            for table in self.tables.values():
                if user in table.users:
                    self.leaveTable(user, table.tableid)
            if user in self.users: # recursion possible: a disconnect error calls logout
                self.users.remove(user)

class User(pb.Avatar):
    def __init__(self, userid):
        self.userid = userid
        self.name = Query(['select name from player where id=%s' % userid]).data[0][0]
        self.isReady = False
        self.remote = None
        self.server = None
        self.readyForStart = False
    def attached(self, mind):
        self.remote = mind
        self.server.login(self)
    def detached(self, mind):
        self.server.logout(self)
        self.remote = None
        self.readyForStart = False
    def perspective_joinTable(self, tableid):
        return self.server.joinTable(self, tableid)
    def perspective_leaveTable(self, tableid):
        return self.server.leaveTable(self, tableid)
    def perspective_newTable(self):
        return self.server.newTable(self)
    def perspective_startGame(self, tableid):
        return self.server.startGame(self, tableid)
    def perspective_ready(self, tableid):
        return self.server.ready(self, tableid)
    def perspective_logout(self):
        self.server.logout(self)
        self.remote = None

class MJRealm(object):
    implements(portal.IRealm)

    def requestAvatar(self, avatarId, mind, *interfaces):
        if not pb.IPerspective in interfaces:
            raise NotImplementedError,  "No supported avatar interface"
        avatar = User(avatarId)
        avatar.server = self.server
        avatar.attached(mind)
        return pb.IPerspective,  avatar,  lambda a = avatar:a.detached(mind)

if __name__ == '__main__':
    import sys
    from twisted.internet import reactor
    ABOUT = About()
    KCmdLineArgs.init (sys.argv, ABOUT.about)
    APP = KApplication()
    InitDb()
    realm = MJRealm()
    realm.server = MJServer()
    portal = portal.Portal(realm, [DBPasswordChecker()])
    reactor.listenTCP(8082, pb.PBServerFactory(portal))
    reactor.run()
