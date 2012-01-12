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

import sys
from collections import defaultdict

from util import logException, logWarning, logDebug, m18n
from common import WINDS, InternalParameters, elements, IntDict, Debug
from query import Transaction, Query
from tile import Tile, offsetTiles
from meld import Meld, CONCEALED, PUNG
from scoringengine import HandContent

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

    @staticmethod
    def localPlayers():
        """return a list of locally defined players like we need them
        for a scoring game"""
        return list(x[0] for x in Query('select name, id from player where'
                ' not name like "ROBOT %" and not exists(select 1 from'
                ' server where server.lastname=player.name)').records)

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
        self.handBoard = None

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
        self.dangerousTiles = set() # all elements should be lowercase
        self.explainDangerous = list() # a list of explaining messages
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
                spValue = InternalParameters.field.scoringDialog.spValues[self.idx]
                return spValue.value()
            if not self.game.winner:
                return 0
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
        return '{:<10} {}'.format(self.name[:10], self.wind)

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

    def showConcealedTiles(self, tileNames, show=True):
        """show or hide tileNames"""
        if not self.game.playOpen and self != self.game.myself:
            if not isinstance(tileNames, list):
                tileNames = [tileNames]
            assert len(tileNames) <= len(self.concealedTileNames), \
                '%s: showConcealedTiles %s, we have only %s' % (self, tileNames, self.concealedTileNames)
            for tileName in tileNames:
                src, dst = ('Xy', tileName) if show else (tileName, 'Xy')
                assert src != dst, (self, src, dst, tileNames, self.concealedTileNames)
                if not src in self.concealedTileNames:
                    logException( '%s: showConcealedTiles(%s): %s not in %s.' % \
                            (self, tileNames, src, self.concealedTileNames))
                idx = self.concealedTileNames.index(src)
                self.concealedTileNames[idx] = dst
            self.syncHandBoard()

    def hasExposedPungOf(self, tileName):
        """do I have an exposed Pung of tileName?"""
        for meld in self.exposedMelds:
            if meld.pairs == [tileName.lower()] * 3:
                return True
        return False

    def robTile(self, tileName):
        """used for robbing the kong"""
        assert tileName.istitle()
        tileName = tileName.lower()
        for meld in self.exposedMelds:
            if tileName in meld.pairs:
                meld.pairs.remove(tileName)
                meld.meldtype = PUNG
                self.visibleTiles[tileName] -= 1
                break
        else:
            raise Exception('robTile: no meld found with %s' % tileName)
        if InternalParameters.field:
            hbTiles = self.handBoard.tiles
            self.game.lastDiscard = [x for x in hbTiles if x.element == tileName][-1]
            # remove from board of robbed player, otherwise syncHandBoard would
            # not fix display for the robbed player
            self.game.lastDiscard.setBoard(None)
            self.syncHandBoard()
        else:
            self.game.lastDiscard = Tile(tileName)
        self.game.lastDiscard.element = self.game.lastDiscard.upper()

    def scoreMatchesServer(self, score):
        """do we compute the same score as the server does?"""
        if score is None:
            return True
        if 'Xy' in self.concealedTileNames:
            return True
        self.handContent = self.computeHandContent()
        if str(self.handContent) == score:
            return True
        logDebug('%s localScore:%s' % (self, self.handContent))
        logDebug('%s serverScore:%s' % (self, score))
        logWarning('Game %s: client and server disagree about scoring, see logfile for details' % self.game.seed)
        return False

    def mustPlayDangerous(self, exposing=None):
        """returns True if the player has no choice. Exposing may be a meld
        which will be exposed before we might play dangerous"""
        afterExposed = list(x.lower() for x in self.concealedTileNames)
        if exposing:
            exposing = exposing[:]
            exposing.remove(self.game.lastDiscard.element)
            for tileName in exposing:
                afterExposed.remove(tileName.lower())
        return set(afterExposed) <= self.game.dangerousTiles

    def exposeMeld(self, meldTiles, called=None):
        """exposes a meld with meldTiles: removes them from concealedTileNames,
        adds the meld to exposedMelds and returns it
        called: we got the last tile for the meld from discarded, otherwise
        from the wall"""
        game = self.game
        game.activePlayer = self
        allMeldTiles = meldTiles[:]
        if called:
            allMeldTiles.append(called.element if isinstance(called, Tile) else called)
        if len(allMeldTiles) == 4 and allMeldTiles[0].islower():
            tile0 = allMeldTiles[0].lower()
            # we are adding a 4th tile to an exposed pung
            self.exposedMelds = [meld for meld in self.exposedMelds if meld.pairs != [tile0] * 3]
            meld = Meld(tile0 * 4)
            self.concealedTileNames.remove(allMeldTiles[3])
            self.visibleTiles[tile0] += 1
        else:
            allMeldTiles = sorted(allMeldTiles) # needed for Chow
            meld = Meld(allMeldTiles)
            for meldTile in meldTiles:
                self.concealedTileNames.remove(meldTile)
            for meldTile in allMeldTiles:
                self.visibleTiles[meldTile.lower()] += 1
            meld.expose(bool(called))
        self.exposedMelds.append(meld)
        game.computeDangerous(self)
        adding = [called] if called else None
        self.syncHandBoard(adding=adding)
        return meld

    def findDangerousTiles(self):
        """update the list of dangerous tile"""
        dangerousTiles = set()
        self.explainDangerous = list()
        expMeldCount = len(self.exposedMelds)
        if expMeldCount >= 3:
            if all(x in elements.greenHandTiles for x in self.visibleTiles):
                dangerousTiles |= elements.greenHandTiles
                self.explainDangerous.append(m18n('Player %s has 3 or 4 exposed melds, all are green' % self.name))
            color = defaultdict.keys(self.visibleTiles)[0][0]
            # see http://www.logilab.org/ticket/23986
            assert color.islower(), self.visibleTiles
            if color in 'sbc':
                if all(x[0] == color for x in self.visibleTiles):
                    suitTiles = set([color+x for x in '123456789'])
                    if self.visibleTiles.count(suitTiles) >= 9:
                        dangerousTiles |= suitTiles
                        self.explainDangerous.append(m18n('Player %s may try a True Golor Game' % self.name))
                elif all(x[1] in '19' for x in self.visibleTiles):
                    dangerousTiles |= elements.terminals
                    self.explainDangerous.append(m18n('Player %s may try an All Terminals Game' % self.name))
        if expMeldCount >= 2:
            windMelds = sum(self.visibleTiles[x] >=3 for x in elements.winds)
            dragonMelds = sum(self.visibleTiles[x] >=3 for x in elements.dragons)
            windsDangerous = dragonsDangerous = False
            if windMelds + dragonMelds == expMeldCount and expMeldCount >= 3:
                windsDangerous = dragonsDangerous = True
            windsDangerous = windsDangerous or windMelds == 3
            dragonsDangerous = dragonsDangerous or dragonMelds == 2
            if windsDangerous:
                dangerousTiles |= set(x for x in elements.winds if x not in self.visibleTiles)
            if dragonsDangerous:
                dangerousTiles |= set(x for x in elements.dragons if x not in self.visibleTiles)
            if windsDangerous or dragonsDangerous:
                self.explainDangerous.append(m18n('Player %s exposed too many winds or dragons' % self.name))
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

    def colorizeName(self):
        """virtual: colorize Name on wall"""
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

    def possibleChows(self):
        """returns a unique list of lists with possible chow combinations"""
        discard = self.game.lastDiscard.element
        try:
            value = int(discard[1])
        except ValueError:
            return []
        chows = []
        for offsets in [(1, 2), (-2, -1), (-1, 1)]:
            if value + offsets[0] >= 1 and value + offsets[1] <= 9:
                chow = offsetTiles(discard, offsets)
                if self.hasConcealedTiles(chow):
                    chow.append(discard)
                    if chow not in chows:
                        chows.append(sorted(chow))
        return chows

    def possibleKongs(self, mayPlayDangerous=False):
        """returns a unique list of lists with possible kong combinations"""
        kongs = []
        if self == self.game.activePlayer:
            for tileName in set([x for x in self.concealedTileNames if x[0] not in 'fy']):
                if self.concealedTileNames.count(tileName) == 4:
                    kongs.append([tileName] * 4)
                elif self.concealedTileNames.count(tileName) == 1 and \
                        tileName.lower() * 3 in list(x.joined for x in self.exposedMelds):
                    kongs.append([tileName.lower()] * 3 + [tileName])
        if self.game.lastDiscard:
            discard = self.game.lastDiscard.element
            if self.concealedTileNames.count(discard.capitalize()) == 3:
                must = self.mustPlayDangerous([discard] * 4)
                if mayPlayDangerous or not must:
                    kongs.append([discard.capitalize()] * 4)
                elif Debug.dangerousGame:
                    logDebug('%s: claiming Kong of %s would result in dangerous game' % (self, discard))
        return kongs

    def declaredMahJongg(self, concealed, withDiscard, lastTile, lastMeld):
        """player declared mah jongg. Determine last meld, show concealed tiles grouped to melds"""
        assert not isinstance(lastTile, Tile)
        lastMeld = Meld(lastMeld) # do not change the original!
        self.game.winner = self
        melds = [Meld(x) for x in concealed.split()]
        if withDiscard:
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
