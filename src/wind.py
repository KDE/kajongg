# -*- coding: utf-8 -*-

"""
 Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

# pylint: disable=invalid-name


class Wind:
    """we want to use an wind for indices.

    char is the wind as a char (native string)
    svgName is the name of the wind in the SVG files.
    """
    all = []
    all4 = []

    def __new__(cls, *args):
        if not Wind.all:
            Wind.all = [object.__new__(cls) for cls in (_East, _South, _West, _North, _NoWind)]
            Wind.all4 = list(Wind.all[:4])
        if len(args) == 1:
            windIdent = args[0]
            assert cls is Wind, '{}({}) is illegal'.format(cls.__name__, windIdent)
            windIdx = 'eswn'.index(windIdent.lower())
            return Wind.all[windIdx]
        assert not args and cls is not Wind, 'Wind() must have exactly one argument'

        for result in Wind.all:
            if isinstance(result, cls):
                # return the correct Wind subclass like _East
                return result
        assert False

    def __eq__(self, other):
        if not other:
            return False
        if isinstance(other, self.__class__):
            return True
        if isinstance(other, Wind):
            return False
        try:
            return str(self.char) == other.upper()
        except AttributeError:
            return False

    def __gt__(self, other):
        assert isinstance(other, Wind)
        return self.__index__() > other.__index__()

    def __lt__(self, other):
        assert isinstance(other, Wind)
        return self.__index__() < other.__index__()

    def __ge__(self, other):
        assert isinstance(other, Wind)
        return self.__index__() >= other.__index__()

    def __le__(self, other):
        assert isinstance(other, Wind)
        return self.__index__() <= other.__index__()

    def __hash__(self):
        return self.__index__()

    def __str__(self):
        return self.char

    def __repr__(self):
        return 'Wind.{}'.format(self.char)


class _East(Wind):
    """East"""
    char = 'E'
    svgName = 'WIND_3'
    discSvgName = 'g4657'  # WIND_2 etc have a border

    def __index__(self):
        return 0


class _South(Wind):
    """South"""
    char = 'S'
    svgName = 'WIND_2'
    discSvgName = 'g3980'

    def __index__(self):
        return 1


class _West(Wind):
    """West"""
    char = 'W'
    svgName = 'WIND_4'
    discSvgName = 'g3192'

    def __index__(self):
        return 2


class _North(Wind):
    """North"""
    char = 'N'
    svgName = 'WIND_1'
    discSvgName = 'g4290'

    def __index__(self):
        return 3


class _NoWind(Wind):
    """no wind"""
    char = 'X'
    svgName = None

    def __index__(self):
        return 4


East = _East()
South = _South()
West = _West()
North = _North()
