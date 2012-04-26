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
from meld import CONCEALED, EXPOSED, CLAIMEDKONG, REST
from common import elements

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
    def appliesToMeld(hand, meld):
        return len(meld) >= 3 and meld in hand.dragonMelds

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
        if hand.windMelds or hand.dragonMelds:
            return False
        if len(hand.declaredMelds) > 1:
            return False
        if hand.lastTile.istitle() and hand.declaredMelds:
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
    def appliesToHand(hand):
        if any(x[1] in '2345678' for x in hand.tileNames):
            return False
        if len(hand.declaredMelds) > 1:
            return False
        values = hand.values
        if len(set(values)) != 7:
            return False
        valueCounts = sorted([len([x for x in hand.tileNames if x[1] == y]) for y in set(values)])
        return set(valueCounts) == set([2])

class FourfoldPlenty(Function):
    @staticmethod
    def appliesToHand(hand):
        return len(hand.tileNames) == 18

class ThreeGreatScholars(Function):
    def appliesToHand(self, hand):
        return (StandardMahJongg.appliesToHand(hand)
            and BigThreeDragons.appliesToHand(hand)
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
            return hand.lastTile and hand.lastTile == 'S5'
        return False

class PluckingMoon(Function):
    @staticmethod
    def appliesToHand(hand):
        return hand.won and hand.lastSource == 'z' and hand.lastTile and hand.lastTile == 'S1'

class ScratchingPole(Function):
    @staticmethod
    def appliesToHand(hand):
        return hand.won and hand.lastSource and hand.lastSource == 'k' and hand.lastTile and hand.lastTile == 'b2'

class StandardMahJongg(Function):
    @staticmethod
    def appliesToHand(hand):
        return (len(hand.melds) == 5
            and set(len(x) for x in hand.melds) <= set([2,3,4])
            and not any(x.meldType == REST for x in hand.melds)
            and hand.ruleset.maxChows >= len([x for x in hand.melds if x.isChow()])
            and hand.score.total() >= hand.ruleset.minMJPoints
            and hand.score.doubles >= hand.ruleset.minMJDoubles)

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

class GatesOfHeaven(Function):
    @staticmethod
    def maybeCallingOrWon(hand):
        suits = set(x[0].lower() for x in hand.tileNames)
        if len(suits) != 1 or not suits < set('sbc'):
            return False
        values = hand.values
        if values.count('1') < 3 or values.count('9') < 3:
            return False
        values = set(values) - set('19')
        if len(set(values)) < 7:
            return False
        for meld in hand.declaredMelds:
            if meld.isPung() and meld.pairs[0][1] in '19':
                return False
        return True

    def appliesToHand(self, hand):
        if not hand.won or not hand.lastTile:
            return False
        if not self.maybeCallingOrWon(hand):
            return False
        values = hand.values.replace('111','').replace('999','')
        for value in '2345678':
            values = values.replace(value, '', 1)
        if len(values) != 1:
            return False
        # the last tile must complete the pair
        return 'lastCompletesPair' not in self.options or values == hand.lastTile[1]

    def winningTileCandidates(self, hand):
        result = set()
        if not self.maybeCallingOrWon(hand):
            return result
        values = hand.values
        if len(set(values)) == 7:
            # one value is missing
            if 'lastCompletesPair' in self.options:
                return result
            result = set('2345678') - set(values)
        else:
            # we have all values, last tile may be anything
            if 'lastCompletesPair' in self.options:
                result = set('2345678')
            else:
                result = set('123456789')
        return result

class ThirteenOrphans(Function):
    @staticmethod
    def appliesToHand(hand):
        return set(x.lower() for x in hand.tileNames) == elements.majors

    @staticmethod
    def winningTileCandidates(hand):
        if any(x in hand.values for x in '2345678'):
            # no minors allowed
            return set()
        handTiles = set(x.lower() for x in hand.tileNames)
        missing = elements.majors - handTiles
        if len(missing) == 0:
            # if all 13 tiles are there, we need any one of them:
            return elements.majors
        elif len(missing) == 1:
            return missing
        else:
            return set()
    @staticmethod
    def weigh(dummyAiInstance, candidates):
        return candidates

class OwnFlower(Function):
    @staticmethod
    def appliesToHand(hand):
        fsPairs = list(x.pairs[0] for x in hand.fsMelds)
        return 'f' + hand.ownWind in fsPairs

class OwnSeason(Function):
    @staticmethod
    def appliesToHand(hand):
        fsPairs = list(x.pairs[0] for x in hand.fsMelds)
        return 'y' + hand.ownWind in fsPairs

class OwnFlowerOwnSeason(Function):
    @staticmethod
    def appliesToHand(hand):
        return (OwnFlower.appliesToHand(hand)
            and OwnSeason.appliesToHand(hand))

class AllFlowers(Function):
    @staticmethod
    def appliesToHand(hand):
        return len([x for x in hand.fsMelds if x.pairs[0][0] == 'f']) == 4

class AllSeasons(Function):
    @staticmethod
    def appliesToHand(hand):
        return len([x for x in hand.fsMelds if x.pairs[0][0] == 'y']) == 4

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
        offset = hand.handLenOffset()
        return (not hand.won and offset > 0) or offset > 1

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
        if self.active:
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
