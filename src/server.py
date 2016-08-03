#!/usr/bin/env python
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

The DBPasswordChecker is based on an example from the book
Twisted Network Programming Essentials by Abe Fettig, 2006
O'Reilly Media, Inc., ISBN 0-596-10032-9
"""

# pylint: disable=wrong-import-order, wrong-import-position

import sys
import os
import logging
from signal import signal, SIGABRT, SIGINT, SIGTERM

from zope.interface import implementer


def cleanExit(*dummyArgs):
    """we want to cleanly close sqlite3 files"""
    if Options.socket and os.name != 'nt':
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
        reactor.stop()
    except NameError:
        sys.exit(0)
    except ReactorNotRunning:
        pass

signal(SIGABRT, cleanExit)
signal(SIGINT, cleanExit)
signal(SIGTERM, cleanExit)
if os.name != 'nt':
    from signal import SIGHUP, SIGQUIT
    signal(SIGHUP, cleanExit)
    signal(SIGQUIT, cleanExit)


from common import Options, Internal, Debug
Internal.isServer = True
Internal.logPrefix = 'S'

from twisted.spread import pb
from twisted.internet import error
from twisted.internet.defer import maybeDeferred, fail, succeed
from twisted.cred import checkers, portal, credentials, error as credError
from twisted.internet import reactor
from twisted.internet.error import ReactorNotRunning
reactor.addSystemEventTrigger('before', 'shutdown', cleanExit)
Internal.reactor = reactor

from player import Players
from query import Query, initDb
from log import m18n, m18nE, logDebug, logWarning, logError, SERVERMARK
from util import elapsedSince
from message import Message, ChatMessage
from deferredutil import DeferredBlock
from rule import Ruleset
from servercommon import srvError, srvMessage
from user import User
from servertable import ServerTable, ServerGame


@implementer(checkers.ICredentialsChecker)
class DBPasswordChecker(object):

    """checks against our sqlite3 databases"""
    credentialInterfaces = (credentials.IUsernamePassword,
                            credentials.IUsernameHashedPassword)

    def requestAvatarId(self, cred):  # pylint: disable=no-self-use
        """get user id from database"""
        cred.username = cred.username.decode('utf-8')
        args = cred.username.split(SERVERMARK)
        if len(args) > 1:
            if args[0] == u'adduser':
                cred.username = args[1]
                password = args[2]
                query = Query(
                    'insert or ignore into player(name,password) values(?,?)',
                    (cred.username,
                     password))
            elif args[1] == u'deluser':
                pass
        query = Query(
            'select id, password from player where name=?', (cred.username,))
        if not len(query.records):
            template = u'Wrong username: %1'
            if Debug.connections:
                logDebug(m18n(template, cred.username))
            return fail(credError.UnauthorizedLogin(srvMessage(template, cred.username)))
        userid, password = query.records[0]
        # checkPassword uses md5 which cannot handle unicode strings (python
        # 2.7)
        defer1 = maybeDeferred(cred.checkPassword, password.encode('utf-8'))
        defer1.addCallback(DBPasswordChecker._checkedPassword, userid)
        return defer1

    @staticmethod
    def _checkedPassword(matched, userid):
        """after the password has been checked"""
        if not matched:
            return fail(credError.UnauthorizedLogin(srvMessage(m18nE('Wrong password'))))
        return userid


class MJServer(object):

    """the real mah jongg server"""

    def __init__(self):
        self.tables = {}
        self.srvUsers = list()
        Players.load()
        self.lastPing = None
        self.checkPings()

    def chat(self, chatString):
        """a client sent us a chat message"""
        chatLine = ChatMessage(chatString)
        if Debug.chat:
            logDebug(u'server got chat message %s' % chatLine)
        self.tables[chatLine.tableid].sendChatMessage(chatLine)

    def login(self, user):
        """accept a new user"""
        if user not in self.srvUsers:
            self.srvUsers.append(user)
            self.loadSuspendedTables(user)

    def callRemote(self, user, *args, **kwargs):
        """if we still have a connection, call remote, otherwise clean up"""
        if user.mind:
            try:
                args2, kwargs2 = Message.jellyAll(args, kwargs)
                return user.mind.callRemote(*args2, **kwargs2).addErrback(MJServer.ignoreLostConnection)
            except (pb.DeadReferenceError, pb.PBConnectionLost):
                user.mind = None
                self.logout(user)

    @staticmethod
    def __stopAfterLastDisconnect():
        """as the name says"""
        if Options.socket and not Options.continueServer:
            try:
                reactor.stop()
                if Debug.connections:
                    logDebug(u'local server terminates from %s. Reason: last client disconnected' % (
                        Options.socket))
            except ReactorNotRunning:
                pass

    def checkPings(self):
        """are all clients still alive? If not log them out"""
        if not self.srvUsers and self.lastPing and elapsedSince(self.lastPing) > 30:
            # no user at all since 30 seconds, but we did already have a user
            self.__stopAfterLastDisconnect()
        for user in self.srvUsers:
            self.lastPing = max(
                self.lastPing,
                user.lastPing) if self.lastPing else user.lastPing
            if elapsedSince(user.lastPing) > 60:
                logDebug(
                    u'No messages from %s since 60 seconds, clearing connection now' %
                    user.name)
                user.mind = None
                self.logout(user)
        reactor.callLater(10, self.checkPings)

    @staticmethod
    def ignoreLostConnection(failure):
        """if the client went away correctly, do not dump error messages on stdout."""
        msg = failure.getErrorMessage()
        if 'twisted.internet.error.ConnectionDone' not in msg:
            logError(msg)
        failure.trap(pb.PBConnectionLost)

    def sendTables(self, user, tables=None):
        """send tables to user. If tables is None, he gets all new tables and those
        suspended tables he was sitting on"""
        if tables is None:
            tables = list(x for x in self.tables.values()
                          if not x.running and (not x.suspendedAt or x.hasName(user.name)))
        if len(tables):
            data = list(x.asSimpleList() for x in tables)
            if Debug.table:
                logDebug(
                    u'sending %d tables to %s: %s' %
                    (len(tables), user.name, data))
            return self.callRemote(user, 'newTables', data)
        else:
            return succeed([])

    def _lookupTable(self, tableid):
        """return table by id or raise exception"""
        if tableid not in self.tables:
            raise srvError(
                pb.Error,
                m18nE('table with id <numid>%1</numid> not found'),
                tableid)
        return self.tables[tableid]

    def generateTableId(self):
        """generates a new table id: the first free one"""
        usedIds = set(self.tables or [0])
        availableIds = set(x for x in range(1, 2 + max(usedIds)))
        return min(availableIds - usedIds)

    def newTable(self, user, ruleset, playOpen,
                 autoPlay, wantedGame, tableId=None):
        """user creates new table and joins it"""
        def gotRuleset(ruleset):
            """now we have the full ruleset definition from the client"""
            Ruleset.cached(
                ruleset).save()  # make it known to the cache and save in db
        if tableId in self.tables:
            return fail(srvError(pb.Error,
                                 'You want a new table with id=%d but that id is already used for table %s' % (
                                     tableId, self.tables[tableId])))
        if Ruleset.hashIsKnown(ruleset):
            return self.__newTable(None, user, ruleset, playOpen, autoPlay, wantedGame, tableId)
        else:
            return self.callRemote(user, 'needRuleset', ruleset).addCallback(
                gotRuleset).addCallback(
                    self.__newTable, user, ruleset, playOpen, autoPlay, wantedGame, tableId)

    def __newTable(self, dummy, user, ruleset,
                   playOpen, autoPlay, wantedGame, tableId=None):
        """now we know the ruleset"""
        def sent(dummy):
            """new table sent to user who created it"""
            return table.tableid
        table = ServerTable(
            self,
            user,
            ruleset,
            None,
            playOpen,
            autoPlay,
            wantedGame,
            tableId)
        result = None
        for srvUser in self.srvUsers:
            deferred = self.sendTables(srvUser, [table])
            if user == srvUser:
                result = deferred
                deferred.addCallback(sent)
        assert result
        return result

    def needRulesets(self, rulesetHashes):
        """the client wants those full rulesets"""
        result = []
        for table in self.tables.values():
            if table.ruleset.hash in rulesetHashes:
                result.append(table.ruleset.toList())
        return result

    def joinTable(self, user, tableid):
        """user joins table"""
        table = self._lookupTable(tableid)
        table.addUser(user)
        block = DeferredBlock(table)
        block.tell(
            None,
            self.srvUsers,
            Message.TableChanged,
            source=table.asSimpleList())
        if len(table.users) == table.maxSeats():
            if Debug.table:
                logDebug(u'Table %s: All seats taken, starting' % table)

            def startTable(dummy):
                """now all players know about our join"""
                table.readyForGameStart(table.owner)
            block.callback(startTable)
        else:
            block.callback(False)
        return True

    def tablesWith(self, user):
        """table ids with user, except table 'without'"""
        return list(x.tableid for x in self.tables.values() if user in x.users)

    def leaveTable(self, user, tableid, message=None, *args):
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
                        block = DeferredBlock(table)
                        block.tell(
                            None,
                            self.srvUsers,
                            Message.TableChanged,
                            source=table.asSimpleList())
                        block.callback(False)
        return True

    def startGame(self, user, tableid):
        """try to start the game"""
        return self._lookupTable(tableid).readyForGameStart(user)

    def removeTable(self, table, reason, message=None, *args):
        """remove a table"""
        assert reason in ('silent', 'tableRemoved', 'gameOver', 'abort')
        # HumanClient implements methods remote_tableRemoved etc.
        message = message or ''
        if Debug.connections or reason == 'abort':
            logDebug(
                u'%s%s ' % (('%s:' % table.game.seed) if table.game else '',
                            m18n(message, *args)), withGamePrefix=None)
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
                    u'removing table %d: %s %s' %
                    (table.tableid, m18n(message, *args), reason))
        if table.game:
            table.game.close()

    def logout(self, user):
        """remove user from all tables"""
        if user not in self.srvUsers:
            return
        self.srvUsers.remove(user)
        for tableid in self.tablesWith(user):
            self.leaveTable(
                user,
                tableid,
                m18nE('Player %1 has logged out'),
                user.name)
        # wait a moment. We want the leaveTable message to arrive everywhere before
        # we say serverDisconnects. Sometimes the order was reversed.
        reactor.callLater(1, self.__logout2, user)

    def __logout2(self, user):
        """now the leaveTable message had a good chance to get to the clients first"""
        self.callRemote(user, 'serverDisconnects')
        user.mind = None
        for block in DeferredBlock.blocks:
            for request in block.requests:
                if request.user == user:
                    block.removeRequest(request)

    def loadSuspendedTables(self, user):
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
                table.game = ServerGame.loadFromDB(gameid)


@implementer(portal.IRealm)
class MJRealm(object):

    """connects mind and server"""

    def __init__(self):
        self.server = None

    def requestAvatar(self, avatarId, mind, *interfaces):
        """as the tutorials do..."""
        if pb.IPerspective not in interfaces:
            raise NotImplementedError("No supported avatar interface")
        avatar = User(avatarId)
        avatar.server = self.server
        avatar.attached(mind)
        if Debug.connections:
            logDebug(u'Connection from %s ' % avatar.source())
        return pb.IPerspective, avatar, lambda a=avatar: a.detached(mind)


def parseArgs():
    """as the name says"""
    from optparse import OptionParser
    parser = OptionParser()
    defaultPort = Internal.defaultPort
    parser.add_option('', '--port', dest='port',
                      help=m18n(
                          'the server will listen on PORT (%d)' %
                          defaultPort),
                      type=int, default=defaultPort)
    parser.add_option('', '--socket', dest='socket',
                      help=m18n('the server will listen on SOCKET'), default=None)
    parser.add_option(
        '',
        '--db',
        dest='dbpath',
        help=m18n('name of the database'),
        default=None)
    parser.add_option(
        '', '--continue', dest='continueServer', action='store_true',
        help=m18n('do not terminate local game server after last client disconnects'), default=False)
    parser.add_option('', '--debug', dest='debug',
                      help=Debug.help())
    parser.add_option('', '--nokde', dest='nokde', action='store_true',
                      help=m18n('do not use KDE bindings. Only for testing'))
    parser.add_option('', '--qt5', dest='qt5', action='store_true',
                      help=m18n('Force using Qt5. Currently Qt4 is used by default'))
    (options, args) = parser.parse_args()
    if args and ''.join(args):
        logWarning(m18n('unrecognized arguments:%1', ' '.join(args)))
        sys.exit(2)
    Options.continueServer |= options.continueServer
    if options.dbpath:
        Options.dbPath = os.path.expanduser(options.dbpath)
    if options.socket:
        Options.socket = options.socket
    Debug.setOptions(options.debug)
    Options.fixed = True  # may not be changed anymore
    del parser           # makes Debug.gc quieter
    return options


def kajonggServer():
    """start the server"""
    # pylint: disable=too-many-branches
    options = parseArgs()
    if not initDb():
        sys.exit(1)
    realm = MJRealm()
    realm.server = MJServer()
    kajonggPortal = portal.Portal(realm, [DBPasswordChecker()])
    import predefined  # pylint: disable=unused-variable
    try:
        if Options.socket:
            if os.name == 'nt':
                if Debug.connections:
                    logDebug(
                        u'local server listening on 127.0.0.1 port %d' %
                        options.port)
                reactor.listenTCP(
                    options.port,
                    pb.PBServerFactory(kajonggPortal),
                    interface='127.0.0.1')
            else:
                if Debug.connections:
                    logDebug(
                        u'local server listening on UNIX socket %s' %
                        Options.socket)
                reactor.listenUNIX(
                    Options.socket,
                    pb.PBServerFactory(kajonggPortal))
        else:
            if Debug.connections:
                logDebug(u'server listening on port %d' % options.port)
            reactor.listenTCP(options.port, pb.PBServerFactory(kajonggPortal))
    except error.CannotListenError as errObj:
        logWarning(errObj)
        sys.exit(1)
    else:
        reactor.run()


def profileMe():
    """where do we lose time?"""
    import cProfile
    cProfile.run('kajonggServer()', 'prof')
    import pstats
    statistics = pstats.Stats('prof')
    statistics.sort_stats('cumulative')
    statistics.print_stats(40)
