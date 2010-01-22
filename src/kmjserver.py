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

import inspect, syslog

from twisted.spread import pb
from twisted.internet import error
from twisted.internet.defer import Deferred, maybeDeferred, DeferredList
from zope.interface import implements
from twisted.cred import checkers,  portal, credentials, error as credError
import random
from PyKDE4.kdecore import KCmdLineArgs, KCmdLineOptions, ki18n
from PyKDE4.kdeui import KApplication
from about import About
from game import RemoteGame, Players, WallEmpty
from client import Client
from query import Query,  InitDb
import predefined  # make predefined rulesets known
from scoringengine import Ruleset,  PredefinedRuleset, Pairs, Meld, \
    PAIR, PUNG, KONG, CHOW
import util
from util import m18n, m18nE, m18ncE, SERVERMARK, WINDS, syslogMessage
from config import Preferences,InternalParameters

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
        query = Query('select id, password from player where host=? and name=?',
            list([Query.serverName, cred.username]))
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
        self.preparedGame= None
        self.game = None
        self.pendingDeferreds = []

    def addUser(self,  user):
        if user.name in list(x.name for x in self.users):
            raise srvError(pb.Error, m18nE('You already joined this table'))
        if len(self.users) == 4:
            raise srvError(pb.Error, m18nE('All seats are already taken'))
        self.users.append(user)
        if len(self.users) == 4:
            self.readyForGameStart()

    def delUser(self,  user):
        if user in self.users:
            self.game = None
            self.users.remove(user)
            if user is self.owner:
                # silently pass ownership
                if self.users:
                    self.owner = self.users[0]

    def __repr__(self):
        return str(self.tableid) + ':' + ','.join(x.name for x in self.users)

    def sendMove(self, other, about, command, **kwargs):
        if util.PREF.debugTraffic:
            print 'SERVER to %s about %s:' % (other, about), command, kwargs
        if isinstance(other.remote, Client):
            defer = Deferred()
            defer.addCallback(other.remote.remote_move, about.name, command, **kwargs)
            defer.callback(self.tableid)
        else:
            defer = self.server.callRemote(other.remote, 'move', self.tableid, about.name, command, **kwargs)
        if defer:
            # the remote player might already be disconnected
            self.pendingDeferreds.append((defer, other))

    def tellPlayer(self, player,  command,  **kwargs):
        self.sendMove(player, player, command, **kwargs)

    def tellOthers(self, player, command, **kwargs):
        for other in self.game.players:
            if other != player:
                self.sendMove(other, player, command, **kwargs)

    def tellAll(self, player, command, **kwargs):
        for other in self.game.players:
            self.sendMove(other, player, command, **kwargs)

    def readyForGameStart(self, user):
        if len(self.users) < 4 and self.owner != user:
            raise srvError(pb.Error, m18nE('Only the initiator %1 can start this game, you are %2'), self.owner.name, user.name)
        rulesets = Ruleset.availableRulesets() + PredefinedRuleset.rulesets()
        names = list(x.name for x in self.users)
        # the server and all databases save the english name but we
        # want to make sure a translation exists for the client GUI
        robotNames = [
            m18ncE('kmj', 'ROBOT 1'),
            m18ncE('kmj', 'ROBOT 2'),
            m18ncE('kmj', 'ROBOT 3')]
        while len(names) < 4:
            names.append(robotNames[3 - len(names)])
        game = RemoteGame(names,  rulesets[0], client=Client())
        self.preparedGame = game
        for player, user in zip(game.players, self.users):
            player.remote = user
            if user == self.owner:
                self.owningPlayer = player
        for player in game.players:
            if not player.remote:
                player.remote = Client(player.name)
                player.remote.table = self
        random.shuffle(game.players)
        for player,  wind in zip(game.players, WINDS):
            player.wind = wind
        # send the names for players E,S,W,N in that order:
        # for each database, only one Game instance should save.
        dbPaths = ['127.0.0.1:' + Query.dbhandle.databaseName()]
        for player in game.players:
            if isinstance(player.remote, User):
                peer = player.remote.mind.broker.transport.getPeer()
                path = peer.host + ':' + player.remote.dbPath
                shouldSave = path not in dbPaths
                if shouldSave:
                    dbPaths.append(path)
            else:
                shouldSave=False
            self.tellPlayer(player, 'readyForGameStart', shouldSave=shouldSave, seed=game.seed, source='//'.join(x.name for x in game.players))
        self.waitAndCall(self.startGame)

    def startGame(self, results):
        for result in results:
            player, args = result
            if args == False:
                # this player answered "I am not ready", exclude her from table
                self.server.leaveTable(player.remote, self.tableid)
                self.preparedGame = None
                return
        self.game = self.preparedGame
        self.preparedGame = None
        # if the players on this table also reserved seats on other tables,
        # clear them
        for user in self.users:
            for tableid in self.server.tables.keys()[:]:
                if tableid != self.tableid:
                    self.server.leaveTable(user, tableid)
        self.startHand()

    def waitAndCall(self, callback, *args, **kwargs):
        """after all pending deferreds have returned, process them"""
        d = DeferredList([x[0] for x in self.pendingDeferreds], consumeErrors=True)
        d.addBoth(self.clearPending, callback, *args, **kwargs)

    def claim(self, username, claim):
        """who claimed something. Show that claim at once everywhere
        without waiting for all players to answer"""
        player = self.game.players.byName(username)
        pendingDeferreds = self.pendingDeferreds
        self.pendingDeferreds = []
        self.tellAll(player,'popupMsg', msg=claim)
        self.pendingDeferreds = pendingDeferreds

    def clearPending(self, results, callback, *args, **kwargs):
        """all pending deferreds have returned. Augment the result list with the
        corresponding players, clear the pending list and exec the given callback"""
        pendings = self.pendingDeferreds
        self.pendingDeferreds = []
        augmented = []
        for pair, other in zip(results, pendings):
            player = other[1]
            if pair[0]:
                augmented.append((player, pair[1]))
            else:
                failure = pair[1]
                if failure.type in  [pb.PBConnectionLost]:
                    msg = m18nE('The game server lost connection to player %1')
                    self.abort(msg, player.name)
                else:
                    msg = m18nE('Unknown error for player %1: %2\n%3')
                    self.abort(msg, player.name, failure.getErrorMessage(), failure.getTraceback())
                return
        if self.game or self.preparedGame:
            # both are None if a player left the table meanwhile
            callback(augmented, *args, **kwargs)

    def pickTile(self, results=None, deadEnd=False):
        """the active player gets a tile from wall. Tell all clients."""
        player = self.game.activePlayer
        try:
            pickTile = self.game.wall.dealTo(deadEnd=deadEnd)[0]
            self.game.pickedTile(player, pickTile, deadEnd)
        except WallEmpty:
            self.waitAndCall(self.endHand)
        else:
            self.tellPlayer(player, 'pickedTile', source=pickTile, deadEnd=deadEnd)
            if pickTile[0] in 'fy':
                self.tellOthers(player, 'pickedTile', source=pickTile, deadEnd=deadEnd)
            else:
                self.tellOthers(player, 'pickedTile', source= 'Xy', deadEnd=deadEnd)
            self.waitAndCall(self.moved)

    def pickDeadEndTile(self, results=None):
        self.pickTile(results, deadEnd=True)

    def startHand(self, results=None):
        self.game.prepareHand()
        self.game.deal()
        self.tellAll(self.owningPlayer, 'initHand',
            divideAt=self.game.divideAt)
        for player in self.game.players:
            self.tellPlayer(player, 'setTiles', source=player.concealedTiles + player.bonusTiles)
            self.tellOthers(player, 'setTiles', source= ['Xy']*13+player.bonusTiles)
        self.waitAndCall(self.dealt)

    def endHand(self, results):
        for player in self.game.players:
            self.tellOthers(player, 'showTiles', source=player.concealedTiles)
        self.waitAndCall(self.saveHand)

    def saveHand(self, results):
        self.game.saveHand()
        self.tellAll(self.owningPlayer, 'saveHand')
        self.waitAndCall(self.nextHand)

    def nextHand(self, results):
        rotate = self.game.maybeRotateWinds()
        if self.game.finished():
            self.abort(m18nE('The game is over!'))
            return
        self.game.sortPlayers()
        playerNames = '//'.join(self.game.players[x].name for x in WINDS)
        self.tellAll(self.owningPlayer, 'readyForHandStart', source=playerNames,
          rotate=rotate)
        self.waitAndCall(self.startHand)

    def abort(self, message, *args):
        self.server.abortTable(self, message, *args)

    def claimTile(self, player, claim, meldTiles,  nextMessage):
        """a player claims a tile for pung, kong, chow or Mah Jongg.
        meldTiles contains the claimed tile, concealed"""
        claimedTile = player.game.lastDiscard
        if claimedTile not in meldTiles:
            msg = m18nE('Tile %1 discarded by %2 is not in meld %3')
            self.abort(msg, str(claimedTile), player.name, ''.join(meldTiles))
            return
        meld = Meld(meldTiles)
        concKong =  len(meldTiles) == 4 and meldTiles[0][0].isupper() and meldTiles == [meldTiles[0]]*4
        # this is a concealed kong with 4 concealed tiles, will be changed to x#X#X#x#
        # by exposeMeld()
        if not concKong and meld.meldType not in [PAIR, PUNG, KONG, CHOW]:
            msg = m18nE('%1 wrongly said %2 for meld %3')
            self.abort(msg, player.name, m18n(claim), str(meld))
            return
        checkTiles = meldTiles[:]
        checkTiles.remove(claimedTile)
        if not player.hasConcealedTiles(checkTiles):
            msg = m18nE('%1 wrongly said %2: claims to have concealed tiles %3 but only has %4')
            self.abort(msg, player.name, m18n(claim), ''.join(checkTiles), ''.join(player.concealedTiles))
            return
        self.game.activePlayer = player
        player.addTile(claimedTile)
        player.lastTile = claimedTile.lower()
        player.lastSource = 'd'
        player.exposeMeld(meldTiles)
        self.tellAll(player, nextMessage, source=meldTiles)
        if claim == 'Kong':
            self.waitAndCall(self.pickDeadEndTile)
        else:
            self.waitAndCall(self.moved)

    def declareKong(self, player, meldTiles):
        """player declares a Kong, meldTiles is a list"""
        if not player.hasConcealedTiles(meldTiles) and not player.hasExposedPungOf(meldTiles[0]):
            msg = m18nE('declareKong:%1 wrongly said Kong for meld %2')
            args = (player.name, ''.join(meldTiles))
            syslogMessage(m18n(msg, *args), syslog.LOG_ERR)
            syslogMessage('declareKong:concealedTiles:%s' % ''.join(player.concealedTiles), syslog.LOG_ERR)
            syslogMessage('declareKong:concealedMelds:%s' % ' '.join(x.joined for x in player.concealedMelds), syslog.LOG_ERR)
            syslogMessage('declareKong:exposedMelds:%s' % ' '.join(x.joined for x in player.exposedMelds), syslog.LOG_ERR)
            self.abort(msg, *args)
            return
        player.exposeMeld(meldTiles, claimed=False)
        self.tellAll(player, 'declaredKong', source=meldTiles)
        self.waitAndCall(self.pickDeadEndTile)

    def claimMahJongg(self, player, concealedMelds, withDiscard, lastMeld):
        ignoreDiscard = withDiscard
        for part in concealedMelds.split():
            meld = Meld(part)
            for pair in meld.pairs:
                if pair == ignoreDiscard:
                    ignoreDiscard = None
                else:
                    if not pair in player.concealedTiles:
                        msg = m18nE('%1 claiming MahJongg: She does not really have tile %2')
                        self.abort(msg, player.name, pair)
                    player.concealedTiles.remove(pair)
            player.concealedMelds.append(meld)
        if player.concealedTiles:
            msg = m18nE('%1 claiming MahJongg: She did not pass all concealed tiles to the server')
            self.abort(msg, player.name)
        player.declaredMahJongg(concealedMelds, withDiscard, player.lastTile, lastMeld)
        if not player.computeHandContent().maybeMahjongg():
            msg = m18nE('%1 claiming MahJongg: This is not a winning hand: %2')
            self.abort(msg, player.name, player.computeHandContent().string)
        self.tellAll(player, 'declaredMahJongg', source=concealedMelds, lastTile=player.lastTile,
                     lastMeld=list(lastMeld.pairs), withDiscard=withDiscard, winnerBalance=player.balance)
        self.waitAndCall(self.endHand)

    def dealt(self, results):
        """all tiles are dealt, ask east to discard a tile"""
        self.tellAll(self.game.activePlayer, 'activePlayer')
        self.waitAndCall(self.pickTile)

    def nextTurn(self):
        """the next player becomes active"""
        self.game.nextTurn()
        self.tellAll(self.game.activePlayer, 'activePlayer')
        self.waitAndCall(self.pickTile)

    def moved(self, results):
        """a player did something"""
        answers = []
        for result in results:
            player, args = result
            if isinstance(args, tuple):
                answer = args[0]
                args = args[1:]
            else:
                answer = args
                args = None
            if answer and answer not in ['No Claim', 'OK']:
                answers.append((player, answer, args))
        if not answers:
            self.nextTurn()
            return
        if len(answers) > 1:
            for answerMsg in ['Mah Jongg', 'Kong', 'Pung', 'Chow', 'OK']:
                if answerMsg in [x[1] for x in answers]:
                    # ignore answers with lower priority:
                    answers = [x for x in answers if x[1] == answerMsg]
                    break
        if len(answers) > 1 and answers[0][1] == 'Mah Jongg':
            answeredPlayers = [x[0] for x in answers]
            nextPlayer = self.game.nextPlayer()
            while nextPlayer not in answeredPlayers:
                nextPlayer = self.game.nextPlayer(nextPlayer)
            answers = [x for x in answers if x[0] == nextPlayer]
        if len(answers) > 1:
            print answers
            self.abort('More than one player said %s' % answer[0][1])
            return
        assert len(answers) == 1,  answers
        player, answer, args = answers[0]
        if util.PREF.debugTraffic:
            print player, 'ANSWER:', answer, args
        if answer in ['Discard', 'Bonus']:
            if player != self.game.activePlayer:
                msg = '%s said %s but is not the active player' % (player, answer)
                self.abort(msg)
                return
        if answer == 'Discard':
            tile = args[0]
            if tile not in player.concealedTiles:
                self.abort('player %s discarded %s but does not have it' % (player, tile))
                return
            self.tellAll(player, 'hasDiscarded', tile=tile)
            self.game.hasDiscarded(player, tile)
            self.waitAndCall(self.moved)
        elif answer == 'Chow':
            if self.game.nextPlayer() != player:
                print 'Chow:player:', player
                print 'Chow: nextPlayer:', self.game.nextPlayer()
                print 'Chow: activePlayer:', self.game.activePlayer
                for idx in range(4):
                    print 'Chow: Player', idx, ':', self.game.players[idx]
                self.abort('player %s illegally said Chow' % player)
                return
            self.claimTile(player, answer, args[0], 'calledChow')
        elif answer == 'Pung':
            self.claimTile(player, answer, args[0], 'calledPung')
        elif answer == 'Kong':
            if player == self.game.activePlayer:
                self.declareKong(player, args[0])
            else:
                self.claimTile(player, answer, args[0], 'calledKong')
        elif answer == 'Mah Jongg':
            self.claimMahJongg(player, args[0], args[1], Meld(args[2]))
        elif answer == 'Bonus':
            self.tellOthers(player, 'pickedBonus', source=args[0])
            self.waitAndCall(self.pickTile)
        elif answer == 'exposed':
            self.tellAll('hasExposed', args[0])
            self.game.hasExposed(args[0])
        else:
            print 'unknown args:', player, answer, args

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
            if self.tables:
                # send current tables only to new user
                defer = self.callRemote(user, 'tablesChanged', self.tableMsg())
                if defer:
                    defer.addErrback(self.ignoreLostConnection)
            else:
                # if we log into the server and there is no table on the server,
                # automatically create a table. This is helpful if we want to
                # play against 3 robots on localhost.
                self.newTable(user)

    def callRemote(self, user, *args, **kwargs):
        """if we still have a connection, call remote, otherwise clean up"""
        if user.mind:
            try:
                return user.mind.callRemote(*args, **kwargs)
            except (pb.DeadReferenceError, pb.PBConnectionLost) as e:
                user.mind = None
                self.logout(user)

    def ignoreLostConnection(self, failure):
        failure.trap(pb.PBConnectionLost)

    def broadcast(self, *args):
        """tell all users of this server"""
        for user in self.users:
            defer = self.callRemote(user, *args)
            if defer:
                defer.addErrback(self.ignoreLostConnection)

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
        return self._lookupTable(tableid).readyForGameStart(user)

    def abortTable(self, table, message, *args):
        """abort a table"""
        syslogMessage(m18n(message, *args))
        if table.tableid in self.tables:
            for user in table.users:
                table.delUser(user)
            self.broadcast('abort', table.tableid, message, *args)
            del self.tables[table.tableid]
            self.broadcastTables()

    def claim(self, user, tableid, claim):
        """a player calls something. Pass that to the other players
        at once, bypassing the pendingDeferreds"""
        table = self._lookupTable(tableid)
        table.claim(user.name, claim)

    def logout(self, user):
        """remove user from all tables"""
        if user in self.users and user.mind:
            defer = self.callRemote(user,'serverDisconnects')
            if defer:
                defer.addErrback(self.ignoreLostConnection)
            user.mind = None
            for table in self.tables.values():
                if user in table.users:
                    for pending in table.pendingDeferreds:
                        player = pending[1]
                        if player.remote == user:
                            table.pendingDeferreds.remove(pending)
                            del pending
                    if table.game:
                        self.abortTable(table, m18nE('Player %1 has logged out'), user.name)
                    else:
                        self.leaveTable(user, table.tableid)
            if user in self.users: # recursion possible: a disconnect error calls logout
                self.users.remove(user)

