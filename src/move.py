# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

import weakref
from typing import Optional, TYPE_CHECKING, Dict, Any, Union, Type

from common import ReprMixin, Internal
from message import Message
from wind import Wind
from tile import Tile, TileTuple, Meld, MeldList

if TYPE_CHECKING:
    from tilesource import TileSource
    from player import PlayingPlayer


class Move(ReprMixin):
    """used for decoded move information from the game server"""

    def __init__(self, player:Optional['PlayingPlayer'],
        command:Union[Type[Message], str], kwargs:Dict[Any,Any]) ->None:
        if isinstance(command, Message):
            self.message = command
        else:
            assert isinstance(command, str) # for mypy
            self.message = Message.defined[command]
        self.table = None
        self.notifying = False
        self._player = weakref.ref(player) if player else None
        self.token = kwargs['token']
        self.kwargs = kwargs.copy()
        del self.kwargs['token']
        self.score = None
        for key, value in kwargs.items():
            assert not isinstance(value, bytes), 'value is bytes:{}'.format(repr(value))
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
    def __convertWinds(tuples):
        """convert wind strings to Wind objects"""
        result = []
        for wind, name in tuples:
            result.append(tuple([Wind(wind), name]))
        return result

    @property
    def player(self):
        """hide weakref"""
        return self._player() if self._player else None

    def __str__(self):
        return '{!r} {!r} {!r}'.format(self.player, self.message, self.kwargs)
