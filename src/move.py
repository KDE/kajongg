# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from common import Debug, unicodeString, StrMixin, nativeString
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
            self.message = Message.defined[nativeString(command)]
        self.table = None
        self.notifying = False
        self._player = weakref.ref(player) if player else None
        self.token = kwargs['token']
        self.kwargs = kwargs.copy()
        del self.kwargs['token']
        self.score = None
        self.lastMeld = None
        for key, value in kwargs.items():
            assert value != 'None'
            if value is None:
                self.__setattr__(key, None)
            elif key.lower().endswith('tile'):
                self.__setattr__(key, Tile(nativeString(value)))
            elif key.lower().endswith('tiles'):
                self.__setattr__(key, TileList(nativeString(value)))
            elif key.lower().endswith('meld'):
                self.__setattr__(key, Meld(nativeString(value)))
            elif key.lower().endswith('melds'):
                self.__setattr__(key, MeldList(nativeString(value)))
            elif key in ('wantedGame', 'score'):
                self.__setattr__(key, nativeString(value))
            elif key == 'playerNames':
                self.__setattr__(key, self.convertWinds(value))
            else:
                self.__setattr__(key, value)

    @staticmethod
    def convertWinds(tuples):
        """convert wind strings to Wind objects"""
        if isinstance(tuples[0][0], Wind):
            return tuples
        result = list()
        for wind, name in tuples:
            result.append(tuple([Wind(wind), name]))
        return result

    @property
    def player(self):
        """hide weakref"""
        if self._player:
            return self._player()

    @staticmethod
    def prettyKwargs(kwargs):
        """this is also used by the server, but the server does not use class Move"""
        result = u''
        for key in sorted(kwargs.keys()):
            value = kwargs[key]
            if key == 'token':
                continue
            if isinstance(value, (list, tuple)) and isinstance(value[0], (list, tuple)):
                oldValue = value
                tuples = []
                for oldTuple in oldValue:
                    tuples.append(u''.join(unicodeString(x) for x in oldTuple))
                value = u','.join(tuples)
            if Debug.neutral and key == 'gameid':
                result += u' gameid:GAMEID'
            elif isinstance(value, bool) and value:
                result += u' %s' % key
            elif isinstance(value, bool):
                pass
            elif isinstance(value, bytes):
                result += u' %s:%s' % (key, unicodeString(value))
            else:
                result += u' %s:%s' % (key, value)
        for old, new in ((u"('", u"("), (u"')", u")"), (u" '", u""),
                         (u"',", u","), (u"[(", u"("), (u"])", u")")):
            result = result.replace(old, new)
        return result

    def __unicode__(self):
        return u'%s %s%s' % (self.player, self.message, Move.prettyKwargs(self.kwargs))
