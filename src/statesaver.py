# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

Kajongg is free software you can redistribute it and/or modify
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

from qt import QString, QObject, QByteArray, QEvent, QSplitter, QHeaderView
from qt import usingQt5

from common import Internal, isAlive, english, isPython3


class StateSaver(QObject):

    """saves and restores the state for widgets"""

    savers = {}

    def __init__(self, *what):
        QObject.__init__(self)
        pref = Internal.Preferences
        if what[0] not in StateSaver.savers:
            StateSaver.savers[what[0]] = self
            what[0].installEventFilter(self)
        self.widgets = []
        for widget in what:
            name = self.__generateName(widget)
            self.widgets.append((name, widget))
            pref.addString('States', name + 'State')
            pref.addString('States', name + 'Geometry')
        for name, widget in self.widgets:
            stateFound = self.__restore(widget, name + 'State')
            geometryFound = self.__restore(widget, name + 'Geometry')
            if not stateFound and not geometryFound:
                pref.addString('States', name)
                self.__restore(widget, name)

    @staticmethod
    def __restore(widget, name):
        """decode the saved string"""
        if usingQt5 and isPython3:
            # Qt5 fromHex expects bytes, not str
            state = QByteArray.fromHex(Internal.Preferences[name].encode())
        else:
            state = QByteArray.fromHex(Internal.Preferences[name])
        if state:
            if name.endswith('State'):
                widget.restoreState(state)
            elif name.endswith('Geometry'):
                widget.restoreGeometry(state)
            else:
                # legacy
                if isinstance(widget, (QSplitter, QHeaderView)):
                    widget.restoreState(state)
                else:
                    widget.restoreGeometry(state)
        return bool(state)

    @staticmethod
    def __generateName(widget):
        """generate a name for this widget to be used in the config file"""
        orgWidget = widget
        name = english(widget.objectName())
        if not name:
            while widget.parentWidget():
                name = widget.__class__.__name__ + name
                widget = widget.parentWidget()
                if widget.parentWidget():
                    widgetName = english(widget.parentWidget().objectName())
                    if widgetName:
                        name = widgetName + name
                        break
        if not name:
            name = orgWidget.__class__.__name__
        return str(name)

    def eventFilter(self, dummyWatched, event):
        """if the watched widget hides, save its state.
        Return False if the event should be handled further"""
        if QEvent is not None:
            # while appquit, QEvent may be None. Maybe not anymore
            # with later versions?
            if event.type() == QEvent.Hide:
                self.save()
            elif event.type() == QEvent.Close:
                self.save()
                widget = self.widgets[0][1]
                if widget in StateSaver.savers:
                    del StateSaver.savers[widget]
        return False

    @staticmethod
    def saveAll():
        """execute all registered savers and write states to config file"""
        for saver in StateSaver.savers.values():
            saver.save()
        Internal.Preferences.writeConfig()

    def save(self):
        """writes the state into Preferences, but does not save"""
        for name, widget in self.widgets:
            if isAlive(widget):
                if hasattr(widget, 'saveState'):
                    Internal.Preferences[name + 'State'] = QString(
                        widget.saveState().toHex())
                if hasattr(widget, 'saveGeometry'):
                    Internal.Preferences[name + 'Geometry'] = QString(
                        widget.saveGeometry().toHex())
