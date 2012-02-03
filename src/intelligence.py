# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from itertools import chain

from util import logDebug
from message import Message
from common import IntDict, Debug
from scoringengine import HandContent
from meld import elementKey

class AIDefault:
    """all AI code should go in here"""

    groupPrefs = {'s':0, 'b':0, 'c':0, 'w':4, 'd':7}


    def __init__(self, client):
        self.client = client

    @staticmethod
    def runningWindow(lst, windowSize):
        """generates moving sublists for each item. The item is always in the middle of the
        sublist or - for even lengths - one to the left."""
        if windowSize % 2:
            pre = windowSize / 2
        else:
            pre = windowSize / 2 - 1
        full = list(chain([None] * pre, lst, [None] * (windowSize - pre - 1)))
        for idx in range(len(lst)):
            yield full[idx:idx+windowSize]

    def _weighSameColors(self, candidates):
        """weigh tiles of same color against each other"""
        for color in 'sbc':
            colorCandidates = list(x for x in candidates if x.name[0] == color)
            if len(colorCandidates) == 4:
                # special case: do we have 4 consecutive singles?
                values = list(set(int(x.name[1]) for x in colorCandidates))
                if len(values) == 4 and values[0] + 3 == values[3]:
                    colorCandidates[0].preference -= 5
                    for candidate in colorCandidates[1:]:
                        candidate.preference += 5
                    break
            for prevCandidate, candidate, nextCandidate in self.runningWindow(colorCandidates, 3):
                value = int(candidate.name[1])
                prevValue = int(prevCandidate.name[1]) if prevCandidate else -99
                nextValue = int(nextCandidate.name[1]) if nextCandidate else 99
                if value == prevValue + 1:
                    prevCandidate.preference += 1
                    candidate.preference += 1
                    if value == nextValue - 1:
                        prevCandidate.preference += 2
                        nextCandidate.preference += 2
                if value == nextValue - 1:
                    nextCandidate.preference += 1
                    candidate.preference += 1
                if value == nextValue - 2:
                    nextCandidate.preference += 0.5
                    candidate.preference += 0.5

    def selectDiscard(self):
        # pylint: disable=R0912, R0915
        # disable warning about too many branches
        """returns exactly one tile for discard.
        Much of this is just trial and success - trying to get as much AI
        as possible with limited computing resources, it stands on
        no theoretical basis"""
        hand = self.client.game.myself.computeHandContent()
        groupCounts = IntDict() # counts for tile groups (sbcdw), exposed and concealed
        hiddenTiles = sum((x.pairs.lower() for x in hand.hiddenMelds), [])
        for tile in hiddenTiles:
            groupCounts[tile[0]] += 1
        candidates = list(TileAI(x) for x in sorted(set(hiddenTiles), key=elementKey))
        declaredGroupCounts = IntDict()
        for tile in sum((x.pairs.lower() for x in hand.declaredMelds), []):
            groupCounts[tile[0]] += 1
            declaredGroupCounts[tile[0]] += 1
        for candidate in candidates:
            preference = candidate.preference
            group, value = candidate.name
            candidate.occurrence = hiddenTiles.count(candidate.name)
            candidate.dangerous = bool(self.client.game.dangerousFor(self.client.game.myself, candidate.name))
            if candidate.dangerous:
                preference += 1000
            if candidate.occurrence >= 3:
                preference += 10
            elif candidate.occurrence == 2:
                preference += 5
            preference += self.groupPrefs[group]
            if group == 'w':
                if value == hand.ownWind:
                    preference += 1
                if value == hand.roundWind:
                    preference += 1
            if value in '19':
                preference += 2
            if self.client.game.visibleTiles[candidate.name] == 3:
                preference -= 10
            elif self.client.game.visibleTiles[candidate.name] == 2:
                preference -= 5
            candidate.preference = preference
        self._weighSameColors(candidates)
        for candidate in candidates:
            group = candidate.name[0]
            groupCount = groupCounts[group]
            if group in 'sbc':
                # count tiles with a different color:
                if groupCount == 1:
                    candidate.preference -= 2
                else:
                    otherGC = sum(groupCounts[x] for x in 'sbc' if x != group)
                    if otherGC:
                        if groupCount > 8 or otherGC < 5:
                            # do not go for color game if we already declared something in another color:
                            if not any(declaredGroupCounts[x] for x in 'sbc' if x != group):
                                candidate.preference += 20 // otherGC
            elif group == 'w' and groupCount > 8:
                candidate.preference += 10
            elif group == 'd' and groupCount > 7:
                candidate.preference += 15
        self.weighCallingHand(hand, candidates)
        candidates = sorted(candidates, key=lambda x: x.preference)
        if Debug.robotAI:
            logDebug('%s: %s' % (self.client.game.myself, ' '.join(str(x) for x in candidates)))
        # return tile with lowest preference:
        return candidates[0].name.capitalize()

    @staticmethod
    def weighCallingHand(hand, candidates):
        """if we can get a calling hand, prefer that"""
        for candidate in candidates:
            newHand = hand - candidate.name.capitalize()
            for winnerTile in newHand.isCalling(99):
                string = newHand.string.replace(' m', ' M')
                mjHand = HandContent.cached(newHand.ruleset, string, newHand.computedRules, plusTile=winnerTile)
                candidate.preference -= mjHand.total() / 10

    def selectAnswer(self, answers):
        """this is where the robot AI should go.
        Returns answer and one parameter"""
        answer = parameter = None
        tryAnswers = (x for x in [Message.MahJongg, Message.Kong,
            Message.Pung, Message.Chow, Message.Discard] if x in answers)
        for tryAnswer in tryAnswers:
            parameter = self.client.sayable[tryAnswer]
            if not parameter:
                continue
            if tryAnswer == Message.Discard:
                parameter = self.selectDiscard()
            elif tryAnswer == Message.Pung and self.client.maybeDangerous(tryAnswer):
                continue
            elif tryAnswer == Message.Chow:
                parameter = self.selectChow(parameter)
            elif tryAnswer == Message.Kong:
                parameter = self.selectKong(parameter)
            if parameter:
                answer = tryAnswer
                break
        if not answer:
            answer = answers[0] # for now always return default answer
        return answer, parameter

    def selectChow(self, chows):
        """selects a chow to be completed. Add more AI here."""
        game = self.client.game
        myself = game.myself
        for chow in chows:
            # a robot should never play dangerous
            if not myself.mustPlayDangerous(chow):
                if not myself.hasConcealedTiles(chow):
                    # do not dissolve an existing chow
                    belongsToPair = False
                    for tileName in chow:
                        if myself.concealedTileNames.count(tileName) == 2:
                            belongsToPair = True
                            break
                    if not belongsToPair:
                        return chow

    def selectKong(self, kongs):
        """selects a kong to be declared. Having more than one undeclared kong is quite improbable"""
        for kong in kongs:
            if not self.client.game.myself.mustPlayDangerous(kong):
                return kong


class TileAI(object):
    """holds a few AI related tile properties"""
    def __init__(self, name):
        self.name = name
        self.occurrence = 0
        self.dangerous = False
        self.preference = 0

    def __str__(self):
        dang = ' dang:%d' % self.dangerous if self.dangerous else ''
        return '%s:=%d%s' % (self.name, self.preference, dang)

INTELLIGENCES = {'Default': AIDefault}
