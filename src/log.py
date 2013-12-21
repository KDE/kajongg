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
import string

from locale import getpreferredencoding
from sys import stderr, _getframe

SERVERMARK = '&&SERVER&&'

# util must not import twisted or we need to change kajongg.py

from common import Internal, Debug, unicode, isPython3 # pylint: disable=redefined-builtin
from util import elapsedSince, traceback, xToUtf8, gitHead
from kde import i18n, i18nc
from dialogs import Sorry, Information, NoPrompt

ENGLISHDICT = {}

LOGGER = None


class Fmt(string.Formatter):
    """this formatter can parse {id(x)} and output a short ascii form for id"""
    alphabet = string.ascii_uppercase + string.ascii_lowercase
    base = len(alphabet)
    formatter = None
    @staticmethod
    def num_encode(number, length=4):
        """make a short unique ascii string out of number, truncate to length"""
        result = []
        while number and len(result)<length:
            number, remainder = divmod(number, Fmt.base)
            result.append(Fmt.alphabet[remainder])
        return ''.join(reversed(result))

    def get_value(self, key, args, kwargs):
        if key.startswith('id(') and key.endswith(')'):
            idpar = key[3:-1]
            if idpar == 'self':
                idpar = 'SELF'
            if kwargs[idpar] is None:
                return 'None'
            elif Debug.neutral:
                return '....'
            else:
                return Fmt.num_encode(id(kwargs[idpar]))
        elif key == 'self':
            return kwargs['SELF']
        else:
            return kwargs[key]

Fmt.formatter = Fmt()

def fmt(text, **kwargs):
    """use the context dict for finding arguments.
    For something like {self} output 'self:selfValue'"""
    if '}' in text:
        parts = []
        for part in text.split('}'):
            if not '{' in part:
                parts.append(part)
            else:
                part2 = part.split('{')
                parts.append('%s%s:{%s}' % (part2[0], part2[1], part2[1]))
        text = ''.join(parts)
    argdict = _getframe(1).f_locals
    argdict.update(kwargs)
    if 'self' in argdict:
        # formatter.format will not accept 'self' as keyword
        argdict['SELF'] = argdict['self']
        del argdict['self']
    return Fmt.formatter.format(text, **argdict) # pylint: disable=star-args

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

def dbgIndent(this, parent):
    """show messages indented"""
    if this.indent == 0:
        return ''
    else:
        pIndent = parent.indent if parent else 0
        return (u'. ' * (pIndent))[:pIndent] + u'└' + u'─' * (this.indent - pIndent - 1)

def __logUnicodeMessage(prio, msg):
    """if we can encode the unicode msg to ascii, do so.
    Otherwise convert the unicode object into an utf-8 encoded
    str object.
    The logger module would log the unicode object with the
    marker feff at the beginning of every message, we do not want that."""
    msg = msg.encode(getpreferredencoding(), 'ignore')[:4000]
    if isPython3:
        msg = msg.decode()
    LOGGER.log(prio, msg)

def logMessage(msg, prio, showDialog, showStack=False, withGamePrefix=True):
    """writes info message to log and to stdout"""
    # pylint: disable=R0912
    if isinstance(msg, Exception):
        msg = ' '.join(unicode(x.decode(getpreferredencoding()) \
             if isinstance(x, str) else unicode(x)) for x in msg.args if x is not None)
    try:
        if isinstance(msg, str):
            msg = unicode(msg, 'utf-8')
        elif not isinstance(msg, unicode):
            msg = unicode(str(msg), 'utf-8')
    except TypeError:
        pass # python3 TODO:
    msg = translateServerMessage(msg)
    logMsg = msg
    if withGamePrefix and Internal.logPrefix:
        logMsg = u'{prefix}{process}: {msg}'.format(
            prefix=Internal.logPrefix,
            process = os.getpid() if Debug.process else '',
            msg=msg)
    if Debug.time:
        logMsg = u'{:08.4f} {}'.format(elapsedSince(Debug.time), logMsg)
    if Debug.git:
        head = gitHead()
        if head not in ('current', None):
            logMsg = u'git:{} {}'.format(head, logMsg)

    __logUnicodeMessage(prio, logMsg)
    if showStack:
        if showStack is True:
            lower = 2
        else:
            lower = -showStack - 3
        for line in traceback.format_stack()[lower:-3]:
            if not 'logException' in line:
                __logUnicodeMessage(prio, '  ' + line.strip())
    if showDialog and not Internal.isServer:
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

