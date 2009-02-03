#!/usr/bin/env python
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
from PyQt4.QtGui import  QPainter,  QLabel,  QSizePolicy,  QLabel,  QFrame
from tileset import Tileset,  TileException
import random

from util import logException

class Tile(QLabel):
    """a single tile on the board.
    the unit of xoffset is the width of the nextTo tile, 
    the unit of yoffset is the height of the nextTo tile. 
    If the nextTo tile is rotated by 90 or 270 degrees, the units are
    exchanged. If there is no nextTo, the units are determined by
    self.rotation
    """
    def __init__(self, element,  xoffset = 0, yoffset = 0, rotation = 0, level=0):
        super(Tile, self).__init__(None)
        self.board = None
        self.element = element
        self.selected = False
        self.level = level
        self.nextTo = None
        self.xoffset = float(xoffset)
        self.yoffset = float(yoffset)
        self.rotation = rotation
        self.scaledRect = None
        self.unscaledRect = None
    
    def sizeStr(self, scaled):
        """printable string with tile size"""
        if scaled:
            size= self.scaledRect
        else:
            size = self.unscaledRect
        if size:
            return '%d.%d %dx%d' % (size.left(), size.top(), size.width(), size.height())
        else:
            return 'No Size'
            
    def __str__(self):
        """printable string with tile data"""
        if self.nextTo is None:
            return '%s %d: at %s %d noNextTo ' % (self.element, id(self), self.sizeStr(False), self.level)
        else:
            return '%s %d: at %s x=%d y=%d z=%d %s %d (%s) ' % \
                (self.element, id(self),  self.sizeStr(False), 
                self.xoffset,
                self.yoffset,  
                self.level, 
                self.nextTo.element, id(self.nextTo), 
                self.nextTo.sizeStr(False))
        
    def resetSize(self, scaled):
        """mark rect as undefined"""
        if scaled:
            self.scaledRect = None
        else:
            self.unscaledRect = None

    def rect(self, scaled):
        """the scaled or unscaled tile rect"""
        if scaled:
            return self.scaledRect
        else:
            return self.unscaledRect
            
    def resize(self, scaled):
        """resize the tile to the board size"""
        if self.rect(scaled):
            return self.rect(scaled)
        newMetrics = self.board.metrics(scaled)
        nextTo = self.nextTo
        if nextTo:
            if not nextTo.rect(scaled):
                nextTo.resize(scaled)
            nextToRect = nextTo.rect(scaled)
        else:
            nextToRect = QRect(0, 0, 0, 0)
        newSize = QSize(newMetrics.tileSize)
        if self.rotation % 180 != 0:
            newSize.transpose()
        result = QRect(0, 0, 0, 0)
        result.setSize(newSize)
        xunit = newMetrics.faceSize.width()
        yunit = newMetrics.faceSize.height()
        nextTo = self.nextTo
        if nextTo:
            nextToRect = nextTo.rect(scaled)
            rotation = nextTo.rotation
        else:
            nextToRect = QRect(0, 0, 0, 0)
            rotation = self.rotation
        if rotation % 180 != 0:
            xunit, yunit = yunit, xunit
        result.moveTo(nextToRect.topLeft())
        result.translate(self.xoffset*xunit, self.yoffset*yunit)
        
        # if we are on a higher level, shift:
        if self.level > 0:
            shiftX = 0
            shiftY = 0
            stepX = self.level*newMetrics.shadowWidth()/2
            stepY = self.level*newMetrics.shadowHeight()/2
            if 'E' in self.board.lightSource:
                shiftX = stepX
            if 'W' in self.board.lightSource:
                shiftX = -stepX
            if 'N' in self.board.lightSource:
                shiftY = -stepY
            if 'S' in self.board.lightSource:
                shiftY = stepY
            result.translate(shiftX, shiftY)
        if scaled:
            self.scaledRect = result
        else:
            self.unscaledRect = result
        return result
     
    def translate(self, deltaX, deltaY, scaled):
        """translate the scaled or the unscaled item"""
        if scaled:
            self.scaledRect.translate(deltaX, deltaY)
        else:
            self.unscaledRect.translate(deltaX, deltaY)
            
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
 
    def attachOver(self,  element,  xoffset = 0, yoffset = 0):
        """Same as attach, but one level higher.  And rotation is inherited."""
        tile = Tile(element, xoffset, yoffset, self.rotation)
        tile.nextTo = self
        tile.level = self.level + 1
        return self.board.add(tile)
 
    def select(self, selected=True):
        """selected tiles are drawn differently"""
        if self.selected != selected:
            self.selected = selected
            self.repaint()
        
