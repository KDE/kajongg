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

from PyKDE4.kdecore import i18n
from PyQt4.QtCore import Qt, QPointF,  QString,  QRectF, QMimeData,  SIGNAL, QVariant
from PyQt4.QtGui import  QGraphicsRectItem, QGraphicsItem,  QSizePolicy, QFrame
from PyQt4.QtGui import  QMenu, QCursor, QGraphicsView,  QGraphicsEllipseItem,  QGraphicsScene
from PyQt4.QtGui import QColor, QPainter, QDrag, QPixmap, QStyleOptionGraphicsItem
from PyQt4.QtSvg import QGraphicsSvgItem
from tileset import Tileset, TileException,  LIGHTSOURCES, elements,  Elements
from scoring import Meld, SINGLE, PAIR, PONG, KAN, CHI, meldName

import random

from util import logException

ROUNDWINDCOLOR = QColor(235, 235, 173)

class Tile(QGraphicsSvgItem):
    """a single tile on the board.
    the unit of xoffset is the width of the tile,
    the unit of yoffset is the height of the tile.
    """
    def __init__(self, element,  xoffset = 0, yoffset = 0, level=0,  faceDown=False):
        QGraphicsSvgItem.__init__(self)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsFocusable)
        self.__board = None
        self.element = element
        self.__selected = False
        self.__faceDown = faceDown
        self.level = level
        self.xoffset = xoffset
        self.yoffset = yoffset
        self.face = None
        self.pixmap = None
        self.concealed = False

    def getBoard(self):
        """the board this tile belongs to"""
        return self.__board

    def setBoard(self, board):
        """assign the tile to a board and define it according to the board parameters.
        This always recomputes the tile position in the board even if we assign to the
        same board - class Board depends on this"""
        self.__board = board
        self.recompute()

    def __shiftedPos(self, width, height):
        """the face position adjusted by shadow and / or border"""
        lightSource = self.board.rotatedLightSource()
        xoffset = width-1 if 'E' in lightSource else 0
        yoffset = height-1 if 'S' in lightSource else 0
        return QPointF(xoffset, yoffset)

    def facePos(self):
        """returns the face position relative to the tile"""
        shadowWidth = self.tileset.shadowWidth()
        shadowHeight = self.tileset.shadowHeight()
        return self.__shiftedPos(shadowWidth, shadowHeight)

    def clickablePos(self):
        """the topleft position for the tile rect that should accept mouse events"""
        shadowWidth = self.tileset.shadowWidth()
        shadowHeight = self.tileset.shadowHeight()
        return self.__shiftedPos(shadowWidth, shadowHeight)

    def recompute(self):
        """recomputes position and visuals of the tile"""
        self.prepareGeometryChange()
        self.setParentItem(self.__board)
        if self.__board is None:
            return
        if self.tileset:
            self.setSharedRenderer(self.tileset.renderer())
        self.setTileId()
        self.placeInBoard()

        if self.element and not self.faceDown:
            if not self.face:
                self.face = QGraphicsSvgItem()
                self.face.setParentItem(self)
                self.face.setElementId(self.element)
            # if we have a left or a top shadow, move face
            # by shadow width
            facePos = self.facePos()
            self.face.setPos(facePos.x(), facePos.y())
            self.face.setSharedRenderer(self.tileset.renderer())
        elif self.face:
            self.face.setParentItem(None)
            self.face = None

    board = property(getBoard, setBoard)

    def getFaceDown(self):
        """does the tile with face down?"""
        return self.__faceDown

    def setFaceDown(self, faceDown):
        """turn the tile face up/down"""
        if self.__faceDown != faceDown:
            self.__faceDown = faceDown
            self.recompute()

    faceDown = property(getFaceDown, setFaceDown)

    def setPos(self, xoffset=0, yoffset=0, level=0):
        """change Position of tile in board"""
        if (self.level, self.xoffset, self.yoffset) != (level, xoffset, yoffset):
            self.level = level
            self.xoffset = xoffset
            self.yoffset = yoffset
            self.recompute()
            if self.board:
                self.board.setDrawingOrder()

    def setTileId(self):
        """sets the SVG element id of the tile"""
        lightSourceIndex = LIGHTSOURCES.index(self.board.rotatedLightSource())
        tileName = QString("TILE_%1").arg(lightSourceIndex%4+1)
        if self.selected:
            tileName += '_SEL'
        self.setElementId(tileName)

    def __getTileset(self):
        """the active tileset"""
        parent = self.parentItem()
        return parent.tileset if parent else None

    tileset = property(__getTileset)

    def sizeStr(self):
        """printable string with tile size"""
        size = self.sceneBoundingRect()
        if size:
            return '%d.%d %dx%d' % (size.left(), size.top(), size.width(), size.height())
        else:
            return 'No Size'

    def scoringStr(self):
        """returns a string representation for use in the scoring engine"""
        return Elements.scoringTileName[self.element]

    def __str__(self):
        """printable string with tile data"""
        return '%s %d: at %s %d ' % (self.element, id(self),
            self.sizeStr(), self.level)

    def placeInBoard(self):
        """places the tile in the Board"""
        if not self.board:
            return
        width = self.tileset.faceSize.width()
        height = self.tileset.faceSize.height()
        shiftZ = self.board.shiftZ(self.level)
        boardX = self.xoffset*width+ shiftZ.x()
        boardY = self.yoffset*height+ shiftZ.y()
        QGraphicsRectItem.setPos(self, boardX, boardY)
        self.board.setGeometry()

    def __getSelected(self):
        """getter for selected attribute"""
        return self.__selected

    def __setSelected(self, selected):
        """selected tiles are drawn differently"""
        if self.__selected != selected:
            self.__selected = selected
            self.setTileId()

    selected = property(__getSelected, __setSelected)

    def clickableRect(self):
        """returns a rect for the range where a click is allowed (excludes border and shadow).
        Value in item coordinates"""
        return QRectF(self.clickablePos(), self.tileset.faceSize)

    def isFlower(self):
        """is this a flower tile?"""
        return self.element[:3] == 'FLO'

    def isSeason(self):
        """is this a season tile?"""
        return self.element[:3] == 'SEA'

    def isBonus(self):
        """is this a bonus tile? (flower,season)"""
        return self.isFlower() or self.isSeason()

