# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2011 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from twisted.spread import pb
from twisted.internet.defer import Deferred, DeferredList, succeed
from util import logDebug, logException, Duration
from message import Message
from common import InternalParameters, WINDS, Debug
from scoringengine import Ruleset, PredefinedRuleset, meldsContent
from game import RemoteGame
from query import Transaction, Query
from move import Move
from animation import animate
from intelligence import AIDefault

class ClientTable(object):
    """the table as seen by the client"""
    # pylint: disable=R0902
    # pylint: disable=R0913
    # pylint says too many args, too many instance variables
    def __init__(self, tableid, gameid, status, rulesetStr, playOpen, autoPlay, seed, playerNames,
                 playersOnline, endValues):
        self.tableid = tableid
        self.gameid = gameid
        self.status = status
        self.running = status == 'Running'
        self.suspended = status.startswith('Suspended')
        self.ruleset = Ruleset.fromList(rulesetStr)
        self.playOpen = playOpen
        self.autoPlay = autoPlay
        self.seed = seed
        self.playerNames = playerNames
        self.playersOnline = playersOnline
        self.endValues = endValues
        self.myRuleset = None # if set, points to an identical local ruleset
        allRulesets = Ruleset.availableRulesets() + PredefinedRuleset.rulesets()
        for myRuleset in allRulesets:
            if myRuleset == self.ruleset:
                self.myRuleset = myRuleset
                break

    def __str__(self):
        return 'Table %d %s rules %s players %s online %s' % (self.tableid or 0, self.status, self.ruleset.name,
            ', '.join(self.playerNames), ', '.join(str(x) for x in self.playersOnline))

    def gameExistsLocally(self):
        """does the game exist in the data base of the client?"""
        assert self.gameid
        return bool(Query('select 1 from game where id=?', list([self.gameid])).records)

    def humanPlayerNames(self):
        """returns a list excluding robot players"""
        return list(x for x in self.playerNames if not x.startswith('ROBOT'))

