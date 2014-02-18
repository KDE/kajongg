# -*- coding: utf-8 -*-

"""Copyright (C) 2009-2014 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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



Read the user manual for a description of the interface to this scoring engine
"""


from itertools import chain

from log import m18nc
from tile import Tile, TileList, elements

class Meld(TileList):
    """represents a meld. Can be empty. Many Meld methods will
    raise exceptions if the meld is empty. But we do not care,
    those methods are not supposed to be called on empty melds.
    Meld is essentially a list of Tile with added methods.
    A Meld is immutable, not from the view of python but for
    its user

    for melds with 3 tiles:
        isDeclared == isExposed : 3 exposed tiles
        not isDeclared == isConcealed: 3 concealed Tiles
        exposed: aaa
        exposedClaimed: aaa

    for melds with 4 tiles:
        isKong = aAAa or aaaa or aaaA but NOT AAAA
        isDeclared = aAAa or aaaa or aaaA
        isExposed = aaaa or aaaA
        isConcealed: aAAa or AAAA
        exposedClaimed: aaaA
        exposed: aaaa

    """
    # pylint: disable=too-many-instance-attributes

    __hash__ = None
    cache = {}
    def __new__(cls, newContent=None):
        """try to use cache"""
        if isinstance(newContent, str):
            if newContent in cls.cache:
                return cls.cache[newContent]
        elif isinstance(newContent, Meld):
            return newContent
        tiles = TileList(newContent)
        cacheKey = tiles.key()
        if cacheKey in cls.cache:
            return cls.cache[cacheKey]
        return TileList.__new__(cls, tiles)

    @classmethod
    def check(cls):
        """check cache consistency"""
        for key, value in cls.cache.items():
            assert key == value.key or key == str(value), 'cache wrong: cachekey=%s realkey=%s value=%s' % (
                key, value.key, value)
            assert value.key == 1 + value.hashTable.index(value) / 2
            assert value.key == TileList.key(value), \
                'static key:%s current key:%s, static value:%s, current value:%s ' % (
                value.key, TileList.key(value), value.original, value)

    def __init__(self, newContent=None):
        """init the meld: content can be either
        - a single string with 2 chars for every tile
        - a list containing such strings
        - another meld. Its tiles are not passed.
        - a list of Tile objects"""
        if not hasattr(self, '_fixed'): # already defined if I am from cache
            TileList.__init__(self, newContent)
            self.case = ''.join('a' if x.islower() else 'A' for x in self)
            self.key = TileList.key(self)
            if self.key not in self.cache:
                self.cache[self.key] = self
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
            groups = set(x.group.lower() for x in self)
            if len(groups) == 1:
                self.group = self[0].group
                self.lowerGroup = self.group.lower()
            else:
                self.group = 'X'
                self.lowerGroup = 'x'
            self.isRest = False
            self.__staticRules = {} # ruleset is key
            self.__dynamicRules = {} # ruleset is key
            self.__staticDoublingRules = {} # ruleset is key
            self.__dynamicDoublingRules = {} # ruleset is key
            self.__hasRules = None # unknown yet
            self.__hasDoublingRules = None # unknown yet
            self.concealed = self.exposed = self.declared = self.exposedClaimed = None # to satisfy pylint
            self._fixed = True

            if len(self) < 4:
                TileList.__setattr__(self, 'concealed', Meld(TileList(x.concealed for x in self)))
                TileList.__setattr__(self, 'declared', self.concealed)
                TileList.__setattr__(self, 'exposed', Meld(TileList(x.exposed for x in self)))
                TileList.__setattr__(self, 'exposedClaimed', self.exposed)
            else:
                TileList.__setattr__(self, 'concealed', Meld(TileList(x.concealed for x in self)))
                TileList.__setattr__(self, 'declared',
                    Meld(TileList([self[0].exposed, self[1].concealed, self[2].concealed, self[3].exposed])))
                TileList.__setattr__(self, 'exposed', Meld(TileList(x.exposed for x in self)))
                TileList.__setattr__(self, 'exposedClaimed',
                    Meld(TileList([self[0].exposed, self[1].exposed, self[2].exposed, self[3].concealed])))

    def __setattr__(self, name, value):
        if (hasattr(self, '_fixed')
            and not name.endswith('__hasRules')
            and not name.endswith('__hasDoublingRules')):
            raise TypeError
        TileList.__setattr__(self, name, value)

    def __prepareRules(self, ruleset):
        """prepare rules from ruleset"""
        rulesetId = id(ruleset)
        self.__staticRules[rulesetId] = list(x for x in ruleset.meldRules
            if not hasattr(x, 'mayApplyToMeld') and x.appliesToMeld(None, self))
        self.__dynamicRules[rulesetId] = list(x for x in ruleset.meldRules
            if hasattr(x, 'mayApplyToMeld') and x.mayApplyToMeld(self))
        self.__hasRules = any(len(x) for x in chain(
            self.__staticRules.values(), self.__dynamicRules.values()))

        self.__staticDoublingRules[rulesetId] = list(x for x in ruleset.doublingMeldRules
            if not hasattr(x, 'mayApplyToMeld') and x.appliesToMeld(None, self))
        self.__dynamicDoublingRules[rulesetId] = list(x for x in ruleset.doublingMeldRules
            if hasattr(x, 'mayApplyToMeld') and x.mayApplyToMeld(self))
        self.__hasDoublingRules = any(len(x) for x in chain(
            self.__staticDoublingRules.values(), self.__dynamicDoublingRules.values()))

    def rules(self, hand):
        """all applicable rules for this meld being part of hand"""
        if self.__hasRules is False:
            return []
        ruleset = hand.ruleset
        rulesetId = id(ruleset)
        if rulesetId not in self.__staticRules:
            self.__prepareRules(ruleset)
        result = self.__staticRules[rulesetId][:]
        result.extend(x for x in self.__dynamicRules[rulesetId] if x.appliesToMeld(hand, self))
        return result

    def doublingRules(self, hand):
        """all applicable doubling rules for this meld being part of hand"""
        ruleset = hand.ruleset
        rulesetId = id(ruleset)
        if rulesetId not in self.__staticRules:
            self.__prepareRules(ruleset)
        result = self.__staticDoublingRules[rulesetId][:]
        result.extend(x for x in self.__dynamicDoublingRules[rulesetId] if x.appliesToMeld(hand, self))
        return result

    def append(self, dummy):
        """we want to be immutable"""
        raise TypeError

    def extend(self, dummy):
        """we want to be immutable"""
        raise TypeError

    def insert(self, dummy):
        """we want to be immutable"""
        raise TypeError

    def pop(self, dummy):
        """we want to be immutable"""
        raise TypeError

    def remove(self, dummy):
        """we want to be immutable"""
        raise TypeError

    def without(self, remove):
        """self without tile. The rest will be uppercased."""
        tiles = TileList()
        for tile in self:
            if tile is remove:
                remove = None
            else:
                tiles.append(tile.concealed)
        return tiles

    def __setitem__(self, index, value):
        """sets a tile in the meld"""
        raise TypeError

    def __delitem__(self, index):
        """removes a tile from the meld"""
        raise TypeError

    def __isExposed(self):
        """meld state: exposed or not"""
        if self.case.islower():
            return True
        elif len(self) == 4:
            return self.case[1:3].islower()
        else:
            return False

    def __setMeldType(self):
        """compute meld type. Except knitting melds."""
        # pylint: disable=too-many-branches,too-many-return-statements
        length = len(self)
        if length == 0:
            return
        if length > 4:
            raise UserWarning('Meld %s is too long' % self)
        if any(not x.isKnown for x in self):
            if len(set(self)) != 1:
                raise UserWarning('Meld %s: Cannot mix known and unknown tiles')
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
                raise UserWarning('Meld %s is malformed' % self)
            return
        # now length is 3 or 4
        tiles = set(self)
        if len(tiles) == 1:
            if length == 3:
                self.isPung = True
            else:
                self.isKong = True
            return
        if len(tiles) == 3 and length == 3:
            if len(set(x.value for x in tiles)) == 1:
                if self.case in ('aaa', 'AAA'):
                    if len(set(x.group for x in tiles)) == 3:
                        if all(x.lowerGroup in Tile.colors for x in tiles):
                            self.isKnitted = True
                            return
        groups = set(x.group for x in self)
        if len(groups) > 2 or len(set(x.lower() for x in groups)) > 1:
            raise UserWarning('Meld %s is malformed' % self)
        values = set(x.value for x in self)
        if length == 4:
            if len(values) > 1:
                raise UserWarning('Meld %s is malformed' % self)
            if self.case == 'aaaA':
                self.isKong = self.isClaimedKong = True
            elif self.case == 'aAAa':
                self.isKong = True
            else:
                raise UserWarning('Meld %s is malformed' % self)
            return
        # only possibilities left are CHOW and REST
        # length is 3
        if len(groups) == 1:
            if groups.pop().lower() in Tile.colors:
                if self[0].nextForChow is self[1] and self[1].nextForChow is self[2]:
                    self.isChow = True
                    return
        raise UserWarning('Meld %s is malformed' % self)

    def __lt__(self, other):
        """used for sorting. Smaller value is shown first."""
        if len(other) == 0:
            return False
        if len(self) == 0:
            return True
        if self.isDeclared and not other.isDeclared:
            return True
        if not self.isDeclared and other.isDeclared:
            return False
        if self[0].key == other[0].key:
            return len(self) > len(other)
        return self[0].key < other[0].key

    def __repr__(self):
        """the default representation"""
        return 'Meld(%s)' % str(self)

    def typeName(self):
        """convert int to speaking name with shortcut. ATTENTION: UNTRANSLATED!"""
        # pylint: disable=too-many-return-statements
        if self.isBonus:
            return m18nc('kajongg meld type', 'Bonus')
        elif self.isSingle:
            return m18nc('kajongg meld type', '&single')
        elif self.isPair:
            return m18nc('kajongg meld type', '&pair')
        elif self.isChow:
            return m18nc('kajongg meld type', '&chow')
        elif self.isPung:
            return m18nc('kajongg meld type', 'p&ung')
        elif self.isClaimedKong:
            return m18nc('kajongg meld type', 'c&laimed kong')
        elif self.isKong:
            return m18nc('kajongg meld type', 'k&ong')
        else:
            return m18nc('kajongg meld type', 'rest of tiles')

    def __stateName(self):
        """the translated name of the state"""
        if self.isBonus or self.isClaimedKong:
            return ''
        elif self.isExposed:
            return m18nc('kajongg meld state', 'Exposed')
        else:
            return m18nc('kajongg meld state', 'Concealed')

    def name(self):
        """the long name"""
        result = m18nc('kajongg meld name, do not translate parameter names', '{state} {meldType} {name}')
        return result.format(
            state=self.__stateName(),
            meldType=self.typeName(),
            name=self[0].name()).replace('  ', ' ').strip()

    @staticmethod
    def cacheMeldsInTiles():
        """define all usual melds as Tile attributes"""
        Tile.unknown.single = Meld(Tile.unknown)
        Tile.unknown.pung = Meld(Tile.unknown * 3)
        for tile, occ in elements.occurrence.items():
            tile.single = Meld(tile)
            tile.concealed.single = Meld(tile.concealed)
            if occ > 1:
                tile.pair = Meld(tile * 2)
                tile.concealed.pair = Meld(tile.concealed * 2)
                if occ > 2:
                    tile.pung = Meld(tile * 3)
                    tile.concealed.pung = Meld(tile.concealed * 3)
                    if tile.value in range(1, 8):
                        tile.chow = Meld([tile, tile.nextForChow, tile.nextForChow.nextForChow])
                        tile.concealed.chow = Meld([tile.concealed, tile.nextForChow.concealed,
                            tile.nextForChow.nextForChow.concealed])
                    if tile.value in range(1, 10):
                        tile.knitted3 = Meld([Tile(x, tile.value) for x in Tile.colors])
                        tile.concealed.knitted3 = Meld([Tile(x, tile.value).concealed for x in Tile.colors])
                    if occ > 3:
                        tile.kong = Meld(tile * 4)
                        tile.claimedKong = Meld([tile, tile, tile, tile.concealed])
                        tile.concealed.kong = Meld(tile.concealed * 4)

class MeldList(list):
    """a list of melds"""
    def __init__(self, newContent=None):
        list.__init__(self)
        if newContent is None:
            return
        if isinstance(newContent, Meld):
            list.append(self, newContent)
        elif isinstance(newContent, str):
            list.extend(self, [Meld(x) for x in newContent.split()]) # pylint: disable=maybe-no-member
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
        return TileList(sum(self, []))

    def __str__(self):
        if len(self):
            return ' '.join(str(x) for x in self)
        else:
            return ''

Meld.cacheMeldsInTiles()
