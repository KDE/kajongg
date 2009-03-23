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

from PyQt4.QtCore import Qt,  QPointF,  QString,  QRectF,  SIGNAL
from PyQt4.QtGui import  QGraphicsRectItem, QGraphicsItem,  QSizePolicy, QFrame
from PyQt4.QtGui import QGraphicsView,  QGraphicsEllipseItem,  QColor, QPainter
from PyQt4.QtSvg import QGraphicsSvgItem
from tileset import TileException,  LIGHTSOURCES
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
        self.__board = None
        self.element = element
        self.__selected = False
        self.__faceDown = faceDown
        self.level = level
        self.xoffset = xoffset
        self.yoffset = yoffset
        self.face = None

    def mousePressEvent(self, event):
        """selects the tile."""
        if self.clickableRect().contains(event.pos()):
            selTile = self
            # this might be a border of a lower tile: select highest tile at this place
            for tile in self.board.childItems():
                if isinstance(tile, Tile):
                    if (tile.xoffset, tile.yoffset) == (self.xoffset, self.yoffset):
                        if tile.level > selTile.level:
                            selTile = tile
            self.scene().emit(SIGNAL('tileClicked'), selTile)
        else:
            # we pressed on the shadow - pass the event to the underlying tiles
            QGraphicsSvgItem.mousePressEvent(self, event)
        return

    def getBoard(self):
        """the board this tile belongs to"""
        return self.__board

    def setBoard(self, board):
        """assign the tile to a board and define it according to the board parameters"""
#        if self.__board and board != self.__board:
   #         logException(TileException('Tile can only belong to one board'))
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
        shadowWidth = self.tileset.shadowWidth() / 2
        shadowHeight = self.tileset.shadowHeight() / 2
        return self.__shiftedPos(shadowWidth, shadowHeight)

    def recompute(self):
        """recomputes position and visuals of the tile"""
        self.prepareGeometryChange()
        self.setParentItem(self.__board)
        if self.__board is None:
            return
        self.placeInBoard()
        self.setSharedRenderer(self.tileset.renderer())

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
        self.setTileId()

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
        """returns a rect for the range where a click is allowed (excludes shadow).
        Value in scene coordinates"""
        tileSize = self.tileset.tileSize
        faceSize = self.tileset.faceSize
        return QRectF(self.clickablePos(), tileSize - (tileSize-faceSize)/2)

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
        if tiles:
            for tile in tiles:
                tile.board = self

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
        rotNumber = self.rotation / 90
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
        else:
            return None

    def __setTileset(self, tileset):
        """set the active tileset and resize accordingly"""
        self.__reload(tileset, self.lightSource)

    tileset = property(__getTileset, __setTileset)

    def __reload(self, tileset, lightSource):
        """call this if tileset or lightsource change: recomputes the entire board"""
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
            if isinstance(item, Tile):
                item.setZValue(item.level*100000+self.lightDistance(item))
            elif isinstance(item, Board):
                item.setZValue(self.lightDistance(item))

    def tileSize(self):
        """the current tile size"""
        return self.__tileset.tileSize

    def faceSize(self):
        """the current face size"""
        return self.__tileset.faceSize

    def faceRect(self, level=0):
        """the rect boundary around the tile faces, ignoring the shadows.
        level is the tile level. Use 1 for writing on a 2 story wall"""
        result = self.childrenBoundingRect()
        shW = self.tileset.shadowWidth()
        shH = self.tileset.shadowHeight()
        result.setWidth(result.width()-shW)
        result.setHeight(result.height()-shH)
        # shift once with border+shadow and only with border for higher level.
        # Note: border and shadow have the same sizes, shadowWidth is
        # border+shadow
        shifter = self.shiftZ(1+level/2.0)
        result.translate(shifter)
        return result

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

    def resizeEvent(self, event):
        """scale the scene for new view size"""
        if self.scene():
            self.fitInView(self.scene().itemsBoundingRect(), Qt.KeepAspectRatio)

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

