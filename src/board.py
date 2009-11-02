#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
 (C) 2008,2009 Wolfgang Rohdewald <wolfgang@rohdewald.de>

kmj is free software you can redistribute it and/or modify
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

from PyQt4.QtCore import Qt, QPointF,  QPoint,  QRectF, QMimeData,  SIGNAL, QVariant
from PyQt4.QtGui import  QGraphicsRectItem, QGraphicsItem,  QSizePolicy, QFrame, QGraphicsItemGroup
from PyQt4.QtGui import  QMenu, QCursor, QGraphicsView,  QGraphicsEllipseItem,  QGraphicsScene, QLabel
from PyQt4.QtGui import QColor, QPainter, QDrag, QPixmap, QStyleOptionGraphicsItem, QPen
from PyQt4.QtSvg import QGraphicsSvgItem
from tileset import Tileset, TileException,  LIGHTSOURCES, Elements
from tile import Tile
from scoringengine import Meld, EXPOSED, CONCEALED, meldContent, shortcuttedMeldName

import random
import weakref

import util
from util import logException, WINDS, m18n, m18nc, rotateCenter

ROUNDWINDCOLOR = QColor(235, 235, 173)

WINDPIXMAPS = {}

class PlayerWind(QGraphicsEllipseItem):
    """a round wind tile"""
    def __init__(self, name, tileset, roundsFinished=0, parent = None):
        """generate new wind tile"""
        if not len(WINDPIXMAPS):
            WINDPIXMAPS[('E', False)] = None  # avoid recursion
            self.genWINDPIXMAPS()
        QGraphicsEllipseItem.__init__(self)
        if parent:
            self.setParentItem(parent)
        self.name = name
        self.face = QGraphicsSvgItem()
        self.face.setParentItem(self)
        self.prevailing = None
        self.setWind(name, roundsFinished)
        self.tileset = tileset
        self.__sizeFace()

    @staticmethod
    def genWINDPIXMAPS():
        """prepare wind tiles"""
        tileset = Tileset(util.PREF.windTilesetName)
        for wind in WINDS:
            for prevailing in False, True:
                pwind = PlayerWind(wind, tileset, prevailing)
                pMap = QPixmap(40, 40)
                pMap.fill(Qt.transparent)
                painter = QPainter(pMap)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.scale(0.40, 0.40)
                pwind.paint(painter, QStyleOptionGraphicsItem())
                for child in pwind.childItems():
                    if isinstance(child, QGraphicsSvgItem):
                        painter.save()
                        painter.translate(child.mapToParent(0.0, 0.0))
                        child.paint(painter, QStyleOptionGraphicsItem())
                        painter.restore()
                WINDPIXMAPS[(wind, prevailing)] = pMap

    def __sizeFace(self):
        """size the chinese character depending on the wind tileset"""
        self.resetTransform()
        size = self.tileset.faceSize
        self.setFlag(QGraphicsItem.ItemClipsChildrenToShape)
        if self.tileset.desktopFileName == 'traditional':
            diameter = size.height()*1.1
            self.setRect(0, 0, diameter, diameter)
            self.scale(1.2, 1.2)
            self.face.setPos(10, 10)
        elif self.tileset.desktopFileName == 'default':
            diameter = size.height()*1.1
            self.setRect(0, 0, diameter, diameter)
            self.scale(1.2, 1.2)
            self.face.setPos(15, 10)
        elif self.tileset.desktopFileName == 'classic':
            diameter = size.height()*1.1
            self.setRect(0, 0, diameter, diameter)
            self.scale(1.2, 1.2)
            self.face.setPos(19, 1)
        elif self.tileset.desktopFileName == 'jade':
            diameter = size.height()*1.1
            self.setRect(0, 0, diameter, diameter)
            self.scale(1.2, 1.2)
            self.face.setPos(19, 1)
        self.face.setSharedRenderer(self.tileset.renderer())
        self.scale(0.75, 0.75)

    def setWind(self, name,  roundsFinished):
        """change the wind"""
        self.name = name
        if isinstance(roundsFinished, bool):
            self.prevailing = roundsFinished
        else:
            self.prevailing = name == WINDS[roundsFinished]
        self.setBrush(ROUNDWINDCOLOR if self.prevailing else QColor('white'))
        windtilenr = {'N':1, 'S':2, 'E':3, 'W':4}
        self.face.setElementId('WIND_%d' % windtilenr[name])

class WindLabel(QLabel):
    """QLabel holding the wind tile"""
    def __init__(self, wind = None, roundsFinished = 0, parent=None):
        QLabel.__init__(self, parent)
        self.__wind = None
        if wind is None:
            wind = 'E'
        self.__roundsFinished = roundsFinished
        self.wind = wind

    @apply
    def wind():
        def fget(self):
            return self.__wind
        def fset(self, wind):
            if self.__wind != wind:
                self.__wind = wind
                self._refresh()
        return property(**locals())

    @apply
    def roundsFinished():
        def fget(self):
            return self.__roundsFinished
        def fset(self, roundsFinished):
            if self.__roundsFinished != roundsFinished:
                self.__roundsFinished = roundsFinished
                self._refresh()
        return property(**locals())

    def _refresh(self):
        PlayerWind.genWINDPIXMAPS()
        self.setPixmap(WINDPIXMAPS[(self.__wind,
            self.__wind == WINDS[min(self.__roundsFinished, 3)])])

