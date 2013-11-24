#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
"""

from common import Debug
import unittest
from hand import Hand, Score
from tile import TileList
from predefined import ClassicalChineseDMJL, ClassicalChineseBMJA
from log import initLog

RULESETS = []

# test each of those rulesets twice: once with limit, once with roof off
for testRuleset in [ClassicalChineseDMJL, ClassicalChineseBMJA] * 2:
    _ = testRuleset()
    _.load()
    RULESETS.append(_)

for _ in RULESETS[2:]:
    _.roofOff = True

PROGRAM = None

class Regex(unittest.TestCase):
    """tests lots of hand examples. We might want to add comments which test should test which rule"""
    # pylint: disable=too-many-public-methods

    def __init__(self, arg):
        unittest.TestCase.__init__(self, arg)

    def testPartials(self):
        """some partial hands"""
        self.scoreTest(b'drdrdr fe mes Ldrdrdrdr', [Score(8, 1), Score(8, 2)])
        self.scoreTest(b'fe mes', [Score(4), Score(4, 1)])
        self.scoreTest(b'fs fw fe fn mes', [Score(16, 1), Score(16, 3)])
        self.scoreTest(b'fs ys mse', [Score(8, 1), Score(8, 2)])
        self.scoreTest(b'drdrdr mes Ldrdrdrdr', Score(4, 1))
    def testZeroHand(self):
        """zero hand games"""
        self.scoreTest(b'c1c2c3 c7c8c9 b2b3b4 c5c5 s1s2s3 fw yw Mwn Lc1c1c2c3',
            [Score(points=28, doubles=2), Score()])
        self.scoreTest(b'c1c2c3 c7c8c9 b2b3b4 drdr s1s2s3 fw yw Mwn Lc1c1c2c3',
            [Score(points=30, doubles=1), Score()])
    def testFalseColorGame(self):
        """false color games"""
        self.scoreTest(b'c1c1c1 c7c7c7 c2c3c4 c5c5 c6c6c6 Mwn Lc5c5c5', [Score(34, 3), Score(28)])
        self.scoreTest(b'c1c2c3 wewewe drdrdr dbdb DgDgDg Mwn Ldbdbdb', [Score(46, 4), Score(38, 2)])
        self.scoreTest(b's1s1s1 wewewe c2c3c4 c5c5 c6c6c6 Mwn Lc5c5c5', [Score(36), Score(30)])
        self.scoreTest(b'RB1B1B1B1B2B3B4B5B6B7B8B9DrDr fe ys Mwe LDrDrDr', [Score(48, 2), Score()])
        self.scoreTest(b'b1B1B1b1 RB2B3B4B5B6B7B8B8B8 DrDr fe ys Mwe LDrDrDr', [Score(76, 2), Score()])
        self.scoreTest(b'b1B1B1b1 RB2B2B2B5B6B7B8B8B8 DrDr fe ys Mwe LDrDrDr', [Score(80, 3), Score(72, 1)])
    def testWrigglingSnake(self):
        """the wriggling snake as in BMJA"""
        self.scoreTest(b'c1c1 c2c3c4 c5c6c7 RC8C9WeWwWsWn Mee Lc1c1c1', [Score(), Score(limits=1)])
        self.scoreTest(b'c2c3c4 c5c6c7 RC1C1C8C9WeWwWsWn Mee LC1C1C1', [Score(), Score(limits=1)])
        self.scoreTest(b'c2c3c4 c5c6c7 RC1C1C8C9WeWwWsWn Mee LWnWn', [Score(), Score(limits=1)])
        self.scoreTest(b'c1c1 c2c3c4 c5c6c7 RC8C9WwWwWsWn Mee Lc1c1c1', [Score(), Score()])
        self.callingTest(b'RS1S3WwS6WsS3S3WnWeS5 s7s8s9 fs mse', b'')
        self.callingTest(b'RS1S2WwS6WsS3S3WnWeS5 s7s8s9 fs mse', b'')
        self.callingTest(b'RS1S2WwS6WsS3S4WnWeS5 s7s8s9 fs mse', [b'', b's1'])
        self.callingTest(b'RS1S2WwS6WsS3S4WnWeS1 s7s8s9 fs mse', [b'', b's5'])
    def testSquirmingSnake(self):
        """the winding snake"""
        self.scoreTest(b'c1c1c1 c3c4c5 c9c9c9 c6c7c8 RC2C2 Mee Lc1c1c1c1', [Score(limits=1), Score()])
        self.scoreTest(b'c1c1c1 c4c5c6 c9c9c9 c6c7c8 RC2C2 Mee Lc1c1c1c1', [Score(points=28, doubles=3), Score()])
        self.scoreTest(b'c1c1c1 c3c4c5 c9c9c9 c6c7c8 RS2S2 Mee Lc1c1c1c1', [Score(points=28), Score()])
        self.scoreTest(b's1s1s1 s2s3s4 s9s9s9 s6s7s8 RS5S5 Mee Ls1s1s1s1', [Score(limits=1), Score()])
        self.scoreTest(b'b1b1b1 c3c4c5 c6c7c8 c9c9c9 RC2C2 Mee Lc3c3c4c5', [Score(points=28), Score()])
        self.scoreTest(b'b1b1b1 c3c4c5 c6c7c8 c9c9c9 RC2C2 Mee Lc4c3c4c5', [Score(points=32), Score()])
        self.scoreTest(b'RC1C1C1C2C3C4C5C6C7C8C9C9C9C5 Mee LC5', [Score(limits=1), Score(limits=1)])
        self.scoreTest(b'RC1C1C1C3C4C5C6C7C8C9C9C9C5 mee LC3', [Score(16), Score(limits=0.4)])
        self.scoreTest(b'RC1C1C2C3C4C5C6C7C8C9C9C9C5 mee LC3', [Score(8), Score(limits=0.4)])
    def testPurity(self):
        """Purity BMJA"""
        self.scoreTest(b'b1b1b1b1 RB2B3B4B5B6B7B8B8B2B2B2 fe fs fn fw Mwe LB3B2B3B4',
                [Score(points=62, doubles=4), Score()])
        self.scoreTest(b'b1b1b1 RB3B3B3B6B6B6B8B8B2B2B2 fe fs fn fw Mwe LB3', [Score(54, 6), Score(54, 7)])
        self.scoreTest(b'b1b1b1 RB3B3B3B6B6B8B8B2B2B2 fe fs fn fw mwe LB3', [Score(28, 1), Score(28, 6)])
        self.scoreTest(b'c1C1C1c1 c3c3c3 c8c8c8 RC4C5C6C7C7 fs fw ys yw Mwe Lc8c8c8c8', [Score(72, 4), Score(72, 2)])
    def testTrueColorGame(self):
        """true color games"""
        self.scoreTest(b'b1b1b1b1 RB2B3B4B5B6B7B8B8B2B2B2 fe fs fn fw Mwe LB3B2B3B4',
                [Score(points=62, doubles=4), Score()])
        self.scoreTest(b'b1b1b1B1 RB2B3B4B5B6B7B8B8B2B2B2 fe fs fn fw Mwe LB3B2B3B4', [Score(limits=1), Score()])
        self.callingTest(b'RB1B2B3B4B5B5B6B6B7B7B8B8B8 mwe LB1', [b'b1b3b4b6b7b9', b''])
    def testOnlyConcealedMelds(self):
        """only concealed melds"""
        self.scoreTest(b'RB1B1B1B1B2B3B4B5B6B7B8B9DrDr fe ys Mwe LDrDrDr', [Score(48, 2), Score()])
        self.scoreTest(b'RB1B1B1B2B2B2B4B4B4B7B8B9DrDr fe ys Mwe LDrDrDr', [Score(56, 3), Score(48, 1)])
        self.scoreTest(b'b1B1B1b1 RB2B3B4B5B6B7B8B8B8DrDr fe ys Mwe LDrDrDr', [Score(76, 2), Score()])
        self.scoreTest(b'b1B1B1b1 RB2B2B2B5B6B7B8B8B8DrDr fe ys Mwe LDrDrDr', [Score(80, 3), Score(72, 1)])

    def testLimitHands(self):
        """various limit hands"""
        self.scoreTest(b'c1c1c1 c9c9 b9b9b9b9 s1s1s1 s9s9s9 Mee Lc1c1c1c1', Score(limits=1))
        self.scoreTest(b'c1c1c1c1 drdr wewewewe c3c3c3C3 s1S1S1s1 Mee Ldrdrdr', Score(limits=1))
        self.scoreTest(b'drdr c1c1c1c1 wewewewe c3c3c3C3 s1S1S1s1 Mee Ldrdrdr', Score(limits=1))
        self.scoreTest(b'c1c1c1c1 wewewewe c3c3c3C3 s1S1S1s1 drdr Mee Ldrdrdr', Score(limits=1))
    def testAllGreen(self):
        """the green hand"""
        self.scoreTest(b'c1c1c1 c7c7c7 c2c3c4 c5c5 c6c6c6 Mwn Lc5c5c5', [Score(34, 3), Score(28)])
        self.scoreTest(b'b2b2b2b2 RDgDgDg b6b6b6 b4b4b4 b8b8 Mee Lb6b6b6b6', Score(limits=1))
        self.scoreTest(b'b2b2b2b2 RDgDg b6b6b6 b4b4b4 b8b8 mee Lb6b6b6b6', [Score(14), Score(limits=0.4)])
        self.scoreTest(b'b1b1b1b1 RDgDgDg b6b6b6 b4b4b4 b8b8 Mee Lb6b6b6b6', [Score(48, 3), Score(48, 2)])
    def testNineGates(self):
        """the nine gates"""
        # DMJL allows 1..9 as last tile, BMJA allows only 2..8
        self.scoreTest(b'RC1C1C1C2C3C4C5C6C7C8C9C9C9C5 Mee LC5', Score(limits=1))
        self.scoreTest(b'RC1C1C1C2C3C4C5C6C7C8C9C9C9C5 Mee LC6', [Score(limits=1), Score(limits=1)])
        self.scoreTest(b'RC1C1C1C2C3C4C5C6C7C8C9C9C9C9 Mee LC9', [Score(limits=1), Score()])
        self.scoreTest(b'RC1C1C1C2C3C4C5C6C7C8C9C9C9C9 Mee LC9', [Score(limits=1), Score()])
        self.scoreTest(b'RC1C1C1C2C3C4C5C6C7C8C9C9C9C5 Mee LC2', [Score(limits=1), Score(limits=1)])
        self.scoreTest(b'RC1C1C1C2C3C4C5C6C7C8C9C9C9C9 Mee LC1', [Score(limits=1), Score()])
        self.scoreTest(b'RC1C1C2C3C4C5C6C7C8C9C9C9C9 mee LC1', [Score(8), Score(8)])
        self.scoreTest(b'RC1C1C2C3C4C5C6C7C8C8C9C9C9 mee LC1', [Score(8), Score(limits=0.4)])
    def testManual(self):
        """some manual rules for manual scoring"""
        # this should actually never happen but anyway we want to be sure that no rule
        # fires on this
        self.scoreTest(b' Mse', Score(points=0))
        self.scoreTest(b' mse', Score(points=0))
    def testThirteenOrphans(self):
        """The 13 orphans"""
        self.scoreTest(b'RC1C9B9B1S1S9WeDgWsWnWwDbDrS1 mes LDgDg', Score())
        self.scoreTest(b'ww RC1C9B9B1S1S9WeDgWsWnDbDrS8 Mes Lww', Score())
        self.scoreTest(b'ww RC1C9B9B1S1S9WeDgWsWnDbDrS9 Mes Lww', Score(limits=1))
        self.scoreTest(b'RC1C9B9B1S1S9S9WeDgWsWnWwDbDr Mes LDrDr', Score(limits=1))
        self.scoreTest(b'dr RC1C9B9B1S1S9S9WeDgWsWnWwDb Mes Ldrdr', Score(limits=1))
        self.scoreTest(b'RC1C9B9B1S1S9S9WeDgWnWwDbDr mes LDb', [Score(), Score(limits=0.4)])
        self.callingTest(b'Dg Dg Dr We Ws Ww Wn Wn RB1B9C1S1S9 mwe LWe', b'')
        self.callingTest(b'Db Dg Dr We Ws Ww Wn B7 RB1B9C1S1S9 mwe LWe', b'')
        self.callingTest(b'RDbDgDrWeWsWwWnWnB1B9C1S1S9 mwe LWn', b'c9')
        self.callingTest(b'RDbDgDrWsWwWnWnB1B9C1S1S9C9 mwe LDg', b'we')
    def testSimpleNonWinningCases(self):
        """normal hands"""
        self.scoreTest(b's2s2s2 s2s3s4 RB1B1B1B1 c9c9c9C9 mes Ls2s2s3s4', Score(26))
    def testFourBlessingsOverTheDoor(self):
        """lots of winds"""
        self.scoreTest(b'b1b1 wewewe wswsws WnWnWn wwwwwwww Mne Lb1b1b1', Score(limits=1))
        self.scoreTest(b'RDgDg wewewe wswsws WnWnWn wwwwwwww Mne LDgDgDg', Score(limits=1))
        self.scoreTest(b'wewewe wswsws WnWnWn wwwwwwww DrDr Mne LDrDrDr', Score(limits=1))
        self.scoreTest(b'wewewe wswsws WnWnWn wwwwwwww DrDr Mne LDrDrDr', Score(limits=1))
        self.scoreTest(b'wewewe wswsws WnWnWn wwwwwwww DrDr Mnez LDrDrDr', Score(limits=1))
        self.scoreTest(b'wewewe wswsws RWnWnWnDr wwwwwwww mne', [Score(32, 4), Score(limits=0.4)])
    def testAllHonours(self):
        """only honours"""
        self.scoreTest(b'drdrdr wewe wswsws wnwnwn dbdbdb Mesz Ldrdrdrdr', Score(limits=1))
        self.scoreTest(b'wewewe wswsws RWnWnWnB1 wwwwwwww mne LB1', [Score(32, 4), Score(limits=0.4)])
        # this one is limits=0.4 = 400 points, but points 512 are higher:
        self.scoreTest(b'wewewe drdrdr RDrDrDrDb wwwwwwww mee LDb', [Score(32, 4), Score(32, 4)])
        self.scoreTest(b'wewe wswsws RWnWnWn wwwwwwww b1b1 mne Lwewewe', [Score(30, 2), Score(30, 1)])
    def testBuriedTreasure(self):
        """buried treasure, CC BMJA"""
        self.scoreTest(b'RWeWeWeC3C3C3S3S3 c4c4c4C4 b8B8B8b8 Meee LWeWeWeWe',
                       [Score(limits=1), Score(58, 4)])
        self.scoreTest(b'RWeWeWeC3C3C3S3S3C4C4C4B8B8B8 Meee LWeWeWeWe',
                       [Score(limits=1), Score(42, 4)])
        self.scoreTest(b'RWeWeWeC3C3C3C5C5C4C4C4C8C8C8 Meee LWeWeWeWe',
                       [Score(limits=1), Score(limits=1)])
        self.scoreTest(b'RWeWeC3C3C3C5C5C4C4C4C8C8C8 meee LWe',
                       [Score(16, 1), Score(limits=0.4)])
        self.scoreTest(b'RWeWeWeC3C3C3C5C5C4C4C4C7C8C9 Meee LWeWeWeWe',
                       [Score(38, 6), Score(38, 3)])
    def testHiddenTreasure(self):
        """hidden treasure, CC DMJL"""
        self.scoreTest(b'RWeWeWeC3C3C3S3S3 c4c4c4C4 b8B8B8b8 Meee LWeWeWeWe',
                       [Score(limits=1), Score(58, 4)])
        self.scoreTest(b'RWeWeWeC3C3C3S3S3 c4c4c4C4 b8B8B8b8 Mee LC3C3C3C3',
                       [Score(limits=1), Score(58, 4)])
        self.scoreTest(b'RWeWeWeC3C3C3 c4c4c4C4 b8B8B8b8 s3s3 Mee Ls3s3s3',
                       [Score(62, 4), Score(56, 3)])
    def testFourfoldPlenty(self):
        """4 kongs"""
        self.scoreTest(b'RB3B3B3C1C1C1 b1b1b1 s3s4s5 wewe Mee LB3B3B3B3', Score(42))
        self.scoreTest(b'b3B3B3b3 c1C1C1c1 b1b1b1b1 s3s3s3s3 wewe Mee Lwewewe', Score(limits=1))
        self.scoreTest(b'b3B3B3b3 c1C1C1c1 b1b1b1b1 s3s3s3s3 WeWe Mee LWeWeWe', Score(limits=1))
        self.scoreTest(b'b3b3 c1C1C1c1 b1b1b1b1 s3s3s3s3 wewewewe Mee Lb3b3b3', Score(limits=1))
        self.scoreTest(b'b3b3b3b3 c1c1 b1b1b1b1 s3s3s3s3 wewewewe Mee Lc1c1c1', Score(limits=1))
        self.scoreTest(b'b3b3b3b3 RC1 b1b1b1b1 s3s3s3s3 wewewewe mee', [Score(48, 2), Score(limits=0.4)])
    def testPlumBlossom(self):
        """Gathering the plum blossom from the roof"""
        self.scoreTest(b's2s2s2 RS5S5S5B1B1B1B2B2 c9C9C9c9 Mese LS5S5S5S5', Score(limits=1))
        self.scoreTest(b's2s2s2 RS5S5S5B1B1B1B2B2 c9C9C9c9 Mese Ls2s2s2s2', [Score(66, 3), Score(66, 1)])
        self.scoreTest(b's2s2s2 RS5S5S5B1B1B1B2B2 c9C9C9c9 Mes LS5S5S5S5', [Score(68, 2), Score(68, 1)])

    def testPluckingMoon(self):
        """plucking the moon from the bottom of the sea"""
        self.scoreTest(b's2s2s2 RS1S1S1B1B1B1B2B2 c9C9C9c9 Mesz LS1S1S1S1', Score(limits=1))
        self.scoreTest(b's2s2s2 RS1S1S1B1B1B1B2B2 c9C9C9c9 Mesz Ls2s2s2s2', [Score(70, 3), Score(70, 2)])
        self.scoreTest(b's2s2s2 RS1S1S1B1B1B1B2B2 c9C9C9c9 Mes LS1S1S1S1', [Score(72, 2), Score(72, 1)])

    def testScratchingPole(self):
        """scratch a carrying pole"""
        self.scoreTest(b'b2b3b4 RS1S1S1B1B1B1B4B4 c9C9C9c9 Mesk Lb2b2b3b4', Score(limits=1))
        self.scoreTest(b'b2b2b2 RS1S1S1B1B1B1B4B4 c9C9C9c9 Mes LS1S1S1S1', [Score(72, 2), Score(72, 1)])
        self.scoreTest(b'b2b2b2 RS1S1S1B1B1B1B4B4 c9C9C9c9 Mes Lb2b2b2b2', [Score(70, 2), Score(70, 1)])

    def testThreeGreatScholars(self):
        """three concealed pungs"""
        self.scoreTest(b'dgdgdg RDrDrDrDbDbDb s4s4s4 c5c5 Msw', [Score(limits=1), Score(limits=1)])
        self.scoreTest(b'dgdgdg RDrDrDrDbDb s4s4s4 c5c5 msw', [Score(16, 3), Score(limits=0.4)])
        self.scoreTest(b'dgdgdg RDrDrDrDbDbDb s4s5s6 c5c5 Msw', [Score(limits=1), Score(40, 3)])
        # calling for Three Great Scholars:
        self.scoreTest(b's2s2 RDgDgDgDbDbDbDrDrDr b2b2b2b2 Mee Ls2s2s2', Score(limits=1))
        self.scoreTest(b'RDgDgDgDbDbDbDrDrDrS2 b2b2b2b2 mee LDbDbDbDb', [Score(32, 6), Score(limits=0.4)])
        # 40, 5 is more than 0.4 limits:
        self.scoreTest(b'RS2DgDgDgDbDbDbDrDrDr wewewewe mee LDbDbDbDb', [Score(40, 8), Score(40, 5)])
    def testThreeConcealedPungs(self):
        """three concealed pungs"""
        self.scoreTest(b'RB2B2B2S1S1S1B1B1B1B4B4 c9c9c9c9 Mes LB2B2B2B2', [Score(58, 2), Score(58, 1)])
        self.scoreTest(b'RB2B2B2S1S1S1B4B4 b1b1b1 c9c9c9c9 Mes LB2B2B2B2', Score(54, 1))
        self.scoreTest(b'RB2B2B2S1S1S1B4B4 b1b1b1 c9c9c9C9 Mes LB2B2B2B2', [Score(54, 2), Score(54, 1)])

    def testRest(self):
        """various tests"""
        self.scoreTest(b's1s1s1s1 s2s2s2 wewe RS3S3S3 s4s4s4 Msw Ls2s2s2s2',
                       [Score(44, 2), Score(44, 1)])
        self.scoreTest(b's1s1s1s1 s2s2s2 RWeWeS3S3S3 s4s4s4 Mswe LS3S3S3S3',
                       [Score(46, 3), Score(46, 1)])
        self.scoreTest(b'b3B3B3b3 RDbDbDbDrDrDr wewewewe s2s2 Mee Ls2s2s2', [Score(74, 6), Score(68, 5)])
        self.scoreTest(b's1s2s3 s1s2s3 b3b3b3 b4b4b4 RB5 fn yn mne LB5', [Score(12, 1), Score(12, 2)])
        self.scoreTest(b'b3b3b3b3 RDbDbDb drdrdr weWeWewe s2s2 Mee Ls2s2s2', [Score(78, 5), Score(72, 5)])
        self.scoreTest(b's2s2s2 s2s3s4 RB1B1B1B1 c9C9C9c9 mes Ls2s2s3s4', Score(42))
        self.scoreTest(b's2s2s2 RDgDgDbDbDbDrDrDr b2b2b2b2 Mee Ls2s2s2s2', [Score(48, 4), Score(48, 3)])
        self.scoreTest(b's1s1s1s1 s2s2s2 s3s3s3 s4s4s4 s5s5 Msww Ls3s3s3s3', Score(42, 4))
        self.scoreTest(b'RB2C1B2C1B2C1WeWeS4WeS4WeS6 mee LC1', [Score(20, 3), Score(20, 2)])
        self.scoreTest(b'b6b6b6 RB1B1B2B2B3B3B7S7C7B8 mnn LB3', Score(2))
        self.scoreTest(b'RB1B1B1B1B2B3B4B5B6B7B8B9DrDr fe fs fn fw Mwe LDrDrDr',
                       [Score(56, 3), Score()])
        self.scoreTest(b'RB1B1B1B2B2B2B5B5B5B7B8B9DrDr fe fs fn fw Mwe LDrDrDr',
                       [Score(64, 4), Score(56, 4)])
        self.scoreTest(b'RB1B1B1B1B2B3B4B5B6B7B8B9DrDr fe fs fn fw Mwee LDrDrDr',
                       [Score(56, 4), Score()])
        self.scoreTest(b'RB1B1B1B1B2B3B4B4B4B7B7B7DrDr fe fs fn fw Mwez LDrDrDr',
                       [Score(64, 5), Score(56, 5)])
        self.scoreTest(b'RB1B1B1B1B2B3B4B4B4B7B7B7DrDr fe fs fn fw MweZ LDrDrDr',
                       [Score(64, 5), Score(56, 5)])
        self.scoreTest(b'drdr RB1B1B1B1B2B3B4B5B6B7B8B9 fe fs fn fw MweZ Ldrdrdr',
                       [Score(54, 3), Score()])
        self.scoreTest(b'RB1B1B1B1B2B3B4B5B6B7B8B8B2B2 fe fs fn fw mwe LB4', Score())
        self.scoreTest(b'RB1B1B1B1B2B3B4B5B6B8B8B2B2 fe fs fn fw mwe LB4',
                       [Score(28, 1), Score(28, 3)])
        self.scoreTest(b'wewe wswsws RWnWnWn wwwwwwww b1b1b1 Mnez Lb1b1b1b1',
                       [Score(54, 6), Score(54, 4)])
        self.scoreTest(b'wswsws RWeWeWnWnWnB1B1B1 wwwwwwww Mnez LB1B1B1B1',
                       [Score(60, 6), Score(60, 4)])
        self.scoreTest(b'RB2B2 b4b4b4 b5b6b7 b7b8b9 c1c1c1 Mssd Lb7b7b8b9', [Score(30), Score()])
        self.scoreTest(b'RB8B8 s4s4s4 b1b2b3 b4b5b6 c1c1c1 Mssd Lb3b1b2b3', [Score(30), Score()])
        self.scoreTest(b'RB2B2 s4s4s4 b1b2b3 b4b5b6 c1c1c1 Mssd Lb3b1b2b3', [Score(26), Score()])
        self.scoreTest(b'RB2B2 s4s4s4 b1b2b3 b4b5b6 c1c1c1 Mssd Lb3b1b2b3', [Score(26), Score()])
    def testTwofoldFortune(self):
        """Twofold fortune"""
        self.scoreTest(b'b1B1B1b1 RB2B3B4B5B6B7 b8b8b8b8 b5b5 fe fs fn fw Mwe.t LB4', [Score(limits=1), Score()])
        self.scoreTest(b'b1B1B1b1 RB2B3B4B6B6B6 b8b8b8b8 b5b5 fe fs fn fw Mwe.t LB4', Score(limits=1))
    def testOriginalCall(self):
        """original call"""
        # in DMJL, b4 would also win:
        self.scoreTest(b's1s1s1 s1s2s3 RB6B6B6B8B8B8B5B5 fn yn Mne.a LB5',
                       [Score(44, 2), Score(42, 3)])
        self.scoreTest(b's1s1s1 s1s2s3 RB6B6B6B8B8B8B5 fn yn mne.a LB5',
                       [Score(20, 1), Score(20, 2)])
    def testRobbingKong(self):
        """robbing the kong"""
        # this hand is only possible if the player declared a hidden chow.
        # is that legal?
        self.scoreTest(b's1s2s3 s1s2s3 RB6B6B7B7B8B8B5 fn yn mne.a LB5',
                       [Score(8, 1), Score(8, 2)])
        self.scoreTest(b's1s2s3 s2s3s4 RB6B6B7B7B8B8B5B5 fn yn Mneka Ls1s1s2s3',
                       [Score(28, 4), Score()])
        self.scoreTest(b's4s5s6 RS1S2S3B6B6B7B7B8B8B5B5 fn yn Mne.a LS1S1S2S3',
                       [Score(30, 3), Score()])
        self.scoreTest(b's4s5s6 RS1S2S3B6B6B7B7B8B8 fn yn mne.a Ls4s4s5s6',
                       [Score(8, 1), Score(8, 2)])
    def testBlessing(self):
        """blessing of heaven or earth"""
        self.scoreTest(b's4s5s6 RS1S2S3B6B6B7B7B8B8 b5b5 fn yn Mne1 LS1S1S2S3',
                       [Score(limits=1), Score()])
        self.scoreTest(b's4s5s6 RS1S2S3B6B6B7B7B8B8 b5b5 fn yn Mee1 LS1S1S2S3',
                       [Score(limits=1), Score()])
        self.scoreTest(b's4s5s6 RS1S1S1B6B6B6B8B8B8 b5b5 fn yn Mee1 LS1S1S1S1',
                       Score(limits=1))

    def testTerminals(self):
        """only terminals"""
        # must disallow chows:
        self.scoreTest(b'b1b1 c1c2c3 c1c2c3 c1c2c3 c1c2c3 Mes Lb1b1b1', [Score(28, 1), Score()])
        self.scoreTest(b'b1b1 c1c2c3 c9c9c9 s1s1s1 s9s9s9 Mes Lb1b1b1', [Score(40), Score(32)])
        self.scoreTest(b'b1b1 c1c1c1 c9c9c9 s1s1s1 s9s9s9 Mes Lb1b1b1', Score(limits=1))
        self.scoreTest(b'RB1 c1c1c1 c9c9c9 s1s1s1 s9s9s9 mes', [Score(16), Score(limits=0.4)])
    def testLongHand(self):
        """long hand"""
        self.scoreTest(b's1s2s3 s1s2s3 b3b3b3 b4b4b4 B5B5 fn yn mne LB5', Score())
        self.scoreTest(b'RB2C1B2C1B2C1WeWeS4WeS4WeS6S5 mee LS5', Score())
        self.scoreTest(b'RB2C1B2C1B2C1WeWeS4WeS4WeS6S5S5 mee LS5', Score())
        self.scoreTest(b'RB2C1B2C1B2C1WeWeS4WeS4WeS6S5S5 Mee LS5', Score())
        self.scoreTest(b'RWsWsWsWsWnS6C1C1WeWeWeS4S4S5S5 Mee LS5', Score())

    def testSingle(self):
        """for testing test rules"""
        pass

    def testMJ(self):
        """test winner hands.
        Are the hidden melds grouped correctly?"""
        self.scoreTest(b'RB1B1B1B2B2B2B3B4 wnwnwn wewewe Mee Lwnwnwnwn', [Score(36, 3), Score(36, 2)])
        self.scoreTest(b'RB1B1B1B2B2B2B3B3B3S1S1 c3c4c5 Mee Lc3c3c4c5', [Score(36, 1), Score(36)])
        self.scoreTest(b'RB1B1B1B2B2B2B3B3S1S2S3 c3c4c5 Mee Lc3c3c4c5', [Score(32), Score()])
        self.scoreTest(b'c1C1C1c1 b5B5B5b5 c2C2C2c2 c3C3C3c3 C4B6 fs fw fn fe Mee LC4', Score())
        self.scoreTest(b'wewewe wswsws wnwnwnWn RWwWwWwC6 mee LC6', [Score(32, 4), Score(limits=0.4)])
        self.scoreTest(b'wewewe wswsws wnwnwnWn RWwWwWwC3B6 Mee LC3', Score())
        self.scoreTest(b'wewewe wswsws wnwnwnWn RWwWwWwC3C3 Mee LC3', Score(limits=1))

    def testLastIsOnlyPossible(self):
        """tests for determining if this was the only possible last tile"""
        self.scoreTest(b'b3B3B3b3 wewewewe s2s2 RDbDbDbDrDrDr Mee Ls2s2s2',
            [Score(74, 6), Score(68, 5)], totals=(500, 1000, 4736, 2176))
        self.scoreTest(b'b3B3B3b3 wewewe RDbDbDbS1S1S1S2S2 Mee LS2S2S2', [Score(60, 5), Score(58, 4)])
        self.scoreTest(b'b3B3B3b3 wewewe RDbDbDbS1S1S1S3S3 Mee LS3S3S3', [Score(60, 5), Score(58, 4)])
        self.scoreTest(b'b3B3B3b3 wewewe RDbDbDbS1S1S1S4S4 Mee LS4S4S4', [Score(64, 5), Score(58, 4)])
        self.scoreTest(b'b3B3B3b3 wewewe RDbDbDbS1S1S1S3S3 Mee LS1S1S1S1', [Score(58, 5), Score(58, 4)])
        self.scoreTest(b's9s9s9 s8s8s8 RDgDgS1S2S3S3S4S5 Mee LS3 fe', [Score(34, 1), Score()])
        self.scoreTest(b's9s9s9 s8s8s8 RDgDgS1S2S3S4S4S4 Mee LS3 fe', [Score(42, 1), Score(38, 1)])
        self.scoreTest(b's9s9s9 s8s8s8 RDgDgS1S2S3S4S5S6 Mee LS6 fe', [Score(34, 1), Score()])
        self.scoreTest(b's9s9s9 s8s8s8 RDgDgS1S2S3S7S8S9 Mee LS7 fe', [Score(38, 1), Score()])

    def testTripleKnitting(self):
        """triple knitting BMJA"""
        self.scoreTest(b'RS2B2C2S4B4C4S6B6C6S7B7C7 s8b8 Mee Ls8s8b8', [Score(), Score(limits=0.5)])
        self.scoreTest(b'RB2C2S4B4C4S6B6C6S7B7C7S8B8 mee LS8', [Score(), Score(limits=0.2)])
        self.scoreTest(b'RS2B2C2S4B4C4S6B6C6S7B7C7S8 mee LS8', [Score(), Score(limits=0.2)])
        self.scoreTest(b'RS2B2C2S7B7C7S4B4C4S6B6C6 s8b8 Mee Ls8s8b8', [Score(), Score(limits=0.5)])
        self.scoreTest(b'RS2B2C2S6B6C6S7B7C7 s4b4c4 s8b8 Mee Ls8s8b8', Score())
        self.scoreTest(b'RS2B2C2S4B4C4S6B6C6S4B4C4 s8b9 Mee Ls8s8b8', [Score(), Score()])
        self.scoreTest(b'RS2B2C2S4B4C4S6B6C6S4B4C4 s8c8 Mee Ls8s8c8', [Score(), Score(limits=0.5)])
        self.scoreTest(b'RS2B2C2S3B3C3S4B4C4S4B4C4 s8c8 Mee Ls8s8c8', [Score(), Score(limits=0.5)])
        self.scoreTest(b'RB2C2B3C3B4C4S4B4C4 s2s3s4 s8c8 Mee Ls8s8c8', [Score(), Score()])
        self.scoreTest(b'RB5S7B7B3B9S7S6C9C3B7S3 c5c6c7 Mwew LS3', Score(0))
        self.scoreTest(b'RC1C2C5C8C9S2S4S9B4B5B6B6B8S1 mee', [Score(), Score()])
        self.scoreTest(b'RC1C2C5C8C9S2S4S9B4B5B6B6B8 mee', [Score(), Score()])
        self.scoreTest(b'RS2B2C2S4B4C4S6B6C6S4B4C4S8 mee', [Score(), Score(limits=0.2)])
        self.scoreTest(b'RS1B1C1S2B2C2S5B5S8B8C8B9C7C9 LB2 Mew', Score(0))
        self.callingTest(b'RS2B2C2S4B4C4S6B6C6S7B7C7S8 mee LS8', [b'', b'b8c8'])
        self.callingTest(b'RS2B2C2S4B4C4S6B6C6B7C7S8C8 mee LC7', [b'', b's7b8'])

    def testKnitting(self):
        """knitting BMJA"""
        self.scoreTest(b'RS2B2S3B3S4B4S5B5S6B6S7B7 s9b9 Mwn Ls9s9b9', [Score(), Score(limits=0.5)])
        self.scoreTest(b'RS2B2S3B3B4S5B5S6B6S7B7 S9B9 mwn LS9', [Score(), Score(limits=0.2)])
        self.scoreTest(b'RS2B2S3S5B5B3S4B4S6B6S7B7 s9c9 Mwn Ls9s9c9', [Score(), Score()])
        self.scoreTest(b'RS2B3S3B3S4B4S5B5S6B6S7B7 s9b9 Mwn Ls9s9b9', [Score(), Score()])
        self.scoreTest(b'RS2B2S2B2S4B4S5B5S6B6S7B7 s9b9 Mwn Ls9s9b9', [Score(), Score(limits=0.5)])
        self.scoreTest(b'RS2S3S4S5S6S7S9B2B3B4B5B6B7B9 LB9 Mwn', [Score(), Score(limits=0.5)])
        self.scoreTest(b'RS3S4S5S6S7S9B2B3B4B5B6B7B9 LB9 Mwn', [Score(), Score(limits=0.2)])
        self.scoreTest(b'RS3S4S9S9B1B1B2B3B4B8B8 s2s2s2 fs Msww LS4', Score(0))
        self.scoreTest(b'RS3S9S9B1B1B2B3B8B8S2S2S2 s4b4 fs Msww Ls4', Score(0))
        self.callingTest(b'RS2B2S3B3S4B4S5B5S6B6S7B7S9 Mwn LB7', [b's9', b'b9'])

    def testAllPairHonors(self):
        """all pairs honours BMJA"""
        self.scoreTest(b'RWeWeS1S1B9B9DgDgDrDrWsWsWwWw Mwn LS1S1S1', [Score(), Score(limits=0.5)])
        self.scoreTest(b'RWeWeS1S1B9B9DgDgDrDrWsWs wwww Mwn Lww', [Score(), Score(limits=0.5)])
        self.scoreTest(b'RWeWeS1S1B9B9DgDgDrDrWsWwWw mwn LS1', [Score(6), Score(limits=0.2)])
        self.scoreTest(b'RWeWeS2S2B9B9DgDgDrDrWsWsWwWw Mwn LS2S2S2', [Score(), Score()])

    def testBMJA(self):
        """specials for chinese classical BMJA"""
        self.scoreTest(b'RS1S1S5S6S7S8S9WeWsWwWn s2s3s4 Msw Ls3s2s3s4', [Score(), Score(limits=1)])

    def testLastTile(self):
        """will the best last meld be chosen?"""
        self.scoreTest(b'wewewe s1s1s1 b9b9b9 RC1C1C1C2C3 Mee LC1', [Score(38, 2), Score(34, 2)])
        self.scoreTest(b'wewewe s1s1s1 b9b9b9 RC1C2C3C3C3 Mee LC3', [Score(40, 2), Score(34, 2)])
        self.scoreTest(b'b5b6b7 s1s1s1 RB8C6C7C5B8B8C7C7 Mwew LC7', [Score(32, 0), Score(0)])

    def testCallingHands(self):
        """diverse calling hands
        TODO: try assigning them to specif rule tests"""
        self.callingTest(b's1s1s1s1 b5b6b7 RB1B8C2C2C6C7C8 mwe Lb5', b'')
        self.callingTest(b'WnWn B1 B2 c4c5c6 b6b6b6 b8b8b8 ye yw mne', [b'b3', b''])
        self.callingTest(b'WnWn B1 B2 dgdgdg b6b6b6 b8b8b8 ye yw mne', b'b3')
        self.callingTest(b's1s1s1s1 b5b6b7 RB8B8C2C2C6C7C8 mwe Lb5', [b'b8c2', b''])
        self.callingTest(b's1s1s1s1 b5b6b7 RB7B8C2C2C6C7C8 mwe Lb5', [b'b6b9', b''])
        self.callingTest(b'c3c3c3 RDbDbDbS5S6S7S7S8B2B2 mwe LS8', [b's6s9', b''])
        self.callingTest(b'RC4C4C5C6C5C7C8 dgdgdg s6s6s6 mnn', b'c4c5')
        self.callingTest(b'RS1S4C5C6C5C7C8 dgdgdg s6s6s6 mnn', b'')
        self.callingTest(b'RDbDgDrWsWwWeWnB1B9C1S1S9C9 mwe LWe', b'dbdgdrwewswwwns1s9b1b9c1c9')

    def scoreTest(self, string, expected, totals=None):
        """execute one scoreTest test"""
        for idx, ruleset in enumerate(RULESETS):
            variants = []
            variant = Hand(ruleset, string)
            variants.append(variant)
            score = variant.score
# activate depending on what you are testing
#            kprint(string, 'expected:', expected.__str__()), variant
#            kprint(ruleset.name.encode('utf-8'))
#            kprint('\n'.join(variant.explain).encode('ut-f8'))
            if isinstance(expected, list):
                expIdx = idx
                if expIdx >= len(expected):
                    expIdx %= len(RULESETS) // 2
                exp = expected[expIdx]
            else:
                exp = expected
            exp.ruleset = ruleset
            self.assertTrue(score == exp, self.dumpCase(variants, exp, total=None))
            if totals:
                self.assertTrue(score.total() == totals[idx], self.dumpCase(variants, exp, totals[idx]))

    def callingTest(self, string, expected):
        """test a calling hand"""
        for idx, ruleset in enumerate(RULESETS):
            hand = Hand(ruleset, string)
            completedHands = hand.callingHands(99)
            testSays = TileList(set(x.lastTile.lower() for x in completedHands)).sorted()
            if idx >= len(expected):
                idx %= len(RULESETS) // 2
            if isinstance(expected, list):
                expIdx = idx
                if expIdx >= len(expected):
                    print('chaging expidx from %d to %d' % (expIdx, expIdx % len(RULESETS) // 2))
                    expIdx %= len(RULESETS) // 2
                if expIdx >= len(expected):
                    print('exPdix', expIdx, 'expected', expected)
                exp = expected[expIdx]
            else:
                exp = expected
            completingTiles = TileList(exp)
            self.assertTrue(testSays == completingTiles,
                '%s: %s may be completed by %s but testresult is %s' % (
                ruleset.name, string, completingTiles or 'None', testSays or 'None'))

    def dumpCase(self, variants, expected, total):
        """dump test case"""
        assert self
        result = []
        result.append('')
        result.append(variants[0].string)
        for hand in variants:
            score = hand.score
            roofOff = ' roofOff' if hand.ruleset.roofOff else ''
            if score != expected:
                result.append('%s%s: %s should be %s' % (
                    hand.ruleset.name, roofOff, score.__str__(), expected.__str__()))
                result.append('hand:%s' % hand)
            if total is not None:
                if score.total() != total:
                    result.append('%s%s: total %s for %s should be %s' % (hand.ruleset.name, roofOff,
                        score.total(), score.__str__(), total))
                result.append('hand:%s' % hand)
            result.extend(hand.explain())
            result.append('base=%d,doubles=%d,total=%d' % (score.points, score.doubles, hand.total()))
            result.append('')
        return '\n'.join(str(x) for x in result).encode('ascii', 'ignore')

class TstProgram(unittest.TestProgram):
    """we want global access to this program so we can check for verbosity in our tests"""
    def __init__(self, *args, **kwargs):
        global PROGRAM # pylint: disable=global-statement
        PROGRAM = self
        unittest.TestProgram.__init__(self, *args, **kwargs)

if __name__ == '__main__':
    initLog('scoringtest')
    Debug.profileRegex = True
   # Debug.handMatch = True
    TstProgram()
