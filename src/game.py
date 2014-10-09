# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2014 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
"""

import datetime
import weakref
import os, csv
if os.name != 'nt':
    import resource
from random import Random
from collections import defaultdict
from functools import total_ordering

from twisted.internet.defer import succeed
from util import stack, gitHead
from log import logError, logWarning, logException, logDebug, m18n
from common import WINDS, Internal, IntDict, Debug, Options
from query import Query
from rule import Ruleset
from tile import Tile, elements
from sound import Voice
from wall import Wall
from move import Move
from player import Players, Player, PlayingPlayer

class CountingRandom(Random):
    """counts how often random() is called and prints debug info"""
    def __init__(self, game, value=None):
        self._game = weakref.ref(game)
        Random.__init__(self, value)
        self.count = 0

    @property
    def game(self):
        """hide the fact that game is a weakref"""
        return self._game()

    def random(self):
        """the central randomizator"""
        self.count += 1
        return Random.random(self)
    def seed(self, newSeed=None):
        self.count = 0
        if Debug.random:
            self.game.debug('Random gets seed %s' % newSeed)
        Random.seed(self, newSeed)
    def shuffle(self, listValue, func=None): # pylint: disable=arguments-differ
        """pylint needed for python up to 2.7.5"""
        oldCount = self.count
        Random.shuffle(self, listValue, func)
        if Debug.random:
            self.game.debug('%d out of %d calls to random by Random.shuffle from %s' % (
                self.count - oldCount, self.count, stack('')[-2]))
    def randrange(self, start, stop=None, step=1): # pylint: disable=arguments-differ
        oldCount = self.count
        result = Random.randrange(self, start, stop, step)
        if Debug.random:
            self.game.debug('%d out of %d calls to random by Random.randrange(%d,%s) from %s' % (
                self.count - oldCount, self.count, start, stop, stack('')[-2]))
        return result
    def choice(self, fromList):
        if len(fromList) == 1:
            return fromList[0]
        oldCount = self.count
        result = Random.choice(self, fromList)
        if Debug.random:
            self.game.debug('%d out of %d calls to random by Random.choice(%s) from %s' % (
                self.count - oldCount, self.count, str([str(x) for x in fromList]), stack('')[-2]))
        return result
    def sample(self, population, wantedLength):
        oldCount = self.count
        result = Random.sample(self, population, wantedLength)
        if Debug.random:
            self.game.debug('%d out of %d calls to random by Random.sample(x, %d) from %s' % (
                self.count - oldCount, self.count, wantedLength, stack('')[-2]))
        return result

@total_ordering
class HandId(object):
    """handle a string representing a hand Id"""
    def __init__(self, game, string=None, stringIdx=0):
        self.game = game
        self.seed = game.seed
        self.roundsFinished = self.rotated = self.notRotated = self.moveCount = 0
        if string is None:
            self.roundsFinished = game.roundsFinished
            self.rotated = game.rotated
            self.notRotated = game.notRotated
            self.moveCount = len(game.moves)
        else:
            self.__scanHandId(string, stringIdx)
        assert self.rotated < 4, self

    def goto(self):
        """advance game to self"""
        for _ in range(self.roundsFinished * 4 + self.rotated):
            self.game.rotateWinds()
        self.game.notRotated = self.notRotated

    def __scanHandId(self, string, stringIdx):
        """gets the --game option.
        stringIdx 0 is the part in front of ..
        stringIdx 1 is the part after ..
        """
        # pylint: disable=too-many-return-statements
        if not string:
            return
        seed = int(string.split('/')[0])
        assert self.seed is None or self.seed == seed, string
        self.seed = seed
        if not '/' in string:
            if stringIdx == 1:
                self.roundsFinished = 100
            return
        string = string.split('/')[1]
        parts = string.split('..')
        if stringIdx == 1 and len(parts) == 2 and parts[1] == '':
            self.roundsFinished = 100
            return
        if stringIdx == 0 and len(parts) == 2 and parts[0] == '':
            return
        if stringIdx == 1 and len(parts) == 2 and parts[1] == '':
            self.roundsFinished = 100
            return
        handId = parts[min(stringIdx, len(parts)-1)]
        if handId[0] not in WINDS:
            logException('--game=%s with / must specify the round wind' % string)
        ruleset = self.game.ruleset
        self.roundsFinished = WINDS.index(handId[0])
        if self.roundsFinished > ruleset.minRounds:
            logWarning('Ruleset %s has %d minimum rounds but you want round %d(%s)' % (
                ruleset.name, ruleset.minRounds, self.roundsFinished + 1, handId[0]))
            self.roundsFinished = ruleset.minRounds
            return
        self.rotated = int(handId[1]) - 1
        if self.rotated > 3:
            logWarning('You want %d rotations, reducing to maximum of 3' % self.rotated)
            self.rotated = 3
            return
        for char in handId[2:]:
            if char < 'a':
                logWarning('you want %s, changed to a' % char)
                char = 'a'
            if char > 'z':
                logWarning('you want %s, changed to z' % char)
                char = 'z'
            self.notRotated = self.notRotated * 26 + ord(char) - ord('a') + 1

    def prompt(self, withSeed=True, withAI=True, withMoveCount=False):
        """
        Identifies the hand for window title and scoring table.

        @param withSeed: If set, include the seed used for the random generator.
        @type  withSeed: C{Boolean}
        @param withAI:   If set and AI != Default: include AI name for human players.
        @type  withAI:   C{Boolean}
        @param withMoveCount:   If set, include the current count of moves.
        @type  withMoveCount:   C{Boolean}
        @return:         The prompt.
        @rtype:          C{str}
        """
        aiVariant = ''
        if withAI and self.game.belongsToHumanPlayer():
            aiName = self.game.myself.intelligence.name() if self.game.myself else 'Default'
            if aiName != 'Default':
                aiVariant = aiName + '/'
        num = self.notRotated
        assert isinstance(num, int), num
        charId = ''
        while num:
            charId = chr(ord('a') + (num-1) % 26) + charId
            num = (num-1) // 26
        wind = (WINDS + 'X')[self.roundsFinished]
        if withSeed:
            seed = self.seed
        else:
            seed = ''
        delim = '/' if withSeed or withAI else ''
        result = '%s%s%s%s%s%s' % (aiVariant, seed, delim, wind, self.rotated + 1, charId)
        if withMoveCount:
            result += '/%d' % self.moveCount
        return result

    def token(self):
        """server and client use this for checking if they talk about the same thing"""
        return self.prompt(withAI=False)

    def __str__(self):
        return self.prompt()

    def __repr__(self):
        return 'HandId({})'.format(self.prompt())

    def __eq__(self, other):
        return other and (self.roundsFinished, self.rotated, self.notRotated) == (
            other.roundsFinished, other.rotated, other.notRotated)

    def __ne__(self, other):
        return not self == other

    def __lt__(self, other):
        return (self.roundsFinished, self.rotated, self.notRotated) < (
            other.roundsFinished, other.rotated, other.notRotated)

class Game(object):
    """the game without GUI"""
    # pylint: disable=too-many-instance-attributes
    playerClass = Player
    wallClass = Wall

    def __init__(self, names, ruleset, gameid=None, wantedGame=None, client=None):
        """a new game instance. May be shown on a field, comes from database if gameid is set

        Game.lastDiscard is the tile last discarded by any player. It is reset to None when a
        player gets a tile from the living end of the wall or after he claimed a discard.
        """
        # pylint: disable=too-many-statements
        assert self.__class__ != Game, 'Do not directly instantiate Game'
        self.players = Players() # if we fail later on in init, at least we can still close the program
        self.myself = None   # the player using this client instance for talking to the server
        self.__shouldSave = False
        self._client = None
        self.client = client
        self.rotated = 0
        self.notRotated = 0 # counts hands since last rotation
        self.ruleset = None
        self.roundsFinished = 0
        self._currentHandId = None
        self._prevHandId = None
        self.randomGenerator = CountingRandom(self)
        self.wantedGame = wantedGame
        self._setHandSeed()
        self.activePlayer = None
        self.__winner = None
        self.moves = []
        self.gameid = gameid
        self.playOpen = False
        self.autoPlay = False
        self.handctr = 0
        self.roundHandCount = 0
        self.handDiscardCount = 0
        self.divideAt = None
        self.__lastDiscard = None # always uppercase
        self.visibleTiles = IntDict()
        self.discardedTiles = IntDict(self.visibleTiles) # tile names are always lowercase
        self.dangerousTiles = list()
        self.csvTags = []
        self._setGameId()
        self.__useRuleset(ruleset)
        # shift rules taken from the OEMC 2005 rules
        # 2nd round: S and W shift, E and N shift
        self.shiftRules = 'SWEN,SE,WE'
        self.wall = self.wallClass(self)
        self.assignPlayers(names)
        if self.belongsToGameServer():
            self.__shufflePlayers()
        self._scanGameOption()
        for player in self.players:
            player.clearHand()

    @property
    def shouldSave(self):
        """as a property"""
        return self.__shouldSave

    @shouldSave.setter
    def shouldSave(self, value):
        """if activated, save start time"""
        if value and not self.__shouldSave:
            self.saveStartTime()
        self.__shouldSave = value

    @property
    def handId(self):
        """current position in game"""
        result = HandId(self)
        if result != self._currentHandId:
            self._prevHandId = self._currentHandId
            self._currentHandId = result
        return result

    @property
    def client(self):
        """hide weakref"""
        if self._client:
            return self._client()

    @client.setter
    def client(self, value):
        """hide weakref"""
        if value:
            self._client = weakref.ref(value)
        else:
            self._client = None

    def clearHand(self):
        """empty all data"""
        if self.moves:
            for move in self.moves:
                del move
        self.moves = []
        for player in self.players:
            player.clearHand()
        self.__winner = None
        self.__activePlayer = None
        self.prevActivePlayer = None
        self.dangerousTiles = list()
        self.discardedTiles.clear()
        assert self.visibleTiles.count() == 0

    def _scanGameOption(self):
        """this is only done for PlayingGame"""
        pass

    @property
    def lastDiscard(self):
        """hide weakref"""
        return self.__lastDiscard
    @lastDiscard.setter
    def lastDiscard(self, value):
        """hide weakref"""
        self.__lastDiscard = value
        if value is not None:
            assert isinstance(value, Tile), value
            if value.isExposed:
                raise Exception('lastDiscard is exposed:%s' % value)

    @property
    def winner(self):
        """the name of the game server this game is attached to"""
        return self.__winner

    @property
    def roundWind(self):
        """the round wind for Hand"""
        return 'eswn'[self.roundsFinished % 4]

    @winner.setter
    def winner(self, value):
        """the name of the game server this game is attached to"""
        if self.__winner != value:
            if self.__winner:
                self.__winner.invalidateHand()
            self.__winner = value
            if value:
                value.invalidateHand()

    def addCsvTag(self, tag, forAllPlayers=False):
        """tag will be written to tag field in csv row"""
        if forAllPlayers or self.belongsToHumanPlayer():
            self.csvTags.append('%s/%s' % (tag, self.handId.prompt(withSeed=False)))

    def isFirstHand(self):
        """as the name says"""
        return self.roundHandCount == 0 and self.roundsFinished == 0

    def _setGameId(self):
        """virtual"""
        assert not self # we want it to fail, and quieten pylint

    def close(self):
        """log off from the server and return a Deferred"""
        self.wall = None
        self.lastDiscard = None

    def playerByName(self, playerName):
        """return None or the matching player"""
        if playerName is None:
            return None
        for myPlayer in self.players:
            if myPlayer.name == playerName:
                return myPlayer
        logException('Move references unknown player %s' % playerName)

    def losers(self):
        """the 3 or 4 losers: All players without the winner"""
        return list([x for x in self.players if x is not self.__winner])

    def belongsToRobotPlayer(self):
        """does this game instance belong to a robot player?"""
        return self.client and self.client.isRobotClient()

    def belongsToHumanPlayer(self):
        """does this game instance belong to a human player?"""
        return self.client and self.client.isHumanClient()

    def belongsToGameServer(self):
        """does this game instance belong to the game server?"""
        return self.client and self.client.isServerClient()

    @staticmethod
    def isScoringGame():
        """are we scoring a manual game?"""
        return False

    def belongsToPlayer(self):
        """does this game instance belong to a player (as opposed to the game server)?"""
        return self.belongsToRobotPlayer() or self.belongsToHumanPlayer()

    def assignPlayers(self, playerNames):
        """
        The server tells us the seating order and player names.

        @param playerNames: A list of 4 tuples. Each tuple holds wind and name.
        @type playerNames: The tuple contents must be C{unicode}
        @todo: Can we pass L{Players} instead of that tuple list?
        """
        if not self.players:
            self.players = Players(self.playerClass(self, playerNames[x][1]) for x in range(4))
        for wind, name in playerNames:
            self.players.byName(name).wind = wind
        if self.client and self.client.name:
            self.myself = self.players.byName(self.client.name)
        self.sortPlayers()

    def __shufflePlayers(self):
        """assign random seats to the players and assign winds"""
        self.players.sort(key=lambda x: x.name)
        self.randomGenerator.shuffle(self.players)
        for player, wind in zip(self.players, WINDS):
            player.wind = wind

    def __exchangeSeats(self):
        """execute seat exchanges according to the rules"""
        winds = self.shiftRules.split(',')[(self.roundsFinished-1) % 4]
        players = list(self.players[x] for x in winds)
        pairs = list(players[x:x+2] for x in range(0, len(winds), 2))
        for playerA, playerB in self._mustExchangeSeats(pairs):
            playerA.wind, playerB.wind = playerB.wind, playerA.wind
        self.sortPlayers()

    def _mustExchangeSeats(self, pairs):
        """filter: which player pairs should really swap places?"""
        # pylint: disable=no-self-use
        return pairs

    def sortPlayers(self):
        """sort by wind order. Place ourself at bottom (idx=0)"""
        self.players.sort(key=lambda x: WINDS.index(x.wind))
        self.activePlayer = self.players[u'E']
        if Internal.scene:
            if self.belongsToHumanPlayer():
                while self.players[0] != self.myself:
                    self.players = Players(self.players[1:] + self.players[:1])
                for idx, player in enumerate(self.players):
                    player.front = self.wall[idx]

    @staticmethod
    def _newGameId():
        """write a new entry in the game table
        and returns the game id of that new entry"""
        return Query("insert into game(seed) values(0)").cursor.lastrowid

    def saveStartTime(self):
        """save starttime for this game"""
        starttime = datetime.datetime.now().replace(microsecond=0).isoformat()
        args = list([starttime, self.seed, int(self.autoPlay), self.ruleset.rulesetId])
        args.extend([p.nameid for p in self.players])
        args.append(self.gameid)
        Query("update game set starttime=?,seed=?,autoplay=?," \
                "ruleset=?,p0=?,p1=?,p2=?,p3=? where id=?", tuple(args))

    def __useRuleset(self, ruleset):
        """use a copy of ruleset for this game, reusing an existing copy"""
        self.ruleset = ruleset
        self.ruleset.load()
        if Internal.db:
            # only if we have a DB open. False in scoringtest.py
            query = Query('select id from ruleset where id>0 and hash=?', (self.ruleset.hash,))
            if query.records:
                # reuse that ruleset
                self.ruleset.rulesetId = query.records[0][0]
            else:
                # generate a new ruleset
                self.ruleset.save()

    @property
    def seed(self): # TODO: move this to PlayingGame
        """extract it from wantedGame. Set wantedGame if empty."""
        if not self.wantedGame:
            self.wantedGame = str(int(self.randomGenerator.random() * 10**9))
        return int(self.wantedGame.split('/')[0])

    def _setHandSeed(self): # TODO: move this to PlayingGame
        """set seed to a reproducable value, independent of what happend
        in previous hands/rounds.
        This makes it easier to reproduce game situations
        in later hands without having to exactly replay all previous hands"""
        seedFactor = (self.roundsFinished + 1) * 10000 + self.rotated * 1000 + self.notRotated * 100
        self.randomGenerator.seed(self.seed * seedFactor)

    def prepareHand(self):
        """prepare a game hand"""
        self.clearHand()
        if self.finished():
            if Options.rounds:
                self.close().addCallback(Internal.mainWindow.close)
            else:
                self.close()

    def initHand(self):
        """directly before starting"""
        self.dangerousTiles = list()
        self.discardedTiles.clear()
        assert self.visibleTiles.count() == 0
        if Internal.scene:
# why not self.scene?
            Internal.scene.prepareHand()
        self._setHandSeed()

    def saveHand(self):
        """save hand to database, update score table and balance in status line"""
        self.__payHand()
        self._saveScores()
        self.handctr += 1
        self.notRotated += 1
        self.roundHandCount += 1
        self.handDiscardCount = 0

    def _saveScores(self):
        """save computed values to database, update score table and balance in status line"""
        scoretime = datetime.datetime.now().replace(microsecond=0).isoformat()
        logMessage = ''
        for player in self.players:
            if player.hand:
                manualrules = '||'.join(x.rule.name for x in player.hand.usedRules)
            else:
                manualrules = m18n('Score computed manually')
            Query("INSERT INTO SCORE "
                "(game,hand,data,manualrules,player,scoretime,won,prevailing,wind,"
                "points,payments, balance,rotated,notrotated) "
                "VALUES(%d,%d,?,?,%d,'%s',%d,'%s','%s',%d,%d,%d,%d,%d)" % \
                (self.gameid, self.handctr, player.nameid,
                    scoretime, int(player == self.__winner),
                    WINDS[self.roundsFinished % 4], player.wind, player.handTotal,
                    player.payment, player.balance, self.rotated, self.notRotated),
                (player.hand.string, manualrules))
            logMessage += '{player:<12} {hand:>4} {total:>5} {won} | '.format(
                player=str(player)[:12], hand=player.handTotal, total=player.balance,
                won='WON' if player == self.winner else '   ')
            for usedRule in player.hand.usedRules:
                rule = usedRule.rule
                if rule.score.limits:
                    self.addCsvTag(rule.name.replace(' ', ''))
        if Debug.scores:
            self.debug(logMessage)

    def maybeRotateWinds(self):
        """rules which make winds rotate"""
        result = list(x for x in self.ruleset.filterRules('rotate') if x.rotate(self))
        if result:
            if Debug.explain:
                if not self.belongsToRobotPlayer():
                    self.debug(result, prevHandId=True)
            self.rotateWinds()
        return bool(result)

    def rotateWinds(self):
        """rotate winds, exchange seats. If finished, update database"""
        self.rotated += 1
        self.notRotated = 0
        if self.rotated == 4:
            self.roundsFinished += 1
            self.rotated = 0
            self.roundHandCount = 0
        if self.finished():
            endtime = datetime.datetime.now().replace(microsecond=0).isoformat()
            with Internal.db as transaction:
                transaction.execute('UPDATE game set endtime = "%s" where id = %d' % \
                    (endtime, self.gameid))
        elif not self.belongsToPlayer():
            # the game server already told us the new placement and winds
            winds = [player.wind for player in self.players]
            winds = winds[3:] + winds[0:3]
            for idx, newWind in enumerate(winds):
                self.players[idx].wind = newWind
            if self.roundsFinished % 4 and self.rotated == 0:
                # exchange seats between rounds
                self.__exchangeSeats()

    def debug(self, msg, btIndent=None, prevHandId=False):
        """prepend game id"""
        if self.belongsToRobotPlayer():
            prefix = 'R'
        elif self.belongsToHumanPlayer():
            prefix = 'C'
        elif self.belongsToGameServer():
            prefix = 'S'
        else:
            logDebug(msg, btIndent=btIndent)
            return
        logDebug('%s%s: %s' % (prefix, self._prevHandId if prevHandId else self.handId.prompt(withMoveCount=True), msg),
            withGamePrefix=False, btIndent=btIndent)

    @staticmethod
    def __getName(playerid):
        """get name for playerid
        """
        try:
            return Players.allNames[playerid]
        except KeyError:
            return m18n('Player %1 not known', playerid)

    @classmethod
    def loadFromDB(cls, gameid, client=None):
        """load game by game id and return a new Game instance"""
        Internal.logPrefix = 'S' if Internal.isServer else 'C'
        qGameRecords = Query("select p0,p1,p2,p3,ruleset,seed from game where id = ?", (gameid,)).records
        if not qGameRecords:
            return None
        qGameRecord = qGameRecords[0]
        rulesetId = qGameRecord[4] or 1
        ruleset = Ruleset.cached(rulesetId)
        Players.load() # we want to make sure we have the current definitions
        qLastHandRecords = Query("select hand,rotated from score where game=? and hand="
            "(select max(hand) from score where game=?)", (gameid, gameid)).records
        if qLastHandRecords:
            qLastHandRecord = qLastHandRecords[0]
        else:
            qLastHandRecord = tuple([0,0])
        qScoreRecords = Query("select player, wind, balance, won, prevailing from score "
            "where game=? and hand=?", (gameid, qLastHandRecord[0])).records
        if not qScoreRecords:
            # this should normally not happen
            qScoreRecords = tuple([
                    tuple([qGameRecord[x], WINDS[x], 0, False, 'E']) for x in range(4)
                   ])
        if len(qScoreRecords) != 4:
            logError(u'game %d inconsistent: There should be exactly '
                    '4 score records for the last hand' % gameid)

        # after loading SQL, prepare values.

        # default value. If the server saved a score entry but our client did not,
        # we get no record here. Should we try to fix this or exclude such a game from
        # the list of resumable games?
        if len(set(x[4] for x in qScoreRecords)) != 1:
            logError(u'game %d inconsistent: All score records for the same '
                'hand must have the same prevailing wind' % gameid)
        prevailing = qScoreRecords[0][4]

        players = list(tuple([x[1], Game.__getName(x[0])]) for x in qScoreRecords)

        # create the game instance.
        game = cls(players, ruleset, gameid=gameid, client=client, wantedGame=qGameRecord[5])
        game.handctr, game.rotated = qLastHandRecord

        for record in qScoreRecords:
            playerid = record[0]
            player = game.players.byId(playerid)
            if not player:
                logError(
                'game %d inconsistent: player %d missing in game table' % \
                    (gameid, playerid))
            else:
                player.getsPayment(record[2])
            if record[3]:
                game.winner = player
        game.roundsFinished = WINDS.index(prevailing)
        game.handctr += 1
        game.notRotated += 1
        game.maybeRotateWinds()
        game.sortPlayers()
        game.wall.decorate()
        return game

    def finished(self):
        """The game is over after minRounds completed rounds. Also,
        check if we reached the second handId defined by --game.
        If we did, the game is over too"""
        last = HandId(self, self.wantedGame, 1)
        if self.handId > last:
            return True
        if Options.rounds:
            return self.roundsFinished >= 1
        elif self.ruleset:
            # while initialising Game, ruleset might be None
            return self.roundsFinished >= self.ruleset.minRounds

    def __payHand(self):
        """pay the scores"""
        # pylint: disable=too-many-branches
        # too many branches
        winner = self.__winner
        if winner:
            winner.wonCount += 1
            guilty = winner.usedDangerousFrom
            if guilty:
                payAction = self.ruleset.findUniqueOption('payforall')
            if guilty and payAction:
                if Debug.dangerousGame:
                    self.debug('%s: winner %s. %s pays for all' % \
                                (self.handId, winner, guilty))
                guilty.hand.usedRules.append((payAction, None))
                score = winner.handTotal
                score = score * 6 if winner.wind == 'E' else score * 4
                guilty.getsPayment(-score)
                winner.getsPayment(score)
                return

        for player1 in self.players:
            if Debug.explain:
                if not self.belongsToRobotPlayer():
                    self.debug('%s: %s' % (player1, player1.hand.string))
                    for line in player1.hand.explain():
                        self.debug('   %s' % (line))
            for player2 in self.players:
                if id(player1) != id(player2):
                    if player1.wind == 'E' or player2.wind == 'E':
                        efactor = 2
                    else:
                        efactor = 1
                    if player2 != winner:
                        player1.getsPayment(player1.handTotal * efactor)
                    if player1 != winner:
                        player1.getsPayment(-player2.handTotal * efactor)

    def lastMoves(self, only=None, without=None, withoutNotifications=False):
        """filters and yields the moves in reversed order"""
        for idx in range(len(self.moves)-1, -1, -1):
            move = self.moves[idx]
            if withoutNotifications and move.notifying:
                continue
            if only:
                if move.message in only:
                    yield move
            elif without:
                if move.message not in without:
                    yield move
            else:
                yield move

    def throwDices(self):
        """sets random living and kongBox
        sets divideAt: an index for the wall break"""
        breakWall = self.randomGenerator.randrange(4)
        sideLength = len(self.wall.tiles) // 4
        # use the sum of four dices to find the divide
        self.divideAt = breakWall * sideLength + \
            sum(self.randomGenerator.randrange(1, 7) for idx in range(4))
        if self.divideAt % 2 == 1:
            self.divideAt -= 1
        self.divideAt %= len(self.wall.tiles)

class PlayingGame(Game):
    """this game is played using the computer"""
    # pylint: disable=too-many-arguments,too-many-public-methods,too-many-instance-attributes
    playerClass = PlayingPlayer

    def __init__(self, names, ruleset, gameid=None, wantedGame=None, \
            client=None, playOpen=False, autoPlay=False):
        """a new game instance, comes from database if gameid is set"""
        self.__activePlayer = None
        self.prevActivePlayer = None
        self.defaultNameBrush = None
        Game.__init__(self, names, ruleset, gameid, wantedGame=wantedGame, client=client)
        self.playOpen = playOpen
        self.autoPlay = autoPlay
        myself = self.myself
        if self.belongsToHumanPlayer() and myself:
            myself.voice = Voice.locate(myself.name)
            if myself.voice:
                if Debug.sound:
                    logDebug('myself %s gets voice %s' % (myself.name, myself.voice))
            else:
                if Debug.sound:
                    logDebug('myself %s gets no voice'% (myself.name))

    def writeCsv(self):
        """write game summary to Options.csv"""
        if self.finished() and Options.csv:
            gameWinner = max(self.players, key=lambda x: x.balance)
            writer = csv.writer(open(Options.csv, 'a'), delimiter=';')
            if Debug.process and os.name != 'nt':
                self.csvTags.append('MEM:%s' % resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            if Options.rounds:
                self.csvTags.append('ROUNDS:%s' % Options.rounds)
            row = [self.ruleset.name, Options.AI, gitHead(), str(self.seed),
                ','.join(self.csvTags)]
            for player in sorted(self.players, key=lambda x: x.name):
                row.append(player.name.encode('utf-8'))
                row.append(player.balance)
                row.append(player.wonCount)
                row.append(1 if player == gameWinner else 0)
            writer.writerow(row)
            del writer

    def close(self):
        """log off from the server and return a Deferred"""
        Game.close(self)
        self.writeCsv()
        Internal.autoPlay = False # do that only for the first game
        if self.client:
            client = self.client
            self.client = None
            result = client.logout()
        else:
            result = succeed(None)
        return result

    def _setGameId(self):
        """do nothing, we already went through the game id reservation"""
        pass

    @property
    def activePlayer(self):
        """the turn is on this player"""
        return self.__activePlayer

    @activePlayer.setter
    def activePlayer(self, player):
        """the turn is on this player"""
        if self.__activePlayer != player:
            self.prevActivePlayer = self.__activePlayer
            if self.prevActivePlayer:
                self.prevActivePlayer.hidePopup()
            self.__activePlayer = player
            if Internal.scene: # mark the name of the active player in blue
                for player in self.players:
                    player.colorizeName()

    def prepareHand(self):
        """prepares the next hand"""
        Game.prepareHand(self)
        if not self.finished():
            self.sortPlayers()
            self.hidePopups()
            self._setHandSeed()
            self.wall.build(shuffleFirst=True)

    def hidePopups(self):
        """hide all popup messages"""
        for player in self.players:
            player.hidePopup()

    def saveStartTime(self):
        """write a new entry in the game table with the selected players"""
        if not self.gameid:
            # in server.__prepareNewGame, gameid is None here
            return
        records = Query("select seed from game where id=?", (self.gameid,)).records
        assert records, 'self.gameid: %s' % self.gameid
        seed = records[0][0]

        if not Internal.isServer and self.client:
            host = self.client.connection.url
        else:
            host = None

        if seed == 'proposed' or seed == host:
            # we reserved the game id by writing a record with seed == host
            Game.saveStartTime(self)

    def _saveScores(self):
        """save computed values to database, update score table and balance in status line"""
        if self.shouldSave:
            if self.belongsToRobotPlayer():
                assert False, 'shouldSave must not be True for robot player'
            Game._saveScores(self)

    def nextPlayer(self, current=None):
        """returns the player after current or after activePlayer"""
        if not current:
            current = self.activePlayer
        pIdx = self.players.index(current)
        return self.players[(pIdx + 1) % 4]

    def nextTurn(self):
        """move activePlayer"""
        self.activePlayer = self.nextPlayer()

    def __concealedTileName(self, tileName):
        """tileName has been discarded, by which name did we know it?"""
        player = self.activePlayer
        if self.myself and player != self.myself and not self.playOpen:
            # we are human and server tells us another player discarded a tile. In our
            # game instance, tiles in handBoards of other players are unknown
            player.makeTileKnown(tileName)
            result = Tile.unknown
        else:
            result = tileName
        if not tileName in player.concealedTiles:
            raise Exception('I am %s. Player %s is told to show discard of tile %s but does not have it, he has %s' % \
                           (self.myself.name if self.myself else 'None',
                            player.name, result, player.concealedTiles))
        return result

    def hasDiscarded(self, player, tileName):
        """discards a tile from a player board"""
        # pylint: disable=too-many-branches
        # too many branches
        assert isinstance(tileName, Tile)
        if player != self.activePlayer:
            raise Exception('Player %s discards but %s is active' % (player, self.activePlayer))
        self.discardedTiles[tileName.exposed] += 1
        player.discarded.append(tileName)
        self.__concealedTileName(tileName) # has side effect, needs to be called
        if Internal.scene:
            player.handBoard.discard(tileName)
        self.lastDiscard = Tile(tileName)
        player.removeTile(self.lastDiscard)
        if any(tileName.exposed in x[0] for x in self.dangerousTiles):
            self.computeDangerous()
        else:
            self._endWallDangerous()
        self.handDiscardCount += 1

    def saveHand(self):
        """server told us to save this hand"""
        for player in self.players:
            assert player.hand.won == (player == self.winner), 'hand.won:%s winner:%s' % (
                player.hand.won, player == self.winner)
        Game.saveHand(self)

    def _mustExchangeSeats(self, pairs):
        """filter: which player pairs should really swap places?"""
        if self.belongsToPlayer():
            # if we are a client in a remote game, the server swaps and tells us the new places
            return []
        else:
            return pairs

    def _scanGameOption(self):
        """scan the --game option and go to start of wanted hand"""
        if '/' in self.wantedGame:
            first, last = (HandId(self, self.wantedGame, x) for x in (0, 1))
            if first > last:
                raise UserWarning('{}..{} is a negative range'.format(first, last))
            HandId(self, self.wantedGame).goto()

    def assignVoices(self):
        """now we have all remote user voices"""
        assert self.belongsToHumanPlayer()
        available = Voice.availableVoices()[:]
        # available is without transferred human voices
        for player in self.players:
            if player.voice and player.voice.oggFiles():
                # remote human player sent her voice, or we are human and have a voice
                if Debug.sound and player != self.myself:
                    logDebug('%s got voice from opponent: %s' % (player.name, player.voice))
            else:
                player.voice = Voice.locate(player.name)
                if player.voice:
                    if Debug.sound:
                        logDebug('%s has own local voice %s' % (player.name, player.voice))
            if player.voice:
                for voice in Voice.availableVoices():
                    if voice in available and voice.md5sum == player.voice.md5sum:
                        # if the local voice is also predefined,
                        # make sure we do not use both
                        available.remove(voice)
        # for the other players use predefined voices in preferred language. Only if
        # we do not have enough predefined voices, look again in locally defined voices
        predefined = [x for x in available if x.language() != 'local']
        predefined.extend(available)
        for player in self.players:
            if player.voice is None and predefined:
                player.voice = predefined.pop(0)
                if Debug.sound:
                    logDebug('%s gets one of the still available voices %s' % (player.name, player.voice))

    def dangerousFor(self, forPlayer, tile):
        """returns a list of explaining texts if discarding tile
        would be Dangerous game for forPlayer. One text for each
        reason - there might be more than one"""
        assert isinstance(tile, Tile), tile
        tile = tile.exposed
        result = []
        for dang, txt in self.dangerousTiles:
            if tile in dang:
                result.append(txt)
        for player in forPlayer.others():
            for dang, txt in player.dangerousTiles:
                if tile in dang:
                    result.append(txt)
        return result

    def computeDangerous(self, playerChanged=None):
        """recompute gamewide dangerous tiles. Either for playerChanged or for all players"""
        self.dangerousTiles = list()
        if playerChanged:
            playerChanged.findDangerousTiles()
        else:
            for player in self.players:
                player.findDangerousTiles()
        self._endWallDangerous()

    def _endWallDangerous(self):
        """if end of living wall is reached, declare all invisible tiles as dangerous"""
        if len(self.wall.living) <= 5:
            allTiles = [x for x in defaultdict.keys(elements.occurrence) if not x.isBonus]
            for tile in allTiles:
                assert isinstance(tile, Tile), tile
            # see http://www.logilab.org/ticket/23986
            invisibleTiles = set(x for x in allTiles if x not in self.visibleTiles)
            msg = m18n('Short living wall: Tile is invisible, hence dangerous')
            self.dangerousTiles = list(x for x in self.dangerousTiles if x[1] != msg)
            self.dangerousTiles.append((invisibleTiles, msg))

    def appendMove(self, player, command, kwargs):
        """append a Move object to self.moves"""
        self.moves.append(Move(player, command, kwargs))
