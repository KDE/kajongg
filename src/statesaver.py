# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

from qt import QObject, QByteArray, QEvent, QSplitter, QHeaderView

from common import Internal, isAlive
from mi18n import english


class StateSaver(QObject):

    """saves and restores the state for widgets"""

    savers = {}

    def __init__(self, *widgets):
        QObject.__init__(self)
        pref = Internal.Preferences
        if widgets[0] not in StateSaver.savers:
            StateSaver.savers[widgets[0]] = self
            widgets[0].installEventFilter(self)
        self.widgets = []
        for widget in widgets:
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
        # pylint: disable=unsubscriptable-object
        def canRestore(name,what):
            return name.endswith(what) and hasattr(widget, 'restore' + what)
        state = QByteArray.fromHex(Internal.Preferences[name].encode())
        if state:
            if canRestore(name, 'State'):
                widget.restoreState(state)
            elif canRestore(name, 'Geometry'):
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

    def eventFilter(self, unusedWatched, event):
        """if the watched widget hides, save its state.
        Return False if the event should be handled further"""
        if QEvent is not None:
            # while appquit, QEvent may be None. Maybe not anymore
            # with later versions?
            if event.type() in(QEvent.Type.Hide, QEvent.Type.Move, QEvent.Type.Resize):
                self.save()
            elif event.type() == QEvent.Type.Close:
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

    @staticmethod
    def stateStr(state):
        """convert hex string to str"""
        return str(bytes(state.toHex()).decode())

    def save(self):
        """writes the state into Preferences, but does not save"""
        for name, widget in self.widgets:
            if isAlive(widget):
                # pylint: disable=unsupported-assignment-operation
                if hasattr(widget, 'saveState'):
                    Internal.Preferences[name + 'State'] = self.stateStr(widget.saveState())
                if hasattr(widget, 'saveGeometry'):
                    Internal.Preferences[name + 'Geometry'] = self.stateStr(widget.saveGeometry())
