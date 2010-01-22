#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008,2009 Wolfgang Rohdewald <wolfgang@rohdewald.de>

kmj is free software you can redistribute it and/or modify
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

import sys, datetime, syslog, string, random

from PyQt4.QtCore import Qt
from PyQt4.QtGui import QBrush, QColor

from util import logMessage,  logException, m18n, WINDS
from config import InternalParameters
from query import Query
from scoringengine import Ruleset
from tileset import Elements
from tile import Tile
from scoringengine import Pairs, Meld, HandContent

class WallEmpty(Exception):
    pass

class Players(list):
    """a list of players where the player can also be indexed by wind"""

    allNames = {}
    allIds = {}

    def __init__(self, players=None):
        list.__init__(self)
        if players:
            self.extend(players)

    def __getitem__(self, index):
        """allow access by idx or by wind"""
        if isinstance(index, (bytes, str)) and len(index) == 1:
            # bytes for Python 2.6, str for 3.0
            for player in self:
                if player.wind == index:
                    return player
            logException(Exception("no player has wind %s" % index))
        return list.__getitem__(self, index)

    def __str__(self):
        return ', '.join(list('%s: %s' % (x.name, x.wind) for x in self))

    def byId(self, playerid):
        """lookup the player by id"""
        for player in self:
            if player.nameid == playerid:
                return player
        logException(Exception("no player has id %d" % playerid))

    def byName(self, playerName):
        """lookup the player by name"""
        for player in self:
            if player.name == playerName:
                return player
        logException(Exception("no player has name %s" % playerName))

    @staticmethod
    def load():
        """load all defined players into self.allIds and self.allNames"""
        query = Query("select id,host,name from player")
        if not query.success:
            sys.exit(1)
        Players.allIds = {}
        Players.allNames = {}
        for record in query.data:
            (nameid, host,  name) = record
            Players.allIds[(host, name)] = nameid
            Players.allNames[nameid] = (host, name)

    @staticmethod
    def createIfUnknown(host, name):
        if (host, name) not in Players.allNames.values():
            Players.load()  # maybe somebody else already added it
            if (host, name) not in Players.allNames.values():
                Query("insert into player(host,name) values(?,?)",
                      list([host, name]))
                Players.load()
        assert (host, name) in Players.allNames.values()

