# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2014 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
from math import ceil as _ceil
from math import log as _log

from util import stack
from common import Debug
from common import isPython3, xrange


class CountingRandom(Random):

    """counts how often random() is called and prints debug info"""

    # pylint: disable=redefined-builtin, invalid-name

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

    def __seed(self, newSeed):
        """common for PY2 and PY3"""
        self.count = 0
        if Debug.random:
            self.game.debug('Random gets seed %s' % newSeed)

    def __randrange(self, start, stop=None, step=1, _int=int):
        """This is taken and simplified from 2.7 because 3.2 changed,
        resulting in different values for randint.

        Choose a random item from range(start, stop[, step]).
        """

        if step != 1:
            raise ValueError('kajongg randrange does not support step')

        istart = _int(start)
        if istart != start:
            raise ValueError("non-integer arg 1 for randrange()")
        if stop is None:
            if istart > 0:
                return self._randbelow(istart)
            raise ValueError("empty range for randrange()")

        # stop argument supplied.
        istop = _int(stop)
        if istop != stop:
            raise ValueError("non-integer stop for randrange()")
        while True:
            result = int(self.random() * (istop+1))
            if istart <= result <= istop:
                return result

    if isPython3:
        def seed(self, newSeed=None, version=1): # pylint: disable=arguments-differ
            self.__seed(newSeed)
            Random.seed(self, newSeed, version)
    else:
        def seed(self, newSeed=None): # pylint: disable=arguments-differ
            self.__seed(newSeed)
            Random.seed(self, newSeed)

    def _randbelow(self, n, int=int, maxsize=1<<BPF, type=type,
                   Method=_MethodType, BuiltinMethod=_BuiltinMethodType):
        "Return a random int in the range [0,n).  Raises ValueError if n==0."

        getrandbits = self.getrandbits
        k = n.bit_length()  # don't use (n-1) here because n can be 1
        r = getrandbits(k)          # 0 <= r < 2**k
        while r >= n:
            r = getrandbits(k)
        return r

    def randrange(self, start, stop=None, step=1):
        # pylint: disable=arguments-differ
        oldCount = self.count
        result = self.__randrange(start, stop, step)
        if Debug.random:
            self.game.debug(
                '%d out of %d calls to random by '
                'Random.randrange(%d,%s) from %s'
                % (self.count - oldCount, self.count, start, stop,
                   stack('')[-2]))
        return result

    def choice(self, fromList):
        """Choose a random element from a non-empty sequence."""
        if len(fromList) == 1:
            return fromList[0]
        oldCount = self.count
        idx = self.randrange(0, len(fromList)-1)
        result = fromList[idx]
        if Debug.random:
            self.game.debug(
                '%d out of %d calls to random by '
                'Random.choice(%s) from %s' % (
                    self.count - oldCount, self.count,
                    str([str(x) for x in fromList]),
                    stack('')[-2]))
        return result

    def sample(self, population, wantedLength):
        oldCount = self.count
        result = self.__sample(population, wantedLength)
        if Debug.random:
            self.game.debug(
                '%d out of %d calls to random by '
                'Random.sample(x, %d) from %s' %
                (self.count - oldCount, self.count, wantedLength,
                 stack('')[-2]))
        return result


    def shuffle(self, listValue, func=None):
        """pylint needed for python up to 2.7.5"""
        # pylint: disable=arguments-differ
        oldCount = self.count
        self.__shuffle(listValue, func)
        if Debug.random:
            self.game.debug(
                '%d out of %d calls to random by Random.shuffle from %s'
                % (self.count - oldCount, self.count, stack('')[-2]))


    def __shuffle(self, x, random=None):
        """x, random=random.random -> shuffle list x in place; return None.

        Optional arg random is a 0-argument function returning a random
        float in [0.0, 1.0); by default, the standard random.random.

        taken from python2.7 because 3.5 does something different with
        different results
        """

        if random is None:
            random = self.random
        _int = int
        for i in reversed(xrange(1, len(x))):
            # pick an element in x[:i+1] with which to exchange x[i]
            j = _int(random() * (i+1))
            x[i], x[j] = x[j], x[i]

    def __sample(self, population, k):
        """Chooses k unique random elements from a population sequence.

        Returns a new list containing elements from the population while
        leaving the original population unchanged.  The resulting list is
        in selection order so that all sub-slices will also be valid random
        samples.  This allows raffle winners (the sample) to be partitioned
        into grand prize and second place winners (the subslices).

        Members of the population need not be hashable or unique.  If the
        population contains repeats, then each occurrence is a possible
        selection in the sample.

        To choose a sample in a range of integers, use xrange as an argument.
        This is especially fast and space efficient for sampling from a
        large population:   sample(xrange(10000000), 60)

        taken from python2.7 because 3.5 does something different with
        different results
        """

        # Sampling without replacement entails tracking either potential
        # selections (the pool) in a list or previous selections in a set.

        # When the number of selections is small compared to the
        # population, then tracking selections is efficient, requiring
        # only a small set and an occasional reselection.  For
        # a larger number of selections, the pool tracking method is
        # preferred since the list takes less space than the
        # set and it doesn't suffer from frequent reselections.

        n = len(population)
        if not 0 <= k <= n:
            raise ValueError("sample larger than population")
        random = self.random
        _int = int
        result = [None] * k
        setsize = 21        # size of a small set minus size of an empty list
        if k > 5:
            setsize += 4 ** _ceil(_log(k * 3, 4)) # table size for big sets
        if n <= setsize or hasattr(population, "keys"):
            # An n-length list is smaller than a k-length set, or this is a
            # mapping type so the other algorithm wouldn't work.
            pool = list(population)
            for i in xrange(k):         # invariant:  non-selected at [0,n-i)
                j = _int(random() * (n-i))
                result[i] = pool[j]
                pool[j] = pool[n-i-1]   # move non-selected item into vacancy
        else:
            try:
                selected = set()
                selected_add = selected.add
                for i in xrange(k):
                    j = _int(random() * n)
                    while j in selected:
                        j = _int(random() * n)
                    selected_add(j)
                    result[i] = population[j]
            except (TypeError, KeyError):   # handle (at least) sets
                if isinstance(population, list):
                    raise
                return self.sample(tuple(population), k)
        return result

