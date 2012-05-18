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

from tile import chiNext
from meld import Meld, CONCEALED, EXPOSED, CLAIMEDKONG, REST
from common import elements, IntDict
from message import Message

class Function(object):
    """Parent for all Function classes. We need to implement
    those methods as in Regex:
    appliesToHand and appliesToMeld"""

    functions = {}

    def __init__(self):
        self.options = {}

# pylint: disable=C0111
# the class and method names are mostly self explaining, we do not
# need docstringss

class DragonPungKong(Function):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return (len(meld) >= 3
            and meld.pairs[0][0].lower() == 'd'
            and (meld.isPung() or meld.isKong()))

class RoundWindPungKong(Function):
    @staticmethod
    def appliesToMeld(hand, meld):
        return len(meld) >= 3 and meld.pairs[0].lower() == 'w' + hand.roundWind

class ExposedMinorPung(Function):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return meld.isPung() and meld.pairs.isLower(0, 3) and meld.pairs[0][1] in '2345678'

class ExposedTerminalsPung(Function):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return meld.isPung() and meld.pairs.isLower(0, 3) and meld.pairs[0][1] in '19'

class ExposedHonorsPung(Function):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return meld.isPung() and meld.pairs[0][0] in 'wd'

class ExposedMinorKong(Function):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return len(meld) == 4 and meld.pairs.isLower(0, 3) and meld.pairs[0][1] in '2345678'

class ExposedTerminalsKong(Function):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return len(meld) == 4 and meld.pairs.isLower(0, 3) and meld.pairs[0][1] in '19'

class ExposedHonorsKong(Function):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return len(meld) == 4 and meld.pairs.isLower(0, 3) and meld.pairs[0][0] in 'wd'

class ConcealedMinorPung(Function):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return meld.isPung() and meld.pairs.isUpper(0, 3) and meld.pairs[0][1] in '2345678'

class ConcealedTerminalsPung(Function):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return meld.isPung() and meld.pairs.isUpper(0, 3) and meld.pairs[0][1] in '19'

class ConcealedHonorsPung(Function):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return meld.isPung() and meld.pairs[0][0] in 'WD'

class ConcealedMinorKong(Function):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return len(meld) == 4 and meld.state == CONCEALED and meld.pairs[0][1] in '2345678'

class ConcealedTerminalsKong(Function):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return len(meld) == 4 and meld.state == CONCEALED and meld.pairs[0][1] in '19'

class ConcealedHonorsKong(Function):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return len(meld) == 4 and meld.state == CONCEALED and meld.pairs[0][0] in 'wd'

class OwnWindPungKong(Function):
    @staticmethod
    def appliesToMeld(hand, meld):
        return len(meld) >= 3 and meld.pairs[0].lower() == 'w' + hand.ownWind

class OwnWindPair(Function):
    @staticmethod
    def appliesToMeld(hand, meld):
        return len(meld) == 2 and meld.pairs[0].lower() == 'w' + hand.ownWind

class RoundWindPair(Function):
    @staticmethod
    def appliesToMeld(hand, meld):
        return len(meld) == 2 and meld.pairs[0].lower() == 'w' + hand.roundWind

class DragonPair(Function):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return len(meld) == 2 and meld.pairs[0][0].lower() == 'd'

class LastTileCompletesPairMinor(Function):
    @staticmethod
    def appliesToHand(hand):
        return (hand.lastMeld and len(hand.lastMeld) == 2
            and hand.lastMeld.pairs[0][0] == hand.lastMeld.pairs[1][0]
            and hand.lastTile and hand.lastTile[1] in '2345678')

class Flower(Function):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return len(meld) == 1 and meld.pairs[0][0] == 'f'

class Season(Function):
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        return len(meld) == 1 and meld.pairs[0][0] == 'y'

class LastTileCompletesPairMajor(Function):
    @staticmethod
    def appliesToHand(hand):
        return (hand.lastMeld and len(hand.lastMeld) == 2
            and hand.lastMeld.pairs[0][0] == hand.lastMeld.pairs[1][0]
            and hand.lastTile and hand.lastTile[1] not in '2345678')

class LastFromWall(Function):
    @staticmethod
    def appliesToHand(hand):
        return hand.lastTile and hand.lastTile[0].isupper()

class ZeroPointHand(Function):
    @staticmethod
    def appliesToHand(hand):
        return not any(x.meld for x in hand.usedRules if x.meld and len(x.meld) > 1)

