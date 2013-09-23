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
"""

import datetime

from PyQt4.QtCore import QTimer
from twisted.spread import pb
from twisted.internet import reactor
from twisted.internet.task import deferLater
from twisted.internet.defer import Deferred, succeed, DeferredList
from twisted.internet.error import ReactorNotRunning
from twisted.python.failure import Failure
from util import logDebug, logException, logWarning, Duration, m18nc
from message import Message
from common import Internal, Debug
from rule import Ruleset
from meld import meldsContent
from game import RemoteGame
from query import Transaction, Query
from move import Move
from animation import animate
from intelligence import AIDefault
from statesaver import StateSaver
from player import Player

class Table(object):
    """defines things common to both ClientTable and ServerTable"""
    def __init__(self, tableid, ruleset, suspendedAt, running, playOpen, autoPlay, wantedGame):
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
            result = m18nc('table status', 'Suspended')
            result += ' ' + datetime.datetime.strptime(self.suspendedAt,
                '%Y-%m-%dT%H:%M:%S').strftime('%c').decode('utf-8')
        if self.running:
            result += ' ' + m18nc('table status', 'Running')
        return result or m18nc('table status', 'New')

class ClientTable(Table):
    """the table as seen by the client"""
    # pylint: disable=R0902
    # pylint: disable=R0913
    # pylint says too many args, too many instance variables

    def __init__(self, client, tableid, ruleset, gameid, suspendedAt, running,
                 playOpen, autoPlay, wantedGame, playerNames,
                 playersOnline, endValues):
        Table.__init__(self, tableid, ruleset, suspendedAt, running, playOpen, autoPlay, wantedGame)
        self.client = client
        self.gameid = gameid
        self.playerNames = playerNames
        self.playersOnline = playersOnline
        self.endValues = endValues
        self.myRuleset = None # if set, points to an identical local ruleset
        allRulesets =  Ruleset.availableRulesets()
        for myRuleset in allRulesets:
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
        onlineNames = list(x for x in self.playerNames if self.isOnline(x))
        offlineString = ''
        offlineNames = list(x for x in self.playerNames if x not in onlineNames
            and not x.startswith('Robot'))
        if offlineNames:
            offlineString = ' offline:' + ','.join(offlineNames)
        return '%d(%s %s%s)' % (self.tableid, self.ruleset.name, ','.join(onlineNames), offlineString)

    def __repr__(self):
        return 'ClientTable(%s)' % str(self)

    def gameExistsLocally(self):
        """does the game exist in the data base of the client?"""
        assert self.gameid
        return bool(Query('select 1 from game where id=?', list([self.gameid])).records)

class Client(object, pb.Referenceable):
    """interface to the server. This class only implements the logic,
    so we can also use it on the server for robot clients. Compare
    with HumanClient(Client)"""

    clients = []

    def __init__(self, username=None, intelligence=AIDefault):
        """username is something like Robot 1 or None for the game server"""
        self.username = username
        self.game = None
        self.intelligence = intelligence(self)
        self.__connection = None
        self.tables = []
        self.table = None
        self.tableList = None
        self.sayable = {} # recompute for each move, use as cache
        self.clients.append(self)

    @property
    def connection(self):
        """update main window title if needed"""
        return self.__connection

    @connection.setter
    def connection(self, value):
        """update main window title if needed"""
        if self.__connection != value:
            self.__connection = value
            if Internal.field:
                Internal.field.updateGUI()

    def _tableById(self, tableid):
        """returns table with tableid"""
        for table in self.tables:
            if table.tableid == tableid:
                return table

    @staticmethod
    def shutdownClients(exception=None):
        """close connections to servers except maybe one"""
        clients = Client.clients
        def done():
            """return True if clients is cleaned"""
            return len(clients) == 0 or (exception and clients == [exception])
        def disconnectedClient(dummyResult, client):
            """now the client is really disconnected from the server"""
            if client in clients:
                # HumanClient.serverDisconnects also removes it!
                clients.remove(client)
        if isinstance(exception, Failure):
            logException(exception)
        for client in clients[:]:
            if client.tableList:
                client.tableList.hide()
        if done():
            return succeed(None)
        deferreds = []
        for client in clients[:]:
            if client != exception and client.connection:
                deferreds.append(client.logout().addCallback(disconnectedClient, client))
        return DeferredList(deferreds)

    @staticmethod
    def quitProgram(result=None):
        """now all connections to servers are cleanly closed"""
        if isinstance(result, Failure):
            logException(result)
        try:
            Internal.reactor.stop()
        except ReactorNotRunning:
            pass
        StateSaver.saveAll()
        field = Internal.field
        if field:
            # if we have the ruleset editor visible, we get:
            # File "/hdd/pub/src/gitgames/kajongg/src/rulesetselector.py", line 194, in headerData
            #  if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            #  AttributeError: 'NoneType' object has no attribute 'DisplayRole'
            # how can Qt get None? Same happens with QEvent, see statesaver.py
            if field.confDialog:
                field.confDialog.hide()
            field.hide() # do not make the user see the delay for stopping the reactor
        # we may be in a Deferred callback which would
        # catch sys.exit as an exception
        # and the qt4reactor does not quit the app when being stopped
        Internal.quitWaitTime = 0
        QTimer.singleShot(10, Client.appquit)

    @staticmethod
    def appquit():
        """retry until the reactor really stopped"""
        if Internal.reactor.running:
            Internal.quitWaitTime += 10
            if Internal.quitWaitTime % 1000 == 0:
                logDebug('waiting since %d seconds for reactor to stop' % (Internal.quitWaitTime // 1000))
            QTimer.singleShot(10, Client.appquit)
        else:
            if Internal.quitWaitTime > 1000:
                logDebug('reactor stopped after %d seconds' % (Internal.quitWaitTime // 1000))
            Internal.app.quit()

    def logout(self, dummyResult=None): # pylint: disable=R0201
        """virtual"""
        return succeed(None)

    def isRobotClient(self):
        """avoid using isinstance because that imports too much for the server"""
        return bool(self.username)

    @staticmethod
    def isHumanClient():
        """avoid using isinstance because that imports too much for the server"""
        return False

    def isServerClient(self):
        """avoid using isinstance because that imports too much for the server"""
        return bool(not self.username)

    def remote_newTables(self, tables):
        """update table list"""
        newTables = list(ClientTable(self, *x) for x in tables) # pylint: disable=W0142
        self.tables.extend(newTables)
        if Debug.table:
            logDebug('%s got new tables:%s' % (self.username, newTables))

    @staticmethod
    def remote_serverRulesets(hashes):
        """the server will normally send us hashes of rulesets. If
        a hash is not known by us, tell the server so it will send the
        full ruleset definition instead of the hash. It would be even better if
        the server always only sends the hash and the client then says "I do
        not know this ruleset, please send definition", but that would mean
        more changes to the client code"""
        return list(x for x in hashes if not Ruleset.hashIsKnown(x))

    def remote_tableChanged(self, table):
        """update table list"""
        newClientTable = ClientTable(self, *table) # pylint: disable=W0142
        oldTable = self._tableById(newClientTable.tableid)
        if oldTable:
            self.tables.remove(oldTable)
            self.tables.append(newClientTable)

    def remote_tableRemoved(self, tableid, dummyMsg, *dummyMsgArgs):
        """update table list"""
        table = self._tableById(tableid)
        if table:
            self.tables.remove(table)

    def reserveGameId(self, gameid):
        """the game server proposes a new game id. We check if it is available
        in our local data base - we want to use the same gameid everywhere"""
        with Transaction():
            query = Query('insert into game(id,seed) values(?,?)',
                      list([gameid, self.connection.url]), mayFail=True)
            if query.rowcount() != 1:
                return Message.NO
        return Message.OK

    def readyForGameStart(self, tableid, gameid, wantedGame, playerNames, shouldSave=True):
        """the game server asks us if we are ready. A robot is always ready."""
        def disagree(about):
            """do not bother to translate this, it should normally not happen"""
            self.game.close()
            msg = 'The data bases for game %s have different %s' % (self.game.seed, about)
            logWarning(msg)
            raise pb.Error(msg)
        if self.isHumanClient():
            assert not self.table
            assert self.tables
            self.table = self._tableById(tableid)
            if not self.table:
                raise pb.Error('client.readyForGameStart: tableid %d unknown' % tableid)
        if self.table.suspendedAt:
            self.game = RemoteGame.loadFromDB(gameid, self)
            self.game.assignPlayers(playerNames)
            if self.isHumanClient():
                if self.game.handctr != self.table.endValues[0]:
                    disagree('numbers for played hands: Server:%s, Client:%s' % (
                        self.table.endValues[0], self.game.handctr))
                for player in self.game.players:
                    if player.balance != self.table.endValues[1][player.wind]:
                        disagree('balances for wind %s: Server:%s, Client:%s' % (
                            player.wind, self.table.endValues[1][player.wind], player.balance))
        else:
            self.game = RemoteGame(playerNames, self.table.ruleset,
                shouldSave=shouldSave, gameid=gameid, wantedGame=wantedGame, client=self,
                playOpen=self.table.playOpen, autoPlay=self.table.autoPlay)
        self.game.prepareHand()
        return succeed(Message.OK)

    def readyForHandStart(self, playerNames, rotateWinds):
        """the game server asks us if we are ready. A robot is always ready..."""
        self.game.assignPlayers(playerNames)
        if rotateWinds:
            self.game.rotateWinds()
        self.game.prepareHand()

    def ask(self, move, answers):
        """this is where the robot AI should go.
        sends answer and one parameter to server"""
        delay = 0.0
        delayStep = 0.1
        def delayed(result, delay):
            """try again, may we chow now?"""
            noClaimCount = 0
            delay += delayStep
            for move in self.game.lastMoves():
                # latest move first
                if move.message == Message.Discard:
                    break
                elif move.message == Message.NoClaim and move.notifying:
                    noClaimCount += 1
                    if noClaimCount == 2:
                        # self.game.debug('everybody said "I am not interested", so %s claims chow now' %
                        #     self.game.myself.name)
                        return result
                elif move.message in (Message.Pung, Message.Kong) and move.notifying:
                    # self.game.debug('somebody said Pung or Kong, so %s suppresses Chow' % self.game.myself.name)
                    return Message.NoClaim
            if delay < self.game.ruleset.claimTimeout * 0.95:
                # one of those slow humans is still thinking
                return deferLater(reactor, delayStep, delayed, result, delay)
            # self.game.debug('%s must chow now because timeout is over' % self.game.myself.name)
            return result
        self._computeSayable(move, answers)
        result = self.intelligence.selectAnswer(answers)
        if result[0] == Message.Chow:
            # self.game.debug('%s waits to see if somebody says Pung or Kong before saying chow' %
            #     self.game.myself.name)
            return deferLater(reactor, delayStep, delayed, result, delay)
        return succeed(result)

    def thatWasMe(self, player):
        """returns True if player == myself"""
        if not self.game:
            return False
        return player == self.game.myself

    @staticmethod
    def __convertMessage(value):
        """the Message classes are not pb.copyable, convert them into their names"""
        if isinstance(value, Message):
            return value.name
        if isinstance(value, tuple) and isinstance(value[0], Message):
            if value[1] == None or value[1] == []:
                return value[0].name
            else:
                return tuple(list([value[0].name] + list(value[1:])))
        assert value is None, 'strange value:%s' % str(value)
        return Message.OK.name

    def remote_move(self, playerName, command, *dummyArgs, **kwargs):
        """the server sends us info or a question and always wants us to answer"""
        if self.game:
            player = self.game.playerByName(playerName)
        elif playerName:
            player = Player(None)
            player.name = playerName
        else:
            player = None
        move = Move(player, command, kwargs)
        if Debug.traffic:
            if self.isHumanClient():
                if self.game:
                    self.game.debug('got Move: %s' % move)
                else:
                    logDebug('got Move: %s' % move)
        if self.game:
            self.game.checkTarget()
            if move.token:
                if move.token != self.game.handId(withAI=False):
                    logException( 'wrong token: %s, we have %s' % (move.token, self.game.handId()))
        with Duration('Move %s:' % move):
            return self.exec_move(move).addCallback(self.__convertMessage)

    def exec_move(self, move):
        """mirror the move of a player as told by the the game server"""
        message = move.message
        if message.needsGame and not self.game:
            # server already disconnected, see HumanClient.remote_ServerDisconnects
            return succeed(Message.OK)
        action = message.notifyAction if move.notifying else message.clientAction
        answer = action(self, move)
        if not isinstance(answer, Deferred):
            answer = succeed(answer)
        game = self.game
        if game:
            if not move.notifying and move.player and not move.player.scoreMatchesServer(move.score):
                game.close()
            game.moves.append(move)
# This is an example how to find games where specific situations arise. We prefer games where this
# happens very early for easier reproduction. So set number of rounds to 1 in the ruleset before doing this.
# This example looks for a situation where the single human player may call Chow but one of the
# robot players calls Pung. See https://bugs.kde.org/show_bug.cgi?id=318981
#            if self.isHumanClient() and game.nextPlayer() == game.myself:
#                # I am next
#                if message == Message.Pung and move.notifying:
#                    # somebody claimed a pung
#                    if move.player != game.myself:
#                        # it was not me
#                        if game.handctr == 0 and len(game.moves) < 30:
#                            # early on in the game
#                            if self.__maySayChow():
#                                # I may say Chow
#                                print('FOUND EXAMPLE IN:', game.handId(withMoveCount=True))

        if message == Message.Discard:
            # do not block here, we want to get the clientDialog
            # before the animated tile reaches its end position
            animate()
            return answer
        elif message == Message.AskForClaims:
            # no need to start an animation. If we did the below standard clause, this is what
            # could happen:
            # 1. user says Chow
            # 2. SelectChow dialog pops up
            # 3. previous animation ends, making animate() callback with current answer
            # 4. but this answer is Chow, without a selected Chow. This is wrongly sent to server
            return answer
        else:
            # return answer only after animation ends. Put answer into
            # the Deferred returned by animate().
            return animate().addCallback(lambda x: answer)

    def claimed(self, move):
        """somebody claimed a discarded tile"""
        calledTile = self.game.lastDiscard
        self.game.lastDiscard = None
        calledTileName = calledTile.element
        self.game.discardedTiles[calledTileName.lower()] -= 1
        assert calledTileName in move.source, '%s %s'% (calledTileName, move.source)
        if Internal.field:
            Internal.field.discardBoard.lastDiscarded = None
        move.player.lastTile = calledTileName.lower()
        move.player.lastSource = 'd'
        hadTiles = move.source[:]
        hadTiles.remove(calledTileName)
        if not self.thatWasMe(move.player) and not self.game.playOpen:
            move.player.showConcealedTiles(hadTiles)
        move.exposedMeld = move.player.exposeMeld(hadTiles, calledTile=calledTile)
        if self.thatWasMe(move.player):
            if move.message != Message.Kong:
                # we will get a replacement tile first
                return self.myAction(move)
        elif self.game.prevActivePlayer == self.game.myself and self.connection:
            # even here we ask: if our discard is claimed we need time
            # to notice - think 3 robots or network timing differences
            return self.ask(move, [Message.OK])

    def myAction(self, move):
        """ask myself what I want to do after picking or claiming a tile"""
        # only when all animations ended, our handboard gets focus. Otherwise
        # we would see a blue focusRect in the handboard even when a tile
        # ist still moving from the discardboard to the handboard.
        animate().addCallback(move.player.getsFocus)
        possibleAnswers = [Message.Discard, Message.Kong, Message.MahJongg]
        if not move.player.discarded:
            possibleAnswers.append(Message.OriginalCall)
        return self.ask(move, possibleAnswers)

    def declared(self, move):
        """somebody declared something.
        By declaring we mean exposing a meld, using only tiles from the hand.
        For now we only support Kong: in Classical Chinese it makes no sense
        to declare a Pung."""
        assert move.message == Message.Kong
        if not self.thatWasMe(move.player) and not self.game.playOpen:
            move.player.showConcealedTiles(move.source)
        move.exposedMeld = move.player.exposeMeld(move.source)
        if not self.thatWasMe(move.player):
            self.ask(move, [Message.OK])

    def __maySayChow(self):
        """returns answer arguments for the server if calling chow is possible.
        returns the meld to be completed"""
        if self.game.myself == self.game.nextPlayer():
            return self.game.myself.possibleChows()

    def __maySayPung(self):
        """returns answer arguments for the server if calling pung is possible.
        returns the meld to be completed"""
        if self.game.lastDiscard:
            element = self.game.lastDiscard.element
            assert element[0].isupper(), str(self.game.lastDiscard)
            if self.game.myself.concealedTileNames.count(element) >= 2:
                return [element] * 3

    def __maySayKong(self):
        """returns answer arguments for the server if calling or declaring kong is possible.
        returns the meld to be completed or to be declared"""
        return self.game.myself.possibleKongs()

    def __maySayMahjongg(self, move):
        """returns answer arguments for the server if calling or declaring Mah Jongg is possible"""
        game = self.game
        myself = game.myself
        robbableTile = withDiscard = None
        if move.message == Message.DeclaredKong:
            withDiscard = move.source[0].capitalize()
            if move.player != myself:
                robbableTile = move.exposedMeld.pairs[1] # we want it capitalized for a hidden Kong
        elif move.message == Message.AskForClaims:
            withDiscard = game.lastDiscard.element
        hand = myself.computeHand(withTile=withDiscard, robbedTile=robbableTile, asWinner=True)
        if hand.won:
            if Debug.robbingKong:
                if move.message == Message.DeclaredKong:
                    game.debug('%s may rob the kong from %s/%s' % \
                       (myself, move.player, move.exposedMeld.joined))
            if Debug.mahJongg:
                game.debug('%s may say MJ:%s, active=%s' % (
                    myself, list(x for x in game.players), game.activePlayer))
            return (meldsContent(hand.hiddenMelds), withDiscard, list(hand.lastMeld.pairs))

    def __maySayOriginalCall(self):
        """returns True if Original Call is possible"""
        myself = self.game.myself
        for tileName in set(myself.concealedTileNames):
            if (myself.hand - tileName).callingHands():
                if Debug.originalCall:
                    self.game.debug('%s may say Original Call' % myself)
                return True

    def _computeSayable(self, move, answers):
        """find out what the player can legally say with this hand"""
        self.sayable = {}
        for message in Message.defined.values():
            self.sayable[message] = True
        if Message.Pung in answers:
            self.sayable[Message.Pung] = self.__maySayPung()
        if Message.Chow in answers:
            self.sayable[Message.Chow] = self.__maySayChow()
        if Message.Kong in answers:
            self.sayable[Message.Kong] = self.__maySayKong()
        if Message.MahJongg in answers:
            self.sayable[Message.MahJongg] = self.__maySayMahjongg(move)
        if Message.OriginalCall in answers:
            self.sayable[Message.OriginalCall] = self.__maySayOriginalCall()

    def maybeDangerous(self, msg):
        """could answering with msg lead to dangerous game?
        If so return a list of resulting melds
        where a meld is represented by a list of 2char strings"""
        result = []
        if msg in (Message.Chow, Message.Pung, Message.Kong):
            possibleMelds = self.sayable[msg]
            if isinstance(possibleMelds[0], basestring):
                possibleMelds = [possibleMelds]
            result = [x for x in possibleMelds if self.game.myself.mustPlayDangerous(x)]
        return result
