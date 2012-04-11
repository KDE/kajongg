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
        self.timeSum = 0.0
        self.count = 0
        self.definition = ''

class FunctionDragonPungKong(Function):
    """x"""
    @staticmethod
    def appliesToMeld(hand, meld):
        """see class docstring"""
        return len(meld) >= 3 and meld in hand.dragonMelds

class FunctionRoundWindPungKong(Function):
    """x"""
    @staticmethod
    def appliesToMeld(hand, meld):
        """see class docstring"""
        return len(meld) >= 3 and meld.pairs[0].lower() == 'w' + hand.roundWind

class FunctionExposedMinorPung(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        return meld.isPung() and meld.pairs.isLower(0, 3) and meld.pairs[0][1] in '2345678'

class FunctionExposedTerminalsPung(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        return meld.isPung() and meld.pairs.isLower(0, 3) and meld.pairs[0][1] in '19'

class FunctionExposedHonorsPung(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        return meld.isPung() and meld.pairs[0][0] in 'wd'

class FunctionExposedMinorKong(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        return len(meld) == 4 and meld.pairs.isLower(0, 3) and meld.pairs[0][1] in '2345678'

class FunctionExposedTerminalsKong(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        return len(meld) == 4 and meld.pairs.isLower(0, 3) and meld.pairs[0][1] in '19'

class FunctionExposedHonorsKong(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        return len(meld) == 4 and meld.pairs.isLower(0, 3) and meld.pairs[0][0] in 'wd'

class FunctionConcealedMinorPung(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        return meld.isPung() and meld.pairs.isUpper(0, 3) and meld.pairs[0][1] in '2345678'

class FunctionConcealedTerminalsPung(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        return meld.isPung() and meld.pairs.isUpper(0, 3) and meld.pairs[0][1] in '19'

class FunctionConcealedHonorsPung(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        return meld.isPung() and meld.pairs[0][0] in 'WD'

class FunctionConcealedMinorKong(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        return len(meld) == 4 and meld.state == CONCEALED and meld.pairs[0][1] in '2345678'

class FunctionConcealedTerminalsKong(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        return len(meld) == 4 and meld.state == CONCEALED and meld.pairs[0][1] in '19'

class FunctionConcealedHonorsKong(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        return len(meld) == 4 and meld.state == CONCEALED and meld.pairs[0][0] in 'wd'

class FunctionOwnWindPungKong(Function):
    """x"""
    @staticmethod
    def appliesToMeld(hand, meld):
        """see class docstring"""
        return len(meld) >= 3 and meld.pairs[0].lower() == 'w' + hand.ownWind

class FunctionOwnWindPair(Function):
    """x"""
    @staticmethod
    def appliesToMeld(hand, meld):
        """see class docstring"""
        return len(meld) == 2 and meld.pairs[0].lower() == 'w' + hand.ownWind

class FunctionRoundWindPair(Function):
    """x"""
    @staticmethod
    def appliesToMeld(hand, meld):
        """see class docstring"""
        return len(meld) == 2 and meld.pairs[0].lower() == 'w' + hand.roundWind

class FunctionDragonPair(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        return len(meld) == 2 and meld.pairs[0][0].lower() == 'd'

class FunctionLastTileCompletesPairMinor(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return (hand.lastMeld and len(hand.lastMeld) == 2
            and hand.lastMeld.pairs[0][0] == hand.lastMeld.pairs[1][0]
            and hand.lastTile and hand.lastTile[1] in '2345678')

class FunctionFlower1(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return 'fe' in hand.fsMeldNames

class FunctionFlower2(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return 'fs' in hand.fsMeldNames

class FunctionFlower3(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return 'fw' in hand.fsMeldNames

class FunctionFlower4(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return 'fn' in hand.fsMeldNames

class FunctionSeason1(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return 'ye' in hand.fsMeldNames

class FunctionSeason2(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return 'ys' in hand.fsMeldNames

class FunctionSeason3(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return 'yw' in hand.fsMeldNames

class FunctionSeason4(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return 'yn' in hand.fsMeldNames

class FunctionLastTileCompletesPairMajor(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return (hand.lastMeld and len(hand.lastMeld) == 2
            and hand.lastMeld.pairs[0][0] == hand.lastMeld.pairs[1][0]
            and hand.lastTile and hand.lastTile[1] not in '2345678')

class FunctionLastFromWall(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return hand.lastTile and hand.lastTile[0].isupper()

class FunctionZeroPointHand(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return sum(x.score.points for x in hand.melds) == 0

class FunctionNoChow(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return not any(x.isChow() for x in hand.melds)

class FunctionOnlyConcealedMelds(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return not any((x.state == EXPOSED and x.meldType != CLAIMEDKONG) for x in hand.melds)

class FunctionFalseColorGame(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        suits = set(x[0].lower() for x in hand.tileNames)
        dwSet = set('dw')
        return dwSet & suits and len(suits - dwSet) == 1

class FunctionTrueColorGame(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        suits = set(x[0].lower() for x in hand.tileNames)
        return len(suits) == 1 and suits < set('sbc')

class FunctionConcealedTrueColorGame(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        suits = set(x[0].lower() for x in hand.tileNames)
        if len(suits) != 1 or not (suits < set('sbc')):
            return False
        return not any((x.state == EXPOSED and x.meldType != CLAIMEDKONG) for x in hand.melds)

class FunctionOnlyMajors(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        values = set(x[1] for x in hand.tileNames)
        return not values - set('grbeswn19')

class FunctionOnlyHonors(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        values = set(x[1] for x in hand.tileNames)
        return not values - set('grbeswn')

class FunctionHiddenTreasure(Function):
    """x"""
    # TODO: BMJA calls this Buried Treasure and does not require
    # the last tile to come from the wall. Parametrize.
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return (not any(((x.state == EXPOSED and x.meldType != CLAIMEDKONG) or x.isChow()) for x in hand.melds)
            and hand.lastTile and hand.lastTile[0].isupper()
            and len(hand.melds) == 5)

class FunctionAllTerminals(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        values = set(x[1] for x in hand.tileNames)
        return not values - set('19')

class FunctionSquirmingSnake(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
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

class FunctionWrigglingSnake(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
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

class FunctionTripleKnitting(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
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

class FunctionKnitting(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
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

class FunctionAllPairHonors(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        if any(x[1] in '2345678' for x in hand.tileNames):
            return False
        if len(hand.declaredMelds) > 1:
            return False
        values = list(x[1] for x in hand.tileNames)
        if len(set(values)) != 7:
            return False
        valueCounts = sorted([len([x for x in hand.tileNames if x[1] == y]) for y in set(values)])
        return set(valueCounts) == set([2])

class FunctionFourfoldPlenty(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return len(hand.tileNames) == 18

class FunctionThreeGreatScholars(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return (FunctionStandardMahJongg.appliesToHand(hand)
            and FunctionBigThreeDragons.appliesToHand(hand))

class FunctionBigThreeDragons(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return len([x for x in hand.dragonMelds if len(x) >= 3]) == 3

class FunctionBigFourJoys(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return len([x for x in hand.windMelds if len(x) >= 3]) == 4

class FunctionLittleFourJoys(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return (len([x for x in hand.windMelds if len(x) >= 3]) == 3
            and len([x for x in hand.windMelds if len(x) == 2]) == 1)

class FunctionLittleThreeDragons(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return (len([x for x in hand.dragonMelds if len(x) >= 3]) == 2
            and len([x for x in hand.dragonMelds if len(x) == 2]) == 1)

class FunctionFourBlessingsHoveringOverTheDoor(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return len([x for x in hand.melds if len(x) >= 3 and x.pairs[0][0] in 'wW']) == 4

class FunctionAllGreen(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        tiles = set(x.lower() for x in hand.tileNames)
        return hand.won and tiles < set(['b2', 'b3', 'b4', 'b5', 'b6', 'b8', 'dg'])

class FunctionLastTileFromWall(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return hand.won and hand.lastSource == 'w'

class FunctionLastTileFromDeadWall(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return hand.won and hand.lastSource == 'e'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return hand.lastSource == 'w'

class FunctionIsLastTileFromWall(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return hand.won and hand.lastSource == 'z'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return hand.won and hand.lastSource == 'w'

class FunctionIsLastTileFromWallDiscarded(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return hand.won and hand.lastSource == 'Z'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return hand.lastSource == 'd'

class FunctionRobbingKong(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return hand.won and hand.lastSource == 'k'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return (hand.lastSource and hand.lastSource in 'kwd'
            and hand.lastTile and hand.lastTile[0].islower()
            and [x.lower() for x in hand.tileNames].count(hand.lastTile.lower()) < 2)

class FunctionGatheringPlumBlossomFromRoof(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        if not hand.won:
            return False
        if FunctionLastTileFromDeadWall.appliesToHand(hand):
            return hand.lastTile and hand.lastTile == 'S5'
        return False

class FunctionPluckingMoon(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return hand.won and hand.lastSource == 'z' and hand.lastTile and hand.lastTile == 'S1'

class FunctionScratchingPole(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return hand.won and hand.lastSource and hand.lastSource == 'k' and hand.lastTile and hand.lastTile == 'b2'

class FunctionStandardMahJongg(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return (len(hand.melds) == 5
            and set(len(x) for x in hand.melds) <= set([2,3,4])
            and not any(x.meldType == REST for x in hand.melds)
            and hand.ruleset.maxChows >= len([x for x in hand.melds if x.isChow()]))

class FunctionNineGates(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return FunctionGatesOfHeaven.appliesToHand(hand, lastCompletesPair=True)

class FunctionGatesOfHeaven(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand, lastCompletesPair=False):
        """see class docstring"""
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
        return not lastCompletesPair or values == hand.lastTile[1]

class FunctionThirteenOrphans(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return set(x.lower() for x in hand.tileNames) == elements.majors

class FunctionOwnFlower(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        fsPairs = list(x.pairs[0] for x in hand.fsMelds)
        return 'f' + hand.ownWind in fsPairs

class FunctionOwnSeason(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        fsPairs = list(x.pairs[0] for x in hand.fsMelds)
        return 'y' + hand.ownWind in fsPairs

class FunctionOwnFlowerOwnSeason(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return (FunctionOwnFlower.appliesToHand(hand)
            and FunctionOwnSeason.appliesToHand(hand))

class FunctionAllFlowers(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return len([x for x in hand.fsMelds if x.pairs[0][0] == 'f']) == 4

class FunctionAllSeasons(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return len([x for x in hand.fsMelds if x.pairs[0][0] == 'y']) == 4

class FunctionThreeConcealedPongs(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return len([x for x in hand.melds if (
            x.state == CONCEALED or x.meldType == CLAIMEDKONG) and (x.isPung() or x.isKong())]) >= 3

class FunctionMahJonggWithOriginalCall(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return (hand.won and 'a' in hand.announcements
            and len([x for x in hand.melds if x.state == EXPOSED]) < 3)

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        # one may be claimed before declaring OC and one for going MJ
        # the previous regex was too strict
        exp = [x for x in hand.melds if x.state == EXPOSED]
        return hand.won and len(exp) < 3

class FunctionTwofoldFortune(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return hand.won and 't' in hand.announcements

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        kungs = [x for x in hand.melds if len(x) == 4]
        return hand.won and len(kungs) >= 2

class FunctionBlessingOfHeaven(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return hand.won and hand.ownWind == 'e' and hand.lastSource == '1'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return (hand.won and hand.ownWind == 'e'
            and hand.lastSource and hand.lastSource in 'wd'
            and not (set(hand.announcements) - set('a')))

class FunctionBlessingOfEarth(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return hand.won and hand.ownWind != 'e' and hand.lastSource == '1'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return (hand.won and hand.ownWind != 'e'
            and hand.lastSource and hand.lastSource in 'wd'
            and not (set(hand.announcements) - set('a')))

class FunctionLongHand(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        offset = hand.handLenOffset()
        return (not hand.won and offset > 0) or offset > 1

class FunctionDangerousGame(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return not hand.won

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return not hand.won

class FunctionLastOnlyPossible(Function):
    """check if the last tile was the only one possible for winning"""

    active = False

    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        if FunctionLastOnlyPossible.active:
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
            FunctionLastOnlyPossible.active = True
            try:
                otherCallingHands = shortHand.callingHands(doNotCheck=hand.lastTile)
            finally:
                FunctionLastOnlyPossible.active = False
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
                    name = glob.__name__.replace('Function', '')
                    Function.functions[name] = glob

__scanSelf()
