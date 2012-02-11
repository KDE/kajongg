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

    def name(self):
        """return our name"""
        return self.__class__.__name__[2:]

    @staticmethod
    def _weighSameColors(candidates):
        """weigh tiles of same color against each other"""
        for candidate in candidates:
            if candidate.prev:
                candidate.prev.keep += 1
                candidate.keep += 1
                if candidate.next:
                    candidate.prev.keep += 2
                    candidate.next.keep += 2
            if candidate.next:
                candidate.next.keep += 1
                candidate.keep += 1
            elif candidate.next2: # TODO: test with if instead of elif
                candidate.keep += 0.5
                candidate.next2.keep += 0.5

    def selectDiscard(self):
        # pylint: disable=R0912, R0915
        # disable warning about too many branches
        """returns exactly one tile for discard.
        Much of this is just trial and success - trying to get as much AI
        as possible with limited computing resources, it stands on
        no theoretical basis"""
        hand = self.client.game.myself.computeHandContent()
        groupCounts = IntDict() # counts for tile groups (sbcdw), exposed and concealed
        candidates = Candidates(self.client.game, hand)
        for tile in candidates.hiddenTiles:
            groupCounts[tile[0]] += 1
        declaredGroupCounts = IntDict()
        for tile in sum((x.pairs.lower() for x in hand.declaredMelds), []):
            groupCounts[tile[0]] += 1
            declaredGroupCounts[tile[0]] += 1
        for candidate in candidates:
            keep = candidate.keep
            group, value = candidate.name
            if candidate.dangerous:
                keep += 1000
            if candidate.occurrence >= 3:
                keep += 10
            elif candidate.occurrence == 2:
                keep += 5
            keep += self.groupPrefs[group]
            if group == 'w':
                if value == hand.ownWind:
                    keep += 1
                if value == hand.roundWind:
                    keep += 1
            if value in '19':
                keep += 2
            if self.client.game.visibleTiles[candidate.name] == 3:
                keep -= 10 # TODO: this would even resolve a hidden chow
            elif self.client.game.visibleTiles[candidate.name] == 2:
                keep -= 5
            candidate.keep = keep
        self._weighSameColors(candidates)
        for candidate in candidates:
            group = candidate.name[0]
            groupCount = groupCounts[group]
            if group in 'sbc':
                # count tiles with a different color:
                if groupCount == 1:
                    candidate.keep -= 2
                else:
                    otherGC = sum(groupCounts[x] for x in 'sbc' if x != group)
                    if otherGC:
                        if groupCount > 8 or otherGC < 5:
                            # do not go for color game if we already declared something in another color:
                            if not any(declaredGroupCounts[x] for x in 'sbc' if x != group):
                                candidate.keep += 20 // otherGC
            elif group == 'w' and groupCount > 8:
                candidate.keep += 10
            elif group == 'd' and groupCount > 7:
                candidate.keep += 15
        self.weighCallingHand(hand, candidates)
        return candidates.best()

    def weighCallingHand(self, hand, candidates):
        """if we can get a calling hand, prefer that"""
        for candidate in candidates:
            newHand = hand - candidate.name.capitalize()
            winningTiles = self.chancesToWin(newHand)
            for winnerTile in set(winningTiles):
                string = newHand.string.replace(' m', ' M')
                mjHand = HandContent.cached(newHand.ruleset, string, newHand.computedRules, plusTile=winnerTile)
                candidate.keep -= mjHand.total() / 10
            # more weight if we have several chances to win
            if winningTiles:
                candidate.keep -= float(len(winningTiles)) / len(set(winningTiles)) * 5

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

    def chancesToWin(self, hand):
        """count the physical tiles that make us win and still seem availabe"""
        result = []
        for tileName in hand.isCalling(99):
            result.extend([tileName] * (self.client.game.myself.tileAvailable(tileName, hand)))
        return result


class TileAI(object):
    """holds a few AI related tile properties"""
    # pylint: disable=R0902
    # we do want that many instance attributes
    def __init__(self, name):
        self.name = name
        self.occurrence = 0
        self.dangerous = False
        self.keep = 0
        self.available = 0
        self.group, self.value = name
        self.prev = None
        self.next = None
        self.prev2 = None
        self.next2 = None


    def __str__(self):
        dang = ' dang:%d' % self.dangerous if self.dangerous else ''
        return '%s:=%s%s' % (self.name, self.keep, dang)

class Candidates(list):
    """a list of TileAI objects. This class should only hold
    AI neutral methods"""
    def __init__(self, game, hand):
        list.__init__(self)
        self.game = game
        self.hand = hand
        self.hiddenTiles = sum((x.pairs.lower() for x in hand.hiddenMelds), [])
        self.extend(list(TileAI(x) for x in sorted(set(self.hiddenTiles), key=elementKey)))
        for candidate in self:
            candidate.occurrence = self.hiddenTiles.count(candidate.name)
            candidate.dangerous = bool(self.game.dangerousFor(self.game.myself, candidate.name))
        self.link()

    def link(self):
        """define values for candidate.prev and candidate.next"""
        prev = prev2 = None
        for this in self:
            if this.group in 'sbc':
                if prev and prev.group == this.group:
                    if int(prev.value) + 1 == int(this.value):
                        prev.next = this
                        this.prev = prev
                    if int(prev.value) + 2 == int(this.value):
                        prev.next2 = this
                        this.prev2 = prev
                if prev2 and prev2.group == this.group and int(prev2.value) + 2 == int(this.value):
                    prev2.next2 = this
                    this.prev2 = prev2
            prev2 = prev
            prev = this

    def best(self):
        """returns the candidate with the lowest value"""
        if Debug.robotAI:
            logDebug('%s: %s' % (self.game.myself, ' '.join(str(x) for x in self)))
        lowest = min(x.keep for x in self)
        candidates = sorted(list(x for x in self if x.keep == lowest), key=lambda x: x.name)
        return candidates[0].name.capitalize()

INTELLIGENCES = {'Default': AIDefault}
