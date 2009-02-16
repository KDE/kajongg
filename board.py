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

from PyQt4.QtCore import Qt,  QPointF,  QString
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
    def __init__(self, element,  xoffset = 0, yoffset = 0, level=0):
        QGraphicsSvgItem.__init__(self)
        self.__board = None
        self.element = element
        self.selected = False
        self.level = level
        self.xoffset = xoffset
        self.yoffset = yoffset
        self.face = None

    def xmousePressEvent(self, event):
        """selects the tile. While moving, it should be above all other tiles"""
#        self.setZValue(1000000000)
        print 'mousepos:', self.mapToScene(event.pos())
        print 'tilerect:', self.mapToScene(self.boundingRect()).boundingRect()
        print 'tileset.tilesize:', self.tileset.tileSize
        if self.face:
            print 'facerect:', self.face.mapToScene(self.face.boundingRect()).boundingRect()
        print 'tileset.facesize:', self.tileset.faceSize
        QGraphicsSvgItem.mousePressEvent(self, event)
        
    def xmouseReleaseEvent(self, event):
        """deselect the tile. If it collides with another tile put it above it."""
        self.select(False)
        newLevel = self.level
        for item in self.collidingItems(Qt.IntersectsItemBoundingRect):
            # ignore the tiles, we only consider faces.
            if type(item) != Tile:
                if item.parentItem() is not self:
                    newLevel = max(item.parentItem().level + 1,  newLevel)
        self.level = newLevel
        self.board.setDrawingOrder()
        QGraphicsSvgItem.mouseReleaseEvent(self, event)
        
    def getBoard(self):
        """the board this tile belongs to"""
        return self.__board

    def setBoard(self, board):
        """assign the tile to a board and define it according to the board parameters"""
        if self.__board and board != self.__board:
            logException(TileException('Tile can only belong to one board'))
        self.prepareGeometryChange()
        self.__board = board
        self.setParentItem(board)
        self.placeInScene()
        self.setSharedRenderer(self.tileset.renderer())
        lightSource = self.board.lightSource
        shadowHeight = self.tileset.shadowHeight()
        shadowWidth = self.tileset.shadowWidth()
        xoffset = 0
        yoffset = 0
        
        lightSource = self.board.rotatedLightSource()
        if 'E' in lightSource:
            xoffset = shadowWidth-1
        if 'S' in lightSource:
            yoffset = shadowHeight-1
        if self.element:
            if not self.face:
                self.face = QGraphicsSvgItem()
                self.face.setParentItem(self)
                self.face.setElementId(self.element)
            # if we have a left or a top shadow, move face
            # by shadow width
            self.face.setPos(xoffset, yoffset)
            self.face.setSharedRenderer(self.tileset.renderer())
        else:
            self.face = None
        self.setTileId()
     
    board = property(getBoard, setBoard)
    
    def setTileId(self):
        """sets the SVG element id of the tile"""
        lightSourceIndex = LIGHTSOURCES.index(self.board.rotatedLightSource())
        tileName = QString("TILE_%1").arg(lightSourceIndex%4+1)
        if self.selected:
            tileName += '_SEL'
        self.setElementId(tileName)
    
    def getTileset(self):
        """the active tileset"""
        return self.parentItem().tileset
        
    tileset = property(getTileset)
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
        
    def placeInScene(self):
        """places the tile in the QGraphicsScene"""
        if not self.board:
            return
        width = self.tileset.faceSize.width()
        height = self.tileset.faceSize.height()
        shiftZ = self.board.shiftZ(self.level)
        sceneX = self.xoffset*width+ shiftZ.x()
        sceneY = self.yoffset*height+ shiftZ.y()
        self.setPos(sceneX, sceneY)
     
    def select(self, selected=True):
        """selected tiles are drawn differently"""
        if self.selected != selected:
            self.selected = selected
            self.setTileId()

 
