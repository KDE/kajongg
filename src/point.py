# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

from functools import total_ordering

from typing import Optional, TYPE_CHECKING

from log import logWarning, logException
from common import ReprMixin
from wind import Wind

if TYPE_CHECKING:
    from game import Game


@total_ordering
class Point(ReprMixin):

    """A point in time of a game. Useful for positioning after abort/restart"""

    def __init__(self, game:'Game', string:Optional[str]=None, stringIdx:int=0) ->None:
        self.game = game
        self.seed = game.seed
        self.roundsFinished = 0
        self.rotated = 0
        self.notRotated = 0
        self.moveCount = 0
        if string is None:
            self.roundsFinished = game.roundsFinished
            self.rotated = game.rotated
            self.notRotated = game.notRotated
            self.moveCount = len(game.moves)
        else:
            self.__scanPoint(string, stringIdx)
        assert self.rotated < 5, self

    def __scanPoint(self, string:str, stringIdx:int) ->None:
        """get the --game option.
        stringIdx 0 is the part in front of ..
        stringIdx 1 is the part after ..
        """
        # pylint: disable=too-many-return-statements,too-many-branches
        if not string:
            return
        seed = int(string.split('/')[0])
        assert self.seed is None or self.seed == seed, string
        self.seed = seed
        if '/' not in string:
            if stringIdx == 1:
                self.roundsFinished = 4
            return
        string1 = string.split('/')[1]
        if not string1:
            logException(f'--game={string} must specify the wanted round')
        parts = string1.split('..')
        if len(parts) == 2:
            if stringIdx == 0 and parts[0] == '':
                return
            if stringIdx == 1 and parts[1] == '':
                self.roundsFinished = 4
                return
        point = parts[min(stringIdx, len(parts) - 1)]
        if point[0].lower() not in 'eswn':
            logException(f'--game={string} must specify the round wind')
        handWind = Wind(point[0])
        ruleset = self.game.ruleset
        self.roundsFinished = handWind.__index__()
        minRounds = ruleset.minRounds  # type:ignore[attr-defined]
        if self.roundsFinished > minRounds:
            logWarning(
                f'Ruleset {ruleset.name} has {int(minRounds)} minimum rounds '
                f'but you want round {int(self.roundsFinished + 1)}({handWind})')
            self.roundsFinished = minRounds
            return
        self.rotated = int(point[1]) - 1
        if self.rotated > 3:
            logWarning(
                f'You want {int(self.rotated)} rotations, reducing to maximum of 3')
            self.rotated = 3
            return
        for char in point[2:]:
            if char < 'a':
                logWarning(f'you want {char}, changed to a')
                char = 'a'
            if char > 'z':
                logWarning(f'you want {char}, changed to z')
                char = 'z'
            self.notRotated = self.notRotated * 26 + ord(char) - ord('a') + 1
        return

    def prompt(self, withSeed:bool=True, withAI:bool=True, withMoveCount:bool=False) ->str:
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
        if withAI and self.game.belongsToHumanPlayer():
            if self.game.myself:
                aiName = self.game.myself.intelligence.name()
            else:
                aiName = 'DefaultAI'
            if aiName != 'DefaultAI':
                aiVariant = aiName + '/'
        num = self.notRotated
        assert isinstance(num, int), num
        charId = ''
        while num:
            charId = chr(ord('a') + (num - 1) % 26) + charId
            num = (num - 1) // 26
        if not charId:
            charId = ' ' # align to the most common case
        wind = Wind.all4[self.roundsFinished % 4]
        if withSeed:
            seedStr = str(self.seed)
        else:
            seedStr = ''
        delim = '/' if withSeed or withAI else ''
        result = f'{aiVariant}{seedStr}{delim}{wind}{self.rotated + 1}{charId}'
        if withMoveCount:
            result += f'/{int(self.moveCount):3}'
        return result

    def token(self) ->str:
        """server and client use this for checking if they talk about
        the same thing"""
        return self.prompt(withAI=False)

    def __str__(self) ->str:
        return self.prompt()

    def __eq__(self, other:object) ->bool:
        if not isinstance(other, Point):
            return NotImplemented
        return (self.roundsFinished, self.rotated, self.notRotated) == \
                (other.roundsFinished, other.rotated, other.notRotated)

    def __ne__(self, other:object) ->bool:
        return not self == other

    def __lt__(self, other:object) ->bool:
        if not isinstance(other, Point):
            return NotImplemented
        return (self.roundsFinished, self.rotated, self.notRotated) < (
            other.roundsFinished, other.rotated, other.notRotated)
