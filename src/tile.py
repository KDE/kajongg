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
    return '%s%d' % (color, baseValue+offset)

def swapTitle(element):
    """if istitle, return lower. If lower, return capitalize"""
    if element.islower():
        return element.capitalize()
    else:
        return element.lower()

class Tile(object):
    """a single tile on the board. This is a QObject because we want to animate it.
    the unit of xoffset is the width of the tile,
    the unit of yoffset is the height of the tile.
    """
    def __init__(self, element):
        self.__element = element
    # pylint: disable=too-many-public-methods,R0924

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

    @property
    def element(self):
        """tileName"""
        return self.__element

    @element.setter
    def element(self, value):
        """set element and update display"""
        self.__element = value

    def lower(self):
        """return element.lower"""
        return self.element.lower()

    def upper(self):
        """return hidden element name"""
        if self.isBonus():
            return self.element
        return self.element.capitalize()

    def __str__(self):
        """printable string with tile"""
        return self.element

    def __repr__(self):
        """default representation"""
        return 'Tile(%s)' % str(self)

    def isFlower(self):
        """is this a flower tile?"""
        return self.element[0] == 'f'

    def isSeason(self):
        """is this a season tile?"""
        return self.element[0] == 'y'

    def isBonus(self):
        """is this a bonus tile? (flower,season)"""
        return self.isFlower() or self.isSeason()

    def isHonor(self):
        """is this a wind or dragon?"""
        return self.element[0] in 'wWdD'

    def name(self):
        """returns translated name of a single tile"""
        return self.colorNames[self.element[0].lower()] + ' ' + self.valueNames[self.element[1]]

class Elements(object):
    """represents all elements"""
    # pylint: disable=too-many-instance-attributes
    # too many attributes
    def __init__(self):
        self.occurrence = IntDict() # key: db, s3 etc. value: occurrence
        self.winds = set(['we', 'ws', 'ww', 'wn'])
        self.wINDS = set(['We', 'Ws', 'Ww', 'Wn'])
        self.dragons = set(['db', 'dg', 'dr'])
        self.dRAGONS = set(['Db', 'Dg', 'Dr'])
        self.honors = self.winds | self.dragons
        self.hONORS = self.wINDS | self.dRAGONS
        self.terminals = set(['s1', 's9', 'b1', 'b9', 'c1', 'c9'])
        self.tERMINALS = set(['S1', 'S9', 'B1', 'B9', 'C1', 'C9'])
        self.majors = self.honors | self.terminals
        self.mAJORS = self.hONORS | self.tERMINALS
        self.minors = set()
        self.mINORS = set()
        self.greenHandTiles = set(['dg', 'b2', 'b3', 'b4', 'b6', 'b8'])
        for color in 'sbc':
            for value in '2345678':
                self.minors |= set(['%s%s' % (color, value)])
        for tile in self.majors:
            self.occurrence[tile] = 4
        for tile in self.minors:
            self.occurrence[tile] = 4
        for bonus in 'fy':
            for wind in 'eswn':
                self.occurrence['%s%s' % (bonus, wind)] = 1

    def __filter(self, ruleset):
        """returns element names"""
        return (x for x in self.occurrence if ruleset.withBonusTiles or (x[0] not in 'fy'))

    def count(self, ruleset):
        """how many tiles are to be used by the game"""
        return self.occurrence.count(self.__filter(ruleset))

    def all(self, ruleset):
        """a list of all elements, each of them occurrence times"""
        return self.occurrence.all(self.__filter(ruleset))

elements = Elements()  # pylint: disable=invalid-name
