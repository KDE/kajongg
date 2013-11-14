# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

import logging, socket, logging.handlers, os

from locale import getpreferredencoding
from sys import stderr

SERVERMARK = '&&SERVER&&'

# util must not import twisted or we need to change kajongg.py

from common import Internal, Debug
from util import kprint, elapsedSince, traceback, xToUtf8

if Internal.haveKDE:
    from kde import i18n, i18nc
    from dialogs import Sorry, Information, NoPrompt
else:
    # a server might not have KDE4
    def i18n(englishIn, *args):
        """dummy for server"""
        result = englishIn
        if '%' in result:
            for idx, arg in enumerate(args):
                arg = xToUtf8(arg)
                result = result.replace('%' + str(idx+1), unicode(arg))
        if '%' in result:
            for ignore in ['numid', 'filename']:
                result = result.replace('<%s>' % ignore, '')
                result = result.replace('</%s>' % ignore, '')
        return result
    def i18nc(dummyContext, englishIn, *args):
        """dummy for server"""
        return i18n(englishIn, *args)

from kde import i18n, i18nc
from dialogs import Sorry, Information, NoPrompt

if not Internal.isServer:
    class PrintFirstArg(object):
        """just print the first argument"""
        def __init__(self, *args):
            kprint(args[0])
    Sorry = Information = PrintFirstArg  # pylint: disable=invalid-name

ENGLISHDICT = {}

LOGGER = None

def english(i18nstring):
    """translate back from local language"""
    return ENGLISHDICT.get(i18nstring, i18nstring)

def translateServerMessage(msg):
    """because a PB exception can not pass a list of arguments, the server
    encodes them into one string using SERVERMARK as separator. That
    string is always english. Here we unpack and translate it into the
    client language."""
    if msg.find(SERVERMARK) >= 0:
        return m18n(*tuple(msg.split(SERVERMARK)[1:-1]))
    return msg

def initLog(logName):
    """init the loggers"""
    global LOGGER # pylint: disable=global-statement
    LOGGER = logging.getLogger(logName)
    try:
        handler = logging.handlers.SysLogHandler('/dev/log')
    except (AttributeError, socket.error):
        handler = logging.handlers.RotatingFileHandler('kajongg.log', maxBytes=100000000, backupCount=10)
    LOGGER.addHandler(handler)
    LOGGER.addHandler(logging.StreamHandler(stderr))
    LOGGER.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(name)s: %(levelname)s %(message)s")
    handler.setFormatter(formatter)

def __logUnicodeMessage(prio, msg):
    """if we can encode the unicode msg to ascii, do so.
    Otherwise convert the unicode object into an utf-8 encoded
    str object.
    The logger module would log the unicode object with the
    marker feff at the beginning of every message, we do not want that."""
    msg = msg.encode(getpreferredencoding(), 'ignore')[:4000]
    LOGGER.log(prio, msg)

def logMessage(msg, prio, showDialog, showStack=False, withGamePrefix=True):
    """writes info message to log and to stdout"""
    # pylint: disable=R0912
    if isinstance(msg, Exception):
        msg = ' '.join(unicode(x.decode(getpreferredencoding()) \
             if isinstance(x, str) else unicode(x)) for x in msg.args if x is not None)
    if isinstance(msg, str):
        msg = unicode(msg, 'utf-8')
    elif not isinstance(msg, unicode):
        msg = unicode(str(msg), 'utf-8')
    msg = translateServerMessage(msg)
    logMsg = msg
    if withGamePrefix and Internal.logPrefix:
        logMsg = u'{prefix}{process}{time}: {msg}'.format(
            prefix=Internal.logPrefix,
            process = os.getpid() if Debug.process else '',
            time = '[%s]' % elapsedSince(Debug.time) if Debug.time else '',
            msg=msg)
    __logUnicodeMessage(prio, logMsg)
    if showStack:
        if showStack is True:
            lower = 2
        else:
            lower = -showStack - 3
        for line in traceback.format_stack()[lower:-3]:
            if not 'logException' in line:
                __logUnicodeMessage(prio, '  ' + line.strip())
    if showDialog:
        if prio == logging.INFO:
            return Information(msg)
        else:
            return Sorry(msg)
    return NoPrompt(msg)

def logInfo(msg, showDialog=False, withGamePrefix=True):
    """log an info message"""
    return logMessage(msg, logging.INFO, showDialog, withGamePrefix=withGamePrefix)

def logError(msg, withGamePrefix=True):
    """log an error message"""
    return logMessage(msg, logging.ERROR, True, showStack=True, withGamePrefix=withGamePrefix)

def logDebug(msg, showStack=False, withGamePrefix=True, btIndent=None):
    """log this message and show it on stdout
    if btIndent is set, message is indented by depth(backtrace)-btIndent"""
    if btIndent:
        depth = traceback.extract_stack()
        msg = ' ' * (len(depth) - btIndent) + msg
    return logMessage(msg, logging.DEBUG, False, showStack=showStack, withGamePrefix=withGamePrefix)

def logWarning(msg, withGamePrefix=True):
    """log this message and show it on stdout"""
    return logMessage(msg, logging.WARNING, True, withGamePrefix=withGamePrefix)

def logException(exception, withGamePrefix=True):
    """logs error message and re-raises exception"""
    logError(exception, withGamePrefix=withGamePrefix)
    if isinstance(exception, (str, unicode)):
        msg = exception.encode('utf-8', 'replace')
        exception = Exception(msg)
    raise exception

def m18n(englishText, *args):
    """wrapper around i18n converting QString into a Python unicode string"""
    englishText = xToUtf8(englishText)
    result = unicode(i18n(englishText, *args))
    if not args:
        ENGLISHDICT[result] = englishText
    return result

def m18nc(context, englishText, *args):
    """wrapper around i18nc converting QString into a Python unicode string"""
    englishText = xToUtf8(englishText)
    result = unicode(i18nc(context, englishText, *args))
    if not args:
        ENGLISHDICT[result] = englishText
    return result

def m18nE(englishText):
    """use this if you want to get the english text right now but still have the string translated"""
    return englishText

def m18ncE(dummyContext, englishText):
    """use this if you want to get the english text right now but still have the string translated"""
    return englishText

