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

from log import logDebug
from tile import Tile, Values, TileList
from meld import Meld, MeldList
from rule import Score, Ruleset
from common import Debug
from permutations import Permutations

class UsedRule(object):
    """use this in scoring, never change class Rule.
    If the rule has been used for a meld, pass it"""
    def __init__(self, rule, meld=None):
        self.rule = rule
        self.meld = meld

    def __str__(self):
        result = self.rule.name
        if self.meld:
            result += ' ' + str(self.meld)
        return result

    def __repr__(self):
        return 'UsedRule(%s)' % str(self)

class Hand(object):
    """represent the hand to be evaluated.

    lenOffset is <0 for short hand, 0 for correct calling hand, >0 for long hand.
    Of course ignoring bonus tiles.
    if there are no kongs, 13 tiles will return 0

    declaredMelds are not just the exposed melds but also those we
    want to be pre-fixed while evaluating this hand. Only tiles
    passed in the 'R' substring may be rearranged. """

    # pylint: disable=too-many-instance-attributes

    cache = dict()
    misses = 0
    hits = 0

    @staticmethod
    def clearCache(game):
        """clears the cache with Hands"""
        if Debug.handCache and Hand.cache:
            game.debug('cache hits:%d misses:%d' % (Hand.hits, Hand.misses))
        Hand.cache.clear()
        Permutations.cache.clear()
        Hand.hits = 0
        Hand.misses = 0

    def __new__(cls, ruleset, string, computedRules=None, robbedTile=None):
        """since a Hand instance is never changed, we can use a cache"""
        cache = cls.cache
        if computedRules is not None and not isinstance(computedRules, list):
            computedRules = list([computedRules])
        cRuleHash = '&&'.join([rule.name for rule in computedRules]) if computedRules else 'None'
        if isinstance(ruleset, Hand):
            cacheId = id(ruleset.player or ruleset.ruleset)
        else:
            cacheId = id(ruleset)
        cacheKey = hash((cacheId, string, robbedTile, cRuleHash))
        if cacheKey in cache:
            if cache[cacheKey] is None:
                raise Exception('recursion: Hand calls itself for same content')
            cls.hits += 1
            return cache[cacheKey]
        cls.misses += 1
        result = object.__new__(cls)
        cache[cacheKey] = result
        return result

    def __init__(self, ruleset, string, computedRules=None, robbedTile=None):
        """evaluate string using ruleset. rules are to be applied in any case.
        ruleset can be Hand, Game or Ruleset."""
        # silence pylint. This method is time critical, so do not split it into smaller methods
        # pylint: disable=too-many-instance-attributes,too-many-branches,too-many-statements
        if hasattr(self, 'string'):
            # I am from cache
            return
        assert isinstance(string, bytes)
        if isinstance(ruleset, Hand):
            self.ruleset = ruleset.ruleset
            self.player = ruleset.player
            self.computedRules = ruleset.computedRules
        elif isinstance(ruleset, Ruleset):
            self.ruleset = ruleset
            self.player = None
        else:
            self.player = ruleset
            self.ruleset = self.player.game.ruleset
        self.string = string
        self.robbedTile = robbedTile
        if computedRules is not None and not isinstance(computedRules, list):
            computedRules = list([computedRules])
        self.computedRules = computedRules or []
        self.__won = False
        self.__callingHands = {}
        self.mjStr = b''
        self.mjRule = None
        self.ownWind = None
        self.roundWind = None
        tileStrings = []
        haveM = False
        for part in self.string.split():
            partId = part[:1]
            if partId in b'Mmx':
                haveM = True
                self.ownWind = part[1:2]
                self.roundWind = part[2:3]
                self.mjStr += b' ' + part
                self.__won = partId == b'M'
            elif partId == b'L':
                if len(part[1:]) > 8:
                    raise Exception('last tile cannot complete a kang:' + self.string)
                self.mjStr += b' ' + part
            else:
                if part != b'R':
                    tileStrings.append(part)

        if not haveM:
            raise Exception('Hand got string without mMx: %s', self.string)
        self.__lastTile = self.__lastSource = self.__announcements = b''
        self.__lastMeld = 0
        self.__lastMelds = MeldList()
        self.melds = MeldList()
        self.bonusMelds, tileStrings = self.__separateBonusMelds(tileStrings)
        tileString = b' '.join(tileStrings)
        self.tileNames = TileList(tileString.replace(b' ', b'').replace(b'R', b''))
        self.tileNames.sort()
        self.values = Values(x.value for x in self.tileNames)
        self.suits = set(x.lowerGroup for x in self.tileNames)
        for split in tileStrings[:]:
            if split[:1] != b'R':
                self.melds.append(Meld(split))
                tileStrings.remove(split)
        self.declaredMelds = MeldList(x for x in self.melds if x.isDeclared)
        declaredTiles = list(sum((x for x in self.declaredMelds), []))
        self.tilesInHand = TileList(x for x in self.tileNames if x not in declaredTiles)
        self.lenOffset = len(self.tileNames) - 13 - sum(x.isKong for x in self.melds)
        assert len(tileStrings) < 2, tileStrings
        if len(tileStrings):
            self.__split(sorted(TileList(tileStrings[0][1:])))
        self.melds.sort()
        self.hasHonorMelds = any(x.isHonorMeld for x in self.melds)

        self.usedRules = []
        self.score = None
        oldWon = self.won
        self.__applyRules()
        if len(self.lastMelds) > 1:
            self.__applyBestLastMeld()
        if self.won != oldWon:
            # if not won after all, this might be a long hand.
            # So we might even have to unapply meld rules and
            # bonus points. Instead just recompute all again.
            # This should only happen with scoring manual games
            # and with scoringtest - normally kajongg would not
            # let you declare an invalid mah jongg
            self.__applyRules()

    def hasTiles(self):
        """tiles are assigned to this hand"""
        return self.tileNames or self.bonusMelds

    @property
    def lastTile(self):
        """compute and cache, readonly"""
        if self.__lastTile == b'':
            self.__setLastTile()
        return self.__lastTile

    @property
    def lastSource(self):
        """compute and cache, readonly"""
        if self.__lastTile == b'':
            self.__setLastTile()
        return self.__lastSource

    @property
    def announcements(self):
        """compute and cache, readonly"""
        if self.__lastTile == b'':
            self.__setLastTile()
        return self.__announcements

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
        return self.__won

    @won.setter
    def won(self, value):
        """must never change to True"""
        value = bool(value)
        assert not value
        self.__won = value
        self.string = self.string.replace(b' M', b' m')
        self.mjStr = self.mjStr.replace(b' M', b' m')

    def debug(self, msg, btIndent=None):
        """try to use Game.debug so we get a nice prefix"""
        if self.player:
            self.player.game.debug(msg, btIndent=btIndent)
        else:
            logDebug(msg, btIndent=btIndent)

    def __applyRules(self):
        """find out which rules apply, collect in self.usedRules.
        This may change self.won"""
        self.usedRules = list([UsedRule(rule) for rule in self.computedRules])
        if self.__hasExclusiveRules():
            return
        self.__applyMeldRules()
        self.__applyHandRules()
        if self.__hasExclusiveRules():
            return
        self.score = self.__totalScore()

        # do the rest only if we know all tiles of the hand
        if Tile.unknown in self.string:
            self.won = False    # we do not know better
            return
        if self.won:
            matchingMJRules = self.__maybeMahjongg()
            if not matchingMJRules:
                self.won = False
                self.score = self.__totalScore()
                return
            self.mjRule = matchingMJRules[0]
            self.usedRules.append(UsedRule(self.mjRule))
            if self.__hasExclusiveRules():
                return
            self.usedRules.extend(self.matchingWinnerRules())
            self.score = self.__totalScore()
        else: # not self.won
            assert self.mjRule is None
            loserRules = self.__matchingRules(self.ruleset.loserRules)
            if loserRules:
                self.usedRules.extend(list(UsedRule(x) for x in loserRules))
                self.score = self.__totalScore()

    def matchingWinnerRules(self):
        """returns a list of matching winner rules"""
        matching = self.__matchingRules(self.ruleset.winnerRules)
        for rule in matching:
            if (self.ruleset.limit and rule.score.limits >= 1) or 'absolute' in rule.options:
                return [UsedRule(rule)]
        return list(UsedRule(x) for x in matching)

    def __hasExclusiveRules(self):
        """if we have one, remove all others"""
        exclusive = list(x for x in self.usedRules if 'absolute' in x.rule.options)
        if exclusive:
            self.usedRules = exclusive
            self.score = self.__totalScore()
            self.won = self.__maybeMahjongg()
        return bool(exclusive)

    def __setLastTile(self):
        """sets lastTile, lastSource, announcements"""
        self.__announcements = b''
        self.__lastTile = None # not b'' because we want to cache the result, see lastTile property
        self.__lastSource = None
        parts = self.mjStr.split()
        for part in parts:
            if part[:1] == b'L':
                part = part[1:]
                if len(part) > 2:
                    self.__lastMeld = Meld(part[2:])
                self.__lastTile = Tile(part[:2])
            elif part[:1] == b'M':
                if len(part) > 3:
                    self.__lastSource = part[3:4]
                    if len(part) > 4:
                        self.__announcements = part[4:]
        if self.__lastTile:
            assert self.__lastTile in self.tileNames, 'lastTile %s is not in tiles %s, mjStr=%s' % (
                self.__lastTile, self.tileNames, self.mjStr)
            if self.__lastSource == 'k':
                assert self.tileNames.count(self.__lastTile.lower()) + \
                    self.tileNames.count(self.__lastTile.capitalize()) == 1, \
                    'Robbing kong: I cannot have lastTile %s more than once in %s' % (
                    self.__lastTile, ' '.join(self.tileNames))


    def __setLastMeld(self):
        """sets the shortest possible last meld. This is
        not yet the final choice, see __applyBestLastMeld"""
        self.__lastMeld = None
        if self.lastTile and self.won:
            if hasattr(self.mjRule.function, 'computeLastMelds'):
                self.__lastMelds = self.mjRule.function.computeLastMelds(self)
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
        for lastMeld in self.lastMelds:
            self.__lastMeld = lastMeld
            self.__applyRules()
            totals.append((self.won, self.__totalScore().total(), lastMeld))
        if any(x[0] for x in totals): # if any won
            totals = list(x[1:] for x in totals if x[0]) # remove lost variants
            totals = sorted(totals) # sort by totalScore
            maxScore = totals[-1][0]
            totals = list(x[1] for x in totals if x[0] == maxScore)
            # now we have a list of only lastMelds reaching maximum score
            if prev not in totals or self.__lastMeld not in totals:
                if Debug.explain and prev not in totals:
                    if not self.player or not self.player.game.belongsToRobotPlayer():
                        self.debug('replaced last meld %s with %s' % (prev, totals[0]))
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
        parts = self.string.split()
        mPart = b''
        rPart = b'R' + addTile
        unchanged = []
        for part in parts:
            if part[:1] in b'SBCDW':
                rPart += part
            elif part[:1] == b'R':
                rPart += part[1:]
            elif part[:1].lower() == b'm':
                mPart = part
            elif part[:1] == b'L':
                pass
            else:
                unchanged.append(part)
        # combine all parts about hidden tiles plus the new one to one part
        # because something like DrDrS8S9 plus S7 will have to be reordered
        # anyway
        # set the "won" flag M
        parts = unchanged
        parts.extend([rPart, mPart.capitalize(), b'L' + addTile])
        return Hand(self, b' '.join(parts))

    def __sub__(self, subtractTile):
        """returns a copy of self minus subtractTiles. Case of subtractTile (hidden
        or exposed) is ignored. If the tile is part of a declared meld, that meld
        will be reduced and moved to the undeclared tiles.
        Exposed melds of length<3 will also be hidden."""
        # pylint: disable=too-many-branches
        # If lastMeld is given, it must be first in the list. Next try undeclared melds, then declared melds
        newMelds = MeldList(x for x in self.melds if not x.isDeclared)
        newMelds.extend(sorted((x for x in self.melds if x.isDeclared), key=lambda x: (x != self.lastMeld, x.key)))
        rest = TileList()
        boni = MeldList(sorted(self.bonusMelds))
        if subtractTile.isBonus:
            for idx, meld in enumerate(boni):
                if subtractTile == meld[0]:
                    del boni[idx]
                    break
        else:
            for meld in newMelds[:]:
                if subtractTile.lower() in meld:
                    restTiles = meld.without(subtractTile.lower())
                    newMelds.remove(meld)
                    rest.extend(restTiles.toUpper())
                    break
                if subtractTile.upper() in meld:
                    restTiles = meld.without(subtractTile.upper())
                    newMelds.remove(meld)
                    rest.extend(restTiles.toUpper())
                    break
        for meld in newMelds[:]:
            if len(meld) < 3:
                newMelds.remove(meld)
                meld = meld.toUpper()
                rest.extend(meld)
        mjStr = self.mjStr
        if self.lastTile == subtractTile:
            parts = mjStr.split()
            newParts = []
            for idx, part in enumerate(parts):
                if part[:1] == b'M':
                    part = b'm' + part[1:]
                    if len(part) > 3 and part[3:4] == b'k':
                        part = part[:3]
                elif part[:1] == b'L':
                    continue
                newParts.append(part)
            mjStr = b' '.join(newParts)
        rest = b'R' + bytes(rest) if rest else b''
        newString = b' '.join(bytes(x) for x in (newMelds, rest, boni, mjStr))
        return Hand(self, newString, self.computedRules)

    def manualRuleMayApply(self, rule):
        """returns True if rule has selectable() and applies to this hand"""
        if self.won and rule in self.ruleset.loserRules:
            return False
        if not self.won and rule in self.ruleset.winnerRules:
            return False
        return rule.selectable(self) or rule.appliesToHand(self) # needed for activated rules

    def callingHands(self, wanted=1, excludeTile=None, mustBeAvailable=False):
        """the hand is calling if it only needs one tile for mah jongg.
        Returns up to 'wanted' hands which would only need one tile.
        If mustBeAvailable is True, make sure the missing tile might still
        be available.
        """
        if not mustBeAvailable:
            cacheKey = (wanted, excludeTile)
            if cacheKey in self.__callingHands:
                return self.__callingHands[cacheKey]
        result = []
        string = self.string
        if b' x' in string or self.lenOffset:
            return result
        candidates = []
        for rule in self.ruleset.mjRules:
            if hasattr(rule, 'winningTileCandidates'):
                candidates.extend(x.capitalize() for x in rule.winningTileCandidates(self))
        # sort only for reproducibility
        candidates = sorted(set(candidates))
        for tileName in candidates:
            if excludeTile and tileName == excludeTile.capitalize():
                continue
            if mustBeAvailable and not self.player.tileAvailable(tileName, self):
                continue
            hand = self + tileName
            if hand.won:
                result.append(hand)
                if len(result) == wanted:
                    break
        if not mustBeAvailable:
            self.__callingHands[cacheKey] = result
        return result

    def __maybeMahjongg(self):
        """check if this is a mah jongg hand.
        Return a sorted list of matching MJ rules, highest
        total first"""
        if not self.won:
            return []
        if self.lenOffset != 1:
            return []
        matchingMJRules = [x for x in self.ruleset.mjRules if x.appliesToHand(self)]
        if self.robbedTile and self.robbedTile.istitle():
            # Millington 58: robbing hidden kong is only allowed for 13 orphans
            matchingMJRules = [x for x in matchingMJRules if 'mayrobhiddenkong' in x.options]
        return sorted(matchingMJRules, key=lambda x: -x.score.total())

