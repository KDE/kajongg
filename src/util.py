#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008,2009 Wolfgang Rohdewald <wolfgang@rohdewald.de>

kmj is free software you can redistribute it and/or modify
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

import syslog,  traceback
from PyQt4.QtCore import QByteArray, QString
from PyQt4.QtGui import QSplitter, QHeaderView
from PyKDE4.kdecore import i18n, i18nc
from PyKDE4.kdeui import KMessageBox

PREF = None
WINDS = 'ESWN'

english = {}

syslog.openlog('kmj')

SERVERMARK = '&&SERVER&&'

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

def logWarning(msg, prio=syslog.LOG_WARNING, isServer=False):
    """writes info message to syslog and to stdout"""
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
    raise exception

def m18n(englishText, *args):
    """wrapper around i18n converting QString into a Python unicode string"""
    try:
        result = unicode(i18n(englishText, *args))
        if not args:
            if result != englishText:
                english[result] = englishText
        return result
    except Exception as e:
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

def rotateCenter(item, angle):
    """rotates a QGraphicsItem around its center"""
    center = item.boundingRect().center()
    centerX, centerY = center.x(), center.y()
    item.translate(centerX, centerY)
    item.rotate(angle)
    item.translate(-centerX, -centerY)
    return item

class StateSaver(object):
    """saves and restores the state for widgets"""
    def __init__(self, *what):
        self.widgets = []
        for widget in what:
            name = unicode(widget.objectName())
            if not name:
                if widget.parentWidget():
                    name = unicode(widget.parentWidget().objectName()+widget.__class__.__name__)
                else:
                    name = unicode(widget.__class__.__name__)
            self.widgets.append((widget,  name))
            PREF.addString('States', name)
        for widget, name in self.widgets:
            oldState = QByteArray.fromHex(PREF[name])
            if isinstance(widget, (QSplitter, QHeaderView)):
                widget.restoreState(oldState)
            else:
                widget.restoreGeometry(oldState)

    def save(self):
        """saves the state"""
        for widget, name in self.widgets:
            if isinstance(widget, (QSplitter, QHeaderView)):
                saveMethod = widget.saveState
            else:
                saveMethod = widget.saveGeometry
            PREF[name] = QString(saveMethod().toHex())
            PREF.writeConfig()

