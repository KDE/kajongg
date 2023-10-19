# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

import datetime
import weakref

from twisted.spread import pb
from twisted.internet.task import deferLater
from twisted.internet.defer import Deferred, succeed, fail
from util import Duration
from log import logDebug, logException, logWarning
from mi18n import i18nc
from message import Message
from common import Internal, Debug, Options, ReprMixin
from common import isAlive
from tilesource import TileSource
from rule import Ruleset
from game import PlayingGame
from query import Query
from move import Move
from animation import animate, animateAndDo
from player import PlayingPlayer

import intelligence
import altint


class Table(ReprMixin):

    """defines things common to both ClientTable and ServerTable"""

    def __init__(self, tableid, ruleset, suspendedAt,
                 running, playOpen, autoPlay, wantedGame):
        self.tableid = tableid
        if isinstance(ruleset, Ruleset):
            self.ruleset = ruleset
        else:
            self.ruleset = Ruleset.cached(ruleset)
        self.suspendedAt = suspendedAt
        self.running = running
        self.playOpen = playOpen
        self.autoPlay = autoPlay
        self.wantedGame = wantedGame

    def status(self):
        """a status string"""
        result = ''
        if self.suspendedAt:
            result = i18nc('table status', 'Suspended')
            result += ' ' + datetime.datetime.strptime(
                self.suspendedAt,
                '%Y-%m-%dT%H:%M:%S').strftime('%c')
        if self.running:
            result += ' ' + i18nc('table status', 'Running')
        return result or i18nc('table status', 'New')

    def __str__(self):
        return 'Table({})'.format(self.tableid)


class ClientTable(Table):

    """the table as seen by the client"""
    # pylint: disable=too-many-arguments

    def __init__(self, client, tableid, ruleset, gameid, suspendedAt, running,
                 playOpen, autoPlay, wantedGame, playerNames,
                 playersOnline, endValues):
        Table.__init__(
            self,
            tableid,
            ruleset,
            suspendedAt,
            running,
            playOpen,
            autoPlay,
            wantedGame)
        self.client = client
        self.gameid = gameid
        self.playerNames = playerNames
        self.playersOnline = playersOnline
        self.endValues = endValues
        self.myRuleset = None  # if set, points to an identical local ruleset
        for myRuleset in Ruleset.availableRulesets():
            if myRuleset == self.ruleset:
                self.myRuleset = myRuleset
                break
        self.chatWindow = None

    def isOnline(self, player):
        """did he join the tabled?"""
        for idx, name in enumerate(self.playerNames):
            if player == name:
                return self.playersOnline[idx]
        return False

    def __str__(self):
        onlineNames = [x for x in self.playerNames if self.isOnline(x)]
        offlineString = ''
        offlineNames = [
            x for x in self.playerNames if x not in onlineNames
            and not x.startswith('Robot')]
        if offlineNames:
            offlineString = ' offline:' + ','.join(offlineNames)
        return '%d(%s %s%s)' % (self.tableid, self.ruleset.name, ','.join(onlineNames), offlineString)

    def gameExistsLocally(self):
        """True if the game exists in the data base of the client"""
        assert self.gameid
        return bool(Query('select 1 from game where id=?', (self.gameid,)).records)


