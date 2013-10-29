# -*- coding: utf-8 -*-

"""
 Copyright (C) 2008-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
"""

from PyQt4.QtCore import Qt, QString, QRectF, QPointF, QSizeF, QSize, pyqtProperty
from PyQt4.QtGui import QGraphicsObject, QGraphicsItem, QPixmap, QPainter
from PyQt4.QtGui import QColor
from util import logException, stack, logDebug
from guiutil import Painter
from common import LIGHTSOURCES, ZValues, Internal, Preferences, Debug, isAlive

from tile import Tile
from meld import Meld

class UITile(QGraphicsObject):
    """A tile visible on the screen. Every tile is only allocated once
    and then reshuffled and reused for every game.
    The unit of xoffset is the width of the tile,
    the unit of yoffset is the height of the tile.
    This is a QObject because we want to animate it."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, tile, xoffset = 0.0, yoffset = 0.0, level=0):
        QGraphicsObject.__init__(self)
        if not isinstance(tile, Tile):
            tile = Tile(tile)
        self._tile = tile
        self._boundingRect = None
        self._cross = False
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        # while moving the tile we use ItemCoordinateCache, see
        # Tile.setActiveAnimation
        self.__board = None
        self.setClippingFlags()
        self.__xoffset = xoffset
        self.__yoffset = yoffset
        self.__dark = False
        self.level = level
        self.activeAnimation = dict() # key is the property name
        self.queuedAnimations = []

    def showShadows(self):
        """do we need to show shadows?"""
        return self.board.showShadows if self.board else False

    def setClippingFlags(self):
        """if we do not show shadows, we need to clip"""
        showShadows = self.showShadows
        self.setFlag(QGraphicsItem.ItemClipsChildrenToShape, enabled=not showShadows)
        self.setFlag(QGraphicsItem.ItemClipsToShape, enabled=not showShadows)

    def keyPressEvent(self, event):
        """redirect to the board"""
        assert self == self.board.focusTile, 'id(self):%s, self:%s, focusTile:%s/%s' % \
        (id(self), self, id(self.board.focusTile), self.board.focusTile)
        return self.board.keyPressEvent(event)

    def __lightDistance(self):
        """the distance of item from the light source"""
        board = self.board
        if not board:
            return 0
        rect = self.sceneBoundingRect()
        lightSource = board.lightSource
        result = 0
        if 'E' in lightSource:
            result -= rect.right()
        if 'W' in lightSource:
            result += rect.left()
        if 'S' in lightSource:
            result -= rect.bottom()
        if 'N' in lightSource:
            result += rect.top()
        return result

    @property
    def tileset(self):
        """the active tileset"""
        return self.board.tileset if self.board else None

    def setDrawingOrder(self):
        """set drawing order for this tile"""
        boardLevel = self.board.level if self.board else ZValues.boardLevelFactor
        moving = 0
        # show moving tiles above non-moving tiles
        changePos = self.activeAnimation.get('pos')
        changeRotation = self.activeAnimation.get('rotation')
        changeScale = self.activeAnimation.get('scale')
        # show rotating and scaling tiles above all others
        if changeScale or changeRotation:
            moving += ZValues.moving
            moving += ZValues.boardLevelFactor
        elif changePos:
            if self.rotation % 180 == 0:
                currentY = self.y()
                newY = changePos.unpackEndValue().y()
            else:
                currentY = self.x()
                newY = changePos.unpackEndValue().x()
            if currentY != newY:
                moving += ZValues.moving
        self.setZValue(moving + \
            boardLevel + \
            (self.level+(2 if self.tile != 'Xy' else 1))*ZValues.itemLevelFactor + \
            self.__lightDistance())

    def boundingRect(self):
        """define the part of the tile we want to see. Do not return QRect()
        if tileset is not known because that makes QGraphicsscene crash"""
        if self.tileset:
            self._boundingRect = QRectF(QPointF(), self.tileset.tileSize if self.showShadows else self.tileset.faceSize)
        return self._boundingRect

    def facePos(self):
        """returns the face position relative to the tile
        depend on tileset, lightSource and shadow"""
        return self.board.tileFacePos()

    def showFace(self):
        """should we show face for this tile?"""
        game = Internal.field.game
        element = self.tile
        if game and game.isScoringGame():
            result = element and element != 'Xy' and (self.yoffset or not self.dark)
        else:
            result = element and element != 'Xy' and not self.dark
        return result

    def __elementId(self):
        """returns the SVG element id of the tile"""
        if not self.showShadows:
            return QString("TILE_2")
        lightSourceIndex = LIGHTSOURCES.index(self.board.rotatedLightSource())
        return QString("TILE_%1").arg(lightSourceIndex%4+1)

    def paint(self, painter, dummyOption, dummyWidget=None):
        """paint the entire tile.
        I tried to cache a pixmap for the tile and darkener but without face,
        but that actually made it slower."""
        with Painter(painter):
            renderer = self.tileset.renderer()
            withBorders = self.showShadows
            if not withBorders:
                painter.scale(*self.tileset.tileFaceRelation())
            renderer.render(painter, self.__elementId(), self.boundingRect())
            self._drawDarkness(painter)
        with Painter(painter):
            if self.showFace():
                if withBorders:
                    faceSize = self.tileset.faceSize.toSize()
                    renderer.render(painter, self.tileset.svgName[self.tile.lower()],
                            QRectF(self.facePos(), QSizeF(faceSize)))
                else:
                    renderer.render(painter, self.tileset.svgName[self.tile.lower()],
                        self.boundingRect())
        if self.cross:
            self.__paintCross(painter)

    def __paintCross(self, painter):
        """paint a cross on the tile"""
        with Painter(painter):
            faceSize = self.tileset.faceSize
            width = faceSize.width()
            height = faceSize.height()
            painter.translate(self.facePos())
            painter.drawLine(QPointF(0.0, 0.0), QPointF(width, height))
            painter.drawLine(QPointF(width, 0.0), QPointF(0.0, height))

    def pixmapFromSvg(self, pmapSize=None, withBorders=None):
        """returns a pixmap with default size as given in SVG and optional borders/shadows"""
        if withBorders is None:
            withBorders = Preferences.showShadows
        if withBorders:
            wantSize = self.tileset.tileSize.toSize()
        else:
            wantSize = self.tileset.faceSize.toSize()
        if not pmapSize:
            pmapSize = wantSize
        result = QPixmap(pmapSize)
        result.fill(Qt.transparent)
        painter = QPainter(result)
        if not painter.isActive():
            logException('painter is not active. Wanted size: %s' % str(pmapSize))
        try:
            xScale = float(pmapSize.width()) / wantSize.width()
            yScale = float(pmapSize.height()) / wantSize.height()
        except ZeroDivisionError:
            xScale = 1
            yScale = 1
        if not withBorders:
            painter.scale(*self.tileset.tileFaceRelation())
            painter.translate(-self.facePos())
        renderer = self.tileset.renderer()
        renderer.render(painter, self.__elementId())
        painter.resetTransform()
        self._drawDarkness(painter)
        if self.showFace():
            faceSize = self.tileset.faceSize.toSize()
            faceSize = QSize(faceSize.width() * xScale, faceSize.height() * yScale)
            painter.translate(self.facePos())
            renderer.render(painter, self.tileset.svgName[self.tile.lower()],
                    QRectF(QPointF(), QSizeF(faceSize)))
        return result

    def _drawDarkness(self, painter):
        """if appropriate, make tiles darker. Mainly used for hidden tiles"""
        if self.dark:
            board = self.board
            rect = board.tileFaceRect().adjusted(-1, -1, -1, -1)
            color = QColor('black')
            color.setAlpha(self.tileset.darkenerAlpha)
            painter.fillRect(rect, color)

    def sortKey(self, sortDir=Qt.Key_Right):
        """moving order for cursor"""
        dirs = [Qt.Key_Right, Qt.Key_Up, Qt.Key_Left, Qt.Key_Down] * 2
        sorter = dirs[dirs.index(sortDir) + self.__board.sceneRotation()//90]
        if sorter == Qt.Key_Down:
            return self.xoffset * 100 + self.yoffset
        elif sorter == Qt.Key_Up:
            return -self.xoffset * 100 - self.yoffset
        elif sorter == Qt.Key_Left:
            return -self.yoffset * 100 - self.xoffset
        else:
            return self.yoffset * 100 + self.xoffset

    def setBoard(self, board, xoffset=None, yoffset=None, level=0):
        """change Position of tile in board"""
        placeDirty = False
        if self.__board != board:
            oldBoard = self.__board
            self.__board = board
            if oldBoard:
                oldBoard.removeUITile(self)
            if board:
                board.addUITile(self)
            placeDirty = True
        if self.level != level:
            self.level = level
            placeDirty = True
        if xoffset is not None and xoffset != self.__xoffset:
            self.__xoffset = xoffset
            placeDirty = True
        if yoffset is not None and yoffset != self.__yoffset:
            self.__yoffset = yoffset
            placeDirty = True
        if board and placeDirty:
            board.placeTile(self)

    @property
    def tile(self):
        """tile"""
        return self._tile

    @tile.setter
    def tile(self, value): # pylint: disable=arguments-differ
        """set tile name and update display"""
        if value != self._tile:
            self._tile = value
            self.setDrawingOrder()
            self.update()

    @property
    def cross(self):
        """cross tiles in kongbox"""
        return self._cross

    @cross.setter
    def cross(self, value):
        """cross tiles in kongbox"""
        if self._cross == value:
            return
        self._cross = value
        self.update()

    @property
    def dark(self):
        """show face?"""
        return self.__dark

    @dark.setter
    def dark(self, value):
        """toggle and update display"""
        if value != self.__dark:
            self.__dark = value
            self.update()

    def _get_pos(self):
        """getter for property pos"""
        return QGraphicsObject.pos(self)

    def _set_pos(self, pos):
        """setter for property pos"""
        QGraphicsObject.setPos(self, pos)

    pos = pyqtProperty('QPointF', fget=_get_pos, fset=_set_pos)

    def _get_scale(self):
        """getter for property scale"""
        return QGraphicsObject.scale(self)

    def _set_scale(self, scale):
        """setter for property scale"""
        QGraphicsObject.setScale(self, scale)

    scale = pyqtProperty(float, fget=_get_scale, fset=_set_scale)

    def _get_rotation(self):
        """getter for property rotation"""
        return QGraphicsObject.rotation(self)

    def _set_rotation(self, rotation):
        """setter for property rotation"""
        QGraphicsObject.setRotation(self, rotation)

    rotation = pyqtProperty(float, fget=_get_rotation, fset=_set_rotation)

    def queuedAnimation(self, propertyName):
        """return the last queued animation for this tile and propertyName"""
        for item in reversed(self.queuedAnimations):
            if item.pName() == propertyName:
                return item

    def shortcutAnimation(self, animation):
        """directly set the end value of the animation"""
        setattr(self, animation.pName(), animation.unpackValue(animation.endValue()))
        self.queuedAnimations = []
        self.setDrawingOrder()

    def getValue(self, pName):
        """gets a property value by not returning a QVariant"""
        return {'pos': self.pos, 'rotation': self.rotation, 'scale':self.scale}[pName]

    def setActiveAnimation(self, animation):
        """the tile knows which of its properties are currently animated"""
        self.queuedAnimations = []
        propName = animation.pName()
        assert propName not in self.activeAnimation or not isAlive(self.activeAnimation[propName])
        self.activeAnimation[propName] = animation
        self.setCacheMode(QGraphicsItem.ItemCoordinateCache)

    def clearActiveAnimation(self, animation):
        """an animation for this tile has ended. Finalize tile in its new position"""
        del self.activeAnimation[animation.pName()]
        self.setDrawingOrder()
        if not len(self.activeAnimation):
            self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
            self.update()

    @property
    def focusable(self):
        """as the name says"""
        return bool(self.flags() & QGraphicsItem.ItemIsFocusable)

    @focusable.setter
    def focusable(self, value):
        """redirect and generate Debug output"""
        if str(self) in Debug.focusable:
            newStr = 'focusable' if value else 'unfocusable'
            logDebug('%s: %s from %s' % (newStr, self.tile, stack('')[-2]))
        self.setFlag(QGraphicsItem.ItemIsFocusable, value)

    @property
    def board(self):
        """get current board of this tile. Readonly."""
        return self.__board

    @property
    def xoffset(self):
        """in logical board coordinates"""
        return self.__xoffset

    @xoffset.setter
    def xoffset(self, value):
        """in logical board coordinates"""
        if value != self.__xoffset:
            self.__xoffset = value
            if self.__board:
                self.__board.placeTile(self)

    @property
    def yoffset(self):
        """in logical board coordinates"""
        return self.__yoffset

    @yoffset.setter
    def yoffset(self, value):
        """in logical board coordinates. Update board display."""
        if value != self.__yoffset:
            self.__yoffset = value
            if self.__board:
                self.__board.placeTile(self)

    def __str__(self):
        """printable string with tile"""
        rotation = ' rot%d' % self.rotation if self.rotation else ''
        scale = ' scale=%.2f' % self.scale if self.scale != 1 else ''
        level = ' level=%d' % self.level if self.level else ''
        if self.boundingRect():
            size = self.boundingRect()
            size = ' %.2dx%.2d' % (size.width(), size.height())
        else:
            size = ''
        return '%s(%s) %d: x/y/z=%.1f(%.1f)/%.1f(%.1f)/%.2f%s%s%s%s' % \
            (self.tile,
            self.board.name() if self.board else 'None', id(self) % 10000,
            self.xoffset, self.x(), self.yoffset,
            self.y(), self.zValue(), size, rotation, scale, level)

    def __repr__(self):
        """default representation"""
        return 'UITile(%s)' % str(self)

    def isBonus(self):
        """proxy for tile"""
        return self.tile.isBonus()

class UIMeld(list):
    """represents a visible meld. Can be empty. Many Meld methods will
    raise exceptions if the meld is empty. But we do not care,
    those methods are not supposed to be called on empty melds.
    UIMeld is a list of UITile"""

    __hash__ = None

    def __init__(self, newContent):
        list.__init__(self)
        if isinstance(newContent, list) and newContent and isinstance(newContent[0], UITile):
            self.extend(newContent)
        elif isinstance(newContent, UITile):
            self.append(newContent)
        assert len(self), newContent

    def typeName(self):
        """convert int to speaking name with shortcut"""
        return Meld(self).typeName()
