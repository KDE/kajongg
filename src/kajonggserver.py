#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

The DBPasswordChecker is based on an example from the book
Twisted Network Programming Essentials by Abe Fettig. Copyright 2006
O'Reilly Media, Inc., ISBN 0-596-10032-9
"""

import syslog
syslog.openlog('kajonggserver')

from twisted.spread import pb
from twisted.internet import error
from twisted.internet.defer import Deferred, maybeDeferred, DeferredList
from twisted.internet.address import UNIXAddress
from zope.interface import implements
from twisted.cred import checkers, portal, credentials, error as credError
import random
#from PyKDE4.kdecore import ki18n
#from PyKDE4.kdeui import KApplication
#from about import About
from game import RemoteGame, Players, WallEmpty
from client import Client
from query import Query, InitDb
import predefined  # make predefined rulesets known, ignore pylint warning
from scoringengine import Ruleset, Meld, PAIR, PUNG, KONG, CHOW, CONCEALED
from util import m18n, m18nE, m18ncE, syslogMessage, debugMessage, logWarning, SERVERMARK, \
  logException
from message import Message
from common import WINDS, InternalParameters
from move import Move
from sound import Voice

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
        if InternalParameters.socket:
            serverName = Query.localServerName
        else:
            serverName = Query.serverName
        query = Query('select id, password from player where host=? and name=?',
            list([serverName, cred.username]))
        if not len(query.data):
            raise srvError(credError.UnauthorizedLogin, m18nE('Wrong username or password'))
        userid, password = query.data[0]
        defer1 = maybeDeferred(cred.checkPassword, password)
        defer1.addCallback(self._checkedPassword, userid)
        return defer1

    def _checkedPassword(self, matched, userid):
        """after the password has been checked"""
        if not matched:
            raise srvError(credError.UnauthorizedLogin, m18nE('Wrong username or password'))
        return userid


class Request(object):
    """holds a Deferred and related data, used as part of a DeferredBlock"""
    def __init__(self, deferred, player):
        self.deferred = deferred
        self.player = player
        self.answers = None

    def __str__(self):
        answers = ','.join(str(self.answers))
        return '%s: answers:%s' % (self.player, answers)

class Answer(object):
    def __init__(self, player, args):
        self.player = player
        if isinstance(args, tuple):
            answer = args[0]
            if isinstance(args[1], tuple):
                self.args = list(args[1])
            else:
                self.args = list([args[1]])
        else:
            answer = args
            self.args = None
        if answer is not None:
            self.answer = Message.defined[answer]
        else:
            self.answer = None

    def __str__(self):
        return '%s answers: %s: %s' % (self.player, self.answer, self.args)

    def __repr__(self):
        return '<Answer: %s>' % self


class DeferredBlock(object):
    """holds a list of deferreds and waits for each of them individually,
    with each deferred having its own independent callbacks. Fires a
    'general' callback after all deferreds have returned."""

    blocks = []

    def __init__(self, table):
        self.garbageCollection()
        self.table = table
        self.requests = []
        self.__callback = None
        self.outstanding = 0
        self.completed = False
        DeferredBlock.blocks.append(self)

    def garbageCollection(self):
        """delete completed blocks"""
        for block in DeferredBlock.blocks[:]:
            if block.completed:
                DeferredBlock.blocks.remove(block)

    def add(self, deferred, player):
        """add deferred for player to this block"""
        assert not self.__callback
        assert not self.completed
        request = Request(deferred, player)
        self.requests.append(request)
        self.outstanding += 1
        deferred.addCallback(self.__gotAnswer, request).addErrback(self.__failed, request)

    def removeRequest(self, request):
        """we do not want this request anymore"""
        self.requests.remove(request)
        self.outstanding -= 1

    def callback(self, cb):
        """to be done after all players answered"""
        assert not self.completed
        self.__callback = cb
        if self.outstanding <= 0:
            cb(self.requests)

    def __gotAnswer(self, result, request):
        """got answer from player"""
        assert not self.completed
        request.answers = [x[1] for x in result if x[0]]
        if request.answers is not None:
            if not isinstance(request.answers, list):
                request.answers = list([request.answers])
            for answer in request.answers:
                if isinstance(answer, tuple):
                    answer = answer[0]
                if answer and Message.defined[answer].notifyAtOnce:
                    block = DeferredBlock(self.table)
                    block.tellAll(request.player, Message.PopupMsg, msg=answer)
        self.outstanding -= 1
        if self.outstanding <= 0 and self.__callback:
            self.completed = True
            answers = []
            for request in self.requests:
                if request.answers is not None:
                    for args in request.answers:
                        answers.append(Answer(request.player, args))
            self.__callback(answers)

    def __failed(self, result, request):
        """a player did not or not correctly answer"""
        if result.type in  [pb.PBConnectionLost]:
            msg = m18nE('The game server lost connection to player %1')
            self.table.abort(msg, request.player.name)
        else:
            msg = m18nE('Unknown error for player %1: %2\n%3')
            self.table.abort(msg, request.player.name, result.getErrorMessage(), result.getTraceback())

    def tell(self, about, receivers, command, **kwargs):
        """send info about player 'about' to players 'receivers'"""
        if not isinstance(receivers, list):
            receivers = list([receivers])
        for receiver in receivers:
            if command != Message.PopupMsg:
                self.table.lastMove = Move(about, command, kwargs)
            if InternalParameters.showTraffic:
                if  not isinstance(receiver.remote, Client):
                    debugMessage('SERVER to %s about %s: %s %s' % (receiver, about, command, kwargs))
            if isinstance(receiver.remote, Client):
                defer = Deferred()
                defer.addCallback(receiver.remote.remote_move, command, **kwargs)
                defer.callback(about.name)
            else:
                defer = self.table.server.callRemote(receiver.remote, 'move', about.name, command.name, **kwargs)
            if defer:
                # the remote player might already be disconnected, defer would be None then
                self.add(defer, receiver)

    def tellPlayer(self, player, command,  **kwargs):
        """address only one player"""
        self.tell(player, player, command, **kwargs)

    def tellOthers(self, player, command, **kwargs):
        """tell others about player'"""
        game = self.table.game or self.table.preparedGame
        self.tell(player,  list([x for x in game.players if x!= player]), command, **kwargs)

    def tellAll(self, player, command, **kwargs):
        """tell something to all players"""
        game = self.table.game or self.table.preparedGame
        self.tell(player, game.players, command, **kwargs)

