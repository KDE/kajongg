# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

import weakref
from itertools import chain

from message import Message
from common import IntDict, Debug, ReprMixin
from tile import Tile


class AIDefaultAI:

    """all AI code should go in here"""

    groupPrefs = dict(zip(Tile.colors + Tile.honors, (0, 0, 0, 4, 7)))

    # we could solve this by moving those filters into DiscardCandidates
    # but that would make it more complicated to define alternative AIs

    def __init__(self, player):
        self._player = weakref.ref(player)

    @property
    def player(self):
        """hide weakref"""
        return self._player() if self._player else None

    def name(self):
        """return our name"""
        return self.__class__.__name__[2:]

    @staticmethod
    def weighSameColors(unusedAiInstance, candidates):
        """weigh tiles of same group against each other"""
        for candidate in candidates:
            if candidate.group in Tile.colors:
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
        # disable warning about too many branches
        """return exactly one tile for discard.
        Much of this is just trial and success - trying to get as much AI
        as possible with limited computing resources, it stands on
        no theoretical basis"""
        candidates = DiscardCandidates(self.player, hand)
        result = self.weighDiscardCandidates(candidates).best()
        candidates.unlink()
        return result

    def weighDiscardCandidates(self, candidates):
        """the standard"""
        game = self.player.game
        weighRules = game.ruleset.filterRules('weigh')
        for aiFilter in [self.weighBasics, self.weighSameColors,
                         self.weighSpecialGames, self.weighCallingHand,
                         self.weighOriginalCall,
                         self.alternativeFilter] + weighRules:
            if aiFilter in weighRules:
                filterName = aiFilter.__class__.__name__
                aiFilter = aiFilter.weigh
            else:
                filterName = aiFilter.__name__
            if Debug.robotAI:
                prevWeights = ((x.tile, x.keep) for x in candidates)
                candidates = aiFilter(self, candidates)
                newWeights = ((x.tile, x.keep) for x in candidates)
                for oldW, newW in zip(prevWeights, newWeights):
                    if oldW != newW:
                        game.debug('%s: %s: %.3f->%.3f' % (
                            filterName, oldW[0], oldW[1], newW[1]))
            else:
                candidates = aiFilter(self, candidates)
        return candidates

    @staticmethod
    def alternativeFilter(unusedAiInstance, candidates):
        """if the alternative AI only adds tests without changing
        default filters, you can override this one to minimize
        the source size of the alternative AI"""
        return candidates

    @staticmethod
    def weighBasics(aiInstance, candidates):
        """basic things"""
        # pylint: disable=too-many-branches
        # too many branches
        for candidate in candidates:
            keep = candidate.keep
            tile = candidate.tile
            value = tile.value
            if candidate.dangerous:
                keep += 1000
            if candidate.occurrence >= 3:
                keep += 10.04
            elif candidate.occurrence == 2:
                keep += 5.08
            keep += aiInstance.groupPrefs[tile.group]
            if tile.isWind:
                if value == candidates.hand.ownWind:
                    keep += 1.01
                if value == candidates.hand.roundWind:
                    keep += 1.02
            if tile.isTerminal:
                keep += 2.16
            if candidate.maxPossible == 1:
                if tile.isHonor:
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
                if tile.isHonor:
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
    def weighSpecialGames(unusedAiInstance, candidates):
        """like color game, many dragons, many winds"""
        # pylint: disable=too-many-nested-blocks
        for candidate in candidates:
            tile = candidate.tile
            groupCount = candidates.groupCounts[tile.group]
            if tile.isWind:
                if groupCount > 8:
                    candidate.keep += 10.153
            elif tile.isDragon:
                if groupCount > 7:
                    candidate.keep += 15.157
            else:
                # count tiles with a different group:
                if groupCount == 1:
                    candidate.keep -= 2.013
                else:
                    otherGC = sum(candidates.groupCounts[x]
                                  for x in Tile.colors if x != tile.group)
                    if otherGC:
                        if groupCount > 8 or otherGC < 5:
                            # do not go for color game if we already declared
                            # something in another group:
                            if not any(candidates.declaredGroupCounts[x] for x in Tile.colors if x != tile.group):
                                candidate.keep += 20 // otherGC
        return candidates

    @staticmethod
    def weighOriginalCall(aiInstance, candidates):
        """if we declared Original Call, respect it"""
        myself = aiInstance.player
        game = myself.game
        if myself.originalCall and myself.mayWin:
            if Debug.originalCall:
                game.debug('weighOriginalCall: lastTile=%s, candidates=%s' %
                           (myself.lastTile, [str(x) for x in candidates]))
            for candidate in candidates:
                if candidate.tile is myself.lastTile.exposed:
                    winningTiles = myself.originalCallingHand.chancesToWin()
                    if Debug.originalCall:
                        game.debug('weighOriginalCall: winningTiles=%s for %s' %
                                   (winningTiles, str(myself.originalCallingHand)))
                        game.debug('weighOriginalCall respects originalCall: %s with %d' %
                                   (candidate.tile, -99 * len(winningTiles)))
                    candidate.keep -= 99 * len(winningTiles)
        return candidates

    @staticmethod
    def weighCallingHand(aiInstance, candidates):
        """if we can get a calling hand, prefer that"""
        for candidate in candidates:
            newHand = candidates.hand - candidate.tile.concealed
            winningTiles = newHand.chancesToWin()
            if winningTiles:
                for winnerTile in sorted(set(winningTiles)):
                    winnerHand = newHand + winnerTile.concealed
                    if Debug.robotAI:
                        aiInstance.player.game.debug('weighCallingHand %s cand %s winnerTile %s winnerHand %s: %s' % (
                            newHand, candidate, winnerTile, winnerHand, '     '.join(winnerHand.explain())))
                    keep = winnerHand.total() / 10.017
                    candidate.keep -= keep
                    if Debug.robotAI:
                        aiInstance.player.game.debug(
                            'weighCallingHand %s winnerTile %s: discardCandidate %s keep -= %.4f' % (
                                newHand, winnerTile, candidate, keep))
                # more weight if we have several chances to win
                candidate.keep -= float(len(winningTiles)) / len(
                    set(winningTiles)) * 5.031
                if Debug.robotAI:
                    aiInstance.player.game.debug('weighCallingHand %s for %s winningTiles:%s' % (
                        newHand, candidates.hand, winningTiles))
        return candidates

    def selectAnswer(self, answers):
        """this is where the robot AI should go.
        Returns answer and one parameter"""
        # disable warning about too many branches
        answer = parameter = None
        tryAnswers = (
            x for x in [Message.MahJongg, Message.OriginalCall, Message.Kong,
                        Message.Pung, Message.Chow, Message.Discard] if x in answers)
        hand = self.player.hand
        claimness = IntDict()
        discard = self.player.game.lastDiscard
        if discard:
            for rule in self.player.game.ruleset.filterRules('claimness'):
                claimness += rule.claimness(hand, discard)
                if Debug.robotAI:
                    hand.debug(
                        '%s: claimness in selectAnswer:%s' %
                        (rule.name, claimness))
        for tryAnswer in tryAnswers:
            parameter = self.player.sayable[tryAnswer]
            if not parameter:
                continue
            if claimness[tryAnswer] < 0:
                continue
            if tryAnswer in [Message.Discard, Message.OriginalCall]:
                parameter = self.selectDiscard(hand)
            elif tryAnswer == Message.Pung and self.player.maybeDangerous(tryAnswer):
                continue
            elif tryAnswer == Message.Chow:
                parameter = self.selectChow(parameter)
            elif tryAnswer == Message.Kong:
                parameter = self.selectKong(parameter)
            if parameter:
                answer = tryAnswer
                break
        if not answer:
            answer = answers[0]  # for now always return default answer
        return answer, parameter

    def selectChow(self, chows):
        """selects a chow to be completed. Add more AI here."""
        for chow in chows:
            # a robot should never play dangerous
            if not self.player.mustPlayDangerous(chow):
                if not self.player.hasConcealedTiles(chow):
                    # do not dissolve an existing chow
                    belongsToPair = False
                    for tile in chow:
                        if self.player.concealedTiles.count(tile) == 2:
                            belongsToPair = True
                            break
                    if not belongsToPair:
                        return chow
        return None

    def selectKong(self, kongs):
        """selects a kong to be declared. Having more than one undeclared kong is quite improbable"""
        for kong in kongs:
            if not self.player.mustPlayDangerous(kong):
                return kong
        return None

    def handValue(self, hand):
        """compute the value of a hand.
        This is not just its current score but also
        what possibilities to evolve it has. E.g. if
        only one tile is concealed and 3 of it are already
        visible, chances for MJ are 0.
        This will become the central part of AI -
        moves will be done which optimize the hand value.
        For now it is only used by Hand.__split but not
        by the actual discarding code"""
        return hand.total()

