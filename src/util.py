#!/usr/bin/env python
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

import syslog,  traceback, os, sys

SYSLOGPREFIX = os.path.splitext(os.path.basename(sys.argv[0]))[0]
syslog.openlog(SYSLOGPREFIX)

try:
    import sip
    from PyKDE4.kdecore import i18n, i18nc,  KGlobal
    from PyKDE4.kdeui import KMessageBox
    def getDbPath():
        return KGlobal.dirs().locateLocal("appdata","kajongg.db")
except Exception:
    # a server does not have KDE4
    def i18n(english,  *args):
        result = english
        for idx, arg in enumerate(args):
            result = result.replace('%' + str(idx+1), arg)
        for ignore in ['numid', 'filename']:
            result = result.replace('<%s>' % ignore, '')
            result = result.replace('</%s>' % ignore, '')
        return result   
    def i18nc(context, english, *args):
        return i18n(english, *args)
    def KMessageBox(*args):
        pass
    def getDbPath():
        path = os.path.expanduser('~/.kde/share/apps/kajongg/kajongg.db')
        try:
            os.makedirs(os.path.dirname(path))
        except Exception:
            pass
        return path

# util must not import twisted or we need to change kajongg.py

PREF = None
WINDS = 'ESWN'
LIGHTSOURCES = ['NE', 'NW', 'SW', 'SE']

english = {}

SERVERMARK = '&&SERVER&&'

class InternalParameters:
    seed = None
    autoMode = False
    showSql = False
    debugTraffic = False
    debugRegex = False
    profileRegex = False
    dbPath = getDbPath()

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
    syslog.syslog(prio,  msg)

def logMessage(msg, prio=syslog.LOG_INFO):
    """writes info message to syslog and to stdout"""
    msg = translateServerMessage(msg)
    syslogMessage(msg,prio)
    if prio == syslog.LOG_ERR:
        print(msg)
        for line in traceback.format_stack()[:-2]:
            if not 'logException' in line:
                syslogMessage(line,prio)
                print(line)

def debugMessage(msg):
    logMessage(msg, prio=syslog.LOG_DEBUG)
    print(msg)

def logWarning(msg, prio=syslog.LOG_WARNING, isServer=False):
    """writes info message to syslog and to stdout"""
    msg = str(msg) # might be an exception
    msg = translateServerMessage(msg)
    logMessage(msg, prio)
    if not isServer:
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
                english[result] = englishText
        return result
    except Exception, e:
        if args:
            raise e
        # m18n might be called for a ruleset description. This could be standard
        # english text or indigene text.
        return englishText

def m18nc(context, englishText, *args):
    """wrapper around i18nc converting QString into a Python unicode string"""
    result = unicode(i18nc(context, englishText, *args))
    if not args:
        english[result] = englishText
    return result

def m18nE(englishText):
    """use this if you want to get the english text right now but still have the string translated"""
    return englishText

def m18ncE(context, englishText):
    """use this if you want to get the english text right now but still have the string translated"""
    return englishText

def isAlive(qobj):
    try:
        sip.unwrapinstance(qobj)
    except RuntimeError:
        return False
    else:
        return True

class Elements(object):
    """represents all elements"""
    def __init__(self):
        self.occurrence =  dict() # key: db, s3 etc. value: occurrence
        for wind in 'eswn':
            self.occurrence['w%s' % wind] = 4
        for dragon in 'bgr':
            self.occurrence['d%s' % dragon] = 4
        for color in 'sbc':
            for value in '123456789':
                self.occurrence['%s%s' % (color, value)] = 4
        for bonus in 'fy':
            for wind in 'eswn':
                self.occurrence['%s%s' % (bonus, wind)] = 1

    def __filter(self, withBoni):
        return (x for x in self.occurrence if withBoni or (x[0] not in 'fy'))

    def count(self, withBoni):
        """how many tiles are to be used by the game"""
        return sum(self.occurrence[e] for e in self.__filter(withBoni))

    def all(self, withBoni):
        """a list of all elements, each of them occurrence times"""
        result = []
        for element in self.__filter(withBoni):
            result.extend([element] * self.occurrence[element])
        return result

Elements = Elements()



if __name__ == '__main__':
    print m18n('i am a <numid>%1</numid> template %2 %1', 'abc', 'def')
