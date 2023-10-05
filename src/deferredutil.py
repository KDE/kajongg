# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

import traceback
import datetime
import weakref
import gc

from twisted.spread import pb
from twisted.internet.defer import Deferred

from log import logInfo, logDebug, logException
from mi18n import i18nE
from message import Message
from common import Debug, ReprMixin, id4
from move import Move


class Request(ReprMixin):

    """holds a Deferred and related attributes, used as part of a DeferredBlock"""

    def __init__(self, block, deferred, user):
        self._block = weakref.ref(block)
        self.deferred = deferred
        self._user = weakref.ref(user)
        self.answer = None
        self.args = None
        self.startTime = datetime.datetime.now()
        player = self.block.playerForUser(user)
        self._player = weakref.ref(player) if player else None

    @property
    def block(self):
        """hide weakref"""
        return self._block() if self._block else None

    @property
    def user(self):
        """hide weakref"""
        return self._user() if self._user else None

    @property
    def player(self):
        """hide weakref"""
        return self._player() if self._player else None

    def gotAnswer(self, rawAnswer):
        """convert the wired answer into something more useful"""
        if isinstance(rawAnswer, tuple):
            answer = rawAnswer[0]
            if isinstance(rawAnswer[1], tuple):
                self.args = rawAnswer[1]
            else:
                self.args = [rawAnswer[1]]
        else:
            answer = rawAnswer
            self.args = None
        if answer in Message.defined:
            self.answer = Message.defined[answer]
        else:
            if Debug.deferredBlock:
                logDebug('Request %s ignores %s' % (self, rawAnswer))

    def age(self):
        """my age in full seconds"""
        return int((datetime.datetime.now() - self.startTime).total_seconds())

    def __str__(self):
        cmd = self.deferred.command
        if self.answer:
            answer = str(self.answer) # TODO: needed?
        else:
            answer = 'OPEN'
        result = ''
        if Debug.deferredBlock:
            result += '[{id4:>4}] '.format(id4=id4(self))
        result += '{cmd}->{cls}({receiver:<10}): {answer}'.format(
            cls=self.user.__class__.__name__, cmd=cmd, receiver=self.user.name,
            answer=answer)
        if self.age():
            result += ' after {} sec'.format(self.age())
        return result

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
        result = ''
        if Debug.deferredBlock:
            result += '[{id4:>4}] '.format(id4=id4(self))
        result += '{cmd:<12}<-{cls:>6}({receiver:<10}): ANS={answer}'.format(
            cls=self.user.__class__.__name__,
            answer=self.prettyAnswer(), cmd=self.deferred.command, receiver=self.user.name)
        if self.age() > 0:
            result += ' after {} sec'.format(self.age())
        return result