class PlayerWind(QGraphicsEllipseItem):
    """a round wind tile"""
    def __init__(self, name, roundsFinished=0,  parent = None):
        """generate new wind tile"""
        QGraphicsEllipseItem.__init__(self)
        if parent:
            self.setParentItem(parent)
        self.name = name
        self.face = QGraphicsSvgItem()
        self.face.setParentItem(self)
        self.prevailing = None
        self.setWind(name, roundsFinished)
        if parent and parent.tileset:
            self.setTileset(parent.tileset)

    def setTileset(self, tileset):
        """sets tileset and defines the round wind tile according to tileset"""
        self.face.tileset = tileset
        size = tileset.faceSize
        self.setFlag(QGraphicsItem.ItemClipsChildrenToShape)
        if tileset.desktopFileName == 'traditional':
            diameter = size.height()*1.1
            self.setRect(0, 0, diameter, diameter)
            self.scale(1.2, 1.2)
            self.face.setPos(10, 10)
        elif tileset.desktopFileName == 'default':
            diameter = size.height()*1.1
            self.setRect(0, 0, diameter, diameter)
            self.scale(1.2, 1.2)
            self.face.setPos(15, 10)
        elif tileset.desktopFileName == 'classic':
            diameter = size.height()*1.1
            self.setRect(0, 0, diameter, diameter)
            self.scale(1.2, 1.2)
            self.face.setPos(19, 1)
        elif tileset.desktopFileName == 'jade':
            diameter = size.height()*1.1
            self.setRect(0, 0, diameter, diameter)
            self.scale(1.2, 1.2)
            self.face.setPos(19, 1)
        self.face.setSharedRenderer(tileset.renderer())
        self.scale(0.75, 0.75)

    def setWind(self, name,  roundsFinished):
        """change the wind"""
        self.name = name
        self.prevailing = name == 'ESWN'[roundsFinished]
        self.setBrush(ROUNDWINDCOLOR if self.prevailing else QColor('white'))
        windtilenr = {'N':1, 'S':2, 'E':3, 'W':4}
        self.face.setElementId('WIND_%d' % windtilenr[name])

