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

from message import Message
from common import IntDict, Debug
from meld import elementKey

class AIDefault(object):
    """all AI code should go in here"""

    groupPrefs = {'s':0, 'b':0, 'c':0, 'w':4, 'd':7}

    # pylint: disable=R0201
    # we could solve this by moving those filters into DiscardCandidates
    # but that would make it more complicated to define alternative AIs

    def __init__(self, client):
        self.client = client

    def name(self):
        """return our name"""
        return self.__class__.__name__[2:]

    @staticmethod
    def weighSameColors(dummyAiInstance, candidates):
        """weigh tiles of same color against each other"""
        for candidate in candidates:
            if candidate.group in 'sbc':
                if candidate.prev.occurrence:
                    candidate.prev.keep += 1.001
                    candidate.keep += 1.002
                    if candidate.next.occurrence:
                        candidate.prev.keep += 2.001
                        candidate.next.keep += 2.003
                if candidate.next.occurrence:
                    candidate.next.keep += 1.003
                    candidate.keep += 1.002
                elif candidate.next2.occurrence:
                    candidate.keep += 0.502
                    candidate.next2.keep += 0.503
        return candidates

    def selectDiscard(self, hand):
        # pylint: disable=R0912, R0915
        # disable warning about too many branches
        """returns exactly one tile for discard.
        Much of this is just trial and success - trying to get as much AI
        as possible with limited computing resources, it stands on
        no theoretical basis"""
        candidates = DiscardCandidates(self.client.game, hand)
        result = self.weighDiscardCandidates(candidates).best()
        candidates.unlink()
        return result

    def weighDiscardCandidates(self, candidates):
        """the standard"""
        game = self.client.game
        weighFunctions = self.client.game.ruleset.filterFunctions('weigh')
        for aiFilter in [self.weighBasics, self.weighSameColors,
                self.weighSpecialGames, self.weighCallingHand,
                self.weighOriginalCall,
                self.alternativeFilter] + weighFunctions:
            if aiFilter in weighFunctions:
                filterName = aiFilter.__class__.__name__
                aiFilter = aiFilter.weigh
            else:
                filterName = aiFilter.__name__
            if Debug.robotAI:
                prevWeights = list((x.name, x.keep) for x in candidates)
                candidates = aiFilter(self, candidates)
                newWeights = list((x.name, x.keep) for x in candidates)
                for oldW, newW in zip(prevWeights, newWeights):
                    if oldW != newW:
                        game.debug('%s: %s: %.3f->%.3f' % (
                            filterName, oldW[0], oldW[1], newW[1]))
            else:
                candidates = aiFilter(self, candidates)
        return candidates

    @staticmethod
    def alternativeFilter(dummyAiInstance, candidates):
        """if the alternative AI only adds tests without changing
        default filters, you can override this one to minimize
        the source size of the alternative AI"""
        return candidates

    @staticmethod
    def weighBasics(aiInstance, candidates):
        """basic things"""
        # pylint: disable=R0912
        # too many branches
        for candidate in candidates:
            keep = candidate.keep
            group, value = candidate.name
            if candidate.dangerous:
                keep += 1000
            if candidate.occurrence >= 3:
                keep += 10.04
            elif candidate.occurrence == 2:
                keep += 5.08
            keep += aiInstance.groupPrefs[group]
            if group == 'w':
                if value == candidates.hand.ownWind:
                    keep += 1.01
                if value == candidates.hand.roundWind:
                    keep += 1.02
            if value in '19':
                keep += 2.16
            if candidate.maxPossible == 1:
                if group in 'wd':
                    keep -= 8.32
                    # not too much, other players might profit from this tile
                else:
                    if not candidate.next.maxPossible:
                        if not candidate.prev.maxPossible or not candidate.prev2.maxPossible:
                            keep -= 100
                    if not candidate.prev.maxPossible:
                        if not candidate.next.maxPossible or not candidate.next2.maxPossible:
                            keep -= 100
            if candidate.available == 1 and candidate.occurrence == 1:
                if group in 'wd':
                    keep -= 3.64
                else:
                    if not candidate.next.maxPossible:
                        if not candidate.prev.maxPossible or not candidate.prev2.maxPossible:
                            keep -= 3.64
                    if not candidate.prev.maxPossible:
                        if not candidate.next.maxPossible or not candidate.next2.maxPossible:
                            keep -= 3.64
            candidate.keep = keep
        return candidates

    @staticmethod
    def weighSpecialGames(dummyAiInstance, candidates):
        """like color game, many dragons, many winds"""
        for candidate in candidates:
            group = candidate.group
            groupCount = candidates.groupCounts[group]
            if group in 'sbc':
                # count tiles with a different color:
                if groupCount == 1:
                    candidate.keep -= 2.013
                else:
                    otherGC = sum(candidates.groupCounts[x] for x in 'sbc' if x != group)
                    if otherGC:
                        if groupCount > 8 or otherGC < 5:
                            # do not go for color game if we already declared something in another color:
                            if not any(candidates.declaredGroupCounts[x] for x in 'sbc' if x != group):
                                candidate.keep += 20 // otherGC
            elif group == 'w' and groupCount > 8:
                candidate.keep += 10.153
            elif group == 'd' and groupCount > 7:
                candidate.keep += 15.157
        return candidates

    def respectOriginalCall(self):
        """True if we said CaO and can still win without violating it"""
        game = self.client.game
        myself = game.myself
        if not myself.originalCall or not myself.mayWin:
            return False
        result = self.chancesToWin(myself.originalCallingHand)
        if not result:
            myself.mayWin = False # bad luck
        return result

    @staticmethod
    def weighOriginalCall(aiInstance, candidates):
        """if we declared Original Call, respect it"""
        game = aiInstance.client.game
        myself = game.myself
        if myself.originalCall and myself.mayWin:
            if Debug.originalCall:
                game.debug('weighOriginalCall: lastTile=%s, candidates=%s' %
                    (myself.lastTile, [str(x) for x in candidates]))
            for candidate in candidates:
                if candidate.name == myself.lastTile.lower():
                    winningTiles = aiInstance.chancesToWin(myself.originalCallingHand)
                    if Debug.originalCall:
                        game.debug('weighOriginalCall: winningTiles=%s for %s' %
                            (winningTiles, str(myself.originalCallingHand)))
                        game.debug('weighOriginalCall respects originalCall: %s with %d' %
                            (candidate.name, -99 * len(winningTiles)))
                    candidate.keep -= 99 * len(winningTiles)
        return candidates

    @staticmethod
    def weighCallingHand(aiInstance, candidates):
        """if we can get a calling hand, prefer that"""
        for candidate in candidates:
            newHand = candidates.hand - candidate.name.capitalize()
            winningTiles = aiInstance.chancesToWin(newHand)
            for winnerTile in set(winningTiles):
                candidate.keep -= newHand.picking(winnerTile).total() / 10.017
            if winningTiles:
                # more weight if we have several chances to win
                candidate.keep -= float(len(winningTiles)) / len(set(winningTiles)) * 5.031
        return candidates

    def selectAnswer(self, answers):
        """this is where the robot AI should go.
        Returns answer and one parameter"""
        # pylint: disable=R0912
        # disable warning about too many branches
        answer = parameter = None
        tryAnswers = (x for x in [Message.MahJongg, Message.OriginalCall, Message.Kong,
            Message.Pung, Message.Chow, Message.Discard] if x in answers)
        hand = self.client.game.myself.hand
        claimness = IntDict()
        discard = self.client.game.lastDiscard
        if discard:
            for func in self.client.game.ruleset.filterFunctions('claimness'):
                claimness += func.claimness(hand, discard.element)
        for tryAnswer in tryAnswers:
            parameter = self.client.sayable[tryAnswer]
            if not parameter:
                continue
            if claimness[tryAnswer] < 0:
                if Debug.robotAI:
                    hand.debug('claimness %d inhibits %s %s' % (claimness[tryAnswer], tryAnswer, parameter))
                continue
            if tryAnswer in [Message.Discard, Message.OriginalCall]:
                parameter = self.selectDiscard(hand)
            elif tryAnswer in [Message.Pung, Message.Chow, Message.Kong] and self.respectOriginalCall():
                continue
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
        for completedHand in hand.callingHands(99):
            result.extend([completedHand.lastTile] * (
                    self.client.game.myself.tileAvailable(completedHand.lastTile, hand)))
        return result

    def xxxxhandValue(self):
        """UNUSED CODE!
        compute the value of a hand.
        This is not just its current score but also
        what possibilities to evolve it has. E.g. if
        only one tile is concealed and 3 of it are already
        visible, chances for MJ are 0.
        This will become the central part of AI -
        moves will be done which optimize the hand value"""
        game = self.client.game
        hand = game.myself.hand
        assert not hand.handlenOffset(), hand
        result = 0
        if hand.won:
            return 1000
        result = hand.total()
        completedHands = hand.callingHands(99)
        if completedHands:
            result += 500 + len(completedHands) * 20
        for meld in hand.declaredMelds:
            if not meld.isChow():
                result += 40
        garbage = []
        for meld in []: # hand.hiddenMelds does not exist anymore
            assert len(meld) < 4, hand
            if meld.isPung():
                result += 50
            elif meld.isChow():
                result += 30
            elif meld.isPair():
                result += 5
            else:
                garbage.append(meld)
        return result

