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

import weakref
from collections import defaultdict

from log import logException, logWarning, m18n, m18nc, m18nE
from common import IntDict, Debug, unicode
from common import StrMixin
from wind import East
from query import Query
from tile import Tile, TileList, elements
from tilesource import TileSource
from meld import Meld, MeldList
from permutations import Permutations
from message import Message
from hand import Hand
from intelligence import AIDefault


class Players(list, StrMixin):

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
        for player in self:
            if player.wind == index:
                return player
        return list.__getitem__(self, index)

    def __unicode__(self):
        return u', '.join(list(u'%s: %s' % (x.name, x.wind) for x in self))

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
        logException(
            "no player has name %s - we have %s" %
            (playerName, [x.name for x in self]))

    @staticmethod
    def load():
        """load all defined players into self.allIds and self.allNames"""
        Players.allIds = {}
        Players.allNames = {}
        for nameid, name in Query("select id,name from player").records:
            Players.allIds[name] = nameid
            Players.allNames[nameid] = name
            if not name.startswith(u'Robot'):
                Players.humanNames[nameid] = name

    @staticmethod
    def createIfUnknown(name):
        """create player in database if not there yet"""
        if name not in Players.allNames.values():
            Players.load()  # maybe somebody else already added it
            if name not in Players.allNames.values():
                Query("insert or ignore into player(name) values(?)", (name,))
                Players.load()
        assert name in Players.allNames.values(), '%s not in %s' % (
            name, Players.allNames.values())

    def translatePlayerNames(self, names):
        """for a list of names, translates those names which are english
        player names into the local language"""
        known = set(x.name for x in self)
        return list(self.byName(x).localName if x in known else x for x in names)