# the rest is not yet used: __split only wants something nice for
# display but is not relevant for the real decision making
#        if hand is None:
#            hand = self.player.hand
#        result = 0
#        if hand.won:
#            return 1000 + hand.total()
#        result = hand.total()
#        if hand.callingHands:
#            result += 500 + len(hand.callingHands) * 20
#        for meld in hand.declaredMelds:
#            if not meld.isChow:
#                result += 40
#        garbage = []
#        for meld in (x for x in hand.melds if not x.isDeclared):
#            assert len(meld) < 4, hand
#            if meld.isPung:
#                result += 50
#            elif meld.isChow:
#                result += 30
#            elif meld.isPair:
#                result += 5
#            else:
#                garbage.append(meld)
#        return result


class TileAI(ReprMixin):

    """holds a few AI related tile properties"""
    # pylint: disable=too-many-instance-attributes
    # we do want that many instance attributes

    def __init__(self, candidates, tile):
        self.tile = tile
        self.group, self.value = tile.group, tile.value
        if tile.isReal:
            self.occurrence = candidates.hiddenTiles.count(tile)
            self.available = candidates.player.tileAvailable(
                tile, candidates.hand)
            self.maxPossible = self.available + self.occurrence
            self.dangerous = bool(
                candidates.player.game.dangerousFor(
                    candidates.player,
                    tile))
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

    def __lt__(self, other):
        """for sorting"""
        return self.tile < other.tile

    def __str__(self):
        dang = ' dang:%d' % self.dangerous if self.dangerous else ''
        return '%s:=%.4f%s' % (self.tile, self.keep, dang)