class Table(object):
    """a table on the game server"""
    TableId = 0
    def __init__(self, server, owner, rulesetStr, playOpen):
        self.server = server
        self.owner = owner
        self.rulesetStr = rulesetStr
        self.ruleset = Ruleset.fromList(rulesetStr)
        self.playOpen = playOpen
        self.owningPlayer = None
        Table.TableId = Table.TableId + 1
        self.tableid = Table.TableId
        self.users = [owner]
        self.preparedGame = None
        self.game = None
        self.lastMove = None
        self.voiceDataRequests = []

    def addUser(self, user):
        """add user to this table"""
        if user.name in list(x.name for x in self.users):
            raise srvError(pb.Error, m18nE('You already joined this table'))
        if len(self.users) == 4:
            raise srvError(pb.Error, m18nE('All seats are already taken'))
        self.users.append(user)
        if len(self.users) == 4:
            self.readyForGameStart()

    def delUser(self, user):
        """remove user from this table"""
        if user in self.users:
            self.game = None
            self.users.remove(user)
            if user is self.owner:
                # silently pass ownership
                if self.users:
                    self.owner = self.users[0]

    def __repr__(self):
        """for debugging output"""
        return str(self.tableid) + ':' + ','.join(x.name for x in self.users)

    def readyForGameStart(self, user):
        """the table initiator told us he wants to start the game"""
        if len(self.users) < 4 and self.owner != user:
            raise srvError(pb.Error,
                m18nE('Only the initiator %1 can start this game, you are %2'),
                self.owner.name, user.name)
        names = list(x.name for x in self.users)
        # the server and all databases save the english name but we
        # want to make sure a translation exists for the client GUI
        robotNames = [
            m18ncE('kajongg', 'ROBOT 1'),
            m18ncE('kajongg', 'ROBOT 2'),
            m18ncE('kajongg', 'ROBOT 3')]
        while len(names) < 4:
            names.append(robotNames[3 - len(names)])
        game = RemoteGame(names, self.ruleset, client=Client(), playOpen=self.playOpen)
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
        for player, wind in zip(game.players, WINDS):
            player.wind = wind
        # send the names for players E,S,W,N in that order:
        # for each database, only one Game instance should save.
        dbPaths = ['127.0.0.1:' + Query.dbhandle.databaseName()]
        block = DeferredBlock(self)
        for player in game.players:
            if isinstance(player.remote, User):
                peer = player.remote.mind.broker.transport.getPeer()
                if isinstance(peer, UNIXAddress):
                    hostName = Query.localServerName
                else:
                    hostName = peer.host
                path = hostName + ':' + player.remote.dbPath
                shouldSave = path not in dbPaths
                if shouldSave:
                    dbPaths.append(path)
            else:
                shouldSave = False
            block.tellPlayer(player, Message.ReadyForGameStart, tableid=self.tableid, shouldSave=shouldSave,
                seed=game.seed, source='//'.join(x.name for x in game.players))
        block.callback(self.startGame)

    def startGame(self, requests):
        """if all players said ready, start the game"""
        for msg in requests:
            if msg.answer == Message.NO:
                # this player answered "I am not ready", exclude her from table
                self.server.leaveTable(msg.player.remote, self.tableid)
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
        self.sendVoiceIds()

    def sendVoiceIds(self):
        """tell each player what voice ids the others have. By now the client has a Game instance!"""
        block = DeferredBlock(self)
        for player in self.game.players:
            if isinstance(player.remote, User):
                # send it to other human players:
                others = [x for x in self.game.players if not isinstance(x.remote, Client)]
                block.tell(player, others, Message.VoiceId, source=player.remote.voiceId)
        block.callback(self.collectVoiceData)

    def collectVoiceData(self, requests):
        """collect data for voices of other players"""
        block = DeferredBlock(self)
        for request in requests:
            if request.answer == Message.ClientWantsVoiceData:
                # another human player requests data to voiceId
                voiceId = request.args[0]
                voiceFor = [x for x in self.game.players if isinstance(x.remote, User) and x.remote.voiceId == voiceId][0]
                voice = Voice(voiceId)
                voiceFor.voice = voice
                self.voiceDataRequests.append((request.player, voiceId))
                if not voice.hasData():
                    # the server does not have it, ask the client with that voice
                    block.tell(self.owningPlayer, voiceFor, Message.ServerWantsVoiceData)
        block.callback(self.sendVoiceData)

    def sendVoiceData(self, requests):
        """sends voice data to other human players"""
        self.processAnswers(requests)
        block = DeferredBlock(self)
        for voiceDataRequester, voiceId in self.voiceDataRequests:
            # this player requested data for voiceId
            voice = Voice(voiceId)
            if voice and voice.hasData():
                block.tell(self.owningPlayer, voiceDataRequester, Message.VoiceData, source=voice.data)
        block.callback(self.startHand)

    def pickTile(self, results=None, deadEnd=False):
        """the active player gets a tile from wall. Tell all clients."""
        player = self.game.activePlayer
        block = DeferredBlock(self)
        try:
            tile = self.game.wall.dealTo(deadEnd=deadEnd)[0]
            self.game.pickedTile(player, tile, deadEnd)
        except WallEmpty:
            block.callback(self.endHand)
        else:
            block.tellPlayer(player, Message.PickedTile, source=tile, deadEnd=deadEnd)
            if tile[0] in 'fy' or self.game.playOpen:
                block.tellOthers(player, Message.PickedTile, source=tile, deadEnd=deadEnd)
            else:
                block.tellOthers(player, Message.PickedTile, source= 'Xy', deadEnd=deadEnd)
            block.callback(self.moved)

    def pickKongReplacement(self, requests=None):
        """the active player gets a tile from the dead end. Tell all clients."""
        requests = self.prioritize(requests)
        if requests and requests[0].answer == Message.MahJongg:
            requests[0].answer.serverAction(self, requests[0])
        else:
            self.pickTile(requests, deadEnd=True)

    def startHand(self, results=None):
        """all players are ready to start a hand, so do it"""
        self.game.prepareHand()
        self.game.deal()
        block = self.tellAll(self.owningPlayer, Message.InitHand,
            divideAt=self.game.divideAt)
        for player in self.game.players:
            if self.game.playOpen:
                concealed = player.concealedTiles
            else:
                concealed = ['Xy']*13
            block.tellPlayer(player, Message.SetTiles, source=player.concealedTiles + player.bonusTiles)
            block.tellOthers(player, Message.SetTiles, source=concealed+player.bonusTiles)
        block.callback(self.dealt)

    def endHand(self, results):
        """hand is over, show all concealed tiles to all players"""
        block = DeferredBlock(self)
        for player in self.game.players:
            block.tellOthers(player, Message.ShowTiles, source=player.concealedTiles)
        block.callback(self.saveHand)

    def saveHand(self, results):
        """save the hand to the database and proceed to next hand"""
        self.game.saveHand()
        self.tellAll(self.owningPlayer, Message.SaveHand, self.nextHand)

    def nextHand(self, results):
        """next hand: maybe rotate"""
        rotate = self.game.maybeRotateWinds()
        if self.game.finished():
            self.close('gameOver', m18nE('The game is over!'))
            return
        self.game.sortPlayers()
        playerNames = '//'.join(self.game.players[x].name for x in WINDS)
        self.tellAll(self.owningPlayer, Message.ReadyForHandStart, self.startHand,
            source=playerNames, rotate=rotate)

    def abort(self, message, *args):
        """abort the table. Reason: message/args"""
        self.close('abort', message, *args)

    def close(self, reason, message, *args):
        """close the table. Reason: message/args"""
        self.server.closeTable(self, reason, message, *args)

    def claimTile(self, player, claim, meldTiles, nextMessage):
        """a player claims a tile for pung, kong, chow or Mah Jongg.
        meldTiles contains the claimed tile, concealed"""
        claimedTile = player.game.lastDiscard
        if claimedTile not in meldTiles:
            msg = m18nE('Discarded tile %1 is not in meld %2')
            self.abort(msg, str(claimedTile), ''.join(meldTiles))
            return
        meld = Meld(meldTiles)
        concKong =  len(meldTiles) == 4 and meldTiles[0][0].isupper() and meldTiles == [meldTiles[0]]*4
        # this is a concealed kong with 4 concealed tiles, will be changed to x#X#X#x#
        # by exposeMeld()
        if not concKong and meld.meldType not in [PAIR, PUNG, KONG, CHOW]:
            msg = m18nE('%1 wrongly said %2 for meld %3')
            self.abort(msg, player.name, claim.name, str(meld))
            return
        checkTiles = meldTiles[:]
        checkTiles.remove(claimedTile)
        if not player.hasConcealedTiles(checkTiles):
            msg = m18nE('%1 wrongly said %2: claims to have concealed tiles %3 but only has %4')
            self.abort(msg, player.name, claim.name, ''.join(checkTiles), ''.join(player.concealedTiles))
            return
        self.game.activePlayer = player
        player.addTile(claimedTile)
        player.lastTile = claimedTile.lower()
        player.lastSource = 'd'
        player.exposeMeld(meldTiles)
        if claim == Message.Kong:
            callback = self.pickKongReplacement
        else:
            callback = self.moved
        self.tellAll(player, nextMessage, callback, source=meldTiles)

    def declareKong(self, player, meldTiles):
        """player declares a Kong, meldTiles is a list"""
        if not player.hasConcealedTiles(meldTiles) and not player.hasExposedPungOf(meldTiles[0]):
            msg = m18nE('declareKong:%1 wrongly said Kong for meld %2')
            args = (player.name, ''.join(meldTiles))
            syslogMessage(m18n(msg, *args), syslog.LOG_ERR)
            syslogMessage('declareKong:concealedTiles:%s' % ''.join(player.concealedTiles), syslog.LOG_ERR)
            syslogMessage('declareKong:concealedMelds:%s' % \
                ' '.join(x.joined for x in player.concealedMelds), syslog.LOG_ERR)
            syslogMessage('declareKong:exposedMelds:%s' % \
                ' '.join(x.joined for x in player.exposedMelds), syslog.LOG_ERR)
            self.abort(msg, *args)
            return
        player.exposeMeld(meldTiles, claimed=False)
        self.tellAll(player, Message.DeclaredKong, self.pickKongReplacement, source=meldTiles)

    def claimMahJongg(self, msg):
        """a player claims mah jongg. Check this and if correct, tell all."""
        player = msg.player
        concealedMelds, withDiscard, lastMeld = msg.args
        lastMeld = Meld(lastMeld)
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
        block = DeferredBlock(self)
        if self.lastMove.command == Message.DeclaredKong:
            player.lastSource = 'k'
            self.game.activePlayer.robTile(withDiscard)
            block.tellAll(player, Message.RobbedTheKong, tile=withDiscard)
        block.tellAll(player, Message.DeclaredMahJongg, source=concealedMelds, lastTile=player.lastTile,
                     lastMeld=list(lastMeld.pairs), withDiscard=withDiscard, winnerBalance=player.balance)
        block.callback(self.endHand)

    def pickedBonus(self, player, bonus):
        block = DeferredBlock(self)
        block.tellOthers(player, Message.PickedBonus, source=bonus)
        block.callback(self.pickTile)

    def dealt(self, results):
        """all tiles are dealt, ask east to discard a tile"""
        self.tellAll(self.game.activePlayer, Message.ActivePlayer, self.pickTile)

    def nextTurn(self):
        """the next player becomes active"""
        self.game.nextTurn()
        self.tellAll(self.game.activePlayer, Message.ActivePlayer, self.pickTile)

    def prioritize(self, requests):
        """returns only requests we want to execute"""
        answers = [x for x in requests if x.answer not in [Message.NoClaim, Message.OK, None]]
        if len(answers) > 1:
            claims = [Message.MahJongg, Message.Kong, Message.Pung, Message.Chow]
            for claim in claims:
                if claim in [x.answer for x in answers]:
                    # ignore claims with lower priority:
                    answers = [x for x in answers if x.answer == claim or x.answer not in claims]
                    break
        mjAnswers = [x for x in answers if x.answer == Message.MahJongg]
        if len(mjAnswers) > 1:
            mjPlayers = [x.player for x in mjAnswers]
            nextPlayer = self.game.nextPlayer()
            while nextPlayer not in mjPlayers:
                nextPlayer = self.game.nextPlayer(nextPlayer)
            answers = [x for x in answers if x.player == nextPlayer or x.answer != Message.MahJongg]
        return answers

    def askForClaims(self, requests):
        self.tellAll(self.game.activePlayer, Message.AskForClaims, self.moved)

    def processAnswers(self, requests):
        """a player did something"""
        if not self.game:
            return
        answers = self.prioritize(requests)
        if not answers:
            return
        for answer in answers:
            if InternalParameters.showTraffic:
                debugMessage(str(answer))
            answer.answer.serverAction(self, answer)
        return answers

    def moved(self, requests):
        """a player did something"""
        answers = self.processAnswers(requests)
        if not answers:
            self.nextTurn()

    def tellAll(self, player, command, callback=None,  **kwargs):
        """tell something to all players"""
        block = DeferredBlock(self)
        block.tellAll(player, command, **kwargs)
        if callback:
            block.callback(callback)
        return block

