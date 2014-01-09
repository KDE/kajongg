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

from __future__ import print_function

from log import m18n, m18nc, logException
from common import IntDict

class Tile(str):
    """a single tile"""
    # pylint: disable=too-many-public-methods, abstract-class-not-used, too-many-instance-attributes
    cache = {}
    # TODO: try hashTable as dict: return idx for name
    hashTable = 'XyxyDbdbDgdgDrdrWeweWswsWw//wwWnwn' \
                'S/s/S0s0S1s1S2s2S3s3S4s4S5s5S6s6S7s7S8s8S9s9S:s:S;s;' \
                'B/b/B0b0B1b1B2b2B3b3B4b4B5b5B6b6B7b7B8b8B9b9B:b:B;b;' \
                'C/c/C0c0C1c1C2c2C3c3C4c4C5c5C6c6C7c7C8c8C9c9C:c:C;c;' \
                'fefsfwfnyeysywyn'
        # the // is needed as separator between too many w's
        # intelligence.py will define Tile('b0') or Tile('s:')
    unknown = None
    hidden = 'x'
    stone = 's'
    bamboo = 'b'
    character = 'c'
    colors = stone + bamboo + character
    wind = 'w'
    dragon = 'd'
    white = 'b'
    green = 'g'
    red = 'r'
    dragons = white + green + red
    honors = wind + dragon
    minors = '2345678'
    terminals = '19'
    numbers = '123456789'
    majors = honors + terminals
    east = 'e'
    south = 's'
    west = 'w'
    north = 'n'
    winds = east + south + west + north
    flower = 'f'
    season = 'y'
    boni = flower + season

    def __new__(cls, *args):
        if isinstance(args[0], Tile):
            return args[0]
        if args not in cls.cache:
            arg0 = args[0]
            if len(args) == 1:
                arg0, arg1 = args[0]
            else:
                arg0, arg1 = args
            if isinstance(arg0, int):
                arg0 = chr(arg0)
            if isinstance(arg1, int):
                arg1 = chr(arg1)
            what = arg0 + arg1
            cls.cache[args] = str.__new__(cls, what)
        return cls.cache[args]

    def __init__(self, *dummyArgs):
        # pylint: disable=super-init-not-called
        if not hasattr(self, '_fixed'): # already defined if I am from cache
            self.group, self.value = self
            self.lowerGroup = self.group.lower()
            self.isExposed = self.group == self.lowerGroup
            self.isBonus = self.group in Tile.boni
            self.isDragon = self.lowerGroup == Tile.dragon
            self.isWind = self.lowerGroup == Tile.wind
            self.isHonor = self.isDragon or self.isWind
            self.isTerminal = self.value in Tile.terminals

            if self.isHonor or self.isBonus:
                self.isReal = True
            else:
                self.isReal = self.value in Tile.numbers
            self.isMajor = self.isHonor or self.isTerminal
            self.isMinor = not self.isMajor
            try:
                self.key = 1 + self.hashTable.index(self) / 2
            except ValueError:
                logException('%s is not a valid tile string' % self)
            self.isKnown = Tile.unknown is not None and self != Tile.unknown
            self._fixed = True

    def __setattr__(self, name, value):
        if hasattr(self, '_fixed'):
            raise TypeError
        str.__setattr__(self, name, value)

    def __getitem__(self, index):
        if hasattr(self, '_fixed'):
            raise TypeError
        return str.__getitem__(self, index)

    def __setitem__(self, index, value):
        raise TypeError

    def __delitem__(self, index):
        raise TypeError

    def lower(self):
        """return exposed element name"""
        return Tile(str.lower(self))

    def upper(self):
        """return hidden element name"""
        if self.isBonus:
            return self
        return Tile(str.capitalize(self))

    def capitalize(self):
        """return hidden element name. Just make sure we get a real Tile even
        if we call this"""
        return self.upper()

    def swapTitle(self):
        """if istitle, return lower. If lower, return capitalize"""
        if self.islower():
            return self.upper()
        else:
            return self.lower()

    def nextForChow(self):
        """the following tile for a chow"""
        return Tile(self.group, ord(self.value) + 1)

    def __repr__(self):
        """default representation"""
        return 'Tile(%s)' % str(self)

    def groupName(self):
        """the name of the group this tile is of"""
        names = {Tile.hidden:m18nc('kajongg','hidden'), Tile.stone: m18nc('kajongg','stone'),
            Tile.bamboo: m18nc('kajongg','bamboo'), Tile.character:m18nc('kajongg','character'),
            Tile.wind:m18nc('kajongg','wind'), Tile.dragon:m18nc('kajongg','dragon'),
            Tile.flower:m18nc('kajongg','flower'), Tile.season:m18nc('kajongg','season')}
        return names[self.lowerGroup]

    def valueName(self):
        """the name of the value this tile has"""
        names = {'y':m18nc('kajongg','tile'), Tile.white:m18nc('kajongg','white'),
            Tile.red:m18nc('kajongg','red'), Tile.green:m18nc('kajongg','green'),
            Tile.east:m18nc('kajongg','East'), Tile.south:m18nc('kajongg','South'), Tile.west:m18nc('kajongg','West'),
            Tile.north:m18nc('kajongg','North'),
            '1':'1', '2':'2', '3':'3', '4':'4', '5':'5', '6':'6', '7':'7', '8':'8', '9':'9'}
        return names[self.value]

    def name(self):
        """returns name of a single tile"""
        if self.group.lower() == Tile.wind:
            result = {Tile.east:m18n('East Wind'), Tile.south:m18n('South Wind'),
                Tile.west:m18n('West Wind'), Tile.north:m18n('North Wind')}[self.value]
        else:
            result = m18nc('kajongg tile name', '{group} {value}')
        return result.format(value=self.valueName(), group=self.groupName())

    def __lt__(self, other):
        """needed for sort"""
        return self.key < other.key

