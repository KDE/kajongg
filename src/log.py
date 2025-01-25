# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

import logging
import os
from typing import TYPE_CHECKING, Union, Protocol, Optional

from locale import getpreferredencoding

# we must not import twisted or we need to change kajongg.py

from common import Internal, Debug
from qt import Qt, QEvent, PYQT_VERSION
from util import elapsedSince, traceback, gitHead, callers
from mi18n import i18n
from dialogs import Sorry, Information, NoPrompt


if TYPE_CHECKING:
    from twisted.internet.defer import Deferred
    from qt import QObject

SERVERMARK = '&&SERVER&&'


def translateServerMessage(msg:str) ->str:
    """because a PB exception can not pass a list of arguments, the server
    encodes them into one string using SERVERMARK as separator. That
    string is always english. Here we unpack and translate it into the
    client language."""
    if msg.find(SERVERMARK) >= 0:
        return i18n(*tuple(msg.split(SERVERMARK)[1:-1]))
    return msg

class SupportsIndent(Protocol):
    """for mypy"""
    indent:int

def dbgIndent(this:SupportsIndent, parent:Optional[SupportsIndent]) ->str:
    """show messages indented"""
    if this.indent == 0:
        return ''
    pIndent = parent.indent if parent and parent.indent else 0
    return (' │ ' * (pIndent)) + ' ├' + '─' * (this.indent - pIndent - 1)


def __logUnicodeMessage(prio:int, msg:str) ->None:
    """if we can encode the str msg to ascii, do so.
    Otherwise convert the str object into an utf-8 encoded
    str object.
    The logger module would log the str object with the
    marker feff at the beginning of every message, we do not want that."""
    byte_msg = msg.encode(getpreferredencoding(), 'ignore')[:4000]
    msg = byte_msg.decode(getpreferredencoding())
    Internal.logger.log(prio, msg)


def __enrichMessage(msg:str, withGamePrefix:bool=True) ->str:
    """
    Add some optional prefixes to msg: S/C, process id, time, git commit.

    @param msg: The original message.
    @type msg: C{str}
    @param withGamePrefix: If set, prepend the game prefix.
    @type withGamePrefix: C{Boolean}
    @rtype: C{str}
    """
    result = msg  # set the default
    if withGamePrefix and Internal.logPrefix:
        result = f"{Internal.logPrefix}{os.getpid() if Debug.process else ''}: {msg}"
    if Debug.timestamp:
        result = f'{elapsedSince(Debug.timestamp):08.4f} {result}'
    if Debug.git:
        head = gitHead()
        if head not in ('current', None):
            result = f'git:{head}/p3 {result}'
    if int(Debug.callers):
        result = '  ' + result
    return result


def __exceptionToString(exception:Exception) ->str:
    """
    Convert exception into a useful string for logging.

    @param exception: The exception to be logged.
    @type exception: C{Exception}

    @rtype: C{str}
    """
    parts = []
    for arg in exception.args:
        if hasattr(arg, 'strerror'):
            # when using py kde 4, this is already translated at this point
            # but I do not know what it does differently with gettext and if
            # I can do the same with the python gettext module
            parts.append(
                f'[Errno {arg.errno}] {i18n(arg.strerror)}')
        elif arg is None:
            pass
        else:
            parts.append(str(arg))
    if hasattr(exception, 'filename'):
        parts.append(exception.filename)
    return ' '.join(parts)

def logSummary(summary:traceback.StackSummary, prio:int) ->None:
    """log traceback summary"""
    for line in summary.format():
        if 'logException' not in line:
            __logUnicodeMessage(prio, '  ' + line.strip())

def logMessage(msg:Union[Exception, str], prio:int, showDialog:bool,
    showStack:bool=False, withGamePrefix:bool=True) ->'Deferred':
    """writes info message to log and to stdout"""
    if isinstance(msg, Exception):
        msg = __exceptionToString(msg)
    msg = str(msg)
    msg = translateServerMessage(msg)
    __logUnicodeMessage(prio, __enrichMessage(msg, withGamePrefix))
    if showStack:
        _ = traceback.walk_stack(None)
        summary = traceback.StackSummary.extract(_, limit=3, capture_locals=True)
        logSummary(summary, prio)
    if int(Debug.callers):
        __logUnicodeMessage(prio, callers(int(Debug.callers)))
    if showDialog and not Internal.isServer:
        return Information(msg) if prio == logging.INFO else Sorry(msg, always=True)
    return NoPrompt(msg)


