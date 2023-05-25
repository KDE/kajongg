# -*- coding: utf-8 -*-

"""
 Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

from itertools import chain
from types import GeneratorType
from typing import Dict, Any
from log import logException
from mi18n import i18n, i18nc
from common import IntDict, ReprMixin, id4
from wind import Wind, East, South, West, North


class Tile(ReprMixin):

    """
    A single tile, represented as a string of length 2.

    Always True:
      - only for suits: tile.group + chr(tile.value + 48) == str(tile)
      - tile.group + tile.char == str(tile)
      - Tile(tile) is tile
      - Tile(tile.group, tile.value) is tile

    Tile() accepts
      - another Tile
      - a string, length 2
      - two args: a char and either a char or an int -1..11

    group is a char: b=bonus w=wind d=dragon X=unknown
    value is
        1..9 for real suit tiles
        -1/0/10/11 for usage in AI
        Wind for winds and boni
        bgr for dragons
    """
    # pylint: disable=too-many-instance-attributes
    cache = {}
    hashTable = 'XxxxXyxyDbdbDgdgDrdrWeweWswsWw//wwWnwn' \
                'S/s/S0s0S1s1S2s2S3s3S4s4S5s5S6s6S7s7S8s8S9s9S:s:S;s;' \
                'B/b/B0b0B1b1B2b2B3b3B4b4B5b5B6b6B7b7B8b8B9b9B:b:B;b;' \
                'C/c/C0c0C1c1C2c2C3c3C4c4C5c5C6c6C7c7C8c8C9c9C:c:C;c;' \
                'fefsfwfnyeysywyn'
    # the // is needed as separator between too many w's
    # intelligence.py will define Tile('b0') or Tile('s:')

    unknown = None
    none = None

    # Groups:
    hidden = 'x'
    stone = 's'
    bamboo = 'b'
    character = 'c'
    colors = stone + bamboo + character
    wind = 'w'
    dragon = 'd'
    honors = wind + dragon
    flower = 'f'
    season = 'y'
    boni = flower + season

    # Values:
    dragons = 'bgr'
    white, green, red = dragons
    winds = 'eswn'
    numbers = range(1, 10)
    terminals = list([1, 9])
    minors = range(2, 9)
    majors = list(dragons) + list(winds) + terminals

    def __new__(cls, *args):
        if len(args) == 1:
            if  type(args[0]) is Tile:  # pylint: disable=unidiomatic-typecheck
                return args[0]
            if  type(args[0]) is Piece:  # pylint: disable=unidiomatic-typecheck
                args = tuple([args[0].name2()])
# FIXME: wirklich list als key?
# lieber arg1, arg2 und fuer dict und _build daraus eines machen
        try:
            return cls.cache[args]
        except KeyError:
            return cls._build(*args)

    @classmethod
    def _build(cls, *args):
        """build a new Tile object out of args"""

        result = super().__new__(cls)
        result.setUp(args)
        return result

    def setUp(self, args):  # pylint:disable=too-many-statements, too-many-branches
        """Initialize"""

        # parse args
        if isinstance(args, Tile):
            group, arg1 = args.group, args.char
        elif len(args) == 1:
            if isinstance(args[0], Tile):
                group = args[0].group
                arg1 = args[0].value
            else:
                assert isinstance(args[0], str)
                group, arg1 = args[0]
        else:
            group, arg1 = args
        self.group = group

        # set attributes depending only on group
        self.isKnown = self.group != 'X'
        self.lowerGroup = self.group.lower()
        self.isExposed = self.group == self.lowerGroup
        self.isConcealed = not self.isExposed
        self.isBonus = self.group in Tile.boni
        self.isDragon = self.lowerGroup == Tile.dragon
        self.isWind = self.lowerGroup == Tile.wind
        self.isHonor = self.isDragon or self.isWind

        self.char, self.value = self.parse_arg1(arg1)

        self.key:int
        try:
            self.key = 1 + self.hashTable.index(Tile.__str__(self)) // 2
        except ValueError:
            logException('%s is not a valid tile string' % self)

        self.isNumber = False
        self.isTerminal = False
        self.isReal = False

        if self.isBonus or self.isDragon or self.isWind:
            self.isReal = True
        elif self.isKnown:
            self.isNumber = True
            self.isTerminal = self.value in Tile.terminals
            self.isReal = self.value in Tile.numbers
        self.isMajor = self.isHonor or self.isTerminal
        self.isMinor = self.isKnown and not self.isMajor

        if self.__class__ is Tile:
            Tile._storeInCache(self)

        self.exposed = self.concealed = self.swapped = None
        self.single = self.pair = self.pung = None
        self.chow = self.kong = None
        if self.__class__ is Tile:
            # a Piece may change
            self._fixed = True

        object.__setattr__(
            self,
            'exposed',
            Tile(self.name2()) if not self.isKnown else Tile(self.group.lower(), self.char))
        object.__setattr__(self, 'concealed',
                        Tile(self.name2()) if not self.isKnown or self.isBonus
                        else Tile(self.group.upper(), self.char))
        object.__setattr__(
            self,
            'swapped',
            self.exposed if self.isConcealed else self.concealed)
        if isinstance(self.value, int):
            if 0 <= self.value <= 11:
                object.__setattr__(
                    self,
                    'prevForChow',
                    Tile(self.group,
                         self.value - 1))
            if -1 <= self.value <= 10:
                object.__setattr__(
                    self,
                    'nextForChow',
                    Tile(
                        self.group,
                        self.value +
                        1))

    def parse_arg1(self, arg1):
        """set the interpreted Tile.value (str, Wind, int)"""
        if isinstance(arg1, Wind):
            char = arg1.char.lower()
        elif isinstance(arg1, int):
            char = chr(arg1 + 48)
        else:
            char = arg1
        value = char  # default
        if self.isWind or self.isBonus:
            if isinstance(arg1, Wind):
                value = arg1
            else:
                value = Wind(arg1)
        elif self.isDragon:
            assert char in 'gbr', arg1
        elif self.group != 'X':
            if isinstance(char, int):
                value = char
            else:
                value = ord(char) - 48
        return char, value

    @classmethod
    def _storeInCache(cls, result):
        """Put the new tile into the cache"""
        for key in (
                result, (str(result),), (result.group, result.value),
                (result.group, result.char)):
            cls.cache[key] = result

        existing = list([x for x in cls.cache.values() if x.key == result.key]) # pylint: disable=consider-using-generator
        existingIds = {id4(x) for x in existing}
        assert len(existingIds) == 1, 'cls is {} new is:{} existing are: {} keys are:{}'.format(cls.__name__,
            repr(result), ','.join(repr(x) for x in existing), ','.join(repr(x) for x in cls.cache if x == 1))

    def name2(self):
        """__str__ might be changed by a subclass"""
        return self.group + str(self.char)

    def __repr__(self):
        """ReprMixin does not seem to work on str subclass"""
        return ReprMixin.__repr__(self)

    def __str__(self):
        return self.group + self.char

    def __hash__(self):
        return self.key

    def __mul__(self, other):
        return [self] * other

    def __imul__(self, other):
        return [self] * other

    def __bool__(self):
        return self.isKnown

    def meld(self, size):
        """return a meld of size. Those attributes are set
        in Meld.cacheMeldsInTiles"""
        _ = self
        if isinstance(_, Piece):
            _ = Tile(_)
        return getattr(_, ('single', 'pair', 'pung', 'kong')[size - 1])

    def groupName(self):
        """the name of the group this tile is of"""
        names = {
            Tile.hidden: i18nc('kajongg', 'hidden'),
            Tile.stone: i18nc('kajongg', 'stone'),
            Tile.bamboo: i18nc('kajongg', 'bamboo'),
            Tile.character: i18nc('kajongg', 'character'),
            Tile.wind: i18nc('kajongg', 'wind'),
            Tile.dragon: i18nc('kajongg', 'dragon'),
            Tile.flower: i18nc('kajongg', 'flower'),
            Tile.season: i18nc('kajongg', 'season')}
        return names[self.lowerGroup]

    def valueName(self):
        """the name of the value this tile has"""
        names = {
            'y': i18nc('kajongg', 'tile'),
            Tile.white: i18nc('kajongg', 'white'),
            Tile.red: i18nc('kajongg', 'red'),
            Tile.green: i18nc('kajongg', 'green'),
            East: i18nc('kajongg', 'East'),
            South: i18nc('kajongg', 'South'),
            West: i18nc('kajongg', 'West'),
            North: i18nc('kajongg', 'North')}
        for idx in Tile.numbers:
            names[idx] = chr(idx + 48)
        return names[self.value]

    def name(self):
        """return name of a single tile"""
        if self.group.lower() == Tile.wind:
            result = {
                East: i18n('East Wind'),
                South: i18n('South Wind'),
                West: i18n('West Wind'),
                North: i18n('North Wind')}[self.value]
        else:
            result = i18nc('kajongg tile name', '{group} {value}')
        return result.format(value=self.valueName(), group=self.groupName())

    def __lt__(self, other):
        """needed for sort"""
        return self.key < other.key

    def change_name(self, element):
        """FIXME: should go away when Tile/Piece is done"""
        assert element.__class__ is Tile, repr(element)
        if element is Tile.none:
            return self
        assert element.__class__ is Tile, repr(element)
        return element

    def __eq__(self, other):
        if isinstance(other, Tile):
            return self.name2() == other.name2()
        return object.__eq__(self, other)

    def cacheMelds(self):
        """fill meld cache"""
        occ = elements.occurrence[self]
        self.single = Meld(self)
        self.concealed.single = Meld(self.concealed)
        if occ > 1:
            self.pair = Meld(self * 2)
            self.concealed.pair = Meld(self.concealed * 2)
            if occ > 2:
                self.pung = Meld(self * 3)
                self.concealed.pung = Meld(self.concealed * 3)
                if self.value in range(1, 8):
                    self.chow = Meld(
                        [self,
                         self.nextForChow,
                         self.nextForChow.nextForChow])
                    self.concealed.chow = Meld(
                        [self.concealed,
                         self.concealed.nextForChow,
                         self.concealed.nextForChow.nextForChow])
                if self.value in range(1, 10):
                    self.knitted3 = Meld(  # pylint:disable=attribute-defined-outside-init
                        [Tile(x, self.value) for x in Tile.colors])
                    self.concealed.knitted3 = Meld(
                        [Tile(x, self.value).concealed for x in Tile.colors])
                if occ > 3:
                    self.kong = Meld(self * 4)
                    self.claimedKong = Meld(  # pylint:disable=attribute-defined-outside-init
                        [self, self, self, self.concealed])
                    self.concealed.kong = Meld(self.concealed * 4)

class Tiles:

    """a Mixin for TileList and TileTuple"""

    def __init__(self, newContent=None):  # pylint:disable=unused-argument
        ...

    @classmethod
    def _parseArgs(cls, iterable):
        """flatten any args into a nice sequence"""
        if isinstance(iterable, str):
            memberList = [cls.tileClass(iterable[x:x + 2])
                       for x in range(0, len(iterable), 2)]
        elif isinstance(iterable, Tile) or iterable.__class__.__name__ == 'UITile':
            memberList = [iterable]
        elif iterable is None:
            memberList = []
        else:
            memberList = []
            for member in iterable:
                if isinstance(member, cls.tileClass):
                    memberList.append(member)
                elif isinstance(member, str):
                    memberList.extend(cls.tileClass(member[x:x + 2])
                               for x in range(0, len(member), 2))
                elif hasattr(member, '__iter__'):
                    memberList.extend(member)
                elif isinstance(member, Tile): # FIXME: remove again
                    memberList.append(member)
                else:
                    raise ValueError(
                        '{}() accepts only {} and str but got {}'.format(
                            cls.__name__, cls.tileClass.__name__, repr(member)))
        return memberList

    def sorted(self):
        """sort(TileList) would not keep TileList type"""
        return self.__class__(sorted(self))

    def possibleChows(self, tile):
        """return my chows with tileName"""
        if tile not in self:
            return []
        if tile.lowerGroup not in Tile.colors:
            return []
        group = tile.group
        values = {x.value for x in self if x.group == group}
        chows = []
        for offsets in [(0, 1, 2), (-2, -1, 0), (-1, 0, 1)]:
            subset = {tile.value + x for x in offsets}
            if subset <= values:
                chow = self.__class__(self.tileClass(group, x) for x in sorted(subset))
                if chow not in chows:
                    chows.append(chow)
        return chows

    def __str__(self):
        """the content"""
        return str(''.join(str(x) for x in self))

    def __repr__(self):
        """for debugging"""
        return '{}_{}({})'.format(self.__class__.__name__, id4(self), ','.join(repr(x) for x in self))

    def __iter__(self):
        """just to make this clear to mypy"""
        return iter(self)


class TileList(list, Tiles):

    """a list that can only hold tiles"""

    tileClass = Tile

    def __init__(self, newContent=None):
        list.__init__(self)
        Tiles.__init__(self, newContent)
        self.extend(self._parseArgs(newContent))
        if self:
            self.isRest = True

    def __add__(self, other):
        result = TileList(self)
        result.extend(self._parseArgs(other))
        return result


class TileTuple(tuple, Tiles):

    """a tuple that can only hold tiles"""

    tileClass = Tile

    def __new__(cls, iterable=None):
        result = tuple.__new__(cls, cls._parseArgs(iterable))
        result.isRest = True
        result._hash = result._compute_hash()
        return result

    def __init__(self, iterable=None):  # pylint: disable=unused-argument
        tuple.__init__(self)
        Tiles.__init__(self)

    def _compute_hash(self):
        """usable for sorting"""
        result = 0
        factor = len(Tile.hashTable) // 2
        for tile in self:
            result = result * factor + tile.key
        return result

    def __hash__(self):
        return self._hash

    def __add__(self, other):
        return TileTuple(TileList(self) + self._parseArgs(other))


class Elements:

    """represents all elements"""
    # pylint: disable=too-many-instance-attributes
    # too many attributes

    def __init__(self):
        self.occurrence = IntDict()  # key: db, s3 etc. value: occurrence
        self.winds = {Tile(Tile.wind, x) for x in Tile.winds}
        self.wINDS = {x.concealed for x in self.winds}
        self.dragons = {Tile(Tile.dragon, x) for x in Tile.dragons}
        self.dRAGONS = {x.concealed for x in self.dragons}
        self.honors = self.winds | self.dragons
        self.hONORS = self.wINDS | self.dRAGONS
        self.terminals = {Tile(x, y)
                          for x in Tile.colors for y in Tile.terminals}
        self.tERMINALS = {x.concealed for x in self.terminals}
        self.majors = self.honors | self.terminals
        self.mAJORS = self.hONORS | self.tERMINALS
        self.greenHandTiles = {
            Tile(Tile.bamboo, x)
            for x in '23468'} | {Tile(Tile.dragon, Tile.green)}
        self.minors = {Tile(x, y) for x in Tile.colors for y in Tile.minors}
        for tile in self.majors:
            self.occurrence[tile] = 4
        for tile in self.minors:
            self.occurrence[tile] = 4
        for bonus in Tile.boni:
            for _ in Tile.winds:
                self.occurrence[Tile(bonus, _)] = 1

    def __filter(self, ruleset):
        """return element names"""
        return (x for x in self.occurrence
                if ruleset.withBonusTiles or (not x.isBonus))

    def count(self, ruleset):
        """how many tiles are to be used by the game"""
        return self.occurrence.count(self.__filter(ruleset))

    def all(self, ruleset):
        """a list of all elements, each of them occurrence times"""
        return self.occurrence.all(self.__filter(ruleset))


class Piece(Tile):

    """
    This tile is part of the game. The wall is built from this.
    """

    def __new__(cls, *args):
        result = cls._build(*args)
        return result

    def __init__(self, *args):  # pylint: disable=unused-argument
        self.uiTile = None  # might be a UITile

    def __hash__(self):
        """this is not inherited from Tile. I am sure there is a good reason."""
        return self.key


class PieceList(TileList):

    """a list that can only hold tiles"""

    tileClass = Piece

    def __contains__(self, value):
        """If value is Piece: must be the same object
        If value is Tile: any element having the same name"""
        if value.__class__ is Tile:
            _ =  value.name2()
            return any(x.name2() == _ for x in self)
        return any(x is value for x in self)

    def index(self, value):
        """Also accept Tile."""
        if value.__class__ is Tile:
            for result, _ in enumerate(self):
                if _ == value:
                    return result
            raise ValueError('{!r} is not in list {!r}'.format(value, self))
        return TileList.index(self, value)

    def remove(self, value):
        """Can also remove Tile."""
# FIXME: should we do tile == piece? would remove then work?
        if value.__class__ is Tile:
            name2 = value.name2()
            for _ in self:
                if _.name2() == name2:
                    value = _
                    break
            else:
                raise ValueError('{} does not contain {!r}'.format(self, value))
        return TileList.remove(self, value)

# those two must come first

Tile.unknownStr = 'Xy'
Tile.unknown = Tile(Tile.unknownStr)
Tile.noneStr = 'Xx'
Tile.none = Tile(Tile.noneStr)

elements = Elements()
assert not Tile.unknown.isKnown
for wind in Wind.all4:
    wind.tile = Tile('w', wind.char.lower())


class Meld(TileTuple, ReprMixin):

    """represents a meld. Can be empty. Many Meld methods will
    raise exceptions if the meld is empty. But we do not care,
    those methods are not supposed to be called on empty melds.
    Meld is essentially a list of Tile with added methods.
    A Meld is immutable, not from the view of python but for
    its user

    for melds with 3 tiles::
        isDeclared == isExposed : 3 exposed tiles
        not isDeclared == isConcealed: 3 concealed Tiles
        exposed = aaa
        exposedClaimed = aaa

    for melds with 4 tiles::
        isKong = aAAa or aaaa or aaaA but NOT AAAA
        isDeclared = aAAa or aaaa or aaaA
        isExposed = aaaa or aaaA
        isConcealed = aAAa or AAAA
        exposedClaimed = aaaA
        exposed = aaaa

    """
    # pylint: disable=too-many-instance-attributes

    cache : Dict[Any, 'Meld'] = {}

    def __new__(cls, iterable=None):
        """try to use cache"""
        if isinstance(iterable, str) and iterable in cls.cache:
            return cls.cache[iterable]
        if isinstance(iterable, Meld):
            # brauchen wir das?
            return iterable
        superclass = TileTuple
        if hasattr(iterable, '__iter__') and not isinstance(iterable, str):
            iterable = list(iterable)
            if iterable:
                class1 = iterable[0].__class__
# FIXME: computeLastMelds may mix Piece and Tile, is that wanted?
                assert all(x.__class__ is class1 for x in iterable), repr(list(iterable))
                if class1 is Piece:
                    superclass = TileList
        tiles = super(Meld, cls).__new__(cls, superclass(iterable))
        if tiles in cls.cache:
            return cls.cache[tiles]
        return tiles

    def __init__(self, iterable=None):
        """init the meld: content can be either
        - a single string with 2 chars for every tile
        - a list containing such strings
        - another meld. Its tiles are not passed.
        - a list of Tile objects"""
        self.exposed:'Meld'
        if not hasattr(self, '_fixed'):  # already defined if I am from cache
            TileTuple.__init__(self, iterable)
            self.case = ''.join('a' if x.isExposed else 'A' for x in self)
            if self not in self.cache:
                self.cache[self] = self
                self.cache[str(self)] = self
            self.isExposed = self.__isExposed()
            self.isConcealed = not self.isExposed
            self.isSingle = self.isPair = self.isChow = self.isPung = False
            self.isKong = self.isClaimedKong = self.isKnitted = False
            self.isDragonMeld = len(self) and self[0].isDragon
            self.isWindMeld = len(self) and self[0].isWind
            self.isHonorMeld = self.isDragonMeld or self.isWindMeld
            self.isBonus = len(self) == 1 and self[0].isBonus
            self.isKnown = len(self) and self[0].isKnown
            self.__setMeldType()
            self.isPungKong = self.isPung or self.isKong
            self.isDeclared = self.isExposed or self.isKong
            groups = {x.group.lower() for x in self}
            if len(groups) == 1:
                self.group = self[0].group
                self.lowerGroup = self.group.lower()
            else:
                self.group = 'X'
                self.lowerGroup = 'x'
            self.isRest = False
            self.__staticRules = {}  # ruleset is key
            self.__dynamicRules = {}  # ruleset is key
            self.__staticDoublingRules = {}  # ruleset is key
            self.__dynamicDoublingRules = {}  # ruleset is key
            self.__hasRules = None  # unknown yet
            self.concealed = self.exposed = self.declared = self.exposedClaimed = None  # to satisfy pylint
            self._fixed = True

            if len(self) < 4:
                TileTuple.__setattr__(
                    self,
                    'concealed',
                    Meld(x.concealed for x in self))
                TileTuple.__setattr__(self, 'declared', self.concealed)
                TileTuple.__setattr__(
                    self,
                    'exposed',
                    Meld(x.exposed for x in self))
                TileTuple.__setattr__(self, 'exposedClaimed', self.exposed)
            else:
                TileTuple.__setattr__(
                    self,
                    'concealed',
                    Meld(x.concealed for x in self))
                TileTuple.__setattr__(
                    self, 'declared',
                    Meld([self[0].exposed, self[1].concealed, self[2].concealed, self[3].exposed]))
                TileTuple.__setattr__(
                    self,
                    'exposed',
                    Meld(x.exposed for x in self))
                TileTuple.__setattr__(
                    self, 'exposedClaimed',
                    Meld([self[0].exposed, self[1].exposed, self[2].exposed, self[3].concealed]))

    def __setattr__(self, name, value):
        if (hasattr(self, '_fixed')
                and not name.endswith('__hasRules')):
            raise TypeError
        TileTuple.__setattr__(self, name, value)

    def __prepareRules(self, ruleset):
        """prepare rules from ruleset"""
        rulesetId = id(ruleset)
        self.__staticRules[rulesetId] = [
            x for x in ruleset.meldRules
            if not hasattr(x, 'mayApplyToMeld') and x.appliesToMeld(None, self)]
        self.__dynamicRules[rulesetId] = [
            x for x in ruleset.meldRules
            if hasattr(x, 'mayApplyToMeld') and x.mayApplyToMeld(self)]
        self.__hasRules = any(len(x) for x in chain(
            self.__staticRules.values(), self.__dynamicRules.values()))

        self.__staticDoublingRules[rulesetId] = [
            x for x in ruleset.doublingMeldRules
            if not hasattr(x, 'mayApplyToMeld') and x.appliesToMeld(None, self)]
        self.__dynamicDoublingRules[rulesetId] = [x for x in ruleset.doublingMeldRules
                                                  if hasattr(x, 'mayApplyToMeld') and x.mayApplyToMeld(self)]

    def rules(self, hand):
        """all applicable rules for this meld being part of hand"""
        if self.__hasRules is False:
            return []
        ruleset = hand.ruleset
        rulesetId = id(ruleset)
        if rulesetId not in self.__staticRules:
            self.__prepareRules(ruleset)
        result = self.__staticRules[rulesetId][:]
        result.extend(x for x in self.__dynamicRules[
            rulesetId] if x.appliesToMeld(hand, self))
        return result

    def doublingRules(self, hand):
        """all applicable doubling rules for this meld being part of hand"""
        ruleset = hand.ruleset
        rulesetId = id(ruleset)
        if rulesetId not in self.__staticRules:
            self.__prepareRules(ruleset)
        result = self.__staticDoublingRules[rulesetId][:]
        result.extend(x for x in self.__dynamicDoublingRules[
            rulesetId] if x.appliesToMeld(hand, self))
        return result

    def without(self, remove):
        """self without tile. The rest will be uppercased."""
        assert remove is not None, 'without(None) is illegal'
        tiles = []
        for tile in self:
            if tile is remove:
                remove = None
            else:
                tiles.append(tile.concealed)
        assert remove is None, 'trying to remove {} from {}'.format(remove, self)
        return TileTuple(tiles)

    def __setitem__(self, index, value):
        """set a tile in the meld"""
        raise TypeError

    def __delitem__(self, index):
        """removes a tile from the meld"""
        raise TypeError

    def __isExposed(self):
        """meld state: exposed or not"""
        if self.case.islower():
            return True
        if len(self) == 4:
            return self.case[1:3].islower()
        return False

    def __setMeldType(self):
        """compute meld type. Except knitting melds."""
        # pylint: disable=too-many-branches,too-many-return-statements
        length = len(self)
        if length == 0:
            return
        if length > 4:
            raise UserWarning('Meld %s is too long' % str(self))
        if any(not x.isKnown for x in self):
            if len(set(self)) != 1:
                raise UserWarning(
                    'Meld %s: Cannot mix known and unknown tiles')
            self.isKnown = False
            return
        if length == 1:
            self.isSingle = True
            return
        if length == 2:
            if self[0] == self[1]:
                self.isPair = True
            elif self[0].value == self[1].value and self.case[0] == self.case[1] \
                    and all(x.lowerGroup in Tile.colors for x in self):
                self.isKnitted = True
            else:
                raise UserWarning('Meld %s is malformed' % str(self))
            return
        # now length is 3 or 4
        tiles = set(self)
        if len(tiles) == 1:
            if length == 3:
                self.isPung = True
            elif self.case != 'AAAA':
                self.isKong = True
            return
        if len(tiles) == 3 and length == 3:
            if len({x.value for x in tiles}) == 1:
                if self.case in ('aaa', 'AAA'):
                    if len({x.group for x in tiles}) == 3:
                        if all(x.lowerGroup in Tile.colors for x in tiles):
                            self.isKnitted = True
                            return
        groups = {x.group for x in self}
        if len(groups) > 2 or len({x.lower() for x in groups}) > 1:
            raise UserWarning('Meld %s is malformed' % str(self))
        values = {x.value for x in self}
        if length == 4:
            if len(values) > 1:
                raise UserWarning('Meld %s is malformed' % str(self))
            if self.case == 'aaaA':
                self.isKong = self.isClaimedKong = True
            elif self.case == 'aAAa':
                self.isKong = True
            else:
                raise UserWarning('Meld %s is malformed' % str(self))
            return
        # only possibilities left are CHOW and REST
        # length is 3
        if len(groups) == 1:
            if groups.pop().lower() in Tile.colors:
                if self[0].nextForChow is self[1] and self[1].nextForChow is self[2]:
                    self.isChow = True
                    return
        raise UserWarning('Meld %s is malformed' % str(self))

    def __lt__(self, other):
        """used for sorting. Smaller value is shown first."""
        if not other:
            return False
        if not self:
            return True
        if self.isDeclared and not other.isDeclared:
            return True
        if not self.isDeclared and other.isDeclared:
            return False
        if self[0].key == other[0].key:
            return len(self) > len(other)
        return self[0].key < other[0].key

    def typeName(self):
        """convert int to speaking name with shortcut. ATTENTION: UNTRANSLATED!"""
        # pylint: disable=too-many-return-statements
        if self.isBonus:
            return i18nc('kajongg meld type', 'Bonus')
        if self.isSingle:
            return i18nc('kajongg meld type', '&single')
        if self.isPair:
            return i18nc('kajongg meld type', '&pair')
        if self.isChow:
            return i18nc('kajongg meld type', '&chow')
        if self.isPung:
            return i18nc('kajongg meld type', 'p&ung')
        if self.isClaimedKong:
            return i18nc('kajongg meld type', 'c&laimed kong')
        if self.isKong:
            return i18nc('kajongg meld type', 'k&ong')
        return i18nc('kajongg meld type', 'rest of tiles')

    def __stateName(self):
        """the translated name of the state"""
        if self.isBonus or self.isClaimedKong:
            return ''
        if self.isExposed:
            return i18nc('kajongg meld state', 'Exposed')
        return i18nc('kajongg meld state', 'Concealed')

    def name(self):
        """the long name"""
        result = i18nc(
            'kajongg meld name, do not translate parameter names',
            '{state} {meldType} {name}')
        return result.format(
            state=self.__stateName(),
            meldType=self.typeName(),
            name=self[0].name()).replace('  ', ' ').strip()

    @staticmethod
    def cacheMeldsInTiles():
        """define all usual melds as Tile attributes"""
        Tile.unknown.single = Meld(Tile.unknown)
        Tile.unknown.pung = Meld(Tile.unknown * 3)
        do_those = list(elements.occurrence.keys())
        for tile in do_those:
            tile.cacheMelds()

    def __repr__(self):
        """because TileTuple.__repr__ does not indicate class Meld"""
        return 'Meld({}'.format(TileTuple.__repr__(self))


class MeldList(list):

    """a list of melds"""

    def __init__(self, newContent=None):
        list.__init__(self)
        if newContent is None:
            return
        if isinstance(newContent, Meld):
            list.append(self, newContent)
        elif isinstance(newContent, (list, GeneratorType)):
            # I tried hasattr('__iter__') but that does not work
            list.extend(self, newContent)
        elif isinstance(newContent, str):
            list.extend(self, [Meld(x)
                               for x in newContent.split()])
        else:
            list.extend(self, [Meld(x) for x in newContent])
        self.sort()

    def extend(self, values):
        list.extend(self, values)
        self.sort()

    def append(self, value):
        list.append(self, value)
        self.sort()

    def tiles(self):
        """flat view of all tiles in all melds"""
        return TileTuple(self)

    def __str__(self):
        if self:
            return ' '.join(str(x) for x in self)
        return ''

Meld.cacheMeldsInTiles()
