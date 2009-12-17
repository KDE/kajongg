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
from twisted.internet import error
from twisted.internet.defer import Deferred, maybeDeferred, DeferredList
from zope.interface import implements
from twisted.cred import checkers,  portal, credentials, error as credError
import random
from PyKDE4.kdecore import KCmdLineArgs
from PyKDE4.kdeui import KApplication
from about import About
from game import RemoteGame, Players,  Player, RobotPlayer
from query import Query,  InitDb
import predefined  # make predefined rulesets known
from scoringengine import Ruleset,  PredefinedRuleset
from util import m18n, m18nE,  SERVERMARK, WINDS

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
        defer1 = maybeDeferred(cred.checkPassword,  password)
        defer1.addCallback(self._checkedPassword,  userid)
        return defer1

    def _checkedPassword(self, matched, userid):
        if not matched:
            raise srvError(credError.UnauthorizedLogin, m18nE('Wrong username or password'))
        return userid

class Table(object):
    TableId = 0
    def __init__(self,  server, owner):
        self.server = server
        self.owner = owner
        self.owningPlayer = None
        Table.TableId = Table.TableId + 1
        self.tableid = Table.TableId
        self.users = [owner]
        self.game = None
        self.pendingDeferreds = []

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
    def __repr__(self):
        return str(self.tableid) + ':' + ','.join(x.name for x in self.users)
    def broadcast(self, *args):
        for player in self.game.humanPlayers():
            self.server.callRemote(player.client, *args)

    def robot(self, user, other, about, command, **kwargs):
        print 'robot: other:', other, 'about:', about, 'command:', command
        print 'kwargs:', kwargs
        if command == 'setTiles':
            if other == about:
                other.tiles = kwargs['source']
        elif command == 'firstMove':
            if other == about:
                for tile in other.tiles:
                    print 'robot,firstmove: try to discard', tile
                    if tile[0] not in 'fy':
                        # do not remove tile from hand here, the server will tell all players
                        # including us that it has been discarded. Only then we will remove it.
                        return 'discard', tile

    def sendMove(self, other, about, command, **kwargs):
        if isinstance(other, RobotPlayer):
            defer = Deferred()
            print 'send move to robot'
            defer.addCallback(self.robot, other, about, command,  **kwargs)
            defer.callback(self)
        else:
            defer = self.server.callRemote(other.client, 'move', self.tableid, about.name, command, kwargs)
        self.pendingDeferreds.append((defer, other))

    def tellPlayer(self, player,  command,  **kwargs):
        """send move. If user is given, only to user. Otherwise to all humans."""
        self.sendMove(player, player, command, **kwargs)

    def tellOthers(self, player, command, **kwargs):
        for other in self.game.players:
            if other != player:
                self.sendMove(other, player, command, **kwargs)

    def tellAll(self, player, command, **kwargs):
        for other in self.game.players:
            self.sendMove(other, player, command, **kwargs)

    def ready(self, user):
        if len(self.users) < 4 and self.owner != user:
            raise srvError(pb.Error, m18nE('Only the initiator %1 can start this game'), self.owner.name)
        rulesets = Ruleset.availableRulesets() + PredefinedRuleset.rulesets()
        names = list(x.name for x in self.users)
        while len(names) < 4:
            names.append('ROBOT'+str(4 - len(names))) # TODO: constants for ROBOT and SERVER
        self.game = RemoteGame('SERVER', names,  rulesets[0])
        for player, user in zip(self.game.players, self.users):
            player.client = user
            if user == self.owner:
                self.owningPlayer = player
        random.shuffle(self.game.players)
        for player,  wind in zip(self.game.players, WINDS):
            player.wind = wind
        self.game.deal()
        # send the names for players E,S,W,N in that order:
        self.broadcast('readyForStart', self.tableid, '//'.join(x.name for x in self.game.players))

    def allPlayersReady(self):
        for player in self.game.players:
            if not isinstance(player, RobotPlayer) and not player.client.ready:
                return False
        return True

    def start(self):
        assert not self.pendingDeferreds
        self.tellAll(self.owningPlayer, 'setDiceSum', source=self.game.diceSum)
        for player in self.game.players:
            self.tellPlayer(player,'setTiles', source=player.tiles)
            count = 14 if player.wind == 'E' else 13
            boni = ' '.join(x for x in player.tiles if x[0] in 'fy')
            self.tellOthers(player, 'setTiles', source='XY'*count+boni)
        self.waitAndCall(self.dealt)

    def waitAndCall(self, callback):
        """after all pending deferreds have returned, process them"""
        d = DeferredList([x[0] for x in self.pendingDeferreds], consumeErrors=True)
        d.addCallback(self.clearPending, callback)

    def clearPending(self, results, callback):
        """all pending deferreds have returned. Augment the result list with the
        corresponding players, clear the pending list and exec the given callback"""
        augmented = []
        for pair, other in zip(results, self.pendingDeferreds):
            augmented.append((other[1], pair[1]))
        pendings = self.pendingDeferreds
        self.pendingDeferreds = []
        ok = True
        for result, pendings in zip(results, pendings):
            if not result[0]:
                message = 'ERROR in table %d: %s' % (self.tableid, result[1].getErrorMessage())
                self.tellAll(pendings[1], 'error', source=message)
                ok = False
        if not ok:
            self.server.abortTable(self)
        else:
            callback(augmented)

    def dealt(self, results):
        """all tiles are dealt, ask east to discard a tile"""
        self.currentPlayer = self.game.players[0]
        self.tellAll(self.currentPlayer, 'firstMove')
        self.waitAndCall(self.moved)

    def moved(self, results):
        """a player did something"""
        print 'moved', results
        for result in results:
            player, args = result
            if args:
                answer = args[0]
                args = args[1:]
                if answer == 'discard':
                    tile = args[0]
                    if tile not in player.tiles:
                        raise Exception('player %s discarded %s but does not have it' % (player, tile))
                    player.tiles.remove(tile)
                    self.tellAll(player, 'hasDiscarded', tile=tile)
                    self.waitAndCall(self.moved)



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
                print args
                return user.remote.callRemote(*args)
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
        if not table.users:
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

    def abortTable(self, table):
        print 'aborting table'
        for user in table.users:
            table.delUser(user)
        self.broadcast('abort', table.tableid)
        del self.tables[table.tableid]
        self.broadcastTables()

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
    try:
        reactor.listenTCP(8082, pb.PBServerFactory(portal))
    except error.CannotListenError as e:
        print e
    else:
        reactor.run()
