# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

import datetime
import weakref
import sys
from collections import defaultdict
from functools import total_ordering

from twisted.internet.defer import succeed
from util import gitHead
from kajcsv import CsvRow
from rand import CountingRandom
from log import logError, logWarning, logException, logDebug, i18n
from common import Internal, IntDict, Debug, Options
from common import ReprMixin, Speeds
from wind import Wind, East
from query import Query
from rule import Ruleset
from tile import Tile, elements
from tilesource import TileSource
from sound import Voice
from wall import Wall
from player import Players, Player, PlayingPlayer
from animation import animateAndDo, AnimationSpeed, ParallelAnimationGroup

if sys.platform != 'win32':
    import resource


@total_ordering
class HandId(ReprMixin):

    """handle a string representing a hand Id"""

    def __init__(self, game, string=None, stringIdx=0):
        self.game = game
        self.seed = game.seed
        self.roundsFinished = self.rotated = self.notRotated = 0
        self.moveCount = 0
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
        """get the --game option.
        stringIdx 0 is the part in front of ..
        stringIdx 1 is the part after ..
        """
        # pylint: disable=too-many-return-statements,too-many-branches
        if not string:
            return
        seed = int(string.split('/')[0])
        assert self.seed is None or self.seed == seed, string
        self.seed = seed
        if '/' not in string:
            if stringIdx == 1:
                self.roundsFinished = 100
            return
        string1 = string.split('/')[1]
        if not string1:
            logException('--game=%s must specify the wanted round' % string)
        parts = string1.split('..')
        if len(parts) == 2:
            if stringIdx == 0 and parts[0] == '':
                return
            if stringIdx == 1 and parts[1] == '':
                self.roundsFinished = 100
                return
        handId = parts[min(stringIdx, len(parts) - 1)]
        if handId[0].lower() not in 'eswn':
            logException('--game=%s must specify the round wind' % string)
        handWind = Wind(handId[0])
        ruleset = self.game.ruleset
        self.roundsFinished = handWind.__index__()
        if self.roundsFinished > ruleset.minRounds:
            logWarning(
                'Ruleset %s has %d minimum rounds but you want round %d(%s)'
                % (ruleset.name, ruleset.minRounds, self.roundsFinished + 1,
                   handWind))
            self.roundsFinished = ruleset.minRounds
            return
        self.rotated = int(handId[1]) - 1
        if self.rotated > 3:
            logWarning(
                'You want %d rotations, reducing to maximum of 3' %
                self.rotated)
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
        return

    def prompt(self, withSeed=True, withAI=True, withMoveCount=False):
        """
        Identifies the hand for window title and scoring table.

        @param withSeed: If set, include the seed used for the
        random generator.
        @type  withSeed: C{Boolean}
        @param withAI:   If set and AI != DefaultAI: include AI name for
        human players.
        @type  withAI:   C{Boolean}
        @param withMoveCount:   If set, include the current count of moves.
        @type  withMoveCount:   C{Boolean}
        @return:         The prompt.
        @rtype:          C{str}
        """
        aiVariant = ''
        if withAI and self.game.belongsToHumanPlayer():
            if self.game.myself:
                aiName = self.game.myself.intelligence.name()
            else:
                aiName = 'DefaultAI'
            if aiName != 'DefaultAI':
                aiVariant = aiName + '/'
        num = self.notRotated
        assert isinstance(num, int), num
        charId = ''
        while num:
            charId = chr(ord('a') + (num - 1) % 26) + charId
            num = (num - 1) // 26
        if not charId:
            charId = ' ' # align to the most common case
        wind = Wind.all4[self.roundsFinished % 4]
        if withSeed:
            seed = str(self.seed)
        else:
            seed = ''
        delim = '/' if withSeed or withAI else ''
        result = '%s%s%s%s%s%s' % (
            aiVariant, seed, delim, wind, self.rotated + 1, charId)
        if withMoveCount:
            result += '/%3d' % self.moveCount
        return result

    def token(self):
        """server and client use this for checking if they talk about
        the same thing"""
        return self.prompt(withAI=False)

    def __str__(self):
        return self.prompt()

    def __eq__(self, other):
        return (other
                and (self.roundsFinished, self.rotated, self.notRotated) ==
                (other.roundsFinished, other.rotated, other.notRotated))

    def __ne__(self, other):
        return not self == other

    def __lt__(self, other):
        return (self.roundsFinished, self.rotated, self.notRotated) < (
            other.roundsFinished, other.rotated, other.notRotated)