class TileList(list):
    """a list that can only hold tiles"""
    def __init__(self, newContent=None):
        list.__init__(self)
        if newContent is None:
            return
        if newContent.__class__.__name__ == 'generator':
            newContent = list(newContent)
        if isinstance(newContent, list) and newContent and hasattr(newContent[0], 'focusable'):
            self.extend(x.tile for x in newContent)
        elif isinstance(newContent, (list, tuple, set)):
            list.extend(self, [Tile(x) for x in newContent])
        elif isinstance(newContent, Tile):
            list.append(self, newContent)
        elif hasattr(newContent, 'tile'):
            list.append(self, newContent.tile) # pylint: disable=E1103
        else:
            assert isinstance(newContent, str), '%s:%s' % (type(newContent), newContent)
            assert len(newContent) % 2 == 0, newContent
            list.extend(self, [Tile(newContent[x:x+2]) for x in range(0, len(newContent), 2)])
        for tile in self:
            assert isinstance(tile, Tile), self
        self.isRest = True

    def key(self):
        """usable for sorting"""
        result = 0
        factor = len(Tile.hashTable) / 2
        for tile in self:
            result = result * factor + tile.key
        return result

    def sorted(self):
        """sort(TileList) would not keep TileList type"""
        return TileList(sorted(self))

    def toLower(self, first=None, last=None):
        """use first and last as for ranges"""
        if first is not None:
            if last is None:
                self[first] = self[first].lower()
                return self
        else:
            assert last is None
            first, last = 0, len(self)
        for idx in range(first, last):
            self[idx] = self[idx].lower()
        return self

    def toUpper(self, first=None, last=None):
        """use first and last as for ranges"""
        if first is not None:
            if last is None:
                self[first] = self[first].capitalize()
                return self
        else:
            assert last is None
            first, last = 0, len(self)
        for idx in range(first, last):
            self[idx] = self[idx].capitalize()
        return self

    def isLower(self, first=None, last=None):
        """use first and last as for ranges"""
        if first is not None:
            if last is None:
                return self[first].islower()
        else:
            assert last is None
            first, last = 0, len(self)
        return ''.join(self[first:last]).islower()

    def isUpper(self, first=None, last=None):
        """use first and last as for ranges"""
        if first is not None:
            if last is None:
                return self[first].istitle()
        else:
            assert last is None
            first, last = 0, len(self)
        return all(self[x].istitle() for x in range(first, last))

    def hasChows(self, tile):
        """returns my chows with tileName"""
        if tile not in self:
            return []
        if tile.lowerGroup not in Tile.colors:
            return []
        group = tile.group
        value = ord(tile.value)
        values = set(ord(x.value) for x in self if x.group == group)
        chows = []
        for offsets in [(0, 1, 2), (-2, -1, 0), (-1, 0,  1)]:
            subset = set([value + x for x in offsets])
            if subset <= values:
                chow = TileList(Tile(group, x) for x in sorted(subset))
                if chow not in chows:
                    chows.append(chow)
        return chows

    def __str__(self):
        """the content"""
        return str(''.join(self))

class Elements(object):
    """represents all elements"""
    # pylint: disable=too-many-instance-attributes
    # too many attributes
    def __init__(self):
        self.occurrence = IntDict() # key: db, s3 etc. value: occurrence
        self.winds = {Tile(Tile.wind, x) for x in Tile.winds}
        self.wINDS = {x.upper() for x in self.winds}
        self.dragons = {Tile(Tile.dragon, x) for x in Tile.dragons}
        self.dRAGONS = {x.upper() for x in self.dragons}
        self.honors = self.winds | self.dragons
        self.hONORS = self.wINDS | self.dRAGONS
        self.terminals = {Tile(x, y) for x in Tile.colors for y in Tile.terminals}
        self.tERMINALS = {x.upper() for x in self.terminals}
        self.majors = self.honors | self.terminals
        self.mAJORS = self.hONORS | self.tERMINALS
        self.greenHandTiles = {Tile(Tile.bamboo, x) for x in '23468'} | {Tile(Tile.dragon, Tile.green)}
        self.minors = {Tile(x, y) for x in Tile.colors for y in Tile.minors}
        for tile in self.majors:
            self.occurrence[tile] = 4
        for tile in self.minors:
            self.occurrence[tile] = 4
        for bonus in Tile.boni:
            for wind in Tile.winds:
                self.occurrence[Tile(bonus, wind)] = 1

    def __filter(self, ruleset):
        """returns element names"""
        return (x for x in self.occurrence if ruleset.withBonusTiles or (not x.isBonus))

    def count(self, ruleset):
        """how many tiles are to be used by the game"""
        return self.occurrence.count(self.__filter(ruleset))

    def all(self, ruleset):
        """a list of all elements, each of them occurrence times"""
        return self.occurrence.all(self.__filter(ruleset))

Tile.unknown = Tile('Xy') # must come first
elements = Elements()  # pylint: disable=invalid-name
assert not Tile.unknown.isKnown