class Client(pb.Referenceable):
    """interface to the server. This class only implements the logic,
    so we can also use it on the server for robot clients. Compare
    with HumanClient(Client)"""

    def __init__(self, username=None, intelligence=AIDefault):
        """username is something like ROBOT 1 or None for the game server"""
        self.username = username
        self.game = None
        self.intelligence = intelligence(self)
        self.perspective = None # always None for a robot client
        self.tables = []
        self.table = None
        self.answers = [] # buffer for one or more answers to one server request
            # an answer can be a simple type or a Deferred

    @apply
    def host():
        """the name of the host we are connected with"""
        def fget(dummySelf):
            return None # Client on the server
        return property(**locals())

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

    def remote_tablesChanged(self, tables):
        """update table list"""
        self.tables = [ClientTable(*x) for x in tables] # pylint: disable=W0142

    def reserveGameId(self, gameid):
        """the game server proposes a new game id. We check if it is available
    in our local data base - we want to use the same gameid everywhere"""
        with Transaction():
            if Query('select id from game where id=?', list([gameid])).records:
                self.answers.append(Message.NO)
            else:
                Query('insert into game(id,seed) values(?,?)',
                      list([gameid, self.host]))

    def readyForGameStart(self, tableid, gameid, seed, playerNames, shouldSave=True):
        """the game server asks us if we are ready. A robot is always ready."""
        if self.isHumanClient():
            assert not self.table
            assert self.tables
            for tryTable in self.tables:
                if tryTable.tableid == tableid:
                    self.table = tryTable
            if not self.table:
                raise Exception('client.readyForGameStart: tableid %d unknown' % tableid)
        if self.table.suspended:
            self.game = RemoteGame.loadFromDB(gameid, client=self)
            for idx, playerName in enumerate(playerNames.split('//')):
                self.game.players.byName(playerName).wind = WINDS[idx]
            if self.isHumanClient():
                if self.game.handctr != self.table.endValues[0]:
                    self.game.close()
                    return 'The data bases for game %1 have different numbers for played hands: Server:%2, Client:%3', \
                            self.game.seed, self.table.endValues[0], self.game.handctr
                for player in self.game.players:
                    if player.balance != self.table.endValues[1][player.wind]:
                        self.game.close()
                        return 'The data bases for game %1 have different balances for wind %2: Server:%3, Client:%4', \
                                self.game.seed, player.wind, self.table.endValues[1][player.wind], player.balance
        else:
            self.game = RemoteGame(playerNames.split('//'), self.table.ruleset,
                shouldSave=shouldSave, gameid=gameid, seed=seed, client=self,
                playOpen=self.table.playOpen, autoPlay=self.table.autoPlay)
        self.game.prepareHand()
        self.answers.append(Message.OK)

    def readyForHandStart(self, playerNames, rotateWinds):
        """the game server asks us if we are ready. A robot is always ready..."""
        for idx, playerName in enumerate(playerNames.split('//')):
            self.game.players.byName(playerName).wind = WINDS[idx]
        if rotateWinds:
            self.game.rotateWinds()
        self.game.prepareHand()

    def invalidateOriginalCall(self, player):
        """called if a move violates the Original Call"""
        if player.originalCall:
            if player.mayWin and self.thatWasMe(player):
                if player.discarded:
                    player.mayWin = False
                    self.answers.append(Message.ViolatesOriginalCall)

    def ask(self, move, answers, callback=None):
        """this is where the robot AI should go.
        sends answer and one parameter to server"""
        self.answers.append(self.intelligence.selectAnswer(move, answers))
        if callback:
            callback()

    def thatWasMe(self, player):
        """returns True if player == myself"""
        if not self.game:
            return False
        return player == self.game.myself

    def remote_move(self, playerName, command, *args, **kwargs):
        """the server sends us info or a question and always wants us to answer"""
        self.answers = []
        token = kwargs['token']
        if token and self.game:
            if token != self.game.handId():
                logException( 'wrong token: %s, we have %s' % (token, self.game.handId()))
        with Duration('%s: %s' % (playerName, command)):
            return self.exec_move(playerName, command, *args, **kwargs)

    def remote_move_done(self, dummyResults=None):
        """the client is done with executing the move. Animations have ended."""
        # use the following for slowing down animation before reaching a bug
        # if self.game and not InternalParameters.isServer:
        #    if self.game.handId().split('/')[1]  == 'S3b' and 290 > len(self.game.moves) > 280:
        #        PREF.animationSpeed = 1
        for idx, answer in enumerate(self.answers):
            if not isinstance(answer, Deferred):
                if isinstance(answer, Message):
                    answer = answer.name
                if isinstance(answer, tuple) and isinstance(answer[0], Message):
                    answer = tuple(list([answer[0].name] + list(answer[1:])))
                self.answers[idx] = succeed(answer)
        return DeferredList(self.answers)

    def exec_move(self, playerName, command, *dummyArgs, **kwargs):
        """mirror the move of a player as told by the the game server"""
        # too many branches. pylint: disable=R0912
        player = None
        if self.game:
            if not self.game.client:
                # we aborted the game, ignore what the server tells us
                return
            player = self.game.playerByName(playerName)
        if InternalParameters.showTraffic:
            if self.isHumanClient():
                kw2 = kwargs.copy()
                del kw2['token']
                logDebug('%s %s %s' % (player, command, kw2))
        move = Move(player, command, kwargs)
        move.message.clientAction(self, move)
        if self.game:
            if player and not player.scoreMatchesServer(move.score):
                self.game.close()
            self.game.moves.append(move)
        if move.message == Message.HasDiscarded:
            # do not block here, we want to get the clientDialog
            # before the tile reaches its end position
            animate()
            return self.remote_move_done()
        else:
            return animate().addCallback(self.remote_move_done)

    def called(self, move):
        """somebody called a discarded tile"""
        calledTile = self.game.lastDiscard
        calledTileName = calledTile.element
        self.game.discardedTiles[calledTileName.lower()] -= 1
        assert calledTileName in move.source, '%s %s'% (calledTileName, move.source)
        if InternalParameters.field:
            InternalParameters.field.discardBoard.lastDiscarded = None
        self.invalidateOriginalCall(move.player)
        move.player.lastTile = calledTileName.lower()
        move.player.lastSource = 'd'
        hadTiles = move.source[:]
        hadTiles.remove(calledTileName)
        if not self.thatWasMe(move.player) and not self.game.playOpen:
            move.player.showConcealedTiles(hadTiles)
        move.exposedMeld = move.player.exposeMeld(hadTiles, called=calledTile)
        if self.thatWasMe(move.player):
            if move.message != Message.CalledKong:
                # we will get a replacement tile first
                self.ask(move, [Message.Discard, Message.MahJongg])
        elif self.game.prevActivePlayer == self.game.myself and self.perspective:
            # even here we ask: if our discard is claimed we need time
            # to notice - think 3 robots or network timing differences
            self.ask(move, [Message.OK])
