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
"""

from twisted.spread import pb
from twisted.internet.defer import Deferred, DeferredList, succeed
from util import logException, debugMessage
from message import Message
from common import InternalParameters, WINDS
from scoringengine import Ruleset, PredefinedRuleset, meldsContent
from game import RemoteGame
from query import Query
from move import Move

class ClientTable(object):
    """the table as seen by the client"""
    def __init__(self, tableid, running, rulesetStr, playOpen, seed, playerNames):
        self.tableid = tableid
        self.running = running
        self.ruleset = Ruleset.fromList(rulesetStr)
        self.playOpen = playOpen
        self.seed = seed
        self.playerNames = list(playerNames)
        self.myRuleset = None # if set, points to an identical local rulest
        allRulesets = Ruleset.availableRulesets() + PredefinedRuleset.rulesets()
        for myRuleset in allRulesets:
            if myRuleset.hash == self.ruleset.hash:
                self.myRuleset = myRuleset
                break

    def __str__(self):
        return 'Table %d rules %s players %s' % (self.tableid, self.ruleset.name,
            ', '.join(self.playerNames))

class Client(pb.Referenceable):
    """interface to the server. This class only implements the logic,
    so we can also use it on the server for robot clients. Compare
    with HumanClient(Client)"""

    def __init__(self, username=None):
        """username is something like ROBOT 1 or None for the game server"""
        self.username = username
        self.game = None
        self.moves = []
        self.perspective = None # always None for a robot client
        self.tables = []
        self.table = None
        self.answers = [] # buffer for one or more answers to one server request
            # an answer can be a simple type or a Deferred

    @apply
    def host():
        """the name of the host we are connected with"""
        def fget(dummySelf):
            return Query.serverName
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

    def remote_tablesChanged(self, dummyTableid, tables):
        """update table list"""
        self.tables = [ClientTable(*x) for x in tables] # pylint: disable-msg=W0142

    def readyForGameStart(self, tableid, seed, playerNames, shouldSave=True):
        """the game server asks us if we are ready. A robot is always ready..."""
        if self.isHumanClient():
            assert not self.table
            for tryTable in self.tables:
                if tryTable.tableid == tableid:
                    self.table = tryTable
            if not self.table:
                raise Exception('client.readyForGameStart: tableid %d unknown' % tableid)
        self.game = RemoteGame(playerNames.split('//'), self.table.ruleset,
            shouldSave=shouldSave, seed=seed, client=self, playOpen=self.table.playOpen)
        self.game.prepareHand()
        self.answers.append(Message.OK)

    def readyForHandStart(self, playerNames, rotate):
        """the game server asks us if we are ready. A robot is always ready..."""
        for idx, playerName in enumerate(playerNames.split('//')):
            self.game.players.byName(playerName).wind = WINDS[idx]
        if rotate:
            self.game.rotateWinds()
        self.game.prepareHand()

    def invalidateOriginalCall(self, player):
        """called if a move violates the Original Call"""
        if player.originalCall:
            if player.mayWin and self.thatWasMe(player):
                if player.discarded:
                    player.mayWin = False
                    self.answers.append(Message.ViolatesOriginalCall)

    def selectDiscard(self):
        """returns exactly one tile for discard"""
        hand = self.game.myself.computeHandContent()
        for withDangerous in [False, True]:
            for meldLen in range(1, 4):
                melds = (x for x in hand.hiddenMelds if len(x) == meldLen)
                # hand.hiddenMelds are built from a set, order undefined. But
                # we want to be able to replay a game exactly, so sort them
                candidates = list(reversed(sorted(sum((x.pairs for x in melds), []))))
                if not withDangerous and self.game.dangerousTiles:
                    candidates = [x for x in candidates if x.lower() not in self.game.dangerousTiles]
                if not withDangerous and len(candidates) > 1:
                    for visibleCount in [3, 2]:
                        # if already 3 or 2 of this tile are discarded or exposed, prefer it
                        for candidate in candidates:
                            if self.game.visibleTiles[candidate.lower()] == visibleCount:
                                return candidate
                if candidates:
                    return candidates[-1]
        assert False, 'nothing discarded! hand:%s' % hand

    def ask(self, move, answers, dummyCallback=None):
        """this is where the robot AI should go"""
        answer = None
        for tryAnswer in [Message.MahJongg, Message.Kong, Message.Pung, Message.Chow]:
            if tryAnswer in answers:
                sayable = self.maySay(move, tryAnswer, select=True)
                if sayable:
                    answer = (tryAnswer, sayable)
                    break
        if not answer:
            answer = answers[0] # for now always return default answer
        if answer == Message.Discard:
            # do not remove tile from hand here, the server will tell all players
            # including us that it has been discarded. Only then we will remove it.
            self.answers.append((answer, self.selectDiscard()))
        else:
            # the other responses do not have a parameter
            self.answers.append((answer))

    def thatWasMe(self, player):
        """returns True if player == myself"""
        if not self.game:
            return False
        return player == self.game.myself

    def remote_move(self, playerName, command, *args, **kwargs):
        """the server sends us info or a question and always wants us to answer"""
        self.answers = []
        self.exec_move(playerName, command, *args, **kwargs)
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
        player = None
        if self.game:
            self.game.checkSelectorTiles()
            if not self.game.client:
                # we aborted the game, ignore what the server tells us
                return
            for myPlayer in self.game.players:
                if myPlayer.name == playerName:
                    player = myPlayer
            if not player:
                logException('Move references unknown player %s' % playerName)
        if InternalParameters.showTraffic:
            if self.isHumanClient():
                debugMessage('%s %s %s' % (player, command, kwargs))
        move = Move(player, command, kwargs)
        self.moves.append(move)
        move.message.clientAction(self, move)

    def called(self, move):
        """somebody called a discarded tile"""
        calledTile = self.game.lastDiscard
        self.game.discardedTiles[calledTile.lower()] -= 1
        assert calledTile in move.source, '%s %s'% (calledTile, move.source)
        if InternalParameters.field:
            InternalParameters.field.discardBoard.removeLastDiscard()
        self.invalidateOriginalCall(move.player)
        if self.thatWasMe(move.player) or self.game.playOpen:
            move.player.addTile(calledTile)
            move.player.lastTile = calledTile.lower()
        else:
            move.player.addTile('Xy')
            move.player.makeTilesKnown(move.source)
        move.player.lastSource = 'd'
        move.exposedMeld = move.player.exposeMeld(move.source)
        if self.thatWasMe(move.player):
            if move.message != Message.CalledKong:
                # we will get a replacement tile first
                self.ask(move, [Message.Discard, Message.MahJongg])
        elif self.game.prevActivePlayer == self.game.myself and self.perspective:
            # even here we ask: if our discard is claimed we need time
            # to notice - think 3 robots or network timing differences
            self.ask(move, [Message.OK])

    def selectChow(self, chows):
        """selects a chow to be completed. Add more AI here."""
        game = self.game
        myself = game.myself
        for chow in chows:
            if not myself.hasConcealedTiles(chow):
                # do not dissolve an existing chow
                belongsToPair = False
                for tileName in chow:
                    if myself.concealedTiles.count(tileName) == 2:
                        belongsToPair = True
                        break
                if not belongsToPair:
                    return chow

    def maySayChow(self, select=False):
        """returns answer arguments for the server if calling chow is possible.
        returns the meld to be completed"""
        game = self.game
        myself = game.myself
        result = myself.possibleChows(game.lastDiscard)
        if result and select:
            result = self.selectChow(result)
        return result

    def maySayPung(self):
        """returns answer arguments for the server if calling pung is possible.
        returns the meld to be completed"""
        if self.game.myself.concealedTiles.count(self.game.lastDiscard) >= 2:
            return [self.game.lastDiscard] * 3

    def maySayKong(self):
        """returns answer arguments for the server if calling or declaring kong is possible.
        returns the meld to be completed or to be declared"""
        game = self.game
        myself = game.myself
        if game.activePlayer == myself:
            if self.isRobotClient() or not InternalParameters.field:
                tileNames = set([x for x in myself.concealedTiles if x[0] not in 'fy'])
            else:
                tileNames = [myself.handBoard.focusTile.element]
            for tileName in tileNames:
                assert tileName[0].isupper(), tileName
                if myself.concealedTiles.count(tileName) == 4:
                    return [tileName] * 4
                searchMeld = tileName.lower() * 3
                allMeldContent = ' '.join(x.joined for x in myself.exposedMelds)
                if searchMeld in allMeldContent:
                    return [tileName.lower()] * 3 + [tileName]
        else:
            if myself.concealedTiles.count(game.lastDiscard) == 3:
                return [game.lastDiscard] * 4

    def maySayMahjongg(self, move):
        """returns answer arguments for the server if calling or declaring Mah Jongg is possible"""
        game = self.game
        myself = game.myself
        robbableTile = None
        withDiscard = game.lastDiscard if move.message == Message.AskForClaims else None
        if move.message == Message.DeclaredKong:
            withDiscard = move.source[0].capitalize()
            if move.player != myself:
                robbableTile = move.exposedMeld.pairs[1] # we want it capitalized for a hidden Kong
        game.winner = myself
        try:
            hand = myself.computeHandContent(withTile=withDiscard, robbedTile=robbableTile)
        finally:
            game.winner = None
        if hand.maybeMahjongg():
            if move.message == Message.DeclaredKong:
                pass
                # we need this for our search of seeds/autoplay where kongs are actually robbable
                # debugMessage('JAU! %s may rob the kong from %s/%s, roundsFinished:%d' % \
                #   (myself, move.player, move.exposedMeld.joined, game.roundsFinished))
            lastTile = withDiscard or myself.lastTile
            lastMeld = list(hand.computeLastMeld(lastTile).pairs)
            return meldsContent(hand.hiddenMelds), withDiscard, lastMeld

    def maySay(self, move, msg, select=False):
        """returns answer arguments for the server if saying msg is possible"""
        # do not use a dict - most calls will be Pung
        if msg == Message.Pung:
            return self.maySayPung()
        if msg == Message.Chow:
            return self.maySayChow(select)
        if msg == Message.Kong:
            return self.maySayKong()
        if msg == Message.MahJongg:
            return self.maySayMahjongg(move)
        return True

class Client1(Client):
    """alternative AI class"""
    pass
