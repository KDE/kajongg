#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
"""

import traceback

from twisted.spread import pb
from twisted.internet.defer import Deferred

from util import m18nE, logInfo, logDebug, logException
from message import Message
from common import Debug

class Request(object):
    """holds a Deferred and related attributes, used as part of a DeferredBlock"""
    def __init__(self, deferred, player):
        self.deferred = deferred
        self.player = player
        self.answered = False
        self.answer = None

    def __str__(self):
        cmd = self.deferred.command if hasattr(self.deferred, 'command') else ''
        return '[%s] %s->%s: %s' % (id(self)%1000, cmd, self.player.name,
            str(self.answer) if self.answer else 'OPEN')

class Answer(object):
    """helper class for parsing client answers"""
    def __init__(self, request):
        self.player = request.player
        if isinstance(request.answer, tuple):
            answer = request.answer[0]
            if isinstance(request.answer[1], tuple):
                self.args = list(request.answer[1])
            else:
                self.args = list([request.answer[1]])
        else:
            answer = request.answer
            self.args = None
        if answer is not None:
            self.answer = Message.defined[answer]
        else:
            self.answer = None

    def __str__(self):
        return '%s: %s: %s' % (self.player, self.answer, self.args)

    def __repr__(self):
        return '<Answer: %s>' % self


class DeferredBlock(object):
    """holds a list of deferreds and waits for each of them individually,
    with each deferred having its own independent callbacks. Fires a
    'general' callback after all deferreds have returned.
    Usage: 1. define, 2. add requests, 3. set callback"""

    blocks = []
    blockWarned = False # did we already warn about too many blocks?

    def __init__(self, table, temp=False):
        dummy, dummy, function, dummy = traceback.extract_stack()[-2]
        self.calledBy = function
        if not temp:
            self.garbageCollection()
        self.table = table
        self.requests = []
        self.callbackMethod = None
        self.__callbackArgs = None
        self.outstanding = 0
        self.completed = False
        if not temp:
            DeferredBlock.blocks.append(self)
            if not DeferredBlock.blockWarned:
                if len([x for x in DeferredBlock.blocks if x.table == table]) > 10:
                    DeferredBlock.blockWarned = True
                    logInfo('We have %d DBlocks:' % len(DeferredBlock.blocks))
                    for block in DeferredBlock.blocks:
                        logInfo(str(block))
        if Debug.deferredBlock:
            logDebug('new DBlock %s' % str(self))

    def __str__(self):
        return '[%s] %s requests=%s outstanding=%d %s callback=%s(%s)' % \
            (id(self)%1000, self.calledBy,
            '[' + ','.join(str(x) for x in self.requests) + ']',
            self.outstanding,
            'is completed' if self.completed else 'not completed',
            self.callbackMethod, ','.join([str(x) for x in self.__callbackArgs] if self.__callbackArgs else ''))

    def outstandingStr(self):
        """like __str__ but only with outstanding answers"""
        return '%s callback=%s(%s):%s' % \
            (self.calledBy,
            self.callbackMethod, ','.join([str(x) for x in self.__callbackArgs] if self.__callbackArgs else ''),
            '[' + ','.join(str(x) for x in self.requests if not x.answered) + ']')


    @staticmethod
    def garbageCollection():
        """delete completed blocks. Only to be called before
        inserting a new block. Assuming that block creation
        never overlaps."""
        for block in DeferredBlock.blocks[:]:
            if not block.callbackMethod:
                block.logBug('DBlock %s has no callback' % str(block))
            if block.completed:
                DeferredBlock.blocks.remove(block)

    def __addRequest(self, deferred, player):
        """add deferred for player to this block"""
        assert not self.callbackMethod
        assert not self.completed
        request = Request(deferred, player)
        self.requests.append(request)
        self.outstanding += 1
        deferred.addCallback(self.__gotAnswer, request).addErrback(self.__failed, request)
        if Debug.deferredBlock:
            logDebug('added request %s to DBlock %s' % (request, str(self)))

    def removeRequest(self, request):
        """we do not want this request anymore"""
        self.requests.remove(request)
        self.outstanding -= 1
        if self.outstanding == 0:
            self.callbackIfDone()
        if Debug.deferredBlock:
            logDebug('removed request %s from DBlock %s' % (request, str(self)))

    def callback(self, method, *args):
        """to be done after all players answered"""
        assert not self.completed
        assert not self.callbackMethod
        self.callbackMethod = method
        self.__callbackArgs = args
        self.callbackIfDone()

    def __gotAnswer(self, result, request):
        """got answer from player"""
        if request in self.requests:
            # after having lost connection to client, an answer could still be in the pipe
            assert not self.completed
            request.answer = result
            request.answered = True
            if result is not None:
                if isinstance(result, tuple):
                    result = result[0]
                if result and Message.defined[result].notifyAtOnce:
                    block = DeferredBlock(self.table, temp=True)
                    block.tellAll(request.player, Message.PopupMsg, msg=result)
            self.outstanding -= 1
        self.callbackIfDone()

    def logBug(self, msg):
        """log msg and raise exception"""
        for request in self.requests:
            logDebug(str(request))
        logException(msg)

    def callbackIfDone(self):
        """if we are done, convert received answers to Answer objects and callback"""
        assert not self.completed, 'DeferredBlock %s already called callback %s' % (self, self.callbackMethod)
        if self.outstanding <= 0 and self.callbackMethod:
            if not all(x.answered for x in self.requests):
                self.logBug('Block %s: Some requests are unanswered' % str(self))
            answers = [Answer(x) for x in self.requests]
            self.completed = True
            if Debug.deferredBlock:
                logDebug('just completed:outstanding=%s %s' % (self.outstanding, str(self)))
            self.callbackMethod(answers, *self.__callbackArgs)

    def __failed(self, result, request):
        """a player did not or not correctly answer"""
        if request in self.requests:
            self.removeRequest(request)
        if result.type in [pb.PBConnectionLost]:
            msg = m18nE('The game server lost connection to player %1')
            self.table.abort(msg, request.player.name)
        else:
            msg = m18nE('Error for player %1: %2\n%3')
            try:
                traceBack = result.getTraceback()
            except BaseException:
                # may happen with twisted 12.3.0
                traceBack = 'twisted cannot give us a traceback'
            self.table.abort(msg, request.player.name, result.getErrorMessage(), traceBack)

    @staticmethod
    def __enrichMessage(game, about, command, kwargs):
        """add supplemental data for debugging"""
        if command.sendScore and about:
            # the clients will compare our status with theirs. This helps
            # very much in finding bugs.
            kwargs['score'] = str(about.hand)
        if game and game.gameid and 'token' not in kwargs:
            # this lets the client assert that the message is meant for the current hand
            kwargs['token'] = game.handId()
        else:
            kwargs['token'] = None

    def tell(self, about, receivers, command, **kwargs):
        """send info about player 'about' to players 'receivers'"""
        if not isinstance(receivers, list):
            receivers = list([receivers])
        assert receivers, 'DeferredBlock.tell(%s) has no receiver % command'
        self.__enrichMessage(self.table.game, about, command, kwargs)
        aboutName = about.name if about else None
        if self.table.running and len(receivers) in [1, 4]:
            # messages are either identical for all 4 players
            # or identical for 3 players and different for 1 player. And
            # we want to capture each message exactly once.
            self.table.game.appendMove(about, command, kwargs)
        localDeferreds = []
        for receiver in receivers:
            isClient = receiver.remote.__class__.__name__ == 'Client'
            if Debug.traffic and not isClient:
                message = '-> %s about %s %s' % (receiver, about, command)
                for key, value in kwargs.items():
                    if key != 'token':
                        message += ' %s:%s' % (key, value)
                logDebug(message)
            if isClient:
                defer = Deferred()
                defer.addCallback(receiver.remote.remote_move, command, **kwargs)
            else:
                defer = self.table.server.callRemote(receiver.remote, 'move', aboutName, command.name, **kwargs)
            if defer:
                defer.command = command.name
                self.__addRequest(defer, receiver)
            else:
                msg = m18nE('The game server lost connection to player %1')
                self.table.abort(msg, receiver.name)
            if isClient:
                localDeferreds.append(defer)
        for defer in localDeferreds:
            defer.callback(aboutName)


    def tellPlayer(self, player, command, **kwargs):
        """address only one player"""
        self.tell(player, player, command, **kwargs)

    def tellOthers(self, player, command, **kwargs):
        """tell others about player'"""
        self.tell(player, list([x for x in self.table.game.players if x!= player]), command, **kwargs)

    def tellAll(self, player, command, **kwargs):
        """tell something to all players"""
        self.tell(player, self.table.game.players, command, **kwargs)