class Player(StrMixin):

    """
    all player related attributes without GUI stuff.
    concealedTiles: used during the hand for all concealed tiles, ungrouped.
    concealedMelds: is empty during the hand, will be valid after end of hand,
    containing the concealed melds as the player presents them.

    @todo: Now that Player() always calls createIfUnknown, test defining new
    players and adding new players to server
    """
    # pylint: disable=too-many-instance-attributes,too-many-public-methods

    def __init__(self, game, name):
        """
        Initialize a player for a give game.

        @type game: L{Game} or None.
        @param game: The game this player is part of. May be None.
        """
        if game:
            self._game = weakref.ref(game)
        else:
            self._game = None
        self.__balance = 0
        self.__payment = 0
        self.wonCount = 0
        self.__name = ''
        Players.createIfUnknown(name)
        self.name = name
        self.wind = East
        self.intelligence = AIDefault(self)
        self.visibleTiles = IntDict(game.visibleTiles) if game else IntDict()
        self.handCache = {}
        self.cacheHits = 0
        self.cacheMisses = 0
        self.__lastSource = TileSource.East14th
        self.clearHand()
        self.handBoard = None

    def __lt__(self, other):
        """Used for sorting"""
        if not other:
            return False
        return self.name < other.name

    def clearCache(self):
        """clears the cache with Hands"""
        if Debug.hand and len(self.handCache):
            self.game.debug(
                '%s: cache hits:%d misses:%d' %
                (self, self.cacheHits, self.cacheMisses))
        self.handCache.clear()
        Permutations.cache.clear()
        self.cacheHits = 0
        self.cacheMisses = 0

    @property
    def name(self):
        """
        The name of the player, can be changed only once.

        @type: C{unicode}
        """
        return self.__name

    @name.setter
    def name(self, value):
        """write once"""
        assert self.__name == ''
        assert value
        assert isinstance(value, unicode), 'Player.name must be unicode but not {}'.format(type(value))
        self.__name = value

    @property
    def game(self):
        """hide the fact that this is a weakref"""
        if self._game:
            return self._game()

    def clearHand(self):
        """clear player attributes concerning the current hand"""
        self._concealedTiles = []
        self._exposedMelds = []
        self._concealedMelds = []
        self._bonusTiles = []
        self.discarded = []
        self.visibleTiles.clear()
        self.newHandContent = None
        self.originalCallingHand = None
        self.__lastTile = None
        self.lastSource = TileSource.East14th
        self.lastMeld = Meld()
        self.__mayWin = True
        self.__payment = 0
        self.originalCall = False
        self.dangerousTiles = list()
        self.claimedNoChoice = False
        self.playedDangerous = False
        self.usedDangerousFrom = None
        self.isCalling = False
        self.clearCache()
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
# TODO: str or what?
        if not self._hand:
            self._hand = self.__computeHand()
        return self._hand

    @property
    def bonusTiles(self):
        """a readonly tuple"""
        return tuple(self._bonusTiles)

    @property
    def concealedTiles(self):
        """a readonly tuple"""
        return tuple(self._concealedTiles)

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
    def lastSource(self, value):
        """the source of the last tile the player got"""
        if value is TileSource.LivingWallDiscard and not self.game.wall.living:
            value = TileSource.LivingWallEndDiscard
        if value is TileSource.LivingWall and not self.game.wall.living:
            value = TileSource.LivingWallEnd
        if self.__lastSource != value:
            self.__lastSource = value
            self._hand = None

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
        """the hand total of this player for the final scoring"""
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
            self.lastSource = TileSource.DeadWall
        else:
            self.game.lastDiscard = None
            self.lastSource = TileSource.LivingWall
        return self.lastTile

    def removeTile(self, tile):
        """remove from my tiles"""
        if tile.isBonus:
            self._bonusTiles.remove(tile)
        else:
            try:
                self._concealedTiles.remove(tile)
            except ValueError:
                raise Exception('removeTile(%s): tile not in concealed %s' %
                                (tile, ''.join(self._concealedTiles)))
        if tile is self.lastTile:
            self.lastTile = None
        self._hand = None

    def addConcealedTiles(self, tiles, animated=False):  # pylint: disable=unused-argument
        """add to my tiles"""
        assert len(tiles)
        for tile in tiles:
            if tile.isBonus:
                self._bonusTiles.append(tile)
            else:
                assert tile.isConcealed, '%s data=%s' % (tile, tiles)
                self._concealedTiles.append(tile)
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

    def mjString(self):
        """compile hand info into a string as needed by the scoring engine"""
        announcements = 'a' if self.originalCall else ''
        return ''.join(['m', self.lastSource.char, ''.join(announcements)])

    def makeTileKnown(self, tileName):
        """used when somebody else discards a tile"""
        assert not self._concealedTiles[0].isKnown
        self._concealedTiles[0] = tileName
        self._hand = None

    def __computeHand(self):
        """returns Hand for this player"""
        assert not (self._concealedMelds and self._concealedTiles)
        melds = list()
        melds.extend(str(x) for x in self._exposedMelds)
        melds.extend(str(x) for x in self._concealedMelds)
        if self._concealedTiles:
            melds.append('R' + ''.join(str(x) for x in sorted(self._concealedTiles)))
        melds.extend(str(x) for x in self._bonusTiles)
        melds.append(self.mjString())
        if self.lastTile:
            melds.append(
                'L%s%s' %
                (self.lastTile, self.lastMeld if self.lastMeld else ''))
        return Hand(self, ' '.join(melds))

    def _computeHandWithDiscard(self, discard):
        """what if"""
        lastSource = self.lastSource # TODO: recompute
        save = (self.lastTile, self.lastSource)
        try:
            self.lastSource = lastSource
            if discard:
                self.lastTile = discard
                self._concealedTiles.append(discard)
            return self.__computeHand()
        finally:
            self.lastTile, self.lastSource = save
            if discard:
                self._concealedTiles = self._concealedTiles[:-1]

    def scoringString(self):
        """helper for HandBoard.__str__"""
        if self._concealedMelds:
            parts = [str(x) for x in self._concealedMelds + self._exposedMelds]
        else:
            parts = [''.join(self._concealedTiles)]
            parts.extend([str(x) for x in self._exposedMelds])
        parts.extend(str(x) for x in self._bonusTiles)
        return ' '.join(parts)

    def sortRulesByX(self, rules):  # pylint: disable=no-self-use
        """if this game has a GUI, sort rules by GUI order"""
        return rules

    def others(self):
        """a list of the other 3 players"""
        return (x for x in self.game.players if x != self)

    def tileAvailable(self, tileName, hand):
        """a count of how often tileName might still appear in the game
        supposing we have hand"""
        lowerTile = tileName.exposed
        upperTile = tileName.concealed
        visible = self.game.discardedTiles.count([lowerTile])
        if visible:
            if hand.lenOffset == 0 and self.game.lastDiscard and lowerTile is self.game.lastDiscard.exposed:
                # the last discarded one is available to us since we can claim
                # it
                visible -= 1
        visible += sum(x.visibleTiles.count([lowerTile, upperTile])
                       for x in self.others())
        visible += sum(x.exposed == lowerTile for x in hand.tiles)
        return 4 - visible

    def violatesOriginalCall(self, discard=None):
        """called if discarding discard violates the Original Call"""
        if not self.originalCall or not self.mayWin:
            return False
        if self.lastTile.exposed != discard.exposed:
            if Debug.originalCall:
                self.game.debug(
                    '%s would violate OC with %s, lastTile=%s' %
                    (self, discard, self.lastTile))
            return True
        return False


