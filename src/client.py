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

from itertools import chain

from twisted.spread import pb
from twisted.internet.defer import Deferred, DeferredList, succeed
from util import logException, debugMessage, Duration
from message import Message
from common import InternalParameters, WINDS, IntDict
from scoringengine import Ruleset, PredefinedRuleset, meldsContent, HandContent
from game import RemoteGame
from query import Transaction, Query
from move import Move
from meld import elementKey

class ClientTable(object):
    """the table as seen by the client"""
    # pylint: disable=R0902
    # pylint: disable=R0913
    # pylint says too many args, too many instance variables
    def __init__(self, tableid, gameid,  status, rulesetStr, playOpen, autoPlay, seed, playerNames, playersOnline):
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
        self.myRuleset = None # if set, points to an identical local rulest
        allRulesets = Ruleset.availableRulesets() + PredefinedRuleset.rulesets()
        for myRuleset in allRulesets:
            if myRuleset.hash == self.ruleset.hash:
                self.myRuleset = myRuleset
                break

    def __str__(self):
        return 'Table %d %s rules %s players %s online %s' % (self.tableid or 0, self.status, self.ruleset.name,
            ', '.join(self.playerNames),  ', '.join(str(x) for x in self.playersOnline))

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

    def __init__(self, username=None):
        """username is something like ROBOT 1 or None for the game server"""
        self.username = username
        self.game = None
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
            self.game = RemoteGame.load(gameid, client=self)
            for idx, playerName in enumerate(playerNames.split('//')):
                self.game.players.byName(playerName).wind = WINDS[idx]
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

    groupPrefs = {'s':0, 'b':0, 'c':0, 'w':5, 'd':10}

    @staticmethod
    def runningWindow(lst, windowSize):
        """generates moving sublists for each item. The item is always in the middle of the
        sublist or - for even lengths - one to the left."""
        if windowSize % 2:
            pre = windowSize / 2
        else:
            pre = windowSize / 2 - 1
        full = list(chain([None] * pre, lst, [None] * (windowSize - pre - 1)))
        for idx in range(len(lst)):
            yield full[idx:idx+windowSize]

    def __weighSameColors(self, candidates):
        """weigh tiles of same color against each other"""
        for color in 'sbc':
            colorCandidates = list(x for x in candidates if x.name[0] == color)
            if len(colorCandidates) == 4:
                # special case: do we have 4 consecutive singles?
                values = list(set(int(x.name[1]) for x in colorCandidates))
                if len(values) == 4 and values[0] + 3 == values[3]:
                    colorCandidates[0].preference -= 5
                    for candidate in colorCandidates[1:]:
                        candidate.preference += 5
                    break
            for prevCandidate, candidate, nextCandidate in self.runningWindow(colorCandidates, 3):
                value = int(candidate.name[1])
                prevValue = int(prevCandidate.name[1]) if prevCandidate else -99
                nextValue = int(nextCandidate.name[1]) if nextCandidate else 99
                if value == prevValue + 1:
                    prevCandidate.preference += 1
                    candidate.preference += 1
                    if value == nextValue - 1:
                        prevCandidate.preference += 2
                        nextCandidate.preference += 2
                if value == nextValue - 1:
                    nextCandidate.preference += 1
                    candidate.preference += 1
                if value == nextValue - 2:
                    nextCandidate.preference += 0.5
                    candidate.preference += 0.5

    def selectDiscard(self):
        # pylint: disable=R0912
        # disable warning about too many branches
        """returns exactly one tile for discard.
        Much of this is just trial and success - trying to get as much AI
        as possible with limited computing resources, it stands on
        no theoretical basis"""
        hand = self.game.myself.computeHandContent()
        hiddenTiles = sum((x.pairs.lower() for x in hand.hiddenMelds), [])
        tiles = list(sorted(set(hiddenTiles), key=elementKey))
        candidates = list(TileAI(x) for x in tiles)
        groupCounts = IntDict() # counts for tile groups (sbcdw), exposed and concealed
        declaredGroupCounts = IntDict()
        for tile in sum((x.pairs.lower() for x in hand.declaredMelds), []):
            groupCounts[tile[0]] += 1
            declaredGroupCounts[tile[0]] += 1
        for candidate in candidates:
            preference = candidate.preference
            group, value = candidate.name
            groupCounts[group] += 1
            candidate.occurrence = hiddenTiles.count(candidate.name)
            candidate.dangerous = candidate.name in self.game.dangerousTiles
            if candidate.dangerous:
                preference += 1000
            if candidate.occurrence >= 3:
                preference += 10
            elif candidate.occurrence == 2:
                preference += 5
            preference += Client.groupPrefs[group]
            if value in '19':
                preference += 2
            if self.game.visibleTiles[candidate.name] == 3:
                preference -= 10
            elif self.game.visibleTiles[candidate.name] == 2:
                preference -= 5
            candidate.preference = preference
        self.__weighSameColors(candidates)
        for candidate in candidates:
            group = candidate.name[0]
            groupCount = groupCounts[group]
            if group in 'sbc':
                if groupCount == 1:
                    candidate.preference -= 2
                elif groupCount > 8:
                    # do not go for color game if we already declared something in another color:
                    if not any(declaredGroupCounts[x] for x in 'sbc' if x != group):
                        # improvement: less if we already have a concealed pung of another color
                        # improvement: pref for pong only / 0value game
                        candidate.preference += (groupCount-5) * 2
            elif group == 'w' and groupCount > 5:
                candidate.preference += 10
            elif group == 'd' and groupCount > 5:
                candidate.preference += 15
        self.weighCallingHand(hand, candidates)
        # return tile with lowest preference:
        return sorted(candidates, key=lambda x: x.preference)[0].name.capitalize()

    @staticmethod
    def weighCallingHand(hand, candidates):
        """if we can get a calling hand, prefer that"""
        for candidate in candidates:
            newHand = hand - candidate.name.capitalize()
            winnerTile = newHand.isCalling()
            if winnerTile:
                string = newHand.string.replace(' m', ' M')
                mjHand = HandContent.cached(newHand.ruleset, string, newHand.computedRules, plusTile=winnerTile)
                candidate.preference -= mjHand.total() / 10

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
        with Duration('%s: %s' % (playerName, command)):
            return self.exec_move(playerName, command, *args, **kwargs)

    def remote_move_done(self, dummyResults=None):
        """the client is done with executing the move. Animations have ended."""
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
            if not self.game.client:
                # we aborted the game, ignore what the server tells us
                return
            if playerName is None:
                player = None
            else:
                for myPlayer in self.game.players:
                    if myPlayer.name == playerName:
                        player = myPlayer
                if not player:
                    logException('Move references unknown player %s' % playerName)
        if InternalParameters.showTraffic:
            if self.isHumanClient():
                debugMessage('%s %s %s' % (player, command, kwargs))
        move = Move(player, command, kwargs)
        move.message.clientAction(self, move)
        if self.game:
            if player and not player.scoreMatchesServer(move.score):
                self.game.close()
            self.game.moves.append(move)
        field = InternalParameters.field
        if field:
            deferred = Deferred()
            deferred.addCallback(self.remote_move_done)
            field.animate(deferred)
            return deferred
        else:
            return self.remote_move_done()

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

    def selectChow(self, chows):
        """selects a chow to be completed. Add more AI here."""
        game = self.game
        myself = game.myself
        for chow in chows:
            if not myself.hasConcealedTiles(chow):
                # do not dissolve an existing chow
                belongsToPair = False
                for tileName in chow:
                    if myself.concealedTileNames.count(tileName) == 2:
                        belongsToPair = True
                        break
                if not belongsToPair:
                    return chow

    # pylint: disable=R0201
    # yes it could be a function but we want to override it
    def selectKong(self, kongs):
        """selects a kong to be declared. Having more than one undeclared kong is quite improbable"""
        return kongs[0]

    def maySayChow(self, select=False):
        """returns answer arguments for the server if calling chow is possible.
        returns the meld to be completed"""
        game = self.game
        myself = game.myself
        result = myself.possibleChows()
        if result and select:
            result = self.selectChow(result)
        return result

    def maySayPung(self):
        """returns answer arguments for the server if calling pung is possible.
        returns the meld to be completed"""
        if self.game.myself.concealedTileNames.count(self.game.lastDiscard.element) >= 2:
            return [self.game.lastDiscard.element] * 3

    def maySayKong(self, select=False):
        """returns answer arguments for the server if calling or declaring kong is possible.
        returns the meld to be completed or to be declared"""
        game = self.game
        myself = game.myself
        result = myself.possibleKongs()
        if result and select:
            result = self.selectKong(result)
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
            return self.maySayKong(select)
        if msg == Message.MahJongg:
            return self.maySayMahjongg(move)
        return True

class TileAI(object):
    """holds a few AI related tile properties"""
    def __init__(self, name):
        self.name = name
        self.occurrence = 0
        self.dangerous = False
        self.preference = 0

    def __str__(self):
        return '%s, occ=%d, dangerous=%d, pref=%d' % (self.name, self.occurrence, self.dangerous, self.preference)

class Client1(Client):
    """alternative AI class"""
    pass