class NoChow(Function):
    @staticmethod
    def appliesToHand(hand):
        return not any(x.isChow() for x in hand.melds)

class OnlyConcealedMelds(Function):
    @staticmethod
    def appliesToHand(hand):
        return not any((x.state == EXPOSED and x.meldType != CLAIMEDKONG) for x in hand.melds)

class FalseColorGame(Function):
    @staticmethod
    def appliesToHand(hand):
        dwSet = set('dw')
        return dwSet & hand.suits and len(hand.suits - dwSet) == 1

class TrueColorGame(Function):
    @staticmethod
    def appliesToHand(hand):
        return len(hand.suits) == 1 and hand.suits < set('sbc')

class Purity(Function):
    @staticmethod
    def appliesToHand(hand):
        return (len(hand.suits) == 1 and hand.suits < set('sbc')
            and not any(x.isChow() for x in hand.melds))

class ConcealedTrueColorGame(Function):
    @staticmethod
    def appliesToHand(hand):
        if len(hand.suits) != 1 or not (hand.suits < set('sbc')):
            return False
        return not any((x.state == EXPOSED and x.meldType != CLAIMEDKONG) for x in hand.melds)

class OnlyMajors(Function):
    @staticmethod
    def appliesToHand(hand):
        return not set(hand.values) - set('grbeswn19')

class OnlyHonors(Function):
    @staticmethod
    def appliesToHand(hand):
        return not set(hand.values) - set('grbeswn')

class HiddenTreasure(Function):
    @staticmethod
    def appliesToHand(hand):
        return (not any(((x.state == EXPOSED and x.meldType != CLAIMEDKONG) or x.isChow()) for x in hand.melds)
            and hand.lastTile and hand.lastTile[0].isupper()
            and len(hand.melds) == 5)

class BuriedTreasure(Function):
    @staticmethod
    def appliesToHand(hand):
        return (len(hand.suits - set('dw')) == 1
            and StandardMahJongg.appliesToHand(hand)
            and all((x.isPung() and x.state == CONCEALED) or x.isPair() for x in hand.melds))

class AllTerminals(Function):
    @staticmethod
    def appliesToHand(hand):
        return not set(hand.values) - set('19')

class SquirmingSnake(Function):
    @staticmethod
    def appliesToHand(hand):
        if len(hand.suits) != 1 or not hand.suits < set('sbc'):
            return False
        values = hand.values
        if values.count('1') < 3 or values.count('9') < 3:
            return False
        pairs = [x for x in '258' if values.count(x) == 2]
        if len(pairs) != 1:
            return False
        return len(set(values)) == len(values) - 5

class WrigglingSnake(Function):
    @staticmethod
    def appliesToHand(hand):
        suits = hand.suits.copy()
        if 'w' not in suits:
            return False
        suits -= set('w')
        if len(suits) != 1 or not suits < set('sbc'):
            return False
        if hand.values.count('1') != 2:
            return False
        return len(set(hand.values)) == 13

class CallingLimithand(Function):
    def __init__(self):
        Function.__init__(self)
        self.active = False
        self.limitHand = None

    def appliesToHand(self, hand):
        if self.active:
            return False
        if hand.lenOffset != 0:
            return False
        assert not hand.won, str(hand)
        assert not 'M' in hand.string, hand.string
        if not self.limitHand:
            self.limitHand = Function.functions[self.options['hand']]()
            self.limitHand.options = self.options
        self.active = True
        try:
            if hasattr(self.limitHand, 'winningTileCandidates'):
                candidates = self.limitHand.winningTileCandidates(hand)
            else:
                candidates = StandardMahJongg.winningTileCandidates(hand)
            for tileName in candidates:
                tileName = tileName.capitalize()
                thisOne = hand.addTile(hand.string, tileName)
                fullHand = hand.cached(hand.ruleset, thisOne)
                if self.limitHand.appliesToHand(fullHand):
                    return True
            return False
        finally:
            self.active = False