class MJServer(object):
    """the real mah jongg server"""
    def __init__(self):
        self.tables = {}
        self.users = list()
        Players.load()
    def login(self, user):
        """accept a new user"""
        if not user in self.users:
            self.users.append(user)

    def callRemote(self, user, *args, **kwargs):
        """if we still have a connection, call remote, otherwise clean up"""
        legalTypes = (int, long, basestring, float, list, type(None))
        for arg in args:
            if not isinstance(arg, legalTypes):
                raise Exception('callRemote got illegal arg: %s %s' (arg, type(arg)))
        for kw, arg in kwargs.items():
            if not isinstance(arg, legalTypes):
                raise Exception('callRemote got illegal kwarg: %s:%s %s' (kw, arg, type(arg)))
        if user.mind:
            try:
                return user.mind.callRemote(*args, **kwargs)
            except (pb.DeadReferenceError, pb.PBConnectionLost), errObj:
                user.mind = None
                self.logout(user)

    def ignoreLostConnection(self, failure):
        """if the client went away, do not dump error messages on stdout"""
        failure.trap(pb.PBConnectionLost)

    def broadcast(self, *args):
        """tell all users of this server"""
        if InternalParameters.showTraffic:
            debugMessage('SERVER broadcasts: %s' % ' '.join([str(x) for x in args]))
        for user in self.users:
            defer = self.callRemote(user, *args)
            if defer:
                defer.addErrback(self.ignoreLostConnection)

    def tableMsg(self):
        """build a message containing table info"""
        msg = list()
        for table in self.tables.values():
            msg.append(tuple([table.tableid, bool(table.game), table.rulesetStr, table.playOpen,  tuple(x.name for x in table.users)]))
        return msg

    def requestTables(self, user):
        """user requests the table list"""
        defer = self.callRemote(user, 'tablesChanged', None, self.tableMsg())
        if defer:
            defer.addErrback(self.ignoreLostConnection)

    def broadcastTables(self, tableid=None):
        """tell all users about changed tables"""
        self.broadcast('tablesChanged', tableid, self.tableMsg())

    def _lookupTable(self, tableid):
        """return table by id or raise exception"""
        if tableid not in self.tables:
            raise srvError(pb.Error, m18nE('table with id <numid>%1</numid> not found'), tableid)
        return self.tables[tableid]

    def newTable(self, user, ruleset, playOpen):
        """user creates new table and joins it"""
        table = Table(self, user, ruleset, playOpen)
        self.tables[table.tableid] = table
        self.broadcastTables(table.tableid)
        return table.tableid

    def joinTable(self, user, tableid):
        """user joins table"""
        self._lookupTable(tableid).addUser(user)
        self.broadcastTables()
        return True

    def leaveTable(self, user, tableid):
        """user leaves table. If no human user is left on table, delete it"""
        if tableid in self.tables:
            table = self._lookupTable(tableid)
            table.delUser(user)
            if not table.users:
                del self.tables[tableid]
            self.broadcastTables()
        return True

    def startGame(self, user, tableid):
        """try to start the game"""
        return self._lookupTable(tableid).readyForGameStart(user)

    def closeTable(self, table, reason, message, *args):
        """close a table"""
        syslogMessage(m18n(message, *args))
        if table.tableid in self.tables:
            for user in table.users:
                table.delUser(user)
            self.broadcast(reason, table.tableid, message, *args)
            del self.tables[table.tableid]
            self.broadcastTables()

    def logout(self, user):
        """remove user from all tables"""
        if user in self.users and user.mind:
            defer = self.callRemote(user,'serverDisconnects')
            if defer:
                defer.addErrback(self.ignoreLostConnection)
            user.mind = None
            for block in DeferredBlock.blocks:
                for request in block.requests:
                    if request.player.remote == user:
                        block.removeRequest(request)
            if user in self.users: # avoid recursion : a disconnect error calls logout
                for table in self.tables.values():
                    if user in table.users:
                        if table.game:
                            self.closeTable(table, 'abort', m18nE('Player %1 has logged out'), user.name)
                        else:
                            self.leaveTable(user, table.tableid)
                self.users.remove(user)