#        raise Exception('end of called')

    def maySayChow(self, select=False):
        """returns answer arguments for the server if calling chow is possible.
        returns the meld to be completed"""
        if self.game.myself == self.game.nextPlayer():
            result = self.game.myself.possibleChows()
            if result and select:
                result = self.intelligence.selectChow(result)
            return result

    def maySayPung(self):
        """returns answer arguments for the server if calling pung is possible.
        returns the meld to be completed"""
        element = self.game.lastDiscard.element
        assert element[0].isupper(), str(self.game.lastDiscard)
        if self.game.myself.concealedTileNames.count(element) >= 2:
            return [element] * 3

    def maySayKong(self, select=False):
        """returns answer arguments for the server if calling or declaring kong is possible.
        returns the meld to be completed or to be declared"""
        result = self.game.myself.possibleKongs()
        if result and select:
            result = self.intelligence.selectKong(result)
        return result

    def maySayMahjongg(self, move):
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
        game.winner = myself
        try:
            hand = myself.computeHandContent(withTile=withDiscard, robbedTile=robbableTile)
        finally:
            game.winner = None
        if hand.maybeMahjongg():
            if Debug.robbingKong:
                if move.message == Message.DeclaredKong:
                    logDebug('%s may rob the kong from %s/%s' % \
                       (myself, move.player, move.exposedMeld.joined))
            lastTile = withDiscard or myself.lastTile
            lastMeld = list(hand.computeLastMeld(lastTile).pairs)
            if Debug.mahJongg:
                logDebug('%s may say MJ:%s, active=%s' % (
                    myself, list(x for x in game.players), game.activePlayer))
            return meldsContent(hand.hiddenMelds), withDiscard, lastMeld

    def maySay(self, move, msg, select=False):
        """returns answer arguments for the server if saying msg is possible"""
        # do not use a dict - most calls will be Pung
        if msg == Message.Pung:
            return self.maySayPung()
        if msg == Message.Chow:
            return self.maySayChow(select)
        if msg == Message.Kong:
            return self.maySayKong(select)
        if msg == Message.MahJongg:
            return self.maySayMahjongg(move)
        return True

    def maybeDangerous(self, msg, possibleMelds):
        """could answering with msg lead to dangerous game?
        If so return a list of text lines explaining why
        possibleMelds may be a list of melds or a single meld
        where a meld is represented by a list of 2char strings"""
        result = []
        if msg in (Message.Chow, Message.Pung, Message.Kong):
            if isinstance(possibleMelds[0], basestring):
                possibleMelds = [possibleMelds]
            result = [x for x in possibleMelds if self.game.myself.mustPlayDangerous(x)]
        return result