class TripleKnitting(Function):
    @staticmethod
    def maybeCallingOrWon(hand):
        if hand.windMelds or hand.dragonMelds:
            return False
        if len(hand.declaredMelds) > 1:
            return False
        if len(hand.suits) < 3:
            return False
        return True

    @staticmethod
    def appliesToHand(hand):
        if not TripleKnitting.maybeCallingOrWon(hand):
            return False
        tileNames = [x.lower() for x in hand.tileNames]
        suitCounts = sorted([len([x for x in tileNames if x[0] == y]) for y in 'sbc'])
        if suitCounts != [4, 5, 5]:
            return False
        # remove triple sets:
        for value in hand.values:
            valTiles = list(x + value for x in 'sbc')
            if set(valTiles) <= set(tileNames):
                for tile in valTiles:
                    tileNames.remove(tile)
        if len(tileNames) != 2:
            return False
        return (tileNames[0][0] != tileNames[1][0]
            and tileNames[0][1] == tileNames[1][1])

    @staticmethod
    def winningTileCandidates(hand):
        if not TripleKnitting.maybeCallingOrWon(hand):
            return set()
        values = hand.values
        result = set()
        for value in (x for x in values if values.count(x) % 3):
            result |= set(x + value for x in 'sbc' if x.upper() + value not in hand.tileNames)
        return result

class Knitting(Function):
    def __init__(self):
        Function.__init__(self)
        self.suitCounts = []
    def maybeCallingOrWon(self, hand):
        melds = hand.windMelds + hand.dragonMelds
        if melds and max(len(x) for x in melds) >= 3:
            return False
        if len(hand.declaredMelds) > 1:
            return False
        if hand.lastTile and hand.lastTile.istitle() and hand.declaredMelds:
            return False
        tileNames = [x.lower() for x in hand.tileNames]
        self.suitCounts = sorted([len([x for x in tileNames if x[0] == y]) for y in 'sbc'])
        return True
    def appliesToHand(self, hand):
        if not self.maybeCallingOrWon(hand):
            return set()
        if self.suitCounts != [0, 7, 7]:
            return False
        values = hand.values
        return all(values.count(x) % 2 == 0 for x in set(values))
    def winningTileCandidates(self, hand):
        if not self.maybeCallingOrWon(hand):
            return set()
        if self.suitCounts != [0, 6, 7]:
            return set()
        values = hand.values
        singleValue = list(x for x in values if values.count(x) % 2)
        if len(singleValue) != 1:
            return set()
        singleValue = singleValue[0]
        singleTile = list(x for x in hand.tileNames if x[1] == singleValue)
        assert len(singleTile) == 1, hand
        singleTile = singleTile[0]
        otherSuit = list(hand.suits - set([singleTile[0].lower()]))[0]
        otherTile = otherSuit.capitalize() + singleTile[1]
        return set([otherTile])

class AllPairHonors(Function):
    @staticmethod
    def maybeCallingOrWon(hand):
        if any(x[1] in '2345678' for x in hand.tileNames):
            return False
        return len(hand.declaredMelds) < 2
    def appliesToHand(self, hand):
        if not self.maybeCallingOrWon(hand):
            return False
        values = hand.values
        if len(set(values)) != 7:
            return False
        valueCounts = sorted([len([x for x in hand.tileNames if x[1] == y]) for y in set(values)])
        return set(valueCounts) == set([2])
    def winningTileCandidates(self, hand):
        if not self.maybeCallingOrWon(hand):
            return set()
        single = list(x for x in hand.tileNames if hand.tileNames.count(x) == 1)
        if len(single) != 1:
            return set()
        return set(single)

class FourfoldPlenty(Function):
    @staticmethod
    def appliesToHand(hand):
        return len(hand.tileNames) == 18

class ThreeGreatScholars(Function):
    def appliesToHand(self, hand):
        return (BigThreeDragons.appliesToHand(hand)
            and ('nochow' not in self.options or not any(x.isChow() for x in hand.melds)))

class BigThreeDragons(Function):
    @staticmethod
    def appliesToHand(hand):
        return len([x for x in hand.dragonMelds if len(x) >= 3]) == 3

class BigFourJoys(Function):
    @staticmethod
    def appliesToHand(hand):
        return len([x for x in hand.windMelds if len(x) >= 3]) == 4

class LittleFourJoys(Function):
    @staticmethod
    def appliesToHand(hand):
        return (len([x for x in hand.windMelds if len(x) >= 3]) == 3
            and len([x for x in hand.windMelds if len(x) == 2]) == 1)

class LittleThreeDragons(Function):
    @staticmethod
    def appliesToHand(hand):
        return (len([x for x in hand.dragonMelds if len(x) >= 3]) == 2
            and len([x for x in hand.dragonMelds if len(x) == 2]) == 1)

class FourBlessingsHoveringOverTheDoor(Function):
    @staticmethod
    def appliesToHand(hand):
        return len([x for x in hand.melds if len(x) >= 3 and x.pairs[0][0] in 'wW']) == 4