class PlayerWind(QGraphicsEllipseItem):
    """a round wind tile"""
    def __init__(self, name, parent = None):
        """generate new wind tile"""
        QGraphicsEllipseItem.__init__(self)
        if parent:
            self.setParentItem(parent)
        self.name = name
        self.prevailing = False
        self.face = QGraphicsSvgItem()
        self.face.setParentItem(self)
        self.setWind(name, 0)
        if parent:
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
    def __init__(self, rotation = 0):
        QGraphicsRectItem.__init__(self)         
        self.rotation = rotation
        self.rotate(rotation)
        self.__lightSource = 'NW'
        self.__allTiles = []        
        self.__tileset = None
        self.xWidth = 0
        self.xHeight = 0
        self.yWidth = 0
        self.yHeight = 0

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

    def addTile(self,  element,  xoffset = 0, yoffset = 0, level=0):
        """adds a new tile to the board. If a tile with the same size exists at this        
            position, change that existing tile and return the existing tile. If a
            tile exists with the same topleft position, we delete that one first"""
        tile = Tile(element, xoffset, yoffset, level=level)
        return self.add(tile)
        
    def add(self, tile):
        """add the prepared tile to the board"""
        tile.board = self
        self.setDrawingOrder()
        return tile
    
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
        self.reposition()
        
    def reposition(self):
        """internal function: move the board to the correct position.
        This is also called when the tileset or the light source for this board changes"""
        if self.tileset is None:
            return
        width = self.tileset.faceSize.width()
        height = self.tileset.faceSize.height()
        newX = self.xWidth*width+self.xHeight*height
        newY = self.yWidth*width+self.yHeight*height
        lightSourceIndex = LIGHTSOURCES.index(self.lightSource)
        offsets = self.tileset.shadowOffsets[lightSourceIndex][self.rotation/90]
        newX += offsets[0]
        newY += offsets[1]
        QGraphicsRectItem.setPos(self, newX, newY)
        
    def getLightSource(self):
        """the active lightSource"""
        return self.__lightSource
        
    def setLightSource(self, lightSource):
        """set active lightSource"""
        if   lightSource not in LIGHTSOURCES:
            logException(TileException('lightSource %s illegal' % lightSource))
        self.reload(self.tileset, lightSource)
    
    lightSource = property(getLightSource,  setLightSource)
    
    def getTileset(self):
        """the active tileset"""
        if self.__tileset:
            return self.__tileset
        elif self.parentItem():
            return self.parentItem().tileset
        else:
            return None
        
    def setTileset(self, tileset):
        """set the active tileset and resize accordingly"""
        self.reload(tileset, self.lightSource)

    tileset = property(getTileset, setTileset)
    
    def reload(self, tileset, lightSource):
        """call this if tileset or lightsource change: recomputes the entire board"""
        if self.__tileset != tileset or self.__lightSource != lightSource:
            self.__tileset = tileset
            self.__lightSource = lightSource
            for child in self.children():
                if isinstance(child, Board) or isinstance(child, PlayerWind):
                    child.tileset = tileset
                    child.lightSource = lightSource
                elif isinstance(child, Tile):
                    child.board = self # tile will reposition itself
            self.reposition()
        
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
        for item in self.children():
            level = 0 if isinstance(item, Board) else item.level*100000
            item.setZValue(level+self.lightDistance(item))

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
        
        
    def placeAllTilesInScene(self):
        """we need to reposition all tiles if the tile size changes"""
        # mark all tiles as unplaced:
        for item in self.children():
            if isinstance(item, Tile):
                item.placeInScene()
        return
        
    def allTiles(self):
        """returns a list with all tileface names"""
        if len(self.__allTiles) == 0:
            for name, num, amount in (('CHARACTER', 9, 4), ('BAMBOO', 9, 4), 
                ('ROD', 9, 4), ('SEASON', 4, 1), ('FLOWER', 4, 1), ('WIND', 4, 4),
                ('DRAGON', 3, 4)):
                for idx in range(1, num+1):
                    self.__allTiles.extend([name + '_' + str(idx)]*amount)
        return list(self.__allTiles)

    def randomTile144(self):
        """a generator returning 144 random tiles"""
        tiles = self.allTiles()
        random.shuffle(tiles)
        for idx in range(0, len(tiles)):
            yield tiles[idx]


class FittingView(QGraphicsView):
    """a graphics view that always makes sure the whole scene is visible"""
    def __init__(self, parent=None):
        """generate a fitting view with our favorite properties"""
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
        QGraphicsView.resizeEvent(self, event)
        if self.scene():
            self.fitInView(self.scene().itemsBoundingRect(), Qt.KeepAspectRatio)
    
    def xmousePressEvent(self, event):
        """for debugging"""
        print 'mousepos:', self.mapToScene(event.pos())
        QGraphicsView.mousePressEvent(self, event)
        
class Walls(Board):
    """represents the four walls"""
    def __init__(self, length, tileset):
        Board.__init__(self)
        self.length = length
        self.dividePos = None
        self.lightSource = 'NW'
        self.tileset = tileset
        self.walls = [self.wall(angle) for angle in (270, 0, 90, 180)]
        self.walls[0].setPos(xWidth=self.length, yWidth=self.length, yHeight=1 )
        self.walls[1].setPos(yWidth=self.length)
        self.walls[2].setPos(xHeight=1)
        self.walls[3].setPos(xHeight=1, xWidth=self.length, yHeight=1)
        self.setDrawingOrder()

    def __getitem__(self, index):
        return self.walls[index]
        
    def wall(self, rotation):
        """builds one wall"""
        result = Board(rotation)
        result.setParentItem(self)
        result.lightSource = self.lightSource
        for position in range(0, self.length):
            result.addTile('', position)
            result.addTile('', position, level=1)
        return result

class Shisen(Board):
    """builds a Shisen board, just for testing"""
    def __init__(self):
        Board.__init__(self)
        tile = self.randomTile144()
        for row in range(0, 8):
            for col in range(0, 18):
                self.addTile(tile.next(), xoffset=col, yoffset=row)
                
 
class Solitaire(Board):
    """builds a Solitaire board, just for testing"""
    def __init__(self):
        Board.__init__(self)
        tile = self.randomTile144()
        for row, columns in enumerate((12, 8, 10, 12, 12, 10, 8, 12)):
            offset = (14-columns)/2 - 1
            for col  in range(0, columns):
                self.addTile(tile.next(), xoffset = col+offset,  yoffset=row)
        self.addTile(tile.next(), xoffset=-1, yoffset=3.5)
        self.addTile(tile.next(), xoffset=12, yoffset=3.5)
        self.addTile(tile.next(), xoffset=13, yoffset=3.5)
        for row in range(1, 7):
            for col in range(3, 9):
                self.addTile(tile.next(), xoffset=col, yoffset=row,  level=1)
        for row in range(2, 6):
            for col in range(4, 8):
                self.addTile(tile.next(), xoffset=col, yoffset=row,  level=2)
        for row in range(3, 5):
            for col in range(5, 7):
                self.addTile(tile.next(), xoffset=col, yoffset=row,  level=3)
        self.addTile(tile.next(), xoffset=5.5, yoffset=3.5,  level=4)
            