class Board(QGraphicsRectItem):
    """ a board with any number of positioned tiles"""
    def __init__(self, width, height, tileset, tiles=None,  rotation = 0):
        QGraphicsRectItem.__init__(self)
        self._focusTile = None
        self.focusRect = None
        self._noPen()
        self.tileDragEnabled = False
        self.rotation = rotation
        self.rotate(rotation)
        self._lightSource = 'NW'
        self.xWidth = 0
        self.xHeight = 0
        self.yWidth = 0
        self.yHeight = 0
        self.__fixedWidth = width
        self.__fixedHeight = height
        self.__tileset = None
        self.tileset = tileset
        self.level = 0
        if tiles:
            for tile in tiles:
                tile.board = self

    @apply
    def focusTile():
        def fget(self):
            if self._focusTile is None:
                focusableTiles = self.__focusableTiles()
                if len(focusableTiles):
                    self._focusTile = weakref.ref(focusableTiles[0])
            return self._focusTile() if self._focusTile else None
        def fset(self, tile):
            if tile:
                self._focusTile = weakref.ref(tile)
            else:
                self._focusTile = None
        return property(**locals())

    def setEnabled(self, enabled):
        """enable/disable this board"""
        self.tileDragEnabled = enabled
        QGraphicsRectItem.setEnabled(self, enabled)

    def allTiles(self, sortDir=Qt.Key_Right):
        """returns a list of all tiles in this board sorted such that
        moving in the sortDir direction corresponds to going to
        the next list element.
        respect board orientation: Right Arrow should always move right
        relative to the screen, not relative to the board"""
        dirs = [Qt.Key_Right, Qt.Key_Down, Qt.Key_Left, Qt.Key_Up] * 2
        sorter = dirs[dirs.index(sortDir) + self.sceneRotation()//90]
        if sorter == Qt.Key_Down:
            sortFunction = lambda x: x.xoffset * 100 + x.yoffset
        elif sorter == Qt.Key_Up:
            sortFunction = lambda x: -x.xoffset * 100 - x.yoffset
        elif sorter == Qt.Key_Left:
            sortFunction = lambda x: -x.yoffset * 100 - x.xoffset
        else:
            sortFunction = lambda x: x.yoffset * 100 + x.xoffset
        return sorted(list(x for x in self.childItems() if isinstance(x, Tile)),
            key=sortFunction)

    def __focusableTiles(self, sortDir=Qt.Key_Right):
        """returns a list of all focusable tiles in this board sorted by y then x"""
        return list(x for x in self.allTiles(sortDir) if x.isFocusable())

    def __row(self, yoffset):
        """a list with all tiles at yoffset sorted by xoffset"""
        return list(tile for tile in self.__focusableTiles() if tile.yoffset == yoffset)

    def __column(self, xoffset):
        """a list with all tiles at xoffset sorted by yoffset"""
        return list(tile for tile in self.__focusableTiles() if tile.xoffset == xoffset)

    def keyPressEvent(self, event):
        """navigate in the board"""
        key = event.key()
        arrows = (Qt.Key_Left, Qt.Key_Down, Qt.Key_Up, Qt.Key_Right)
        charArrows = m18nc('kmj:arrow keys hjkl like in the vi editor', 'HJKL')
        if chr(key%256) in charArrows:
            key = arrows[charArrows.index(chr(key%256))]
        if key in arrows:
            self.__moveCursor(key)
            return
        QGraphicsRectItem.keyPressEvent(self, event)

    def __moveCursor(self, key):
        """move focus"""
        tiles = self.__focusableTiles(key)
        tiles = list(x for x in tiles if x.opacity or x == self.focusTile)
        tiles.append(tiles[0])
        tiles[tiles.index(self.focusTile)+1].setFocus()

    def dragEnterEvent(self, event):
        """drag enters the HandBoard: highlight it"""
        assert event # quieten pylint
        self.setPen(QPen(QColor('blue')))

    def dragLeaveEvent(self, event):
        """drag leaves the HandBoard"""
        assert event # quieten pylint
        self._noPen()

    def _noPen(self):
        """remove pen for this board. The pen defines the border"""
        self.setPen(QPen(Qt.NoPen))


    def tileAt(self, xoffset, yoffset, level=0):
        """if there is a tile at this place, return it"""
        for tile in self.allTiles():
            if (tile.xoffset, tile.yoffset, tile.level) == (xoffset, yoffset, level):
                return tile

    def tilesByElement(self, element):
        """returns all child items hold a tile for element"""
        return list(tile for tile in self.childItems() \
                    if isinstance(tile, Tile) and tile.element == element)

    def lightDistance(self, item):
        """the distance of item from the light source"""
        rect = item.sceneBoundingRect()
        result = 0
        if 'E' in self.lightSource:
            result -= rect.right()
        if 'W' in self.lightSource:
            result += rect.left()
        if 'S' in self.lightSource:
            result -= rect.bottom()
        if 'N' in self.lightSource:
            result += rect.top()
        return result

    def rotatedLightSource(self):
        """the light source we need for the original tile before it is rotated"""
        lightSourceIndex = LIGHTSOURCES.index(self.lightSource)
        lightSourceIndex = (lightSourceIndex+self.sceneRotation() // 90)%4
        return LIGHTSOURCES[lightSourceIndex]

    def sceneRotation(self):
        """the combined rotation of self and all parents"""
        matrix = self.sceneTransform()
        matrix = (int(matrix.m11()), int(matrix.m12()), int(matrix.m21()), int(matrix.m22()))
        return [(1, 0, 0, 1), (0, 1, -1, 0), (-1, 0, 0, -1), (0, -1, 1, 0)].index(matrix) * 90

    def setPos(self, xWidth=0, xHeight=0, yWidth=0, yHeight=0):
        """sets the position in the parent item expressing the position in tile face units.
        The X position is xWidth*facewidth + xHeight*faceheight, analog for Y"""
        self.xWidth = xWidth
        self.xHeight = xHeight
        self.yWidth = yWidth
        self.yHeight = yHeight
        self.setGeometry()

    def setRect(self, width, height):
        """gives the board a fixed size in tile coordinates"""
        self.__fixedWidth = width
        self.__fixedHeight = height
        self._setRect()

    def _setRect(self):
        """translate from our rect coordinates to scene coord"""
        sizeX = self.tileset.faceSize.width() * self.__fixedWidth + self.tileset.shadowWidth()
        sizeY = self.tileset.faceSize.height() * self.__fixedHeight + self.tileset.shadowHeight()
        rect = self.rect()
        rect.setWidth(sizeX)
        rect.setHeight(sizeY)
        self.prepareGeometryChange()
        QGraphicsRectItem.setRect(self, rect)

    @property
    def width(self):
        """getter for width"""
        return self.__fixedWidth

    def setGeometry(self):
        """move the board to the correct position and set its rect surrounding all its
        items. This is needed for enabling drops into the board.
        This is also called when the tileset or the light source for this board changes"""
        width = self.tileset.faceSize.width()
        height = self.tileset.faceSize.height()
        if isinstance(self, HandBoard):
            offsets = (0, 0)
        else:
            offsets = self.tileset.shadowOffsets(self._lightSource, self.sceneRotation())
        newX = self.xWidth*width+self.xHeight*height + offsets[0]
        newY = self.yWidth*width+self.yHeight*height + offsets[1]
        QGraphicsRectItem.setPos(self, newX, newY)

    @apply
    def lightSource():
        """the active lightSource"""
        def fget(self):
            return self._lightSource
        def fset(self, lightSource):
            """set active lightSource"""
            if self._lightSource != lightSource:
                if   lightSource not in LIGHTSOURCES:
                    logException(TileException('lightSource %s illegal' % lightSource))
                self.__reload(self.tileset, lightSource)
        return property(**locals())

    @apply
    def tileset():
        """get/set the active tileset and resize accordingly"""
        def fget(self):
            if self.__tileset:
                return self.__tileset
            elif self.parentItem():
                return self.parentItem().tileset
            elif isinstance(self, Board):
                return Tileset('default')
        def fset(self, tileset):
            self.__reload(tileset, self._lightSource)
        return property(**locals())

    def __reload(self, tileset=None, lightSource=None):
        """call this if tileset or lightsource change: recomputes the entire board"""
        if tileset is None:
            tileset = self.tileset
        if lightSource is None:
            lightSource = self._lightSource
        if self.__tileset != tileset or self._lightSource != lightSource:
            self.prepareGeometryChange()
            self.__tileset = tileset
            self._lightSource = lightSource
            for child in self.childItems():
                if isinstance(child, (Board, PlayerWind)):
                    child.tileset = tileset
                    child.lightSource = lightSource
                elif isinstance(child, Tile):
                    child.board = self # tile will reposition itself
            self._setRect()
            self.setGeometry()
            self.setDrawingOrder()
            self.__placeFocusRect()

    def showFocusRect(self, tile):
        """show a blue rect around tile"""
        self.hideFocusRect()
        self.focusTile = tile
        self.focusRect = QGraphicsRectItem()
        pen = QPen(QColor(Qt.blue))
        pen.setWidth(6)
        self.focusRect.setPen(pen)
        self.focusRect.setParentItem(self)
        self.focusRect.setZValue(99999999999)
        self.__placeFocusRect()
        # if the board window is unselected and we select it
        # by clicking on another tile, the previous tile keeps
        # its focusRect unless we call update here. Qt4.5
        # it would be even nicer if the focusRect of the previous
        # tile would not show up for a split second.
        self.update()

    def __placeFocusRect(self):
        """size and position the blue focus rect"""
        if self.focusRect:
            rect = QRectF(self.focusTile.facePos(), self.focusTile.tileset.faceSize)
            rect.setWidth(rect.width()*self._focusRectWidth())
            self.focusRect.setRect(self.focusTile.mapToParent(rect).boundingRect())

    def hideFocusRect(self):
        """hides the focus rect"""
        if self.focusRect:
            self.focusRect.hide()
        self.focusRect = None

    def _focusRectWidth(self):
        """how many tiles are in focus rect?"""
        if not self:
            assert True # quieten pylint
        return 1

    def shiftZ(self, level):
        """used for 3D: compute the needed shift for the tile.
        level is the vertical position. 0 is the face position on
        ground level, -1 is the imprint a tile makes on the
        surface it stands on"""
        shiftX = 0
        shiftY = 0
        if level != 0:
            lightSource = self.rotatedLightSource()
            stepX = level*self.tileset.shadowWidth()/2
            stepY = level*self.tileset.shadowHeight()/2
            if 'E' in lightSource:
                shiftX = stepX
            if 'W' in lightSource:
                shiftX = -stepX
            if 'N' in lightSource:
                shiftY = -stepY
            if 'S' in lightSource:
                shiftY = stepY
        return QPointF(shiftX, shiftY)

    def setDrawingOrder(self):
        """the tiles are painted by qt in the order in which they were
        added to the board widget. So if we place a tile between
        existing tiles, we have to reassign the following tiles.
        When calling setDrawingOrder, the tiles must already have positions
        and sizes"""
        for item in self.childItems():
            if isinstance(item, (Tile, Board)):
                item.setZValue((item.level+1)*100000+self.lightDistance(item))

    def tileSize(self):
        """the current tile size"""
        return self.__tileset.tileSize

    def faceSize(self):
        """the current face size"""
        return self.__tileset.faceSize

class SelectorTile(Tile):
    """tile with count. If count>0, show tile"""
    def __init__(self, element, count, xoffset=0, yoffset=0):
        Tile.__init__(self, element, xoffset, yoffset)
        self.count = count

    def pop(self):
        """reduce count by 1"""
        assert self.count > 0
        self.count -= 1
        if not self.count:
            self.setOpacity(0.0)

    def push(self):
        """increase count by 1"""
        assert self.count < 4
        self.count += 1
        if self.count:
            self.setOpacity(1.0)

class SelectorBoard(Board):
    """a board containing all possible tiles for selection"""
    __rows = {'CHARACTER':0,  'BAMBOO':1,  'ROD':2, 'WIND':3, 'DRAGON':3, 'SEASON':4, 'FLOWER':4}

    def __init__(self, tileset):
        Board.__init__(self, 9, 5, tileset)
        self.setAcceptDrops(True)
        for tile in Elements.elements.available:
            for idx in range(1, tile.high+1):
                self.placeAvailable(SelectorTile(tile.name + '_' + str(idx), tile.occurrence))
        self.setDrawingOrder()

    def dropEvent(self, event):
        """drop a tile into the selector"""
        self.receive(self.scene().clickedTile)
        event.accept()

    def receive(self, tile):
        """self receives a tile"""
        senderHand = tile.board if isinstance(tile.board, HandBoard) else None
        if senderHand: # None if we are already in the selectorboard. Do not send to self.
            senderHand.remove(tile)
            self._noPen()
            self.scene().field.handSelectorChanged(senderHand)

    def placeAvailable(self, tile):
        """place the tile in the selector at its place"""
        parts = tile.element.split('_')
        column = int(parts[1])-1
        if parts[0] == 'DRAGON':
            column += 6
        elif parts[0] == 'FLOWER':
            column += 5
        elif parts[0] == 'WIND':
            column += [3, 0, -2, -1][column]
        row = SelectorBoard.__rows[parts[0]]
        tile.board = self
        tile.setPos(column, row)

    def elementTiles(self, element):
        """returns all tiles with this element"""
        return list(item for item in self.childItems() if item.element == element)

class HandBoard(Board):
    """a board showing the tiles a player holds"""
    def __init__(self, playerGUI):
        self.meldDistance = 0.3
        self.rowDistance = 0.2
        Board.__init__(self, 22.7, 2.0 + self.rowDistance, playerGUI.field.tileset)
        self.tileDragEnabled = False
        self.playerGUI = playerGUI
        self.selector = playerGUI.field.selectorBoard
        self.setParentItem(playerGUI.wall)
        self.setAcceptDrops(True)
        self.upperMelds = []
        self.lowerMelds = []
        self.flowers = []
        self.seasons = []
        self.lowerHalf = False # quieten pylint
        self.helperGroup = QGraphicsItemGroup()
        self.scene().addItem(self.helperGroup)
        splitter = QGraphicsRectItem(self)
        center = self.rect().center()
        center.setX(self.playerGUI.wall.center().x())
        splitter.setRect(center.x() * 0.5, center.y(), center.x() * 1, 1)
        helpItems = [splitter]
        for name, yFactor in [(m18n('Move Exposed Tiles Here'), 0.5), (m18n('Move Concealed Tiles Here'), 3)]:
            helper = self.scene().addSimpleText(name)
            helper.setParentItem(self)
            helper.scale(3, 3)
            nameRect = QRectF()
            nameRect.setSize(helper.mapToParent(helper.boundingRect()).boundingRect().size())
            center.setY(center.y() * yFactor)
            helper.setPos(center - nameRect.center())
            if self.sceneRotation() == 180:
                rotateCenter(helper, 180)
            helpItems.append(helper)
        self.helperGroup = self.scene().createItemGroup(helpItems)
        self.__sourceView = None

    def _focusRectWidth(self):
        """how many tiles are in focus rect? We want to focus
        the entire meld"""
        return len(self.meldWithTile(self.focusTile) or [1])

    def allMelds(self):
        """returns a list containing all melds"""
        return self.lowerMelds + self.upperMelds + self.flowers + self.seasons

    def scoringString(self):
        """helper for __str__"""
        return ' '.join(x.content for x in self.allMelds())

    def __str__(self):
        return self.scoringString()

    def meldWithTile(self, tile):
        """returns the meld holding tile"""
        for melds in self.upperMelds, self.lowerMelds:
            for meld in melds:
                if tile in meld:
                    return meld

    def __removeTile(self, tile):
        """return the tile to the selector board"""
        self.selector.tilesByElement(tile.element)[0].push()
        self.hideFocusRect()
        tile.hide()
        tile.board = None
        del tile

    def __addTile(self, tile):
        """get tile from the selector board, return tile"""
        self.selector.tilesByElement(tile.element)[0].pop()
        tile.board = self
        return tile

    def remove(self, data):
        """return tile or meld to the selector board"""
        if not (self.focusTile and self.focusTile.hasFocus()):
            hadFocus = False
        elif isinstance(data,  Tile):
            hadFocus = self.focusTile == data
        else:
            hadFocus = self.focusTile == data[0]
        if isinstance(data, Tile) and data.isBonus():
            self.__removeTile(data) # flower, season
        else:
            if isinstance(data, Tile):
                data = self.meldWithTile(data)
            assert data
            for tile in data.tiles:
                self.__removeTile(tile)
        self.placeTiles()
        if hadFocus:
            self.focusTile = None # force calculation of new focusTile
            if self.focusTile:
                self.focusTile.setFocus()

    def clear(self):
        """return all tiles to the selector board"""
        if self.allMelds():
            for melds in self.upperMelds, self.lowerMelds:
                for meld in melds:
                    self.remove(meld)
            for tiles in self.flowers,  self.seasons:
                for tile in tiles:
                    self.remove(tile)
            self.scene().field.handSelectorChanged(self)

    def _add(self, data):
        """get tile or meld from the selector board"""
        if isinstance(data, Meld):
            data.tiles = []
            for pair in data.contentPairs:
                elName = Elements.elementName[pair.lower()]
                data.tiles.append(self.__addTile(Tile(elName)))
            for tile in data.tiles[1:]:
                tile.setFlag(QGraphicsItem.ItemIsFocusable, False)
            self.focusTile = data.tiles[0]
        else:
            tile = Tile(data) # flower, season
            self.__addTile(tile) # flower, season
            self.focusTile = tile
        self.placeTiles()

    def dragMoveEvent(self, event):
        """allow dropping of tile from ourself only to other state (open/concealed)"""
        tile = self.scene().clickedTile
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
            oldLowerHalf = isinstance(tile.board, HandBoard) and tile in tile.board.lowerHalfTiles()
            doAccept = oldLowerHalf != newLowerHalf
        event.setAccepted(doAccept)

    def dropEvent(self, event):
        """drop a tile into this handboard"""
        tile = self.scene().clickedTile
        lowerHalf = self.mapFromScene(QPointF(event.scenePos())).y() >= self.rect().height()/2.0
        if self.receive(tile, event.source(), lowerHalf):
            event.accept()
        else:
            event.ignore()
        self._noPen()

    def receive(self, tile, sourceView, lowerHalf):
        """self receives a tile, lowerHalf says into which part"""
        self.__sourceView = sourceView
        self.lowerHalf = lowerHalf
        added = self.integrate(tile)
        senderHand = tile.board if isinstance(tile.board, HandBoard) else None
        if added:
            if senderHand == self:
                self.placeTiles()
                self.showFocusRect(added.tiles[0])
            else:
                if senderHand:
                    senderHand.remove(added)
                self._add(added)
            self.scene().field.handSelectorChanged(self)
        return added

    @staticmethod
    def chiNext(element, offset):
        """the element name of the following value"""
        color, baseValue = element.split('_')
        baseValue = int(baseValue)
        return '%s_%d' % (color, baseValue+offset-1)

    @staticmethod
    def __lineLength(melds):
        """the length of the melds in meld sizes when shown in the board"""
        return sum(len(meld) for meld in melds) + len(melds)//2

    def lowerHalfTiles(self):
        """returns a list with all single tiles of the lower half melds"""
        result = []
        for meld in self.lowerMelds:
            result.extend(meld)
        return result

    def integrate(self, tile):
        """place the dropped tile in its new board, possibly using
        more tiles from the source to build a meld"""
        if tile.isBonus():
            if tile.isFlower():
                self.flowers.append(tile)
            else:
                self.seasons.append(tile)
            return tile
        else:
            meld = self.__meldFromTile(tile) # from other hand
            if not meld:
                return None
            meld.state = EXPOSED if not self.lowerHalf else CONCEALED
            (self.lowerMelds if self.lowerHalf else self.upperMelds).append(meld)
            return meld

    def placeTiles(self):
        """place all tiles in HandBoard"""
        self.__removeForeignTiles()
        flowerY = 0
        seasonY = 1.0 + self.rowDistance
        upperLen = self.__lineLength(self.upperMelds) + self.meldDistance
        lowerLen = self.__lineLength(self.lowerMelds) + self.meldDistance
        if upperLen + len(self.flowers) > self.width and lowerLen + len(self.seasons) < self.width \
            and len(self.seasons) < len(self.flowers):
            flowerY, seasonY = seasonY, flowerY

        self.upperMelds = sorted(self.upperMelds, key=meldContent)
        self.lowerMelds = sorted(self.lowerMelds, key=meldContent)

        for yPos, melds in ((0, self.upperMelds), (1.0 + self.rowDistance, self.lowerMelds)):
            lineBoni = self.flowers if yPos == flowerY else self.seasons
            bonusStart = self.width - len(lineBoni) - self.meldDistance
            meldX = 0
            meldY = yPos
            for meld in melds:
                if meldX+ len(meld) >= bonusStart:
                    meldY = 1.0 + self.rowDistance - meldY
                    meldX = 9
                for idx, tile in enumerate(meld):
                    tile.setPos(meldX, meldY)
                    tile.dark = meld.contentPairs[idx][0].isupper()
                    meldX += 1
                meldX += self.meldDistance
            self.__showBoni(lineBoni, meldX, yPos)
        self.setDrawingOrder()

    def __showBoni(self, bonusTiles, xPos, yPos):
        """show bonus tiles in HandBoard"""
        if xPos > self.width - 4.0:
            xPos = self.width - len(bonusTiles)
        else:
            xPos = self.width - 4.0
        for bonus in sorted(bonusTiles):
            bonus.board = self
            bonus.setPos(xPos, yPos)
            xPos += 1

    def __removeForeignTiles(self):
        """remove tiles/melds from our lists that no longer belong to our board"""
        normalMelds = set(meld for meld in self.upperMelds + self.lowerMelds \
                          if len(meld.tiles) and meld[0].board == self)
        self.upperMelds = list(meld for meld in normalMelds if meld.state != CONCEALED) # includes CLAIMEDKONG
        self.lowerMelds = list(meld for meld in normalMelds if meld.state == CONCEALED)
        tiles = self.allTiles()
        unknownTiles = list([tile for tile in tiles if not tile.isBonus() \
                        and not self.meldWithTile(tile)])
        assert not len(unknownTiles)
        self.flowers = list(tile for tile in tiles if tile.isFlower())
        self.seasons = list(tile for tile in tiles if tile.isSeason())
        self.helperGroup.setVisible(not tiles)

    def __meldVariants(self, tile):
        """returns a list of possible variants based on the dropped tile.
        The Variants are scoring strings. Do not use the real tiles because we
        change their properties"""
        lowerName = tile.content.lower()
        upperName = lowerName[0].upper() + lowerName[1]
        if self.lowerHalf:
            scName = upperName
        else:
            scName = lowerName
        variants = [scName]
        baseTiles = self.selector.tilesByElement(tile.element)[0].count
        if baseTiles >= 2:
            variants.append(scName * 2)
        if baseTiles >= 3:
            variants.append(scName * 3)
        if baseTiles == 4:
            if self.lowerHalf:
                variants.append(lowerName + upperName * 2 + lowerName)
            else:
                variants.append(lowerName * 4)
                variants.append(lowerName * 3 + upperName)
        if tile.element[:2] not in ('WI', 'DR') and tile.element[-1] < '8':
            chow2 = self.chiNext(tile.element, 2)
            chow3 = self.chiNext(tile.element, 3)
            chow2 = self.selector.tilesByElement(chow2)[0]
            chow3 = self.selector.tilesByElement(chow3)[0]
            if chow2.count and chow3.count:
                baseChar = scName[0]
                baseValue = ord(scName[1])
                varStr = '%s%s%s%s%s' % (scName, baseChar, chr(baseValue+1), baseChar, chr(baseValue+2))
                variants.append(varStr)
        return [Meld(x) for x in variants]

    def __meldFromTile(self, tile):
        """returns a meld, lets user choose between possible meld types"""
        if isinstance(tile.board, HandBoard):
            meld = tile.board.meldWithTile(tile)
            assert meld
            if not self.lowerHalf and len(meld) == 4 and meld.state == CONCEALED:
                pair0 = meld.contentPairs[0].lower()
                meldVariants = [Meld(pair0*4), Meld(pair0*3 + pair0.upper())]
                for variant in meldVariants:
                    variant.tiles = meld.tiles
            else:
                return meld
        else:
            meldVariants = self.__meldVariants(tile)
        idx = 0
        if len(meldVariants) > 1:
            menu = QMenu(m18n('Choose from'))
            for idx, variant in enumerate(meldVariants):
                action = menu.addAction(shortcuttedMeldName(variant.meldType))
                action.setData(QVariant(idx))
            if self.scene().clickedTile:
                menuPoint = QCursor.pos()
            else:
                faceRect = QRectF(tile.facePos(), tile.tileset.faceSize)
                mousePoint = faceRect.bottomRight()
                view = self.__sourceView
                menuPoint = view.mapToGlobal(view.mapFromScene(tile.mapToScene(mousePoint)))
            action = menu.exec_(menuPoint)
            if not action:
                return None
            idx = action.data().toInt()[0]
        if tile.board == self:
            meld.tiles = []
        return meldVariants[idx]

class FittingView(QGraphicsView):
    """a graphics view that always makes sure the whole scene is visible"""
    def __init__(self, parent=None):
        """generate a fitting view with our favourite properties"""
        QGraphicsView.__init__(self, parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        vpol = QSizePolicy()
        vpol.setHorizontalPolicy(QSizePolicy.Expanding)
        vpol.setVerticalPolicy(QSizePolicy.Expanding)
        self.setSizePolicy(vpol)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.__background = None
        self.setStyleSheet('background: transparent')
        self.setFrameShadow(QFrame.Plain)
        self.tilePressed = None
        self.tilePressedAt = None
        self.setFocus()

    def resizeEvent(self, event):
        """scale the scene for new view size"""
        assert event # quieten pylint
        # also adjust the background to the container. Do this here because this way
        # it is easier to minimize calls to setBackground()
        parent = self.parentWidget()
        if parent:
            grandpa = parent.parentWidget()
            if grandpa and grandpa.objectName() == 'MainWindow':
                if grandpa.ignoreResizing:
                    grandpa.ignoreResizing -= 1
                    return
                grandpa.applySettings()
                # resize background:
                grandpa.backgroundName = grandpa.backgroundName
        if self.scene():
            self.fitInView(self.scene().itemsBoundingRect(), Qt.KeepAspectRatio)
        self.setFocus()

    def __matchingTile(self, position, item):
        """is position in the clickableRect of this tile?"""
        if not isinstance(item, Tile):
            return False
        itemPos = item.mapFromScene(self.mapToScene(position))
        return item.clickableRect().contains(itemPos)

    def tileAt(self, position):
        """find out which tile is clickable at this position"""
        allTiles = [x for x in self.items(position) if isinstance(x, Tile)]
        items = [x for x in allTiles if self.__matchingTile(position, x)]
        if not items:
            return None
        maxLevel = max(x.level for x in items)
        item = [x for x in items if x.level == maxLevel][0]
        for other in allTiles:
            if (other.xoffset, other.yoffset) == (item.xoffset, item.yoffset):
                if other.level > item.level:
                    item = other
        return item

    def mousePressEvent(self, event):
        """emit tileClicked(event,tile)"""
        self.tilePressedAt = None
        tile = self.tileAt(event.pos())
        if tile:
            if tile.opacity:
                if not tile.isFocusable() and isinstance(tile.board, HandBoard):
                    tile = tile.board.meldWithTile(tile)[0]
                tile.setFocus()
            self.tilePressed = tile
            # copy event.pos() because it returns something mutable
            self.tilePressedAt = QPoint(event.pos())
            self.scene().emit(SIGNAL('tileClicked'), event, tile)

    def mouseReleaseEvent(self, event):
        """release self.tilePressed"""
        assert event # quieten pylint
        self.tilePressed = None

    def mouseMoveEvent(self, event):
        """selects the correct tile"""
        assert event # quieten pylint
        if self.tilePressed and self.tilePressed.opacity:
            if self.tilePressed.board and self.tilePressed.board.tileDragEnabled:
                drag = self.drag(self.tilePressed)
                drag.exec_(Qt.MoveAction)
        self.tilePressed = None

    def drag(self, item):
        """returns a drag object"""
        drag = QDrag(self)
        mimeData = QMimeData()
        mimeData.setText(item.element)
        drag.setMimeData(mimeData)
        tSize = item.boundingRect()
        tRect = QRectF(0.0, 0.0, tSize.width(), tSize.height())
        vRect = self.viewportTransform().mapRect(tRect)
        pmapSize = vRect.size().toSize()
        xScale = pmapSize.width() / item.boundingRect().width()
        yScale = pmapSize.height() / item.boundingRect().height()
        if item.pixmap is None or item.pixmap.size() != pmapSize:
            item.pixmap = QPixmap(pmapSize)
            item.pixmap.fill(Qt.transparent)
            painter = QPainter(item.pixmap)
            painter.scale(xScale, yScale)
            QGraphicsSvgItem.paint(item, painter, QStyleOptionGraphicsItem())
            for child in item.childItems():
                if isinstance(child, QGraphicsSvgItem):
                    painter.save()
                    painter.translate(child.mapToParent(0.0, 0.0))
                    QGraphicsSvgItem.paint(child, painter, QStyleOptionGraphicsItem())
                    painter.restore()
        drag.setPixmap(item.pixmap)
        itemPos = item.mapFromScene(self.mapToScene(self.tilePressedAt)).toPoint()
        itemPos.setX(itemPos.x()*xScale)
        itemPos.setY(itemPos.y()*yScale)
        drag.setHotSpot(itemPos)
        return drag

class Wall(Board):
    """a Board representing a wall of tiles"""
    def __init__(self, tileset, rotation, length):
        Board.__init__(self, length, 1, tileset, rotation=rotation)
        self.length = length

    def center(self):
        """returns the center point of the wall in relation to the faces of the upper level"""
        faceSize = self.tileset.faceSize
        result = self.tileAt(0, 0, 1).facePos() + self.shiftZ(1) + \
            QPointF(self.length // 2 * faceSize.width(), faceSize.height()/2)
        result.setX(result.x() + faceSize.height()/2) # corner tile
        return result

class Walls(Board):
    """represents the four walls. self.walls[] indexes them counter clockwise, 0..3"""
    def __init__(self, tileset, tiles):
        """init and position the walls"""
        assert len(tiles) % 8 == 0
        self.length = len(tiles) // 8
        self.walls = [Wall(tileset, rotation, self.length) for rotation in (0, 270, 180, 90)]
        Board.__init__(self, self.length+1, self.length+1, tileset)
        for wall in self.walls:
            wall.setParentItem(self)
            wall.lightSource = self.lightSource
        self.walls[0].setPos(yWidth=self.length)
        self.walls[3].setPos(xHeight=1)
        self.walls[2].setPos(xHeight=1, xWidth=self.length, yHeight=1)
        self.walls[1].setPos(xWidth=self.length, yWidth=self.length, yHeight=1 )
        self.build(tiles) # without dividing
        self.setDrawingOrder()

    def __getitem__(self, index):
        """make Walls index-able"""
        return self.walls[index]

    def build(self, tiles,  wallIndex=None, diceSum=None):
        """builds the walls from tiles with a divide in wall wallIndex"""
        random.shuffle(tiles)
        tileIter = iter(tiles)
        for wall in (self.walls[0], self.walls[3], self.walls[2],  self.walls[1]):
            upper = True     # upper tile is played first
            for position in range(self.length*2-1, -1, -1):
                tile = tileIter.next()
                tile.board = wall
                tile.setPos(position//2, level=1 if upper else 0)
                tile.faceDown = True
                upper = not upper
        if wallIndex is not None and diceSum is not None:
            self._divide(tiles, wallIndex, diceSum)

    @apply
    def lightSource():
        def fget(self):
            return Board.lightSource.fget(self)
        def fset(self, lightSource):
            if lightSource != self._lightSource:
                Board.lightSource.fset(self, lightSource)
                self.setDrawingOrder()
        return property(**locals())

    def setDrawingOrder(self):
        """set drawing order of the walls"""
        levels = {'NW': (2, 3, 1, 0), 'NE':(3, 1, 0, 2), 'SE':(1, 0, 2, 3), 'SW':(0, 2, 3, 1)}
        for idx, wall in enumerate(self.walls):
            wall.level = levels[wall.lightSource][idx]*1000
        Board.setDrawingOrder(self)

    def _moveDividedTile(self, wallIndex,  tile, offset):
        """moves a tile from the divide hole to its new place"""
        newOffset = tile.xoffset + offset
        if newOffset >= self.length:
            tile.board = self.walls[(wallIndex+1) % 4]
        tile.setPos(newOffset % self.length, level=2)

    def _divide(self, tiles, wallIndex, diceSum):
        """divides a wall (numbered 0..3 counter clockwise), building a living and and a dead end"""
        # neutralise the different directions
        myIndex = wallIndex if wallIndex in (0, 2) else 4-wallIndex
        livingEnd = 2 * (myIndex * self.length + diceSum)
        # shift tiles: tile[0] becomes living end
        tiles[:] = tiles[livingEnd:] + tiles[0:livingEnd]
        # move last two tiles onto the dead end:
        self._moveDividedTile(wallIndex, tiles[-1], 3)
        self._moveDividedTile(wallIndex, tiles[-2], 5)
    def _setRect(self):
        """translate from our rect coordinates to scene coord"""
        wall = self.walls[0]
        sideLength = wall.rect().width() + wall.rect().height()
        # not quite correct - should be adjusted by shadows, but
        # sufficient for our needs
        rect = self.rect()
        rect.setWidth(sideLength)
        rect.setHeight(sideLength)
        self.prepareGeometryChange()
        QGraphicsRectItem.setRect(self, rect)

class Shisen(Board):
    """builds a Shisen board, just for testing"""
    def __init__(self, tileset,  tiles):
        Board.__init__(self, 18, 8,  tileset,  tiles)
        random.shuffle(tiles)
        for row in range(0, 8):
            for col in range(0, 18):
                tile = tiles[row*18+col]
                tile.board = self
                tile.setPos(xoffset=col, yoffset=row)


class Solitaire(Board):
    """builds a Solitaire board, just for testing"""
    def __init__(self, tileset,  tiles):
        Board.__init__(self, 15, 8, tileset,  tiles)
        random.shuffle(tiles)
        tile = iter(tiles)
        for row, columns in enumerate((12, 8, 10, 12, 12, 10, 8, 12)):
            offset = (14-columns)/2 - 1
            for col  in range(0, columns):
                tile.next().setPos(xoffset = col+offset,  yoffset=row)
        tile.next().setPos(xoffset=-1, yoffset=3.5)
        tile.next().setPos(xoffset=12, yoffset=3.5)
        tile.next().setPos(xoffset=13, yoffset=3.5)
        for row in range(1, 7):
            for col in range(3, 9):
                tile.next().setPos(xoffset=col, yoffset=row,  level=1)
        for row in range(2, 6):
            for col in range(4, 8):
                tile.next().setPos(xoffset=col, yoffset=row,  level=2)
        for row in range(3, 5):
            for col in range(5, 7):
                tile.next().setPos(xoffset=col, yoffset=row,  level=3)
        tile.next().setPos(xoffset=5.5, yoffset=3.5,  level=4)

class MJScene(QGraphicsScene):
    """our scene with a few private attributes"""
    def __init__(self):
        QGraphicsScene.__init__(self)
        self.clickedTile = None
        self.clickedTileEvent = None
