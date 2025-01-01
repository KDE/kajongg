# -*- coding: utf-8 -*-

"""
 Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

# pylint: disable=invalid-name

import sqlite3

from typing import Any, List, Optional, TYPE_CHECKING

from mi18n import i18nc

if TYPE_CHECKING:
    from tile import Tile
    from board import WindDisc



class Wind:
    """we want to use an wind for indices.

    char is the wind as a char (native string)
    svgName is the name of the wind in the SVG files.
    """

    char: str
    discSvgName: str
    all : List['Wind'] = []
    all4 : List['Wind'] = []

    tile : 'Tile'
    disc:'WindDisc'

    # X is used in scoring games for moving back a tile to the central court
    eswnx = 'ESWNX'
    eswnx_i18n = 'ESWNX'

    def __new__(cls, *args:Any) ->'Wind':
        if not Wind.all:
            Wind.all = [object.__new__(cls) for cls in (_East, _South, _West, _North, _NoWind)]
            Wind.all4 = list(Wind.all[:4])
            Wind.eswnx_i18n = i18nc('kajongg:keyboard commands for moving tiles to the players '
                             'with wind ESWN or to the central tile selector (X)', Wind.eswnx)
        if len(args) == 1:
            windIdent = args[0]
            assert cls is Wind, f'{cls.__name__}({windIdent}) is illegal'
            windIdx = 'eswn'.index(windIdent.lower())
            return Wind.all[windIdx]
        assert not args and cls is not Wind, 'Wind() must have exactly one argument'

        for result in Wind.all:
            if isinstance(result, cls):
                # return the correct Wind subclass like _East
                return result
        assert False

    def __eq__(self, other:Any) ->bool:
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

    def __gt__(self, other:Any) ->bool:
        assert isinstance(other, Wind)
        return self.__index__() > other.__index__()

    def __lt__(self, other:Any) ->bool:
        assert isinstance(other, Wind)
        return self.__index__() < other.__index__()

    def __ge__(self, other:Any) ->bool:
        assert isinstance(other, Wind)
        return self.__index__() >= other.__index__()

    def __le__(self, other:Any) ->bool:
        assert isinstance(other, Wind)
        return self.__index__() <= other.__index__()

    def __hash__(self) ->int:
        return self.__index__()

    def __index__(self) ->int:
        raise NotImplementedError

    def __str__(self) ->str:
        return self.char

    def __repr__(self) ->str:
        return f'Wind.{self.char}'

    def __next__(self) ->'Wind':
        """after North, return NoWind"""
        return Wind.all[self.__index__() +1]

    def __conform__(self, protocol) ->Optional[str]:
        if protocol is sqlite3.PrepareProtocol:
            return self.char
        return None

    @classmethod
    def normalized(cls, key:int) -> Optional['Wind']:
        """translate i18n key to wanted Wind. None if key is not a Wind character"""
        try:
            return Wind.all[cls.eswnx_i18n.index(chr(key))]
        except ValueError:
            return None

class _East(Wind):
    """East"""
    char = 'E'
    svgName = 'WIND_3'
    discSvgName = 'g4657'  # WIND_2 etc have a border

    def __index__(self) ->int:
        return 0


class _South(Wind):
    """South"""
    char = 'S'
    svgName = 'WIND_2'
    discSvgName = 'g3980'

    def __index__(self) ->int:
        return 1


class _West(Wind):
    """West"""
    char = 'W'
    svgName = 'WIND_4'
    discSvgName = 'g3192'

    def __index__(self) ->int:
        return 2


class _North(Wind):
    """North"""
    char = 'N'
    svgName = 'WIND_1'
    discSvgName = 'g4290'

    def __index__(self) ->int:
        return 3


class _NoWind(Wind):
    """no wind"""
    char = 'X'
    svgName = None

    def __index__(self) ->int:
        return 4


East = _East()
South = _South()
West = _West()
North = _North()
NoWind = _NoWind()

def convert_from_sql(raw:bytes) -> 'Wind':
    """see https://docs.python.org/3/library/sqlite3.html"""
    return Wind(raw.decode())


sqlite3.register_converter("wind", convert_from_sql)
