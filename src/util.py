# -*- coding: utf-8 -*-

"""
Copyright (C) 2008,2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

The function isAlive() is taken from the book
"Rapid GUI Programming with Python and Qt"
by Mark Summerfield.

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
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

import syslog, traceback, os, datetime

SERVERMARK = '&&SERVER&&'

# util must not import twisted or we need to change kajongg.py

import sip

import common

try:
    from PyKDE4.kdecore import i18n, i18nc, i18np
except ImportError:
    # a server might not have KDE4
    # pylint thinks those are already defined
    # pylint: disable=E0102
    def i18n(englishIn,  *args):
        """dummy for server"""
        result = englishIn
        if '%' in result:
            for idx, arg in enumerate(args):
                result = result.replace('%' + str(idx+1), unicode(arg))
        if '%' in result:
            for ignore in ['numid', 'filename']:
                result = result.replace('<%s>' % ignore, '')
                result = result.replace('</%s>' % ignore, '')
        return result
    def i18nc(dummyContext, englishIn, *args):
        """dummy for server"""
        return i18n(englishIn, *args)

if common.InternalParameters.app:
    # this must work on the client
    from PyKDE4.kdeui import KMessageBox
    from PyKDE4.kdecore import KGlobal
    def appdataDir():
        """the per user directory with kajongg application information like the database"""
        return os.path.dirname(str(KGlobal.dirs().locateLocal("appdata", "kajongg.db"))) + '/'
else:
    class KMessageBox(object):
        """dummy for server, just show on stdout"""
        @staticmethod
        def sorry(dummy, *args):
            """just output to stdout"""
            print ' '.join(args)
    def appdataDir():
        """the per user directory with kajongg application information like the database"""
        kdehome = os.environ.get('KDEHOME', '~/.kde')
        path = os.path.expanduser(kdehome + '/share/apps/kajongg/')
        if not os.path.exists(path):
            os.makedirs(path)
        return path

ENGLISHDICT = {}

def english(i18nstring):
    """translate back from local language"""
    return ENGLISHDICT.get(i18nstring, i18nstring)

def translateServerMessage(msg):
    """because a PB exception can not pass a list of arguments, the server
    encodes them into one string using SERVERMARK as separator. That
    string is always english. Here we unpack and translate it into the
    client language."""
    if msg.find(SERVERMARK) >=0:
        return m18n(*tuple(msg.split(SERVERMARK)[1:]))
    return msg

def syslogMessage(msg, prio=syslog.LOG_INFO):
    """writes msg to syslog"""
    msg = translateServerMessage(msg)
    msg = msg.encode('utf-8', 'replace') # syslog does not work with unicode string
    syslog.syslog(prio, msg)

def stack(msg, limit=6):
    """returns a list of lines with msg as prefix"""
    result = []
    for fileName, line, function, txt in traceback.extract_stack(limit=limit+2)[:-2]:
        result.append('%s %s/%d %s: %s' % (msg, os.path.splitext(os.path.basename(fileName))[0],
                                line, function, txt))
    return result

def logMessage(msg, prio=syslog.LOG_INFO):
    """writes info message to syslog and to stdout"""
    msg = translateServerMessage(msg)
    syslogMessage(msg, prio)
    if prio == syslog.LOG_ERR:
        print(msg)
        for line in traceback.format_stack()[:-2]:
            if not 'logException' in line:
                syslogMessage(line, prio)
                print(line)

def debugMessage(msg):
    """syslog/debug this message and show it on stdout"""
    logMessage(msg, prio=syslog.LOG_DEBUG)
    print(msg)

def logWarning(msg, prio=syslog.LOG_WARNING):
    """writes info message to syslog and to stdout"""
    if isinstance(msg, Exception):
        msg = ' '.join(unicode(x) for x in msg.args if x is not None)
    if isinstance(msg, str):
        msg = unicode(msg, 'utf-8')
    elif not isinstance(msg, unicode):
        msg = unicode(str(msg), 'utf-8')
    msg = translateServerMessage(msg)
    logMessage(msg, prio)
    if  common.InternalParameters.isServer:
        print msg
    else:
        if prio == syslog.LOG_INFO:
            KMessageBox.information(None, msg)
        else:
            KMessageBox.sorry(None, msg)

def logException(exception, prio=syslog.LOG_ERR):
    """writes error message to syslog and re-raises exception"""
    msg = str(exception)
    msg = translateServerMessage(msg)
    logMessage(msg, prio)
    KMessageBox.sorry(None, msg)
    if isinstance(exception, (str, unicode)):
        exception = Exception(exception)
    raise exception

def m18n(englishText, *args):
    """wrapper around i18n converting QString into a Python unicode string"""
    if  isinstance(englishText, unicode):
        englishText = englishText.encode('utf-8')
    result = unicode(i18n(englishText, *args))
    if not args:
        ENGLISHDICT[result] = englishText
    return result

def m18np(englishSingular, englishPlural, *args):
    """wrapper around i18np converting QString into a Python unicode string"""
    return unicode(i18np(englishSingular, englishPlural, *args))

def m18nc(context, englishText, *args):
    """wrapper around i18nc converting QString into a Python unicode string"""
    if  isinstance(englishText, unicode):
        englishText = englishText.encode('utf-8')
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

def isAlive(qobj):
    """is the underlying C++ object still valid?"""
    try:
        sip.unwrapinstance(qobj)
    except RuntimeError:
        return False
    else:
        return True

def socketName():
    """the client process uses this socket to talk to a local game server"""
    return appdataDir() + 'socket'

def which(program):
    """returns the full path for the binary or None"""
    for path in os.environ['PATH'].split(':'):
        fullName = os.path.join(path, program)
        if os.path.exists(fullName):
            return fullName

import gc

def _getr(slist, olist, seen):
    """Recursively expand slist's objects into olist, using seen to track
    already processed objects."""
    for elment in slist:
        if id(elment) in seen:
            continue
        seen[id(elment)] = None
        olist.append(elment)
        tlist = gc.get_referents(elment)
        if tlist:
            _getr(tlist, olist, seen)

# The public function.
def get_all_objects():
    """Return a list of all live Python objects, not including the
    list itself. May use this in Duration for showing where
    objects are leaking"""
    gc.collect()
    gcl = gc.get_objects()
    olist = []
    seen = {}
    # Just in case:
    seen[id(gcl)] = None
    seen[id(olist)] = None
    seen[id(seen)] = None
    # _getr does the real work.
    _getr(gcl, olist, seen)
    return olist

class Duration(object):
    """a helper class for checking code execution duration"""
    def __init__(self, name, time=None, bug=False):
        """name describes where in the source we are checking
        time is a threshold in seconds, do not warn below
        if bug is True, throw an exception if time is exceeded"""
        self.name = name
        self.time = time or 1.0
        self.bug = bug
        self.__start = datetime.datetime.now()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trback):
        """now check time passed"""
        diff = datetime.datetime.now() - self.__start
        if diff.seconds + diff.microseconds / 1000000 > self.time:
            if diff.seconds < 86000:
        # be silent for small negative changes of system date
                msg = '%s: duration: %d.%06d seconds' % (self.name, diff.seconds, diff.microseconds)
                if self.bug:
                    logException(msg)
                else:
                    debugMessage(msg)
