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
from scoring import Hand, Ruleset,  Score

class RegTest(unittest.TestCase):
    """tests lots of hand examples. We might want to add comments which test should test which rule"""
    def __init__(self, arg):
        unittest.TestCase.__init__(self, arg)
        self.rulesets = [Ruleset('CCP'), Ruleset('CCR')]

    def testPartials(self):
        self.scoreTest(r'drdrdr fe', 'mesdr', Score(8, 1))
        self.scoreTest(r'fe', 'mesdr', Score(4))
        self.scoreTest(r'fs fw fe fn', 'mesdr', Score(16, 1))
        self.scoreTest(r'drdrdr', 'mesdr', Score(4, 1))
    def testTrueColorGame(self):
        self.scoreTest(r'b1b1b1B1 B2B3B4B5B6B7B8B8B2B2B2 fe fs fn fw', 'MweDr', Score(limits=1))
    def testOnlyConcealedMelds(self):
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe ys', 'MweDrw', Score(44, 2), rules=[20])
        self.scoreTest(r'b1B1B1b1 B2B3B4 B5B6B7 B8B8B8 DrDr fe ys', 'MweDrw', Score(72, 2), rules=[20])

    def testLimitHands(self):
        self.scoreTest(r'c1c1c1 c9c9 b9b9b9b9 s1s1s1 s9s9s9', 'Meec1', Score(limits=1), rules=[20])
        self.scoreTest(r'c1c1c1c1 drdr wewewewe c3c3c3C3 s1S1S1s1', 'Meec1', Score(limits=1), rules=[20])
        self.scoreTest(r'drdr c1c1c1c1 wewewewe c3c3c3C3 s1S1S1s1', 'Meec1', Score(limits=1), rules=[20])
        self.scoreTest(r'c1c1c1c1 wewewewe c3c3c3C3 s1S1S1s1 drdr', 'Meec1', Score(limits=1), rules=[20])
        self.scoreTest(r'b2b2b2b2 DgDgDg b6b6b6 b4b4b4 b8b8', 'Meeb2', Score(limits=1), rules=[20])
    def testNineGates(self):
        self.scoreTest(r'C1C1C1C2C3C4C5C6C7C8C9C9C9 c5', 'MeeC5', Score(limits=1))
        self.scoreTest(r'C1C1C1C2C3C4C5C6C7C8C9C9C9 c5', 'Meec5', Score(limits=1))
    def testThirteenOrphans(self):
        self.scoreTest(r'c1c9B9b1s1s9wedgwswnwwdbdrs1', 'mesdr', Score())
        self.scoreTest(r'c1c9B9b1s1s9wedgwswnwwdbdrs9', 'Mesdr', Score(limits=1))
    def testSimpleNonWinningCases(self):
        self.scoreTest(r's2s2s2 s2s3s4 B1B1B1B1 c9c9c9C9', 'mes', Score(26))
    def testAllHonours(self):
        self.scoreTest(r'drdrdr wewe wswsws wnwnwn dbdbdb', 'Mesdrz', Score(limits=1))
        self.scoreTest(r'wewewe wswsws WnWnWn wwwwwwww B1', 'mne', Score(32, 4))
        self.scoreTest(r'wewe wswsws WnWnWn wwwwwwww b1b1', 'mne', Score(30, 2))
        self.scoreTest(r'wewewe wswsws WnWnWn wwwwwwww b1b1', 'Mneb1Z', Score(limits=1))
        self.scoreTest(r'wewewe wswsws WnWnWn wwwwwwww DrDr', 'MneDrd', Score(limits=1))
        self.scoreTest(r'wewewe wswsws WnWnWn wwwwwwww DrDr', 'MneDrd', Score(limits=1))
        self.scoreTest(r'wewewe wswsws WnWnWn wwwwwwww DrDr', 'MneDrz', Score(limits=1))
    def testRest(self):
        self.scoreTest(r's1s1s1s1 s2s2s2 wewe S3S3S3 s4s4s4', 'Msws3', Score(44, 3), rules=[21])
        self.scoreTest(r'b3B3B3b3 DbDbDb DrDrDr wewewewe s2s2', 'Mees2', Score(72, 6), rules=[20])
        self.scoreTest(r's1s2s3 s1s2s3 b3b3b3 b4b4b4 B5B5 fn yn', 'mne', Score(12, 1))
        self.scoreTest(r'WeWeWe C3C3C3 c4c4c4C4 b8B8B8b8 S3S3', 'Meec4', Score(limits=1), rules=[29])
        self.scoreTest(r'WeWeWe C3C3C3 c4c4c4C4 b8B8B8b8 S3S3', 'Meec4', Score(56, 5), rules=[21])
        self.scoreTest(r'b3b3b3b3 DbDbDb drdrdr weWeWewe s2s2', 'Mees2', Score(76, 5),  rules=[20])
        self.scoreTest(r's2s2s2 s2s3s4 B1B1B1B1 c9C9C9c9', 'mes', Score(42))
        self.scoreTest(r's2s2s2 DgDg DbDbDb b2b2b2b2 DrDrDr', 'Mees2w', Score(50, 4),  rules=[20])
        self.scoreTest(r's2s2 DgDgDg DbDbDb b2b2b2b2 DrDrDr', 'Mees2w', Score(limits=1),  rules=[20])
        self.scoreTest(r's2s2 DgDgDg DbDbDb b2b2b2b2 DrDrDr', 'mee', Score(32, 6))
        self.scoreTest(r's1s1s1s1 s2s2s2 s3s3s3 s4s4s4 s5s5', 'MswS3w', Score(44, 4),  rules=[20])
        self.scoreTest(r'B2C1B2C1B2C1WeWeS4WeS4WeS6S5', 'mee', Score(20, 3))
        self.scoreTest(r'c1c1c1 c3c4c5 c6c7c8 c9c9c9 c2c2', 'Meec1w', Score(limits=1),  rules=[20])
        self.scoreTest(r'b6b6b6 B1B1B2B2B3B3B7S7C7B8', 'mnn', Score(2))
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe fs fn fw ', 'MweDrw', Score(52, 3),  rules=[20])
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe fs fn fw ', 'MweDre', Score(50, 4),  rules=[21])
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe fs fn fw ', 'MweDrz', Score(50, 4),  rules=[22])
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe fs fn fw ', 'MweDrZ', Score(50, 4),  rules=[23])
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B8B2B2 fe fs fn fw ', 'mwe', Score(28, 1))
        self.scoreTest(r's1s2s3 s1s2s3 B6B6B7B7B8B8 B5B5 fn yn', 'MneB5ka', Score(32, 3),  rules=[20, 24, 25])
        self.scoreTest(r'wewe wswsws WnWnWn wwwwwwww b1b1b1', 'Mneb1z', Score(54, 6),  rules=[22])
    def testTerminals(self):
        # must disallow chows:
        self.scoreTest(r'b1b1 c1c2c3 c1c2c3 c1c2c3 c1c2c3', 'Mesb1', Score(26, 1),  rules = [20] )

    def scoreTest(self, tiles, mjStr, expected, rules=None):
        """execute one scoreTest test"""
        variants = []
        for ruleset in self.rulesets:
            variant = Hand(ruleset, tiles, mjStr, rules)
            variants.append(variant)
            score = variant.score()
            print(tiles, mjStr, 'expected:', expected.__str__())
            print(ruleset.name.encode('utf8'))
            print('\n'.join(variant.explain).encode('utf8'))
            #TODO: make expected a class Score()
            self.assert_(score == expected, self.dumpCase(variants, expected))

    def dumpCase(self, variants, expected):
        """dump test case data"""
        assert self
        result = []
        result.append('')
        result.append('%s%s' % (variants[0].normalized, variants[0].mjStr))
        for hand in variants:
            score = hand.score()
            if score != expected:
                result.append('%s: %s should be %s' % (hand.ruleset.name, score.__str__(), expected.__str__()))
            result.extend(hand.explain)
            result.append('base=%d,doubles=%d,total=%d' % (score.points, score.doubles,  score.total(hand.limit)))
            result.append('')
        return '\n'.join(result).encode('ascii', 'ignore')

if __name__ == '__main__':
    unittest.main()
