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

from common import elements
from tile import Tile

class WallEmpty(Exception):
    """exception when trying to get a tile off the empty wall"""
    pass

class Wall(object):
    """represents the wall with four sides. self.wall[] indexes them counter clockwise, 0..3. 0 is bottom."""
    def __init__(self, game):
        """init and position the wall"""
        # we use only white dragons for building the wall. We could actually
        # use any tile because the face is never shown anyway.
        self.game = game
        self.tileCount = elements.count(game.ruleset.withBonusTiles)
        self.tiles = []
        self.living = None
        self.kongBox = None
        assert self.tileCount % 8 == 0
        self.length = self.tileCount // 8

    def dealTo(self, player=None, deadEnd=False, count=1):
        """deal tiles to player. May raise WallEmpty.
        Returns a list of tileNames"""
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
        tileNames = [x.element for x in tiles]
        for tile in tiles:
            tile.board = None
            del tile
        if player:
            for tile in tileNames:
                player.addTile(tile)
        return tileNames

    def removeTiles(self, count, deadEnd=False):
        """remove count tiles from the living or dead end. Removes the
        number of actually removed tiles"""
        removed = 0
        for loop in range(count):
            if deadEnd:
                tile = self.kongBox[-1]
                self.kongBox = self.kongBox[:-1]
                if len(self.kongBox) % 2 == 0:
                    self.placeLooseTiles()
            else:
                tile = self.living[0]
                self.living = self.living[1:]
            tile.board = None
            del tile
            removed += 1
        return removed

    def build(self, randomGenerator, tiles=None):
        """builds the wall from tiles without dividing them"""

        # first do a normal build without divide
        # replenish the needed tiles
        if tiles:
            self.tiles = tiles
            assert len(tiles) == self.tileCount
            randomGenerator.shuffle(self.tiles)
        else:
            self.tiles.extend(Tile('Xy') for x in range(self.tileCount-len(self.tiles)))
            self.tiles = self.tiles[:self.tileCount] # in case we have to reduce. Possible at all?

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
        assert len(self.tiles) == self.tileCount
        self.tiles[:] = self.tiles[self.game.divideAt:] + self.tiles[0:self.game.divideAt]
        kongBoxSize = self.game.ruleset.kongBoxSize
        self.living = self.tiles[:-kongBoxSize]
        boxTiles = self.tiles[-kongBoxSize:]
        for pair in range(kongBoxSize // 2):
            boxTiles = boxTiles[:pair*2] + [boxTiles[pair*2+1], boxTiles[pair*2]] + boxTiles[pair*2+2:]
        self.kongBox = boxTiles

