# -*- coding: utf-8 -*-

"""Copyright (C) 2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

kajongg is free software you can redistribute it and/or modifys
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

# See the user manual for a description of how to define rulesets.
# Names and descriptions must be english and may only contain ascii chars.
# Because kdecore.i18n() only accepts 8bit characters, no unicode.
# The KDE translation teams will "automatically" translate name and
# description into many languages.

from rule import PredefinedRuleset
from log import m18nE, m18n

class ClassicalChinese(PredefinedRuleset):

    """classical chinese rules, standard rules. Serves as a basis
    for local variants. This should be defined such that the
    sum of the differences to the local variants is minimized."""

    def __init__(self, name=None):
        PredefinedRuleset.__init__(self, name or m18nE('Classical Chinese standard'))

    def _initRuleset(self):
        """sets the description"""
        self.description = m18n('Classical Chinese')

    def addManualRules(self):
        """those are actually winner rules but in the kajongg scoring mode they must be selected manually"""
        # applicable only if we have a concealed meld and a declared kong:
        self.winnerRules.createRule('Last Tile Taken from Dead Wall',
                'FLastTileFromDeadWall||Olastsource=e', doubles=1,
                description=m18n('The dead wall is also called kong box: The last 16 tiles of the wall '
                'used as source of replacement tiles'))
        self.winnerRules.createRule('Last Tile is Last Tile of Wall',
                'FIsLastTileFromWall||Olastsource=z', doubles=1,
                description=m18n('Winner said Mah Jong with the last tile taken from the living end of the wall'))
        self.winnerRules.createRule('Last Tile is Last Tile of Wall Discarded',
                'FIsLastTileFromWallDiscarded||Olastsource=Z', doubles=1,
                description=m18n('Winner said Mah Jong by claiming the last tile taken from the living end of the '
                'wall, discarded by another player'))
        self.winnerRules.createRule('Robbing the Kong', r'FRobbingKong||Olastsource=k', doubles=1,
                description=m18n('Winner said Mah Jong by claiming the 4th tile of a kong another player '
                'just declared'), debug=True)
        self.winnerRules.createRule('Mah Jongg with Original Call',
                'FMahJonggWithOriginalCall||Odeclaration=a', doubles=1,
                description=m18n(
                'Just before the first discard, a player can declare Original Call meaning she needs only one '
                'tile to complete the hand and announces she will not alter the hand in any way (except bonus tiles)'))
        self.winnerRules.createRule('Dangerous Game', 'FDangerousGame||Opayforall',
                description=m18n('In some situations discarding a tile that has a high chance to help somebody to win '
                'is declared to be dangerous, and if that tile actually makes somebody win, the discarder '
                'pays the winner for all'))
        self.winnerRules.createRule('Twofold Fortune', 'FTwofoldFortune||Odeclaration=t',
                limits=1, description=m18n('Kong after Kong: Declare Kong and a second Kong with the replacement '
                'tile and Mah Jong with the second replacement tile'))
        # limit hands:
        self.winnerRules.createRule('Blessing of Heaven', 'FBlessingOfHeaven||Olastsource=1', limits=1,
                description=m18n('East says Mah Jong with the unmodified dealt tiles'))
        self.winnerRules.createRule('Blessing of Earth', 'FBlessingOfEarth||Olastsource=1', limits=1,
                description=m18n('South, West or North says Mah Jong with the first tile discarded by East'))
        self.winnerRules.createRule('East won nine times in a row', 'FEastWonNineTimesInARow||Orotate', limits=1,
                description=m18n('If that happens, East gets a limit score and the winds rotate'))

    def addPenaltyRules(self):
        """as the name says"""
        self.penaltyRules.createRule(
                'False Naming of Discard, Claimed for Mah Jongg and False Declaration of Mah Jongg',
                'Oabsolute payers=2 payees=2', points = -300)

    def addHandRules(self):
        """as the name says"""
        self.handRules.createRule('Own Flower and Own Season', 'FOwnFlowerOwnSeason', doubles=1)
        self.handRules.createRule('All Flowers', 'FAllFlowers', doubles=1)
        self.handRules.createRule('All Seasons', 'FAllSeasons', doubles=1)
        self.handRules.createRule('Three Concealed Pongs', 'FThreeConcealedPongs', doubles=1)
        self.handRules.createRule('Long Hand', r'FLongHand||Oabsolute', points=0,
                description=m18n('The hand contains too many tiles'))

    def addParameterRules(self):
        """as the name says"""
        self.parameterRules.createRule('Points Needed for Mah Jongg', 'intminMJPoints', parameter=0)
        self.parameterRules.createRule('Minimum number of doubles needed for Mah Jongg',
                'intminMJDoubles', parameter=0)
        self.parameterRules.createRule('Points for a Limit Hand', 'intlimit||Omin=1', parameter=500)
        self.parameterRules.createRule('Play with the roof off', 'boolroofOff', parameter=False,
                description=m18n('Play with no upper scoring limit'))
        self.parameterRules.createRule('Claim Timeout', 'intclaimTimeout', parameter=10)
        self.parameterRules.createRule('Size of Kong Box', 'intkongBoxSize', parameter=16,
                description=m18n('The Kong Box is used for replacement tiles when declaring kongs'))
        self.parameterRules.createRule('Play with Bonus Tiles', 'boolwithBonusTiles', parameter=True,
                description=m18n('Bonus tiles increase the luck factor'))
        self.parameterRules.createRule('Minimum number of rounds in game', 'intminRounds', parameter=4)
        self.parameterRules.createRule('number of allowed chows', 'intmaxChows', parameter=4,
                description=m18n('The number of chows a player may build'))
        self.parameterRules.createRule('must declare calling hand',
                'boolmustDeclareCallingHand', parameter=False,
                description=m18n('Mah Jongg is only allowed after having declared to have a calling hand'))
        self.parameterRules.createRule('Standard Rotation', 'FStandardRotation||Orotate||Ointernal')

    def loadRules(self):
        """define the rules"""
        self.addParameterRules() # must be first!
        self.addPenaltyRules()
        self.addHandRules()
        self.addManualRules()
        self.winnerRules.createRule('Last Tile Completes Pair of 2..8', 'FLastTileCompletesPairMinor', points=2)
        self.winnerRules.createRule('Last Tile Completes Pair of Terminals or Honors',
                'FLastTileCompletesPairMajor', points=4)
        self.winnerRules.createRule('Last Tile is Only Possible Tile', 'FLastOnlyPossible', points=2)
        self.winnerRules.createRule('Won with Last Tile Taken from Wall', 'FLastFromWall', points=2)

        self.winnerRules.createRule('Zero Point Hand', 'FZeroPointHand', doubles=1,
                description=m18n('The hand has 0 basis points excluding bonus tiles'))
        self.winnerRules.createRule('No Chow', 'FNoChow', doubles=1)
        self.winnerRules.createRule('Only Concealed Melds', 'FOnlyConcealedMelds', doubles=1)
        self.winnerRules.createRule('False Color Game', 'FFalseColorGame', doubles=1,
                description=m18n('Only same-colored tiles (only bamboo/stone/character) '
                'plus any number of winds and dragons'))
        self.winnerRules.createRule('True Color Game', 'FTrueColorGame', doubles=3,
                description=m18n('Only same-colored tiles (only bamboo/stone/character)'))
        self.winnerRules.createRule('Concealed True Color Game', 'FConcealedTrueColorGame',
                limits=1, description=m18n('All tiles concealed and of the same suit, no honors'))
        self.winnerRules.createRule('Only Terminals and Honors', 'FOnlyMajors', doubles=1,
                description=m18n('Only winds, dragons, 1 and 9'))
        self.winnerRules.createRule('Only Honors', 'FOnlyHonors', limits=1,
                description=m18n('Only winds and dragons'))
        self.winnerRules.createRule('Hidden Treasure', 'FHiddenTreasure', limits=1,
                description=m18n('Only hidden Pungs or Kongs, last tile from wall'))
        self.winnerRules.createRule('Heads and Tails', 'FAllTerminals', limits=1,
                description=m18n('Only 1 and 9'))
        self.winnerRules.createRule('Fourfold Plenty', 'FFourfoldPlenty', limits=1,
                description=m18n('4 Kongs'))
        self.winnerRules.createRule('Three Great Scholars', 'FThreeGreatScholars', limits=1,
                description=m18n('3 Pungs or Kongs of dragons'))
        self.winnerRules.createRule('Four Blessings Hovering over the Door',
                'FFourBlessingsHoveringOverTheDoor', limits=1,
                description=m18n('4 Pungs or Kongs of winds'))
        self.winnerRules.createRule('Imperial Jade', 'FAllGreen', limits=1,
                description=m18n('Only green tiles: Green dragon and Bamboo 2,3,4,6,8'))
        self.winnerRules.createRule('Gathering the Plum Blossom from the Roof',
                'FGatheringPlumBlossomFromRoof', limits=1,
                description=m18n('Mah Jong with stone 5 from the dead wall'))
        self.winnerRules.createRule('Plucking the Moon from the Bottom of the Sea', 'FPluckingMoon', limits=1,
                description=m18n('Mah Jong with the last tile from the wall being a stone 1'))
        self.winnerRules.createRule('Scratching a Carrying Pole', 'FScratchingPole', limits=1,
                description=m18n('Robbing the Kong of bamboo 2'))

        # only hands matching an mjRule can win. Keep this list as short as
        # possible. If a special hand matches the standard pattern, do not put it here
        # All mjRule functions must have a winningTileCandidates() method
        self.mjRules.createRule('Standard Mah Jongg', 'FStandardMahJongg', points=20)
        # option internal makes it not show up in the ruleset editor
        self.mjRules.createRule('Nine Gates', 'FGatesOfHeaven||OlastExtra', limits=1,
                description=m18n('All tiles concealed of same color: Values 1-1-1-2-3-4-5-6-7-8-9-9-9 completed '
                'with another tile of the same color (from wall or discarded)'))
        self.mjRules.createRule('Thirteen Orphans', 'FThirteenOrphans||Omayrobhiddenkong', limits=1,
            description=m18n('13 single tiles: All dragons, winds, 1, 9 and a 14th tile building a pair '
            'with one of them'))

        # doubling melds:
        self.meldRules.createRule('Pung/Kong of Dragons', 'FDragonPungKong',
            explainTemplate='{meldName}', doubles=1)
        self.meldRules.createRule('Pung/Kong of Own Wind', 'FOwnWindPungKong',
            explainTemplate='{meldType} of Own Wind ({value})', doubles=1)
        self.meldRules.createRule('Pung/Kong of Round Wind', 'FRoundWindPungKong',
            explainTemplate='{meldType} of Round Wind ({value})', doubles=1)

        # exposed melds:
        self.meldRules.createRule('Exposed Kong', 'FExposedMinorKong',
            explainTemplate='{meldName}', points=8)
        self.meldRules.createRule('Exposed Kong of Terminals', 'FExposedTerminalsKong',
            explainTemplate='{meldName}', points=16)
        self.meldRules.createRule('Exposed Kong of Honors', 'FExposedHonorsKong',
            explainTemplate='{meldName}', points=16)

        self.meldRules.createRule('Exposed Pung', 'FExposedMinorPung',
            explainTemplate='{meldName}', points=2)
        self.meldRules.createRule('Exposed Pung of Terminals', 'FExposedTerminalsPung',
            explainTemplate='{meldName}', points=4)
        self.meldRules.createRule('Exposed Pung of Honors', 'FExposedHonorsPung',
            explainTemplate='{meldName}', points=4)

        # concealed melds:
        self.meldRules.createRule('Concealed Kong', 'FConcealedMinorKong',
            explainTemplate='{meldName}', points=16)
        self.meldRules.createRule('Concealed Kong of Terminals', 'FConcealedTerminalsKong',
            explainTemplate='{meldName}', points=32)
        self.meldRules.createRule('Concealed Kong of Honors', 'FConcealedHonorsKong',
            explainTemplate='{meldName}', points=32)

        self.meldRules.createRule('Concealed Pung', 'FConcealedMinorPung',
            explainTemplate='{meldName}', points=4)
        self.meldRules.createRule('Concealed Pung of Terminals', 'FConcealedTerminalsPung',
            explainTemplate='{meldName}', points=8)
        self.meldRules.createRule('Concealed Pung of Honors', 'FConcealedHonorsPung',
            explainTemplate='{meldName}', points=8)

        self.meldRules.createRule('Pair of Own Wind', 'FOwnWindPair',
            explainTemplate='Pair of Own Wind ({value})', points=2)
        self.meldRules.createRule('Pair of Round Wind', 'FRoundWindPair',
            explainTemplate='Pair of Round Wind ({value})', points=2)
        self.meldRules.createRule('Pair of Dragons', 'FDragonPair',
            explainTemplate='{meldName}', points=2)

        # bonus tiles:
        self.meldRules.createRule('Flower', 'FFlower',
            explainTemplate='{meldName}', points=4)
        self.meldRules.createRule('Season', 'FSeason',
            explainTemplate='{meldName}', points=4)

class ClassicalChineseDMJL(ClassicalChinese):
    """classical chinese rules, German rules"""

    def __init__(self, name=None):
        ClassicalChinese.__init__(self, name or m18nE('Classical Chinese DMJL'))

    def _initRuleset(self):
        """sets the description"""
        ClassicalChinese._initRuleset(self)
        self.description = m18n('Classical Chinese as defined by the Deutsche Mah Jongg Liga (DMJL) e.V.')

    def loadRules(self):
        ClassicalChinese.loadRules(self)
        # the squirming snake is only covered by standard mahjongg rule if tiles are ordered
        self.mjRules.createRule('Squirming Snake', 'FSquirmingSnake', limits=1,
                description=m18n('All tiles of same color. Pung or Kong of 1 and 9, pair of 2, 5 or 8 and two '
                'Chows of the remaining values'))
        self.handRules.createRule('Little Three Dragons', 'FLittleThreeDragons', doubles=1,
                description=m18n('2 Pungs or Kongs of dragons and 1 pair of dragons'))
        self.handRules.createRule('Big Three Dragons', 'FBigThreeDragons', doubles=2,
                description=m18n('3 Pungs or Kongs of dragons'))
        self.handRules.createRule('Little Four Joys', 'FLittleFourJoys', doubles=1,
                description=m18n('3 Pungs or Kongs of winds and 1 pair of winds'))
        self.handRules.createRule('Big Four Joys', 'FBigFourJoys', doubles=2,
                description=m18n('4 Pungs or Kongs of winds'))

        self.winnerRules['OnlyHonors'].doubles = 2

        self.penaltyRules.createRule('False Naming of Discard, Claimed for Chow', points = -50)
        self.penaltyRules.createRule('False Naming of Discard, Claimed for Pung/Kong', points = -100)
        self.penaltyRules.createRule('False Declaration of Mah Jongg by One Player',
                'Oabsolute payees=3', points = -300)
        self.penaltyRules.createRule('False Declaration of Mah Jongg by Two Players',
                'Oabsolute payers=2 payees=2', points = -300)
        self.penaltyRules.createRule('False Declaration of Mah Jongg by Three Players',
                'Oabsolute payers=3', points = -300)
        self.penaltyRules.createRule('False Naming of Discard, Claimed for Mah Jongg',
                'Oabsolute payees=3', points = -300)

class ClassicalChineseBMJA(ClassicalChinese):
    """classical chinese rules, British rules"""

    def __init__(self, name=None):
        ClassicalChinese.__init__(self, name or m18nE('Classical Chinese BMJA'))

    def _initRuleset(self):
        """sets the description"""
        ClassicalChinese._initRuleset(self)
        self.description = m18n('Classical Chinese as defined by the British Mah-Jong Association')

    def addParameterRules(self):
        """those differ for BMJA from standard"""
        ClassicalChinese.addParameterRules(self)
        self.parameterRules['kongBoxSize'].parameter = 14
        self.parameterRules['maxChows'].parameter = 1
        self.parameterRules['limit'].parameter = 1000
        self.parameterRules['mustDeclareCallingHand'].parameter = True

    def loadRules(self):
# TODO: we need a separate part for any number of announcements. Both r for robbing kong and a for
# Original Call can be possible together.
        ClassicalChinese.loadRules(self)
        del self.winnerRules['ZeroPointHand']
        originalCall = self.winnerRules.pop('MahJonggwithOriginalCall')
        self.winnerRules.createRule('Original Call', originalCall.definition, doubles=1,
            description=originalCall.description)
        del self.mjRules['NineGates']
        self.mjRules.createRule('Gates of Heaven', 'FGatesOfHeaven||Opair28', limits=1,
                description=m18n('All tiles concealed of same color: Values 1-1-1-2-3-4-5-6-7-8-9-9-9 and '
                'another tile 2..8 of the same color'))
        self.mjRules.createRule('Wriggling Snake', 'FWrigglingSnake', limits=1,
                description=m18n('Pair of 1s and a run from 2 to 9 in the same suit with each of the winds'))
        self.mjRules.createRule('Triple Knitting', 'FTripleKnitting', limits=0.5,
                description=m18n('Four sets of three tiles in the different suits and a pair: No Winds or Dragons'))
        self.mjRules.createRule('Knitting', 'FKnitting', limits=0.5,
                description=m18n('7 pairs of tiles in any 2 out of 3 suits; no Winds or Dragons'))
        self.mjRules.createRule('All pair honors', 'FAllPairHonors', limits=0.5,
                description=m18n('7 pairs of 1s/9s/Winds/Dragons'))
        del self.handRules['OwnFlowerandOwnSeason']
        del self.handRules['ThreeConcealedPongs']
        self.meldRules.createRule('Own Flower', 'FOwnFlower', doubles=1)
        self.meldRules.createRule('Own Season', 'FOwnSeason', doubles=1)
        del self.winnerRules['LastTileTakenfromDeadWall']
        del self.winnerRules['HiddenTreasure']
        del self.winnerRules['FalseColorGame']
        del self.winnerRules['ConcealedTrueColorGame']
        del self.winnerRules['Eastwonninetimesinarow']
        del self.winnerRules['LastTileCompletesPairof28']
        del self.winnerRules['LastTileCompletesPairofTerminalsorHonors']
        del self.winnerRules['LastTileisOnlyPossibleTile']
        del self.winnerRules['TrueColorGame']
        del self.winnerRules['ThreeGreatScholars'] 
        self.winnerRules.createRule('Buried Treasure', 'FBuriedTreasure', limits=1,
                description=m18n('Concealed pungs of one suit with winds/dragons and a pair'))
        self.winnerRules.createRule('Purity', 'FPurity', doubles=3,
                description=m18n('Only same-colored tiles (no chows, dragons or winds)'))
        self.winnerRules.createRule('Three Great Scholars', 'FThreeGreatScholars||Onochow', limits=1,
                description=m18n('3 Pungs or Kongs of dragons plus any pung/kong and a pair'))
        orphans = self.mjRules.pop('ThirteenOrphans')
        self.mjRules.createRule('The 13 Unique Wonders', orphans.definition, limits=1, description=orphans.description)
        self.handRules['AllFlowers'].score.doubles = 2
        self.handRules['AllSeasons'].score.doubles = 2
        self.penaltyRules.createRule('False Naming of Discard, Claimed for Chow/Pung/Kong', points = -50)
        self.penaltyRules.createRule('False Declaration of Mah Jongg by One Player',
                'Oabsolute payees=3', limits = -0.5)
        self.winnerRules.createRule('False Naming of Discard, Claimed for Mah Jongg', 'FFalseDiscardForMJ||Opayforall')

        self.loserRules.createRule('Calling for Only Honors', 'FCallingHand||Ohand=OnlyHonors', limits=0.4)
        self.loserRules.createRule('Calling for Wriggling Snake', 'FCallingHand||Ohand=WrigglingSnake', limits=0.4)
        self.loserRules.createRule('Calling for Triple Knitting', 'FCallingHand||Ohand=TripleKnitting', limits=0.2)
        self.loserRules.createRule('Calling for Gates of Heaven', 'FCallingHand||Ohand=GatesofHeaven||Opair28',
                limits=0.4)
        self.loserRules.createRule('Calling for Knitting', 'FCallingHand||Ohand=Knitting', limits=0.2)
        self.loserRules.createRule('Calling for Imperial Jade', 'FCallingHand||Ohand=ImperialJade', limits=0.4)
        self.loserRules.createRule('Calling for The 13 Unique Wonders', 'FCallingHand||Ohand=The13UniqueWonders',
                limits=0.4)
        self.loserRules.createRule('Calling for Three Great Scholars', 'FCallingHand||Ohand=ThreeGreatScholars',
                limits=0.4)
        self.loserRules.createRule('Calling for All pair honors', 'FCallingHand||Ohand=Allpairhonors', limits=0.2)
        self.loserRules.createRule('Calling for Heads and Tails', 'FCallingHand||Ohand=HeadsandTails', limits=0.4)
        self.loserRules.createRule('Calling for Four Blessings Hovering over the Door',
                'FCallingHand||Ohand=FourBlessingsHoveringovertheDoor', limits=0.4)
        self.loserRules.createRule('Calling for Buried Treasure', 'FCallingHand||Ohand=BuriedTreasure', limits=0.4)
        self.loserRules.createRule('Calling for Fourfold Plenty', 'FCallingHand||Ohand=FourfoldPlenty', limits=0.4)
        self.loserRules.createRule('Calling for Purity', 'FCallingHand||Ohand=Purity', doubles=3)

# add new predefined rulesets here
if not PredefinedRuleset.classes:
    PredefinedRuleset.classes.add(ClassicalChineseDMJL)
    PredefinedRuleset.classes.add(ClassicalChineseBMJA)
