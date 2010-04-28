# -*- coding: utf-8 -*-

"""
Copyright (C) 2008,2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

from collections import defaultdict

PREF = None

WINDS = 'ESWN'
LIGHTSOURCES = ['NE', 'NW', 'SW', 'SE']

class InternalParameters:
    """they are never saved in a config file. Some of them
    can be defined on the command line."""
    seed = None
    autoPlay = False
    showSql = False
    showTraffic = False
    debugRegex = False
    profileRegex = False
    dbPath = None
    app = None
    socket = None
    playOpen = False

class IntDict(defaultdict):
    """a dict where the values are expected to be numeric, so
    we can add dicts.If parent is given, parent is expected to
    be another IntDict, and our changes propagate into parent.
    This allows us to have a tree of IntDicts, and we only have
    to update the leaves, getting the sums for free"""

    def __init__(self, parent=None):
        defaultdict.__init__(self, int)
        self.parent = parent

    def copy(self):
        """need to reimplement this because the __init__ signature of
        IntDict is not identical to that of defaultdict"""
        result = IntDict(self.parent)
        result.update(self)
        return result

    def __add__(self, other):
        """add two IntDicts"""
        result = self.copy()
        for key, value in other.items():
            result[key] += value
        return result

    def __radd__(self, other):
        """we want sum to work (no start value)"""
        assert other == 0
        return self.copy()

    def __sub__(self, other):
        """self - other"""
        result = self.copy()
        for key, value in other.items():
            result[key] -= value
        for key in result.keys():
            if result[key] == 0:
                del result[key]
        return result

    def __eq__(self, other):
        return self.all() == other.all()

    def count(self, countFilter=None):
        """how many tiles defined by countFilter do we hold?
        countFilter is an iterator of element names. No countFilter: Take all
        So count(['we','ws']) should return 8"""
        return sum(self[x] for x in countFilter or self)

    def all(self, countFilter=None):
        """returns a list of all tiles defined by countFilter, each tile multiplied by its occurrence
        countFilter is an iterator of element names. No countFilter: take all
        So all(['we','fs']) should return ['we', 'we', 'we', 'we', 'fs']"""
        result = []
        for element in countFilter or self:
            result.extend([element] * self[element])
        return sorted(result)

    def __contains__(self, tile):
        """does not contain tiles with count 0"""
        return defaultdict.__contains__(self, tile) and self[tile] > 0

    def __setitem__(self, key, value):
        """also update parent if given"""
        if self.parent is not None:
            self.parent[key] += value - self.get(key, 0)
        defaultdict.__setitem__(self, key, value)

    def __delitem__(self, key):
        """also update parent if given"""
        if self.parent is not None:
            self.parent[key] -= self.get(key, 0)
        defaultdict.__delitem__(self, key)

    def clear(self):
        """also update parent if given"""
        if self.parent is not None:
            for key, value in self.items():
                self.parent[key] -= value
        defaultdict.clear(self)

    def __str__(self):
        return str(dict(self))

    def __repr__(self):
        return "<IntDict: %s>" % self

class Elements(object):
    """represents all elements"""
    def __init__(self):
        self.occurrence =  IntDict() # key: db, s3 etc. value: occurrence
        self.winds = ['we', 'ws', 'ww', 'wn']
        self.dragons = ['db', 'dg', 'dr']
        self.honors = self.winds + self.dragons
        self.terminals = ['s1', 's9', 'b1', 'b9', 'c1', 'c9']
        self.majors = self.honors + self.terminals
        self.minors = []
        self.greenHandTiles = ['dg', 'b2', 'b3', 'b4', 'b6', 'b8']
        for color in 'sbc':
            for value in '2345678':
                self.minors.append('%s%s' % (color, value))
        for tile in self.majors:
            self.occurrence[tile] = 4
        for tile in self.minors:
            self.occurrence[tile] = 4
        for bonus in 'fy':
            for wind in 'eswn':
                self.occurrence['%s%s' % (bonus, wind)] = 1

    def __filter(self, withBoni):
        """returns element names"""
        return (x for x in self.occurrence if withBoni or (x[0] not in 'fy'))

    def count(self, withBoni):
        """how many tiles are to be used by the game"""
        return self.occurrence.count(self.__filter(withBoni))

    def all(self, withBoni):
        """a list of all elements, each of them occurrence times"""
        return self.occurrence.all(self.__filter(withBoni))

elements = Elements()  # pylint: disable-msg=C0103
