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

import weakref
from random import Random, BPF, _MethodType, _BuiltinMethodType

from util import stack
from common import Debug


class CountingRandom(Random):

    """counts how often random() is called and prints debug info"""

    # pylint: disable=invalid-name

    def __init__(self, game, value=None):
        self._game = weakref.ref(game)
        Random.__init__(self, value)
        self.count = 0

    @property
    def game(self):
        """hide the fact that game is a weakref"""
        return self._game()

    def random(self):
        """the central randomizator"""
        self.count += 1
        return Random.random(self)

    def seed(self, newSeed=None, version=2):
        self.count = 0
        Random.seed(self, newSeed, version)
        if Debug.random:
            self.game.debug('Random gets seed %s' % newSeed)

    # pylint: disable=redefined-builtin
    def _randbelow(self, n, int=int, maxsize=1<<BPF, type=type,
                   Method=_MethodType, BuiltinMethod=_BuiltinMethodType):
        "Return a random int in the range [0,n).  Raises ValueError if n==0."

        getrandbits = self.getrandbits
        k = n.bit_length()  # don't use (n-1) here because n can be 1
        r = getrandbits(k)          # 0 <= r < 2**k
        while r >= n:
            r = getrandbits(k)
        return r

    def randrange(self, start, stop=None, step=1, _int=int):
        oldCount = self.count
        result = Random.randrange(self, start, stop, step)
        if Debug.random:
            self.game.debug(
                '%d out of %d calls to random by '
                'Random.randrange(%d,%s) from %s'
                % (self.count - oldCount, self.count, start, stop,
                   stack('')[-2]))
        return result

    def choice(self, fromList):
        """Choose a random element from a non-empty sequence."""
        oldCount = self.count
        result = Random.choice(self, fromList)
        if Debug.random:
            self.game.debug(
                '%d out of %d calls to random by '
                'Random.choice(%s) from %s' % (
                    self.count - oldCount, self.count,
                    str([str(x) for x in fromList]),
                    stack('')[-2]))
        return result

    def sample(self, population, wantedLength):
        """add debug output to sample"""
        oldCount = self.count
        result = Random.sample(self, population, wantedLength)
        if Debug.random:
            self.game.debug(
                '%d out of %d calls to random by '
                'Random.sample(x, %d) from %s' %
                (self.count - oldCount, self.count, wantedLength,
                 stack('')[-2]))
        return result

    def shuffle(self, listValue, func=None):
        """add debug output to shuffle"""
        oldCount = self.count
        Random.shuffle(self, listValue, func)
        if Debug.random:
            self.game.debug(
                '%d out of %d calls to random by Random.shuffle from %s'
                % (self.count - oldCount, self.count, stack('')[-2]))