class Client(pb.Referenceable):

    """interface to the server. This class only implements the logic,
    so we can also use it on the server for robot clients. Compare
    with HumanClient(Client)"""

    def __init__(self, name=None):
        """name is something like Robot 1 or None for the game server"""
        self.name = name
        self.game = None
        self.__connection = None
        self.tables = []
        self._table = None
        self.tableList = None

    @property
    def table(self):
        """hide weakref"""
        if self._table:
            return self._table()
        return None

    @table.setter
    def table(self, value):
        """hide weakref"""
        if value is not None:
            self._table = weakref.ref(value)

    @property
    def connection(self):
        """update main window title if needed"""
        return self.__connection

    @connection.setter
    def connection(self, value):
        """update main window title if needed"""
        if self.__connection != value:
            self.__connection = value
            if Internal.scene:
                Internal.scene.mainWindow.updateGUI()

    def _tableById(self, tableid):
        """return table with tableid"""
        for table in self.tables:
            if table.tableid == tableid:
                return table
        return None

    def logout(self, unusedResult=None):
        """virtual"""
        return succeed(None)

    def isRobotClient(self):
        """avoid using isinstance because that imports too much for the server"""
        return bool(self.name)

    @staticmethod
    def isHumanClient():
        """avoid using isinstance because that imports too much for the server"""
        return False

    def isServerClient(self):
        """avoid using isinstance because that imports too much for the server"""
        return bool(not self.name)

    def remote_newTables(self, tables):
        """update table list"""
        newTables = [ClientTable(self, *x) for x in tables]
        self.tables.extend(newTables)
        if Debug.table:
            _ = ', '.join(str(ClientTable(self, *x)) for x in tables)
            logDebug('%s got new tables:%s' % (self.name, _))

    @staticmethod
    def remote_serverRulesets(hashes):
        """the server will normally send us hashes of rulesets. If
        a hash is not known by us, tell the server so it will send the
        full ruleset definition instead of the hash. It would be even better if
        the server always only sends the hash and the client then says "I do
        not know this ruleset, please send definition", but that would mean
        more changes to the client code"""
        return [x for x in hashes if not Ruleset.hashIsKnown(x)]

    def tableChanged(self, table):
        """update table list"""
        newTable = ClientTable(self, *table)
        oldTable = self._tableById(newTable.tableid)
        if oldTable:
            self.tables.remove(oldTable)
            self.tables.append(newTable)  # FIXME: I think indent is wrong
        return oldTable, newTable

    def remote_tableRemoved(self, tableid, message, *args):  # pylint: disable=unused-argument
        """update table list"""
        table = self._tableById(tableid)
        if table:
            self.tables.remove(table)

    def reserveGameId(self, gameid):
        """the game server proposes a new game id. We check if it is available
        in our local data base - we want to use the same gameid everywhere"""
        with Internal.db:
            assert self.connection
            query = Query('insert into game(id,seed) values(?,?)',
                          (gameid, self.connection.url), mayFail=True, failSilent=True)
            if query.rowcount() != 1:
                return Message.NO
        return Message.OK

    @staticmethod
    def __findAI(modules, aiName):
        """list of all alternative AIs defined in altint.py"""
        for module in modules:
            for key, value in module.__dict__.items():
                if key == 'AI' + aiName:
                    return value
        return None

    def __assignIntelligence(self):
        """assign intelligence to myself. All players already have default intelligence."""
        if self.isHumanClient():
            assert self.game
            aiClass = self.__findAI([intelligence, altint], Options.AI)
            if not aiClass:
                raise ValueError('intelligence %s is undefined' % Options.AI)
            self.game.myself.intelligence = aiClass(self.game.myself)

    def readyForGameStart(
            self, tableid, gameid, wantedGame, playerNames, shouldSave=True, gameClass=None):
        """the game server asks us if we are ready. A robot is always ready."""
        def disagree(about):
            """do not bother to translate this, it should normally not happen"""
            assert self.game  # mypy should be able to infer this
            self.game.close()
            msg = 'The data bases for game %s have different %s' % (
                self.game.seed, about)
            logWarning(msg)
            raise pb.Error(msg)
        if not self.table:
            assert not self.isRobotClient()
            self.table = self._tableById(tableid)
        else:
            assert self.isRobotClient()
            # robot client instance: self.table is already set
        assert self.table
        if gameClass is None:
            gameClass = PlayingGame
        if self.table.suspendedAt:
            self.game = gameClass.loadFromDB(gameid, self)
            assert self.game, 'cannot load game {}'.format(gameid)
            self.game.assignPlayers(playerNames)
            if self.isHumanClient():
                if self.game.handctr != self.table.endValues[0]:
                    disagree('numbers for played hands: Server:%s, Client:%s' % (
                        self.table.endValues[0], self.game.handctr))
                for player in self.game.players:
                    if player.balance != self.table.endValues[1][player.wind.char]:
                        disagree('balances for wind %s: Server:%s, Client:%s' % (
                            player.wind, self.table.endValues[1][player.wind], player.balance))
        else:
            self.game = gameClass(playerNames, self.table.ruleset,
                                  gameid=gameid, wantedGame=wantedGame, client=self,
                                  playOpen=self.table.playOpen, autoPlay=self.table.autoPlay)
            assert self.game, 'cannot initialize game {}'.format(gameid)
        self.game.shouldSave = shouldSave
        self.__assignIntelligence()
                                  # intelligence variant is not saved for
                                  # suspended games
        self.game.prepareHand()
        return succeed(Message.OK)

    def readyForHandStart(self, playerNames, rotateWinds):
        """the game server asks us if we are ready. A robot is always ready..."""
        if self.game:
            self.game.assignPlayers(playerNames)
            if rotateWinds:
                self.game.rotateWinds()
            self.game.prepareHand()

    def __delayAnswer(self, result, delay, delayStep):
        """try again, may we chow now?"""
        if not self.game:
            # game has been aborted meanwhile
            return result
        noClaimCount = 0
        delay += delayStep
        for move in self.game.lastMoves():
            # latest move first
            if move.message == Message.Discard:
                break
            if move.message == Message.NoClaim and move.notifying:
                noClaimCount += 1
                if noClaimCount == 2:
                    if Debug.delayChow and self.game.lastDiscard:
                        self.game.debug('everybody said "I am not interested", so {} claims chow now for {}'.format(
                            self.game.myself.name, self.game.lastDiscard.name()))
                    return result
            elif move.message in (Message.Pung, Message.Kong, Message.MahJongg) and move.notifying:
                if Debug.delayChow and self.game.lastDiscard:
                    self.game.debug('{} said {} so {} suppresses Chow for {}'.format(
                        move.player, move.message, self.game.myself, self.game.lastDiscard.name()).replace('  ', ' '))
                return Message.NoClaim
        if delay < self.game.ruleset.claimTimeout * 0.95:
            # one of those slow humans is still thinking
            return deferLater(Internal.reactor, delayStep, self.__delayAnswer, result, delay, delayStep)
        if Debug.delayChow and self.game.lastDiscard:
            self.game.debug('{} must chow now for {} because timeout is over'.format(
                self.game.myself.name, self.game.lastDiscard.name()))
        return result

    def ask(self, move, answers):
        """place the robot AI here.
        send answer and one parameter to server"""
        delay = 0.0
        delayStep = 0.1
        assert self.game
        myself = self.game.myself
        myself.computeSayable(move, answers)
        result = myself.intelligence.selectAnswer(answers)
        assert result
        if result[0] == Message.Chow:
            if Debug.delayChow and self.game.lastDiscard:
                self.game.debug('{} waits to see if somebody says Pung or Kong before saying chow for {}'.format(
                    self.game.myself.name, self.game.lastDiscard.name()))
            return deferLater(Internal.reactor, delayStep, self.__delayAnswer, result, delay, delayStep)
        return succeed(result)

    def thatWasMe(self, player):
        """return True if player == myself"""
        if not self.game:
            return False
        return player == self.game.myself

    @staticmethod
    def __jellyMessage(value):
        """the Message classes are not pb.copyable, convert them into their names"""
        return Message.OK.name if value is None else Message.jelly(value, value)

    def remote_move(self, playerName, command, *unusedArgs, **kwargs):
        """the server sends us info or a question and always wants us to answer"""
        if Internal.scene and not isAlive(Internal.scene):
            return fail()
        if self.game:
            player = self.game.playerByName(playerName)
        elif playerName:
            player = PlayingPlayer(None, playerName)
        else:
            player = None
        move = Move(player, command, kwargs)
        if Debug.traffic:
            if self.isHumanClient():
                if self.game:
                    self.game.debug('got Move: {!r}'.format(move))
                else:
                    logDebug('got Move: {!r}'.format(move))
        if self.game:
            if move.token:
                if move.token != self.game.handId.token():
                    logException(
                        'wrong token: %s, we have %s' %
                        (move.token, self.game.handId.token()))
        with Duration('Move {!r}:'.format(move)):
            return self.exec_move(move).addCallback(self.__jellyMessage)

    def exec_move(self, move):
        """mirror the move of a player as told by the game server"""
        message = move.message
        if message.needsGame and not self.game:
            # server already disconnected, see
            # HumanClient.remote_ServerDisconnects
            return succeed(Message.OK)
        action = message.notifyAction if move.notifying else message.clientAction
        game = self.game
        if game:
            game.moves.append(move)
        answer = action(self, move)
        if not isinstance(answer, Deferred):
            answer = succeed(answer)
        if game:
            if not move.notifying and move.player and not move.player.scoreMatchesServer(move.score):
                game.close()
