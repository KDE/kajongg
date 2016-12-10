# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

import weakref

from common import StrMixin
from tile import Tile, elements


class WallEmpty(Exception):

    """exception when trying to get a tile off the empty wall"""
    pass


class KongBox(object):

    """a non-ui kong box"""

    def __init__(self):
        self._tiles = []

    def fill(self, tiles):
        """fill the box"""
        self._tiles = tiles

    def pop(self, count):
        """get count tiles from kong box"""
        if len(self._tiles) < count:
            raise WallEmpty
        tiles = self._tiles[-count:]
        self._tiles = self._tiles[:-count]
        return tiles

    def __getitem__(self, index):
        return self._tiles[index]

    def __len__(self):
        """# of tiles in kong box"""
        return len(self._tiles)


class Wall(StrMixin):

    """represents the wall with four sides. self.wall[] indexes them
    counter clockwise, 0..3. 0 is bottom.
    Wall.tiles always holds references to all tiles in the game even
    when they are used"""
    tileClass = Tile
    kongBoxClass = KongBox

    def __init__(self, game):
        """init and position the wall"""
        self._game = weakref.ref(game)  # avoid cycles for garbage collection
        self.tiles = [self.tileClass(Tile.unknown)
                      for _ in range(elements.count(game.ruleset))]
        self.living = None
        self.kongBox = self.kongBoxClass()
        assert len(self.tiles) % 8 == 0

    @property
    def game(self):
        """hide the fact that this is a weakref"""
        return self._game()

    @staticmethod
    def __nameTile(tile, element):
        """define what tile this is"""
        if element is None:
            return tile
        assert isinstance(element, Tile), element
        if isinstance(tile, Tile):
            return element
        else:
            # tile is UITile
            tile.tile = element
            return tile

    def deal(self, tiles=None, deadEnd=False):
        """deal tiles. May raise WallEmpty.
        Returns a list of tiles"""
        if tiles is None:
            tiles = [None]
        count = len(tiles)
        if deadEnd:
            dealTiles = self.kongBox.pop(count)
            if len(self.kongBox) % 2 == 0:
                self._placeLooseTiles()
        else:
            if len(self.living) < count:
                raise WallEmpty
            dealTiles = self.living[:count]
            self.living = self.living[count:]
        return list(self.__nameTile(*x)
                    for x in zip(dealTiles, tiles))

    def build(self, shuffleFirst=False):
        """virtual: build visible wall"""

    def _placeLooseTiles(self, deferredResult=None):
        """to be done only for UIWall"""
        pass

    def decorate(self):
        """virtual: show player info on the wall"""

    def hide(self):
        """virtual: hide all four walls and their decorators"""

    def divide(self):
        """divides a wall, building a living and and a dead end"""
        # neutralise the different directions of winds and removal of wall
        # tiles
        assert self.game.divideAt is not None
        # shift tiles: tile[0] becomes living end
        self.tiles[:] = self.tiles[
            self.game.divideAt:] + \
            self.tiles[0:self.game.divideAt]
        kongBoxSize = self.game.ruleset.kongBoxSize
        self.living = self.tiles[:-kongBoxSize]
        boxTiles = self.tiles[-kongBoxSize:]
        for pair in range(kongBoxSize // 2):
            boxTiles = boxTiles[:pair * 2] + [
                boxTiles[pair * 2 + 1],
                boxTiles[pair * 2]] + \
                boxTiles[pair * 2 + 2:]
        self.kongBox.fill(boxTiles)

    @staticmethod
    def name():
        """name for debug messages"""
        return u'4sided wall'

    def __unicode__(self):
        """for debugging"""
        return self.name()
