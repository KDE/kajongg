# -*- coding: utf-8 -*-

"""
 (C) 2008-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
"""

import weakref

from PyQt4.QtGui import QGraphicsRectItem
from tile import Tile
from uitile import UITile
from meld import Meld, CONCEALED, REST, tileKey, elementKey, meldKey
from hand import Hand
from board import Board

from util import logDebug
from common import Preferences, Internal, Debug, isAlive

class TileAttr(object):
    """a helper class for syncing the hand board, holding relevant tile attributes"""
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
            player = hand.player
            scoring = hand.__class__.__name__ ==  'ScoringHandBoard'  # TODO: get rid of this
            if yoffset == 0:
                self.dark = self.tile.istitle()
            else:
                self.dark = self.tile == b'Xy' or scoring
            self.focusable = True
            if scoring:
                self.focusable = idx == 0
            else:
                self.focusable = (not self.tile.isBonus()
                    and self.tile != b'Xy'
                    and player == player.game.activePlayer
                    and player == player.game.myself
                    and (meld.state == CONCEALED
                    and (len(meld) < 4 or meld.meldType == REST)))
            if self.tile in Debug.focusable:
                logDebug('TileAttr %s:%s' % (self.tile, self.focusable))

    def __str__(self):
        return '%s %.2f/%.1f%s%s' % (self.tile, self.xoffset, self.yoffset, ' dark' if self.dark else '', \
            ' focusable' if self.focusable else '')

    def __repr__(self):
        return 'TileAttr(%s)' % str(self)

class HandBoard(Board):
    """a board showing the tiles a player holds"""
    # pylint: disable=too-many-public-methods,too-many-instance-attributes
    def __init__(self, player):
        assert player
        self._player = weakref.ref(player)
        self.exposedMeldDistance = 0.15
        self.concealedMeldDistance = 0.0
        self.lowerY = 1.0
        Board.__init__(self, 15.6, 2.0, Internal.scene.tileset)
        self.isHandBoard = True
        self.tileDragEnabled = False
        self.setParentItem(player.front)
        self.setAcceptDrops(True)
        self.rearrangeMelds = Preferences.rearrangeMelds
        self.showShadows = Preferences.showShadows

    def computeRect(self):
        """also adjust the scale for maximum usage of space"""
        Board.computeRect(self)
        sideRect = self.player.front.boundingRect()
        boardRect = self.boundingRect()
        scale = (sideRect.width() + sideRect.height()) / (boardRect.width() - boardRect.height())
        self.setScale(scale)

    @property
    def player(self):
        """player is readonly and never None"""
        if self._player:
            return self._player()

    @property
    def showShadows(self):
        """the active value"""
        return self._showShadows

    # this is ordered such that pylint does not complain about identical code in board.py

    @property
    def name(self):
        """for debugging messages"""
        return self.player.name

    @showShadows.setter
    def showShadows(self, value): # pylint: disable=arguments-differ
        """set showShadows"""
        if self._showShadows is None or self._showShadows != value:
            if value:
                self.setPos(yHeight= 1.5)
            else:
                self.setPos(yHeight= 1.0)
            if value:
                self.lowerY = 1.2
            else:
                self.lowerY = 1.0
            self.setRect(15.6, 1.0 + self.lowerY)
            self._reload(self.tileset, showShadows=value)
            self.sync()

    @property
    def rearrangeMelds(self):
        """when setting this, concealed melds are grouped"""
        return bool(self.concealedMeldDistance)

    @rearrangeMelds.setter
    def rearrangeMelds(self, rearrangeMelds):
        """when setting this, concealed melds are grouped"""
        if rearrangeMelds != self.rearrangeMelds:
            self.concealedMeldDistance = self.exposedMeldDistance if rearrangeMelds else 0.0
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
        """returns a list with all single tiles of the lower half melds without boni"""
        return list(x for x in self.uiTiles if x.yoffset > 0 and not x.isBonus())

    def newLowerMelds(self):
        """a list of melds for the hand as it should look after sync"""

    def newTilePositions(self):
        """returns list(TileAttr) for all tiles except bonus tiles.
        The tiles are not associated to any board."""
        result = list()
        newUpperMelds = list(self.player.exposedMelds)
        newLowerMelds = self.newLowerMelds()
        for yPos, melds in ((0, newUpperMelds), (self.lowerY, newLowerMelds)):
            meldDistance = self.concealedMeldDistance if yPos else self.exposedMeldDistance
            meldX = 0
            for meld in melds:
                for idx in range(len(meld)):
                    result.append(TileAttr(self, meld, idx, meldX, yPos))
                    meldX += 1
                meldX += meldDistance
        return sorted(result, key=lambda x: x.yoffset * 100 + x.xoffset)

    def newBonusPositions(self, bonusTiles, newTilePositions):
        """returns list(TileAttr)
        calculate places for bonus tiles. Put them all in one row,
        right adjusted. If necessary, extend to the right even outside of our board"""
        positions = list(x.xoffset for x in newTilePositions if x.yoffset==0)
        upperLen = max(positions) if positions else 0
        positions = list(x.xoffset for x in newTilePositions if x.yoffset!=0)
        lowerLen = max(positions) if positions else 0