class TileAI(object):
    """holds a few AI related tile properties"""
    # pylint: disable=R0902
    # we do want that many instance attributes
    def __init__(self, candidates, name):
        self.name = name
        self.group, self.value = name[:2]
        if self.value in '123456789bgreswn' and len(name) == 2:
            self.occurrence = candidates.hiddenTiles.count(name)
            self.available = candidates.game.myself.tileAvailable(name, candidates.hand)
            self.maxPossible = self.available + self.occurrence
            self.dangerous = bool(candidates.game.dangerousFor(candidates.game.myself, name))
        else:
            # value might be -1, 0, 10, 11 for suits
            self.occurrence = 0
            self.available = 0
            self.maxPossible = 0
            self.dangerous = False
        self.keep = 0.0
        self.prev = None
        self.next = None
        self.prev2 = None
        self.next2 = None

    def __str__(self):
        dang = ' dang:%d' % self.dangerous if self.dangerous else ''
        return '%s:=%s%s' % (self.name, self.keep, dang)

class DiscardCandidates(list):
    """a list of TileAI objects. This class should only hold
    AI neutral methods"""
    def __init__(self, game, hand):
        list.__init__(self)
        self.game = game
        self.hand = hand
        self.hiddenTiles = list(x.lower() for x in hand.tileNamesInHand)
        self.groupCounts = IntDict() # counts for tile groups (sbcdw), exposed and concealed
        for tile in self.hiddenTiles:
            self.groupCounts[tile[0]] += 1
        self.declaredGroupCounts = IntDict()
        for tile in sum((x.pairs.lower() for x in hand.declaredMelds), []):
            self.groupCounts[tile[0]] += 1
            self.declaredGroupCounts[tile[0]] += 1
        self.extend(list(TileAI(self, x) for x in sorted(set(self.hiddenTiles), key=elementKey)))
        self.link()

    def link(self):
        """define values for candidate.prev and candidate.next"""
        prev = prev2 = None
        for this in self:
            if this.group in 'sbc':
                thisValue = this.value
                if prev and prev.group == this.group:
                    if int(prev.value) + 1 == int(thisValue):
                        prev.next = this
                        this.prev = prev
                    if int(prev.value) + 2 == int(thisValue):
                        prev.next2 = this
                        this.prev2 = prev
                if prev2 and prev2.group == this.group and int(prev2.value) + 2 == int(thisValue):
                    prev2.next2 = this
                    this.prev2 = prev2
            prev2 = prev
            prev = this
        for this in self:
            if this.group in 'sbc':
                # we want every tile to have prev/prev2/next/next2
                # the names do not matter, just occurrence, available etc
                thisValue = this.value
                if not this.prev:
                    this.prev = TileAI(self, this.group +  str(int(thisValue)-1))
                if not this.prev2:
                    this.prev2 = TileAI(self, this.group +  str(int(thisValue)-2))
                if not this.next:
                    this.next = TileAI(self, this.group +  str(int(thisValue)+1))
                if not this.next2:
                    this.next2 = TileAI(self, this.group +  str(int(thisValue)+2))

    def unlink(self):
        """remove links between elements. This helps garbage collection."""
        for this in self:
            this.prev = None
            this.next = None
            this.prev2 = None
            this.next2 = None

    def best(self):
        """returns the candidate with the lowest value"""
        lowest = min(x.keep for x in self)
        candidates = sorted(list(x for x in self if x.keep == lowest), key=lambda x: x.name)
        result = self.game.randomGenerator.choice(candidates).name.capitalize()
        if Debug.robotAI:
            self.game.debug('%s: discards %s out of %s' % (self.game.myself, result, ' '.join(str(x) for x in self)))
        return result
