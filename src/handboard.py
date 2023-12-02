# -*- coding: utf-8 -*-

"""
Copyright 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

import weakref
from typing import Optional, TYPE_CHECKING, List, Dict, Union, Any, cast

from qt import QGraphicsRectItem, QColor
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
            self.dark = self.setDark()
            # dark and focusable are different in a ScoringHandBoard
            self.focusable = self.setFocusable(hand, meld, idx)
            if self.tile.name2() in Debug.focusable:
                logDebug('TileAttr %s:%s' % (self.tile, self.focusable))

    def setDark(self) ->bool:
        """should the tile appear darker?"""
        return self.tile.isConcealed if self.yoffset == 0 else not self.tile.isKnown

    def setFocusable(self, hand:'HandBoard', meld:Meld, idx:Optional[int]) ->bool: # pylint: disable=unused-argument
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

    def __str__(self) ->str:
        assert self.xoffset is not None
        return (
            '%s %.2f/%d%s%s' %
            (self.tile, self.xoffset, self.yoffset,
             ' dark' if self.dark else '',
             ' focusable' if self.focusable else ''))


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
        Board.__init__(self, 15.6, 2.0, Tileset.current())
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
        Board.computeRect(self)
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
        return [x for x in self.uiTiles if x.yoffset > 0 and not x.isBonus]

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

    def placeBoniInRow(self, bonusTiles:List[UITile], tilePositions:List[TileAttr],
        bonusY:int, keepTogether:bool=True) ->List[TileAttr]:
        """Try to place bonusTiles in upper or in lower row.
        tilePositions are the normal tiles, already placed.
        If there is no space, return None

        returns list(TileAttr)"""
        positions = [x.xoffset for x in tilePositions if x.yoffset == bonusY]
        rightmostTileX = max(positions) if positions else 0
        placeBoni = bonusTiles[:]
        while 13 - len(placeBoni) < rightmostTileX + 1 + self.exposedMeldDistance:
            if keepTogether:
                return []
            placeBoni = placeBoni[:-1]
        result = []
        xPos = 13 - len(placeBoni)
        newBonusTiles = [self.tileAttrClass(x) for x in placeBoni]
        for bonus in sorted(newBonusTiles, key=lambda x: x.tile.key):
            bonus.xoffset, bonus.yoffset = xPos, bonusY
            bonus.dark = False
            result.append(bonus)
            xPos += 1
        return result

    def newBonusPositions(self, bonusTiles:List[UITile], newTilePositions:List[TileAttr]) ->List[TileAttr]:
        """return list(TileAttr)
        calculate places for bonus tiles. Try to put them all in one row,
        right adjusted. If necessary, extend to the right even
        outside of our board"""
        if not bonusTiles:
            return []
        bonusTiles = sorted(bonusTiles, key=lambda x: hash(x.tile))
        result = (
            self.placeBoniInRow(bonusTiles, newTilePositions, 0)
            or
            self.placeBoniInRow(bonusTiles, newTilePositions, 1))
        if not result:
            # we cannot place all bonus tiles in the same row!
            result = self.placeBoniInRow(bonusTiles, newTilePositions, 0, keepTogether=False)
            result.extend(self.placeBoniInRow(
                bonusTiles[len(result):], newTilePositions, 1, keepTogether=False))

        assert len(bonusTiles) == len(result)
        return result

    def placeTiles(self, tiles:List[UITile]) ->List[UITile]:
        """tiles are all tiles for this board.
        returns a list of those uiTiles which are placed on the board"""
        oldTiles:Dict[Tile, List[UITile]] = {}
        oldBonusTiles:Dict[Tile, List[UITile]] = {}
        for uiTile in tiles:
            assert isinstance(uiTile, UITile), 'uiTile is {}'.format(type(uiTile))
            if uiTile.isBonus:
                targetDict = oldBonusTiles
            else:
                targetDict = oldTiles
            if uiTile.tile not in targetDict:
                targetDict[uiTile.tile] = []
            targetDict[uiTile.tile].append(uiTile)
        result:Dict[UITile, TileAttr] = {}
        newPositions = self.listNewTilePositions()
        for newPosition in newPositions:
            assert isinstance(newPosition.tile, Tile)
            matches = oldTiles.get(newPosition.tile) \
                or oldTiles.get(newPosition.tile.swapped) \
                or oldTiles.get(Tile.unknown)
            if not matches and not newPosition.tile.isKnown and oldTiles:
                # 13 orphans, robbing Kong, lastTile is single:
                # no oldTiles exist
                matches = list(oldTiles.values())[0]
            if matches:
                # no matches happen when we move a uiTile within a board,
                # here we simply ignore existing tiles with no matches
                matches = sorted(
                    matches, key=lambda x:
                    + abs(newPosition.yoffset - x.yoffset) * 100 # pylint: disable=cell-var-from-loop
                    + abs(newPosition.xoffset - x.xoffset)) # pylint: disable=cell-var-from-loop
                # pylint is too cautious here. Check with later versions.
                match = matches[0]
                result[match] = newPosition
                oldTiles[match.tile].remove(match)
                if not oldTiles[match.tile]:
                    del oldTiles[match.tile]
        for newBonusPosition in self.newBonusPositions(
                [x for x in tiles if x.isBonus], newPositions):
            result[oldBonusTiles[newBonusPosition.tile][0]] = newBonusPosition
        self._avoidCrossingMovements(result)
        for uiTile, newPos in result.items():
            uiTile.level = 0  # for tiles coming from the wall
            uiTile.change_name(newPos.tile)
            uiTile.setBoard(self, newPos.xoffset, newPos.yoffset)
            uiTile.dark = newPos.dark
            uiTile.focusable = newPos.focusable
        return list(result.keys())

    def _avoidCrossingMovements(self, places:Dict[UITile, TileAttr]) ->None:
        """not needed for all HandBoards"""

    def sync(self, adding:Optional[List[UITile]]=None) ->None:
        """place all tiles in HandBoard.
        adding tiles: their board is where they come from. Those tiles
        are already in the Player tile lists.
        The sender board must not be self, see ScoringPlayer.moveMeld"""
        if not self.uiTiles and not adding:
            return
        allTiles = self.uiTiles[:]
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
        for uiTile in self.uiTiles:
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
            '%s: exposed: player %s != hand %s. Check those:%s' %
            (self.player, logExposed, physExposed,
             set(logExposed) ^ set(physExposed)))
        assert logConcealed == physConcealed, (
            '%s: concealed: player %s != hand %s' %
            (self.player, logConcealed, physConcealed))


class PlayingHandBoard(HandBoard):

    """a board showing the tiles a player holds"""

    def __init__(self, player:'VisiblePlayer') ->None:
        HandBoard.__init__(self, player)

    def sync(self, adding:Optional[List[UITile]]=None) ->None:
        """place all tiles in HandBoard"""
        allTiles = self.uiTiles[:]
        if adding:
            allTiles.extend(adding)
        newTiles = self.placeTiles(allTiles)
        source = adding if adding else newTiles
        focusCandidates = [x for x in source if x.focusable and x.tile.isConcealed]
        if not focusCandidates:
            # happens if we just exposed a claimed meld
            focusCandidates = [x for x in newTiles if x.focusable and x.tile.isConcealed]
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
            assert self.player
            assert self.player.game
            self.tileDragEnabled = (
                enabled
                and self.player == self.player.game.myself)
            QGraphicsRectItem.setEnabled(self, enabled)

    def dragMoveEvent(self, event:'QGraphicsSceneDragDropEvent') ->None:
        """only dragging to discard board should be possible"""
        event.setAccepted(False)

    def _avoidCrossingMovements(self, places:Dict[UITile, TileAttr]) ->None:
        """"the above is a good approximation but if the board already had more
        than one identical tile they often switch places - this should not
        happen. So for each element, we make sure that the left-right order is
        still the same as before. For this check, ignore all new tiles"""
        movingPlaces = self.__movingPlaces(places)
        for yOld in 0, 1:
            for yNew in 0, 1:
                items = [x for x in movingPlaces.items()
                         if (x[0].board == self)
                         and x[0].yoffset == yOld
                         and x[1] and x[1].yoffset == yNew
                         and not x[0].isBonus]
                for element in {x[1].tile for x in items}:
                    items = [x for x in movingPlaces.items()
                             if x[1].tile is element]
                    if len(items) > 1:
                        oldList = sorted((x[0] for x in items),
                                         key=lambda x:
                                         bool(x.board != self) * 1000 + x.xoffset)
                        newList = sorted((x[1] for x in items),
                                         key=lambda x: x.xoffset)
                        for idx, oldTile in enumerate(oldList):
                            places[oldTile] = newList[idx]

    def __movingPlaces(self, places:Dict[UITile, TileAttr]) ->Dict[UITile, TileAttr]:
        """filter out the left parts of the rows which do not change
        at all"""
        rows:List[List[Any]] = [[], []]
        for idx, yOld in enumerate([0, 1]):
            rowPlaces = [x for x in places.items() if x[0].yoffset == yOld]
            rowPlaces = sorted(rowPlaces, key=lambda x: x[0].xoffset)
            smallestX = 999.9
            for tileItem, newPos in places.items():
                if (tileItem.xoffset != newPos.xoffset
                        or tileItem.yoffset != newPos.yoffset):
                    if newPos.yoffset == yOld:
                        smallestX = min(smallestX, newPos.xoffset)
                    else:
                        smallestX = min(smallestX, tileItem.xoffset)
            rows[idx] = [x for x in rowPlaces
                         if x[0].xoffset >= smallestX
                         and x[1].xoffset >= smallestX]
        result = dict(rows[0])
        result.update(dict(rows[1]))
        return result

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
            matchingTiles = sorted(self.tilesByElement(tile),
                                   key=lambda x: x.xoffset)
            # if an opponent player discards, we want to discard from the
            # right end of the hand# thus minimizing tile movement
            # within the hand
            lastDiscard = matchingTiles[-1]
        assert Internal.scene
        cast('PlayingScene', Internal.scene).discardBoard.discardTile(lastDiscard)
        for uiTile in self.uiTiles:
            uiTile.focusable = False

    def addUITile(self, uiTile:UITile) ->None:
        """add uiTile to this board"""
        Board.addUITile(self, uiTile)
        assert self.player
        assert self.player.game
        if uiTile.isBonus and not self.player.game.isScoringGame():
            Sound.bonus()
