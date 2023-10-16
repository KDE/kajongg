# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0


The DBPasswordChecker is based on an example from the book
Twisted Network Programming Essentials by Abe Fettig, 2006
O'Reilly Media, Inc., ISBN 0-596-10032-9
"""

# pylint: disable=wrong-import-order, wrong-import-position

import sys
import os
import logging
import datetime
import argparse
from typing import TYPE_CHECKING, Tuple, Any, Optional, Sequence, List, Mapping, Dict, Union, cast, Type

from zope.interface import implementer


def cleanExit(*unusedArgs: Any) ->None:
    """we want to cleanly close sqlite3 files"""
    if Debug.quit:
        logDebug('cleanExit')
    if Options.socket and sys.platform != 'win32':
        if os.path.exists(Options.socket):
            os.remove(Options.socket)
    try:
        if Internal.db:
            Internal.db.close()
                              # setting to None does not call close(), do we
                              # need close?
        logging.shutdown()
        os._exit(0)  # pylint: disable=protected-access
    except NameError:
        logging.shutdown()
    try:
        reactor.stop()  # type:ignore[misc]
    except NameError:
        sys.exit(0)
    except ReactorNotRunning:
        pass

from common import handleSignals
handleSignals(cleanExit)

from common import Options, Internal, Debug
Internal.isServer = True
Internal.logPrefix = 'S'

from twisted.spread import pb
from twisted.internet.interfaces import IReactorCore
from twisted.internet import error
from twisted.internet.defer import maybeDeferred, fail, succeed, Deferred
from twisted.cred import checkers, portal, credentials, error as credError
from twisted.internet import reactor as reactor_module
from twisted.internet.error import ReactorNotRunning
if TYPE_CHECKING:
    from twisted.python.failure import Failure

reactor = cast(IReactorCore, reactor_module)
reactor.addSystemEventTrigger('before', 'shutdown', cleanExit)  # type:ignore[arg-type]
Internal.reactor = reactor  # type:ignore[assignment]

from player import Players
from query import Query, initDb
from log import logDebug, logWarning, logError, logInfo, logException, SERVERMARK
from mi18n import i18n, i18nE
from util import elapsedSince
from message import Message, ChatMessage
from deferredutil import DeferredBlock
from rule import Ruleset
from servercommon import srvError, srvMessage
from user import User
from servertable import ServerTable, ServerGame


@implementer(checkers.ICredentialsChecker)
class DBPasswordChecker:

    """checks against our sqlite3 databases"""
    credentialInterfaces = (credentials.IUsernamePassword,
                            credentials.IUsernameHashedPassword)

    def requestAvatarId(self, cred: pb._PortalAuthChallenger) ->Deferred:
        """get user id from database"""
        cred.username = cred.username.decode('utf-8')
        args = cred.username.split(SERVERMARK)
        if len(args) > 1:
            if args[0] == 'adduser':
                cred.username = args[1]
                password = args[2]
                query = Query(
                    'insert or ignore into player(name,password) values(?,?)',
                    (cred.username,
                     password))
            elif args[1] == 'deluser':
                pass
        query = Query(
            'select id, password from player where name=?', (cred.username,))
        if not query.records:
            template = 'Wrong username: %1'
            if Debug.connections:
                logDebug(i18n(template, cred.username))
            return fail(credError.UnauthorizedLogin(srvMessage(template, cred.username)))
        userid, password = query.records[0]
        defer1 = maybeDeferred(cred.checkPassword, password.encode('utf-8'))
        defer1.addCallback(DBPasswordChecker._checkedPassword, userid).addErrback(logException)
        return defer1

    @staticmethod
    def _checkedPassword(matched: bool, userid:str) ->Union[str, Deferred]:
        """after the password has been checked. TODO: is the result type correct?"""
        if not matched:
            return fail(credError.UnauthorizedLogin(srvMessage(i18nE('Wrong password'))))
        return userid


class MJServer:

    """the real mah jongg server"""

    def __init__(self) ->None:
        self.tables:Dict[int, ServerTable] = {}
        self.srvUsers:List[User] = []
        Players.load()
        self.lastPing = datetime.datetime.now()
        self.checkPings()

    def chat(self, chatString:str) ->None:
        """a client sent us a chat message"""
        # FIXME: why does this work?
        chatLine = ChatMessage(chatString)  # type:ignore[arg-type]


        self.tables[chatLine.tableid].sendChatMessage(chatLine)

    def login(self, user: User) ->None:
        """accept a new user"""
        if user not in self.srvUsers:
            self.srvUsers.append(user)
            self.loadSuspendedTables(user)

    def callRemote(self, user:User, *args: Any, **kwargs:Mapping[Any, Any]) ->Deferred:
        """if we still have a connection, call remote, otherwise clean up"""
        if user.mind:
            try:
                args2, kwargs2 = Message.jellyAll(args, kwargs)
                return user.mind.callRemote(*args2, **kwargs2).addErrback(MJServer.ignoreLostConnection)
            except (pb.DeadReferenceError, pb.PBConnectionLost):
                user.mind = None
                self.logout(user)
        return succeed([])

    @staticmethod
    def __stopAfterLastDisconnect() ->None:
        """as the name says"""
        if Options.socket and not Options.continueServer:
            try:
                reactor.stop()  # type:ignore[misc]
                if Debug.connections:
                    logDebug('local server terminates from %s. Reason: last client disconnected' % (
                        Options.socket))
            except ReactorNotRunning:
                pass

    def checkPings(self) ->None:
        """are all clients still alive? If not log them out"""
        since = elapsedSince(self.lastPing)
        if self.srvUsers and since > 30:
            if Debug.quit:
                logDebug('no ping since {} seconds but we still have users:{}'.format(
                    elapsedSince(self.lastPing), self.srvUsers))
        if not self.srvUsers and since > 30:
            # no user at all since 30 seconds, but we did already have a user
            self.__stopAfterLastDisconnect()
        for user in self.srvUsers:
            if elapsedSince(user.lastPing) > 60:
                logInfo(
                    'No messages from %s since 60 seconds, clearing connection now' %
                    user.name)
                user.mind = None
                self.logout(user)
        reactor.callLater(10, self.checkPings)

    @staticmethod
    def ignoreLostConnection(failure: 'Failure') ->None:
        """if the client went away correctly, do not dump error messages on stdout."""
        msg = failure.getErrorMessage()
        if 'twisted.internet.error.ConnectionDone' not in msg:
            logError(msg)
        failure.trap(pb.PBConnectionLost)

    def sendTables(self, user:User, tables:Optional[List[ServerTable]]=None) ->Deferred:
        """send tables to user. If tables is None, he gets all new tables and those
        suspended tables he was sitting on"""
        if tables is None:
            tables = [
                x for x in self.tables.values()
                if not x.running and (not x.suspendedAt or x.hasName(user.name))]
        if tables:
            data = [x.asSimpleList() for x in tables]
            if Debug.table:
                logDebug(
                    'sending %d tables to %s: %s' %
                    (len(tables), user.name, data))
            return self.callRemote(user, 'newTables', data)
        return succeed([])

    def _lookupTable(self, tableid: int) ->ServerTable:
        """return table by id or raise exception"""
        if tableid not in self.tables:
            srvError(
                pb.Error,
                i18nE('table with id <numid>%1</numid> not found'),
                tableid)
        return self.tables[tableid]

    def generateTableId(self) ->int:
        """generates a new table id: the first free one"""
        usedIds = set(self.tables or [0])
        availableIds = set(x for x in range(1, 2 + max(usedIds)))
        return min(availableIds - usedIds)

    def newTable(self, user:User, ruleset:str, playOpen:bool,
                 autoPlay:bool, wantedGame:str, tableId:Optional[int]=None) ->Optional[Deferred]:
        """user creates new table and joins it"""
        def gotRuleset(ruleset:str) ->None:
            """now we have the full ruleset definition from the client"""
            Ruleset.cached(
                ruleset).save()  # make it known to the cache and save in db
        if tableId in self.tables:
            assert tableId is not None  # for mypy
            return fail(srvError(pb.Error,
                                 'You want a new table with id=%d but that id is already used for table %s' % (
                                     tableId, self.tables[tableId])))
        if Ruleset.hashIsKnown(ruleset):
            return self.__newTable(None, user, ruleset, playOpen, autoPlay, wantedGame, tableId)
        _ = self.callRemote(user, 'needRuleset', ruleset)
        if _:
            return _.addCallback(
                gotRuleset).addErrback(logException).addCallback(
                    self.__newTable, user, ruleset, playOpen, autoPlay, wantedGame, tableId).addErrback(logException)
        return None

    def __newTable(self, unused:None, user:User, ruleset:str,
                   playOpen:bool, autoPlay:bool, wantedGame:str, tableId:Optional[int]=None) ->Deferred:
        """now we know the ruleset"""
        def sent(unused: Any) ->int:
            """new table sent to user who created it"""
            return table.tableid
        table = ServerTable(
            self,
            owner=user,
            ruleset=ruleset,
            suspendedAt=None,
            playOpen=playOpen,
            autoPlay=autoPlay,
            wantedGame=wantedGame,
            tableId=tableId)
        result = None
        for srvUser in self.srvUsers:
            deferred = self.sendTables(srvUser, [table])
            if user == srvUser:
                result = deferred
                deferred.addCallback(sent).addErrback(logException)
        assert result
        return result

    def needRulesets(self, rulesetHashes: List[str]) -> List[List[List[Union[int, str, float]]]]:
        """the client wants those full rulesets"""
        result = []
        for table in self.tables.values():
            if table.ruleset.hash in rulesetHashes:
                result.append(table.ruleset.toList())
        return result

    def joinTable(self, user: User, tableid: int) ->bool:
        """user joins table"""
        table = self._lookupTable(tableid)
        table.addUser(user)
        block = DeferredBlock(table, where='joinTable')
        block.tell(
            None,
            self.srvUsers,
            Message.TableChanged,
            source=table.asSimpleList())
        if len(table.users) == table.maxSeats():
            if Debug.table:
                logDebug('Table %s: All seats taken, starting' % table)

            def startTable(unused: Any) -> None:
                """now all players know about our join"""
                assert table.owner
                table.readyForGameStart(table.owner)
            block.callback(startTable)
        else:
            block.callback(False)
        return True

    def tablesWith(self, user: User) ->List[int]:
        """table ids with user, except table 'without'"""
        return [x.tableid for x in self.tables.values() if user in x.users]

    def leaveTable(self, user: User, tableid: int, message: str, *args: str) ->bool:
        """user leaves table. If no human user is left on a new table, remove it"""
        if tableid in self.tables:
            table = self.tables[tableid]
            if user in table.users:
                if len(table.users) == 1 and not table.suspendedAt:
                    # silent: do not tell the user who left the table that he
                    # did
                    self.removeTable(table, 'silent', message, *args)
                else:
                    table.delUser(user)
                    if self.srvUsers:
                        block = DeferredBlock(table, where='leaveTable')
                        block.tell(
                            None,
                            self.srvUsers,
                            Message.TableChanged,
                            source=table.asSimpleList())
                        block.callback(False)
        return True

    def startGame(self, user: User, tableid: int) ->None:
        """try to start the game"""
        self._lookupTable(tableid).readyForGameStart(user)

    def removeTable(self, table: ServerTable, reason: str, message: str, *args:Union[str, int]) ->None:
        """remove a table"""
        assert reason in ('silent', 'tableRemoved', 'gameOver', 'abort')
        # HumanClient implements methods remote_tableRemoved etc.
        if Debug.connections or reason == 'abort':
            logDebug(
                '%s%s ' % (('%d:' % table.game.seed) if table.game else '',
                           i18n(message, *args)), withGamePrefix=False)
        if table.tableid in self.tables:
            del self.tables[table.tableid]
            if reason == 'silent':
                tellUsers = []
            else:
                tellUsers = table.users if table.running else self.srvUsers
            for user in tellUsers:
                # this may in turn call removeTable again!
                self.callRemote(user, reason, table.tableid, message, *args)
            for user in table.users:
                table.delUser(user)
            if Debug.table:
                logDebug(
                    'removing table %d: %s %s' %
                    (table.tableid, i18n(message, *args), reason))
        if table.game:
            table.game.close()

    def logout(self, user: User) ->None:
        """remove user from all tables"""
        if user not in self.srvUsers:
            return
        self.srvUsers.remove(user)
        for tableid in self.tablesWith(user):
            self.leaveTable(
                user,
                tableid,
                i18nE('Player %1 has logged out'),
                user.name)
        # wait a moment. We want the leaveTable message to arrive everywhere before
        # we say serverDisconnects. Sometimes the order was reversed.
        reactor.callLater(1, self.__logout2, user)

    def __logout2(self, user: User) ->None:
        """now the leaveTable message had a good chance to get to the clients first"""
        self.callRemote(user, 'serverDisconnects')
        user.mind = None
        for block in DeferredBlock.blocks:
            for request in block.requests:
                if request.user == user:
                    request.answer = Message.Abort

    def loadSuspendedTables(self, user: User) ->None:
        """loads all yet unloaded suspended tables where this
        user is participating. We do not unload them if the
        user logs out, there are filters anyway returning only
        the suspended games for a certain user.
        Never load old autoplay games."""
        query = Query("select distinct g.id, g.starttime, "
                      "g.seed, "
                      "ruleset, s.scoretime "
                      "from game g, player p0, score s,"
                      "player p1, player p2, player p3 "
                      "where autoplay=0 "
                      " and p0.id=g.p0 and p1.id=g.p1 "
                      " and p2.id=g.p2 and p3.id=g.p3 "
                      " and (p0.name=? or p1.name=? or p2.name=? or p3.name=?) "
                      " and s.game=g.id"
                      " and g.endtime is null"
                      " and exists(select 1 from ruleset where ruleset.id=g.ruleset)"
                      " and exists(select 1 from score where game=g.id)"
                      " and s.scoretime = (select max(scoretime) from score where game=g.id) limit 10",
                      (user.name, user.name, user.name, user.name))
        for gameid, _, seed, ruleset, suspendTime in query.records:
            if gameid not in (x.game.gameid for x in self.tables.values() if x.game):
                table = ServerTable(
                    self, None, ruleset, suspendTime, playOpen=False,
                    autoPlay=False, wantedGame=str(seed))
                table.game = cast(ServerGame, ServerGame.loadFromDB(gameid))


@implementer(portal.IRealm)
class MJRealm:

    """connects mind and server"""

    def __init__(self) ->None:
        self.server : Optional[MJServer] = None

    def requestAvatar(self, avatarId: str, mind: pb.RemoteReference,
        *interfaces: Sequence[pb.IPerspective]) -> Tuple[Type[pb.IPerspective], User, Any]:
        """as the tutorials do..."""
        if pb.IPerspective not in interfaces:
            raise NotImplementedError("No supported avatar interface")
        avatar = User(avatarId)
        avatar.server = self.server
        avatar.attached(mind)
        if Debug.connections:
            logDebug('Connection from %s ' % avatar.source())
        return pb.IPerspective, avatar, lambda a=avatar: a.detached(mind)

def parseArgs() -> argparse.Namespace:
    """as the name says"""
    parser = argparse.ArgumentParser()
    defaultPort = Internal.defaultPort
    parser.add_argument('--port', dest='port',
                      help=i18n(
                          'the server will listen on PORT (%d)' %
                          defaultPort),
                      type=int, default=defaultPort)
    parser.add_argument('--socket', dest='socket',
                      help=i18n('the server will listen on SOCKET'), default=None)
    parser.add_argument(
        '--db',
        dest='dbpath',
        help=i18n('name of the database'),
        default=None)
    parser.add_argument(
        '--continue', dest='continueServer', action='store_true',
        help=i18n('do not terminate local game server after last client disconnects'), default=False)
    parser.add_argument('--debug', dest='debug',
                      help=Debug.help())
    args = parser.parse_args(sys.argv[1:])
    Options.continueServer |= args.continueServer
    if args.dbpath:
        Options.dbPath = os.path.expanduser(args.dbpath)
    if args.socket:
        Options.socket = args.socket
    Debug.setOptions(args.debug)
    Options.fixed = True  # may not be changed anymore
    del parser           # makes Debug.gc quieter
    return args


def kajonggServer() ->None:
    """start the server"""
    options = parseArgs()
    if not initDb():
        sys.exit(1)
    realm = MJRealm()
    realm.server = MJServer()
    kajonggPortal = portal.Portal(realm, [DBPasswordChecker()])
    import predefined
    predefined.load()
    try:
        if Options.socket:
            # we do not want tracebacks to go from server to client,
            # please check on the server side instead
            factory = pb.PBServerFactory(kajonggPortal, unsafeTracebacks=False)
            if sys.platform == 'win32':
                if Debug.connections:
                    logDebug(
                        'local server listening on 127.0.0.1 port %d' %
                        options.port)
                reactor.listenTCP(options.port, factory, interface='127.0.0.1')
            else:
                if Debug.connections:
                    logDebug(
                        'local server listening on UNIX socket %s' %
                        Options.socket)
                reactor.listenUNIX(Options.socket, factory)
        else:
            if Debug.connections:
                logDebug('server listening on port %d' % options.port)
            reactor.listenTCP(options.port, pb.PBServerFactory(kajonggPortal))
    except error.CannotListenError as errObj:
        logWarning(errObj)
        sys.exit(1)
    else:
        reactor.run()  # type:ignore[misc]


def profileMe() ->None:
    """where do we lose time?"""
    import cProfile
    cProfile.run('kajonggServer()', 'prof')
    import pstats
    statistics = pstats.Stats('prof')
    statistics.sort_stats('cumulative')
    statistics.print_stats(40)