class Board(QGraphicsRectItem):
    """ a board with any number of positioned tiles"""
    def __init__(self, tileset, tiles=None,  rotation = 0):
        QGraphicsRectItem.__init__(self)
        self.tileDragEnabled = False
        self.rotation = rotation
        self.rotate(rotation)
        self.__lightSource = 'NW'
        self.xWidth = 0
        self.xHeight = 0
        self.yWidth = 0
        self.yHeight = 0
        self.__fixedWidth = None
        self.__fixedHeight = None
        self.__tileset = None
        self.tileset = tileset
        self.level = 0
        if tiles:
            for tile in tiles:
                tile.board = self

    def tileAt(self, xoffset, yoffset, level=0):
        """if there is a tile at this place, return it"""
        for tile in self.childItems():
            if isinstance(tile, Tile):
                if (tile.xoffset, tile.yoffset, tile.level) == (xoffset, yoffset, level):
                    return tile
        return None

    def tilesByName(self, element):
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
        matrix = self.sceneTransform()
        matrix = (int(matrix.m11()), int(matrix.m12()), int(matrix.m21()), int(matrix.m22()))
        rotNumber = [(1, 0, 0, 1), (0, 1, -1, 0), (-1, 0, 0, -1), (0, -1, 1, 0)].index(matrix)
        lightSourceIndex = LIGHTSOURCES.index(self.lightSource)
        lightSourceIndex = (lightSourceIndex+rotNumber)%4
        return LIGHTSOURCES[lightSourceIndex]

    def setPos(self, xWidth=0, xHeight=0, yWidth=0, yHeight=0):
        """sets the position in the parent item expressing the position in tile face units.
        The X position is xWidth*facewidth + xHeight*faceheight, analog for Y"""
        self.xWidth = xWidth
        self.xHeight = xHeight
        self.yWidth = yWidth
        self.yHeight = yHeight
        self.setGeometry()

    def setFixedSize(self, width, height):
        """gives the board a fixed size in tile coordinates"""
        if (self.__fixedWidth, self.__fixedHeight) != (width, height):
            self.__fixedWidth = width
            self.__fixedHeight = height
            sizeX = self.tileset.faceSize.width() * width + self.tileset.shadowWidth()
            sizeY = self.tileset.faceSize.height() * height + self.tileset.shadowHeight()
            oldRect = self.rect()
            oldRect.setWidth(sizeX)
            oldRect.setHeight(sizeY)
            self.setRect(oldRect)

    def setGeometry(self):
        """move the board to the correct position and set its rect surrounding all its
        items. This is needed for enabling drops into the board.
        This is also called when the tileset or the light source for this board changes"""
        width = self.tileset.faceSize.width()
        height = self.tileset.faceSize.height()
        offsets = self.tileset.shadowOffsets(self.lightSource, self.rotation)
        newX = self.xWidth*width+self.xHeight*height + offsets[0]
        newY = self.yWidth*width+self.yHeight*height + offsets[1]
        QGraphicsRectItem.setPos(self, newX, newY)
        if not self.__fixedWidth:
            newRect = QRectF(self.rect())
            newSize = self.childrenBoundingRect().size()
            newRect.setHeight(newSize.height())
            newRect.setWidth(newSize.width())
            if newRect != self.rect():
                self.setRect(newRect)

    def __getLightSource(self):
        """the active lightSource"""
        return self.__lightSource

    def __setLightSource(self, lightSource):
        """set active lightSource"""
        if self.__lightSource != lightSource:
            if   lightSource not in LIGHTSOURCES:
                logException(TileException('lightSource %s illegal' % lightSource))
            self.__reload(self.tileset, lightSource)
            self.setDrawingOrder()

    lightSource = property(__getLightSource,  __setLightSource)

    def __getTileset(self):
        """the active tileset"""
        if self.__tileset:
            return self.__tileset
        elif self.parentItem():
            return self.parentItem().tileset
        elif isinstance(self, Board):
            return Tileset('default')
        else:
            return None

    def __setTileset(self, tileset):
        """set the active tileset and resize accordingly"""
        self.__reload(tileset, self.lightSource)

    tileset = property(__getTileset, __setTileset)

    def __reload(self, tileset=None, lightSource=None):
        """call this if tileset or lightsource change: recomputes the entire board"""
        if tileset is None:
            tileset = self.tileset
        if lightSource is None:
            lightSource = self.__lightSource
        if self.__tileset != tileset or self.__lightSource != lightSource:
            self.__tileset = tileset
            self.__lightSource = lightSource
            for child in self.childItems():
                if isinstance(child, Board) or isinstance(child, PlayerWind):
                    child.tileset = tileset
                    child.lightSource = lightSource
                elif isinstance(child, Tile):
                    child.board = self # tile will reposition itself
            self.setGeometry()

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
                item.setZValue(item.level*100000+self.lightDistance(item))

    def tileSize(self):
        """the current tile size"""
        return self.__tileset.tileSize

    def faceSize(self):
        """the current face size"""
        return self.__tileset.faceSize

