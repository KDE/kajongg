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

import unittest
from scoringengine import HandContent, Score
from predefined import ClassicalChineseDMJL, ClassicalChineseBMJA
from common import Debug
from util import initLog

RULESETS = [ClassicalChineseDMJL(), ClassicalChineseBMJA()]
PROGRAM = None

for x in RULESETS:
    x.load()

class Regex(unittest.TestCase):
    """tests lots of hand examples. We might want to add comments which test should test which rule"""
    # pylint: disable=R0904
    # pylint - we need more than 40 public methods

    def __init__(self, arg):
        unittest.TestCase.__init__(self, arg)

    def testPartials(self):
        """some partial hands"""
        self.scoreTest(r'drdrdr fe mes Ldrdrdrdr', [Score(8, 1), Score(8, 2)])
        self.scoreTest(r'fe mes Lxx', [Score(4), Score(4, 1)])
        self.scoreTest(r'fs fw fe fn mes Lxx', [Score(16, 1), Score(16, 2)])
        self.scoreTest(r'fs ys mse Lxx', [Score(8, 1), Score(8, 2)])
        self.scoreTest(r'drdrdr mes Ldrdrdrdr', Score(4, 1))
    def testZeroHand(self):
        """zero hand games"""
        self.scoreTest(r'c1c2c3 c7c8c9 b2b3b4 c5c5 s1s2s3 fw yw Mwn Lc1c1c2c3',
            [Score(points=28, doubles=2), Score()])
    def testFalseColorGame(self):
        """false color games"""
        self.scoreTest(r'c1c1c1 c7c7c7 c2c3c4 c5c5 c6c6c6 Mwn Lc5c5c5', Score(points=34, doubles=3))
        self.scoreTest(r'c1c2c3 wewewe drdrdr dbdb DgDgDg Mwn Ldbdbdb', Score(points=46, doubles=4))
        self.scoreTest(r's1s1s1 wewewe c2c3c4 c5c5 c6c6c6 Mwn Lc5c5c5', Score(points=36))
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe ys Mwe LDrDrDr', [Score(48, 2), Score()])
        self.scoreTest(r'b1B1B1b1 B2B3B4 B5B6B7 B8B8B8 DrDr fe ys Mwe LDrDrDr', [Score(76, 2), Score()])
        self.scoreTest(r'b1B1B1b1 B2B2B2 B5B6B7 B8B8B8 DrDr fe ys Mwe LDrDrDr', Score(80, 3))
    def testSquirmingSnake(self):
        """the winding snake"""
        self.scoreTest(r'c1c1c1 c3c4c5 c9c9c9 c6c7c8 c2c2 Mee Lc1c1c1c1', [Score(limits=1), Score()])
        self.scoreTest(r'c1c1c1 c4c5c6 c9c9c9 c6c7c8 c2c2 Mee Lc1c1c1c1', [Score(points=28, doubles=3), Score()])
        self.scoreTest(r'c1c1c1 c3c4c5 c9c9c9 c6c7c8 s2s2 Mee Lc1c1c1c1', [Score(points=28), Score()])
        self.scoreTest(r's1s1s1 s2s3s4 s9s9s9 s6s7s8 s5s5 Mee Ls1s1s1s1', [Score(limits=1), Score()])
        self.scoreTest(r'b1b1b1 c3c4c5 c6c7c8 c9c9c9 c2c2 Mee Lc3c3c4c5', [Score(points=28), Score()])
        self.scoreTest(r'b1b1b1 c3c4c5 c6c7c8 c9c9c9 c2c2 Mee Lc4c3c4c5', [Score(points=32), Score()])
        self.scoreTest(r'C1C1C1 C2C3C4 C5C6C7 C8 C9C9C9 C5 Mee LC2C2C3C4', [Score(limits=1), Score(limits=1)])
    def testTrueColorGame(self):
        """true color games"""
        self.scoreTest(r'b1b1b1b1 B2B3B4B5B6B7B8B8B2B2B2 fe fs fn fw Mwe LB3B2B3B4',
                [Score(points=62, doubles=4), Score()])
        self.scoreTest(r'b1b1b1B1 B2B3B4B5B6B7B8B8B2B2B2 fe fs fn fw Mwe LB3B2B3B4', [Score(limits=1), Score()])
    def testOnlyConcealedMelds(self):
        """only concealed melds"""
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe ys Mwe LDrDrDr', [Score(48, 2), Score()])
        self.scoreTest(r'B1B1B1B2B2B2B4B4B4B7B8B9DrDr fe ys Mwe LDrDrDr', Score(56, 3))
        self.scoreTest(r'b1B1B1b1 B2B3B4 B5B6B7 B8B8B8 DrDr fe ys Mwe LDrDrDr', [Score(76, 2), Score()])
        self.scoreTest(r'b1B1B1b1 B2B2B2 B5B6B7 B8B8B8 DrDr fe ys Mwe LDrDrDr', Score(80, 3))

    def testLimitHands(self):
        """various limit hands"""
        self.scoreTest(r'c1c1c1 c9c9 b9b9b9b9 s1s1s1 s9s9s9 Mee Lc1c1c1c1', Score(limits=1))
        self.scoreTest(r'c1c1c1c1 drdr wewewewe c3c3c3C3 s1S1S1s1 Mee Ldrdrdr', Score(limits=1))
        self.scoreTest(r'drdr c1c1c1c1 wewewewe c3c3c3C3 s1S1S1s1 Mee Ldrdrdr', Score(limits=1))
        self.scoreTest(r'c1c1c1c1 wewewewe c3c3c3C3 s1S1S1s1 drdr Mee Ldrdrdr', Score(limits=1))
    def testAllGreen(self):
        """the green hand"""
        self.scoreTest(r'c1c1c1 c7c7c7 c2c3c4 c5c5 c6c6c6 Mwn Lc5c5c5', Score(points=34, doubles=3))
        self.scoreTest(r'b2b2b2b2 DgDgDg b6b6b6 b4b4b4 b8b8 Mee Lb6b6b6b6', Score(limits=1))
        self.scoreTest(r'b1b1b1b1 DgDgDg b6b6b6 b4b4b4 b8b8 Mee Lb6b6b6b6', Score(points=48, doubles=3))
    def testNineGates(self):
        """the nine gates"""
        self.scoreTest(r'C1C1C1 C2C3C4 C5C6C7 C8 C9C9C9 C5 Mee LC5C5', Score(limits=1))
        self.scoreTest(r'C1C1C1 C2C3C4 C5C6C7 C8 C9C9C9 C5 Mee LC6C5C6C7', Score(limits=1))
        self.scoreTest(r'C1C1C1 C2C3C4 C5C6C7 C8 C9C9C9 C9 Mee LC9C9', Score(limits=1))
        self.scoreTest(r'C1C1C1 C2C3C4 C5C6C7 C8 C9C9C9 c9 Mee Lc9c9', Score(limits=1))
        # this is a squirming snake:
        self.scoreTest(r'C1C1C1 C2C3C4 C5C6C7 C8 C9C9C9 C5 Mee LC2C2C3C4', Score(limits=1))
        # this is illegal in DMJL, last tile is wrong. BMJA allows this.
        self.scoreTest(r'C1C1C1 C2C3C4 C5C6C7 C8 C9C9C9 C9 Mee LC1C1C1C1', [Score(), Score(limits=1)])
    def testManual(self):
        """some manual rules for manual scoring"""
        # this should actually never happen but anyway we want to be sure that no rule
        # fires on this
        self.scoreTest(r' Mse L', Score(points=0))
        self.scoreTest(r' mse L', Score(points=0))
    def testThirteenOrphans(self):
        """The 13 orphans"""
        self.scoreTest(r'C1C9B9B1S1S9WeDgWsWnWwDbDrS1 mes LDgDg', Score())
        self.scoreTest(r'C1C9B9B1S1S9WeDgWsWnwwDbDrS8 Mes LDrDr', Score())
        self.scoreTest(r'C1C9B9B1S1S9WeDgWsWnwwDbDrS9 Mes LDrDr', Score(limits=1))
        self.scoreTest(r'C1C9B9B1S1S9S9WeDgWsWnWwDbDr Mes LDrDr', Score(limits=1))
        self.scoreTest(r'C1C9B9B1S1S9S9WeDgWsWnWwDbdr Mes Ldrdr', Score(limits=1))
    def testSimpleNonWinningCases(self):
        """normal hands"""
        self.scoreTest(r's2s2s2 s2s3s4 B1B1B1B1 c9c9c9C9 mes Ls2s2s3s4', Score(26))
    def testFourBlessingsOverTheDoor(self):
        """lots of winds"""