# TODO: keep them in the row they are in as long as there is room
        if upperLen < lowerLen :
            bonusY = 0
            tileLen = upperLen
        else:
            bonusY = self.lowerY
            tileLen = lowerLen
        tileLen += 1 + self.exposedMeldDistance
        newBonusTiles = list(TileAttr(x) for x in bonusTiles)
        xPos = 13 - len(newBonusTiles)
        xPos = max(xPos, tileLen)
        result = list()
        for bonus in sorted(newBonusTiles, key=lambda x: tileKey(x.tile)):
            bonus.xoffset, bonus.yoffset = xPos, bonusY
            bonus.dark = False
            result.append(bonus)
            xPos += 1
        return result

    def calcPlaces(self, tiles):
        """returns a dict. Keys are existing tiles, Values are TileAttr instances.
        Values may be None: This is a tile to be removed from the board."""
        oldTiles = dict()
        oldBonusTiles = dict()
        for uiTile in tiles:
            assert isinstance(uiTile, UITile)
            if uiTile.isBonus():
                targetDict = oldBonusTiles
            else:
                targetDict = oldTiles
            if not uiTile.tile in targetDict.keys():
                targetDict[uiTile.tile] = list()
            targetDict[uiTile.tile].append(uiTile)
        result = dict()
        newPositions = self.newTilePositions()
        for newPosition in newPositions:
            assert isinstance(newPosition.tile, Tile)
            matches = oldTiles.get(newPosition.tile) \
                or oldTiles.get(newPosition.tile.swapTitle()) \
                or oldTiles.get(b'Xy')
            if not matches and newPosition.tile == b'Xy':
                matches = oldTiles.values()[0]
            if matches:
                # no matches happen when we move a uiTile within a board,
                # here we simply ignore existing tiles with no matches
                matches = sorted(matches, key=lambda x: \
                    + abs(newPosition.yoffset-x.yoffset) * 100 \
                    + abs(newPosition.xoffset-x.xoffset))
                match = matches[0]
                result[match] = newPosition
                oldTiles[match.tile].remove(match)
                if not len(oldTiles[match.tile]):
                    del oldTiles[match.tile]
        for newBonusPosition in self.newBonusPositions(list(x for x in tiles if x.isBonus()), newPositions):
            result[oldBonusTiles[newBonusPosition.tile][0]] = newBonusPosition # TODO: testen
        self._avoidCrossingMovements(result)
        for uiTile, newPos in result.items():
            uiTile.level = 0 # for tiles coming from the wall
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
            if uiTile.yoffset == 0 or uiTile.isBonus():
                physExposed.append(uiTile.tile)
            else:
                physConcealed.append(uiTile.tile)
        for meld in self.player.exposedMelds:
            logExposed.extend(meld)
        if self.player.concealedMelds:
            for meld in self.player.concealedMelds:
                logConcealed.extend(meld)
        else:
            logConcealed = sorted(self.player.concealedTileNames)
        logExposed.sort()
        physExposed.sort()
        logConcealed.sort()
        physConcealed.sort()
        assert logExposed == physExposed, '%s: exposed: player %s != hand %s. Check those:%s' % (
            self.player, logExposed, physExposed, set(logExposed) ^ set(physExposed))
        assert logConcealed == physConcealed, '%s: concealed: player %s != hand %s' % (
            self.player, logConcealed, physConcealed)

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
        focusCandidates = list(x for x in source if x.focusable)
        focusCandidates = sorted(focusCandidates, key=lambda x: x.xoffset)
        if focusCandidates:
            self.focusTile = focusCandidates[0]
        Internal.scene.handSelectorChanged(self)
        self.hasFocus = bool(adding)

    @Board.focusTile.setter
    def focusTile(self, uiTile): # pylint: disable=arguments-differ
        Board.focusTile.fset(self, uiTile)
        if self.player and Internal.scene.clientDialog:
# TODO: warum kann clientDialog None sein?
            Internal.scene.clientDialog.focusTileChanged()

    def setEnabled(self, enabled):
        """enable/disable this board"""
        if isAlive(self):
            # aborting a running game: the underlying C++ object might
            # already have been destroyed
            self.tileDragEnabled = enabled and self.player == self.player.game.myself
            QGraphicsRectItem.setEnabled(self, enabled)

    def dragMoveEvent(self, event): # pylint: disable=no-self-use
        """only dragging to discard board should be possible"""
        event.setAccepted(False)

    def _avoidCrossingMovements(self, places):
        """"the above is a good approximation but if the board already had more
        than one identical tile they often switch places - this should not happen.
        So for each element, we make sure that the left-right order is still the
        same as before. For this check, ignore all new tiles"""
        movingPlaces = self.__movingPlaces(places)
        for yOld in 0, self.lowerY:
            for yNew in 0, self.lowerY:
                items = [x for x in movingPlaces.items() \
                         if (x[0].board == self) \
                            and x[0].yoffset == yOld \
                            and x[1] and x[1].yoffset == yNew \
                            and not x[0].isBonus()]
                for element in set(x[1].tile for x in items):
                    items = [x for x in movingPlaces.items() if x[1].tile == element]
                    if len(items) > 1:
                        oldList = sorted(list(x[0] for x in items), key=lambda x:bool(x.board!=self)*1000+x.xoffset)
                        newList = sorted(list(x[1] for x in items), key=lambda x:x.xoffset)
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
                if tileItem.xoffset != newPos.xoffset or tileItem.yoffset != newPos.yoffset:
                    if newPos.yoffset == yOld:
                        smallestX = min(smallestX, newPos.xoffset)
                    else:
                        smallestX = min(smallestX, tileItem.xoffset)
            rows[idx] = [x for x in rowPlaces if x[0].xoffset >= smallestX and x[1].xoffset >= smallestX]
        result = dict(rows[0])
        result.update(dict(rows[1]))
        return result

    def newLowerMelds(self):
        """a list of melds for the hand as it should look after sync"""
        if self.player.concealedMelds:
            result = sorted(self.player.concealedMelds, key=meldKey)
        else:
            tileStr = 'R' + ''.join(str(x) for x in self.player.concealedTileNames)
            handStr = ' '.join([tileStr, self.player.mjString()])
            content = Hand.cached(self.player, handStr)
            result = list(Meld(x) for x in content.sortedMeldsContent.split())
            if result:
                if self.rearrangeMelds:
                    if result[0][0] == b'Xy':
                        result = sorted(result, key=len, reverse=True)
                else:
                    # generate one meld with all sorted tiles
                    result = [Meld(sorted(sum((x for x in result), []), key=elementKey))]
        return result

    def discard(self, tile):
        """select the rightmost matching tileItem and move it to DiscardBoard"""
        if self.focusTile and self.focusTile.tile == tile:
            lastDiscard = self.focusTile
        else:
            matchingTiles = sorted(self.tilesByElement(tile), key=lambda x:x.xoffset)
            # if an opponent player discards, we want to discard from the right end of the hand
            # thus minimizing tile movement within the hand
            lastDiscard = matchingTiles[-1]
        Internal.scene.discardBoard.discardTile(lastDiscard)
        for uiTile in self.uiTiles:
            uiTile.focusable = False