class SelectorBoard(Board):
    """a board containing all possible tiles for selection"""
    __rows = {'CHARACTER':0,  'BAMBOO':1,  'ROD':2, 'WIND':3, 'DRAGON':3, 'SEASON':4, 'FLOWER':4}

    def __init__(self, tileset):
        Board.__init__(self, tileset)
        self.setAcceptDrops(True)
        for tile in elements.all():
            self.placeAvailable(Tile(tile))
        self.setDrawingOrder()

    def dropEvent(self, event):
        """drop a tile into the selector"""
        tile = self.scene().clickedTile
        meld = None

        oldHand = tile.board if isinstance(tile.board, HandBoard) else None
        if oldHand:
            meld = oldHand.meldWithTile(tile)
        if meld is None:
            meld = Meld([tile])
        for tile in meld:
            self.placeAvailable(tile)
        if oldHand:
            oldHand.placeTiles()
        self.setDrawingOrder()
        event.accept()

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
        tile.setPos(column, row)
        tile.board = self

    def elementTiles(self, element):
        """returns all tiles with this element"""
        return list(item for item in self.childItems() if item.element == element)

class HandBoard(Board):
    """a board showing the tiles a player holds"""
    def __init__(self, player):
        Board.__init__(self, player.wall.tileset)
        self.setFixedSize(23.0, 2.2)
        self.tileDragEnabled = True
        self.player = player
        self.selector = None
        self.setParentItem(player.wall)
        self.setAcceptDrops(True)
        self.openMelds = []
        self.concealedMelds = []
        self.flowers = []
        self.seasons = []
        self.setFlag(QGraphicsItem.ItemClipsChildrenToShape)

    def meldWithTile(self, tile):
        """returns the meld holding tile"""
        for melds in self.openMelds, self.concealedMelds:
            for meld in melds:
                if tile in meld:
                    return meld
        return None

    def dropEvent(self, event):
        """drop a tile into this handboard"""
        tile = self.scene().clickedTile
        concealed = self.mapFromScene(QPointF(event.scenePos())).y() >= self.rect().height()/2.0
        oldHand = tile.board if isinstance(tile.board, HandBoard) else None
        if self.addTile(tile, concealed=concealed):
            if oldHand:
                oldHand.placeTiles()
            self.placeTiles()
            self.setDrawingOrder()
            event.accept()
        else:
            event.ignore()

    @staticmethod
    def chiNext(element, offset):
        """the element name of the following value"""
        color, baseValue = element.split('_')
        baseValue = int(baseValue)
        return '%s_%d' % (color, baseValue+offset-1)

    @staticmethod
    def lineLength(melds):
        """the length of the melds in meld sizes when shown in the board"""
        return sum(len(meld) for meld in melds) + len(melds)/2

    def addTile(self, tile, concealed):
        """place the dropped tile in its new board, possibly dragging
        more tiles from the source to build a meld"""
        if tile.isBonus():
            tile.board = self
            if tile.isFlower():
                self.flowers.append(tile)
            else:
                self.seasons.append(tile)
        else:
            meld = self.meldFromTile(tile) # from other hand
            if not meld:
                return False
            for xTile in meld:
                xTile.board = self
            (self.concealedMelds if concealed else self.openMelds).append(meld)
        return True

    def placeTiles(self):
        """place all tiles in HandBoard"""
        self.removeForeignTiles()
        flowerY = 0
        seasonY = 1.2
        openLen = self.lineLength(self.openMelds) + 0.5
        concealedLen = self.lineLength(self.concealedMelds) + 0.5
        if openLen + len(self.flowers) > 23 and concealedLen + len(self.seasons) < 23 \
            and len(self.seasons) < len(self.flowers):
            flowerY, seasonY = seasonY, flowerY

        for yPos, melds in ((0, self.openMelds), (1.2, self.concealedMelds)):
            lineBoni = self.flowers if yPos == flowerY else self.seasons
            bonusStart = 23 - len(lineBoni) - 0.5
            meldX = 0
            meldY = yPos
            for meld in melds:
                if meldX+ len(meld) >= bonusStart:
                    meldY = 1.2 - meldY
                    meldX = 23 - 4.5 - len(meld)
                for tile in meld:
                    tile.setPos(meldX, meldY)
                    meldX += 1
                meldX += 0.5
            self.__showBoni(lineBoni, yPos)

    def __showBoni(self, bonusTiles, yPos):
        """show bonus tiles in HandBoard"""
        for idx, bonus in enumerate(sorted(bonusTiles)):
            bonus.board = self
            xPos = 23 - len(bonusTiles) + idx
            bonus.setPos(xPos, yPos)

    def removeForeignTiles(self):
        """remove tiles/melds from our lists that no longer belong to our board"""
        for melds in (self.openMelds, self.concealedMelds):
            melds[:] = list(meld for meld in melds if meld[0].board == self)
        tiles = self.childItems()
        assert not len([tile for tile in tiles if not tile.isBonus() \
                        and not self.meldWithTile(tile)])
        self.flowers = list(tile for tile in tiles if tile.isFlower())
        self.seasons = list(tile for tile in tiles if tile.isSeason())


    def meldVariants(self, tile):
        """returns a list of possible variants based on the dropped tile"""
        variants = [(SINGLE, [tile])]
        baseTiles = self.selector.tilesByName(tile.element)
        if len(baseTiles) >= 2:
            variants.append((PAIR, baseTiles[:2]))
        if len(baseTiles) >= 3:
            variants.append((PONG, baseTiles[:3]))
        if len(baseTiles) == 4:
            variants.append((KAN, baseTiles))
        if tile.element[:2] not in ('WI', 'DR'):
            chi2 = self.chiNext(tile.element, 2)
            chi3 = self.chiNext(tile.element, 3)
            chi2Tiles = self.selector.tilesByName(chi2)
            chi3Tiles = self.selector.tilesByName(chi3)
            if len(chi2Tiles) and len(chi3Tiles):
                variants.append((CHI, [tile, chi2Tiles[0], chi3Tiles[0]]))
        return variants

    def meldFromTile(self, tile):
        """returns a meld, lets user choose between possible meld types"""
        if isinstance(tile.board, HandBoard):
            meld = tile.board.meldWithTile(tile)
            if meld:
                return meld
        meldVariants = self.meldVariants(tile)
        idx = 0
        if len(meldVariants) > 1:
            menu = QMenu(i18n('Choose from'))
            for idx, variant in enumerate(meldVariants):
                action = menu.addAction(meldName(variant[0]))
                action.setData(QVariant(idx))
            action = menu.exec_(QCursor.pos())
            if not action:
                return None
            idx = action.data().toInt()[0]
        return Meld(meldVariants[idx][1])

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
        self.mousePressed = False

    def resizeEvent(self, event):
        """scale the scene for new view size"""
        assert event # quieten pylint
        if self.scene():
            self.fitInView(self.scene().itemsBoundingRect(), Qt.KeepAspectRatio)
            self.ensureVisible(self.scene().itemsBoundingRect())

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
        self.mousePressed = True
        tile = self.tileAt(event.pos())
        if tile:
            self.scene().emit(SIGNAL('tileClicked'), event, tile)

    def mouseReleaseEvent(self, event):
        """change state of self.mousePressed"""
        assert event # quieten pylint
        self.mousePressed = False

    def mouseMoveEvent(self, event):
        """selects the correct tile and emits tileMoved"""
        tile = self.tileAt(event.pos())
        if tile:
            self.scene().emit(SIGNAL('tileMoved'), event, tile)
            if self.mousePressed and tile.board and tile.board.tileDragEnabled:
                dragger = self.drag(event, tile)
                dragger.exec_(Qt.MoveAction)
        self.mousePressed = False # mouseReleaseEvent will not be called, why?

    def drag(self, event, item):
        """returns a drag object"""
        drag = QDrag(self)
        mimeData = QMimeData()
        mimeData.setText(item.element)
        drag.setMimeData(mimeData)
        tSize = item.boundingRect()
        tRect = QRectF(0.0, 0.0, tSize.width(), tSize.height())
        # TODO: pixmap size stimmt nicht mehr
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
                QGraphicsSvgItem.paint(child, painter, QStyleOptionGraphicsItem())
        drag.setPixmap(item.pixmap)
        itemPos = item.mapFromScene(self.mapToScene(event.pos())).toPoint()
        itemPos.setX(itemPos.x()*xScale)
        itemPos.setY(itemPos.y()*yScale)
        drag.setHotSpot(itemPos)
        return drag

