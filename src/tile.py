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

from PyQt4.QtCore import Qt, QString, QRectF, QPointF, QSizeF, QSize, pyqtProperty, QObject
from PyQt4.QtGui import QGraphicsItem, QPixmap, QPainter
from PyQt4.QtGui import QColor
from util import logException, stack, logDebug
from common import LIGHTSOURCES, ZValues, InternalParameters, Preferences, Debug, isAlive

def chiNext(element, offset):
    """the element name of the following value"""
    color, baseValue = element
    baseValue = int(baseValue)
    return '%s%d' % (color, baseValue+offset)

def swapTitle(element):
    """if istitle, return lower. If lower, return capitalize"""
    if element.islower():
        return element.capitalize()
    else:
        return element.lower()

class GraphicsTileItem(QGraphicsItem):
    """represents all sorts of tiles"""

    def __init__(self, tile):
        QGraphicsItem.__init__(self)
        self.tile = tile
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        # while moving the tile we use ItemCoordinateCache, see
        # Tile.setActiveAnimation
        self.setClippingFlags()

    def setClippingFlags(self):
        """if we do not show shadows, we need to clip"""
        showShadows = self.showShadows
        self.setFlag(QGraphicsItem.ItemClipsChildrenToShape, enabled=not showShadows)
        self.setFlag(QGraphicsItem.ItemClipsToShape, enabled=not showShadows)

    def keyPressEvent(self, event):
        """redirect to the board"""
        assert self == self.tile.board.focusTile.graphics, 'id(self):%s, self:%s, focusTile:%s/%s' % \
           (id(self), self, id(self.tile.board.focusTile), self.tile.board.focusTile)
        return self.tile.board.keyPressEvent(event)

    def __lightDistance(self):
        """the distance of item from the light source"""
        board = self.tile.board
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
        return self.tile.board.tileset if self.tile.board else None

    def setDrawingOrder(self):
        """set drawing order for this tile"""
        boardLevel = self.tile.board.level if self.tile.board else ZValues.boardLevelFactor
        moving = 0
        # show moving tiles above non-moving tiles
        changePos = self.tile.activeAnimation.get('pos')
        changeRotation = self.tile.activeAnimation.get('rotation')
        changeScale = self.tile.activeAnimation.get('scale')
        # show rotating and scaling tiles above all others
        if changeScale or changeRotation:
            moving += ZValues.moving
            moving += ZValues.boardLevelFactor
        elif changePos:
            if self.rotation() % 180 == 0:
                currentY = self.y()
                newY = changePos.unpackEndValue().y()
            else:
                currentY = self.x()
                newY = changePos.unpackEndValue().x()
            if currentY != newY:
                moving += ZValues.moving
        self.setZValue(moving + \
            boardLevel + \
            (self.tile.level+(2 if self.tile.element !='Xy' else 1))*ZValues.itemLevelFactor + \
            self.__lightDistance())

    def boundingRect(self):
        """define the part of the tile we want to see"""
        return QRectF(QPointF(), self.tileset.tileSize if self.showShadows else self.tileset.faceSize)

    @property
    def showShadows(self):
        """do we need to show shadows?"""
        return self.tile.board.showShadows if self.tile.board else False

    def facePos(self):
        """returns the face position relative to the tile
        depend on tileset, lightSource and shadow"""
        return self.tile.board.tileFacePos()

    def showFace(self):
        """should we show face for this tile?"""
        game = InternalParameters.field.game
        element = self.tile.element
        if game and game.isScoringGame():
            result = element and element != 'Xy' and (self.tile.yoffset or not self.tile.dark)
        else:
            result = element and element != 'Xy' and not self.tile.dark
        return result

    def elementId(self):
        """returns the SVG element id of the tile"""
        if not self.showShadows:
            return QString("TILE_2")
        lightSourceIndex = LIGHTSOURCES.index(self.tile.board.rotatedLightSource())
        return QString("TILE_%1").arg(lightSourceIndex%4+1)

    def paint(self, painter, dummyOption, dummyWidget=None):
        """paint the entire tile.
        I tried to cache a pixmap for the tile and darkener but without face,
        but that actually made it slower."""
        painter.save()
        renderer = self.tileset.renderer()
        withBorders = self.showShadows
        if not withBorders:
            painter.scale(*self.tileset.tileFaceRelation())
        renderer.render(painter, self.elementId(), self.boundingRect())
        self._drawDarkness(painter)
        painter.restore()
        painter.save()
        if self.showFace():
            if withBorders:
                faceSize = self.tileset.faceSize.toSize()
                renderer.render(painter, self.tileset.svgName[self.tile.element.lower()],
                        QRectF(self.facePos(), QSizeF(faceSize)))
            else:
                renderer.render(painter, self.tileset.svgName[self.tile.element.lower()],
                    self.boundingRect())
        painter.restore()
        game = InternalParameters.field.game
        if game:
            kongBox = game.wall.kongBox
            if kongBox and self.tile in kongBox:
                painter.save()
                faceSize = self.tileset.faceSize
                width = faceSize.width()
                height = faceSize.height()
                painter.translate(self.facePos())
                painter.drawLine(QPointF(0.0, 0.0), QPointF(width, height))
                painter.drawLine(QPointF(width, 0.0), QPointF(0.0, height))
                painter.restore()

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
        renderer.render(painter, self.elementId())
        painter.resetTransform()
        self._drawDarkness(painter)
        if self.showFace():
            faceSize = self.tileset.faceSize.toSize()
            faceSize = QSize(faceSize.width() * xScale, faceSize.height() * yScale)
            painter.translate(self.facePos())
            renderer.render(painter, self.tileset.svgName[self.tile.element.lower()],
                    QRectF(QPointF(), QSizeF(faceSize)))
        return result

    def _drawDarkness(self, painter):
        """if appropriate, make tiles darker. Mainly used for hidden tiles"""
        if self.tile.dark:
            board = self.tile.board
            rect = board.tileFaceRect().adjusted(-1, -1, -1, -1)
            color = QColor('black')
            color.setAlpha(self.tileset.darkenerAlpha)
            painter.fillRect(rect, color)

    def __str__(self):
        """printable string with tile"""
        level = ' level=%d' % self.tile.level if self.tile.level else ''
        scale = ' scale=%.2f' % self.scale() if self.scale() != 1 else ''
        size = self.boundingRect().size()
        return '%s(%s) %d: x/y/z=%.1f(%.1f)/%.1f(%.1f)/%.2f %.2dx%.2d rot%d %s %s' % \
            (self.tile.element,
            self.tile.board.name() if self.tile.board else 'None', id(self) % 10000,
            self.tile.xoffset, self.x(), self.tile.yoffset,
            self.y(), self.zValue(), size.width(), size.height(), self.rotation(), scale, level)

    def __repr__(self):
        """default representation"""
        return 'GraphicsTileItem(%s)' % str(self)