# TODO: test playing without a limit
        self.scoreTest(r'b1b1 wewewe wswsws WnWnWn wwwwwwww Mne Lb1b1b1', Score(limits=1))
        self.scoreTest(r'DgDg wewewe wswsws WnWnWn wwwwwwww Mne LDgDgDg', Score(doubles=2, limits=1))
        self.scoreTest(r'wewewe wswsws WnWnWn wwwwwwww DrDr Mne LDrDrDr', Score(doubles=2, limits=1))
        self.scoreTest(r'wewewe wswsws WnWnWn wwwwwwww DrDr Mne LDrDrDr', Score(doubles=2, limits=1))
        self.scoreTest(r'wewewe wswsws WnWnWn wwwwwwww DrDr Mnez LDrDrDr', Score(doubles=2, limits=1))
    def testAllHonours(self):
        """only honours"""
        self.scoreTest(r'drdrdr wewe wswsws wnwnwn dbdbdb Mesz Ldrdrdrdr', Score(doubles=2, limits=1))
        self.scoreTest(r'wewewe wswsws WnWnWn wwwwwwww B1 mne LB1', Score(32, 4))
        self.scoreTest(r'wewe wswsws WnWnWn wwwwwwww b1b1 mne Lwewewe', Score(30, 2))
    def testHiddenTreasure(self):
        """hidden treasure"""
        self.scoreTest(r'WeWeWe C3C3C3 c4c4c4C4 b8B8B8b8 S3S3 Meee LWeWeWeWe',
                       Score(limits=1))
        self.scoreTest(r'WeWeWe C3C3C3 c4c4c4C4 b8B8B8b8 S3S3 Mee LC3C3C3C3',
                       Score(limits=1))
        self.scoreTest(r'WeWeWe C3C3C3 c4c4c4C4 b8B8B8b8 s3s3 Mee Ls3s3s3',
                       Score(62, 4))
    def testFourfoldPlenty(self):
        """4 kongs"""
        self.scoreTest(r'B3B3B3 C1C1C1 b1b1b1 s3s4s5 wewe Mee LB3B3B3B3', Score(42))
        self.scoreTest(r'b3B3B3b3 c1C1C1c1 b1b1b1b1 s3s3s3s3 wewe Mee LWeWeWe', Score(limits=1))
        self.scoreTest(r'b3b3 c1C1C1c1 b1b1b1b1 s3s3s3s3 wewewewe Mee LB3B3B3B3', Score(limits=1))
        self.scoreTest(r'b3b3b3b3 c1c1 b1b1b1b1 s3s3s3s3 wewewewe Mee LC1C1C1', Score(limits=1))
    def testPlumBlossom(self):
        """Gathering the plum blossom from the roof"""
        self.scoreTest(r's2s2s2 S5S5S5 B1B1B1 B2B2 c9C9C9c9 Mese LS5S5S5S5', Score(limits=1))
        self.scoreTest(r's2s2s2 S5S5S5 B1B1B1 B2B2 c9C9C9c9 Mese Ls2s2s2s2', Score(66, 3))
        self.scoreTest(r's2s2s2 S5S5S5 B1B1B1 B2B2 c9C9C9c9 Mes LS5S5S5S5', Score(68, 2))

    def testPluckingMoon(self):
        """plucking the moon from the bottom of the sea"""
        self.scoreTest(r's2s2s2 S1S1S1 B1B1B1 B2B2 c9C9C9c9 Mesz LS1S1S1S1', Score(limits=1))
        self.scoreTest(r's2s2s2 S1S1S1 B1B1B1 B2B2 c9C9C9c9 Mesz Ls2s2s2s2', Score(70, 3))
        self.scoreTest(r's2s2s2 S1S1S1 B1B1B1 B2B2 c9C9C9c9 Mes LS1S1S1S1', Score(72, 2))

    def testScratchingPole(self):
        """scratch a carrying pole"""
        self.scoreTest(r'b2b2b2 S1S1S1 B1B1B1 B4B4 c9C9C9c9 Mesk Lb2b2b2b2', Score(limits=1))
        self.scoreTest(r'b2b2b2 S1S1S1 B1B1B1 B4B4 c9C9C9c9 Mesk Ls2s2s2s2', Score(70, 3))
        self.scoreTest(r'b2b2b2 S1S1S1 B1B1B1 B4B4 c9C9C9c9 Mes Lb2b2b2b2', Score(70, 2))

    def testThreeConcealedPungs(self):
        """three concealed pungs"""
        self.scoreTest(r'B2B2B2 S1S1S1 B1B1B1 B4B4 c9c9c9c9 Mes LB2B2B2B2', Score(58, 2))
        self.scoreTest(r'B2B2B2 S1S1S1 b1b1b1 B4B4 c9c9c9c9 Mes LB2B2B2B2', Score(54, 1))
        self.scoreTest(r'B2B2B2 S1S1S1 b1b1b1 B4B4 c9c9c9C9 Mes LB2B2B2B2', Score(54, 2))

    def testRest(self):
        """various tests"""
        self.scoreTest(r's1s1s1s1 s2s2s2 wewe S3S3S3 s4s4s4 Msw Ls2s2s2s2',
                       Score(44, 2))
        self.scoreTest(r's1s1s1s1 s2s2s2 WeWe S3S3S3 s4s4s4 Mswe LS3S3S3S3',
                       Score(46, 3))
        self.scoreTest(r'b3B3B3b3 DbDbDb DrDrDr wewewewe s2s2 Mee Ls2s2s2', Score(74, 6))
        self.scoreTest(r's1s2s3 s1s2s3 b3b3b3 b4b4b4 B5 fn yn mne LB5', [Score(12, 1), Score(12, 2)])
        self.scoreTest(r'b3b3b3b3 DbDbDb drdrdr weWeWewe s2s2 Mee Ls2s2s2', Score(78, 5))
        self.scoreTest(r's2s2s2 s2s3s4 B1B1B1B1 c9C9C9c9 mes Ls2s2s3s4', Score(42))
        self.scoreTest(r's2s2s2 DgDg DbDbDb b2b2b2b2 DrDrDr Mee Ls2s2s2s2', Score(48, 4))
        self.scoreTest(r's2s2 DgDgDg DbDbDb b2b2b2b2 DrDrDr Mee Ls2s2s2', Score(limits=1))
        self.scoreTest(r's2 DgDgDg DbDbDb b2b2b2b2 DrDrDr mee LDbDbDbDb', Score(32, 6))
        self.scoreTest(r's1s1s1s1 s2s2s2 s3s3s3 s4s4s4 s5s5 Msww Ls3s3s3s3', Score(42, 4))
        self.scoreTest(r'B2C1B2C1B2C1WeWeS4WeS4WeS6 mee LC1', Score(20, 3))
        self.scoreTest(r'b6b6b6 B1B1B2B2B3B3B7S7C7B8 mnn LB3', Score(2))
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe fs fn fw Mwe LDrDrDr',
                       [Score(56, 3), Score()])
        self.scoreTest(r'B1B1B1B2B2B2B5B5B5B7B8B9DrDr fe fs fn fw Mwe LDrDrDr',
                       [Score(64, 4), Score(64, 5)])
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe fs fn fw Mwee LDrDrDr',
                       [Score(56, 4), Score()])
        self.scoreTest(r'B1B1B1B1B2B3B4B4B4B7B7B7DrDr fe fs fn fw Mwez LDrDrDr',
                       [Score(64, 5), Score(64, 6)])
        self.scoreTest(r'B1B1B1B1B2B3B4B4B4B7B7B7DrDr fe fs fn fw MweZ LDrDrDr',
                       [Score(64, 5), Score(64, 6)])
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B9drdr fe fs fn fw MweZ Ldrdrdr',
                       [Score(54, 3), Score()])
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B8B2B2 fe fs fn fw mwe LB4', Score())
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B8B8B2B2 fe fs fn fw mwe LB4',
                       [Score(28, 1), Score(28, 2)])
        self.scoreTest(r'wewe wswsws WnWnWn wwwwwwww b1b1b1 Mnez Lb1b1b1b1',
                       Score(54, 6))
        self.scoreTest(r'WeWe wswsws WnWnWn wwwwwwww B1B1B1 Mnez LB1B1B1B1',
                       Score(60, 6))
        self.scoreTest(r'B2B2 b4b4b4 b5b6b7 b7b8b9 c1c1c1 Mssd Lb7b7b8b9', [Score(30), Score()])
    def testTwofoldFortune(self):
        """Twofold fortune"""
        self.scoreTest(r'b1B1B1b1 B2B3B4 B5B6B7 b8b8b8b8 b5b5 fe fs fn fw Mwe.t LB4', [Score(limits=1), Score()])
        self.scoreTest(r'b1B1B1b1 B2B3B4 B6B6B6 b8b8b8b8 b5b5 fe fs fn fw Mwe.t LB4', Score(limits=1))
    def testRobbingKong(self):
        """robbing the kong"""
        # this hand is only possible if the player declared a hidden chow.
        # is that legal?
        self.scoreTest(r's1s2s3 s1s2s3 B6B6B7B7B8B8 B5 fn yn mne.a LB5',
                       [Score(8, 1), Score(8, 2)])
        self.scoreTest(r's1s1s1 s1s2s3 B6B6B6B8B8B8 B5 fn yn mne.a LB5',
                       [Score(20, 1), Score(20, 2)])
        self.scoreTest(r's1s2s3 s1s2s3 B6B6B7B7B8B8 B5B5 fn yn Mneka Ls1s1s2s3',
                       [Score(28, 4), Score()])
        self.scoreTest(r'S1S2S3 s4s5s6 B6B6B7B7B8B8 B5B5 fn yn Mne.a LS1S1S2S3',
                       [Score(30, 3), Score()])
        self.scoreTest(r'S1S2S3 s4s5s6 B6B6B7B7B8B8 fn yn mne.a Ls4s4s5s6',
                       [Score(8, 1), Score(8, 2)])
    def testBlessing(self):
        """blessing of heaven or earth"""
        self.scoreTest(r'S1S2S3 s4s5s6 B6B6B7B7B8B8 b5b5 fn yn Mne1 LS1S1S2S3',
                       [Score(limits=1), Score()])
        self.scoreTest(r'S1S2S3 s4s5s6 B6B6B7B7B8B8 b5b5 fn yn Mee1 LS1S1S2S3',
                       [Score(limits=1), Score()])
        self.scoreTest(r'S1S1S1 s4s5s6 B6B6B6B8B8B8 b5b5 fn yn Mee1 LS1S1S1S1',
                       Score(limits=1))

    def testTerminals(self):
        """only terminals"""
        # must disallow chows:
        self.scoreTest(r'b1b1 c1c2c3 c1c2c3 c1c2c3 c1c2c3 Mes Lb1b1b1', [Score(28, 1), Score()])
        self.scoreTest(r'b1b1 c1c2c3 c9c9c9 s1s1s1 s9s9s9 Mes Lb1b1b1', Score(40, 0))
        self.scoreTest(r'b1b1 c1c1c1 c9c9c9 s1s1s1 s9s9s9 Mes Lb1b1b1', Score(limits=1))
    def testLongHand(self):
        """long hand"""
        self.scoreTest(r's1s2s3 s1s2s3 b3b3b3 b4b4b4 B5B5 fn yn mne LB5', Score())
        self.scoreTest(r'B2C1B2C1B2C1WeWeS4WeS4WeS6S5 mee LS5', Score())
        self.scoreTest(r'B2C1B2C1B2C1WeWeS4WeS4WeS6S5S5 mee LS5', Score())
        self.scoreTest(r'B2C1B2C1B2C1WeWeS4WeS4WeS6S5S5 Mee LS5', Score())
        self.scoreTest(r'WsWsWsWsWnS6 C1C1 WeWeWe S4S4 S5S5 Mee LS5', Score())

    def testSingle(self):
        """for testing test rules"""
        pass

    def testMJ(self):
        """test winner hands.
        Are the hidden melds grouped correctly?"""
        self.scoreTest(r'B1B1B1B2B2B2B3B4 wnwnwn wewewe Mee Lwnwnwnwn', Score(36, 3))
        self.scoreTest(r'B1B1B1B2B2B2B3B3B3S1S1 c3c4c5 Mee Lc3c3c4c5', Score(36, 1))
        self.scoreTest(r'B1B1B1B2B2B2B3B3S1S2S3 c3c4c5 Mee Lc3c3c4c5', [Score(32), Score()])
        self.scoreTest(r'c1C1C1c1 b5B5B5b5 c2C2C2c2 c3C3C3c3 C4B6 fs fw fn fe Mee LC4', Score())
        self.scoreTest(r'wewewe wswsws wnwnwnWn WwWwWw C6 mee LC6', Score(32, 4))
        self.scoreTest(r'wewewe wswsws wnwnwnWn WwWwWw C3B6 Mee LC3', Score())
        self.scoreTest(r'wewewe wswsws wnwnwnWn WwWwWw C3C3 Mee LC3', Score(limits=1))

    def testIsCalling(self):
        """test calling hands"""
        for content, completingTiles in [('s1s1s1s1 b5b6b7 B8B8C2C2C6C7C8 mwe Lb5', 'b8c2'),
                        ('s1s1s1s1 b5b6b7 B7B8C2C2C6C7C8 mwe Lb5', 'b6b9'),
                        ('Db Dg Dr We Ws Ww Wn Wn B1B9C1S1S9 mwe LWn', 'c9'),
                        ('Db Dg Dr Ws Ww Wn Wn B1B9C1S1S9C9 mwe LDg', 'we'),
                        ('B1B2B3B4B5B5B6B6B7B7B8B8B8 mwe LB1', 'b1b3b4b6b7b9'),
                        ('Db Dg Dr Ws Ww We Wn B1B9C1S1S9C9 mwe LWe', 'b1b9c1c9dbdgdrs1s9wewnwsww')]:
            hand = HandContent(RULESETS[0], content)
            completedHands = hand.callingHands(99)
            testSays = ''.join(x.lastTile for x in completedHands).lower()
            self.assert_(testSays == completingTiles,
                '%s is completed by %s but test says %s' % (
                content, completingTiles, testSays))
        for content in ['s1s1s1s1 b5b6b7 B1B8C2C2C6C7C8 mwe Lb5',
                        'Dg Dg Dr We Ws Ww Wn Wn B1B9C1S1S9 mwe LWe',
                        'Db Dg Dr We Ws Ww Wn B7 B1B9C1S1S9 mwe LWe']:
            hand = HandContent(RULESETS[0], content)
            self.assert_(not hand.callingHands(), content)

    def testLastIsOnlyPossible(self):
        """tests for determining if this was the only possible last tile"""
        self.scoreTest(r'b3B3B3b3 wewewewe s2s2 DbDbDbDrDrDr Mee Ls2s2s2', Score(74, 6))
        self.scoreTest(r'b3B3B3b3 wewewe DbDbDbS1S1S1S2S2 Mee LS2S2S2', Score(60, 5))
        self.scoreTest(r'b3B3B3b3 wewewe DbDbDbS1S1S1S3S3 Mee LS3S3S3', Score(60, 5))
        self.scoreTest(r'b3B3B3b3 wewewe DbDbDbS1S1S1S4S4 Mee LS4S4S4', Score(64, 5))
        self.scoreTest(r'b3B3B3b3 wewewe DbDbDb S1S1S1 S3S3 Mee LS1S1S1S1', Score(58, 5))
        self.scoreTest(r's9s9s9 s8s8s8 DgDgS1S2S3S3S4S5 Mee LS3S1S2S3 fe', [Score(34, 1), Score()])
        self.scoreTest(r's9s9s9 s8s8s8 DgDgS1S2S3S4S4S4 Mee LS3S1S2S3 fe', [Score(42, 1), Score(42, 2)])
        self.scoreTest(r's9s9s9 s8s8s8 DgDgS1S2S3S4S5S6 Mee LS6S4S5S6 fe', [Score(34, 1), Score()])
        self.scoreTest(r's9s9s9 s8s8s8 DgDgS1S2S3S7S8S9 Mee LS7S7S8S9 fe', [Score(38, 1), Score()])

    def testTripleKnitting(self):
        """triple knitting BMJA"""
        self.scoreTest('S2B2C2 S4B4C4 S6B6C6 s8b8 S7B7C7 Mee Ls8s8b8', [Score(), Score(doubles=1, limits=0.5)])
        self.scoreTest('S2B2C2S7B7C7S4B4C4 S6B6C6 s8b8 Mee Ls8s8b8', [Score(), Score(doubles=1, limits=0.5)])
        self.scoreTest('S2B2C2 s4b4c4 S6B6C6 s8b8 S7B7C7 Mee Ls8s8b8', Score())
        self.scoreTest('S2B2C2 S4B4C4 S6B6C6 s8b9 S4B4C4 Mee Ls8s8b8', [Score(), Score()])
    def testKnitting(self):
        """knitting BMJA"""
        self.scoreTest('S2B2 S3B3 S4B4 S5B5 S6B6 S7B7 s9b9 Mwn Ls9s9b9', [Score(), Score(limits=0.5)])
        self.scoreTest('S2B2 S3S5B5 B3 S4B4 S6B6 S7B7 s9c9 Mwn Ls9s9c9', [Score(), Score()])
        self.scoreTest('S2B3 S3B3 S4B4 S5B5 S6B6 S7B7 s9b9 Mwn Ls9s9b9', [Score(), Score()])
        self.scoreTest('S2B2 S2B2 S4B4 S5B5 S6B6 S7B7 s9b9 Mwn Ls9s9b9', [Score(), Score(limits=0.5)])
    def testAllPairHonors(self):
        """all pairs honours BMJA"""
        self.scoreTest('WeWe S1S1 B9B9 DgDg DrDr WsWs WwWw Mwn LS1S1S1', [Score(), Score(16, 3, 0.5)])
        self.scoreTest('WeWe S2S2 B9B9 DgDg DrDr WsWs WwWw Mwn LS1S1S1', [Score(), Score()])
    def testBMJA(self):
        """specials for chinese classical BMJA"""
        self.scoreTest(r'S1S1 s2s3s4 S5S6S7S8S9 We ws ww wn Msw Ls3s2s3s4', [Score(), Score(limits=1)])

    def scoreTest(self, string, expected):
        """execute one scoreTest test"""
        for idx, ruleset in enumerate(RULESETS):
            variants = []
            variant = HandContent(ruleset, string)
            variants.append(variant)
            score = variant.score
