#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

import unittest
from typing import Optional, List, Tuple, Union, TYPE_CHECKING

from common import Debug
from wind import Wind, East, South, West, North
from player import Players
from game import PlayingGame
from hand import Hand, Score
from tile import TileTuple
from predefined import ClassicalChineseDMJL, ClassicalChineseBMJA

if TYPE_CHECKING:
    from rule import Ruleset

RULESETS = []

# test each of those rulesets twice: once with limit, once with roof off
for testRuleset in [ClassicalChineseDMJL, ClassicalChineseBMJA] * 2:
    _ = testRuleset()
    _.load()
    RULESETS.append(_)

for _ in RULESETS[2:]:
    _.roofOff = True  # type: ignore

# Do not create our test players in the data base:
Players.createIfUnknown = str  # type: ignore

# RULESETS=RULESETS[:1]
GAMES = [PlayingGame([tuple([wind, str(wind.char)]) for wind in Wind.all4], x) for x in RULESETS]  # type:ignore[misc]
PROGRAM = None


class Expected:

    """define what we expect from test"""

    def __init__(self, won:bool, points:int, doubles:int, limits:float) ->None:
        self.won = won
        self.score = Score(points, doubles, limits)
        self.ruleset:Optional['Ruleset'] = None

    def __str__(self) ->str:
        return f'Won with {self.score}' if self.won else f'Lost with {self.score}'


class Nothing(Expected):

    """we do not expect anything"""

    def __init__(self, points:int=0, doubles:int=0, limits:float=0.0) ->None:
        super().__init__(True, points, doubles, limits)


class Win(Expected):

    """we expect a winning hand"""

    def __init__(self, points:int=0, doubles:int=0, limits:float=0.0) ->None:
        super().__init__(True, points, doubles, limits)


class NoWin(Expected):

    """we expect a losing hand"""

    def __init__(self, points:int=0, doubles:int=0, limits:float=0.0) ->None:
        super().__init__(False, points, doubles, limits)


class Base(unittest.TestCase):


    """tests lots of hand examples. We might want to add comments which test should test which rule"""

    # pylint: disable=too-many-locals

    def scoreTest(self, string:str, expected:Union[Expected, List[Expected]],
        myWind:Optional[Wind]=None, roundWind:Optional[Wind]=None, totals:Optional[Tuple[int, ...]]=None) ->None:
        """execute one scoreTest test"""
        if myWind is None:
            myWind = East
        if roundWind is None:
            roundWind = East
        for idx, ruleset in enumerate(RULESETS):
            if isinstance(expected, list):
                expIdx = idx
                if expIdx >= len(expected):
                    expIdx %= len(RULESETS) // 2
                exp = expected[expIdx]
            else:
                exp = expected
            exp.ruleset = ruleset
            variants = []
            game = GAMES[idx]
            for widx, wind in enumerate(Wind.all4):
                game.players[widx].wind = wind
            game.winner = game.players[myWind]
            game.myself = game.winner
            game.point.prevailing = roundWind
            game.winner.clearCache()
            if Debug.hand:
                print('')
                print(f'starting test for {ruleset.name}')
            variant = Hand(game.winner, string)
            score = variant.score
            assert score is not None
            variants.append(variant)
            self.assertTrue(
                variant.won == isinstance(exp, Win) and score == exp.score,
                self.dumpCase(variant, exp, total=None))
# activate depending on what you are testing
#            print(string, 'expected:', expected.__str__()), variant
#            print(ruleset.name.encode('utf-8'))
#            print('\n'.join(variant.explain).encode('ut-f8'))
            if totals:
                self.assertTrue(score.total() == totals[idx], '\n'.join(
                    self.dumpCase(x, exp, totals[idx]) for x in variants))

    def callingTest(self, string:str, expected:Union[str, List[str]]) ->None:
        """test a calling hand"""
        for idx, ruleset in enumerate(RULESETS):
            game = GAMES[idx]
            game.players[0].clearCache()
            hand = Hand(game.players[0], string)
            testSays = TileTuple({x.lastTile.exposed for x in hand.callingHands}).sorted()
            if isinstance(expected, list):
                if idx >= len(expected):
                    idx %= len(RULESETS) // 2
                expIdx = idx
                if expIdx >= len(expected):
                    expIdx %= len(RULESETS) // 2
                exp = expected[expIdx]
            else:
                exp = expected
            completingTiles = TileTuple(exp)
            self.assertTrue(testSays == completingTiles,
                            f"{ruleset.name}: {string} may be completed by {completingTiles or 'None'} "
                            f"but testresult is {testSays or 'None'}")

    def dumpCase(self, hand:Hand, expected:Expected, total:Optional[int]) ->str:
        """dump test case"""
        assert self
        result = []
        result.append('')
        if not hand:
            result.append('Hand was illegal: claimed to be won but was not')
        else:
            if hand.won != isinstance(expected, Win):
                result.append(
                    f'hand.won is {hand.won}, expected {isinstance(expected, Win)}')
            result.append(hand.string)
            roofOff = ' roofOff' if hand.player.game.ruleset.roofOff else ''  #  type: ignore
            score = hand.score
            assert score is not None
            assert hand.player.game
            if score != expected.score:
                result.append(f"{hand.player.game.ruleset.name}{roofOff}: "
                              f"{'Won' if hand.won else 'Lost'} with {score} should be {expected}")
                result.append(f'hand:{hand}')
            if total is not None:
                if score.total() != total:
                    result.append(f'{id(hand.player.game.ruleset)} {hand.player.game.ruleset.name}{roofOff}: '
                                  f'total {score.total()} for {str(score)} should be {total}')
                result.append(f'hand:{hand}')
            result.extend(hand.explain())
            result.append(
                f'base={int(score.points)},doubles={int(score.doubles)},total={int(hand.total())}')
            result.append('')
        return '\n'.join(result)

