# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

import weakref
from typing import TYPE_CHECKING, Optional, List, Union
from itertools import zip_longest
from twisted.internet.defer import Deferred

from common import ReprMixin
from tile import Piece, Tile, TileList

if TYPE_CHECKING:
    from game import Game
    from deferredutil import Request
    from uitile import UITile

class WallEmpty(Exception):

    """exception when trying to get a tile off the empty wall"""


class KongBox:

    """a non-ui kong box"""

    def __init__(self) ->None:
        self._tiles = []

    def fill(self, tiles:List[Union[Piece, 'UITile']]) ->None:
        """fill the box"""
        self._tiles = tiles

    def pop(self, count:int) ->List[Union[Piece, 'UITile']]:
        """get count tiles from kong box"""
        if len(self._tiles) < count:
            raise WallEmpty
        tiles = self._tiles[-count:]
        self._tiles = self._tiles[:-count]
        return tiles

    def __getitem__(self, index:int) ->Union[Piece, 'UITile']:
        return self._tiles[index]

    def __len__(self) ->int:
        """# of tiles in kong box"""
        return len(self._tiles)


class Wall(ReprMixin):

    """represents the wall with four sides. self.wall[] indexes them
    counter clockwise, 0..3. 0 is bottom.
    Wall.tiles always holds references to all tiles in the game even
    when they are used"""
    tileClass = Piece
    kongBoxClass = KongBox

    def __init__(self, game:'Game') ->None:
        """init and position the wall"""
        self._game = weakref.ref(game)  # avoid cycles for garbage collection
        self.tiles = [self.tileClass(Piece.unknownStr)
                      for _ in range(game.fullWallSize)]
        self.living = []
        self.kongBox = self.kongBoxClass()
        assert len(self.tiles) % 8 == 0

    @property
    def game(self) ->Optional['Game']:
        """hide the fact that this is a weakref"""
        return self._game()

    @staticmethod
    def __nameTile(tile:Union['UITile', Piece], element:'Tile') ->Union['UITile', Piece]:
        """define what tile this is"""
        if tile.__class__.__name__ == 'UITile':
            tile.change_name(element)
        else:
            tile = tile.change_name(element)
        return tile

    def deal(self, tiles:Union[TileList, Tile, None]=None, deadEnd:bool=False) ->List[Union['UITile', Piece]]:
        """deal tiles. May raise WallEmpty.
        Returns a list of tiles"""
        if isinstance(tiles, Tile):
            tiles = TileList(tiles)
        elif tiles is None:
            tiles = TileList(Tile.none)
        elif len(tiles) == 0:
            raise ValueError('Wall.deal() does not accept empty TileList()')
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
        return [self.__nameTile(x[0], x[1]) for x in zip_longest(dealTiles, tiles)]

    def build(self, shuffleFirst:bool=False) ->Deferred:  # pylint:disable=unused-argument
        """virtual: build visible wall"""
        return Deferred()

    def _placeLooseTiles(self, deferredResult:Optional['Request']=None) ->None:
        """to be done only for UIWall"""

    def decorate4(self, deferredResult:Optional['Request']=None) ->None:
        """virtual: show player info on the wall"""

    def hide(self) ->None:
        """virtual: hide all four walls and their decorators"""

    def divide(self) ->None:
        """divides a wall, building a living end and a dead end"""
        # neutralise the different directions of winds and removal of wall
        # tiles
        assert self.game
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

    def __len__(self) ->int:
        """Proxy for len(tiles)"""
        return len(self.tiles)

    @staticmethod
    def debug_name() ->str:
        """name for debug messages"""
        return '4sided wall'

    def __str__(self) ->str:
        """for debugging"""
        return self.debug_name()
