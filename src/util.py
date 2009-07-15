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
from PyQt4.QtGui import QSplitter
from PyKDE4.kdecore import i18n, i18nc
from PyKDE4.kdeui import KMessageBox

PREF = None
WINDS = 'ESWN'

import PyQt4.pyqtconfig

PYQTVERSION = PyQt4.pyqtconfig.Configuration().pyqt_version_str

english = {}

syslog.openlog('kmj')
def logMessage(msg, prio=syslog.LOG_INFO):
    """writes info message to syslog and to stdout"""
    msg = str(msg).encode('utf-8', 'replace') # syslog does not work with unicode string
    syslog.syslog(prio,  msg)
    if prio == syslog.LOG_ERR:
        for line in traceback.format_stack()[:-2]:
            logMessage(line)
            print(line)

def logException(exception, prio=syslog.LOG_ERR):
    """writes error message to syslog and re-raises exception"""
    msg = unicode(exception.message)
    print('logException:', msg)
    KMessageBox.sorry(None, msg)
    logMessage(msg, prio)
    for line in traceback.format_stack()[:-2]:
        logMessage(line)
    raise exception

def m18n(englishText, *args):
    """wrapper around i18n converting QString into a Python unicode string"""
    try:
        result = unicode(i18n(englishText, *args))
        if not args:
            if result != englishText:
                english[result] = englishText
        return result
    except Exception:
        assert not args
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

def rotateCenter(item, angle):
    """rotates a QGraphicsItem around its center"""
    center = item.boundingRect().center()
    centerX, centerY = center.x(), center.y()
    item.translate(centerX, centerY)
    item.rotate(angle)
    item.translate(-centerX, -centerY)
    return item

class StateSaver(object):
        def __init__(self, what, name=None):
            self.what = what
            self.name = name
            if not self.name:
                self.name = str(what.objectName())
            if not self.name:
                if what.parentWidget():
                    self.name = str(what.parentWidget().objectName()+what.__class__.__name__)
                else:
                    self.name = str(what.__class__.__name__)
            PREF.addString('States', self.name)
            oldState = QByteArray.fromHex(PREF[self.name])
            if isinstance(what, QSplitter):
                what.restoreState(oldState)
                self.saveMethod = what.saveState
            else:
                what.restoreGeometry(oldState)
                self.saveMethod = what.saveGeometry

        def save(self):
            if self:
                PREF[self.name] = QString(self.saveMethod().toHex())
                PREF.writeConfig()

