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

from PyQt4 import QtCore, QtGui
from tileset import Tileset,  TileException

class BoardTile(QtGui.QLabel):
    """a single tile on the board"""
    def __init__(self, parent,  element,  selected=False):
        super(BoardTile, self).__init__(parent)
        self.element = element
        self.selected = selected
        
class Board(QtGui.QWidget):
    """ a board with any number of positioned tiles"""
    def __init__(self, parent):
        super(Board, self).__init__(parent)
        self.boardSize = QtCore.QSize(parent.size())    # deep copy
        self.minimumHeight = 60
        self.minimumWidth = 40
        self.__angle = 2
        self.items = []
        self.xcells = 0
        self.ycells = 0
        self.__tileset = Tileset('default')
        pol = QtGui.QSizePolicy()
        pol.setHorizontalPolicy(QtGui.QSizePolicy.Expanding)
        pol.setVerticalPolicy(QtGui.QSizePolicy.Expanding)
        self.setSizePolicy(pol)

    def setTile(self, element, xpos, ypos, selected=False):
        """place a tile. selected: if True show it in selected color"""
        # we need to add placeholder widgets for holes. Otherwise we have a
        # problem if the hole is filled in later because the widgets are painted
        # in the order in which they are assigned to the board
        while len(self.items) < ypos+1:
            self.items.append([BoardTile(self, None)])
        line = self.items[ypos]
        while len(line) < xpos+1 :
            line.append(BoardTile(self,  None))
        self.ycells = len(self.items)
        self.xcells = max(self.xcells, len(line))
        if line[xpos].element != element or line[xpos].selected != selected:
            line[xpos].element = element
            line[xpos].selected = selected
            # we could optimize this and only repaint minimum tile set
            self.rebuild()
    
    def getAngle(self):
        """the active angle"""
        return self.__angle
        
    def setAngle(self, angle):
        """set active angle"""
        if not 0 < angle < 5:
            raise TileException('angle %d illegal' % angle)
        self.__angle = angle
    
    angle = property(getAngle,  setAngle)
    
    def getTileset(self):
        """the active tileset"""
        return self.__tileset
        
    def setTileset(self, tileset):
        """set the active tileset and resize accordingly"""
        if self.__tileset.name != tileset.name:
            self.__tileset = tileset
            self.resizeToBoard()

    tileset = property(getTileset, setTileset)
    
    def clearTile(self,  xpos,  ypos):
        """remove a Tile"""
        self.items[ypos][xpos].element = None
        
    def resizeEvent(self, event):
        """here we resize ourself"""
        self.boardSize = QtCore.QSize(event.size()) # deep copy
        self.resizeToBoard()
        
    def resizeToBoard(self):
        """resize to new board size"""
        snew = self.__tileset.preferredTileSize(self.boardSize, self.xcells, self.ycells)
        self.__tileset.updateScaleInfo(snew.width(), snew.height())
        self.rebuild()
    
    def rebuild(self):
        """rebuild board with current size"""
        fullw = self.__tileset.width()
        fullh = self.__tileset.height()
        facew = self.__tileset.faceWidth()
        faceh = self.__tileset.faceHeight()
        angle = self.__angle
        for posy,  line in enumerate(self.items[::1 if angle < 3 else -1]):
            for posx,  item in enumerate(line[::1 if angle == 2 or angle == 3 else -1]):
                if item.element:
                    item.setPixmap(self.__tileset.tile(item.element, angle, item.selected))
                    item.setGeometry(posx*facew, posy*faceh, fullw, fullh)
                else:
                    item.setPixmap(QtGui.QPixmap())
        
    def sizeHint(self):
        """the default size for the board"""
        return self.__tileset.gridSize(self.xcells,  self.ycells)
        
    def minimumSizeHint(self):
        """the minimum size for a tile"""
        return QtCore.QSize(32*self.xcells, 40*self.ycells)
        
