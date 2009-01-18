#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
 (C) 2008 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from PyQt4 import QtGui
from PyQt4.QtCore import QRect,  QSize
from PyQt4.QtGui import  QPainter,  QLabel,  QSizePolicy,  QLabel
from tileset import Tileset,  TileException

from util import logException

class Tile(QLabel):
    """a single tile on the board.
    the unit of xoffset is the width of the nextTo tile, 
    the unit of yoffset is the height of the nextTo tile. 
    If the nextTo tile is rotated by 90 or 270 degrees, the units are
    exchanged. If there is no nextTo, the units are determined by
    self.rotation
    """
    def __init__(self, element,  xoffset = 0, yoffset = 0, rotation = 0):
        super(Tile, self).__init__(None)
        self.board = None
        self.element = element
        self.selected = False
        self.nextTo = None
        self.xoffset = float(xoffset)
        self.yoffset = float(yoffset)
        self.rotation = rotation
        self.sized = False
        self.resetSize()
    
    def __str__(self):
        if self.nextTo is None:
            return '%s %d: atreal %d.%d, %dx%d noNextTo ' % \
                (self.element, id(self),  
                self.rect.left(), self.rect.top(), self.rect.width(), self.rect.height())
        else:
            return '%s %d: at real %d.%d, %dx%d x=%d y=%d %s %d (%d.%d, %dx%d) ' % \
                (self.element, id(self) , 
                self.rect.left(), self.rect.top(), self.rect.width(), self.rect.height(), 
                self.xoffset,
                self.yoffset,  
                self.nextTo.element, id(self.nextTo), 
                self.nextTo.rect.left(), self.nextTo.rect.top(), self.nextTo.rect.width(),
                self.nextTo.rect.height())
        
    def resetSize(self):
        """mark size as undefined"""
        self.sized = False 
        self.rect = QRect()

    def resize(self, newMetrics):
        """resize the tile to the board size"""
        if self.sized:
            return
        self.sized = True
        faceSize = newMetrics.faceSize
        newSize = QSize(newMetrics.tileSize)
        if self.rotation % 180 != 0:
            newSize.transpose()
        if self.rect.size() == newSize:
            return
        self.rect.setSize(newSize)
        nextTo = self.nextTo
        if nextTo:
            if not nextTo.sized:
                nextTo.resize(newMetrics)
            nextToRect = nextTo.rect
        else:
            nextToRect = QRect(0, 0, 0, 0)
        xunit = faceSize.width()
        yunit = faceSize.height()
        if nextTo:
            rotation = nextTo.rotation
        else:
            rotation = self.rotation
        if rotation % 180 != 0:
            xunit, yunit = yunit, xunit
        self.rect.moveTo(nextToRect.topLeft())
        self.rect.translate(self.xoffset*xunit, self.yoffset*yunit)

    def paintEvent(self, event):
        """paint the tile"""
        if event:
            pass # make pylint happy
        pixMap = self.board.tileset.tilePixmap(self.element,
            self.board.lightSource, self.rotation,  self.selected)
        painter = QPainter(self)
        painter.drawPixmap(0, 0, pixMap)
        painter.end()
        
    def attach(self,  element,  xoffset = 0, yoffset = 0,  rotation = 0):
        """attach a new tile to this one. If a tile with the same size exists at this        
            position, change that existing tile and return the existing tile. If a
            tile exists with the same topleft position, we delete that one first"""
        tile = Tile(element, xoffset, yoffset, rotation)
        tile.nextTo = self
        return self.board.add(tile)
 
    def select(self, selected=True):
        """selected tiles are drawn differently"""
        self.selected = selected
        
def cmpItemNE(aItem, bItem):
    """sort by distance to light source"""
    aval = -aItem.rect.right() + aItem.rect.top()
    bval = -bItem.rect.right() + bItem.rect.top()
    return aval - bval
    
def cmpItemNW(aItem, bItem):
    """sort by distance to light source"""
    aval = aItem.rect.left() + aItem.rect.top()
    bval = bItem.rect.left() + bItem.rect.top()
    return aval - bval
        
def cmpItemSW(aItem, bItem):
    """sort by distance to light source"""
    aval = aItem.rect.left() - aItem.rect.bottom()
    bval = bItem.rect.left() - bItem.rect.bottom()
    return aval - bval
    
def cmpItemSE(aItem, bItem):
    """sort by distance to light source"""
    aval = -aItem.rect.right() - aItem.rect.bottom()
    bval = -bItem.rect.right() - bItem.rect.bottom()
    return aval - bval
    