class DiscardCandidates(list):

    """a list of TileAI objects. This class should only hold
    AI neutral methods"""

    def __init__(self, player, hand):
        list.__init__(self)
        self._player = weakref.ref(player)
        self._hand = weakref.ref(hand)
        if Debug.robotAI:
            player.game.debug('DiscardCandidates for hand %s are %s' % (
                hand, hand.tilesInHand))
        self.hiddenTiles = [x.exposed for x in hand.tilesInHand]
        self.groupCounts = IntDict()
                                   # counts for tile groups (sbcdw), exposed
                                   # and concealed
        for tile in self.hiddenTiles:
            self.groupCounts[tile.group] += 1
        self.declaredGroupCounts = IntDict()
        for tile in chain(*hand.declaredMelds):
            self.groupCounts[tile.lowerGroup] += 1
            self.declaredGroupCounts[tile.lowerGroup] += 1
        self.extend(TileAI(self, x) for x in sorted(set(self.hiddenTiles)))
        self.link()

    @property
    def player(self):
        """hide weakref"""
        return self._player() if self._player else None

    @property
    def hand(self):
        """hide weakref"""
        return self._hand() if self._hand else None

    def link(self):
        """define values for candidate.prev and candidate.next"""
        prev = prev2 = None
        for this in self:
            if this.group in Tile.colors:
                thisValue = this.value
                if prev and prev.group == this.group:
                    if prev.value + 1 == thisValue:
                        prev.next = this
                        this.prev = prev
                    if prev.value + 2 == thisValue:
                        prev.next2 = this
                        this.prev2 = prev
                if prev2 and prev2.group == this.group and prev2.value + 2 == thisValue:
                    prev2.next2 = this
                    this.prev2 = prev2
            prev2 = prev
            prev = this
        for this in self:
            if this.group in Tile.colors:
                # we want every tile to have prev/prev2/next/next2
                # the names do not matter, just occurrence, available etc
                thisValue = this.value
                if not this.prev:
                    this.prev = TileAI(self, this.tile.prevForChow)
                if not this.prev2:
                    this.prev2 = TileAI(self, this.prev.tile.prevForChow)
                if not this.next:
                    this.next = TileAI(self, this.tile.nextForChow)
                if not this.next2:
                    this.next2 = TileAI(self, this.next.tile.nextForChow)

    def unlink(self):
        """remove links between elements. This helps garbage collection."""
        for this in self:
            this.prev = None
            this.next = None
            this.prev2 = None
            this.next2 = None

    def best(self):
        """return the candidate with the lowest value"""
        lowest = min(x.keep for x in self)
        candidates = sorted(x for x in self if x.keep == lowest)
        result = self.player.game.randomGenerator.choice(
            candidates).tile.concealed
        if Debug.robotAI:
            self.player.game.debug(
                '%s: discards %s out of %s' %
                (self.player, result, ' '.join(str(x) for x in self)))
        return result
