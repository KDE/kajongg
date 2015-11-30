#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2014 Wolfgang Rohdewald <wolfgang@rohdewald.de>

Kajongg is free software you can redistribute it and/or modify
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
Twisted Network Programming Essentials by Abe Fettig, 2006
O'Reilly Media, Inc., ISBN 0-596-10032-9
"""

import sys
import os
import random
import traceback
if os.name != 'nt':
    import resource
import datetime
import logging
from itertools import chain


def cleanExit(*dummyArgs):
    """we want to cleanly close sqlite3 files"""
    if Options.socket and os.name != 'nt':
        if os.path.exists(Options.socket):
            os.remove(Options.socket)
    try:
        if Internal.db:
            Internal.db.close()
                              # setting to None does not call close(), do we
                              # need close?
        logging.shutdown()
        os._exit(0)  # pylint: disable=protected-access
    except NameError:
        logging.shutdown()
    try:
        reactor.stop()
    except NameError:
        sys.exit(0)
    except ReactorNotRunning:
        pass

from signal import signal, SIGABRT, SIGINT, SIGTERM
signal(SIGABRT, cleanExit)
signal(SIGINT, cleanExit)
signal(SIGTERM, cleanExit)
if os.name != 'nt':
    from signal import SIGHUP, SIGQUIT
    signal(SIGHUP, cleanExit)
    signal(SIGQUIT, cleanExit)


from common import Options, Internal, unicode, WINDS, nativeString
Internal.isServer = True
Internal.logPrefix = 'S'

from twisted.spread import pb
from twisted.internet import error
from twisted.internet.defer import maybeDeferred, fail, succeed
from zope.interface import implementer
from twisted.cred import checkers, portal, credentials, error as credError
from twisted.internet import reactor
from twisted.internet.error import ReactorNotRunning
reactor.addSystemEventTrigger('before', 'shutdown', cleanExit)
Internal.reactor = reactor

from tile import Tile, TileList, elements
from game import PlayingGame
from player import Players
from wall import WallEmpty
from client import Client, Table
from query import Query, initDb
from meld import Meld, MeldList
from log import m18n, m18nE, m18ncE, logDebug, logWarning, logError, SERVERMARK
from util import Duration, elapsedSince
from message import Message, ChatMessage
from common import Debug
from sound import Voice
from deferredutil import DeferredBlock
from rule import Ruleset


def srvMessage(*args):
    """
    concatenate all args needed for m18n encoded in one string.
    For an explanation see util.translateServerMessage.

    @returns: The string to be wired.
    @rtype: C{str}, utf-8 encoded
    """
    strArgs = []
    for arg in args:
        if isinstance(arg, unicode):
            arg = arg.encode('utf-8')
        else:
            arg = str(arg).encode('utf-8')
        strArgs.append(arg)
    mark = SERVERMARK.encode()
    return mark + mark.join(strArgs) + mark


def srvError(cls, *args):
    """raise an exception, passing args as a single string"""
    raise cls(srvMessage(*args))


@implementer(checkers.ICredentialsChecker)
class DBPasswordChecker(object):

    """checks against our sqlite3 databases"""
    credentialInterfaces = (credentials.IUsernamePassword,
                            credentials.IUsernameHashedPassword)

    def requestAvatarId(self, cred):  # pylint: disable=no-self-use
        """get user id from database"""
        cred.username = cred.username.decode('utf-8')
        args = cred.username.split(SERVERMARK)
        if len(args) > 1:
            if args[0] == u'adduser':
                cred.username = args[1]
                password = args[2]
                query = Query(
                    'insert or ignore into player(name,password) values(?,?)',
                    (cred.username,
                     password))
            elif args[1] == u'deluser':
                pass
        query = Query(
            'select id, password from player where name=?', (cred.username,))
        if not len(query.records):
            template = u'Wrong username: %1'
            if Debug.connections:
                logDebug(m18n(template, cred.username))
            return fail(credError.UnauthorizedLogin(srvMessage(template, cred.username)))
        userid, password = query.records[0]
        # checkPassword uses md5 which cannot handle unicode strings (python
        # 2.7)
        defer1 = maybeDeferred(cred.checkPassword, password.encode('utf-8'))
        defer1.addCallback(DBPasswordChecker._checkedPassword, userid)
        return defer1

    @staticmethod
    def _checkedPassword(matched, userid):
        """after the password has been checked"""
        if not matched:
            return fail(credError.UnauthorizedLogin(srvMessage(m18nE('Wrong password'))))
        return userid


class ServerGame(PlayingGame):

    """the central game instance on the server"""
    # pylint: disable=too-many-arguments, too-many-public-methods

    def __init__(self, names, ruleset, gameid=None, wantedGame=None,
                 client=None, playOpen=False, autoPlay=False):
        PlayingGame.__init__(
            self,
            names,
            ruleset,
            gameid,
            wantedGame,
            client,
            playOpen,
            autoPlay)
        self.shouldSave = True

    def throwDices(self):
        """sets random living and kongBox
        sets divideAt: an index for the wall break"""
        self.wall.tiles.sort()
        self.randomGenerator.shuffle(self.wall.tiles)
        PlayingGame.throwDices(self)

    def initHand(self):
        """Happens only on server: every player gets 13 tiles (including east)"""
        self.throwDices()
        self.wall.divide()
        for player in self.players:
            player.clearHand()
            # 13 tiles at least, with names as given by wall
            player.addConcealedTiles(self.wall.deal([None] * 13))
            # compensate boni
            while len(player.concealedTiles) != 13:
                player.addConcealedTiles(self.wall.deal())
        PlayingGame.initHand(self)


class ServerTable(Table):

    """a table on the game server"""
    # pylint: disable=too-many-arguments

    def __init__(self, server, owner, ruleset, suspendedAt,
                 playOpen, autoPlay, wantedGame, tableId=None):
        if tableId is None:
            tableId = server.generateTableId()
        Table.__init__(
            self,
            tableId,
            ruleset,
            suspendedAt,
            False,
            playOpen,
            autoPlay,
            wantedGame)
        self.server = server
        self.owner = owner
        self.users = [owner] if owner else []
        self.remotes = {}   # maps client connections to users
        self.game = None
        self.client = None
        server.tables[self.tableid] = self
        if Debug.table:
            logDebug(u'new table %s' % self)

    def hasName(self, name):
        """returns True if one of the players in the game is named 'name'"""
        return bool(self.game) and any(x.name == name for x in self.game.players)

    def asSimpleList(self, withFullRuleset=False):
        """return the table attributes to be sent to the client"""
        game = self.game
        onlineNames = [x.name for x in self.users]
        if self.suspendedAt:
            names = tuple(x.name for x in game.players)
        else:
            names = tuple(x.name for x in self.users)
        online = tuple(bool(x in onlineNames) for x in names)
        if game:
            endValues = game.handctr, dict(
                (x.wind, x.balance) for x in game.players)
        else:
            endValues = None
        if withFullRuleset:
            ruleset = self.ruleset.toList()
        else:
            ruleset = self.ruleset.hash
        return list(
            [self.tableid, ruleset, game.gameid if game else None, self.suspendedAt, self.running,
                self.playOpen, self.autoPlay, self.wantedGame, names, online, endValues])

    def maxSeats(self):
        """for a new game: 4. For a suspended game: The
        number of humans before suspending"""
        result = 4
        if self.suspendedAt:
            result -= sum(x.name.startswith(u'Robot ')
                          for x in self.game.players)
        return result

    def sendChatMessage(self, chatLine):
        """sends a chat messages to all clients"""
        if Debug.chat:
            logDebug(u'server sends chat msg %s' % chatLine)
        if self.suspendedAt:
            chatters = []
            for player in self.game.players:
                chatters.extend(
                    x for x in self.server.srvUsers if x.name == player.name)
        else:
            chatters = self.users
        for other in chatters:
            self.server.callRemote(other, 'chat', chatLine.asList())

    def addUser(self, user):
        """add user to this table"""
        if user.name in list(x.name for x in self.users):
            raise srvError(pb.Error, m18nE('You already joined this table'))
        if len(self.users) == self.maxSeats():
            raise srvError(pb.Error, m18nE('All seats are already taken'))
        self.users.append(user)
        if Debug.table:
            logDebug(u'%s seated on table %s' % (user.name, self))
        self.sendChatMessage(ChatMessage(self.tableid, user.name,
                                         m18nE('takes a seat'), isStatusMessage=True))

    def delUser(self, user):
        """remove user from this table"""
        if user in self.users:
            self.running = False
            self.users.remove(user)
            self.sendChatMessage(ChatMessage(self.tableid, user.name,
                                             m18nE('leaves the table'), isStatusMessage=True))
            if user is self.owner:
                # silently pass ownership
                if self.users:
                    self.owner = self.users[0]
                    if Debug.table:
                        logDebug(u'%s leaves table %d, %s is the new owner' % (
                            user.name, self.tableid, self.owner))
                else:
                    if Debug.table:
                        logDebug(u'%s leaves table %d, table is now empty' % (
                            user.name, self.tableid))
            else:
                if Debug.table:
                    logDebug(u'%s leaves table %d, %s stays owner' % (
                        user.name, self.tableid, self.owner))

    def __unicode__(self):
        """for debugging output"""
        onlineNames = list(x.name + (u'(Owner)' if x == self.owner.name else u'')
                           for x in self.users)
        offlineString = u''
        if self.game:
            offlineNames = list(x.name for x in self.game.players if x.name not in onlineNames
                                and not x.name.startswith(u'Robot'))
            if offlineNames:
                offlineString = u' offline:' + u','.join(offlineNames)
        return u'%d(%s%s)' % (self.tableid, u','.join(onlineNames), offlineString)

    def calcGameId(self):
        """based upon the max gameids we got from the clients, propose
        a new one, we want to use the same gameid in all data bases"""
        serverMaxGameId = Query('select max(id) from game').records[0][0]
        serverMaxGameId = int(serverMaxGameId) if serverMaxGameId else 0
        gameIds = [x.maxGameId for x in self.users]
        gameIds.append(serverMaxGameId)
        return max(gameIds) + 1

    def __prepareNewGame(self):
        """returns a new game object"""
        names = list(x.name for x in self.users)
        # the server and all databases save the english name but we
        # want to make sure a translation exists for the client GUI
        robotNames = [
            m18ncE(
                'kajongg, name of robot player, to be translated',
                u'Robot 1'),
            m18ncE(
                'kajongg, name of robot player, to be translated',
                u'Robot 2'),
            m18ncE('kajongg, name of robot player, to be translated', u'Robot 3')]
        while len(names) < 4:
            names.append(robotNames[3 - len(names)])
        names = list(tuple([WINDS[idx], name])
                     for idx, name in enumerate(names))
        self.client = Client()
                             # Game has a weakref to client, so we must keep
                             # it!
        return ServerGame(names, self.ruleset, client=self.client,
                          playOpen=self.playOpen, autoPlay=self.autoPlay, wantedGame=self.wantedGame)

    def userForPlayer(self, player):
        """finds the table user corresponding to player"""
        for result in self.users:
            if result.name == player.name:
                return result

    def __connectPlayers(self):
        """connects client instances with the game players"""
        game = self.game
        for player in game.players:
            remote = self.userForPlayer(player)
            if not remote:
                # we found a robot player, its client runs in this server
                # process
                remote = Client(player.name)
                remote.table = self
            self.remotes[player] = remote

    def __checkDbIdents(self):
        """for 4 players, we have up to 4 data bases:
        more than one player might use the same data base.
        However the server always needs to use its own data base.
        If a data base is used by more than one client, only one of
        them should update. Here we set shouldSave for all players,
        while the server always saves"""
        serverIdent = Internal.db.identifier
        dbIdents = set()
        game = self.game
        for player in game.players:
            player.shouldSave = False
            if isinstance(self.remotes[player], User):
                dbIdent = self.remotes[player].dbIdent
                assert dbIdent != serverIdent, \
                    'client and server try to use the same database:%s' % \
                    Internal.db.path
                player.shouldSave = dbIdent not in dbIdents
                dbIdents.add(dbIdent)

    def readyForGameStart(self, user):
        """the table initiator told us he wants to start the game"""
        if len(self.users) < self.maxSeats() and self.owner != user:
            raise srvError(pb.Error,
                           m18nE(
                               'Only the initiator %1 can start this game, you are %2'),
                           self.owner.name, user.name)
        if self.suspendedAt:
            self.__connectPlayers()
            self.__checkDbIdents()
            self.initGame()
        else:
            self.game = self.__prepareNewGame()
            self.__connectPlayers()
            self.__checkDbIdents()
            self.proposeGameId(self.calcGameId())
        # TODO: remove table for all other srvUsers out of sight

    def proposeGameId(self, gameid):
        """server proposes an id to the clients ands waits for answers"""
        while True:
            query = Query('insert into game(id,seed) values(?,?)',
                          (gameid, 'proposed'), mayFail=True, failSilent=True)
            if not query.failure:
                break
            gameid += random.randrange(1, 100)
        block = DeferredBlock(self)
        for player in self.game.players:
            if player.shouldSave and isinstance(self.remotes[player], User):
                # do not ask robot players, they use the server data base
                block.tellPlayer(player, Message.ProposeGameId, gameid=gameid)
        block.callback(self.collectGameIdAnswers, gameid)

    def collectGameIdAnswers(self, requests, gameid):
        """clients answered if the proposed game id is free"""
        if requests:
            # when errors happen, there might be no requests left
            for msg in requests:
                if msg.answer == Message.NO:
                    self.proposeGameId(gameid + 1)
                    return
                elif msg.answer != Message.OK:
                    raise srvError(
                        pb.Error,
                        'collectGameIdAnswers got neither NO nor OK')
            self.game.gameid = gameid
            self.initGame()

    def initGame(self):
        """ask clients if they are ready to start"""
        game = self.game
        game.saveStartTime()
        block = DeferredBlock(self)
        for player in game.players:
            block.tellPlayer(
                player, Message.ReadyForGameStart, tableid=self.tableid,
                gameid=game.gameid, shouldSave=player.shouldSave,
                wantedGame=game.wantedGame, source=list((x.wind, x.name) for x in game.players))
        block.callback(self.startGame)

    def startGame(self, requests):
        """if all players said ready, start the game"""
        for user in self.users:
            userRequests = list(x for x in requests if x.user == user)
            if not userRequests or userRequests[0].answer == Message.NoGameStart:
                if Debug.table:
                    if not userRequests:
                        logDebug(
                            u'Server.startGame: found no request for user %s' %
                            user.name)
                    else:
                        logDebug(
                            u'Server.startGame: %s said NoGameStart' %
                            user.name)
                self.game = None
                return
        if Debug.table:
            logDebug(u'Game starts on table %s' % self)
        elementIter = iter(elements.all(self.game.ruleset))
        wallSize = len(self.game.wall.tiles)
        self.game.wall.tiles = []
        for _ in range(wallSize):
            self.game.wall.tiles.append(next(elementIter).concealed)
        assert isinstance(self.game, ServerGame), self.game
        self.running = True
        self.__adaptOtherTables()
        self.sendVoiceIds()

    def __adaptOtherTables(self):
        """if the players on this table also reserved seats on other tables, clear them
        make running table invisible for other users"""
        for user in self.users:
            for tableid in self.server.tablesWith(user):
                if tableid != self.tableid:
                    self.server.leaveTable(user, tableid)
        foreigners = list(
            x for x in self.server.srvUsers if x not in self.users)
        if foreigners:
            if Debug.table:
                logDebug(
                    u'make running table %s invisible for %s' %
                    (self, ','.join(str(x) for x in foreigners)))
            for srvUser in foreigners:
                self.server.callRemote(
                    srvUser,
                    'tableRemoved',
                    self.tableid,
                    '')

    def sendVoiceIds(self):
        """tell each player what voice ids the others have. By now the client has a Game instance!"""
        humanPlayers = [
            x for x in self.game.players if isinstance(self.remotes[x], User)]
        if len(humanPlayers) < 2 or not any(self.remotes[x].voiceId for x in humanPlayers):
            # no need to pass around voice data
            self.assignVoices()
            return
        block = DeferredBlock(self)
        for player in humanPlayers:
            remote = self.remotes[player]
            if remote.voiceId:
                # send it to other human players:
                others = [x for x in humanPlayers if x != player]
                if Debug.sound:
                    logDebug(u'telling other human players that %s has voiceId %s' % (
                        player.name, remote.voiceId))
                block.tell(
                    player,
                    others,
                    Message.VoiceId,
                    source=remote.voiceId)
        block.callback(self.collectVoiceData)

    def collectVoiceData(self, requests):
        """collect voices of other players"""
        if not self.running:
            return
        block = DeferredBlock(self)
        voiceDataRequests = []
        for request in requests:
            if request.answer == Message.ClientWantsVoiceData:
                # another human player requests sounds for voiceId
                voiceId = request.args[0]
                voiceFor = [x for x in self.game.players if isinstance(self.remotes[x], User)
                            and self.remotes[x].voiceId == voiceId][0]
                voiceFor.voice = Voice(voiceId)
                if Debug.sound:
                    logDebug(
                        u'client %s wants voice data %s for %s' %
                        (request.user.name, request.args[0], voiceFor))
                voiceDataRequests.append((request.user, voiceFor))
                if not voiceFor.voice.oggFiles():
                    # the server does not have it, ask the client with that
                    # voice
                    block.tell(
                        voiceFor,
                        voiceFor,
                        Message.ServerWantsVoiceData)
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
                    logDebug(
                        u'server got voice data %s for %s from client' %
                        (voiceFor.voice, voiceFor.name))
                block.tell(
                    voiceFor,
                    voiceDataRequester,
                    Message.VoiceData,
                    md5sum=voice.md5sum,
                    source=content)
            elif Debug.sound:
                logDebug(u'server got empty voice data %s for %s from client' % (
                    voice, voiceFor.name))
        block.callback(self.assignVoices)

    def assignVoices(self, dummyResults=None):
        """now all human players have all voice data needed"""
        humanPlayers = [
            x for x in self.game.players if isinstance(self.remotes[x], User)]
        block = DeferredBlock(self)
        block.tell(None, humanPlayers, Message.AssignVoices)
        block.callback(self.startHand)

    def pickTile(self, dummyResults=None, deadEnd=False):
        """the active player gets a tile from wall. Tell all clients."""
        if not self.running:
            return
        player = self.game.activePlayer
        try:
            tile = player.pickedTile(deadEnd)
        except WallEmpty:
            self.endHand()
        else:
            self.game.lastDiscard = None
            block = DeferredBlock(self)
            block.tellPlayer(
                player,
                Message.PickedTile,
                tile=tile,
                deadEnd=deadEnd)
            showTile = tile if tile.isBonus or self.game.playOpen else Tile.unknown
            block.tellOthers(
                player,
                Message.PickedTile,
                tile=showTile,
                deadEnd=deadEnd)
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
        if not self.running:
            return
        player = msg.player
        assert player == self.game.activePlayer
        tile = Tile(msg.args[0])
        if tile not in player.concealedTiles:
            self.abort(
                u'player %s discarded %s but does not have it' %
                (player, tile))
            return
        dangerousText = self.game.dangerousFor(player, tile)
        mustPlayDangerous = player.mustPlayDangerous()
        violates = player.violatesOriginalCall(tile)
        self.game.hasDiscarded(player, tile)
        block = DeferredBlock(self)
        block.tellAll(player, Message.Discard, tile=tile)
        block.callback(self._clientDiscarded2, msg, dangerousText, mustPlayDangerous, violates)

    def _clientDiscarded2(self, dummyResults, msg, dangerousText, mustPlayDangerous, violates):
        """client told us he discarded a tile. Continue, check for calling"""
        block = DeferredBlock(self)
        player = msg.player
        if violates:
            if Debug.originalCall:
                tile = Tile(msg.args[0])
                logDebug(u'%s just violated OC with %s' % (player, tile))
            player.mayWin = False
            block.tellAll(player, Message.ViolatesOriginalCall)
        block.callback(self._clientDiscarded3, msg, dangerousText, mustPlayDangerous)

    def _clientDiscarded3(self, dummyResults, msg, dangerousText, mustPlayDangerous):
        """client told us he discarded a tile. Continue, check for calling"""
        block = DeferredBlock(self)
        player = msg.player
        if self.game.ruleset.mustDeclareCallingHand and not player.isCalling:
            if player.hand.callingHands:
                player.isCalling = True
                block.tellAll(player, Message.Calling)
        block.callback(self._clientDiscarded4, msg, dangerousText, mustPlayDangerous)

    def _clientDiscarded4(self, dummyResults, msg, dangerousText, mustPlayDangerous):
        """client told us he discarded a tile. Continue, check for dangerous game"""
        block = DeferredBlock(self)
        player = msg.player
        if dangerousText:
            if mustPlayDangerous and player.lastSource not in 'dZ':
                if Debug.dangerousGame:
                    tile = Tile(msg.args[0])
                    logDebug(u'%s claims no choice. Discarded %s, keeping %s. %s' %
                             (player, tile, ''.join(player.concealedTiles), ' / '.join(dangerousText)))
                player.claimedNoChoice = True
                block.tellAll(
                    player,
                    Message.NoChoice,
                    tiles=TileList(player.concealedTiles))
            else:
                player.playedDangerous = True
                if Debug.dangerousGame:
                    tile = Tile(msg.args[0])
                    logDebug(u'%s played dangerous. Discarded %s, keeping %s. %s' %
                             (player, tile, ''.join(player.concealedTiles), ' / '.join(dangerousText)))
                block.tellAll(
                    player,
                    Message.DangerousGame,
                    tiles=TileList(player.concealedTiles))
        if msg.answer == Message.OriginalCall:
            player.isCalling = True
            block.callback(self.clientMadeOriginalCall, msg)
        else:
            block.callback(self._askForClaims, msg)

    def clientMadeOriginalCall(self, dummyResults, msg):
        """first tell everybody about original call
        and then treat the implicit discard"""
        msg.player.originalCall = True
        if Debug.originalCall:
            logDebug(u'server.clientMadeOriginalCall: %s' % msg.player)
        block = DeferredBlock(self)
        block.tellAll(msg.player, Message.OriginalCall)
        block.callback(self._askForClaims, msg)

    def startHand(self, dummyResults=None):
        """all players are ready to start a hand, so do it"""
        if self.running:
            self.game.prepareHand()
            self.game.initHand()
            block = self.tellAll(None, Message.InitHand,
                                 divideAt=self.game.divideAt)
            block.callback(self.divided)

    def divided(self, dummyResults=None):
        """the wall is now divided for all clients"""
        if not self.running:
            return
        block = DeferredBlock(self)
        for clientPlayer in self.game.players:
            for player in self.game.players:
                if player == clientPlayer or self.game.playOpen:
                    tiles = player.concealedTiles
                else:
                    tiles = TileList(Tile.unknown * 13)
                block.tell(player, clientPlayer, Message.SetConcealedTiles,
                           tiles=TileList(chain(tiles, player.bonusTiles)))
        block.callback(self.dealt)

    def endHand(self, dummyResults=None):
        """hand is over, show all concealed tiles to all players"""
        if not self.running:
            return
        if self.game.playOpen:
            self.saveHand()
        else:
            block = DeferredBlock(self)
            for player in self.game.players:
                # there might be no winner, winner.others() would be wrong
                if player != self.game.winner:
                    # the winner tiles are already shown in claimMahJongg
                    block.tellOthers(
                        player, Message.ShowConcealedTiles, show=True,
                        tiles=TileList(player.concealedTiles))
            block.callback(self.saveHand)

    def saveHand(self, dummyResults=None):
        """save the hand to the database and proceed to next hand"""
        if not self.running:
            return
        self.tellAll(None, Message.SaveHand, self.nextHand)
        self.game.saveHand()

    def nextHand(self, dummyResults):
        """next hand: maybe rotate"""
        if not self.running:
            return
        DeferredBlock.garbageCollection()
        for block in DeferredBlock.blocks:
            if block.table == self:
                logError(
                    u'request left from previous hand: %s' %
                    block.outstandingUnicode())
        token = self.game.handId.prompt(
            withAI=False)  # we need to send the old token until the
                                   # clients started the new hand
        rotateWinds = self.game.maybeRotateWinds()
        if self.game.finished():
            self.server.removeTable(
                self,
                'gameOver',
                m18nE('Game <numid>%1</numid> is over!'),
                self.game.seed)
            if Debug.process and os.name != 'nt':
                logDebug(
                    u'MEM:%s' %
                    resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            return
        self.game.sortPlayers()
        playerNames = list((x.wind, x.name) for x in self.game.players)
        self.tellAll(None, Message.ReadyForHandStart, self.startHand,
                     source=playerNames, rotateWinds=rotateWinds, token=token)

    def abort(self, message, *args):
        """abort the table. Reason: message/args"""
        self.server.removeTable(self, 'abort', message, *args)

    def claimTile(self, player, claim, meldTiles, nextMessage):
        """a player claims a tile for pung, kong or chow.
        meldTiles contains the claimed tile, concealed"""
        if not self.running:
            return
        lastDiscard = self.game.lastDiscard
        # if we rob a tile, self.game.lastDiscard has already been set to the
        # robbed tile
        hasTiles = Meld(meldTiles[:])
        discardingPlayer = self.game.activePlayer
        hasTiles = hasTiles.without(lastDiscard)
        meld = Meld(meldTiles)
        if len(meld) != 4 and not (meld.isPair or meld.isPungKong or meld.isChow):
            msg = m18nE('%1 wrongly said %2 for meld %3')
            self.abort(msg, player.name, claim.name, str(meld))
            return
        if not player.hasConcealedTiles(hasTiles):
            msg = m18nE(
                '%1 wrongly said %2: claims to have concealed tiles %3 but only has %4')
            self.abort(
                msg,
                player.name,
                claim.name,
                ' '.join(hasTiles),
                ''.join(player.concealedTiles))
            return
        # update our internal state before we listen to the clients again
        self.game.discardedTiles[lastDiscard.exposed] -= 1
        self.game.activePlayer = player
        if lastDiscard:
            player.lastTile = lastDiscard.exposed
            player.lastSource = 'd'
        player.exposeMeld(hasTiles, lastDiscard)
        self.game.lastDiscard = None
        block = DeferredBlock(self)
        if (nextMessage != Message.Kong
                and self.game.dangerousFor(discardingPlayer, lastDiscard)
                and discardingPlayer.playedDangerous):
            player.usedDangerousFrom = discardingPlayer
            if Debug.dangerousGame:
                logDebug(u'%s claims dangerous tile %s discarded by %s' %
                         (player, lastDiscard, discardingPlayer))
            block.tellAll(
                player,
                Message.UsedDangerousFrom,
                source=discardingPlayer.name)
        block.tellAll(player, nextMessage, meld=meld)
        if claim == Message.Kong:
            block.callback(self.pickKongReplacement)
        else:
            block.callback(self.moved)

    def declareKong(self, player, meldTiles):
        """player declares a Kong, meldTiles is a list"""
        kongMeld = Meld(meldTiles)
        if not player.hasConcealedTiles(kongMeld) and kongMeld[0].exposed.pung not in player.exposedMelds:
            # pylint: disable=star-args
            msg = m18nE('declareKong:%1 wrongly said Kong for meld %2')
            args = (player.name, str(kongMeld))
            logDebug(m18n(msg, *args))
            logDebug(
                u'declareKong:concealedTiles:%s' %
                ''.join(player.concealedTiles))
            logDebug(u'declareKong:concealedMelds:%s' %
                     ' '.join(str(x) for x in player.concealedMelds))
            logDebug(u'declareKong:exposedMelds:%s' %
                     ' '.join(str(x) for x in player.exposedMelds))
            self.abort(msg, *args)
            return
        player.exposeMeld(kongMeld)
        self.tellAll(
            player,
            Message.DeclaredKong,
            self.pickKongReplacement,
            meld=kongMeld)

    def claimMahJongg(self, msg):
        """a player claims mah jongg. Check this and
        if correct, tell all. Otherwise abort game,  kajongg client is faulty"""
        if not self.running:
            return
        player = msg.player
        concealedMelds = MeldList(msg.args[0])
        withDiscard = Tile(msg.args[1]) if msg.args[1] else None
        lastMeld = Meld(msg.args[2])
        if self.game.ruleset.mustDeclareCallingHand:
            assert player.isCalling, '%s %s %s says MJ but never claimed: concmelds:%s withdiscard:%s lastmeld:%s' % (
                self.game.handId, player.hand, player, concealedMelds, withDiscard, lastMeld)
        discardingPlayer = self.game.activePlayer
        lastMove = next(self.game.lastMoves(withoutNotifications=True))
        robbedTheKong = lastMove.message == Message.DeclaredKong
        if robbedTheKong:
            player.lastSource = 'k'
            withDiscard = lastMove.meld[0].concealed
            lastMove.player.robTile(withDiscard)
        msgArgs = player.showConcealedMelds(concealedMelds, withDiscard)
        if msgArgs:
            self.abort(*msgArgs)  # pylint: disable=star-args
            return
        player.declaredMahJongg(
            concealedMelds,
            withDiscard,
            player.lastTile,
            lastMeld)
        if not player.hand.won:
            msg = m18nE('%1 claiming MahJongg: This is not a winning hand: %2')
            self.abort(msg, player.name, player.hand.string)
            return
        block = DeferredBlock(self)
        if robbedTheKong:
            block.tellAll(player, Message.RobbedTheKong, tile=withDiscard)
        if (player.lastSource == 'd'
                and self.game.dangerousFor(discardingPlayer, player.lastTile)
                and discardingPlayer.playedDangerous):
            player.usedDangerousFrom = discardingPlayer
            if Debug.dangerousGame:
                logDebug(u'%s wins with dangerous tile %s from %s' %
                         (player, self.game.lastDiscard, discardingPlayer))
            block.tellAll(
                player,
                Message.UsedDangerousFrom,
                source=discardingPlayer.name)
        block.tellAll(
            player, Message.MahJongg, melds=concealedMelds, lastTile=player.lastTile,
                     lastMeld=lastMeld, withDiscardTile=withDiscard)
        block.callback(self.endHand)

    def dealt(self, dummyResults):
        """all tiles are dealt, ask east to discard a tile"""
        if self.running:
            self.tellAll(
                self.game.activePlayer,
                Message.ActivePlayer,
                self.pickTile)

    def nextTurn(self):
        """the next player becomes active"""
        if self.running:
            # the player might just have disconnected
            self.game.nextTurn()
            self.tellAll(
                self.game.activePlayer,
                Message.ActivePlayer,
                self.pickTile)

    def prioritize(self, requests):
        """returns only requests we want to execute"""
        if not self.running:
            return
        answers = [
            x for x in requests if x.answer not in [
                Message.NoClaim,
                Message.OK,
                None]]
        if len(answers) > 1:
            claims = [
                Message.MahJongg,
                Message.Kong,
                Message.Pung,
                Message.Chow]
            for claim in claims:
                if claim in [x.answer for x in answers]:
                    # ignore claims with lower priority:
                    answers = [
                        x for x in answers if x.answer == claim or x.answer not in claims]
                    break
        mjAnswers = [x for x in answers if x.answer == Message.MahJongg]
        if len(mjAnswers) > 1:
            mjPlayers = [x.player for x in mjAnswers]
            nextPlayer = self.game.nextPlayer()
            while nextPlayer not in mjPlayers:
                nextPlayer = self.game.nextPlayer(nextPlayer)
            answers = [
                x for x in answers if x.player == nextPlayer or x.answer != Message.MahJongg]
        return answers

    def _askForClaims(self, dummyRequests, dummyMsg):
        """ask all players if they want to claim"""
        if self.running:
            self.tellOthers(
                self.game.activePlayer,
                Message.AskForClaims,
                self.moved)

    def processAnswers(self, requests):
        """a player did something"""
        if not self.running:
            return
        answers = self.prioritize(requests)
        if not answers:
            return
        for answer in answers:
            msg = u'<-  %s' % answer
            if Debug.traffic:
                logDebug(msg)
            with Duration(msg):
                answer.answer.serverAction(self, answer)
        return answers

    def moved(self, requests):
        """a player did something"""
        if Debug.stack:
            stck = traceback.extract_stack()
            if len(stck) > 30:
                logDebug(u'stack size:%d' % len(stck))
                logDebug(stck)
        answers = self.processAnswers(requests)
        if not answers:
            self.nextTurn()

    def tellAll(self, player, command, callback=None, **kwargs):
        """tell something about player to all players"""
        block = DeferredBlock(self)
        block.tellAll(player, command, **kwargs)
        block.callback(callback)
        return block

    def tellOthers(self, player, command, callback=None, **kwargs):
        """tell something about player to all other players"""
        block = DeferredBlock(self)
        block.tellOthers(player, command, **kwargs)
        block.callback(callback)
        return block


class MJServer(object):

    """the real mah jongg server"""

    def __init__(self):
        self.tables = {}
        self.srvUsers = list()
        Players.load()
        self.lastPing = None
        self.checkPings()

    def chat(self, chatString):
        """a client sent us a chat message"""
        chatLine = ChatMessage(chatString)
        if Debug.chat:
            logDebug(u'server got chat message %s' % chatLine)
        self.tables[chatLine.tableid].sendChatMessage(chatLine)

    def login(self, user):
        """accept a new user"""
        if not user in self.srvUsers:
            self.srvUsers.append(user)
            self.loadSuspendedTables(user)

    def callRemote(self, user, *args, **kwargs):
        """if we still have a connection, call remote, otherwise clean up"""
        if user.mind:
            try:
                args2, kwargs2 = Message.jellyAll(args, kwargs)
                # pylint: disable=star-args
                return user.mind.callRemote(*args2, **kwargs2).addErrback(MJServer.ignoreLostConnection)
            except (pb.DeadReferenceError, pb.PBConnectionLost):
                user.mind = None
                self.logout(user)

    @staticmethod
    def __stopAfterLastDisconnect():
        """as the name says"""
        if Options.socket and not Options.continueServer:
            try:
                reactor.stop()
                if Debug.connections:
                    logDebug(u'local server terminates from %s. Reason: last client disconnected' % (
                        Options.socket))
            except ReactorNotRunning:
                pass

    def checkPings(self):
        """are all clients still alive? If not log them out"""
        if not self.srvUsers and self.lastPing and elapsedSince(self.lastPing) > 30:
            # no user at all since 30 seconds, but we did already have a user
            self.__stopAfterLastDisconnect()
        for user in self.srvUsers:
            self.lastPing = max(
                self.lastPing,
                user.lastPing) if self.lastPing else user.lastPing
            if elapsedSince(user.lastPing) > 60:
                logDebug(
                    u'No messages from %s since 60 seconds, clearing connection now' %
                    user.name)
                user.mind = None
                self.logout(user)
        reactor.callLater(10, self.checkPings)

    @staticmethod
    def ignoreLostConnection(failure):
        """if the client went away correctly, do not dump error messages on stdout."""
        msg = failure.getErrorMessage()
        if not 'twisted.internet.error.ConnectionDone' in msg:
            logError(msg)
        failure.trap(pb.PBConnectionLost)

    def sendTables(self, user, tables=None):
        """send tables to user. If tables is None, he gets all new tables and those
        suspended tables he was sitting on"""
        if tables is None:
            tables = list(x for x in self.tables.values()
                          if not x.running and (not x.suspendedAt or x.hasName(user.name)))
        if len(tables):
            data = list(x.asSimpleList() for x in tables)
            if Debug.table:
                logDebug(
                    u'sending %d tables to %s: %s' %
                    (len(tables), user.name, data))
            return self.callRemote(user, 'newTables', data)
        else:
            return succeed([])

    def _lookupTable(self, tableid):
        """return table by id or raise exception"""
        if tableid not in self.tables:
            raise srvError(
                pb.Error,
                m18nE('table with id <numid>%1</numid> not found'),
                tableid)
        return self.tables[tableid]

    def generateTableId(self):
        """generates a new table id: the first free one"""
        usedIds = set(self.tables or [0])
        availableIds = set(x for x in range(1, 2 + max(usedIds)))
        return min(availableIds - usedIds)

    def newTable(self, user, ruleset, playOpen,
                 autoPlay, wantedGame, tableId=None):
        """user creates new table and joins it"""
        def gotRuleset(ruleset):
            """now we have the full ruleset definition from the client"""
            Ruleset.cached(
                ruleset).save(
            )  # make it known to the cache and save in db
        if tableId in self.tables:
            return fail(srvError(pb.Error,
                                 'You want a new table with id=%d but that id is already used for table %s' % (
                                 tableId, self.tables[tableId])))
        if Ruleset.hashIsKnown(ruleset):
            return self.__newTable(None, user, ruleset, playOpen, autoPlay, wantedGame, tableId)
        else:
            return self.callRemote(user, 'needRuleset', ruleset).addCallback(
                gotRuleset).addCallback(
                self.__newTable, user, ruleset, playOpen, autoPlay, wantedGame, tableId)

    def __newTable(self, dummy, user, ruleset,
                   playOpen, autoPlay, wantedGame, tableId=None):
        """now we know the ruleset"""
        def sent(dummy):
            """new table sent to user who created it"""
            return table.tableid
        table = ServerTable(
            self,
            user,
            ruleset,
            None,
            playOpen,
            autoPlay,
            wantedGame,
            tableId)
        result = None
        for srvUser in self.srvUsers:
            deferred = self.sendTables(srvUser, [table])
            if user == srvUser:
                result = deferred
                deferred.addCallback(sent)
        assert result
        return result

    def needRulesets(self, rulesetHashes):
        """the client wants those full rulesets"""
        result = []
        for table in self.tables.values():
            if table.ruleset.hash in rulesetHashes:
                result.append(table.ruleset.toList())
        return result

    def joinTable(self, user, tableid):
        """user joins table"""
        table = self._lookupTable(tableid)
        table.addUser(user)
        block = DeferredBlock(table)
        block.tell(
            None,
            self.srvUsers,
            Message.TableChanged,
            source=table.asSimpleList())
        if len(table.users) == table.maxSeats():
            if Debug.table:
                logDebug(u'Table %s: All seats taken, starting' % table)

            def startTable(dummy):
                """now all players know about our join"""
                table.readyForGameStart(table.owner)
            block.callback(startTable)
        else:
            block.callback(False)
        return True

    def tablesWith(self, user):
        """table ids with user, except table 'without'"""
        return list(x.tableid for x in self.tables.values() if user in x.users)

    def leaveTable(self, user, tableid, message=None, *args):
        """user leaves table. If no human user is left on a new table, remove it"""
        if tableid in self.tables:
            table = self.tables[tableid]
            if user in table.users:
                if len(table.users) == 1 and not table.suspendedAt:
                    # silent: do not tell the user who left the table that he
                    # did
                    self.removeTable(table, 'silent', message, *args)
                else:
                    table.delUser(user)
                    if self.srvUsers:
                        block = DeferredBlock(table)
                        block.tell(
                            None,
                            self.srvUsers,
                            Message.TableChanged,
                            source=table.asSimpleList())
                        block.callback(False)
        return True

    def startGame(self, user, tableid):
        """try to start the game"""
        return self._lookupTable(tableid).readyForGameStart(user)

    def removeTable(self, table, reason, message=None, *args):
        """remove a table"""
        assert reason in ('silent', 'tableRemoved', 'gameOver', 'abort')
        # HumanClient implements methods remote_tableRemoved etc.
        message = message or ''
        if Debug.connections or reason == 'abort':
            logDebug(
                u'%s%s ' % (('%s:' % table.game.seed) if table.game else '',
                            m18n(message, *args)), withGamePrefix=None)
        if table.tableid in self.tables:
            del self.tables[table.tableid]
            if reason == 'silent':
                tellUsers = []
            else:
                tellUsers = table.users if table.running else self.srvUsers
            for user in tellUsers:
                # this may in turn call removeTable again!
                self.callRemote(user, reason, table.tableid, message, *args)
            for user in table.users:
                table.delUser(user)
            if Debug.table:
                logDebug(
                    u'removing table %d: %s %s' %
                    (table.tableid, m18n(message, *args), reason))
        if table.game:
            table.game.close()

    def logout(self, user):
        """remove user from all tables"""
        if user not in self.srvUsers:
            return
        self.srvUsers.remove(user)
        for tableid in self.tablesWith(user):
            self.leaveTable(
                user,
                tableid,
                m18nE('Player %1 has logged out'),
                user.name)
        # wait a moment. We want the leaveTable message to arrive everywhere before
        # we say serverDisconnects. Sometimes the order was reversed.
        reactor.callLater(1, self.__logout2, user)

    def __logout2(self, user):
        """now the leaveTable message had a good chance to get to the clients first"""
        self.callRemote(user, 'serverDisconnects')
        user.mind = None
        for block in DeferredBlock.blocks:
            for request in block.requests:
                if request.user == user:
                    block.removeRequest(request)

    def loadSuspendedTables(self, user):
        """loads all yet unloaded suspended tables where this
        user is participating. We do not unload them if the
        user logs out, there are filters anyway returning only
        the suspended games for a certain user.
        Never load old autoplay games."""
        query = Query("select distinct g.id, g.starttime, "
                      "g.seed, "
                      "ruleset, s.scoretime "
                      "from game g, player p0, score s,"
                      "player p1, player p2, player p3 "
                      "where autoplay=0 "
                      " and p0.id=g.p0 and p1.id=g.p1 "
                      " and p2.id=g.p2 and p3.id=g.p3 "
                      " and (p0.name=? or p1.name=? or p2.name=? or p3.name=?) "
                      " and s.game=g.id"
                      " and g.endtime is null"
                      " and exists(select 1 from ruleset where ruleset.id=g.ruleset)"
                      " and exists(select 1 from score where game=g.id)"
                      " and s.scoretime = (select max(scoretime) from score where game=g.id) limit 10",
                      (user.name, user.name, user.name, user.name))
        for gameid, _, seed, ruleset, suspendTime in query.records:
            if gameid not in (x.game.gameid for x in self.tables.values() if x.game):
                table = ServerTable(
                    self, None, ruleset, suspendTime, playOpen=False,
                    autoPlay=False, wantedGame=str(seed))
                table.game = ServerGame.loadFromDB(gameid)


class User(pb.Avatar):

    """the twisted avatar"""

    def __init__(self, userid):
        self.name = Query(
            'select name from player where id=?',
            (userid,
             )).records[0][0]
        self.mind = None
        self.server = None
        self.dbIdent = None
        self.voiceId = None
        self.maxGameId = None
        self.lastPing = None
        self.pinged()

    def pinged(self):
        """time of last ping or message from user"""
        self.lastPing = datetime.datetime.now()

    def source(self):
        """how did he connect?"""
        result = str(self.mind.broker.transport.getPeer())
        if 'UNIXAddress' in result:
            # socket: we want to get the socket name
            result = Options.socket
        return result

    def attached(self, mind):
        """override pb.Avatar.attached"""
        self.mind = mind
        self.server.login(self)

    def detached(self, dummyMind):
        """override pb.Avatar.detached"""
        if Debug.connections:
            logDebug(
                u'%s: connection detached from %s' %
                (self, self.source()))
        self.server.logout(self)
        self.mind = None

    def perspective_setClientProperties(
            self, dbIdent, voiceId, maxGameId, clientVersion=None):
        """perspective_* methods are to be called remotely"""
        self.dbIdent = dbIdent
        self.voiceId = voiceId
        self.maxGameId = maxGameId
        clientVersion = nativeString(clientVersion)
        serverVersion = Internal.defaultPort
        if clientVersion != serverVersion:
            # we assume that versions x.y.* are compatible
            if clientVersion is None:
                # client passed no version info
                return fail(srvError(pb.Error,
                                     m18nE(
                                     'Your client has a version older than 4.9.0 but you need %1 for this server'),
                                     serverVersion))
            else:
                commonDigits = len([x for x in zip(
                    clientVersion.split(b'.'),
                    serverVersion.split(b'.'))
                    if x[0] == x[1]])
                if commonDigits < 2:
                    return fail(srvError(pb.Error,
                                         m18nE(
                                         'Your client has version %1 but you need %2 for this server'),
                                         clientVersion or '<4.9.0',
                                         '.'.join(serverVersion.split('.')[:2]) + '.*'))
        self.server.sendTables(self)

    def perspective_ping(self):
        """perspective_* methods are to be called remotely"""
        return self.pinged()

    def perspective_needRulesets(self, rulesetHashes):
        """perspective_* methods are to be called remotely"""
        return self.server.needRulesets(rulesetHashes)

    def perspective_joinTable(self, tableid):
        """perspective_* methods are to be called remotely"""
        return self.server.joinTable(self, tableid)

    def perspective_leaveTable(self, tableid):
        """perspective_* methods are to be called remotely"""
        return self.server.leaveTable(self, tableid)

    def perspective_newTable(
            self, ruleset, playOpen, autoPlay, wantedGame, tableId=None):
        """perspective_* methods are to be called remotely"""
        wantedGame = nativeString(wantedGame)
        return self.server.newTable(self, ruleset, playOpen, autoPlay, wantedGame, tableId)

    def perspective_startGame(self, tableid):
        """perspective_* methods are to be called remotely"""
        return self.server.startGame(self, tableid)

    def perspective_logout(self):
        """perspective_* methods are to be called remotely"""
        self.detached(None)

    def perspective_chat(self, chatString):
        """perspective_* methods are to be called remotely"""
        return self.server.chat(chatString)

    def __unicode__(self):
        return self.name


@implementer(portal.IRealm)
class MJRealm(object):

    """connects mind and server"""

    def __init__(self):
        self.server = None

    def requestAvatar(self, avatarId, mind, *interfaces):
        """as the tutorials do..."""
        if not pb.IPerspective in interfaces:
            raise NotImplementedError("No supported avatar interface")
        avatar = User(avatarId)
        avatar.server = self.server
        avatar.attached(mind)
        if Debug.connections:
            logDebug(u'Connection from %s ' % avatar.source())
        return pb.IPerspective, avatar, lambda a=avatar: a.detached(mind)


def parseArgs():
    """as the name says"""
    from optparse import OptionParser
    parser = OptionParser()
    defaultPort = Internal.defaultPort
    parser.add_option('', '--port', dest='port',
                      help=m18n(
                      'the server will listen on PORT (%d)' %
                      defaultPort),
                      type=int, default=defaultPort)
    parser.add_option('', '--socket', dest='socket',
                      help=m18n('the server will listen on SOCKET'), default=None)
    parser.add_option(
        '',
        '--db',
     dest='dbpath',
     help=m18n('name of the database'),
     default=None)
    parser.add_option(
        '', '--continue', dest='continueServer', action='store_true',
        help=m18n('do not terminate local game server after last client disconnects'), default=False)
    parser.add_option('', '--debug', dest='debug',
                      help=Debug.help())
    parser.add_option('', '--nokde', dest='nokde', action='store_true',
                      help=m18n('do not use KDE bindings. Only for testing'))
    parser.add_option('', '--qt5', dest='qt5', action='store_true',
                      help=m18n('Force using Qt5. Currently Qt4 is used by default'))
    (options, args) = parser.parse_args()
    if args and ''.join(args):
        logWarning(m18n('unrecognized arguments:%1', ' '.join(args)))
        sys.exit(2)
    Options.continueServer |= options.continueServer
    if options.dbpath:
        Options.dbPath = os.path.expanduser(options.dbpath)
    if options.socket:
        Options.socket = options.socket
    Debug.setOptions(options.debug)
    Options.fixed = True  # may not be changed anymore
    del parser           # makes Debug.gc quieter
    return options


def kajonggServer():
    """start the server"""
    # pylint: disable=too-many-branches
    options = parseArgs()
    if not initDb():
        sys.exit(1)
    realm = MJRealm()
    realm.server = MJServer()
    kajonggPortal = portal.Portal(realm, [DBPasswordChecker()])
    import predefined  # pylint: disable=unused-variable
    try:
        if Options.socket:
            if os.name == 'nt':
                if Debug.connections:
                    logDebug(
                        u'local server listening on 127.0.0.1 port %d' %
                        options.port)
                reactor.listenTCP(
                    options.port,
                    pb.PBServerFactory(kajonggPortal),
                    interface='127.0.0.1')
            else:
                if Debug.connections:
                    logDebug(
                        u'local server listening on UNIX socket %s' %
                        Options.socket)
                reactor.listenUNIX(
                    Options.socket,
                    pb.PBServerFactory(kajonggPortal))
        else:
            if Debug.connections:
                logDebug(u'server listening on port %d' % options.port)
            reactor.listenTCP(options.port, pb.PBServerFactory(kajonggPortal))
    except error.CannotListenError as errObj:
        logWarning(errObj)
        sys.exit(1)
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
