# -*- coding: utf-8 -*-

"""
Copyright 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
"""

import weakref

from qt import QGraphicsRectItem
from tile import Tile
from tileset import Tileset
from uitile import UITile
from meld import Meld, MeldList
from hand import Hand
from board import Board
from sound import Sound

from log import logDebug
from common import Internal, Debug, isAlive


class TileAttr(object):

    """a helper class for syncing the hand board, holding relevant
    tile attributes.
    xoffset and yoffset are expressed in number of tiles but may be
    fractional for adding distances between melds"""

    def __init__(self, hand, meld=None, idx=None, xoffset=None, yoffset=None):
        if isinstance(hand, UITile):
            self.tile = hand.tile
            self.xoffset = hand.xoffset
            self.yoffset = hand.yoffset
            self.dark = hand.dark
            self.focusable = hand.focusable
        else:
            self.tile = Tile(meld[idx])
            self.xoffset = xoffset
            self.yoffset = yoffset
            self.dark = self.setDark()
            # dark and focusable are different in a ScoringHandBoard
            self.focusable = self.setFocusable(hand, meld, idx)
            if self.tile in Debug.focusable:
                logDebug(u'TileAttr %s:%s' % (self.tile, self.focusable))

    def setDark(self):
        """should the tile appear darker?"""
        if self.yoffset == 0:
            return self.tile.isConcealed
        else:
            return not self.tile.isKnown

    def setFocusable(self, hand, meld, dummyIdx):
        """is it focusable?"""
        player = hand.player
        return (
            not self.tile.isBonus
            and self.tile.isKnown
            and player == player.game.activePlayer
            and player == player.game.myself
            and meld.isConcealed and not meld.isKong)

    def __str__(self):
        return (
            '%s %.2f/%.1f%s%s' %
            (self.tile, self.xoffset, self.yoffset,
             ' dark' if self.dark else '',
             ' focusable' if self.focusable else ''))

    def __repr__(self):
        return 'TileAttr(%s)' % str(self)


