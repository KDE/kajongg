#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008,2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from PyQt4.QtCore import QByteArray, QString
from PyQt4.QtGui import QSplitter, QHeaderView
from PyKDE4.kdecore import i18n, i18nc
from PyKDE4.kdeui import KMessageBox
from util import isAlive
import globals

class StateSaver(object):
    """saves and restores the state for widgets"""

    savers = []

    def __init__(self, *what):
        StateSaver.savers.append(self)
        self.widgets = []
        for widget in what:
            name = unicode(widget.objectName())
            if not name:
                if widget.parentWidget():
                    name = unicode(widget.parentWidget().objectName()+widget.__class__.__name__)
                else:
                    name = unicode(widget.__class__.__name__)
            self.widgets.append((widget, name))
            globals.PREF.addString('States', name)
        for widget, name in self.widgets:
            oldState = QByteArray.fromHex(globals.PREF[name])
            if isinstance(widget, (QSplitter, QHeaderView)):
                widget.restoreState(oldState)
            else:
                widget.restoreGeometry(oldState)

    @staticmethod
    def saveAll():
        """execute all registered savers.
        If a window is destroyed explicitly, it is expected to remove its saver"""
        for saver in StateSaver.savers:
            saver._write()
        globals.PREF.writeConfig()

    def _write(self):
        """writes the state into globals.PREF, but does not save"""
        for widget, name in self.widgets:
            assert isAlive(widget), name
            if isinstance(widget, (QSplitter, QHeaderView)):
                saveMethod = widget.saveState
            else:
                saveMethod = widget.saveGeometry
            globals.PREF[name] = QString(saveMethod().toHex())

