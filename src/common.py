#!/usr/bin/env python
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


PREF = None

WINDS = 'ESWN'
LIGHTSOURCES = ['NE', 'NW', 'SW', 'SE']

class InternalParameters:
    seed = None
    autoMode = False
    showSql = False
    showTraffic = False
    debugRegex = False
    profileRegex = False
    dbPath = None
    app = None
    
class Elements(object):
    """represents all elements"""
    def __init__(self):
        self.occurrence =  dict() # key: db, s3 etc. value: occurrence
        for wind in 'eswn':
            self.occurrence['w%s' % wind] = 4
        for dragon in 'bgr':
            self.occurrence['d%s' % dragon] = 4
        for color in 'sbc':
            for value in '123456789':
                self.occurrence['%s%s' % (color, value)] = 4
        for bonus in 'fy':
            for wind in 'eswn':
                self.occurrence['%s%s' % (bonus, wind)] = 1

    def __filter(self, withBoni):
        return (x for x in self.occurrence if withBoni or (x[0] not in 'fy'))

    def count(self, withBoni):
        """how many tiles are to be used by the game"""
        return sum(self.occurrence[e] for e in self.__filter(withBoni))

    def all(self, withBoni):
        """a list of all elements, each of them occurrence times"""
        result = []
        for element in self.__filter(withBoni):
            result.extend([element] * self.occurrence[element])
        return result

Elements = Elements()
