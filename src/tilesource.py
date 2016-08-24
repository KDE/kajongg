# -*- coding: utf-8 -*-

"""
 Copyright (C) 2008-2014 Wolfgang Rohdewald <wolfgang@rohdewald.de>

Kajongg is free software you can redistribute it and/or modify
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

class TileSource(object):
    """
    some constants
    """

    byChar = dict()

    def __str__(self):
        return str(self.char)

    def __repr__(self):
        return str(self)

    class SourceClass(object):
        """Defines defaults"""
        isDiscarded = False

    class LivingWallDiscard(SourceClass):
        """Last Tile was discarded"""
        char = 'd'
        isDiscarded = True

    class LivingWall(SourceClass):
        """Last tile comes from wall"""
        char = 'w'

    class East14th(SourceClass):
        """This is the 14th tile for East"""
        char = '1'

    class RobbedKong(SourceClass):
        """Last tile comes from robbing a kong"""
        char = 'k'

    class DeadWall(SourceClass):
        """Last tile comes from dead wall"""
        char = 'e'

    class LivingWallEnd(SourceClass):
        """Last tile comes from living wall and is the last living wall tile"""
        char = 'z'

    class LivingWallEndDiscard(SourceClass):
        """like LivingWallEnd but discarded"""
        char = 'Z'
        isDiscarded = True

    class Unknown(SourceClass):
        """Unknown source"""
        char = '.'

TileSource.byChar['w'] = TileSource.LivingWall
TileSource.byChar['d'] = TileSource.LivingWallDiscard
TileSource.byChar['z'] = TileSource.LivingWallEnd
TileSource.byChar['e'] = TileSource.DeadWall
TileSource.byChar['Z'] = TileSource.LivingWallEndDiscard
TileSource.byChar['1'] = TileSource.East14th
TileSource.byChar['k'] = TileSource.RobbedKong
TileSource.byChar['.'] = TileSource.Unknown