class PlayingPlayer(Player):

    """a player in a computer game as opposed to a ScoringPlayer"""
    # pylint: disable=too-many-public-methods
    # too many public methods

    def __init__(self, game, name):
        self.sayable = {}               # recompute for each move, use as cache
        Player.__init__(self, game, name)

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
        if Debug.mahJongg:
            self.game.debug('{} declared MJ: concealed={}, withDiscard={}, lastTile={},lastMeld={}'.format(
                self, concealed, withDiscard, lastTile, lastMeld))
            self.game.debug('  with hand being {}'.format(self.hand))
        melds = concealed[:]
        self.game.winner = self
        assert lastMeld in melds, \
            'lastMeld %s not in melds: concealed=%s: melds=%s lastTile=%s withDiscard=%s' % (
                lastMeld, self._concealedTiles, melds, lastTile, withDiscard)
        if withDiscard:
            PlayingPlayer.addConcealedTiles(
                self,
                [withDiscard])  # this should NOT invoke syncHandBoard
            if self.lastSource is not TileSource.RobbedKong:
                self.lastSource = TileSource.LivingWallDiscard
            # the last claimed meld is exposed
            melds.remove(lastMeld)
            lastTile = withDiscard.exposed
            lastMeld = lastMeld.exposed
            self._exposedMelds.append(lastMeld)
            for tileName in lastMeld:
                self.visibleTiles[tileName] += 1
        self.lastTile = lastTile
        self.lastMeld = lastMeld
        self._concealedMelds = melds
        self._concealedTiles = []
        self._hand = None
        if Debug.mahJongg:
            self.game.debug('  hand becomes {}'.format(self.hand))
            self._hand = None

    def __possibleChows(self):
        """returns a unique list of lists with possible claimable chow combinations"""
        if self.game.lastDiscard is None:
            return []
        exposedChows = [x for x in self._exposedMelds if x.isChow]
        if len(exposedChows) >= self.game.ruleset.maxChows:
            return []
        tile = self.game.lastDiscard
        within = TileList(self.concealedTiles[:])
        within.append(tile)
        return within.hasChows(tile)

    def __possibleKongs(self):
        """returns a unique list of lists with possible kong combinations"""
        kongs = []
        if self == self.game.activePlayer:
            # declaring a kong
            for tileName in sorted(set([x for x in self._concealedTiles if not x.isBonus])):
                if self._concealedTiles.count(tileName) == 4:
                    kongs.append(tileName.kong)
                elif self._concealedTiles.count(tileName) == 1 and \
                        tileName.exposed.pung in self._exposedMelds:
                    # the result will be an exposed Kong but the 4th tile
                    # came from the wall, so we use the form aaaA
                    kongs.append(tileName.kong.exposedClaimed)
        if self.game.lastDiscard:
            # claiming a kong
            discardTile = self.game.lastDiscard.concealed
            if self._concealedTiles.count(discardTile) == 3:
                # discard.kong.concealed is aAAa but we need AAAA
                kongs.append(Meld(discardTile * 4))
        return kongs

    def __maySayChow(self, dummyMove):
        """returns answer arguments for the server if calling chow is possible.
        returns the meld to be completed"""
        if self == self.game.nextPlayer():
            return self.__possibleChows()

    def __maySayPung(self, dummyMove):
        """returns answer arguments for the server if calling pung is possible.
        returns the meld to be completed"""
        lastDiscard = self.game.lastDiscard
        if self.game.lastDiscard:
            assert lastDiscard.isConcealed, lastDiscard
            if self.concealedTiles.count(lastDiscard) >= 2:
                return MeldList([lastDiscard.pung])

    def __maySayKong(self, dummyMove):
        """returns answer arguments for the server if calling or declaring kong is possible.
        returns the meld to be completed or to be declared"""
        return self.__possibleKongs()

    def __maySayMahjongg(self, move):
        """returns answer arguments for the server if calling or declaring Mah Jongg is possible"""
        game = self.game
        if move.message == Message.DeclaredKong:
            withDiscard = move.meld[0].concealed
        elif move.message == Message.AskForClaims:
            withDiscard = game.lastDiscard
        else:
            withDiscard = None
        hand = self._computeHandWithDiscard(withDiscard)
        if hand.won:
            if Debug.robbingKong:
                if move.message == Message.DeclaredKong:
                    game.debug('%s may rob the kong from %s/%s' %
                               (self, move.player, move.exposedMeld))
            if Debug.mahJongg:
                game.debug('%s may say MJ:%s, active=%s' % (
                    self, list(x for x in game.players), game.activePlayer))
                game.debug('  with hand {}'.format(hand))
            return MeldList(x for x in hand.melds if not x.isDeclared), withDiscard, hand.lastMeld

    def __maySayOriginalCall(self, dummyMove):
        """returns True if Original Call is possible"""
        for tileName in sorted(set(self.concealedTiles)):
            newHand = self.hand - tileName
            if newHand.callingHands:
                if Debug.originalCall:
                    self.game.debug(
                        '%s may say Original Call by discarding %s from %s' %
                        (self, tileName, self.hand))
                return True

    sayables = {
        Message.Pung: __maySayPung,
        Message.Kong: __maySayKong,
        Message.Chow: __maySayChow,
        Message.MahJongg: __maySayMahjongg,
        Message.OriginalCall: __maySayOriginalCall}

    def computeSayable(self, move, answers):
        """find out what the player can legally say with this hand"""
        self.sayable = {}
        for message in Message.defined.values():
            if message in answers and message in self.sayables:
                self.sayable[message] = self.sayables[message](self, move)
            else:
                self.sayable[message] = True

    def maybeDangerous(self, msg):
        """could answering with msg lead to dangerous game?
        If so return a list of resulting melds
        where a meld is represented by a list of 2char strings"""
        if msg in (Message.Chow, Message.Pung, Message.Kong):
            return [x for x in self.sayable[msg] if self.mustPlayDangerous(x)]
        else:
            return []

    def hasConcealedTiles(self, tiles, within=None):
        """do I have those concealed tiles?"""
        if within is None:
            within = self._concealedTiles
        within = within[:]
        for tile in tiles:
            if tile not in within:
                return False
            within.remove(tile)
        return True

    def showConcealedTiles(self, tiles, show=True):
        """show or hide tiles"""
        if not self.game.playOpen and self != self.game.myself:
            if not isinstance(tiles, (list, tuple)):
                tiles = [tiles]
            assert len(tiles) <= len(self._concealedTiles), \
                '%s: showConcealedTiles %s, we have only %s' % (
                    self, tiles, self._concealedTiles)
            for tileName in tiles:
                src, dst = (Tile.unknown, tileName) if show else (
                    tileName, Tile.unknown)
                assert src != dst, (
                    self, src, dst, tiles, self._concealedTiles)
                if src not in self._concealedTiles:
                    logException('%s: showConcealedTiles(%s): %s not in %s.' %
                                 (self, tiles, src, self._concealedTiles))
                idx = self._concealedTiles.index(src)
                self._concealedTiles[idx] = dst
            if self.lastTile and not self.lastTile.isKnown:
                self.lastTile = None
            self._hand = None
            self.syncHandBoard()

    def showConcealedMelds(self, concealedMelds, ignoreDiscard=None):
        """the server tells how the winner shows and melds his
        concealed tiles. In case of error, return message and arguments"""
        for meld in concealedMelds:
            for tile in meld:
                if tile == ignoreDiscard:
                    ignoreDiscard = None
                else:
                    if tile not in self._concealedTiles:
                        msg = m18nE(
                            '%1 claiming MahJongg: She does not really have tile %2')
                        return msg, self.name, tile
                    self._concealedTiles.remove(tile)
            if meld.isConcealed and not meld.isKong:
                self._concealedMelds.append(meld)
            else:
                self._exposedMelds.append(meld)
        if self._concealedTiles:
            msg = m18nE(
                '%1 claiming MahJongg: She did not pass all concealed tiles to the server')
            return msg, self.name
        self._hand = None

    def robTileFrom(self, tile):
        """used for robbing the kong from this player"""
        assert tile.isConcealed
        tile = tile.exposed
        for meld in self._exposedMelds:
            if tile in meld:
                meld = meld.without(tile)
                self.visibleTiles[tile] -= 1
                break
        else:
            raise Exception('robTileFrom: no meld found with %s' % tile)
        self.game.lastDiscard = tile.concealed
        self.lastTile = None  # our lastTile has just been robbed
        self._hand = None

    def robsTile(self):
        """True if the player is robbing a tile"""
        self.lastSource = TileSource.RobbedKong

    def scoreMatchesServer(self, score):
        """do we compute the same score as the server does?"""
        if score is None:
            return True
        if any(not x.isKnown for x in self._concealedTiles):
            return True
        if str(self.hand) == score:
            return True
        self.game.debug('%s localScore:%s' % (self, self.hand))
        self.game.debug('%s serverScore:%s' % (self, score))
        logWarning(
            u'Game %s: client and server disagree about scoring, see logfile for details' %
            self.game.seed)
        return False

    def mustPlayDangerous(self, exposing=None):
        """]
        True if the player has no choice, otherwise False.

        @param exposing: May be a meld which will be exposed before we might
        play dangerous.
        @type exposing: L{Meld}
        @rtype: C{Boolean}
        """
        if self == self.game.activePlayer and exposing and len(exposing) == 4:
            # declaring a kong is never dangerous because we get
            # an unknown replacement
            return False
        afterExposed = list(x.exposed for x in self._concealedTiles)
        if exposing:
            exposing = exposing[:]
            if self.game.lastDiscard:
                # if this is about claiming a discarded tile, ignore it
                # the player who discarded it is responsible
                exposing.remove(self.game.lastDiscard)
            for tile in exposing:
                if tile.exposed in afterExposed:
                    # the "if" is needed for claimed pung
                    afterExposed.remove(tile.exposed)
        return all(self.game.dangerousFor(self, x) for x in afterExposed)

    def exposeMeld(self, meldTiles, calledTile=None):
        """exposes a meld with meldTiles: removes them from concealedTiles,
        adds the meld to exposedMelds and returns it
        calledTile: we got the last tile for the meld from discarded, otherwise
        from the wall"""
        game = self.game
        game.activePlayer = self
        allMeldTiles = meldTiles[:]
        if calledTile:
            assert isinstance(calledTile, Tile), calledTile
            allMeldTiles.append(calledTile)
        if len(allMeldTiles) == 4 and allMeldTiles[0].isExposed:
            tile0 = allMeldTiles[0].exposed
            # we are adding a 4th tile to an exposed pung
            self._exposedMelds = [
                x for x in self._exposedMelds if x != tile0.pung]
            meld = tile0.kong
            if allMeldTiles[3] not in self._concealedTiles:
                game.debug(
                    't3 %s not in conc %s' %
                    (allMeldTiles[3], self._concealedTiles))
            self._concealedTiles.remove(allMeldTiles[3])
            self.visibleTiles[tile0] += 1
        else:
            allMeldTiles = sorted(allMeldTiles)  # needed for Chow
            meld = Meld(allMeldTiles)
            for meldTile in meldTiles:
                self._concealedTiles.remove(meldTile)
            for meldTile in allMeldTiles:
                self.visibleTiles[meldTile.exposed] += 1
            meld = meld.exposedClaimed if calledTile else meld.declared
        if self.lastTile in allMeldTiles:
            self.lastTile = self.lastTile.exposed
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
            group = list(defaultdict.keys(self.visibleTiles))[0].group
            # see http://www.logilab.org/ticket/23986
            assert group.islower(), self.visibleTiles
            if group in Tile.colors:
                if all(x.group == group for x in self.visibleTiles):
                    suitTiles = set([Tile(group, x) for x in Tile.numbers])
                    if self.visibleTiles.count(suitTiles) >= 9:
                        dangerous.append(
                            (suitTiles, m18n('Player %1 may try a True Color Game', pName)))
                elif all(x.value in Tile.terminals for x in self.visibleTiles):
                    dangerous.append((elements.terminals,
                                      m18n('Player %1 may try an All Terminals Game', pName)))
        if expMeldCount >= 2:
            windMelds = sum(self.visibleTiles[x] >= 3 for x in elements.winds)
            dragonMelds = sum(
                self.visibleTiles[x] >= 3 for x in elements.dragons)
            windsDangerous = dragonsDangerous = False
            if windMelds + dragonMelds == expMeldCount and expMeldCount >= 3:
                windsDangerous = dragonsDangerous = True
            windsDangerous = windsDangerous or windMelds >= 3
            dragonsDangerous = dragonsDangerous or dragonMelds >= 2
            if windsDangerous:
                dangerous.append(
                    (set(x for x in elements.winds if x not in self.visibleTiles),
                     m18n('Player %1 exposed many winds', pName)))
            if dragonsDangerous:
                dangerous.append(
                    (set(x for x in elements.dragons if x not in self.visibleTiles),
                     m18n('Player %1 exposed many dragons', pName)))
        self.dangerousTiles = dangerous
        if dangerous and Debug.dangerousGame:
            self.game.debug('dangerous:%s' % dangerous)
