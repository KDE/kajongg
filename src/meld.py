# -*- coding: utf-8 -*-

"""Copyright (C) 2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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




from util import m18n, m18nc, m18nE, english

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

class NamedList(list):
    """a list with a name and a description (to be used as hint)"""

    def __init__(self, listId, name, description):
        list.__init__(self)
        self.listId = listId
        self.name = name
        self.description = description

def meldsContent(melds):
    """return content of melds"""
    return ' '.join([meld.joined for meld in melds])

class Score(object):
    """holds all parts contributing to a score. It has two use cases:
    1. for defining what a rules does: either points or doubles or limits, holding never more than one unit
    2. for summing up the scores of all rules: Now more than one of the units can be in use. If a rule
    should want to set more than one unit, split it into two rules.
    For the first use case only we have the attributes value and unit"""


    def __init__(self, points=0, doubles=0, limits=0, limitPoints=None):
        self.points = 0 # define the types for those values
        self.doubles = 0
        self.limits = 0.0
        self.limitPoints = limitPoints
        self.points = type(self.points)(points)
        self.doubles = type(self.doubles)(doubles)
        self.limits = type(self.limits)(limits)

    unitNames = [m18nE('points'), m18nE('doubles'), m18nE('limits')]

    @staticmethod
    def unitName(unit):
        """maps the index to the name"""
        return m18n(Score.unitNames[unit])

    def clear(self):
        """set all to 0"""
        self.points = self.doubles = self.limits = 0

    def __str__(self):
        """make score printable"""
        parts = []
        if self.points:
            parts.append('points=%d' % self.points)
        if self.doubles:
            parts.append('doubles=%d' % self.doubles)
        if self.limits:
            parts.append('limits=%f' % self.limits)
        return ' '.join(parts)

    def contentStr(self):
        """make score readable for humans, i18n"""
        parts = []
        if self.points:
            parts.append(m18nc('Kajongg', '%1 points', self.points))
        if self.doubles:
            parts.append(m18nc('Kajongg', '%1 doubles', self.doubles))
        if self.limits:
            parts.append(m18nc('Kajongg', '%1 limits', self.limits))
        return ' '.join(parts)

    def assertSingleUnit(self):
        """make sure only one unit is used"""
        if sum(1 for x in [self.points, self.doubles, self.limits] if x) > 1:
            raise Exception('this score must not hold more than one unit: %s' % self.__str__())

    @apply
    def unit(): # pylint: disable=E0202
        """for use in ruleset tree view. returns an index into Score.units."""
        def fget(self):
            self.assertSingleUnit()
            if self.doubles:
                return 1
            elif self.limits:
                return 2
            else:
                return 0
        def fset(self, unit):
            self.assertSingleUnit()
            oldValue = self.value
            self.clear()
            self.__setattr__(english(Score.unitName(unit)), oldValue)
        return property(**locals())

    @apply
    def value():
        """value without unit. Only one unit value may be set for this to be usable"""
        def fget(self):
            self.assertSingleUnit()
            # limits first because for all 0 we want to get 0, not 0.0
            return self.limits or self.points or self.doubles
        def fset(self, value):
            self.assertSingleUnit()
            uName = Score.unitNames[self.unit]
            self.__setattr__(uName, type(self.__getattribute__(uName))(value))
        return property(**locals())

    def __eq__(self, other):
        """ == comparison """
        assert isinstance(other, Score)
        return self.points == other.points and self.doubles == other.doubles and self.limits == other.limits

    def __ne__(self, other):
        """ != comparison """
        return self.points != other.points or self.doubles != other.doubles or self.limits != other.limits

    def __lt__(self, other):
        return self.total() < other.total()

    def __le__(self, other):
        return self.total() <= other.total()

    def __gt__(self, other):
        return self.total() > other.total()

    def __ge__(self, other):
        return self.total() >= other.total()

    def __add__(self, other):
        """implement adding Score"""
        if self.limitPoints and other.limitPoints:
            assert self.limitPoints == other.limitPoints
        return Score(self.points + other.points, self.doubles+other.doubles,
            max(self.limits, other.limits), self.limitPoints or other.limitPoints)

    def __radd__(self, other):
        """allows sum() to work"""
        return Score(points = self.points + other, doubles=self.doubles,
            limits=self.limits, limitPoints=self.limitPoints)

    def total(self, limitPoints=None):
        """the total score"""
        if limitPoints is None:
            limitPoints = self.limitPoints
        if limitPoints is None:
            raise Exception('Score.total: limitPoints unknown')
        if self.limits:
            return int(round(self.limits * limitPoints))
        else:
            return int(min(self.points * (2 ** self.doubles), limitPoints))

    def __int__(self):
        """the total score"""
        return self.total()

class Pairs(list):
    """base class for Meld and Slot"""
    def __init__(self, newContent=None):
        list.__init__(self)
        if newContent:
            if isinstance(newContent, list):
                self.extend(newContent)
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

    tileNames = {'x':m18nc('kajongg','hidden'), 's': m18nc('kajongg','stone') ,
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

    def __init__(self, newContent = None):
        """init the meld: content can be either
        - a single string with 2 chars for every tile
        - a list containing such strings
        - another meld. Its tiles are not passed.
        - a list of Tile objects"""
        self.__pairs = Pairs()
        self.__valid = False
        self.score = Score()
        self.meldType = None
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
            self.tiles = []

    def __len__(self):
        """how many tiles do we have?"""
        return len(self.tiles) if self.tiles else len(self.__pairs)

    def __str__(self):
        """make meld printable"""
        if not self.pairs:
            return 'EMPTY'
        which = Meld.tileNames[self.__pairs[0][0].lower()]
        value = Meld.valueNames[self.__pairs[0][1]]
        pStr = m18nc('kajongg', '%1 points', self.score.points) if self.score.points else ''
        fStr = m18nc('kajongg', '%1 doubles', self.score.doubles) if self.score.doubles else ''
        score = ' '.join([pStr, fStr])
        return u'%s %s %s %s:   %s' % (stateName(self.state),
            meldName(self.meldType) , which, value, score)

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

    def isSingle(self):
        """is this meld a pair?"""
        return self.meldType == SINGLE

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

    def regex(self, claimedKongAsConcealed=False):
        """a string containing the tile type, the meld size and its value. For Chow, return size 0.
        Example: C304 is a concealed pung of characters with 4 base points
        """
        myLen = 0 if self.meldType == CHOW else len(self)
        idx = 0
        if self.meldType == KONG:
            idx = 1
        elif self.meldType == CLAIMEDKONG and claimedKongAsConcealed:
            idx = 3
        return '%s%s%02d' % (self.__pairs[idx][0], str(myLen), self.score.points)

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
            self.__pairs = Pairs(newContent)
            self.__valid = True
            self.meldType = self._getMeldType()
        return property(**locals())

    def expose(self, claimed):
        """expose this meld. For kungs, leave one or two concealed,
        showing how the kung was built"""
        assert self.__pairs.isUpper(), self.joined
        if len(self.__pairs) < 4:
            self.__pairs.toLower()
        else:
            if claimed:
                self.__pairs.toLower(0, 3)
                self.__pairs.toUpper(3)
            else: # concealed kong
                self.__pairs.toLower(0)
                self.__pairs.toUpper(1, 3)
                self.__pairs.toLower(3)
