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
EMPTY, SINGLE, PAIR, CHOW, PUNG, KONG, CLAIMEDKONG, ALLMELDS, REST = \
        0, 1, 2, 4, 8, 16, 32, 63, 128

def shortcuttedMeldName(meld):
    """convert int to speaking name with shortcut"""
    if meld == ALLMELDS or meld == REST or meld == 0:
        return ''
    parts = []
    if SINGLE & meld:
        parts.append(m18nc('kajongg meld type','&single'))
    if PAIR & meld:
        parts.append(m18nc('kajongg meld type','&pair'))
    if CHOW & meld:
        parts.append(m18nc('kajongg meld type','&chow'))
    if PUNG & meld:
        parts.append(m18nc('kajongg meld type','p&ung'))
    if KONG & meld:
        parts.append(m18nc('kajongg meld type','k&ong'))
    if CLAIMEDKONG & meld:
        parts.append(m18nc('kajongg meld type','c&laimed kong'))
    return '|'.join(parts)

def meldName(meld):
    """convert int to speaking name with shortcut"""
    return shortcuttedMeldName(meld).replace('&', '')

def stateName(state):
    """convert int to speaking name"""
    if state == ALLSTATES:
        return ''
    parts = []
    if CONCEALED & state:
        parts.append(m18nc('kajongg','concealed'))
    if EXPOSED & state:
        parts.append(m18nc('kajongg','exposed'))
    return '|'.join(parts)

def elementKey(element):
    """to be used in sort() and sorted() as key=. Sort by tile type, value, case.
    element can also be a meld from the summary."""
    assert len(element) >= 2, 'elementKey wrong:%s' % element
    group = element[0].lower()
    aPos = chr('xdwsbcfy'.index(group) + ord('0'))
    bPos = element[1].lower()
    if group in 'wfy' and bPos in 'eswn':
        bPos = chr('eswn'.index(bPos) + ord('0'))
    # add element: upper/lowercase should have a defined order too
    return aPos + bPos + element

def tileKey(tile):
    """for tile sorting"""
    return elementKey(tile.element)

def meldKey(meld):
    """for meld sorting.
    To be used in sort() and sorted() as key=.
    Sorts by tile (dwsbc), then by the whole meld"""
    return elementKey(meld.pairs[0]) + meld.joined

def meldsContent(melds):
    """return content of melds"""
    return ' '.join([meld.joined for meld in melds])

class Pairs(list):
    """base class for Meld and Slot"""
    def __init__(self, newContent=None):
        list.__init__(self)
        if newContent:
            if isinstance(newContent, list):
                self.extend(newContent)
            elif isinstance(newContent, tuple):
                self.extend(list(newContent))
            else:
                self.extend([newContent[x:x+2] for x in range(0, len(newContent), 2)])

    def startChars(self, first=None, last=None):
        """use first and last as for ranges"""
        if first is not None:
            if last is None:
                return self[first][0]
        else:
            assert last is None
            first, last = 0, len(self)
        return list(x[0] for x in self[first:last])

    def values(self, first=None, last=None):
        """use first and last as for ranges"""
        if first is not None:
            if last is None:
                return int(self[first][1])
        else:
            assert last is None
            first, last = 0, len(self)
        return list(int(x[1]) for x in self[first:last])

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
        return Pairs(self).toLower(first, last)

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