# activate depending on what you are testing
#            kprint(string, 'expected:', expected.__str__()), variant
#            kprint(ruleset.name.encode('utf-8'))
#            kprint('\n'.join(variant.explain).encode('ut-f8'))
            if isinstance(expected, list):
                exp = expected[idx]
            else:
                exp = expected
            self.assert_(score == exp, self.dumpCase(variants, exp))

    def dumpCase(self, variants, expected):
        """dump test case"""
        assert self
        result = []
        result.append('')
        result.append(variants[0].string)
        for hand in variants:
            score = hand.score
            if score != expected:
                result.append('%s: %s should be %s' % (hand.ruleset.name, score.__str__(), expected.__str__()))
                result.append('hand:%s' % hand)
            result.extend(hand.explain())
            result.append('base=%d,doubles=%d,total=%d' % (score.points, score.doubles, hand.total()))
            result.append('')
        return '\n'.join(result).encode('ascii', 'ignore')

class TstProgram(unittest.TestProgram):
    """we want global access to this program so we can check for verbosity in our tests"""
    def __init__(self, *args, **kwargs):
        global PROGRAM # pylint: disable=W0603
        PROGRAM = self
        unittest.TestProgram.__init__(self, *args, **kwargs)

if __name__ == '__main__':
    initLog('kajonggtest')
    Debug.profileRegex = True
   # Debug.handMatch = True
    TstProgram()
