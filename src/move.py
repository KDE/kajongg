#!/usr/bin/env python
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

from util import m18n, logWarning
from game import Players
from query import Query
from message import Message
from scoringengine import Meld

class Move(object):
    def __init__(self, player, command, args):
        self.message = Message.byName(command)
        self.table = None
        self.player = player
        self.command = command
        self.args = args
        # those are only here to quieten pylint:
        self.seed = self.source = self.shouldSave = self.rotate = None
        self.withDiscard = self.lastTile = self.lastMeld = None
        self.winnerBalance = self.deadEnd = self.discardBoard = None
        self.divideAt = self.msg = self.tile = self.exposedMeld = None
        for key, value in args.items():
            self.__setattr__(key, value)
        if self.lastMeld:
            self.lastMeld = Meld(self.lastMeld)

    def __str__(self):
        return '%s %s %s' % (self.player, self.command, self.args)

    def __repr__(self):
        return '<Move: %s>' % self