def logInfo(msg:Union[Exception, str], showDialog:bool=False, withGamePrefix:bool=True) ->'Deferred':
    """log an info message"""
    return logMessage(msg, logging.INFO, showDialog, withGamePrefix=withGamePrefix)


def logError(msg:Union[Exception, str], showStack:bool=True, withGamePrefix:bool=True) ->'Deferred':
    """log an error message"""
    return logMessage(msg, logging.ERROR, True, showStack=showStack, withGamePrefix=withGamePrefix)


def logDebug(msg:Union[Exception, str], showStack:bool=False,
    withGamePrefix:bool=True, btIndent:Optional[int]=None) ->'Deferred':
    """log this message and show it on stdout
    if btIndent is set, message is indented by depth(backtrace)-btIndent"""
    if btIndent:
        depth = traceback.extract_stack()
        msg = ' ' * (len(depth) - btIndent) + str(msg)
    return logMessage(msg, logging.DEBUG, False, showStack=showStack, withGamePrefix=withGamePrefix)


def logWarning(msg:Union[Exception, str], withGamePrefix:bool=True) ->'Deferred':
    """log this message and show it on stdout"""
    return logMessage(msg, logging.WARNING, True, withGamePrefix=withGamePrefix)


def logException(exception: Union[Exception, str], withGamePrefix:bool=True) ->None:
    """logs error message and re-raises exception if we are not server"""
    logError(exception, withGamePrefix=withGamePrefix)
    exc_type = exception.__class__
    if hasattr(exception, 'type'):
        exc_type = exception.type
    isAssertion = 'Assertion' in exc_type.__name__
    if not Internal.isServer or isAssertion:
        if isinstance(exception, Exception):
            raise exception
        raise Exception(exception)  # pylint:disable=broad-exception-raised

class EventData(str):

    """used for generating a nice string"""
    events = {y: x for x, y in QEvent.__dict__.items() if isinstance(y, int)}
    # those are not documented for qevent but appear in Qt5Core/qcoreevent.h
    extra = {
        15: 'Create',
        16: 'Destroy',
        20: 'Quit',
        152: 'AcceptDropsChange',
        154: 'Windows:ZeroTimer'
    }
    events.update(extra)
    keys = {y: x for x, y in Qt.__dict__.items() if isinstance(y, int)}

    def __new__(cls, receiver:'QObject', event:'QEvent', prefix:Optional[str]=None) ->'EventData':
        """create the wanted string"""
        name = cls.eventName(event)
        msg = f'{name}{cls.eventValue(event)}receiver:{cls.eventReceiver(receiver)}'
        if prefix:
            msg = ': '.join([prefix, msg])
        if 'all' in Debug.events or any(x in msg for x in Debug.events.split(':')):
            logDebug(msg)
        return super().__new__(cls, msg)

    @classmethod
    def eventReceiver(cls, receiver:'QObject') ->str:
        """Format data about event receiver"""
        text = ''
        if hasattr(receiver, 'text'):
            try:
                text = receiver.text()
            except TypeError:
                text = receiver.text
        name = ''
        if hasattr(receiver, 'objectName') and receiver.objectName():
            name = receiver.objectName()
        debug_name = ''
        if hasattr(receiver, 'debug_name'):
            debug_name = receiver.debug_name()

        return ''.join([text, name, debug_name, repr(receiver)])

    @classmethod
    def eventValue(cls, event:'QEvent') ->str:
        """Format data about event value"""
        value = ''
        if hasattr(event, 'key'):
            if event.key() in cls.keys:
                value = cls.keys[event.key()]
            else:
                value = f'unknown key:{event.key()}'
        if hasattr(event, 'text'):
            eventText = str(event.text())
            if eventText and eventText != '\r':
                value += f':{eventText}'
        return value

    @classmethod
    def eventName(cls, event:'QEvent') ->str:
        """Format data about event name"""
        if not PYQT_VERSION:
            # Pyside
            evtype = event.type()
            repr_last = repr(evtype).split('.')[-1]
            result = repr_last.split(':')[0]
        elif event.type() in cls.events:
            # ignore unknown event types
            result = cls.events[event.type()]
        else:
            result = f'unknown :{event.type()}'
        return f'Event:{result}'
