# -*- coding: utf-8 -*-

"""Copyright (C) 2009-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only




Read the user manual for a description of the interface to this scoring engine
"""

from itertools import chain
import weakref
from hashlib import md5
from typing import List, Optional, TYPE_CHECKING, Set, Dict, Tuple, Type, Any, Union

from log import dbgIndent
from tile import Tile, TileList, TileTuple, Meld, MeldList
from tilesource import TileSource
from rule import Score, UsedRule
from common import Debug, ReprMixin, num_encode
from util import callers
from message import Message

if TYPE_CHECKING:
    from player import Player
    from tile import Tiles
    from wind import Wind
    from rule import Rule, Ruleset

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

    def __new__(cls, player:'Player', string:Optional[str]=None, melds:Optional[MeldList]=None,  # pylint: disable=too-many-arguments
            unusedTiles:Optional['Tiles']=None, bonusTiles:Optional['Tiles']=None,
            lastSource:Type[TileSource.SourceClass]=TileSource.Unknown, lastTile:Optional[Tile]=None,
            lastMeld:Optional[Meld]=None, announcements:Optional[Set[str]]=None,
            prevHand:Optional['Hand']=None) ->'Hand':
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

    def __init__(self, player:'Player', string:Optional[str]=None, melds:Optional[MeldList]=None,  # pylint: disable=too-many-arguments
            unusedTiles:Optional['Tiles']=None, bonusTiles:Optional['Tiles']=None,
            lastSource:Type[TileSource.SourceClass]=TileSource.Unknown, lastTile:Optional[Tile]=None,
            lastMeld:Optional[Meld]=None, announcements:Optional[Set[str]]=None,
            prevHand:Optional['Hand']=None) ->None:
        """evaluate string for player. rules are to be applied in any case"""

        # pylint: disable=too-many-statements
        self.is_from_cache:bool
        if self.is_from_cache:
            return

        # shortcuts for speed:
        self._player = weakref.ref(player)
        assert player.game
        self.ruleset:'Ruleset' = player.game.ruleset
        self.__robbedTile = Tile.none
        self.prevHand = prevHand
        self.__won = None
        self.__score:Score = Score()
        self.__callingHands:Optional[List['Hand']] = None
        self.__mjRule:Optional['Rule'] = None
        self.ruleCache:Dict[Tuple[Type, str], Any] = {}
        self.__lastTile = Tile.none
        self.__lastSource:Type[TileSource.SourceClass] = TileSource.Unknown
        self.__announcements:Set[str] = set()
        self.__lastMeld:Union[Meld, int, None] = 0
        self.__lastMelds = MeldList()
        self.tiles:TileList = TileList()
        self.melds:MeldList = MeldList()
        self.bonusMelds:MeldList = MeldList()
        self.usedRules:List[UsedRule] = []
        self.unusedTiles:TileList = TileList()
        self.__arranged:Optional[bool] = None
        self.lenOffset:int

        if string:
            self.__parseString(string)
        else:
            self.melds = melds or MeldList()
            if unusedTiles is not None:
                self.unusedTiles.extend(unusedTiles)  # FIXME: assign
            if bonusTiles:
                self.bonusMelds = MeldList(Meld(x) for x in bonusTiles)
            self.__lastSource = lastSource
            if lastTile:
                self.__lastTile = lastTile
            if lastMeld:
                self.__lastMeld= lastMeld
            self.__announcements = announcements or set()
            # FIXME: TileList() should suffice, but it does not yet resolve melds to tiles. TileTuple does.
            self.tiles = TileList(TileTuple(chain(self.melds, self.unusedTiles)))
            string = self.newString()
        self.string:str = string

        self.__precompute()

        self.__won = self.lenOffset == 1 and player.mayWin

        if Debug.hand or (Debug.mahJongg and self.lenOffset == 1):
            self.debug(f'{callers(exclude=["__init__"])}')
            Hand.indent += 1
            self.debug(f'New Hand {string} lenOffset={self.lenOffset}')

        try:
            self.__arrange()
            self.__calculate()
            self.__arranged = True
        except Hand.__NotWon as notwon:
            if Debug.mahJongg:
                self.debug(str(notwon))
            self.__won = False
            self.__score = Score()
        finally:
            self._fixed = True
            if Debug.hand or (Debug.mahJongg and self.lenOffset == 1):
                self.debug(f"Fixing {self} {'won ' if self.won else ''}{self.score}")
            Hand.indent -= 1

    def __parseString(self, inString:str) ->None:
        """parse the string passed to Hand()"""
        tileStrings = []
        for part in inString.split():
            partId = part[0]
            if partId == 'm':
                if len(part) > 1:
                    try:
                        self.__lastSource = TileSource.byChar[part[1]]
                    except KeyError as _:
                        raise KeyError(f'{inString} has unknown lastTile {part[1]}') from _
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

    def __precompute(self) ->None:
        """precompute commonly used things"""
        self.tiles = TileList(self.tiles.sorted())

        self.values = tuple(x.value for x in self.tiles)
        self.suits = {x.lowerGroup for x in self.tiles}
        self.declaredMelds = MeldList(x for x in self.melds if x.isDeclared)
        declaredTiles = TileTuple(self.declaredMelds)
        self.tilesInHand = TileList(x for x in self.tiles
                                    if x not in declaredTiles)
        self.lenOffset = (len(self.tiles) - self.ruleset.dealtTiles
                          - sum(x.isKong for x in self.melds))

        last = self.__lastTile
        if last and last.isKnown and not last.isBonus:
#            print('lastTile %s hand.tiles %s, string=%s hand %s' % (last, self.tiles, self.string, str(self)))
            assert last in self.tiles, \
                f'lastTile {last} is not in hand.tiles {self.tiles}, hand {str(self)}'
            if self.__lastSource is TileSource.RobbedKong:
                assert self.tiles.count(last.exposed) + \
                    self.tiles.count(last.concealed) == 1, (
                        f"Robbing kong: I cannot have lastTile {last} more than once in {' '.join(self.tiles)}")
        self.newStr = self.newString()

    @property
    def arranged(self) ->Optional[bool]:
        """readonly"""
        return self.__arranged

    @property
    def player(self) ->'Player':
        """weakref"""
        result = self._player()
        assert result
        return result

    @property
    def ownWind(self) ->'Wind':
        """for easier usage"""
        return self.player.wind

    @property
    def roundWind(self) ->'Wind':
        """for easier usage"""
        assert self.player.game
        return self.player.game.point.prevailing

    def __calculate(self) ->None:
        """apply rules, calculate score"""
        # TODO: in __init__: self.__score == self.__calculate()
        assert not self.unusedTiles, (
            f'Hand.__calculate expects there to be no unused tiles: {self}')
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
        if not self.__score:
            self.__score = Score()

    def hasTiles(self) ->bool:
        """tiles are assigned to this hand"""
        return bool(self.tiles or self.bonusMelds)

    @property
    def mjRule(self) ->Optional['Rule']:
        """getter"""
        return self.__mjRule

    @mjRule.setter
    def mjRule(self, value:'Rule') ->None:
        """changing mjRule must reset score"""
        if self.__mjRule != value:
            self.__mjRule = value
            self.__score = Score()

    @property
    def lastTile(self) -> Tile:
        """compute and cache, readonly"""
        return self.__lastTile

    @property
    def lastSource(self) ->Type[TileSource.SourceClass]:
        """compute and cache, readonly"""
        return self.__lastSource

    @property
    def announcements(self) ->Set[str]:
        """compute and cache, readonly"""
        return self.__announcements

    @property
    def score(self) ->Score:
        """calculate it first if not yet done"""
        if self.__score is None and self.__arranged is not None:
            self.__calculate()
        assert self.__score is not None, f'cannot calculate score for {self}'
        return self.__score

    @property
    def lastMeld(self) ->Optional[Meld]:
        """compute and cache, readonly"""
        if self.__lastMeld == 0:
            self.__setLastMeld()
        return self.__lastMeld  # type:ignore[return-value]

    @property
    def lastMelds(self) ->MeldList:
        """compute and cache, readonly"""
        if self.__lastMeld == 0:
            self.__setLastMeld()
        return self.__lastMelds

    @property
    def won(self) ->bool:
        """do we really have a winner hand?"""
        return bool(self.__won)

    def debug(self, msg:str) ->None:
        """try to use Game.debug so we get a nice prefix"""
        idPrefix = num_encode(hash(self))
        if self.prevHand:
            idPrefix += f'<{num_encode(hash(self.prevHand))}'
        idPrefix = f'Hand({idPrefix})'
        assert self.player.game
        self.player.game.debug(' '.join([dbgIndent(self, self.prevHand), idPrefix, msg]))

    def __applyRules(self) ->None:
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

    def matchingWinnerRules(self) ->List[UsedRule]:
        """return a list of matching winner rules"""
        matching = [UsedRule(x) for x in self.__matchingRules(self.ruleset.winnerRules)]
        limitRule = self.maxLimitRule(matching)
        return [limitRule] if limitRule else matching

    def __checkHasExclusiveRules(self) ->None:
        """if we have one, remove all others"""
        exclusive = [x for x in self.usedRules if 'absolute' in x.rule.options]
        if exclusive:
            self.usedRules = exclusive
            self.__score = self.__totalScore()
            if self.__won and not bool(self.__maybeMahjongg()):
                raise Hand.__NotWon(f'exclusive rule {exclusive} does not win')

    def __setLastMeld(self) ->None:
        """set the shortest possible last meld. This is
        not yet the final choice, see __applyBestLastMeld"""
        self.__lastMeld = None
        if self.lastTile and self.__won:
            if self.mjRule:
                self.__lastMelds = self.mjRule.computeLastMelds(self)  # type:ignore[call-arg,misc,attr-defined]
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

    def __applyBestLastMeld(self) ->None:
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
                        self.debug(f'replaced last meld {prev} with {bestLastMelds[0]}')
                self.__lastMeld = bestLastMelds[0]
                self.__applyRules()

    def chancesToWin(self) ->List[Tile]:
        """count the physical tiles that make us win and still seem available"""
        assert self.lenOffset == 0
        result = []
        for completedHand in self.callingHands:
            assert completedHand.lastTile
            result.extend(
                [completedHand.lastTile] *
                (self.player.tileAvailable(completedHand.lastTile, self)))
        return result

    def assertEqual(self, other:'Hand') ->None:
        """raise assertion if not equal with detailled info"""
        assert self.melds == other.melds, \
            f'Melds in hands differ:{self.melds!r} != {other.melds!r}'
        assert self.lastTile == other.lastTile, \
            f'lastTile in hands differs:{self.lastTile} != {other.lastTile}'
        assert self.lastMeld == other.lastMeld, \
            f'lastMeld in hands differs:{self.lastMeld} != {other.lastMeld}'
        assert self.newString() == other.newString(), \
            f'newString() in hands differs:{self.newString()} != {other.newString()}'
        assert self.newStr == other.newStr, \
            f'newStr in hands differs:{self.newStr} != {other.newStr}'

    def newString(self, melds:MeldList=1, unusedTiles:Optional['Tiles']=1,  # type:ignore[assignment]
        lastSource:Optional[Type[TileSource.SourceClass]]=1, announcements:Set[str]=1,  # type:ignore[assignment]
        lastTile:Tile=1, lastMeld:Optional[Meld]=1) ->str:  # type:ignore[assignment]  # type:ignore[assignment]
        """create string representing a hand. Default is current Hand, but every part
        can be overridden or excluded by passing None"""
        if melds == 1:
            melds = MeldList(chain(self.melds, self.bonusMelds))
        if unusedTiles== 1:
            unusedTiles = self.unusedTiles
        if lastSource == 1:
            lastSource = self.lastSource
        if announcements == 1:
            announcements = self.announcements
        if lastTile == 1:
            lastTile = self.lastTile
        if lastMeld == 1:
            lastMeld = self.__lastMeld  # type:ignore[assignment]
        parts = [str(x) for x in sorted(melds)]
        if unusedTiles:
            parts.append('R' + ''.join(str(x) for x in sorted(unusedTiles)))
        if lastSource or announcements:
            parts.append(f"m{self.lastSource.char}{''.join(self.announcements)}")
        if lastTile:
            parts.append(f"L{lastTile}{lastMeld if lastMeld else ''}")
            self.player.assertLastTile()
        return ' '.join(parts).strip()

    def __add__(self, addTile:Tile) ->'Hand':
        """return a new Hand built from this one plus addTile"""
        assert addTile.isConcealed, f'addTile {addTile} should be concealed:'
        # combine all parts about hidden tiles plus the new one to one part
        # because something like DrDrS8S9 plus S7 will have to be reordered
        # anyway
        newString = self.newString(
            melds=MeldList(chain(self.declaredMelds, self.bonusMelds)),
            unusedTiles=self.tilesInHand + [addTile],
            lastSource=None,
            lastTile=addTile,
            lastMeld=None
            )
        return Hand(self.player, newString, prevHand=self)

    def __sub__(self, subtractTile:Tile) ->'Hand':
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
                        f'lastMeld {lastMeld} is not in declaredMelds {declaredMelds}, hand is: {self}') from _
                tilesInHand.extend(lastMeld.concealed)
            try:
                tilesInHand.remove(subtractTile.concealed)
            except ValueError as _:
                raise ValueError(
                f'subtractTile.concealed={subtractTile.concealed} is not in tilesInHand {tilesInHand}') from _

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

    def manualRuleMayApply(self, rule:'Rule') ->bool:
        """return True if rule has selectable() and applies to this hand"""
        if self.__won and rule in self.ruleset.loserRules:
            return False
        if not self.__won and rule in self.ruleset.winnerRules:
            return False
        return rule.selectable(self) or rule.appliesToHand(self)
        # needed for activated rules

    @property
    def callingHands(self) ->List['Hand']:
        """the hand is calling if it only needs one tile for mah jongg.
        Returns all hands which would only need one tile.
        If mustBeAvailable is True, make sure the missing tile might still
        be available.
        """
        if self.__callingHands is None:
            self.__callingHands = self.__findAllCallingHands()
        return self.__callingHands

    def __findAllCallingHands(self) ->List['Hand']:
        """always try to find all of them"""
        result:List['Hand'] = []
        if self.lenOffset:
            return result
        candidates:TileList = TileList()
        for rule in self.ruleset.mjRules:
            cand = rule.winningTileCandidates(self)
            if Debug.hand and cand:
                candis = ''.join(str(x) for x in sorted(cand))
                self.debug(f'callingHands found {candis} for {rule}')
            candidates.extend(x.concealed for x in cand)
        for tile in sorted(set(candidates)):
            if sum(x.exposed == tile.exposed for x in self.tiles) == 4:
                continue
            hand = self + tile
            if hand.won:
                result.append(hand)
        if Debug.hand:
            _hiderules = ', '.join({x.mjRule.name for x in result if x.mjRule})
            if _hiderules:
                self.debug(f'Is calling {_hiderules}')
        return result

    @property
    def robbedTile(self) ->Tile:
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

    def __maybeMahjongg(self) ->List['Rule']:
        """check if this is a mah jongg hand.
        Return a sorted list of matching MJ rules, highest
        total first."""
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
                    self.debug(f'{callers()} Found {matchingMJRules}')
                return result
        return []

    def __arrangements(self) ->List[Tuple['Rule', MeldList]]:
        """find all legal arrangements.
        Returns a list of tuples with the mjRule and a list of concealed melds"""
        self.unusedTiles.sort()
        result:List[Tuple['Rule', MeldList]] = []
        stdMJ = self.ruleset.standardMJRule
        assert stdMJ
        if self.mjRule:
            rules = [self.mjRule]
        else:
            rules = self.ruleset.mjRules
        for mjRule in rules:
            if ((self.lenOffset == 1 and mjRule.appliesToHand(self))
                    or (self.lenOffset < 1 and mjRule.shouldTry(self))):  # type:ignore[attr-defined]
                if self.unusedTiles:
                    unused = TileList(Tile(x) for x in self.unusedTiles)
                    for melds, rest2 in mjRule.rearrange(self, unused):  # type:ignore[attr-defined]
                        if rest2:
                            melds = MeldList(melds)
                            restMelds, _ = next(
                                stdMJ.rearrange(self, rest2[:]))  # type:ignore[attr-defined]
                            melds.extend(restMelds)
                        result.append((mjRule, melds))
        if not result:
            result.extend(
                (stdMJ, x[0])
                for x in stdMJ.rearrange(self, self.unusedTiles[:]))  # type:ignore[attr-defined]
        return result

    def __arrange(self) ->None:
        """work hard to always return the variant with the highest Mah Jongg value."""
        if any(not x.isKnown for x in self.unusedTiles):
            meldCount, restCount = divmod(len(self.unusedTiles), 3)
            assert Tile.unknown.pung
            self.melds.extend([Tile.unknown.pung] * meldCount)
            if restCount:
                self.melds.append(Meld(Tile.unknown * restCount))
            self.unusedTiles = TileList()
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
                MeldList(chain(allMelds, self.bonusMelds)),
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
        self.unusedTiles = TileList()
        self.ruleCache.clear()

    def __gt__(self, other:Any) ->bool:
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

    def __lt__(self, other:Any) ->bool:
        """compares hand values"""
        return other.__gt__(self)

    def __eq__(self, other:Any) ->bool:
        """compares hand values"""
        assert self.__class__ is other.__class__, \
            f'Hands have different classes:{self.__class__} and {other.__class__}'
        assert self.player == other.player
        return self.newStr == other.newStr

    def __ne__(self, other:Any) ->bool:
        """compares hand values"""
        assert self.__class__ is other.__class__
        assert self.player == other.player
        return self.newStr != other.newStr

    def __matchingRules(self, rules:List['Rule']) ->List['Rule']:
        """return all matching rules for this hand"""
        return [rule for rule in rules if rule.appliesToHand(self)]

    @staticmethod
    def maxLimitRule(usedRules:List[UsedRule]) ->Optional[UsedRule]:
        """return the rule with the highest limit score or None"""
        result = None
        maxLimit = 0.0
        usedRules = [x for x in usedRules if x.rule.score.limits]
        for usedRule in usedRules:
            score = usedRule.rule.score
            if score.limits > maxLimit:
                maxLimit = score.limits
                result = usedRule
        return result

    def __totalScore(self) ->Score:
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

    def total(self) ->int:
        """total points of hand"""
        return self.score.total()

    @staticmethod
    def __separateBonusMelds(tileStrings:List[str]) ->Tuple[MeldList, List[str]]:
        """One meld per bonus tile. Others depend on that."""
        bonusMelds = MeldList()
        for tileString in tileStrings[:]:
            if len(tileString) == 2:
                tile = Tile(tileString)
                if tile.isBonus:
                    bonusMelds.append(tile.single)
                    tileStrings.remove(tileString)
        return bonusMelds, tileStrings

    def explain(self) ->List[str]:
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

    def doublesEstimate(self, discard:Optional[Tile]=None) ->int:
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

    def __str__(self) ->str:
        """hand as a string"""
        return self.newString()

    def __hash__(self) ->int:
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
