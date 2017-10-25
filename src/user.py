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

The DBPasswordChecker is based on an example from the book
Twisted Network Programming Essentials by Abe Fettig, 2006
O'Reilly Media, Inc., ISBN 0-596-10032-9
"""

import datetime

from twisted.internet.defer import fail
from twisted.spread import pb

from common import Internal, Debug, Options, StrMixin
from servercommon import srvError
from log import logDebug
from mi18n import i18nE
from query import Query

class User(pb.Avatar, StrMixin):

    """the twisted avatar"""

    def __init__(self, userid):
        self.name = Query(
            'select name from player where id=?',
            (userid,
            )).records[0][0]
        self.mind = None
        self.server = None
        self.dbIdent = None
        self.voiceId = None
        self.maxGameId = None
        self.lastPing = None
        self.pinged()

    def pinged(self):
        """time of last ping or message from user"""
        self.lastPing = datetime.datetime.now()
        if self.server:
            self.server.lastPing = self.lastPing

    def source(self):
        """how did he connect?"""
        result = str(self.mind.broker.transport.getPeer())
        if 'UNIXAddress' in result:
            # socket: we want to get the socket name
            result = Options.socket
        return result

    def attached(self, mind):
        """override pb.Avatar.attached"""
        self.mind = mind
        self.server.login(self)

    def detached(self, unusedMind):
        """override pb.Avatar.detached"""
        if Debug.connections:
            logDebug(
                '%s: connection detached from %s' %
                (self, self.source()))
        self.server.logout(self)
        self.mind = None

    def perspective_setClientProperties(
            self, dbIdent, voiceId, maxGameId, clientVersion=None):
        """perspective_* methods are to be called remotely"""
        self.pinged()
        self.dbIdent = dbIdent
        self.voiceId = voiceId
        self.maxGameId = maxGameId
        serverVersion = Internal.defaultPort
        if clientVersion != serverVersion:
            # we assume that versions x.y.* are compatible
            if clientVersion is None:
                # client passed no version info
                return fail(srvError(pb.Error,
                                     i18nE(
                                         'Your client has a version older than 4.9.0 but you need %1 for this server'),
                                     serverVersion))
            else:
                commonDigits = len([x for x in zip(
                    clientVersion.split(b'.'),
                    serverVersion.split(b'.'))
                                    if x[0] == x[1]])
                if commonDigits < 2:
                    return fail(srvError(pb.Error,
                                         i18nE(
                                             'Your client has version %1 but you need %2 for this server'),
                                         clientVersion or '<4.9.0',
                                         '.'.join(serverVersion.split('.')[:2]) + '.*'))
        if Debug.table:
            logDebug('client has dbIdent={} voiceId={} maxGameId={} clientVersion {}'.format(
                self.dbIdent, self.voiceId, self.maxGameId, clientVersion))
        self.server.sendTables(self)

    def perspective_ping(self):
        """perspective_* methods are to be called remotely"""
        return self.pinged()

    def perspective_needRulesets(self, rulesetHashes):
        """perspective_* methods are to be called remotely"""
        return self.server.needRulesets(rulesetHashes)

    def perspective_joinTable(self, tableid):
        """perspective_* methods are to be called remotely"""
        return self.server.joinTable(self, tableid)

    def perspective_leaveTable(self, tableid):
        """perspective_* methods are to be called remotely"""
        return self.server.leaveTable(self, tableid)

    def perspective_newTable(
            self, ruleset, playOpen, autoPlay, wantedGame: str, tableId=None):
        """perspective_* methods are to be called remotely"""
        return self.server.newTable(self, ruleset, playOpen, autoPlay, wantedGame, tableId)

    def perspective_startGame(self, tableid):
        """perspective_* methods are to be called remotely"""
        return self.server.startGame(self, tableid)

    def perspective_logout(self):
        """perspective_* methods are to be called remotely"""
        self.detached(None)

    def perspective_chat(self, chatString):
        """perspective_* methods are to be called remotely"""
        self.pinged()
        return self.server.chat(chatString)

    def __str__(self):
        return self.name