# pylint: disable=useless-suppression,missing-docstring



class Partials(Base):

    """some partial hands"""

    def testMe(self) ->None:
        self.scoreTest('drdrdr fe Ldrdrdrdr', [NoWin(8, 1), NoWin(8, 2)])
        self.scoreTest('fe', [NoWin(4), NoWin(4, 1)])
        self.scoreTest('fs fw fe fn', [NoWin(16, 1), NoWin(16, 3)])
        self.scoreTest('fs ys', [NoWin(8, 1), NoWin(8, 2)], myWind=South)
        self.scoreTest('drdrdr Ldrdrdrdr', NoWin(4, 1))


class ZeroHand(Base):

    """zero hand games"""

    def testMe(self) ->None:
        self.scoreTest('c1c2c3 c7c8c9 b2b3b4 c5c5 s1s2s3 fw yw Lc1c1c2c3',
                       [Win(points=28, doubles=2), NoWin()], myWind=West, roundWind=North)
        self.scoreTest('c1c2c3 c7c8c9 b2b3b4 drdr s1s2s3 fw yw Lc1c1c2c3',
                       [Win(points=30, doubles=1), NoWin()], myWind=West, roundWind=North)


class FalseColorGame(Base):

    """false color games"""

    def testMe(self) ->None:
        self.scoreTest(
            'c1c1c1 c7c7c7 c2c3c4 c5c5 c6c6c6 Lc5c5c5', [Win(32, 3), Win(28)])
        self.scoreTest('c1c2c3 wewewe drdrdr dbdb DgDgDg Ldbdbdb', [
            Win(44, 4), Win(38, 2)], myWind=West, roundWind=North)
        self.scoreTest(
            's1s1s1 wewewe c2c3c4 c5c5 c6c6c6 Lc5c5c5',
            [Win(34),
             Win(30)],
            myWind=West, roundWind=North)
        self.scoreTest(
            'RB1B1B1B1B2B3B4B5B6B7B8B9DrDr fe ys LDrDrDr', [Win(46, 2), NoWin()])
        self.scoreTest(
            'b1B1B1b1 RB2B3B4B5B6B7B8B8B8 DrDr fe ys LDrDrDr', [Win(74, 2), NoWin()])
        self.scoreTest('b1B1B1b1 RB2B2B2B5B6B7B8B8B8 DrDr fe ys LDrDrDr', [
            Win(78, 3), Win(72, 1)], myWind=West)


class WrigglingSnake(Base):

    """the wriggling snake as in BMJA"""

    def testMe(self) ->None:
        self.scoreTest(
            'c1c1 c2c3c4 c5c6c7 RC8C9WeWwWsWn Lc1c1c1', [NoWin(), NoWin()])
        self.scoreTest(
            'c2c3c4 c5c6c7 RC1C1C8C9WeWwWsWn LC1C1C1', [NoWin(), NoWin()])
        self.scoreTest(
            'c2c3c4 c5c6c7 RC1C1C8C9WeWwWsWn LWnWn', [NoWin(), NoWin()])
        self.scoreTest(
            'RC1C1C2C3C4C5C6C7C8C9WeWwWsWn LC1C1',
            [NoWin(),
             Win(limits=1)])
        self.callingTest('RS1S3WwS6WsS3S3WnWeS5 s7s8s9 fs', '')
        self.callingTest('RS1S2WwS6WsS3S3WnWeS5S7S8S9 fs', '')
        self.callingTest('RS1S2WwS6WsS3S4WnWeS5S7S8S9 fs', ['', 's1'])
        self.callingTest('RS1S2WwS6WsS3S4WnWeS1S7S8S9 fs', ['', 's5'])


class SquirmingSnake(Base):

    """the winding snake"""

    def testMe(self) ->None:
        self.scoreTest(
            'c1c1c1 c3c4c5 c9c9c9 c6c7c8 RC2C2 Lc1c1c1c1',
            [Win(limits=1),
             NoWin()])
        self.scoreTest('c1c1c1 c4c5c6 c9c9c9 c6c7c8 RC2C2 Lc1c1c1c1', [
            Win(points=28, doubles=3), NoWin()])
        self.scoreTest(
            'c1c1c1 c3c4c5 c9c9c9 c6c7c8 RS2S2 Lc1c1c1c1',
            [Win(points=28),
             NoWin()])
        self.scoreTest(
            's1s1s1 s2s3s4 s9s9s9 s6s7s8 RS5S5 Ls1s1s1s1',
            [Win(limits=1),
             NoWin()])
        self.scoreTest(
            'b1b1b1 c3c4c5 c6c7c8 c9c9c9 RC2C2 Lc3c3c4c5',
            [Win(points=28),
             NoWin()])
        self.scoreTest(
            'b1b1b1 c3c4c5 c6c7c8 c9c9c9 RC2C2 Lc4c3c4c5',
            [Win(points=30),
             NoWin()])
        self.scoreTest('RC1C1C1C2C3C4C5C6C7C8C9C9C9C5 LC5', Win(limits=1))
        self.scoreTest(
            'RC1C1C1C3C4C5C6C7C8C9C9C9C5 LC3',
            [NoWin(16),
             NoWin(limits=0.4)])
        self.scoreTest(
            'RC1C1C2C3C4C5C6C7C8C9C9C9C5 LC3',
            [NoWin(8),
             NoWin(limits=0.4)])


class Purity(Base):

    """Purity BMJA"""

    def testMe(self) ->None:
        self.scoreTest(
            'b1b1b1b1 RB2B3B4B5B6B7B8B8B2B2B2 fe fs fn fw LB3B2B3B4',
            [Win(points=60, doubles=4), NoWin()])
        self.scoreTest(
            'b1b1b1 RB3B3B3B6B6B6B8B8B2B2B2 fe fs fn fw LB3', [Win(54, 6), Win(54, 7)])
        self.scoreTest(
            'b1b1b1 RB3B3B3B6B6B8B8B2B2B2 fe fs fn fw LB3', [NoWin(28, 1), NoWin(28, 6)])
        self.scoreTest(
            'c1C1C1c1 c3c3c3 c8c8c8 RC4C5C6C7C7 fs fw ys yw Lc8c8c8c8',
            [Win(72, 4), Win(72, 2)], myWind=West)


