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
from move import Move

class Request(object):
    """holds a Deferred and related attributes, used as part of a DeferredBlock"""
    def __init__(self, deferred, player, about):
        self.deferred = deferred
        self.player = player
        self.about = about
        self.answer = None
        self.args = None

    def gotAnswer(self, rawAnswer):
        """convert the wired answer into something more useful"""
        if isinstance(rawAnswer, tuple):
            answer = rawAnswer[0]
            if isinstance(rawAnswer[1], tuple):
                self.args = list(rawAnswer[1])
            else:
                self.args = list([rawAnswer[1]])
        else:
            answer = rawAnswer
            self.args = None
        if answer in Message.defined:
            self.answer = Message.defined[answer]
        else:
            if Debug.deferredBlock:
                logDebug('Request %s ignores %s' % (self, rawAnswer))

    def __str__(self):
        cmd = self.deferred.command
        if self.answer:
            answer = str(self.answer)
        else:
            answer = 'OPEN'
        return '[{id:>4}] {cmd}->{receiver:<10}: {answer}'.format(
            id=id(self)%10000, cmd=cmd, receiver=self.player.name, answer=answer)

    def __repr__(self):
        return 'Request(%s)' % str(self)

    def prettyAnswer(self):
        """for debug output"""
        if self.answer:
            result = str(self.answer)
        else:
            result = 'OPEN'
        if self.args:
            result += '(%s)' % ','.join(str(x) for x in self.args)
        return result

    def pretty(self):
        """for debug output"""
        return '[{id:>4}] {cmd:<10}<-{receiver:<10}: ANS={answer}'.format(
            id=id(self)%10000, answer=self.prettyAnswer(), cmd=self.deferred.command, receiver=self.player.name)

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

    def debugPrefix(self, marker=''):
        """prefix for debug message"""
        return 'Block [{id:>4}] {caller:<15} {marker:<3}(out={out})'.format(
            id=id(self) % 10000, caller=self.calledBy[:15], marker=marker,
            out=self.outstanding)

    def debug(self, marker, msg):
        """standard debug format"""
        logDebug(' '.join([self.debugPrefix(marker), msg]))

    def __str__(self):
        return '%s requests=%s outstanding=%d %s callback=%s(%s)' % (
            self.debugPrefix(),
            '[' + ','.join(str(x) for x in self.requests) + ']',
            self.outstanding,
            'is completed' if self.completed else 'not completed',
            self.callbackMethod, ','.join([str(x) for x in self.__callbackArgs] if self.__callbackArgs else ''))

    def outstandingStr(self):
        """like __str__ but only with outstanding answers"""
        return '%s callback=%s(%s):%s' % \
            (self.calledBy,
            self.callbackMethod, ','.join([str(x) for x in self.__callbackArgs] if self.__callbackArgs else ''),
            '[' + ','.join(str(x) for x in self.requests if not x.answer) + ']')


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

    def __addRequest(self, deferred, player, about):
        """add deferred for player to this block"""
        assert not self.callbackMethod, 'AddRequest: already have callback defined'
        assert not self.completed, 'AddRequest: already completed'
        request = Request(deferred, player, about)
        self.requests.append(request)
        self.outstanding += 1
        deferred.addCallback(self.__gotAnswer, request).addErrback(self.__failed, request)
        if Debug.deferredBlock:
            notifying = ' notifying' if deferred.notifying else ''
            rqString = '[{id:>4}] {cmd}{notifying} {about}->{receiver:<10}'.format(
                id=id(request)%10000, cmd=request.deferred.command, receiver=request.player.name,
                about=about.name if about else '', notifying=notifying)
            self.debug('+:%d' % len(self.requests), rqString)

    def removeRequest(self, request):
        """we do not want this request anymore"""
        self.requests.remove(request)
        if not request.answer:
            self.outstanding -= 1
        if Debug.deferredBlock:
            self.debug('-:%d' % self.outstanding, str(request))
        self.callbackIfDone()

    def callback(self, method, *args):
        """to be done after all players answered"""
        assert not self.completed, 'callback already completed'
        assert not self.callbackMethod, 'callback: no method defined'
        self.callbackMethod = method
        self.__callbackArgs = args
        if Debug.deferredBlock:
            self.debug('CB', '%s%s' % (method, args if args else ''))
        self.callbackIfDone()

    def __gotAnswer(self, result, request):
        """got answer from player"""
        if request in self.requests:
            # after having lost connection to client, an answer could still be in the pipe
           # assert not self.completed
            request.gotAnswer(result)
            user = self.table.userForPlayer(request.player)
            if user:
                user.pinged()
            if Debug.deferredBlock:
                self.debug('ANS', request.pretty())
            if hasattr(request.answer, 'notifyAction'):
                block = DeferredBlock(self.table, temp=True)
                receivers = request.answer.receivers(self)
                if receivers:
                    block.tell(request.player, receivers, request.answer, notifying=True)
            self.outstanding -= 1
            assert self.outstanding >= 0, '__gotAnswer: outstanding %d' % self.outstanding
            self.callbackIfDone()
        else:
            if Debug.deferredBlock:
                self.debug('NOP', request.pretty())

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

    def logBug(self, msg):
        """log msg and raise exception"""
        for request in self.requests:
            logDebug(str(request))
        logException(msg)

    def callbackIfDone(self):
        """if we are done, convert received answers to something more useful and callback"""
        if self.completed:
            return
        assert self.outstanding >= 0, 'callbackIfDone: outstanding %d' % self.outstanding
        if self.outstanding == 0 and self.callbackMethod:
            self.completed = True
            if any(not x.answer for x in self.requests):
                self.logBug('Block %s: Some requests are unanswered' % str(self))
            if Debug.deferredBlock:
                commandText = []
                for command in set(x.deferred.command for x in self.requests):
                    text = '%s:' % command
                    answerList = []
                    for answer in set(x.prettyAnswer() for x in self.requests if x.deferred.command == command):
                        answerList.append((answer, list(x for x in self.requests
                            if x.deferred.command == command and answer==x.prettyAnswer())))
                    answerList = sorted(answerList, key=lambda x:len(x[1]))
                    answerTexts = []
                    if len(answerList) == 1:
                        answerTexts.append('{answer} from all'.format(answer=answerList[-1][0]))
                    else:
                        for answer, requests in answerList[:-1]:
                            answerTexts.append('{answer} from {players}'.format(answer=answer,
                                players=','.join(x.player.name for x in requests)))
                        answerTexts.append('{answer} from others'.format(answer=answerList[-1][0]))
                    text += ', '.join(answerTexts)
                    commandText.append(text)
                self.debug('END', 'calling {method}({answers})'.format(
                    method=self.callbackMethod, answers=' / '.join(commandText)).replace('bound method ', ''))
            self.callbackMethod(self.requests, *self.__callbackArgs)

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
        assert receivers, 'DeferredBlock.tell(%s) has no receiver' % command
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
                message = '-> {receiver:<15} about {about} {command}{kwargs}'.format(
                    receiver=receiver.name[:15], about=about, command=command,
                    kwargs=Move.prettyKwargs(kwargs))
                logDebug(message)
            if isClient:
                defer = Deferred()
                defer.addCallback(receiver.remote.remote_move, command, **kwargs)
            else:
                defer = self.table.server.callRemote(receiver.remote, 'move', aboutName, command.name, **kwargs)
            if defer:
                defer.command = command.name
                defer.notifying = 'notifying' in kwargs
                self.__addRequest(defer, receiver, about)
            else:
                msg = m18nE('The game server lost connection to player %1')
                self.table.abort(msg, receiver.name)
            if isClient:
                localDeferreds.append(defer)
        for defer in localDeferreds:
            defer.callback(aboutName) # callback needs an argument !

    def tellPlayer(self, player, command, **kwargs):
        """address only one player"""
        self.tell(player, player, command, **kwargs)

    def tellOthers(self, player, command, **kwargs):
        """tell others about player'"""
        self.tell(player, list([x for x in self.table.game.players if x!= player]), command, **kwargs)

    def tellAll(self, player, command, **kwargs):
        """tell something to all players"""
        self.tell(player, self.table.game.players, command, **kwargs)
