# -*- coding: utf-8 -*-
"""
Copyright (C) 2009-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

import weakref
from typing import Optional, TYPE_CHECKING, Dict, Any, Union, List, Tuple

from common import ReprMixin, Internal
from message import Message
from wind import Wind
from tile import Tile, TileTuple, Meld, MeldList

if TYPE_CHECKING:
    from tilesource import TileSource
    from player import PlayingPlayer


class Move(ReprMixin):  # pylint: disable=too-many-instance-attributes
    """used for decoded move information from the game server"""

    def __init__(self, player:Optional['PlayingPlayer'],
        command:Union[Message, str], kwargs:Dict[Any,Any]) ->None:

        # pylint: disable=too-many-statements

        self.message:Message
        if isinstance(command, Message):
            self.message = command
        else:
            assert isinstance(command, str) # for mypy
            self.message = Message.defined[command]
        self.tile:Tile
        self.lastTile:Tile
        self.withDiscardTile:Tile
        self.tiles:TileTuple
        self.table = None
        self.notifying = False
        self._player = weakref.ref(player) if player else None
        self.token = kwargs['token']
        self.kwargs = kwargs.copy()
        del self.kwargs['token']
        self.score = None
        self.lastMeld:Meld
        self.meld:Meld
        self.melds:MeldList
        self.exposedMeld:Meld
        self.source:'TileSource'
        self.md5sum:str
        self.wantedGame:str
        self.show:bool
        self.shouldSave:bool
        self.playerNames:List[Tuple[Wind, str]]
        self.deadEnd:bool
        self.mustRotateWinds:bool
        self.divideAt:int
        self.tableid:int
        self.gameid:int
        for key, value in kwargs.items():
            assert not isinstance(value, bytes), f'value is bytes:{repr(value)}'
            if value is None:
                self.__setattr__(key, None)
            else:
                if key.lower().endswith('tile'):
                    self.__setattr__(key, Tile(value))
                elif key.lower().endswith('tiles'):
                    self.__setattr__(key, TileTuple(value))
                elif key.lower().endswith('meld'):
                    self.__setattr__(key, Meld(value))
                elif key.lower().endswith('melds'):
                    self.__setattr__(key, MeldList(value))
                elif key == 'playerNames':
                    if Internal.isServer:
                        self.__setattr__(key, value)
                    else:
                        self.__setattr__(key, self.__convertWinds(value))
                else:
                    self.__setattr__(key, value)

    @staticmethod
    def __convertWinds(tuples:List[Tuple[str, str]]) ->List[Tuple[Wind, str]]:
        """convert wind strings to Wind objects"""
        result = []
        for wind, name in tuples:
            _  = Wind(wind), name
            result.append(_)
        return result

    @property
    def player(self) ->Optional['PlayingPlayer']:
        """hide weakref"""
        return self._player() if self._player else None

    def __str__(self) ->str:
        return f'{self.player!r} {self.message!r} {self.kwargs!r}'
