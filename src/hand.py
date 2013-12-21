# -*- coding: utf-8 -*-

"""Copyright (C) 2009-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

class Hand(object):
    """represent the hand to be evaluated.

    lenOffset is <0 for short hand, 0 for correct calling hand, >0 for long hand.
    Of course ignoring bonus tiles.
    if there are no kongs, 13 tiles will return 0

    declaredMelds are those which cannot be changed anymore: Chows, Pungs,
    Kongs.

    tilesInHand are those not in declaredMelds

    Only tiles passed in the 'R' substring may be rearranged.

    mjRule is the one out of mjRule with the highest resulting score. Every
    hand gets an mjRule even it is not a wining hand."""
    # pylint: disable=too-many-instance-attributes

    def __new__(cls, player, string, robbedTile=None, prevHand=None): # pylint: disable=unused-argument
        """since a Hand instance is never changed, we can use a cache"""
        cache = player.handCache
        cacheKey = hash((string, robbedTile))
        if cacheKey in cache:
            result = cache[cacheKey]
            if not hasattr(result, '_fixed'):
                raise Exception('recursion: Hand calls itself for same content')
            player.cacheHits += 1
            if Debug.hand:
                result._player = weakref.ref(player) # pylint: disable=protected-access
                result.debug(fmt(
                  '{callers}: cached Hand({id(result)} {string}) {result.lenOffset} {id(prevHand)}',
                    callers=callers(10, exclude=['__init__'])))
            return result
        player.cacheMisses += 1
        result = object.__new__(cls)
        cache[cacheKey] = result
        return result

    def __init__(self, player, string, robbedTile=None, prevHand=None):
        """evaluate string for player. rules are to be applied in any case"""
        # silence pylint. This method is time critical, so do not split it into smaller methods
        # pylint: disable=too-many-instance-attributes,too-many-branches,too-many-statements
        if hasattr(self, 'string'):
            # I am from cache
            return
        self._player = weakref.ref(player)
        self.indent = prevHand.indent + 1 if prevHand else 0

        # two shortcuts for speed:
        self.ruleset = self.player.game.ruleset
        self.intelligence = self.player.intelligence if self.player else AIDefault()
        self.string = string
        self.robbedTile = robbedTile
        self.prevHand = prevHand
        self.__won = False
        self.__score = None
        self.__callingHands = {}
        self.mjStr = ''
        self.mjRule = None
        self.ownWind = None
        self.roundWind = None
        self.ruleCache = {}
        tileStrings = []
        haveM = False
        for part in self.string.split():
            partId = part[:1]
            if partId in 'Mmx':
                haveM = True
                self.ownWind = part[1:2]
                self.roundWind = part[2:3]
                self.mjStr += ' ' + part
                self.__won = partId == 'M'
            elif partId == 'L':
                if len(part[1:]) > 8:
                    raise Exception('last tile cannot complete a kang:' + self.string)
                self.mjStr += ' ' + part
            else:
                if part != 'R':
                    tileStrings.append(part)

        if not haveM:
            raise Exception('Hand got string without mMx: %s', self.string)
        self.__lastTile = self.__lastSource = self.__announcements = ''
        self.__lastMeld = 0
        self.__lastMelds = MeldList()
        self.melds = MeldList()
        self.bonusMelds, tileStrings = self.__separateBonusMelds(tileStrings)
        tileString = ' '.join(tileStrings)
        self.tiles = TileList(tileString.replace(' ', '').replace('R', ''))
        self.tiles.sort()
        self.values = ''.join(x.value for x in self.tiles)
        self.suits = set(x.lowerGroup for x in self.tiles)
        for part in tileStrings[:]:
            if part[:1] != 'R':
                self.melds.append(Meld(part))
                tileStrings.remove(part)
        # those must be set before splitting the rest because the rearrange()
        # functions need them
        self.declaredMelds = MeldList(x for x in self.melds if x.isDeclared)
        declaredTiles = list(sum((x for x in self.declaredMelds), []))
        self.tilesInHand = TileList(x for x in self.tiles if x not in declaredTiles)
        self.lenOffset = len(self.tiles) - 13 - sum(x.isKong for x in self.declaredMelds)

        assert len(tileStrings) < 2, tileStrings
        self.rest = TileList()
        if len(tileStrings):
            self.rest.extend(TileList(tileStrings[0][1:]))
        self.usedRules = []
        self.calculated = False
        if Debug.hand:
            self.debug(fmt('Fixing Hand({id(self)}, {string}, {self.won}'))
        self._fixed = True

    @property
    def player(self):
        """weakref"""
        return self._player()

    def calculate(self):
        """rearrange and calculate score"""
        if self.calculated:
            return
        self.calculated = True
        self.__split()
        self.melds.sort()

        self.usedRules = []
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
        if not self.__score:
            self.calculate()
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
        """have we been modified since load or last save?
        The "won" value is set to True when instantiating the hand,
        according to the mMx in the init string. Later on, it may
        only be cleared."""
        self.calculate()
        return self.__won

    @won.setter
    def won(self, value):
        """must never change to True"""
        value = bool(value)
        assert not value
        self.__won = value
        self.string = self.string.replace(' M', ' m')
        self.mjStr = self.mjStr.replace(' M', ' m')

    def debug(self, msg):
        """try to use Game.debug so we get a nice prefix"""
        self.player.game.debug(dbgIndent(self, self.prevHand) + msg)

    def __applyRules(self):
        """find out which rules apply, collect in self.usedRules.
        This may change self.won"""
        self.usedRules = []
        if self.__hasExclusiveRules():
            return
        self.__applyMeldRules()
        self.__applyHandRules()
        if self.__hasExclusiveRules():
            return
        self.__score = self.__totalScore()

        self.ruleCache.clear()
        # do the rest only if we know all tiles of the hand
        if Tile.unknown in self.string:
            self.won = False    # we do not know better
            return
        if self.__won:
            matchingMJRules = self.__maybeMahjongg()
            if not matchingMJRules:
                self.won = False
                if Debug.hand:
                    self.debug(fmt('no matching MJ Rule for {id(self)} {self}'))
                self.__score = self.__totalScore()
                return
            self.mjRule = matchingMJRules[0]
            if self.mjRule:
                self.usedRules.append(UsedRule(self.mjRule))
            if self.__hasExclusiveRules():
                return
            self.usedRules.extend(self.matchingWinnerRules())
            self.__score = self.__totalScore()
        else: # not self.won
            loserRules = self.__matchingRules(self.ruleset.loserRules)
            if loserRules:
                self.usedRules.extend(list(UsedRule(x) for x in loserRules))
                self.__score = self.__totalScore()

    def matchingWinnerRules(self):
        """returns a list of matching winner rules"""
        matching = list(UsedRule(x) for x in self.__matchingRules(self.ruleset.winnerRules))
        limitRule = self.maxLimitRule(matching)
        return [limitRule] if limitRule else matching

    def __hasExclusiveRules(self):
        """if we have one, remove all others"""
        exclusive = list(x for x in self.usedRules if 'absolute' in x.rule.options)
        if exclusive:
            self.usedRules = exclusive
            self.__score = self.__totalScore()
            self.won = self.__maybeMahjongg()
            if not self.won and Debug.hand:
                self.debug(fmt('exclusive rule {exclusive} does not win: {self}'))
        return bool(exclusive)

    def __setLastTile(self):
        """sets lastTile, lastSource, announcements"""
        self.__announcements = ''
        self.__lastTile = None # not '' because we want to cache the result, see lastTile property
        self.__lastSource = None
        parts = self.mjStr.split()
        for part in parts:
            if part[:1] == 'L':
                part = part[1:]
                if len(part) > 2:
                    self.__lastMeld = Meld(part[2:])
                self.__lastTile = Tile(part[:2])
            elif part[:1] == 'M':
                if len(part) > 3:
                    self.__lastSource = part[3:4]
                    if len(part) > 4:
                        self.__announcements = part[4:]
        if self.__lastTile:
            assert self.__lastTile.isBonus or self.__lastTile in self.tiles, \
                'lastTile %s is not in hand %s, mjStr=%s' % (
                self.__lastTile, self.string, self.mjStr)
            if self.__lastSource == 'k':
                assert self.tiles.count(self.__lastTile.lower()) + \
                    self.tiles.count(self.__lastTile.capitalize()) == 1, \
                    'Robbing kong: I cannot have lastTile %s more than once in %s' % (
                    self.__lastTile, ' '.join(self.tiles))


    def __setLastMeld(self):
        """sets the shortest possible last meld. This is
        not yet the final choice, see __applyBestLastMeld"""
        self.__lastMeld = None
        if self.lastTile and self.__won:
            if self.mjRule and hasattr(self.mjRule, 'computeLastMelds'):
                self.__lastMelds = self.mjRule.computeLastMelds(self)
                if self.__lastMelds:
                    # syncHandBoard may return nothing
                    if len(self.__lastMelds) == 1:
                        self.__lastMeld = self.__lastMelds[0]
                    else:
                        totals = sorted((len(x), idx) for idx, x in enumerate(self.__lastMelds))
                        self.__lastMeld = self.__lastMelds[totals[0][1]]
            if not self.__lastMeld:
                self.__lastMeld = Meld([self.lastTile])
                self.__lastMelds = MeldList(self.__lastMeld)

    def __applyBestLastMeld(self):
        """select the last meld giving the highest score (only winning variants)"""
        assert len(self.lastMelds) > 1
        totals = []
        prev = self.lastMeld
        for rule in self.usedRules:
            assert isinstance(rule, UsedRule)
        for lastMeld in self.lastMelds:
            self.__lastMeld = lastMeld
            self.__applyRules()
            totals.append((self.__won, self.__totalScore().total(), lastMeld))
        if any(x[0] for x in totals): # if any won
            totals = list(x[1:] for x in totals if x[0]) # remove lost variants
            totals = sorted(totals) # sort by totalScore
            maxScore = totals[-1][0]
            totals = list(x[1] for x in totals if x[0] == maxScore)
            # now we have a list of only lastMelds reaching maximum score
            if prev not in totals or self.__lastMeld not in totals:
                if Debug.explain and prev not in totals:
                    if not self.player.game.belongsToRobotPlayer():
                        self.debug(fmt('replaced last meld {prev} with {totals[0]}'))
                self.__lastMeld = totals[0]
                self.__applyRules()

    def chancesToWin(self):
        """count the physical tiles that make us win and still seem availabe"""
        result = []
        for completedHand in self.callingHands(99):
            result.extend([completedHand.lastTile] * (
                    self.player.tileAvailable(completedHand.lastTile, self)))
        return result

    def __add__(self, addTile):
        """returns a new Hand built from this one plus addTile"""
        assert addTile.istitle(), 'addTile %s should be title:' % addTile
        # combine all parts about hidden tiles plus the new one to one part
        # because something like DrDrS8S9 plus S7 will have to be reordered
        # anyway
        # set the "won" flag M
        parts = [str(self.declaredMelds)]
        parts.extend(str(x[0]) for x in self.bonusMelds)
        parts.append('R' + ''.join(str(x) for x in sorted(self.tilesInHand + [addTile])))
        parts.append('M' + self.ownWind + self.roundWind + self.announcements)
        parts.append('L' + addTile)
        return Hand(self.player, ' '.join(parts).strip(), prevHand=self)

    def __sub__(self, subtractTile):
        """returns a copy of self minus subtractTiles. Case of subtractTile (hidden
        or exposed) is ignored. subtractTile must either be undeclared or part of
        lastMeld. Exposed melds of length<3 will be hidden."""
        # pylint: disable=too-many-branches
        # If lastMeld is given, it must be first in the list. Next try undeclared melds, then declared melds
        assert self.lenOffset == 1
        if self.lastTile:
            if self.lastTile == subtractTile and self.prevHand:
                return self.prevHand
        declaredMelds = self.declaredMelds
        tilesInHand = TileList(self.tilesInHand)
        boni = MeldList(self.bonusMelds)
        lastMeld = self.lastMeld
        if subtractTile.isBonus:
            for idx, meld in enumerate(boni):
                if subtractTile == meld[0]:
                    del boni[idx]
                    break
        else:
            if lastMeld and lastMeld.isDeclared and subtractTile.lower() in lastMeld.toLower():
                declaredMelds.remove(lastMeld)
                tilesInHand.extend(lastMeld.toUpper())
            tilesInHand.remove(subtractTile.upper())
        for meld in declaredMelds[:]:
            if len(meld) < 3:
                declaredMelds.remove(meld)
                tilesInHand.extend(meld.toUpper())
        newParts = []
        for idx, part in enumerate(self.mjStr.split()):
            if part[:1] == 'M':
                part = 'm' + part[1:]
                if len(part) > 3 and part[3:4] == 'k':
                    part = part[:3]
            elif part[:1] == 'L':
                if self.lastTile.isExposed and self.lastTile.upper() in tilesInHand:
                    part = 'L' + self.lastTile.upper()
                else:
                    continue
            newParts.append(part)
        mjStr = ' '.join(newParts)
        rest = 'R' + str(tilesInHand)
        newString = ' '.join(str(x) for x in (declaredMelds, rest, boni, mjStr))
        return Hand(self.player, newString, prevHand=self)

    def manualRuleMayApply(self, rule):
        """returns True if rule has selectable() and applies to this hand"""
        if self.__won and rule in self.ruleset.loserRules:
            return False
        if not self.__won and rule in self.ruleset.winnerRules:
            return False
        return rule.selectable(self) or rule.appliesToHand(self) # needed for activated rules

    def callingHands(self, wanted=1, excludeTile=None, mustBeAvailable=False):
        """the hand is calling if it only needs one tile for mah jongg.
        Returns up to 'wanted' hands which would only need one tile.
        If mustBeAvailable is True, make sure the missing tile might still
        be available.
        """
        # pylint: disable=too-many-branches
        if not mustBeAvailable:
            cacheKey = (wanted, excludeTile)
            if cacheKey in self.__callingHands:
                return self.__callingHands[cacheKey]
        result = []
        string = self.string
        if ' x' in string or self.lenOffset:
            return result
        candidates = []
        for rule in self.ruleset.mjRules:
            cand = rule.winningTileCandidates(self)
            if Debug.hand and cand:
                self.debug(fmt('callingHands found {cand} for {rule}'))
            candidates.extend(x.capitalize() for x in cand)
        # sort only for reproducibility
        candidates = sorted(set(candidates))
        for tileName in candidates:
            if excludeTile and tileName == excludeTile.capitalize():
                continue
            if mustBeAvailable and not self.player.tileAvailable(tileName, self):
                continue
            if sum(x.lower() == tileName.lower() for x in self.tiles) == 4:
                continue
            hand = self + tileName
            if hand.won:
                result.append(hand)
                if len(result) == wanted:
                    break
        if not mustBeAvailable:
            self.__callingHands[cacheKey] = result
        if Debug.hand:
            self.debug(fmt('{id(self)} {self} is calling {rules}', rules=list(x.mjRule.name for x in result)))
        return result

    def __maybeMahjongg(self):
        """check if this is a mah jongg hand.
        Return a sorted list of matching MJ rules, highest
        total first"""
        if not self.__won:
            return []
        if self.lenOffset != 1:
            return []
        matchingMJRules = [x for x in self.ruleset.mjRules if x.appliesToHand(self)]
        if self.robbedTile and self.robbedTile.istitle():
            # Millington 58: robbing hidden kong is only allowed for 13 orphans
            matchingMJRules = [x for x in matchingMJRules if 'mayrobhiddenkong' in x.options]
        return sorted(matchingMJRules, key=lambda x: -x.score.total())

    def __arrange(self):
        """find all legal arrangements"""
        self.rest.sort()
        arrangements = []
        stdMJ = self.ruleset.standardMJRule
        if self.mjRule:
            rules = [self.mjRule]
        else:
            rules = self.ruleset.mjRules
        for mjRule in rules:
            if ((self.lenOffset == 1 and mjRule.appliesToHand(self))
                    or (self.lenOffset < 1 and mjRule.shouldTry(self))):
                if self.rest:
                    for melds, rest2 in mjRule.rearrange(self, self.rest[:]):
                        if rest2:
                            melds = list(melds)
                            restMelds, _ = next(stdMJ.rearrange(self, rest2[:]))
                            melds.extend(restMelds)
                        arrangements.append((mjRule, melds))
        if not arrangements:
            arrangements.extend((stdMJ, x[0]) for x in stdMJ.rearrange(self, self.rest[:]))
        return arrangements

    def __split(self):
        """work hard to always return the variant with the highest Mah Jongg value.
        Adds melds to self.melds. A rest will be rearranged by standard rules."""
        for tile in self.rest[:]:
            if not tile.isKnown:
                self.rest.remove(tile)
                self.melds.append(Meld(tile))
        if not self.rest:
            return
        arrangements = self.__arrange()
        bestVariant = None
        bestRule = None
        if len(arrangements) == 1:
            bestRule = arrangements[0][0]
            bestVariant = arrangements[0][1]
        else:
            wonHands = []
            lostHands = []
            for mjRule, melds in arrangements:
                _ = ' '.join(str(x) for x in sorted(chain(self.melds, melds, self.bonusMelds))) + ' ' + self.mjStr
                tryHand = Hand(self.player, _, prevHand=self)
                tryHand.mjRule = mjRule
                tryHand.calculate()
                if tryHand.won:
                    wonHands.append((mjRule, melds, tryHand))
                else:
                    lostHands.append((mjRule, melds, tryHand))
            tryHands = wonHands if wonHands else lostHands
            bestRule, bestVariant, _ = max(tryHands, key=lambda x:x[2])
        self.mjRule = bestRule
        self.melds.extend(bestVariant)
        self.melds.sort()
        self.rest = []
        self.ruleCache.clear()
        assert sum(len(x) for x in self.melds) == len(self.tiles), '%s != %s' % (
            self.melds, self.tiles)

    def __gt__(self, other):
        """compares hand values"""
        assert self.player == other.player
        return self.intelligence.handValue(self) > self.intelligence.handValue(other)

    def __lt__(self, other):
        """compares hand values"""
        assert self.player == other.player
        return self.intelligence.handValue(self) < self.intelligence.handValue(other)

    def __eq__(self, other):
        """compares hand values"""
        assert self.player == other.player
        return self.intelligence.handValue(self) == self.intelligence.handValue(other)

    def __matchingRules(self, rules):
        """return all matching rules for this hand"""
        return list(rule for rule in rules if rule.appliesToHand(self))

    def __applyMeldRules(self):
        """apply all rules for single melds"""
        for meld in self.melds + self.bonusMelds:
            self.usedRules.extend(meld.staticRules(self.ruleset))
            for rule in self.ruleset.dynamicMeldRules:
                if rule.appliesToMeld(self, meld):
                    self.usedRules.append(UsedRule(rule, meld))

    def __applyHandRules(self):
        """apply all hand rules for both winners and losers"""
        for rule in self.ruleset.handRules:
            if rule.appliesToHand(self):
                self.usedRules.append(UsedRule(rule))

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
        pointsTotal = sum((x.rule.score for x in self.usedRules), Score(ruleset=self.ruleset))
        if maxRule:
            maxLimit = maxRule.rule.score.limits
            if maxLimit >= 1.0 or maxLimit * self.ruleset.limit > pointsTotal.total():
                self.usedRules =  [maxRule]
                return Score(ruleset=self.ruleset, limits=maxLimit)
        return pointsTotal

    def total(self):
        """total points of hand"""
        return self.score.total()

    @staticmethod
    def __separateBonusMelds(tileStrings):
        """keep them separate. One meld per bonus tile. Others depend on that."""
        bonusMelds = MeldList()
        for tileString in tileStrings[:]:
            if len(tileString) == 2:
                tile = Tile(tileString)
                if tile.isBonus:
                    bonusMelds.append(Meld(tile))
                    tileStrings.remove(tileString)
        return bonusMelds, tileStrings

    def explain(self):
        """explain what rules were used for this hand"""
        usedRules = self.player.sortRulesByX(self.usedRules)
        result = [x.rule.explain(x.meld) for x in usedRules
            if x.rule.score.points]
        result.extend([x.rule.explain(x.meld) for x in usedRules
            if x.rule.score.doubles])
        result.extend([x.rule.explain(x.meld) for x in usedRules
            if not x.rule.score.points and not x.rule.score.doubles])
        if any(x.rule.debug for x in usedRules):
            result.append(str(self))
        return result

    def doublesEstimate(self):
        """this is only an estimate because it only uses meldRules and handRules,
        but not things like mjRules, winnerRules, loserRules"""
        result = 0
        for meld in (x for x in self.melds if x.isHonorMeld):
            for rule in self.ruleset.doublingMeldRules:
                if rule.appliesToMeld(self, meld):
                    result += rule.score.doubles
        for rule in self.ruleset.doublingHandRules:
            if rule.appliesToHand(self):
                result += rule.score.doubles
        return result

    def __str__(self):
        """hand as a string"""
        rest = 'REST ' + ''.join(str(x) for x in self.rest)
        return ' '.join(str(x) for x in (self.melds, rest, self.bonusMelds, self.mjStr)).replace('  ', ' ')

    def __repr__(self):
        """the default representation"""
        return 'Hand(%s)' % str(self)