# TODO: get rid of __split, the mjRules should do that if they need it at all
# only __split at end of Hand.__init__, now we do it twice for winning hands
    def __split(self, rest):
        """work hard to always return the variant with the highest Mah Jongg value.
        Adds melds to self.melds.
        only one special mjRule may try to rearrange melds.
        A rest will be rearranged by standard rules."""
        for tile in rest[:]:
            if not tile.isKnown:
                rest.remove(tile)
                self.melds.append(Meld(tile))
        if not rest:
            return
        arrangements = []
        for mjRule in self.ruleset.mjRules:
            func = mjRule.function
            if func.__class__.__name__ == 'StandardMahJongg':
                stdMJ = func
        if self.mjRule:
            rules = [self.mjRule]
        else:
            rules = self.ruleset.mjRules
        for mjRule in rules:
            func = mjRule.function
            if func != stdMJ and hasattr(func, 'rearrange'):
                if ((self.lenOffset == 1 and func.appliesToHand(self))
                        or (self.lenOffset < 1 and func.shouldTry(self))):
                    melds, pairs = func.rearrange(self, rest[:])
                    if melds:
                        arrangements.append((mjRule, melds, pairs))
        if arrangements:
# TODO: we should know for each arrangement how many tiles for MJ are still needed.
# If len(pairs) == 4, one or up to three might be needed. That would allow for better AI.
# TODO: if hand just completed and we did not win, only try stdmj
            arrangement = sorted(arrangements, key=lambda x: len(x[2]))[0]
            self.melds.extend(arrangement[1])
            self.melds.extend([Meld(x) for x in arrangement[2]])
        else:
            # stdMJ is special because it might build more than one pair
            # the other special hands would put that into the rest
            # if the above TODO is done, stdMJ does not have to be special anymore
            if rest:
                melds, _ = stdMJ.rearrange(self, rest[:])
                self.melds.extend(melds)
        assert sum(len(x) for x in self.melds) == len(self.tileNames), '%s != %s' % (
            self.melds, self.tileNames)

    def __matchingRules(self, rules):
        """return all matching rules for this hand"""
        return list(rule for rule in rules if rule.appliesToHand(self))

    def __applyMeldRules(self):
        """apply all rules for single melds"""
        for rule in self.ruleset.meldRules:
            for meld in self.melds + self.bonusMelds:
                if rule.appliesToMeld(self, meld):
                    self.usedRules.append(UsedRule(rule, meld))

    def __applyHandRules(self):
        """apply all hand rules for both winners and losers"""
        for rule in self.ruleset.handRules:
            if rule.appliesToHand(self):
                self.usedRules.append(UsedRule(rule))

    def __totalScore(self):
        """use all used rules to compute the score"""
        pointsTotal = Score(ruleset=self.ruleset)
        maxLimit = 0.0
        maxRule = None
        for usedRule in self.usedRules:
            score = usedRule.rule.score
            if score.limits:
                # we assume that a hand never gets different limits combined
                maxLimit = max(maxLimit, score.limits)
                maxRule = usedRule
            else:
                pointsTotal += score
        if maxLimit:
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
        if self.player:
            usedRules = self.player.sortRulesByX(self.usedRules)
        else:
            # scoringtest
            usedRules = self.usedRules
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
        return ' '.join(str(x) for x in (self.melds, self.bonusMelds, self.mjStr)).replace('  ', ' ')

    def __repr__(self):
        """the default representation"""
        return 'Hand(%s)' % str(self)