class HandBoard(Board):

    """a board showing the tiles a player holds"""
    # pylint: disable=too-many-public-methods,too-many-instance-attributes
    tileAttrClass = TileAttr
    penColor = 'blue'

    def __init__(self, player):
        assert player
        self._player = weakref.ref(player)
        self.exposedMeldDistance = 0.15
        self.concealedMeldDistance = 0.0
        self.lowerY = 1.0
        Board.__init__(self, 15.6, 2.0, Tileset.activeTileset())
        self.isHandBoard = True
        self.tileDragEnabled = False
        self.setParentItem(player.front)
        self.setPosition()
        self.setAcceptDrops(True)
        Internal.Preferences.addWatch(
            'rearrangeMelds', self.rearrangeMeldsChanged)
        self.rearrangeMeldsChanged(None, Internal.Preferences.rearrangeMelds)
        Internal.Preferences.addWatch(
            'showShadows', self.showShadowsChanged)

    def computeRect(self):
        """also adjust the scale for maximum usage of space"""
        Board.computeRect(self)
        sideRect = self.player.front.boundingRect()
        boardRect = self.boundingRect()
        scale = ((sideRect.width() + sideRect.height())
                 / (boardRect.width() - boardRect.height()))
        self.setScale(scale)

    @property
    def player(self):
        """player is readonly and never None"""
        if self._player:
            return self._player()

    # this is ordered such that pylint does not complain about
    # identical code in board.py

    @property
    def name(self):
        """for debugging messages"""
        return self.player.name

    def showShadowsChanged(self, dummyOldValue, dummyNewValue):
        """Add or remove the shadows."""
        self.setPosition()

    def setPosition(self):
        """Position myself"""
        show = Internal.Preferences.showShadows
        if show:
            self.setPos(yHeight=1.5)
        else:
            self.setPos(yHeight=1.0)
        if show:
            self.lowerY = 1.2
        else:
            self.lowerY = 1.0
        self.setRect(15.6, 1.0 + self.lowerY)
        self._reload(self.tileset, showShadows=show)
        self.sync()

    def rearrangeMeldsChanged(self, dummyOldValue, newValue):
        """when True, concealed melds are grouped"""
        self.concealedMeldDistance = (
            self.exposedMeldDistance if newValue else 0.0)
        self._reload(self.tileset, self._lightSource)
        self.sync()

    def focusRectWidth(self):
        """how many tiles are in focus rect? We want to focus
        the entire meld"""
        # playing game: always make only single tiles selectable
        return 1

    def __str__(self):
        return self.player.scoringString()

    def lowerHalfTiles(self):
        """returns a list with all single tiles of the lower half melds
        without boni"""
        return list(x for x in self.uiTiles if x.yoffset > 0 and not x.isBonus)

    def newLowerMelds(self):
        """a list of melds for the hand as it should look after sync"""

    def newTilePositions(self):
        """returns list(TileAttr) for all tiles except bonus tiles.
        The tiles are not associated to any board."""
        result = list()
        newUpperMelds = list(self.player.exposedMelds)
        newLowerMelds = self.newLowerMelds()
        for yPos, melds in ((0, newUpperMelds), (self.lowerY, newLowerMelds)):
            meldDistance = (self.concealedMeldDistance if yPos
                            else self.exposedMeldDistance)
            meldX = 0
            for meld in melds:
                for idx in range(len(meld)):
                    result.append(
                        self.tileAttrClass(self, meld, idx, meldX, yPos))
                    meldX += 1
                meldX += meldDistance
        return sorted(result, key=lambda x: x.yoffset * 100 + x.xoffset)

    def placeBoniInRow(self, bonusTiles, tilePositions, bonusY):
        """Try to place bonusTiles in upper or in lower row.
        tilePositions are the normal tiles, already placed.
        If there is no space, return None

        returns list(TileAttr)"""
        positions = list(x.xoffset for x in tilePositions if x.yoffset == bonusY)
        rightmostTileX = max(positions) if positions else 0
        xPos = 13 - len(bonusTiles)
        if xPos < rightmostTileX + 1 + self.exposedMeldDistance:
            return list()
        result = list()
        newBonusTiles = list(self.tileAttrClass(x) for x in bonusTiles)
        for bonus in sorted(newBonusTiles, key=lambda x: hash(x.tile)):
            bonus.xoffset, bonus.yoffset = xPos, bonusY
            bonus.dark = False
            result.append(bonus)
            xPos += 1
        return result

    def newBonusPositions(self, bonusTiles, newTilePositions):
        """returns list(TileAttr)
        calculate places for bonus tiles. Put them all in one row,
        right adjusted. If necessary, extend to the right even
        outside of our board"""

        return (
            self.placeBoniInRow(bonusTiles, newTilePositions, 0.0)
            or
            self.placeBoniInRow(bonusTiles, newTilePositions, self.lowerY))

    def calcPlaces(self, tiles):
        """returns a dict. Keys are existing tiles, Values are TileAttr instances.
        Values may be None: This is a tile to be removed from the board."""
        oldTiles = dict()
        oldBonusTiles = dict()
        for uiTile in tiles:
            assert isinstance(uiTile, UITile)
            if uiTile.isBonus:
                targetDict = oldBonusTiles
            else:
                targetDict = oldTiles
            if uiTile.tile not in targetDict.keys():
                targetDict[uiTile.tile] = list()
            targetDict[uiTile.tile].append(uiTile)
        result = dict()
        newPositions = self.newTilePositions()
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
                if not len(oldTiles[match.tile]):
                    del oldTiles[match.tile]
        for newBonusPosition in self.newBonusPositions(
                list(x for x in tiles if x.isBonus), newPositions):
            result[oldBonusTiles[newBonusPosition.tile][0]] = newBonusPosition
        self._avoidCrossingMovements(result)
        for uiTile, newPos in result.items():
            uiTile.level = 0  # for tiles coming from the wall
            uiTile.tile = newPos.tile
            uiTile.setBoard(self, newPos.xoffset, newPos.yoffset)
            uiTile.dark = newPos.dark
            uiTile.focusable = newPos.focusable
        return result

    def _avoidCrossingMovements(self, places):
        """not needed for all HandBoards"""
        pass

    def sync(self, adding=None):
        """place all tiles in HandBoard.
        adding tiles: their board is where they come from. Those tiles
        are already in the Player tile lists.
        The sender board must not be self, see ScoringPlayer.moveMeld"""
        if not self.uiTiles and not adding:
            return
        allTiles = self.uiTiles[:]
        if adding:
            allTiles.extend(adding)
        self.calcPlaces(allTiles)

    def checkTiles(self):
        """does the logical state match the displayed tiles?"""
        logExposed = list()
        physExposed = list()
        logConcealed = list()
        physConcealed = list()
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
            logConcealed = sorted(self.player.concealedTiles)
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
    # pylint: disable=too-many-public-methods,too-many-instance-attributes

    def __init__(self, player):
        HandBoard.__init__(self, player)

    def sync(self, adding=None):
        """place all tiles in HandBoard"""
        allTiles = self.uiTiles[:]
        if adding:
            allTiles.extend(adding)
        newPlaces = self.calcPlaces(allTiles)
        source = adding if adding else newPlaces.keys()
        focusCandidates = list(x for x in source
                               if x.focusable and x.tile.isConcealed)
        if not focusCandidates:
            # happens if we just exposed a claimed meld
            focusCandidates = list(x for x in newPlaces.keys()
                                   if x.focusable and x.tile.isConcealed)
        focusCandidates = sorted(focusCandidates, key=lambda x: x.xoffset)
        if focusCandidates:
            self.focusTile = focusCandidates[0]
        Internal.scene.handSelectorChanged(self)
        self.hasFocus = bool(adding)

    @Board.focusTile.setter
    def focusTile(self, uiTile):  # pylint: disable=arguments-differ
        Board.focusTile.fset(self, uiTile)
        if self.player and Internal.scene.clientDialog:
            Internal.scene.clientDialog.focusTileChanged()

    def setEnabled(self, enabled):
        """enable/disable this board"""
        if isAlive(self):
            # aborting a running game: the underlying C++ object might
            # already have been destroyed
            self.tileDragEnabled = (
                enabled
                and self.player == self.player.game.myself)
            QGraphicsRectItem.setEnabled(self, enabled)

    def dragMoveEvent(self, event):  # pylint: disable=no-self-use
        """only dragging to discard board should be possible"""
        event.setAccepted(False)

    def _avoidCrossingMovements(self, places):
        """"the above is a good approximation but if the board already had more
        than one identical tile they often switch places - this should not
        happen. So for each element, we make sure that the left-right order is
        still the same as before. For this check, ignore all new tiles"""
        movingPlaces = self.__movingPlaces(places)
        for yOld in 0, self.lowerY:
            for yNew in 0, self.lowerY:
                items = [x for x in movingPlaces.items()
                         if (x[0].board == self)
                         and x[0].yoffset == yOld
                         and x[1] and x[1].yoffset == yNew
                         and not x[0].isBonus]
                for element in set(x[1].tile for x in items):
                    items = [x for x in movingPlaces.items()
                             if x[1].tile is element]
                    if len(items) > 1:
                        oldList = sorted(list(x[0] for x in items),
                                         key=lambda x:
                                         bool(x.board != self) * 1000 + x.xoffset)
                        newList = sorted(list(x[1] for x in items),
                                         key=lambda x: x.xoffset)
                        for idx, oldTile in enumerate(oldList):
                            places[oldTile] = newList[idx]

    def __movingPlaces(self, places):
        """filter out the left parts of the rows which do not change
        at all"""
        rows = [[], []]
        for idx, yOld in enumerate([0, self.lowerY]):
            rowPlaces = [x for x in places.items() if x[0].yoffset == yOld]
            rowPlaces = sorted(rowPlaces, key=lambda x: x[0].xoffset)
            smallestX = 999
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

    def newLowerMelds(self):
        """a list of melds for the hand as it should look after sync"""
        if self.player.concealedMelds:
            result = MeldList(self.player.concealedMelds)
        elif self.player.concealedTiles:
            tileStr = 'R' + ''.join(x for x in self.player.concealedTiles)
            content = Hand(self.player, tileStr)
            result = MeldList(content.melds + content.bonusMelds)
        else:
            return []
        if not Internal.Preferences.rearrangeMelds:
            result = MeldList(Meld(x) for x in result.tiles())
            # one meld per tile
        result.sort()
        return result

    def discard(self, tile):
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
        Internal.scene.discardBoard.discardTile(lastDiscard)
        for uiTile in self.uiTiles:
            uiTile.focusable = False

    def addUITile(self, uiTile):
        """add uiTile to this board"""
        Board.addUITile(self, uiTile)
        if uiTile.isBonus and not self.player.game.isScoringGame():
            Sound.bonus()
