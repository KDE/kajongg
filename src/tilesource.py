# -*- coding: utf-8 -*-

"""
 Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

class TileSource:
    """
    some constants
    """

    byChar = dict()

    def __str__(self):
        return self.char

    def __repr__(self):
        return 'TileSource.{}'.format(self.__class__.__name__)

    class SourceClass:
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
