#!/usr/bin/env python
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
from scoringengine import Ruleset,  PredefinedRuleset
from util import m18n

TABLEID = 0

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
            raise credError.UnauthorizedLogin(m18n('Wrong username or password'))
        userid,  password = query.data[0]
        defer1 = defer.maybeDeferred(cred.checkPassword,  password)
        defer1.addCallback(self._checkedPassword,  userid)
        return defer1

    def _checkedPassword(self, matched, userid):
        if not matched:
            raise credError.UnauthorizedLogin(m18n('Wrong username or password'))
        return userid

class RobotUser(object):
    def __init__(self,  number):
        self.name = m18n('Computer player <numid>%1</numid>', number)
        self.remote = None

class Table(object):
    TableId = 0
    def __init__(self,  owner):
        self.owner = owner
        Table.TableId = Table.TableId + 1
        self.tableid = Table.TableId
        self.users = [owner]
        self.game = None
    def addUser(self,  user):
        if user in self.users:
            raise pb.Error(m18n('You already joined this table'))
        if len(self.users) == 4:
            raise pb.Error(m18n('All seats are already taken'))
        self.users.append(user)
        if len(self.users) == 4:
            self.start()

    def delUser(self,  user):
        if user in self.users:
            self.users.remove(user)
            if user is self.owner:
                self.owner = user
    def humanUsers(self):
        result = 0
        for user in self.users:
            if not isinstance(user, RobotUser):
                result += 1
        return result
    def __repr__(self):
        return str(self.tableid) + ':' + ','.join(x.name for x in self.users)
    def start(self, user):
        if len(self.users) < 4 and self.owner != user:
            raise pb.Error(m18n('Only the initiator %1 can start this game', self.owner.name))
        while len(self.users) < 4:
            self.users.append(RobotUser(4 - len(self.users)))
        random.shuffle(self.users)
        players = Players([Player() for idx in range(4)])
        winds = list(['E', 'S',  'W',  'N'])
        random.shuffle(winds)
        for idx,  player in enumerate(players):
            player.name = self.users[idx].name
            self.users[idx].player = player
            player.wind = winds[idx]
        rulesets = Ruleset.availableRulesets() + PredefinedRuleset.rulesets()
        self.game = Game(players,  ruleset=rulesets[0])
#        nextPlayer = 'E'
 #       for user in self.users:
   #         if user.remote:
   #             user.remote.callRemote('print', 'Message to'+user.name+'E starting')

class MJServer(object):
    def __init__(self):
        self.tables = list()
        self.users = list()
        Players.load()
    def login(self, user):
        if not user in self.users:
            self.users.append(user)
            # send current tables only to new user
            self.callRemote(user, 'tablesChanged', self.tableMsg())
    def callRemote(self, user, *args):
        if user.remote:
            try:
                user.remote.callRemote(*args)
            except pb.DeadReferenceError:
                user.remote = None
                self.logout(user)

    def broadcast(self, *args):
        for user in self.users:
            self.callRemote(user, *args)
    def tableMsg(self):
        msg = list()
        for table in self.tables:
            msg.append(tuple([table.tableid, tuple(x.name for x in table.users)]))
        return msg
    def broadcastTables(self):
        self.broadcast('tablesChanged', self.tableMsg())
    def newTable(self, user):
        table = Table(user)
        self.tables.append(table)
        self.broadcastTables()
        return table.tableid
    def deleteTable(self, user, tableid):
        for table in self.tables:
            if table.tableid == tableid:
                if table.owner != user:
                    raise pb.Error(m18n('Only the initiator %1 can delete a table', table.owner.name))
                self.tables.remove(table)
                self.broadcastTables()
                return True
        raise pb.Error(m18n('table with id <numid>%1</numid> not found',  tableid))
    def joinTable(self, user, tableid):
        for table in self.tables:
            if table.tableid == tableid:
                table.addUser(user)
                self.broadcastTables()
                return True
        raise pb.Error('table with id %d not found' % tableid)
    def leaveTable(self, user, tableid):
        for table in self.tables:
            if table.tableid == tableid:
                table.delUser(user)
                if not table.humanUsers():
                    self.tables.remove(table)
                self.broadcastTables()
                return True
        raise pb.Error('table with id %d not found' % tableid)
    def logout(self, user):
        """remove user from all tables"""
        if user in self.users:
            self.callRemote(user,'serverDisconnects')
            for table in self.tables:
                if user in table.users:
                    self.leaveTable(user, table.tableid)
            if user in self.users: # needed because a disconnect error also calls logout
                self.users.remove(user)

class User(pb.Avatar):
    def __init__(self, userid):
        self.userid = userid
        self.name = Query(['select name from player where id=%s' % userid]).data[0][0]
        self.isReady = False
        self.remote = None
        self.server = None
    def attached(self, mind):
        self.remote = mind
        self.server.login(self)
    def detached(self, mind):
        self.server.logout(self)
        self.remote = None
    def perspective_joinTable(self, tableid):
        self.server.joinTable(self, tableid)
    def perspective_leaveTable(self, tableid):
        self.server.leaveTable(self, tableid)
    def perspective_newTable(self):
        return self.server.newTable(self)
    def perspective_deleteTable(self, tableid):
        return self.server.deleteTable(self, tableid)

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
