# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0


The DBPasswordChecker is based on an example from the book
Twisted Network Programming Essentials by Abe Fettig, 2006
O'Reilly Media, Inc., ISBN 0-596-10032-9
"""

import datetime
from typing import Optional, TYPE_CHECKING, List, Any, Union

from twisted.internet.defer import fail
from twisted.spread import pb

from common import Internal, Debug, Options, ReprMixin
from servercommon import srvError
from log import logDebug
from mi18n import i18nE
from query import Query

if TYPE_CHECKING:
    from twisted.internet.defer import Deferred
    from server import MJServer
    from rule import Ruleset


class User(pb.Avatar, ReprMixin):

    """the twisted avatar"""

    def __init__(self, userid:str) ->None:
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

    def pinged(self) ->None:
        """time of last ping or message from user"""
        self.lastPing = datetime.datetime.now()
        if self.server:
            self.server.lastPing = self.lastPing

    def source(self) ->str:
        """how did he connect?"""
        if self.mind is None:
            result = 'SOURCE UNKNOWN: self.mind is None'
        else:
            result = str(self.mind.broker.transport.getPeer())
        if 'UNIXAddress' in result:
            # socket: we want to get the socket name
            result = Options.socket or 'ERROR: Options.socket is None'
        return result

    def attached(self, mind:pb.RemoteReference) ->None:
        """override pb.Avatar.attached"""
        self.mind = mind
        assert self.server
        self.server.login(self)

    def detached(self, unusedMind:Optional[pb.RemoteReference]=None) ->None:
        """override pb.Avatar.detached"""
        if Debug.connections:
            logDebug(
                '%s: connection detached from %s' %
                (self, self.source()))
        assert self.server
        self.server.logout(self)
        self.mind = None

    def perspective_setClientProperties(
            self, dbIdent:str, voiceId:str, maxGameId:int, clientVersion:Optional[str]=None) ->Optional['Deferred']:
        """perspective_* methods are to be called remotely"""
        self.pinged()
        self.dbIdent = dbIdent
        self.voiceId = voiceId
        self.maxGameId = maxGameId
        serverVersion = Internal.defaultPort
        if clientVersion != serverVersion:
            if clientVersion is None:
                # client passed no version info
                return fail(srvError(
                                     i18nE(
                                         'Your client has a version older than 4.9.0 but you need %1 for this server'),
                                     serverVersion))
            return fail(srvError(pb.Error,
                                 i18nE(
                                     'Your client has version %1 but you need %2 for this server'),
                                 clientVersion or '<4.9.0',
                                 serverVersion))
        if Debug.table:
            logDebug('client has dbIdent={} voiceId={} maxGameId={} clientVersion {}'.format(
                self.dbIdent, self.voiceId, self.maxGameId, clientVersion))
        assert self.server
        self.server.sendTables(self)
        return None

    def perspective_ping(self) ->None:
        """perspective_* methods are to be called remotely"""
        return self.pinged()

    def perspective_needRulesets(self, rulesetHashes:List[str]) ->List[List[List[Union[int, str, float]]]]:
        """perspective_* methods are to be called remotely"""
        assert self.server
        return self.server.needRulesets(rulesetHashes)

    def perspective_joinTable(self, tableid:int) ->bool:
        """perspective_* methods are to be called remotely"""
        assert self.server
        return self.server.joinTable(self, tableid)

    def perspective_leaveTable(self, tableid:int) ->bool:
        """perspective_* methods are to be called remotely"""
        assert self.server
        return self.server.leaveTable(self, tableid, 'correctly left table {}'.format(tableid))

    def perspective_newTable(
            self, ruleset:str, playOpen:bool, autoPlay:bool, wantedGame: str,
            tableId:Optional[int]=None) ->Optional[Any]:
        """perspective_* methods are to be called remotely"""
        assert self.server
        return self.server.newTable(self, ruleset, playOpen, autoPlay, wantedGame, tableId)

    def perspective_startGame(self, tableid:int) ->None:
        """perspective_* methods are to be called remotely"""
        assert self.server
        self.server.startGame(self, tableid)

    def perspective_logout(self) ->None:
        """perspective_* methods are to be called remotely"""
        self.detached(None)

    def perspective_chat(self, chatString:str) ->None:
        """perspective_* methods are to be called remotely"""
        self.pinged()
        assert self.server
        self.server.chat(chatString)

    def __str__(self) ->str:
        return self.name