class AllGreen(Function):
    @staticmethod
    def appliesToHand(hand):
        tiles = set(x.lower() for x in hand.tileNames)
        return hand.won and tiles < set(['b2', 'b3', 'b4', 'b5', 'b6', 'b8', 'dg'])

class LastTileFromWall(Function):
    @staticmethod
    def appliesToHand(hand):
        return hand.won and hand.lastSource == 'w'

class LastTileFromDeadWall(Function):
    @staticmethod
    def appliesToHand(hand):
        return hand.won and hand.lastSource == 'e'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return hand.lastSource == 'w'

class IsLastTileFromWall(Function):
    @staticmethod
    def appliesToHand(hand):
        return hand.won and hand.lastSource == 'z'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return hand.won and hand.lastSource == 'w'

class IsLastTileFromWallDiscarded(Function):
    @staticmethod
    def appliesToHand(hand):
        return hand.won and hand.lastSource == 'Z'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return hand.lastSource == 'd'

class RobbingKong(Function):
    @staticmethod
    def appliesToHand(hand):
        return hand.won and hand.lastSource == 'k'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return (hand.lastSource and hand.lastSource in 'kwd'
            and hand.lastTile and hand.lastTile[0].islower()
            and [x.lower() for x in hand.tileNames].count(hand.lastTile.lower()) < 2)

class GatheringPlumBlossomFromRoof(Function):
    @staticmethod
    def appliesToHand(hand):
        if not hand.won:
            return False
        if LastTileFromDeadWall.appliesToHand(hand):
            return hand.lastTile == 'S5'
        return False

class PluckingMoon(Function):
    @staticmethod
    def appliesToHand(hand):
        return hand.won and hand.lastSource == 'z' and hand.lastTile == 'S1'

class ScratchingPole(Function):
    @staticmethod
    def appliesToHand(hand):
        return hand.won and hand.lastSource and hand.lastSource == 'k' and hand.lastTile == 'b2'

class StandardMahJongg(Function):
    @staticmethod
    def computeLastMelds(hand):
        """returns all possible last melds"""
        if not hand.lastTile:
            return
        if hand.lastTile[0].isupper():
            checkMelds = hand.hiddenMelds
        else:
            checkMelds = hand.declaredMelds
        return [x for x in checkMelds if hand.lastTile in x.pairs and len(x) < 4]

    @staticmethod
    def appliesToHand(hand):
        """winner rules are not yet applied to hand"""
        # pylint: disable=R0911
        # too many return statements
        if len(hand.melds) != 5:
            return False
        if any(len(x) not in (2, 3, 4) for x in hand.melds):
            return False
        if any(x.meldType == REST for x in hand.melds):
            return False
        if hand.countMelds(Meld.isChow) > hand.ruleset.maxChows:
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
    def winningTileCandidates(hand):
        if len(hand.melds) > 6:
            return set()
        hiddenTiles = sum((x.pairs for x in hand.hiddenMelds), [])
        result = set(x.lower() for x in hiddenTiles)
        for tile in (x.lower() for x in hiddenTiles if x[0] in 'SBC'):
            if tile[1] > '1':
                result.add(chiNext(tile, -1))
            if tile[1] < '9':
                result.add(chiNext(tile, 1))
        return result

    @staticmethod
    def rearrange(hand, rest):
        """rest is a string with those tiles that can still
        be rearranged: No declared melds and no bonus tiles"""
        pairs = Meld(rest).pairs
        _ = [pair for pair in pairs if pair[0] in 'DWdw']
        honourResult = hand.splitRegex(''.join(_)) # easy since they cannot have a chow
        splitVariants = {}
        for color in 'SBC':
            colorPairs = [pair for pair in pairs if pair[0] == color]
            if not colorPairs:
                splitVariants[color] = [None]
                continue
            splitVariants[color] = hand.genVariants(colorPairs)
        bestHand = None
        bestVariant = None
        for combination in ((s, b, c)
                for s in splitVariants['S']
                for b in splitVariants['B']
                for c in splitVariants['C']):
            variantMelds = honourResult[:] + sum((x for x in combination if x is not None), [])
            melds = hand.melds[:] + variantMelds
            melds.extend(hand.bonusMelds)
            _ = ' '.join(x.joined for x in melds) + ' ' + hand.mjStr
            tryHand = hand.cached(hand, _, computedRules=hand.computedRules)
            if not bestHand or tryHand.total() > bestHand.total():
                bestHand = tryHand
                bestVariant = variantMelds
        hand.melds.extend(bestVariant)
        return True

