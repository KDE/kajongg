# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

import weakref
from typing import Dict, List, Type, Optional, Set, Generator, Tuple, TYPE_CHECKING
from typing import Union, Any, Callable, overload, SupportsIndex, Iterable, cast

from log import logException, logWarning, logDebug
from mi18n import i18n, i18nc, i18nE
from common import IntDict, Debug
from common import ReprMixin, Internal
from wind import East, Wind
from query import Query
from tile import Tile, TileList, TileTuple, PieceList, elements, Meld, MeldList
from tilesource import TileSource
from permutations import Permutations
from message import Message
from hand import Hand
from intelligence import AIDefaultAI

if TYPE_CHECKING:
    from sound import Voice
    from tile import Tiles, Piece
    from game import Game, PlayingGame
    from uitile import UITile
    from deferredutil import Request
    from rule import UsedRule
    from move import Move
    from handboard import HandBoard
    from message import ClientMessage


class Players(list, ReprMixin):

    """a list of players where the player can also be indexed by wind.
    The position in the list defines the place on screen. First is on the
    screen bottom, second on the right, third top, forth left"""

    allNames:Dict[int, str] = {}
    allIds:Dict[str, int] = {}
    humanNames:Dict[int, str] = {}

    def __init__(self, players:Optional[List['Player']]=None) ->None:
        list.__init__(self)
        if players:
            self.extend(players)

    @overload
    def __getitem__(self, index:SupportsIndex) ->'Player': ...
    @overload
    def __getitem__(self, index:slice) ->List['Player']: ...

    def __getitem__(self, index:Union[SupportsIndex, slice]) ->Union['Player', List['Player']]:
        """allow access by idx or by wind"""
        if isinstance(index, Wind):
            for player in self:
                if player.wind == index:
                    return player
        assert isinstance(index, (int, slice)), f'index is neither Wind, int nor slice:{type(index)}'
        return list.__getitem__(self, index)

    def __str__(self) ->str:
        return ', '.join(f'{x.name}: {x.wind}' for x in self)

    def byId(self, playerid:int) ->Optional['Player']:
        """lookup the player by id"""
        for player in self:
            if player.nameid == playerid:
                return player
        logException(f"no player has id {int(playerid)}")
        return None

    def byName(self, playerName:str) ->Optional['Player']:
        """lookup the player by name"""
        for player in self:
            if player.name == playerName:
                return player
        logException(
            f"no player has name '{playerName}' - we have {[x.name for x in self]}")
        return None

    @staticmethod
    def load() -> None:
        """load all defined players into self.allIds and self.allNames"""
        Players.allIds = {}
        Players.allNames = {}
        for nameid, name in Query("select id,name from player").records:
            Players.allIds[name] = nameid
            Players.allNames[nameid] = name
            if not name.startswith('Robot'):
                Players.humanNames[nameid] = name

    @staticmethod
    def createIfUnknown(name:str) ->None:
        """create player in database if not there yet"""
        if not Internal.db:
            # kajonggtest
            nameid = len(Players.allIds) + 1
            Players.allIds[name] = nameid
            Players.allNames[nameid] = name
            if not name.startswith('Robot'):
                Players.humanNames[nameid] = name

        if name not in Players.allNames.values():
            Players.load()  # maybe somebody else already added it
            if name not in Players.allNames.values():
                Query("insert or ignore into player(name) values(?)", (name,))
                Players.load()
        assert name in Players.allNames.values(), f'{name} not in {Players.allNames.values()}'

    def translatePlayerNames(self, names:Iterable[str]) ->List[str]:
        """for a list of names, translates those names which are english
        player names into the local language"""
        known = {x.name for x in self}
        return [self.byName(x).localName if x in known else x for x in names]  # type: ignore[union-attr]


