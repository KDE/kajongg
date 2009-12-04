#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""
Copyright (C) 2009 Wolfgang Rohdewald <wolfgang@rohdewald.de>

kmj is free software you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

import unittest
from scoringengine import HandContent,  Score, Regex
from predefined import ClassicalChinese

RULESETS = [ClassicalChinese()]
for x in RULESETS:
    x.load()
    x.profileIt = True

class RegTest(unittest.TestCase):
    """tests lots of hand examples. We might want to add comments which test should test which rule"""
    def __init__(self, arg):
        unittest.TestCase.__init__(self, arg)

    def testPartials(self):
        self.scoreTest(r'drdrdr fe mesdr', Score(8, 1))
        self.scoreTest(r'fe mesdr', Score(4))
        self.scoreTest(r'fs fw fe fn mesdr', Score(16, 1))
        self.scoreTest(r'drdrdr mesdr', Score(4, 1))
    def testFalseColorGame(self):
        self.scoreTest(r'c1c1c1 c7c7c7 c2c3c4 c5c5 c6c6c6 Mwn Lc5c5c5', Score(points=34, doubles=3))
        self.scoreTest(r'c1c2c3 wewewe drdrdr dbdb DgDgDg Mwn Ldbdbdb', Score(points=46, doubles=4))
        self.scoreTest(r's1s1s1 wewewe c2c3c4 c5c5 c6c6c6 Mwn Lc5c5c5', Score(points=36))
    def testWindingSnake(self):
        self.scoreTest(r'c1c1c1 c3c4c5 c9c9c9 c6c7c8 c2c2 Mee Lc1c1c1c1', Score(limits=1))
        self.scoreTest(r'c1c1c1 c4c5c6 c9c9c9 c6c7c8 c2c2 Mee Lc1c1c1c1', Score(points=28, doubles=3))
        self.scoreTest(r'c1c1c1 c3c4c5 c9c9c9 c6c7c8 s2s2 Mee Lc1c1c1c1', Score(points=28))
        self.scoreTest(r's1s1s1 s2s3s4 s9s9s9 s6s7s8 s5s5 Mee Ls1s1s1s1', Score(limits=1))
        self.scoreTest(r'b1b1b1 c3c4c5 c6c7c8 c9c9c9 c2c2 Mee Lc3c3c4c5', Score(points=28))
        self.scoreTest(r'b1b1b1 c3c4c5 c6c7c8 c9c9c9 c2c2 Mee Lc4c3c4c5', Score(points=32))
    def testTrueColorGame(self):
        self.scoreTest(r'b1b1b1b1 B2B3B4B5B6B7B8B8B2B2B2 fe fs fn fw Mwe LB3B2B3B4', Score(points=62, doubles=4))
        self.scoreTest(r'b1b1b1B1 B2B3B4B5B6B7B8B8B2B2B2 fe fs fn fw Mwe LB3B2B3B4', Score(limits=1))
    def testOnlyConcealedMelds(self):
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe ys Mwe LDrDrDr', Score(48, 2))
        self.scoreTest(r'b1B1B1b1 B2B3B4 B5B6B7 B8B8B8 DrDr fe ys Mwe LDrDrDr', Score(76, 2))

    def testLimitHands(self):
        self.scoreTest(r'c1c1c1 c9c9 b9b9b9b9 s1s1s1 s9s9s9 Mee Lc1c1c1c1', Score(limits=1))
        self.scoreTest(r'c1c1c1c1 drdr wewewewe c3c3c3C3 s1S1S1s1 Mee Ldrdrdr', Score(limits=1))
        self.scoreTest(r'drdr c1c1c1c1 wewewewe c3c3c3C3 s1S1S1s1 Mee Ldrdrdr', Score(limits=1))
        self.scoreTest(r'c1c1c1c1 wewewewe c3c3c3C3 s1S1S1s1 drdr Mee Ldrdrdr', Score(limits=1))
    def testAllGreen(self):
        self.scoreTest(r'b2b2b2b2 DgDgDg b6b6b6 b4b4b4 b8b8 Mee Lb6b6b6b6', Score(limits=1))
        self.scoreTest(r'b1b1b1b1 DgDgDg b6b6b6 b4b4b4 b8b8 Mee Lb6b6b6b6', Score(points=48, doubles=3))
    def testNineGates(self):
        self.scoreTest(r'C1C1C1 C2C3C4 C5C6C7 C8 C9C9C9 c5 Mee LC5C5', Score(limits=1))
    def testManual(self):
        # this should actually never happen but anyway we want to be sure that no rule
        # fires on this
        self.scoreTest(r' Mse L', Score(points=20))
        self.scoreTest(r' mse', Score(points=0))
    def testThirteenOrphans(self):
        self.scoreTest(r'c1 c9 B9 b1 s1 s9 we dg ws wn ww db dr s1 mes', Score())
        self.scoreTest(r'c1 c9 B9 b1 s1 s9 we dg ws wn ww db dr s9 Mes Ldrdr', Score(limits=1))
        self.scoreTest(r'c1 c9 B9 b1 s1 s9 s9 we dg ws wn ww db dr Mes Ldrdr', Score(limits=1))
        self.scoreTest(r'c1c9B9b1s1s9s9wedgwswnwwdbdr Mes Ldrdr', Score(limits=1))
    def testSimpleNonWinningCases(self):
        self.scoreTest(r's2s2s2 s2s3s4 B1B1B1B1 c9c9c9C9 mes', Score(26))
    def testFourBlessingsOverTheDoor(self):
        self.scoreTest(r'b1b1 wewewe wswsws WnWnWn wwwwwwww Mne Lb1b1b1', Score(limits=1))
        self.scoreTest(r'DgDg wewewe wswsws WnWnWn wwwwwwww Mne Lb1b1b1', Score(limits=1))
        self.scoreTest(r'wewewe wswsws WnWnWn wwwwwwww DrDr Mne LDrDrDr', Score(limits=1))
        self.scoreTest(r'wewewe wswsws WnWnWn wwwwwwww DrDr Mne LDrDrDr', Score(limits=1))
        self.scoreTest(r'wewewe wswsws WnWnWn wwwwwwww DrDr Mnez LDrDrDr', Score(limits=1))
    def testAllHonours(self):
        self.scoreTest(r'drdrdr wewe wswsws wnwnwn dbdbdb Mesz Ldrdrdrdr', Score(limits=1))
        self.scoreTest(r'wewewe wswsws WnWnWn wwwwwwww B1 mne', Score(32, 4))
        self.scoreTest(r'wewe wswsws WnWnWn wwwwwwww b1b1 mne', Score(30, 2))
    def testHiddenTreasure(self):
        self.scoreTest(r'WeWeWe C3C3C3 c4c4c4C4 b8B8B8b8 S3S3 Mee LWeWeWeWe',
                       Score(limits=1), rules=['Last Tile Taken from Dead Wall'])
        self.scoreTest(r'WeWeWe C3C3C3 c4c4c4C4 b8B8B8b8 S3S3 Mee LC3C3C3C3',
                       Score(limits=1))
        self.scoreTest(r'WeWeWe C3C3C3 c4c4c4C4 b8B8B8b8 s3s3 Mee Ls3s3s3',
                       Score(62, 4))
    def testFourfoldPlenty(self):
        self.scoreTest(r'B3B3B3 C1C1C1 b1b1b1 s3s4s5 wewe Mee LB3B3B3B3', Score(42))
        self.scoreTest(r'b3B3B3b3 c1C1C1c1 b1b1b1b1 s3s3s3s3 wewe Mee LB3B3B3B3', Score(limits=1))
        self.scoreTest(r'b3b3 c1C1C1c1 b1b1b1b1 s3s3s3s3 wewewewe Mee LB3B3B3B3', Score(limits=1))
        self.scoreTest(r'b3b3b3b3 c1c1 b1b1b1b1 s3s3s3s3 wewewewe Mee LB3B3B3B3', Score(limits=1))
    def testRest(self):
        self.scoreTest(r's1s1s1s1 s2s2s2 wewe S3S3S3 s4s4s4 Msw Ls2s2s2s2',
                       Score(44, 2), rules=['Last Tile Taken from Dead Wall'])
        self.scoreTest(r's1s1s1s1 s2s2s2 wewe S3S3S3 s4s4s4 Mswe LS3S3S3S3',
                       Score(46, 3), rules=['Last Tile Taken from Dead Wall'])
        self.scoreTest(r'b3B3B3b3 DbDbDb DrDrDr wewewewe s2s2 Mee Ls2s2s2', Score(74, 6))
        self.scoreTest(r's1s2s3 s1s2s3 b3b3b3 b4b4b4 B5 fn yn mne', Score(12, 1))
        self.scoreTest(r'b3b3b3b3 DbDbDb drdrdr weWeWewe s2s2 Mee Ls2s2s2', Score(78, 5))
        self.scoreTest(r's2s2s2 s2s3s4 B1B1B1B1 c9C9C9c9 mes', Score(42))
        self.scoreTest(r's2s2s2 DgDg DbDbDb b2b2b2b2 DrDrDr Mee Ls2s2s2s2', Score(48, 4))
        self.scoreTest(r's2s2 DgDgDg DbDbDb b2b2b2b2 DrDrDr Mee Ls2s2s2', Score(limits=1))
        self.scoreTest(r's2 DgDgDg DbDbDb b2b2b2b2 DrDrDr mee', Score(32, 6))
        self.scoreTest(r's1s1s1s1 s2s2s2 s3s3s3 s4s4s4 s5s5 Msww Ls3s3s3s3', Score(42, 4))
        self.scoreTest(r'B2C1B2C1B2C1WeWeS4WeS4WeS6 mee', Score(20, 3))
        self.scoreTest(r'b6b6b6 B1B1B2B2B3B3B7S7C7B8 mnn', Score(2))
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe fs fn fw Mwe LDrDrDr', Score(56, 3))
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe fs fn fw Mwee LDrDrDr',
                       Score(56, 4),  rules=['Last Tile Taken from Dead Wall'])
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe fs fn fw Mwez LDrDrDr',
                       Score(56, 4),  rules=['Last Tile is Last Tile of Wall'])
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe fs fn fw MweZ LDrDrDr',
                       Score(56, 3),  rules=['Last Tile is Last Tile of Wall Discarded'])
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B9drdr fe fs fn fw MweZ Ldrdrdr',
                       Score(52, 3),  rules=['Last Tile is Last Tile of Wall Discarded'])
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B8B2B2 fe fs fn fw mwe', Score())
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B8B8B2B2 fe fs fn fw mwe', Score(28, 1))
        self.scoreTest(r'wewe wswsws WnWnWn wwwwwwww b1b1b1 Mnez Lb1b1b1b1',
                       Score(54, 5),  rules=['Last Tile is Last Tile of Wall'])
        self.scoreTest(r'wewe wswsws WnWnWn wwwwwwww b1b1b1 Mnez LB1B1B1B1',
                       Score(56, 6),  rules=['Last Tile is Last Tile of Wall'])
    def testRobbingKong(self):
        self.scoreTest(r's1s2s3 s1s2s3 B6B6B7B7B8B8 b5b5 fn yn Mneka Lb5b5b5',
                       Score(34, 2),  rules=['Robbing the Kong', 'Mah Jongg with Call at Beginning'])
        self.scoreTest(r'S1S2S3 s4s5s6 B6B6B7B7B8B8 b5b5 fn yn Mneka LS1S1S2S3',
                       Score(30, 2),  rules=['Robbing the Kong', 'Mah Jongg with Call at Beginning'])
        self.scoreTest(r's1s2s3 s4s5s6 B6B6B7B7B8B8 b5b5 fn yn Mneka Ls1s1s2s3',
                       Score(28, 3),  rules=['Robbing the Kong', 'Mah Jongg with Call at Beginning'])

    def testTerminals(self):
        # must disallow chows:
        self.scoreTest(r'b1b1 c1c2c3 c1c2c3 c1c2c3 c1c2c3 Mes Lb1b1b1', Score(28, 1))
    def testLongHand(self):
        self.scoreTest(r's1s2s3 s1s2s3 b3b3b3 b4b4b4 B5B5 fn yn mne', Score())
        self.scoreTest(r'B2C1B2C1B2C1WeWeS4WeS4WeS6S5 mee', Score())
        self.scoreTest(r'B2C1B2C1B2C1WeWeS4WeS4WeS6S5S5 mee', Score())
        self.scoreTest(r'B2C1B2C1B2C1WeWeS4WeS4WeS6S5S5 Mee', Score())
        self.scoreTest(r'WsWsWsWs C1C1 Wn WeWeWe S4S4 S6 S5S5 Mee', Score(0))

    def testSingle(self):
        pass

    def testZZ(self):
        profiles = []
        for ruleset in RULESETS:
            for lst in ruleset.ruleLists:
                for rule in lst:
                    for variant in rule.variants:
                        if isinstance(variant, Regex):
                            if variant.count:
                                if len(RULESETS) == 1:
                                    profiles.append((variant.timeSum / variant.count, variant.count, rule.name, variant.definition))
                                else:
                                    profiles.append((variant.timeSum / variant.count, variant.count, ruleset.name, rule.name, variant.definition))
        print
        print 'The slowest 10 regular expressions were:'
        for profile in list(reversed(sorted(profiles)))[:10]:
            print profile

    def scoreTest(self, string, expected, rulesetIdx = 0, rules=None):
        """execute one scoreTest test"""
        variants = []
        ruleset = RULESETS[rulesetIdx]
        variant = HandContent(ruleset, string, rules)
        variants.append(variant)
        score = variant.score
# activate depending on what you are testing
#            print(string, 'expected:', expected.__str__()), variant.normalized, variant.original, variant.mjStr
#            print(ruleset.name.encode('utf8'))
#            print('\n'.join(variant.explain).encode('utf8'))
        self.assert_(score == expected, self.dumpCase(variants, expected))

    def dumpCase(self, variants, expected):
        """dump test case data"""
        assert self
        result = []
        result.append('')
        result.append(variants[0].string)
        for hand in variants:
            score = hand.score
            if score != expected:
                result.append('%s: %s should be %s' % (hand.ruleset.name, score.__str__(), expected.__str__()))
                result.append('original:%s' % hand.original)
                result.append('normalized:%s' % hand.normalized)
            result.extend(hand.explain())
            result.append('base=%d,doubles=%d,total=%d' % (score.points, score.doubles,  hand.total()))
            result.append('')
        return '\n'.join(result).encode('ascii', 'ignore')

if __name__ == '__main__':
    unittest.main()
