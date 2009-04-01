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
from scoring import Hand, Ruleset, LIMIT

class RegTest(unittest.TestCase):
    """tests lots of hand examples. We might want to add comments which test should test which rule"""
    def __init__(self, arg):
        unittest.TestCase.__init__(self, arg)
        self.rulesetP = Ruleset('CCP')
        self.rulesetR = Ruleset('CCR')

    def testPartials(self):
        self.score(r'drdrdr', 'mesdr', expected = 8)
    def testTrueColorGame(self):
        self.score(r'b1b1b1B1 B2B3B4B5B6B7B8B8B2B2B2 fe fs fn fw', 'MweDrw L0500', expected=LIMIT)
    def testOnlyConcealedMelds(self):
        self.score(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe  ys', 'MweDrw L0500', expected=184)
        self.score(r'b1B1B1b1 B2B3B4 B5B6B7 B8B8B8 DrDr fe  ys', 'MweDrw L0500', expected=296)

    def testLimitHands(self):
        self.score(r'c1c1c1 c9c9 b9b9b9b9 s1s1s1 s9s9s9', 'Meec1w', expected=LIMIT)
        self.score(r'c1c1c1c1 drdr wewewewe c3c3c3C3 s1S1S1s1', 'Meec1w', expected=LIMIT)
        self.score(r'drdr c1c1c1c1 wewewewe c3c3c3C3 s1S1S1s1', 'Meec1w', expected=LIMIT)
        self.score(r'c1c1c1c1 wewewewe c3c3c3C3 s1S1S1s1 drdr', 'Meec1w', expected=LIMIT)
        self.score(r'b2b2b2b2 DgDgDg b6b6b6 b4b4b4 b8b8', 'Meeb2w', expected=LIMIT)
    def testNineGates(self):
        self.score(r'C1C1C1C2C3C4C5C6C7C8C9C9C9 c5', 'MeeC5w', expected=LIMIT)
        self.score(r'C1C1C1C2C3C4C5C6C7C8C9C9C9 c5', 'Meec5w', expected=LIMIT)
    def testThirteenOrphans(self):
        self.score(r'c1c9B9b1s1s9wedgwswnwwdbdrs1', 'mesdrd', expected=0)
        self.score(r'c1c9B9b1s1s9wedgwswnwwdbdrs9', 'Mesdrd', expected=LIMIT)
    def testSimpleNonWinningCases(self):
        self.score(r's2s2s2 s2s3s4 B1B1B1B1 c9c9c9C9', 'mes L0500', expected = 26)
    def testAllHonours(self):
        self.score(r'drdrdr wewe wswsws wnwnwn dbdbdb', 'Mesdrz', expected=LIMIT)
        self.score(r'wewewe wswsws WnWnWn wwwwwwww B1', 'mne L0500', expected=512)
        self.score(r'wewe wswsws WnWnWn wwwwwwww b1b1', 'mne L0500', expected=120)
        self.score(r'wewewe wswsws WnWnWn wwwwwwww b1b1', 'Mneb1Z L0500', expected=LIMIT)
        self.score(r'wewewe wswsws WnWnWn wwwwwwww DrDr', 'MneDrd L0500', expected=LIMIT)
        self.score(r'wewewe wswsws WnWnWn wwwwwwww DrDr', 'MneDrd L0500', expected=LIMIT)
        self.score(r'wewewe wswsws WnWnWn wwwwwwww DrDr', 'MneDrz L0500', expected=LIMIT)
    def testRest(self):
        self.score(r's1s1s1s1 s2s2s2 wewe S3S3S3 s4s4s4', 'Msws3d L0500', expected = 352)
        self.score(r'b3B3B3b3 DbDbDb DrDrDr wewewewe s2s2', 'Mees2w L0500', expected = 4608)
        self.score(r's1s2s3 s1s2s3 b3b3b3 b4b4b4 B5B5 fn yn', 'mne L0500', expected = 24)
        self.score(r'WeWeWe C3C3C3 c4c4c4C4 b8B8B8b8 S3S3', 'Meec4w', expected=LIMIT)
        self.score(r'WeWeWe C3C3C3 c4c4c4C4 b8B8B8b8 S3S3', 'Meec4d', expected=1792)
        self.score(r'b3b3b3b3 DbDbDb drdrdr weWeWewe s2s2', 'Mees2w L0500', expected = 2432)
        self.score(r's2s2s2 s2s3s4 B1B1B1B1 c9C9C9c9', 'mes L0500', expected = 42)
        self.score(r's2s2s2 DgDg DbDbDb b2b2b2b2 DrDrDr', 'Mees2w L0500', expected = 800)
        self.score(r's2s2 DgDgDg DbDbDb b2b2b2b2 DrDrDr', 'Mees2w L0500', expected =LIMIT)
        self.score(r's2s2 DgDgDg DbDbDb b2b2b2b2 DrDrDr', 'mee L0500', expected =2048)
        self.score(r's1s1s1s1 s2s2s2 s3s3s3 s4s4s4 s5s5', 'MswS3w L0500', expected = 736)
        self.score(r'B2C1B2C1B2C1WeWeS4WeS4WeS6S5', 'mee L0500', expected = 160)
        self.score(r'c1c1c1 c3c4c5 c6c7c8 c9c9c9 c2c2', 'Meec1w', expected=LIMIT)
        self.score(r'b6b6b6 B1B1B2B2B3B3B7S7C7B8', 'mnn L0500', expected=2)
        self.score(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe  fs  fn fw ', 'MweDrw L0500', expected=432)
        self.score(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe  fs  fn fw ', 'MweDrd L0500', expected=832)
        self.score(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe  fs  fn fw ', 'MweDrz L0500', expected=832)
        self.score(r'B1B1B1B1B2B3B4B5B6B7B8B9DrDr fe  fs  fn fw ', 'MweDrZ L0500', expected=832)
        self.score(r'B1B1B1B1B2B3B4B5B6B7B8B8B2B2 fe  fs  fn fw ', 'mwe L0500', expected=56)
        self.score(r's1s2s3 s1s2s3 B6B6B7B7B8B8 B5B5 fn yn', 'MneB5ka L0500', expected = 256)
        self.score(r'wewe wswsws WnWnWn wwwwwwww b1b1b1', 'Mneb1z L0500', expected=3456)

    def score(self, tiles, mjStr, expected):
        """execute one score test"""
        handP = Hand(self.rulesetP, tiles, mjStr)
        handP.score()
        print tiles, mjStr, expected
        print self.rulesetP.name
        print '\n'.join(handP.explain)
        handR = Hand(self.rulesetR, tiles, mjStr)
        handR.score()
        print self.rulesetR.name
        print '\n'.join(handR.explain)
        print
        self.assert_(handP.total == expected and handR.total == expected, self.dumpCase(handP, handR, expected))

    def dumpCase(self, handP, handR, expected):
        """dump test case data"""
        assert self
        result = []
        result.append('')
        result.append('%s%s' % (handP.normalized, handP.mjStr))
        for hand in handP, handR:
            if hand.total != expected:
                result.append('%s: %d should be %d' % (hand.ruleset.name, hand.total, expected))
            result.extend(hand.explain)
            result.append('base=%d,doubles=%d,total=%d' % (hand.basePoints, hand.doubles,  hand.total))
            result.append('')
        return '\n'.join(result)

if __name__ == '__main__':
    unittest.main()
