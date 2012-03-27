#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

The DBPasswordChecker is based on an example from the book
Twisted Network Programming Essentials by Abe Fettig. Copyright 2006
O'Reilly Media, Inc., ISBN 0-596-10032-9
"""

import sys, os, random
import signal

# keyboardinterrupt should simply terminate
signal.signal(signal.SIGINT, signal.SIG_DFL)

from common import InternalParameters
InternalParameters.isServer = True
InternalParameters.logPrefix = 'S'
from util import initLog
initLog('kajonggserver')

from PyQt4.QtCore import QCoreApplication
from twisted.spread import pb
from twisted.internet import error
from twisted.internet.defer import maybeDeferred, fail
from twisted.internet.address import UNIXAddress
from zope.interface import implements
from twisted.cred import checkers, portal, credentials, error as credError
from twisted.internet import reactor

from game import RemoteGame
from player import Players
from wall import WallEmpty
from client import Client
from query import Transaction, Query, initDb
from predefined import loadPredefinedRulesets
from meld import Meld, PAIR, PUNG, KONG, CHOW
from scoringengine import Ruleset
from util import m18n, m18nE, m18ncE, logInfo, logDebug, logWarning, SERVERMARK, \
    Duration, socketName, logError
from message import Message, ChatMessage
from common import elements, Debug
from sound import Voice
from deferredutil import DeferredBlock

def srvMessage(*args):
    """concatenate all args needed for m18n encoded in one string.
    For an explanation see util.translateServerString"""
    strArgs = []
    for arg in args:
        if not isinstance(arg, (str, unicode)):
            arg = unicode(arg)
        elif isinstance(arg, unicode):
            arg = arg.encode('utf-8')
        strArgs.append(arg)
    return SERVERMARK+SERVERMARK.join(list([str(x) for x in strArgs]))+SERVERMARK

def srvError(cls, *args):
    """raise an exception, passing args as a single string"""
    raise cls(srvMessage(*args))

class DBPasswordChecker(object):
    """checks against our sqlite3 databases"""
    implements(checkers.ICredentialsChecker)
    credentialInterfaces = (credentials.IUsernamePassword,
                            credentials.IUsernameHashedPassword)

    def requestAvatarId(self, cred): # pylint: disable=R0201
        """get user id from database"""
        args = cred.username.split(SERVERMARK)
        if len(args) > 1:
            if args[0] == 'adduser':
                cred.username = args[1]
                password = args[2]
                with Transaction():
                    query = Query('insert into player(name,password) values(?,?)',
                        list([cred.username.decode('utf-8'), password.decode('utf-8')]))
                    if not query.success:
                        if query.msg.startswith('ERROR: constraint failed') \
                        or 'not unique' in query.msg:
                            template = m18nE('User %1 already exists')
                            logInfo(m18n(template, cred.username))
                            query.msg = srvMessage(template, cred.username)
                        else:
                            logInfo(query.msg)
                        return fail(credError.UnauthorizedLogin(query.msg))
            elif args[1] == 'deluser':
                pass
        query = Query('select id, password from player where name=?',
            list([cred.username.decode('utf-8')]))
        if not len(query.records):
            template = 'Wrong username: %1'
            logInfo(m18n(template, cred.username))
            return fail(credError.UnauthorizedLogin(srvMessage(template, cred.username)))
        userid, password = query.records[0]
        # checkPassword uses md5 which cannot handle unicode strings (python 2.7)
        defer1 = maybeDeferred(cred.checkPassword, password.encode('utf-8'))
        defer1.addCallback(DBPasswordChecker._checkedPassword, userid)
        return defer1

    @staticmethod
    def _checkedPassword(matched, userid):
        """after the password has been checked"""
        if not matched:
            return fail(credError.UnauthorizedLogin(srvMessage(m18nE('Wrong password'))))
        return userid


class Table(object):
    """a table on the game server"""
    # pylint: disable=R0902
    # pylint we need more than 10 instance attributes
    # pylint: disable=R0904
    # pylint we have too many public methods

    def __init__(self, server, owner, rulesetStr, playOpen, autoPlay, wantedGame):
        self.server = server
        self.owner = owner
        if isinstance(rulesetStr, Ruleset):
            self.ruleset = rulesetStr
        else:
            self.ruleset = Ruleset.fromList(rulesetStr)
        self.playOpen = playOpen
        self.autoPlay = autoPlay
        self.wantedGame = wantedGame
        self.tableid = None
        self.users = [owner] if owner else []
        self.preparedGame = None
        self.game = None
        self.status = m18ncE('table status','New')

    @apply
    def suspended(): # pylint: disable=E0202
        """is this table holding a suspended game?"""
        def fget(self):
            # pylint: disable=W0212
            return self.status.startswith('Suspended')
        return property(**locals())

    def msg(self, onlyHash=False):
        """return the table attributes to be sent to the client"""
        game = self.game or self.preparedGame
        onlineNames = [x.name for x in self.users]
        if game:
            names = tuple(x.name for x in game.players)
        else:
            names = tuple(x.name for x in self.users)
        online = tuple(bool(x in onlineNames) for x in names)
        if game:
            endValues = game.handctr, dict((x.wind, x.balance) for x in game.players)
        else:
            endValues = None
        ruleset = self.ruleset.hash if onlyHash else self.ruleset.toList()
        return self.tableid, game.gameid if game else None, self.status, ruleset, \
                self.playOpen, self.autoPlay, self.wantedGame, names, online, endValues

    def maxSeats(self):
        """for a new game: 4. For a suspended game: The
        number of humans before suspending"""
        result = 4
        if self.preparedGame:
            result -= sum (x.name.startswith('ROBOT') for x in self.preparedGame.players)
        return result

    def sendChatMessage(self, chatLine):
        """sends a chat messages to all clients"""
        if Debug.chat:
            logDebug('server sends chat msg %s' % chatLine)
        for other in self.users:
            self.server.callRemote(other, 'chat', chatLine.serialize())

    def addUser(self, user):
        """add user to this table"""
        if user.name in list(x.name for x in self.users):
            raise srvError(pb.Error, m18nE('You already joined this table'))
        if len(self.users) == self.maxSeats():
            raise srvError(pb.Error, m18nE('All seats are already taken'))
        self.users.append(user)
        self.sendChatMessage(ChatMessage(self.tableid, user.name,
            m18nE('takes a seat'), isStatusMessage=True))

        if len(self.users) == self.maxSeats():
            self.readyForGameStart(self.owner)

    def delUser(self, user):
        """remove user from this table"""
        if user in self.users:
            self.game = None
            self.users.remove(user)
            self.sendChatMessage(ChatMessage(self.tableid, user.name,
                m18nE('leaves the table'), isStatusMessage=True))
            if user is self.owner:
                # silently pass ownership
                if self.users:
                    self.owner = self.users[0]

    def __repr__(self):
        """for debugging output"""
        return str(self.tableid) + ':' + ','.join(x.name for x in self.users)

    def calcGameId(self):
        """based upon the max gameids we got from the clients, propose
        a new one, we want to use the same gameid in all data bases"""
        serverMaxGameId = Query('select max(id) from game').records[0][0]
        serverMaxGameId = int(serverMaxGameId) if serverMaxGameId else 0
        gameIds = [x.maxGameId for x in self.users]
        gameIds.append(serverMaxGameId)
        return max(gameIds) + 1

    def prepareNewGame(self):
        """returns a new game object"""
        names = list(x.name for x in self.users)
        # the server and all databases save the english name but we
        # want to make sure a translation exists for the client GUI
        robotNames = [
            m18ncE('kajongg', 'ROBOT 1'),
            m18ncE('kajongg', 'ROBOT 2'),
            m18ncE('kajongg', 'ROBOT 3')]
        while len(names) < 4:
            names.append(robotNames[3 - len(names)])
        result = RemoteGame(names, self.ruleset, client=Client(),
            playOpen=self.playOpen, autoPlay=self.autoPlay, wantedGame=self.wantedGame, shouldSave=True)
        return result

    def connectPlayers(self, game):
        """connects client instances with the game players"""
        if not game.client:
            # the server game representation gets a dummy client
            game.client = Client()
        for player in game.players:
            for user in self.users:
                if player.name == user.name:
                    player.remote = user
        for player in game.players:
            if not player.remote:
                # we found a robot player, its client runs in this server process
                player.remote = Client(player.name)
                player.remote.table = self

    @staticmethod
    def checkDbPaths(game):
        """for 4 players, we have up to 4 data bases:
        more than one player might use the same data base.
        However the server always needs to use its own data base.
        If a data base is used by more than one client, only one of
        them should update. Here we set shouldSave for all players,
        while the server always saves"""
        serverPath = '127.0.0.1:' + Query.dbhandle.databaseName()
        dbPaths = []
        for player in game.players:
            player.shouldSave = False
            if isinstance(player.remote, User):
                peer = player.remote.mind.broker.transport.getPeer()
                if isinstance(peer, UNIXAddress):
                    hostName = '127.0.0.1'
                else:
                    hostName = peer.host
                path = hostName + ':' + player.remote.dbPath
                assert path != serverPath, 'client and server try to use the same database:%s' % path
                player.shouldSave = path not in dbPaths
            if player.shouldSave:
                dbPaths.append(path)

    def readyForGameStart(self, user):
        """the table initiator told us he wants to start the game"""
        # pylint: disable=R0912
        # pylint too many branches
        if len(self.users) < self.maxSeats() and self.owner != user:
            raise srvError(pb.Error,
                m18nE('Only the initiator %1 can start this game, you are %2'),
                self.owner.name, user.name)
        if not self.suspended:
            self.preparedGame = self.prepareNewGame()
        game = self.preparedGame
        self.connectPlayers(game)
        self.checkDbPaths(game)
        if self.suspended:
            self.initGame()
        else:
            self.proposeGameId(self.calcGameId())

    def proposeGameId(self, gameid):
        """server proposes an id to the clients ands waits for answers"""
        while True:
            with Transaction():
                query = Query('insert into game(id,seed) values(?,?)',
                      list([gameid, 'proposed']), mayFail=True)
                if query.success:
                    break
                gameid += random.randrange(1, 100)
        block = DeferredBlock(self)
        for player in self.preparedGame.players:
            if player.shouldSave and isinstance(player.remote, User):
                # do not ask robot players, they use the server data base
                block.tellPlayer(player, Message.ProposeGameId, gameid=gameid)
        block.callback(self.collectGameIdAnswers, gameid)

    def collectGameIdAnswers(self, requests, gameid):
        """clients answered if the proposed game id is free"""
        for msg in requests:
            if msg.answer == Message.NO:
                self.proposeGameId(gameid + 1)
                return
        self.preparedGame.gameid = gameid
        self.initGame()

    def initGame(self):
        """ask clients if they are ready to start"""
        game = self.preparedGame
        game.saveNewGame()
        block = DeferredBlock(self)
        for player in game.players:
            block.tellPlayer(player, Message.ReadyForGameStart, tableid=self.tableid,
                gameid=game.gameid, shouldSave=player.shouldSave,
                wantedGame=game.wantedGame, source=list((x.wind, x.name) for x in game.players))
        block.callback(self.startGame)

    def startGame(self, requests):
        """if all players said ready, start the game"""
        mayStart = True
        for msg in requests:
            if msg.answer == Message.NO or len(requests) < 4:
                # this player answered "I am not ready", exclude her from table
                # a player might already have logged of from the table. So if we
                # are not 4 anymore, all players must leave the table
                self.server.leaveTable(msg.player.remote, self.tableid)
                self.preparedGame = None
                mayStart = False
        if not mayStart:
            return
        self.game = self.preparedGame
        elementIter = iter(elements.all(self.game.ruleset))
        for tile in self.game.wall.tiles:
            tile.element = elementIter.next()
            tile.element = tile.upper()
        assert isinstance(self.game, RemoteGame), self.game
        self.status = m18ncE('table status', 'Running')
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
        humanPlayers = [x for x in self.game.players if isinstance(x.remote, User)]
        if len(humanPlayers) < 2 or not any(x.remote.voiceId for x in humanPlayers):
            # no need to pass around voice data
            self.assignVoices()
            return
        block = DeferredBlock(self)
        for player in humanPlayers:
            if player.remote.voiceId:
                # send it to other human players:
                others = [x for x in humanPlayers if x != player]
                if Debug.sound:
                    logDebug('telling other human players that %s has voiceId %s' % (
                        player.name, player.remote.voiceId))
                block.tell(player, others, Message.VoiceId, source=player.remote.voiceId)
        block.callback(self.collectVoiceData)

    def collectVoiceData(self, requests):
        """collect voices of other players"""
        block = DeferredBlock(self)
        voiceDataRequests = []
        for request in requests:
            if request.answer == Message.ClientWantsVoiceData:
                # another human player requests sounds for voiceId
                voiceId = request.args[0]
                voiceFor = [x for x in self.game.players if isinstance(x.remote, User) \
                    and x.remote.voiceId == voiceId][0]
                voiceFor.voice = Voice(voiceId)
                if Debug.sound:
                    logDebug('client %s wants voice data %s for %s' % (request.player.name, request.args[0], voiceFor))
                voiceDataRequests.append((request.player, voiceFor))
                if not voiceFor.voice.oggFiles():
                    # the server does not have it, ask the client with that voice
                    block.tell(voiceFor, voiceFor, Message.ServerWantsVoiceData)
        block.callback(self.sendVoiceData, voiceDataRequests)

    def sendVoiceData(self, requests, voiceDataRequests):
        """sends voice sounds to other human players"""
        self.processAnswers(requests)
        block = DeferredBlock(self)
        for voiceDataRequester, voiceFor in voiceDataRequests:
            # this player requested sounds for voiceFor
            voice = voiceFor.voice
            content = voice.archiveContent
            if content:
                if Debug.sound:
                    logDebug('server got voice data %s for %s from client' % (voiceFor.voice, voiceFor.name))
                block.tell(voiceFor, voiceDataRequester, Message.VoiceData, md5sum=voice.md5sum, source=content)
            elif Debug.sound:
                logDebug('server got empty voice data %s for %s from client' % (
                    voice, voiceFor.name))
        block.callback(self.assignVoices)

    def assignVoices(self, dummyResults=None):
        """now all human players have all voice data needed"""
        humanPlayers = [x for x in self.game.players if isinstance(x.remote, User)]
        block = DeferredBlock(self)
        block.tell(None, humanPlayers, Message.AssignVoices)
        block.callback(self.startHand)

    def pickTile(self, dummyResults=None, deadEnd=False):
        """the active player gets a tile from wall. Tell all clients."""
        if not self.game:
            return
        player = self.game.activePlayer
        try:
            tile = self.game.pickedTile(player, deadEnd)
        except WallEmpty:
            self.endHand()
        else:
            tileName = tile.element
            block = DeferredBlock(self)
            block.tellPlayer(player, Message.PickedTile, source=tileName, deadEnd=deadEnd)
            if tileName[0] in 'fy' or self.game.playOpen:
                block.tellOthers(player, Message.PickedTile, source=tileName, deadEnd=deadEnd)
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

    def clientDiscarded(self, msg):
        """client told us he discarded a tile. Check for consistency and tell others."""
        player = msg.player
        game = self.game
        assert player == game.activePlayer
        tile = msg.args[0]
        if tile not in player.concealedTileNames:
            self.abort('player %s discarded %s but does not have it' % (player, tile))
            return
        txt = game.dangerousFor(player, tile)
        mustPlayDangerous = player.mustPlayDangerous()
        block = DeferredBlock(self)
        game.hasDiscarded(player, tile)
        block.tellAll(player, Message.HasDiscarded, tile=tile)
        if player.violatesOriginalCall():
            if Debug.originalCall:
                logDebug('%s just violated OC with %s' % (player, player.discarded[-1]))
            player.mayWin = False
            block.tellAll(player, Message.ViolatedOriginalCall)
        if txt:
            if mustPlayDangerous and player.lastSource not in 'dZ':
                if Debug.dangerousGame:
                    logDebug('%s claims no choice. Discarded %s, keeping %s. %s' % \
                         (player, tile, ''.join(player.concealedTileNames), ' / '.join(txt)))
                player.claimedNoChoice = True
                block.tellAll(player, Message.HasNoChoice, tile=player.concealedTileNames)
            else:
                player.playedDangerous = True
                if Debug.dangerousGame:
                    logDebug('%s played dangerous. Discarded %s, keeping %s. %s' % \
                         (player, tile, ''.join(player.concealedTileNames), ' / '.join(txt)))
                block.tellAll(player, Message.PlayedDangerous, tile=player.concealedTileNames)
        if msg.answer == Message.OriginalCall:
            block.callback(self.clientMadeOriginalCall, msg)
        else:
            block.callback(self.askForClaims)

    def clientMadeOriginalCall(self, dummyResults, msg):
        """first tell everybody about original call
        and then treat the implicit discard"""
        msg.player.originalCall = True
        if Debug.originalCall:
            logDebug('server.clientMadeOriginalCall: %s' % msg.player)
        block = DeferredBlock(self)
        block.tellAll(msg.player, Message.MadeOriginalCall)
        block.callback(self.askForClaims)

    def startHand(self, dummyResults=None):
        """all players are ready to start a hand, so do it"""
        if self.game:
            self.game.prepareHand()
            self.game.initialDeal()
            block = self.tellAll(None, Message.InitHand,
                divideAt=self.game.divideAt)
            block.callback(self.divided)

    def divided(self, dummyResults=None):
        """the wall is now divided for all clients"""
        block = DeferredBlock(self)
        for clientPlayer in self.game.players:
            allPlayerTiles = []
            for player in self.game.players:
                bonusTileNames = list(x.element for x in player.bonusTiles)
                if player == clientPlayer or self.game.playOpen:
                    playerTiles = player.concealedTileNames
                else:
                    playerTiles = ['Xy'] * 13
                allPlayerTiles.append((player.name, playerTiles + bonusTileNames))
            block.tellPlayer(clientPlayer, Message.SetConcealedTiles, source=allPlayerTiles)
        block.callback(self.dealt)

    def endHand(self, dummyResults=None):
        """hand is over, show all concealed tiles to all players"""
        if not self.game:
            return
        if self.game.playOpen:
            self.saveHand()
        else:
            block = DeferredBlock(self)
            for player in self.game.players:
                # there might be no winner, winner.others() would be wrong
                if player != self.game.winner:
                    # the winner tiles are already shown in claimMahJongg
                    block.tellOthers(player, Message.ShowConcealedTiles, show=True,
                        source=player.concealedTileNames)
            block.callback(self.saveHand)

    def saveHand(self, dummyResults=None):
        """save the hand to the database and proceed to next hand"""
        self.tellAll(None, Message.SaveHand, self.nextHand)
        self.game.saveHand()

    def nextHand(self, dummyResults):
        """next hand: maybe rotate"""
        DeferredBlock.garbageCollection()
        for block in DeferredBlock.blocks:
            if block.table == self:
                logError('request left from previous hand: %s' % block.outstandingStr())
        token = self.game.handId() # we need to send the old token until the
                                   # clients started the new hand
        rotateWinds = self.game.maybeRotateWinds()
        if self.game.finished():
            self.close('gameOver', m18nE('The game is over!'))
            return
        self.game.sortPlayers()
        playerNames = list((x.wind, x.name) for x in self.game.players)
        self.tellAll(None, Message.ReadyForHandStart, self.startHand,
            source=playerNames, rotateWinds=rotateWinds, token=token)

    def abort(self, message, *args):
        """abort the table. Reason: message/args"""
        self.close('abort', message, *args)

    def close(self, reason, message, *args):
        """close the table. Reason: message/args"""
        self.server.closeTable(self, reason, message, *args)

    def claimTile(self, player, claim, meldTiles, nextMessage):
        """a player claims a tile for pung, kong or chow.
        meldTiles contains the claimed tile, concealed"""
        lastDiscard = self.game.lastDiscard
        claimedTile = lastDiscard.element
        hasTiles = meldTiles[:]
        discardingPlayer = self.game.activePlayer
        hasTiles.remove(claimedTile)
        meld = Meld(meldTiles)
        if len(meldTiles) != 4 and meld.meldType not in [PAIR, PUNG, KONG, CHOW]:
            msg = m18nE('%1 wrongly said %2 for meld %3') + 'x:' + str(meld.meldType) + meld.joined
            self.abort(msg, player.name, claim.name, str(meld))
            return
        if not player.hasConcealedTiles(hasTiles):
            msg = m18nE('%1 wrongly said %2: claims to have concealed tiles %3 but only has %4')
            self.abort(msg, player.name, claim.name, ' '.join(hasTiles), ''.join(player.concealedTileNames))
            return
        # update our internal state before we listen to the clients again
        self.game.activePlayer = player
        if claimedTile:
            player.lastTile = claimedTile.lower()
            player.lastSource = 'd'
        player.exposeMeld(hasTiles, claimedTile)
        self.game.lastDiscard = None
        block = DeferredBlock(self)
        if (nextMessage != Message.CalledKong
                and self.game.dangerousFor(discardingPlayer, lastDiscard)
                and discardingPlayer.playedDangerous):
            player.usedDangerousFrom = discardingPlayer
            if Debug.dangerousGame:
                logDebug('%s claims dangerous tile %s discarded by %s' % \
                         (player, lastDiscard, discardingPlayer))
            block.tellAll(player, Message.UsedDangerousFrom, source=discardingPlayer.name)
        block.tellAll(player, nextMessage, source=meldTiles)
        if claim == Message.Kong:
            block.callback(self.pickKongReplacement)
        else:
            block.callback(self.moved)

    def declareKong(self, player, meldTiles):
        """player declares a Kong, meldTiles is a list"""
        if not player.hasConcealedTiles(meldTiles) and not player.hasExposedPungOf(meldTiles[0]):
            # pylint: disable=W0142
            msg = m18nE('declareKong:%1 wrongly said Kong for meld %2')
            args = (player.name, ''.join(meldTiles))
            logError(m18n(msg, *args))
            logError('declareKong:concealedTileNames:%s' % ''.join(player.concealedTileNames))
            logError('declareKong:concealedMelds:%s' % \
                ' '.join(x.joined for x in player.concealedMelds))
            logError('declareKong:exposedMelds:%s' % \
                ' '.join(x.joined for x in player.exposedMelds))
            self.abort(msg, *args)
            return
        player.exposeMeld(meldTiles)
        self.tellAll(player, Message.DeclaredKong, self.pickKongReplacement, source=meldTiles)

    def claimMahJongg(self, msg):
        """a player claims mah jongg. Check this and if correct, tell all."""
        player = msg.player
        concealedMelds, withDiscard, lastMeld = msg.args
        discardingPlayer = self.game.activePlayer
        # pylint: disable=E1103
        # (pylint ticket 8774)
        lastMove = self.game.lastMoves(without=[Message.PopupMsg]).next()
        robbedTheKong = lastMove.message == Message.DeclaredKong
        if robbedTheKong:
            player.lastSource = 'k'
            withDiscard = lastMove.source[0].capitalize()
            lastMove.player.robTile(withDiscard)
        lastMeld = Meld(lastMeld)
        ignoreDiscard = withDiscard
        for part in concealedMelds.split():
            meld = Meld(part)
            for pair in meld.pairs:
                if pair == ignoreDiscard:
                    ignoreDiscard = None
                else:
                    if not pair in player.concealedTileNames:
                        msg = m18nE('%1 claiming MahJongg: She does not really have tile %2')
                        self.abort(msg, player.name, pair)
                    player.concealedTileNames.remove(pair)
            player.concealedMelds.append(meld)
        if player.concealedTileNames:
            msg = m18nE('%1 claiming MahJongg: She did not pass all concealed tiles to the server')
            self.abort(msg, player.name)
        player.declaredMahJongg(concealedMelds, withDiscard, player.lastTile, lastMeld)
        if not player.computeHandContent().maybeMahjongg():
            msg = m18nE('%1 claiming MahJongg: This is not a winning hand: %2')
            self.abort(msg, player.name, player.computeHandContent().string)
        block = DeferredBlock(self)
        if robbedTheKong:
            block.tellAll(player, Message.RobbedTheKong, tile=withDiscard)
        if (player.lastSource == 'd'
                and self.game.dangerousFor(discardingPlayer, self.game.lastDiscard)
                and discardingPlayer.playedDangerous):
            player.usedDangerousFrom = discardingPlayer
            if Debug.dangerousGame:
                logDebug('%s wins with dangerous tile %s from %s' % \
                             (player, self.game.lastDiscard, discardingPlayer))
            block.tellAll(player, Message.UsedDangerousFrom, source=discardingPlayer.name)
        block.tellAll(player, Message.DeclaredMahJongg, source=concealedMelds, lastTile=player.lastTile,
                     lastMeld=list(lastMeld.pairs), withDiscard=withDiscard)
        block.callback(self.endHand)

    def dealt(self, dummyResults):
        """all tiles are dealt, ask east to discard a tile"""
        self.tellAll(self.game.activePlayer, Message.ActivePlayer, self.pickTile)

    def nextTurn(self):
        """the next player becomes active"""
        if self.game:
            # the player might just have disconnected
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

    def askForClaims(self, dummyRequests):
        """ask all players if they want to claim"""
        if self.game:
            self.tellAll(self.game.activePlayer, Message.AskForClaims, self.moved)

    def processAnswers(self, requests):
        """a player did something"""
        if not self.game:
            return
        answers = self.prioritize(requests)
        if not answers:
            return
        for answer in answers:
            msg = '<-  %s' % unicode(answer)
            if Debug.traffic:
                logDebug(msg)
            with Duration(msg):
                answer.answer.serverAction(self, answer)
        return answers

    def moved(self, requests):
        """a player did something"""
        answers = self.processAnswers(requests)
        if not answers:
            self.nextTurn()

    def notMoved(self, requests):
        """a player sent a notification, has already been processed"""
        self.processAnswers(requests) # we still want debugging output

    def tellAll(self, player, command, callback=None, **kwargs):
        """tell something about player to all players"""
        block = DeferredBlock(self)
        block.tellAll(player, command, **kwargs)
        block.callback(callback)
        return block

class MJServer(object):
    """the real mah jongg server"""
    def __init__(self):
        self.tables = {}
        self.suspendedTables = {} # key is gameid
        self.users = list()
        Players.load()

    def chat(self, chatString):
        """a client sent us a chat message"""
        chatLine = ChatMessage(chatString)
        if Debug.chat:
            logDebug('server got chat message %s' % chatLine)
        self.tables[chatLine.tableid].sendChatMessage(chatLine)

    def login(self, user):
        """accept a new user"""
        if not user in self.users:
            self.users.append(user)
            self.loadSuspendedTables(user)

    def callRemote(self, user, *args, **kwargs):
        """if we still have a connection, call remote, otherwise clean up"""
        legalTypes = (int, long, basestring, float, list, type(None))
        for arg in args:
            if not isinstance(arg, legalTypes):
                raise Exception('callRemote got illegal arg: %s %s' % (arg, type(arg)))
        for keyword, arg in kwargs.items():
            if not isinstance(arg, legalTypes):
                raise Exception('callRemote got illegal kwarg: %s:%s %s' % (keyword, arg, type(arg)))
        if user.mind:
            try:
                return user.mind.callRemote(*args, **kwargs).addErrback(MJServer.ignoreLostConnection)
            except (pb.DeadReferenceError, pb.PBConnectionLost):
                user.mind = None
                self.logout(user)

    @staticmethod
    def ignoreLostConnection(failure):
        """if the client went away, do not dump error messages on stdout"""
        failure.trap(pb.PBConnectionLost)

    def sendTables(self, user):
        """user requests the table list. If several tables have the same
        ruleset, send it only once. For the other tables, send its hash"""
        tables = self.tables.values()
        for suspTable in self.suspendedTables.values():
            for player in suspTable.preparedGame.players:
                if player.name == user.name:
                    tables.append(suspTable)
        if Debug.traffic:
            logDebug('SERVER sends %d unstarted tables and %d suspended tables to %s' % (
                len(self.tables), len(tables) - len(self.tables), user.name),
                withGamePrefix=False)
        hashes = set(x.ruleset.hash for x in tables)
        tableList = []
        for table in tables:
            tableList.append(table.msg(table.ruleset.hash not in hashes))
            hashes -= set([table.ruleset.hash])
        return tableList

    def broadcastTables(self):
        """tell all users about changed tables"""
        for user in self.users:
            tableList = self.sendTables(user)
            self.callRemote(user, 'tablesChanged', tableList)

    def _lookupTable(self, tableid):
        """return table by id or raise exception"""
        if tableid not in self.tables:
            raise srvError(pb.Error, m18nE('table with id <numid>%1</numid> not found'), tableid)
        return self.tables[tableid]

    def setTableId(self, table):
        """generates a new table id: the first free one"""
        usedIds = set(self.tables.keys() or [0])
        availableIds = set(x for x in range(1, 2+max(usedIds)))
        result = min(availableIds - usedIds)
        table.tableid = result
        self.tables[table.tableid] = table
        self.broadcastTables()
        return result

    def newTable(self, user, ruleset, playOpen, autoPlay, wantedGame):
        """user creates new table and joins it. Use the first free table id"""
        table = Table(self, user, ruleset, playOpen, autoPlay, wantedGame)
        self.setTableId(table)
        return table.tableid

    def joinTable(self, user, tableid):
        """user joins table"""
        if tableid in self.tables:
            self._lookupTable(tableid).addUser(user)
            self.broadcastTables()
            return True
        else:
            # might be a suspended table:
            for suspTable in self.suspendedTables.values():
                assert isinstance(suspTable.preparedGame, RemoteGame), suspTable.preparedGame
                if suspTable.tableid == tableid:
                    self.setTableId(suspTable)
                    del self.suspendedTables[suspTable.preparedGame.gameid]
                    suspTable.addUser(user)
                    self.broadcastTables()
                    return True
        raise srvError(pb.Error, m18nE('table with id <numid>%1</numid> not found'), tableid)

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
        logInfo('%s%s ' % (('%s:' % table.game.seed) if table.game else '', m18n(message, *args)), withGamePrefix=None)
        if table.tableid in self.tables:
            for user in table.users:
                self.callRemote(user, reason, table.tableid, message, *args)
            for user in table.users:
                table.delUser(user)
            del self.tables[table.tableid]
            self.broadcastTables()
        for block in DeferredBlock.blocks[:]:
            if block.table == table:
                DeferredBlock.blocks.remove(block)

    def logout(self, user):
        """remove user from all tables"""
        if user in self.users and user.mind:
            self.callRemote(user,'serverDisconnects')
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
        if InternalParameters.socket and not InternalParameters.continueServer \
            and not self.users and reactor.running:
            # do not stop right now, the client might reconnect right away
            # this happens if the wanted human player name did not yet exist
            # in the data base - in that case login fails. Next the client
            # might tell us to add that user to the data base. So let's wait
            # to see for 5 seconds if he does
            reactor.callLater(5, self.stopNowAfterLastDisconnect)

    def stopNowAfterLastDisconnect(self):
        """as the name says"""
        if InternalParameters.socket and not InternalParameters.continueServer \
            and not self.users and reactor.running:
            logInfo('local server terminates. Reason: last client disconnected')
            reactor.stop()

    def loadSuspendedTables(self, user):
        """loads all yet unloaded suspended tables where this
        user is participating. We do not unload them if the
        user logs out, there are filters anyway returning only
        the suspended games for a certain user.
        Never load old autoplay games."""
        query = Query("select distinct g.id, g.starttime, " \
            "g.seed, " \
            "ruleset, s.scoretime " \
            "from game g, player p0, score s," \
            "player p1, player p2, player p3 " \
            "where autoplay=0 " \
            " and p0.id=g.p0 and p1.id=g.p1 " \
            " and p2.id=g.p2 and p3.id=g.p3 " \
            " and (p0.name=? or p1.name=? or p2.name=? or p3.name=?) " \
            " and s.game=g.id" \
            " and g.endtime is null" \
            " and exists(select 1 from score where game=g.id)" \
            " and s.scoretime = (select max(scoretime) from score where game=g.id) limit 10",
            list([user.name, user.name, user.name, user.name]))
        for gameid, starttime, seed, ruleset, suspendTime in query.records:
            playOpen = False # do not continue playing resumed games with open tiles,
                                        # playOpen is for testing purposes only anyway
            if gameid not in self.suspendedTables and starttime:
                # why do we get a record with empty fields when the query should return nothing?
                if gameid not in (x.game.gameid if x.game else None for x in self.tables.values()):
                    table = Table(self, None, Ruleset.cached(ruleset, used=True), playOpen,
                        autoPlay=False, wantedGame=str(seed))
                    table.tableid = 1000 + gameid
                    table.status = m18ncE('table status', 'Suspended') + suspendTime
                    table.preparedGame = RemoteGame.loadFromDB(gameid, None, cacheRuleset=True)
                    self.suspendedTables[gameid] = table

class User(pb.Avatar):
    """the twisted avatar"""
    def __init__(self, userid):
        self.name = Query(['select name from player where id=%d' % userid]).records[0][0]
        self.mind = None
        self.server = None
        self.dbPath = None
        self.voiceId = None
        self.maxGameId = None

    def attached(self, mind):
        """override pb.Avatar.attached"""
        self.mind = mind
        self.server.login(self)
    def detached(self, dummyMind):
        """override pb.Avatar.detached"""
        self.server.logout(self)
        self.mind = None
    def perspective_setClientProperties(self, dbPath, voiceId, maxGameId, clientVersion=None):
        """perspective_* methods are to be called remotely"""
        self.dbPath = dbPath
        self.voiceId = voiceId
        self.maxGameId = maxGameId
        serverVersion = InternalParameters.version
        if clientVersion != serverVersion:
            # we assume that versions x.y.* are compatible
            if clientVersion is None:
                # client passed no version info
                return fail(srvError(pb.Error,
                    m18nE('Your client has a version older than 4.9.0 but you need %1 for this server'),
                        serverVersion))
            else:
                commonDigits = len([x for x in zip(
                    clientVersion.split('.'),
                    serverVersion.split('.'))
                    if x[0] == x[1]])
                if commonDigits < 2:
                    return fail(srvError(pb.Error,
                        m18nE('Your client has version %1 but you need %2 for this server'),
                            clientVersion or '<4.9.0',
                            '.'.join(serverVersion.split('.')[:2]) + '.*'))
    def perspective_sendTables(self):
        """perspective_* methods are to be called remotely"""
        return self.server.sendTables(self)
    def perspective_joinTable(self, tableid):
        """perspective_* methods are to be called remotely"""
        return self.server.joinTable(self, tableid)
    def perspective_leaveTable(self, tableid):
        """perspective_* methods are to be called remotely"""
        return self.server.leaveTable(self, tableid)
    def perspective_newTable(self, ruleset, playOpen, autoPlay, wantedGame):
        """perspective_* methods are to be called remotely"""
        return self.server.newTable(self, ruleset, playOpen, autoPlay, wantedGame)
    def perspective_startGame(self, tableid):
        """perspective_* methods are to be called remotely"""
        return self.server.startGame(self, tableid)
    def perspective_logout(self):
        """perspective_* methods are to be called remotely"""
        self.detached(None)
    def perspective_chat(self, chatString):
        """perspective_* methods are to be called remotely"""
        return self.server.chat(chatString)
    def __str__(self):
        return '%d:%s' % (id(self) % 10000, self.name)

class MJRealm(object):
    """connects mind and server"""
    implements(portal.IRealm)

    def __init__(self):
        self.server = None

    def requestAvatar(self, avatarId, mind, *interfaces):
        """as the tutorials do..."""
        if not pb.IPerspective in interfaces:
            raise NotImplementedError, "No supported avatar interface"
        avatar = User(avatarId)
        avatar.server = self.server
        avatar.attached(mind)
        return pb.IPerspective, avatar, lambda a = avatar:a.detached(mind)

# pylint: disable=W0404
# pylint does not like imports within functions

def kajonggServer():
    """start the server"""
    from optparse import OptionParser
    parser = OptionParser()
    defaultPort = InternalParameters.defaultPort()
    parser.add_option('', '--port', dest='port',
        help=m18n('the server will listen on PORT (%d)' % defaultPort),
        type=int, default=defaultPort)
    parser.add_option('', '--socket', dest='socket',
        help=m18n('the server will listen on SOCKET'), default=None)
    parser.add_option('', '--db', dest='dbpath', help=m18n('name of the database'), default=None)
    parser.add_option('', '--local', dest='local', action='store_true',
        help=m18n('start a local game server'), default=False)
    parser.add_option('', '--continue', dest='continueServer', action='store_true',
        help=m18n('do not terminate local game server after last client disconnects'), default=False)
    parser.add_option('', '--debug', dest='debug',
        help=Debug.help())
    (options, args) = parser.parse_args()
    if args and ''.join(args):
        logWarning(m18n('unrecognized arguments:%1', ' '.join(args)))
        sys.exit(2)
    InternalParameters.continueServer |= options.continueServer
    if options.dbpath:
        InternalParameters.dbPath = os.path.expanduser(options.dbpath)
    if options.local:
        InternalParameters.socket = socketName()
    if options.socket:
        InternalParameters.socket = options.socket
    Debug.setOptions(options.debug)
    Query.dbhandle = initDb()
    realm = MJRealm()
    realm.server = MJServer()
    kajonggPortal = portal.Portal(realm, [DBPasswordChecker()])
    # pylint: disable=E1101
    # pylint thinks reactor is missing listen* and run
    loadPredefinedRulesets()
    try:
        if InternalParameters.socket:
            if os.name == 'nt':
                logInfo('local server listening on 127.0.0.1 port %d' % options.port)
                reactor.listenTCP(options.port, pb.PBServerFactory(kajonggPortal),
                    interface='127.0.0.1')
            else:
                logInfo('local server listening on UNIX socket %s' % InternalParameters.socket)
                reactor.listenUNIX(InternalParameters.socket, pb.PBServerFactory(kajonggPortal))
        else:
            logInfo('server listening on port %d' % options.port)
            reactor.listenTCP(options.port, pb.PBServerFactory(kajonggPortal))
    except error.CannotListenError, errObj:
        logWarning(errObj)
    else:
        reactor.run()

def profileMe():
    """where do we lose time?"""
    import cProfile
    cProfile.run('kajonggServer()', 'prof')
    import pstats
    statistics = pstats.Stats('prof')
    statistics.sort_stats('cumulative')
    statistics.print_stats(40)

# we need this so we can load SQL driver plugins on Windows
SERVERAPP = QCoreApplication([])
