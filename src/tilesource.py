# -*- coding: utf-8 -*-

"""
 Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

from common import ReprMixin

class TileSource:
    """
    some constants
    """

    byChar = {}

    class SourceClass(ReprMixin):
        """Defines defaults"""
        isDiscarded = False

        def __str__(self) ->str:
            return self.__repr__()

        def __repr__(self) ->str:
            return 'TileSource.' + self.__class__.__name__.rsplit('.', maxsplit=1)[-1]

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
