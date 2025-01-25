# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

partially based on C++ code from:
 - Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

SPDX-License-Identifier: GPL-2.0-only

"""

from collections import defaultdict
from typing import Dict, Optional, Union, TYPE_CHECKING, Callable, Any, cast

from kde import KConfigSkeleton
from log import logException, logDebug
from common import Internal, Debug

if TYPE_CHECKING:
    from kdestub import KConfigSkeletonItem, ItemInt


class Parameter:

    """helper class for defining configuration parameters"""

    def __init__(self, group:str, name:str, default:Union[int, str, bool]) ->None:
        """configuration group, parameter name, default value"""
        self.group = group
        self.name = name
        self.default = default
        self.item:'KConfigSkeletonItem'

    def add(self, skeleton:KConfigSkeleton) ->None:
        """for mypy"""
        raise NotImplementedError

    def itemValue(self) ->Union[int, str, bool]:
        """return the value of this item"""
        return self.item.value()


class StringParameter(Parameter):

    """helper class for defining string parameters"""

    def __init__(self, group:str, name:str, default:Optional[str]=None) ->None:
        if default is None:
            default = ''
        Parameter.__init__(self, group, name, default)
        self.value = ''

    def add(self, skeleton:KConfigSkeleton) ->None:
        """add tis parameter to the skeleton"""
        self.item = skeleton.addItem(self.name, self.value, self.default or '')

    def itemValue(self) ->str:
        """return the value of this item"""
        return str(self.item.value())


class BoolParameter(Parameter):

    """helper class for defining boolean parameters"""

    def __init__(self, group:str, name:str, default:Optional[bool]=None) ->None:
        if default is None:
            default = False
        Parameter.__init__(self, group, name, default)
        self.value = default

    def add(self, skeleton:KConfigSkeleton) ->None:
        """add tis parameter to the skeleton"""
        self.item = skeleton.addItem(self.name, self.value, self.default)


class IntParameter(Parameter):

    """helper class for defining integer parameters"""

    def __init__(self, group:str, name:str, default:Optional[int]=None,
                 minValue:Optional[int]=None, maxValue:Optional[int]=None) ->None:
        """minValue and maxValue are also used by the edit widget"""
        if default is None:
            default = 0
        Parameter.__init__(self, group, name, default)
        self.value = default
        self.minValue = minValue
        self.maxValue = maxValue

    def add(self, skeleton:KConfigSkeleton) ->None:
        """add this parameter to the skeleton"""
        self.item = skeleton.addItem(self.name, self.value, self.default)
        if self.minValue is not None:
            cast('ItemInt', self.item).setMinValue(self.minValue)
        if self.maxValue is not None:
            cast('ItemInt', self.item).setMaxValue(self.maxValue)


class SetupPreferences(KConfigSkeleton):

    """Holds all Kajongg options. Only instantiate this once"""
    _Parameters : Dict[str, Parameter] = {}

    def __init__(self) ->None:
        if Internal.Preferences:
            logException('Preferences is not None')
        self.__watching = defaultdict(list)  # type:ignore
        Internal.Preferences = self
        KConfigSkeleton.__init__(self)
        self.configChanged.connect(self.callTriggers)
        self.__oldValues  = defaultdict(str)  # type:ignore
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

    def callTrigger(self, name:str) ->None:
        """call registered callback for this attribute change"""
        newValue = getattr(self, name)
        if self.__oldValues[name] != newValue:
            if Debug.preferences:
                logDebug(f"{name}: {self.__oldValues[name]} -> "
                         f"{newValue} calling {','.join(x.__name__ for x in self.__watching[name])}")
            for method in self.__watching[name]:
                method(self.__oldValues[name], newValue)
        self.__oldValues[name] = newValue

    def callTriggers(self) ->None:
        """call registered callbacks for specific attribute changes"""
        for name in self.__watching:
            self.callTrigger(name)

    #def addWatch(self, name:str, method:Callable[List[Union[int, str, bool]], None]) ->None:
    def addWatch(self, name:str, method:Callable[..., None]) ->None:
        """If name changes, call method.
        method must accept 2 arguments: old value and new value."""
        if method not in self.__watching[name]:
            self.__watching[name].append(method)
            if Debug.preferences:
                logDebug(f'addWatch on {name}, hook {method.__name__}')
            self.callTrigger(name)  # initial change

    def __getattr__(self, name:str) ->Union[int, str, bool]:
        """undefined attributes might be parameters"""
        if name not in SetupPreferences._Parameters:
            return self.__getattribute__(name)
        par = SetupPreferences._Parameters[name]
        return par.itemValue()

    def __setattr__(self, name:str, value:Union[int, str, bool]) ->None:
        """undefined attributes might be parameters"""
        if name not in SetupPreferences._Parameters:
            KConfigSkeleton.__setattr__(self, name, value)
            return
        par = SetupPreferences._Parameters[name]
        par.item.setValue(value)

    def __getitem__(self, key:str):  # type:ignore
        return self.__getattr__(key)

    def __setitem__(self, key:str, value:Any) ->None:
        self.__setattr__(key, value)

    def __delitem__(self, key:str) ->None:
        """pylint wants this for a complete container, but we do not need it"""
        del SetupPreferences._Parameters[key]

    def __len__(self) ->int:
        """pylint wants this for a complete container, but we do not need it"""
        return len(SetupPreferences._Parameters)

    def addParameter(self, par:Parameter) ->None:
        """add a parameter to the skeleton"""
        if par.name not in SetupPreferences._Parameters:
            SetupPreferences._Parameters[par.name] = par
            self.setCurrentGroup(par.group)
            par.add(self)

    def addString(self, group:str, name:str, default:Optional[str]=None) ->None:
        """add a string parameter to the skeleton"""
        self.addParameter(StringParameter(group, name, default))

    def addBool(self, group:str, name:str, default:Optional[bool]=None) ->None:
        """add a string parameter to the skeleton"""
        self.addParameter(BoolParameter(group, name, default))

    def addInteger(self, group:str, name:str, default:Optional[int]=None,
                   minValue:Optional[int]=None, maxValue:Optional[int]=None) ->None:
        """add a string parameter to the skeleton"""
        self.addParameter(IntParameter(
            group, name, default, minValue, maxValue))

    def animationDuration(self) ->int:
        """in milliseconds"""
        return max(0, (99 - self.animationSpeed) * 100 // 4)  # type:ignore