class TrueColorGame(Base):

    """true color games"""

    def testMe(self) ->None:
        self.scoreTest(
            'b1b1b1b1 RB2B3B4B5B6B7B8B8B2B2B2 fe fs fn fw LB3B2B3B4',
            [Win(points=60, doubles=4), NoWin()])
        self.callingTest(
            'RB1B2B3B4B5B5B6B6B7B7B8B8B8 LB1', ['b1b3b4b6b7b9', ''])
        self.scoreTest(
            'b1b1b1B1 RB2B3B4B5B6B7B8B8B2B2B2 fe fs fn fw LB3B2B3B4',
            [Win(limits=1),
             NoWin()])


class OnlyConcealedMelds(Base):

    """only concealed melds"""

    def testMe(self) ->None:
        self.scoreTest(
            'RB1B1B1B1B2B3B4B5B6B7B8B9DrDr fe ys LDrDrDr', [Win(46, 2), NoWin()])
        self.scoreTest('RB1B1B1B2B2B2B4B4B4B7B8B9DrDr fe ys LDrDrDr', [
            Win(54, 3), Win(48, 1)], myWind=West)
        self.scoreTest(
            'b1B1B1b1 RB2B3B4B5B6B7B8B8B8DrDr fe ys LDrDrDr', [Win(74, 2), NoWin()])
        self.scoreTest('b1B1B1b1 RB2B2B2B5B6B7B8B8B8DrDr fe ys LDrDrDr', [
            Win(78, 3), Win(72, 1)], myWind=West)


class LimitHands(Base):

    """various limit hands"""

    def testMe(self) ->None:
        self.scoreTest(
            'c1c1c1 c9c9 b9b9b9b9 s1s1s1 s9s9s9 Lc1c1c1c1',
            Win(limits=1))
        self.scoreTest(
            'c1c1c1c1 drdr wewewewe c3c3c3C3 s1S1S1s1 Ldrdrdr',
            Win(limits=1))
        self.scoreTest(
            'drdr c1c1c1c1 wewewewe c3c3c3C3 s1S1S1s1 Ldrdrdr',
            Win(limits=1))
        self.scoreTest(
            'c1c1c1c1 wewewewe c3c3c3C3 s1S1S1s1 drdr Ldrdrdr',
            Win(limits=1))


class AllGreen(Base):

    """the green hand"""

    def testMe(self) ->None:
        self.scoreTest(
            'c1c1c1 c7c7c7 c2c3c4 c5c5 c6c6c6 Lc5c5c5', [Win(32, 3), Win(28)])
        self.scoreTest(
            'b2b2b2b2 RDgDgDg b6b6b6 b4b4b4 b8b8 Lb6b6b6b6',
            Win(limits=1))
        self.scoreTest(
            'b2b2b2b2 RDgDg b6b6b6 b4b4b4 b8b8 Lb6b6b6b6',
            [NoWin(14),
             NoWin(limits=0.4)])
        self.scoreTest(
            'b1b1b1b1 RDgDgDg b6b6b6 b4b4b4 b8b8 Lb6b6b6b6', [Win(48, 3), Win(48, 2)])


class NineGates(Base):

    """the nine gates"""
        # DMJL allows 1..9 as last tile, BMJA allows only 2..8

    def testMe(self) ->None:
        self.scoreTest('RC1C1C1C2C3C4C5C6C7C8C9C9C9C5 LC5', Win(limits=1))
        self.scoreTest(
            'RC1C1C1C2C3C4C5C6C7C8C9C9C9C5 LC6',
            [Win(limits=1),
             Win(limits=1)])
        self.scoreTest(
            'RC1C1C1C2C3C4C5C6C7C8C9C9C9C9 LC9',
            [Win(limits=1),
             NoWin()])
        self.scoreTest(
            'RC1C1C1C2C3C4C5C6C7C8C9C9C9C9 LC9',
            [Win(limits=1),
             NoWin()])
        self.scoreTest('RC1C1C1C2C3C4C5C6C7C8C9C9C9C5 LC2', Win(limits=1))
        self.scoreTest(
            'RC1C1C1C2C3C4C5C6C7C8C9C9C9C9 LC1',
            [Win(limits=1),
             NoWin()])
        self.scoreTest('RC1C1C2C3C4C5C6C7C8C9C9C9C9 LC1', NoWin(8))
        self.scoreTest(
            'RC1C1C2C3C4C5C6C7C8C8C9C9C9 LC1',
            [NoWin(8),
             NoWin(limits=0.4)])


class Manual(Base):

    """some manual rules for manual scoring"""
        # this should actually never happen but anyway we want to be sure that no rule
        # fires on this

    def testMe(self) ->None:
        self.scoreTest('', NoWin())
        self.scoreTest('', NoWin())


class ThirteenOrphans(Base):

    """The 13 orphans"""

    def testMe(self) ->None:
        self.scoreTest('RC1C9B9B1S1S9WeDgWsWnWwDbDrS1 LDgDg', Win(limits=1))
        self.scoreTest('ww RC1C9B9B1S1S9WeDgWsWnDbDrS8 Lwwww', NoWin())
        self.scoreTest('ww RC1C9B9B1S1S9WeDgWsWnDbDrS9 Lwwww', Win(limits=1))
        self.scoreTest('RC1C9B9B1S1S9S9WeDgWsWnWwDbDr LDrDr', Win(limits=1))
        self.scoreTest('dr RC1C9B9B1S1S9S9WeDgWsWnWwDb Ldrdr', Win(limits=1))
        self.scoreTest(
            'RC1C9B9B1S1S9S9WeDgWnWwDbDr LDb',
            [NoWin(),
             NoWin(limits=0.4)])
        self.callingTest('Dg Dg Dr We Ws Ww Wn Wn RB1B9C1S1S9 LWe', '')
        self.callingTest('Db Dg Dr We Ws Ww Wn B7 RB1B9C1S1S9 LWe', '')
        self.callingTest('RDbDgDrWeWsWwWnWnB1B9C1S1S9 LWn', 'c9')
        self.callingTest('RDbDgDrWsWwWnWnB1B9C1S1S9C9 LDg', 'we')


