# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

import weakref
from random import Random

from util import callers
from common import Debug

class CountRandomCalls:

    """a helper class for logging count of random calls"""

    def __init__(self, rnd, what):
        self.rnd = rnd
        self.what = what
        self.oldCount = CountingRandom.count

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trback):
        if Debug.random:
            if self.rnd.game:
                self.rnd.game.debug(
                    '{} out of {} calls to random by {} from {}'.format(
                        CountingRandom.count - self.oldCount,
                        CountingRandom.count,
                        self.what,
                        callers()))


class CountingRandom(Random):

    """counts how often random() is called and prints debug info"""

    count = 0

    def __init__(self, game, value=None):
        self._game = weakref.ref(game)
        Random.__init__(self, value)
        CountingRandom.count = 0

    @property
    def game(self):
        """hide the fact that game is a weakref"""
        return self._game()

    def random(self):
        """the central randomizator"""
        CountingRandom.count += 1
        return Random.random(self)

    def seed(self, a=None, version=2):
        CountingRandom.count = 0
        Random.seed(self, a, version)
        if Debug.random:
            if self.game:
                self.game.debug('Random gets seed %s' % a)

    def randrange(self, start, stop=None, step=1):
        with CountRandomCalls(self, 'randrange({},{},step={})'.format(
            start, stop, step)):
            return Random.randrange(self, start, stop, step)

    def choice(self, seq):
        """Choose a random element from a non-empty sequence."""
        if len(seq) == 1:
            return seq[0]
        with CountRandomCalls(self, 'choice({})'.format(seq)):
            return Random.choice(self, seq)

    def sample(self, population, k, *, counts=None):
        """add debug output to sample. Chooses k unique random elements"""
        with CountRandomCalls(self, 'sample({}, {})'.format(population, k)):
            return Random.sample(self, population, k, counts=counts)

    def shuffle(self, x, random=None):
        """add debug output to shuffle. Shuffles list x in place."""
        with CountRandomCalls(self, 'shuffle({})'.format(x)):
            try:
                # Python 3.10 or earlier
                # pylint:disable=deprecated-argument,too-many-function-args
                Random.shuffle(self, x, random)
            except TypeError:
                # Python 3.11 or later
                # pylint:disable=deprecated-argument
                Random.shuffle(self, x)
