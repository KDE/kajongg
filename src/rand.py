# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

import weakref
from random import Random
from typing import Type, Any, TYPE_CHECKING, Optional, Sequence
from typing import Iterable, Protocol, TypeVar
from typing import MutableSequence

from util import callers
from common import Debug

if TYPE_CHECKING:
    from game import Game

_T_co = TypeVar("_T_co", covariant=True)
_T = TypeVar("_T")

class SupportsLenAndGetItem(Protocol[_T_co]):
    """just for type checking"""
    def __len__(self) -> int: ...
    def __getitem__(self, __k: int) -> _T_co: ...


class CountRandomCalls:

    """a helper class for logging count of random calls"""

    def __init__(self, rnd:'CountingRandom', what:str) ->None:
        self.rnd = rnd
        self.what = what
        self.oldCount = CountingRandom.count

    def __enter__(self) ->'CountRandomCalls':
        return self

    def __exit__(self, exc_type:Type[Exception], exc_value:Exception, trback:str) ->None:
        if Debug.random:
            if self.rnd.game:
                self.rnd.game.debug(
                    f'{CountingRandom.count - self.oldCount} out of '
                    f'{CountingRandom.count} calls to random by {self.what} from {callers()}')


class CountingRandom(Random):

    """counts how often random() is called and prints debug info"""

    count = 0

    def __init__(self, game:'Game', value:Any=None) ->None:
        self._game = weakref.ref(game)
        Random.__init__(self, value)
        CountingRandom.count = 0

    @property
    def game(self) ->Optional['Game']:
        """hide the fact that game is a weakref"""
        return self._game()

    def random(self) ->float:
        """the central randomizator"""
        CountingRandom.count += 1
        return Random.random(self)

    def seed(self, a:Any=None, version:int=2) ->None:
        CountingRandom.count = 0
        Random.seed(self, a, version)
        if Debug.random:
            if self.game:
                self.game.debug(f'Random gets seed {a}')

    def randrange(self, start:int, stop:Optional[int]=None, step:int=1) ->int:
        with CountRandomCalls(self, f'randrange({start},{stop},step={step})'):
            return Random.randrange(self, start, stop, step)

    def choice(self, seq:SupportsLenAndGetItem[_T]) ->_T:
        """Choose a random element from a non-empty sequence."""
        if len(seq) == 1:
            return seq[0]
        with CountRandomCalls(self, f'choice({seq})'):
            return Random.choice(self, seq)

    def sample(self, population:Sequence[_T],
        k:int, *, counts:Optional[Iterable[int]]=None) ->list[_T]:
        """add debug output to sample. Chooses k unique random elements"""
        with CountRandomCalls(self, f'sample({population}, {k})'):
            return Random.sample(self, population, k, counts=counts)

    def shuffle(self, x:MutableSequence[Any], random:Optional[Any]=None) ->None:
        """add debug output to shuffle. Shuffles list x in place."""
        with CountRandomCalls(self, f'shuffle({x})'):
            try:
                # Python 3.10 or earlier
                # pylint:disable=deprecated-argument,too-many-function-args
                Random.shuffle(self, x, random)  # type:ignore[call-arg]
            except TypeError:
                # Python 3.11 or later
                # pylint:disable=deprecated-argument
                Random.shuffle(self, x)
