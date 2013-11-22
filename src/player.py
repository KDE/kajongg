# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

import sys, weakref
from collections import defaultdict

from log import logException, logWarning, m18n, m18nc, m18nE
from common import WINDS, Internal, IntDict, Debug
from query import Transaction, Query
from tile import Tile, TileList, elements
from meld import Meld, meldsContent
from message import Message
from hand import Hand
from intelligence import AIDefault

class Players(list):
    """a list of players where the player can also be indexed by wind.
    The position in the list defines the place on screen. First is on the
    screen bottom, second on the right, third top, forth left"""

    allNames = {}
    allIds = {}
    humanNames = {}

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
        logException("no player has name %s - we have %s" % (playerName, [x.name for x in self]))

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
            if not name.startswith('Robot'):
                Players.humanNames[nameid] = name

    @staticmethod
    def createIfUnknown(name):
        """create player in database if not there yet"""
        if name not in Players.allNames.values():
            Players.load()  # maybe somebody else already added it
            if name not in Players.allNames.values():
                with Transaction():
                    Query("insert or ignore into player(name) values(?)",
                          list([name]))
                Players.load()
        assert name in Players.allNames.values(), '%s not in %s' % (name, Players.allNames.values())

    def translatePlayerNames(self, names):
        """for a list of names, translates those names which are english
        player names into the local language"""
        known = set(x.name for x in self)
        return list(self.byName(x).localName if x in known else x for x in names)