class GatesOfHeaven(Function):
    def __init__(self):
        Function.__init__(self)
        self.suit = None
    def maybeCallingOrWon(self, hand):
        suits = set(x[0].lower() for x in hand.tileNames)
        if len(suits) != 1 or not suits < set('sbc'):
            return False
        self.suit = suits.pop()
        for meld in hand.declaredMelds:
            if meld.isPung():
                return False
        return True

    def appliesToHand(self, hand):
# TODO:  assert hand.won and bool(hand.lastTile)
        if not self.maybeCallingOrWon(hand):
            return False
        values = hand.values
        if len(set(values)) < 0 or not values.startswith('111') or not values.endswith('999'):
            return False
        values = values[3:-3]
        for value in '2345678':
            values = values.replace(value, '', 1)
        if len(values) != 1:
            return False
        surplus = values[0]
        if 'pair28' in self.options:
            return surplus in '2345678'
        if 'lastExtra' in self.options:
            return surplus == hand.lastTile[1]
        return True

    def winningTileCandidates(self, hand):
        result = set()
        if not self.maybeCallingOrWon(hand):
            return result
        values = hand.values
        if len(set(values)) == 8:
            # one minor is missing
            result = set('2345678') - set(values)
        else:
            # we have something of all values
            if not values.startswith('111'):
                result = set('1')
            elif not values.endswith('999'):
                result = set('9')
            else:
                if 'pair28' in self.options:
                    result = set('2345678')
                else:
                    result = set('123456789')
        return set(self.suit + x for x in result)

class ThirteenOrphans(Function):
    def __init__(self):
        Function.__init__(self)
        self.missingTiles = None
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
        if any(x in hand.values for x in '2345678'):
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
        if hand.game and hand.game.myself:
            # in scoringtest, we have no game instance
            # on the server we have no myself in saveHand
            for missingTile in missing:
                if not hand.game.myself.tileAvailable(missingTile, hand):
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
            if candidate.value in '2345678':
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
        fsPairs = list(x.pairs[0] for x in hand.bonusMelds)
        return 'f' + hand.ownWind in fsPairs

class OwnSeason(Function):
    @staticmethod
    def appliesToHand(hand):
        fsPairs = list(x.pairs[0] for x in hand.bonusMelds)
        return 'y' + hand.ownWind in fsPairs

class OwnFlowerOwnSeason(Function):
    @staticmethod
    def appliesToHand(hand):
        return (OwnFlower.appliesToHand(hand)
            and OwnSeason.appliesToHand(hand))

class AllFlowers(Function):
    @staticmethod
    def appliesToHand(hand):
        return len([x for x in hand.bonusMelds if x.pairs[0][0] == 'f']) == 4

class AllSeasons(Function):
    @staticmethod
    def appliesToHand(hand):
        return len([x for x in hand.bonusMelds if x.pairs[0][0] == 'y']) == 4

class ThreeConcealedPongs(Function):
    @staticmethod
    def appliesToHand(hand):
        return len([x for x in hand.melds if (
            x.state == CONCEALED or x.meldType == CLAIMEDKONG) and (x.isPung() or x.isKong())]) >= 3

class MahJonggWithOriginalCall(Function):
    @staticmethod
    def appliesToHand(hand):
        return (hand.won and 'a' in hand.announcements
            and len([x for x in hand.melds if x.state == EXPOSED]) < 3)

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        # one may be claimed before declaring OC and one for going MJ
        # the previous regex was too strict
        exp = [x for x in hand.melds if x.state == EXPOSED]
        return hand.won and len(exp) < 3

class TwofoldFortune(Function):
    @staticmethod
    def appliesToHand(hand):
        return hand.won and 't' in hand.announcements

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        kungs = [x for x in hand.melds if len(x) == 4]
        return hand.won and len(kungs) >= 2

class BlessingOfHeaven(Function):
    @staticmethod
    def appliesToHand(hand):
        return hand.won and hand.ownWind == 'e' and hand.lastSource == '1'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return (hand.won and hand.ownWind == 'e'
            and hand.lastSource and hand.lastSource in 'wd'
            and not (set(hand.announcements) - set('a')))

class BlessingOfEarth(Function):
    @staticmethod
    def appliesToHand(hand):
        return hand.won and hand.ownWind != 'e' and hand.lastSource == '1'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return (hand.won and hand.ownWind != 'e'
            and hand.lastSource and hand.lastSource in 'wd'
            and not (set(hand.announcements) - set('a')))

class LongHand(Function):
    @staticmethod
    def appliesToHand(hand):
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
