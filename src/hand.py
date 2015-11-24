# -*- coding: utf-8 -*-

"""Copyright (C) 2009-2014 Wolfgang Rohdewald <wolfgang@rohdewald.de>

Kajongg is free software you can redistribute it and/or modify
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



Read the user manual for a description of the interface to this scoring engine
"""

from itertools import chain
import weakref

from log import dbgIndent, fmt
from tile import Tile, TileList
from meld import Meld, MeldList
from rule import Score, UsedRule
from common import Debug
from intelligence import AIDefault
from util import callers
from message import Message


class Hand(object):

    """represent the hand to be evaluated.

    lenOffset is
      <0 for a short hand
      0 for a correct calling hand
      1 for a correct winner hand or a long loser hand
      >1 for a long winner hand
    Of course ignoring bonus tiles and respecting kong replacement tiles.
    if there are no kongs, 13 tiles will return 0

    We assume that long hands never happen. For manual scoring, this should
    be asserted by the caller after creating the Hand instance. If the Hand
    has lenOffset 1 but is no winning hand, the Hand instance will not be
    fully evaluated, it is given Score 0 and hand.won == False.

    declaredMelds are those which cannot be changed anymore: Chows, Pungs,
    Kongs.

    tilesInHand are those not in declaredMelds

    Only tiles passed in the 'R' substring may be rearranged.

    mjRule is the one out of mjRules with the highest resulting score. Every
    hand gets an mjRule even it is not a wining hand, it is the one which
    was used for rearranging the hiden tiles to melds."""
    # pylint: disable=too-many-instance-attributes

    class __NotWon(UserWarning):  # pylint: disable=invalid-name

        """should be won but is not a winning hand"""

    def __new__(cls, player, string, prevHand=None):
        # pylint: disable=unused-argument
        """since a Hand instance is never changed, we can use a cache"""
        cache = player.handCache
        cacheKey = string
        if cacheKey in cache:
            result = cache[cacheKey]
            player.cacheHits += 1
            if Debug.hand:
                result._player = (  # pylint: disable=protected-access
                    weakref.ref(player))
                result.debug(
                    fmt(
                        '{callers}: cached Hand({id(result)} {string}) '
                        '{result.lenOffset} {id(prevHand)}',
                        callers=callers(10, exclude=['__init__'])))
            return result
        player.cacheMisses += 1
        result = object.__new__(cls)
        cache[cacheKey] = result
        return result

    def __init__(self, player, string, prevHand=None):
        """evaluate string for player. rules are to be applied in any case"""
        # silence pylint. This method is time critical, so do not split it
        # into smaller methods
        # pylint: disable=too-many-instance-attributes,too-many-branches
        # pylint: disable=too-many-statements
        if hasattr(self, 'string'):
            # I am from cache
            return
        self._player = weakref.ref(player)
        self.indent = prevHand.indent + 1 if prevHand else 0

        # two shortcuts for speed:
        self.ruleset = self.player.game.ruleset
        if self.player:
            self.intelligence = self.player.intelligence
        else:
            self.intelligence = AIDefault()
        self.string = string
        self.__robbedTile = Tile.unknown
        self.prevHand = prevHand
        self.__won = None
        self.__score = None
        self.__callingHands = None
        self.mjStr = ''
        self.__mjRule = None
        self.ruleCache = {}
        tileStrings = []
        for part in self.string.split():
            partId = part[0]
            if partId == 'm':
                self.mjStr += ' ' + part
            elif partId == 'L':
                if len(part[1:]) > 8:
                    raise Exception(
                        'last tile cannot complete a kang:' + self.string)
                self.mjStr += ' ' + part
            else:
                if part != 'R':
                    tileStrings.append(part)

        self.__lastTile = self.__lastSource = self.__announcements = ''
        self.__lastMeld = 0
        self.__lastMelds = MeldList()
        self.melds = MeldList()
        self.bonusMelds, tileStrings = self.__separateBonusMelds(tileStrings)
        tileString = ' '.join(tileStrings)
        self.tiles = TileList(tileString.replace(' ', '').replace('R', ''))
        self.tiles.sort()
        self.values = tuple(x.value for x in self.tiles)
        self.suits = set(x.lowerGroup for x in self.tiles)
        for part in tileStrings[:]:
            if part[:1] != 'R':
                self.melds.append(Meld(part))
                tileStrings.remove(part)
        # those must be set before splitting the rest because the rearrange()
        # functions need them
        self.declaredMelds = MeldList(x for x in self.melds if x.isDeclared)
        declaredTiles = list(sum((x for x in self.declaredMelds), []))
        self.tilesInHand = TileList(x for x in self.tiles
                                    if x not in declaredTiles)
        self.lenOffset = (len(self.tiles) - 13
                          - sum(x.isKong for x in self.melds))

        assert len(tileStrings) < 2, tileStrings
        self.__rest = TileList()
        if len(tileStrings):
            self.__rest.extend(TileList(tileStrings[0][1:]))
        self.usedRules = None
        if Debug.hand:
            self.debug(fmt(
                '{callers}: new Hand({id(self)} {string} '
                '{self.lenOffset} {id(prevHand)})',
                callers=callers(10, exclude=['__init__'])))
        self.__arranged = None
        self.__won = self.lenOffset == 1 and self.player.mayWin
        try:
            self.__arrange()
            self.__calculate()
            self.__arranged = True
        except Hand.__NotWon:
            self.__won = False
            self.__score = Score()
        finally:
            if Debug.hand:
                self.debug(fmt(
                    'Fixing Hand({id(self)}, {string}, '
                    '{self.won}, {self.score}'))
            self._fixed = True

    @property
    def arranged(self):
        """readonly"""
        return self.__arranged

    @property
    def player(self):
        """weakref"""
        return self._player()

    @property
    def ownWind(self):
        """for easier usage"""
        return self.player.wind.lower()

    @property
    def roundWind(self):
        """for easier usage"""
        return self.player.game.roundWind

    def __calculate(self):
        """apply rules, calculate score"""
        assert not self.__rest, (
            'Hand.__calculate expects there to be no rest tiles: %s' % self)
        oldWon = self.__won
        self.__applyRules()
        if len(self.lastMelds) > 1:
            self.__applyBestLastMeld()
        if self.__won != oldWon:
            # if not won after all, this might be a long hand.
            # So we might even have to unapply meld rules and
            # bonus points. Instead just recompute all again.
            # This should only happen with scoring manual games
            # and with scoringtest - normally kajongg would not
            # let you declare an invalid mah jongg
            self.__applyRules()

    def hasTiles(self):
        """tiles are assigned to this hand"""
        return self.tiles or self.bonusMelds

    @property
    def mjRule(self):
        """getter"""
        return self.__mjRule

    @mjRule.setter
    def mjRule(self, value):
        """changing mjRule must reset score"""
        if self.__mjRule != value:
            self.__mjRule = value
            self.__score = None

    @property
    def lastTile(self):
        """compute and cache, readonly"""
        if self.__lastTile == '':
            self.__setLastTile()
        return self.__lastTile

    @property
    def lastSource(self):
        """compute and cache, readonly"""
        if self.__lastTile == '':
            self.__setLastTile()
        return self.__lastSource

    @property
    def announcements(self):
        """compute and cache, readonly"""
        if self.__lastTile == '':
            self.__setLastTile()
        return self.__announcements

    @property
    def score(self):
        """calculate it first if not yet done"""
        if self.__score is None and self.__arranged is not None:
            self.__score = Score()
            self.__calculate()
        return self.__score

    @property
    def lastMeld(self):
        """compute and cache, readonly"""
        if self.__lastMeld == 0:
            self.__setLastMeld()
        return self.__lastMeld

    @property
    def lastMelds(self):
        """compute and cache, readonly"""
        if self.__lastMeld == 0:
            self.__setLastMeld()
        return self.__lastMelds

    @property
    def won(self):
        """do we really have a winner hand?"""
        return self.__won

    def debug(self, msg):
        """try to use Game.debug so we get a nice prefix"""
        self.player.game.debug(dbgIndent(self, self.prevHand) + msg)

    def __applyRules(self):
        """find out which rules apply, collect in self.usedRules"""
        self.usedRules = []
        for meld in chain(self.melds, self.bonusMelds):
            self.usedRules.extend(UsedRule(x, meld) for x in meld.rules(self))
        for rule in self.ruleset.handRules:
            if rule.appliesToHand(self):
                self.usedRules.append(UsedRule(rule))

        self.__score = self.__totalScore()

        self.ruleCache.clear()
        # do the rest only if we know all tiles of the hand
        if Tile.unknown in self.string:
            return
        if self.__won:
            matchingMJRules = self.__maybeMahjongg()
            if not matchingMJRules:
                if Debug.hand:
                    self.debug(fmt(
                        'no matching MJ Rule for {id(self)} {self}'))
                self.__score = Score()
                raise Hand.__NotWon
            self.__mjRule = matchingMJRules[0]
            self.usedRules.append(UsedRule(self.__mjRule))
            self.usedRules.extend(self.matchingWinnerRules())
            self.__score = self.__totalScore()
        else:  # not self.won
            loserRules = self.__matchingRules(self.ruleset.loserRules)
            if loserRules:
                self.usedRules.extend(list(UsedRule(x) for x in loserRules))
                self.__score = self.__totalScore()
        self.__checkHasExclusiveRules()

    def matchingWinnerRules(self):
        """returns a list of matching winner rules"""
        matching = list(
            UsedRule(x)
            for x in self.__matchingRules(self.ruleset.winnerRules))
        limitRule = self.maxLimitRule(matching)
        return [limitRule] if limitRule else matching

    def __checkHasExclusiveRules(self):
        """if we have one, remove all others"""
        exclusive = list(x for x in self.usedRules
                         if 'absolute' in x.rule.options)
        if exclusive:
            self.usedRules = exclusive
            self.__score = self.__totalScore()
            if self.__won and not bool(self.__maybeMahjongg()):
                if Debug.hand:
                    self.debug(fmt(
                        'exclusive rule {exclusive} does not win: {self}'))
                raise Hand.__NotWon

    def __setLastTile(self):
        """sets lastTile, lastSource, announcements"""
        self.__announcements = ''
        self.__lastTile = None
        # not '' because we want to cache the result, see lastTile property
        self.__lastSource = None
        parts = self.mjStr.split()
        for part in parts:
            if part[0] == 'L':
                part = part[1:]
                if len(part) > 2:
                    self.__lastMeld = Meld(part[2:])
                self.__lastTile = Tile(part[:2])
            elif part[0] == 'm':
                if len(part) > 1:
                    self.__lastSource = part[1]
                    if len(part) > 2:
                        self.__announcements = part[2]
        if self.__lastTile:
            assert self.__lastTile.isBonus or self.__lastTile in self.tiles, \
                'lastTile %s is not in hand %s, mjStr=%s' % (
                    self.__lastTile, self.string, self.mjStr)
            if self.__lastSource == 'k':
                assert self.tiles.count(self.__lastTile.exposed) + \
                    self.tiles.count(self.__lastTile.concealed) == 1, (
                        'Robbing kong: I cannot have '
                        'lastTile %s more than once in %s' % (
                            self.__lastTile, ' '.join(self.tiles)))

    def __setLastMeld(self):
        """sets the shortest possible last meld. This is
        not yet the final choice, see __applyBestLastMeld"""
        self.__lastMeld = None
        if self.lastTile and self.__won:
            if self.mjRule:
                self.__lastMelds = self.mjRule.computeLastMelds(self)
                if self.__lastMelds:
                    # syncHandBoard may return nothing
                    if len(self.__lastMelds) == 1:
                        self.__lastMeld = self.__lastMelds[0]
                    else:
                        totals = sorted(
                            (len(x), idx)
                            for idx, x in enumerate(self.__lastMelds))
                        self.__lastMeld = self.__lastMelds[totals[0][1]]
            if not self.__lastMeld:
                self.__lastMeld = self.lastTile.single
                self.__lastMelds = MeldList(self.__lastMeld)

    def __applyBestLastMeld(self):
        """select the last meld giving the highest score
        (only winning variants)"""
        assert len(self.lastMelds) > 1
        totals = []
        prev = self.lastMeld
        for rule in self.usedRules:
            assert isinstance(rule, UsedRule)
        for lastMeld in self.lastMelds:
            self.__lastMeld = lastMeld
            try:
                self.__applyRules()
                totals.append((self.__totalScore().total(), lastMeld))
            except Hand.__NotWon:
                pass
        if totals:
            totals = sorted(totals)  # sort by totalScore
            maxScore = totals[-1][0]
            totals = list(x[1] for x in totals if x[0] == maxScore)
            # now we have a list of only lastMelds reaching maximum score
            if prev not in totals or self.__lastMeld not in totals:
                if Debug.explain and prev not in totals:
                    if not self.player.game.belongsToRobotPlayer():
                        self.debug(fmt(
                            'replaced last meld {prev} with {totals[0]}'))
                self.__lastMeld = totals[0]
                self.__applyRules()

    def chancesToWin(self):
        """count the physical tiles that make us win and still seem availabe"""
        assert self.lenOffset == 0
        result = []
        for completedHand in self.callingHands:
            result.extend(
                [completedHand.lastTile] *
                (self.player.tileAvailable(completedHand.lastTile, self)))
        return result

    def __add__(self, addTile):
        """returns a new Hand built from this one plus addTile"""
        assert addTile.isConcealed, 'addTile %s should be concealed:' % addTile
        # combine all parts about hidden tiles plus the new one to one part
        # because something like DrDrS8S9 plus S7 will have to be reordered
        # anyway
        parts = [str(self.declaredMelds)]
        parts.extend(str(x[0]) for x in self.bonusMelds)
        parts.append('R' + ''.join(str(x) for x in sorted(
            self.tilesInHand + [addTile])))
        if self.announcements:
            parts.append('m' + self.announcements)
        parts.append('L' + addTile)
        return Hand(self.player, ' '.join(parts).strip(), prevHand=self)

    def __sub__(self, subtractTile):
        """returns a copy of self minus subtractTiles.
        Case of subtractTile (hidden or exposed) is ignored.
        subtractTile must either be undeclared or part of
        lastMeld. Exposed melds of length<3 will be hidden."""
        # pylint: disable=too-many-branches
        # If lastMeld is given, it must be first in the list.
        # Next try undeclared melds, then declared melds
        assert self.lenOffset == 1
        if self.lastTile:
            if self.lastTile is subtractTile and self.prevHand:
                return self.prevHand
        declaredMelds = self.declaredMelds
        tilesInHand = TileList(self.tilesInHand)
        boni = MeldList(self.bonusMelds)
        lastMeld = self.lastMeld
        if subtractTile.isBonus:
            for idx, meld in enumerate(boni):
                if subtractTile is meld[0]:
                    del boni[idx]
                    break
        else:
            if lastMeld and lastMeld.isDeclared and (
                    subtractTile.exposed in lastMeld.exposed):
                declaredMelds.remove(lastMeld)
                tilesInHand.extend(lastMeld.concealed)
            tilesInHand.remove(subtractTile.concealed)
        for meld in declaredMelds[:]:
            if len(meld) < 3:
                declaredMelds.remove(meld)
                tilesInHand.extend(meld.concealed)
        newParts = []
        for idx, part in enumerate(self.mjStr.split()):
            if part[0] == 'm':
                if len(part) > 1 and part[1] == 'k':
                    continue
            elif part[0] == 'L':
                if (self.lastTile.isExposed
                        and self.lastTile.concealed in tilesInHand):
                    part = 'L' + self.lastTile.concealed
                else:
                    continue
            newParts.append(part)
        mjStr = ' '.join(newParts)
        rest = 'R' + str(tilesInHand)
        newString = ' '.join(str(x) for x in (
            declaredMelds, rest, boni, mjStr))
        return Hand(self.player, newString, prevHand=self)

    def manualRuleMayApply(self, rule):
        """returns True if rule has selectable() and applies to this hand"""
        if self.__won and rule in self.ruleset.loserRules:
            return False
        if not self.__won and rule in self.ruleset.winnerRules:
            return False
        return rule.selectable(self) or rule.appliesToHand(self)
        # needed for activated rules

    @property
    def callingHands(self):
        """the hand is calling if it only needs one tile for mah jongg.
        Returns all hands which would only need one tile.
        If mustBeAvailable is True, make sure the missing tile might still
        be available.
        """
        if self.__callingHands is None:
            self.__callingHands = self.__findAllCallingHands()
        return self.__callingHands

    def __findAllCallingHands(self):
        """always try to find all of them"""
        result = []
        string = self.string
        if ' x' in string or self.lenOffset:
            return result
        candidates = []
        for rule in self.ruleset.mjRules:
            cand = rule.winningTileCandidates(self)
            if Debug.hand and cand:
                # Py2 and Py3 show sets differently
                candis = ''.join(str(x) for x in sorted(cand)) # pylint: disable=unused-variable
                self.debug(fmt('callingHands found {candis} for {rule}'))
            candidates.extend(x.concealed for x in cand)
        # FIXME: we must differentiate between last Tile exposed or concealed.
        # example:
        # ./kajongg.py --game=7165/E4 --demo --ruleset=BMJA --playopen --debug=hand
        # sort only for reproducibility
        for tile in sorted(set(candidates)):
            if sum(x.exposed == tile.exposed for x in self.tiles) == 4:
                continue
            hand = self + tile
            if hand.won:
                result.append(hand)
        if Debug.hand:
            self.debug(
                fmt('{id(self)} {self} is calling {rules}',
                    rules=list(x.mjRule.name for x in result)))
        return result

    @property
    def robbedTile(self):
        """cache this here for use in rulecode"""
        if self.__robbedTile is Tile.unknown:
            self.__robbedTile = None
            if self.player.game.moves:
                # scoringtest does not (yet) simulate this
                lastMove = self.player.game.moves[-1]
                if (lastMove.message == Message.DeclaredKong
                        and lastMove.player != self.player):
                    self.__robbedTile = lastMove.meld[1]
                    # we want it concealed only for a hidden Kong
        return self.__robbedTile

    def __maybeMahjongg(self):
        """check if this is a mah jongg hand.
        Return a sorted list of matching MJ rules, highest
        total first. If no rule matches, return None"""
        if self.lenOffset == 1 and self.player.mayWin:
            matchingMJRules = [x for x in self.ruleset.mjRules
                               if x.appliesToHand(self)]
            if matchingMJRules:
                if self.robbedTile and self.robbedTile.isConcealed:
                    # Millington 58: robbing hidden kong is only
                    # allowed for 13 orphans
                    matchingMJRules = [
                        x for x in matchingMJRules
                        if 'mayrobhiddenkong' in x.options]
                result = sorted(matchingMJRules, key=lambda x: -x.score.total())
                if Debug.mahJongg:
                    self.debug(u'Hand {}: found matching MJRules:{}'.format(self,matchingMJRules))
                return result

    def __arrangements(self):
        """find all legal arrangements"""
        self.__rest.sort()
        result = []
        stdMJ = self.ruleset.standardMJRule
        if self.mjRule:
            rules = [self.mjRule]
        else:
            rules = self.ruleset.mjRules
        for mjRule in rules:
            if ((self.lenOffset == 1 and mjRule.appliesToHand(self))
                    or (self.lenOffset < 1 and mjRule.shouldTry(self))):
                if self.__rest:
                    for melds, rest2 in mjRule.rearrange(self, self.__rest[:]):
                        if rest2:
                            melds = list(melds)
                            restMelds, _ = next(
                                stdMJ.rearrange(self, rest2[:]))
                            melds.extend(restMelds)
                        result.append((mjRule, melds))
        if not result:
            result.extend(
                (stdMJ, x[0])
                for x in stdMJ.rearrange(self, self.__rest[:]))
        return result

    def __arrange(self):
        """work hard to always return the variant with the highest Mah Jongg value.
        Adds melds to self.melds. A rest will be rearranged by
        standard rules."""
        if any(not x.isKnown for x in self.__rest):
            melds, rest = divmod(len(self.__rest), 3)
            self.melds.extend([Tile.unknown.pung] * melds)
            if rest:
                self.melds.append(Meld(Tile.unknown * rest))
            self.__rest = []
        if not self.__rest:
            self.melds.sort()
            mjRules = self.__maybeMahjongg()
            self.__won &= bool(mjRules)
            if mjRules:
                self.mjRule = mjRules[0]
            return
        wonHands = []
        lostHands = []
        for mjRule, melds in self.__arrangements():
            _ = ' '.join(str(x) for x in sorted(
                chain(self.melds, melds, self.bonusMelds))) + ' ' + self.mjStr
            tryHand = Hand(self.player, _, prevHand=self)
            if tryHand.won:
                tryHand.mjRule = mjRule
                wonHands.append((mjRule, melds, tryHand))
            else:
                lostHands.append((mjRule, melds, tryHand))
        # we prefer a won Hand even if a lost Hand might have a higher score
        tryHands = wonHands if wonHands else lostHands
        bestRule, bestVariant, _ = max(tryHands, key=lambda x: x[2])
        self.mjRule = bestRule
        self.melds.extend(bestVariant)
        self.melds.sort()
        self.__rest = []
        self.ruleCache.clear()
        assert sum(len(x) for x in self.melds) == len(self.tiles), (
            '%s != %s' % (self.melds, self.tiles))

    def __gt__(self, other):
        """compares hand values"""
        assert self.player == other.player
        if not other.arranged:
            return True
        if self.won and not (other.arranged and other.won):
            return True
        elif not (self.arranged and self.won) and other.won:
            return False
        else:
            return (self.intelligence.handValue(self)
                    > self.intelligence.handValue(other))

    def __lt__(self, other):
        """compares hand values"""
        return other.__gt__(self)

    def __eq__(self, other):
        """compares hand values"""
        assert self.player == other.player
        return self.string == other.string

    def __ne__(self, other):
        """compares hand values"""
        assert self.player == other.player
        return self.string != other.string

    def __matchingRules(self, rules):
        """return all matching rules for this hand"""
        return list(rule for rule in rules if rule.appliesToHand(self))

    @staticmethod
    def maxLimitRule(usedRules):
        """returns the rule with the highest limit score or None"""
        result = None
        maxLimit = 0
        usedRules = list(x for x in usedRules if x.rule.score.limits)
        for usedRule in usedRules:
            score = usedRule.rule.score
            if score.limits > maxLimit:
                maxLimit = score.limits
                result = usedRule
        return result

    def __totalScore(self):
        """use all used rules to compute the score"""
        maxRule = self.maxLimitRule(self.usedRules)
        maxLimit = 0.0
        pointsTotal = sum((x.rule.score for x in self.usedRules),
                          Score(ruleset=self.ruleset))
        if maxRule:
            maxLimit = maxRule.rule.score.limits
            if (maxLimit >= 1.0
                    or maxLimit * self.ruleset.limit > pointsTotal.total()):
                self.usedRules = [maxRule]
                return Score(ruleset=self.ruleset, limits=maxLimit)
        return pointsTotal

    def total(self):
        """total points of hand"""
        return self.score.total()

    @staticmethod
    def __separateBonusMelds(tileStrings):
        """One meld per bonus tile. Others depend on that."""
        bonusMelds = MeldList()
        for tileString in tileStrings[:]:
            if len(tileString) == 2:
                tile = Tile(tileString)
                if tile.isBonus:
                    bonusMelds.append(tile.single)
                    tileStrings.remove(tileString)
        return bonusMelds, tileStrings

    def explain(self):
        """explain what rules were used for this hand"""
        usedRules = self.player.sortRulesByX(self.usedRules)
        result = [x.rule.explain(x.meld) for x in usedRules
                  if x.rule.score.points]
        result.extend(
            [x.rule.explain(x.meld) for x in usedRules
             if x.rule.score.doubles])
        result.extend(
            [x.rule.explain(x.meld) for x in usedRules
             if not x.rule.score.points and not x.rule.score.doubles])
        if any(x.rule.debug for x in usedRules):
            result.append(str(self))
        return result

    def doublesEstimate(self, discard=None):
        """this is only an estimate because it only uses meldRules and handRules,
        but not things like mjRules, winnerRules, loserRules"""
        result = 0
        if discard and self.tiles.count(discard) == 2:
            melds = chain(self.melds, self.bonusMelds, [discard.exposed.pung])
        else:
            melds = chain(self.melds, self.bonusMelds)
        for meld in melds:
            result += sum(x.score.doubles for x in meld.doublingRules(self))
        for rule in self.ruleset.doublingHandRules:
            if rule.appliesToHand(self):
                result += rule.score.doubles
        return result

    def __str__(self):
        """hand as a string"""
        rest = 'REST ' + ''.join(str(x) for x in self.__rest)
        return ' '.join(str(x) for x in (
            self.melds, rest, self.bonusMelds, self.mjStr)).replace('  ', ' ')

    def __repr__(self):
        """the default representation"""
        return 'Hand(%s)' % str(self)
