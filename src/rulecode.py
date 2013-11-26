# -*- coding: utf-8 -*-

"""Copyright (C) 2009-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

kajongg is free software you can redistribute it and/or modify
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

from tile import Tile, Tileset, elements, Byteset, Bytelist
from meld import Meld, MeldList
from common import IntDict, WINDS
from message import Message
from query import Query
from permutations import Permutations

class Function(object):
    """Parent for all Function classes. We need to implement
    those methods as in Regex:
    appliesToHand and appliesToMeld"""

    functions = {}

    def __init__(self):
        self.options = {}

    def __str__(self):
        return self.__class__.__name__

    def __repr__(self):
        return self.__class__.__name__

# pylint: disable=missing-docstring
# the class and method names are mostly self explaining, we do not
# need docstringss

# pylint: disable=arguments-differ
# pylint does not know that overriding a method may change it from normal to static
class MeldFunction(Function):
    def appliesToMeld(self, dummyHand, dummyMeld):
        raise NotImplementedError

class MahJonggFunction(Function):
    def winningTileCandidates(self, dummyHand):
        """this should return all tiles leading to a winning hand no matter
        by which mjRule the hand will be matched, see SquirmingSnake"""
        raise NotImplementedError

    def computeLastMelds(self, dummyHand):
        """returns a list of all melds which can be built with lastTile.
        lastTile must be known!"""
        raise NotImplementedError

    def appliesToHand(self, dummyHand):
        raise NotImplementedError

    def shouldTry(self, dummyHand, maxMissing=3):
        """does not have to be exact, just a fast guess if it makes sense
        to look at this possibility harder"""
        raise NotImplementedError

    def rearrange(self, dummyHand, pairs):
        raise NotImplementedError

class DragonPungKong(MeldFunction):
    def appliesToMeld(self, dummyHand, meld):
        return (len(meld) >= 3
            and meld.isDragonMeld
            and (meld.isPung or meld.isKong))

class RoundWindPungKong(MeldFunction):
    @staticmethod
    def appliesToMeld(hand, meld):
        return len(meld) >= 3 and meld.isWindMeld and meld[0].value == hand.roundWind

class ExposedMinorPung(MeldFunction):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return meld.isPung and meld.isLower(0, 3) and meld[0].value in b'2345678'

class ExposedTerminalsPung(MeldFunction):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return meld.isPung and meld.isLower(0, 3) and meld[0].value in b'19'

class ExposedHonorsPung(MeldFunction):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return meld.isPung and meld.group in b'wd'

class ExposedMinorKong(MeldFunction):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return len(meld) == 4 and meld.isLower(0, 3) and meld[0].value in b'2345678'

class ExposedTerminalsKong(MeldFunction):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return len(meld) == 4 and meld.isLower(0, 3) and meld[0].value in b'19'

class ExposedHonorsKong(MeldFunction):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return len(meld) == 4 and meld.isLower(0, 3) and meld.group in b'wd'

class ConcealedMinorPung(MeldFunction):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return meld.isPung and meld.isUpper(0, 3) and meld[0].value in b'2345678'

class ConcealedTerminalsPung(MeldFunction):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return meld.isPung and meld.isUpper(0, 3) and meld[0].value in b'19'

class ConcealedHonorsPung(MeldFunction):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return meld.isPung and meld.group in b'WD'

class ConcealedMinorKong(MeldFunction):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return len(meld) == 4 and not meld.isExposed and meld[0].value in b'2345678'

class ConcealedTerminalsKong(MeldFunction):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return len(meld) == 4 and not meld.isExposed and meld[0].value in b'19'

class ConcealedHonorsKong(MeldFunction):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return len(meld) == 4 and not meld.isExposed and meld.isHonorMeld

class OwnWindPungKong(MeldFunction):
    @staticmethod
    def appliesToMeld(hand, meld):
        return len(meld) >= 3 and meld.isWindMeld and meld[0].value == hand.ownWind

class OwnWindPair(MeldFunction):
    @staticmethod
    def appliesToMeld(hand, meld):
        return len(meld) == 2 and meld.isWindMeld and meld[0].value == hand.ownWind

class RoundWindPair(MeldFunction):
    @staticmethod
    def appliesToMeld(hand, meld):
        return len(meld) == 2 and meld.isWindMeld and meld[0].value == hand.roundWind

class DragonPair(MeldFunction):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return len(meld) == 2 and meld.isDragonMeld

class LastTileCompletesPairMinor(Function):
    @staticmethod
    def appliesToHand(hand):
        return (hand.lastMeld and len(hand.lastMeld) == 2
            and hand.lastMeld.group != b'X'
            and hand.lastTile.value in b'2345678')

class Flower(MeldFunction):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return len(meld) == 1 and meld.group == b'f'

class Season(MeldFunction):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return len(meld) == 1 and meld.group == b'y'

class LastTileCompletesPairMajor(Function):
    @staticmethod
    def appliesToHand(hand):
        return (hand.lastMeld and len(hand.lastMeld) == 2
            and hand.lastMeld.group == hand.lastMeld[1].group
            and hand.lastTile.value not in b'2345678')

class LastFromWall(Function):
    @staticmethod
    def appliesToHand(hand):
        return hand.lastTile and hand.lastTile.group.isupper()

class ZeroPointHand(Function):
    @staticmethod
    def appliesToHand(hand):
        return not any(x.meld for x in hand.usedRules if x.meld and len(x.meld) > 1)

class NoChow(Function):
    @staticmethod
    def appliesToHand(hand):
        return not any(x.isChow for x in hand.melds)

class OnlyConcealedMelds(Function):
    @staticmethod
    def appliesToHand(hand):
        return not any((x.isExposed and not x.isClaimedKong) for x in hand.melds)

class FalseColorGame(Function):
    @staticmethod
    def appliesToHand(hand):
        dwSet = {b'd', b'w'}
        return dwSet & hand.suits and len(hand.suits - dwSet) == 1

class TrueColorGame(Function):
    @staticmethod
    def appliesToHand(hand):
        return len(hand.suits) == 1 and hand.suits < {b's', b'b', b'c'}

class Purity(Function):
    @staticmethod
    def appliesToHand(hand):
        return (len(hand.suits) == 1 and hand.suits < {b's', b'b', b'c'}
            and not any(x.isChow for x in hand.melds))

class ConcealedTrueColorGame(Function):
    @staticmethod
    def appliesToHand(hand):
        if len(hand.suits) != 1 or not (hand.suits < {b's', b'b', b'c'}):
            return False
        return not any((x.isExposed and not x.isClaimedKong) for x in hand.melds)

class OnlyMajors(Function):
    @staticmethod
    def appliesToHand(hand):
        return not set(hand.values) - Byteset(b'grbeswn19')

class OnlyHonors(Function):
    @staticmethod
    def appliesToHand(hand):
        return not set(hand.values) - Byteset(b'grbeswn')

class HiddenTreasure(Function):
    @staticmethod
    def appliesToHand(hand):
        return (not any(((x.isExposed and not x.isClaimedKong) or x.isChow) for x in hand.melds)
            and hand.lastTile and hand.lastTile.group.isupper()
            and len(hand.melds) == 5)

class BuriedTreasure(Function):
    @staticmethod
    def appliesToHand(hand):
        return (len(hand.suits - Byteset(b'dw')) == 1
            and sum(x.isPung for x in hand.melds) == 4
            and all((x.isPung and not x.isExposed ) or x.isPair for x in hand.melds))

class AllTerminals(Function):
    @staticmethod
    def appliesToHand(hand):
        return not set(hand.values) - Byteset(b'19')

class StandardMahJongg(MahJonggFunction):
    @staticmethod
    def computeLastMelds(hand):
        """returns all possible last melds"""
        return MeldList(x for x in hand.melds if hand.lastTile in x and len(x) < 4)

    @staticmethod
    def appliesToHand(hand):
        """winner rules are not yet applied to hand"""
        # pylint: disable=too-many-return-statements
        # too many return statements
        if len(hand.melds) != 5:
            return False
        if any(len(x) not in (2, 3, 4) for x in hand.melds):
            return False
        if any(x.isRest for x in hand.melds):
            return False
        if sum(x.isChow for x in hand.melds) > hand.ruleset.maxChows:
            return False
        if hand.score.total() < hand.ruleset.minMJPoints:
            return False
        if hand.score.doubles >= hand.ruleset.minMJDoubles:
            # shortcut
            return True
        # but maybe we have enough doubles by winning:
        doublingWinnerRules = sum(x.rule.score.doubles for x in hand.matchingWinnerRules())
        return hand.score.doubles + doublingWinnerRules >= hand.ruleset.minMJDoubles

    @staticmethod
    def fillChow(group, values):
        val0, val1 = values
        if val0 + 1 == val1:
            if val0 == 1:
                return {Tile(group, val0 + 2)}
            if val0 == 8:
                return {Tile(group, val0 - 1)}
            return {Tile(group, val0 - 1), Tile(group, val0 + 2)}
        else:
            assert val0 + 2 == val1, 'group:%s values:%s' % (group, values)
            return {Tile(group, val0 + 1)}

    @staticmethod
    def winningTileCandidates(hand):
        # pylint: disable=too-many-locals,too-many-return-statements,too-many-branches,too-many-statements
        if len(hand.melds) > 7:
            # hope 7 is sufficient, 6 was not
            return set()
        if not hand.tilesInHand:
            return set()
        inHand = list(x.lower() for x in hand.tilesInHand)
        result = inHand[:]
        pairs = 0
        isolated = 0
        maxChows = hand.ruleset.maxChows - sum(x.isChow for x in hand.declaredMelds)
        # TODO: does not differentiate between maxChows == 1 and maxChows > 1
        # test with kajonggtest and a ruleset where maxChows == 2
        if maxChows < 0:
            return set()
        if maxChows == 0:
            checkTiles = set(inHand)
        else:
            checkTiles = set(inHand) & elements.honors
        for tileName in checkTiles:
            count = inHand.count(tileName)
            if count == 1:
                isolated += 1
            elif count == 2:
                pairs += 1
            else:
                for _ in range(count):
                    result.remove(tileName)
        if maxChows:
            if pairs > 2 or isolated > 2 or (pairs > 1 and isolated > 1):
                # this is not a calling hand
                return set()
        else:
            if pairs + isolated > 2:
                return set()
        if maxChows == 0:
            return set(result)
        melds = []
        for group in hand.suits & {b's', b'c', b'b'}:
            values = sorted(int(x.value) for x in result if x.group == group)
            changed = True
            while (changed and len(values) > 2
                    and values.count(values[0]) == 1
                    and values.count(values[1]) == 1
                    and values.count(values[2]) == 1):
                changed = False
                if values[0] + 2 == values[2] and (len(values) == 3 or values[3] > values[0] + 3):
                    # print('removing first 3 from %s' % values)
                    meld = Meld([Tile(group, values[x]) for x in range(3)])
                    for pair in meld:
                        result.remove(pair)
                    melds.append(meld)
                    values = values[3:]
                    changed = True
                elif values[0] + 1 == values[1] and values[2] > values[0] + 2:
                    # print('found incomplete chow at start of %s' % values)
                    return StandardMahJongg.fillChow(group, values[:2])
            changed = True
            while (changed and len(values) > 2
                    and values.count(values[-1]) == 1
                    and values.count(values[-2]) == 1
                    and values.count(values[-3]) == 1):
                changed = False
                if values[-1] - 2 == values[-3] and (len(values) == 3 or values[-4] < values[-1] - 3):
                    meld = Meld([Tile(group, values[x]) for x in range(-3, 0)])
                    for pair in meld:
                        result.remove(pair)
                    melds.append(meld)
                    values = values[:-3]
                    changed = True
                elif values[-1] - 1 == values[-2] and values[-3] < values[-1] - 2:
                    # print('found incomplete chow at end of %s' % values)
                    return StandardMahJongg.fillChow(group, values[-2:])

            if len(values) % 3 == 0:
                # adding a 4th, 7th or 10th tile with this color can not let us win,
                # so we can exclude this color from the candidates
                result = list(x for x in result if x.group != group)
                continue
            valueSet = set(values)
            if len(values) == 4 and len(values) == len(valueSet):
                if values[0] + 3 == values[-1]:
                    # print('seq4 in %s' % hand.tilesInHand)
                    return {Tile(group, values[0]), Tile(group, values[-1])}
            if len(values) == 7 and len(values) == len(valueSet):
                if values[0] + 6 == values[6]:
                    # print('seq7 in %s' % hand.tilesInHand)
                    return {Tile(group, values[x]) for x in (0, 3, 6)}
            if len(values) == 1:
                # only a pair of this value is possible
                return {Tile(group.upper(), values[0])}
            if len(valueSet) == 1:
                # no chow reachable, only pair/pung
                continue
            singles = set(x for x in valueSet
                 if values.count(x) == 1
                 and not set([x-1, x-2, x+1, x+2]) & valueSet)
            isolated += len(singles)
            if isolated > 1:
                # this is not a calling hand
                return set()
            if len(values) == 2 and len(valueSet) == 2:
                # exactly two adjacent values: must be completed to Chow
                if maxChows == 0:
                    # not a calling hand
                    return set()
                return StandardMahJongg.fillChow(group, values)
            if (len(values) == 4 and len(valueSet) == 2
                    and values[0] == values[1] and values[2] == values[3]):
                # print('we have 2 pairs of %s' % group)
                return {Tile(group, values[0]), Tile(group, values[2])}
            if maxChows:
                for value in valueSet:
                    if value > 1:
                        result.append(Tile(group, str(value - 1)))
                    if value < 9:
                        result.append(Tile(group, str(value + 1)))
        return set(result)

    @staticmethod
    def shouldTry(dummyHand):
        return True
    @staticmethod
    def rearrange(hand, pairs):
        """rest is a string with those tiles that can still
        be rearranged: No declared melds and no bonus tiles.
        done is already arranged, do not change this.
        Returns list(Meld)"""
# TODO: return all variants. The parent should find the best mjrRule/variant combo
        assert pairs
        permutations = Permutations(pairs)
        bestHand = None
        bestVariant = None
        for variantMelds in permutations.variants:
            melds = hand.melds[:] + variantMelds
            melds.extend(hand.bonusMelds)
            _ = b' '.join(bytes(x) for x in melds) + b' ' + hand.mjStr
            tryHand = hand.__class__(hand, _, computedRules=hand.computedRules)
            if not bestHand or tryHand.total() > bestHand.total():
                bestHand = tryHand
                bestVariant = variantMelds
        return bestVariant, []

class SquirmingSnake(StandardMahJongg):
    @staticmethod
    def appliesToHand(hand):
        if len(hand.suits) != 1 or not hand.suits < {b's', b'b', b'c'}:
            return False
        values = hand.values
        if values.count(b'1') < 3 or values.count(b'9') < 3:
            return False
        pairs = [x for x in Byteset(b'258') if values.count(x) == 2]
        if len(pairs) != 1:
            return False
        return len(set(values)) == len(values) - 5

    @staticmethod
    def winningTileCandidates(hand):
        """they have already been found by the StandardMahJongg rule"""
        return set()

class WrigglingSnake(MahJonggFunction):
    @staticmethod
    def shouldTry(hand, maxMissing=3):
        return (len(set(x.lower() for x in hand.tileNames)) + maxMissing > 12
           and all(not x.isChow for x in hand.declaredMelds))

    def computeLastMelds(self, hand):
        if hand.lastTile.value == b'1':
            return [Meld([hand.lastTile] * 2)]
        else:
            return [Meld([hand.lastTile])]

    def winningTileCandidates(self, hand):
        suits = hand.suits.copy()
        if b'w' not in suits or b'd' in suits or len(suits) > 2:
            return set()
        suits -= {b'w'}
        group = suits.pop()
        values = set(hand.values)
        if len(values) < 12:
            return set()
        elif len(values) == 12:
            # one of 2..9 or a wind is missing
            if len(list(x for x in hand.values if x == b'1')) < 2:
                # and the pair of 1 is incomplete too
                return set()
            else:
                return (elements.winds | set([Tile(group, x) for x in range(2, 10)])) \
                    - set([x.lower() for x in hand.tileNames])
        else:
            # pair of 1 is not complete
            return set([Tile(group, 1)])

    @staticmethod
    def rearrange(dummyHand, pairs):
        result = []
        for tileName in pairs[:]:
            if pairs.count(tileName) >= 2:
                result.append(Meld([tileName, tileName]))
                pairs.remove(tileName)
                pairs.remove(tileName)
            elif pairs.count(tileName) == 1:
                result.append(Meld([tileName]))
                pairs.remove(tileName)
        return result, pairs

    @staticmethod
    def appliesToHand(hand):
        suits = hand.suits.copy()
        if b'w' not in suits:
            return False
        suits -= {b'w'}
        if len(suits) != 1 or not suits < {b's', b'b', b'c'}:
            return False
        if hand.values.count(b'1') != 2:
            return False
        return len(set(hand.values)) == 13

class CallingHand(Function):
    def __init__(self):
        Function.__init__(self)
        self.active = False
        self.limitHand = None

    def appliesToHand(self, hand):
        if self.active:
            # this cannot be reentrant because we attach the options to the
            # one global CallingHand instance
            return False
        if hand.lenOffset != 0:
            return False
        if not self.limitHand:
            self.limitHand = Function.functions[self.options['hand']]()
            self.limitHand.options = self.options
        self.active = True
        try:
            if hasattr(self.limitHand, 'winningTileCandidates'):
                # it is a MahJonggFunction
                candidates = self.limitHand.winningTileCandidates(hand)
            else:
                # it is any other normal Function
                candidates = StandardMahJongg.winningTileCandidates(hand)
            for tileName in candidates:
                fullHand = hand + tileName.capitalize()
                if fullHand.won and self.limitHand.appliesToHand(fullHand):
                    return True
            return False
        finally:
            self.active = False

class TripleKnitting(MahJonggFunction):

    def computeLastMelds(self, hand):
        """returns all possible last melds"""
        if not hand.lastTile:
            return
        triples, rest = self.findTriples(hand)
        assert len(rest) == 2
        triples.append(rest)  # just a list of tuples
        return [Meld(x) for x in triples if hand.lastTile in x]

    def claimness(self, hand, dummyDiscard):
        result = IntDict()
        if self.shouldTry(hand):
            result[Message.Pung] = -999
            result[Message.Kong] = -999
            result[Message.Chow] = -999
        return result

    def weigh(self, dummyAiInstance, candidates):
        if self.shouldTry(candidates.hand):
            _, rest = self.findTriples(candidates.hand)
            for candidate in candidates:
                if candidate.group in b'dw':
                    candidate.keep -= 50
                if rest.count(candidate.name) > 1:
                    candidate.keep -= 10
        return candidates

    def rearrange(self, hand, pairs):
        melds = []
        for triple in self.findTriples(hand)[0]:
            melds.append(Meld(triple))
            pairs.remove(triple[0])
            pairs.remove(triple[1])
            pairs.remove(triple[2])
        while len(pairs) >= 2:
            for value in Byteset(list(ord(x.value) for x in pairs)):
                suits = set(x.group for x in pairs if ord(x.value) == value)
                if len(suits) <2:
                    return melds, pairs
                pair = (Tile(suits.pop(), value), Tile(suits.pop(), value))
                melds.append(Meld(sorted(pair)))
                pairs.remove(pair[0])
                pairs.remove(pair[1])
        return melds, pairs

    def appliesToHand(self, hand):
        if any(x.isHonor for x in hand.tileNames):
            return False
        if len(hand.declaredMelds) > 1:
            return False
        if hand.lastTile and hand.lastTile.istitle() and hand.declaredMelds:
            return False
        triples, rest = self.findTriples(hand)
        return (len(triples) == 4 and len(rest) == 2
            and rest[0].group != rest[1].group and rest[0].value == rest[1].value)

    def winningTileCandidates(self, hand):
        if hand.hasHonorMelds:
            return set()
        if hand.declaredMelds:
            return set()
        _, rest = self.findTriples(hand)
        if len(rest) not in (1, 4):
            return set()
        result = list([Tile(x, y.value) for x in (b'S', b'B', b'C') for y in rest])
        for restTile in rest:
            result.remove(restTile)
        return set(result)

    def shouldTry(self, hand, maxMissing=3):
        if hand.declaredMelds:
            return False
        tripleWanted = 7 - maxMissing // 3 # count triples
        tripleCount = len(self.findTriples(hand)[0])
        return tripleCount >= tripleWanted

    @staticmethod
    def findTriples(hand):
        """returns a list of Triples, including the mj triple.
        Also returns the remaining untripled tiles"""
        if hand.declaredMelds:
            if len(hand.declaredMelds) > 1:
                return [], None
        result = []
        tilesS = list(x.capitalize() for x in hand.tileNames if x.lowerGroup == b's')
        tilesB = list(x.capitalize() for x in hand.tileNames if x.lowerGroup == b'b')
        tilesC = list(x.capitalize() for x in hand.tileNames if x.lowerGroup == b'c')
        for tileS in tilesS[:]:
            tileB = Tile(b'B' + tileS.value)
            tileC = Tile(b'C' + tileS.value)
            if tileB in tilesB and tileC in tilesC:
                tilesS.remove(tileS)
                tilesB.remove(tileB)
                tilesC.remove(tileC)
                result.append((tileS, tileB, tileC))
        return result, tilesS + tilesB + tilesC

class Knitting(MahJonggFunction):
    def computeLastMelds(self, hand):
        """returns all possible last melds"""
        if not hand.lastTile:
            return []
        couples, rest = self.findCouples(hand)
        assert not rest, '%s: couples=%s rest=%s' % (hand.string, couples, rest)
        return [Meld(x) for x in couples if hand.lastTile in x]

    def claimness(self, hand, dummyDiscard):
        result = IntDict()
        if self.shouldTry(hand):
            result[Message.Pung] = -999
            result[Message.Kong] = -999
            result[Message.Chow] = -999
        return result
    def weigh(self, dummyAiInstance, candidates):
        if self.shouldTry(candidates.hand):
            for candidate in candidates:
                if candidate.group in b'dw':
                    candidate.keep -= 50
        return candidates
    def shouldTry(self, hand, maxMissing=4):
        if hand.declaredMelds:
            return False
        pairWanted = 7 - maxMissing // 2 # count pairs
        pairCount = len(self.findCouples(hand)[0])
        return pairCount >= pairWanted

    def appliesToHand(self, hand):
        if any(x.isHonor for x in hand.tileNames):
            return False
        if len(hand.declaredMelds) > 1:
            return False
        if hand.lastTile and hand.lastTile.istitle() and hand.declaredMelds:
            return False
        return len(self.findCouples(hand)[0]) == 7

    def winningTileCandidates(self, hand):
        if any(x.isDeclared for x in hand.melds):
            return set()
        if hand.hasHonorMelds:
            return set()
        couples, singleTile = self.findCouples(hand)
        if len(couples) != 6:
            return set()
        if not singleTile:
            # single tile has wrong suit
            return set()
        assert len(singleTile) == 1
        singleTile = singleTile[0]
        otherSuit = (hand.suits - set([singleTile.lowerGroup])).pop()
        otherTile = Tile(otherSuit.capitalize(), singleTile.value)
        return set([otherTile])
    def rearrange(self, hand, pairs):
        melds = []
        for couple in self.findCouples(hand, pairs)[0]:
            if couple[0].islower():
                # this is the mj pair, lower after claiming
                continue
            melds.append(Meld(couple))
            pairs.remove(couple[0])
            pairs.remove(couple[1])
        return melds, pairs
    def findCouples(self, hand, pairs=None):
        """returns a list of tuples, including the mj couple.
        Also returns the remaining uncoupled tiles IF they
        are of the wanted suits"""
        if hand.declaredMelds:
            if len(hand.declaredMelds) > 1 or len(hand.declaredMelds[0]) > 2:
                return [], []
        result = []
        if pairs is None:
            pairs = hand.tileNames
        suits = self.pairSuits(hand)
        if not suits:
            return [], []
        tiles0 = list(x for x in pairs if x.lowerGroup == suits[0])
        tiles1 = list(x for x in pairs if x.lowerGroup == suits[1])
        for tile0 in tiles0[:]:
            if tile0.islower():
                tile1 = Tile(suits[1], tile0.value)
            else:
                tile1 = Tile(suits[1].upper(), tile0.value)
            if tile1 in tiles1:
                tiles0.remove(tile0)
                tiles1.remove(tile1)
                result.append((tile0, tile1))
        return result, tiles0 + tiles1
    @staticmethod
    def pairSuits(hand):
        """returns a lowercase string with two suit characters. If no prevalence, returns None"""
        suitCounts = list(len([x for x in hand.tileNames if x.lowerGroup == y]) for y in (b's', b'b', b'c'))
        minSuit = min(suitCounts)
        result = b''.join(x for idx, x in enumerate([b's', b'b', b'c']) if suitCounts[idx] > minSuit)
        if len(result) == 2:
            return Bytelist(result)

class AllPairHonors(MahJonggFunction):
    @staticmethod
    def computeLastMelds(hand):
        return [Meld([hand.lastTile, hand.lastTile])]
    @staticmethod
    def claimness(hand, dummyDiscard):
        result = IntDict()
        if AllPairHonors.shouldTry(hand):
            result[Message.Pung] = -999
            result[Message.Kong] = -999
            result[Message.Chow] = -999
        return result
    @staticmethod
    def maybeCallingOrWon(hand):
        if any(x.value in b'2345678' for x in hand.tileNames):
            return False
        return len(hand.declaredMelds) < 2
    def appliesToHand(self, hand):
        if not self.maybeCallingOrWon(hand):
            return False
        if len(set(hand.values)) != 7:
            return False
        valueCounts = sorted([len([x for x in hand.tileNames if x.value == y]) for y in hand.values])
        return set(valueCounts) == set([2])
    def winningTileCandidates(self, hand):
        if not self.maybeCallingOrWon(hand):
            return set()
        single = list(x for x in hand.tileNames if hand.tileNames.count(x) == 1)
        if len(single) != 1:
            return set()
        return set(single)
    @staticmethod
    def shouldTry(hand, maxMissing=4):
        if hand.declaredMelds:
            return False
        tiles = list(x.lower() for x in hand.tileNames)
        pairCount = kongCount = 0
        for tile in elements.majors:
            count = tiles.count(tile)
            if count == 2:
                pairCount += 1
            elif count == 4:
                kongCount += 1
        pairWanted = 7 - maxMissing // 2 # count pairs
        result = pairCount >= pairWanted or (pairCount + kongCount * 2) > pairWanted
        return result
    @staticmethod
    def rearrange(dummyHand, pairs):
        melds = []
        for pair in set(pairs) & elements.mAJORS:
            while pairs.count(pair) >= 2:
                melds.append(Meld(pair * 2))
                pairs.remove(pair)
                pairs.remove(pair)
        return melds, pairs
    @staticmethod
    def weigh(dummyAiInstance, candidates):
        hand = candidates.hand
        if not AllPairHonors.shouldTry(hand):
            return candidates
        keep = 10
        for candidate in candidates:
            if candidate.value in b'2345678':
                candidate.keep -= keep
            else:
                if candidate.occurrence == 3:
                    candidate.keep -= keep / 2
                else:
                    candidate.keep += keep
        return candidates


class FourfoldPlenty(Function):
    @staticmethod
    def appliesToHand(hand):
        return len(hand.tileNames) == 18

class ThreeGreatScholars(Function):
    def appliesToHand(self, hand):
        return (BigThreeDragons.appliesToHand(hand)
            and ('nochow' not in self.options or not any(x.isChow for x in hand.melds)))

class BigThreeDragons(Function):
    @staticmethod
    def appliesToHand(hand):
        return len([x for x in hand.melds if x.isDragonMeld and len(x) >= 3]) == 3

class BigFourJoys(Function):
    @staticmethod
    def appliesToHand(hand):
        return len([x for x in hand.melds if x.isWindMeld and len(x) >= 3]) == 4

class LittleFourJoys(Function):
    @staticmethod
    def appliesToHand(hand):
        lengths = sorted([min(len(x), 3) for x in hand.melds if x.isWindMeld])
        return lengths == [2, 3, 3, 3]

class LittleThreeDragons(Function):
    @staticmethod
    def appliesToHand(hand):
        lengths = sorted([min(len(x), 3) for x in hand.melds if x.isDragonMeld])
        return lengths == [2, 3, 3]

class FourBlessingsHoveringOverTheDoor(Function):
    @staticmethod
    def appliesToHand(hand):
        return len([x for x in hand.melds if len(x) >= 3 and x.isWindMeld]) == 4

class AllGreen(Function):
    @staticmethod
    def appliesToHand(hand):
        tiles = set(bytes(x.lower()) for x in hand.tileNames)
        return tiles < Tileset([b'b2', b'b3', b'b4', b'b5', b'b6', b'b8', b'dg'])

class LastTileFromWall(Function):
    @staticmethod
    def appliesToHand(hand):
        return hand.lastSource == b'w'

class LastTileFromDeadWall(Function):
    @staticmethod
    def appliesToHand(hand):
        return hand.lastSource == b'e'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return hand.lastSource == b'w'

class IsLastTileFromWall(Function):
    @staticmethod
    def appliesToHand(hand):
        return hand.lastSource == b'z'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return hand.lastSource == b'w'

class IsLastTileFromWallDiscarded(Function):
    @staticmethod
    def appliesToHand(hand):
        return hand.lastSource == b'Z'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return hand.lastSource == b'd'

class RobbingKong(Function):
    @staticmethod
    def appliesToHand(hand):
        return hand.lastSource == b'k'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return (hand.lastSource and hand.lastSource in b'kwd'
            and hand.lastTile and hand.lastTile.group.islower()
            and [x.lower() for x in hand.tileNames].count(hand.lastTile.lower()) < 2)

class GatheringPlumBlossomFromRoof(Function):
    @staticmethod
    def appliesToHand(hand):
        return LastTileFromDeadWall.appliesToHand(hand) and hand.lastTile == b'S5'

class PluckingMoon(Function):
    @staticmethod
    def appliesToHand(hand):
        return IsLastTileFromWall.appliesToHand(hand) and hand.lastTile == b'S1'

class ScratchingPole(Function):
    @staticmethod
    def appliesToHand(hand):
        return RobbingKong.appliesToHand(hand) and hand.lastTile == b'b2'

class StandardRotation(Function):
    @staticmethod
    def rotate(game):
        return game.winner and game.winner.wind != b'E'

class EastWonNineTimesInARow(Function):
    nineTimes = 9
    @staticmethod
    def appliesToHand(hand):
        if not hand.player:
            return False
        game = hand.player.game
        return EastWonNineTimesInARow.appliesToGame(game)
    @staticmethod
    def appliesToGame(game, needWins=None):
        if needWins is None:
            needWins = EastWonNineTimesInARow.nineTimes
            if game.isScoringGame():
                # we are only proposing for the last needed Win
                needWins  -= 1
        if game.winner and game.winner.wind == b'E' and game.notRotated >= needWins:
            prevailing = WINDS[game.roundsFinished % 4]
            eastMJCount = int(Query("select count(1) from score "
                "where game=%d and won=1 and wind='E' and player=%d "
                "and prevailing='%s'" % \
                (game.gameid, game.players['E'].nameid, prevailing)).records[0][0])
            return eastMJCount == needWins
        return False
    @staticmethod
    def rotate(game):
        return EastWonNineTimesInARow.appliesToGame(game, needWins = EastWonNineTimesInARow.nineTimes)

class GatesOfHeaven(StandardMahJongg):
    def __init__(self):
        StandardMahJongg.__init__(self)
        self.suit = None
    def shouldTry(self, hand):
        for suit in b'sbc':
            count19 = sum(x.value in b'19' for x in hand.tileNames)
            suitCount = len(list(x for x in hand.tileNames if x.lowerGroup == suit))
            if suitCount > 10 and count19 > 4:
                return True
        return False

    def maybeCallingOrWon(self, hand):
        suits = set(x.lowerGroup for x in hand.tileNames)
        if len(suits) != 1 or not suits < {b's', b'c', b'b'}:
            return False
        self.suit = suits.pop()
        for meld in hand.declaredMelds:
            if meld.isPung:
                return False
        return True

    def appliesToHand(self, hand):
        if not self.maybeCallingOrWon(hand):
            return False
        values = hand.values
        if len(set(values)) < 9 or not values.startswith(b'111') or not values.endswith(b'999'):
            return False
        values = values[3:-3]
        for value in Byteset(b'2345678'):
            if value in values:
                values.remove(value)
        if len(values) != 1:
            return False
        surplus = values[0]
        if 'pair28' in self.options:
            return surplus in b'2345678'
        if 'lastExtra' in self.options:
            return hand.lastTile and surplus == hand.lastTile.value
        return True

    def winningTileCandidates(self, hand):
        result = set()
        if not self.maybeCallingOrWon(hand):
            return result
        values = hand.values
        if len(set(values)) == 8:
            # one minor is missing
            result = Byteset(b'2345678') - Byteset(values)
        else:
            # we have something of all values
            if not values.startswith(b'111'):
                result = b'1'
            elif not values.endswith(b'999'):
                result = b'9'
            else:
                if 'pair28' in self.options:
                    result = b'2345678'
                else:
                    result = b'123456789'
        return {Tile(self.suit, x) for x in result}

class ThirteenOrphans(MahJonggFunction):
    def __init__(self):
        MahJonggFunction.__init__(self)
        self.missingTiles = None

    @staticmethod
    def computeLastMelds(hand):
        meldSize = hand.tilesInHand.count(hand.lastTile)
        return [Meld([hand.lastTile] * meldSize)]

    @staticmethod
    def rearrange(dummyHand, pairs):
        result = []
        for tileName in pairs[:]:
            if pairs.count(tileName) >= 2:
                result.append(Meld([tileName, tileName]))
                pairs.remove(tileName)
                pairs.remove(tileName)
            elif pairs.count(tileName) == 1:
                result.append(Meld([tileName]))
                pairs.remove(tileName)
        return result, pairs

    @staticmethod
    def claimness(hand, discard):
        result = IntDict()
        if ThirteenOrphans.shouldTry(hand):
            doublesCount = hand.doublesEstimate()
            if hand.tileNames.count(discard) == 2:
# TODO: compute scoring for resulting hand. If it is high anyway,
# prefer pung over trying 13 orphans
                for rule in hand.ruleset.doublingMeldRules:
                    if rule.appliesToMeld(hand, Meld(discard.lower() * 3)):
                        doublesCount += 1
            if doublesCount < 2 or ThirteenOrphans.shouldTry(hand, maxMissing=1):
                result[Message.Pung] = -999
                result[Message.Kong] = -999
                result[Message.Chow] = -999
        return result

    @staticmethod
    def appliesToHand(hand):
        return set(x.lower() for x in hand.tileNames) == elements.majors

    @staticmethod
    def winningTileCandidates(hand):
        if any(x in hand.values for x in Byteset(b'2345678')):
            # no minors allowed
            return set()
        if not ThirteenOrphans.shouldTry(hand, maxMissing=1):
            return set()
        handTiles = set(x.lower() for x in hand.tileNames)
        missing = elements.majors - handTiles
        if len(missing) == 0:
            # if all 13 tiles are there, we need any one of them:
            return elements.majors
        else:
            assert len(missing) == 1
            return missing

    @staticmethod
    def shouldTry(hand, maxMissing=4):
        # TODO: look at how many tiles there still are on the wall
        if hand.declaredMelds:
            return False
        if hand.doublesEstimate() > 1:
            return False
        handTiles = set(x.lower() for x in hand.tileNames)
        missing = elements.majors - handTiles
        if len(missing) > maxMissing:
            return False
        if hand.player:
            # in scoringtest, we have no game instance
            # on the server we have no myself in saveHand
            for missingTile in missing:
                if not hand.player.tileAvailable(missingTile, hand):
                    return False
        return True

    @staticmethod
    def weigh(dummyAiInstance, candidates):
        hand = candidates.hand
        if not ThirteenOrphans.shouldTry(hand):
            return candidates
        handTiles = set(x.lower() for x in hand.tileNames)
        missing = elements.majors - handTiles
        havePair = False
        keep = (6 - len(missing)) * 5
        for candidate in candidates:
            if candidate.value in b'2345678':
                candidate.keep -= keep
            else:
                if havePair and candidate.occurrence >= 2:
                    candidate.keep -= keep
                else:
                    candidate.keep += keep
                havePair = candidate.occurrence == 2
        return candidates

class OwnFlower(Function):
    @staticmethod
    def appliesToHand(hand):
        fsPairs = list(x[0] for x in hand.bonusMelds)
        return Tile(b'f', hand.ownWind) in fsPairs

class OwnSeason(Function):
    @staticmethod
    def appliesToHand(hand):
        fsPairs = list(x[0] for x in hand.bonusMelds)
        return Tile(b'y', hand.ownWind) in fsPairs

class OwnFlowerOwnSeason(Function):
    @staticmethod
    def appliesToHand(hand):
        return (OwnFlower.appliesToHand(hand)
            and OwnSeason.appliesToHand(hand))

class AllFlowers(Function):
    @staticmethod
    def appliesToHand(hand):
        return len([x for x in hand.bonusMelds if x.group == b'f']) == 4

class AllSeasons(Function):
    @staticmethod
    def appliesToHand(hand):
        return len([x for x in hand.bonusMelds if x.group == b'y']) == 4

class ThreeConcealedPongs(Function):
    @staticmethod
    def appliesToHand(hand):
        return len([x for x in hand.melds if (
            not x.isExposed or x.isClaimedKong) and (x.isPung or x.isKong)]) >= 3

class MahJonggWithOriginalCall(Function):
    @staticmethod
    def appliesToHand(hand):
        return (b'a' in hand.announcements
            and sum(x.isExposed for x in hand.melds) < 3)

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        # one tile may be claimed before declaring OC and one for going MJ
        # the previous regex was too strict
        return sum(x.isExposed for x in hand.melds) < 3

    @staticmethod
    def claimness(hand, dummyDiscard):
        result = IntDict()
        if hand.player:
            if hand.player.originalCall and hand.player.mayWin:
                winningChances = hand.player.originalCallingHand.chancesToWin()
                if not winningChances:
                    hand.player.mayWin = False # bad luck
                else:
                    # winning with OriginalCall is still possible
                    result[Message.Pung] = -999
                    result[Message.Kong] = -999
                    result[Message.Chow] = -999
        return result

class TwofoldFortune(Function):
    @staticmethod
    def appliesToHand(hand):
        return b't' in hand.announcements

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        kungs = [x for x in hand.melds if len(x) == 4]
        return len(kungs) >= 2

class BlessingOfHeaven(Function):
    @staticmethod
    def appliesToHand(hand):
        return hand.ownWind == b'e' and hand.lastSource == b'1'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return (hand.ownWind == b'e'
            and hand.lastSource and hand.lastSource in b'wd'
            and not (Byteset(hand.announcements) - {b'a'}))

class BlessingOfEarth(Function):
    @staticmethod
    def appliesToHand(hand):
        return hand.ownWind != b'e' and hand.lastSource == b'1'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return (hand.ownWind != b'e'
            and hand.lastSource and hand.lastSource in b'wd'
            and not (Byteset(hand.announcements) - {b'a'}))

class LongHand(Function):
    @staticmethod
    def appliesToHand(hand):
        if hand.player:
            game = hand.player.game
            if game:
                if not game.isScoringGame():
                    # never apply to a real game, the program makes sure that we never have
                    # a long hand. Otherwise we would have to check if the player is about
                    # to disard a tile
                    return False
        return (not hand.won and hand.lenOffset > 0) or hand.lenOffset > 1

class FalseDiscardForMJ(Function):
    @staticmethod
    def appliesToHand(hand):
        return not hand.won

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return not hand.won

class DangerousGame(Function):
    @staticmethod
    def appliesToHand(hand):
        return not hand.won

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return not hand.won

class LastOnlyPossible(Function):
    """check if the last tile was the only one possible for winning"""

    def __init__(self):
        Function.__init__(self)
        self.active = False

    def appliesToHand(self, hand):
        if self.active or not hand.lastTile:
            return False
        if any(hand.lastTile in x for x in hand.melds if len(x) == 4):
            # the last tile completed a Kong
            return False
        shortHand = hand - hand.lastTile
        self.active = True
        try:
            otherCallingHands = shortHand.callingHands(excludeTile=hand.lastTile)
            return len(otherCallingHands) == 0
        finally:
            self.active = False

def __scanSelf():
    """for every Function class defined in this module,
    generate an instance and add it to dict Function.functions"""
    if not Function.functions:
        for glob in globals().values():
            if hasattr(glob, "__mro__"):
                if glob.__mro__[-2] == Function and len(glob.__mro__) > 2:
                    name = glob.__name__
                    Function.functions[name] = glob

__scanSelf()
