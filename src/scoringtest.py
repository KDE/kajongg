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
from scoring import Hand, Ruleset

class RegTest(unittest.TestCase):
    """tests lots of hand examples. We might want to add comments which test should test which rule"""
    def __init__(self, arg):
        unittest.TestCase.__init__(self, arg)
        self.rulesets = [Ruleset('CCP'), Ruleset('CCR')]

    def testPartials(self):
        self.scoreTest(r'drdrdr fe', 'mesdr', expectedPoints = 16)
        self.scoreTest(r'fe', 'mesdr', expectedPoints = 4)
        self.scoreTest(r'fs fw fe fn', 'mesdr', expectedPoints = 32)
        self.scoreTest(r'drdrdr', 'mesdr', expectedPoints = 8)
    def testTrueColorGame(self):
        self.scoreTest(r'b1b1b1B1 B2B3B4B5B6B7B8B8B2B2B2 fe fs fn fw', 'MweDr L1234123', expectedPoints=1234123)
    def testOnlyConcealedMelds(self):
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe ys', 'MweDrw L0500', expectedPoints=176, rules=[20])
        self.scoreTest(r'b1B1B1b1 B2B3B4 B5B6B7 B8B8B8 DrDr fe ys', 'MweDrw L0500', expectedPoints=288, rules=[20])

    def testLimitHands(self):
        self.scoreTest(r'c1c1c1 c9c9 b9b9b9b9 s1s1s1 s9s9s9', 'Meec1 L1234123', expectedPoints=1234123, rules=[20])
        self.scoreTest(r'c1c1c1c1 drdr wewewewe c3c3c3C3 s1S1S1s1', 'Meec1 L1234123', expectedPoints=1234123, rules=[20])
        self.scoreTest(r'drdr c1c1c1c1 wewewewe c3c3c3C3 s1S1S1s1', 'Meec1 L1234123', expectedPoints=1234123, rules=[20])
        self.scoreTest(r'c1c1c1c1 wewewewe c3c3c3C3 s1S1S1s1 drdr', 'Meec1 L1234123', expectedPoints=1234123, rules=[20])
        self.scoreTest(r'b2b2b2b2 DgDgDg b6b6b6 b4b4b4 b8b8', 'Meeb2 L1234123', expectedPoints=1234123, rules=[20])
    def testNineGates(self):
        self.scoreTest(r'C1C1C1C2C3C4C5C6C7C8C9C9C9 c5', 'MeeC5 L1234123', expectedPoints=1234123)
        self.scoreTest(r'C1C1C1C2C3C4C5C6C7C8C9C9C9 c5', 'Meec5 L1234123', expectedPoints=1234123)
    def testThirteenOrphans(self):
        self.scoreTest(r'c1c9B9b1s1s9wedgwswnwwdbdrs1', 'mesdr L12345', expectedPoints=0)
        self.scoreTest(r'c1c9B9b1s1s9wedgwswnwwdbdrs9', 'Mesdr L1234123', expectedPoints=1234123)
    def testSimpleNonWinningCases(self):
        self.scoreTest(r's2s2s2 s2s3s4 B1B1B1B1 c9c9c9C9', 'mes L0500', expectedPoints = 26)
    def testAllHonours(self):
        self.scoreTest(r'drdrdr wewe wswsws wnwnwn dbdbdb', 'Mesdrz L1234123', expectedPoints=1234123)
        self.scoreTest(r'wewewe wswsws WnWnWn wwwwwwww B1', 'mne L0590', expectedPoints=512)
        self.scoreTest(r'wewe wswsws WnWnWn wwwwwwww b1b1', 'mne L0500', expectedPoints=120)
        self.scoreTest(r'wewewe wswsws WnWnWn wwwwwwww b1b1', 'Mneb1Z L1234123', expectedPoints=1234123)
        self.scoreTest(r'wewewe wswsws WnWnWn wwwwwwww DrDr', 'MneDrd L1234123', expectedPoints=1234123)
        self.scoreTest(r'wewewe wswsws WnWnWn wwwwwwww DrDr', 'MneDrd L1234123', expectedPoints=1234123)
        self.scoreTest(r'wewewe wswsws WnWnWn wwwwwwww DrDr', 'MneDrz L1234123', expectedPoints=1234123)
    def testRest(self):
        self.scoreTest(r's1s1s1s1 s2s2s2 wewe S3S3S3 s4s4s4', 'Msws3 L0500', expectedPoints = 352, rules=[21])
        self.scoreTest(r'b3B3B3b3 DbDbDb DrDrDr wewewewe s2s2', 'Mees2 L9999', expectedPoints = 4608, rules=[20])
        self.scoreTest(r's1s2s3 s1s2s3 b3b3b3 b4b4b4 B5B5 fn yn', 'mne L0500', expectedPoints = 24)
        self.scoreTest(r'WeWeWe C3C3C3 c4c4c4C4 b8B8B8b8 S3S3', 'Meec4 L1234123', expectedPoints=1234123, rules=[29])
        self.scoreTest(r'WeWeWe C3C3C3 c4c4c4C4 b8B8B8b8 S3S3', 'Meec4 L9999', expectedPoints=1792, rules=[21])
        self.scoreTest(r'b3b3b3b3 DbDbDb drdrdr weWeWewe s2s2', 'Mees2 L9999', expectedPoints = 2432,  rules=[20])
        self.scoreTest(r's2s2s2 s2s3s4 B1B1B1B1 c9C9C9c9', 'mes L0500', expectedPoints = 42)
        self.scoreTest(r's2s2s2 DgDg DbDbDb b2b2b2b2 DrDrDr', 'Mees2w L0900', expectedPoints = 800,  rules=[20])
        self.scoreTest(r's2s2 DgDgDg DbDbDb b2b2b2b2 DrDrDr', 'Mees2w L1234123', expectedPoints=1234123,  rules=[20])
        self.scoreTest(r's2s2 DgDgDg DbDbDb b2b2b2b2 DrDrDr', 'mee L3500', expectedPoints =2048)
        self.scoreTest(r's1s1s1s1 s2s2s2 s3s3s3 s4s4s4 s5s5', 'MswS3w L2500', expectedPoints = 704,  rules=[20])
        self.scoreTest(r'B2C1B2C1B2C1WeWeS4WeS4WeS6S5', 'mee L0500', expectedPoints = 160)
        self.scoreTest(r'c1c1c1 c3c4c5 c6c7c8 c9c9c9 c2c2', 'Meec1w L1234123', expectedPoints=1234123,  rules=[20])
        self.scoreTest(r'b6b6b6 B1B1B2B2B3B3B7S7C7B8', 'mnn L0500', expectedPoints=2)
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe fs fn fw ', 'MweDrw L0500', expectedPoints=416,  rules=[20])
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe fs fn fw ', 'MweDre L0900', expectedPoints=800,  rules=[21])
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe fs fn fw ', 'MweDrz L0900', expectedPoints=800,  rules=[22])
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe fs fn fw ', 'MweDrZ L0900', expectedPoints=800,  rules=[23])
        self.scoreTest(r'B1B1B1B1B2B3B4B5B6B7B8B8B2B2 fe fs fn fw ', 'mwe L0500', expectedPoints=56)
        self.scoreTest(r's1s2s3 s1s2s3 B6B6B7B7B8B8 B5B5 fn yn', 'MneB5ka L0500', expectedPoints = 256,  rules=[20, 24, 25])
        self.scoreTest(r'wewe wswsws WnWnWn wwwwwwww b1b1b1', 'Mneb1z L3500', expectedPoints=3456,  rules=[22])
    def testTerminals(self):
        # must disallow chows:
        self.scoreTest(r'b1b1 c1c2c3 c1c2c3 c1c2c3 c1c2c3', 'Mesb1 L1234123', expectedPoints = 52,  rules = [20] )

    def scoreTest(self, tiles, mjStr, expectedPoints=0, expectedLimits=0, rules=None):
        """execute one scoreTest test"""
        variants = []
        for ruleset in self.rulesets:
            variant = Hand(ruleset, tiles, mjStr, rules)
            variants.append(variant)
            score = variant.score()
            print(tiles, mjStr, expectedPoints, expectedLimits)
            print(ruleset.name.encode('utf8'))
            print('\n'.join(variant.explain).encode('utf8'))
            #TODO: make expected a class Score()
            self.assert_(score.total(variant.limit) == expectedPoints, self.dumpCase(variants, expectedPoints))

    def dumpCase(self, variants, expectedPoints):
        """dump test case data"""
        assert self
        result = []
        result.append('')
        result.append('%s%s' % (variants[0].normalized, variants[0].mjStr))
        for hand in variants:
            score = hand.score()
            if score.total(hand.limit) != expectedPoints:
                result.append('%s: %d should be %d' % (hand.ruleset.name, score.total(hand.limit), expectedPoints))
            result.extend(hand.explain)
            result.append('base=%d,doubles=%d,total=%d' % (score.points, score.doubles,  score.total(hand.limit)))
            result.append('')
        return '\n'.join(result)

if __name__ == '__main__':
    unittest.main()
