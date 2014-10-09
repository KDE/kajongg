# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2014 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from common import Debug, unicodeString, StrMixin
from message import Message
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
            assert value != 'None'
            if value is None:
                self.__setattr__(key, None)
            elif key.lower().endswith('tile'):
                self.__setattr__(key, Tile(value))
            elif key.lower().endswith('tiles'):
                self.__setattr__(key, TileList(value))
            elif key.lower().endswith('meld'):
                self.__setattr__(key, Meld(value))
            elif key.lower().endswith('melds'):
                self.__setattr__(key, MeldList(value))
            else:
                self.__setattr__(key, value)

    @property
    def player(self):
        """hide weakref"""
        if self._player:
            return self._player()

    @staticmethod
    def prettyKwargs(kwargs):
        """this is also used by the server, but the server does not use class Move"""
        result = ''
        for key, value in kwargs.items():
            if key == 'token':
                continue
            if isinstance(value, (list, tuple)) and isinstance(value[0], (list, tuple)):
                oldValue = value
                tuples = []
                for t in oldValue:
                    tuples.append(u''.join(unicodeString(x) for x in t))
                value = u','.join(tuples)
            if Debug.neutral and key == 'gameid':
                result += ' gameid:GAMEID'
            elif isinstance(value, bool) and value:
                result += ' %s' % key
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
