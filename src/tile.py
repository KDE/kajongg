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

from PyQt4.QtCore import Qt, QPointF,  QString,  QRectF
from PyQt4.QtGui import  QGraphicsRectItem, QGraphicsItem, QPixmap, QPainter
from PyQt4.QtGui import QColor, QPen, QBrush, QStyleOptionGraphicsItem
from PyQt4.QtSvg import QGraphicsSvgItem
from tileset import LIGHTSOURCES, Elements

class Tile(QGraphicsSvgItem):
    """a single tile on the board.
    the unit of xoffset is the width of the tile,
    the unit of yoffset is the height of the tile.
    """
    def __init__(self, element,  xoffset = 0, yoffset = 0, level=0):
        QGraphicsSvgItem.__init__(self)
        if isinstance(element, Tile):
            xoffset, yoffset, level = element.xoffset, element.yoffset, element.level
            element = element.element
        self.setFlag(QGraphicsItem.ItemIsFocusable)
        self.__board = None
        self.element = element
        self.__selected = False
        self.level = level
        self.xoffset = xoffset
        self.yoffset = yoffset
        self.face = None
        self.__pixmap = None
        self.darkener = None
        self.opacity = 1.0

    def setOpacity(self, value):
        """Change this for qt4.5 which has setOpacity built in"""
        self.opacity = value
        self.recompute()

    def paint(self, painter, option, widget=None):
        """emulate setOpacity for qt4.4 and older"""
        if self.opacity > 0.5:
            QGraphicsSvgItem.paint(self, painter, option, widget)

    def paintAll(self,painter):
        """paint full tile with shadows"""
        option = QStyleOptionGraphicsItem()
        self.paint(painter, option)
        for item in [self.darkener, self.face]:
            if item and item.isVisibleTo(self):
                painter.save()
                painter.translate(item.pos())
                item.paint(painter, option)
                painter.restore()

    def focusInEvent(self, event):
        """tile gets focus: draw blue border"""
        self.board.showFocusRect(self)
        QGraphicsSvgItem.focusInEvent(self, event)

    @apply
    def focusable():
        """hide code"""
        def fget(self):
            return self.flags() & QGraphicsItem.ItemIsFocusable
        def fset(self, focusable):
            self.setFlag(QGraphicsItem.ItemIsFocusable, focusable)
        return property(**locals())

    @apply
    def board():
        """get/assign the tile to a board and define it according to the board parameters.
        This always recomputes the tile position in the board even if we assign to the
        same board - class Board depends on this"""
        def fget(self):
            return self.__board
        def fset(self, board):
            if not board:
                self.hide()
            self.__board = board
            self.recompute()
        return property(**locals())

    def facePos(self):
        """returns the face position relative to the tile"""
        return self.board.tileFacePos()

    def recompute(self):
        """recomputes position and visuals of the tile"""
        self.setParentItem(self.__board)
        if self.__board is None:
            return
        if self.tileset:
            self.setSharedRenderer(self.tileset.renderer())
        if self.dark: # we need to regenerate the darkener
            self.dark = False
            self.dark = True
        self.setTileId()
        self.placeInBoard()

        if self.element and self.element != 'Xy' and self.opacity > 0:
            if not self.face:
                self.face = QGraphicsSvgItem()
                self.face.setParentItem(self)
                self.face.setElementId(Elements.name[self.element.lower()])
                self.face.setZValue(1) # above the darkener
            # if we have a left or a top shadow, move face
            # by shadow width
            facePos = self.facePos()
            self.face.setPos(facePos.x(), facePos.y())
            self.face.setSharedRenderer(self.tileset.renderer())
        elif self.face:
            self.face.setParentItem(None)
            self.face = None

    @apply
    def dark():
        def fget(self):
            return self.darkener is not None
        def fset(self, dark):
            if dark:
                if self.darkener is None:
                    self.darkener = QGraphicsRectItem()
                    self.darkener.setParentItem(self)
                    self.darkener.setRect(QRectF(self.facePos(), self.tileset.faceSize))
                    self.darkener.setPen(QPen(Qt.NoPen))
                    color = QColor('black')
                    color.setAlpha(self.tileset.darkenerAlpha)
                    self.darkener.setBrush(QBrush(color))
            else:
                if self.darkener is not None:
                    self.darkener.hide()
                    self.darkener = None
        return property(**locals())

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

    @property
    def tileset(self):
        """the active tileset"""
        parent = self.parentItem()
        return parent.tileset if parent else None

    def sizeStr(self):
        """printable string with tile size"""
        size = self.sceneBoundingRect()
        if size:
            return '%d.%d %dx%d' % (size.left(), size.top(), size.width(), size.height())
        else:
            return 'No Size'

    def lower(self):
        return self.element.lower()

    def upper(self):
        if self.isBonus():
            return self.element
        return self.element[0].upper() + self.element[1]

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

    @apply
    def selected():
        """selected tiles are drawn differently"""
        def fget(self):
            return self.__selected
        def fset(self, selected):
            if self.__selected != selected:
                self.__selected = selected
                self.setTileId()
        return property(**locals())

    def hide(self):
        if self.board and self == self.board.focusTile:
            self.board.hideFocusRect()
        QGraphicsSvgItem.hide(self)

    def clickableRect(self):
        """returns a rect for the range where a click is allowed (excludes border and shadow).
        Value in item coordinates"""
        return QRectF(self.facePos(), self.tileset.faceSize)

    def isFlower(self):
        """is this a flower tile?"""
        return self.element[0] == 'f'

    def isSeason(self):
        """is this a season tile?"""
        return self.element[0] == 'y'

    def isBonus(self):
        """is this a bonus tile? (flower,season)"""
        return self.isFlower() or self.isSeason()

    def isHonor(self):
        """is this a wind or dragon?"""
        return self.element[0] in 'wWdD'

    def pixmap(self, pmapSize=None):
        if not pmapSize:
            pmapSize = self.tileset.tileSize # ().size().toSize()
        if self.__pixmap is None or self.__pixmap.size() != pmapSize:
            self.__pixmap = QPixmap(pmapSize)
            self.__pixmap.fill(Qt.transparent)
            painter = QPainter(self.__pixmap)
            if not painter.isActive():
                print 'painter is not active'
                return None
            try:
                xScale = pmapSize.width() / self.boundingRect().width()
                yScale = pmapSize.height() / self.boundingRect().height()
            except ZeroDivisionError:
                xScale = 1
                yScale = 1
            painter.scale(xScale, yScale)
            QGraphicsSvgItem.paint(self, painter, QStyleOptionGraphicsItem())
            for child in self.childItems():
                if isinstance(child, QGraphicsSvgItem):
                    painter.save()
                    painter.translate(child.mapToParent(0.0, 0.0))
                    QGraphicsSvgItem.paint(child, painter, QStyleOptionGraphicsItem())
                    painter.restore()
        return self.__pixmap

    @staticmethod
    def chiNext(element, offset):
        """the element name of the following value"""
        color, baseValue = element
        baseValue = int(baseValue)
        return '%s%d' % (color, baseValue+offset)