def cmpItemNE(aItem, bItem):
    """sort by distance to light source"""
    if aItem.level != bItem.level:
        return aItem.level - bItem.level
    aval = -aItem.rect(False).right() + aItem.rect(False).top()
    bval = -bItem.rect(False).right() + bItem.rect(False).top()
    return aval - bval
    
def cmpItemNW(aItem, bItem):
    """sort by distance to light source"""
    if aItem.level != bItem.level:
        return aItem.level - bItem.level
    aval = aItem.rect(False).left() + aItem.rect(False).top()
    bval = bItem.rect(False).left() + bItem.rect(False).top()
    return aval - bval
        
def cmpItemSW(aItem, bItem):
    """sort by distance to light source"""
    if aItem.level != bItem.level:
        return aItem.level - bItem.level
    aval = aItem.rect(False).left() - aItem.rect(False).bottom()
    bval = bItem.rect(False).left() - bItem.rect(False).bottom()
    return aval - bval
    
def cmpItemSE(aItem, bItem):
    """sort by distance to light source"""
    if aItem.level != bItem.level:
        return aItem.level - bItem.level
    aval = -aItem.rect(False).right() - aItem.rect(False).bottom()
    bval = -bItem.rect(False).right() - bItem.rect(False).bottom()
    return aval - bval
    
