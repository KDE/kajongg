# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

from functools import total_ordering
import sys

from typing import Optional, Union, Tuple, TYPE_CHECKING

from common import ReprMixin
from wind import Wind, East
from query import Query
from log import logError

if TYPE_CHECKING:
    from game import Game


@total_ordering
class Point(ReprMixin):

    """A point in time of a game. Useful for positioning after abort/restart

        Point does not care about wind or players or about any rules.

        seed: the seed for the random generator, shown in window title
        prevailing: the prevailing wind of the current round
        rotated: how often we rotated within current round
        notRotated: how often we did NOT rotate since last rotation
        moveCount: Number of executed moves within current hand
    """

    def __init__(self, source:Union[str, int, 'Point']) -> None:
        """Default values point to start of game"""
        self.seed = 0
        self.prevailing:Wind = East
        self.rotated = 0
        self.notRotated = 0
        self.moveCount = 0   # within current hand
        self.handCount = 0   # unique ID over all hands of a game for data base

        if isinstance(source, str):
            self.__init_from_string(source)
        elif isinstance(source, int):
            self.__init_from_db(source)
        elif isinstance(source, Point):
            self.__init_from_point(source)
        else:
            raise ValueError(f'Point() does not accept source {source}')

    def __init_from_string(self, string:str) ->None:
        """Init myself from string

            String format: SEED/Wrnm
            where only trailing parameters can be omitted.

            SEED: 1..n digits: the seed
            W: 1 char:         prevailing wind
            r: 0..1 digit:     rotations within current round
            n: 0..n chars:     how often we currently did not rotate. Encoded in letters a..z
            m: 0..n digits:    Number of current move within current hand
        """

        self.seed = int(string.split('/')[0])
        normalized = string
        if normalized.endswith('/'):
            normalized = normalized[:-1]
        if '/' in normalized:
            rest = normalized.split('/')[1]
            self.prevailing = Wind(rest[0])
            rest = rest[1:]
            if rest:
                self.rotated = int(rest[0])
                rest = rest[1:]
                self.notRotated, rest = self.decode_from_az(rest)
                if rest:
                    self.moveCount = int(rest)

    def __init_from_point(self, other:'Point') ->None:
        """Init myself from a Game instance"""
        self.seed = other.seed
        self.prevailing = other.prevailing
        self.rotated = other.rotated
        self.notRotated = other.notRotated
        self.moveCount = other.moveCount
        self.handCount = other.handCount

    def __init_from_db(self, gameid:int) ->None:
        """last recorded position"""
        self.handCount, self.rotated, self.notRotated, self.prevailing = Query(
            'select {fields} from score where game=? order by hand desc limit 1', (gameid, ),
            fields='hand, rotated, notrotated, prevailing').tuple()

    def is_in_first_hand(self) ->bool:
        """True only if this point is in the first hand of a game"""
        return self.handCount == 0

    def endHand(self) ->None:
        """hand is done"""
        self.handCount += 1
        self.notRotated += 1  # if we rotate, we will call Point.rotate()

    def rotate(self) ->None:
        """rotate winds"""
        self.notRotated = 0
        self.rotated += 1
        if self.rotated == 4:
            self.prevailing = next(self.prevailing)
            self.rotated = 0

    def prompt(self, game:'Game', withSeed:bool=True, withAI:bool=True, withMoveCount:bool=False) ->str:
        """
        Identifies the hand for window title and scoring table.

        @param withSeed: If set, include the seed used for the
        random generator.
        @type  withSeed: C{Boolean}
        @param withAI:   If set and AI != DefaultAI: include AI name for
        human players.
        @type  withAI:   C{Boolean}
        @param withMoveCount:   If set, include the current count of moves.
        @type  withMoveCount:   C{Boolean}
        @return:         The prompt.
        @rtype:          C{str}
        """
        aiVariant = ''
        if withAI and game and game.belongsToHumanPlayer():
            if game.myself:
                aiName = game.myself.intelligence.name()
            else:
                aiName = 'DefaultAI'
            if aiName != 'DefaultAI':
                aiVariant = aiName + '/'
        if withSeed:
            seedStr = str(self.seed)
        else:
            seedStr = ''
        delim = '/' if withSeed or withAI else ''
        _ = self.notRotated_as_str() or ' '
        result = f'{aiVariant}{seedStr}{delim}{self.prevailing}{self.rotated + 1}{_}'
        if withMoveCount:
            result += f'/{int(self.moveCount):3}'
        return result

    @property
    def roundsFinished(self) -> int:
        """wind index"""
        return self.prevailing.__index__()

    def seedFactor(self) -> int:
        """we want a predictable but different seed for every starting point"""
        return ((self.roundsFinished + 1) * 10000
               + self.rotated * 1000
               + self.notRotated * 100)

    def encode_to_az(self, value:int) ->str:
        """encode an integer into string"""
        result = ''
        num = value
        while num:
            result = chr(ord('a') + (num - 1) % 26) + result
            num = (num - 1) // 26
        return result

    def decode_from_az(self, value:str) ->Tuple[int, str]:
        """decode and return rest"""
        rest = value[:]
        result = 0
        while rest and rest[0] >= 'a' and rest[0] <= 'z':
            result = result * 26 + ord(rest[0]) - ord('a') + 1
            rest = rest[1:]
        return result, rest

    def notRotated_as_str(self) ->str:
        """encode into a..z"""
        return self.encode_to_az(self.notRotated)

    def token(self, game:'Game') ->str:
        """server and client use this for checking whether they talk about
        the same thing"""
        return self.prompt(game, withAI=False)

    def __str__(self) ->str:
        return f'{self.prevailing}{self.rotated}{self.notRotated_as_str()}'

    def __eq__(self, other:object) ->bool:
        if other is None:
            return False
        if not isinstance(other, Point):
            return NotImplemented
        return (self.prevailing, self.rotated, self.notRotated) == \
                (other.prevailing, other.rotated, other.notRotated)

    def __ne__(self, other:object) ->bool:
        return not self == other

    def __gt__(self, other:object) ->bool:
        if other is None:
            # open end
            return False
        if not isinstance(other, Point):
            return NotImplemented
        return (self.prevailing, self.rotated, self.notRotated) > (
            other.prevailing, other.rotated, other.notRotated)

    def __lt__(self, other:object) ->bool:
        if other is None:
            # open end
            return True
        if not isinstance(other, Point):
            return NotImplemented
        return (self.prevailing, self.rotated, self.notRotated) < (
            other.prevailing, other.rotated, other.notRotated)

