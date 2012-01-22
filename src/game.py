# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2011 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
from random import Random
from collections import defaultdict

from util import logError, logException, logDebug, m18n, isAlive
from common import WINDS, InternalParameters, elements, IntDict, Debug
from query import Transaction, Query
from scoringengine import Ruleset
from tile import Tile
from scoringengine import HandContent
from sound import Voice
from wall import Wall
from move import Move
from animation import Animated
from player import Player, Players

class Game(object):
    """the game without GUI"""
    # pylint: disable=R0902
    # pylint we need more than 10 instance attributes

    def __init__(self, names, ruleset, gameid=None, seed=None, shouldSave=True, client=None):
        """a new game instance. May be shown on a field, comes from database if gameid is set

        Game.lastDiscard is the tile last discarded by any player. It is reset to None when a
        player gets a tile from the living end of the wall.
        """
        # pylint: disable=R0915
        # pylint we need more than 50 statements
        field = InternalParameters.field
        if field:
            field.game = self
        self.randomGenerator = Random()
        self.client = client
        self.seed = None
        if not self.isScoringGame():
            _ = int(InternalParameters.game.split('/')[0]) if InternalParameters.game else 0
            self.seed = seed or _ or int(self.randomGenerator.random() * 10**9)
        self.shouldSave = shouldSave
        self.randomGenerator.seed(self.seed)
        self.rotated = 0
        self.notRotated = 0 # counts hands since last rotation
        self.players = [] # if we fail later on in init, at least we can still close the program
        self.activePlayer = None
        self.ruleset = None
        self.winner = None
        self.moves = []
        self.roundsFinished = 0
        self.myself = None
        self.gameid = gameid
        self.setGameId()
        self.playOpen = False
        self.autoPlay = False
        self.handctr = 0
        self.roundHandCount = 0
        self.handDiscardCount = 0
        self.divideAt = None
        self.lastDiscard = None # always uppercase
        self.visibleTiles = IntDict()
        self.discardedTiles = IntDict(self.visibleTiles) # tile names are always lowercase
        self.eastMJCount = 0
        self.dangerousTiles = list()
        self.__useRuleset(ruleset)
        # shift rules taken from the OEMC 2005 rules
        # 2nd round: S and W shift, E and N shift
        self.shiftRules = 'SWEN,SE,WE'
        if field:
            field.showWall()
        else:
            self.wall = Wall(self)
        for name in names:
            Players.createIfUnknown(name)
        if field:
            self.players = field.genPlayers()
        else:
            self.players = Players([Player(self) for idx in range(4)])
        for idx, player in enumerate(self.players):
            player.name = names[idx]
            player.wind = WINDS[idx]
        if self.client and self.client.username:
            self.myself = self.players.byName(self.client.username)
        if self.shouldSave:
            self.saveNewGame()
        if field:
            self.initVisiblePlayers()
            field.refresh()
            self.wall.decorate()

    def isFirstHand(self):
        """as the name says"""
        return self.roundHandCount == 0 and self.roundsFinished == 0

    def handId(self):
        """identifies the hand for window title and scoring table"""
        character = chr(ord('a') - 1 + self.notRotated) if self.notRotated else ''
        return '%s/%s%s%s' % (self.seed, WINDS[self.roundsFinished % 4], self.rotated + 1, character)

    def setGameId(self):
        """virtual"""
        assert not self # we want it to fail, and quiten pylint

    def close(self, dummyCallback=None):
        """log off from the server"""
        self.hide()

    def hide(self, dummyResult=None):
        """if the game is shown in the client, hide it"""
        field = InternalParameters.field
        if field and isAlive(field):
            for player in self.players:
                if player.handBoard:
                    player.clearHand()
                    player.handBoard.hide()
            field.setWindowTitle('Kajongg')
            field.selectorBoard.tiles = []
            field.selectorBoard.allSelectorTiles = []
            self.removeWall()
            field.centralScene.removeTiles()
            field.game = None
            field.refresh()

    def removeWall(self):
        """remote the wall"""
        if self.wall:
            self.wall.hide()
            self.wall = None

    def initVisiblePlayers(self):
        """make players visible"""
        for idx, player in enumerate(self.players):
            player.front = self.wall[idx]
            player.clearHand()
            player.handBoard.setVisible(True)
            scoring = self.isScoringGame()
            player.handBoard.setEnabled(scoring or \
                (self.belongsToHumanPlayer() and player == self.myself))
            player.handBoard.showMoveHelper(scoring)
        InternalParameters.field.adjustView()

    def setConcealedTiles(self, allPlayerTiles):
        """when starting the hand. tiles is one string"""
        with Animated(False):
            for playerName, tileNames in allPlayerTiles:
                player = self.playerByName(playerName)
                player.addConcealedTiles(self.wall.deal(tileNames))

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
        return list([x for x in self.players if x is not self.winner])

    @staticmethod
    def windOrder(player):
        """cmp function for __exchangeSeats"""
        return 'ESWN'.index(player.wind)

    @apply
    def host():
        """the name of the game server this game is attached to"""
        def fget(self):
            if not InternalParameters.isServer and self.client:
                return self.client.host
        return property(**locals())

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

    def shufflePlayers(self):
        """assign random seats to the players and assign winds"""
        self.randomGenerator.shuffle(self.players)
        for player, wind in zip(self.players, WINDS):
            player.wind = wind

    def __exchangeSeats(self):
        """execute seat exchanges according to the rules"""
        windPairs = self.shiftRules.split(',')[(self.roundsFinished-1) % 4]
        while len(windPairs):
            windPair = windPairs[0:2]
            windPairs = windPairs[2:]
            swappers = list(self.players[windPair[x]] for x in (0, 1))
            if self.belongsToPlayer():
                # we are a client in a remote game, the server swaps and tells us the new places
                shouldSwap = False
            elif self.isScoringGame():
                # we play a manual game and do only the scoring
                shouldSwap = InternalParameters.field.askSwap(swappers)
            else:
                # we are the game server. Always swap in remote games.
                # do not do assert self.belongsToGameServer() here because
                # self.client might not yet be set - this code is called for all
                # suspended games but self.client is assigned later
                shouldSwap = True
            if shouldSwap:
                swappers[0].wind, swappers[1].wind = swappers[1].wind, swappers[0].wind
        self.sortPlayers()

    def sortPlayers(self):
        """sort by wind order. If we are in a remote game, place ourself at bottom (idx=0)"""
        players = self.players
        if InternalParameters.field:
            fieldAttributes = list([(p.handBoard, p.front) for p in players])
        players.sort(key=Game.windOrder)
        for idx, player in enumerate(players):
            player.idx = idx
        if self.belongsToHumanPlayer():
            myName = self.myself.name
            while players[0].name != myName:
                values0 = players[0].values
                for idx in range(4, 0, -1):
                    this, prev = players[idx % 4], players[idx - 1]
                    this.values = prev.values
                players[1].values = values0
            self.myself = players[0]
        if InternalParameters.field:
            for idx, player in enumerate(players):
                player.handBoard, player.front = fieldAttributes[idx]
                player.handBoard.player = player

    @staticmethod
    def _newGameId():
        """write a new entry in the game table
        and returns the game id of that new entry"""
        with Transaction():
            query = Query("insert into game(seed) values(0)")
            gameid, gameidOK = query.query.lastInsertId().toInt()
        assert gameidOK
        return gameid

    def saveNewGame(self):
        """write a new entry in the game table with the selected players"""
        if self.gameid is None:
            return
        if not self.isScoringGame():
            records = Query("select seed from game where id=?", list([self.gameid])).records
            assert records
            if not records:
                return
            seed = records[0][0]
        if self.isScoringGame() or seed == 'proposed' or seed == self.host:
            # we reserved the game id by writing a record with seed == hostname
            starttime = datetime.datetime.now().replace(microsecond=0).isoformat()
            args = list([starttime, self.seed, int(self.autoPlay), self.ruleset.rulesetId])
            args.extend([p.nameid for p in self.players])
            args.append(self.gameid)
            with Transaction():
                Query("update game set starttime=?,seed=?,autoplay=?," \
                        "ruleset=?,p0=?,p1=?,p2=?,p3=? where id=?", args)
                Query(["update usedruleset set lastused='%s' where id=%d" %\
                        (starttime, self.ruleset.rulesetId),
                    "update ruleset set lastused='%s' where hash='%s'" %\
                        (starttime, self.ruleset.hash)])
                if not InternalParameters.isServer:
                    Query('update server set lastruleset=? where url=?',
                          list([self.ruleset.rulesetId, self.host]))

    def __useRuleset(self, ruleset):
        """use a copy of ruleset for this game, reusing an existing copy"""
        self.ruleset = ruleset
        self.ruleset.load()
        query = Query('select id from usedruleset where hash="%s"' % \
            self.ruleset.hash)
        if query.records:
            # reuse that usedruleset
            self.ruleset.rulesetId = query.records[0][0]
        else:
            # generate a new usedruleset
            self.ruleset.rulesetId = self.ruleset.newId(used=True)
            self.ruleset.save()

    def prepareHand(self):
        """prepares the next hand"""
        del self.moves[:]
        seedFactor = (self.roundsFinished + 1) * 10000 + self.rotated * 1000 + self.notRotated * 100
        # set seed to a reproducable value, independent of what happend in previous hands/rounds.
        # This makes it easier to reproduce game situations
        # in later hands without having to exactly replay all previous hands
        self.randomGenerator.seed(self.seed * seedFactor)
        if self.finished():
            if InternalParameters.field and isAlive(InternalParameters.field):
                InternalParameters.field.refresh()
            self.close()
        else:
            for player in self.players:
                player.clearHand()
            self.winner = None
            if not self.isScoringGame():
                self.sortPlayers()
            self.hidePopups()
            self.activePlayer = self.players['E']
            self.wall.build()
            HandContent.clearCache()
            self.dangerousTiles = list()
            self.discardedTiles.clear()
            assert self.visibleTiles.count() == 0
        if InternalParameters.field:
            InternalParameters.field.prepareHand()

    def hidePopups(self):
        """hide all popup messages"""
        for player in self.players:
            player.hidePopup()

    def saveHand(self):
        """save hand to database, update score table and balance in status line"""
        self.__payHand()
        self.__saveScores()
        self.handctr += 1
        self.notRotated += 1
        self.roundHandCount += 1
        self.handDiscardCount = 0
        if self.winner and self.winner.wind == 'E':
            self.eastMJCount += 1

    def needSave(self):
        """do we need to save this game?"""
        if self.isScoringGame():
            return True
        elif self.belongsToRobotPlayer():
            return False
        else:
            return self.shouldSave # as the server told us

    def __saveScores(self):
        """save computed values to database, update score table and balance in status line"""
        if not self.needSave():
            return
        scoretime = datetime.datetime.now().replace(microsecond=0).isoformat()
        with Transaction():
            for player in self.players:
                if player.handContent:
                    manualrules = '||'.join(x.name for x, meld in player.handContent.usedRules)
                else:
                    manualrules = m18n('Score computed manually')
                Query("INSERT INTO SCORE "
                    "(game,hand,data,manualrules,player,scoretime,won,prevailing,wind,"
                    "points,payments, balance,rotated,notrotated) "
                    "VALUES(%d,%d,?,?,%d,'%s',%d,'%s','%s',%d,%d,%d,%d,%d)" % \
                    (self.gameid, self.handctr, player.nameid,
                        scoretime, int(player == self.winner),
                        WINDS[self.roundsFinished % 4], player.wind, player.handTotal,
                        player.payment, player.balance, self.rotated, self.notRotated),
                    list([player.handContent.string, manualrules]))

    def savePenalty(self, player, offense, amount):
        """save computed values to database, update score table and balance in status line"""
        if not self.needSave():
            return
        scoretime = datetime.datetime.now().replace(microsecond=0).isoformat()
        with Transaction():
            Query("INSERT INTO SCORE "
                "(game,penalty,hand,data,manualrules,player,scoretime,"
                "won,prevailing,wind,points,payments, balance,rotated,notrotated) "
                "VALUES(%d,1,%d,?,?,%d,'%s',%d,'%s','%s',%d,%d,%d,%d,%d)" % \
                (self.gameid, self.handctr, player.nameid,
                    scoretime, int(player == self.winner),
                    WINDS[self.roundsFinished % 4], player.wind, 0,
                    amount, player.balance, self.rotated, self.notRotated),
                list([player.handContent.string, offense.name]))
        if InternalParameters.field:
            InternalParameters.field.refresh()

    def maybeRotateWinds(self):
        """if needed, rotate winds, exchange seats. If finished, update database"""
        if self.belongsToPlayer():
            # the server does that and tells us to rotate
            return False
        if not self.winner:
            return False
        result = self.winner.wind != 'E' or self.eastMJCount == 9
        if result:
            self.rotateWinds()
        return result

    def rotateWinds(self):
        """rotate winds, exchange seats. If finished, update database"""
        self.rotated += 1
        self.notRotated = 0
        self.eastMJCount = 0
        if self.rotated == 4:
            if not self.finished():
                self.roundsFinished += 1
            self.rotated = 0
            self.roundHandCount = 0
        if self.finished():
            endtime = datetime.datetime.now().replace(microsecond=0).isoformat()
            with Transaction():
                Query('UPDATE game set endtime = "%s" where id = %d' % \
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

    @staticmethod
    def __getNames(record):
        """get name ids from record
        and return the names"""
        names = []
        for idx in range(4):
            nameid = record[idx]
            try:
                name = Players.allNames[nameid]
            except KeyError:
                name = m18n('Player %1 not known', nameid)
            names.append(name)
        return names

    @staticmethod
    def loadFromDB(gameid, client=None, what=None, cacheRuleset=False):
        """load game by game id and return a new Game instance"""
        qGame = Query("select p0,p1,p2,p3,ruleset,seed from game where id = %d" % gameid)
        if not qGame.records:
            return None
        rulesetId = qGame.records[0][4] or 1
        if cacheRuleset:
            ruleset = Ruleset.cached(rulesetId, used=True)
        else:
            ruleset = Ruleset(rulesetId, used=True)
        Players.load() # we want to make sure we have the current definitions
        what = what or Game
        game = what(Game.__getNames(qGame.records[0]), ruleset, gameid=gameid,
                client=client, seed=qGame.records[0][5])
        qLastHand = Query("select hand,rotated from score where game=%d and hand="
            "(select max(hand) from score where game=%d)" % (gameid, gameid))
        if qLastHand.records:
            (game.handctr, game.rotated) = qLastHand.records[0]

        qScores = Query("select player, wind, balance, won, prevailing from score "
            "where game=%d and hand=%d" % (gameid, game.handctr))
        # default value. If the server saved a score entry but our client did not,
        # we get no record here. Should we try to fix this or exclude such a game from
        # the list of resumable games?
        prevailing = 'E'
        for record in qScores.records:
            playerid = record[0]
            wind = str(record[1])
            player = game.players.byId(playerid)
            if not player:
                logError(
                'game %d inconsistent: player %d missing in game table' % \
                    (gameid, playerid))
            else:
                player.getsPayment(record[2])
                player.wind = wind
            if record[3]:
                game.winner = player
            prevailing = record[4]
        game.roundsFinished = WINDS.index(prevailing)
        if game.handctr:
            game.eastMJCount = int(Query("select count(1) from score "
                "where game=%d and won=1 and wind='E' and player=%d "
                "and prevailing='%s'" % \
                (gameid, game.players['E'].nameid, prevailing)).records[0][0])
        else:
            game.eastMJCount = 0
        game.handctr += 1
        game.maybeRotateWinds()
        game.sortPlayers()
        game.wall.decorate()
        return game

    def finished(self):
        """The game is over after minRounds completed rounds"""
        return self.roundsFinished >= self.ruleset.minRounds

    def __payHand(self):
        """pay the scores"""
        winner = self.winner
        if winner:
            winner.wonCount += 1
            guilty = winner.usedDangerousFrom
            if guilty:
                if Debug.dangerousGame:
                    logDebug('%s: winner %s. %s pays for all' % \
                                (self.handId(), winner, guilty))
                score = winner.handTotal
                score = score * 6 if winner.wind == 'E' else score * 4
                guilty.getsPayment(-score)
                winner.getsPayment(score)
                return

        for player1 in self.players:
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

    def lastMoves(self, only=None, without=None):
        """filters and yields the moves in reversed order"""
        for idx in range(len(self.moves)-1, -1, -1):
            move = self.moves[idx]
            if only:
                if move.message in only:
                    yield move
            elif without:
                if move.message not in without:
                    yield move

    def throwDices(self):
        """sets random living and kongBox
        sets divideAt: an index for the wall break"""
        if self.belongsToGameServer():
            self.randomGenerator.shuffle(self.wall.tiles)
        breakWall = self.randomGenerator.randrange(4)
        sideLength = len(self.wall.tiles) // 4
        # use the sum of four dices to find the divide
        self.divideAt = breakWall * sideLength + \
            sum(self.randomGenerator.randrange(1, 7) for idx in range(4))
        if self.divideAt % 2 == 1:
            self.divideAt -= 1
        self.divideAt %= len(self.wall.tiles)

    def dangerousFor(self, forPlayer, tile):
        """returns a list of explaining texts if discarding tile
        would be Dangerous game for forPlayer. One text for each
        reason - there might be more than one"""
        if isinstance(tile, Tile):
            tile = tile.element
        tile = tile.lower()
        result = []
        for dang, txt in self.dangerousTiles:
            if tile in dang:
                result.append(txt)
        for player in self.players:
            if player != forPlayer:
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
        if len(self.wall.living) <=5:
            allTiles = [x for x in defaultdict.keys(elements.occurrence) if x[0] not in 'fy']
            # see http://www.logilab.org/ticket/23986
            invisibleTiles = set(x for x in allTiles if x not in self.visibleTiles)
            msg = m18n('Short living wall: Tile is invisible, hence dangerous')
            self.dangerousTiles = list(x for x in self.dangerousTiles if x[1] != msg)
            self.dangerousTiles.append((invisibleTiles, msg))
            if InternalParameters.field:
                for player in self.players:
                    player.setTileToolTip()

    def appendMove(self, player, command, kwargs):
        """append a Move object to self.moves"""
        self.moves.append(Move(player, command, kwargs))

class ScoringGame(Game):
    """we play manually on a real table with real tiles and use
    kajongg only for scoring"""

    def __init__(self, names, ruleset, gameid=None, client=None, seed=None):
        Game.__init__(self, names, ruleset, gameid=gameid, client=client, seed=seed)
        field = InternalParameters.field
        field.selectorBoard.load(self)
        self.prepareHand()

    def prepareHand(self):
        """prepare a scoring game hand"""
        if not self.finished():
            selector = InternalParameters.field.selectorBoard
            selector.refill()
            selector.hasFocus = True
        Game.prepareHand(self)

    @staticmethod
    def isScoringGame():
        """are we scoring a manual game?"""
        return True

    def setGameId(self):
        """get a new id"""
        if not self.gameid:
            # a loaded game has gameid already set
            self.gameid = self._newGameId()

class PlayingGame(Game):
    """we play against the computer or against players over the net"""

    def setGameId(self):
        """do nothing, we already went through the game id reservation"""
        pass

class RemoteGame(PlayingGame):
    """this game is played using the computer"""
    # pylint: disable=R0913
    # pylint: disable=R0904
    # pylint too many arguments, too many public methods
    def __init__(self, names, ruleset, gameid=None, seed=None, shouldSave=True, \
            client=None, playOpen=False, autoPlay=False):
        """a new game instance, comes from database if gameid is set"""
        self.__activePlayer = None
        self.prevActivePlayer = None
        self.defaultNameBrush = None
        PlayingGame.__init__(self, names, ruleset, gameid,
            seed=seed, shouldSave=shouldSave, client=client)
        self.playOpen = playOpen
        self.autoPlay = autoPlay
        for player in self.players:
            if player.name.startswith('ROBOT'):
                player.voice = Voice(player.name)

    @staticmethod
    def loadFromDB(gameid, client=None, what=None, cacheRuleset=False):
        """like Game.loadFromDB, but returns a RemoteGame"""
        return Game.loadFromDB(gameid, client, RemoteGame, cacheRuleset)

    @apply
    def activePlayer(): # pylint: disable=E0202
        """the turn is on this player"""
        def fget(self):
            # pylint: disable=W0212
            return self.__activePlayer
        def fset(self, player):
            # pylint: disable=W0212
            if self.__activePlayer != player:
                self.prevActivePlayer = self.__activePlayer
                self.__activePlayer = player
                if InternalParameters.field: # mark the name of the active player in blue
                    for player in self.players:
                        player.setTileToolTip()
                        player.colorizeName()
        return property(**locals())

    def nextPlayer(self, current=None):
        """returns the player after current or after activePlayer"""
        if not current:
            current = self.activePlayer
        pIdx = self.players.index(current)
        return self.players[(pIdx + 1) % 4]

    def nextTurn(self):
        """move activePlayer"""
        self.activePlayer = self.nextPlayer()

    def initialDeal(self):
        """Happens only on server: every player gets 13 tiles (including east)"""
        self.throwDices()
        self.wall.divide()
        for player in self.players:
            player.clearHand()
            # 13 tiles at least, with names as given by wall
            player.addConcealedTiles(self.wall.deal([None] * 13))
            # compensate boni
            while len(player.concealedTileNames) != 13:
                player.addConcealedTiles(self.wall.deal())

    def pickedTile(self, player, deadEnd, tileName=None):
        """got a tile from wall"""
        self.activePlayer = player
        tile = self.wall.deal([tileName], deadEnd=deadEnd)[0]
        player.addConcealedTiles(tile)
        player.lastTile = tile.element
        if deadEnd:
            player.lastSource = 'e'
        else:
            self.lastDiscard = None
            player.lastSource = 'w'
        return tile

    def showField(self):
        """show remote game in field"""
        self.wall.divide()
        if InternalParameters.field:
            InternalParameters.field.setWindowTitle(m18n('Kajongg <numid>%1</numid>',
               self.handId()))
            InternalParameters.field.discardBoard.setRandomPlaces(self.randomGenerator)
            for tableList in InternalParameters.field.tableLists:
                tableList.hide()
            InternalParameters.field.tableLists = []

    def __concealedTileName(self, tileName):
        """tileName has been discarded, by which name did we know it?"""
        player = self.activePlayer
        if self.myself and player != self.myself and not self.playOpen:
            # we are human and server tells us another player discarded a tile. In our
            # game instance, tiles in handBoards of other players are unknown
            player.concealedTileNames[0] = tileName
            result = 'Xy'
        else:
            result = tileName
        if not tileName in player.concealedTileNames:
            raise Exception('I am %s. Player %s is told to show discard of tile %s but does not have it, he has %s' % \
                           (self.myself.name if self.myself else 'None',
                            player.name, result, player.concealedTileNames))
        return result

    def hasDiscarded(self, player, tileName):
        """discards a tile from a player board"""
        # pylint: disable=R0912
        # too many branches
        if player != self.activePlayer:
            raise Exception('Player %s discards but %s is active' % (player, self.activePlayer))
        self.discardedTiles[tileName.lower()] += 1
        player.discarded.append(tileName)
        concealedTileName = self.__concealedTileName(tileName) # has side effect, needs to be called
        if InternalParameters.field:
            if player.handBoard.focusTile and player.handBoard.focusTile.element == tileName:
                self.lastDiscard = player.handBoard.focusTile
            else:
                matchingTiles = sorted(player.handBoard.tilesByElement(concealedTileName),
                    key=lambda x:x.xoffset)
                # if an opponent player discards, we want to discard from the right end of the hand
                # thus minimizing tile movement
                self.lastDiscard = matchingTiles[-1]
                self.lastDiscard.element = tileName
            InternalParameters.field.discardBoard.discardTile(self.lastDiscard)
        else:
            self.lastDiscard = Tile(tileName)
        player.remove(tile=self.lastDiscard)
        if any(tileName.lower() in x[0] for x in self.dangerousTiles):
            self.computeDangerous()
        else:
            self._endWallDangerous()
        self.handDiscardCount += 1
        if InternalParameters.field:
            for tile in player.handBoard.tiles:
                tile.focusable = False
        if InternalParameters.game:
            parts = InternalParameters.game.split('/')
            if len(parts) > 1:
                handId = '/'.join(parts[:2])
                discardCount = int(parts[2]) if len(parts) > 2 else 0
                if self.handId() == handId \
                   and self.handDiscardCount >= int(discardCount):
                    self.autoPlay = False
                    InternalParameters.game = None # --game has been processed
                    if InternalParameters.field: # mark the name of the active player in blue
                        InternalParameters.field.actionAutoPlay.setChecked(False)

    def saveHand(self):
        """server told us to save this hand"""
        for player in self.players:
            player.handContent = player.computeHandContent()
            if player == self.winner:
                assert player.handContent.maybeMahjongg()
        Game.saveHand(self)

    def close(self, callback=None):
        """log off from the server"""
        InternalParameters.autoPlay = False # do that only for the first game
        if self.client:
            deferred = self.client.logout() if self.client.perspective else None
            self.client = None
            if deferred:
                deferred.addBoth(self.hide)
                if callback:
                    deferred.addBoth(callback)
                return
        self.hide()
        if callback:
            callback()
