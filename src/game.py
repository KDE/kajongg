# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

import datetime
import weakref
import sys
from collections import namedtuple

from typing import List, Optional, Tuple, TYPE_CHECKING, Union, Dict, Iterable, Generator, Any, Set, cast

from twisted.internet.defer import succeed
from util import gitHead
from kajcsv import CsvRow
from rand import CountingRandom
from log import logError, logException, logDebug, i18n
from common import Internal, IntDict, Debug, Options
from common import Speeds
from wind import Wind, East, South, West, North
from query import Query
from rule import Ruleset, UsedRule
from tile import Tile, elements
from tilesource import TileSource
from sound import Voice
from wall import Wall
from player import Players, Player, PlayingPlayer
from animation import animateAndDo, AnimationSpeed, ParallelAnimationGroup
from point import Point, PointRange

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
        self._client = None  # FIXME: add comment
        self.client = client  # FIXME: add comment
        self.roundWind:Wind = East  # after 4 rounds, roundWind is NoWind
        self.rotated:int = 0
        self.notRotated:int = 0  # counts hands since last rotation
        self.moves:List['Move'] = []  # only the current hand
        self.randomGenerator:CountingRandom = CountingRandom(self)
        if wantedGame is None:
            wantedGame = str(int(self.randomGenerator.random() * 10 ** 9))
        self.first_point: Point
        self.last_point: Optional[Point]
        self.first_point, self.last_point = PointRange.from_string(wantedGame)
        self.ruleset:Ruleset = ruleset
        self._currentPoint:Optional[Point] = None
        self._prevPoint:Optional[Point] = None
        self.gameid:Optional[int] = gameid
        self.playOpen:bool = False
        self.autoPlay:bool = False
        self.handctr:int = 0
        self.divideAt:Optional[int] = None
        self.__lastDiscard:Optional[Tile] = None  # always uppercase
        # TODO: use Tile.none and remove assertions in message.py and otherwhere
        self.visibleTiles:Dict[Tile, int] = IntDict()
        self.discardedTiles:Dict[Tile, int] = IntDict(self.visibleTiles)
        # tile names are always lowercase
        self.dangerousTiles:List[Tuple[Set[Tile], str]] = []
        self.csvTags:List[str] = []
        self._setHandSeed()
        self.activePlayer:Optional[Player] = None
        self.__winner:Optional[Player] = None
        self._setGameId()
        self.__loadRuleset()
        # shift rules taken from the OEMC 2005 rules
        # 2nd round: S and W shift, E and N shift
        self.wall:Optional[Wall] = self.wallClass(self)  # type:ignore[arg-type]
        # FIXME:  wall nach PlayingGame verschieben?
        self.assignPlayers(names)  # also defines self.myself
        if self.belongsToGameServer():
            self.__shufflePlayers()
        self.goto(self.first_point)
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
    def point(self) ->Point:
        """current position in game"""
        result = Point(self)
        if result != self._currentPoint:
            self._prevPoint = self._currentPoint
            self._currentPoint = result
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
    def roundsFinished(self) ->int:
        """rounds finished as given by round wind"""
        return self.roundWind.__index__()

    @roundsFinished.setter
    def roundsFinished(self, value:int) ->None:
        """next round"""
        self.roundWind = Wind.all[value]

    def addCsvTag(self, tag:str, forAllPlayers:bool=False) ->None:
        """tag will be written to tag field in csv row"""
        if forAllPlayers or self.belongsToHumanPlayer():
            self.csvTags.append(f'{tag}/{self.point.prompt(self, withSeed=False)}')

    def isFirstHand(self) ->bool:
        """as the name says"""
        return Point(self).is_in_first_hand()

    def _setGameId(self) ->None:
        """virtual"""
        assert not self  # we want it to fail, and quieten pylint

    def close(self) ->None:
        """log off from the server"""
        self.wall = None
        self.lastDiscard = None
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
        _ = {East: (), South: (South, West, East, North), West: (South, East), North: (West, East)}
        winds = _[self.roundWind]

        players = [self.players[x] for x in winds]
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

    def goto(self, point:Point) ->None:
        """go to the point"""
        if point.moveCount > 0:
            raise NotImplementedError('Game.goto() only accepts moveCount 0')
        while self.point < point:
            self.rotateWinds()
            self.notRotated = point.notRotated

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
    def seed(self) ->int:
        """extract it from wantedGame. Set wantedGame if empty."""
        return self.first_point.seed

    def _setHandSeed(self) ->None:
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
                 self.roundWind, player.wind,
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
                    self.debug(','.join(x.name for x in result), showPrevPoint=True)
            self.rotateWinds()
            if self.finished():
                self.finish_in_db()
        return bool(result)

    def rotateWinds(self) ->None:
        """rotate winds, exchange seats. If finished, update database"""
        self.rotated += 1
        self.notRotated = 0
        if self.rotated == 4:
            self.roundWind = next(self.roundWind)
            self.rotated = 0
        if not self.finished() and not self.belongsToPlayer():
            # the game server already told us the new placement and winds
            winds = [player.wind for player in self.players]
            winds = winds[3:] + winds[0:3]
            for idx, newWind in enumerate(winds):
                self.players[idx].wind = newWind
            if self.rotated == 0:
                # exchange seats between rounds
                self.__exchangeSeats()
            if Internal.scene:
                with AnimationSpeed(Speeds.windDisc):
                    cast('UIWall', self.wall).showWindDiscs()

    def finish_in_db(self) ->None:
        """write endtime into db"""
        endtime = datetime.datetime.now().replace(
            microsecond=0).isoformat()
        assert self.gameid
        with Internal.db as transaction:
            transaction.execute(
                f'UPDATE game set endtime = "{endtime}" where id = {int(self.gameid)}')

    def debug(self, msg:str, btIndent:Optional[int]=None,
        showPrevPoint:bool=False, showStack:bool=False) ->None:  # pylint: disable=unused-argument
        """
        Log a debug message.

        @param msg: The message.
        @type msg: A string.
        @param btIndent: If given, message is indented by
        depth(backtrace)-btIndent
        @type btIndent: C{int}
        @param showPrevPoint: If True, do not use current point but previous
        @type showPrevPoint: C{bool}
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
        # FIXME temp disabled point = self._prevPoint if showPrevPoint else self.point
        point = self.point
        assert point
        point_str = point.prompt(self, withMoveCount=True)
        logDebug(
            f'{prefix}{point_str}: {msg}',
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
    def _loadGameRecord(cls, gameid:int) ->Optional[Any]:
        """load and sanitize"""
        record = Query(
            "select {fields} from game where id = ?",
            (gameid,), fields='p0,p1,p2,p3,ruleset,id,seed').tuple()
        if record:
            return record._replace(ruleset=int(record.ruleset) or 1)
        return None

    @classmethod
    def _loadLastHand(cls, gameid:int) ->Any:
        """load or invent"""
        records = Query(
            "select {fields} from score "
            "where game=? "
                "and hand=(select max(hand) from score where game=?) ",
            (gameid, gameid), fields='hand,rotated').tuples()
        if records:
            return records[0]
        _ = namedtuple('_', 'hand,rotated')
        return _(0, 0)

    @classmethod
    def _loadScores(cls, qGame: Any, hand:int) ->Any:
        """If the server saved a score entry but our client
           did not, we get no record here. Should we try to fix this or
           exclude such a game from the list of resumable games?"""
        scoreFields = 'player, wind, balance, won, prevailing'
        qScores = Query(
            "select {fields} from score "
            "where game=? and hand=?",
            (qGame.id, hand), fields=scoreFields).tuples()  # type: ignore
        if not qScores:
            # this should normally not happen
            my_class = namedtuple('_', scoreFields)  # type: ignore
            qScores = list(
                my_class(qGame[wind], wind.char, 0, False, East.char)  # type:ignore
                for wind in Wind.all4)  # type: ignore[call-arg]
        if len(qScores) != 4:
            logError(
                f'game {int(qGame.id)}: last hand should have 4 score records, found {len(qScores)}')
        if len({x.prevailing for x in qScores}) != 1:
            logError(f'game {qGame.id} inconsistent: '
                     f'All score records for the same hand must have the same prevailing wind')
        return qScores

    @classmethod
    def loadFromDB(cls, gameid:int, client:Optional['Client']=None) ->Optional[Union['Game', 'ServerGame']]:
        """load game by game id and return a new Game instance"""
        # TODO would be nice to use cls in result annotation, but how?
        Internal.logPrefix = 'S' if Internal.isServer else 'C'
        qGame = cls._loadGameRecord(gameid)
        if qGame is None:
            return None
        ruleset = Ruleset.cached(qGame.ruleset)
        Players.load()  # we want to make sure we have the current definitions
        qLastHandRecord = cls._loadLastHand(gameid)
        qScores = cls._loadScores(qGame, qLastHandRecord.hand)  # FIXME: war 1, aber 1 ist doch rotated

        players = list((x.wind, Game.__getName(x.player)) for x in qScores)

        # create the game instance. It gets the starting point from DB itself
        game = cls(players, ruleset, gameid=gameid, client=client, wantedGame=qGame.seed)
        game.handctr = qLastHandRecord.hand
        game.rotated = qLastHandRecord.rotated

        # FIXME wie geht game zum richtigen Startpunkt? Hier ist kein goto,
        # Game.__init__ verwendet dazu nur wantedGame, also ganz von vorne

        for qScore in qScores:
            player = game.players.byId(qScore.player)
            if not player:
                logError(
                    f'game {int(gameid)} inconsistent: player {qScore.player} missing in game table')
            else:
                player.getsPayment(qScore.balance)
            if qScore.won:
                game.winner = player
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
        check if we reached the second point defined by --game.
        If we did, the game is over too"""
        if self.point >= self.last_point:
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
            payAction = self.ruleset.findUniqueOption('payforall') if guilty else None
            if payAction:
                assert isinstance(guilty, Player)  # mypy should be able to infer this
                if Debug.dangerousGame:
                    self.debug(f'{self.point}: winner {winner}. {guilty} pays for all')
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
                self.csvTags.append(f'MEM:{resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}')  # pylint:disable=possibly-used-before-assignment
            if Options.rounds:
                self.csvTags.append(f'ROUNDS:{Options.rounds}')
            _ = CsvRow.Fields
            row = [''] * CsvRow.Fields.PLAYERS
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