class Player(object):
    """all player related attributes without GUI stuff.
    concealedTileNames: used during the hand for all concealed tiles, ungrouped.
    concealedMelds: is empty during the hand, will be valid after end of hand,
    containing the concealed melds as the player presents them."""
    # pylint: disable=too-many-instance-attributes,too-many-public-methods

    def __init__(self, game):
        if game:
            self._game = weakref.ref(game)
        else:
            self._game = None
        self.__balance = 0
        self.__payment = 0
        self.wonCount = 0
        self.__name = ''
        self.wind = WINDS[0]
        self.intelligence = AIDefault(self)
        self.visibleTiles = IntDict(game.visibleTiles) if game else IntDict()
        self.clearHand()
        self.__lastSource = '1' # no source: blessing from heaven or earth
        self.handBoard = None

    @property
    def name(self):
        """write once, read many"""
        return self.__name

    @name.setter
    def name(self, value):
        """write once"""
        assert self.__name == ''
        assert value
        self.__name = value

    @property
    def game(self):
        """hide the fact that this is a weakref"""
        if self._game:
            return self._game()

    def clearHand(self):
        """clear player attributes concerning the current hand"""
        self._concealedTileNames = []
        self._exposedMelds = []
        self._concealedMelds = []
        self._bonusTiles = []
        self.discarded = []
        self.visibleTiles.clear()
        self.newHandContent = None
        self.originalCallingHand = None
        self.__lastTile = None
        self.lastSource = '1'
        self.lastMeld = Meld()
        self.__mayWin = True
        self.__payment = 0
        self.originalCall = False
        self.dangerousTiles = list()
        self.claimedNoChoice = False
        self.playedDangerous = False
        self.usedDangerousFrom = None
        self.isCalling = False
        self._hand = None

    @property
    def lastTile(self):
        """temp for debugging"""
        return self.__lastTile

    @lastTile.setter
    def lastTile(self, value):
        """temp for debugging"""
        assert isinstance(value, (Tile, type(None))), value
        self.__lastTile = value

    def invalidateHand(self):
        """some source for the computation of current hand changed"""
        self._hand = None

    @property
    def hand(self):
        """a readonly tuple"""
        if not self._hand:
            self._hand = self.computeHand()
        return self._hand

    @property
    def bonusTiles(self):
        """a readonly tuple"""
        return tuple(self._bonusTiles)

    @property
    def concealedTileNames(self):
        """a readonly tuple"""
        return tuple(self._concealedTileNames)

    @property
    def exposedMelds(self):
        """a readonly tuple"""
        return tuple(self._exposedMelds)

    @property
    def concealedMelds(self):
        """a readonly tuple"""
        return tuple(self._concealedMelds)

    @property
    def mayWin(self):
        """winning possible?"""
        return self.__mayWin

    @mayWin.setter
    def mayWin(self, value):
        """winning possible?"""
        if self.__mayWin != value:
            self.__mayWin = value
            self._hand = None

    @property
    def lastSource(self):
        """the source of the last tile the player got"""
        return self.__lastSource

    @lastSource.setter
    def lastSource(self, lastSource):
        """the source of the last tile the player got"""
        self.__lastSource = lastSource
        if lastSource == 'd' and not self.game.wall.living:
            self.__lastSource = 'Z'
        if lastSource == 'w' and not self.game.wall.living:
            self.__lastSource = 'z'

    @property
    def nameid(self):
        """the name id of this player"""
        return Players.allIds[self.name]

    @property
    def localName(self):
        """the localized name of this player"""
        return m18nc('kajongg, name of robot player, to be translated', self.name)

    @property
    def handTotal(self):
        """the hand total of this player"""
        if not self.game.winner:
            return 0
        else:
            return self.hand.total()

    @property
    def balance(self):
        """the balance of this player"""
        return self.__balance

    @balance.setter
    def balance(self, balance):
        """the balance of this player"""
        self.__balance = balance
        self.__payment = 0

    def getsPayment(self, payment):
        """make a payment to this player"""
        self.__balance += payment
        self.__payment += payment

    @property
    def payment(self):
        """the payments for the current hand"""
        return self.__payment

    @payment.setter
    def payment(self, payment):
        """the payments for the current hand"""
        assert payment == 0
        self.__payment = 0

    def __repr__(self):
        return u'{name:<10} {wind}'.format(name=self.name[:10], wind=self.wind)

    def __unicode__(self):
        return u'{name:<10} {wind}'.format(name=self.name[:10], wind=self.wind)

    def pickedTile(self, deadEnd, tileName=None):
        """got a tile from wall"""
        self.game.activePlayer = self
        tile = self.game.wall.deal([tileName], deadEnd=deadEnd)[0]
        if hasattr(tile, 'tile'):
            self.lastTile = tile.tile
        else:
            self.lastTile = tile
        self.addConcealedTiles([tile])
        if deadEnd:
            self.lastSource = 'e'
        else:
            self.game.lastDiscard = None
            self.lastSource = 'w'
        return self.lastTile

    def removeTile(self, tile):
        """remove from my tiles"""
        if tile.isBonus:
            self._bonusTiles.remove(tile)
        else:
            try:
                self._concealedTileNames.remove(tile)
            except ValueError:
                raise Exception('removeTile(%s): tile not in concealed %s' % \
                    (tile, ''.join(self._concealedTileNames)))
        self._hand = None

    def addConcealedTiles(self, tiles, animated=False): # pylint: disable=unused-argument
        """add to my tiles"""
        assert len(tiles)
        for tile in tiles:
            assert isinstance(tile, Tile), 'tile:%s' % tile
            if tile.isBonus:
                self._bonusTiles.append(tile)
            else:
                assert tile.istitle(), '%s data=%s' % (tile, tiles)
                self._concealedTileNames.append(tile)
        self._hand = None

    def syncHandBoard(self, adding=None):
        """virtual: synchronize display"""
        pass

    def colorizeName(self):
        """virtual: colorize Name on wall"""
        pass

    def getsFocus(self, dummyResults=None):
        """virtual: player gets focus on his hand"""
        pass

    def mjString(self, asWinner=False):
        """compile hand info into a string as needed by the scoring engine"""
        game = self.game
        assert game
        winds = self.wind.lower() + 'eswn'[game.roundsFinished % 4]
        wonChar = 'm'
        lastSource = ''
        declaration = ''
        if asWinner or self == game.winner:
            wonChar = 'M'
            lastSource = self.lastSource
            if self.originalCall:
                declaration = 'a'
        if not self.mayWin:
            wonChar = 'x'
        return ''.join([wonChar, winds, lastSource, declaration])

    def makeTileKnown(self, tileName):
        """used when somebody else discards a tile"""
        assert not self._concealedTileNames[0].isKnown
        self._concealedTileNames[0] = tileName
        self._hand = None

    def computeHand(self, withTile=None, robbedTile=None, dummy=None, asWinner=False):
        """returns Hand for this player"""
        assert not (self._concealedMelds and self._concealedTileNames)
        assert isinstance(self.lastTile, (Tile, type(None)))
        assert isinstance(withTile, (Tile, type(None)))
        melds = ['R' + ''.join(str(x) for x in self._concealedTileNames)]
        if withTile:
            melds[0] += withTile
        melds.extend(str(x) for x in self._exposedMelds)
        melds.extend(str(x) for x in self._concealedMelds)
        melds.extend(str(x) for x in self._bonusTiles)
        mjString = self.mjString(asWinner)
        melds.append(mjString)
        if mjString.startswith('M') and (withTile or self.lastTile):
            melds.append('L%s%s' % (withTile or self.lastTile, self.lastMeld if self.lastMeld else ''))
        return Hand.cached(self, ' '.join(melds), robbedTile=robbedTile)

    def scoringString(self):
        """helper for HandBoard.__str__"""
        if self._concealedMelds:
            parts = [str(x) for x in self._concealedMelds + self._exposedMelds]
        else:
            parts = [''.join(self._concealedTileNames)]
            parts.extend([str(x) for x in self._exposedMelds])
        parts.extend(str(x) for x in self._bonusTiles)
        return ' '.join(parts)

    def sortRulesByX(self, rules): # pylint: disable=no-self-use
        """if this game has a GUI, sort rules by GUI order"""
        return rules

    def others(self):
        """a list of the other 3 players"""
        return (x for x in self.game.players if x != self)

    def tileAvailable(self, tileName, hand):
        """a count of how often tileName might still appear in the game
        supposing we have hand"""
        visible = self.game.discardedTiles.count([tileName.lower()])
        for player in self.others():
            visible += player.visibleTiles.count([tileName.capitalize()])
            visible += player.visibleTiles.count([tileName.lower()])
        for pair in hand.tileNames:
            if pair.lower() == tileName.lower():
                visible += 1
        return 4 - visible

    def violatesOriginalCall(self, tileName=None):
        """called if discarding tileName (default=just discarded tile)
        violates the Original Call"""
        if not self.originalCall or not self.mayWin:
            return False
        if tileName is None:
            if len(self.discarded) < 2:
                return False
            tileName = self.discarded[-1]
        if self.lastTile.lower() != tileName.lower():
            if Debug.originalCall:
                self.game.debug('%s would violate OC with %s, lastTile=%s' % (self, tileName, self.lastTile))
            return True
        return False

