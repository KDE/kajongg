# -*- coding: utf-8 -*-

"""
 Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

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
    hashTable = 'XyxyDbdbDgdgDrdrWeweWswsWw//wwWnwn' \
                'S/s/S0s0S1s1S2s2S3s3S4s4S5s5S6s6S7s7S8s8S9s9S:s:S;s;' \
                'B/b/B0b0B1b1B2b2B3b3B4b4B5b5B6b6B7b7B8b8B9b9B:b:B;b;' \
                'C/c/C0c0C1c1C2c2C3c3C4c4C5c5C6c6C7c7C8c8C9c9C:c:C;c;' \
                'fefsfwfnyeysywyn'
    # the // is needed as separator between too many w's
    # intelligence.py will define Tile('b0') or Tile('s:')

    unknown = None

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
        elif self.group.lower() == 'x':
            char = 'y'
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
        return getattr(self, ('single', 'pair', 'pung', 'kong')[size - 1])

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
        if element is None:
            return self
        assert element.__class__ is Tile, repr(element)
        return element

    def __eq__(self, other):
        if isinstance(other, Tile):
            return self.name2() == other.name2()
        return object.__eq__(self, other)


class TileList(list):

    """a list that can only hold tiles"""

    tileClass = Tile

    def __init__(self, newContent=None):
        list.__init__(self)
        if newContent is None:
            return
        if isinstance(newContent, self.tileClass):
            list.append(self, newContent)
        elif isinstance(newContent, str):
            list.extend(
                self, [self.tileClass(newContent[x:x + 2])
                       for x in range(0, len(newContent), 2)])
        else:
            list.extend(self, newContent)
        self.isRest = True

    def key(self):
        """usable for sorting"""
        result = 0
        factor = len(Tile.hashTable) // 2
        for tile in self:
            result = result * factor + tile.key
        return result

    def __hash__(self):
        return self.key()

    def sorted(self):
        """sort(TileList) would not keep TileList type"""
        return TileList(sorted(self))

    def hasChows(self, tile):
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

class TileTuple(tuple):

    """a list that can only hold tiles"""

    tileClass = Tile

    def __new__(cls, iterable=None):
        if isinstance(iterable, str):
            memberList = [cls.tileClass(iterable[x:x + 2])
                       for x in range(0, len(iterable), 2)]
        elif isinstance(iterable, Tile):
            memberList = [iterable]
        elif iterable is None:
            memberList = []
        else:
            memberList = []
            for member in iterable:
                if isinstance(member, cls.tileClass):
                    memberList.append(member)
                elif isinstance(member, str):
                    memberList = [cls.tileClass(member[x:x + 2])
                               for x in range(0, len(member), 2)]
                elif hasattr(member, '__iter__'):
                    memberList.extend(member)
                else:
                    raise ValueError(
                        'TileTuple() accepts only {} and str but got {}'.format(cls.tileClass.__name__, repr(member)))
        result = tuple.__new__(cls, memberList)
        result.isRest = True
        result._hash = result._compute_hash()
        return result

    def __init__(self, iterable=None):  # pylint: disable=unused-argument
        tuple.__init__(self)

    def _compute_hash(self):
        """usable for sorting"""
        result = 0
        factor = len(Tile.hashTable) // 2
        for tile in self:
            assert isinstance(tile, Tile), 'tile is:{}'.format(repr(tile))
            result = result * factor + tile.key
        return result

    def __hash__(self):
        return self._hash

    def __add__(self, other):
        result = list(self)
        if isinstance(other, str):
            result.extend(
                [self.tileClass(other[x:x + 2])
                       for x in range(0, len(other), 2)])
        elif hasattr(other, '__iter__'):
            result.extend(other)
        else:
            result.append(other)
        return TileTuple(result)

    def sorted(self):
        """sort(TileTuple) would not keep TileTuple type"""
        return TileTuple(sorted(self))

    def hasChows(self, tile):
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


Tile.unknownStr = 'Xy'
Tile.unknown = Tile(Tile.unknownStr)  # must come first

elements = Elements()
assert not Tile.unknown.isKnown
for wind in Wind.all4:
    wind.tile = Tile('w', wind.char.lower())