class Board(QtGui.QFrame):
    """ a board with any number of positioned tiles"""
    def __init__(self, parent):
        QFrame.__init__(self, parent)         
        self.sizeIncrement = 20
        self.__lightSource = 'NW'
        self.setFrameStyle(QFrame.Box|QFrame.Plain)
        self.tiles = []
        self.__allTiles = []        
        self.boardWidth = 0
        self.boardHeight = 0
        self.__unscaledSize = None
        self.__scaledSize = None
        self.__tileset = Tileset('default') # TODO: wegoptimieren
        self.__newItems = []
        self.sizeSource = None
        self.pol = QSizePolicy()
        self.pol.setHorizontalPolicy(QSizePolicy.Preferred)
        self.pol.setVerticalPolicy(QSizePolicy.Preferred)
        self.setSizePolicy(self.pol)
        self.__cmpItems = {'NE': cmpItemNE, 'NW': cmpItemNW, 
            'SW': cmpItemSW, 'SE': cmpItemSE}

    def addTile(self,  element,  xoffset = 0, yoffset = 0, rotation = 0,  level=0):
        """adds a new tile to the board. If a tile with the same size exists at this        
            position, change that existing tile and return the existing tile. If a
            tile exists with the same topleft position, we delete that one first"""
        tile = Tile(element, xoffset, yoffset, rotation, level)
        return self.add(tile)
        
    def add(self, tile):
        """add the prepared tile to the board"""
        tile.board = self
        self.tiles.append(tile)
        tile.resize(False)
        for item in self.tiles:
            if item == tile:
                continue
            if item.level != tile.level:
                continue
            if item.rect(False) == tile.rect(False):
                item.element = tile.element
                item.selected = tile.selected
                self.repaint()
                self.tiles.remove(tile)
                del(tile)
                return item
            if item.rect(False).topLeft() == tile.rect(False).topLeft():
                self.tiles.remove(item)
                del(item)
                self.resizeItems(False)
                break
        self.__scaledSize = None
        self.setDrawingOrder()
        self.resizeItems(True)
        self.updateGeometry()
        self.update()
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
            self.resizeItems(False)
            self.updateItemGeometry(self.size())
            self.updateGeometry()
            self.update()
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

    def metrics(self, scaled):
        """the current metrics"""
        if scaled:
            return self.__tileset.scaled
        else:
            return self.__tileset.unscaled
            
    def resizeItems(self, scaled):
        """compute item sizes for current board size.
        If we compute an item that is partially covered
        by another item (borders), compute that other item 
        first."""
        if len(self.tiles) == 0:
            return
        # mark all tiles as unresized:
        for item in self.tiles:
            item.resetSize(scaled)
        for item in self.tiles:
            item.resize(scaled)
            
        # if we have a left or a top shadow, move all tiles
        # by shadow width
        xoffset = 0
        yoffset = 0
        if 'E' in self.lightSource:
            xoffset = self.metrics(scaled).shadowSize().width()-1
        if 'S' in self.lightSource:
            yoffset = self.metrics(scaled).shadowSize().height()-1
        for item in self.tiles:
            item.translate(xoffset, yoffset, scaled)
            
        # move the tiles such that the leftmost tile starts at x=0
        # and the topmost tile starts at y=0:
        minY = min(min(x.rect(scaled).top() for x in self.tiles), 0)
        minX = min(min(x.rect(scaled).left() for x in self.tiles), 0)
        maxY = max(max(x.rect(scaled).bottom() for x in self.tiles), 0)
        maxX = max(max(x.rect(scaled).right() for x in self.tiles), 0)
        width = 1 + maxX - minX
        height = 1 + maxY - minY
            
        if scaled:
            self.__scaledSize = QSize(width, height)
            xdelta = 0
            ydelta = 0
            if minY != 0 or minX != 0:
                xdelta = -minX
                ydelta = -minY
            if width < self.width():
                xdelta += (self.width() - width ) / 2
            if height < self.height():
                ydelta += (self.height() - height) / 2
            if xdelta != 0 or ydelta != 0:
                for  item in self.tiles:
                    item.translate(xdelta, ydelta, scaled)
        else:
            self.__unscaledSize = QSize(width, height)
        
    def unscaledSize(self):
        """the unscaled size of the entire board"""
        if  not self.__unscaledSize:
            self.resizeItems(scaled=False)
        return self.__unscaledSize
        
    def scaledSize(self):
        """the scaled size of the entire board"""
        if  not self.__scaledSize:
            self.resizeItems(scaled=True)
        return self.__scaledSize
        
    def resizeEvent(self, event):
        """here we resize all our tiles"""
        if event.size().height() == 0 or event.size().width() == 0:
            return
        # do not recompute all tiles for every slight change
        if (0 < event.size().height() - self.boardHeight  < self.sizeIncrement) \
            and (0 < event.size().width() - self.boardWidth  < self.sizeIncrement):
            return
        self.updateItemGeometry(event.size())
            
    def updateItemGeometry(self, newSize):
        """compute new geometry for all tiles"""
        if len(self.tiles) == 0:
            return
        self.boardWidth = newSize.width()
        self.boardHeight = newSize.height()
        modelRatio = float(self.unscaledSize().width()) / float(self.unscaledSize().height())
        viewRatio = float(self.boardWidth) / self.boardHeight 
        scaleWidth = float(self.boardWidth) / self.unscaledSize().width()
        scaleHeight = float(self.boardHeight) / self.unscaledSize().height()
        scale = scaleWidth if modelRatio > viewRatio else scaleHeight
        newtilew = int(scale * self.__tileset.unscaled.tileSize.width())
        newtileh = int(scale * self.__tileset.unscaled.tileSize.height())
        self.__tileset.updateScaleInfo(QSize(newtilew, newtileh))
        self.resizeItems(scaled=True)
     
    def paintEvent(self, event):
        """set the geometry for all tiles"""
        if len(self.tiles) == 0:
            return
        if event:
            pass # satisfy pylint
        for item in self.tiles:
            item.setGeometry(item.rect(True))
        QFrame.paintEvent(self, event)
        
    def sizeHint(self):
        """the preferred board size"""
        return self.unscaledSize()
        
    def minimumSizeHint(self):
        """the minimum size for the entire board"""
        if self.sizeSource:
            return self.sizeSource.size()
        result = self.unscaledSize() * 0.15
        return result

    def maximumSize(self):
        """the maximum size for the entire board"""
        result = self.unscaledSize() * 20
        return result
        
    def allTiles(self):
        """returns a list with all tileface namess"""
        if len(self.__allTiles) == 0:
            for name, num, amount in (('CHARACTER', 9, 4), ('BAMBOO', 9, 4), 
                ('ROD', 9, 4), ('SEASON', 4, 1), ('FLOWER', 4, 1), ('WIND', 4, 4),
                ('DRAGON', 3, 4)):
                for idx in range(1, num+1):
                    for xxxx in range(0, amount):
                        self.__allTiles.append(name + '_' + str(idx))
        return list(self.__allTiles)

    def randomTile144(self):
        """a generator returning 144 random tiles"""
        tiles = self.allTiles()
        random.shuffle(tiles)
        for idx in range(0, len(tiles)):
            yield tiles[idx]