class Player(object):
    """all player related data without GUI stuff.
    concealedTiles: used during the hand for all concealed tiles, ungrouped.
    concealedMelds: is empty during the hand, will be valid after end of hand,
    containing the concealed melds as the player presents them."""
    def __init__(self, game, handContent=None):
        self.game = game
        self.handContent = handContent
        self.__balance = 0
        self.__payment = 0
        self.name = ''
        self.wind = WINDS[0]
        self.concealedTiles = []
        self.exposedMelds = []
        self.concealedMelds = []
        self.bonusTiles = []
        self.lastTile = 'xx' # place holder for None
        self.__lastSource = '1' # no source: blessing from heaven or earth
        self.lastMeld = Meld()
        self.remote = None # only for server

    def clearHand(self):
        """clear player data concerning the current hand"""
        self.concealedTiles = []
        self.exposedMelds = []
        self.concealedMelds = []
        self.bonusTiles = []
        self.handContent = None
        self.lastTile = 'xx'
        self.lastSource = '1'
        self.lastMeld = Meld()
        self.__payment = 0

    @apply
    def lastSource():
        """the name id of this player"""
        def fget(self):
            return self.__lastSource
        def fset(self, lastSource):
            self.__lastSource = lastSource
            if lastSource == 'd' and not self.game.wall.living:
                self.__lastSource = 'Z'
            if lastSource == 'w' and not self.game.wall.living:
                self.__lastSource = 'z'
        return property(**locals())

    @apply
    def nameid():
        """the name id of this player"""
        def fget(self):
            if self.game.shouldSave:
                host = self.game.host
            else:
                # if we should not save, the server uses the same database as we do,
                # so use the player ids the server uses
                # TODO: this does not cover the case where the server is really remote but two
                # local players share the same data base. The server should pass all player ids
                # together with shouldSave=False
                host = Query.serverName
            return Players.allIds[(host,  self.name)]
        return property(**locals())

    def hasManualScore(self):
        return False

    @apply
    def handTotal():
        """the name id of this player"""
        def fget(self):
            if self.hasManualScore():
                spValue =  self.game.field.scoringDialog.spValues[self.idx]
                return spValue.value()
            if self.handContent:
                return self.handContent.total()
            return 0
        return property(**locals())

    @apply
    def balance():
        """the balance of this player"""
        def fget(self):
            return self.__balance
        def fset(self, balance):
            self.__balance = balance
            self.__payment = 0
        return property(**locals())

    @apply
    def values():
        """the values that are still needed after ending a hand"""
        def fget(self):
            return self.name, self.wind, self.balance
        def fset(self, values):
            self.name = values[0]
            self.wind = values[1]
            self.balance = values[2]
        return property(**locals())

    def getsPayment(self, payment):
        """make a payment to this player"""
        self.__balance += payment
        self.__payment += payment

    @apply
    def payment():
        """the payments for the current hand"""
        def fget(self):
            return self.__payment
        def fset(self, payment):
            assert payment == 0
            self.__payment = 0
        return property(**locals())

    def __repr__(self):
        return '%s %s' % (self.name,  self.wind)

    def addTile(self, tileName, sync=True):
        """add to my concealed tiles"""
        if tileName[0] in 'fy':
            self.bonusTiles.append(tileName)
        else:
            self.concealedTiles.append(tileName)

    def removeTile(self, tileName):
        """remove from my concealed tiles"""
        self.concealedTiles.remove(tileName)

    def hasConcealedTiles(self, tileNames):
        """do I have those concealed tiles?"""
        concealedTiles = self.concealedTiles[:]
        for tile in tileNames:
            if tile not in concealedTiles:
                return False
            concealedTiles.remove(tile)
        return True

    def hasExposedPungOf(self, tileName):
        for meld in self.exposedMelds:
            if meld.pairs == [tileName.lower()] * 3:
                return True
        return False

    def makeTilesKnown(self, tileNames):
        """another player exposes something"""
        if not isinstance(tileNames, list):
            tileNames = [tileNames]
        for tileName in tileNames:
            if tileName[0].isupper():
                # VisiblePlayer.addtile would update HandBoard
                # but we do not want that now
                Player.addTile(self, tileName)
                Player.removeTile(self,'Xy')

    def exposeMeld(self, meldTiles, claimed=True):
        """exposes a meld with meldTiles: removes them from concealedTiles,
        adds the meld to exposedMelds
        lastTile is the tile just added to the player. If we declare
        a kong we already had, lastTile is None.
        lastTile is not included in meldTiles.
        If lastTile is a claimed tile, it is already exposed"""
        game = self.game
        game.activePlayer = self
        if len(meldTiles) == 4 and meldTiles[0].islower():
            tile0 = meldTiles[0].lower()
            # we are adding a 4th tile to an exposed pung
            self.exposedMelds = [meld for meld in self.exposedMelds if meld.pairs != [tile0] * 3]
            self.exposedMelds.append(Meld(tile0 * 4))
            self.concealedTiles.remove(meldTiles[3])
        else:
            meld = Meld(meldTiles)
            pairs = meld.pairs
            assert pairs.isUpper(), meld.joined
            for meldTile in pairs:
                self.concealedTiles.remove(meldTile)
            if len(pairs) < 4:
                pairs.toLower()
            else:
                if claimed:
                    pairs.toLower(0, 3)
                    pairs.toUpper(3)
                else: # concealed kong
                    pairs.toLower(0)
                    pairs.toUpper(1, 3)
                    pairs.toLower(3)
            self.exposedMelds.append(meld)

    def popupMsg(self, msg):
        pass

    def hidePopup(self):
        pass

    def syncHandBoard(self):
        pass

    def __mjString(self):
        """compile hand info into  a string as needed by the scoring engine"""
        game = self.game
        assert game
        winds = self.wind.lower() + 'eswn'[game.roundsFinished]
        wonChar = 'm'
        if self == game.winner:
            wonChar = 'M'
            lastSource = self.lastSource
        else:
            lastSource = ''
        return ''.join([wonChar, winds, lastSource])

    def __lastString(self):
        """compile hand info into  a string as needed by the scoring engine"""
        game = self.game
        if game is None:
            return ''
        if self != game.winner:
            return ''
        return 'L%s%s' % (self.lastTile, self.lastMeld.joined)

    def computeHandContent(self, withTile=None):
        assert not (self.concealedMelds and self.concealedTiles)
        prevLastTile = self.lastTile
        if withTile:
            self.lastTile = withTile
        try:
            melds = [''.join(self.concealedTiles)]
            if withTile:
                melds[0] += withTile
            melds.extend(x.joined for x in self.exposedMelds)
            melds.extend(x.joined for x in self.concealedMelds)
            melds.extend(self.bonusTiles)
            melds.append(self.__mjString())
            melds.append(self.__lastString())
        finally:
            self.lastTile = prevLastTile
        if self.game.eastMJCount == 8 and self == self.game.winner and self.wind == 'E':
            # eastMJCount will only be inced later, in saveHand
            rules = [self.game.ruleset.findManualRule('XXXE9')]
        else:
            rules = None
        return HandContent.cached(self.game.ruleset, ' '.join(melds), computedRules=rules)

    def offsetTiles(self, tileName, offsets):
        chow2 = Tile.chiNext(tileName, offsets[0])
        chow3 = Tile.chiNext(tileName, offsets[1])
        return [chow2, chow3]

    def possibleChows(self, tileName):
        """returns a unique list of lists with possible chow combinations"""
        try:
            value = int(tileName[1])
        except ValueError:
            return []
        chows = []
        for offsets in [(1, 2), (-2, -1), (-1, 1)]:
            if value + offsets[0] >= 1 and value + offsets[1] <= 9:
                chow = self.offsetTiles(tileName, offsets)
                if self.hasConcealedTiles(chow):
                    chow.append(tileName)
                    if chow not in chows:
                        chows.append(sorted(chow))
        return chows

    def possiblePung(self, tileName):
        if self.concealedTiles.count(tileName) >= 2:
            return [tileName] * 3

    def possibleKong(self, tileName):
        """can we call kong with tileName?"""
        if self.concealedTiles.count(tileName) == 3:
            return [tileName] * 4

    def containsPossibleKong(self, tileName):
        """if we have a concealed kong of tileName, return it
        as a list of tileNames"""
        assert tileName[0].isupper(), tileName
        if self.concealedTiles.count(tileName) == 4:
            return [tileName] * 4
        searchMeld = tileName.lower() * 3
        allMeldContent = ' '.join(x.joined for x in self.exposedMelds)
        if searchMeld in allMeldContent:
            return [tileName.lower()] * 3 + [tileName]
    def declaredMahJongg(self, concealed, withDiscard, lastTile, lastMeld):
        lastMeld = Meld(lastMeld) # do not change the original!
        self.game.winner = self
        melds = [Meld(x) for x in concealed.split()]
        if withDiscard:
            if self.game.belongsToHumanPlayer():
                discardBoard = self.game.field.discardBoard
                discardBoard.lastDiscarded.board = None
                discardBoard.lastDiscarded = None
            self.lastTile = withDiscard.lower()
            self.lastSource = 'd'
            # the last claimed meld is exposed
            melds.remove(lastMeld)
            lastMeld.pairs.toLower()
            self.exposedMelds.append(lastMeld)
            self.lastMeld = lastMeld
        else:
            self.lastTile = lastTile
            self.lastMeld = lastMeld
        self.concealedMelds = melds
        self.concealedTiles = []
        self.syncHandBoard()

