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




from util import m18nc

from tile import Tile

CONCEALED, EXPOSED, ALLSTATES = 1, 2, 3
EMPTY, SINGLE, PAIR, CHOW, PUNG, KONG, CLAIMEDKONG, REST = \
        0, 1, 2, 3, 4, 5, 6, 7


def elementKey(element):
    """to be used in sort() and sorted() as key=. Sort by tile type, value, case.
    element can also be a meld from the summary."""
    assert len(element) >= 2, 'elementKey wrong:%s' % element
    group = element[0].lower()
    bPos = element[1].lower()
    aPos = chr('xdwsbcfy'.index(group) + ord('0'))
    if group in 'wfy' and bPos in 'eswn':
        bPos = chr('eswn'.index(bPos) + ord('0'))
    # add element: upper/lowercase should have a defined order too
    return aPos + bPos + element

def tileKey(tile):
    """for tile sorting"""
    return elementKey(tile)

def meldKey(meld):
    """for meld sorting.
    To be used in sort() and sorted() as key=.
    Sorts by tile (dwsbc), then by the whole meld"""
    return elementKey(meld[0]) + meld.joined

def meldsContent(melds):
    """return content of melds"""
    return ' '.join([meld.joined for meld in melds])

class Meld(list):
    """represents a meld. Can be empty. Many Meld methods will
    raise exceptions if the meld is empty. But we do not care,
    those methods are not supposed to be called on empty melds.
    Meld is essentially a list of Tile with added methods"""

    __hash__ = None

    def __init__(self, newContent = None):
        """init the meld: content can be either
        - a single string with 2 chars for every tile
        - a list containing such strings
        - another meld. Its tiles are not passed.
        - a list of Tile objects"""
        list.__init__(self)
        self.__meldType = None
        if newContent is None:
            return
        if newContent.__class__.__name__ == 'generator':
            newContent = list(newContent)
        if isinstance(newContent, list) and newContent and hasattr(newContent[0], 'focusable'):
            self.extend(x.tile for x in newContent)
        elif isinstance(newContent, (list, tuple, Meld)):
            self.extend([Tile(x) for x in newContent])
        elif isinstance(newContent, Tile):
            self.append(newContent)
        elif hasattr(newContent, 'tile'):
            self.append(newContent.tile) # pylint: disable=E1103
        else:
            self.extend([Tile(newContent[x:x+2]) for x in range(0, len(newContent), 2)])
        for tile in self:
            assert isinstance(tile, Tile), self

    def toLower(self, first=None, last=None):
        """use first and last as for ranges"""
        if first is not None:
            if last is None:
                self[first] = self[first].lower()
                return
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
                return
        else:
            assert last is None
            first, last = 0, len(self)
        for idx in range(first, last):
            self[idx] = self[idx].capitalize()
        return self

    def lower(self, first=None, last=None):
        """use first and last as for ranges"""
        return Meld(self).toLower(first, last)

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

    def __setitem__(self, index, value):
        """sets a tile in the meld"""
        list.__setitem__(self, index, value)
        self.__meldType = None

    def __delitem__(self, index):
        """removes a tile from the meld"""
        list.__delitem__(self, index)
        self.__meldType = None

    @property
    def meldType(self):
        """caching the computation"""
        if self.__meldType is None:
            self.__meldType = self._getMeldType()
        return self.__meldType

    @property
    def state(self):
        """meld state"""
        firsts = list(x[0] for x in self)
        if ''.join(firsts).islower():
            return EXPOSED
        elif len(self) == 4 and firsts[1].isupper() and firsts[2].isupper():
            return CONCEALED
        elif len(self) == 4:
            return EXPOSED
        else:
            return CONCEALED

    @state.setter
    def state(self, state):
        """meld state"""
        if state == EXPOSED:
            self.toLower()
            if self.meldType == CLAIMEDKONG:
                self.toUpper(3)
        elif state == CONCEALED:
            self.toUpper()
            if len(self) == 4:
                self.toLower(0)
                self.toLower(3)
        else:
            raise Exception('meld.setState: illegal state %d' % state)

    def _getMeldType(self):
        """compute meld type. Except knitting melds."""
        # pylint: disable=too-many-branches, R0911
        # too many branches, too many returns
        if 'Xy' in self:
            return REST
        length = len(self)
        if not length:
            return EMPTY
        if length == 1:
            return SINGLE
        if length == 2:
            if self[0] == self[1]:
                return PAIR
            else:
                return REST
        if length > 4:
            return REST
        # now length is 3 or 4
        tiles = set(self)
        if len(tiles) == 1:
            if length == 3:
                return PUNG
            else:
                return KONG
        groups = set(x[0] for x in self)
        if len(groups) > 2:
            return REST
        if len(set(x.lower() for x in groups)) > 1:
            return REST
        values = set(x[1] for x in self)
        if length == 4:
            if len(values) > 1:
                return REST
            if self.isUpper():
                return REST
            elif self.isLower(0, 3) and self.isUpper(3):
                return CLAIMEDKONG
            elif self.isUpper(1, 3) and self.isLower(0) and self.isLower(3):
                return KONG
            else:
                assert False
        # only possibilities left are CHOW and REST
        # length is 3
        if len(groups) == 1:
            if groups & set('sbcSBC'):
                values = list(ord(x[1]) for x in self)
                if values[2] == values[0] + 2 and values[1] == values[0] + 1:
                    return CHOW
        return REST

    def tileType(self):
        """return one of d w s b c f y"""
        return self[0][0].lower()

    def isPair(self):
        """is this meld a pair?"""
        return self.meldType == PAIR

    def isChow(self):
        """is this meld a pair?"""
        return self.meldType == CHOW

    def isPung(self):
        """is this meld a pair?"""
        return self.meldType == PUNG

    def isKong(self):
        """is it a kong?"""
        return self.meldType in (KONG, CLAIMEDKONG)

    @property
    def joined(self):
        """content"""
        return ''.join(self)

    def expose(self, isClaiming):
        """expose this meld. For kungs, leave one or two concealed,
        showing how the kung was built"""
        if len(self) < 4:
            self.toLower()
        else:
            if isClaiming:
                self.toLower(0, 3)
                self.toUpper(3)
            else: # concealed kong
                self.toLower(0)
                self.toUpper(1, 3)
                self.toLower(3)
        self.__meldType = None

    def conceal(self):
        """conceal this meld again"""
        self.toUpper()
        self.__meldType = None

    def __repr__(self):
        """the default representation"""
        return 'Meld(%s)' % str(self)

    def __str__(self):
        """the content"""
        return self.joined

    def shortName(self):
        """convert int to speaking name with shortcut. ATTENTION: UNTRANSLATED!"""
        names = {SINGLE:m18nc('kajongg meld type','&single'),
            PAIR:m18nc('kajongg meld type','&pair'),
            CHOW:m18nc('kajongg meld type','&chow'),
            PUNG:m18nc('kajongg meld type','p&ung'),
            KONG:m18nc('kajongg meld type','k&ong'),
            CLAIMEDKONG:m18nc('kajongg meld type','c&laimed kong')}
        return names[self.meldType]

def hasChows(tile, within):
    """returns chows with tileName within within"""
    assert isinstance(tile, Tile)
    if not tile in within:
        return []
    color = tile[0]
    if color not in 'SBC':
        return []
    value = int(tile[1])
    values = set(int(x[1]) for x in within if x[0] == color)
    chows = []
    for offsets in [(0, 1, 2), (-2, -1, 0), (-1, 0,  1)]:
        subset = set([value + x for x in offsets])
        if subset <= values:
            chow = [color + str(x) for x in sorted(subset)]
            if chow not in chows:
                chows.append(list([Tile(x) for x in chow]))
    return chows