class Player(ReprMixin):

    """
    all player related attributes without GUI stuff.
    concealedTiles: used during the hand for all concealed tiles, ungrouped.
    concealedMelds: is empty during the hand, will be valid after end of hand,
    containing the concealed melds as the player presents them.

    @todo: Now that Player() always calls createIfUnknown, test defining new
    players and adding new players to server
    """
    # pylint: disable=too-many-instance-attributes

    def __init__(self, game:Optional['Game'], name:str) ->None:
        """
        Initialize a player for a give game.

        @type game: L{Game} or None.
        @param game: The game this player is part of. May be None.
        """
        self._game:Optional[weakref.ReferenceType['Game']] = None
        if game:
            self._game = weakref.ref(game)
        self.__balance = 0
        self.__payment = 0
        self.wonCount = 0
        self.__name = ''
        Players.createIfUnknown(name)
        self.name = name
        self.wind:Wind = East
        self.intelligence:AIDefaultAI = AIDefaultAI(self)  # type:ignore[arg-type]
        self.visibleTiles:Dict[Tile, int] = IntDict(cast(IntDict, game.visibleTiles)) if game else IntDict()
        self.handCache:Dict[str, 'Hand'] = {}
        self.cacheHits:int = 0
        self.cacheMisses:int = 0
        self.__lastSource:Type[TileSource.SourceClass] = TileSource.Unknown
        self.clearHand()
        self.handBoard:Optional['HandBoard'] = None

    def __lt__(self, other:Any) ->bool:
        """Used for sorting"""
        if not other:
            return False
        if not isinstance(other, Player):
            return False
        return self.name < other.name

    def clearCache(self) -> None:
        """clears the cache with Hands"""
        if Debug.hand and self.handCache and self.game:
            self.game.debug(
                f'{self}: cache hits:{int(self.cacheHits)} misses:{int(self.cacheMisses)}')
        self.handCache.clear()
        Permutations.cache.clear()
        self.cacheHits = 0
        self.cacheMisses = 0

    @property
    def name(self) ->str:
        """
        The name of the player, can be changed only once.

        @type: C{str}
        """
        return self.__name

    @name.setter
    def name(self, value:str) ->None:
        """write once"""
        assert self.__name == ''
        assert value
        assert isinstance(value, str), f'Player.name must be str but not {type(value)}'
        self.__name = value

    @property
    def game(self) ->Optional['Game']:
        """hide the fact that this is a weakref"""
        return self._game() if self._game else None

    def clearHand(self) -> None:
        """clear player attributes concerning the current hand"""
        self._concealedTiles:PieceList = PieceList()
        self._exposedMelds = MeldList()
        self._concealedMelds = MeldList()
        self._bonusTiles:TileList = TileList()
        self.discarded:List[Tile] = []
        self.visibleTiles.clear()
        self.newHandContent = None
        self.originalCallingHand:Optional[Hand] = None
        self.__lastTile = Tile.none
        self.lastSource = TileSource.Unknown
        self.lastMeld = Meld()
        self.__mayWin = True
        self.__payment = 0
        self.__originalCall:bool = False
        self.dangerousTiles:List[Tuple[Set[Tile], str]] = []
        self.claimedNoChoice:bool = False
        self.playedDangerous:bool = False
        self.usedDangerousFrom:Optional['PlayingPlayer'] = None
        self.isCalling:bool = False
        self.clearCache()
        self._hand:Optional['Hand'] = None

    @property
    def lastTile(self) ->Tile:
        """temp for debugging"""
        return self.__lastTile

    @lastTile.setter
    def lastTile(self, value:Tile) ->None:
        """temp for debugging"""
        assert isinstance(value, Tile), value
        self.__lastTile = value
        if value is Tile.none:
            self.lastMeld = Meld()
        # FIXME self.assertLastTile()
