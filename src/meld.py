# -*- coding: utf-8 -*-

"""Copyright (C) 2009-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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




from log import m18nc
from tile import Tile, TileList

def meldsContent(melds):
    """return content of melds"""
    return b' '.join([bytes(meld) for meld in melds])

class Meld(TileList):
    """represents a meld. Can be empty. Many Meld methods will
    raise exceptions if the meld is empty. But we do not care,
    those methods are not supposed to be called on empty melds.
    Meld is essentially a list of Tile with added methods.
    A Meld is immutable, not from the view of python but for
    its user"""
    # pylint: disable=too-many-instance-attributes

    __hash__ = None
    cache = {}
    def __new__(cls, newContent=None):
        """try to use cache"""
        if isinstance(newContent, (str, bytes)):
            if newContent in cls.cache:
                return cls.cache[newContent]
        if isinstance(newContent, Meld):
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
            assert key == value.key or key == bytes(value), 'cache wrong: cachekey=%s realkey=%s value=%s' % (
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
            assert len(self) < 5, newContent
            self.key = TileList.key(self)
            if self.key not in self.cache:
                self.cache[self.key] = self
                self.cache[bytes(self)] = self
            self.isExposed = self.__getState()
            self.tileType = self[0].lowerGroup if len(self) else None
            self.isSingle = self.isPair = self.isChow = self.isPung = False
            self.isKong = self.isClaimedKong = self.isRest = False
            self.__setMeldType()
            self._fixed = True

    def __setattr__(self, name, value):
        if hasattr(self, '_fixed'):
            raise TypeError
        TileList.__setattr__(self, name, value)

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
        """self without tile"""
        tiles = TileList()
        for tile in self:
            if tile == remove:
                remove = None
            else:
                tiles.append(tile)
        return Meld(tiles)

    def toLower(self, first=None, last=None):
        """use first and last as for ranges"""
        return Meld(TileList(self).toLower(first, last))

    def toUpper(self, first=None, last=None):
        """use first and last as for ranges"""
        return Meld(TileList(self).toUpper(first, last))

    def __setitem__(self, index, value):
        """sets a tile in the meld"""
        raise TypeError

    def __delitem__(self, index):
        """removes a tile from the meld"""
        raise TypeError

    def __getState(self):
        """meld state"""
        firsts = b''.join(x.group for x in self)
        if firsts.islower():
            return True
        elif len(self) == 4 and firsts[1:3].isupper():
            return False
        elif len(self) == 4:
            return True
        else:
            return False

    def __setMeldType(self):
        """compute meld type. Except knitting melds."""
        # pylint: disable=too-many-branches,too-many-return-statements
        length = len(self)
        if any(not x.isKnown for x in self) or length > 4:
            self.isRest = True
            return
        if length == 1:
            self.isSingle = True
            return
        if length == 2:
            if self[0] == self[1]:
                self.isPair = True
            else:
                self.isRest = True
            return
        # now length is 3 or 4
        tiles = set(self)
        if len(tiles) == 1:
            if length == 3:
                self.isPung = True
            else:
                self.isKong = True
            return
        groups = set(x.group for x in self)
        if len(groups) > 2:
            self.isRest = True
            return
        if len(set(x.lower() for x in groups)) > 1:
            self.isRest = True
            return
        values = set(x.value for x in self)
        if length == 4:
            if len(values) > 1:
                self.isRest = True
            if self.isUpper():
                self.isRest = True
            elif self.isLower(0, 3) and self.isUpper(3):
                self.isKong = self.isClaimedKong = True
            elif self.isUpper(1, 3) and self.isLower(0) and self.isLower(3):
                self.isKong = True
            else:
                assert False, self
            return
        # only possibilities left are CHOW and REST
        # length is 3
        if len(groups) == 1:
            if groups.pop() in b'sbcSBC':
                values = list(ord(x.value) for x in self)
                if values[2] == values[0] + 2 and values[1] == values[0] + 1:
                    self.isChow = True
                    return
        self.isRest = True

    def expose(self, isClaiming):
        """expose this meld. For kungs, leave one or two concealed,
        showing how the kung was built"""
        tiles = TileList(self)
        if len(self) < 4:
            return Meld(tiles.toLower())
        elif isClaiming:
            return Meld(tiles.toLower(0, 3).toUpper(3))
        else: # concealed kong
            return Meld(tiles.toLower(0).toUpper(1, 3).toLower(3))

    def __lt__(self, other):
        """used for sorting"""
        return self.key < other.key

    def __bytes__(self):
        return b''.join(self)

    def __repr__(self):
        """the default representation"""
        return 'Meld(%s)' % str(self)

    def typeName(self):
        """convert int to speaking name with shortcut. ATTENTION: UNTRANSLATED!"""
        # pylint: disable=too-many-return-statements
        if self[0].isBonus:
            return m18nc('kajongg meld type', 'Bonus')
        elif self.isSingle:
            return m18nc('kajongg meld type','&single')
        elif self.isPair:
            return m18nc('kajongg meld type','&pair')
        elif self.isChow:
            return m18nc('kajongg meld type','&chow')
        elif self.isPung:
            return m18nc('kajongg meld type','p&ung')
        elif self.isClaimedKong:
            return m18nc('kajongg meld type','c&laimed kong')
        elif self.isKong:
            return m18nc('kajongg meld type','k&ong')
        else:
            return m18nc('kajongg meld type', 'rest of tiles')

    def __stateName(self):
        """the translated name of the state"""
        if self[0].isBonus or self.isClaimedKong:
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
