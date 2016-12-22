# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

partially based on C++ code from:
 - Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

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

from collections import defaultdict

from qt import QString
from kde import KConfigSkeleton
from log import logException, logDebug
from common import Internal, Debug


class Parameter(object):

    """helper class for defining configuration parameters"""

    def __init__(self, group, name, default=None):
        """configuration group, parameter name, default value"""
        self.group = group
        self.name = name
        self.default = default
        self.item = None

    def itemValue(self):
        """returns the value of this item"""
        return self.item.value()


class StringParameter(Parameter):

    """helper class for defining string parameters"""

    def __init__(self, group, name, default=None):
        if default is None:
            default = ''
        Parameter.__init__(self, group, name, default)
        self.value = QString()

    def add(self, skeleton):
        """add tis parameter to the skeleton"""
        self.item = skeleton.addItemString(
            self.name, self.value, QString(self.default or ''))

    def itemValue(self):
        """returns the value of this item"""
        return str(self.item.value())


class BoolParameter(Parameter):

    """helper class for defining boolean parameters"""

    def __init__(self, group, name, default=None):
        if default is None:
            default = False
        Parameter.__init__(self, group, name, default)
        self.value = default

    def add(self, skeleton):
        """add tis parameter to the skeleton"""
        self.item = skeleton.addItemBool(self.name, self.value, self.default)


class IntParameter(Parameter):

    """helper class for defining integer parameters"""

    def __init__(self, group, name, default=None,
                 minValue=None, maxValue=None):
        """minValue and maxValue are also used by the edit widget"""
        if default is None:
            default = 0
        Parameter.__init__(self, group, name, default)
        self.value = default
        self.minValue = minValue
        self.maxValue = maxValue

    def add(self, skeleton):
        """add this parameter to the skeleton"""
        self.item = skeleton.addItemInt(self.name, self.value, self.default)
        if self.minValue is not None:
            self.item.setMinValue(self.minValue)
        if self.maxValue is not None:
            self.item.setMaxValue(self.maxValue)


class SetupPreferences(KConfigSkeleton):

    """Holds all Kajongg options. Only instantiate this once"""
    _Parameters = {}

    def __init__(self):  # pylint: disable=super-init-not-called
        if Internal.Preferences:
            logException('Preferences is not None')
        self.__watching = defaultdict(list)
        Internal.Preferences = self
        KConfigSkeleton.__init__(self)
        self.configChanged.connect(self.callTriggers)
        self.__oldValues = defaultdict(str)
        self.addString('General', 'tilesetName', 'default')
        self.addString('General', 'windTilesetName', 'traditional')
        self.addString('General', 'backgroundName', 'wood_light')
        self.addBool('Display', 'showShadows', True)
        self.addBool('Display', 'rearrangeMelds', False)
        self.addBool('Display', 'showOnlyPossibleActions', True)
        self.addBool('Display', 'propose', True)
        self.addInteger('Display', 'animationSpeed', 70, 0, 99)
        self.addBool('Display', 'useSounds', True)
        self.addBool('Display', 'uploadVoice', False)

    def callTrigger(self, name):
        """call registered callback for this attribute change"""
        newValue = getattr(self, name)
        if self.__oldValues[name] != newValue:
            if Debug.preferences:
                logDebug(u'{}: {} -> {} calling {}'.format(
                    name,
                    self.__oldValues[name],
                    newValue,
                    ','.join(x.__name__ for x in self.__watching[name])))
            for method in self.__watching[name]:
                method(self.__oldValues[name], newValue)
        self.__oldValues[name] = newValue

    def callTriggers(self):
        """call registered callbacks for specific attribute changes"""
        for name in self.__watching:
            self.callTrigger(name)

    def addWatch(self, name, method):
        """If name changes, call method.
        method must accept 2 arguments: old value and new value."""
        if method not in self.__watching[name]:
            self.__watching[name].append(method)
            if Debug.preferences:
                logDebug('addWatch on {}, hook {}'.format(
                    name, method.__name__))
            self.callTrigger(name)  # initial change

    def __getattr__(self, name):
        """undefined attributes might be parameters"""
        if name not in SetupPreferences._Parameters:
            return self.__getattribute__(name)
        par = SetupPreferences._Parameters[name]
        return par.itemValue()

    def __setattr__(self, name, value):
        """undefined attributes might be parameters"""
        if name not in SetupPreferences._Parameters:
            KConfigSkeleton.__setattr__(self, name, value)
            return
        par = SetupPreferences._Parameters[name]
        par.item.setValue(value)

    def __getitem__(self, key):
        return self.__getattr__(key)

    def __setitem__(self, key, value):
        self.__setattr__(key, value)

    def __delitem__(self, key):
        """pylint wants this for a complete container, but we do not need it"""
        del SetupPreferences._Parameters[key]

    def __len__(self):
        """pylint wants this for a complete container, but we do not need it"""
        return len(SetupPreferences._Parameters)

    def addParameter(self, par):
        """add a parameter to the skeleton"""
        if par.name not in SetupPreferences._Parameters:
            SetupPreferences._Parameters[par.name] = par
            self.setCurrentGroup(par.group)
            par.add(self)

    def addString(self, group, name, default=None):
        """add a string parameter to the skeleton"""
        self.addParameter(StringParameter(group, name, default))

    def addBool(self, group, name, default=None):
        """add a string parameter to the skeleton"""
        self.addParameter(BoolParameter(group, name, default))

    def addInteger(self, group, name, default=None,
                   minValue=None, maxValue=None):
        """add a string parameter to the skeleton"""
        self.addParameter(IntParameter(
            group, name, default, minValue, maxValue))

    def animationDuration(self):
        """in milliseconds"""
        return (99 - self.animationSpeed) * 100 // 4