# this would probably work if we compute new tiles first and lastTile/lastMeld last, but
# when changing that order, kajongg returns different results.

    @property
    def originalCall(self) ->bool:
        """temp for debugging"""
        return self.__originalCall

    @originalCall.setter
    def originalCall(self, value:bool) ->None:
        """temp for debugging"""
        if self.__originalCall != value:
            self.__originalCall = value
            self._hand = None  # force recreation

    def invalidateHand(self) ->None:
        """some source for the computation of current hand changed"""
        self._hand = None

    @property
    def hand(self) ->'Hand':
        """readonly: the current Hand. Compute if invalidated."""
        if not self._hand:
            self._hand = self.__computeHand()
        elif Debug.hand:
            _ = self.__computeHand()
            assert self._hand == _, f'{self.hand} != {_}'
        return self._hand

    @property
    def bonusTiles(self) ->TileList:
        """a readonly tuple"""
        return self._bonusTiles

    @property
    def concealedTiles(self) ->TileTuple:
        """a readonly tuple"""
        return TileTuple(self._concealedTiles)

    @property
    def exposedMelds(self) ->MeldList:
        """a readonly tuple"""
        return self._exposedMelds

    @property
    def concealedMelds(self) ->MeldList:
        """a readonly tuple"""
        return self._concealedMelds

    @property
    def mayWin(self) ->bool:
        """winning possible?"""
        return self.__mayWin

    @mayWin.setter
    def mayWin(self, value:bool) ->None:
        """winning possible?"""
        if self.__mayWin != value:
            self.__mayWin = value
            self._hand = None

    @property
    def lastSource(self) ->Type[TileSource.SourceClass]:
        """the source of the last tile the player got"""
        return self.__lastSource

    @lastSource.setter
    def lastSource(self, value: Type[TileSource.SourceClass]) ->None:
        """the source of the last tile the player got"""
        if self.game:
            if self.game.wall:
                if value is TileSource.LivingWallDiscard and not self.game.wall.living:
                    value = TileSource.LivingWallEndDiscard
                if value is TileSource.LivingWall and not self.game.wall.living:
                    value = TileSource.LivingWallEnd
        if self.__lastSource != value:
            self.__lastSource = value
            self._hand = None

    @property
    def nameid(self) ->int:
        """the name id of this player"""
        return Players.allIds[self.name]

    @property
    def localName(self) ->str:
        """the localized name of this player"""
        return i18nc('kajongg, name of robot player, to be translated', self.name)

    @property
    def handTotal(self) ->int:
        """the hand total of this player for the final scoring"""
        assert self.game
        return 0 if not self.game.winner else self.hand.total()

    @property
    def balance(self) ->int:
        """the balance of this player"""
        return self.__balance

    @balance.setter
    def balance(self, balance:int) ->None:
        """the balance of this player"""
        self.__balance = balance
        self.__payment = 0

    def getsPayment(self, payment:int) ->None:
        """make a payment to this player"""
        self.__balance += payment
        self.__payment += payment

    @property
    def payment(self) ->int:
        """the payments for the current hand"""
        return self.__payment

    @payment.setter
    def payment(self, payment:int) ->None:
        """the payments for the current hand"""
        assert payment == 0
        self.__payment = 0

    def __str__(self) ->str:
        return f'{self.name[:10]:<10} {self.wind}'

    def pickedTile(self, deadEnd:bool, tileName:Optional[Tile] =None) -> Tile:
        """got a tile from wall"""
        assert self.game
        assert self.game.wall
        self.game.activePlayer = self
        tile = self.game.wall.deal(tileName, deadEnd=deadEnd)[0]  # type:ignore[list-item]
        if hasattr(tile, 'tile'):
            self.lastTile = tile.tile
        else:
            self.lastTile = tile
        self.addConcealedTiles(TileList(tile))
        if deadEnd:
            self.lastSource = TileSource.DeadWall
        else:
            self.game.lastDiscard = None
            self.lastSource = TileSource.LivingWall
        return self.lastTile

    def removeConcealedTile(self, tile: Tile) -> None:
        """remove from my tiles"""
        assert not tile.isBonus, tile
        assert tile.__class__ == Tile
        if tile not in self._concealedTiles:
            raise ValueError(f'removeConcealedTile({tile!r}): tile not in concealed {self._concealedTiles!r}')
        self._concealedTiles.remove(tile)
        if tile is self.lastTile:
            self.lastTile = Tile.none
        self._hand = None

    def addConcealedTiles(self, tiles:'Tiles', animated:bool=False) -> None:  # pylint: disable=unused-argument
        """add to my tiles"""
        assert tiles
        for tile in tiles:
            if tile.isBonus:
                self._bonusTiles.append(tile)
            else:
                assert tile.isConcealed, f'{tile} data={tiles}'
                self._concealedTiles.append(tile)
        self._hand = None

    def syncHandBoard(self, adding:Optional[List['UITile']]=None) ->None:
        """virtual: synchronize display"""

    def colorizeName(self) ->None:
        """virtual: colorize Name on wall"""

    def getsFocus(self, unusedResults:Optional[List['Request']]=None) ->None:
        """virtual: player gets focus on his hand"""

    def __announcements(self) -> Set:
        """used to build the Hand"""
        return set('a') if self.originalCall else set()

    def makeTileKnown(self, tile:Tile) -> None:
        """used when somebody else discards a tile"""
        assert not self._concealedTiles[0].isKnown
        self._concealedTiles[0] = tile
        self._hand = None

    def assertLastTile(self) ->None:
        """TODO: Remove again"""
        return
        # pylint: disable=unreachable
        if self.lastTile and self.lastTile.isKnown:
            if not self.lastTile.isBonus: # TODO: wirklich ausklammern?
                # pylint:disable=consider-using-f-string
                assert (self.lastTile in self._concealedTiles
                    or any(self.lastTile in x for x in self._exposedMelds)
                    or any(self.lastTile in x for x in self._concealedMelds)), \
                    'lastTile:{!r} conc:{!r} exp:{!r} concmelds:{!r}'.format(
                        self.lastTile, self._concealedTiles, self._exposedMelds, self._concealedMelds)

    def __computeHand(self) -> Hand:
        """return Hand for this player"""
        assert not (self._concealedMelds and self._concealedTiles)
        return Hand(
            self, melds=MeldList(self._exposedMelds + self._concealedMelds), unusedTiles=self._concealedTiles,
            bonusTiles=self._bonusTiles, lastTile=self.lastTile, lastMeld=self.lastMeld,
            lastSource=self.lastSource, announcements=self.__announcements())

    def _computeHandWithDiscard(self, discard:Tile) -> Hand:
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
                self._concealedTiles.pop(-1)

    def scoringString(self) -> str:
        """helper for HandBoard.__str__"""
        if self._concealedMelds:
            parts = [str(x) for x in self._concealedMelds + self._exposedMelds]
        else:
            parts = [str(self._concealedTiles)]
            parts.extend([str(x) for x in self._exposedMelds])
        parts.extend(str(x) for x in self._bonusTiles)
        return ' '.join(parts)

    def sortRulesByX(self, rules:List['UsedRule']) ->List['UsedRule']:
        """if this game has a GUI, sort rules by GUI order"""
        return rules

    def others(self) -> Generator['Player', None, None]:
        """a list of the other 3 players"""
        assert self.game
        return (x for x in self.game.players if x != self)

    def tileAvailable(self, tile:Tile, hand:Hand) -> int:
        """a count of how often tile might still appear in the game
        supposing we have hand"""
        lowerTile = tile.exposed
        upperTile = tile.concealed
        assert self.game
        visible = cast(IntDict, self.game.discardedTiles).count([lowerTile])
        if visible:
            if hand.lenOffset == 0 and self.game.lastDiscard and lowerTile is self.game.lastDiscard.exposed:
                # the last discarded one is available to us since we can claim
                # it
                visible -= 1
        visible += sum(cast(IntDict, x.visibleTiles).count([lowerTile, upperTile])
                       for x in self.others())
        visible += sum(x.exposed == lowerTile for x in hand.tiles)
        return 4 - visible

    def violatesOriginalCall(self, discard:Tile) ->bool:
        """called if discarding discard violates the Original Call"""
        if not self.originalCall or not self.mayWin:
            return False
        if self.lastTile and self.lastTile.exposed != discard.exposed:
            if Debug.originalCall and self.game:
                self.game.debug(
                    f'{self} would violate OC with {discard}, lastTile={self.lastTile}')
            return True
        return False