class User(pb.Avatar):
    def __init__(self, userid):
        self.userid = userid
        self.name = Query(['select name from player where id=%d' % userid]).data[0][0]
        self.mind = None
        self.server = None
        self.dbPath = None
    def attached(self, mind):
        self.mind = mind
        self.server.login(self)
    def detached(self, mind):
        self.server.logout(self)
        self.mind = None
    def perspective_setDbPath(self, dbPath):
        self.dbPath = dbPath
    def perspective_joinTable(self, tableid):
        return self.server.joinTable(self, tableid)
    def perspective_leaveTable(self, tableid):
        return self.server.leaveTable(self, tableid)
    def perspective_newTable(self):
        return self.server.newTable(self)
    def perspective_startGame(self, tableid):
        return self.server.startGame(self, tableid)
    def perspective_logout(self):
        self.server.logout(self)
        self.mind = None
    def perspective_claim(self, tableid, claim):
        self.server.claim(self, tableid, claim)

class MJRealm(object):
    """connects mind and server"""
    implements(portal.IRealm)

    def requestAvatar(self, avatarId, mind, *interfaces):
        if not pb.IPerspective in interfaces:
            raise NotImplementedError,  "No supported avatar interface"
        avatar = User(avatarId)
        avatar.server = self.server
        avatar.attached(mind)
        return pb.IPerspective,  avatar,  lambda a = avatar:a.detached(mind)

def server():
    import sys
    from twisted.internet import reactor
    about = About()
    KCmdLineArgs.init (sys.argv, about.about)
    options = KCmdLineOptions()
    options.add(bytes("port <PORT>"), ki18n("the server will listen on PORT"), bytes('8149'))
    options.add(bytes("debugtraffic"), ki18n("the server will show network messages"))
    options.add(bytes("seed <SEED>"), ki18n("for testing purposes: Initializes the random generator"))
    KCmdLineArgs.addCmdLineOptions(options)
    app = KApplication()
    Preferences() # load them, override with cmd line args
    args = KCmdLineArgs.parsedArgs()
    InternalParameters.seed = int(args.getOption('seed') or 0)
    port = int(args.getOption('port'))
    util.PREF.debugTraffic |= args.isSet('debugtraffic')
    InitDb()
    realm = MJRealm()
    realm.server = MJServer()
    kmjPortal = portal.Portal(realm, [DBPasswordChecker()])
    try:
        reactor.listenTCP(port, pb.PBServerFactory(kmjPortal))
    except error.CannotListenError as e:
        print e
    else:
        reactor.run()


if __name__ == '__main__':
    server()
