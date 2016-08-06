# -*- coding: utf-8 -*-

"""Copyright (C) 2009-2014 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from tile import Tile, elements
from meld import Meld, MeldList
from common import IntDict, WINDS
from message import Message
from query import Query
from permutations import Permutations


class RuleCode(object):

    """Parent for all RuleCode classes. A RuleCode class can be used to
    define the behaviour of a Rule. Classes Rule and RuleCode
    are separate because
    - different rulesets may have a Rule with the same name
      but with different behaviour
    - different rulesets may use different names for the same rule
    - the RuleCode class should be as short and as concise
      as possible because this is the important part about
      implementing a new ruleset, and it is the most error prone.

    All methods in RuleCode classes will automatically be converted
    into staticmethods or classmethods if the 1st arg is named 'cls'.
    """

    cache = ()

# pylint: disable=missing-docstring
# the class and method names are mostly self explaining, we do not
# need docstringss

# pylint: disable=no-self-argument, no-self-use, no-value-for-parameter, no-member
# pylint: disable=too-many-function-args, unused-argument, arguments-differ


class DragonPungKong(RuleCode):

    def appliesToMeld(hand, meld):
        return meld.isPungKong and meld.isDragonMeld


class ExposedMinorPung(RuleCode):

    def appliesToMeld(hand, meld):
        return meld.isPung and meld[0].isMinor and meld.isExposed


class ExposedTerminalsPung(RuleCode):

    def appliesToMeld(hand, meld):
        return meld.isExposed and meld[0].isTerminal and meld.isPung


class ExposedHonorsPung(RuleCode):

    def appliesToMeld(hand, meld):
        return meld.isExposed and meld.isHonorMeld and meld.isPung


class ExposedMinorKong(RuleCode):

    def appliesToMeld(hand, meld):
        return meld.isExposed and meld[0].isMinor and meld.isKong


class ExposedTerminalsKong(RuleCode):

    def appliesToMeld(hand, meld):
        return meld.isExposed and meld[0].isTerminal and meld.isKong


class ExposedHonorsKong(RuleCode):

    def appliesToMeld(hand, meld):
        return meld.isExposed and meld.isHonorMeld and meld.isKong


class ConcealedMinorPung(RuleCode):

    def appliesToMeld(hand, meld):
        return meld.isConcealed and meld[0].isMinor and meld.isPung


class ConcealedTerminalsPung(RuleCode):

    def appliesToMeld(hand, meld):
        return meld.isConcealed and meld[0].isTerminal and meld.isPung


class ConcealedHonorsPung(RuleCode):

    def appliesToMeld(hand, meld):
        return meld.isConcealed and meld.isHonorMeld and meld.isPung


class ConcealedMinorKong(RuleCode):

    def appliesToMeld(hand, meld):
        return meld.isConcealed and meld[0].isMinor and meld.isKong


class ConcealedTerminalsKong(RuleCode):

    def appliesToMeld(hand, meld):
        return meld.isConcealed and meld[0].isTerminal and meld.isKong


class ConcealedHonorsKong(RuleCode):

    def appliesToMeld(hand, meld):
        return meld.isConcealed and meld.isHonorMeld and meld.isKong


class OwnWindPungKong(RuleCode):

    def appliesToMeld(hand, meld):
        return meld[0].value == hand.ownWind

    def mayApplyToMeld(meld):
        """for meld rules which depend on context like hand.ownWind, we want
        to know if there could be a context where this rule applies. See
        Meld.rules.
        NOTE: If a rulecode class has mayApplyToMeld, its appliesToMeld can
        assume that mayApplyToMeld has already been checked."""
        return meld.isPungKong and meld.isWindMeld


class OwnWindPair(RuleCode):

    def appliesToMeld(hand, meld):
        return meld[0].value == hand.ownWind

    def mayApplyToMeld(meld):
        return meld.isPair and meld.isWindMeld


class RoundWindPungKong(RuleCode):

    def appliesToMeld(hand, meld):
        return meld[0].value == hand.roundWind

    def mayApplyToMeld(meld):
        return meld.isPungKong and meld.isWindMeld


class RoundWindPair(RuleCode):

    def appliesToMeld(hand, meld):
        return meld[0].value == hand.roundWind

    def mayApplyToMeld(meld):
        return meld.isPair and meld.isWindMeld


class DragonPair(RuleCode):

    def appliesToMeld(hand, meld):
        return meld.isDragonMeld and meld.isPair


class LastTileCompletesPairMinor(RuleCode):

    def appliesToHand(hand):
        return hand.lastMeld and hand.lastMeld.isPair and hand.lastTile.isMinor


class Flower(RuleCode):

    def appliesToMeld(hand, meld):
        return meld.isSingle and meld.group == Tile.flower


class Season(RuleCode):

    def appliesToMeld(hand, meld):
        return meld.isSingle and meld.group == Tile.season


class LastTileCompletesPairMajor(RuleCode):

    def appliesToHand(hand):
        return hand.lastMeld and hand.lastMeld.isPair and hand.lastTile.isMajor


class LastFromWall(RuleCode):

    def appliesToHand(hand):
        return hand.lastTile and hand.lastTile.isConcealed


class ZeroPointHand(RuleCode):

    def appliesToHand(hand):
        return not any(x.meld for x in hand.usedRules if x.meld and len(x.meld) > 1)


class NoChow(RuleCode):

    def appliesToHand(hand):
        return not any(x.isChow for x in hand.melds)


class OnlyConcealedMelds(RuleCode):

    def appliesToHand(hand):
        return not any((x.isExposed and not x.isClaimedKong) for x in hand.melds)


class FalseColorGame(RuleCode):

    def appliesToHand(hand):
        dwSet = set(Tile.honors)
        return dwSet & hand.suits and len(hand.suits - dwSet) == 1


class TrueColorGame(RuleCode):

    def appliesToHand(hand):
        return len(hand.suits) == 1 and hand.suits < set(Tile.colors)


class Purity(RuleCode):

    def appliesToHand(hand):
        return (len(hand.suits) == 1 and hand.suits < set(Tile.colors)
                and not any(x.isChow for x in hand.melds))


class ConcealedTrueColorGame(RuleCode):

    def appliesToHand(hand):
        if len(hand.suits) != 1 or not hand.suits < set(Tile.colors):
            return False
        return not any((x.isExposed and not x.isClaimedKong) for x in hand.melds)


class OnlyMajors(RuleCode):

    def appliesToHand(hand):
        return all(x.isMajor for x in hand.tiles)


class OnlyHonors(RuleCode):

    def appliesToHand(hand):
        return all(x.isHonor for x in hand.tiles)


class HiddenTreasure(RuleCode):

    def appliesToHand(hand):
        return (not any(((x.isExposed and not x.isClaimedKong) or x.isChow) for x in hand.melds)
                and hand.lastTile and hand.lastTile.isConcealed
                and len(hand.melds) == 5)


class BuriedTreasure(RuleCode):

    def appliesToHand(hand):
        return (len(hand.suits - set(Tile.honors)) == 1
                and sum(x.isPung for x in hand.melds) == 4
                and all((x.isPung and x.isConcealed) or x.isPair for x in hand.melds))


class AllTerminals(RuleCode):

    def appliesToHand(hand):
        return all(x.isTerminal for x in hand.tiles)


class StandardMahJongg(RuleCode):
    cache = ('appliesToHand',)

    def computeLastMelds(hand):
        """returns all possible last melds"""
        return MeldList(x for x in hand.melds if hand.lastTile in x and len(x) < 4)

    def appliesToHand(hand):
        """winner rules are not yet applied to hand"""
        # pylint: disable=too-many-return-statements
        # too many return statements
        if len(hand.melds) != 5:
            return False
        if any(len(x) not in (2, 3, 4) for x in hand.melds):
            return False
        if any(x.isRest or x.isKnitted for x in hand.melds):
            return False
        if sum(x.isChow for x in hand.melds) > hand.ruleset.maxChows:
            return False
        if hand.arranged is None:
            # this is only Hand.__arrange
            return True
        if hand.score.total() < hand.ruleset.minMJPoints:
            return False
        if hand.score.doubles >= hand.ruleset.minMJDoubles:
            # shortcut
            return True
        # but maybe we have enough doubles by winning:
        doublingWinnerRules = sum(
            x.rule.score.doubles for x in hand.matchingWinnerRules())
        return hand.score.doubles + doublingWinnerRules >= hand.ruleset.minMJDoubles

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

    def winningTileCandidates(cls, hand):
        # pylint:
        # disable=too-many-locals,too-many-return-statements,too-many-branches,too-many-statements
        if len(hand.melds) > 7:
            # hope 7 is sufficient, 6 was not
            return set()
        if not hand.tilesInHand:
            return set()
        inHand = list(x.exposed for x in hand.tilesInHand)
        result = inHand[:]
        pairs = 0
        isolated = 0
        maxChows = hand.ruleset.maxChows - \
            sum(x.isChow for x in hand.declaredMelds)
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
        for group in hand.suits & set(Tile.colors):
            values = sorted(x.value for x in result if x.group == group)
            changed = True
            while (changed and len(values) > 2
                    and values.count(values[0]) == 1
                    and values.count(values[1]) == 1
                    and values.count(values[2]) == 1):
                changed = False
                if values[0] + 2 == values[2] and (len(values) == 3 or values[3] > values[0] + 3):
                    # logDebug(u'removing first 3 from %s' % values)
                    meld = Tile(group, values[0]).chow
                    for pair in meld:
                        result.remove(pair)
                    melds.append(meld)
                    values = values[3:]
                    changed = True
                elif values[0] + 1 == values[1] and values[2] > values[0] + 2:
                    # logDebug(u'found incomplete chow at start of %s' %
                    # values)
                    return cls.fillChow(group, values[:2])
            changed = True
            while (changed and len(values) > 2
                    and values.count(values[-1]) == 1
                    and values.count(values[-2]) == 1
                    and values.count(values[-3]) == 1):
                changed = False
                if values[-1] - 2 == values[-3] and (len(values) == 3 or values[-4] < values[-1] - 3):
                    meld = Tile(group, values[-3]).chow
                    for pair in meld:
                        result.remove(pair)
                    melds.append(meld)
                    values = values[:-3]
                    changed = True
                elif values[-1] - 1 == values[-2] and values[-3] < values[-1] - 2:
                    # logDebug(u'found incomplete chow at end of %s' % values)
                    return cls.fillChow(group, values[-2:])

            if len(values) % 3 == 0:
                # adding a 4th, 7th or 10th tile with this color can not let us win,
                # so we can exclude this color from the candidates
                result = list(x for x in result if x.group != group)
                continue
            valueSet = set(values)
            if len(values) == 4 and len(values) == len(valueSet):
                if values[0] + 3 == values[-1]:
                    # logDebug(u'seq4 in %s' % hand.tilesInHand)
                    return {Tile(group, values[0]), Tile(group, values[-1])}
            if len(values) == 7 and len(values) == len(valueSet):
                if values[0] + 6 == values[6]:
                    # logDebug(u'seq7 in %s' % hand.tilesInHand)
                    return {Tile(group, values[x]) for x in (0, 3, 6)}
            if len(values) == 1:
                # only a pair of this value is possible
                # logDebug(u'need pair')
                return {Tile(group, values[0]).concealed}
            if len(valueSet) == 1:
                # no chow reachable, only pair/pung
                continue
            singles = set(x for x in valueSet
                          if values.count(x) == 1
                          and not set([x - 1, x - 2, x + 1, x + 2]) & valueSet)
            isolated += len(singles)
            if isolated > 1:
                # this is not a calling hand
                return set()
            if len(values) == 2 and len(valueSet) == 2:
                # exactly two adjacent values: must be completed to Chow
                if maxChows == 0:
                    # not a calling hand
                    return set()
                # logDebug(u'return fillChow for %s' % values)
                return cls.fillChow(group, values)
            if (len(values) == 4 and len(valueSet) == 2
                    and values[0] == values[1] and values[2] == values[3]):
                return {Tile(group, values[0]), Tile(group, values[2])}
            if maxChows:
                for value in valueSet:
                    if value > 1:
                        result.append(Tile(group, value - 1))
                    if value < 9:
                        result.append(Tile(group, value + 1))
        return set(result)

    def shouldTry(hand, maxMissing=10):
        return True

    def rearrange(hand, rest):
        """rest is a list of those tiles that can still
        be rearranged: No declared melds and no bonus tiles.
        done is already arranged, do not change this.
        TODO: also return how many tiles are missing for winning"""
        permutations = Permutations(rest)
        for variantMelds in permutations.variants:
            yield tuple(variantMelds), tuple()


class SquirmingSnake(StandardMahJongg):
    cache = ()

    def appliesToHand(hand):
        cacheKey = (hand.ruleset.standardMJRule.__class__, 'appliesToHand')
        std = hand.ruleCache.get(cacheKey, None)
        if std is False:
            return False
        if len(hand.suits) != 1 or not hand.suits < set(Tile.colors):
            return False
        values = hand.values
        if values.count(1) < 3 or values.count(9) < 3:
            return False
        pairs = [x for x in (2, 5, 8) if values.count(x) == 2]
        if len(pairs) != 1:
            return False
        return len(set(values)) == len(values) - 5

    def winningTileCandidates(hand):
        """they have already been found by the StandardMahJongg rule"""
        return set()


class WrigglingSnake(RuleCode):

    def shouldTry(hand, maxMissing=3):
        if hand.declaredMelds:
            return False
        return (len(set(x.exposed for x in hand.tiles)) + maxMissing > 12
                and all(not x.isChow for x in hand.declaredMelds))

    def computeLastMelds(hand):
        if hand.lastTile.value == 1:
            return [hand.lastTile.pair]
        else:
            return [hand.lastTile.single]

    def winningTileCandidates(hand):
        suits = hand.suits.copy()
        if Tile.wind not in suits or Tile.dragon in suits or len(suits) > 2:
            return set()
        suits -= {Tile.wind}
        group = suits.pop()
        values = set(hand.values)
        if len(values) < 12:
            return set()
        elif len(values) == 12:
            # one of 2..9 or a wind is missing
            if hand.values.count(1) < 2:
                # and the pair of 1 is incomplete too
                return set()
            else:
                return (elements.winds | set([Tile(group, x) for x in range(2, 10)])) \
                    - set([x.exposed for x in hand.tiles])
        else:
            # pair of 1 is not complete
            return set([Tile(group, '1')])

    def rearrange(hand, rest):
        melds = []
        for tileName in rest[:]:
            if rest.count(tileName) >= 2:
                melds.append(tileName.pair)
                rest.remove(tileName)
                rest.remove(tileName)
            elif rest.count(tileName) == 1:
                melds.append(tileName.single)
                rest.remove(tileName)
        yield tuple(melds), tuple(rest)

    def appliesToHand(hand):
        if hand.declaredMelds:
            return False
        suits = hand.suits.copy()
        if Tile.wind not in suits:
            return False
        suits -= {Tile.wind}
        if len(suits) != 1 or not suits < set(Tile.colors):
            return False
        if hand.values.count(1) != 2:
            return False
        return len(set(hand.values)) == 13


class CallingHand(RuleCode):

    def appliesToHand(cls, hand):
        for callHand in hand.callingHands:
            used = list(x.rule.__class__ for x in callHand.usedRules)
            if cls.limitHand in used:
                return True
        return False


class TripleKnitting(RuleCode):

    def computeLastMelds(cls, hand):
        """returns all possible last melds"""
        if not hand.lastTile:
            return
        triples, rest = cls.findTriples(hand)
        assert len(rest) == 2
        triples = list(triples)
        triples.append(rest)
        return [Meld(x) for x in triples if hand.lastTile in x]

    def claimness(cls, hand, discard):
        result = IntDict()
        if cls.shouldTry(hand):
            result[Message.Pung] = -999
            result[Message.Kong] = -999
            result[Message.Chow] = -999
        return result

    def weigh(cls, aiInstance, candidates):
        if cls.shouldTry(candidates.hand):
            _, rest = cls.findTriples(candidates.hand)
            for candidate in candidates:
                if candidate.group in Tile.honors:
                    candidate.keep -= 50
                if rest.count(candidate.tile) > 1:
                    candidate.keep -= 10
        return candidates

    def rearrange(cls, hand, rest):
        melds = []
        for triple in cls.findTriples(hand)[0]:
            melds.append(triple)
            rest.remove(triple[0])
            rest.remove(triple[1])
            rest.remove(triple[2])
        while len(rest) >= 2:
            for value in set(x.value for x in rest):
                suits = set(x.group for x in rest if x.value == value)
                if len(suits) < 2:
                    yield tuple(melds), tuple(rest)
                    return
                pair = (Tile(suits.pop(), value), Tile(suits.pop(), value))
                melds.append(Meld(sorted(pair)))
                rest.remove(pair[0])
                rest.remove(pair[1])
        yield tuple(melds), tuple(rest)

    def appliesToHand(cls, hand):
        if any(x.isHonor for x in hand.tiles):
            return False
        if len(hand.declaredMelds) > 1:
            return False
        if hand.lastTile and hand.lastTile.isConcealed and hand.declaredMelds:
            return False
        triples, rest = cls.findTriples(hand)
        return (len(triples) == 4 and len(rest) == 2
                and rest[0].group != rest[1].group and rest[0].value == rest[1].value)

    def winningTileCandidates(cls, hand):
        if hand.declaredMelds:
            return set()
        if any(x.isHonor for x in hand.tiles):
            return set()
        _, rest = cls.findTriples(hand)
        if len(rest) not in (1, 4):
            return set()
        result = list(
            [Tile(x, y.value).concealed for x in Tile.colors for y in rest])
        for restTile in rest:
            result.remove(restTile)
        return set(result)

    def shouldTry(cls, hand, maxMissing=3):
        if hand.declaredMelds:
            return False
        tripleWanted = 7 - maxMissing // 3  # count triples
        tripleCount = len(cls.findTriples(hand)[0])
        return tripleCount >= tripleWanted

    def findTriples(cls, hand):
        """returns a list of triple knitted melds, including the mj triple.
        Also returns the remaining untripled tiles"""
        if hand.declaredMelds:
            if len(hand.declaredMelds) > 1:
                return (Meld(), None)
        result = []
        tilesS = list(
            x.concealed for x in hand.tiles if x.lowerGroup == Tile.stone)
        tilesB = list(
            x.concealed for x in hand.tiles if x.lowerGroup == Tile.bamboo)
        tilesC = list(
            x.concealed for x in hand.tiles if x.lowerGroup == Tile.character)
        for tileS in tilesS[:]:
            tileB = Tile(Tile.bamboo, tileS.value).concealed
            tileC = Tile(Tile.character, tileS.value).concealed
            if tileB in tilesB and tileC in tilesC:
                tilesS.remove(tileS)
                tilesB.remove(tileB)
                tilesC.remove(tileC)
                result.append(tileS.knitted3)
        return tuple(result), tuple(tilesS + tilesB + tilesC)


class Knitting(RuleCode):

    def computeLastMelds(cls, hand):
        """returns all possible last melds"""
        if not hand.lastTile:
            return []
        couples, rest = cls.findCouples(hand)
        assert not rest, '%s: couples=%s rest=%s' % (
            hand.string, couples, rest)
        return [Meld(x) for x in couples if hand.lastTile in x]

    def claimness(cls, hand, discard):
        result = IntDict()
        if cls.shouldTry(hand):
            result[Message.Pung] = -999
            result[Message.Kong] = -999
            result[Message.Chow] = -999
        return result

    def weigh(cls, aiInstance, candidates):
        if cls.shouldTry(candidates.hand):
            for candidate in candidates:
                if candidate.group in Tile.honors:
                    candidate.keep -= 50
        return candidates

    def shouldTry(cls, hand, maxMissing=4):
        if hand.declaredMelds:
            return False
        pairWanted = 7 - maxMissing // 2  # count pairs
        pairCount = len(cls.findCouples(hand)[0])
        return pairCount >= pairWanted

    def appliesToHand(cls, hand):
        if any(x.isHonor for x in hand.tiles):
            return False
        if len(hand.declaredMelds) > 1:
            return False
        if hand.lastTile and hand.lastTile.isConcealed and hand.declaredMelds:
            return False
        return len(cls.findCouples(hand)[0]) == 7

    def winningTileCandidates(cls, hand):
        if hand.declaredMelds:
            return set()
        if any(x.isHonor for x in hand.tiles):
            return set()
        couples, singleTile = cls.findCouples(hand)
        if len(couples) != 6:
            return set()
        if not singleTile:
            # single tile has wrong suit
            return set()
        assert len(singleTile) == 1
        singleTile = singleTile[0]
        otherSuit = (hand.suits - set([singleTile.lowerGroup])).pop()
        otherTile = Tile(otherSuit, singleTile.value).concealed
        return set([otherTile])

    def rearrange(cls, hand, rest):
        melds = []
        for couple in cls.findCouples(hand, rest)[0]:
            if couple[0].islower():
                # this is the mj pair, lower after claiming
                continue
            melds.append(Meld(couple))
            rest.remove(couple[0])
            rest.remove(couple[1])
        yield tuple(melds), tuple(rest)

    def findCouples(cls, hand, pairs=None):
        """returns a list of tuples, including the mj couple.
        Also returns the remaining uncoupled tiles IF they
        are of the wanted suits"""
        if hand.declaredMelds:
            if len(hand.declaredMelds) > 1 or len(hand.declaredMelds[0]) > 2:
                return [], []
        result = []
        if pairs is None:
            pairs = hand.tiles
        suits = cls.pairSuits(hand)
        if not suits:
            return [], []
        tiles0 = list(x for x in pairs if x.lowerGroup == suits[0])
        tiles1 = list(x for x in pairs if x.lowerGroup == suits[1])
        for tile0 in tiles0[:]:
            if tile0.isExposed:
                tile1 = Tile(suits[1], tile0.value)
            else:
                tile1 = Tile(suits[1], tile0.value).concealed
            if tile1 in tiles1:
                tiles0.remove(tile0)
                tiles1.remove(tile1)
                result.append((tile0, tile1))
        return result, tiles0 + tiles1

    def pairSuits(hand):
        """returns a lowercase string with two suit characters. If no prevalence, returns None"""
        suitCounts = list(len([x for x in hand.tiles if x.lowerGroup == y])
                          for y in set(Tile.colors))
        minSuit = min(suitCounts)
        result = ''.join(
            x for idx,
            x in enumerate(set(Tile.colors)) if suitCounts[idx] > minSuit)
        if len(result) == 2:
            return result


class AllPairHonors(RuleCode):

    def computeLastMelds(hand):
        return [hand.lastTile.pair]

    def claimness(hand, discard):
        result = IntDict()
        if AllPairHonors.shouldTry(hand):
            result[Message.Pung] = -999
            result[Message.Kong] = -999
            result[Message.Chow] = -999
        return result

    def maybeCallingOrWon(hand):
        if any(x.value in Tile.minors for x in hand.tiles):
            return False
        return len(hand.declaredMelds) < 2

    def appliesToHand(cls, hand):
        if not cls.maybeCallingOrWon(hand):
            return False
        if len(set(hand.tiles)) != 7:
            return False
        tileCounts = list([len([x for x in hand.tiles if x == y])
                          for y in hand.tiles])
        return set(tileCounts) == set([2])

    def winningTileCandidates(cls, hand):
        if not cls.maybeCallingOrWon(hand):
            return set()
        single = list(x for x in hand.tiles if hand.tiles.count(x) == 1)
        if len(single) != 1:
            return set()
        return set(single)

    def shouldTry(hand, maxMissing=4):
        if hand.declaredMelds:
            return False
        tiles = list(x.exposed for x in hand.tiles)
        pairCount = kongCount = 0
        for tile in elements.majors:
            count = tiles.count(tile)
            if count == 2:
                pairCount += 1
            elif count == 4:
                kongCount += 1
        pairWanted = 7 - maxMissing // 2  # count pairs
        result = pairCount >= pairWanted or (
            pairCount + kongCount * 2) > pairWanted
        return result

    def rearrange(hand, rest):
        melds = []
        for pair in set(rest) & elements.mAJORS:
            while rest.count(pair) >= 2:
                melds.append(pair.pair)
                rest.remove(pair)
                rest.remove(pair)
        yield tuple(melds), tuple(rest)

    def weigh(aiInstance, candidates):
        hand = candidates.hand
        if not AllPairHonors.shouldTry(hand):
            return candidates
        keep = 10
        for candidate in candidates:
            if candidate.value in Tile.minors:
                candidate.keep -= keep
            else:
                if candidate.occurrence == 3:
                    candidate.keep -= keep / 2
                else:
                    candidate.keep += keep
        return candidates


class FourfoldPlenty(RuleCode):

    def appliesToHand(hand):
        return len(hand.tiles) == 18


class ThreeGreatScholars(RuleCode):

    def appliesToHand(cls, hand):
        return (BigThreeDragons.appliesToHand(hand)
                and ('nochow' not in cls.options or not any(x.isChow for x in hand.melds)))


class BigThreeDragons(RuleCode):

    def appliesToHand(hand):
        return len([x for x in hand.melds if x.isDragonMeld and x.isPungKong]) == 3


class BigFourJoys(RuleCode):

    def appliesToHand(hand):
        return len([x for x in hand.melds if x.isWindMeld and x.isPungKong]) == 4


class LittleFourJoys(RuleCode):

    def appliesToHand(hand):
        lengths = sorted([min(len(x), 3) for x in hand.melds if x.isWindMeld])
        return lengths == [2, 3, 3, 3]


class LittleThreeDragons(RuleCode):

    def appliesToHand(hand):
        lengths = sorted([min(len(x), 3)
                         for x in hand.melds if x.isDragonMeld])
        return lengths == [2, 3, 3]


class FourBlessingsHoveringOverTheDoor(RuleCode):

    def appliesToHand(hand):
        return len([x for x in hand.melds if x.isPungKong and x.isWindMeld]) == 4


class AllGreen(RuleCode):

    def appliesToHand(hand):
        return set(x.exposed for x in hand.tiles) < elements.greenHandTiles


class LastTileFromWall(RuleCode):

    def appliesToHand(hand):
        return hand.lastSource == 'w'


class LastTileFromDeadWall(RuleCode):

    def appliesToHand(hand):
        return hand.lastSource == 'e'

    def selectable(hand):
        """for scoring game"""
        return hand.lastSource == 'w'


class IsLastTileFromWall(RuleCode):

    def appliesToHand(hand):
        return hand.lastSource == 'z'

    def selectable(hand):
        """for scoring game"""
        return hand.lastSource == 'w'


class IsLastTileFromWallDiscarded(RuleCode):

    def appliesToHand(hand):
        return hand.lastSource == 'Z'

    def selectable(hand):
        """for scoring game"""
        return hand.lastSource == 'd'


class RobbingKong(RuleCode):

    def appliesToHand(hand):
        return hand.lastSource == 'k'

    def selectable(hand):
        """for scoring game"""
        return (hand.lastSource and hand.lastSource in 'kwd'
                and hand.lastTile and hand.lastTile.group.islower()
                and [x.exposed for x in hand.tiles].count(hand.lastTile.exposed) < 2)


class GatheringPlumBlossomFromRoof(RuleCode):

    def appliesToHand(hand):
        return LastTileFromDeadWall.appliesToHand(hand) and hand.lastTile is Tile(Tile.stone, '5').concealed


class PluckingMoon(RuleCode):

    def appliesToHand(hand):
        return IsLastTileFromWall.appliesToHand(hand) and hand.lastTile is Tile(Tile.stone, '1').concealed


class ScratchingPole(RuleCode):

    def appliesToHand(hand):
        return RobbingKong.appliesToHand(hand) and hand.lastTile is Tile(Tile.bamboo, '2')


class StandardRotation(RuleCode):

    def rotate(game):
        return game.winner and game.winner.wind != 'E'


class EastWonNineTimesInARow(RuleCode):
    nineTimes = 9

    def appliesToHand(cls, hand):
        return cls.appliesToGame(hand.player.game)

    def appliesToGame(cls, game, needWins=None):
        if needWins is None:
            needWins = EastWonNineTimesInARow.nineTimes
            if game.isScoringGame():
                # we are only proposing for the last needed Win
                needWins -= 1
        if game.winner and game.winner.wind == 'E' and game.notRotated >= needWins:
            prevailing = WINDS[game.roundsFinished % 4]
            eastMJCount = int(Query("select count(1) from score "
                                    "where game=%d and won=1 and wind='E' and player=%d "
                                    "and prevailing='%s'" %
                                    (game.gameid, game.players['E'].nameid, prevailing)).records[0][0])
            return eastMJCount == needWins
        return False

    def rotate(cls, game):
        return cls.appliesToGame(game, needWins=EastWonNineTimesInARow.nineTimes)


class GatesOfHeaven(StandardMahJongg):
    cache = ()

# FIXME: computeLastMelds must return a real meld
# FIXME: in BMJA, 111 and 999 must be concealed, we do not check this
    def computeLastMelds(hand):
        return [hand.lastTile.single]

    def shouldTry(hand, maxMissing=3):
        if hand.declaredMelds:
            return False
        for suit in Tile.colors:
            count19 = sum(x.isTerminal for x in hand.tiles)
            suitCount = len(
                list(x for x in hand.tiles if x.lowerGroup == suit))
            if suitCount > 10 and count19 > 4:
                return True
        return False

    def maybeCallingOrWon(hand):
        if len(hand.suits) != 1 or not hand.suits < set(Tile.colors):
            return False
        return not hand.declaredMelds

    def appliesToHand(cls, hand):
        if not cls.maybeCallingOrWon(hand):
            return False
        values = hand.values
        if len(set(values)) < 9 or values.count(1) != 3 or values.count(9) != 3:
            return False
        values = list(values[3:-3])
        for value in Tile.minors:
            if value in values:
                values.remove(value)
        if len(values) != 1:
            return False
        surplus = values[0]
        if 'pair28' in cls.options:
            return 1 < surplus < 9
        if 'lastExtra' in cls.options:
            return hand.lastTile and surplus == hand.lastTile.value
        return True

    def winningTileCandidates(cls, hand):
        result = set()
        if not cls.maybeCallingOrWon(hand):
            return result
        values = hand.values
        if len(set(values)) == 8:
            # one minor is missing
            result = set(Tile.minors) - set(values)
        else:
            # we have something of all values
            if values.count(1) != 3:
                result = (1,)
            elif values.count(9) != 3:
                result = (9,)
            else:
                if 'pair28' in cls.options:
                    result = Tile.minors
                else:
                    result = Tile.numbers
        return {Tile(list(hand.suits)[0], x) for x in result}

    def rearrange(hand, rest):
        melds = []
        for suit in hand.suits:
            for value in Tile.numbers:
                tile = Tile(suit, value).concealed
                if rest.count(tile) == 3 and tile.isTerminal:
                    melds.append(tile.pung)
                    rest.remove(tile)
                    rest.remove(tile)
                    rest.remove(tile)
                elif rest.count(tile) == 2:
                    melds.append(tile.pair)
                    rest.remove(tile)
                    rest.remove(tile)
                elif rest.count(tile) == 1:
                    melds.append(tile.single)
                    rest.remove(tile)
            break
        yield tuple(melds), tuple(rest)


class ThirteenOrphans(RuleCode):

    def computeLastMelds(hand):
        meldSize = hand.tilesInHand.count(hand.lastTile)
        if meldSize == 0:
            # the last tile is called and not yet in the hand
            return [Meld()]
        return [hand.lastTile.meld(meldSize)]

    def rearrange(hand, rest):
        melds = []
        for tileName in rest:
            if rest.count(tileName) >= 2:
                melds.append(tileName.pair)
                rest.remove(tileName)
                rest.remove(tileName)
            elif rest.count(tileName) == 1:
                melds.append(tileName.single)
                rest.remove(tileName)
        yield tuple(melds), tuple(rest)

    def claimness(cls, hand, discard):
        result = IntDict()
        if cls.shouldTry(hand):
            doublesCount = hand.doublesEstimate(discard)
# TODO: compute scoring for resulting hand. If it is high anyway,
# prefer pung over trying 13 orphans
            if doublesCount < 2 or cls.shouldTry(hand, 1):
                result[Message.Pung] = -999
                result[Message.Kong] = -999
                result[Message.Chow] = -999
        return result

    def appliesToHand(hand):
        return set(x.exposed for x in hand.tiles) == elements.majors

    def winningTileCandidates(cls, hand):
        if any(x in hand.values for x in Tile.minors):
            # no minors allowed
            return set()
        if not cls.shouldTry(hand, 1):
            return set()
        handTiles = set(x.exposed for x in hand.tiles)
        missing = elements.majors - handTiles
        if len(missing) == 0:
            # if all 13 tiles are there, we need any one of them:
            return elements.majors
        else:
            assert len(missing) == 1
            return missing

    def shouldTry(hand, maxMissing=4):
        # TODO: look at how many tiles there still are on the wall
        if hand.declaredMelds:
            return False
        handTiles = set(x.exposed for x in hand.tiles)
        missing = elements.majors - handTiles
        if len(missing) > maxMissing:
            return False
        for missingTile in missing:
            if not hand.player.tileAvailable(missingTile, hand):
                return False
        return True

    def weigh(cls, aiInstance, candidates):
        hand = candidates.hand
        if not cls.shouldTry(hand):
            return candidates
        handTiles = set(x.exposed for x in hand.tiles)
        missing = elements.majors - handTiles
        havePair = False
        keep = (6 - len(missing)) * 5
        for candidate in candidates:
            if candidate.value in Tile.minors:
                candidate.keep -= keep
            else:
                if havePair and candidate.occurrence >= 2:
                    candidate.keep -= keep
                else:
                    candidate.keep += keep
                havePair = candidate.occurrence == 2
        return candidates


class OwnFlower(RuleCode):

    def appliesToMeld(hand, meld):
        return meld[0].value == hand.ownWind

    def mayApplyToMeld(meld):
        return meld.isBonus and meld[0].group == Tile.flower


class OwnSeason(RuleCode):

    def appliesToMeld(hand, meld):
        return meld[0].value == hand.ownWind

    def mayApplyToMeld(meld):
        return meld.isBonus and meld[0].group == Tile.season


class OwnFlowerOwnSeason(RuleCode):

    def appliesToHand(hand):
        return sum(x.isBonus and x[0].value == hand.ownWind for x in hand.bonusMelds) == 2


class AllFlowers(RuleCode):

    def appliesToHand(hand):
        return len([x for x in hand.bonusMelds if x.group == Tile.flower]) == 4


class AllSeasons(RuleCode):

    def appliesToHand(hand):
        return len([x for x in hand.bonusMelds if x.group == Tile.season]) == 4


class ThreeConcealedPongs(RuleCode):

    def appliesToHand(hand):
        return len([x for x in hand.melds if (
            x.isConcealed or x.isClaimedKong) and x.isPungKong]) >= 3


class MahJonggWithOriginalCall(RuleCode):

    def appliesToHand(hand):
        return ('a' in hand.announcements
                and sum(x.isExposed for x in hand.melds) < 3)

    def selectable(hand):
        """for scoring game"""
        # one tile may be claimed before declaring OC and one for going MJ
        # the previous regex was too strict
        return sum(x.isExposed for x in hand.melds) < 3

    def claimness(hand, discard):
        result = IntDict()
        player = hand.player
        if player.originalCall and player.mayWin:
            if player.originalCallingHand.chancesToWin():
                # winning with OriginalCall is still possible
                result[Message.Pung] = -999
                result[Message.Kong] = -999
                result[Message.Chow] = -999
            else:
                player.mayWin = False  # bad luck
        return result


class TwofoldFortune(RuleCode):

    def appliesToHand(hand):
        return 't' in hand.announcements

    def selectable(hand):
        """for scoring game"""
        kungs = [x for x in hand.melds if len(x) == 4]
        return len(kungs) >= 2


class BlessingOfHeaven(RuleCode):

    def appliesToHand(hand):
        return hand.ownWind == Tile.east and hand.lastSource == '1'

    def selectable(hand):
        """for scoring game"""
        return (hand.ownWind == Tile.east
                and hand.lastSource and hand.lastSource in 'wd'
                and not set(hand.announcements) - {'a'})


class BlessingOfEarth(RuleCode):

    def appliesToHand(hand):
        return hand.ownWind != Tile.east and hand.lastSource == '1'

    def selectable(hand):
        """for scoring game"""
        return (hand.ownWind != Tile.east
                and hand.lastSource and hand.lastSource in 'wd'
                and not set(hand.announcements) - {'a'})


class LongHand(RuleCode):

    def appliesToHand(hand):
        return (not hand.won and hand.lenOffset > 0) or hand.lenOffset > 1


class FalseDiscardForMJ(RuleCode):

    def appliesToHand(hand):
        return not hand.won

    def selectable(hand):
        """for scoring game"""
        return not hand.won


class DangerousGame(RuleCode):

    def appliesToHand(hand):
        return not hand.won

    def selectable(hand):
        """for scoring game"""
        return not hand.won


class LastOnlyPossible(RuleCode):

    """check if the last tile was the only one possible for winning"""
    def appliesToHand(cls, hand):
        if not hand.lastTile:
            return False
        if any(hand.lastTile in x for x in hand.melds if len(x) == 4):
            # the last tile completed a Kong
            return False
        shortHand = hand - hand.lastTile
        return len(shortHand.callingHands) == 1
