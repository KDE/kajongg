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

class NotifyAtOnceMessage(Message):
    def __init__(self, name, shortcut=None):
        Message.__init__(self, name, shortcut)
        self.notifyAtOnce = True

class MessagePung(NotifyAtOnceMessage):
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name=m18ncE('kajongg','Pung'),
            shortcut=m18ncE('kajongg game dialog:Key for Pung', 'P'))

if not Message.defined:
    """The text after 'Key for ' must be identical to the name"""
    Message.NO= Message('NO')
    Message.OK = Message(
        name=m18ncE('kajongg','OK'),
        shortcut=m18ncE('kajongg game dialog:Key for OK', 'O'))
    Message.NoClaim = Message(
        name=m18ncE('kajongg','No Claim'),
        shortcut=m18ncE('kajongg game dialog:Key for No claim', 'N'))
    Message.Discard = Message(
        name=m18ncE('kajongg','Discard'),
        shortcut=m18ncE('kajongg game dialog:Key for Discard', 'D'))
    Message.Pung = MessagePung()
    Message.Kong = NotifyAtOnceMessage(
        name=m18ncE('kajongg','Kong'),
        shortcut=m18ncE('kajongg game dialog:Key for Kong', 'K'))
    Message.Chow = NotifyAtOnceMessage(
        name=m18ncE('kajongg','Chow'),
        shortcut=m18ncE('kajongg game dialog:Key for Chow', 'C'))
    Message.MahJongg = NotifyAtOnceMessage(
        name=m18ncE('kajongg','Mah Jongg'),
        shortcut=m18ncE('kajongg game dialog:Key for Mah Jongg', 'M'))
    Message.OriginalCall = NotifyAtOnceMessage(
        name=m18ncE('kajongg','Original Call'),
        shortcut=m18ncE('kajongg game dialog:Key for Original Call', 'O'))
    Message.ViolatesOriginalCall = NotifyAtOnceMessage(
        name = m18ncE('kajongg', 'Violates Original Call'))
    Message.Bonus = Message('Bonus')
