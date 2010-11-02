# -*- coding: utf-8 -*-

"""
Copyright (C) 2008,2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

import sys, datetime, syslog
from random import Random
from collections import defaultdict

from PyQt4.QtCore import Qt
from PyQt4.QtGui import QBrush, QColor

from util import logMessage, logException, logWarning,  debugMessage, m18n, isAlive
from common import WINDS, InternalParameters, elements, IntDict
from query import Transaction, Query
from scoringengine import Ruleset
from tile import Tile, offsetTiles
from meld import Meld, CONCEALED
from scoringengine import HandContent
from sound import Voice
from wall import Wall
from move import Move

class Players(list):
    """a list of players where the player can also be indexed by wind.
    The position in the list defines the place on screen. First is on the
    screen bottom, second on the right, third top, forth left"""

    allNames = {}
    allIds = {}

    def __init__(self, players=None):
        list.__init__(self)
        if players:
            self.extend(players)

    def __getitem__(self, index):
        """allow access by idx or by wind"""
        if isinstance(index, basestring) and len(index) == 1:
            for player in self:
                if player.wind == index:
                    return player
            logException("no player has wind %s" % index)
        return list.__getitem__(self, index)

    def __str__(self):
        return ', '.join(list('%s: %s' % (x.name, x.wind) for x in self))

    def byId(self, playerid):
        """lookup the player by id"""
        for player in self:
            if player.nameid == playerid:
                return player
        logException("no player has id %d" % playerid)

    def byName(self, playerName):
        """lookup the player by name"""
        for player in self:
            if player.name == playerName:
                return player
        logException("no player has name %s" % playerName)

    @staticmethod
    def load():
        """load all defined players into self.allIds and self.allNames"""
        query = Query("select id,name from player")
        if not query.success:
            sys.exit(1)
        Players.allIds = {}
        Players.allNames = {}
        for nameid, name in query.records:
            Players.allIds[name] = nameid
            Players.allNames[nameid] = name

    @staticmethod
    def createIfUnknown(name):
        """create player in database if not there yet"""
        if name not in Players.allNames.values():
            Players.load()  # maybe somebody else already added it
            if name not in Players.allNames.values():
                with Transaction():
                    Query("insert into player(name) values(?)",
                          list([name]))
                Players.load()
        assert name in Players.allNames.values()

class Player(object):
    """all player related attributes without GUI stuff.
    concealedTileNames: used during the hand for all concealed tiles, ungrouped.
    concealedMelds: is empty during the hand, will be valid after end of hand,
    containing the concealed melds as the player presents them."""
    # pylint: disable=R0902
    # pylint we need more than 10 instance attributes

    def __init__(self, game, handContent=None):
        self.game = game
        self.handContent = handContent
        self.__balance = 0
        self.__payment = 0
        self.wonCount = 0
        self.name = ''
        self.wind = WINDS[0]
        self.visibleTiles = IntDict(game.visibleTiles)
        self.clearHand()
        self.__lastSource = '1' # no source: blessing from heaven or earth
        self.remote = None # only for server
        self.voice = None

    def speak(self, text):
        """speak if we have a voice"""
        if self.voice:
            self.voice.speak(text)

    def clearHand(self):
        """clear player attributes concerning the current hand"""
        self.concealedTileNames = []
        self.exposedMelds = []
        self.concealedMelds = []
        self.bonusTiles = []
        self.discarded = []
        self.visibleTiles.clear()
        self.handContent = None
        self.lastTile = 'xx'
        self.lastSource = '1'
        self.lastMeld = Meld()
        self.mayWin = True
        self.__payment = 0
        self.originalCall = False
        self.dangerousTiles = set()
        self.claimedNoChoice = False
        self.playedDangerous = False
        self.usedDangerousFrom = None

    @apply
    def lastSource(): # pylint: disable=E0202
        """the source of the last tile the player got"""
        def fget(self):
            # pylint: disable=W0212
            return self.__lastSource
        def fset(self, lastSource):
            # pylint: disable=W0212
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
            return Players.allIds[self.name]
        return property(**locals())

    def hasManualScore(self): # pylint: disable=R0201
        """virtual: has a manual score been entered for this game?"""
        # pylint does not recognize that this is overridden by
        # an implementation that needs self
        return False

    @apply
    def handTotal():
        """the name id of this player"""
        def fget(self):
            if self.hasManualScore():
                spValue =  InternalParameters.field.scoringDialog.spValues[self.idx]
                return spValue.value()
            if self.handContent:
                return self.handContent.total()
            return 0
        return property(**locals())

    @apply
    def balance():
        """the balance of this player"""
        def fget(self):
            # pylint: disable=W0212
            return self.__balance
        def fset(self, balance):
            # pylint: disable=W0212
            self.__balance = balance
            self.__payment = 0
        return property(**locals())

    @apply
    def values():
        """the values that are still needed after ending a hand"""
        def fget(self):
            return self.name, self.wind, self.balance, self.voice
        def fset(self, values):
            self.name = values[0]
            self.wind = values[1]
            self.balance = values[2]
            self.voice = values[3]
        return property(**locals())

    def getsPayment(self, payment):
        """make a payment to this player"""
        self.__balance += payment
        self.__payment += payment

    @apply
    def payment():
        """the payments for the current hand"""
        def fget(self):
            # pylint: disable=W0212
            return self.__payment
        def fset(self, payment):
            assert payment == 0
            self.__payment = 0
        return property(**locals())

    def __repr__(self):
        return '%s %s' % (self.name, self.wind)

    def addConcealedTiles(self, data):
        """add to my tiles and sync the hand board"""
        assert isinstance(data, (Tile, list)), data
        assert not self.game.isScoringGame()
        if isinstance(data, Tile):
            data = list([data])
        for tile in data:
            assert isinstance(tile, Tile)
            tileName = tile.element
            if tile.isBonus():
                self.bonusTiles.append(tile)
            else:
                assert tileName.istitle()
                self.concealedTileNames.append(tileName)
        if data:
            self.syncHandBoard(adding=data)

    def addMeld(self, meld):
        """add meld to this hand in a scoring game"""
        assert self.game.isScoringGame()
        if len(meld) == 1 and meld[0].isBonus():
            self.bonusTiles.append(meld[0])
        elif meld.state == CONCEALED and not meld.isKong():
            self.concealedMelds.append(meld)
        else:
            self.exposedMelds.append(meld)

    def remove(self, tile=None, meld=None):
        """remove from my melds or tiles"""
        tiles = [tile] if tile else meld.tiles
        if len(tiles) == 1 and tiles[0].isBonus():
            self.bonusTiles.remove(tiles[0])
            self.syncHandBoard()
            return
        if tile:
            assert not meld, (str(tile), str(meld))
            assert not self.game.isScoringGame()
            tileName = tile.element
            try:
                self.concealedTileNames.remove(tileName)
            except ValueError:
                raise Exception('removeTiles(%s): tile not in concealed %s' % \
                    (tileName, ''.join(self.concealedTileNames)))
        else:
            self.removeMeld(meld)
        self.syncHandBoard()

    def removeMeld(self, meld):
        """remove a meld from this hand in a scoring game"""
        assert self.game.isScoringGame()
        for melds in [self.concealedMelds, self.exposedMelds]:
            for idx, myTile in enumerate(melds):
                if id(myTile) == id(meld):
                    melds.pop(idx)

    def hasConcealedTiles(self, tileNames):
        """do I have those concealed tiles?"""
        concealedTileNames = self.concealedTileNames[:]
        for tileName in tileNames:
            if tileName not in concealedTileNames:
                return False
            concealedTileNames.remove(tileName)
        return True

    def setConcealedTiles(self, tileNames):
        """when starting the hand. tiles is one string"""
        self.addConcealedTiles(self.game.wall.deal(tileNames))

    def showConcealedTiles(self, tileNames, show=True):
        """show or hide tileNames"""
        if not self.game.playOpen:
            if not isinstance(tileNames, list):
                tileNames = [tileNames]
            assert len(tileNames) <= len(self.concealedTileNames), \
                '%s: showConcealedTiles %s, we have only %s' % (self, tileNames, self.concealedTileNames)
            for tileName in tileNames:
                src,  dst = ('Xy', tileName) if show else (tileName, 'Xy')
                assert src in self.concealedTileNames,  \
                    '%s: showConcealedTiles %s, we have only %s' % (self, tileNames, self.concealedTileNames)
                idx = self.concealedTileNames.index(src)
                self.concealedTileNames[idx] = dst

    def hasExposedPungOf(self, tileName):
        """do I have an exposed Pung of tileName?"""
        for meld in self.exposedMelds:
            if meld.pairs == [tileName.lower()] * 3:
                return True
        return False

    def robTile(self, tileName):
        """used for robbing the kong"""
        tileName = tileName.lower()
        for meld in self.exposedMelds:
            if tileName in meld.pairs:
                self.exposedMelds.remove(meld)
                state = meld.state
                newPairs = meld.pairs[:]
                newPairs.remove(tileName)
                newMeld = Meld(newPairs)
                newMeld.state = state
                self.exposedMelds.append(newMeld)
                tileName = tileName.lower()
                self.visibleTiles[tileName] -= 1
                self.syncHandBoard()
                return
        raise Exception('robTile: no meld found with %s' % tileName)

    def mustPlayDangerous(self):
        """returns True if the player has no choice"""
        if self.game.dangerousTiles:
            for meld in self.computeHandContent().hiddenMelds:
                for tile in meld.pairs:
                    if tile not in self.game.dangerousTiles:
                        return False
            return True

    def exposeMeld(self, meldTiles, called=None):
        """exposes a meld with meldTiles: removes them from concealedTileNames,
        adds the meld to exposedMelds and returns it
        called: we got the last tile for the meld from discarded, otherwise
        from the wall"""
        game = self.game
        game.activePlayer = self
        allMeldTiles = meldTiles[:]
        if called:
            allMeldTiles.append(called.element)
        if len(allMeldTiles) == 4 and allMeldTiles[0].islower():
            tile0 = allMeldTiles[0].lower()
            # we are adding a 4th tile to an exposed pung
            self.exposedMelds = [meld for meld in self.exposedMelds if meld.pairs != [tile0] * 3]
            meld = Meld(tile0 * 4)
            # TODO: test removal self.concealedTileNames.remove(allMeldTiles[3])
            self.visibleTiles[tile0] += 1
        else:
            if len(allMeldTiles) == 3 and allMeldTiles[0][1] != allMeldTiles[1][1]:
                # this is a chow, we might have claimed any of its tiles. But the
                # claimed tile is still last in the list.
                allMeldTiles = sorted(allMeldTiles)
            meld = Meld(allMeldTiles)
            for meldTile in meldTiles:
                self.concealedTileNames.remove(meldTile)
                self.visibleTiles[meldTile.lower()] += 1
            meld.expose(called)
        self.exposedMelds.append(meld)
        game.computeDangerous(self)
        adding = [called] if called else None
        self.syncHandBoard(adding=adding)
        return meld

    def findDangerousTiles(self):
        """update the list of dangerous tile"""
        # TODO: this is hardwired for the german CC rules, introduce options
        dangerousTiles = set()
        expMeldCount = len(self.exposedMelds)
        if expMeldCount >= 2:
            if expMeldCount >= 3:
                if all(x in elements.greenHandTiles for x in self.visibleTiles):
                    dangerousTiles |= elements.greenHandTiles
                color = defaultdict.keys(self.visibleTiles)[0][0]
                # see http://www.logilab.org/ticket/23986
                assert color.islower(), self.visibleTiles
                if color in 'sbc':
                    if all(x[0] == color for x in self.visibleTiles):
                        suitTiles = set([color+x for x in '123456789'])
                        if  self.visibleTiles.count(suitTiles) >= 9:
                            dangerousTiles |= suitTiles
                    elif all(x[1] in '19' for x in self.visibleTiles):
                        dangerousTiles |= elements.terminals
            elif expMeldCount >= 2:
                windMelds = sum(self.visibleTiles[x] >=3 for x in elements.winds)
                dragonMelds = sum(self.visibleTiles[x] >=3 for x in elements.dragons)
                windsDangerous = dragonsDangerous = False
                if windMelds + dragonMelds == expMeldCount and expMeldCount >= 3:
                    windsDangerous = dragonsDangerous = True
                windsDangerous = windsDangerous or windMelds  == 3
                dragonsDangerous = dragonsDangerous or dragonMelds == 2
                if windsDangerous:
                    dangerousTiles |= set(x for x in elements.winds if x not in self.visibleTiles)
                if dragonsDangerous:
                    dangerousTiles |= set(x for x in elements.dragons if x not in self.visibleTiles)
        self.dangerousTiles = dangerousTiles

    def popupMsg(self, msg):
        """virtual: show popup on display"""
        pass

    def hidePopup(self):
        """virtual: hide popup on display"""
        pass

    def syncHandBoard(self, adding=None):
        """virtual: synchronize display"""
        pass

    def setFocus(self, dummyTileName):
        """virtual: sets focus on a tile"""
        pass

    def __mjString(self):
        """compile hand info into a string as needed by the scoring engine"""
        game = self.game
        assert game
        winds = self.wind.lower() + 'eswn'[game.roundsFinished % 4]
        wonChar = 'm'
        lastSource = ''
        declaration = ''
        if self == game.winner:
            wonChar = 'M'
            lastSource = self.lastSource
            if self.originalCall:
                declaration = 'a'
        if not self.mayWin:
            wonChar = 'x'
        return ''.join([wonChar, winds, lastSource, declaration])

    def __lastString(self):
        """compile hand info into a string as needed by the scoring engine"""
        game = self.game
        if game is None:
            return ''
        if self != game.winner:
            return ''
        return 'L%s%s' % (self.lastTile, self.lastMeld.joined)

    def computeHandContent(self, withTile=None, robbedTile=None, dummy=None):
        """returns HandContent for this player"""
        assert not (self.concealedMelds and self.concealedTileNames)
        assert not isinstance(self.lastTile, Tile)
        prevLastTile = self.lastTile
        if withTile:
            assert not isinstance(withTile, Tile)
            self.lastTile = withTile
        try:
            melds = [''.join(self.concealedTileNames)]
            if withTile:
                melds[0] += withTile
            melds.extend(x.joined for x in self.exposedMelds)
            melds.extend(x.joined for x in self.concealedMelds)
            melds.extend(''.join(x.element) for x in self.bonusTiles)
            melds.append(self.__mjString())
            melds.append(self.__lastString())
        finally:
            self.lastTile = prevLastTile
        if self.game.eastMJCount == 8 and self == self.game.winner and self.wind == 'E':
            # eastMJCount will only be inced later, in saveHand
            rules = [self.game.ruleset.findRule('XEAST9X')]
        else:
            rules = None
        return HandContent.cached(self.game.ruleset, ' '.join(melds), computedRules=rules, robbedTile=robbedTile)

    def possibleChows(self, tileName):
        """returns a unique list of lists with possible chow combinations"""
        try:
            value = int(tileName[1])
        except ValueError:
            return []
        chows = []
        for offsets in [(1, 2), (-2, -1), (-1, 1)]:
            if value + offsets[0] >= 1 and value + offsets[1] <= 9:
                chow = offsetTiles(tileName, offsets)
                if self.hasConcealedTiles(chow):
                    chow.append(tileName)
                    if chow not in chows:
                        chows.append(sorted(chow))
        return chows

    def possibleKongs(self):
        """returns a unique list of lists with possible kong combinations"""
        kongs = []
        for tileName in set([x for x in self.concealedTileNames if x[0] not in 'fy']):
            assert tileName[0].isupper(), tileName
            if self.concealedTileNames.count(tileName) == 4:
                kongs.append([tileName] * 4)
            if self.visibleTiles[tileName.lower()] == 3:
                # maybe add 4th tile to exposed pung. We do have 3 of this
                # tile exposed, but maybe in Chows, so we must search for Pung
                if tileName.lower() * 3 in ' '.join(x.joined for x in self.exposedMelds):
                    kongs.append([tileName.lower()] * 3 + [tileName])
        return kongs

    def declaredMahJongg(self, concealed, withDiscard, lastTile, lastMeld):
        """player declared mah jongg. Determine last meld, show concealed tiles grouped to melds"""
        assert not isinstance(lastTile, Tile)
        lastMeld = Meld(lastMeld) # do not change the original!
        self.game.winner = self
        melds = [Meld(x) for x in concealed.split()]
        if withDiscard:
            assert withDiscard == self.game.lastDiscard.element
            self.addConcealedTiles(self.game.lastDiscard)
            self.lastTile = withDiscard.lower()
            if self.lastSource != 'k':   # robbed the kong
                self.lastSource = 'd'
            # the last claimed meld is exposed
            melds.remove(lastMeld)
            lastMeld.pairs.toLower()
            self.exposedMelds.append(lastMeld)
            for tileName in lastMeld.pairs:
                self.visibleTiles[tileName] += 1
            self.lastMeld = lastMeld
        else:
            self.lastTile = lastTile
            self.lastMeld = lastMeld
        self.concealedMelds = melds
        self.concealedTileNames = []
        self.syncHandBoard()

    def scoringString(self):
        """helper for HandBoard.__str__"""
        if self.concealedMelds:
            parts = [x.joined for x in self.concealedMelds + self.exposedMelds]
        else:
            parts = [''.join(self.concealedTileNames)]
            parts.extend([x.joined for x in self.exposedMelds])
        parts.extend(''.join(x.element) for x in self.bonusTiles)
        return ' '.join(parts)

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
            self.seed = seed or InternalParameters.seed or int(self.randomGenerator.random() * 10**12)
        self.shouldSave = shouldSave
        self.randomGenerator.seed(self.seed)
        self.rotated = 0
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
        self.divideAt = None
        self.lastDiscard = None # always uppercase
        self.visibleTiles = IntDict()
        self.discardedTiles = IntDict(self.visibleTiles) # tile names are always lowercase
        self.eastMJCount = 0
        self.dangerousTiles = set()
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
                    player.handBoard = None
            field.setWindowTitle('Kajongg')
            field.selectorBoard.tiles = []
            field.selectorBoard.allSelectorTiles = []
            self.removeWall()
            for item in field.centralScene.items():
                if isinstance(item, Tile):
                    field.centralScene.removeItem(item)
            field.game = None
            field.centralScene.focusRect.hide()
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
                assert self.belongsToGameServer()
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
        if self.finished():
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
            self.dangerousTiles = set()
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
        if self.winner and self.winner.wind == 'E':
            self.eastMJCount += 1

    def needSave(self):
        """do we need to save this game?"""
        if self.isScoringGame():
            return True
        elif self.belongsToRobotPlayer():
            return False
        else:
            return self.shouldSave      # as the server told us

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
                    "points,payments, balance,rotated) "
                    "VALUES(%d,%d,?,?,%d,'%s',%d,'%s','%s',%d,%d,%d,%d)" % \
                    (self.gameid, self.handctr, player.nameid,
                        scoretime, int(player == self.winner),
                        WINDS[self.roundsFinished % 4], player.wind, player.handTotal,
                        player.payment, player.balance, self.rotated),
                    list([player.handContent.string, manualrules]))

    def savePenalty(self, player, offense, amount):
        """save computed values to database, update score table and balance in status line"""
        if not self.needSave():
            return
        scoretime = datetime.datetime.now().replace(microsecond=0).isoformat()
        with Transaction():
            Query("INSERT INTO SCORE "
                "(game,hand,data,manualrules,player,scoretime,won,prevailing,wind,points,payments, balance,rotated) "
                "VALUES(%d,%d,?,?,%d,'%s',%d,'%s','%s',%d,%d,%d,%d)" % \
                (self.gameid, self.handctr, player.nameid,
                    scoretime, int(player == self.winner),
                    WINDS[self.roundsFinished % 4], player.wind, 0,
                    amount, player.balance, self.rotated),
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
        self.eastMJCount = 0
        if self.rotated == 4:
            if not self.finished():
                self.roundsFinished += 1
            self.rotated = 0
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
    def load(gameid, client=None, what=None):
        """load game by game id and return a new Game instance"""
        qGame = Query("select p0,p1,p2,p3,ruleset,seed from game where id = %d" % gameid)
        if not qGame.records:
            return None
        rulesetId = qGame.records[0][4] or 1
        ruleset = Ruleset(rulesetId, used=True)
        Players.load() # we want to make sure we have the current definitions
        names = Game.__getNames(qGame.records[0])
        if what is None:
            what = Game
        game = what(names, ruleset, gameid=gameid, client=client, seed=qGame.records[0][5])
        qLastHand = Query("select hand,rotated from score where game=%d and hand="
            "(select max(hand) from score where game=%d)" % (gameid, gameid))
        if qLastHand.records:
            (game.handctr, game.rotated) = qLastHand.records[0]

        qScores = Query("select player, wind, balance, won, prevailing from score "
            "where game=%d and hand=%d" % (gameid, game.handctr))
        for record in qScores.records:
            playerid = record[0]
            wind = str(record[1])
            player = game.players.byId(playerid)
            if not player:
                logMessage(
                'game %d inconsistent: player %d missing in game table' % \
                    (gameid, playerid), syslog.LOG_ERR)
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
            winner.wonCount  += 1
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

    def computeDangerous(self, playerChanged=None):
        """recompute gamewide dangerous tiles. Either for playerChanged or for all players"""
        self.dangerousTiles = set([])
        if playerChanged:
            playerChanged.findDangerousTiles()
        else:
            for player in self.players:
                player.findDangerousTiles()
        for player in self.players:
            self.dangerousTiles |= player.dangerousTiles
        if len(self.wall.living) <=5:
            allTiles = [x for x in defaultdict.keys(elements.occurrence) if x[0] not in 'fy']
            # see http://www.logilab.org/ticket/23986
            self.dangerousTiles |= set(x for x in allTiles if x not in self.visibleTiles)

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
        Game.prepareHand(self)
        selector = InternalParameters.field.selectorBoard
        selector.refill()
        selector.hasFocus = True

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
    # pylint too many arguments
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
    def load(gameid, client=None, what=None):
        """like Game.load, but returns a RemoteGame"""
        return Game.load(gameid, client, RemoteGame)

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
                        name = player.front.nameLabel
                        if not self.defaultNameBrush:
                            self.defaultNameBrush = name.brush()
                        if player == self.activePlayer:
                            brush = QBrush(QColor(Qt.blue))
                        else:
                            brush = self.defaultNameBrush
                        name.setBrush(brush)
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
            InternalParameters.field.setWindowTitle(m18n('Game <numid>%1</numid>', str(self.seed)) + ' - Kajongg')
            InternalParameters.field.discardBoard.setRandomPlaces(self.randomGenerator)
            for tableList in InternalParameters.field.tableLists:
                tableList.hide()
            InternalParameters.field.tableLists = []

    def hasDiscarded(self, player, tileName, score=None):
        """discards a tile from a player board"""
        if player != self.activePlayer:
            raise Exception('Player %s discards but %s is active' % (player, self.activePlayer))
        self.discardedTiles[tileName.lower()] += 1
        player.discarded.append(tileName)
        if self.myself and player != self.myself and not self.playOpen:
            # we are human and server tells us another player discarded a tile. In our
            # game instance, tiles in handBoards of other players are unknown
            concealedTileName = 'Xy'
            player.concealedTileNames[0] = tileName
        else:
            concealedTileName = tileName
        if InternalParameters.field:
            self.lastDiscard = player.handBoard.tilesByElement(concealedTileName)[-1]
            self.lastDiscard.element = tileName
            InternalParameters.field.discardBoard.discardTile(self.lastDiscard)
        else:
            self.lastDiscard = Tile(tileName)
        if not concealedTileName in player.concealedTileNames:
            raise Exception('I am %s. Player %s is told to show discard of tile %s but does not have it, he has %s' % \
                           (self.myself.name if self.myself else 'None',
                            player.name, concealedTileName, player.concealedTileNames))
        player.remove(tile=self.lastDiscard)
        if tileName in self.dangerousTiles:
            self.computeDangerous()
        if InternalParameters.field:
            for tile in player.handBoard.tiles:
                tile.focusable = False
        if score is not None:
            player.handContent = player.computeHandContent()
            if  str(player.handContent) != score:
                debugMessage('%s localScore:%s' % (player, player.handContent))
                debugMessage('%s serverScore:%s' % (player, score))
                logWarning('Game %d: client and server disagree about scoring, see syslog for details' % self.seed)
                self.close()

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