class SimpleNonWinningCases(Base):

    """normal hands"""

    def testMe(self) ->None:
        self.scoreTest('s2s2s2 s2s3s4 RB1B1B1B1 c9c9c9C9 Ls2s2s3s4', NoWin(26))


class FourBlessingsOverTheDoor(Base):

    """lots of winds"""

    def testMe(self) ->None:
        self.scoreTest(
            'b1b1 wewewe wswsws WnWnWn wwwwwwww Lb1b1b1',
            Win(limits=1))
        self.scoreTest(
            'RDgDg wewewe wswsws WnWnWn wwwwwwww LDgDgDg',
            Win(limits=1))
        self.scoreTest(
            'wewewe wswsws WnWnWn wwwwwwww DrDr LDrDrDr',
            Win(limits=1))
        self.scoreTest(
            'wewewe wswsws WnWnWn wwwwwwww DrDr LDrDrDr',
            Win(limits=1))
        self.scoreTest(
            'wewewe wswsws WnWnWn wwwwwwww DrDr mz LDrDrDr',
            Win(limits=1))
        self.scoreTest(
            'wewewe wswsws RWnWnWnDr wwwwwwww', [NoWin(32, 4), NoWin(limits=0.4)])


class AllHonors(Base):

    """only honors"""

    def testMe(self) ->None:
        self.scoreTest(
            'drdrdr wewe wswsws wnwnwn dbdbdb mz Ldrdrdrdr',
            Win(limits=1))
        self.scoreTest(
            'wewewe wswsws RWnWnWnB1 wwwwwwww LB1', [NoWin(32, 4), NoWin(limits=0.4)])
        # this one is limits=0.4 = 400 points, but points 512 are higher:
        self.scoreTest(
            'wewewe drdrdr RDrDrDrDb wwwwwwww LDb', [NoWin(32, 4), NoWin(32, 4)])
        self.scoreTest('wewe wswsws RWnWnWn wwwwwwww b1b1 Lwewewe', [
            NoWin(30, 2), NoWin(30, 1)], myWind=North)


class BuriedTreasure(Base):

    """buried treasure, CC BMJA"""

    def testMe(self) ->None:
        self.scoreTest('RWeWeWeC3C3C3S3S3 c4c4c4C4 b8B8B8b8 me LWeWeWeWe',
                       [Win(limits=1), Win(58, 4)])
        self.scoreTest('RWeWeWeC3C3C3S3S3C4C4C4B8B8B8 me LWeWeWeWe',
                       [Win(limits=1), Win(42, 4)])
        self.scoreTest('RWeWeWeC3C3C3C5C5C4C4C4C8C8C8 me LWeWeWeWe',
                       [Win(limits=1), Win(limits=1)])
        self.scoreTest('RWeWeC3C3C3C5C5C4C4C4C8C8C8 me LWe',
                       [NoWin(16, 1), NoWin(limits=0.4)])
        self.scoreTest('RWeWeWeC3C3C3C5C5C4C4C4C7C8C9 me LWeWeWeWe',
                       [Win(38, 6), Win(38, 3)])


class HiddenTreasure(Base):

    """hidden treasure, CC DMJL"""

    def testMe(self) ->None:
        self.scoreTest('RWeWeWeC3C3C3S3S3 c4c4c4C4 b8B8B8b8 me LWeWeWeWe',
                       [Win(limits=1), Win(58, 4)])
        self.scoreTest('RWeWeWeC3C3C3S3S3 c4c4c4C4 b8B8B8b8 LC3C3C3C3',
                       [Win(limits=1), Win(58, 4)])
        self.scoreTest('RWeWeWeC3C3C3 c4c4c4C4 b8B8B8b8 s3s3 Ls3s3s3',
                       [Win(60, 4), Win(56, 3)])


class FourfoldPlenty(Base):

    """4 kongs"""

    def testMe(self) ->None:
        self.scoreTest('RB3B3B3C1C1C1 b1b1b1 s3s4s5 wewe LB3B3B3B3', Win(42))
        self.scoreTest(
            'b3B3B3b3 c1C1C1c1 b1b1b1b1 s3s3s3s3 wewe Lwewewe',
            Win(limits=1))
        self.scoreTest(
            'b3B3B3b3 c1C1C1c1 b1b1b1b1 s3s3s3s3 WeWe LWeWeWe',
            Win(limits=1))
        self.scoreTest(
            'b3b3 c1C1C1c1 b1b1b1b1 s3s3s3s3 wewewewe Lb3b3b3',
            Win(limits=1))
        self.scoreTest(
            'b3b3b3b3 c1c1 b1b1b1b1 s3s3s3s3 wewewewe Lc1c1c1',
            Win(limits=1))
        self.scoreTest(
            'b3b3b3b3 RC1 b1b1b1b1 s3s3s3s3 wewewewe', [NoWin(48, 2), NoWin(limits=0.4)])


class PlumBlossom(Base):

    """Gathering the plum blossom from the roof"""

    def testMe(self) ->None:
        self.scoreTest(
            's2s2s2 RS5S5S5B1B1B1B2B2 c9C9C9c9 me LS5S5S5S5',
            Win(limits=1))
        self.scoreTest(
            's2s2s2 RS5S5S5B1B1B1B2B2 c9C9C9c9 me Ls2s2s2s2', [Win(66, 3), Win(66, 1)])
        self.scoreTest(
            's2s2s2 RS5S5S5B1B1B1B2B2 c9C9C9c9 LS5S5S5S5', [Win(68, 2), Win(68, 1)])