class PlayingPlayer(Player):  # pylint:disable=too-many-instance-attributes

    """a player in a computer game as opposed to a ScoringPlayer"""
    # too many public methods

    def __init__(self, game:Optional['PlayingGame'], name:str) ->None:
        self.sayable:Dict[Message, Union[bool, MeldList, Tuple[MeldList, Optional[Tile], Meld], None ]] = {}
        # recompute sayable for each move, use as cache
        self.voice:Optional['Voice']
        self.game:Optional['PlayingGame']
        Player.__init__(self, game, name)

    def popupMsg(self, msg:'Message') ->None:
        """virtual: show popup on display"""

    def hidePopup(self) ->None:
        """virtual: hide popup on display"""

    def speak(self, txt:str) ->None:
        """only a visible playing player can speak"""

    def declaredMahJongg(self, concealed:MeldList, withDiscard:Optional[Tile], lastTile:Tile, lastMeld:Meld) ->None:
        """player declared mah jongg. Determine last meld, show concealed tiles grouped to melds"""
        assert self.game
        if Debug.mahJongg:
            self.game.debug(f'{self} declared MJ: concealed={concealed}, '
                            f'withDiscard={withDiscard}, lastTile={lastTile},lastMeld={lastMeld}')
            self.game.debug(f'  with hand being {self.hand}')
        melds = concealed[:]
        self.game.winner = self
        assert lastMeld in melds, (
            f'lastMeld {lastMeld} not in melds: concealed={self._concealedTiles}: '
            f'melds={melds} lastTile={lastTile} withDiscard={withDiscard}')
        if withDiscard:
            PlayingPlayer.addConcealedTiles(
                self,
                TileList(withDiscard))  # this should NOT invoke syncHandBoard
            if len(list(self.game.lastMoves(only=(Message.Discard, )))) == 1:
                self.lastSource = TileSource.East14th
            elif self.lastSource is not TileSource.RobbedKong:
                self.lastSource = TileSource.LivingWallDiscard
            # the last claimed meld is exposed
            melds.remove(lastMeld)
            lastTile = withDiscard.exposed
            lastMeld = lastMeld.exposed
            self._exposedMelds.append(lastMeld)
            for tileName in lastMeld:
                self.visibleTiles[tileName] += 1
        self.lastTile = lastTile or Tile.none
        self.lastMeld = lastMeld
        self._concealedMelds = melds
        self._concealedTiles = PieceList()
        self._hand = None
        if Debug.mahJongg:
            self.game.debug(f'  hand becomes {self.hand}')
            self._hand = None

    def __possibleChows(self) ->MeldList:
        """return a unique list of lists with possible claimable chow combinations"""
        if not self.game:
            return MeldList()
        if self.game.lastDiscard is None:
            return MeldList()
        exposedChows = [x for x in self._exposedMelds if x.isChow]
        if len(exposedChows) >= self.game.ruleset.maxChows:
            return MeldList()
        ladi = self.game.lastDiscard
        return (TileTuple(self.concealedTiles) + ladi).possibleChows(ladi)

    def __possibleKongs(self) ->MeldList:
        """return a unique list of lists with possible kong combinations"""
        if not self.game:
            return MeldList()
        kongs = MeldList()
        if self == self.game.activePlayer:
            # declaring a kong
            for tileName in sorted({x for x in self._concealedTiles if not x.isBonus}):
                if self._concealedTiles.count(tileName) == 4:
                    kongs.append(tileName.kong)
                elif self._concealedTiles.count(tileName) == 1 and \
                        tileName.exposed.pung in self._exposedMelds:
                    # the result will be an exposed Kong but the 4th tile
                    # came from the wall, so we use the form aaaA
                    kongs.append(tileName.kong.exposedClaimed)
        if self.game.lastDiscard:
            # claiming a kong
            discardedTile = self.game.lastDiscard.concealed
            if self._concealedTiles.count(discardedTile) == 3:
                # discard.kong.concealed is aAAa but we need AAAA
                kongs.append(Meld(discardedTile * 4))
        return kongs

    def __maySayChow(self, unusedMove:'Move') ->MeldList:
        """return answer arguments for the server if calling chow is possible.
        returns the meld to be completed"""
        if not self.game:
            return MeldList()
        return self.__possibleChows() if self == self.game.nextPlayer() else MeldList()

    def __maySayPung(self, unusedMove:'Move') -> MeldList:
        """return answer arguments for the server if calling pung is possible.
        returns the meld to be completed"""
        if not self.game:
            return MeldList()
        lastDiscard = self.game.lastDiscard
        if lastDiscard:
            assert lastDiscard.isConcealed, lastDiscard
            if self.concealedTiles.count(lastDiscard) >= 2:
                return MeldList([lastDiscard.pung])
        return MeldList()

    def __maySayKong(self, unusedMove:'Move') ->MeldList:
        """return answer arguments for the server if calling or declaring kong is possible.
        returns the meld to be completed or to be declared"""
        return self.__possibleKongs()

    def __maySayMahjongg(self, move:'Move') ->Optional[Tuple[MeldList, Optional[Tile], Optional[Meld]]]:
        """return answer arguments for the server if calling or declaring Mah Jongg is possible"""
        game = self.game
        assert game
        if move.message == Message.DeclaredKong:  # type: ignore
            assert move.meld
            withDiscard = move.meld[0].concealed
        elif move.message == Message.AskForClaims:  # type: ignore
            withDiscard = game.lastDiscard
        else:
            withDiscard = None
        hand = self._computeHandWithDiscard(withDiscard)
        if hand.won:
            if Debug.robbingKong:
                if move.message == Message.DeclaredKong:  # type: ignore
                    game.debug(f'{self} may rob the kong from {move.player}/{move.exposedMeld}')
            if Debug.mahJongg:
                game.debug(f'{self} may say MJ:{list(x for x in game.players)}, active={game.activePlayer}')
                game.debug(f'  with hand {hand}')
            return MeldList(x for x in hand.melds if not x.isDeclared), withDiscard, hand.lastMeld
        return None

    def __maySayOriginalCall(self, unusedMove:'Move') ->bool:
        """return True if Original Call is possible"""
        assert self.game
        for tileName in sorted(set(self.concealedTiles)):
            newHand = self.hand - tileName
            if newHand.callingHands:
                if Debug.originalCall:
                    self.game.debug(
                        f'{self} may say Original Call by discarding {tileName} from {self.hand}')
                return True
        return False

    __sayables:Dict[Any, Callable] = {
        Message.Pung: __maySayPung,
        Message.Kong: __maySayKong,
        Message.Chow: __maySayChow,
        Message.MahJongg: __maySayMahjongg,
        Message.OriginalCall: __maySayOriginalCall}

    def computeSayable(self, move:'Move', answers:List['ClientMessage']) ->None:
        """find out what the player can legally say with this hand"""
        self.sayable = {}
        for message in Message.defined.values():
            if message in answers and message in self.__sayables:
                self.sayable[message] = self.__sayables[message](self, move)
            else:
                self.sayable[message] = True

    def maybeDangerous(self, msg:Message) ->MeldList:
        """could answering with msg lead to dangerous game?
        If so return a list of resulting melds
        where a meld is represented by a list of 2char strings"""
        result = MeldList()
        if msg in (Message.Chow, Message.Pung, Message.Kong):
            for meld in cast(MeldList, self.sayable[msg]):
                if self.mustPlayDangerous(meld):
                    result.append(meld)
        return result

    def hasConcealedTiles(self, tiles:'Tiles', within:Optional['Tiles'] =None) -> bool:
        """do I have those concealed tiles?"""
        if within is None:
            within = self._concealedTiles
        within = PieceList(within[:])  # type: ignore
        for tile in tiles:
            if tile not in within:
                return False
            within.remove(tile)
        return True

    def showConcealedTiles(self, tiles:TileTuple, show:bool=True) ->None:
        """show or hide tiles"""
        assert isinstance(tiles, TileTuple), repr(tiles)
        assert self.game
        if not self.game.playOpen and self != self.game.myself:
            assert len(tiles) <= len(self._concealedTiles), \
                f'{self}: showConcealedTiles {tiles}, we have only {self._concealedTiles}'
            for tileName in tiles:
                src, dst = (Tile.unknown, tileName) if show else (
                    tileName, Tile.unknown)
                assert src != dst, (
                    self, src, dst, tiles, self._concealedTiles)
                if src not in self._concealedTiles:
                    logException(f'{self}: showConcealedTiles({tiles}): {src} not in {self._concealedTiles}.')
                idx = self._concealedTiles.index(src)
                self._concealedTiles[idx] = dst
            self._hand = None
            self.syncHandBoard()

    def showConcealedMelds(self, concealedMelds:MeldList,
        ignoreDiscard:Optional[Tile] =None) ->Optional[Tuple[str, ...]]:
        """the server tells how the winner shows and melds his
        concealed tiles. In case of error, return message and arguments"""
        for meld in concealedMelds:
            for tile in meld:
                if tile == ignoreDiscard:
                    ignoreDiscard = None
                else:
                    if tile not in self._concealedTiles:
                        msg = i18nE(
                            '%1 claiming MahJongg: She does not really have tile %2')
                        return msg, self.name, tile
                    self._concealedTiles.remove(tile)
            if meld.isConcealed and not meld.isKong:
                self._concealedMelds.append(meld)
            else:
                self._exposedMelds.append(meld)
        if self._concealedTiles:
            msg = i18nE(
                '%1 claiming MahJongg: She did not pass all concealed tiles to the server')
            return msg, self.name
        self._hand = None
        return None

    def getsRobbed(self, tile:Tile) -> None:
        """used for robbing the kong from this player"""
        if Debug.robbingKong:
            logDebug(f'robbed {tile} from {self}')
        assert tile.isConcealed
        tile = tile.exposed
        for meld in self._exposedMelds:
            if tile in meld:
                # FIXME: document if and where Player is updated meld = meld.without(tile)
                self.visibleTiles[tile] -= 1
                break
        else:
            # TODO: should we somehow show an error and continue?
            raise ValueError(f'getsRobbed: no meld found with {tile}')
        assert self.game
        self.game.lastDiscard = tile.concealed
        self.lastTile = Tile.none  # our lastTile has just been robbed
        self._hand = None

    def robsTile(self) -> None:
        """True if the player is robbing a tile"""
        if Debug.robbingKong:
            logDebug(f'{self} robs a tile')
        self.lastSource = TileSource.RobbedKong

    def scoreMatchesServer(self, score:Optional[str]) -> bool:
        """do we compute the same score as the server does?"""
        if score is None:
            return True
        if any(not x.isKnown for x in self._concealedTiles):
            return True
        if str(self.hand) == score:
            return True
        if self.game:
            self.game.debug(f'{self} localScore:{self.hand}')
            self.game.debug(f'{self} serverScore:{score}')
            logWarning(
                f'Game {self.game.seed}: client and server disagree about scoring, see logfile for details')
        return False

    def mustPlayDangerous(self, exposing:Optional[Meld] =None) -> bool:
        """]
        True if the player has no choice, otherwise False.

        @param exposing: May be a meld which will be exposed before we might
        play dangerous.
        @type exposing: L{Meld}
        @rtype: C{Boolean}
        """
        assert self.game
        if self == self.game.activePlayer and exposing and len(exposing) == 4:
            # declaring a kong is never dangerous because we get
            # an unknown replacement
            return False
        afterExposed = [x.exposed for x in self._concealedTiles]
        if exposing:
            exposingTiles = TileList(exposing)
            if self.game.lastDiscard:
                # if this is about claiming a discarded tile, ignore it
                # the player who discarded it is responsible
                exposingTiles.remove(self.game.lastDiscard)
            for tile in exposingTiles:
                if tile.exposed in afterExposed:
                    # the "if" is needed for claimed pung
                    afterExposed.remove(tile.exposed)
        return all(self.game.dangerousFor(self, x) for x in afterExposed)

    def exposeMeld(self, meldTiles: 'Tiles', calledTile:Optional['Piece']=None) -> Meld:
        """exposes a meld with meldTiles: removes them from concealedTiles,
        adds the meld to exposedMelds and returns it
        calledTile: we got the last tile for the meld from discarded, otherwise
        from the wall"""
        self.assertLastTile()
        game = self.game
        assert game
        game.activePlayer = self
        allMeldTiles = list(meldTiles)
        if calledTile:
            assert isinstance(calledTile, Tile), calledTile
            allMeldTiles.append(calledTile)
        if len(allMeldTiles) == 4 and allMeldTiles[0].isExposed:
            tile0 = allMeldTiles[0].exposed
            # we are adding a 4th tile to an exposed pung
            self._exposedMelds = MeldList(
                x for x in self._exposedMelds if x != tile0.pung)
            meld = tile0.kong
            if allMeldTiles[3] not in self._concealedTiles:
                game.debug(
                    f't3 {allMeldTiles[3]} not in conc {self._concealedTiles}')
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
        assert meld
        if self.lastTile in allMeldTiles:
            self.lastTile = self.lastTile.exposed
        self._exposedMelds.append(meld)
        self._hand = None
        game.computeDangerous(self)
        return meld

    def findDangerousTiles(self) -> None:
        """update the list of dangerous tile"""
        assert self.game
        pName = self.localName
        dangerous:List[Tuple[Set[Tile], str]] = []
        expMeldCount = len(self._exposedMelds)
        if expMeldCount >= 3:
            if all(x in elements.greenHandTiles for x in self.visibleTiles):
                dangerous.append((elements.greenHandTiles,
                                  i18n('Player %1 has 3 or 4 exposed melds, all are green', pName)))
            group = list(self.visibleTiles.keys())[0].group
            assert group.islower(), self.visibleTiles
            if group in Tile.colors:
                if all(x.group == group for x in self.visibleTiles):
                    suitTiles = {Tile(group, x) for x in Tile.numbers}
                    if cast(IntDict, self.visibleTiles).count(suitTiles) >= 9:
                        dangerous.append(
                            (suitTiles, i18n('Player %1 may try a True Color Game', pName)))
                elif all(x.value in Tile.terminals for x in self.visibleTiles):
                    dangerous.append((elements.terminals,
                                      i18n('Player %1 may try an All Terminals Game', pName)))
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
                    ({x for x in elements.winds if x not in self.visibleTiles},
                     i18n('Player %1 exposed many winds', pName)))
            if dragonsDangerous:
                dangerous.append(
                    ({x for x in elements.dragons if x not in self.visibleTiles},
                     i18n('Player %1 exposed many dragons', pName)))
        self.dangerousTiles = dangerous
        if dangerous and Debug.dangerousGame:
            self.game.debug(f'dangerous:{dangerous}')
