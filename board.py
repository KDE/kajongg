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

from util import *

class Tile(QLabel):
    """a single tile on the board"""
    def __init__(self,  board,  element, nextTo = None,
            align ='R', offset = 0, selected = False,  rotation = 0):
        super(Tile, self).__init__(None)
        self.board = board
        self.element = element
        self.selected = selected
        self.nextTo = nextTo
        self.align = align
        self.offset = float(offset)
        self.rotation = rotation
        self.sized = False
        self.resetSize()
    
    def nextToKey(self):
        """hash"""
        return 'N%dA%s' % (id(self.nextTo), self.align)

    def __str__(self):
        if self.nextTo is None:
            return '%s %d: atreal %d.%d, %dx%d noNextTo ' % \
                (self.element, id(self),  
                self.rect.left(), self.rect.top(), self.rect.width(), self.rect.height())
        else:
            return '%s %d: at real %d.%d, %dx%d %s %s %d (%d.%d, %dx%d) ' % \
                (self.element, id(self) , 
                self.rect.left(), self.rect.top(), self.rect.width(), self.rect.height(), 
                self.align, 
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
        shadowSize = newMetrics.shadowSize()
        newSize = QSize(newMetrics.tileSize)
        if self.rotation % 180 != 0:
            newSize.transpose()
        if self.rect.size() == newSize:
            return
        self.rect.setSize(newSize)
        nextTo = self.nextTo
        if nextTo is None:
            nextToRect = QRect(0, 0, 0, 0)
            skipShadow = QSize(0, 0)
        else:
            if not nextTo.sized:
                nextTo.resize(newMetrics)
            nextToRect = nextTo.rect
            skipShadow = shadowSize
        if self.align == 'R':
            self.rect.moveTopLeft(nextToRect.topRight())
            self.rect.translate(1-skipShadow.width(), self.offset*faceSize.height())
        elif self.align == 'L':
            self.rect.moveTopRight(nextToRect.topLeft())
            self.rect.translate(1+skipShadow.width(), self.offset*faceSize.height())
        elif self.align == 'B':
            self.rect.moveTopLeft(nextToRect.bottomLeft())
            self.rect.translate(self.offset*faceSize.width(), 1-skipShadow.height())
        elif self.align == 'T':
            self.rect.moveBottomLeft(nextToRect.topLeft())
            self.rect.translate(self.offset*faceSize.width(), 1+skipShadow.height())
   
    def paintEvent(self, event):
        """paint the tile"""
        if event:
            pass # make pylint happy
        pixMap = self.board.tileset.tilePixmap(self.element,
            self.board.angle, self.rotation,  self.selected)
        painter = QPainter(self)
        painter.drawPixmap(0, 0, pixMap)
        painter.end()
 
def cmpItemNW(aItem, bItem):
    """sort by distance to light source"""
    aval = aItem.rect.left() + aItem.rect.top()
    bval = bItem.rect.left() + bItem.rect.top()
    return aval - bval
        
def cmpItemNE(aItem, bItem):
    """sort by distance to light source"""
    aval = -aItem.rect.right() + aItem.rect.top()
    bval = -bItem.rect.right() + bItem.rect.top()
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
        self.__angle = 2
        self.tiles = []
        self.maxBottom = 0
        self.maxRight = 0
        self.__tileset = Tileset('default')
        self.__newItems = []
        pol = QSizePolicy()
        pol.setHorizontalPolicy(QSizePolicy.Expanding)
        pol.setVerticalPolicy(QSizePolicy.Expanding)
        self.setSizePolicy(pol)

    def addTile(self,  element, nextTo = None,
            align ='R', offset = 0, selected = False,  rotation = 0):
        """adds a new tile to the board. If a tile already is attached to the same 
        neighbour, change that existing tile and return the existing tile. If this is
        a new tile, add and return it"""
        tile = Tile(self, element, nextTo, align, offset, selected, rotation)
        self.resizeItems(self.__tileset.scaled)
        tile.resize(self.__tileset.scaled)
        for item in self.tiles:
            if item.nextToKey() == tile.nextToKey():
                item.element = tile.element
                item.selected = tile.selected
                self.repaint()
                return item
        self.tiles.append(tile)
        return tile
    
    def getAngle(self):
        """the active angle"""
        return self.__angle
        
    def setAngle(self, angle):
        """set active angle"""
        if   not 0 < angle < 5:
            logException(TileException('angle %d illegal' % angle))
        self.__angle = angle
    
    angle = property(getAngle,  setAngle)
    
    def getTileset(self):
        """the active tileset"""
        return self.__tileset
        
    def setTileset(self, tileset):
        """set the active tileset and resize accordingly"""
        if self.__tileset.name != tileset.name:
            self.__tileset = tileset
            self.resizeEvent()

    tileset = property(getTileset, setTileset)
    
    def setZOrder(self):
        """the tiles are painted by qt in the order in which they were
        added to the board widget. So if we place a tile between
        existing tiles, we have to reassign the following tiles.
        When calling setZOrder, the tiles must already have positions
        and sizes"""
        if len(self.tiles) == 0:
            return
        self.__newItems = list(self.tiles)
        # order tiles according to light angle
        cmpItems = [cmpItemNE, cmpItemNW, cmpItemSW, cmpItemSE]
        self.__newItems.sort(cmpItems[self.__angle-1])
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
        # make sure all our tiles are in positive coordinates:
        mintop = min(min(x.rect.top() for x in self.tiles), 0)
        minleft = min(min(x.rect.left() for x in self.tiles), 0)
        if mintop < 0 or minleft < 0:
            for  item in self.tiles:
                item.rect.translate(-minleft, -mintop)

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
        # order tiles by distance to light source
        self.setZOrder()
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

#    def preferredSizeHint(self):
 #       """the minimum size for the entire board"""
  #      return QtCore.QSize(32, 40)

class Grid(Board):
    """if all tiles have the same rotation and no offsets, this is
    easier to use than Board"""
    def __init__(self, parent=None,  rotation = 0):
        super(Grid, self).__init__(parent)
        self.rotation = rotation
#        self.boardSize = QSize(parent.size())    # deep copy
        self.gridItems = [[None]]

    def placeTile(self, element, row = 0,  column = 0, selected = False):
        """place a tile. selected: if True show it in selected color"""
        # we need to add placeholder labels for holes. Otherwise we have a
        # problem if the hole is filled in later
        while len(self.gridItems)<=row:
            self.gridItems.append([None])
        while len(self.gridItems[row])<=column:
            self.gridItems[row].append(None)
        if column > 0 and self.gridItems[row][column-1] is None:
            self.placeTile(None, row, column-1)
        if row > 0 and self.gridItems[row-1][0] is None:
            self.placeTile(None, row-1, 0)

        align = 'R'
        nextTo = None
        if column > 0:
            nextTo = self.gridItems[row][column-1]
        elif row > 0:
            nextTo = self.gridItems[row-1][0]
            align = 'B'
        self.gridItems[row][column] = self.addTile(element, nextTo=nextTo, 
            align=align,  selected=selected, 
            rotation =self.rotation)
