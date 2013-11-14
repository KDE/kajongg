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

from log import m18n, m18nc
from common import IntDict

def chiNext(element, offset):
    """the element name of the following value"""
    group, baseValue = element
    baseValue = int(baseValue)
    return Tile('%s%d' % (group, baseValue+offset))

class Tile(bytes):
    """a single tile"""
    # pylint: disable=too-many-public-methods, abstract-class-not-used

    def __new__(cls, *args):
        arg0 = args[0]
        if len(args) == 1:
            if arg0.__class__.__name__ == 'UITile':
                return bytes.__new__(cls, arg0.tile)
            elif len(arg0) == 1 and isinstance(arg0[0], Tile):
                return bytes.__new__(cls, arg0[0])
            else:
                assert len(arg0) == 2, '%s:%s' % (type(arg0), arg0)
                return bytes.__new__(cls, arg0)
        else:
            assert len(args) == 2, args
            return bytes.__new__(cls, arg0 + args[1])

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
        assert False

    def __setitem__(self, index):
        assert False

    def __repr__(self):
        """default representation"""
        return 'Tile(%s)' % str(self)

    def isBonus(self):
        """is this a bonus tile? (flower,season)"""
        return self[0] in b'fy'

    def isHonor(self):
        """is this a wind or dragon?"""

    def groupName(self):
        """the name of the group this tile is of"""
        names = {'x':m18nc('kajongg','hidden'), 's': m18nc('kajongg','stone'),
            'b': m18nc('kajongg','bamboo'), 'c':m18nc('kajongg','character'),
            'w':m18nc('kajongg','wind'), 'd':m18nc('kajongg','dragon'),
            'f':m18nc('kajongg','flower'), 'y':m18nc('kajongg','season')}
        return names[self[0].lower()]

    def valueName(self):
        """the name of the value this tile has"""
        names = {'y':m18nc('kajongg','tile'), 'b':m18nc('kajongg','white'),
            'r':m18nc('kajongg','red'), 'g':m18nc('kajongg','green'),
            'e':m18nc('kajongg','East'), 's':m18nc('kajongg','South'), 'w':m18nc('kajongg','West'),
            'n':m18nc('kajongg','North'),
            '1':'1', '2':'2', '3':'3', '4':'4', '5':'5', '6':'6', '7':'7', '8':'8', '9':'9'}
        return names[self[1]]

    def name(self):
        """returns name of a single tile"""
        if self[0].lower() == 'w':
            result = {'e':m18n('East Wind'), 's':m18n('South Wind'),
                'w':m18n('West Wind'), 'n':m18n('North Wind')}[self[1].lower()]
        else:
            result = m18nc('kajongg tile name', '{group} {value}')
        return result.format(value=self.valueName(), group=self.groupName())

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
        self.winds = Tileset([b'we', b'ws', b'ww', b'wn'])
        self.wINDS = Tileset([b'We', b'Ws', b'Ww', b'Wn'])
        self.dragons = Tileset([b'db', b'dg', b'dr'])
        self.dRAGONS = Tileset([b'Db', b'Dg', b'Dr'])
        self.honors = self.winds | self.dragons
        self.hONORS = self.wINDS | self.dRAGONS
        self.terminals = Tileset([b's1', b's9', b'b1', b'b9', b'c1', b'c9'])
        self.tERMINALS = Tileset([b'S1', b'S9', b'B1', b'B9', b'C1', b'C9'])
        self.majors = self.honors | self.terminals
        self.mAJORS = self.hONORS | self.tERMINALS
        self.minors = Tileset()
        self.mINORS = Tileset()
        self.greenHandTiles = Tileset([b'dg', b'b2', b'b3', b'b4', b'b6', b'b8'])
        for group in b'sbc':
            for value in b'2345678':
                self.minors.add(Tile(group, value))
        for tile in self.majors:
            self.occurrence[tile] = 4
        for tile in self.minors:
            self.occurrence[tile] = 4
        for bonus in b'fe', b'fs', b'fw', b'fn', b'ye', b'ys', b'yw', b'yn':
            self.occurrence[Tile(bonus)] = 1

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
