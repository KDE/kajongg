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
from PyKDE4.kdecore import i18n, i18nc

PREF = None
WINDS = 'ESWN'

import PyQt4.pyqtconfig

PYQTVERSION = PyQt4.pyqtconfig.Configuration().pyqt_version_str

syslog.openlog('kmj')
def logMessage(msg, prio=syslog.LOG_INFO):
    """writes info message to syslog and to stdout"""
    msg = msg.encode('utf-8', 'replace') # syslog does not work with unicode string
    syslog.syslog(prio,  msg)

def logException(exception, prio=syslog.LOG_ERR):
    """writes error message to syslog and re-raises exception"""
    msg = unicode(exception.message)
    print('logMessage:', msg)
    logMessage(msg, prio)
    for line in traceback.format_stack()[:-2]:
        logMessage(line)
    raise exception

def m18n(englishText, *args):
    """wrapper around i18n converting QString into a Python unicode string"""
    return unicode(i18n(englishText, *args))

def m18nc(context, englishText, *args):
    """wrapper around i18nc converting QString into a Python unicode string"""
    return unicode(i18nc(context, englishText, *args))

def rotateCenter(item, angle):
    """rotates a QGraphicsItem around its center"""
    center = item.boundingRect().center()
    centerX, centerY = center.x(), center.y()
    item.translate(centerX, centerY)
    item.rotate(angle)
    item.translate(-centerX, -centerY)
    return item