class User(pb.Avatar):
    """the twisted avatar"""
    def __init__(self, userid):
        self.userid = userid
        self.name = Query(['select name from player where id=%d' % userid]).data[0][0]
        self.mind = None
        self.server = None
        self.dbPath = None
        self.voiceId = None
    def attached(self, mind):
        """override pb.Avatar.attached"""
        self.mind = mind
        self.server.login(self)
    def detached(self, mind):
        """override pb.Avatar.detached"""
        self.server.logout(self)
        self.mind = None
    def perspective_setClientProperties(self, dbPath, voiceId):
        """perspective_* methods are to be called remotely"""
        self.dbPath = dbPath
        self.voiceId = voiceId
    def perspective_requestTables(self):
        """perspective_* methods are to be called remotely"""
        return self.server.requestTables(self)
    def perspective_joinTable(self, tableid):
        """perspective_* methods are to be called remotely"""
        return self.server.joinTable(self, tableid)
    def perspective_leaveTable(self, tableid):
        """perspective_* methods are to be called remotely"""
        return self.server.leaveTable(self, tableid)
    def perspective_newTable(self, ruleset, playOpen):
        """perspective_* methods are to be called remotely"""
        return self.server.newTable(self, ruleset, playOpen)
    def perspective_startGame(self, tableid):
        """perspective_* methods are to be called remotely"""
        return self.server.startGame(self, tableid)
    def perspective_logout(self):
        """perspective_* methods are to be called remotely"""
        self.server.logout(self)
        self.mind = None

