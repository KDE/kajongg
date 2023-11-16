#pylint: disable=too-many-lines
# -*- coding: utf-8 -*-

"""Copyright (C) 2009-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

from typing import Tuple, List, Set, Generator, Optional, TYPE_CHECKING, Union

# we disable those because of our automatic conversion to classmethod/staticmethod
# mypy: disable-error-code="misc, override, call-arg, arg-type"

from tile import Tile, TileList, elements, Meld, MeldList
from tilesource import TileSource
from common import IntDict
from wind import East
from message import Message
from query import Query
from permutations import Permutations

if TYPE_CHECKING:
    from hand import Hand
    from game import PlayingGame
    from tile import Tiles
    from intelligence import AIDefaultAI, DiscardCandidates


# pylint:disable=missing-function-docstring,missing-class-docstring
# the class and method names are mostly self explaining, we do not
# need docstringss
# pylint: disable=no-self-argument,no-member
# pylint: disable=too-many-function-args, unused-argument, arguments-differ


class RuleCode:

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

    winningTileCandidates(cls, hand:'Hand'):
        All rules for going MahJongg must have such a method.
        This is used to find all winning hands which only need
        one tile: The calling hands (after calling)

    """

    cache = ()

    def appliesToHand(self, hand:'Hand') ->bool:
        """returns true if this applies to hand"""
        return False

class MJRule(RuleCode):

    def computeLastMelds(hand:'Hand') ->MeldList:
        """return all possible last melds"""
        return MeldList()

    def shouldTry(hand:'Hand', maxMissing:int=10) ->bool:
        return True

    def rearrange(cls, hand:'Hand', rest:Union[TileList,
        List[Tile]]) ->Generator[Tuple[MeldList, TileList], None, None]:
        """rest is a list of those tiles that can still
        be rearranged: No declared melds and no bonus tiles.
        done is already arranged, do not change this.
        TODO: also return how many tiles are missing for winning"""
        permutations = Permutations(rest)
        for variantMelds in permutations.variants:
            yield variantMelds, TileList()


class DragonPungKong(RuleCode):

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        return meld.isPungKong and meld.isDragonMeld


class ExposedMinorPung(RuleCode):

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        return meld.isPung and meld[0].isMinor and meld.isExposed


class ExposedTerminalsPung(RuleCode):

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        return meld.isExposed and meld[0].isTerminal and meld.isPung


class ExposedHonorsPung(RuleCode):

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        return meld.isExposed and meld.isHonorMeld and meld.isPung


class ExposedMinorKong(RuleCode):

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        return meld.isExposed and meld[0].isMinor and meld.isKong


class ExposedTerminalsKong(RuleCode):

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        return meld.isExposed and meld[0].isTerminal and meld.isKong


class ExposedHonorsKong(RuleCode):

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        return meld.isExposed and meld.isHonorMeld and meld.isKong


class ConcealedMinorPung(RuleCode):

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        return meld.isConcealed and meld[0].isMinor and meld.isPung


class ConcealedTerminalsPung(RuleCode):

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        return meld.isConcealed and meld[0].isTerminal and meld.isPung


class ConcealedHonorsPung(RuleCode):

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        return meld.isConcealed and meld.isHonorMeld and meld.isPung


class ConcealedMinorKong(RuleCode):

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        return meld.isConcealed and meld[0].isMinor and meld.isKong


class ConcealedTerminalsKong(RuleCode):

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        return meld.isConcealed and meld[0].isTerminal and meld.isKong


class ConcealedHonorsKong(RuleCode):

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        return meld.isConcealed and meld.isHonorMeld and meld.isKong


class OwnWindPungKong(RuleCode):

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        assert hand
        return meld[0].value is hand.ownWind

    def mayApplyToMeld(meld:Meld) ->bool:
        """for meld rules which depend on context like hand.ownWind, we want
        to know if there could be a context where this rule applies. See
        Meld.rules.
        NOTE: If a rulecode class has mayApplyToMeld, its appliesToMeld can
        assume that mayApplyToMeld has already been checked."""
        return meld.isPungKong and meld.isWindMeld


class OwnWindPair(RuleCode):

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        assert hand
        return meld[0].value is hand.ownWind

    def mayApplyToMeld(meld:Meld) ->bool:
        return meld.isPair and meld.isWindMeld


class RoundWindPungKong(RuleCode):

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        assert hand
        return meld[0].value is hand.roundWind

    def mayApplyToMeld(meld:Meld) ->bool:
        return meld.isPungKong and meld.isWindMeld


class RoundWindPair(RuleCode):

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        assert hand
        return meld[0].value is hand.roundWind

    def mayApplyToMeld(meld:Meld) ->bool:
        return meld.isPair and meld.isWindMeld


