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

from PyQt4.QtCore import QObject, QByteArray, QString, QEvent
from PyQt4.QtGui import QSplitter, QHeaderView
from util import isAlive, english
import common

class StateSaver(QObject):
    """saves and restores the state for widgets"""

    savers = {}

    def __init__(self, *what):
        QObject.__init__(self)
        if what[0] not in StateSaver.savers:
            what[0].installEventFilter(self)
            StateSaver.savers[what[0]] = self
        self.widgets = []
        for widget in what:
            name = self.__generateName(widget)
            self.widgets.append((name, widget))
            common.PREF.addString('States', name)
        for name, widget in self.widgets:
            oldState = QByteArray.fromHex(common.PREF[name])
            if isinstance(widget, (QSplitter, QHeaderView)):
                widget.restoreState(oldState)
            else:
                widget.restoreGeometry(oldState)

    @staticmethod
    def __generateName(widget):
        """generate a name for this widget to be used in the config file"""
        name = english(widget.objectName())
        if not name:
            while widget.parentWidget():
                name = widget.__class__.__name__ + name
                widget = widget.parentWidget()
                widgetName = english(widget.parentWidget().objectName())
                if widgetName:
                    name = widgetName + name
                    break
        return name

    def eventFilter(self, watched, event):
        """if the watched widget hides, save its state"""
        if event.type() == QEvent.Hide:
            self.save()
        elif event.type() == QEvent.Close:
            self.save()
            del StateSaver.savers[self.widgets[0][1]]
        return QObject.eventFilter(self, watched, event)

    @staticmethod
    def saveAll():
        """execute all registered savers and write states to config file"""
        for saver in StateSaver.savers.values():
            saver.save()
        common.PREF.writeConfig()

    def save(self):
        """writes the state into common.PREF, but does not save"""
        for name, widget in self.widgets:
            if isAlive(widget):
                if isinstance(widget, (QSplitter, QHeaderView)):
                    saveMethod = widget.saveState
                else:
                    saveMethod = widget.saveGeometry
                common.PREF[name] = QString(saveMethod().toHex())
