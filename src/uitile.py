# -*- coding: utf-8 -*-

"""
 Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

from qt import Qt, QRectF, QPointF, QSizeF, QSize
from qt import QGraphicsObject, QGraphicsItem, QPixmap, QPainter, QColor

from util import stack
from log import logException, logDebug
from guiutil import Painter, sceneRotation
from common import LIGHTSOURCES, ZValues, Internal, Debug
from common import ReprMixin, isAlive, id4
from tile import Tile
from meld import Meld
from animation import AnimatedMixin


class UITile(AnimatedMixin, QGraphicsObject, ReprMixin):

    """A tile visible on the screen. Every tile is only allocated once
    and then reshuffled and reused for every game.
    The unit of xoffset is the width of the tile,
    the unit of yoffset is the height of the tile.
    This is a QObject because we want to animate it."""


    clsUid = 0

    def __init__(self, tile, xoffset=0.0, yoffset=0.0, level=0):
        super().__init__()
        if not isinstance(tile, Tile):
            tile = Tile(tile)
        UITile.clsUid += 1
        self.uid = UITile.clsUid
        self._tile = tile
        self._boundingRect = None
        self._cross = False
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        # while moving the tile we use ItemCoordinateCache, see
        # Tile.setActiveAnimation
        self.__board = None
        self.setClippingFlags()
        self.__xoffset = xoffset
        self.__yoffset = yoffset
        self.__dark = False
        self.level = level

    def debug_name(self):
        """identification for animations"""
        return self._tile.name2()

    def setClippingFlags(self):
        """if we do not show shadows, we need to clip"""
        assert Internal.Preferences
        showShadows = Internal.Preferences.showShadows
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape,
            enabled=not showShadows)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsToShape, enabled=not showShadows)

    def keyPressEvent(self, event):
        """redirect to the board"""
        _ = self.board
        assert _
        if self is not _.focusTile:
            logDebug('keyPressEvent %s on [%s]%s but focus is on [%s]%s' % \
                (event, id4(self), self, id4(_.focusTile), _.focusTile))
        _.keyPressEvent(event)

    def __lightDistance(self):
        """the distance of item from the light source"""
        board = self.board
        if not board:
            return 0.0
        rect = self.sceneBoundingRect()
        lightSource = board.lightSource
        result = 0.0
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

    def moveDict(self):
        """a dict with attributes for the new position,
        normally pos, rotation and scale"""
        assert self.board
        assert self.tileset
        width = self.tileset.faceSize.width()
        height = self.tileset.faceSize.height()
        shiftZ = self.board.shiftZ(self.level)
        boardPos = QPointF(
            self.xoffset * width,
            self.yoffset * height) + shiftZ
        scenePos = self.board.mapToScene(boardPos)
        return {'pos': scenePos, 'rotation': sceneRotation(self.board), 'scale': self.board.scale()}

    def setDrawingOrder(self):
        """set drawing order for this tile"""
        if not isAlive(self):
            return
        if self.board:
            boardLevel = self.board.level
        else:
            boardLevel = ZValues.boardZFactor
        movingZ = 0
        # show moving tiles above non-moving tiles
        changePos = self.activeAnimation.get('pos')
        if changePos and not isAlive(changePos):
            return
        changeRotation = self.activeAnimation.get('rotation')
        if changeRotation and not isAlive(changeRotation):
            return
        changeScale = self.activeAnimation.get('scale')
        if changeScale and not isAlive(changeScale):
            return
        # show rotating and scaling tiles above all others
        if changeScale or changeRotation:
            movingZ += ZValues.movingZ
            movingZ += ZValues.boardZFactor
        elif changePos:
            if self.rotation % 180 == 0:
                currentY = self.y()
                newY = changePos.endValue().y()
            else:
                currentY = self.x()
                newY = changePos.endValue().x()
            if currentY != newY:
                movingZ += ZValues.movingZ
        self.setZValue(movingZ +
                       boardLevel +
                       (self.level + (2 if self.isKnown else 1))
                       * ZValues.itemZFactor +
                       self.__lightDistance())

    def boundingRect(self):
        """define the part of the tile we want to see. Do not return QRect()
        if tileset is not known because that makes QGraphicsscene crash"""
        assert Internal.Preferences
        if self.tileset:
            self._boundingRect = QRectF(
                QPointF(),
                self.tileset.tileSize if Internal.Preferences.showShadows
                else self.tileset.faceSize)
        else:
            # just something. QRectF() gives segfault. FIXME: Still true?
            self._boundingRect = QRectF(0.0, 0.0, 10.0, 10.0)
        return self._boundingRect

    def facePos(self, showShadows=None):
        """return the face position relative to the tile
        depend on tileset, lightSource and shadow"""
        assert Internal.Preferences
        if showShadows is None:
            showShadows = bool(Internal.Preferences.showShadows)
        _ = self.board
        return _.tileFacePos(showShadows)

    def showFace(self):
        """should we show face for this tile?"""
        return self.isKnown

    def __elementId(self, showShadows=None):
        """return the SVG element id of the tile"""
        assert Internal.Preferences
        if showShadows is None:
            showShadows = bool(Internal.Preferences.showShadows)
        if not showShadows:
            return "TILE_2"
        _ = self.board
        assert _
        lightSourceIndex = LIGHTSOURCES.index(_.rotatedLightSource())
        return "TILE_{}".format(lightSourceIndex % 4 + 1)

    def paint(self, painter, unusedOption, unusedWidget=None):
        """paint the entire tile.
        I tried to cache a pixmap for the tile and darkener but without face,
        but that actually made it slower."""
        assert Internal.Preferences
        assert self.tileset
        with Painter(painter):
            renderer = self.tileset.renderer()
            withBorders = Internal.Preferences.showShadows
            if not withBorders:
                painter.scale(*self.tileset.tileFaceRelation())
            renderer.render(painter, self.__elementId(), self.boundingRect())
            self._drawDarkness(painter)
        with Painter(painter):
            if self.showFace():
                if withBorders:
                    faceSize = self.tileset.faceSize.toSize()
                    renderer.render(
                        painter, self.tileset.svgName[str(self.exposed)],
                        QRectF(self.facePos(), QSizeF(faceSize)))
                else:
                    renderer.render(
                        painter, self.tileset.svgName[str(self.exposed)],
                        self.boundingRect())
        if self.cross:
            self.__paintCross(painter)

    def __paintCross(self, painter):
        """paint a cross on the tile"""
        with Painter(painter):
            assert self.tileset
            faceSize = self.tileset.faceSize
            width = faceSize.width()
            height = faceSize.height()
            painter.translate(self.facePos())
            painter.drawLine(QPointF(0.0, 0.0), QPointF(width, height))
            painter.drawLine(QPointF(width, 0.0), QPointF(0.0, height))

    def pixmapFromSvg(self, pmapSize, withBorders=None):
        """return a pixmap with default size as given in SVG
        and optional borders/shadows"""
        assert Internal.Preferences
        assert self.tileset
        if withBorders is None:
            withBorders = bool(Internal.Preferences.showShadows)
        if withBorders:
            originalSize = self.tileset.tileSize.toSize()
        else:
            originalSize = self.tileset.faceSize.toSize()
        result = QPixmap(pmapSize)
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        if not painter.isActive():
            logException(
                'painter is not active. Wanted size: %s' %
                str(pmapSize))
        try:
            xScale = float(pmapSize.width()) / originalSize.width()
            yScale = float(pmapSize.height()) / originalSize.height()
        except ZeroDivisionError:
            xScale = 1
            yScale = 1
        # draw the tile too far to the left/upper side such that its shadow is outside of the print region
        if not withBorders:
            painter.scale(*self.tileset.tileFaceRelation())
        renderer = self.tileset.renderer()
        renderer.render(painter, self.__elementId(showShadows=withBorders))
        painter.resetTransform()
        self._drawDarkness(painter)
        if self.showFace():
            faceSize = self.tileset.faceSize.toSize()
            faceSize = QSize(
                int(faceSize.width() * xScale),
                int(faceSize.height() * yScale))
            painter.resetTransform()
            painter.translate(self.facePos(withBorders))
            renderer.render(painter, self.tileset.svgName[self.exposed.name2()],
                            QRectF(QPointF(), QSizeF(faceSize)))
        return result

    def _drawDarkness(self, painter):
        """if appropriate, make tiles darker. Mainly used for hidden tiles"""
        if self.dark:
            assert self.tileset
            board = self.board
            assert board
            rect = board.tileFaceRect().adjusted(-1, -1, -1, -1)
            color = QColor('black')
            color.setAlpha(self.tileset.darkenerAlpha)
            painter.fillRect(rect, color)

    def sortKey(self, sortDir=Qt.Key.Key_Right):
        """moving order for cursor"""
        dirs = [Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Left, Qt.Key.Key_Down] * 2
        assert self.__board
        sorter = dirs[dirs.index(sortDir) + sceneRotation(self.__board) // 90]
        if sorter == Qt.Key.Key_Down:
            return self.xoffset * 100 + self.yoffset
        if sorter == Qt.Key.Key_Up:
            return -(self.xoffset * 100 + self.yoffset)
        if sorter == Qt.Key.Key_Left:
            return -(self.yoffset * 100 + self.xoffset)
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
            if board.scene() and not self.scene():
                board.scene().addItem(self)
            board.placeTile(self)

    @property
    def tile(self):
        """tile"""
        return self._tile

    def change_name(self, value):
        """set tile name and update display"""
        if value is not None:
            if self.name2() != value.name2():
                self._tile = value
                self.setDrawingOrder() # because known tiles are above unknown tiles
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

    @property
    def focusable(self):
        """as the name says"""
        return bool(self.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)

    @focusable.setter
    def focusable(self, value):
        """redirect and generate Debug output"""
        if self.tile.name2() in Debug.focusable:
            newStr = 'focusable' if value else 'unfocusable'
            logDebug('%s: %s from %s' % (newStr, self.tile.name2(), stack('')[-2]))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, value)

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
        _ = self.boundingRect()
        size = ' %.2dx%.2d' % (_.width(), _.height())
        return '%s(%s) %s: x/y/z=%.1f(%.1f)/%.1f(%.1f)/%.2f%s%s%s%s' % \
            (self.tile.name2(),
             self.board.debug_name() if self.board else 'None', id4(self),
             self.xoffset, self.x(), self.yoffset,
             self.y(), self.zValue(), size, rotation, scale, level)

    @property
    def isBonus(self):
        """proxy for tile"""
        return self.tile.isBonus

    @property
    def isKnown(self):
        """proxy for tile"""
        return self.tile.isKnown

    @property
    def exposed(self):
        """proxy for tile"""
        return self.tile.exposed

    @property
    def concealed(self):
        """proxy for tile"""
        return self.tile.concealed

    @property
    def isConcealed(self):
        """proxy for tile"""
        return self.tile.isConcealed

    @property
    def lowerGroup(self):
        """proxy for tile"""
        return self.tile.lowerGroup

    @property
    def char(self):
        """proxy for tile"""
        return self.tile.char

    def name2(self):
        """proxy for tile"""
        return self.tile.name2()


class UIMeld(list):

    """represents a visible meld. Can be empty. Many Meld methods will
    raise exceptions if the meld is empty. But we do not care,
    those methods are not supposed to be called on empty melds.
    UIMeld is a list of UITile"""

    __hash__ = None

    def __init__(self, newContent):
        list.__init__(self)
        if (
                isinstance(newContent, list)
                and newContent
                and isinstance(newContent[0], UITile)):
            self.extend(newContent)
        elif isinstance(newContent, UITile):
            self.append(newContent)
        assert self, newContent

    @property
    def meld(self):
        """return a logical meld"""
        return Meld(x.tile for x in self)