class PluckingMoon(Base):

    """plucking the moon from the bottom of the sea"""

    def testMe(self) ->None:
        self.scoreTest(
            's2s2s2 RS1S1S1B1B1B1B2B2 c9C9C9c9 mz LS1S1S1S1',
            Win(limits=1))
        self.scoreTest(
            's2s2s2 RS1S1S1B1B1B1B2B2 c9C9C9c9 mz Ls2s2s2s2', [Win(70, 3), Win(70, 2)])
        self.scoreTest(
            's2s2s2 RS1S1S1B1B1B1B2B2 c9C9C9c9 LS1S1S1S1', [Win(72, 2), Win(72, 1)])


class ScratchingPole(Base):

    """scratch a carrying pole"""

    def testMe(self) ->None:
        self.scoreTest(
            'b2b3b4 RS1S1S1B1B1B1B4B4 c9C9C9c9 mk Lb2b2b3b4',
            Win(limits=1))
        self.scoreTest(
            'b2b2b2 RS1S1S1B1B1B1B4B4 c9C9C9c9 LS1S1S1S1', [Win(72, 2), Win(72, 1)])
        self.scoreTest(
            'b2b2b2 RS1S1S1B1B1B1B4B4 c9C9C9c9 Lb2b2b2b2', [Win(70, 2), Win(70, 1)])


class ThreeGreatScholars(Base):

    """three concealed pungs"""

    def testMe(self) ->None:
        self.scoreTest('dgdgdg RDrDrDrDbDbDb s4s4s4 c5c5', Win(limits=1))
        self.scoreTest(
            'dgdgdg RDrDrDrDbDb s4s4s4 c5c5', [NoWin(16, 3), NoWin(limits=0.4)])
        self.scoreTest(
            'dgdgdg RDrDrDrDbDbDb s4s5s6 c5c5', [Win(limits=1), Win(40, 3)])
        # calling for Three Great Scholars:
        self.scoreTest(
            's2s2 RDgDgDgDbDbDbDrDrDr b2b2b2b2 Ls2s2s2',
            Win(limits=1))
        self.scoreTest(
            'RDgDgDgDbDbDbDrDrDrS2 b2b2b2b2 LDbDbDbDb', [NoWin(32, 6), NoWin(limits=0.4)])
        # 40, 5 is more than 0.4 limits:
        self.scoreTest(
            'RS2DgDgDgDbDbDbDrDrDr wewewewe LDbDbDbDb', [NoWin(40, 8), NoWin(40, 5)])


class ThreeConcealedPungs(Base):

    """three concealed pungs"""

    def testMe(self) ->None:
        self.scoreTest(
            'RB2B2B2S1S1S1B1B1B1B4B4 c9c9c9c9 LB2B2B2B2', [Win(58, 2), Win(58, 1)])
        self.scoreTest(
            'RB2B2B2S1S1S1B4B4 b1b1b1 c9c9c9c9 LB2B2B2B2', Win(54, 1))
        self.scoreTest(
            'RB2B2B2S1S1S1B4B4 b1b1b1 c9c9c9C9 LB2B2B2B2', [Win(54, 2), Win(54, 1)])


class Rest(Base):

    """various tests"""

    def testMe(self) ->None:
        self.scoreTest('s1s1s1s1 s2s2s2 wewe RS3S3S3 s4s4s4 Ls2s2s2s2',
                       [Win(44, 2), Win(44, 1)], myWind=South, roundWind=West)
        self.scoreTest('s1s1s1s1 s2s2s2 RWeWeS3S3S3 s4s4s4 me LS3S3S3S3',
                       [Win(46, 3), Win(46, 1)], myWind=South, roundWind=West)
        self.scoreTest(
            'b3B3B3b3 RDbDbDbDrDrDr wewewewe s2s2 Ls2s2s2', [Win(72, 6), Win(68, 5)])
        self.scoreTest('s1s2s3 s1s2s3 b3b3b3 b4b4b4 RB5 fn yn LB5', [
            NoWin(12, 1), NoWin(12, 2)], myWind=North)
        self.scoreTest(
            'b3b3b3b3 RDbDbDb drdrdr weWeWewe s2s2 Ls2s2s2', [Win(76, 5), Win(72, 5)])
        self.scoreTest('s2s2s2 s2s3s4 RB1B1B1B1 c9C9C9c9 Ls2s2s3s4', NoWin(42))
        self.scoreTest(
            's2s2s2 RDgDgDbDbDbDrDrDr b2b2b2b2 Ls2s2s2s2', [Win(48, 4), Win(48, 3)])
        self.scoreTest(
            's1s1s1s1 s2s2s2 s3s3s3 s4s4s4 s5s5 mw Ls3s3s3s3', Win(42, 4))
        self.scoreTest(
            'RB2C1B2C1B2C1WeWeS4WeS4WeS6 LC1', [NoWin(20, 3), NoWin(20, 2)])
        self.scoreTest('b6b6b6 RB1B1B2B2B3B3B7S7C7B8 LB3', NoWin(2))
        self.scoreTest('RB1B1B1B1B2B3B4B5B6B7B8B9DrDr fe fs fn fw LDrDrDr',
                       [Win(54, 3), NoWin()])
        self.scoreTest('RB1B1B1B2B2B2B5B5B5B7B8B9DrDr fe fs fn fw LDrDrDr',
                       [Win(62, 4), Win(56, 4)])
        self.scoreTest('RB1B1B1B1B2B3B4B5B6B7B8B9DrDr fe fs fn fw me LDrDrDr',
                       [Win(54, 4), NoWin()])
        self.scoreTest('RB1B1B1B1B2B3B4B4B4B7B7B7DrDr fe fs fn fw mz LDrDrDr',
                       [Win(62, 5), Win(56, 5)])
        self.scoreTest('RB1B1B1B1B2B3B4B4B4B7B7B7DrDr fe fs fn fw mZ LDrDrDr',
                       [Win(62, 5), Win(56, 5)])
        self.scoreTest('drdr RB1B1B1B1B2B3B4B5B6B7B8B9 fe fs fn fw mZ Ldrdrdr',
                       [Win(52, 3), NoWin()])
        self.scoreTest(
            'RB1B1B1B1B2B3B4B5B6B7B8B8B2B2 fe fs fn fw LB4',
            NoWin())
        self.scoreTest('RB1B1B1B1B2B3B4B5B6B8B8B2B2 fe fs fn fw LB4',
                       [NoWin(28, 1), NoWin(28, 3)])
        self.scoreTest('wewe wswsws RWnWnWn wwwwwwww b1b1b1 mz Lb1b1b1b1',
                       [Win(54, 6), Win(54, 4)], myWind=North)
        self.scoreTest('wswsws RWeWeWnWnWnB1B1B1 wwwwwwww mz LB1B1B1B1',
                       [Win(60, 6), Win(60, 4)], myWind=North)
        self.scoreTest(
            'RB2B2 b4b4b4 b5b6b7 b7b8b9 c1c1c1 md Lb7b7b8b9', [Win(28), NoWin()])
        self.scoreTest(
            'RB8B8 s4s4s4 b1b2b3 b4b5b6 c1c1c1 md Lb3b1b2b3', [Win(28), NoWin()])
        self.scoreTest(
            'RB2B2 s4s4s4 b1b2b3 b4b5b6 c1c1c1 md Lb3b1b2b3', [Win(26), NoWin()])
        self.scoreTest(
            'RB2B2 s4s4s4 b1b2b3 b4b5b6 c1c1c1 md Lb3b1b2b3', [Win(26), NoWin()])