class PointRange(ReprMixin):

    """Represents a range of points: Point..Point
        start and end are included.
        If end is None: open end
    """

    def __init__(self, game:'Game',
            first_point:Optional[Point]=None,
            last_point:Optional[Point]=None) ->None:

        self.first_point: Point
        self.last_point: Union[Point, None]  # None means open end

        if first_point is None and last_point is None:
            self.first_point = game.first_point
            self.last_point = game.last_point
        else:
            assert first_point
            self.first_point = first_point
            self.last_point = last_point

        if self.first_point > self.last_point:
            raise UserWarning(f'{first_point}..{last_point} is a negative range')

    @classmethod
    def from_string(cls, string:str) -> Tuple[Point, Union[Point, None]]:
        """parse a string like first..last"""
        if string is None:
            string = ''

        full_str = string
        if '/' not in full_str:
            full_str += '/'
        seed_str, pos_str = full_str.split('/')
        try:
            seed = int(seed_str)
        except ValueError:
            logError(f'Cannot parse seed from {full_str}, I need something like 15/E0..W4', showStack=False)
            sys.exit(1)

        positions = pos_str.split('..')
        first_pos = Point(f'{seed}/{positions[0]}')

        last_pos:Optional[Point] = None   # default
        if len(positions) > 1:
            last_pos = Point(f'{seed}/{positions[1]}')

        if first_pos > last_pos:
            logError(f'start is after end:{full_str}', showStack=False)
            sys.exit(1)
        return first_pos, last_pos

    @property
    def seed(self) ->int:
        """from first_pos"""
        return self.first_point.seed

    def __str__(self) ->str:
        """used in traffic"""
        result = f'{self.first_point.seed}/{self.first_point}'
        if self.last_point:
            result += f'..{self.last_point}'
        return result