class Meld(object):
    """represents a meld. Can be empty. Many Meld methods will
    raise exceptions if the meld is empty. But we do not care,
    those methods are not supposed to be called on empty melds.
    Meld firstly holds the tile elements like 's1','s2','s3' but its
    attribute tiles can also hold references to the visual tile objects.
    The name of the tile element in the meld does not have to be
    identical with the name of the corresponding real tile while tiles
    are added or removed. See end of SelectorBoard.meldVariants()."""

    colorNames = {'x':m18nc('kajongg','hidden'), 's': m18nc('kajongg','stone'),
        'b': m18nc('kajongg','bamboo'), 'c':m18nc('kajongg','character'),
        'w':m18nc('kajongg','wind'), 'd':m18nc('kajongg','dragon'),
        'f':m18nc('kajongg','flower'), 'y':m18nc('kajongg','season')}
    valueNames = {'y':m18nc('kajongg','tile'), 'b':m18nc('kajongg','white'),
        'r':m18nc('kajongg','red'), 'g':m18nc('kajongg','green'),
        'e':m18nc('kajongg','east'), 's':m18nc('kajongg','south'), 'w':m18nc('kajongg','west'),
        'n':m18nc('kajongg','north'),
        'O':m18nc('kajongg','own wind'), 'R':m18nc('kajongg','round wind')}
    for valNameIdx in range(1, 10):
        valueNames[str(valNameIdx)] = str(valNameIdx)

    @staticmethod
    def tileName(element):
        """returns translated name of a single tile"""
        return Meld.colorNames[element[0].lower()] + ' ' + Meld.valueNames[element[1]]

    def __init__(self, newContent = None):
        """init the meld: content can be either
        - a single string with 2 chars for every tile
        - a list containing such strings
        - another meld. Its tiles are not passed.
        - a list of Tile objects"""
        self.__pairs = Pairs()
        self.__valid = False
        self.meldType = None
        self.tiles = []
        if isinstance(newContent, list) and newContent and hasattr(newContent[0], 'focusable'):
            self.joined = ''.join(x.element for x in newContent)
            self.tiles = newContent
        elif isinstance(newContent, Meld):
            self.joined = newContent.joined
            self.tiles = newContent.tiles
        elif isinstance(newContent, Tile):
            self.joined = newContent.element
            self.tiles = [newContent]
        else:
            self.joined = newContent

    def __len__(self):
        """how many tiles do we have?"""
        return len(self.tiles) if self.tiles else len(self.__pairs)

    def __getitem__(self, index):
        """Meld[x] returns Tile # x """
        return self.tiles[index]

    def __eq__(self, other):
        return self.pairs == other.pairs

    def isValid(self):
        """is it valid?"""
        return self.__valid

    def __isChow(self):
        """expensive, but this is only computed once per meld"""
        if len(self.__pairs) == 3:
            starts = set(self.__pairs.startChars())
            if len(starts) == 1:
                if starts & set('sbcSBC'):
                    values = self.__pairs.values()
                    if values[1] == values[0] + 1 and values[2] == values[0] + 2:
                        return True
        return False

    @apply
    def state(): # pylint: disable=E0202
        """meld state"""
        def fget(self):
            # pylint: disable=W0212
            firsts = self.__pairs.startChars()
            if ''.join(firsts).islower():
                return EXPOSED
            elif len(self) == 4 and firsts[1].isupper() and firsts[2].isupper():
                return CONCEALED
            elif len(self) == 4:
                return EXPOSED
            else:
                return CONCEALED
        def fset(self, state):
            # pylint: disable=W0212
            if state == EXPOSED:
                self.__pairs.toLower()
                if self.meldType == CLAIMEDKONG:
                    self.__pairs.toUpper(3)
            elif state == CONCEALED:
                self.__pairs.toUpper()
                if len(self.__pairs) == 4:
                    self.__pairs.toLower(0)
                    self.__pairs.toLower(3)
            else:
                raise Exception('meld.setState: illegal state %d' % state)
            for idx, tile in enumerate(self.tiles):
                tile.element = self.__pairs[idx]
        return property(**locals())

    def _getMeldType(self):
        """compute meld type"""
        length = len(self.__pairs)
        if not length:
            return EMPTY
        assert self.__pairs[0][0].lower() in 'xdwsbcfy', self.__pairs
        if length == 1:
            result = SINGLE
        elif length == 2:
            result = PAIR
        elif length == 4:
            if self.__pairs.isUpper():
                result = REST
                self.__valid = False
            elif self.__pairs.isLower(0, 3) and self.__pairs.isUpper(3):
                result = CLAIMEDKONG
            else:
                result = KONG
        elif self.__isChow():
            result = CHOW
        elif length == 3:
            result = PUNG
        else:
            result = REST
        if result not in [CHOW, REST]:
            if len(set(x.lower() for x in self.__pairs)) > 1:
                result = REST
        return result

    def tileType(self):
        """return one of d w s b c f y"""
        return self.__pairs[0][0].lower()

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

    @apply
    def pairs():
        """make them readonly"""
        def fget(self):
            # pylint: disable=W0212
            return self.__pairs
        return property(**locals())

    @apply
    def joined(): # pylint: disable=E0202
        """content"""
        def fget(self):
            # pylint: disable=W0212
            return ''.join(self.__pairs)
        def fset(self, newContent):
            # pylint: disable=W0212
            assert not self.tiles
            self.__pairs = Pairs(newContent)
            self.__valid = True
            self.meldType = self._getMeldType()
        return property(**locals())

    def expose(self, isClaiming):
        """expose this meld. For kungs, leave one or two concealed,
        showing how the kung was built"""
        assert self.__pairs.isUpper(), self.joined
        if len(self.__pairs) < 4:
            self.__pairs.toLower()
        else:
            if isClaiming:
                self.__pairs.toLower(0, 3)
                self.__pairs.toUpper(3)
            else: # concealed kong
                self.__pairs.toLower(0)
                self.__pairs.toUpper(1, 3)
                self.__pairs.toLower(3)
        self.meldType = self._getMeldType()

    def conceal(self):
        """conceal this meld again"""
        self.__pairs.toUpper()
        self.meldType = self._getMeldType()

def hasChows(tileName, within):
    """returns chows with tileName within within"""
    if not tileName in within:
        return []
    color = tileName[0]
    if color not in 'SBC':
        return []
    value = int(tileName[1])
    values = set(int(x[1]) for x in within if x[0] == color)
    chows = []
    for offsets in [(0, 1, 2), (-2, -1, 0), (-1, 0,  1)]:
        subset = set([value + x for x in offsets])
        if subset <= values:
            chow = [color + str(x) for x in sorted(subset)]
            if chow not in chows:
                chows.append(chow)
    return chows
