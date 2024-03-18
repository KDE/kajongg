# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

import datetime
import weakref
import sys
from functools import total_ordering

from typing import List, Optional, Tuple, TYPE_CHECKING, Union, Dict, Iterable, Generator, Any, Set, cast

from twisted.internet.defer import succeed
from util import gitHead
from kajcsv import CsvRow
from rand import CountingRandom
from log import logError, logWarning, logException, logDebug, i18n
from common import Internal, IntDict, Debug, Options
from common import ReprMixin, Speeds
from wind import Wind, East
from query import Query, openDb, closeDb
from rule import Ruleset, UsedRule
from tile import Tile, elements
from tilesource import TileSource
from sound import Voice
from wall import Wall
from player import Players, Player, PlayingPlayer
from animation import animateAndDo, AnimationSpeed, ParallelAnimationGroup

if sys.platform != 'win32':
    import resource

if TYPE_CHECKING:
    from twisted.internet.defer import Deferred
    from move import Move
    from client import Client
    from uiwall import UIWall
    from message import Message
    from handboard import PlayingHandBoard
    from servertable import ServerGame


@total_ordering
class HandId(ReprMixin):

    """handle a string representing a hand Id"""

    def __init__(self, game:'Game', string:Optional[str]=None, stringIdx:int=0) ->None:
        self.game = game
        self.seed:int = game.seed
        self.roundsFinished:int = 0
        self.rotated:int = 0
        self.notRotated:int = 0
        self.moveCount:int = 0
        if string is None:
            self.roundsFinished = game.roundsFinished
            self.rotated = game.rotated
            self.notRotated = game.notRotated
            self.moveCount = len(game.moves)
        else:
            self.__scanHandId(string, stringIdx)
        assert self.rotated < 4, self
        openDb()

    def goto(self) ->None:
        """advance game to self"""
        for _ in range(self.roundsFinished * 4 + self.rotated):
            self.game.rotateWinds()
        self.game.notRotated = self.notRotated

    def __scanHandId(self, string:str, stringIdx:int) ->None:
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
            logException(f'--game={string} must specify the wanted round')
        parts = string1.split('..')
        if len(parts) == 2:
            if stringIdx == 0 and parts[0] == '':
                return
            if stringIdx == 1 and parts[1] == '':
                self.roundsFinished = 100
                return
        handId = parts[min(stringIdx, len(parts) - 1)]
        if handId[0].lower() not in 'eswn':
            logException(f'--game={string} must specify the round wind')
        handWind = Wind(handId[0])
        ruleset = self.game.ruleset
        self.roundsFinished = handWind.__index__()
        minRounds = ruleset.minRounds  # type:ignore[attr-defined]
        if self.roundsFinished > minRounds:
            logWarning(
                f'Ruleset {ruleset.name} has {int(minRounds)} minimum rounds '
                f'but you want round {int(self.roundsFinished + 1)}({handWind})')
            self.roundsFinished = minRounds
            return
        self.rotated = int(handId[1]) - 1
        if self.rotated > 3:
            logWarning(
                f'You want {int(self.rotated)} rotations, reducing to maximum of 3')
            self.rotated = 3
            return
        for char in handId[2:]:
            if char < 'a':
                logWarning(f'you want {char}, changed to a')
                char = 'a'
            if char > 'z':
                logWarning(f'you want {char}, changed to z')
                char = 'z'
            self.notRotated = self.notRotated * 26 + ord(char) - ord('a') + 1
        return

    def prompt(self, withSeed:bool=True, withAI:bool=True, withMoveCount:bool=False) ->str:
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
            seedStr = str(self.seed)
        else:
            seedStr = ''
        delim = '/' if withSeed or withAI else ''
        result = f'{aiVariant}{seedStr}{delim}{wind}{self.rotated + 1}{charId}'
        if withMoveCount:
            result += f'/{int(self.moveCount):3}'
        return result

    def token(self) ->str:
        """server and client use this for checking if they talk about
        the same thing"""
        return self.prompt(withAI=False)

    def __str__(self) ->str:
        return self.prompt()

    def __eq__(self, other:Optional['HandId']) ->bool:  # type:ignore[override]
        return (other is not None
                and (self.roundsFinished, self.rotated, self.notRotated) ==
                (other.roundsFinished, other.rotated, other.notRotated))

    def __ne__(self, other:Optional['HandId']) ->bool:  # type:ignore[override]
        return not self == other

    def __lt__(self, other:'HandId') ->bool:  # type:ignore[override]
        return (self.roundsFinished, self.rotated, self.notRotated) < (
            other.roundsFinished, other.rotated, other.notRotated)