class TwofoldFortune(Base):

    """Twofold fortune"""

    def testMe(self) ->None:
        self.scoreTest(
            'b1B1B1b1 RB2B3B4B5B6B7 b8b8b8b8 b5b5 fe fs fn fw m.t LB4',
            [Win(limits=1),
             NoWin()])
        self.scoreTest(
            'b1B1B1b1 RB2B3B4B6B6B6 b8b8b8b8 b5b5 fe fs fn fw m.t LB4',
            Win(limits=1))


class OriginalCall(Base):

    """original call"""

    def testMe(self) ->None:
        # in DMJL, b4 would also win:
        self.scoreTest('s1s1s1 s1s2s3 RB6B6B6B8B8B8B5B5 fn yn m.a LB5B5B5',
                       [Win(44, 2), Win(42, 3)], myWind=North)
        self.scoreTest('s1s1s1 s1s2s3 RB6B6B6B8B8B8B5 fn yn m.a LB5',
                       [NoWin(20, 1), NoWin(20, 2)], myWind=North)


class RobbingKong(Base):

    """robbing the kong"""

    def testMe(self) ->None:
        # this hand is only possible if the player declared a hidden chow.
        # is that legal?
        self.scoreTest('s1s2s3 s1s2s3 RB6B6B7B7B8B8B5 fn yn m.a LB5',
                       [NoWin(8, 1), NoWin(8, 2)], myWind=North)
        self.scoreTest('s1s2s3 s2s3s4 RB6B6B7B7B8B8B5B5 fn yn mka Ls1s1s2s3',
                       [Win(28, 4), NoWin()], myWind=North)
        self.scoreTest('s4s5s6 RS1S2S3B6B6B7B7B8B8B5B5 fn yn m.a LS1S1S2S3',
                       [Win(30, 3), NoWin()], myWind=North)
        self.scoreTest('s4s5s6 RS1S2S3B6B6B7B7B8B8 fn yn m.a Ls4s4s5s6',
                       [NoWin(8, 1), NoWin(8, 2)], myWind=North)


class Blessing(Base):

    """blessing of heaven or earth"""

    def testMe(self) ->None:
        self.scoreTest('S4S5S6 RS1S2S3B6B6B7B7B8B8B5B5 fn yn m1',
                       [Win(limits=1), NoWin()])
        self.scoreTest('S4S5S6 RS1S2S3B6B6B7B7B8B8B5B5 fn yn m1',
                       [Win(limits=1), NoWin()])
        self.scoreTest('S4S5S6 RS1S1S1B6B6B6B8B8B8B5B5 fn yn m1',
                       Win(limits=1))
        self.scoreTest('s4s5s6 RS1S2S3B6B6B7B7B8B8 b5b5 fn yn m1 Ls4s4s5s6',
                       [Win(limits=1), NoWin()], myWind=West)


class Terminals(Base):

    """only terminals"""

    def testMe(self) ->None:
        # must disallow chows:
        self.scoreTest(
            'b1b1 c1c2c3 c1c2c3 c1c2c3 c1c2c3 Lb1b1b1', [Win(26, 1), NoWin()])
        self.scoreTest(
            'b1b1 c1c2c3 c9c9c9 s1s1s1 s9s9s9 Lb1b1b1', [Win(38), Win(32)])
        self.scoreTest(
            'b1b1 c1c1c1 c9c9c9 s1s1s1 s9s9s9 Lb1b1b1',
            Win(limits=1))
        self.scoreTest(
            'RB1 c1c1c1 c9c9c9 s1s1s1 s9s9s9',
            [NoWin(16),
             NoWin(limits=0.4)])