class MJRealm(object):
    """connects mind and server"""
    implements(portal.IRealm)

    def __init__(self):
        self.server = None

    def requestAvatar(self, avatarId, mind, *interfaces):
        """as the tutorials do..."""
        if not pb.IPerspective in interfaces:
            raise NotImplementedError,  "No supported avatar interface"
        avatar = User(avatarId)
        avatar.server = self.server
        avatar.attached(mind)
        return pb.IPerspective, avatar, lambda a = avatar:a.detached(mind)

def kajonggServer():
    """start the server"""
    from twisted.internet import reactor
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('', '--port', dest='port', help=m18n('the server will listen on PORT'),
        metavar='PORT', default=8149)
    parser.add_option('', '--showtraffic', dest='showtraffic', action='store_true',
        help=m18n('the server will show network messages'), default=False)
    parser.add_option('', '--showsql', dest='showsql', action='store_true',
        help=m18n('show database SQL commands'), default=False)
    parser.add_option('', '--seed', dest='seed',
        help=m18n('for testing purposes: Initializes the random generator with SEED'),
        metavar='SEED', default=0)
    parser.add_option('', '--db', dest='dbpath', help=m18n('name of the database'), default=None)
    parser.add_option('', '--socket', dest='socket', help=m18n('listen on UNIX SOCKET'), default=None, metavar='SOCKET')
    (options, args) = parser.parse_args()
    InternalParameters.seed = int(options.seed)
    port = int(options.port)
    InternalParameters.showTraffic |= options.showtraffic
    InternalParameters.showSql |= options.showsql
    if options.dbpath:
        InternalParameters.dbPath = options.dbpath
    if options.socket:
        InternalParameters.socket = options.socket
    InitDb()
    realm = MJRealm()
    realm.server = MJServer()
    kajonggPortal = portal.Portal(realm, [DBPasswordChecker()])
    try:
        if options.socket:
            reactor.listenUNIX(options.socket, pb.PBServerFactory(kajonggPortal))
        else:
            reactor.listenTCP(port, pb.PBServerFactory(kajonggPortal))
    except error.CannotListenError, errObj:
        logWarning(errObj)
    else:
        reactor.run()

if __name__ == '__main__':
    kajonggServer()
    if False:
        import cProfile
        cProfile.run('kajonggServer()', 'prof')
        import pstats
        p = pstats.Stats('prof')
        p.sort_stats('cumulative')
        p.print_stats(40)