class Tile(QObject):
    """a single tile on the board. This is a QObject because we want to animate it.
    the unit of xoffset is the width of the tile,
    the unit of yoffset is the height of the tile.
    """
    # pylint: disable=R0902
    def __init__(self, element, xoffset = 0.0, yoffset = 0.0, level=0):
        QObject.__init__(self)
        self.graphics = None
        self.__board = None
        self.__xoffset = xoffset
        self.__yoffset = yoffset
        self.__element = element
        self.__dark = False
        self.level = level
        self.activeAnimation = dict() # key is the property name
        self.queuedAnimations = []

    def _get_pos(self):
        """getter for property pos"""
        return self.graphics.pos()

    def _set_pos(self, pos):
        """setter for property pos"""
        self.graphics.setPos(pos)

    pos = pyqtProperty('QPointF', fget=_get_pos, fset=_set_pos)

    def _get_scale(self):
        """getter for property scale"""
        return self.graphics.scale()

    def _set_scale(self, scale):
        """setter for property scale"""
        self.graphics.setScale(scale)

    scale = pyqtProperty(float, fget=_get_scale, fset=_set_scale)

    def _get_rotation(self):
        """getter for property rotation"""
        return self.graphics.rotation()

    def _set_rotation(self, rotation):
        """setter for property rotation"""
        self.graphics.setRotation(rotation)

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
        self.graphics.setDrawingOrder()

    def getValue(self, pName):
        """gets a property value by not returning a QVariant"""
        return {'pos': self.pos, 'rotation': self.rotation, 'scale':self.scale}[pName]

    def setActiveAnimation(self, animation):
        """the tile knows which of its properties are currently animated"""
        self.queuedAnimations = []
        propName = animation.pName()
        assert propName not in self.activeAnimation or not isAlive(self.activeAnimation[propName])
        self.activeAnimation[propName] = animation
        self.graphics.setCacheMode(QGraphicsItem.ItemCoordinateCache)

    def clearActiveAnimation(self, animation):
        """an animation for this tile has ended. Finalize tile in its new position"""
        del self.activeAnimation[animation.pName()]
        self.graphics.setDrawingOrder()
        if not len(self.activeAnimation):
            self.graphics.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
            self.graphics.update()

    @apply
    def focusable():
        """redirect to self.graphics."""
        def fget(self):
            return bool(self.graphics.flags() & QGraphicsItem.ItemIsFocusable)
        def fset(self, value):
            assert self.graphics or value
            if self.graphics:
                if self.element in Debug.focusable:
                    newStr = 'focusable' if value else 'unfocusable'
                    logDebug('%s: %s from %s' % (newStr, self.element, stack('')[-2]))
                self.graphics.setFlag(QGraphicsItem.ItemIsFocusable, value)
        return property(**locals())

    @apply
    def board():
        """get current board of this tile. Readonly."""
        def fget(self):
            # pylint: disable=W0212
            return self.__board
        return property(**locals())

    @apply
    def xoffset():
        """in logical board coordinates"""
        # pylint: disable=W0212
        def fget(self):
            return self.__xoffset
        def fset(self, value):
            if value != self.__xoffset:
                self.__xoffset = value
                if self.__board:
                    self.__board.placeTile(self)
        return property(**locals())

    @apply
    def yoffset():
        """in logical board coordinates"""
        # pylint: disable=W0212
        def fget(self):
            return self.__yoffset
        def fset(self, value):
            if value != self.__yoffset:
                self.__yoffset = value
                if self.__board:
                    self.__board.placeTile(self)
        return property(**locals())

    @apply
    def element():
        """tileName"""
        def fget(self):
            # pylint: disable=W0212
            return self.__element
        def fset(self, value):
            # pylint: disable=W0212
            if value != self.__element:
                self.__element = value
                if self.graphics:
                    self.graphics.setDrawingOrder()
                    self.graphics.update()
        return property(**locals())

    @apply
    def dark():
        """show face?"""
        def fget(self):
            # pylint: disable=W0212
            return self.__dark
        def fset(self, value):
            # pylint: disable=W0212
            if value != self.__dark:
                self.__dark = value
                if self.graphics:
                    self.graphics.update()
        return property(**locals())

    def setBoard(self, board, xoffset=None, yoffset=None, level=None):
        """change Position of tile in board"""
        placeDirty = False
        if self.__board != board:
            oldBoard = self.__board
            self.__board = board
            if oldBoard:
                oldBoard.tiles.remove(self)
            if board:
                if not self.graphics:
                    self.graphics = GraphicsTileItem(self)
                board.tiles.append(self)
            placeDirty = True
        if level is not None and self.level != level:
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

    def lower(self):
        """return element.lower"""
        return self.element.lower()

    def upper(self):
        """return hidden element name"""
        if self.isBonus():
            return self.element
        return self.element.capitalize()

    def __str__(self):
        """printable string with tile"""
        if self.graphics:
            return self.graphics.__str__()
        else:
            return '%s %.2d/%.2d' % (self.element, self.xoffset, self.yoffset)

    def __repr__(self):
        """default representation"""
        return 'Tile(%s)' % str(self)

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