class Game:

    """the game without GUI"""
    # pylint: disable=too-many-instance-attributes
    playerClass = Player
    wallClass = Wall

    def __init__(self, names, ruleset, gameid=None,
                 wantedGame=None, client=None):
        """a new game instance. May be shown on a field, comes from database
        if gameid is set.

        Game.lastDiscard is the tile last discarded by any player. It is
        reset to None when a player gets a tile from the living end of the
        wall or after he claimed a discard.
        """
        assert self.__class__ != Game, 'Do not directly instantiate Game'
        for wind, name in names:
            assert isinstance(wind, Wind), 'Game.__init__ expects Wind objects'
            assert isinstance(name, str), 'Game.__init__: name must be string and not {}'.format(type(name))
        self.players = Players()
        # if we fail later on in init, at least we can still close the program
        # the player using this client instance for talking to the server
        self.__shouldSave = False
        self._client = None
        self.client = client
        self.rotated = 0
        self.notRotated = 0  # counts hands since last rotation
        self.ruleset = ruleset
        self.roundsFinished = 0
        self._currentHandId = None
        self._prevHandId = None
        self.wantedGame = wantedGame
        self.moves = []
        self.gameid = gameid
        self.playOpen = False
        self.autoPlay = False
        self.handctr = 0
        self.roundHandCount = 0
        self.handDiscardCount = 0
        self.divideAt = None
        self.__lastDiscard = None  # always uppercase
        self.visibleTiles = IntDict()
        self.discardedTiles = IntDict(self.visibleTiles)
        # tile names are always lowercase
        self.dangerousTiles = []
        self.csvTags = []
        self.randomGenerator = CountingRandom(self)
        self._setHandSeed()
        self.activePlayer = None
        self.__winner = None
        self._setGameId()
        self.__loadRuleset()
        # shift rules taken from the OEMC 2005 rules
        # 2nd round: S and W shift, E and N shift
        self.shiftRules = 'SWEN,SE,WE'
        self.wall = self.wallClass(self)
        # FIXME:  wall nach PlayingGame verschieben?
        self.assignPlayers(names)  # also defines self.myself
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
    def fullWallSize(self):
        """How many tiles we want to play with"""
        # the assertion for wallSize should not be done more often than needed: leave it in Wall()
        return int(Debug.wallSize) or elements.count(self.ruleset)

    @property
    def client(self):
        """hide weakref"""
        return self._client() if self._client else None

    @client.setter
    def client(self, value):
        """hide weakref"""
        if value:
            self._client = weakref.ref(value)
        else:
            self._client = None

    def clearHand(self):
        """empty all data"""
        while self.moves:
            _ = self.moves.pop()
            del _
        for player in self.players:
            player.clearHand()
        self.__winner = None
        self.prevActivePlayer = None
        self.dangerousTiles = []
        self.discardedTiles.clear()
        assert self.visibleTiles.count() == 0

    def _scanGameOption(self):
        """this is only done for PlayingGame"""

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
                raise ValueError('lastDiscard is exposed:%s' % value)

    @property
    def winner(self):
        """the name of the game server this game is attached to"""
        return self.__winner

    @winner.setter
    def winner(self, value):
        """the name of the game server this game is attached to"""
        if self.__winner != value:
            if self.__winner:
                self.__winner.invalidateHand()
            self.__winner = value
            if value:
                value.invalidateHand()

    @property
    def roundWind(self):
        """the round wind for Hand"""
        return Wind.all[self.roundsFinished % 4]

    def addCsvTag(self, tag, forAllPlayers=False):
        """tag will be written to tag field in csv row"""
        if forAllPlayers or self.belongsToHumanPlayer():
            self.csvTags.append('%s/%s' %
                                (tag, self.handId.prompt(withSeed=False)))

    def isFirstHand(self):
        """as the name says"""
        return self.roundHandCount == 0 and self.roundsFinished == 0

    def _setGameId(self):
        """virtual"""
        assert not self  # we want it to fail, and quieten pylint

    def close(self):
        """log off from the server and return a Deferred"""
        self.wall = None
        self.lastDiscard = None
        if Options.gui:
            ParallelAnimationGroup.cancelAll()

    def playerByName(self, playerName):
        """return None or the matching player"""
        if playerName is None:
            return None
        for myPlayer in self.players:
            if myPlayer.name == playerName:
                return myPlayer
        logException('Move references unknown player %s' % playerName)
        return None

    def losers(self):
        """the 3 or 4 losers: All players without the winner"""
        return list(x for x in self.players if x is not self.__winner)

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
        """does this game instance belong to a player
        (as opposed to the game server)?"""
        return self.belongsToRobotPlayer() or self.belongsToHumanPlayer()

    def assignPlayers(self, playerNames):
        """
        The server tells us the seating order and player names.

        @param playerNames: A list of 4 tuples. Each tuple holds wind and name.
        @type playerNames: The tuple contents must be C{str}
        @todo: Can we pass L{Players} instead of that tuple list?
        """
        if not self.players:
            self.players = Players()
            for idx in range(4):
                # append each separately: Until they have names, the current length of players
                # is used to assign one of the four walls to the player
                self.players.append(self.playerClass(
                    self, playerNames[idx][1]))
        for wind, name in playerNames:
            self.players.byName(name).wind = wind
        if self.client and self.client.name:
            self.myself = self.players.byName(self.client.name)
        self.sortPlayers()

    def __shufflePlayers(self):
        """assign random seats to the players and assign winds"""
        self.players.sort(key=lambda x: x.name)
        self.randomGenerator.shuffle(self.players)
        for player, wind in zip(self.players, Wind.all4):
            player.wind = wind

    def __exchangeSeats(self):
        """execute seat exchanges according to the rules"""
        winds = list(x for x in self.shiftRules.split(',')[(self.roundsFinished - 1) % 4])
        players = [self.players[Wind(x)] for x in winds]
        pairs = [players[x:x + 2] for x in range(0, len(winds), 2)]
        for playerA, playerB in self._mustExchangeSeats(pairs):
            playerA.wind, playerB.wind = playerB.wind, playerA.wind

    def _mustExchangeSeats(self, pairs):
        """filter: which player pairs should really swap places?"""
        return pairs

    def sortPlayers(self):
        """sort by wind order. Place ourself at bottom (idx=0)"""
        self.players.sort(key=lambda x: x.wind)
        self.activePlayer = self.players[East]
        if Internal.scene:
            if self.belongsToHumanPlayer():
                while self.players[0] != self.myself:
                    self.players = Players(self.players[1:] + self.players[:1])
                for idx, player in enumerate(self.players):
                    player.front = self.wall[idx]
                    player.sideText.board = player.front
                # we want names to move simultaneously
                self.players[1].sideText.refreshAll()

    @staticmethod
    def _newGameId():
        """write a new entry in the game table
        and returns the game id of that new entry"""
        return Query("insert into game(seed) values(0)").cursor.lastrowid

    def saveStartTime(self):
        """save starttime for this game"""
        starttime = datetime.datetime.now().replace(microsecond=0).isoformat()
        args = list([starttime, self.seed, int(self.autoPlay),
                     self.ruleset.rulesetId])
        args.extend([p.nameid for p in self.players])
        args.append(self.gameid)
        Query("update game set starttime=?,seed=?,autoplay=?,"
              "ruleset=?,p0=?,p1=?,p2=?,p3=? where id=?", tuple(args))

    def __loadRuleset(self):
        """use a copy of ruleset for this game, reusing an existing copy"""
        self.ruleset.load()
        if Internal.db:
            # only if we have a DB open. False in scoringtest.py
            query = Query(
                'select id from ruleset where id>0 and hash=?',
                (self.ruleset.hash,))
            if query.records:
                # reuse that ruleset
                self.ruleset.rulesetId = query.records[0][0]
            else:
                # generate a new ruleset
                self.ruleset.save()

    @property
    def seed(self):  # TODO: move this to PlayingGame
        """extract it from wantedGame. Set wantedGame if empty."""
        if not self.wantedGame:
            self.wantedGame = str(int(self.randomGenerator.random() * 10 ** 9))
        return int(self.wantedGame.split('/')[0])

    def _setHandSeed(self):  # TODO: move this to PlayingGame
        """set seed to a reproducible value, independent of what happened
        in previous hands/rounds.
        This makes it easier to reproduce game situations
        in later hands without having to exactly replay all previous hands"""
        seedFactor = ((self.roundsFinished + 1) * 10000
                      + self.rotated * 1000
                      + self.notRotated * 100)
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
        self.dangerousTiles = []
        self.discardedTiles.clear()
        assert self.visibleTiles.count() == 0
        if Internal.scene:
            # TODO: why not self.scene?
            Internal.scene.prepareHand()
        self._setHandSeed()

    def saveHand(self):
        """save hand to database,
        update score table and balance in status line"""
        self.__payHand()
        self._saveScores()
        self.handctr += 1
        self.notRotated += 1
        self.roundHandCount += 1
        self.handDiscardCount = 0

    def _saveScores(self):
        """save computed values to database,
        update score table and balance in status line"""
        scoretime = datetime.datetime.now().replace(microsecond=0).isoformat()
        logMessage = ''
        for player in self.players:
            if player.hand:
                manualrules = '||'.join(x.rule.name
                                        for x in player.hand.usedRules)
            else:
                manualrules = i18n('Score computed manually')
            Query(
                "INSERT INTO SCORE "
                "(game,hand,data,manualrules,player,scoretime,won,prevailing,"
                "wind,points,payments, balance,rotated,notrotated) "
                "VALUES(%d,%d,?,?,%d,'%s',%d,'%s','%s',%d,%d,%d,%d,%d)" %
                (self.gameid, self.handctr, player.nameid,
                 scoretime, int(player == self.__winner),
                 self.roundWind.char, player.wind,
                 player.handTotal, player.payment, player.balance,
                 self.rotated, self.notRotated),
                (player.hand.string, manualrules))
            logMessage += '{player:<12} {hand:>4} {total:>5} {won} | '.format(
                player=str(player)[:12], hand=player.handTotal,
                total=player.balance,
                won='WON' if player == self.winner else '   ')
            for usedRule in player.hand.usedRules:
                rule = usedRule.rule
                if rule.score.limits:
                    self.addCsvTag(rule.name.replace(' ', ''))
        if Debug.scores:
            self.debug(logMessage)

    def maybeRotateWinds(self):
        """rules which make winds rotate"""
        result = [x for x in self.ruleset.filterRules('rotate') if x.rotate(self)]
        if result:
            if Debug.explain:
                if not self.belongsToRobotPlayer():
                    self.debug(','.join(x.name for x in result), prevHandId=True)
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
            endtime = datetime.datetime.now().replace(
                microsecond=0).isoformat()
            with Internal.db as transaction:
                transaction.execute(
                    'UPDATE game set endtime = "%s" where id = %d' %
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
            if Internal.scene:
                with AnimationSpeed(Speeds.windDisc):
                    self.wall.showWindDiscs()

    def debug(self, msg, btIndent=None, prevHandId=False, showStack=False):
        """
        Log a debug message.

        @param msg: The message.
        @type msg: A string.
        @param btIndent: If given, message is indented by
        depth(backtrace)-btIndent
        @type btIndent: C{int}
        @param prevHandId: If True, do not use current handId but previous
        @type prevHandId: C{bool}
        """
        if self.belongsToRobotPlayer():
            prefix = 'R'
        elif self.belongsToHumanPlayer():
            prefix = 'C'
        elif self.belongsToGameServer():
            prefix = 'S'
        else:
            logDebug(msg, btIndent=btIndent)
            return
        handId = self._prevHandId if prevHandId else self.handId
        handId = handId.prompt(withMoveCount=True)
        logDebug(
            '%s%s: %s' % (prefix, handId, msg),
            withGamePrefix=False,
            btIndent=btIndent,
            showStack=showStack)

    @staticmethod
    def __getName(playerid):
        """get name for playerid
        """
        try:
            return Players.allNames[playerid]
        except KeyError:
            return i18n('Player %1 not known', playerid)

    @classmethod
    def loadFromDB(cls, gameid, client=None):
        """load game by game id and return a new Game instance"""
        Internal.logPrefix = 'S' if Internal.isServer else 'C'
        records = Query(
            "select p0,p1,p2,p3,ruleset,seed from game where id = ?",
            (gameid,)).records
        if not records:
            return None
        qGameRecord = records[0]
        rulesetId = qGameRecord[4] or 1
        ruleset = Ruleset.cached(rulesetId)
        Players.load()  # we want to make sure we have the current definitions
        records = Query(
            "select hand,rotated from score where game=? and hand="
            "(select max(hand) from score where game=?)",
            (gameid, gameid)).records
        if records:
            qLastHandRecord = records[0]
        else:
            qLastHandRecord = tuple([0, 0])
        qScoreRecords = Query(
            "select player, wind, balance, won, prevailing from score "
            "where game=? and hand=?",
            (gameid, qLastHandRecord[0])).records
        if not qScoreRecords:
            # this should normally not happen
            qScoreRecords = list(
                tuple([qGameRecord[wind], wind.char, 0, False, East.char])
                for wind in Wind.all4)
        if len(qScoreRecords) != 4:
            logError('game %d inconsistent: There should be exactly '
                     '4 score records for the last hand' % gameid)

        # after loading SQL, prepare values.

        # default value. If the server saved a score entry but our client
        # did not, we get no record here. Should we try to fix this or
        # exclude such a game from the list of resumable games?
        if len({x[4] for x in qScoreRecords}) != 1:
            logError('game %d inconsistent: All score records for the same '
                     'hand must have the same prevailing wind' % gameid)

        players = [tuple([Wind(x[1]), Game.__getName(x[0])]) for x in qScoreRecords]

        # create the game instance.
        game = cls(players, ruleset, gameid=gameid, client=client,
                   wantedGame=qGameRecord[5])
        game.handctr, game.rotated = qLastHandRecord

        for record in qScoreRecords:
            playerid = record[0]
            player = game.players.byId(playerid)
            if not player:
                logError(
                    'game %d inconsistent: player %d missing in game table' %
                    (gameid, playerid))
            else:
                player.getsPayment(record[2])
            if record[3]:
                game.winner = player
        game.roundsFinished = Wind(qScoreRecords[0][4]).__index__()
        game.handctr += 1
        game.notRotated += 1
        game.maybeRotateWinds()
        game.sortPlayers()
        with AnimationSpeed(Speeds.windDisc):
            animateAndDo(game.wall.decorate4)
        return game

    def finished(self):
        """The game is over after minRounds completed rounds. Also,
        check if we reached the second handId defined by --game.
        If we did, the game is over too"""
        last = HandId(self, self.wantedGame, 1)
        if self.handId > last:
            return True
        if Options.rounds:
            return self.roundsFinished >= Options.rounds
        if self.ruleset:
            # while initialising Game, ruleset might be None
            return self.roundsFinished >= self.ruleset.minRounds
        return None

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
                    self.debug('%s: winner %s. %s pays for all' %
                               (self.handId, winner, guilty))
                guilty.hand.usedRules.append((payAction, None))
                score = winner.handTotal
                score = score * 6 if winner.wind == East else score * 4
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
                    if East in (player1.wind, player2.wind):
                        efactor = 2
                    else:
                        efactor = 1
                    if player2 != winner:
                        player1.getsPayment(player1.handTotal * efactor)
                    if player1 != winner:
                        player1.getsPayment(-player2.handTotal * efactor)

    def lastMoves(self, only=None, without=None, withoutNotifications=False):
        """filters and yields the moves in reversed order"""
        for idx in range(len(self.moves) - 1, -1, -1):
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
        """set random living and kongBox
        sets divideAt: an index for the wall break"""
        breakWall = self.randomGenerator.randrange(4)
        sideLength = len(self.wall) // 4
        # use the sum of four dices to find the divide
        self.divideAt = breakWall * sideLength + \
            sum(self.randomGenerator.randrange(1, 7) for idx in range(4))
        if self.divideAt % 2 == 1:
            self.divideAt -= 1
        self.divideAt %= len(self.wall)


class PlayingGame(Game):
    """this game is played using the computer"""

    # pylint: disable=too-many-instance-attributes,useless-suppression
    # pylint 2.16.2 is erratic here, sometimes it warns, sometimes not

    playerClass = PlayingPlayer

    def __init__(self, names, ruleset, gameid=None, wantedGame=None,
                 client=None, playOpen=False, autoPlay=False):
        """a new game instance, comes from database if gameid is set"""
        self.__activePlayer = None
        self.prevActivePlayer = None
        self.defaultNameBrush = None
        Game.__init__(self, names, ruleset,
                      gameid, wantedGame=wantedGame, client=client)
        self.players[East].lastSource = TileSource.East14th
        self.playOpen = playOpen
        self.autoPlay = autoPlay
        if self.belongsToHumanPlayer():
            myself = self.myself
            myself.voice = Voice.locate(myself.name)
            if myself.voice:
                if Debug.sound:
                    logDebug('myself %s gets voice %s' % (
                        myself.name, myself.voice))
            else:
                if Debug.sound:
                    logDebug('myself %s gets no voice' % (myself.name))

    def writeCsv(self):
        """write game summary to Options.csv"""
        if self.finished() and Options.csv:
            gameWinner = max(self.players, key=lambda x: x.balance)
            if Debug.process and sys.platform != 'win32':
                self.csvTags.append('MEM:%s' % resource.getrusage(
                    resource.RUSAGE_SELF).ru_maxrss)
            if Options.rounds:
                self.csvTags.append('ROUNDS:%s' % Options.rounds)
            _ = CsvRow.fields
            row = [''] * CsvRow.fields.PLAYERS
            row[_.GAME] = str(self.seed)
            row[_.RULESET] = self.ruleset.name
            row[_.AI] = Options.AI
            row[_.COMMIT] = gitHead()
            row[_.PY_VERSION] = '{}.{}'.format(*sys.version_info[:2])
            row[_.TAGS] = ','.join(self.csvTags)
            for player in sorted(self.players, key=lambda x: x.name):
                row.append(player.name)
                row.append(player.balance)
                row.append(player.wonCount)
                row.append(1 if player == gameWinner else 0)
            CsvRow(row).write()

    def close(self):
        """log off from the server and return a Deferred"""
        Game.close(self)
        self.writeCsv()
        Internal.autoPlay = False  # do that only for the first game
        if self.client:
            client = self.client
            self.client = None
            result = client.logout()
        else:
            result = succeed(None)
        return result

    def _setGameId(self):
        """do nothing, we already went through the game id reservation"""

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
            if Internal.scene:  # mark the name of the active player in blue
                for _ in self.players:
                    _.colorizeName()

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
        records = Query("select seed from game where id=?", (
            self.gameid,)).records
        assert records, 'self.gameid: %s' % self.gameid
        seed = records[0][0]

        if not Internal.isServer and self.client:
            host = self.client.connection.url
        else:
            host = None

        if seed in ('proposed', host):
            # we reserved the game id by writing a record with seed == host
            Game.saveStartTime(self)

    def _saveScores(self):
        """save computed values to database, update score table
        and balance in status line"""
        if self.shouldSave:
            if self.belongsToRobotPlayer():
                assert False, 'shouldSave must not be True for robot player'
            Game._saveScores(self)

    def nextPlayer(self, current=None):
        """return the player after current or after activePlayer"""
        if not current:
            current = self.activePlayer
        pIdx = self.players.index(current)
        return self.players[(pIdx + 1) % 4]

    def nextTurn(self):
        """move activePlayer"""
        self.activePlayer = self.nextPlayer()

    def _concealedTileName(self, tileName):
        """tileName has been discarded, by which name did we know it?"""
        player = self.activePlayer
        if player != self.myself and not self.playOpen:
            # we are human and server tells us another player discarded
            # a tile. In our game instance, tiles in handBoards of other
            # players are unknown
            player.makeTileKnown(tileName)
            result = Tile.unknown
        else:
            result = tileName
        if tileName not in player.concealedTiles:
            raise ValueError('I am %s. Player %s is told to show discard '
                            'of tile %s but does not have it, he has %s' %
                            (self.myself.name if self.myself else 'None',
                             player.name, result, player.concealedTiles))
        return result

    def hasDiscarded(self, player, tile):
        """discards a tile from a player board"""
        assert isinstance(tile, Tile)
        if player != self.activePlayer:
            raise ValueError('Player %s discards but %s is active' % (
                player, self.activePlayer))
        self.discardedTiles[tile.exposed] += 1
        player.discarded.append(tile)
        player.lastTile = Tile.unknown
        self._concealedTileName(tile)
        # the above has side effect, needs to be called
        if Internal.scene:
            player.handBoard.discard(tile)
        self.lastDiscard = tile
        player.removeConcealedTile(self.lastDiscard)
        if any(tile.exposed in x[0] for x in self.dangerousTiles):
            self.computeDangerous()
        else:
            self._endWallDangerous()
        self.handDiscardCount += 1

    def saveHand(self):
        """server told us to save this hand"""
        for player in self.players:
            handWonMatches = player.hand.won == (player == self.winner)
            assert handWonMatches, 'hand.won:%s winner:%s' % (
                player.hand.won, player == self.winner)
        Game.saveHand(self)

    def _mustExchangeSeats(self, pairs):
        """filter: which player pairs should really swap places?"""
        # if we are a client in a remote game, the server swaps and tells
        # us the new places
        return [] if self.belongsToPlayer() else pairs

    def _scanGameOption(self):
        """scan the --game option and go to start of wanted hand"""
        if '/' in self.wantedGame:
            first, last = (HandId(self, self.wantedGame, x) for x in (0, 1))
            if first > last:
                raise UserWarning('{}..{} is a negative range'.format(
                    first, last))
            HandId(self, self.wantedGame).goto()

    def assignVoices(self):
        """now we have all remote user voices"""
        assert self.belongsToHumanPlayer()
        available = Voice.availableVoices()[:]
        # available is without transferred human voices
        for player in self.players:
            if player.voice and player.voice.oggFiles():
                # remote human player sent her voice, or we are human
                # and have a voice
                if Debug.sound and player != self.myself:
                    logDebug('%s got voice from opponent: %s' % (
                        player.name, player.voice))
            else:
                player.voice = Voice.locate(player.name)
                if player.voice:
                    if Debug.sound:
                        logDebug('%s has own local voice %s' % (
                            player.name, player.voice))
            if player.voice:
                for voice in Voice.availableVoices():
                    if (voice in available
                            and voice.md5sum == player.voice.md5sum):
                        # if the local voice is also predefined,
                        # make sure we do not use both
                        available.remove(voice)
        # for the other players use predefined voices in preferred language.
        # Only if we do not have enough predefined voices, look again in
        # locally defined voices
        predefined = [x for x in available if x.language() != 'local']
        predefined.extend(available)
        for player in self.players:
            if player.voice is None and predefined:
                player.voice = predefined.pop(0)
                if Debug.sound:
                    logDebug(
                        '%s gets one of the still available voices %s' % (
                            player.name, player.voice))

    def dangerousFor(self, forPlayer, tile):
        """return a list of explaining texts if discarding tile
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
        """recompute gamewide dangerous tiles. Either for playerChanged or
        for all players"""
        self.dangerousTiles = []
        if playerChanged:
            playerChanged.findDangerousTiles()
        else:
            for player in self.players:
                player.findDangerousTiles()
        self._endWallDangerous()

    def _endWallDangerous(self):
        """if end of living wall is reached, declare all invisible tiles
        as dangerous"""
        if len(self.wall.living) <= 5:
            allTiles = [x for x in defaultdict.keys(elements.occurrence)
                        if not x.isBonus]
            for tile in allTiles:
                assert isinstance(tile, Tile), tile
            # see https://www.logilab.org/ticket/23986
            invisibleTiles = {x for x in allTiles if x not in self.visibleTiles}
            msg = i18n('Short living wall: Tile is invisible, hence dangerous')
            self.dangerousTiles = [x for x in self.dangerousTiles if x[1] != msg]
            self.dangerousTiles.append((invisibleTiles, msg))
