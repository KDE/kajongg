#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from util import m18nc, m18ncE

class Message(object):
    """those are the message types between client and server"""

    defined = []

    @staticmethod
    def byName(name):
        for msg in Message.defined:
            if msg.name == name:
                return msg

    def __init__(self, name, shortcut=None):
        """those are the english values"""
        self.name = name
        self.methodName = name.replace(' ', '')
        self.shortcut = shortcut
        self.i18nName = m18nc('kajongg', self.name)
        self.notifyAtOnce = False
        self.id = len(Message.defined)
        Message.defined.append(self)

    def buttonCaption(self):
        """localized, with a & for the shortcut"""
        i18nShortcut = m18nc('kajongg game dialog:Key for '+self.name, self.shortcut)
        return self.i18nName.replace(i18nShortcut, '&'+i18nShortcut, 1)

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<Message: %s>" % self

    def isActivePlayer(self, table, msg):
        if msg.player == table.game.activePlayer:
            return True
        errMsg = '%s said %s but is not the active player' % (msg.player, msg.answer.name)
        self.abort(errMsg)

    def serverAction(self, table, msg):
        logException('serverAction is not defined for %s. msg:%s' % (self, msg))

class NotifyAtOnceMessage(Message):
    def __init__(self, name, shortcut=None):
        Message.__init__(self, name, shortcut)
        self.notifyAtOnce = True

class MessagePung(NotifyAtOnceMessage):
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name=m18ncE('kajongg','Pung'),
            shortcut=m18ncE('kajongg game dialog:Key for Pung', 'P'))
    def serverAction(self, table, msg):
        table.claimTile(msg.player, self, msg.args[0], 'calledPung')

class MessageKong(NotifyAtOnceMessage):
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name=m18ncE('kajongg','Kong'),
            shortcut=m18ncE('kajongg game dialog:Key for Kong', 'K'))
    def serverAction(self, table, msg):
        if msg.player == table.game.activePlayer:
            table.declareKong(msg.player, msg.args[0])
        else:
            table.claimTile(msg.player, self, msg.args[0], 'calledKong')

class MessageChow(NotifyAtOnceMessage):
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name=m18ncE('kajongg','Chow'),
            shortcut=m18ncE('kajongg game dialog:Key for Chow', 'C'))
    def serverAction(self, table, msg):
        if table.game.nextPlayer() != msg.player:
            table.abort('player %s illegally said Chow' % msg.player)
        else:
            table.claimTile(msg.player, self, msg.args[0], 'calledChow')

class MessageBonus(Message):
    def __init__(self):
        Message.__init__(self, 'Bonus')
    def serverAction(self, table, msg):
        if self.isActivePlayer(table, msg):
            table.pickedBonus(msg.player, msg.args[0])

class MessageMahJongg(NotifyAtOnceMessage):
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name=m18ncE('kajongg','Mah Jongg'),
            shortcut=m18ncE('kajongg game dialog:Key for Mah Jongg', 'M'))
    def serverAction(self, table, msg):
        table.claimMahJongg(msg)

class MessageOriginalCall(NotifyAtOnceMessage):
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name=m18ncE('kajongg','Original Call'),
            shortcut=m18ncE('kajongg game dialog:Key for Original Call', 'O'))
    def serverAction(self, table, msg):
        if self.isActivePlayer(table, msg):
            msg.player.originalCall = True
            table.tellAll(msg.player, 'madeOriginalCall', table.moved)

class MessageViolatesOriginalCall(NotifyAtOnceMessage):
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name = m18ncE('kajongg', 'Violates Original Call'))
    def serverAction(self, table, msg):
        if self.isActivePlayer(table, msg):
            msg.player.mayWin = False
            table.tellAll(msg.player, 'violatedOriginalCall', table.moved)

class MessageDiscard(Message):
    def __init__(self):
        Message.__init__(self,
            name=m18ncE('kajongg','Discard'),
            shortcut=m18ncE('kajongg game dialog:Key for Discard', 'D'))
    def serverAction(self, table, msg):
        if self.isActivePlayer(table, msg):
            tile = msg.args[0]
            if tile not in msg.player.concealedTiles:
                table.abort('player %s discarded %s but does not have it' % (msg.player, tile))
                return
            table.game.hasDiscarded(msg.player, tile)
            table.tellAll(msg.player,'hasDiscarded', table.moved, tile=tile)

if not Message.defined:
    """The text after 'Key for ' must be identical to the name"""
    Message.NO= Message('NO')
    Message.OK = Message(
        name=m18ncE('kajongg','OK'),
        shortcut=m18ncE('kajongg game dialog:Key for OK', 'O'))
    Message.NoClaim = Message(
        name=m18ncE('kajongg','No Claim'),
        shortcut=m18ncE('kajongg game dialog:Key for No claim', 'N'))
    Message.Discard = MessageDiscard()
    Message.Pung = MessagePung()
    Message.Kong = MessageKong()
    Message.Chow = MessageChow()
    Message.MahJongg = MessageMahJongg()
    Message.OriginalCall = MessageOriginalCall()
    Message.ViolatesOriginalCall = MessageViolatesOriginalCall()
    Message.Bonus = MessageBonus()