class LongHand(Base):

    """long hand"""

    def testMe(self) ->None:
        self.scoreTest('s1s2s3 s1s2s3 b3b3b3 b4b4b4 RB5B6 fn yn LB5', NoWin())
        self.scoreTest('RB2C1B2C1B2C1WeWeS4WeS4WeS6S5 LS5', NoWin())
        self.scoreTest('RB2C1B2C1B2C1WeWeS4WeS4WeS6S5S5 LS5', NoWin())
        self.scoreTest('RB2C1B2C1B2C1WeWeS4WeS4WeS6S5S5 LS5', NoWin())
        self.scoreTest('RWsWsWsWsWnS6C1C1WeWeWeS4S4S5S5 LS5', NoWin())


class MJ(Base):

    """test winner hands.
        Are the hidden melds grouped correctly?"""

    def testMe(self) ->None:
        self.scoreTest(
            'RB1B1B1B2B2B2B3B4 wnwnwn wewewe Lwnwnwnwn', [Win(36, 3), Win(36, 2)])
        self.scoreTest(
            'RB1B1B1B2B2B2B3B3B3S1S1 c3c4c5 Lc3c3c4c5', [Win(36, 1), Win(36)])
        self.scoreTest(
            'RB1B1B1B2B2B2B3B3S1S2S3 c3c4c5 Lc3c3c4c5', [Win(32), NoWin()])
        self.scoreTest(
            'c1C1C1c1 b5B5B5b5 c2C2C2c2 c3C3C3c3 RC4B6 fs fw fn fe LC4',
            NoWin())
        self.scoreTest(
            'wewewe wswsws wnwnwnWn RWwWwWwC6 LC6', [NoWin(32, 4), NoWin(limits=0.4)])
        self.scoreTest('wewewe wswsws wnwnwnWn RWwWwWwC3B6 LC3', NoWin())
        self.scoreTest('wewewe wswsws wnwnwnWn RWwWwWwC3C3 LC3', Win(limits=1))


class LastIsOnlyPossible(Base):

    """tests for determining if this was the only possible last tile"""

    def testMe(self) ->None:
        self.scoreTest(
            's2s3s4 DrDr S1S2S3 S6S7S8 B5B6B7 fw yw fs md Ls2s2s3s4', [Win(34), NoWin(0)])
        self.scoreTest('b3B3B3b3 wewewewe s2s2 RDbDbDbDrDrDr Ls2s2s2',
                       [Win(72, 6), Win(68, 5)], totals=(500, 1000, 4608, 2176))
        self.scoreTest(
            'b3B3B3b3 wewewe RDbDbDbS1S1S1S2S2 LS2S2S2', [Win(60, 5), Win(58, 4)])
        self.scoreTest(
            'b3B3B3b3 wewewe RDbDbDbS1S1S1S3S3 LS3S3S3', [Win(60, 5), Win(58, 4)])
        self.scoreTest(
            'b3B3B3b3 wewewe RDbDbDbS1S1S1S4S4 LS4S4S4', [Win(62, 5), Win(58, 4)])
        self.scoreTest(
            'b3B3B3b3 wewewe RDbDbDbS1S1S1S3S3 LS1S1S1S1', [Win(58, 5), Win(58, 4)])
        self.scoreTest(
            's9s9s9 s8s8s8 RDgDgS1S2S3S3S4S5 LS3 fe', [Win(34, 1), NoWin()])
        self.scoreTest(
            's9s9s9 s8s8s8 RDgDgS1S2S3S4S4S4 LS3 fe', [Win(40, 1), Win(38, 1)])
        self.scoreTest(
            's9s9s9 s8s8s8 RDgDgS1S2S3S4S5S6 LS6 fe', [Win(34, 1), NoWin()])
        self.scoreTest(
            's9s9s9 s8s8s8 RDgDgS1S2S3S7S8S9 LS7 fe', [Win(36, 1), NoWin()])


class TripleKnitting(Base):

    """triple knitting BMJA"""

    def testMe(self) ->None:
        self.scoreTest(
            'RS2B2C2S4B4C4S6B6C6S7B7C7 s8b8 Ls8s8b8',
            [Nothing(),
             Win(limits=0.5)])
        self.scoreTest(
            'RB2C2S4B4C4S6B6C6S7B7C7S8B8 LS8',
            [NoWin(),
             NoWin(limits=0.2)])
        self.scoreTest(
            'RS2B2C2S4B4C4S6B6C6S7B7C7S8 LS8',
            [NoWin(),
             NoWin(limits=0.2)])
        self.scoreTest(
            'RS2B2C2S7B7C7S4B4C4S6B6C6 s8b8 Ls8s8b8',
            [NoWin(),
             Win(limits=0.5)])
        self.scoreTest('RS2B2C2S6B6C6S7B7C7 s4b4c4 s8b8 Ls8s8b8', NoWin())
        self.scoreTest(
            'RS2B2C2S4B4C4S6B6C6S4B4C4 s8c8 Ls8s8c8',
            [NoWin(),
             Win(limits=0.5)])
        self.scoreTest(
            'RS2B2C2S3B3C3S4B4C4S4B4C4 s8c8 Ls8s8c8',
            [NoWin(),
             Win(limits=0.5)])
        self.scoreTest('RB2C2B3C3B4C4S4B4C4 s2s3s4 s8c8 Ls8s8c8', NoWin())
        self.scoreTest('RB5S7B7B3B9S7S6C9C3B7S3 c5c6c7 mw LS3', NoWin())
        self.scoreTest('RC1C2C5C8C9S2S4S9B4B5B6B6B8S1', NoWin())
        self.scoreTest('RC1C2C5C8C9S2S4S9B4B5B6B6B8', NoWin())
        self.scoreTest(
            'RS2B2C2S4B4C4S6B6C6S4B4C4S8',
            [NoWin(),
             NoWin(limits=0.2)])
        self.scoreTest('RS1B1C1S2B2C2S5B5S8B8C8B9C7C9 LB2', NoWin())
        self.callingTest('RS2B2C2S4B4C4S6B6C6S7B7C7S8 LS8', ['', 'b8c8'])
        self.callingTest('RS2B2C2S4B4C4S6B6C6B7C7S8C8 LC7', ['', 's7b8'])