class Wall(Board):
    """a Board representing a wall of tiles"""
    def __init__(self, tileset, rotation, length):
        Board.__init__(self, tileset, rotation=rotation)
        self.length = length

    def center(self):
        """returns the center point of the wall in relation to the faces of the upper level"""
        faceSize = self.tileset.faceSize
        result = self.tileAt(0, 0, 1).facePos() + self.shiftZ(1) + \
            QPointF(self.length / 2 * faceSize.width(), faceSize.height()/2)
        result.setX(result.x() + faceSize.height()/2) # corner tile
        return result

class Walls(Board):
    """represents the four walls. self.walls[] indexes them counter clockwise, 0..3"""
    def __init__(self, tileset, tiles):
        """init and position the walls"""
        Board.__init__(self, tileset)
        assert len(tiles) % 8 == 0
        self.length = len(tiles) / 8
        self.lightSource = 'NW'
        self.walls = [Wall(tileset, rotation, self.length) for rotation in (0, 270, 180, 90)]
        for wall in self.walls:
            wall.setParentItem(self)
            wall.lightSource = self.lightSource
        self.walls[0].setPos(yWidth=self.length)
        self.walls[3].setPos(xHeight=1)
        self.walls[2].setPos(xHeight=1, xWidth=self.length, yHeight=1)
        self.walls[1].setPos(xWidth=self.length, yWidth=self.length, yHeight=1 )
        self.build(tiles) # without dividing

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
                tile.setPos(position/2, level=1 if upper else 0)
                tile.faceDown = True
                upper = not upper
        if wallIndex is not None and diceSum is not None:
            self._divide(tiles, wallIndex, diceSum)
        # define the drawing order for the walls
        levels = {'NW': (2, 3, 1, 0), 'NE':(3, 1, 0, 2), 'SE':(1, 0, 2, 3), 'SW':(0, 2, 3, 1)}
        for idx, wall in enumerate(self.walls):
            wall.level = levels[wall.lightSource][idx]*1000
        self.setDrawingOrder()

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

class Shisen(Board):
    """builds a Shisen board, just for testing"""
    def __init__(self, tileset,  tiles):
        Board.__init__(self,  tileset,  tiles)
        random.shuffle(tiles)
        for row in range(0, 8):
            for col in range(0, 18):
                tile = tiles[row*18+col]
                tile.board = self
                tile.setPos(xoffset=col, yoffset=row)


class Solitaire(Board):
    """builds a Solitaire board, just for testing"""
    def __init__(self, tileset,  tiles):
        Board.__init__(self,  tileset,  tiles)
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
