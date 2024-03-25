# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

import weakref

from common import StrMixin, Internal, id4
from message import Message
from wind import Wind
from tile import Tile, TileList
from meld import Meld, MeldList

class Move(StrMixin):

    """used for decoded move information from the game server"""

    def __init__(self, player, command, kwargs):
        if isinstance(command, Message):
            self.message = command
        else:
            self.message = Message.defined[command]
        self.table = None
        self.notifying = False
        self._player = weakref.ref(player) if player else None
        self.token = kwargs['token']
        self.kwargs = kwargs.copy()
        del self.kwargs['token']
        self.score = None
        self.lastMeld = None
        for key, value in kwargs.items():
            assert not isinstance(value, bytes), 'value is bytes:{}'.format(repr(value))
            if value is None:
                self.__setattr__(key, None)
            else:
                if key.lower().endswith('tile'):
                    self.__setattr__(key, Tile(value))
                elif key.lower().endswith('tiles'):
                    self.__setattr__(key, TileList(value))
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

    def __repr__(self):
        return 'Move_{}({!r} {!r} {!r}'.format(id4(self), self.player, self.message, self.kwargs)
