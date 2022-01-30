# -*- coding: utf-8 -*-

"""Copyright (C) 2013-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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



Read the user manual for a description of the interface to this scoring engine
"""

import itertools

from tile import Tile
from meld import Meld, MeldList


class Permutations:

    """creates permutations for building melds out of single tiles.
    NEVER returns Kongs!"""
    cache = {}
    permuteCache = {}

    def __new__(cls, tiles):
        cacheKey = tuple(x.key for x in tiles)
        if cacheKey in cls.cache:
            return cls.cache[cacheKey]
        else:
            result = object.__new__(cls)
            cls.cache[cacheKey] = result
            return result

    def __init__(self, tiles):
        self.tiles = tiles
        if not hasattr(self, 'variants'):
            self.variants = self._variants()

    def _variants(self):
        """full Meld lists"""
        honors = []
        for tile in sorted(set(self.tiles)):
            if tile.isHonor:
                count = self.tiles.count(tile)
                if count == 4:
                    honors.append(tile.single)
                    count -= 1
                honors.append(tile.meld(count))
        boni = list(x.single for x in self.tiles if x.isBonus)
        variants = []
        for group in Tile.colors.upper():
            gTiles = list(x for x in self.tiles if x.group == group)
            groupVariants = self.__colorVariants(
                group, list(x.value for x in gTiles))
            if groupVariants:
                variants.append(groupVariants)
        result = []
        for variant in (sum(x, []) for x in itertools.product(*variants)):
            if variant not in result:
                result.append(variant)
        result = sorted(MeldList(honors + x + boni) for x in result)
        return result

    @classmethod
    def permute(cls, valuesTuple):
        """returns all groupings into melds.
        values is a tuple of int, range 1..9"""
        assert isinstance(valuesTuple, tuple)
        if valuesTuple in cls.permuteCache:
            return cls.permuteCache[valuesTuple]
        values = list(valuesTuple)
        result = list()
        possibleMelds = []
        valueSet = set(values)
        for value in sorted(valueSet):
            if values.count(value) == 2:
                possibleMelds.append(tuple([value] * 2))
            if values.count(value) >= 3:
                possibleMelds.append(tuple([value] * 3))
            if values.count(value + 1) and values.count(value + 2):
                possibleMelds.append(tuple([value, value + 1, value + 2]))
        if possibleMelds:
            for meld in possibleMelds:
                appendValue = list([meld])
                rest = values[:]
                for tile in meld:
                    rest.remove(tile)
                if rest:
                    permuteRest = cls.permute(tuple(rest))
                    for combi in permuteRest:
                        result.append(tuple(list(appendValue) + list(combi)))
                else:
                    result.append(appendValue)
        else:
            result = list([list([tuple([x]) for x in values])])
        tupleResult = tuple(sorted(set(tuple(tuple(sorted(x)) for x in result))))
        cls.permuteCache[valuesTuple] = tupleResult
        return tupleResult

    colorPermCache = {}

    @classmethod
    def usefulPermutations(cls, values):
        """return all variants usable for standard MJ formt (4 melds plus 1 pair),
        and also the variant with the most pungs. At least one will be returned.
        This is meant for the standard MJ format (4 pungs/kongs/chows plus 1 pair)"""
        values = tuple(values)
        if values not in cls.colorPermCache:
            variants = cls.permute(values)
            result = []
            maxPungs = -1
            maxPungVariant = minMeldVariant = None
            minMelds = 99
            for variant in variants:
                if all(len(meld) > 1 for meld in variant):
                    # no singles: usable for MJ
                    result.append(variant)
                if len(variant) < minMelds:
                    minMelds = len(variant)
                    minMeldVariant = variant
                pungCount = sum(
                    len(meld) == 3 and len(set(meld)) == 1 for meld in variant)
                if pungCount > maxPungs:
                    maxPungs = pungCount
                    maxPungVariant = variant
            if maxPungs > 0 and maxPungVariant not in result:
                result.append(maxPungVariant)
            result.append(minMeldVariant)
            if not result:
                # if nothing seems useful, return all possible permutations
                result.extend(variants)
            cls.colorPermCache[values] = tuple(result)
        return cls.colorPermCache[values]

    @classmethod
    def __colorVariants(cls, color, values):
        """generates all possible meld variants out of original
        where values is a string like '113445'.
        Returns lists of Meld"""
        allValues = sorted(values)
        vSet = set(allValues)
        groups = []
        for border in sorted(x + 1 for x in sorted(vSet) if x + 1 not in vSet):
            content = list(x for x in allValues if x < border)
            if content:
                groups.append(content)
                allValues = list(x for x in allValues if x > border)
        combinations = list(cls.usefulPermutations(x) for x in groups)
        result = []
        for variant in list(itertools.product(*combinations)):
            melds = []
            for block in variant:
                for meld in block:
                    melds.append(Meld(Tile(color, x) for x in meld))
            if melds:
                result.append(melds)
        return result
