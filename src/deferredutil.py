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
from common import InternalParameters

class Request(object):
    """holds a Deferred and related attributes, used as part of a DeferredBlock"""
    def __init__(self, deferred, player):
        self.deferred = deferred
        self.player = player
        self.answered = False
        self.answer = None

    def __str__(self):
        cmd = self.deferred.command if hasattr(self.deferred, 'command') else ''
        return '%s->%s: %s' % (cmd, self.player.name,
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
                if len(DeferredBlock.blocks) > 10:
                    DeferredBlock.blockWarned = True
                    logInfo('We have %d DeferredBlocks:' % len(DeferredBlock.blocks))
                    for block in DeferredBlock.blocks:
                        logInfo(str(block))

    def __str__(self):
        return '%s requests=%s outstanding=%d %s callback=%s(%s)' % \
            (self.calledBy,
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
            if not block.requests:
                logException('block has no requests:%s' % str(block))
            if not block.callbackMethod:
                for request in block.requests:
                    logDebug(str(request))
                logException('block %s has no callback' % str(block))
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

    def removeRequest(self, request):
        """we do not want this request anymore"""
        self.requests.remove(request)
        self.outstanding -= 1

    def callback(self, method, *args):
        """to be done after all players answered"""
        assert self.requests
        assert not self.completed
        assert not self.callbackMethod
        self.callbackMethod = method
        self.__callbackArgs = args
        self.callbackIfDone()

    def __gotAnswer(self, result, request):
        """got answer from player"""
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

    def callbackIfDone(self):
        """if we are done, convert received answers to Answer objects and callback"""
        if self.outstanding <= 0 and self.callbackMethod:
            assert all(x.answered for x in self.requests)
            answers = [Answer(x) for x in self.requests]
            self.completed = True
            self.callbackMethod(answers, *self.__callbackArgs)

    def __failed(self, result, request):
        """a player did not or not correctly answer"""
        if result.type in [pb.PBConnectionLost]:
            msg = m18nE('The game server lost connection to player %1')
            self.table.abort(msg, request.player.name)
        else:
            msg = m18nE('Unknown error for player %1: %2\n%3')
            self.table.abort(msg, request.player.name, result.getErrorMessage(), result.getTraceback())

    def tell(self, about, receivers, command, **kwargs):
        """send info about player 'about' to players 'receivers'"""
        if not isinstance(receivers, list):
            receivers = list([receivers])
        assert receivers, 'DeferredBlock.tell(%s) has no receiver % command'
        game = self.table.game or self.table.preparedGame
        if game and game.gameid and 'token' not in kwargs:
            kwargs['token'] = game.handId()
        else:
            kwargs['token'] = None
        aboutName = about.name if about else None
        if game and len(receivers) in [1, 4]:
            # messages are either identical for all 4 players
            # or identical for 3 players and different for 1 player. And
            # we want to capture each message exactly once.
            game.appendMove(about, command, kwargs)
        localDeferreds = []
        for receiver in receivers:
            isClient = receiver.remote.__class__.__name__ == 'Client'
            if InternalParameters.showTraffic and not isClient:
                kw2 = kwargs.copy()
                del kw2['token']
                logDebug('-> %s about %s: %s %s' % (receiver, about, command, kw2))
            if isClient:
                defer = Deferred()
                defer.addCallback(receiver.remote.remote_move, command, **kwargs)
            else:
                defer = self.table.server.callRemote(receiver.remote, 'move', aboutName, command.name, **kwargs)
            defer.command = command.name
            if defer:
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
        game = self.table.game or self.table.preparedGame
        self.tell(player, list([x for x in game.players if x!= player]), command, **kwargs)

    def tellAll(self, player, command, **kwargs):
        """tell something to all players"""
        game = self.table.game or self.table.preparedGame
        self.tell(player, game.players, command, **kwargs)