class Game:

    """the game without GUI"""
    # pylint: disable=too-many-instance-attributes
    playerClass = Player
    wallClass = Wall

    def __init__(self, names:List[Tuple['Wind', str]], ruleset:Ruleset, gameid:Optional[int]=None,
                 wantedGame:Optional[str]=None, client:Optional['Client']=None):
        """a new game instance. May be shown on a field, comes from database
        if gameid is set.

        Game.lastDiscard is the tile last discarded by any player. It is
        reset to None when a player gets a tile from the living end of the
        wall or after he claimed a discard.
        """
        assert self.__class__ != Game, 'Do not directly instantiate Game'
        for wind, name in names:
            assert isinstance(wind, Wind), 'Game.__init__ expects Wind objects'
            assert isinstance(name, str), f'Game.__init__: name must be string and not {type(name)}'
        self.players = Players()
        # if we fail later on in init, at least we can still close the program
        self.myself:Player
        self.prevActivePlayer:Optional[Player]
        # the player using this client instance for talking to the server
        self.__shouldSave = False
        self._client = None
        self.client = client
        self.rotated:int = 0
        self.notRotated:int = 0  # counts hands since last rotation
        self.ruleset:Ruleset = ruleset
        self.roundsFinished:int = 0
        self._currentHandId:Optional[HandId] = None
        self._prevHandId:Optional[HandId] = None
        self.wantedGame:Optional[str] = wantedGame
        self.moves:List['Move'] = []
        self.gameid:Optional[int] = gameid
        self.playOpen:bool = False
        self.autoPlay:bool = False
        self.handctr:int = 0
        self.roundHandCount:int = 0
        self.handDiscardCount:int = 0
        self.divideAt:Optional[int] = None
        self.__lastDiscard:Optional[Tile] = None  # always uppercase
        self.visibleTiles:Dict[Tile, int] = IntDict()
        self.discardedTiles:Dict[Tile, int] = IntDict(self.visibleTiles)
        # tile names are always lowercase
        self.dangerousTiles:List[Tuple[Set[Tile], str]] = []
        self.csvTags:List[str] = []
        self.randomGenerator:CountingRandom = CountingRandom(self)
        self._setHandSeed()
        self.activePlayer:Optional[Player] = None
        self.__winner:Optional[Player] = None
        self._setGameId()
        self.__loadRuleset()
        # shift rules taken from the OEMC 2005 rules
        # 2nd round: S and W shift, E and N shift
        self.shiftRules = 'SWEN,SE,WE'
        self.wall:Optional[Wall] = self.wallClass(self)  # type:ignore[arg-type]
        # FIXME:  wall nach PlayingGame verschieben?
        self.assignPlayers(names)  # also defines self.myself
        if self.belongsToGameServer():
            self.__shufflePlayers()
        self._scanGameOption()
        for player in self.players:
            player.clearHand()

    @property
    def shouldSave(self) ->bool:
        """as a property"""
        return self.__shouldSave

    @shouldSave.setter
    def shouldSave(self, value:bool) ->None:
        """if activated, save start time"""
        if value and not self.__shouldSave:
            self.saveStartTime()
        self.__shouldSave = value

    @property
    def handId(self) ->HandId:
        """current position in game"""
        result = HandId(self)
        if result != self._currentHandId:
            self._prevHandId = self._currentHandId
            self._currentHandId = result
        return result

    @property
    def fullWallSize(self) ->int:
        """How many tiles we want to play with"""
        # the assertion for wallSize should not be done more often than needed: leave it in Wall()
        return int(Debug.wallSize) or elements.count(self.ruleset)

    @property
    def client(self) ->Optional['Client']:
        """hide weakref"""
        return self._client() if self._client else None

    @client.setter
    def client(self, value:Optional['Client']) ->None:
        """hide weakref"""
        if value:
            self._client = weakref.ref(value)
        else:
            self._client = None

    def clearHand(self) ->None:
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
        assert cast(IntDict, self.visibleTiles).count() == 0

    def _scanGameOption(self) ->None:
        """this is only done for PlayingGame"""

    @property
    def lastDiscard(self) ->Optional[Tile]:
        """hide weakref"""
        return self.__lastDiscard

    @lastDiscard.setter
    def lastDiscard(self, value:Optional[Tile]) ->None:
        """hide weakref"""
        self.__lastDiscard = value
        if value is not None:
            assert isinstance(value, Tile), value
            if value.isExposed:
                raise ValueError(f'lastDiscard is exposed:{value}')

    @property
    def winner(self) ->Optional['Player']:
        """the name of the game server this game is attached to"""
        return self.__winner

    @winner.setter
    def winner(self, value:Optional['Player']) ->None:
        """the name of the game server this game is attached to"""
        if self.__winner != value:
            if self.__winner:
                self.__winner.invalidateHand()
            self.__winner = value
            if value:
                value.invalidateHand()

    @property
    def roundWind(self) ->Wind:
        """the round wind for Hand"""
        return Wind.all[self.roundsFinished % 4]

    def addCsvTag(self, tag:str, forAllPlayers:bool=False) ->None:
        """tag will be written to tag field in csv row"""
        if forAllPlayers or self.belongsToHumanPlayer():
            self.csvTags.append(f'{tag}/{self.handId.prompt(withSeed=False)}')

    def isFirstHand(self) ->bool:
        """as the name says"""
        return self.roundHandCount == 0 and self.roundsFinished == 0

    def _setGameId(self) ->None:
        """virtual"""
        assert not self  # we want it to fail, and quieten pylint

    def close(self) ->None:
        """log off from the server"""
        self.wall = None
        self.lastDiscard = None
        closeDb()
        if Options.gui:
            ParallelAnimationGroup.cancelAll()

    def playerByName(self, playerName:str) ->Optional[Player]:
        """return None or the matching player"""
        if playerName is None:
            return None
        for myPlayer in self.players:
            if myPlayer.name == playerName:
                return myPlayer
        logException(f'Move references unknown player {playerName}')
        return None

    def losers(self) ->List[Player]:
        """the 3 or 4 losers: All players without the winner"""
        return list(x for x in self.players if x is not self.__winner)

    def belongsToRobotPlayer(self) ->bool:
        """does this game instance belong to a robot player?"""
        return self.client is not None and self.client.isRobotClient()

    def belongsToHumanPlayer(self) ->bool:
        """does this game instance belong to a human player?"""
        return self.client is not None and self.client.isHumanClient()

    def belongsToGameServer(self) ->bool:
        """does this game instance belong to the game server?"""
        return self.client is not None and self.client.isServerClient()

    @staticmethod
    def isScoringGame() ->bool:
        """are we scoring a manual game?"""
        return False

    def belongsToPlayer(self) ->bool:
        """does this game instance belong to a player
        (as opposed to the game server)?"""
        return self.belongsToRobotPlayer() or self.belongsToHumanPlayer()

    def assignPlayers(self, playerNames:List[Tuple[Wind, str]]) ->None:
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
            _ = self.players.byName(name)
            assert _
            _.wind = wind
        if self.client and self.client.name:
            _ = self.players.byName(self.client.name)
            assert _
            self.myself = _
        self.sortPlayers()

    def __shufflePlayers(self) ->None:
        """assign random seats to the players and assign winds"""
        self.players.sort(key=lambda x: x.name)
        self.randomGenerator.shuffle(self.players)
        for player, wind in zip(self.players, Wind.all4):
            player.wind = wind

    def __exchangeSeats(self) ->None:
        """execute seat exchanges according to the rules"""
        winds = list(x for x in self.shiftRules.split(',')[(self.roundsFinished - 1) % 4])
        players = [self.players[Wind(x)] for x in winds]
        pairs = [players[x:x + 2] for x in range(0, len(winds), 2)]
        for playerA, playerB in self._mustExchangeSeats(pairs):
            playerA.wind, playerB.wind = playerB.wind, playerA.wind

    def _mustExchangeSeats(self, pairs:List[List[Player]]) ->List[List[Player]]:
        """filter: which player pairs should really swap places?"""
        return pairs

    def sortPlayers(self) ->None:
        """sort by wind order. Place ourself at bottom (idx=0)"""
        self.players.sort(key=lambda x: x.wind)
        self.activePlayer = self.players[East]
        if Internal.scene:
            if self.belongsToHumanPlayer():
                while self.players[0] != self.myself:
                    self.players = Players(self.players[1:] + self.players[:1])
                for idx, player in enumerate(self.players):
                    assert self.wall
                    player.front = cast('UIWall', self.wall)[idx]
                    if hasattr(player, 'sideText'):
                        if player.sideText.board is not player.front:
                            player.sideText.animateNextChange = True
                        player.sideText.board = player.front

    @staticmethod
    def _newGameId() ->int:
        """write a new entry in the game table
        and returns the game id of that new entry"""
        return Query("insert into game(seed) values(0)").cursor.lastrowid

    def saveStartTime(self) ->None:
        """save starttime for this game"""
        starttime = datetime.datetime.now().replace(microsecond=0).isoformat()
        args:List[Union[str, int, float]] = list([starttime, self.seed, int(self.autoPlay),
                     self.ruleset.rulesetId])
        args.extend([p.nameid for p in self.players])
        assert self.gameid
        args.append(self.gameid)
        Query("update game set starttime=?,seed=?,autoplay=?,"
              "ruleset=?,p0=?,p1=?,p2=?,p3=? where id=?", tuple(args))

    def __loadRuleset(self) ->None:
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
    def seed(self) ->int:  # TODO: move this to PlayingGame
        """extract it from wantedGame. Set wantedGame if empty."""
        if not self.wantedGame:
            self.wantedGame = str(int(self.randomGenerator.random() * 10 ** 9))
        return int(self.wantedGame.split('/')[0])

    def _setHandSeed(self) ->None:  # TODO: move this to PlayingGame
        """set seed to a reproducible value, independent of what happened
        in previous hands/rounds.
        This makes it easier to reproduce game situations
        in later hands without having to exactly replay all previous hands"""
        seedFactor = ((self.roundsFinished + 1) * 10000
                      + self.rotated * 1000
                      + self.notRotated * 100)
        self.randomGenerator.seed(self.seed * seedFactor)

    def prepareHand(self) ->None:
        """prepare a game hand"""
        self.clearHand()
        if self.finished():
            if Options.rounds:
                self.close().addCallback(Internal.mainWindow.close).addErrback(logException)
            else:
                self.close()

    def initHand(self) ->None:
        """directly before starting"""
        self.dangerousTiles = []
        self.discardedTiles.clear()
        assert cast(IntDict, self.visibleTiles).count() == 0
        if Internal.scene:
            # TODO: why not self.scene?
            Internal.scene.prepareHand()
        self._setHandSeed()

    def saveHand(self) ->None:
        """save hand to database,
        update score table and balance in status line"""
        self.__payHand()
        self._saveScores()
        self.handctr += 1
        self.notRotated += 1
        self.roundHandCount += 1
        self.handDiscardCount = 0

    def _saveScores(self) ->None:
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
            assert self.gameid
            Query(
                "INSERT INTO SCORE "  # pylint:disable=consider-using-f-string
                "(game,hand,data,manualrules,player,scoretime,won,prevailing,"
                "wind,points,payments, balance,rotated,notrotated) "
                "VALUES(%d,%d,?,?,%d,'%s',%d,'%s','%s',%d,%d,%d,%d,%d)" %
                (self.gameid, self.handctr, player.nameid,
                 scoretime, int(player == self.__winner),
                 self.roundWind.char, player.wind,
                 player.handTotal, player.payment, player.balance,
                 self.rotated, self.notRotated),
                (player.hand.string, manualrules))
            logMessage += (f"{str(player)[:12]:<12} {player.handTotal:>4} {player.balance:>5} "
                          f"{'WON' if player == self.winner else '   '} | ")
            for usedRule in player.hand.usedRules:
                rule = usedRule.rule
                if rule.score.limits:
                    self.addCsvTag(rule.name.replace(' ', ''))
        if Debug.scores:
            self.debug(logMessage)

    def maybeRotateWinds(self) ->bool:
        """rules which make winds rotate"""
        result = [x for x in self.ruleset.filterRules('rotate') if x.rotate(self)]  # type:ignore[attr-defined]
        if result:
            if Debug.explain:
                if not self.belongsToRobotPlayer():
                    self.debug(','.join(x.name for x in result), prevHandId=True)
            self.rotateWinds()
        return bool(result)

    def rotateWinds(self) ->None:
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
            assert self.gameid
            with Internal.db as transaction:
                transaction.execute(
                    f'UPDATE game set endtime = "{endtime}" where id = {int(self.gameid)}')
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
                    cast('UIWall', self.wall).showWindDiscs()

    def debug(self, msg:str, btIndent:Optional[int]=None, prevHandId:bool=False, showStack:bool=False) ->None:
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
        assert handId
        handId_str = handId.prompt(withMoveCount=True)
        logDebug(
            f'{prefix}{handId_str}: {msg}',
            withGamePrefix=False,
            btIndent=btIndent,
            showStack=showStack)

    @staticmethod
    def __getName(playerid:int) ->str:
        """get name for playerid
        """
        try:
            return Players.allNames[playerid]
        except KeyError:
            return i18n('Player %1 not known', playerid)

    @classmethod
    def loadFromDB(cls, gameid:int, client:Optional['Client']=None) ->Optional[Union['Game', 'ServerGame']]:
        """load game by game id and return a new Game instance"""
        # TODO would be nice to use cls in result annotation, but how?
        Internal.logPrefix = 'S' if Internal.isServer else 'C'
        records = Query(
            "select p0,p1,p2,p3,ruleset,seed from game where id = ?",
            (gameid,)).records
        if not records:
            return None
        qGameRecord = records[0]
        rulesetId = int(qGameRecord[4]) or 1
        ruleset = Ruleset.cached(rulesetId)
        Players.load()  # we want to make sure we have the current definitions
        records = Query(
            "select hand,rotated from score where game=? and hand="
            "(select max(hand) from score where game=?)",
            (gameid, gameid)).records
        if records:
            qLastHandRecord = records[0]
        else:
            qLastHandRecord = [0, 0]
        qScoreRecords = Query(
            "select player, wind, balance, won, prevailing from score "
            "where game=? and hand=?",
            (gameid, qLastHandRecord[0])).records
        if not qScoreRecords:
            # this should normally not happen
            qScoreRecords = list(
                list([qGameRecord[wind], wind.char, 0, False, East.char])
                for wind in Wind.all4)
        if len(qScoreRecords) != 4:
            logError(f'game {int(gameid)} inconsistent: There should be exactly 4 score records for the last hand')

        # after loading SQL, prepare values.

        # default value. If the server saved a score entry but our client
        # did not, we get no record here. Should we try to fix this or
        # exclude such a game from the list of resumable games?
        if len({x[4] for x in qScoreRecords}) != 1:
            logError(f'game {int(gameid)} inconsistent: '
                     f'All score records for the same hand must have the same prevailing wind')

        players = list((Wind(x[1]), Game.__getName(x[0])) for x in qScoreRecords)

        # create the game instance.
        game = cls(players, ruleset, gameid=gameid, client=client,
                   wantedGame=qGameRecord[5])
        game.handctr, game.rotated = qLastHandRecord

        for record in qScoreRecords:
            playerid = record[0]
            player = game.players.byId(playerid)
            if not player:
                logError(
                    f'game {int(gameid)} inconsistent: player {int(playerid)} missing in game table')
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
            assert game.wall
            animateAndDo(game.wall.decorate4)
        return game

    def finished(self) ->bool:
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
        return False

    def __payHand(self) ->None:
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
                    self.debug(f'{self.handId}: winner {winner}. {guilty} pays for all')
                guilty.hand.usedRules.append(UsedRule(payAction))
                score = winner.handTotal
                score = score * 6 if winner.wind == East else score * 4
                guilty.getsPayment(-score)
                winner.getsPayment(score)
                return

        for player1 in self.players:
            if Debug.explain:
                if not self.belongsToRobotPlayer():
                    self.debug(f'{player1}: {player1.hand.string}')
                    for line in player1.hand.explain():
                        self.debug(f'   {line}')
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

    def lastMoves(self, only:Optional[Iterable['Message']]=None,
        without:Optional[Iterable['Message']]=None,
        withoutNotifications:bool=False) ->Generator['Move', None, None]:
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

    def throwDices(self) ->None:
        """set random living and kongBox
        sets divideAt: an index for the wall break"""
        breakWall = self.randomGenerator.randrange(4)
        assert self.wall
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

    def __init__(self, names:List[Tuple['Wind', str]], ruleset:Ruleset, gameid:Optional[int]=None,
                 wantedGame:Optional[str]=None, client:Optional['Client']=None,
                 playOpen:bool=False, autoPlay:bool=False) ->None:
        """a new game instance, comes from database if gameid is set"""
        self.__activePlayer:Optional[PlayingPlayer] = None
        self.prevActivePlayer:Optional[PlayingPlayer] = None
        self.defaultNameBrush = None
        Game.__init__(self, names, ruleset,
                      gameid, wantedGame=wantedGame, client=client)
        self.players[East].lastSource = TileSource.East14th
        self.playOpen = playOpen
        self.autoPlay = autoPlay
        if self.belongsToHumanPlayer():
            myself = cast(PlayingPlayer, self.myself)
            myself.voice = Voice.locate(myself.name)
            if myself.voice:
                if Debug.sound:
                    logDebug(f'myself {myself.name} gets voice {myself.voice}')
            else:
                if Debug.sound:
                    logDebug(f'myself {myself.name} gets no voice')

    def writeCsv(self) ->None:
        """write game summary to Options.csv"""
        if self.finished() and Options.csv:
            gameWinner = max(self.players, key=lambda x: x.balance)
            if Debug.process and sys.platform != 'win32':
                self.csvTags.append(f'MEM:{resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}')
            if Options.rounds:
                self.csvTags.append(f'ROUNDS:{Options.rounds}')
            _ = CsvRow.fields
            row = [''] * CsvRow.fields.PLAYERS
            row[_.GAME] = str(self.seed)
            row[_.RULESET] = self.ruleset.name
            row[_.AI] = Options.AI
            row[_.COMMIT] = gitHead()
            row[_.PY_VERSION] = '{}.{}'.format(*sys.version_info[:2])  # pylint:disable=consider-using-f-string
            row[_.TAGS] = ','.join(self.csvTags)
            for player in sorted(self.players, key=lambda x: x.name):
                row.append(player.name)
                row.append(player.balance)
                row.append(player.wonCount)
                row.append(1 if player == gameWinner else 0)
            CsvRow(row).write()

    def close(self) ->Any:
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

    def _setGameId(self) ->None:
        """do nothing, we already went through the game id reservation"""

    @property  # type:ignore[override]
    def activePlayer(self) ->PlayingPlayer:
        """the turn is on this player"""
        result = self.__activePlayer
        assert result
        return result

    @activePlayer.setter
    def activePlayer(self, player:PlayingPlayer) ->None:
        """the turn is on this player"""
        if self.__activePlayer != player:
            self.prevActivePlayer = self.__activePlayer
            if self.prevActivePlayer:
                self.prevActivePlayer.hidePopup()
            self.__activePlayer = player
            if Internal.scene:  # mark the name of the active player in blue
                for _ in self.players:
                    _.colorizeName()

    def prepareHand(self) ->None:
        """prepares the next hand"""
        Game.prepareHand(self)
        if not self.finished():
            self.sortPlayers()
            self.hidePopups()
            self._setHandSeed()
            assert self.wall
            self.wall.build(shuffleFirst=True)

    def hidePopups(self) ->None:
        """hide all popup messages"""
        for player in self.players:
            player.hidePopup()

    def saveStartTime(self) ->None:
        """write a new entry in the game table with the selected players"""
        if not self.gameid:
            # in server.__prepareNewGame, gameid is None here
            return
        records = Query("select seed from game where id=?", (
            self.gameid,)).records
        assert records, f'self.gameid: {self.gameid}'
        seed = records[0][0]

        if not Internal.isServer and self.client:
            assert self.client.connection
            host = self.client.connection.url
        else:
            host = None

        if seed in ('proposed', host):
            # we reserved the game id by writing a record with seed == host
            Game.saveStartTime(self)

    def _saveScores(self) ->None:
        """save computed values to database, update score table
        and balance in status line"""
        if self.shouldSave:
            if self.belongsToRobotPlayer():
                assert False, 'shouldSave must not be True for robot player'
            Game._saveScores(self)

    def nextPlayer(self, current:Optional[PlayingPlayer]=None) ->PlayingPlayer:
        """return the player after current or after activePlayer"""
        if not current:
            current = self.activePlayer
        pIdx = self.players.index(current)
        return cast(PlayingPlayer, self.players[(pIdx + 1) % 4])

    def nextTurn(self) ->None:
        """move activePlayer"""
        self.activePlayer = self.nextPlayer()

    def _concealedTileName(self, tileName:Tile) ->Tile:
        """tileName has been discarded, by which name did we know it?"""
        player = self.activePlayer
        if player != self.myself and not self.playOpen:
            # we are human and server tells us another player discarded
            # a tile. In our game instance, tiles in handBoards of other
            # players are unknown
            player.makeTileKnown(tileName)
            result = Tile.none
        else:
            result = tileName
        if tileName not in player.concealedTiles:
            raise ValueError(f"I am {self.myself.name if self.myself else 'None'}. Player {player.name} "
                             f"is told to show discard of tile {result} "
                             f"but does not have it, he has {player.concealedTiles}")
        return result

    def hasDiscarded(self, player:PlayingPlayer, tile:Tile) ->None:
        """discards a tile from a player board"""
        assert isinstance(tile, Tile)
        if player != self.activePlayer:
            raise ValueError(f'Player {player} discards but {self.activePlayer} is active')
        self.discardedTiles[tile.exposed] += 1
        player.discarded.append(tile)
        player.lastTile = Tile.none
        self._concealedTileName(tile)
        # the above has side effect, needs to be called
        if Internal.scene:
            assert player.handBoard
            cast('PlayingHandBoard', player.handBoard).discard(tile)
        self.lastDiscard = tile
        player.removeConcealedTile(self.lastDiscard)
        if any(tile.exposed in x[0] for x in self.dangerousTiles):
            self.computeDangerous()
        else:
            self._endWallDangerous()
        self.handDiscardCount += 1

    def saveHand(self) ->None:
        """server told us to save this hand"""
        for player in self.players:
            handWonMatches = player.hand.won == (player == self.winner)
            assert handWonMatches, f'hand.won:{player.hand.won} winner:{player == self.winner}'
        Game.saveHand(self)

    def _mustExchangeSeats(self, pairs:List[List[Player]]) ->List[List[Player]]:
        """filter: which player pairs should really swap places?"""
        # if we are a client in a remote game, the server swaps and tells
        # us the new places
        return [] if self.belongsToPlayer() else pairs

    def _scanGameOption(self) ->None:
        """scan the --game option and go to start of wanted hand"""
        if self.wantedGame and '/' in self.wantedGame:
            first, last = (HandId(self, self.wantedGame, x) for x in (0, 1))
            if first > last:
                raise UserWarning(f'{first}..{last} is a negative range')
            HandId(self, self.wantedGame).goto()

    def assignVoices(self) ->None:
        """now we have all remote user voices"""
        assert self.belongsToHumanPlayer()
        available = Voice.availableVoices()[:]
        # available is without transferred human voices
        for player in self.players:
            if player.voice and player.voice.oggFiles():
                # remote human player sent her voice, or we are human
                # and have a voice
                if Debug.sound and player != self.myself:
                    logDebug(f'{player.name} got voice from opponent: {player.voice}')
            else:
                player.voice = Voice.locate(player.name)
                if player.voice:
                    if Debug.sound:
                        logDebug(f'{player.name} has own local voice {player.voice}')
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
                        f'{player.name} gets one of the still available voices {player.voice}')

    def dangerousFor(self, forPlayer:PlayingPlayer, tile:Tile) ->List[str]:
        """return a list of explaining texts if discarding tile
        would be Dangerous game for forPlayer. One text for each
        reason - there might be more than one"""
        assert isinstance(tile, Tile), tile
        tile = tile.exposed
        result:List[str] = []
        for dang, txt in self.dangerousTiles:
            if tile in dang:
                result.append(txt)
        for player in forPlayer.others():
            for dang, txt in player.dangerousTiles:
                if tile in dang:
                    result.append(txt)
        return result

    def computeDangerous(self, playerChanged:Optional[PlayingPlayer]=None) ->None:
        """recompute gamewide dangerous tiles. Either for playerChanged or
        for all players"""
        self.dangerousTiles = []
        if playerChanged:
            playerChanged.findDangerousTiles()
        else:
            for player in self.players:
                player.findDangerousTiles()
        self._endWallDangerous()

    def _endWallDangerous(self) ->None:
        """if end of living wall is reached, declare all invisible tiles
        as dangerous"""
        assert self.wall
        if len(self.wall.living) <= 5:
            allTiles = [x for x in elements.occurrence if not x.isBonus]
            for tile in allTiles:
                assert isinstance(tile, Tile), tile
            # see https://www.logilab.org/ticket/23986
            invisibleTiles = {x for x in allTiles if x not in self.visibleTiles}
            msg = i18n('Short living wall: Tile is invisible, hence dangerous')
            self.dangerousTiles = [x for x in self.dangerousTiles if x[1] != msg]
            self.dangerousTiles.append((invisibleTiles, msg))
