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

from PyQt4.QtCore import QPointF, QRectF
from PyQt4.QtGui import QGraphicsRectItem
from PyQt4.QtGui import QGraphicsSimpleTextItem
from tile import Tile
from uitile import UITile
from meld import Meld, CONCEALED, REST, tileKey, elementKey, meldKey
from hand import Hand
from board import Board, rotateCenter

from util import m18n, logDebug
from common import Preferences, Internal, Debug, isAlive
from animation import animate

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
            scoring = isinstance(hand, ScoringHandBoard)
            if yoffset == 0:
                self.dark = self.tile.istitle()
            else:
                self.dark = self.tile == 'Xy' or scoring
            self.focusable = True
            if scoring:
                self.focusable = idx == 0
            else:
                self.focusable = (self.tile[0] not in 'fy'
                    and self.tile != 'Xy'
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
        self.exposedMeldDistance = 0.15
        self.concealedMeldDistance = 0.0
        self.lowerY = 1.0
        self.player = player
        Board.__init__(self, 15.6, 2.0, Internal.field.tileset)
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
    def showShadows(self):
        """the active value"""
        return self._showShadows

    # this is ordered such that pylint does not complain about identical code in board.py

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
        return list(x for x in self.tiles if x.yoffset > 0 and not x.isBonus())

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
                or oldTiles.get('Xy')
            if not matches and newPosition.tile == 'Xy':
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
        for tile, newPos in result.items():
            tile.level = 0 # for tiles coming from the wall
            tile.tile = newPos.tile
            tile.setBoard(self, newPos.xoffset, newPos.yoffset)
            tile.dark = newPos.dark
            tile.focusable = newPos.focusable
        return result

    def _avoidCrossingMovements(self, places):
        """not needed for all HandBoards"""
        pass

    def sync(self, adding=None):
        """place all tiles in HandBoard.
        adding tiles: their board is where they come from. Those tiles
        are already in the Player tile lists.
        The sender board must not be self, see ScoringPlayer.moveMeld"""
        if not self.tiles and not adding:
            return
        allTiles = self.tiles[:]
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
        for tile in self.tiles:
            if tile.yoffset == 0 or tile.isBonus():
                physExposed.append(tile.tile)
            else:
                physConcealed.append(tile.tile)
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
        assert logExposed == physExposed, '%s: exposed: player %s != hand %s' % (
            self.player, logExposed, physExposed)
        assert logConcealed == physConcealed, '%s: concealed: player %s != hand %s' % (
            self.player, logConcealed, physConcealed)

class ScoringHandBoard(HandBoard):
    """a board showing the tiles a player holds"""
    # pylint: disable=too-many-public-methods,too-many-instance-attributes
    def __init__(self, player):
        self.__moveHelper = None
        self.uiMelds = []
        HandBoard.__init__(self, player)

    def meldVariants(self, tile, lowerHalf):
        """Kong might have variants"""
        meld = Meld(self.uiMeldWithTile(tile))
        if lowerHalf:
            meld.toUpper()
        else:
            meld.toLower()
        result = [meld]
        if len(meld) == 4:
            if lowerHalf:
                meld.toLower()
                meld.toUpper(1, 3)
            else:
                meld2 = Meld(meld)
                meld2.expose(isClaiming=True)
                result.append(meld2)
        return result

    def uiMeldWithTile(self, uiTile):
        """returns the meld with uiTile"""
        for myMeld in self.uiMelds:
            if uiTile in myMeld:
                return myMeld

    def assignUITiles(self, tile, meld): # pylint: disable=unused-argument
        """generate a UIMeld. First tile is given, the rest should be as defined by meld"""
        assert isinstance(tile, UITile), tile
        return self.uiMeldWithTile(tile)

    def autoSelectTile(self):
        Board.autoSelectTile(self)
        self.showMoveHelper()

    def sync(self, adding=None): # pylint: disable=unused-argument
        """place all tiles in ScoringHandBoard"""
        self.calcPlaces(sum(self.uiMelds, []))

    def hide(self):
        """make self invisible"""
        self.showMoveHelper(False)
        Board.hide(self)

    def deselect(self, meld):
        """remove meld from old board"""
        for idx, uiMeld in enumerate(self.uiMelds):
            if all(id(meld[x]) == id(uiMeld[x]) for x in range(len(meld))):
                del self.uiMelds[idx] # do not use uiMelds.remove: If we have 2
                break                 # identical melds, it removes the wrong one
        self.player.removeMeld(Meld(meld))      # uiMeld must already be deleted
        Internal.field.handSelectorChanged(self)
        self.showMoveHelper()

    def dragMoveEvent(self, event):
        """allow dropping of tile from ourself only to other state (open/concealed)"""
        tile = event.mimeData().tile
        localY = self.mapFromScene(QPointF(event.scenePos())).y()
        centerY = self.rect().height()/2.0
        newLowerHalf = localY >= centerY
        noMansLand = centerY / 6
        if -noMansLand < localY - centerY < noMansLand and not tile.isBonus():
            doAccept = False
        elif tile.board != self:
            doAccept = True
        elif tile.isBonus():
            doAccept = False
        else:
            oldLowerHalf = tile.board.isHandBoard and tile in tile.board.lowerHalfTiles()
            doAccept = oldLowerHalf != newLowerHalf
        event.setAccepted(doAccept)

    def dropEvent(self, event):
        """drop into this handboard"""
        tile = event.mimeData().tile
        lowerHalf = self.mapFromScene(QPointF(event.scenePos())).y() >= self.rect().height()/2.0
        if self.dropTile(tile, lowerHalf):
            event.accept()
        else:
            event.ignore()
        self._noPen()

    def dropTile(self, tile, lowerHalf):
        """drop meld or tile into lower or upper half of our hand"""
        senderBoard = tile.board
        self.checkTiles()
        senderBoard.checkTiles()
        newMeld = senderBoard.chooseVariant(tile, lowerHalf)
        if not newMeld:
            self.checkTiles()
            senderBoard.checkTiles()
            return False
        uiMeld = senderBoard.assignUITiles(tile, newMeld)
        senderBoard.deselect(uiMeld)
        for uiTile, tile in zip(uiMeld, newMeld):
            uiTile.tile = tile
        self.uiMelds.append(uiMeld)
        self.player.addMeld(newMeld)
        self.sync()
        self.hasFocus = senderBoard == self or not senderBoard.tiles
        self.showMoveHelper()
        self.checkTiles()
        senderBoard.autoSelectTile()
        senderBoard.checkTiles()
        Internal.field.handSelectorChanged(self)
        animate()
        self.checkTiles()
        return True

    def focusRectWidth(self):
        """how many tiles are in focus rect? We want to focus
        the entire meld"""
        meld = self.uiMeldWithTile(self.focusTile)
        if not meld:
            logDebug('%s: no meld found in %s' % (
                self.focusTile, self.uiMelds))
        return len(meld)

    def showMoveHelper(self, visible=None):
        """show help text In empty HandBoards"""
        if visible is None:
            visible = not self.tiles
        if self.__moveHelper and not isAlive(self.__moveHelper):
            return
        if visible:
            if not self.__moveHelper:
                splitter = QGraphicsRectItem(self)
                hbCenter = self.rect().center()
                splitter.setRect(hbCenter.x() * 0.5, hbCenter.y(), hbCenter.x() * 1, 1)
                helpItems = [splitter]
                for name, yFactor in [(m18n('Move Exposed Tiles Here'), 0.5),
                                        (m18n('Move Concealed Tiles Here'), 1.5)]:
                    helper = QGraphicsSimpleTextItem(name, self)
                    helper.setScale(3)
                    nameRect = QRectF()
                    nameRect.setSize(helper.mapToParent(helper.boundingRect()).boundingRect().size())
                    center = QPointF(hbCenter)
                    center.setY(center.y() * yFactor)
                    helper.setPos(center - nameRect.center())
                    if self.sceneRotation() == 180:
                        rotateCenter(helper, 180)
                    helpItems.append(helper)
                self.__moveHelper = self.scene().createItemGroup(helpItems)
            self.__moveHelper.setVisible(True)
        else:
            if self.__moveHelper:
                self.__moveHelper.setVisible(False)

    def newLowerMelds(self):
        """a list of melds for the hand as it should look after sync"""
        return list(self.player.concealedMelds)

class PlayingHandBoard(HandBoard):
    """a board showing the tiles a player holds"""
    # pylint: disable=too-many-public-methods,too-many-instance-attributes
    def __init__(self, player):
        HandBoard.__init__(self, player)

    def sync(self, adding=None):
        """place all tiles in HandBoard"""
        allTiles = self.tiles[:]
        if adding:
            allTiles.extend(adding)
        newPlaces = self.calcPlaces(allTiles)
        source = adding if adding else newPlaces.keys()
        focusCandidates = list(x for x in source if x.focusable)
        focusCandidates = sorted(focusCandidates, key=lambda x: x.xoffset)
        if focusCandidates:
            self.focusTile = focusCandidates[0]
        Internal.field.handSelectorChanged(self)
        self.hasFocus = bool(adding)

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
                    if result[0][0] == 'Xy':
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
        Internal.field.discardBoard.discardTile(lastDiscard)
        for tile in self.tiles:
            tile.focusable = False