class Knitting(Base):

    """knitting BMJA"""

    def testMe(self) ->None:
        self.scoreTest(
            'RS2B2S3B3S4B4S5B5S6B6S7B7 s9b9 Ls9s9b9',
            [NoWin(),
             Win(limits=0.5)])
        self.scoreTest(
            'RS2B2S3B3B4S5B5S6B6S7B7 S9B9 LS9',
            [NoWin(),
             NoWin(limits=0.2)])
        self.scoreTest('RS2B2S3S5B5B3S4B4S6B6S7B7 s9c9 Ls9s9c9', NoWin())
        self.scoreTest('RS2B3S3B3S4B4S5B5S6B6S7B7 s9b9 Ls9s9b9', NoWin())
        self.scoreTest(
            'RS2B2S2B2S4B4S5B5S6B6S7B7 s9b9 Ls9s9b9',
            [NoWin(),
             Win(limits=0.5)])
        self.scoreTest(
            'RS2S3S4S5S6S7S9B2B3B4B5B6B7B9 LB9',
            [NoWin(),
             Win(limits=0.5)])
        self.scoreTest(
            'RS3S4S5S6S7S9B2B3B4B5B6B7B9 LB9',
            [NoWin(),
             NoWin(limits=0.2)])
        self.scoreTest('RS3S4S9S9B1B1B2B3B4B8B8 s2s2s2 fs mw LS4', NoWin())
        self.scoreTest('RS3S9S9B1B1B2B3B8B8S2S2S2 s4b4 fs mw Ls4', NoWin())
        self.callingTest('RS2B2S3B3S4B4S5B5S6B6S7B7S9 LB7', ['s9', 'b9'])


class AllPairHonors(Base):

    """all pairs honors BMJA"""

    def testMe(self) ->None:
        self.scoreTest(
            'RWeWeS1S1B9B9DgDgDrDrWsWsWwWw LS1S1S1',
            [NoWin(),
             Win(limits=0.5)])
        self.scoreTest(
            'RWeWeS1S1B9B9DgDgDrDrWsWs wwww Lww',
            [NoWin(),
             Win(limits=0.5)])
        self.scoreTest(
            'RWeWeS1S1B9B9DgDgDrDrWsWwWw LS1',
            [NoWin(6),
             NoWin(limits=0.2)],
            myWind=West, roundWind=North)
        self.scoreTest('RWeWeS2S2B9B9DgDgDrDrWsWsWwWw LS2S2S2', NoWin())
        self.scoreTest('RDbDbDgDgDrDrWsWsWnWnS9C1C1C9 LDrDrDr', NoWin())


class BMJA(Base):

    """specials for chinese classical BMJA"""

    def testMe(self) ->None:
        self.scoreTest(
            'RS1S1S5S6S7S8S9WeWsWwWnS2S3S4 LS3S3',
            [NoWin(),
             Win(limits=1)])


class LastTile(Base):

    """will the best last meld be chosen?"""

    def testMe(self) ->None:
        self.scoreTest(
            'wewewe s1s1s1 b9b9b9 RC1C1C1C2C3 LC1C1C1', [Win(38, 2), Win(34, 2)])
        self.scoreTest(
            'wewewe s1s1s1 b9b9b9 RC1C2C3C3C3 LC3C3C3', [Win(38, 2), Win(34, 2)])
        self.scoreTest(
            'b5b6b7 s1s1s1 RB8C6C7C5B8B8C7C7 mw LC7C7C7', [Win(32, 0), NoWin()])


class CallingHands(Base):

    """diverse calling hands"""

    def testMe(self) ->None:
        self.callingTest('s1s1s1s1 b5b6b7 RB1B8C2C2C6C7C8 Lb5', '')
        self.callingTest('WnWn B1 B2 c4c5c6 b6b6b6 b8b8b8 ye yw', ['b3', ''])
        self.callingTest('WnWn B1 B2 dgdgdg b6b6b6 b8b8b8 ye yw', 'b3')
        self.callingTest('s1s1s1s1 b5b6b7 RB8B8C2C2C6C7C8 Lb5', ['b8c2', ''])
        self.callingTest('s1s1s1s1 b5b6b7 RB7B8C2C2C6C7C8 Lb5', ['b6b9', ''])
        self.callingTest('c3c3c3 RDbDbDbS5S6S7S7S8B2B2 LS8', ['s6s9', ''])
        self.callingTest('RC4C4C5C6C5C7C8 dgdgdg s6s6s6', 'c4c5')
        self.callingTest('RS1S4C5C6C5C7C8 dgdgdg s6s6s6', '')
        self.callingTest(
            'RDbDgDrWsWwWeWnB1B9C1S1S9C9 LWe',
            'dbdgdrwewswwwns1s9b1b9c1c9')


class Recursion(Base):

    """recursion in Hand computing should never happen"""

    def testMe(self) ->None:
        self.scoreTest(
            'c6c6c6C6 fe fs RS8S8C1C2C3C4C5C7C8C9 LC6', [NoWin(16), NoWin(16, 1)])
        self.scoreTest(
            'c6c6c6C6 fe fs RS8S8C1C2C3C4C5C7C8C9 LC7', [NoWin(16), NoWin(16, 1)])


class TstProgram(unittest.TestProgram):

    """we want global access to this program so we can check for verbosity in our tests"""

#    def __init__(self, *args: Any, **kwargs:Mapping[Any, Any]) ->None:
    def __init__(self) ->None:
        global PROGRAM  # pylint: disable=global-statement
        PROGRAM = self
        Debug.callers = '8'
#        unittest.TestProgram.__init__(self, exit=False, *args, **kwargs)
        unittest.TestProgram.__init__(self) #, *args, **kwargs)

if __name__ == '__main__':
    # Debug.hand = True
    TstProgram()
