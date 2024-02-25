# -*- coding: utf-8 -*-

"""Copyright (C) 2009-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0




Read the user manual for a description of the interface to this scoring engine
"""

from itertools import chain
import weakref
from hashlib import md5

from log import dbgIndent
from tile import Tile, TileList, TileTuple
from tilesource import TileSource
from meld import Meld, MeldList
from rule import Score, UsedRule
from common import Debug, ReprMixin, Fmt, fmt
from util import callers
from message import Message


class Hand(ReprMixin):

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
    was used for rearranging the hiden tiles to melds.

    suits include dragons and winds."""

    # pylint: disable=too-many-instance-attributes

    indent = 0
    class __NotWon(UserWarning):  # pylint: disable=invalid-name

        """should be won but is not a winning hand"""

    def __new__(cls, player, string=None, melds=None, unusedTiles=None, bonusTiles=None,  # pylint: disable=too-many-arguments
            lastSource=None, lastTile=None, lastMeld=None, announcements=None, prevHand=None):
        # pylint: disable=unused-argument
        """since a Hand instance is never changed, we can use a cache"""
        if string:
            cache = player.handCache
            cacheKey = string
            if cacheKey in cache:
                result = cache[cacheKey]
                player.cacheHits += 1
                result.is_from_cache = True
                return result
            player.cacheMisses += 1
            result = object.__new__(cls)
            cache[cacheKey] = result
        else:
            result = object.__new__(cls)
        result.is_from_cache = False
        return result

    def __init__(self, player, string=None, melds=None, unusedTiles=None, bonusTiles=None,  # pylint: disable=too-many-arguments
            lastSource=None, lastTile=None, lastMeld=None, announcements=None, prevHand=None):
        """evaluate string for player. rules are to be applied in any case"""

        # pylint: disable=too-many-branches, too-many-statements
        self.is_from_cache:bool
        if self.is_from_cache:
            return

        # shortcuts for speed:
        self._player = weakref.ref(player)
        assert player.game
        self.ruleset = player.game.ruleset
        self.__robbedTile = Tile.none
        self.prevHand = prevHand
        self.__won = None
        self.__score = None
        self.__callingHands = None
        self.__mjRule = None
        self.ruleCache = {}
        self.__lastTile = Tile.none
        self.__lastSource = TileSource.Unknown
        self.__announcements = set()
        self.__lastMeld = 0
        self.__lastMelds = MeldList()
        self.tiles = None
        self.melds = MeldList()
        self.bonusMelds = MeldList()
        self.usedRules = []
        self.unusedTiles = TileList()
        self.__arranged = None

        if string:
            self.__parseString(string)
        else:
            self.melds = melds or MeldList()
            if unusedTiles is not None:
                self.unusedTiles.extend(unusedTiles)  # FIXME: assign
            if bonusTiles:
                self.bonusMelds = MeldList(Meld(x) for x in bonusTiles)
            self.__lastSource = lastSource or TileSource.Unknown
            if lastTile:
                self.__lastTile= lastTile
            if lastMeld:
                self.__lastMeld= lastMeld
            self.__announcements = announcements or set()
            self.tiles = TileTuple(chain(self.melds, self.unusedTiles))
            string = self.newString()
        self.string = string

        self.__precompute()

        self.__won = self.lenOffset == 1 and player.mayWin

        if Debug.hand or (Debug.mahJongg and self.lenOffset == 1):
            self.debug(fmt('{callers}',
                           callers=callers(exclude=['__init__'])))
            Hand.indent += 1
            self.debug('New Hand {} lenOffset={}'.format(string, self.lenOffset))

        try:
            self.__arrange()
            self.__calculate()
            self.__arranged = True
        except Hand.__NotWon as notwon:
            if Debug.mahJongg:
                self.debug(fmt(str(notwon)))
            self.__won = False
            self.__score = Score()
        finally:
            self._fixed = True
            if Debug.hand or (Debug.mahJongg and self.lenOffset == 1):
                self.debug('Fixing {} {}{}'.format(self, 'won ' if self.won else '', self.score))
            Hand.indent -= 1

    def __parseString(self, inString):
        """parse the string passed to Hand()"""
        tileStrings = []
        for part in inString.split():
            partId = part[0]
            if partId == 'm':
                if len(part) > 1:
                    try:
                        self.__lastSource = TileSource.byChar[part[1]]
                    except KeyError as _:
                        raise KeyError('{} has unknown lastTile {}'.format(inString, part[1])) from _
                    if len(part) > 2:
                        self.__announcements = set(part[2])
            elif partId == 'L':
                if len(part[1:]) > 8:
                    raise ValueError(
                        'last tile cannot complete a kang:' + inString)
                if len(part) > 3:
                    self.__lastMeld = Meld(part[3:])
                self.__lastTile = Tile(part[1:3])
            else:
                if part != 'R':
                    tileStrings.append(part)
        self.bonusMelds, tileStrings = self.__separateBonusMelds(tileStrings)
        tileString = ' '.join(tileStrings)
        self.tiles = TileList(tileString.replace(' ', '').replace('R', ''))
        for part in tileStrings[:]:
            if part[:1] != 'R':
                self.melds.append(Meld(part))
                tileStrings.remove(part)
        assert len(tileStrings) < 2, tileStrings
        if tileStrings:
            self.unusedTiles.extend(TileList(tileStrings[0][1:]))

    def __precompute(self):
        """precompute commonly used things"""
        self.tiles = self.tiles.sorted()

        self.values = tuple(x.value for x in self.tiles)
        self.suits = {x.lowerGroup for x in self.tiles}
        self.declaredMelds = MeldList(x for x in self.melds if x.isDeclared)
        declaredTiles = TileTuple(self.declaredMelds)
        self.tilesInHand = TileList(x for x in self.tiles
                                    if x not in declaredTiles)
        self.lenOffset = (len(self.tiles) - 13
                          - sum(x.isKong for x in self.melds))

        last = self.__lastTile
        if last.isKnown and not last.isBonus:
#            print('lastTile %s hand.tiles %s, string=%s hand %s' % (last, self.tiles, self.string, str(self)))
            assert last in self.tiles, \
                'lastTile %s is not in hand.tiles %s, hand %s' % (last, self.tiles, str(self))
            if self.__lastSource is TileSource.RobbedKong:
                assert self.tiles.count(last.exposed) + \
                    self.tiles.count(last.concealed) == 1, (
                        'Robbing kong: I cannot have '
                        'lastTile %s more than once in %s' % (
                            last, ' '.join(self.tiles)))
        self.newStr = self.newString()

    @property
    def arranged(self):
        """readonly"""
        return self.__arranged

    @property
    def player(self):
        """weakref"""
        result = self._player()
        assert result
        return result

    @property
    def ownWind(self):
        """for easier usage"""
        return self.player.wind

    @property
    def roundWind(self):
        """for easier usage"""
        assert self.player.game
        return self.player.game.roundWind

    def __calculate(self):
        """apply rules, calculate score"""
        # TODO: in __init__: self.__score == self.__calculate()
        assert not self.unusedTiles, (
            'Hand.__calculate expects there to be no unused tiles: %s' % self)
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
        return self.__lastTile

    @property
    def lastSource(self):
        """compute and cache, readonly"""
        return self.__lastSource

    @property
    def announcements(self):
        """compute and cache, readonly"""
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
        idPrefix = Fmt.num_encode(hash(self))
        if self.prevHand:
            idPrefix += '<{}'.format(Fmt.num_encode(hash(self.prevHand)))
        idPrefix = 'Hand({})'.format(idPrefix)
        assert self.player.game
        self.player.game.debug(' '.join([dbgIndent(self, self.prevHand), idPrefix, msg]))

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
        if self.string:
            if Tile.unknownStr in self.string:
                return
        else:
# FIXME: try to do this also for string
            if Tile.unknown in self.tiles:
                return
        if self.__won:
            matchingMJRules = self.__maybeMahjongg()
            if not matchingMJRules:
                self.__score = Score()
                raise Hand.__NotWon('no matching MJ Rule')
            self.__mjRule = matchingMJRules[0]
            self.usedRules.append(UsedRule(self.__mjRule))
            self.usedRules.extend(self.matchingWinnerRules())
            self.__score = self.__totalScore()
        else:  # not self.won
            loserRules = self.__matchingRules(self.ruleset.loserRules)
            if loserRules:
                self.usedRules.extend(UsedRule(x) for x in loserRules)
                self.__score = self.__totalScore()
        self.__checkHasExclusiveRules()

    def matchingWinnerRules(self):
        """return a list of matching winner rules"""
        matching = [UsedRule(x) for x in self.__matchingRules(self.ruleset.winnerRules)]
        limitRule = self.maxLimitRule(matching)
        return [limitRule] if limitRule else matching

    def __checkHasExclusiveRules(self):
        """if we have one, remove all others"""
        exclusive = [x for x in self.usedRules if 'absolute' in x.rule.options]
        if exclusive:
            self.usedRules = exclusive
            self.__score = self.__totalScore()
            if self.__won and not bool(self.__maybeMahjongg()):
                raise Hand.__NotWon(fmt('exclusive rule {exclusive} does not win'))

    def __setLastMeld(self):
        """set the shortest possible last meld. This is
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
            bestLastMelds = [x[1] for x in totals if x[0] == maxScore]
            # now we have a list of only lastMelds reaching maximum score
            if prev not in bestLastMelds or self.__lastMeld not in bestLastMelds:
                if Debug.explain and prev not in bestLastMelds:
                    assert self.player.game
                    if not self.player.game.belongsToRobotPlayer():
                        self.debug(fmt(
                            'replaced last meld {prev} with {bestLastMelds[0]}'))
                self.__lastMeld = bestLastMelds[0]
                self.__applyRules()

    def chancesToWin(self):
        """count the physical tiles that make us win and still seem available"""
        assert self.lenOffset == 0
        result = []
        for completedHand in self.callingHands:
            assert completedHand.lastTile
            result.extend(
                [completedHand.lastTile] *
                (self.player.tileAvailable(completedHand.lastTile, self)))
        return result

    def assertEqual(self, other):
        """raise assertion if not equal with detailled info"""
        assert self.melds == other.melds, \
            'Melds in hands differ:{!r} != {!r}'.format(self.melds, other.melds)
        assert self.lastTile == other.lastTile, \
            'lastTile in hands differs:{} != {}'.format(self.lastTile, other.lastTile)
        assert self.lastMeld == other.lastMeld, \
            'lastMeld in hands differs:{} != {}'.format(self.lastMeld, other.lastMeld)
        assert self.newString() == other.newString(), \
            'newString() in hands differs:{} != {}'.format(self.newString(), other.newString())
        assert self.newStr == other.newStr, \
            'newStr in hands differs:{} != {}'.format(self.newStr, other.newStr)

    def newString(self, melds=1, unusedTiles=1, lastSource=1, announcements=1, lastTile=1, lastMeld=1):
        """create string representing a hand. Default is current Hand, but every part
        can be overridden or excluded by passing None"""
        if melds == 1:
            melds = chain(self.melds, self.bonusMelds)
        if unusedTiles== 1:
            unusedTiles = self.unusedTiles
        if lastSource == 1:
            lastSource = self.lastSource
        if announcements == 1:
            announcements = self.announcements
        if lastTile == 1:
            lastTile = self.lastTile
        if lastMeld == 1:
            lastMeld = self.__lastMeld
        parts = [str(x) for x in sorted(melds)]
        if unusedTiles:
            parts.append('R' + ''.join(str(x) for x in sorted(unusedTiles)))
        if lastSource or announcements:
            parts.append('m{}{}'.format(
                self.lastSource.char,
                ''.join(self.announcements)))
        if lastTile:
            parts.append('L{}{}'.format(lastTile, lastMeld if lastMeld else ''))
        return ' '.join(parts).strip()

    def __add__(self, addTile):
        """return a new Hand built from this one plus addTile"""
        assert addTile.isConcealed, 'addTile %s should be concealed:' % addTile
        # combine all parts about hidden tiles plus the new one to one part
        # because something like DrDrS8S9 plus S7 will have to be reordered
        # anyway
        newString = self.newString(
            melds=chain(self.declaredMelds, self.bonusMelds),
            unusedTiles=self.tilesInHand + [addTile],
            lastSource=None,
            lastTile=addTile,
            lastMeld=None
            )
        return Hand(self.player, newString, prevHand=self)

    def __sub__(self, subtractTile):
        """return a copy of self minus subtractTiles.
        Case of subtractTile (hidden or exposed) is ignored.
        subtractTile must either be undeclared or part of
        lastMeld. Exposed melds of length<3 will be hidden."""
        # If lastMeld is given, it must be first in the list.
        # Next try undeclared melds, then declared melds
        assert self.lenOffset == 1, \
             f'lenOffset != 1: {self.lenOffset} for {self}'  # correct winner hand or long loser hand
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
                try:
                    declaredMelds.remove(lastMeld)
                except ValueError as _:
                    raise ValueError(
                        'lastMeld {} is not in declaredMelds {}, hand is: {}'.format(
                            lastMeld, declaredMelds, self)) from _
                tilesInHand.extend(lastMeld.concealed)
            tilesInHand.remove(subtractTile.concealed)
        for meld in declaredMelds[:]:
            if len(meld) < 3:
                declaredMelds.remove(meld)
                tilesInHand.extend(meld.concealed)
        # if we robbed a kong, remove that announcement
        mjPart = ''
        announcements = self.announcements - set('k')
        if announcements:
            mjPart = 'm.' + ''.join(announcements)
        rest = 'R' + str(tilesInHand)
        newString = ' '.join(str(x) for x in (
            declaredMelds, rest, boni, mjPart))
        return Hand(self.player, newString, prevHand=self)

    def manualRuleMayApply(self, rule):
        """return True if rule has selectable() and applies to this hand"""
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
        if self.lenOffset:
            return result
        candidates = []
        for rule in self.ruleset.mjRules:
            cand = rule.winningTileCandidates(self)
            if Debug.hand and cand:
                # Py2 and Py3 show sets differently
                candis = ''.join(str(x) for x in sorted(cand))
                self.debug('callingHands found {} for {}'.format(candis, rule))
            candidates.extend(x.concealed for x in cand)
        for tile in sorted(set(candidates)):
            if sum(x.exposed == tile.exposed for x in self.tiles) == 4:
                continue
            hand = self + tile
            if hand.won:
                result.append(hand)
        if Debug.hand:
            _hiderules = ', '.join({x.mjRule.name for x in result})
            if _hiderules:
                self.debug(fmt('Is calling {_hiderules}'))
        return result

    @property
    def robbedTile(self):
        """cache this here for use in rulecode"""
        if self.__robbedTile is Tile.unknown:
            self.__robbedTile = Tile.none
            assert self.player.game
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
                    self.debug(fmt('{callers} Found {matchingMJRules}',
                                   callers=callers()))
                return result
        return None

    def __arrangements(self):
        """find all legal arrangements.
        Returns a list of tuples with the mjRule and a list of concealed melds"""
        self.unusedTiles.sort()
        result = []
        stdMJ = self.ruleset.standardMJRule
        assert stdMJ
        if self.mjRule:
            rules = [self.mjRule]
        else:
            rules = self.ruleset.mjRules
        for mjRule in rules:
            if ((self.lenOffset == 1 and mjRule.appliesToHand(self))
                    or (self.lenOffset < 1 and mjRule.shouldTry(self))):
                if self.unusedTiles:
                    unused = TileList(Tile(x) for x in self.unusedTiles)
                    for melds, rest2 in mjRule.rearrange(self, unused):
                        if rest2:
                            melds = list(melds)
                            restMelds, _ = next(
                                stdMJ.rearrange(self, rest2[:]))
                            melds.extend(restMelds)
                        result.append((mjRule, melds))
        if not result:
            result.extend(
                (stdMJ, x[0])
                for x in stdMJ.rearrange(self, self.unusedTiles[:]))
        return result

    def __arrange(self):
        """work hard to always return the variant with the highest Mah Jongg value."""
        if any(not x.isKnown for x in self.unusedTiles):
            melds, rest = divmod(len(self.unusedTiles), 3)
            self.melds.extend([Tile.unknown.pung] * melds)
            if rest:
                self.melds.append(Meld(Tile.unknown * rest))
            self.unusedTiles = []
        if not self.unusedTiles:
            self.melds.sort()
            mjRules = self.__maybeMahjongg()
            if self.won:
                if not mjRules:
                    # how could this ever happen?
                    raise Hand.__NotWon('Long Hand with no unused tiles')
                self.mjRule = mjRules[0]
            return
        wonHands = []
        lostHands = []
        for mjRule, melds in self.__arrangements():
            allMelds = self.melds[:] + list(melds)
            lastTile = self.lastTile
            if self.lastSource and self.lastSource.isDiscarded:
                lastTile = lastTile.exposed
                lastMelds = sorted(
                    (x for x in allMelds if not x.isDeclared and lastTile.concealed in x),
                    key=lambda x: len(x)) # pylint: disable=unnecessary-lambda
                if lastMelds:
                    allMelds.remove(lastMelds[0])
                    allMelds.append(lastMelds[0].exposed)
            _ = self.newString(
                chain(allMelds, self.bonusMelds),
                unusedTiles=None, lastTile=lastTile, lastMeld=None)
            tryHand = Hand(self.player, _, prevHand=self)
            if tryHand.won:
                tryHand.mjRule = mjRule
                wonHands.append((mjRule, melds, tryHand))
            else:
                lostHands.append((mjRule, melds, tryHand))
        # we prefer a won Hand even if a lost Hand might have a higher score
        tryHands = wonHands if wonHands else lostHands
        bestRule, bestVariant, _ = max(tryHands, key=lambda x: x[2])
        if wonHands:
            self.mjRule = bestRule
        self.melds.extend(bestVariant)
        self.melds.sort()
        self.unusedTiles = []
        self.ruleCache.clear()

    def __gt__(self, other):
        """compares hand values"""
        assert self.player == other.player
        if not other.arranged:
            return True
        if self.won and not (other.arranged and other.won):
            return True
        if not (self.arranged and self.won) and other.won:
            return False
        _ = self.player.intelligence
        return _.handValue(self) > _.handValue(other)

    def __lt__(self, other):
        """compares hand values"""
        return other.__gt__(self)

    def __eq__(self, other):
        """compares hand values"""
        assert self.__class__ is other.__class__, \
            'Hands have different classes:{} and {}'.format(self.__class__, other.__class__)
        assert self.player == other.player
        return self.newStr == other.newStr

    def __ne__(self, other):
        """compares hand values"""
        assert self.__class__ is other.__class__
        assert self.player == other.player
        return self.newStr != other.newStr

    def __matchingRules(self, rules):
        """return all matching rules for this hand"""
        return [rule for rule in rules if rule.appliesToHand(self)]

    @staticmethod
    def maxLimitRule(usedRules):
        """return the rule with the highest limit score or None"""
        result = None
        maxLimit = 0
        usedRules = [x for x in usedRules if x.rule.score.limits]
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
        return self.newString()

    def __hash__(self):
        """used for debug logging to identify the hand"""
        if not hasattr(self, 'string'):
            return 0
        md5sum = md5()
        md5sum.update(self.player.name.encode('utf-8'))
        _ = self.string if self.string else str(self)
        md5sum.update(_.encode())
        digest = md5sum.digest()
        assert len(digest) == 16
        result = 0
        for part in range(4):
            result = (result << 8) + digest[part]
        return result
