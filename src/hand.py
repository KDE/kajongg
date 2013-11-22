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
from tile import Tile, elements, Values, TileList, Byteset
from meld import Meld, meldsContent
from rule import Score, Ruleset
from common import Debug

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
    """represent the hand to be evaluated"""

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
        Hand.hits = 0
        Hand.misses = 0

    @staticmethod
    def cached(ruleset, string, computedRules=None, robbedTile=None):
        """since a Hand instance is never changed, we can use a cache"""
        if computedRules is not None and not isinstance(computedRules, list):
            computedRules = list([computedRules])
        cRuleHash = '&&'.join([rule.name for rule in computedRules]) if computedRules else 'None'
        if isinstance(ruleset, Hand):
            cacheId = id(ruleset.player or ruleset.ruleset)
        else:
            cacheId = id(ruleset)
        cacheKey = hash((cacheId, string, robbedTile, cRuleHash))
        cache = Hand.cache
        if cacheKey in cache:
            if cache[cacheKey] is None:
                raise Exception('recursion: Hand calls itself for same content')
            Hand.hits += 1
            return cache[cacheKey]
        Hand.misses += 1
        cache[cacheKey] = None
        result = Hand(ruleset, string,
            computedRules=computedRules, robbedTile=robbedTile)
        cache[cacheKey] = result
        return result

    def __init__(self, ruleset, string, computedRules=None, robbedTile=None):
        """evaluate string using ruleset. rules are to be applied in any case.
        ruleset can be Hand, Game or Ruleset."""
        # silence pylint. This method is time critical, so do not split it into smaller methods
        # pylint: disable=too-many-instance-attributes,too-many-branches,too-many-statements
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
        self.mjStr = b''
        self.mjRule = None
        self.ownWind = None
        self.roundWind = None
        tileStrings = []
        mjStrings = []
        haveM = False
        splits = self.string.split()
        for part in splits:
            partId = part[:1]
            if partId in b'Mmx':
                haveM = True
                self.ownWind = part[1:2]
                self.roundWind = part[2:3]
                mjStrings.append(part)
                self.__won = partId == b'M'
            elif partId == b'L':
                if len(part[1:]) > 8:
                    raise Exception('last tile cannot complete a kang:' + self.string)
                mjStrings.append(part)
            else:
                tileStrings.append(part)

        if not haveM:
            raise Exception('Hand got string without mMx: %s', self.string)
        self.mjStr = b' '.join(mjStrings)
        self.__lastTile = self.__lastSource = self.__announcements = b''
        self.__lastMeld = 0
        self.__lastMelds = []
        self.hiddenMelds = []
        self.declaredMelds = []
        self.melds = []
        self.bonusMelds, tileStrings = self.__separateBonusMelds(tileStrings)
        tileString = b' '.join(tileStrings)
        self.tileNames = TileList(tileString.replace(b' ', b'').replace(b'R', b''))
        self.tileNames.sort()
        self.values = Values(x.value for x in self.tileNames)
        self.suits = set(x.lowerGroup for x in self.tileNames)
        self.lenOffset = self.__computeLenOffset(tileString)
        self.dragonMelds, self.windMelds = self.__computeDragonWindMelds(tileString)
        self.__separateMelds(tileString)
        self.hiddenMelds.sort()
        self.tilesInHand = sum(self.hiddenMelds, [])
        for tile in self.tilesInHand:
            assert isinstance(tile, Tile), self.tilesInHand
        self.sortedMeldsContent = meldsContent(self.melds)
        if self.bonusMelds:
            self.sortedMeldsContent += b' ' + meldsContent(self.bonusMelds)

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
        if b'Xy' in self.string:
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
        self.__lastTile = None
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
                self.__lastMelds = [self.__lastMeld]

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

    def __sub__(self, tiles):
        """returns a copy of self minus tiles. Case of tiles (hidden
        or exposed) is ignored. If the tile is not hidden
        but found in an exposed meld, this meld will be hidden with
        the tile removed from it. Exposed melds of length<3 will also
        be hidden."""
        # pylint: disable=too-many-branches
        if not isinstance(tiles, list):
            tiles = list([tiles])
        hidden = b'R' + b''.join(self.tilesInHand)
        # exposed is a deep copy of declaredMelds. If lastMeld is given, it
        # must be first in the list.
        exposed = self.declaredMelds[:]
        exposed = sorted(exposed, key=lambda x: (x != self.lastMeld, x.key))
        boni = sorted(self.bonusMelds)
        for tile in tiles:
            assert isinstance(tile, Tile), tiles
            if bytes(tile.upper()) in hidden:
                hidden = hidden.replace(bytes(tile.upper()), b'', 1)
            elif tile.isBonus:
                for idx, meld in enumerate(boni):
                    if tile == meld[0]:
                        del boni[idx]
                        break
            else:
                for idx, meld in enumerate(exposed):
                    if tile.lower() in meld:
                        meld = meld.without(tile.lower())
                        del exposed[idx]
                        meld = meld.toUpper()
                        hidden += bytes(meld)
                        break
        for idx, meld in enumerate(exposed):
            if len(meld) < 3:
                del exposed[idx]
                meld = meld.toUpper()
                hidden += bytes(meld)
        mjStr = self.mjStr
        if self.lastTile in tiles:
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
        newString = b' '.join([hidden, meldsContent(exposed), meldsContent(boni), mjStr])
        return Hand.cached(self, newString, self.computedRules)

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
        result = []
        string = self.string
        if b' x' in string or self.lenOffset:
            return result
        for rule in self.ruleset.mjRules:
            # sort only for reproducibility
            if not hasattr(rule, 'winningTileCandidates'):
                raise Exception('rule %s, code=%s has no winningTileCandidates' % (
                    rule.name, rule.function))
            candidates = sorted(x.capitalize() for x in rule.winningTileCandidates(self))
            for tileName in candidates:
                if excludeTile and tileName == excludeTile.capitalize():
                    continue
                if mustBeAvailable and not self.player.tileAvailable(tileName, self):
                    continue
                hand = self.picking(tileName)
                if hand.won:
                    result.append(hand)
                    if len(result) == wanted:
                        break
            if len(result) == wanted:
                break
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

    @staticmethod
    def splitMelds(rest):
        """split rest into melds as good as possible"""
        melds = []
        groups = {}
        for group in Byteset(b'DWSBC'):
            groups[group] = TileList(x for x in rest if x.group == group)
        for group in Byteset(b'DWSBC'):
            tiles = groups[group]
            for tile in tiles[:]:
                if tiles.count(tile) >= 3:
                    melds.append(Meld([tile, tile, tile]))
                    for _ in range(3):
                        tiles.remove(tile)
        for group in Byteset(b'SBC'):
            tiles = groups[group]
            for tile in tiles[:]:
                tile2 = tile.nextForChow()
                tile3 = tile2.nextForChow()
                while {tile, tile2, tile3} <= set(tiles):
                    melds.append(Meld([tile, tile2, tile3]))
                    tiles.remove(tile)
                    tiles.remove(tile2)
                    tiles.remove(tile3)
        for group in Byteset(b'DWSBC'):
            tiles = groups[group]
            for tile in tiles[:]:
                while tiles.count(tile) == 2:
                    melds.append(Meld([tile, tile]))
                    tiles.remove(tile)
                    tiles.remove(tile)
            for tile in tiles:
                melds.append(Meld(tile))
        melds.extend(Meld(x) for x in rest if x == b'Xy')
        return sorted(melds)

    def __recurse(self, cVariants, foundMelds, rest, maxPairs, group):
        """build the variants recursively"""
        melds = []
        for value in set(rest):
            if rest.count(value) == 3:
                melds.append([value] * 3)
            elif rest.count(value) == 2:
                melds.append([value] * 2)
            if rest.count(value + 1) and rest.count(value + 2):
                melds.append([value, value + 1, value + 2])
        pairsFound = sum(len(x) == 2 for x in foundMelds)
        for meld in (m for m in melds if len(m) !=2 or pairsFound < maxPairs):
            restCopy = rest[:]
            for value in meld:
                restCopy.remove(value)
            newMelds = foundMelds[:]
            newMelds.append(meld)
            if restCopy:
                self.__recurse(cVariants, newMelds, restCopy, maxPairs, group)
            else:
                for idx, newMeld in enumerate(newMelds):
                    newMelds[idx] = b''.join(Tile(group, x) for x in newMeld)
                cVariants.append(b' '.join(sorted(newMelds )))

    def genVariants(self, original0, maxPairs=1):
        """generates all possible meld variants out of original
        where original is a list of tile values like ['1','1','2']"""
        group = original0[0].group
        original = [ord(x.value) for x in original0]
        cVariants = []
        self.__recurse(cVariants, [], original, maxPairs, group)
        gVariants = []
        for cVariant in set(cVariants):
            melds = [Meld(x) for x in cVariant.split()]
            gVariants.append(melds)
        if not gVariants:
            gVariants.append(self.splitMelds(original0)) # fallback: nothing useful found
        return gVariants