class DeferredBlock(ReprMixin):

    """holds a list of deferreds and waits for each of them individually,
    with each deferred having its own independent callbacks. Fires a
    'general' callback after all deferreds have returned.
    Usage: 1. define, 2. add requests, 3. set callback"""

    blocks = []
    blockWarned = False  # did we already warn about too many blocks?

    def __init__(self, table, temp=False, where=None):
        dummy, dummy, function, dummy = traceback.extract_stack()[-2]
        self.outstanding = 0
        self.calledBy = function
        if not temp:
            self.garbageCollection()
        self.where = where
        self.table = table
        self.requests = []
        self.callbackMethod = None
        self.__callbackArgs = None
        self.completed = False
        if not temp:
            DeferredBlock.blocks.append(self)
            if not DeferredBlock.blockWarned:
                if len([x for x in DeferredBlock.blocks if x.table == table]) > 10:
                    DeferredBlock.blockWarned = True
                    logInfo('We have %d DBlocks:' % len(DeferredBlock.blocks))
                    for block in DeferredBlock.blocks:
                        logInfo(str(block))

    def debugPrefix(self, dbgMarker=''):
        """prefix for debug message"""
        return 'T{table} B[{id4:>4}] {caller:<15} {dbgMarker:<3}(out={out})'.format(
            table=self.table.tableid, id4=id4(self), caller=self.calledBy[:15],
            dbgMarker=dbgMarker, out=self.outstanding)

    def debug(self, dbgMarker, msg):
        """standard debug format"""
        logDebug(' '.join([self.debugPrefix(dbgMarker), msg]))

    def __str__(self):
        return '%s requests=%s outstanding=%d %s callback=%s' % (
            self.debugPrefix(),
            '[' + ','.join(str(x) for x in self.requests) + ']',
            self.outstanding,
            'is completed' if self.completed else 'not completed',
            self.prettyCallback())

    def outstandingStr(self):
        """like __str__ but only with outstanding answers"""
        return '%s callback=%s:%s' % (self.calledBy, self.prettyCallback(),
                                      '[' + ','.join(str(x) for x in self.requests if not x.answer) + ']')

    @staticmethod
    def garbageCollection():
        """delete completed blocks. Only to be called before
        inserting a new block. Assuming that block creation
        never overlaps."""
        for block in DeferredBlock.blocks[:]:
            if block.callbackMethod is None:
                try:
                    block.logBug('DBlock %s has no callback' % str(block))
                finally:
                    # we do not want DoS for future games
                    DeferredBlock.blocks.remove(block)
            if block.completed:
                DeferredBlock.blocks.remove(block)
        if len(DeferredBlock.blocks) > 100:
            logDebug(
                'We have %d DeferredBlocks, they must be leaking' %
                len(DeferredBlock.blocks))
            for _ in (id4(x) for x in gc.get_objects() if x.__class__.__name__ == 'DeferredBlock'):
                print('DeferredBlock {} left, allocated by {}'.format(_, _.where))


    def __addRequest(self, deferred, user, about):
        """add deferred for user to this block"""
        assert self.callbackMethod is None, 'AddRequest: already have callback defined'
        assert not self.completed, 'AddRequest: already completed'
        request = Request(self, deferred, user)
        self.requests.append(request)
        self.outstanding += 1
        deferred.addCallback(
            self.__gotAnswer,
            request).addErrback(
                self.__failed,
                request)
        if Debug.deferredBlock:
            notifying = ' notifying' if deferred.notifying else ''
            rqString = '[{id4:>4}] {cmd}{notifying} {about}->{cls:>6}({receiver:<10})'.format(
                cls=user.__class__.__name__,
                id4=id4(request), cmd=deferred.command, receiver=user.name,
                about=about.name if about else '', notifying=notifying)
            self.debug('+:%d' % len(self.requests), rqString)

    def removeRequest(self, request):
        """we do not want this request anymore"""
        self.requests.remove(request)
        if not request.answer:
            self.outstanding -= 1
        if Debug.deferredBlock:
            self.debug('-:%d' % self.outstanding, str(request)) # TODO: auch ohne?
        self.callbackIfDone()

    def callback(self, method, *args):
        """to be done after all users answered"""
        assert not self.completed, 'callback already completed'
        assert self.callbackMethod is None, 'callback: no method defined'
        self.callbackMethod = method
        self.__callbackArgs = args
        if Debug.deferredBlock:
            self.debug('CB', self.prettyCallback())
        self.callbackIfDone()

    def __gotAnswer(self, result, request):
        """got answer from user"""
        if request in self.requests:
            # after having lost connection to client, an answer could still be
            # in the pipe
            if result is None:
                if Debug.deferredBlock:
                    self.debug('IGN', request.pretty())
                return
            request.gotAnswer(result)
            if hasattr(request.user, 'pinged'):
                # a Client (for robots) does not have it
                request.user.pinged()
            if Debug.deferredBlock:
                self.debug('ANS', request.pretty())
            if hasattr(request.answer, 'notifyAction'):
                block = DeferredBlock(self.table, temp=True, where='__gotAnswer')
                receivers = request.answer.receivers(request)
                if receivers:
                    block.tell(
                        request.player,
                        receivers,
                        request.answer,
                        notifying=True)
            self.outstanding -= 1
            assert self.outstanding >= 0, '__gotAnswer: outstanding %d' % self.outstanding
            self.callbackIfDone()
        else:
            if Debug.deferredBlock:
                self.debug('NOP', request.pretty())

    def __failed(self, result, request):
        """a user did not or not correctly answer"""
        if request in self.requests:
            self.removeRequest(request)
        if result.type in [pb.PBConnectionLost]:
            msg = i18nE('The game server lost connection to player %1')
            self.table.abort(msg, request.user.name)
        else:
            msg = i18nE('Error for player %1: %2\n%3')
            if hasattr(result, 'traceback'):
                traceBack = result.traceback
            else:
                traceBack = result.getBriefTraceback()
            if not isinstance(result.value, AssertionError):
                self.table.abort(
                    msg,
                    request.user.name,
                    result.getErrorMessage(),
                    traceBack)

    def logBug(self, msg):
        """log msg and raise exception"""
        for request in self.requests:
            logDebug(str(request)) # TODO:
        logException(msg)

    def callbackIfDone(self):
        """if we are done, convert received answers to something more useful and callback"""
        if self.completed:
            return
        assert self.outstanding >= 0, 'callbackIfDone: outstanding %d' % self.outstanding
        if self.outstanding == 0 and self.callbackMethod is not None:
            self.completed = True
            if any(not x.answer for x in self.requests):
                self.logBug(
                    'Block %s: Some requests are unanswered' %
                    str(self))
            if Debug.deferredBlock:
                commandText = []
                for command in sorted({x.deferred.command for x in self.requests}):
                    text = '%s:' % command
                    answerList = []
                    for answer in sorted({x.prettyAnswer() for x in self.requests if x.deferred.command == command}):
                        answerList.append((answer, [
                            x for x in self.requests
                            if x.deferred.command == command and answer == x.prettyAnswer()]))
                    answerList = sorted(answerList, key=lambda x: len(x[1]))
                    answerTexts = []
                    if len(answerList) == 1:
                        answerTexts.append(
                            '{answer} from all'.format(answer=answerList[-1][0]))
                    else:
                        for answer, requests in answerList[:-1]:
                            answerTexts.append(
                                '{answer} from {players}'.format(answer=answer,
                                                                 players=','.join(x.user.name for x in requests)))
                        answerTexts.append(
                            '{answer} from others'.format(answer=answerList[-1][0]))
                    text += ', '.join(answerTexts)
                    commandText.append(text)
                methodName = self.prettyCallback()
                if methodName:
                    methodName = ' next:%s' % methodName
                self.debug(
                    'END',
                    '{answers} {method}'.format(method=methodName,
                                                answers=' / '.join(commandText)))
            if self.callbackMethod is not False:
                self.callbackMethod(self.requests, *self.__callbackArgs)

    def prettyCallback(self):
        """pretty string for callbackMethod"""
        if self.callbackMethod is False:
            result = ''
        elif self.callbackMethod is None:
            result = 'None'
        else:
            result = self.callbackMethod.__name__
            if self.__callbackArgs:
                result += '({})'.format(
                    ','.join([str(x) for x in self.__callbackArgs] if self.__callbackArgs else ''))
        return result

    def playerForUser(self, user):
        """return the game player matching user"""
        if user.__class__.__name__.endswith('Player'):
            return user
        if self.table.game:
            for player in self.table.game.players:
                if user.name == player.name:
                    return player
        return None

    @staticmethod
    def __enrichMessage(game, about, command, kwargs):
        """add supplemental data for debugging"""
        if command.sendScore and about:
            # the clients will compare our status with theirs. This helps
            # very much in finding bugs.
            kwargs['score'] = str(about.hand)
        if game and game.gameid and 'token' not in kwargs:
            # this lets the client assert that the message is meant for the
            # current hand
            kwargs['token'] = game.handId.token()
        else:
            kwargs['token'] = None

    def __convertReceivers(self, receivers):
        """try to convert Player to User or Client where possible"""
        for rec in receivers:
            if rec.__class__.__name__ == 'User':
                yield rec
            else:
                yield self.table.remotes[rec]

    def tell(self, about, receivers, command, **kwargs):
        """send info about player 'about' to users 'receivers'"""
        def encodeKwargs():
            """those values are classes like Meld, Tile etc.
               Convert to bytes"""
            _ = tuple(kwargs.keys())
            for keyword in _:
                if any(keyword.lower().endswith(x) for x in ('tile', 'tiles', 'meld', 'melds')):
                    if kwargs[keyword] is not None:
                        kwargs[keyword] = str(kwargs[keyword])
                if keyword == 'players':
                    kwargs['playerNames'] = [(x.wind, x.name) for x in kwargs[keyword]]
                    del kwargs['players']
        encodeKwargs()
        if about.__class__.__name__ == 'User':
            about = self.playerForUser(about)
        if not isinstance(receivers, list):
            receivers = list([receivers])
        assert receivers, 'DeferredBlock.tell(%s) has no receiver' % command
        self.__enrichMessage(self.table.game, about, command, kwargs)
        aboutName = about.name if about else None
        if self.table.running and len(receivers) in [1, 4]:
            # messages are either identical for all 4 players
            # or identical for 3 players and different for 1 player. And
            # we want to capture each message exactly once.
            self.table.game.moves.append(Move(about, command, kwargs))
        localDeferreds = []
        for rec in self.__convertReceivers(receivers):

            isClient = rec.__class__.__name__.endswith('Client')
            if isClient:
                defer = Deferred()
                defer.addCallback(rec.remote_move, command, **kwargs).addErrback(logException)
                defer.command = command.name
                defer.notifying = 'notifying' in kwargs
                self.__addRequest(defer, rec, about)
                localDeferreds.append(defer)
            else:
                if Debug.traffic:
                    message = '-> {receiver:<15} about {about} {command}{kwargs!r}'.format(
                        receiver=rec.name[:15], about=about, command=command,
                        kwargs=kwargs)
                    logDebug(message)
                defer = self.table.server.callRemote(
                    rec,
                    'move',
                    aboutName,
                    command.name,
                    **kwargs)
                if defer:
                    defer.command = command.name
                    defer.notifying = 'notifying' in kwargs
                    self.__addRequest(defer, rec, about)
                else:
                    msg = i18nE('The game server lost connection to player %1')
                    self.table.abort(msg, rec.name)


        for defer in localDeferreds:
            defer.callback(aboutName)  # callback needs an argument !

    def tellPlayer(self, player, command, **kwargs):
        """address only one user"""
        self.tell(player, player, command, **kwargs)

    def tellOthers(self, player, command, **kwargs):
        """tell others about player'"""
        self.tell(
            player,
            list(
                x for x in self.table.game.players if x.name != player.name),
            command,
            **kwargs)

    def tellAll(self, player, command, **kwargs):
        """tell something to all players"""
        self.tell(player, self.table.game.players, command, **kwargs)