class DragonPair(RuleCode):

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        return meld.isDragonMeld and meld.isPair


class LastTileCompletesPairMinor(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        if hand.lastMeld is None:
            return False
        return hand.lastMeld.isPair and hand.lastTile.isMinor


class Flower(RuleCode):

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        return meld.isSingle and meld.group == Tile.flower


class Season(RuleCode):

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        return meld.isSingle and meld.group == Tile.season


class LastTileCompletesPairMajor(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        if hand.lastMeld is None:
            return False
        return bool(hand.lastMeld) and hand.lastMeld.isPair and hand.lastTile.isMajor


class LastFromWall(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return bool(hand.lastTile) and hand.lastTile.isConcealed


class ZeroPointHand(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return not any(x.meld for x in hand.usedRules if x.meld and len(x.meld) > 1)


class NoChow(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return not any(x.isChow for x in hand.melds)


class OnlyConcealedMelds(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return not any((x.isExposed and not x.isClaimedKong) for x in hand.melds)


class FalseColorGame(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        dwSet = set(Tile.honors)
        return bool(dwSet & hand.suits) and len(hand.suits - dwSet) == 1


class TrueColorGame(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return len(hand.suits) == 1 and hand.suits < set(Tile.colors)


class Purity(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return (len(hand.suits) == 1 and hand.suits < set(Tile.colors)
                and not any(x.isChow for x in hand.melds))


class ConcealedTrueColorGame(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        if len(hand.suits) != 1 or hand.suits >= set(Tile.colors):
            return False
        return not any((x.isExposed and not x.isClaimedKong) for x in hand.melds)


class OnlyMajors(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return all(x.isMajor for x in hand.tiles)


class OnlyHonors(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return all(x.isHonor for x in hand.tiles)


class HiddenTreasure(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return (not any(((x.isExposed and not x.isClaimedKong) or x.isChow) for x in hand.melds)
                and bool(hand.lastTile) and hand.lastTile.isConcealed
                and len(hand.melds) == 5)


class BuriedTreasure(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return (len(hand.suits - set(Tile.honors)) == 1
                and sum(x.isPung for x in hand.melds) == 4
                and all((x.isPung and x.isConcealed) or x.isPair for x in hand.melds))


class AllTerminals(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return all(x.isTerminal for x in hand.tiles)


class StandardMahJongg(MJRule):

    cache = ('appliesToHand',)

    def computeLastMelds(hand:'Hand') ->MeldList:
        """return all possible last melds"""
        return MeldList(x for x in hand.melds if hand.lastTile in x and len(x) < 4)

    def appliesToHand(hand:'Hand') ->bool:
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
        assert hand.score
        if hand.score.total() < hand.ruleset.minMJPoints:
            return False
        if hand.score.doubles >= hand.ruleset.minMJDoubles:
            # shortcut
            return True
        # but maybe we have enough doubles by winning:
        doublingWinnerRules = sum(
            x.rule.score.doubles for x in hand.matchingWinnerRules())
        return hand.score.doubles + doublingWinnerRules >= hand.ruleset.minMJDoubles

    def fillChow(group:str, values:List[int]) ->Set[Tile]:
        val0, val1 = values
        if val0 + 1 == val1:
            if val0 == 1:
                return {Tile(group, val0 + 2)}
            if val0 == 8:
                return {Tile(group, val0 - 1)}
            return {Tile(group, val0 - 1), Tile(group, val0 + 2)}
        assert val0 + 2 == val1, 'group:%s values:%s' % (group, values)
        return {Tile(group, val0 + 1)}

    def winningTileCandidates(cls, hand:'Hand') ->Set[Tile]:
        # pylint: disable=too-many-locals,too-many-return-statements,too-many-branches,too-many-statements
        if len(hand.melds) > 7:
            # hope 7 is sufficient, 6 was not
            return set()
        if not hand.tilesInHand:
            return set()
        inHand = [x.exposed for x in hand.tilesInHand]
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
        for group in sorted(hand.suits & set(Tile.colors)):
            values = sorted(x.value for x in result if x.group == group)
            changed = True
            while (changed and len(values) > 2
                   and values.count(values[0]) == 1
                   and values.count(values[1]) == 1
                   and values.count(values[2]) == 1):
                changed = False
                if values[0] + 2 == values[2] and (len(values) == 3 or values[3] > values[0] + 3):
                    # logDebug('removing first 3 from %s' % values)
                    meld = Tile(group, values[0]).chow
                    assert meld
                    # must be a pylint bug. meld is TileList is list
                    for pair in meld:
                        result.remove(pair)
                    melds.append(meld)
                    values = values[3:]
                    changed = True
                elif values[0] + 1 == values[1] and values[2] > values[0] + 2:
                    # logDebug('found incomplete chow at start of %s' %
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
                    assert meld
                    # must be a pylint bug. meld is TileList is list
                    for pair in meld:
                        result.remove(pair)
                    melds.append(meld)
                    values = values[:-3]
                    changed = True
                elif values[-1] - 1 == values[-2] and values[-3] < values[-1] - 2:
                    # logDebug('found incomplete chow at end of %s' % values)
                    return cls.fillChow(group, values[-2:])

            if len(values) % 3 == 0:
                # adding a 4th, 7th or 10th tile with this color can not let us win,
                # so we can exclude this color from the candidates
                result = [x for x in result if x.group != group]
                continue
            valueSet = set(values)
            if len(values) == 4 and len(values) == len(valueSet):
                if values[0] + 3 == values[-1]:
                    # logDebug('seq4 in %s' % hand.tilesInHand)
                    return {Tile(group, values[0]), Tile(group, values[-1])}
            if len(values) == 7 and len(values) == len(valueSet):
                if values[0] + 6 == values[6]:
                    # logDebug('seq7 in %s' % hand.tilesInHand)
                    return {Tile(group, values[x]) for x in (0, 3, 6)}
            if len(values) == 1:
                # only a pair of this value is possible
                # logDebug('need pair')
                return {Tile(group, values[0]).concealed}
            if len(valueSet) == 1:
                # no chow reachable, only pair/pung
                continue
            singles = {x for x in valueSet
                       if values.count(x) == 1
                       and not {x - 1, x - 2, x + 1, x + 2} & valueSet}
            isolated += len(singles)
            if isolated > 1:
                # this is not a calling hand
                return set()
            if len(values) == 2 and len(valueSet) == 2:
                # exactly two adjacent values: must be completed to Chow
                if maxChows == 0:
                    # not a calling hand
                    return set()
                # logDebug('return fillChow for %s' % values)
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


class SquirmingSnake(StandardMahJongg):
    cache = ()

    def appliesToHand(hand:'Hand') ->bool:
        cacheKey = (hand.ruleset.standardMJRule.__class__, 'appliesToHand')
        std = hand.ruleCache.get(cacheKey, None)
        if std is False:
            return False
        if len(hand.suits) != 1 or hand.suits >= set(Tile.colors):
            return False
        values = hand.values
        if values.count(1) < 3 or values.count(9) < 3:
            return False
        pairs = [x for x in (2, 5, 8) if values.count(x) == 2]
        if len(pairs) != 1:
            return False
        return len(set(values)) == len(values) - 5

    def winningTileCandidates(hand:'Hand') ->Set[Tile]:
        """they have already been found by the StandardMahJongg rule"""
        return set()


class WrigglingSnake(MJRule):

    def shouldTry(hand:'Hand', maxMissing:int=3) ->bool:
        if hand.declaredMelds:
            return False
        return (len({x.exposed for x in hand.tiles}) + maxMissing > 12
                and all(not x.isChow for x in hand.declaredMelds))

    def computeLastMelds(hand:'Hand') ->MeldList:
        if not hand.lastTile:
            return MeldList()
        _ = Tile(hand.lastTile)
        return MeldList(_.pair) if hand.lastTile.value == 1 else MeldList(_.single)

    def winningTileCandidates(hand:'Hand') ->Set[Tile]:
        suits = hand.suits.copy()
        if Tile.wind not in suits or Tile.dragon in suits or len(suits) > 2:
            return set()
        suits -= {Tile.wind}
        if not suits:
            return set()
        group = suits.pop()
        values = set(hand.values)
        if len(values) < 12:
            return set()
        if len(values) == 12:
            # one of 2..9 or a wind is missing
            if hand.values.count(1) < 2:
                # and the pair of 1 is incomplete too
                return set()
            return (elements.winds | {Tile(group, x) for x in range(2, 10)}) \
                - {x.exposed for x in hand.tiles}
        # pair of 1 is not complete
        return {Tile(group, '1')}

    def rearrange(cls, hand:'Hand', rest:Union[TileList,
        List[Tile]]) ->Generator[Tuple[MeldList, TileList], None, None]:
        melds = MeldList()
        for tileName in rest[:]:
            if rest.count(tileName) >= 2:
                melds.append(tileName.pair)
                rest.remove(tileName)
                rest.remove(tileName)
            elif rest.count(tileName) == 1:
                melds.append(tileName.single)
                rest.remove(tileName)
        yield melds, rest

    def appliesToHand(hand:'Hand') ->bool:
        if hand.declaredMelds:
            return False
        suits = hand.suits.copy()
        if Tile.wind not in suits:
            return False
        suits -= {Tile.wind}
        if len(suits) != 1 or suits >= set(Tile.colors):
            return False
        if hand.values.count(1) != 2:
            return False
        return len(set(hand.values)) == 13


class CallingHand(RuleCode):

    def appliesToHand(cls, hand:'Hand') ->bool:  # pylint:disable=arguments-renamed
        for callHand in hand.callingHands:
            used = (x.rule.__class__ for x in callHand.usedRules)
            assert hasattr(cls, 'limitHand')
            if cls.limitHand in used:
                return True
        return False


class TripleKnitting(MJRule):

    def computeLastMelds(cls, hand:'Hand') ->MeldList:
        """return all possible last melds"""
        if not hand.lastTile:
            return MeldList()
        triples, rest = cls.findTriples(hand)
        assert len(rest) == 2
        triples.append(Meld(rest))
        return MeldList(Meld(x) for x in triples if hand.lastTile in x)

    def claimness(cls, hand:'Hand', discard:Optional[Tile]) ->IntDict:
        result = IntDict()
        if cls.shouldTry(hand):
            result[Message.Pung] = -999
            result[Message.Kong] = -999
            result[Message.Chow] = -999
        return result

    def weigh(cls, aiInstance:'AIDefaultAI', candidates:'DiscardCandidates') ->'DiscardCandidates':
        if cls.shouldTry(candidates.hand):
            _, rest = cls.findTriples(candidates.hand)
            for candidate in candidates:
                if candidate.group in Tile.honors:
                    candidate.keep -= 50
                if rest.count(candidate.tile) > 1:
                    candidate.keep -= 10
        return candidates

    def rearrange(cls, hand:'Hand', rest:Union[TileList,
        List[Tile]]) ->Generator[Tuple[MeldList, TileList], None, None]:
        melds = MeldList()
        for triple in cls.findTriples(hand)[0]:
            melds.append(triple)
            rest.remove(triple[0])
            rest.remove(triple[1])
            rest.remove(triple[2])
        while len(rest) >= 2:
            for tile in sorted(set(rest)):
                value = tile.value
                suits = {x.group for x in rest if x.value == value}
                if len(suits) < 2:
                    yield melds, rest
                    return
                pair = (Tile(suits.pop(), value), Tile(suits.pop(), value))
                melds.append(Meld(sorted(pair)))
                rest.remove(pair[0])
                rest.remove(pair[1])
        yield melds, rest

    def appliesToHand(cls, hand:'Hand') ->bool:  # pylint:disable=arguments-renamed
        if any(x.isHonor for x in hand.tiles):
            return False
        if len(hand.declaredMelds) > 1:
            return False
        if hand.lastTile and hand.lastTile.isConcealed and hand.declaredMelds:
            return False
        triples, rest = cls.findTriples(hand)
        return (len(triples) == 4 and len(rest) == 2
                and rest[0].group != rest[1].group and rest[0].value == rest[1].value)

    def winningTileCandidates(cls, hand:'Hand') ->Set[Tile]:
        if hand.declaredMelds:
            return set()
        if any(x.isHonor for x in hand.tiles):
            return set()
        _, rest = cls.findTriples(hand)
        if len(rest) not in (1, 4):
            return set()
        result = list(
            Tile(x, y.value).concealed for x in Tile.colors for y in rest)
        for restTile in rest:
            result.remove(restTile)
        return set(result)

    def shouldTry(cls, hand:'Hand', maxMissing:int=3) ->bool:  # pylint:disable=arguments-renamed
        if hand.declaredMelds:
            return False
        tripleWanted = 4 - maxMissing // 3  # count triples
        tripleCount = len(cls.findTriples(hand)[0])
        return tripleCount >= tripleWanted

    def findTriples(hand:'Hand') ->Tuple[MeldList, TileList]:
        """return a list of triple knitted melds, including the mj triple.
        Also returns the remaining untripled tiles"""
        if hand.declaredMelds:
            if len(hand.declaredMelds) > 1:
                return MeldList(), TileList()
        result = MeldList()
        tilesS = [x.concealed for x in hand.tiles if x.lowerGroup == Tile.stone]
        tilesB = [x.concealed for x in hand.tiles if x.lowerGroup == Tile.bamboo]
        tilesC = [x.concealed for x in hand.tiles if x.lowerGroup == Tile.character]
        for tileS in tilesS[:]:
            tileB = Tile(Tile.bamboo, tileS.value).concealed
            tileC = Tile(Tile.character, tileS.value).concealed
            if tileB in tilesB and tileC in tilesC:
                tilesS.remove(tileS)
                tilesB.remove(tileB)
                tilesC.remove(tileC)
                result.append(tileS.knitted3)
        return result, TileList(tilesS + tilesB + tilesC)


class Knitting(MJRule):

    def computeLastMelds(cls, hand:'Hand') ->MeldList:
        """return all possible last melds"""
        if not hand.lastTile:
            return MeldList()
        couples, rest = cls.findCouples(hand)
        assert not rest, '%s: couples=%s rest=%s' % (
            hand.string, couples, rest)
        return MeldList(Meld(x) for x in couples if hand.lastTile in x)

    def claimness(cls, hand:'Hand', discard:Optional[Tile]) ->IntDict:
        result = IntDict()
        if cls.shouldTry(hand):
            result[Message.Pung] = -999
            result[Message.Kong] = -999
            result[Message.Chow] = -999
        return result

    def weigh(cls, aiInstance:'AIDefaultAI', candidates:'DiscardCandidates') ->'DiscardCandidates':
        if cls.shouldTry(candidates.hand):
            for candidate in candidates:
                if candidate.group in Tile.honors:
                    candidate.keep -= 50
        return candidates

    def shouldTry(cls, hand:'Hand', maxMissing:int=4) ->bool:  # pylint:disable=arguments-renamed
        if hand.declaredMelds:
            return False
        pairWanted = 7 - maxMissing // 2  # count pairs
        pairCount = len(cls.findCouples(hand)[0])
        return pairCount >= pairWanted

    def appliesToHand(cls, hand:'Hand') ->bool:  # pylint:disable=arguments-renamed
        if any(x.isHonor for x in hand.tiles):
            return False
        if len(hand.declaredMelds) > 1:
            return False
        if hand.lastTile and hand.lastTile.isConcealed and hand.declaredMelds:
            return False
        return len(cls.findCouples(hand)[0]) == 7

    def winningTileCandidates(cls, hand:'Hand') ->Set[Tile]:
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
        tile = singleTile[0]
        otherSuit = (hand.suits - {tile.lowerGroup}).pop()
        otherTile = Tile(otherSuit, tile.value).concealed
        return {otherTile}

    def rearrange(cls, hand:'Hand', rest:Union[TileList,
        List[Tile]]) ->Generator[Tuple[MeldList, TileList], None, None]:
        melds = MeldList()
        for couple in cls.findCouples(hand, rest)[0]:
            if couple[0].isExposed:
                # this is the mj pair, lower after claiming
                continue
            melds.append(Meld(couple))
            rest.remove(couple[0])
            rest.remove(couple[1])
        yield melds, rest

    def findCouples(cls, hand:'Hand', pairs:TileList=TileList()) ->Tuple[MeldList, TileList]:
        """return a list of tuples, including the mj couple.
        Also returns the remaining uncoupled tiles IF they
        are of the wanted suits"""
        if hand.declaredMelds:
            if len(hand.declaredMelds) > 1 or len(hand.declaredMelds[0]) > 2:
                return MeldList(), TileList()
        result = MeldList()
        if not pairs:
            pairs = hand.tiles
        suits = cls.pairSuits(hand)
        if not suits:
            return MeldList(), TileList()
        tiles0 = TileList(x for x in pairs if x.lowerGroup == suits[0])
        tiles1 = TileList(x for x in pairs if x.lowerGroup == suits[1])
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

    def pairSuits(hand:'Hand') ->str:
        """return a lowercase string with two suit characters. If no prevalence, returns ''"""
        suitCounts = [len([x for x in hand.tiles if x.lowerGroup == y]) for y in Tile.colors]
        minSuit = min(suitCounts)
        result = ''.join(x for idx, x in enumerate(Tile.colors) if suitCounts[idx] > minSuit)
        if len(result) == 2:
            return result
        return ''


class AllPairHonors(MJRule):

    def computeLastMelds(hand:'Hand') ->MeldList:
        return MeldList(Tile(hand.lastTile).pair)

    def claimness(cls, hand:'Hand', discard:Optional[Tile]) ->IntDict:
        result = IntDict()
        if cls.shouldTry(hand):
            result[Message.Pung] = -999
            result[Message.Kong] = -999
            result[Message.Chow] = -999
        return result

    def maybeCallingOrWon(hand:'Hand') ->bool:
        if any(x.value in Tile.minors for x in hand.tiles):
            return False
        return len(hand.declaredMelds) < 2

    def appliesToHand(cls, hand:'Hand') ->bool:  # pylint:disable=arguments-renamed
        if not cls.maybeCallingOrWon(hand):
            return False
        if len(set(hand.tiles)) != 7:
            return False
        return {len([x for x in hand.tiles if x == y]) for y in hand.tiles} == {2}

    def winningTileCandidates(cls, hand:'Hand') ->Set[Tile]:
        if not cls.maybeCallingOrWon(hand):
            return set()
        single = [x for x in hand.tiles if hand.tiles.count(x) == 1]
        if len(single) != 1:
            return set()
        return set(single)

    def shouldTry(hand:'Hand', maxMissing:int=4) ->bool:
        if hand.declaredMelds:
            return False
        tiles = [x.exposed for x in hand.tiles]
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

    def rearrange(cls, hand:'Hand', rest:Union[TileList,
        List[Tile]]) ->Generator[Tuple[MeldList, TileList], None, None]:
        melds = MeldList()
        for pair in sorted(set(rest) & elements.mAJORS):
            while rest.count(pair) >= 2:
                melds.append(pair.pair)
                rest.remove(pair)
                rest.remove(pair)
        yield melds, rest

    def weigh(aiInstance:'AIDefaultAI', candidates:'DiscardCandidates') ->'DiscardCandidates':
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

    def appliesToHand(hand:'Hand') ->bool:
        return len(hand.tiles) == 18


class ThreeGreatScholars(RuleCode):

    def appliesToHand(cls, hand:'Hand') ->bool:  # pylint:disable=arguments-renamed
        return (BigThreeDragons.appliesToHand(hand)
                and ('nochow' not in cls.options or not any(x.isChow for x in hand.melds)))


class BigThreeDragons(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return len([x for x in hand.melds if x.isDragonMeld and x.isPungKong]) == 3


class BigFourJoys(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return len([x for x in hand.melds if x.isWindMeld and x.isPungKong]) == 4


class LittleFourJoys(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        lengths = sorted(min(len(x), 3) for x in hand.melds if x.isWindMeld)
        return lengths == [2, 3, 3, 3]


class LittleThreeDragons(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return sorted(min(len(x), 3) for x in hand.melds if x.isDragonMeld) == [2, 3, 3]


class FourBlessingsHoveringOverTheDoor(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return len([x for x in hand.melds if x.isPungKong and x.isWindMeld]) == 4


class AllGreen(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return {x.exposed for x in hand.tiles} < elements.greenHandTiles


class LastTileFromWall(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return hand.lastSource is TileSource.LivingWall


class LastTileFromDeadWall(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return hand.lastSource is TileSource.DeadWall

    def selectable(hand:'Hand') ->bool:
        """for scoring game"""
        return hand.lastSource is TileSource.LivingWall


class IsLastTileFromWall(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return hand.lastSource is TileSource.LivingWallEnd

    def selectable(hand:'Hand') ->bool:
        """for scoring game"""
        return hand.lastSource is TileSource.LivingWall


class IsLastTileFromWallDiscarded(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return hand.lastSource is TileSource.LivingWallEndDiscard

    def selectable(hand:'Hand') ->bool:
        """for scoring game"""
        return hand.lastSource is TileSource.LivingWallDiscard


class RobbingKong(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return hand.lastSource is TileSource.RobbedKong

    def selectable(hand:'Hand') ->bool:
        """for scoring game"""
        return (hand.lastSource in (TileSource.RobbedKong, TileSource.LivingWall, TileSource.LivingWallDiscard)
                and bool(hand.lastTile )and hand.lastTile.group.islower()
                and [x.exposed for x in hand.tiles].count(hand.lastTile.exposed) < 2)


class GatheringPlumBlossomFromRoof(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return LastTileFromDeadWall.appliesToHand(hand) and hand.lastTile is Tile(Tile.stone, '5').concealed


class PluckingMoon(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return IsLastTileFromWall.appliesToHand(hand) and hand.lastTile is Tile(Tile.stone, '1').concealed


class ScratchingPole(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return RobbingKong.appliesToHand(hand) and hand.lastTile is Tile(Tile.bamboo, '2')


class StandardRotation(RuleCode):

    def rotate(game:'PlayingGame') ->bool:
        if game is None:
            return False
        if game.winner is None:
            return False
        return game.winner.wind is not East


class EastWonNineTimesInARow(RuleCode):
    nineTimes = 9

    def appliesToHand(cls, hand:'Hand') ->bool:  # pylint:disable=arguments-renamed
        return cls.appliesToGame(hand.player.game)

    def appliesToGame(game:'PlayingGame', needWins:Optional[int]=None) ->bool:
        if needWins is None:
            needWins = EastWonNineTimesInARow.nineTimes
            if game.isScoringGame():
                # we are only proposing for the last needed Win
                needWins -= 1
        if game.winner and game.winner.wind is East and game.notRotated >= needWins:
            eastMJCount = int(Query("select count(1) from score "
                                    "where game=%s and won=1 and wind='E' and player=%d "
                                    "and prevailing='%s'" %
                                    (game.gameid, game.players[East].nameid, game.roundWind.char)).records[0][0])
            return eastMJCount == needWins
        return False

    def rotate(cls, game:'PlayingGame') ->bool:
        return cls.appliesToGame(game, EastWonNineTimesInARow.nineTimes)


class GatesOfHeaven(StandardMahJongg):
    """as used for Classical Chinese BMJA.

    I believe that when they say a run of 2..8, they must
    all be concealed
    """

    cache = ()

# TODO: in BMJA, 111 and 999 must be concealed, we do not check this
    def computeLastMelds(hand:'Hand') ->MeldList:
        return MeldList(x for x in hand.melds if hand.lastTile in x)

    def shouldTry(hand:'Hand', maxMissing:Optional[int]=None) ->bool:
        if hand.declaredMelds:
            return False
        for suit in Tile.colors:
            count19 = sum(x.isTerminal for x in hand.tiles)
            suitCount = len([x for x in hand.tiles if x.lowerGroup == suit])
            if suitCount > 10 and count19 > 4:
                return True
        return False

    def appliesToHand(hand:'Hand') ->bool:
        if len(hand.suits) != 1 or hand.suits >= set(Tile.colors):
            return False
        if any(len(x) > 2 for x in hand.declaredMelds):
            return False
        values = hand.values
        if len(set(values)) < 9 or values.count(1) != 3 or values.count(9) != 3:
            return False
        values_list = list(values[3:-3])
        for value in Tile.minors:
            if value in values_list:
                values_list.remove(value)
        if len(values_list) != 1:
            return False
        surplus = values_list[0]
        return 1 < surplus < 9

    def winningTileCandidates(hand:'Hand') ->Set[Tile]:
        if hand.declaredMelds:
            return set()
        if len(hand.suits) != 1 or hand.suits >= set(Tile.colors):
            return set()
        values = hand.values
        if len(set(values)) < 9:
            return set()
        # we have something of all values
        if values.count(1) != 3 or values.count(9) != 3:
# TODO: we may get them from the wall but not by claim. Differentiate!
            return set()
        for suit in hand.suits:
            return {Tile(suit, x) for x in Tile.minors}
        return set()

    def rearrange(cls, hand:'Hand', rest:Union[TileList,
        List[Tile]]) ->Generator[Tuple[MeldList, TileList], None, None]:
        melds = MeldList()
        for suit in hand.suits & set(Tile.colors):
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
        yield melds, rest


class NineGates(GatesOfHeaven):
    """as used for Classical Chinese DMJL"""

    def appliesToHand(hand:'Hand') ->bool:
        """last tile may also be 1 or 9"""
        if hand.declaredMelds:
            return False
        if len(hand.suits) != 1 or hand.suits >= set(Tile.colors):
            return False
        values = hand.values
        if len(set(values)) < 9:
            return False
        if values.count(1) != 3 or values.count(9) != 3:
            return False
        values_list = list(values[3:-3])
        for value in Tile.minors:
            if value in values_list:
                values_list.remove(value)
        if len(values_list) != 1:
            return False
        surplus = values_list[0]
        return bool(hand.lastTile) and surplus == hand.lastTile.value

    def winningTileCandidates(hand:'Hand') ->Set[Tile]:
        if hand.declaredMelds:
            return set()
        if len(hand.suits) != 1 or hand.suits >= set(Tile.colors):
            return set()
        values = hand.values
        if len(set(values)) < 9:
            return set()
        # we have something of all values
        if values.count(1) != 3 or values.count(9) != 3:
            return set()
        for suit in hand.suits:
            return {Tile(suit, x) for x in Tile.numbers}
        return set()


class ThirteenOrphans(MJRule):

    def computeLastMelds(hand:'Hand') ->MeldList:
        meldSize = hand.tilesInHand.count(hand.lastTile)
        if meldSize == 0:
            # the last tile is called and not yet in the hand
            return MeldList()
        return MeldList(Tile(hand.lastTile).meld(meldSize))

    def rearrange(cls, hand:'Hand', rest:Union[TileList,
        List[Tile]]) ->Generator[Tuple[MeldList, TileList], None, None]:
        melds = MeldList()
        for tileName in rest:
            if rest.count(tileName) >= 2:
                melds.append(tileName.pair)
                rest.remove(tileName)
                rest.remove(tileName)
            elif rest.count(tileName) == 1:
                melds.append(tileName.single)
                rest.remove(tileName)
        yield melds, rest

    def claimness(cls, hand:'Hand', discard:Optional[Tile]) ->IntDict:
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

    def appliesToHand(hand:'Hand') ->bool:
        return {x.exposed for x in hand.tiles} == elements.majors

    def winningTileCandidates(cls, hand:'Hand') ->Set[Tile]:
        if any(x in hand.values for x in Tile.minors):
            # no minors allowed
            return set()
        if not cls.shouldTry(hand, 1):
            return set()
        handTiles = {x.exposed for x in hand.tiles}
        missing = elements.majors - handTiles
        if not missing:
            # if all 13 tiles are there, we need any one of them:
            return elements.majors
        assert len(missing) == 1
        return missing

    def shouldTry(hand:'Hand', maxMissing:int=4) ->bool:
        # TODO: look at how many tiles there still are on the wall
        if hand.declaredMelds:
            return False
        handTiles = {x.exposed for x in hand.tiles}
        missing = elements.majors - handTiles
        if len(missing) > maxMissing:
            return False
        for missingTile in missing:
            if not hand.player.tileAvailable(missingTile, hand):
                return False
        return True

    def weigh(cls, aiInstance:'AIDefaultAI', candidates:'DiscardCandidates') ->'DiscardCandidates':
        hand = candidates.hand
        assert hand
        if not cls.shouldTry(hand):
            return candidates
        handTiles = {x.exposed for x in hand.tiles}
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

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        assert hand
        return meld[0].value is hand.ownWind

    def mayApplyToMeld(meld:Meld) ->bool:
        # pylint: disable=unsubscriptable-object
        # must be a pylint bug. meld is TileList is list
        return meld.isBonus and meld[0].group == Tile.flower


class OwnSeason(RuleCode):

    def appliesToMeld(hand:Optional['Hand'], meld:Meld) ->bool:
        assert hand
        return meld[0].value is hand.ownWind

    def mayApplyToMeld(meld:Meld) ->bool:
        # pylint: disable=unsubscriptable-object
        # must be a pylint bug. meld is TileList is list
        return meld.isBonus and meld[0].group == Tile.season


class OwnFlowerOwnSeason(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return sum(x.isBonus and x[0].value is hand.ownWind for x in hand.bonusMelds) == 2


class AllFlowers(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return len([x for x in hand.bonusMelds if x.group == Tile.flower]) == 4


class AllSeasons(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return len([x for x in hand.bonusMelds if x.group == Tile.season]) == 4


class ThreeConcealedPongs(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return len([x for x in hand.melds if (
            x.isConcealed or x.isClaimedKong) and x.isPungKong]) >= 3


class MahJonggWithOriginalCall(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return ('a' in hand.announcements
                and sum(x.isExposed for x in hand.melds) < 3)

    def selectable(hand:'Hand') ->bool:
        """for scoring game"""
        # one tile may be claimed before declaring OC and one for going MJ
        # the previous regex was too strict
        return sum(x.isExposed for x in hand.melds) < 3

    def claimness(hand:'Hand', discard:Optional[Tile]) ->IntDict:
        result = IntDict()
        player = hand.player
        if player.originalCall and player.mayWin:
            if player.originalCallingHand and player.originalCallingHand.chancesToWin():
                # winning with OriginalCall is still possible
                result[Message.Pung] = -999
                result[Message.Kong] = -999
                result[Message.Chow] = -999
            else:
                player.mayWin = False  # bad luck
        return result


class TwofoldFortune(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return 't' in hand.announcements

    def selectable(hand:'Hand') ->bool:
        """for scoring game"""
        kungs = [x for x in hand.melds if len(x) == 4]
        return len(kungs) >= 2


class BlessingOfHeaven(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        if hand.lastSource is not TileSource.East14th:
            return False
        if hand.ownWind is not East:
            return False
        if any(x.isExposed for x in hand.melds):
            return False
        assert hand.lastTile is Tile.none, '{}: Blessing of Heaven: There can be no last tile'.format(hand)
        return True

    def selectable(hand:'Hand') ->bool:
        """for scoring game"""
        return (hand.ownWind is East
                and hand.lastSource in (TileSource.LivingWall, TileSource.LivingWallDiscard)
                and not hand.announcements - {'a'})


class BlessingOfEarth(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        if hand.lastSource is not TileSource.East14th:
            return False
        if hand.ownWind is East:
            return False
        return True

    def selectable(hand:'Hand') ->bool:
        """for scoring game"""
        return (hand.ownWind is not East
                and hand.lastSource in (TileSource.LivingWall, TileSource.LivingWallDiscard)
                and not hand.announcements - {'a'})


class LongHand(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return hand.lenOffset > 0 if not hand.won else hand.lenOffset > 1


class FalseDiscardForMJ(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return not hand.won

    def selectable(hand:'Hand') ->bool:
        """for scoring game"""
        return not hand.won


class DangerousGame(RuleCode):

    def appliesToHand(hand:'Hand') ->bool:
        return not hand.won

    def selectable(hand:'Hand') ->bool:
        """for scoring game"""
        return not hand.won


class LastOnlyPossible(RuleCode):

    """check if the last tile was the only one possible for winning"""
    def appliesToHand(hand:'Hand') ->bool:
        if not hand.lastTile:
            return False
        if any(hand.lastTile in x for x in hand.melds if len(x) == 4):
            # the last tile completed a Kong
            return False
        shortHand = hand - hand.lastTile
        return len(shortHand.callingHands) == 1
