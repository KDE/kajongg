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

import platform

PYTHON3 =  platform.python_version_tuple()[0] == '3'

from log import m18n, m18nc
from common import IntDict

class Tile(bytes):
    """a single tile"""
    # pylint: disable=too-many-public-methods, abstract-class-not-used
    cache = {}
    hashTable = b'XyxyDbdbDgdgDrdrWeweWswsWwwwWnwn' \
                b'S/s/S0s0S1s1S2s2S3s3S4s4S5s5S6s6S7s7S8s8S9s9S:s:S;s;' \
                b'B/b/B0b0B1b1B2b2B3b3B4b4B5b5B6b6B7b7B8b8B9b9B:b:B;b;' \
                b'C/c/C0c0C1c1C2c2C3c3C4c4C5c5C6c6C7c7C8c8C9c9C:c:C;c;' \
                b'fefsfwfnyeysywyn'
        # intelligence.py will define Tile('b0') or Tile('s:')
    def __new__(cls, *args):
        if isinstance(args[0], Tile):
            return args[0]
        if args not in cls.cache:
            arg0 = args[0]
            if len(args) == 1:
                arg0, arg1 = args[0]
            else:
                arg0, arg1 = args
            if isinstance(arg1, int):
                if arg1 < 10:
                    arg1 = arg1 + ord('0')
            if PYTHON3:
                if isinstance(arg0, (bytes, str)):
                    arg0 = ord(arg0)
                if isinstance(arg1, (bytes, str)):
                    arg1 = ord(arg1)
                what = (arg0, arg1)
            else:
                if isinstance(arg0, int):
                    arg0 = chr(arg0)
                if isinstance(arg1, int):
                    arg1 = chr(arg1)
                what = arg0 + arg1
            cls.cache[args] = bytes.__new__(cls, what)
        return cls.cache[args]

    def __init__(self, *dummyArgs):
        # pylint: disable=super-init-not-called
        if not hasattr(self, '_fixed'): # already defined if I am from cache
            self.group = self[:1]
            self.value = self[1:]
            self.lowerGroup = self.group.lower()
            self.isBonus = self.group in b'fy'
            self.isHonor = self.lowerGroup in b'dw'
            self.key = self.hashTable.index(self) / 2
            self._fixed = True

    def __setattr__(self, name, value):
        if hasattr(self, '_fixed'):
            raise TypeError
        bytes.__setattr__(self, name, value)

    def __getitem__(self, index):
        if hasattr(self, '_fixed'):
            raise TypeError
        return bytes.__getitem__(self, index)

    def __setitem__(self, index, value):
        raise TypeError

    def __delitem__(self, index):
        raise TypeError

    def lower(self):
        """return exposed element name"""
        return Tile(bytes.lower(self))

    def upper(self):
        """return hidden element name"""
        if self.isBonus:
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

    def nextForChow(self):
        """the following tile for a chow"""
        return Tile(ord(self.group), ord(self.value) + 1)

    def __repr__(self):
        """default representation"""
        return 'Tile(%s)' % str(self)

    def groupName(self):
        """the name of the group this tile is of"""
        names = {b'x':m18nc('kajongg','hidden'), b's': m18nc('kajongg','stone'),
            b'b': m18nc('kajongg','bamboo'), b'c':m18nc('kajongg','character'),
            b'w':m18nc('kajongg','wind'), b'd':m18nc('kajongg','dragon'),
            b'f':m18nc('kajongg','flower'), b'y':m18nc('kajongg','season')}
        return names[self.lowerGroup]

    def valueName(self):
        """the name of the value this tile has"""
        names = {b'y':m18nc('kajongg','tile'), b'b':m18nc('kajongg','white'),
            b'r':m18nc('kajongg','red'), b'g':m18nc('kajongg','green'),
            b'e':m18nc('kajongg','East'), b's':m18nc('kajongg','South'), b'w':m18nc('kajongg','West'),
            b'n':m18nc('kajongg','North'),
            b'1':'1', b'2':'2', b'3':'3', b'4':'4', b'5':'5', b'6':'6', b'7':'7', b'8':'8', b'9':'9'}
        return names[self.value]

    def name(self):
        """returns name of a single tile"""
        if self.group in b'wW':
            result = {b'e':m18n('East Wind'), b's':m18n('South Wind'),
                b'w':m18n('West Wind'), b'n':m18n('North Wind')}[self.value]
        else:
            result = m18nc('kajongg tile name', '{group} {value}')
        return result.format(value=self.valueName(), group=self.groupName())

    def __lt__(self, other):
        """needed for sort"""
        assert isinstance(other, Tile)
        return self.key < other.key

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
        return (x for x in self.occurrence if ruleset.withBonusTiles or (not x.isBonus))

    def count(self, ruleset):
        """how many tiles are to be used by the game"""
        return self.occurrence.count(self.__filter(ruleset))

    def all(self, ruleset):
        """a list of all elements, each of them occurrence times"""
        return self.occurrence.all(self.__filter(ruleset))

elements = Elements()  # pylint: disable=invalid-name