# This is an example how to find games where specific situations arise. We prefer games where this
# happens very early for easier reproduction. So set number of rounds to 1 in the ruleset before doing this.
# This example looks for a situation where the single human player may call Chow but one of the
# robot players calls Pung. See https://bugs.kde.org/show_bug.cgi?id=318981
#            if game.nextPlayer() == game.myself:
# I am next
#                if message == Message.Pung and move.notifying:
# somebody claimed a pung
#                    if move.player != game.myself:
# it was not me
#                        if game.handctr == 0 and len(game.moves) < 30:
# early on in the game
#                            game.myself.computeSayable(move, [Message.Chow])
#                            if game.myself.sayable[Message.Chow]:
# I may say Chow
#                                logDebug('FOUND EXAMPLE FOR %s IN %s' % (game.myself,
#                                       game.handId.prompt(withMoveCount=True)))

        if message == Message.Discard:
            # do not block here, we want to get the clientDialog
            # before the animated tile reaches its end position
            animate()
            return answer
        if message == Message.AskForClaims:
            # no need to start an animation. If we did the below standard clause, this is what
            # could happen:
            # 1. user says Chow
            # 2. SelectChow dialog pops up
            # 3. previous animation ends, making animate() callback with current answer
            # 4. but this answer is Chow, without a selected Chow. This is
            # wrongly sent to server
            return answer
        # return answer only after animation ends. Put answer into
        # the Deferred returned by animate().
        return animate().addCallback(lambda x: answer)

    def claimed(self, move):
        """somebody claimed a discarded tile"""
        assert self.game
        if Internal.scene:
            calledTileItem = Internal.scene.discardBoard.claimDiscard()
            calledTile = calledTileItem.tile
        else:
            calledTileItem = None
            assert self.game.lastDiscard
            calledTile = self.game.lastDiscard
        self.game.lastDiscard = None
        assert calledTile
        self.game.discardedTiles[calledTile.exposed] -= 1
        assert move.meld, 'move has no meld: {!r}'.format(move)
        assert calledTile in move.meld, '%s %s' % (calledTile, move.meld)
        hadTiles = move.meld.without(calledTile)
        assert move.player
        if not self.thatWasMe(move.player) and not self.game.playOpen:
            move.player.showConcealedTiles(hadTiles)
        move.player.lastTile = calledTile.exposed
        move.player.lastSource = TileSource.LivingWallDiscard
        move.exposedMeld = move.player.exposeMeld(
            hadTiles,
            calledTile=calledTileItem or calledTile)

        if self.thatWasMe(move.player):
            if move.message != Message.Kong:
                # we will get a replacement tile first
                return self.myAction(move)
        elif self.game.prevActivePlayer == self.game.myself and self.connection:
            # even here we ask: if our discard is claimed we need time
            # to notice - think 3 robots or network timing differences
            return self.ask(move, [Message.OK])
        return None

    def myAction(self, move):
        """ask myself what I want to do after picking or claiming a tile"""
        # only when all animations ended, our handboard gets focus. Otherwise
        # we would see a blue focusRect in the handboard even when a tile
        # ist still moving from the discardboard to the handboard.
        assert move.player
        animateAndDo(move.player.getsFocus)
        possibleAnswers = [Message.Discard, Message.Kong, Message.MahJongg]
        if not move.player.discarded:
            possibleAnswers.append(Message.OriginalCall)
        return self.ask(move, possibleAnswers)

    def declared(self, move):
        """somebody declared something.
        By declaring we mean exposing a meld, using only tiles from the hand.
        For now we only support Kong: in Classical Chinese it makes no sense
        to declare a Pung."""
        # FIXME: need a test case
        assert move.message == Message.Kong
        assert self.game
        assert move.player
        if not self.thatWasMe(move.player) and not self.game.playOpen:
            move.player.showConcealedTiles(move.source)
        move.exposedMeld = move.player.exposeMeld(move.source)
        if not self.thatWasMe(move.player):
            self.ask(move, [Message.OK])

    def __str__(self):
        assert self.name
        return self.name
