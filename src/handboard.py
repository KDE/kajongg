# -*- coding: utf-8 -*-

"""
Copyright 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

import weakref
from collections import defaultdict
from typing import Optional, TYPE_CHECKING, List, Dict, Union, cast

from qt import QColor
from tile import Tile, TileList, Meld, MeldList
from tileset import Tileset
from uitile import UITile
from hand import Hand
from board import Board
from sound import Sound

from log import logDebug
from common import Internal, Debug, isAlive, ReprMixin

if TYPE_CHECKING:
    from qt import QGraphicsSceneDragDropEvent
    from visible import VisiblePlayer
    from scene import PlayingScene
    from player import PlayingPlayer


class TileAttr(ReprMixin):

    """a helper class for syncing the hand board, holding relevant
    tile attributes.
    xoffset is expressed in number of tiles but may be
    fractional for adding distances between melds"""

    def __init__(self, hand:Union['HandBoard', UITile], meld:Optional[Meld]=None, idx:Optional[int]=None,
        xoffset:Optional[float]=None, yoffset:Optional[int]=None) ->None:
        if isinstance(hand, UITile):
# TODO only used for Bonus tiles, should split or eliminate this
            self.tile = hand.tile
            self.xoffset = hand.xoffset
            self.yoffset = hand.yoffset
            self.dark = hand.dark
            self.focusable = hand.focusable
        else:
            assert meld
            assert idx is not None
            self.tile = Tile(meld[idx])
            assert xoffset is not None # FIXME: overload __init__
            assert yoffset is not None
            self.xoffset = xoffset  # type:ignore[assignment]
            self.yoffset = yoffset
            self.dark = self._setDark()
            # dark and focusable are different in a ScoringHandBoard
            self.focusable = self._setFocusable(hand, meld, idx)
            if self.tile.name2() in Debug.focusable:
                logDebug(f'TileAttr {self.tile}:{self.focusable}')

    def _setDark(self) ->bool:
        """should the tile appear darker?"""
        return self.tile.isConcealed if self.yoffset == 0 else not self.tile.isKnown

    def _setFocusable(self, hand:'HandBoard', meld:Meld, idx:Optional[int]) ->bool: # pylint: disable=unused-argument
        """is it focusable?"""
        player = hand.player
        assert player
        assert player.game
        return (
            not self.tile.isBonus
            and self.tile.isKnown
            and player == player.game.activePlayer
            and player == player.game.myself
            and meld.isConcealed and not meld.isKong)

    def apply_to(self, board:Board, uiTile:UITile) -> None:
        """Change uiTile according to self"""
        uiTile.level = 0  # for tiles coming from the wall
        uiTile.change_name(self.tile)
        uiTile.setBoard(board, self.xoffset, self.yoffset)
        uiTile.dark = self.dark
        uiTile.focusable = self.focusable

    def __str__(self) ->str:
        assert self.xoffset is not None
        return (
            f"{self.tile} {self.xoffset:.2f}/{int(self.yoffset)}{' dark' if self.dark else ''}"
            f"{' focusable' if self.focusable else ''}")


class HandBoard(Board):

    """a board showing the tiles a player holds"""

    tileAttrClass = TileAttr
    penColor = QColor('blue')
    showShadowsBetweenRows = True

    def __init__(self, player:'VisiblePlayer') ->None:
        assert player
        self._player = weakref.ref(player)
        self.exposedMeldDistance:float = 0.15
        self.concealedMeldDistance:float = 0.0
        super().__init__(15.6, 2.0, Tileset.current())
        self.isHandBoard = True
        self.tileDragEnabled = False
        self.setParentItem(player.front)
        self.setPosition()
        self.setAcceptDrops(True)
        assert Internal.Preferences
        Internal.Preferences.addWatch(
            'rearrangeMelds', self.rearrangeMeldsChanged)
        self.rearrangeMeldsChanged(False, bool(Internal.Preferences.rearrangeMelds))
        Internal.Preferences.addWatch(
            'showShadows', self.showShadowsChanged)

    def computeRect(self) ->None:
        """also adjust the scale for maximum usage of space"""
        super().computeRect()
        rect = self.rect()
        rect.setWidth(rect.width() + 2 * self.tileset.shadowHeight())
        self.setRect(rect)

        if self.player:
            sideRect = self.player.front.boundingRect()
            boardRect = self.boundingRect()
            scale = ((sideRect.width() + sideRect.height())
                     / (boardRect.width() - boardRect.height()))
            self.setScale(scale)

    @property
    def player(self) ->Optional['VisiblePlayer']:
        """player is readonly and never None"""
        return self._player() if self._player else None

    # this is ordered such that pylint does not complain about
    # identical code in board.py

    def debug_name(self) ->str:
        """for debugging messages"""
        if self.player is None:
            return 'None'
        return self.player.name

    def showShadowsChanged(self, unusedOldValue:bool, newValue:bool) ->None:
        """Add or remove the shadows."""
        self.setPosition()

    def setPosition(self) ->None:
        """Position myself"""
        assert Internal.Preferences
        show = bool(Internal.Preferences.showShadows)
        if show:
            self.setTilePos(yHeight=1.5)
        else:
            self.setTilePos(yHeight=1.0)
        self.setBoardRect(15.6, 2.2 if show else 2.0)
        self._reload(self.tileset, showShadows=show)
        self.sync()

    def rearrangeMeldsChanged(self, unusedOldValue:bool, newValue:bool) ->None:
        """when True, concealed melds are grouped"""
        self.concealedMeldDistance = (
            self.exposedMeldDistance if newValue else 0.0)
        self._reload(self.tileset, self._lightSource)
        self.sync()

    def focusRectWidth(self) ->int:
        """how many tiles are in focus rect? We want to focus
        the entire meld"""
        # playing game: always make only single tiles selectable
        return 1

    def __str__(self) ->str:
        assert self.player
        return self.player.scoringString()

    def lowerHalfTiles(self) ->List[UITile]:
        """return a list with all single tiles of the lower half melds
        without boni"""
        return [x for x in self if x.yoffset > 0 and not x.isBonus]

    def newLowerMelds(self) ->MeldList:
        """a list of melds for the hand as it should look after sync"""
        return MeldList()

    def listNewTilePositions(self) ->List[TileAttr]:
        """return list(TileAttr) for all tiles except bonus tiles.
        The tiles are not associated to any board."""
        result:List[TileAttr] = []
        assert self.player
        newUpperMelds = list(self.player.exposedMelds)
        newLowerMelds = self.newLowerMelds()
        for yPos, melds in ((0, newUpperMelds), (1, newLowerMelds)):
            meldDistance = (self.concealedMeldDistance if yPos
                            else self.exposedMeldDistance)
            meldX:float = 0.0
            for meld in melds:
                for idx in range(len(meld)):
                    result.append(self.tileAttrClass(self, meld, idx, meldX, yPos))
                    meldX += 1
                meldX += meldDistance
        return sorted(result, key=lambda x: x.yoffset * 100 + x.xoffset)

    def __findMaxX(self, positions:List[TileAttr], row:int) ->float:
        """find the rightmost position for row"""
        x_values = [position.xoffset for position in positions if position.yoffset == row]
        return max(x_values) if x_values else 0.0

    def __placeBoniInRow(self, bonusTiles:List[UITile], after:List[float],
        bonusY:int, keepTogether:bool=True, maxTilesInRow=13) ->List[TileAttr]:
        """Try to place bonusTiles in upper or in lower row.
        tilePositions are the normal tiles, already placed.
        Placed boni are removed from bonusTiles.
        Returns all tiles that could be placed."""

        result:List[TileAttr] = []
        placeBoni = bonusTiles[:]
        while maxTilesInRow - len(placeBoni) < after[bonusY] + 1 + self.exposedMeldDistance:
            if keepTogether:
                return []
            placeBoni = placeBoni[:-1]
            if not placeBoni:
                return result
        for _ in placeBoni:
            bonusTiles.remove(_)
        xPos = maxTilesInRow - len(placeBoni)
        newBonusTiles = [self.tileAttrClass(x) for x in placeBoni]
        for bonus in sorted(newBonusTiles, key=lambda x: x.tile.key):
            bonus.xoffset, bonus.yoffset = xPos, bonusY
            bonus.dark = False
            result.append(bonus)
            after[bonusY] += 1
            xPos += 1
        return result

    def __newBonusPositions(self, bonusTiles:List[UITile], after:List[float]) ->List[TileAttr]:
        """return list(TileAttr)
        calculate places for bonus tiles. Try to put them all in one row,
        right adjusted. If necessary, extend to the right even
        outside of our board"""
        result:List[TileAttr] = []
        bonusTiles = bonusTiles[:]  # do not change passed list
        result.extend(self.__placeBoniInRow(bonusTiles, after, 0))
        result.extend(self.__placeBoniInRow(bonusTiles, after, 1))
        if len(bonusTiles):
            # we cannot place all bonus tiles in the same row!
            result.extend(self.__placeBoniInRow(bonusTiles, after, 0, keepTogether=False))
            result.extend(self.__placeBoniInRow(bonusTiles, after, 1, keepTogether=False))
        maxTilesInRow = 13
        while len(bonusTiles):
            maxTilesInRow += 1
            assert maxTilesInRow < 99, f'cannot place {bonusTiles}'
            result.extend(self.__placeBoniInRow(bonusTiles, after, 0, keepTogether=False, maxTilesInRow=maxTilesInRow))
            result.extend(self.__placeBoniInRow(bonusTiles, after, 1, keepTogether=False, maxTilesInRow=maxTilesInRow))
        return result

    def placeTiles(self, tiles:List[UITile]) ->None:
        """tiles are all tiles for this board."""
        oldTiles = defaultdict(list)
        for uiTile in filter(lambda x: not x.isBonus, tiles):
            oldTiles[uiTile.tile].append(uiTile)
        matches:Dict[UITile, TileAttr] = {}
        newPositions = self.listNewTilePositions()
        for newPosition in newPositions:
            assert isinstance(newPosition.tile, Tile)
            candidates = oldTiles.get(newPosition.tile) \
                or oldTiles.get(newPosition.tile.swapped) \
                or oldTiles.get(Tile.unknown)
            if not candidates and not newPosition.tile.isKnown and oldTiles:
                # 13 orphans, robbing Kong, lastTile is single:
                # no oldTiles exist
                candidates = list(oldTiles.values())[0]
            if candidates:
                # no candidates happen when we move a uiTile within a board,
                # here we simply ignore existing tiles with no candidates
                candidates = sorted(
                    candidates, key=lambda x:
                    + abs(newPosition.yoffset - x.yoffset) * 100 # pylint: disable=cell-var-from-loop
                    + x.xoffset)
                # pylint is too cautious here. Check with later versions.
                match = candidates[0]
                matches[match] = newPosition
                oldTiles[match.tile].remove(match)
                if not oldTiles[match.tile]:
                    del oldTiles[match.tile]
        for uiTile, newPos in matches.items():
            newPos.apply_to(self, uiTile)
        after = list(self.__findMaxX(list(matches.values()), x) for x in (0, 1))
        self._placeBonusTiles(after, tiles)

    def _placeBonusTiles(self, after:List[float], tiles:List[UITile]) ->None:
        """Temporary code, directly after extraction from placeTiles()"""
        boni = list(sorted(filter(lambda x: x.isBonus, tiles), key=lambda x: hash(x.tile)))
        positions = self.__newBonusPositions(boni, after)
        for tile, position in zip(boni, positions):
            position.apply_to(self, tile)

    def sync(self, adding:Optional[List[UITile]]=None) ->None:
        """place all tiles in HandBoard.
        adding tiles: their board is where they come from. Those tiles
        are already in the Player tile lists.
        The sender board must not be self, see ScoringPlayer.moveMeld"""
        if self.empty and not adding:
            return
        allTiles = self[:]
        if adding:
            allTiles.extend(adding)
        self.placeTiles(allTiles)

    def checkTiles(self) ->None:
        """does the logical state match the displayed tiles?"""
        return
# FIXME: when exactly should I call this? afterQueuedAnimations does not help
        # test case: scoring game. move meld from exposed to concealed using the mouse
        logExposed:TileList = TileList()  # pylint: disable=unreachable
        physExposed:TileList = TileList()
        logConcealed:TileList = TileList()
        physConcealed:TileList = TileList()
        assert self.player
        for tile in self.player.bonusTiles:
            logExposed.append(tile)
        for uiTile in self:
            if uiTile.yoffset == 0 or uiTile.isBonus:
                physExposed.append(uiTile.tile)
            else:
                physConcealed.append(uiTile.tile)
        for meld in self.player.exposedMelds:
            logExposed.extend(meld)
        if self.player.concealedMelds:
            for meld in self.player.concealedMelds:
                logConcealed.extend(meld)
        else:
            logConcealed = TileList(self.player.concealedTiles)
            # FIXME: oder player.concealedTiles schon immer sortieren, oder desse Type auf TileList aendern
        logExposed.sort()
        physExposed.sort()
        logConcealed.sort()
        physConcealed.sort()
        assert logExposed == physExposed, (
            f'{self.player}: exposed: player {logExposed} != hand {physExposed}. '
            f'Check those:{set(logExposed) ^ set(physExposed)}')
        assert logConcealed == physConcealed, (
            f'{self.player}: concealed: player {logConcealed} != hand {physConcealed}')


class PlayingHandBoard(HandBoard):

    """a board showing the tiles a player holds"""

    def sync(self, adding:Optional[List[UITile]]=None) ->None:
        """place all tiles in HandBoard"""
        allTiles = self[:]
        if adding:
            allTiles.extend(adding)
        self.placeTiles(allTiles)
        source = adding if adding else self[:]
        focusCandidates = [x for x in source if x.focusable and x.tile.isConcealed]
        if not focusCandidates:
            # happens if we just exposed a claimed meld
            focusCandidates = [x for x in self[:] if x.focusable and x.tile.isConcealed]
        focusCandidates = sorted(focusCandidates, key=lambda x: x.xoffset)
        if focusCandidates:
            self.focusTile = focusCandidates[0]
        assert Internal.scene
        Internal.scene.handSelectorChanged(self)
        self.hasLogicalFocus = bool(adding)

    @Board.focusTile.setter  # type: ignore
    def focusTile(self, uiTile):
        Board.focusTile.fset(self, uiTile)
        assert self.player
        assert Internal.scene
        if self.player and Internal.scene.clientDialog:
            Internal.scene.clientDialog.focusTileChanged()

    def setEnabled(self, enabled:bool) ->None:
        """enable/disable this board"""
        if isAlive(self):
            # aborting a running game: the underlying C++ object might
            # already have been destroyed
            super().setEnabled(enabled)
            assert self.player
            assert self.player.game
            self.tileDragEnabled &= self.player == self.player.game.myself

    def dragMoveEvent(self, event:Optional['QGraphicsSceneDragDropEvent']) ->None:
        """only dragging to discard board should be possible"""
        if event:
            event.setAccepted(False)

    def newLowerMelds(self) ->MeldList:
        """a list of melds for the hand as it should look after sync"""
        assert self.player
        if self.player.concealedMelds:
            result = MeldList(self.player.concealedMelds)
        elif self.player.concealedTiles:
            content = Hand(self.player, unusedTiles=self.player.concealedTiles)
            result = MeldList(content.melds + content.bonusMelds)
        else:
            return MeldList()
        assert Internal.Preferences
        if not Internal.Preferences.rearrangeMelds:
            result = MeldList(Meld(x) for x in result.tiles())
            # one meld per tile
        result.sort()
        return result

    def discard(self, tile:Tile) ->None:
        """select the rightmost matching tileItem and move it
        to DiscardBoard"""
        if self.focusTile and self.focusTile.tile is tile:
            lastDiscard = self.focusTile
        else:
            # if an opponent player discards, we want to discard from the
            # right end of the hand# thus minimizing tile movement
            # within the hand
            lastDiscard = self[tile][-1]  # type:ignore[index]
        assert Internal.scene
        cast('PlayingScene', Internal.scene).discardBoard.discardTile(lastDiscard)
        for uiTile in self:
            uiTile.focusable = False

    def addUITile(self, uiTile:UITile) ->None:
        """add uiTile to this board"""
        super().addUITile(uiTile)
        assert self.player
        assert self.player.game
        if uiTile.isBonus and not self.player.game.isScoringGame():
            Sound.bonus()
