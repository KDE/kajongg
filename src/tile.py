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

from util import m18nc
from common import IntDict

def chiNext(element, offset):
    """the element name of the following value"""
    color, baseValue = element
    baseValue = int(baseValue)
    return Tile('%s%d' % (color, baseValue+offset))

class Tile(bytes):
    """a single tile"""
    # pylint: disable=too-many-public-methods, abstract-class-not-used

    colorNames = {'x':m18nc('kajongg','hidden'), 's': m18nc('kajongg','stone'),
        'b': m18nc('kajongg','bamboo'), 'c':m18nc('kajongg','character'),
        'w':m18nc('kajongg','wind'), 'd':m18nc('kajongg','dragon'),
        'f':m18nc('kajongg','flower'), 'y':m18nc('kajongg','season')}
    valueNames = {'y':m18nc('kajongg','tile'), 'b':m18nc('kajongg','white'),
        'r':m18nc('kajongg','red'), 'g':m18nc('kajongg','green'),
        'e':m18nc('kajongg','east'), 's':m18nc('kajongg','south'), 'w':m18nc('kajongg','west'),
        'n':m18nc('kajongg','north'),
        'O':m18nc('kajongg','own wind'), 'R':m18nc('kajongg','round wind'),
        '1':'1', '2':'2', '3':'3', '4':'4', '5':'5', '6':'6', '7':'7', '8':'8', '9':'9'}

    def __new__(cls, element):
        if element.__class__.__name__ == 'UITile':
            element = element.tile
        if len(element) == 1 and isinstance(element[0], Tile):
            element = element[0]
        assert len(element) == 2, '%s:%s' % (type(element), element)
        return bytes.__new__(cls, element.encode('utf-8'))

    def group(self):
        """group as string"""
        return self[0]

    def value(self):
        """value as string"""
        return self[1]

    def lower(self):
        """return exposed element name"""
        return Tile(bytes.lower(self))

    def upper(self):
        """return hidden element name"""
        if self.isBonus():
            return self
        return Tile(bytes.capitalize(self))

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

    def __delitem__(self, index):
        raise NotImplementedError

    def __setitem__(self, index):
        raise NotImplementedError

    def __repr__(self):
        """default representation"""
        return 'Tile(%s)' % str(self)

    def isBonus(self):
        """is this a bonus tile? (flower,season)"""
        return self[0] in b'fy'

    def isHonor(self):
        """is this a wind or dragon?"""

    def name(self):
        """returns translated name of a single tile"""
        return self.colorNames[self[0].lower()] + ' ' + self.valueNames[self[1]]

class Tileset(set):
    """a helper class for simpler instantiation of the Elements attributes"""
    # pylint: disable=incomplete-protocol
    def __init__(self, tiles=None):
        if tiles is None:
            tiles = []
        set.__init__(self, list(Tile(x) for x in tiles))

class Elements(object):
    """represents all elements"""
    # pylint: disable=too-many-instance-attributes
    # too many attributes
    def __init__(self):
        self.occurrence = IntDict() # key: db, s3 etc. value: occurrence
        self.winds = Tileset(['we', 'ws', 'ww', 'wn'])
        self.wINDS = Tileset(['We', 'Ws', 'Ww', 'Wn'])
        self.dragons = Tileset(['db', 'dg', 'dr'])
        self.dRAGONS = Tileset(['Db', 'Dg', 'Dr'])
        self.honors = self.winds | self.dragons
        self.hONORS = self.wINDS | self.dRAGONS
        self.terminals = Tileset(['s1', 's9', 'b1', 'b9', 'c1', 'c9'])
        self.tERMINALS = Tileset(['S1', 'S9', 'B1', 'B9', 'C1', 'C9'])
        self.majors = self.honors | self.terminals
        self.mAJORS = self.hONORS | self.tERMINALS
        self.minors = Tileset()
        self.mINORS = Tileset()
        self.greenHandTiles = Tileset(['dg', 'b2', 'b3', 'b4', 'b6', 'b8'])
        for color in 'sbc':
            for value in '2345678':
                self.minors.add(Tile('%s%s' % (color, value)))
        for tile in self.majors:
            self.occurrence[tile] = 4
        for tile in self.minors:
            self.occurrence[tile] = 4
        for bonus in 'fy':
            for wind in 'eswn':
                self.occurrence[Tile('%s%s' % (bonus, wind))] = 1

    def __filter(self, ruleset):
        """returns element names"""
        return (x for x in self.occurrence if ruleset.withBonusTiles or (not x.isBonus()))

    def count(self, ruleset):
        """how many tiles are to be used by the game"""
        return self.occurrence.count(self.__filter(ruleset))

    def all(self, ruleset):
        """a list of all elements, each of them occurrence times"""
        return self.occurrence.all(self.__filter(ruleset))

elements = Elements()  # pylint: disable=invalid-name
