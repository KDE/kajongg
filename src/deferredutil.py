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
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
"""

import traceback

from twisted.spread import pb
from twisted.internet.defer import Deferred

from util import m18nE, logInfo, logDebug, \
    logException, kprint
from message import Message
from common import InternalParameters

class Request(object):
    """holds a Deferred and related attributes, used as part of a DeferredBlock"""
    def __init__(self, deferred, player):
        self.deferred = deferred
        self.player = player
        self.answers = None

    def __str__(self):
        answers = ','.join(str(x) for x in self.answers) if self.answers else 'has no answers`'
        return '%s: %s' % (self.player, answers)

class Answer(object):
    """helper class for parsing client answers"""
    def __init__(self, player, args):
        self.player = player
        if isinstance(args, tuple):
            answer = args[0]
            if isinstance(args[1], tuple):
                self.args = list(args[1])
            else:
                self.args = list([args[1]])
        else:
            answer = args
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
        return 'table=%d %s requests=%d outstanding=%d completed=%d callback=%s(%s)' % \
            (self.table.tableid, self.calledBy, len(self.requests), self.outstanding, self.completed,
            self.callbackMethod, ','.join([str(x) for x in self.__callbackArgs] if self.__callbackArgs else ''))

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
        # pylint: disable=R0912
        # pylint too many branches
        assert not self.completed
        if result is None:
            # the player has already logged out
            msg = m18nE('The game server lost connection to player %1')
            self.table.abort(msg, request.player.name)
            return
        failures = [x[1] for x in result if not x[0]]
        if failures:
            for failure in failures:
                kprint(failure)
            for dummy in result:
                kprint(dummy)
            msg = m18nE('Unknown error for player %1: %2\n%3')
            self.table.abort(msg, request.player.name)

        request.answers = [x[1] for x in result if x[0]]
        if request.answers is not None:
            if not isinstance(request.answers, list):
                request.answers = list([request.answers])
            for answer in request.answers:
                if isinstance(answer, tuple):
                    answer = answer[0]
                if answer and Message.defined[answer].notifyAtOnce:
                    block = DeferredBlock(self.table, temp=True)
                    block.tellAll(request.player, Message.PopupMsg, msg=answer)
        self.outstanding -= 1
        self.callbackIfDone()

    def callbackIfDone(self):
        """if we are done, convert received answers to Answer objects and callback"""
        if self.outstanding <= 0 and self.callbackMethod:
            answers = []
            for request in self.requests:
                if request.answers is not None:
                    for args in request.answers:
                        answers.append(Answer(request.player, args))
            self.callbackMethod(answers, *self.__callbackArgs)
            self.completed = True

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
        aboutName = about.name if about else None
        if game and len(receivers) in [1, 4]:
            # messages are either identical for all 4 players
            # or identical for 3 players and different for 1 player. And
            # we want to capture each message exactly once.
            game.appendMove(about, command, kwargs)
        for receiver in receivers:
            isClient = receiver.remote.__class__.__name__ == 'Client'
            if InternalParameters.showTraffic:
                if not isClient:
                    logDebug('%d -> %s about %s: %s %s' % (self.table.tableid, receiver, about, command, kwargs))
            if isClient:
                defer = Deferred()
                defer.addCallback(receiver.remote.remote_move, command, **kwargs)
                defer.callback(aboutName)
            else:
                defer = self.table.server.callRemote(receiver.remote, 'move', aboutName, command.name, **kwargs)
            if defer:
                self.__addRequest(defer, receiver)
            else:
                msg = m18nE('The game server lost connection to player %1')
                self.table.abort(msg, receiver.name)

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
