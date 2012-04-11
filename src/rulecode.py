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
    def appliesToHand(self, hand):
        return 'f' + self.options['wind'] in hand.fsMeldNames

class Season(Function):
    def appliesToHand(self, hand):
        return 'y' + self.options['wind'] in hand.fsMeldNames

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
        return sum(x.score.points for x in hand.melds) == 0

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
        suits = set(x[0].lower() for x in hand.tileNames)
        dwSet = set('dw')
        return dwSet & suits and len(suits - dwSet) == 1

class TrueColorGame(Function):
    @staticmethod
    def appliesToHand(hand):
        suits = set(x[0].lower() for x in hand.tileNames)
        return len(suits) == 1 and suits < set('sbc')

class ConcealedTrueColorGame(Function):
    @staticmethod
    def appliesToHand(hand):
        suits = set(x[0].lower() for x in hand.tileNames)
        if len(suits) != 1 or not (suits < set('sbc')):
            return False
        return not any((x.state == EXPOSED and x.meldType != CLAIMEDKONG) for x in hand.melds)

class OnlyMajors(Function):
    @staticmethod
    def appliesToHand(hand):
        values = set(x[1] for x in hand.tileNames)
        return not values - set('grbeswn19')

class OnlyHonors(Function):
    @staticmethod
    def appliesToHand(hand):
        values = set(x[1] for x in hand.tileNames)
        return not values - set('grbeswn')

class HiddenTreasure(Function):
    # TODO: BMJA calls this Buried Treasure and does not require
    # the last tile to come from the wall. Parametrize.
    @staticmethod
    def appliesToHand(hand):
        return (not any(((x.state == EXPOSED and x.meldType != CLAIMEDKONG) or x.isChow()) for x in hand.melds)
            and hand.lastTile and hand.lastTile[0].isupper()
            and len(hand.melds) == 5)

class AllTerminals(Function):
    @staticmethod
    def appliesToHand(hand):
        values = set(x[1] for x in hand.tileNames)
        return not values - set('19')

class SquirmingSnake(Function):
    @staticmethod
    def appliesToHand(hand):
        suits = set(x[0].lower() for x in hand.tileNames)
        if len(suits) != 1 or not suits < set('sbc'):
            return False
        values = ''.join(x[1] for x in hand.tileNames)
        if values.count('1') < 3 or values.count('9') < 3:
            return False
        pairs = [x for x in '258' if values.count(x) == 2]
        if len(pairs) != 1:
            return False
        return len(set(values)) == len(values) - 5

class WrigglingSnake(Function):
    @staticmethod
    def appliesToHand(hand):
        suits = set(x[0].lower() for x in hand.tileNames)
        if 'w' not in suits:
            return False
        suits -= set('w')
        if len(suits) != 1 or not suits < set('sbc'):
            return False
        values = ''.join(x[1] for x in hand.tileNames)
        if values.count('1') != 2:
            return False
        return len(set(values)) == 13

class TripleKnitting(Function):
    @staticmethod
    def appliesToHand(hand):
        if hand.windMelds or hand.dragonMelds:
            return False
        if len(hand.declaredMelds) > 1:
            return False
        tileNames = [x.lower() for x in hand.tileNames]
        suitCounts = sorted([len([x for x in tileNames if x[0] == y]) for y in 'sbc'])
        if suitCounts != [4, 5, 5]:
            return False
        values = list(x[1] for x in tileNames)
        return all(values.count(x) % 3 != 1 for x in set(values))

class Knitting(Function):
    @staticmethod
    def appliesToHand(hand):
        if hand.windMelds or hand.dragonMelds:
            return False
        if len(hand.declaredMelds) > 1:
            return False
        tileNames = [x.lower() for x in hand.tileNames]
        suitCounts = sorted([len([x for x in tileNames if x[0] == y]) for y in 'sbc'])
        if suitCounts != [0, 7, 7]:
            return False
        values = list(x[1] for x in tileNames)
        return all(values.count(x) % 2 == 0 for x in set(values))

class AllPairHonors(Function):
    @staticmethod
    def appliesToHand(hand):
        if any(x[1] in '2345678' for x in hand.tileNames):
            return False
        if len(hand.declaredMelds) > 1:
            return False
        values = list(x[1] for x in hand.tileNames)
        if len(set(values)) != 7:
            return False
        valueCounts = sorted([len([x for x in hand.tileNames if x[1] == y]) for y in set(values)])
        return set(valueCounts) == set([2])

class FourfoldPlenty(Function):
    @staticmethod
    def appliesToHand(hand):
        return len(hand.tileNames) == 18

class ThreeGreatScholars(Function):
    @staticmethod
    def appliesToHand(hand):
        return (StandardMahJongg.appliesToHand(hand)
            and BigThreeDragons.appliesToHand(hand))

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
            and hand.ruleset.maxChows >= len([x for x in hand.melds if x.isChow()]))

class GatesOfHeaven(Function):
    def appliesToHand(self, hand):
        suits = set(x[0].lower() for x in hand.tileNames)
        if len(suits) != 1 or not suits < set('sbc') or not hand.won or not hand.lastTile:
            return False
        values = ''.join(x[1] for x in hand.tileNames)
        if values.count('1') < 3 or values.count('9') < 3:
            return False
        values = values.replace('111','').replace('999','')
        for value in '2345678':
            values = values.replace(value, '', 1)
        if len(values) != 1:
            return False
        # the last tile must complete the pair
        return 'lastCompletesPair' not in self.options or values == hand.lastTile[1]

class ThirteenOrphans(Function):
    @staticmethod
    def appliesToHand(hand):
        return set(x.lower() for x in hand.tileNames) == elements.majors

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

    active = False

    @staticmethod
    def appliesToHand(hand):
        # pylint: disable=R0911
        # pylint: disable=R0912
        if LastOnlyPossible.active:
            return False
        if hand.lastMeld is None:
            # no last meld specified: This can happen in a scoring game
            # know if saying Mah Jongg is possible
            return False
        if hand.isLimitHand():
            # a limit hand, this rule does not matter anyway
            return False
        if hand.lastMeld.isPung():
            return False # we had two pairs...
        group, value = hand.lastTile
        group = group.lower()
        if group not in 'sbc':
            return True
        intValue = int(value)
        if hand.lastMeld.isChow():
            if hand.lastTile != hand.lastMeld.pairs[1]:
                # left or right tile of a chow:
                if not ((value == '3' and hand.lastMeld.pairs[0][1] == '1')
                        or (value == '7' and hand.lastMeld.pairs[2][1] == '9')):
                    return False
            # now the quick and easy tests are done. For more complex
            # hands we have to do a full test. Note: Always only doing
            # the full test really slows us down by a factor of 2
            shortHand = hand - hand.lastTile
            LastOnlyPossible.active = True
            try:
                otherCallingHands = shortHand.callingHands(doNotCheck=hand.lastTile)
            finally:
                LastOnlyPossible.active = False
            return len(otherCallingHands) == 0
        else:
            if not hand.lastMeld.isPair():
                # special hand like triple knitting
                return False
            for meld in hand.hiddenMelds:
                # look at other hidden melds of same color:
                if meld != hand.lastMeld and meld.pairs[0][0].lower() == group:
                    if meld.isChow():
                        if intValue in [int(meld.pairs[0][1]) - 1, int(meld.pairs[2][1]) + 1]:
                            # pair and adjacent Chow
                            return False
                    elif meld.isPung():
                        if abs(intValue - int(meld.pairs[0][1])) <= 2:
                            # pair and nearby Pung
                            return False
                    elif meld.isSingle():
                        # must be 13 orphans
                        return False
        return True

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
