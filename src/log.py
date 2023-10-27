# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

import logging
import os

from locale import getpreferredencoding

# we must not import twisted or we need to change kajongg.py

from common import Internal, Debug
from qt import Qt, QEvent
from util import elapsedSince, traceback, gitHead, callers
from mi18n import i18n
from dialogs import Sorry, Information, NoPrompt


SERVERMARK = '&&SERVER&&'


def translateServerMessage(msg):
    """because a PB exception can not pass a list of arguments, the server
    encodes them into one string using SERVERMARK as separator. That
    string is always english. Here we unpack and translate it into the
    client language."""
    if msg.find(SERVERMARK) >= 0:
        return i18n(*tuple(msg.split(SERVERMARK)[1:-1]))
    return msg


def dbgIndent(this, parent):
    """show messages indented"""
    if this.indent == 0:
        return ''
    pIndent = parent.indent if parent else 0
    return (' │ ' * (pIndent)) + ' ├' + '─' * (this.indent - pIndent - 1)


def __logUnicodeMessage(prio, msg):
    """if we can encode the str msg to ascii, do so.
    Otherwise convert the str object into an utf-8 encoded
    str object.
    The logger module would log the str object with the
    marker feff at the beginning of every message, we do not want that."""
    msg = msg.encode(getpreferredencoding(), 'ignore')[:4000]
    msg = msg.decode(getpreferredencoding())
    Internal.logger.log(prio, msg)


def __enrichMessage(msg, withGamePrefix=True):
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
        result = '{prefix}{process}: {msg}'.format(
            prefix=Internal.logPrefix,
            process=os.getpid() if Debug.process else '',
            msg=msg)
    if Debug.timestamp:
        result = '{:08.4f} {}'.format(elapsedSince(Debug.timestamp), result)
    if Debug.git:
        head = gitHead()
        if head not in ('current', None):
            result = 'git:{}/p3 {}'.format(head, result)
    if int(Debug.callers):
        result = '  ' + result
    return result


def __exceptionToString(exception):
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
                '[Errno {}] {}'.format(arg.errno, i18n(arg.strerror)))
        elif arg is None:
            pass
        else:
            parts.append(str(arg))
    if hasattr(exception, 'filename'):
        parts.append(exception.filename)
    return ' '.join(parts)

def logSummary(summary, prio):
    """log traceback summary"""
    for line in summary.format():
        if 'logException' not in line:
            __logUnicodeMessage(prio, '  ' + line.strip())

def logMessage(msg, prio, showDialog, showStack=False, withGamePrefix=True):
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


def logInfo(msg, showDialog=False, withGamePrefix=True):
    """log an info message"""
    return logMessage(msg, logging.INFO, showDialog, withGamePrefix=withGamePrefix)


def logError(msg, showStack=True, withGamePrefix=True):
    """log an error message"""
    return logMessage(msg, logging.ERROR, True, showStack=showStack, withGamePrefix=withGamePrefix)


def logDebug(msg, showStack=False, withGamePrefix=True, btIndent=None):
    """log this message and show it on stdout
    if btIndent is set, message is indented by depth(backtrace)-btIndent"""
    if btIndent:
        depth = traceback.extract_stack()
        msg = ' ' * (len(depth) - btIndent) + str(msg)
    return logMessage(msg, logging.DEBUG, False, showStack=showStack, withGamePrefix=withGamePrefix)


def logWarning(msg, withGamePrefix=True):
    """log this message and show it on stdout"""
    return logMessage(msg, logging.WARNING, True, withGamePrefix=withGamePrefix)


def logException(exception: str, withGamePrefix=True) ->None:
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

    def __new__(cls, receiver, event, prefix=None):
        """create the wanted string"""
        # pylint: disable=too-many-branches
        if event.type() in cls.events:
            # ignore unknown event types
            name = cls.events[event.type()]
            value = ''
            if hasattr(event, 'key'):
                if event.key() in cls.keys:
                    value = cls.keys[event.key()]
                else:
                    value = 'unknown key:%s' % event.key()
            if hasattr(event, 'text'):
                eventText = str(event.text())
                if eventText and eventText != '\r':
                    value += ':%s' % eventText
            if value:
                value = '(%s)' % value
            msg = '%s%s->%s' % (name, value, receiver)
            if hasattr(receiver, 'text'):
                if receiver.__class__.__name__ != 'QAbstractSpinBox':
                    # accessing QAbstractSpinBox.text() gives a segfault
                    try:
                        msg += '(%s)' % receiver.text()
                    except TypeError:
                        msg += '(%s)' % receiver.text
            elif hasattr(receiver, 'objectName'):
                msg += '(%s)' % receiver.objectName()
        else:
            msg = 'unknown event:%s' % event.type()
        if prefix:
            msg = ': '.join([prefix, msg])
        if 'all' in Debug.events or any(x in msg for x in Debug.events.split(':')):
            logDebug(msg)
        return msg