class Wall(object):
    """represents the wall with four sides. self.wall[] indexes them counter clockwise, 0..3. 0 is bottom."""
    def __init__(self, game):
        """init and position the wall"""
        # we use only white dragons for building the wall. We could actually
        # use any tile because the face is never shown anyway.
        self.game = game
        self.tileCount = Elements.count(game.ruleset.withBonusTiles)
        self.tiles = []
        self.living = None
        self.kongBox = None
        assert self.tileCount % 8 == 0
        self.length = self.tileCount // 8

    def dealTo(self, player=None, deadEnd=False, count=1):
        """deal tiles to player. May raise WallEmpty.
        Returns a list of tileNames"""
        if deadEnd:
            if len(self.kongBox) < count:
                raise WallEmpty
            tiles = self.kongBox[-count:]
            self.kongBox= self.kongBox[:-count]
            if len(self.kongBox) % 2 == 0:
                self.placeLooseTiles()
        else:
            if len(self.living) < count:
                raise WallEmpty
            tiles = self.living[:count]
            self.living = self.living[count:]
        tileNames = [x.element for x in tiles]
        for tile in tiles:
            tile.board = None
            del tile
        if player:
            for tile in tileNames:
                player.addTile(tile, sync=False)
        return tileNames

    def removeTiles(self, count, deadEnd=False):
        """remove count tiles from the living or dead end. Removes the
        number of actually removed tiles"""
        removed = 0
        for idx in range(count):
            if deadEnd:
                tile = self.kongBox[-1]
                self.kongBox = self.kongBox[:-1]
                if len(self.kongBox) % 2 == 0:
                    self.placeLooseTiles()
            else:
                tile = self.living[0]
                self.living= self.living[1:]
            tile.board = None
            del tile
            removed += 1
        return removed

    def build(self, tiles=None):
        """builds the wall from tiles without dividing them"""

        # first do a normal build without divide
        # replenish the needed tiles
        if tiles:
            self.tiles =tiles
            assert len(tiles) == self.tileCount
            random.shuffle(self.tiles)
        else:
            self.tiles.extend(Tile('Xy') for x in range(self.tileCount-len(self.tiles)))
            self.tiles = self.tiles[:self.tileCount] # in case we have to reduce. Possible at all?

    def placeLooseTiles(self):
        pass

    def divide(self):
        """divides a wall, building a living and and a dead end"""
        # neutralise the different directions of winds and removal of wall tiles
        assert self.game.divideAt is not None
        # shift tiles: tile[0] becomes living end
        assert len(self.tiles) == self.tileCount
        self.tiles[:] = self.tiles[self.game.divideAt:] + self.tiles[0:self.game.divideAt]
        kongBoxSize = self.game.ruleset.kongBoxSize
        self.living = self.tiles[:-kongBoxSize]
        a = self.tiles[-kongBoxSize:]
        for pair in range(kongBoxSize // 2):
            a=a[:pair*2] + [a[pair*2+1], a[pair*2]] + a[pair*2+2:]
        self.kongBox = a

class Game(object):
    """the game without GUI"""
    def __init__(self, names, ruleset, gameid=None, seed=None, field=None, shouldSave=True, client=None):
        """a new game instance. May be shown on a field, comes from database if gameid is set

        Game.lastDiscard is the tile last discarded by any player. It is reset to None when a
        player gets a tile from the living end of the wall.
        """
        self.seed = seed or InternalParameters.seed or int(random.random() * 10**12)
        random.seed(self.seed)
        self.rotated = 0
        self.players = [] # if we fail later on in init, at least we can still close the program
        self.activePlayer = None
        self.field = field
        self.ruleset = None
        self.winner = None
        self.roundsFinished = 0
        self.gameid = gameid
        self.shouldSave = shouldSave
        if not shouldSave:
            data = Query("select id from game where seed='%s' order by id desc"% str(self.seed)).data
            self.gameid = data[0][0]
        self.handctr = 0
        self.divideAt = None
        self.lastDiscard = None # always uppercase
        self.eastMJCount = 0
        self.client = client
        self.__useRuleset(ruleset)
        if field:
            field.game = self
            field.showWall()
        else:
            self.wall = Wall(self)
        # shift rules taken from the OEMC 2005 rules
        # 2nd round: S and W shift, E and N shift
        self.shiftRules = 'SWEN,SE,WE'
        for name in names:
            Players.createIfUnknown(self.host, name)
        if field:
            self.players = field.genPlayers()
        else:
            self.players = Players([Player(self) for idx in range(4)])
        for idx, player in enumerate(self.players):
            player.name = names[idx]
            player.wind = WINDS[idx]
        if self.client and self.client.username:
            self.myself = self.players.byName(self.client.username)
        else:
           self.myself = None
        if not self.gameid:
            self.gameid = self.__newGameId()
        if field:
            self.initVisiblePlayers()
            field.refresh()
            self.wall.decorate()

    def close(self, callback=None):
        if self.client:
            d = self.client.logout()
            self.client = None
            if d:
                d.addBoth(self.clientLoggedOut)
                if callback:
                    d.addBoth(callback)
                return
        self.clientLoggedOut()
        if callback:
            callback()

    def clientLoggedOut(self, result):
        for player in self.players:
            player.clearHand()
            if player.handBoard:
                player.handBoard.hide()
            player.handBoard = None
        if self.field:
            self.field.setWindowTitle('kmj')
            self.removeWall()
            self.field.game = None
            self.field.refresh()

    def removeWall(self):
        if self.wall:
            self.wall.hide()
            self.wall = None

    def initVisiblePlayers(self):
        for idx, player in enumerate(self.players):
            player.front = self.wall[idx]
            player.clearHand()
            player.handBoard.setVisible(True)
            scoring = self.isScoringGame()
            player.handBoard.setEnabled(scoring or \
                (self.belongsToHumanPlayer() and player == self.myself))
            player.handBoard.showMoveHelper(scoring)
        self.field.selectorBoard.fill(self)
        self.field._adjustView()

    def losers(self):
        """the 3 or 4 losers: All players without the winner"""
        return list([x for x in self.players if x is not self.winner])

    def visibleTiles(self):
        """returns a dict of all tiles (lowercase) with a count how often they
        appear in the discardboard or exposed.
        We might optimize this by replacing this method by a list which
        is always updated as needed but not now"""
        tiles = [x.element for x in self.field.discardBoard.allTiles()]
        for player in self.players:
            for meld in player.exposedMelds:
                tiles.extend(meld.pairs)
        result = dict()
        for tile in tiles:
            tile = tile.lower()
            result[tile] = result.get(tile, 0) + 1
        return result

    @staticmethod
    def windOrder(player):
        """cmp function for __exchangeSeats"""
        return 'ESWN'.index(player.wind)

    @apply
    def host():
        def fget(self):
            return self.client.host if self.client else ''
        return property(**locals())

    def belongsToRobotPlayer(self):
        return self.client and self.client.isRobotClient()

    def belongsToHumanPlayer(self):
        return self.client and self.client.isHumanClient()

    def belongsToGameServer(self):
        return self.client and self.client.isServerClient()

    def isScoringGame(self):
        return bool(not self.client)

    def belongsToPlayer(self):
        return self.belongsToRobotPlayer() or self.belongsToHumanPlayer()

    def __exchangeSeats(self):
        """execute seat exchanges according to the rules"""
        windPairs = self.shiftRules.split(',')[self.roundsFinished-1]
        while len(windPairs):
            windPair = windPairs[0:2]
            windPairs = windPairs[2:]
            swappers = list(self.players[windPair[x]] for x in (0, 1))
            if self.belongsToPlayer():
                # we are a client in a remote game, the server swaps and tells us the new places
                shouldSwap = False
            elif self.isScoringGame():
                # we play a manual game and do only the scoring
                shouldSwap = self.field.askSwap(swappers)
            else:
                # we are the game server. Always swap in remote games.
                assert self.belongsToGameServer()
                shouldSwap = True
            if shouldSwap:
                swappers[0].wind,  swappers[1].wind = swappers[1].wind,  swappers[0].wind
        self.sortPlayers()

    def sortPlayers(self):
        """sort by wind order. If we are in a remote game, place ourself at bottom (idx=0)"""
        players = self.players
        if self.field:
            fieldAttributes = list([(p.handBoard, p.front) for p in players])
        players.sort(key=Game.windOrder)
        if self.belongsToHumanPlayer():
            myName = self.myself.name
            while players[0].name != myName:
                values0 = players[0].values
                for idx in range(4, 0, -1):
                    this, prev = players[idx % 4], players[idx - 1]
                    this.values = prev.values
                players[1].values = values0
            self.myself = players[0]
        if self.field:
            for idx, player in enumerate(players):
                player.handBoard, player.front = fieldAttributes[idx]

    def __newGameId(self):
        """write a new entry in the game table with the selected players
        and returns the game id of that new entry"""
        starttime = datetime.datetime.now().replace(microsecond=0).isoformat()
        # first insert and then find out which game id we just generated. Clumsy and racy.
        Query("insert into game(starttime,server,seed,ruleset,p0,p1,p2,p3) values(?, ?, %d, %d, %s)" % \
            (self.seed, self.ruleset.rulesetId, ','.join(str(p.nameid) for p in self.players)),
            list([starttime, self.host]))
        return Query(["update usedruleset set lastused='%s' where id=%d" %\
                (starttime, self.ruleset.rulesetId),
            "update ruleset set lastused='%s' where hash='%s'" %\
                (starttime, self.ruleset.hash),
            "select id from game where starttime = '%s' and seed='%s'" % \
                (starttime, self.seed)]).data[0][0]

    def __useRuleset(self,  ruleset):
        """use a copy of ruleset for this game, reusing an existing copy"""
        self.ruleset = ruleset
        self.ruleset.load()
        query = Query('select id from usedruleset where hash="%s"' % \
              (self.ruleset.hash))
        if query.data:
            # reuse that usedruleset
            self.ruleset.rulesetId = query.data[0][0]
        else:
            # generate a new usedruleset
            self.ruleset.rulesetId = self.ruleset.newId(used=True)
            self.ruleset.save()

    def prepareHand(self):
        if self.finished():
            self.close()
        else:
            for player in self.players:
                player.clearHand()
            self.winner = None
            self.sortPlayers()
            self.hidePopups()
            self.activePlayer = self.players['E']
            self.wall.build()
        if self.field:
            self.field.prepareHand()

    def hidePopups(self):
        """hide all popup messages"""
        for player in self.players:
            player.hidePopup()

    def saveHand(self):
        """save hand to data base, update score table and balance in status line"""
        self.__payHand()
        self.__saveScores()
        self.handctr += 1
        if self.winner and self.winner.wind == 'E':
             self.eastMJCount += 1
        if self.field:
            self.field.refresh()

    def needSave(self):
        """do we need to save this game?"""
        if self.isScoringGame():
            return True
        elif self.belongsToRobotPlayer():
            return False
        else:
            return self.shouldSave      # as the server told us

    def __saveScores(self):
        """save computed values to data base, update score table and balance in status line"""
        if not self.needSave():
            return
        scoretime = datetime.datetime.now().replace(microsecond=0).isoformat()
        for player in self.players:
            if player.handContent:
                manualrules = '||'.join(x.name for x, meld in player.handContent.usedRules)
            else:
                manualrules = m18n('Score computed manually')
            Query("INSERT INTO SCORE "
                "(game,hand,data,manualrules,player,scoretime,won,prevailing,wind,points,payments, balance,rotated) "
                "VALUES(%d,%d,?,?,%d,'%s',%d,'%s','%s',%d,%d,%d,%d)" % \
                (self.gameid, self.handctr, player.nameid,
                    scoretime, int(player == self.winner),
                    WINDS[self.roundsFinished], player.wind, player.handTotal,
                    player.payment, player.balance, self.rotated),
                list([player.handContent.string, manualrules]))

    def savePenalty(self, player, offense, amount):
        """save computed values to data base, update score table and balance in status line"""
        if not self.needSave():
            return
        scoretime = datetime.datetime.now().replace(microsecond=0).isoformat()
        Query("INSERT INTO SCORE "
            "(game,hand,data,manualrules,player,scoretime,won,prevailing,wind,points,payments, balance,rotated) "
            "VALUES(%d,%d,?,?,%d,'%s',%d,'%s','%s',%d,%d,%d,%d)" % \
            (self.gameid, self.handctr, player.nameid,
                scoretime, int(player == self.winner),
                WINDS[self.roundsFinished], player.wind, 0,
                amount, player.balance, self.rotated),
            list([player.handContent.string, offense.name]))
        if self.field:
            self.field.discardBoard.clear()
            self.field.refresh()

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
        self.eastMJCount = 0
        if self.rotated == 4:
            if not self.finished():
                self.roundsFinished += 1
            self.rotated = 0
        if self.finished():
            endtime = datetime.datetime.now().replace(microsecond=0).isoformat()
            Query('UPDATE game set endtime = "%s" where id = %d' % \
                  (endtime, self.gameid))
        elif not self.belongsToPlayer():
            # the game server already told us the new placement and winds
            winds = [player.wind for player in self.players]
            winds = winds[3:] + winds[0:3]
            for idx,  newWind in enumerate(winds):
                self.players[idx].wind = newWind
            if 0 < self.roundsFinished < 4 and self.rotated == 0:
                self.__exchangeSeats()

    @staticmethod
    def load(gameid, field=None, client=None):
        """load game data by game id and return a new Game instance"""
        qGame = Query("select p0, p1, p2, p3, ruleset from game where id = %d" % gameid)
        if not qGame.data:
            return None
        rulesetId = qGame.data[0][4] or 1
        ruleset = Ruleset(rulesetId, used=True)
        Players.load() # we want to make sure we have the current definitions
        hosts = []
        names = []
        for idx in range(4):
            nameid = qGame.data[0][idx]
            try:
                (host, name) = Players.allNames[nameid]
            except KeyError:
                name = m18n('Player %1 not known', nameid)
            hosts.append(host)
            names.append(name)
        if len(set(hosts)) != 1:
            logException('Game %d has players from different hosts' % gameid)
        game = Game(names, ruleset, gameid=gameid, field=field, client=client)

        qLastHand = Query("select hand,rotated from score where game=%d and hand="
            "(select max(hand) from score where game=%d)" % (gameid, gameid))
        if qLastHand.data:
            (game.handctr, game.rotated) = qLastHand.data[0]

        qScores = Query("select player, wind, balance, won, prevailing from score "
            "where game=%d and hand=%d" % (gameid, game.handctr))
        for record in qScores.data:
            playerid = record[0]
            wind = str(record[1])
            player = game.players.byId(playerid)
            if not player:
                logMessage(
                'game %d data inconsistent: player %d missing in game table' % \
                    (gameid, playerid), syslog.LOG_ERR)
            else:
                player.getsPayment(record[2])
                player.wind = wind
            if record[3]:
                game.winner = player
            prevailing = record[4]
        game.roundsFinished = WINDS.index(prevailing)
        game.handctr += 1
        game.maybeRotateWinds()
        # TODO: init game.eastMJCount
        return game

    def finished(self):
        """The game is over after 4 completed rounds"""
        return self.roundsFinished == 4

    def __payHand(self):
        """pay the scores"""
        winner = self.winner
        for player in self.players:
            if player.handContent.hasAction('payforall'):
                score = winner.handTotal
                if winner.wind == 'E':
                    score = score * 6
                else:
                    score = score * 4
                player.getsPayment(-score)
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

    def checkSelectorTiles(self):
        result = True
        if self.field:
            handBoards = list([p.handBoard for p in self.players])
            counts = {}
            selectorTiles = self.field.selectorBoard.allTiles()
            for tile in selectorTiles:
                counts[tile.element.lower()] = tile.count
            for board in handBoards:
                if board:
                    for tile in board.allTiles():
                        if tile.element != 'Xy':
                            counts[tile.element.lower()] += 1
            for tile in selectorTiles:
                ctr = counts[tile.element.lower()]
                if ctr != tile.maxCount:
                    print 'count %d wrong for tile %s: maximum %d' % (ctr, tile.element, tile.maxCount)
                    result = False
        if not result:
            raise Exception('checkSelectorTiles failed')

    def throwDices(self):
        """sets random living and kongBox
        sets divideAt: an index for the wall break"""
        if self.belongsToGameServer():
            tiles = [Tile(x) for x in Elements.all(self.ruleset.withBonusTiles)]
            for tile in tiles:
                if not tile.isBonus():
                    tile.element = tile.element.capitalize()
        else:
            tiles = None
        self.wall.build(tiles)
        breakWall = random.randrange(4)
        wallLength = self.wall.tileCount // 4
        # use the sum of four dices to find the divide
        self.divideAt = breakWall * wallLength + sum(random.randrange(1, 7) for idx in range(4))
        if self.divideAt % 2 == 1:
            self.divideAt -= 1
        self.divideAt %= self.wall.tileCount

class RemoteGame(Game):
    """this game is played using the computer"""

    def __init__(self, names, ruleset, gameid=None, seed=None, field=None, shouldSave=True, client=None):
        """a new game instance. May be shown on a field, comes from database if gameid is set"""
        self.__activePlayer = None
        self.prevActivePlayer = None
        self.defaultNameBrush = None
        Game.__init__(self, names, ruleset, gameid, seed=seed, field=field, shouldSave=shouldSave, client=client)

    @apply
    def activePlayer():
        """the turn is on this player"""
        def fget(self):
            return self.__activePlayer
        def fset(self, player):
            if self.__activePlayer != player:
                self.prevActivePlayer = self.__activePlayer
                self.__activePlayer = player
                if self.field: # mark the name of the active player in blue
                    for player in self.players:
                        name = player.front.nameLabel
                        if not self.defaultNameBrush:
                            self.defaultNameBrush = name.brush()
                        if player == self.activePlayer:
                            brush = QBrush(QColor(Qt.blue))
                        else:
                            brush = self.defaultNameBrush
                        name.setBrush(brush)
        return property(**locals())

    def IAmNext(self):
        return self.myself == self.nextPlayer()

    def nextPlayer(self, current=None):
        """returns the player after current or after activePlayer"""
        if not current:
            current = self.activePlayer
        pIdx = self.players.index(current)
        return self.players[(pIdx + 1) % 4]

    def nextTurn(self):
        """move activePlayer"""
        self.activePlayer = self.nextPlayer()

    def deal(self):
        """every player gets 13 tiles (including east)"""
        self.throwDices()
        self.wall.divide()
        for player in self.players:
            player.clearHand()
            while len(player.concealedTiles) != 13:
                self.wall.dealTo(player)
            player.syncHandBoard()

    def setTiles(self, player, tiles):
        """when starting the hand. tiles is one string"""
        for tile in tiles:
            Player.addTile(player, tile)
        if self.field:
            player.syncHandBoard()
            self.wall.dealTo(count=len(tiles))

    def showTiles(self, player, tiles):
        """when ending the hand. tiles is one string"""
        assert player != self.myself, '%s %s' % (player, self.myself)
        if player != self.winner:
            # the winner separately exposes its mah jongg melds
            xyTiles = player.concealedTiles[:]
            assert len(tiles) == len(xyTiles), '%s server says: showTiles %s, we have %s' % (player, tiles, xyTiles)
            for tile in tiles:
                Player.removeTile(player,'Xy') # without syncing handBoard
                Player.addTile(player, tile)
        player.syncHandBoard()

    def pickedTile(self, player, tile, deadEnd):
        """got a tile from wall"""
        self.activePlayer = player
        player.addTile(tile)
        player.lastTile = tile
        if deadEnd:
            player.lastSource = 'e'
        else:
            self.lastDiscard = None
            player.lastSource = 'w'

    def showField(self):
        """show remote game in field"""
        self.wall.divide()
        if self.field:
            self.field.setWindowTitle(m18n('Game <numid>%1</numid>', str(self.seed)) + ' - kmj')
            self.field.discardBoard.setRandomPlaces()
            for tableList in self.field.tableLists:
                tableList.hide()
            self.field.tableLists = []

    def hasDiscarded(self, player, tileName):
        """discards a tile from a player board"""
        self.lastDiscard = tileName
        if player != self.activePlayer:
            raise Exception('Player %s discards but %s is active' % (player, self.activePlayer))
        if self.field:
            self.field.discardBoard.addTile(tileName)
        if self.myself and player != self.myself:
            # we are human and server tells us another player discarded a tile. In our
            # game instance, tiles in handBoards of other players are unknown
            tileName = 'Xy'
        if not tileName in player.concealedTiles:
            raise Exception('I am %s. Player %s is told to show discard of tile %s but does not have it' % \
                           (self.myself.name if self.myself else 'None', player.name, tileName))
        player.removeTile(tileName)

    def saveHand(self):
        for player in self.players:
            player.handContent = player.computeHandContent()
            if player == self.winner:
                assert player.handContent.maybeMahjongg()
        Game.saveHand(self)