# TODO: get rid of __split, the mjRules should do that if they need it at all
# only __split at end of Hand.__init__, now we do it twice for winning hands
    def __split(self, rest):
        """work hard to always return the variant with the highest Mah Jongg value.
        Adds melds to self.melds.
        only one special mjRule may try to rearrange melds.
        A rest will be rearranged by standard rules."""
        if b'Xy' in rest:
            # hidden tiles of other players:
            self.melds.extend(self.splitMelds(rest))
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
            melds, _ = stdMJ.rearrange(self, rest[:])
            self.melds.extend(melds)
        assert sum(len(x) for x in self.melds) == len(self.tileNames), '%s != %s' % (
            meldsContent(self.melds), self.tileNames)

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

    def __computeLenOffset(self, tileString):
        """lenOffset is <0 for short hand, 0 for correct calling hand, >0 for long hand.
        Of course ignoring bonus tiles.
        if there are no kongs, 13 tiles will return 0"""
        result = len(self.tileNames) - 13
        for split in tileString.split():
            if split[:1] != b'R' and len(split) == 8:
                if Meld(split).isKong:
                    result -= 1
        return result

    @staticmethod
    def __computeDragonWindMelds(tileString):
        """returns lists with melds containing all (even single)
        dragons respective winds"""
        dragonMelds = []
        windMelds = []
        for split in tileString.split():
            if split[:1] == b'R':
                pairs = TileList(split[1:])
                for lst, tiles in ((windMelds, elements.wINDS), (dragonMelds, elements.dRAGONS)):
                    for tile in tiles:
                        count = pairs.count(tile)
                        if count:
                            lst.append(Meld([tile] * count))
            elif split[:1] in b'dD':
                dragonMelds.append(Meld(split))
            elif split[:1] in b'wW':
                windMelds.append(Meld(split))
        return dragonMelds, windMelds

    @staticmethod
    def __separateBonusMelds(tileStrings):
        """keep them separate. One meld per bonus tile. Others depend on that."""
        bonusMelds = []
        for tileString in tileStrings[:]:
            if len(tileString) == 2:
                tile = Tile(tileString)
                if tile.isBonus:
                    bonusMelds.append(Meld(tile))
                    tileStrings.remove(tileString)
        return bonusMelds, tileStrings

    def __separateMelds(self, tileString):
        """build a meld list from the hand string"""
        # no matter how the tiles are grouped make a single
        # meld for every bonus tile
        # we need to remove spaces from the hand string first
        # for building only pairs with length 2
        splits = tileString.split()
        rest = []
        for split in splits:
            if split[:1] == b'R':
                rest = TileList(split[1:])
            else:
                meld = Meld(split)
                self.melds.append(meld)
                self.declaredMelds.append(meld)
        if rest:
            self.__split(sorted(rest))
        self.melds.sort()
        self.__categorizeMelds()

    def picking(self, tileName):
        """returns a new Hand built from this one plus tileName"""
        assert tileName.istitle(), 'tileName %s should be title:' % tileName
        parts = self.string.split()
        mPart = b''
        rPart = b'R' + tileName
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
        parts.extend([rPart, mPart.capitalize(), b'L' + tileName])
        return Hand.cached(self, b' '.join(parts))

    def __categorizeMelds(self):
        """categorize: hidden, declared"""
        self.hiddenMelds = []
        self.declaredMelds = []
        for meld in self.melds:
            if not meld.isExposed and not meld.isKong:
                self.hiddenMelds.append(meld)
            else:
                self.declaredMelds.append(meld)

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
        for meld in self.dragonMelds + self.windMelds:
            for rule in self.ruleset.doublingMeldRules:
                if rule.appliesToMeld(self, meld):
                    result += rule.score.doubles
        for rule in self.ruleset.doublingHandRules:
            if rule.appliesToHand(self):
                result += rule.score.doubles
        return result

    def __str__(self):
        """hand as a string"""
        return ' '.join([str(self.sortedMeldsContent), str(self.mjStr)])

    def __repr__(self):
        """the default representation"""
        return 'Hand(%s)' % str(self)
