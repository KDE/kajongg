# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

from typing import Dict, TYPE_CHECKING, Any, Optional
from qt import QObject, QByteArray, QEvent, QSplitter, QHeaderView

from common import Internal, isAlive
from mi18n import english

if TYPE_CHECKING:
    from qt import QWidget


class StateSaver(QObject):

    """saves and restores the state for widgets"""

    savers : Dict['QWidget', 'StateSaver'] = {}

    def __init__(self, *widgets:'QWidget') ->None:
        super().__init__()
        pref = Internal.Preferences
        assert pref
        self.widgets = []
        for widget in widgets:
            if widget not in StateSaver.savers:
                StateSaver.savers[widget] = self
                widget.installEventFilter(self)
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
    def __restore(widget:'QWidget', name:str) ->bool:
        """decode the saved string"""
        # pylint: disable=unsubscriptable-object
        def canRestore(name:str,what:str) ->bool:
            return name.endswith(what) and hasattr(widget, 'restore' + what)
        assert Internal.Preferences
        state = QByteArray.fromHex(Internal.Preferences[name].encode())
        if state:
            if canRestore(name, 'State'):
                widget.restoreState(state)  # type:ignore[attr-defined]
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
    def __generateName(widget:'QWidget') ->str:
        """generate a name for this widget to be used in the config file"""
        _ = widget
        name = english(widget.objectName())
        if not name:
            while _.parentWidget():
                name = _.__class__.__name__ + name
                assert _  # for mypy - not possible because of while condition
                _ = _.parentWidget()
                if _.parentWidget():
                    widgetName = english(_.parentWidget().objectName())
                    if widgetName:
                        name = widgetName + name
                        break
        if not name:
            name = widget.__class__.__name__
        return str(name)

    def eventFilter(self, unusedWatched:Optional[QObject], event:Optional[QEvent]) ->bool:
        """if the watched widget hides, save its state.
        Return False if the event should be handled further"""
        if QEvent is not None and event:
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
    def saveAll() ->None:
        """execute all registered savers and write states to config file"""
        assert Internal.Preferences
        for saver in StateSaver.savers.values():
            saver.save()
        Internal.Preferences.writeConfig()

    @staticmethod
    def stateStr(state:Any) ->str:
        """convert hex string to str"""
        return str(bytes(state.toHex()).decode())

    def save(self) ->None:
        """writes the state into Preferences, but does not save"""
        assert Internal.Preferences
        for name, widget in self.widgets:
            if isAlive(widget):
                # pylint: disable=unsupported-assignment-operation
                if hasattr(widget, 'saveState'):
                    Internal.Preferences[name + 'State'] = self.stateStr(widget.saveState())
                if hasattr(widget, 'saveGeometry'):
                    Internal.Preferences[name + 'Geometry'] = self.stateStr(widget.saveGeometry())
        Internal.Preferences.writeConfig()
