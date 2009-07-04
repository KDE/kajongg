#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008,2009 Wolfgang Rohdewald <wolfgang@rohdewald.de>

partially based on C++ code from:
    Copyright (C) 2006 Mauricio Piacentini  <mauricio@tabuleiro.com>

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


from PyQt4.QtGui import QWidget
from PyQt4.QtCore import QString, SIGNAL
from PyKDE4.kdecore import i18n
from PyKDE4.kdeui import KConfigSkeleton, KConfigDialog, KMessageBox
from tilesetselector import TilesetSelector
from backgroundselector import BackgroundSelector
from rulesetselector import RulesetSelector
from general_ui import Ui_General
import util
from util import logException
from query import Query


class Parameter(object):
    """helper class for defining configuration parameters"""
    def __init__(self, group, name, default=None):
        """configuration group, parameter name, default value"""
        self.group = group
        self.name = name
        if default:
            self.default = default
        else:
            self.default = None
        self.item = None

class StringParameter(Parameter):
    """helper class for defining string parameters"""
    def __init__(self, group, name, default=None):
        Parameter.__init__(self, group, name, default)
        self.value = QString()

    def add(self, skeleton):
        """add tis parameter to the skeleton"""
        self.item = skeleton.addItemString(self.name, self.value, QString(self.default or ''))

class IntParameter(Parameter):
    """helper class for defining integer parameters"""
    def __init__(self, group, name, default=None, minValue=None, maxValue=None):
        """minValue and maxValue are also used by the edit widget"""
        Parameter.__init__(self, group, name, default)
        self.value = 0
        self.minValue = minValue
        self.maxValue = maxValue

    def add(self, skeleton):
        """add tis parameter to the skeleton"""
        self.item = skeleton.addItemInt(self.name, self.value, self.default)
        if self.minValue is not None:
            self.item.setMinValue(self.minValue)
        if self.maxValue is not None:
            self.item.setMaxValue(self.maxValue)


class Preferences(KConfigSkeleton):
    """Holds all kmj options. Only instantiate this once"""
    _Parameters = {}
    def __init__(self):
        if util.PREF:
            logException(Exception('PREF is not None'))
        util.PREF = self
        KConfigSkeleton.__init__(self)
        self.addParameter(StringParameter('General', 'tilesetName', 'default'))
        self.addParameter(StringParameter('General', 'windTilesetName', 'traditional'))
        self.addParameter(StringParameter('General', 'backgroundName', 'default'))
        self.addParameter(StringParameter('General', 'lastRuleset'))

    def __getattr__(self, name):
        """undefined attributes might be parameters"""
        if not name in Preferences._Parameters:
            raise AttributeError
        par = Preferences._Parameters[name]
        result = par.item.value()
        if isinstance(result, QString):
            result = str(result)
        return result

    def __setattr__(self, name, value):
        """undefined attributes might be parameters"""
        if not name in Preferences._Parameters:
            raise AttributeError
        par = Preferences._Parameters[name]
        par.item.setValue(value)

    def addParameter(self, par):
        """add a parameter to the skeleton"""
        Preferences._Parameters[par.name] = par
        self.setCurrentGroup(par.group)
        par.add(self)

class General(QWidget,  Ui_General):
    """general settings page"""
    def __init__(self,  parent = None):
        super(General, self).__init__(parent)
        self.setupUi(self)

class ConfigDialog(KConfigDialog):
    """configuration dialog with several pages"""
    def __init__(self, parent,  name,  pref):
        super(ConfigDialog, self).__init__(parent,  QString(name), pref )
        self.pref = pref
        self.general = General(self)
        self.rulesetSelector = RulesetSelector(self, pref)
        self.tilesetSelector = TilesetSelector(self, pref)
        self.backgroundSelector = BackgroundSelector(self, pref)
        self.kpagegeneral = self.addPage(self.general,
                i18n("General"), "games-config-options")
        self.kpagetilesel = self.addPage(self.tilesetSelector,
                i18n("Tiles"), "games-config-tiles")
        self.kpagebackgrsel = self.addPage(self.backgroundSelector,
                i18n("Backgrounds"), "games-config-background")
        self.kpagerulesetsel = self.addPage(self.rulesetSelector,
                i18n("Rulesets"), "games-kmj-law")

    def showEvent(self, event):
        """start transaction"""
        assert event # quieten pylint
        Query.dbhandle.transaction()

    def accept(self):
        """commit transaction"""
        if self.rulesetSelector.save():
            if Query.dbhandle.commit():
                KConfigDialog.accept(self)
                return
        KMessageBox.sorry(None, i18n('Cannot save your ruleset changes. You probably introduced a duplicate name.  Message from database: %1',
                                          Query.lastError))

    def reject(self):
        """rollback transaction"""
        Query.dbhandle.rollback()
        KConfigDialog.reject(self)

