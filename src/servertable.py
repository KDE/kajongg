# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0


The DBPasswordChecker is based on an example from the book
Twisted Network Programming Essentials by Abe Fettig, 2006
O'Reilly Media, Inc., ISBN 0-596-10032-9
"""

import os
import random
import traceback
from itertools import chain
from twisted.spread import pb

from common import Debug, Internal, ReprMixin
from wind import Wind
from tilesource import TileSource
from util import Duration
from message import Message, ChatMessage
from log import logDebug, logError
from mi18n import i18nE, i18n, i18ncE
from deferredutil import DeferredBlock
from tile import Tile, TileTuple, elements
from meld import Meld, MeldList
from query import Query
from client import Client, Table
from wall import WallEmpty
from sound import Voice
from servercommon import srvError
from user import User
from game import PlayingGame

if os.name != 'nt':
    import resource


class ServerGame(PlayingGame):

    """the central game instance on the server"""

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
        """set random living and kongBox
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
            # compensate boni
            while len(player.concealedTiles) != 13:
                player.addConcealedTiles(self.wall.deal())
        PlayingGame.initHand(self)

    def _concealedTileName(self, tileName:Tile) ->Tile:
        """The server game instance knows everything but has no myself"""
        player = self.activePlayer
        if tileName not in player.concealedTiles:
            raise ValueError('I am the server Game instance. Player %s is told to show discard '
                            'of tile %s but does not have it, he has %s' %
                            (player.name, tileName, player.concealedTiles))
        return tileName

