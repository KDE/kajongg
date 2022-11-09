# -*- coding: utf-8 -*-

"""
 Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

from log import logException
from mi18n import i18n, i18nc
from common import IntDict, ReprMixin
from wind import Wind, East, South, West, North

class Tile(str, ReprMixin):

    """
    A single tile, represented as a string of length 2.

    Always True:
      - only for suits: tile.group + chr(tile.value + 48) == str(tile)
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
        try:
            return cls.cache[args]
        except KeyError:
            return cls.__build(*args)

    @classmethod
    def __build(cls, *args):
        """build a new Tile object out of args"""
        # pylint: disable=too-many-statements
        if len(args) == 1:
            arg0, arg1 = args[0]
        else:
            arg0, arg1 = args
        if isinstance(arg1, int):
            arg1 = chr(arg1 + 48)
        what = arg0 + arg1
        result = str.__new__(cls, what)
        result.group = result[0]

        result.isKnown = result.group != 'X'
        result.lowerGroup = result.group.lower()
        result.isExposed = result.group == result.lowerGroup
        result.isConcealed = not result.isExposed
        result.isBonus = result.group in Tile.boni
        result.isDragon = result.lowerGroup == Tile.dragon
        result.isWind = result.lowerGroup == Tile.wind
        result.isHonor = result.isDragon or result.isWind

        if result.isBonus or result.isWind:
            result.value = Wind(result[1])
            result.char = result[1]
        elif result.isDragon:
            result.value = result[1]
            result.char = result.value
        else:
            result.value = ord(result[1]) - 48
            result.char = result.value

        result.isTerminal = False
        result.isNumber = False
        result.isReal = False

        if result.isBonus or result.isDragon or result.isWind:
            result.isReal = True
        elif result.isKnown:
            result.isNumber = True
            result.isTerminal = result.value in Tile.terminals
            result.isReal = result.value in Tile.numbers

        result.isMajor = result.isHonor or result.isTerminal
        result.isMinor = result.isKnown and not result.isMajor
        try:
            result.key = 1 + result.hashTable.index(result) // 2
        except ValueError:
            logException('%s is not a valid tile string' % result)

        Tile._storeInCache(result)

        result.exposed = result.concealed = result.swapped = None
        result.single = result.pair = result.pung = None
        result.chow = result.kong = None
        result._fixed = True

        str.__setattr__(
            result,
            'exposed',
            result if not result.isKnown else Tile(result.group.lower(), result.char))
        object.__setattr__(result, 'concealed',
                        result if not result.isKnown or result.isBonus
                        else Tile(result.group.upper(), result.char))
        object.__setattr__(
            result,
            'swapped',
            result.exposed if result.isConcealed else result.concealed)
        if isinstance(result.value, int):
            if 0 <= result.value <= 11:
                str.__setattr__(
                    result,
                    'prevForChow',
                    Tile(result.group,
                         result.value - 1))
            if -1 <= result.value <= 10:
                str.__setattr__(
                    result,
                    'nextForChow',
                    Tile(
                        result.group,
                        result.value +
                        1))

        return result

    @classmethod
    def _storeInCache(cls, result):
        """Put the new tile into the cache"""
        for key in (
                result, (str(result),), (result.group, result.value),
                (result[0], result[1])):
            cls.cache[key] = result

        existing = list([x for x in cls.cache.values() if x.key == result.key]) # pylint: disable=consider-using-generator
        existingIds = {id(x) for x in existing}
        assert len(existingIds) == 1, 'new is:{} existing are: {} with ids {}'.format(result, existing, existingIds)

    def name2(self):
        """__str__ might be changed by a subclass"""
        return self.group + str(self.char)

    def __repr__(self):
        """ReprMixin does not seem to work on str subclass"""
        return ReprMixin.__repr__(self)

    def __getitem__(self, index):
        if hasattr(self, '_fixed'):
            raise TypeError
        return str.__getitem__(self, index)

    def __setitem__(self, index, value):
        raise TypeError

    def __delitem__(self, index):
        raise TypeError

    def lower(self):
        raise TypeError

    def istitle(self):
        raise TypeError
    def __mul__(self, other):
        return [self] * other


    def upper(self):
        raise TypeError

    def capitalize(self):
        raise TypeError
    def __imul__(self, other):
        return [self] * other


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


class TileList(list):

    """a list that can only hold tiles"""

    def __init__(self, newContent=None):
        list.__init__(self)
        if newContent is None:
            return
        if isinstance(newContent, Tile):
            list.append(self, newContent)
        elif isinstance(newContent, str):
            list.extend(
                self, [Tile(newContent[x:x + 2])
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
                chow = TileList(Tile(group, x) for x in sorted(subset))
                if chow not in chows:
                    chows.append(chow)
        return chows

    def __str__(self):
        """the content"""
        return str(''.join(self))


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
