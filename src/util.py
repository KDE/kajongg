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

import syslog, traceback, os

SERVERMARK = '&&SERVER&&'

import common

__USEKDE4 = False

if common.InternalParameters.app:
    try:
        import sip
        from PyKDE4.kdecore import i18n, i18nc, i18np, KGlobal
        from PyKDE4.kdeui import KMessageBox
        def appdataDir():
            """the per user directory with kajongg application information like the database"""
            return os.path.dirname(str(KGlobal.dirs().locateLocal("appdata", "kajongg.db"))) + '/'
        __USEKDE4 = True
    except ImportError:
        pass

if not __USEKDE4:
    # a server does not have KDE4
    def i18n(englishIn,  *args):
        """dummy for server"""
        result = englishIn
        if '%' in result:
            for idx, arg in enumerate(args):
                result = result.replace('%' + str(idx+1), str(arg))
        if '%' in result:
            for ignore in ['numid', 'filename']:
                result = result.replace('<%s>' % ignore, '')
                result = result.replace('</%s>' % ignore, '')
        return result
    def i18nc(dummyContext, englishIn, *args):
        """dummy for server"""
        return i18n(englishIn, *args)
    class KMessageBox(object):
        """dummy for server, just show on stdout"""
        @staticmethod
        def sorry(dummy, *args):
            """just output to stdout"""
            print ' '.join(args)

    def appdataDir():
        """the per user directory with kajongg application information like the database"""
        path = os.path.expanduser('~/.kde/share/apps/kajongg/')
        try:
            os.makedirs(path)
        except Exception:
            pass
        return path

# util must not import twisted or we need to change kajongg.py

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

def logWarning(msg, prio=syslog.LOG_WARNING, isServer=False):
    """writes info message to syslog and to stdout"""
    msg = unicode(msg) # might be an exception
    msg = translateServerMessage(msg)
    logMessage(msg, prio)
    if not isServer and not common.InternalParameters.autoPlay:
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
    try:
        result = unicode(i18n(englishText, *args))
        if not args:
            if result != englishText:
                ENGLISHDICT[result] = englishText
        return result
    except Exception, excObj:
        if args:
            raise excObj
        # m18n might be called for a ruleset description. This could be standard
        # english text or indigene text.
        return englishText

def m18np(englishSingular, englishPlural, *args):
    """wrapper around i18np converting QString into a Python unicode string"""
    return unicode(i18np(englishSingular, englishPlural, *args))

def m18nc(context, englishText, *args):
    """wrapper around i18nc converting QString into a Python unicode string"""
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
