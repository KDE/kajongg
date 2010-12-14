# -*- coding: utf-8 -*-

"""
 (C) 2008,2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

from PyQt4.QtCore import Qt, QString, QRectF, QPointF, QSizeF, QSize
from PyQt4.QtGui import QGraphicsRectItem, QGraphicsItem, QPixmap, QPainter
from PyQt4.QtGui import QColor, QPen, QBrush, QStyleOptionGraphicsItem
from PyQt4.QtSvg import QGraphicsSvgItem
from util import logException, isAlive
from common import LIGHTSOURCES, ZValues, InternalParameters, PREF

def chiNext(element, offset):
    """the element name of the following value"""
    color, baseValue = element
    baseValue = int(baseValue)
    return '%s%d' % (color, baseValue+offset)

def offsetTiles(tileName, offsets):
    """returns two adjacent tiles placed at offsets"""
    chow2 = chiNext(tileName, offsets[0])
    chow3 = chiNext(tileName, offsets[1])
    return [chow2, chow3]

def swapTitle(element):
    """if istitle, return lower. If lower, return capitalize"""
    if element.islower():
        return element.capitalize()
    else:
        return element.lower()

class GraphicsTileItem(QGraphicsSvgItem):
    def __init__(self, tile):
        QGraphicsSvgItem.__init__(self)
        self.tile = tile
        self.focusable = True
        self.face = None
        self.__pixmap = None
        self.darkener = None
        self.activeAnimation = dict() # key is the property name
        self.queuedAnimations = []
        # do not call setCacheMode: Default is DeviceCoordinateCache.
        # the alternative ItemCoordinateCache does not make it faster

    def keyPressEvent(self, event):
        """redirect to the board"""
        assert self == self.tile.board.focusTile.graphics
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
        if self.activeAnimation.get('pos'):
            moving = ZValues.moving
        # show rotating and scaling tiles above all others
        if self.activeAnimation.get('scale') or self.activeAnimation.get('rotation'):
            moving += ZValues.boardLevelFactor
        self.setZValue(moving + \
            boardLevel + \
            (self.tile.level+(2 if self.tile.element !='Xy' else 1))*ZValues.itemLevelFactor + \
            self.__lightDistance())

    def boundingRect(self):
        """define the part of the tile we want to see"""
        if not self.showShadows and self.tileset:
            return QRectF(QPointF(), self.tileset.faceSize)
        return QGraphicsSvgItem.boundingRect(self)

    def queuedAnimation(self, propertyName):
        """return the last queued animation for this tile and propertyName"""
        for item in reversed(self.queuedAnimations):
            if item.pName() == propertyName:
                return item

    def getValue(self, pName):
        """gets a property value by not returning a QVariant"""
        return {'pos': self.pos, 'rotation': self.rotation, 'scale':self.scale}[pName]()

    def setFocus(self, reason=Qt.OtherFocusReason):
        """any tile that gets focus should also be focusItem for the scene"""
        assert self.tile.board
        QGraphicsSvgItem.setFocus(self, reason)
        self.scene().setFocusItem(self)

    @property
    def showShadows(self):
        """do we need to show shadows?"""
        return self.tile.board.showShadows if self.tile.board else False

    @apply
    def focusable(): # pylint: disable=E0202
        """hide code"""
        def fget(self):
            return bool(self.flags() & QGraphicsItem.ItemIsFocusable)
        def fset(self, focusable):
            self.setFlag(QGraphicsItem.ItemIsFocusable, focusable)
        return property(**locals())

    @apply
    def dark(): # pylint: disable=E0202
        """darken the tile. Used for concealed tiles and dead wall"""
        def fget(self):
            return self.darkener is not None
        def fset(self, dark):
            # pylint: disable=W0212
            if dark != bool(self.darkener):
                if dark:
                    if self.darkener is None:
                        self.darkener = QGraphicsRectItem()
                        self.darkener.setParentItem(self)
                        self.darkener.setRect(self.tile.board.tileFaceRect())
                        self.darkener.setPen(QPen(Qt.NoPen))
                        color = QColor('black')
                        color.setAlpha(self.tileset.darkenerAlpha)
                        self.darkener.setBrush(QBrush(color))
                else:
                    if self.darkener is not None:
                        self.darkener.hide()
                        self.darkener = None
                if self.tile.board:
                    self.recomputeFace()
        return property(**locals())


    def facePos(self):
        """returns the face position relative to the tile
        depend on tileset, lightSource and shadow"""
        return self.tile.board.tileFacePos()

    @staticmethod
    def animateMe():
        """we do not animate if
             - we are in a tile drag/drop operation
             - the user disabled animation
             - the tile was not yet visible (no tile will ever be at 0,0)
        """
        field = InternalParameters.field
        return bool(field
                    and not field.centralView.dragObject
                    and PREF.animationSpeed < 99)

    def setActiveAnimation(self, animation):
        """the tile knows which of its properties are currently animated"""
        self.queuedAnimations = []
        propName = animation.pName()
        assert propName not in self.activeAnimation or not isAlive(self.activeAnimation[propName])
        self.activeAnimation[propName] = animation

    def recompute(self):
        """recomputes position and visuals of the tile"""
        if self.tile.board:
            if self.activeAnimation:
                # wait until active animation on this tile is finished
                self.activeAnimation.values()[0].group().deferred.addCallback(self.__recompute2)
            else:
                self.__recompute2()

    def __recompute2(self, dummyResult=None):
        """now we know there is no active animation on this tile"""
        if self.tileset:
            self.setSharedRenderer(self.tileset.renderer())
        if self.dark: # we need to regenerate the darkener
            self.dark = False
            self.dark = True
        self.setTileId()
        self.recomputeFace()
        if self.tile.board:
            self.tile.board.placeTile(self.tile)

    def recomputeFace(self):
        """show/hide face as needed. Depends on shadows, lightSource, tileset"""
        game = InternalParameters.field.game
        element = self.tile.element
        if game and game.isScoringGame():
            showFace = element and element != 'Xy' and (self.tile.yoffset or not self.dark)
        else:
            showFace = element and element != 'Xy' and not self.dark
        if showFace:
            if not self.face:
                self.face = QGraphicsSvgItem()
                self.face.setParentItem(self)
                self.face.setElementId(self.tileset.svgName[element.lower()])
                self.face.setZValue(1) # above the darkener
                # this cache mode helps just a little bit but makes ugly tiles for small screens
                # self.face.setCacheMode(QGraphicsItem.ItemCoordinateCache)
            # if we have a left or a top shadow, move face
            # by shadow width
            facePos = self.facePos()
            self.face.setPos(facePos.x(), facePos.y())
            self.face.setSharedRenderer(self.tileset.renderer())
        elif self.face:
            self.face.setParentItem(None)
            self.face = None

    def setTileId(self):
        """sets the SVG element id of the tile"""
        if not self.showShadows:
            tileName = QString("TILE_2")
        else:
            lightSourceIndex = LIGHTSOURCES.index(self.tile.board.rotatedLightSource())
            tileName = QString("TILE_%1").arg(lightSourceIndex%4+1)
        self.setElementId(tileName)

    def pixmapFromSvg(self, pmapSize=None, withBorders=False):
        """returns a pixmap with default size as given in SVG and optional borders/shadows"""
        if withBorders:
            wantSize = self.tileset.tileSize.toSize()
        else:
            wantSize = self.tileset.faceSize.toSize()
        if not pmapSize:
            pmapSize = wantSize
        if self.__pixmap is None or self.__pixmap.size() != pmapSize:
            self.__pixmap = QPixmap(pmapSize)
            self.__pixmap.fill(Qt.transparent)
            painter = QPainter(self.__pixmap)
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
            if self.darkener:
                self.darkener.paint(painter, QStyleOptionGraphicsItem())
            if self.face:
                faceSize = self.tileset.faceSize.toSize()
                faceSize = QSize(faceSize.width() * xScale,  faceSize.height() * yScale)
                painter.translate(self.facePos())
                renderer.render(painter, self.tileset.svgName[self.tile.element.lower()],
                        QRectF(QPointF(), QSizeF(faceSize)))
        return self.__pixmap

    def __str__(self):
        """printable string with tile"""
        level = ' level=%d' % self.tile.level if self.tile.level else ''
        scale = ' scale=%.2f' % self.scale() if self.scale() != 1 else ''
        return '%s(%s) %d: x/y/z=%.1f(%.1f)/%.1f(%.1f)/%.2f rot%d %s %s' % (self.tile.element,
            self.tile.board.name() if self.tile.board else 'None', id(self) % 10000, self.tile.xoffset, self.x(), self.tile.yoffset,
            self.y(), self.zValue(), self.rotation(), scale, level)


class Tile(object):
    """a single tile on the board.
    the unit of xoffset is the width of the tile,
    the unit of yoffset is the height of the tile.
    """
    # pylint: disable=R0902
    # pylint - we need more than 10 attributes
    def __init__(self, element, xoffset = 0.0, yoffset = 0.0, level=0):
        self.graphics = None
        if isinstance(element, Tile):
            assert False
            xoffset, yoffset, level = element.xoffset, element.yoffset, element.level
            element = element.element
        self.__board = None
        self.__xoffset = xoffset
        self.__yoffset = yoffset
        self.__element = element # self.setBoard() will computeFace()
        self.__selected = False
        self.level = level

    @apply
    def focusable(): # pylint: disable=E0202
        def fget(self):
            return self.graphics.focusable
        def fset(self, value):
            self.graphics.focusable = value
        return property(**locals())

    @apply
    def dark(): # pylint: disable=E0202
        def fget(self):
            return self.graphics.dark
        def fset(self, value):
            self.graphics.dark = value
        return property(**locals())

    @apply
    def board(): # pylint: disable=E0202
        """get/assign the tile to a board and define it according to the board parameters.
        This always recomputes the tile position in the board even if we assign to the
        same board - class Board depends on this"""
        def fget(self):
            # pylint: disable=W0212
            return self.__board
        return property(**locals())

    def recompute(self):
        """recomputes position and visuals of the tile"""
        self.graphics.recompute()

    @apply
    def xoffset(): # pylint: disable=E0202
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
    def yoffset(): # pylint: disable=E0202
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
    def element(): # pylint: disable=E0202
        """tileName"""
        def fget(self):
            # pylint: disable=W0212
            return self.__element
        def fset(self, value):
            # pylint: disable=W0212
            if value != self.__element:
                self.__element = value
                if self.graphics:
                    self.graphics.recomputeFace()
                    self.graphics.setDrawingOrder()
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
                self.recompute()
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
        if placeDirty:
            self.__board.placeTile(self)

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

