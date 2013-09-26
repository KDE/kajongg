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
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
"""

import weakref

from common import elements
from tile import Tile

class WallEmpty(Exception):
    """exception when trying to get a tile off the empty wall"""
    pass

class Wall(object):
    """represents the wall with four sides. self.wall[] indexes them counter clockwise, 0..3. 0 is bottom.
    Wall.tiles always holds references to all tiles in the game even when they are used"""
    tileClass = Tile
    def __init__(self, game):
        """init and position the wall"""
        self._game = weakref.ref(game)  # avoid cycles for garbage collection
        self.tiles = [self.tileClass('Xy') for _ in range(elements.count(game.ruleset))]
        self.living = None
        self.kongBox = None
        assert len(self.tiles) % 8 == 0

    @property
    def game(self):
        """hide the fact that this is a weakref"""
        return self._game()

    def deal(self, tileNames=None, deadEnd=False):
        """deal tiles. May raise WallEmpty.
        Returns a list of tiles"""
        if tileNames is None:
            tileNames = [None]
        count = len(tileNames)
        if deadEnd:
            if len(self.kongBox) < count:
                raise WallEmpty
            tiles = self.kongBox[-count:]
            self.kongBox = self.kongBox[:-count]
            if len(self.kongBox) % 2 == 0:
                self.placeLooseTiles()
        else:
            if len(self.living) < count:
                raise WallEmpty
            tiles = self.living[:count]
            self.living = self.living[count:]
        for tile, name in zip(tiles, tileNames):
            if name is not None:
                tile.element = name
        return tiles

    def build(self):
        """virtual: build visible wall"""

    def placeLooseTiles(self):
        """virtual: place two loose tiles on the dead wall"""

    def decorate(self):
        """virtual: show player info on the wall"""

    def hide(self):
        """virtual: hide all four walls and their decorators"""

    def divide(self):
        """divides a wall, building a living and and a dead end"""
        # neutralise the different directions of winds and removal of wall tiles
        assert self.game.divideAt is not None
        # shift tiles: tile[0] becomes living end
        self.tiles[:] = self.tiles[self.game.divideAt:] + self.tiles[0:self.game.divideAt]
        kongBoxSize = self.game.ruleset.kongBoxSize
        self.living = self.tiles[:-kongBoxSize]
        boxTiles = self.tiles[-kongBoxSize:]
        for pair in range(kongBoxSize // 2):
            boxTiles = boxTiles[:pair*2] + [boxTiles[pair*2+1], boxTiles[pair*2]] + boxTiles[pair*2+2:]
        self.kongBox = boxTiles