class PlayingPlayer(Player):
    """a player in a computer game as opposed to a ScoringPlayer"""
    # pylint: disable=too-many-public-methods
    # too many public methods
    def __init__(self, game):
        self.sayable = {}               # recompute for each move, use as cache
        Player.__init__(self, game)

    def popupMsg(self, msg):
        """virtual: show popup on display"""
        pass

    def hidePopup(self):
        """virtual: hide popup on display"""
        pass

    def speak(self, txt):
        """only a visible playing player can speak"""
        pass

    def declaredMahJongg(self, concealed, withDiscard, lastTile, lastMeld):
        """player declared mah jongg. Determine last meld, show concealed tiles grouped to melds"""
        self.game.winner = self
        if withDiscard:
            assert isinstance(withDiscard, Tile), withDiscard
            self.lastTile = withDiscard
            self.lastMeld = lastMeld
            assert withDiscard == self.game.lastDiscard, 'withDiscard: %s lastDiscard: %s' % (
                withDiscard, self.game.lastDiscard)
            if Internal.scene:
                discardTile = Internal.scene.discardBoard.lastDiscarded
                if discardTile.tile != withDiscard:
                    self.game.debug('%s != %s' % (discardTile.tile, withDiscard))
                    assert False
            else:
                discardTile = withDiscard
            self.addConcealedTiles([discardTile])
            melds = [Meld(x) for x in concealed.split()]
            if self.lastSource != 'k':   # robbed the kong
                self.lastSource = 'd'
            # the last claimed meld is exposed
            assert lastMeld in melds, '%s: concealed=%s melds=%s lastMeld=%s lastTile=%s withDiscard=%s' % (
                    self._concealedTileNames, concealed,
                    meldsContent(melds), lastMeld, lastTile, withDiscard)
            melds.remove(lastMeld)
            self.lastTile = self.lastTile.lower()
            lastMeld = lastMeld.toLower()
            self._exposedMelds.append(lastMeld)
            for tileName in lastMeld:
                self.visibleTiles[tileName] += 1
        else:
            melds = [Meld(x) for x in concealed.split()]
            self.lastTile = lastTile
            self.lastMeld = lastMeld
        self._concealedMelds = melds
        self._concealedTileNames = []
        self._hand = None
        self.syncHandBoard()

    def __possibleChows(self):
        """returns a unique list of lists with possible claimable chow combinations"""
        if self.game.lastDiscard is None:
            return []
        exposedChows = [x for x in self._exposedMelds if x.isChow]
        if len(exposedChows) >= self.game.ruleset.maxChows:
            return []
        tile = self.game.lastDiscard
        within = TileList(self.concealedTileNames[:])
        within.append(tile)
        return within.hasChows(tile)

    def __possibleKongs(self):
        """returns a unique list of lists with possible kong combinations"""
        kongs = []
        if self == self.game.activePlayer:
            # declaring a kong
            for tileName in set([x for x in self._concealedTileNames if not x.isBonus]):
                if self._concealedTileNames.count(tileName) == 4:
                    kongs.append([tileName] * 4)
                elif self._concealedTileNames.count(tileName) == 1 and \
                        tileName.lower() * 3 in list(str(x) for x in self._exposedMelds):
                    kongs.append([tileName.lower()] * 3 + [tileName])
        if self.game.lastDiscard:
            # claiming a kong
            discardTile = self.game.lastDiscard.upper()
            if self._concealedTileNames.count(discardTile) == 3:
                kongs.append([discardTile] * 4)
        for kong in kongs:
            assert isinstance(kong[0], Tile)
        return kongs

    def __maySayChow(self):
        """returns answer arguments for the server if calling chow is possible.
        returns the meld to be completed"""
        if self == self.game.nextPlayer():
            return self.__possibleChows()

    def __maySayPung(self):
        """returns answer arguments for the server if calling pung is possible.
        returns the meld to be completed"""
        lastDiscard = self.game.lastDiscard
        if self.game.lastDiscard:
            assert lastDiscard.group.isupper(), lastDiscard
            if self.concealedTileNames.count(lastDiscard) >= 2:
                return [lastDiscard] * 3

    def __maySayKong(self):
        """returns answer arguments for the server if calling or declaring kong is possible.
        returns the meld to be completed or to be declared"""
        return self.__possibleKongs()

    def __maySayMahjongg(self, move):
        """returns answer arguments for the server if calling or declaring Mah Jongg is possible"""
        game = self.game
        robbableTile = withDiscard = None
        if move.message == Message.DeclaredKong:
            withDiscard = move.meld[0].upper()
            if move.player != self:
                robbableTile = move.exposedMeld[1] # we want it capitalized for a hidden Kong
        elif move.message == Message.AskForClaims:
            withDiscard = game.lastDiscard
        hand = self.computeHand(withTile=withDiscard, robbedTile=robbableTile, asWinner=True)
        if hand.won:
            if Debug.robbingKong:
                if move.message == Message.DeclaredKong:
                    game.debug('%s may rob the kong from %s/%s' % \
                       (self, move.player, move.exposedMeld))
            if Debug.mahJongg:
                game.debug('%s may say MJ:%s, active=%s' % (
                    self, list(x for x in game.players), game.activePlayer))
            return (meldsContent(hand.hiddenMelds), withDiscard, hand.lastMeld)

    def __maySayOriginalCall(self):
        """returns True if Original Call is possible"""
        for tileName in set(self.concealedTileNames):
            newHand = self.hand - tileName
            if newHand.callingHands():
                if Debug.originalCall:
                    self.game.debug('%s may say Original Call by discarding %s from %s' % (self, tileName, self.hand))
                return True

    def computeSayable(self, move, answers):
        """find out what the player can legally say with this hand"""
        self.sayable = {}
        for message in Message.defined.values():
            self.sayable[message] = True
        if Message.Pung in answers:
            self.sayable[Message.Pung] = self.__maySayPung()
        if Message.Chow in answers:
            self.sayable[Message.Chow] = self.__maySayChow()
        if Message.Kong in answers:
            self.sayable[Message.Kong] = self.__maySayKong()
        if Message.MahJongg in answers:
            self.sayable[Message.MahJongg] = self.__maySayMahjongg(move)
        if Message.OriginalCall in answers:
            self.sayable[Message.OriginalCall] = self.__maySayOriginalCall()

    def maybeDangerous(self, msg):
        """could answering with msg lead to dangerous game?
        If so return a list of resulting melds
        where a meld is represented by a list of 2char strings"""
        result = []
        if msg in (Message.Chow, Message.Pung, Message.Kong):
            possibleMelds = self.sayable[msg]
            if isinstance(possibleMelds[0], basestring):
                possibleMelds = [possibleMelds]
            result = [x for x in possibleMelds if self.mustPlayDangerous(x)]
        return result

    def hasConcealedTiles(self, tiles, within=None):
        """do I have those concealed tiles?"""
        if within is None:
            within = self._concealedTileNames
        within = within[:]
        for tile in tiles:
            assert isinstance(tile, Tile), tile
            if tile not in within:
                return False
            within.remove(tile)
        return True

    def showConcealedTiles(self, tileNames, show=True):
        """show or hide tileNames"""
        if not self.game.playOpen and self != self.game.myself:
            if not isinstance(tileNames, (list, tuple)):
                tileNames = [tileNames]
            assert len(tileNames) <= len(self._concealedTileNames), \
                '%s: showConcealedTiles %s, we have only %s' % (self, tileNames, self._concealedTileNames)
            for tileName in tileNames:
                src, dst = (Tile.unknown, tileName) if show else (tileName, Tile.unknown)
                assert src != dst, (self, src, dst, tileNames, self._concealedTileNames)
                if not src in self._concealedTileNames:
                    logException( '%s: showConcealedTiles(%s): %s not in %s.' % \
                            (self, tileNames, src, self._concealedTileNames))
                idx = self._concealedTileNames.index(src)
                self._concealedTileNames[idx] = dst
            self._hand = None
            self.syncHandBoard()

    def showConcealedMelds(self, concealedMelds, ignoreDiscard=None):
        """the server tells how the winner shows and melds his
        concealed tiles. In case of error, return message and arguments"""
        for part in concealedMelds.split():
            meld = Meld(part)
            for pair in meld:
                if pair == ignoreDiscard:
                    ignoreDiscard = None
                else:
                    if not pair in self._concealedTileNames:
                        msg = m18nE('%1 claiming MahJongg: She does not really have tile %2')
                        return msg, self.name, pair
                    self._concealedTileNames.remove(pair)
            if not meld.isExposed and not meld.isKong:
                self._concealedMelds.append(meld)
            else:
                self._exposedMelds.append(meld)
        if self._concealedTileNames:
            msg = m18nE('%1 claiming MahJongg: She did not pass all concealed tiles to the server')
            return msg, self.name
        self._hand = None

    def hasExposedPungOf(self, tileName):
        """do I have an exposed Pung of tileName?"""
        for meld in self._exposedMelds:
            if meld == [tileName.lower()] * 3:
                return True
        return False

    def robTile(self, tile):
        """used for robbing the kong"""
        assert isinstance(tile, Tile)
        assert tile.istitle()
        tile = tile.lower()
        for meld in self._exposedMelds:
            if tile in meld:
                meld = meld.without(tile)
                self.visibleTiles[tile] -= 1
                break
        else:
            raise Exception('robTile: no meld found with %s' % tile)
        self.game.lastDiscard = tile.upper()
        self._hand = None

    def scoreMatchesServer(self, score):
        """do we compute the same score as the server does?"""
        if score is None:
            return True
        if any(not x.isKnown for x in self._concealedTileNames):
            return True
        if str(self.hand) == score:
            return True
        self.game.debug('%s localScore:%s' % (self, self.hand))
        self.game.debug('%s serverScore:%s' % (self, score))
        logWarning('Game %s: client and server disagree about scoring, see logfile for details' % self.game.seed)
        return False

    def mustPlayDangerous(self, exposing=None):
        """returns True if the player has no choice, otherwise False.
        Exposing may be a meld which will be exposed before we might
        play dangerous"""
        if self == self.game.activePlayer and exposing and len(exposing) == 4:
            # declaring a kong is never dangerous because we get
            # an unknown replacement
            return False
        afterExposed = list(x.lower() for x in self._concealedTileNames)
        if exposing:
            exposing = exposing[:]
            if self.game.lastDiscard:
                # if this is about claiming a discarded tile, ignore it
                # the player who discarded it is responsible
                exposing.remove(self.game.lastDiscard)
            for tile in exposing:
                if tile.lower() in afterExposed:
                    # the "if" is needed for claimed pung
                    afterExposed.remove(tile.lower())
        return all(self.game.dangerousFor(self, x) for x in afterExposed)

    def exposeMeld(self, meldTiles, calledTile=None):
        """exposes a meld with meldTiles: removes them from concealedTileNames,
        adds the meld to exposedMelds and returns it
        calledTile: we got the last tile for the meld from discarded, otherwise
        from the wall"""
        game = self.game
        game.activePlayer = self
        allMeldTiles = meldTiles[:]
        if calledTile:
            assert isinstance(calledTile, Tile), calledTile
            allMeldTiles.append(calledTile)
        if len(allMeldTiles) == 4 and allMeldTiles[0].islower():
            tile0 = allMeldTiles[0].lower()
            # we are adding a 4th tile to an exposed pung
            self._exposedMelds = [meld for meld in self._exposedMelds if meld != [tile0] * 3]
            meld = Meld(tile0 * 4)
            self._concealedTileNames.remove(allMeldTiles[3])
            self.visibleTiles[tile0] += 1
        else:
            allMeldTiles = sorted(allMeldTiles) # needed for Chow
            meld = Meld(allMeldTiles)
            for meldTile in meldTiles:
                self._concealedTileNames.remove(meldTile)
            for meldTile in allMeldTiles:
                self.visibleTiles[meldTile.lower()] += 1
            meld = meld.expose(bool(calledTile))
        self._exposedMelds.append(meld)
        self._hand = None
        game.computeDangerous(self)
        return meld

    def findDangerousTiles(self):
        """update the list of dangerous tile"""
        pName = self.localName
        dangerous = list()
        expMeldCount = len(self._exposedMelds)
        if expMeldCount >= 3:
            if all(x in elements.greenHandTiles for x in self.visibleTiles):
                dangerous.append((elements.greenHandTiles,
                     m18n('Player %1 has 3 or 4 exposed melds, all are green', pName)))
            group = defaultdict.keys(self.visibleTiles)[0].group
            # see http://www.logilab.org/ticket/23986
            assert group.islower(), self.visibleTiles
            if group in 'sbc':
                if all(x.group == group for x in self.visibleTiles):
                    suitTiles = set([group+x for x in '123456789'])
                    if self.visibleTiles.count(suitTiles) >= 9:
                        dangerous.append((suitTiles, m18n('Player %1 may try a True Color Game', pName)))
                elif all(x.value in '19' for x in self.visibleTiles):
                    dangerous.append((elements.terminals,
                        m18n('Player %1 may try an All Terminals Game', pName)))
        if expMeldCount >= 2:
            windMelds = sum(self.visibleTiles[x] >=3 for x in elements.winds)
            dragonMelds = sum(self.visibleTiles[x] >=3 for x in elements.dragons)
            windsDangerous = dragonsDangerous = False
            if windMelds + dragonMelds == expMeldCount and expMeldCount >= 3:
                windsDangerous = dragonsDangerous = True
            windsDangerous = windsDangerous or windMelds >= 3
            dragonsDangerous = dragonsDangerous or dragonMelds >= 2
            if windsDangerous:
                dangerous.append((set(x for x in elements.winds if x not in self.visibleTiles),
                     m18n('Player %1 exposed many winds', pName)))
            if dragonsDangerous:
                dangerous.append((set(x for x in elements.dragons if x not in self.visibleTiles),
                     m18n('Player %1 exposed many dragons', pName)))
        self.dangerousTiles = dangerous
        if dangerous and Debug.dangerousGame:
            self.game.debug('dangerous:%s' % dangerous)
