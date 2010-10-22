# -*- coding: utf-8 -*-

"""
 (C) 2008,2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

from PyQt4.QtCore import QPointF, QRectF, QVariant
from PyQt4.QtGui import QGraphicsRectItem
from PyQt4.QtGui import QMenu, QCursor
from PyQt4.QtGui import QGraphicsSimpleTextItem
from tile import Tile
from meld import Meld, EXPOSED, CONCEALED, tileKey, meldKey, shortcuttedMeldName
from board import Board, rotateCenter

from util import logException, logWarning, debugMessage, m18n
import common
from common import InternalParameters
from tile import chiNext

class HandBoard(Board):
    """a board showing the tiles a player holds"""
    # pylint: disable-msg=R0904
    # pylint - we need more than 40 public methods
    # pylint: disable-msg=R0902
    # pylint - we need more than 10 instance attributes
    def __init__(self, player):
        self.exposedMeldDistance = 0.2
        self.concealedMeldDistance = 0.0
        self.rowDistance = 0
        Board.__init__(self, 15.4, 2.0 + self.rowDistance, InternalParameters.field.tileset)
        self.isHandBoard = True
        self.tileDragEnabled = False
        self.player = player
        self.setParentItem(player.front)
        self.setAcceptDrops(True)
        self.upperMelds = []
        self.lowerMelds = []
        self.flowers = []
        self.seasons = []
        self.__moveHelper = None
        self.__sourceView = None
        self.rearrangeMelds = common.PREF.rearrangeMelds
        self.setScale(1.5)
        self.showShadows = common.PREF.showShadows

    @apply
    # pylint: disable-msg=E0202
    def showShadows():
        """the active lightSource"""
        def fget(self):
            # pylint: disable-msg=W0212
            return self._showShadows
        def fset(self, value):
            """set active lightSource"""
            # pylint: disable-msg=W0212
            if self._showShadows is None or self._showShadows != value:
                if value:
                    self.setPos(yHeight= 1.5)
                else:
                    self.setPos(yHeight= 1.0)
                if value:
                    self.rowDistance = 0.2
                else:
                    self.rowDistance = 0
                self.setRect(15.4, 2.0 + self.rowDistance)
                self._reload(self.tileset, showShadows=value)
                self.placeTiles()
                if self.focusRect:
                    self.showFocusRect(self.focusTile)
        return property(**locals())

    @apply
    def rearrangeMelds(): # pylint: disable-msg=E0202
        """when setting this, concealed melds are grouped"""
        def fget(self):
            return bool(self.concealedMeldDistance)
        def fset(self, rearrangeMelds):
            if rearrangeMelds != self.rearrangeMelds:
                self.concealedMeldDistance = self.exposedMeldDistance if rearrangeMelds else 0.0
                self._reload(self.tileset, self._lightSource) # pylint: disable-msg=W0212
                self.placeTiles()
                if self.focusRect:
                    self.showFocusRect(self.focusTile)
        return property(**locals())

    def setEnabled(self, enabled):
        """enable/disable this board"""
        self.tileDragEnabled = enabled and \
        (self.player.game.isScoringGame() or self.player == self.player.game.myself)
        QGraphicsRectItem.setEnabled(self, enabled)

    def showMoveHelper(self, visible=True):
        """show help text In empty HandBoards"""
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

    def hide(self):
        """make self invisible"""
        self.showMoveHelper(False)
        Board.hide(self)

    def _focusRectWidth(self):
        """how many tiles are in focus rect? We want to focus
        the entire meld"""
        if not self.player.game.isScoringGame():
            # network game: always make only single tiles selectable
            return 1
        return len(self.meldWithTile(self.focusTile) or [1])

    @staticmethod
    def moveFocusToClientDialog():
        """if there is an active clientDialog, give it the focus"""
        field = InternalParameters.field
        if field and field.clientDialog and field.clientDialog.isVisible():
            field.clientDialog.activateWindow()

    def scoringString(self):
        """helper for __str__"""
        parts = [x.joined for x in self.lowerMelds + self.upperMelds]
        parts.extend(x.element for x in self.flowers + self.seasons)
        return ' '.join(parts)

    def __str__(self):
        return self.scoringString()

    def meldWithTile(self, tile):
        """returns the meld holding tile"""
        for melds in self.upperMelds, self.lowerMelds:
            for meld in melds:
                if tile in meld:
                    return meld

    @staticmethod
    def __removeTile(tile):
        """return the tile to the selector board"""
        if tile.element != 'Xy':
            InternalParameters.field.selectorBoard.tilesByElement(tile.element.lower())[0].push()
        tile.board = None
        del tile
        if InternalParameters.field.game:
            InternalParameters.field.game.checkSelectorTiles()

    def __addTile(self, tile):
        """get tile from the selector board, return tile"""
        if tile.element != 'Xy':
            selectorTiles = InternalParameters.field.selectorBoard.tilesByElement(tile.element.lower())
            assert selectorTiles, 'board.addTile: %s not available in selector' % tile.element
            if selectorTiles[0].count == 0:
                logWarning('Cannot add tile %s to handBoard for player %s' % (tile.element, self.player))
                for line in self.player.game.locateTile(tile.element):
                    logWarning(line)
            selectorTiles[0].pop()
        tile.board = self
        InternalParameters.field.game.checkSelectorTiles()
        return tile

    def remove(self, removeData):
        """return tile or meld to the selector board"""
        if not (self.focusTile and self.focusTile.hasFocus()):
            hadFocus = False
        elif isinstance(removeData, Tile):
            hadFocus = self.focusTile == removeData
        else:
            hadFocus = self.focusTile == removeData[0]
        if isinstance(removeData, Tile) and removeData.isBonus():
            self.__removeTile(removeData) # flower, season
        else:
            if not self.player.game.isScoringGame() and isinstance(removeData, Tile):
                self.__removeTile(removeData)
            else:
                if isinstance(removeData, Tile):
                    removeData = self.meldWithTile(removeData)
                assert removeData
                for tile in removeData.tiles:
                    self.__removeTile(tile)
        self.placeTiles()
        if hadFocus:
            self.focusTile = None # force calculation of new focusTile

    def clear(self):
        """return all tiles to the selector board"""
        for melds in self.upperMelds, self.lowerMelds:
            for meld in melds:
                self.remove(meld)
        for tiles in self.flowers, self.seasons:
            for tile in tiles:
                self.remove(tile)
        InternalParameters.field.handSelectorChanged(self)

    def _add(self, addData, lowerHalf=None):
        """get tile or meld from the selector board"""
        if isinstance(addData, Meld):
            addData.tiles = []
            for pair in addData.pairs:
                addData.tiles.append(self.__addTile(Tile(pair)))
            self.placeTiles()
            if self.player.game.isScoringGame():
                for tile in addData.tiles[1:]:
                    tile.focusable = False
            else:
                focusable = True
                if lowerHalf is not None and lowerHalf == False:
                    focusable = False
                if self.player != self.player.game.myself:
                    focusable = False
                for tile in addData.tiles:
                    tile.focusable = focusable
            if addData.tiles[0].focusable:
                self.focusTile = addData.tiles[0]
        else:
            tile = Tile(addData) # flower, season
            self.__addTile(tile)
            self.placeTiles()
            if self.player.game.isScoringGame():
                self.focusTile = tile
            else:
                tile.focusable = False

    def dragMoveEvent(self, event):
        """allow dropping of tile from ourself only to other state (open/concealed)"""
        tile = event.mimeData().tile
        localY = self.mapFromScene(QPointF(event.scenePos())).y()
        centerY = self.rect().height()/2.0
        newLowerHalf =  localY >= centerY
        noMansLand = centerY / 6
        if -noMansLand < localY - centerY < noMansLand and not tile.isBonus():
            doAccept = False
        elif tile.board != self:
            doAccept = True
        elif tile.isBonus():
            doAccept = False
        else:
            oldLowerHalf = tile.board.isHandBoard and tile in tile.board.lowerHalfTiles()
            doAccept = self.player.game.isScoringGame() and oldLowerHalf != newLowerHalf
        event.setAccepted(doAccept)

    def dropEvent(self, event):
        """drop a tile into this handboard"""
        tile = event.mimeData().tile
        lowerHalf = self.mapFromScene(QPointF(event.scenePos())).y() >= self.rect().height()/2.0
        if self.receiveTile(tile, lowerHalf):
            event.accept()
        else:
            event.ignore()
        self._noPen()

    def receiveMeld(self, tile, lowerHalf):
        """self receives a meld, lowerHalf says into which part.
        meld can also be a single bonus tile"""
        assert not isinstance(tile, Tile)
        if tile[0] in 'fy':
            assert len(tile) == 2
            if tile[0] == 'f':
                self.flowers.append(Tile(tile))
            else:
                self.seasons.append(Tile(tile))
            self._add(tile)
        else:
            meld = Meld(tile)
            assert lowerHalf or meld.pairs[0] != 'Xy', tile
            (self.lowerMelds if lowerHalf else self.upperMelds).append(meld)
            self._add(meld, lowerHalf)

    def receiveTile(self, tile, lowerHalf):
        """receive a Tile and return the meld this tile becomes part of"""
        senderHand = tile.board if tile.board.isHandBoard else None
        if senderHand == self and tile.isBonus():
            return tile
        added = self.integrate(tile, lowerHalf)
        if added:
            if senderHand == self:
                self.placeTiles()
                self.showFocusRect(added.tiles[0])
            else:
                if senderHand:
                    senderHand.remove(added)
                self._add(added)
            InternalParameters.field.handSelectorChanged(self)
        return added

    @staticmethod
    def __lineLength(melds):
        """the length of the melds in meld sizes when shown in the board"""
        return sum(len(meld) for meld in melds) + len(melds)//2

    def lowerHalfTiles(self):
        """returns a list with all single tiles of the lower half melds without boni"""
        return sum((x.tiles for x in self.lowerMelds), [])

    def exposedTiles(self):
        """returns a list with all single tiles of the lower half melds without boni"""
        return sum((x.tiles for x in self.upperMelds), [])

    def integrate(self, tile, lowerHalf):
        """place the dropped tile in its new board, possibly using
        more tiles from the source to build a meld"""
        if tile.isBonus():
            if tile.isFlower():
                self.flowers.append(tile)
            else:
                self.seasons.append(tile)
            return tile
        else:
            meld = self.__meldFromTile(tile, lowerHalf) # from other hand
            if not meld:
                return None
            meld.state = EXPOSED if not lowerHalf else CONCEALED
            assert lowerHalf or meld.pairs[0] != 'Xy', tile
            (self.lowerMelds if lowerHalf else self.upperMelds).append(meld)
            return meld

    def placeTiles(self):
        """place all tiles in HandBoard"""
        self.__removeForeignTiles()
        boni = self.flowers + self.seasons
        bonusY = 1.0 + self.rowDistance
        upperLen = self.__lineLength(self.upperMelds) + self.exposedMeldDistance
        lowerLen = self.__lineLength(self.lowerMelds) + self.concealedMeldDistance
        if upperLen < lowerLen :
            bonusY = 0
        self.upperMelds = sorted(self.upperMelds, key=meldKey)
        self.lowerMelds = sorted(self.lowerMelds, key=meldKey)

        if common.PREF.rearrangeMelds:
            lowerMelds = self.lowerMelds
        else:
            # generate one meld with all sorted tiles
            lowerMelds = [Meld(sorted(sum((x.tiles for x in self.lowerMelds), []), key=tileKey))]
        for yPos, melds in ((0, self.upperMelds), (1.0 + self.rowDistance, lowerMelds)):
            meldDistance = self.concealedMeldDistance if yPos else self.exposedMeldDistance
            meldX = 0
            meldY = yPos
            for meld in melds:
                for idx, tile in enumerate(meld):
                    tile.setPos(meldX, meldY)
                    tile.dark = meld.pairs[idx].istitle() and (yPos== 0 or self.player.game.isScoringGame())
                    meldX += 1
                meldX += meldDistance
        lastBonusX = max(lowerLen,  upperLen) + len(boni)
        if lastBonusX > self.xWidth:
            lastBonusX = self.xWidth
        self.__showBoni(boni, lastBonusX, bonusY)
        self.setDrawingOrder()

    def __showBoni(self, bonusTiles, lastBonusX, bonusY):
        """show bonus tiles in HandBoard"""
        xPos = 13 - len(bonusTiles)
        if lastBonusX > xPos:
            xPos = lastBonusX
        for bonus in sorted(bonusTiles, key=tileKey):
            bonus.board = self
            bonus.setPos(xPos, bonusY)
            xPos += 1

    def __removeForeignTiles(self):
        """remove tiles/melds from our lists that no longer belong to our board"""
        normalMelds = set(meld for meld in self.upperMelds + self.lowerMelds \
                        if len(meld.tiles) and meld[0].board == self)
        self.upperMelds = list(meld for meld in normalMelds if meld.state !=
                        CONCEALED or meld.isKong()) # includes CLAIMEDKONG
        self.lowerMelds = list(meld for meld in normalMelds if meld not in self.upperMelds)
        tiles = self.allTiles()
        unknownTiles = list([tile for tile in tiles if not tile.isBonus() \
                        and not self.meldWithTile(tile)])
        if len(unknownTiles):
            debugMessage('%s upper melds:%s' % (self.player, ' '.join([x.joined for x in self.upperMelds])))
            debugMessage('%s lower melds:%s' % (self.player, ' '.join([x.joined for x in self.lowerMelds])))
            debugMessage('%s unknown tiles: %s' % (self.player, ' '.join(unknownTiles)))
            logException("board %s is inconsistent, see debug output" % self.player.name)
        self.flowers = list(tile for tile in tiles if tile.isFlower())
        self.seasons = list(tile for tile in tiles if tile.isSeason())
        if self.__moveHelper:
            self.__moveHelper.setVisible(not tiles)

    def __meldVariants(self, tile, lowerHalf):
        """returns a list of possible variants based on the dropped tile.
        The Variants are scoring strings. Do not use the real tiles because we
        change their properties"""
        lowerName = tile.lower()
        upperName = tile.upper()
        if lowerHalf:
            scName = upperName
        else:
            scName = lowerName
        variants = [scName]
        baseTiles = InternalParameters.field.selectorBoard.tilesByElement(tile.element.lower())[0].count
        if baseTiles >= 2:
            variants.append(scName * 2)
        if baseTiles >= 3:
            variants.append(scName * 3)
        if baseTiles == 4:
            if lowerHalf:
                variants.append(lowerName + upperName * 2 + lowerName)
            else:
                variants.append(lowerName * 4)
                variants.append(lowerName * 3 + upperName)
        if not tile.isHonor() and tile.element[-1] < '8':
            chow2 = chiNext(tile.element, 1)
            chow3 = chiNext(tile.element, 2)
            chow2 = InternalParameters.field.selectorBoard.tilesByElement(chow2.lower())[0]
            chow3 = InternalParameters.field.selectorBoard.tilesByElement(chow3.lower())[0]
            if chow2.count and chow3.count:
                baseChar = scName[0]
                baseValue = ord(scName[1])
                varStr = '%s%s%s%s%s' % (scName, baseChar, chr(baseValue+1), baseChar, chr(baseValue+2))
                variants.append(varStr)
        return [Meld(x) for x in variants]

    def __meldFromTile(self, tile, lowerHalf):
        """returns a meld, lets user choose between possible meld types"""
        if tile.board.isHandBoard:
            meld = tile.board.meldWithTile(tile)
            assert meld
            if not lowerHalf and len(meld) == 4 and meld.state == CONCEALED:
                pair0 = meld.pairs[0].lower()
                meldVariants = [Meld(pair0*4), Meld(pair0*3 + pair0.capitalize())]
                for variant in meldVariants:
                    variant.tiles = meld.tiles
            else:
                return meld
        else:
            meldVariants = self.__meldVariants(tile, lowerHalf)
        idx = 0
        if len(meldVariants) > 1:
            menu = QMenu(m18n('Choose from'))
            for idx, variant in enumerate(meldVariants):
                action = menu.addAction(shortcuttedMeldName(variant.meldType))
                action.setData(QVariant(idx))
            if InternalParameters.field.centralView.dragObject:
                menuPoint = QCursor.pos()
            else:
                menuPoint = self.tileFaceRect().bottomRight()
                view = InternalParameters.field.centralView
                menuPoint = view.mapToGlobal(view.mapFromScene(tile.mapToScene(menuPoint)))
            action = menu.exec_(menuPoint)
            if not action:
                return None
            idx = action.data().toInt()[0]
        if tile.board == self:
            meld.tiles = []
        return meldVariants[idx]