class ServerTable(Table, ReprMixin):

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
            logDebug('new table %s' % self)

    def hasName(self, name):
        """return True if one of the players in the game is named 'name'"""
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
            endValues = game.handctr, {x.wind.char: x.balance for x in game.players}
        else:
            endValues = None
        return list([
            self.tableid,
            self.ruleset.toList() if withFullRuleset else self.ruleset.hash,
            game.gameid if game else None, self.suspendedAt, self.running,
            self.playOpen, self.autoPlay, self.wantedGame, names, online, endValues])

    def maxSeats(self):
        """for a new game: 4. For a suspended game: The
        number of humans before suspending"""
        result = 4
        if self.suspendedAt:
            result -= sum(x.name.startswith('Robot ')
                          for x in self.game.players)
        return result

    def sendChatMessage(self, chatLine):
        """sends a chat messages to all clients"""
        if Debug.chat:
            logDebug('server sends chat msg %s' % chatLine)
        if self.suspendedAt and self.game:
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
        if user.name in (x.name for x in self.users):
            raise srvError(pb.Error, i18nE('You already joined this table'))
        if len(self.users) == self.maxSeats():
            raise srvError(pb.Error, i18nE('All seats are already taken'))
        self.users.append(user)
        if Debug.table:
            logDebug('%s seated on table %s' % (user.name, self))
        self.sendChatMessage(ChatMessage(self.tableid, user.name,
                                         i18nE('takes a seat'), isStatusMessage=True))

    def delUser(self, user):
        """remove user from this table"""
        if user in self.users:
            self.running = False
            self.users.remove(user)
            self.sendChatMessage(ChatMessage(self.tableid, user.name,
                                             i18nE('leaves the table'), isStatusMessage=True))
            if user is self.owner:
                # silently pass ownership
                if self.users:
                    self.owner = self.users[0]
                    if Debug.table:
                        logDebug('%s leaves table %d, %s is the new owner' % (
                            user.name, self.tableid, self.owner))
                else:
                    if Debug.table:
                        logDebug('%s leaves table %d, table is now empty' % (
                            user.name, self.tableid))
            else:
                if Debug.table:
                    logDebug('%s leaves table %d, %s stays owner' % (
                        user.name, self.tableid, self.owner))

    def __str__(self):
        """for debugging output"""
        if self.users:
            onlineNames = [x.name + ('(Owner)' if self.owner and x == self.owner.name else '')
                           for x in self.users]
        else:
            onlineNames = ['no users yet']
        offlineString = ''
        if self.game:
            offlineNames = [x.name for x in self.game.players if x.name not in onlineNames
                            and not x.name.startswith('Robot')]
            if offlineNames:
                offlineString = ' offline:' + ','.join(offlineNames)
        return '%d(%s%s)' % (self.tableid, ','.join(onlineNames), offlineString)

    def calcGameId(self):
        """based upon the max gameids we got from the clients, propose
        a new one, we want to use the same gameid in all data bases"""
        serverMaxGameId = Query('select max(id) from game').records[0][0]
        serverMaxGameId = int(serverMaxGameId) if serverMaxGameId else 0
        gameIds = [x.maxGameId for x in self.users]
        gameIds.append(serverMaxGameId)
        return max(gameIds) + 1

    def __prepareNewGame(self):
        """return a new game object"""
        names = [x.name for x in self.users]
        # the server and all databases save the english name but we
        # want to make sure a translation exists for the client GUI
        robotNames = [
            i18ncE(
                'kajongg, name of robot player, to be translated',
                'Robot 1'),
            i18ncE(
                'kajongg, name of robot player, to be translated',
                'Robot 2'),
            i18ncE('kajongg, name of robot player, to be translated', 'Robot 3')]
        while len(names) < 4:
            names.append(robotNames[3 - len(names)])
        names = [tuple([Wind.all4[idx], name]) for idx, name in enumerate(names)]
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
        return None

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
                           i18nE(
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
        block = DeferredBlock(self, where='proposeGameId')
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
                if msg.answer != Message.OK:
                    raise srvError(
                        pb.Error,
                        'collectGameIdAnswers got neither NO nor OK')
            self.game.gameid = gameid
            self.initGame()

    def initGame(self):
        """ask clients if they are ready to start"""
        game = self.game
        game.saveStartTime()
        block = DeferredBlock(self, where='initGame')
        for player in game.players:
            block.tellPlayer(
                player, Message.ReadyForGameStart, tableid=self.tableid,
                gameid=game.gameid, shouldSave=player.shouldSave,
                wantedGame=game.wantedGame, playerNames=[(x.wind, x.name) for x in game.players])
        block.callback(self.startGame)

    def startGame(self, requests):
        """if all players said ready, start the game"""
        for user in self.users:
            userRequests = [x for x in requests if x.user == user]
            if not userRequests or userRequests[0].answer == Message.NoGameStart:
                if Debug.table:
                    if not userRequests:
                        logDebug(
                            'Server.startGame: found no request for user %s' %
                            user.name)
                    else:
                        logDebug(
                            'Server.startGame: %s said NoGameStart' %
                            user.name)
                self.game = None
                return
        if Debug.table:
            logDebug('Game starts on table %s' % self)
        elementIter = iter(elements.all(self.game.ruleset))
        self.game.wall.tiles = []
        for _ in range(self.game.fullWallSize):
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
        foreigners = [x for x in self.server.srvUsers if x not in self.users]
        if foreigners:
            if Debug.table:
                logDebug(
                    'make running table %s invisible for %s' %
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
        block = DeferredBlock(self, where='sendVoiceIds')
        for player in humanPlayers:
            remote = self.remotes[player]
            if remote.voiceId:
                # send it to other human players:
                others = [x for x in humanPlayers if x != player]
                if Debug.sound:
                    logDebug('telling other human players that %s has voiceId %s' % (
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
        block = DeferredBlock(self, where='collectVoiceData')
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
                        'client %s wants voice data %s for %s' %
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
        block = DeferredBlock(self, where='sendVoiceData')
        for voiceDataRequester, voiceFor in voiceDataRequests:
            # this player requested sounds for voiceFor
            voice = voiceFor.voice
            content = voice.archiveContent
            if content:
                if Debug.sound:
                    logDebug(
                        'server got voice data %s for %s from client' %
                        (voiceFor.voice, voiceFor.name))
                block.tell(
                    voiceFor,
                    voiceDataRequester,
                    Message.VoiceData,
                    md5sum=voice.md5sum,
                    source=content)
            elif Debug.sound:
                logDebug('server got empty voice data %s for %s from client' % (
                    voice, voiceFor.name))
        block.callback(self.assignVoices)

    def assignVoices(self, unusedResults=None):
        """now all human players have all voice data needed"""
        humanPlayers = [
            x for x in self.game.players if isinstance(self.remotes[x], User)]
        block = DeferredBlock(self, where='assignVoices')
        block.tell(None, humanPlayers, Message.AssignVoices)
        block.callback(self.startHand)

    def pickTile(self, unusedResults=None, deadEnd=False):
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
            block = DeferredBlock(self, where='pickTile')
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
            # somebody robs my kong
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
                'player %s discarded %s but does not have it. He has %s' %
                (player, tile, player.concealedTiles))
            return
        dangerousText = self.game.dangerousFor(player, tile)
        mustPlayDangerous = player.mustPlayDangerous()
        violates = player.violatesOriginalCall(tile)
        self.game.hasDiscarded(player, tile)
        block = DeferredBlock(self, where='clientDiscarded')
        block.tellAll(player, Message.Discard, tile=tile)
        block.callback(self._clientDiscarded2, msg, dangerousText, mustPlayDangerous, violates)

    def _clientDiscarded2(self, unusedResults, msg, dangerousText, mustPlayDangerous, violates):
        """client told us he discarded a tile. Continue, check for violating original call"""
        block = DeferredBlock(self, where='_clientDiscarded2')
        player = msg.player
        if violates:
            if Debug.originalCall:
                tile = Tile(msg.args[0])
                logDebug('%s just violated OC with %s' % (player, tile))
            player.mayWin = False
            block.tellAll(player, Message.ViolatesOriginalCall)
        block.callback(self._clientDiscarded3, msg, dangerousText, mustPlayDangerous)

    def _clientDiscarded3(self, unusedResults, msg, dangerousText, mustPlayDangerous):
        """client told us he discarded a tile. Continue, check for calling"""
        block = DeferredBlock(self, where='_clientDiscarded3')
        player = msg.player
        if self.game.ruleset.mustDeclareCallingHand and not player.isCalling:
            if player.hand.callingHands:
                player.isCalling = True
                block.tellAll(player, Message.Calling)
        block.callback(self._clientDiscarded4, msg, dangerousText, mustPlayDangerous)

    def _clientDiscarded4(self, unusedResults, msg, dangerousText, mustPlayDangerous):
        """client told us he discarded a tile. Continue, check for dangerous game"""
        block = DeferredBlock(self, where='_clientDiscarded4')
        player = msg.player
        if dangerousText:
            if mustPlayDangerous and not player.lastSource.isDiscarded:
                if Debug.dangerousGame:
                    tile = Tile(msg.args[0])
                    logDebug('%s claims no choice. Discarded %s, keeping %s. %s' %
                             (player, tile, ''.join(player.concealedTiles), ' / '.join(dangerousText)))
                player.claimedNoChoice = True
                block.tellAll(
                    player,
                    Message.NoChoice,
                    tiles=TileTuple(player.concealedTiles))
            else:
                player.playedDangerous = True
                if Debug.dangerousGame:
                    tile = Tile(msg.args[0])
                    logDebug('%s played dangerous. Discarded %s, keeping %s. %s' %
                             (player, tile, ''.join(player.concealedTiles), ' / '.join(dangerousText)))
                block.tellAll(
                    player,
                    Message.DangerousGame,
                    tiles=TileTuple(player.concealedTiles))
        if msg.answer == Message.OriginalCall:
            player.isCalling = True
            block.callback(self.clientMadeOriginalCall, msg)
        else:
            block.callback(self._askForClaims, msg)

    def clientMadeOriginalCall(self, unusedResults, msg):
        """first tell everybody about original call
        and then treat the implicit discard"""
        msg.player.originalCall = True
        if Debug.originalCall:
            logDebug('server.clientMadeOriginalCall: %s' % msg.player)
        block = DeferredBlock(self, where='clientMadeOriginalCall')
        block.tellAll(msg.player, Message.OriginalCall)
        block.callback(self._askForClaims, msg)

    def startHand(self, unusedResults=None):
        """all players are ready to start a hand, so do it"""
        if self.running:
            self.game.prepareHand()
            self.game.initHand()
            block = self.tellAll(None, Message.InitHand,
                                 divideAt=self.game.divideAt)
            block.callback(self.divided)

    def divided(self, unusedResults=None):
        """the wall is now divided for all clients"""
        if not self.running:
            return
        block = DeferredBlock(self, where='divided')
        for clientPlayer in self.game.players:
            for player in self.game.players:
                if player == clientPlayer or self.game.playOpen:
                    tiles = player.concealedTiles
                else:
                    tiles = TileTuple(Tile.unknown * 13)
                block.tell(player, clientPlayer, Message.SetConcealedTiles,
                           tiles=TileTuple(chain(tiles, player.bonusTiles)))
        block.callback(self.dealt)

    def endHand(self, unusedResults=None):
        """hand is over, show all concealed tiles to all players"""
        if not self.running:
            return
        if self.game.playOpen:
            self.saveHand()
        else:
            block = DeferredBlock(self, where='endHand')
            for player in self.game.players:
                # there might be no winner, winner.others() would be wrong
                if player != self.game.winner:
                    # the winner tiles are already shown in claimMahJongg
                    block.tellOthers(
                        player, Message.ShowConcealedTiles, show=True,
                        tiles=TileTuple(player.concealedTiles))
            block.callback(self.saveHand)

    def saveHand(self, unusedResults=None):
        """save the hand to the database and proceed to next hand"""
        if not self.running:
            return
        self.tellAll(None, Message.SaveHand, self.nextHand)
        self.game.saveHand()

    def nextHand(self, unusedResults):
        """next hand: maybe rotate"""
        if not self.running:
            return
        DeferredBlock.garbageCollection()
        for block in DeferredBlock.blocks:
            if block.table == self:
                logError(
                    'request left from previous hand: %s' %
                    block.outstandingStr())
        token = self.game.handId.prompt(
            withAI=False)  # we need to send the old token until the
                                   # clients started the new hand
        rotateWinds = self.game.maybeRotateWinds()
        if self.game.finished():
            self.server.removeTable(
                self,
                'gameOver',
                i18nE('Game <numid>%1</numid> is over!'),
                self.game.seed)
            if Debug.process and os.name != 'nt':
                logDebug(
                    'MEM:%s' %
                    resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            return
        self.game.sortPlayers()
        playerNames = [(x.wind, x.name) for x in self.game.players]
        self.tellAll(None, Message.ReadyForHandStart, self.startHand,
                     playerNames=playerNames, rotateWinds=rotateWinds, token=token)

    def abort(self, message, *args):
        """abort the table. Reason: message/args"""
        self.server.removeTable(self, 'abort', message, *args)

    def claimTile(self, player, claim, meld, nextMessage):
        """a player claims a tile for pung, kong or chow.
        meld contains the claimed tile, concealed"""
        if not self.running:
            return
        assert meld.isConcealed
        lastDiscard = self.game.lastDiscard
        # if we rob a tile, self.game.lastDiscard has already been set to the
        # robbed tile
        discardingPlayer = self.game.activePlayer
        hasTiles = meld.without(lastDiscard)
        if len(meld) != 4 and not (meld.isPair or meld.isPungKong or meld.isChow):
            msg = i18nE('%1 wrongly said %2 for meld %3')
            self.abort(msg, player.name, claim.name, str(meld))
            return
        if not player.hasConcealedTiles(hasTiles):
            msg = i18nE(
                '%1 wrongly said %2: claims to have concealed tiles %3 but only has %4')
            self.abort(
                msg,
                player.name,
                claim.name,
                ' '.join(hasTiles),
                str(player.concealedTiles))
            return
        # update our internal state before we listen to the clients again
        self.game.discardedTiles[lastDiscard.exposed] -= 1
        self.game.activePlayer = player
        if lastDiscard:
            player.lastTile = lastDiscard.exposed
            player.lastSource = TileSource.LivingWallDiscard
        player.exposeMeld(hasTiles, lastDiscard)
        self.game.lastDiscard = None
        block = DeferredBlock(self, where='claimTile')
        if (nextMessage != Message.Kong
                and self.game.dangerousFor(discardingPlayer, lastDiscard)
                and discardingPlayer.playedDangerous):
            player.usedDangerousFrom = discardingPlayer
            if Debug.dangerousGame:
                logDebug('%s claims dangerous tile %s discarded by %s' %
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

    def declareKong(self, player, kongMeld):
        """player declares a Kong"""
        if not player.hasConcealedTiles(kongMeld) and kongMeld[0].exposed.pung not in player.exposedMelds:
            msg = i18nE('declareKong:%1 wrongly said Kong for meld %2')
            args = (player.name, str(kongMeld))
            logDebug(i18n(msg, *args))
            logDebug(
                'declareKong:concealedTiles:%s' %
                ''.join(player.concealedTiles))
            logDebug('declareKong:concealedMelds:%s' %
                     ' '.join(str(x) for x in player.concealedMelds))
            logDebug('declareKong:exposedMelds:%s' %
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
        if correct, tell all. Otherwise abort game, kajongg client is faulty"""
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
            player.robsTile()
            withDiscard = lastMove.meld[0].concealed
            lastMove.player.robTileFrom(withDiscard)
        msgArgs = player.showConcealedMelds(concealedMelds, withDiscard)
        if msgArgs:
            self.abort(*msgArgs)
            return
        player.declaredMahJongg(
            concealedMelds,
            withDiscard,
            player.lastTile,
            lastMeld)
        if not player.hand.won:
            msg = i18nE('%1 claiming MahJongg: This is not a winning hand: %2')
            self.abort(msg, player.name, player.hand.string)
            return
        block = DeferredBlock(self, where='claimMahJongg')
        if robbedTheKong:
            block.tellAll(player, Message.RobbedTheKong, tile=withDiscard)
        if (player.lastSource is TileSource.LivingWallDiscard
                and self.game.dangerousFor(discardingPlayer, player.lastTile)
                and discardingPlayer.playedDangerous):
            player.usedDangerousFrom = discardingPlayer
            if Debug.dangerousGame:
                logDebug('%s wins with dangerous tile %s from %s' %
                         (player, self.game.lastDiscard, discardingPlayer))
            block.tellAll(
                player,
                Message.UsedDangerousFrom,
                source=discardingPlayer.name)
        block.tellAll(
            player, Message.MahJongg, melds=concealedMelds, lastTile=player.lastTile,
            lastMeld=lastMeld, withDiscardTile=withDiscard)
        block.callback(self.endHand)

    def dealt(self, unusedResults):
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
        """return only requests we want to execute"""
        if not self.running:
            return None
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

    def _askForClaims(self, unusedRequests, unusedMsg):
        """ask all players if they want to claim"""
        if self.running:
            self.tellOthers(
                self.game.activePlayer,
                Message.AskForClaims,
                self.moved)

    def processAnswers(self, requests):
        """a player did something"""
        if not self.running:
            return None
        answers = self.prioritize(requests)
        if not answers:
            return None
        for answer in answers:
            msg = '<-  %s' % answer
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
                logDebug('stack size:%d' % len(stck))
                logDebug(stck)
        answers = self.processAnswers(requests)
        if not answers:
            self.nextTurn()

    def tellAll(self, player, command, callback=None, **kwargs):
        """tell something about player to all players"""
        block = DeferredBlock(self, where='tellAll: Player {} command {} kwargs {}'.format(player, command, kwargs))
        block.tellAll(player, command, **kwargs)
        block.callback(callback)
        return block

    def tellOthers(self, player, command, callback=None, **kwargs):
        """tell something about player to all other players"""
        block = DeferredBlock(self, where='tellOthers')
        block.tellOthers(player, command, **kwargs)
        block.callback(callback)
        return block