class Board(QtGui.QWidget):
    """ a board with any number of positioned tiles"""
    def __init__(self, parent):
        super(Board, self).__init__(parent)         
        self.sizeIncrement = 10
        self.__lightSource = 'NW'
        self.tiles = []
        self.maxBottom = 0
        self.maxRight = 0
        self.__tileset = Tileset('default')
        self.__newItems = []
        pol = QSizePolicy()
        pol.setHorizontalPolicy(QSizePolicy.Expanding)
        pol.setVerticalPolicy(QSizePolicy.Expanding)
        self.setSizePolicy(pol)
        self.__cmpItems = {'NE': cmpItemNE, 'NW': cmpItemNW, 
            'SW': cmpItemSW, 'SE': cmpItemSE}

    def addTile(self,  element,  xoffset = 0, yoffset = 0, rotation = 0):
        """adds a new tile to the board. If a tile with the same size exists at this        
            position, change that existing tile and return the existing tile. If a
            tile exists with the same topleft position, we delete that one first"""
        tile = Tile(element, xoffset, yoffset, rotation)
        return self.add(tile)
        
    def add(self, tile):
        """add the prepared tile to the board"""
        tile.board = self
        self.tiles.append(tile)
        self.resizeItems(self.__tileset.scaled)
        for item in self.tiles:
            if item == tile:
                continue
            if item.rect == tile.rect:
                item.element = tile.element
                item.selected = tile.selected
                self.repaint()
                self.tiles.remove(tile)
                del(tile)
                return item
            if item.rect.topLeft() == tile.rect.topLeft():
                self.tiles.remove(item)
                del(item)
                self.resizeItems(self.__tileset.scaled)
                break
        return tile
    
    def getLightSource(self):
        """the active lightSource"""
        return self.__lightSource
        
    def setLightSource(self, lightSource):
        """set active lightSource"""
        if   lightSource not in self.__tileset.lightSources:
            logException(TileException('lightSource %s illegal' % lightSource))
        self.__lightSource = lightSource
    
    lightSource = property(getLightSource,  setLightSource)
    
    def getTileset(self):
        """the active tileset"""
        return self.__tileset
        
    def setTileset(self, tileset):
        """set the active tileset and resize accordingly"""
        if self.__tileset.name != tileset.name:
            self.__tileset = tileset
            self.resizeEvent()

    tileset = property(getTileset, setTileset)
    
    def setDrawingOrder(self):
        """the tiles are painted by qt in the order in which they were
        added to the board widget. So if we place a tile between
        existing tiles, we have to reassign the following tiles.
        When calling setDrawingOrder, the tiles must already have positions
        and sizes"""
        if len(self.tiles) == 0:
            return
        self.__newItems = list(self.tiles)
        # order tiles according to light lightSource
        self.__newItems.sort(self.__cmpItems[self.lightSource])
        for idx, item in enumerate(self.tiles):
            if self.tiles[idx] is not self.__newItems[idx]:
                for delItem in self.tiles[idx:]:
                    delItem.setParent(None)
                for newItem in self.__newItems[idx:]:
                    newItem.setParent(self)
                break
            else:
                if item.parent() is None:
                    item.setParent(self)
                    item.show()
        self.tiles = self.__newItems

    def resizeItems(self, metrics):
        """compute item sizes for current board size.
        If we compute an item that is partially covered
        by another item (borders), compute that other item 
        first."""
        if len(self.tiles) == 0:
            width = 0
            height = 0 
            return
        # mark all tiles as unresized:
        for item in self.tiles:
            item.resetSize()
        for item in self.tiles:
            item.resize(metrics)
            
        # if we have a left or a top shadow, move all tiles
        # by shadow width
        xoffset = 0
        yoffset = 0
        if 'E' in self.lightSource:
            xoffset = metrics.shadowSize().width()-1
        if 'S' in self.lightSource:
            yoffset = metrics.shadowSize().height()-1
        for item in self.tiles:
            item.rect.translate(xoffset, yoffset)
            
        self.setDrawingOrder()
        # move the tiles such that the leftmost tile starts at x=0
        # and the topmost tile starts at y=0:
        mintop = min(min(x.rect.top() for x in self.tiles), 0)
        minleft = min(min(x.rect.left() for x in self.tiles), 0)
        if mintop != 0 or minleft != 0:
            for  item in self.tiles:
                item.rect.translate(-minleft, -mintop)
        width = 1 + max([x.rect.right() for x in self.tiles])
        height = 1 + max([x.rect.bottom() for x in self.tiles])
        return QSize(width, height)
        
    def resizeEvent(self, event=None):
        """here we resize all our tiles"""
        if event:
            pass # make pylint happy
        if len(self.tiles) == 0:
            return
        boardWidth = float(int(self.size().width() / self.sizeIncrement) * self.sizeIncrement)
        boardHeight = float(int(self.size().height() / self.sizeIncrement) * self.sizeIncrement)
        orgSize = self.resizeItems(self.__tileset.unscaled)
        modelRatio = float(orgSize.width()) / orgSize.height()
        viewRatio = float(boardWidth) / boardHeight 
        scaleWidth = boardWidth / orgSize.width()
        scaleHeight = boardHeight / orgSize.height()
        scale = scaleWidth if modelRatio > viewRatio else scaleHeight
        newtilew = int(scale * self.__tileset.unscaled.tileSize.width())
        newtileh = int(scale * self.__tileset.unscaled.tileSize.height())
        self.__tileset.updateScaleInfo(QSize(newtilew, newtileh))
        self.resizeItems(self.__tileset.scaled)
        for item in self.tiles:
            item.setGeometry(item.rect)
                
    def preferredSizeHint(self):
        """the preferred board size"""
        result = self.resizeItems(self.__tileset.unscaled)
        return result
        
    def minimumSizeHint(self):
        """the minimum size for the entire board"""
        result = self.resizeItems(self.__tileset.minimum)
        return result
