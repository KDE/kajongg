# -*- coding: utf-8 -*-

"""
Copyright (C) 2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from message import Message
from scoringengine import Meld

class Move(object): #pylint: disable=R0902
    """used for decoded move information from the game server"""
# pylint allow more than 7 instance attributes
    def __init__(self, player, command, args):
        if isinstance(command, Message):
            self.message = command
        else:
            self.message = Message.defined[command]
        self.table = None
        self.player = player
        self.args = args
        self.lastMeld = None
        for key, value in args.items():
            self.__setattr__(key, value)
        if self.lastMeld:
            self.lastMeld = Meld(self.lastMeld)

    def __str__(self):
        return '%s %s %s' % (self.player, self.message, self.args)

    def __repr__(self):
        return '<Move: %s>' % self

