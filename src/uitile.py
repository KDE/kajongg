# -*- coding: utf-8 -*-

"""
 Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

from typing import TYPE_CHECKING, Optional, Dict, Literal, Any

from qt import Qt, QRectF, QPointF, QSizeF, QSize
from qt import QGraphicsObject, QGraphicsItem, QPixmap, QPainter, QColor

from util import stack
from log import logException, logDebug
from guiutil import Painter, sceneRotation
from common import LIGHTSOURCES, ZValues, Internal, Debug
from common import ReprMixin, isAlive, id4
from tile import Tile, Meld
from animation import AnimatedMixin

if TYPE_CHECKING:
    from qt import QKeyEvent, QWidget, QStyleOptionGraphicsItem
    from tileset import Tileset
    from board import Board


class UITile(AnimatedMixin, QGraphicsObject, ReprMixin):

    """A tile visible on the screen. Every tile is only allocated once
    and then reshuffled and reused for every game.
    The unit of xoffset is the width of the tile,
    the unit of yoffset is the height of the tile.
    This is a QObject because we want to animate it."""


    clsUid = 0

    def __init__(self, tile:Tile, xoffset:float=0.0, yoffset:int=0, level:int=0) ->None:
        super().__init__()
        if not isinstance(tile, Tile):
            tile = Tile(tile)
        UITile.clsUid += 1
        self.uid = UITile.clsUid
        self._tile = tile
        self._boundingRect:Optional[QRectF] = None
        self._cross:bool = False
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        # while moving the tile we use ItemCoordinateCache, see
        # Tile.setActiveAnimation
        self.__board:Optional['Board'] = None
        self.setClippingFlags()
        self.__xoffset = xoffset
        self.__yoffset = yoffset
        self.__dark = False
        self.level = level

    def debug_name(self) ->str:
        """identification for animations"""
        return self._tile.name2()

    def setClippingFlags(self) ->None:
        """if we do not show shadows, we need to clip"""
        assert Internal.Preferences
        showShadows = Internal.Preferences.showShadows
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape,
            enabled=not showShadows)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsToShape, enabled=not showShadows)

    def keyPressEvent(self, event:'QKeyEvent') ->None:
        """redirect to the board"""
        _ = self.board
        assert _
        if self is not _.focusTile:
            logDebug(f'keyPressEvent {event} on {self}_{id4(self)} but focus is on {_.focusTile}_{id4(_.focusTile)}')
        _.keyPressEvent(event)

    def __lightDistance(self) ->float:
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
    def tileset(self) ->Optional['Tileset']:
        """the active tileset"""
        return self.board.tileset if self.board else None

    def moveDict(self) ->Dict[Literal['pos', 'rotation', 'scale'], Any]:
        """a dict with attributes for the new position,
        normally pos, rotation and scale"""
        assert self.board
        assert self.tileset
        assert Internal.Preferences
        width = self.tileset.faceSize.width()
        height = self.tileset.faceSize.height()
        shiftZ = self.board.shiftZ(self.level)
        _ = self.yoffset
        if Internal.Preferences.showShadows and self.board.showShadowsBetweenRows:
            _ *= 1.2
        boardPos = QPointF(
            self.xoffset * width,
           _ * height) + shiftZ
        scenePos = self.board.mapToScene(boardPos)
# TODO: rename to 'def get_moveDict, return class MoveDict(TypedDict)
        return {'pos': scenePos, 'rotation': sceneRotation(self.board), 'scale': self.board.scale()}

    def setDrawingOrder(self) ->None:
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

    def boundingRect(self) ->QRectF:
        """define the part of the tile we want to see. Do not return QRect()
        if tileset is not known because that makes QGraphicsscene crash"""
        assert Internal.Preferences
        if self.tileset:
            self._boundingRect = QRectF(
                QPointF(),
                self.tileset.tileSize if Internal.Preferences.showShadows
                else self.tileset.faceSize)
        else:
            # just something. QRectF() gives segfault.
            self._boundingRect = QRectF(0.0, 0.0, 10.0, 10.0)
        return self._boundingRect

    def facePos(self, showShadows:Optional[bool]=None) ->QRectF:
        """return the face position relative to the tile
        depend on tileset, lightSource and shadow"""
        assert Internal.Preferences
        if showShadows is None:
            showShadows = bool(Internal.Preferences.showShadows)
        _ = self.board
        return _.tileFacePos(showShadows)

    def showFace(self) ->bool:
        """should we show face for this tile?"""
        return self.isKnown

    def __elementId(self, showShadows:Optional[bool]=None) ->str:
        """return the SVG element id of the tile"""
        assert Internal.Preferences
        if showShadows is None:
            showShadows = bool(Internal.Preferences.showShadows)
        if not showShadows:
            return "TILE_2"
        _ = self.board
        assert _
        lightSourceIndex = LIGHTSOURCES.index(_.rotatedLightSource())
        return f"TILE_{lightSourceIndex % 4 + 1}"

    def paint(self, painter:QPainter, unusedOption:'QStyleOptionGraphicsItem',
        unusedWidget:Optional['QWidget']=None) ->None:
        """paint the entire tile.
        I tried to cache a pixmap for the tile and darkener but without face,
        but that actually made it slower."""
        assert Internal.Preferences
        assert self.tileset
        with Painter(painter):
            renderer = self.tileset.renderer
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

    def __paintCross(self, painter:QPainter) ->None:
        """paint a cross on the tile"""
        with Painter(painter):
            assert self.tileset
            faceSize = self.tileset.faceSize
            width = faceSize.width()
            height = faceSize.height()
            painter.translate(self.facePos())
            painter.drawLine(QPointF(0.0, 0.0), QPointF(width, height))
            painter.drawLine(QPointF(width, 0.0), QPointF(0.0, height))

    def pixmapFromSvg(self, pmapSize:QRectF, withBorders:Optional[bool]=None) ->QPixmap:
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
                f'painter is not active. Wanted size: {str(pmapSize)}')
        try:
            xScale = float(pmapSize.width()) / originalSize.width()
            yScale = float(pmapSize.height()) / originalSize.height()
        except ZeroDivisionError:
            xScale = 1
            yScale = 1
        # draw the tile too far to the left/upper side such that its shadow is outside of the print region
        if not withBorders:
            painter.scale(*self.tileset.tileFaceRelation())
        renderer = self.tileset.renderer
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

    def _drawDarkness(self, painter:QPainter) ->None:
        """if appropriate, make tiles darker. Mainly used for hidden tiles"""
        if self.dark:
            assert self.tileset
            board = self.board
            assert board
            rect = board.tileFaceRect().adjusted(-1, -1, -1, -1)
            color = QColor('black')
            color.setAlpha(self.tileset.darkenerAlpha)
            painter.fillRect(rect, color)

    def sortKey(self, sortDir:Qt.Key=Qt.Key.Key_Right) ->float:
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

    def setBoard(self, board:Optional['Board'],
        xoffset:Optional[float]=None, yoffset:Optional[int]=None, level:int=0) ->None:
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
    def tile(self) ->Tile:
        """tile"""
        return self._tile

    def change_name(self, value:Tile) ->None:
        """set tile name and update display"""
        if value is not None:
            if self.name2() != value.name2():
                self._tile = value
                self.setDrawingOrder() # because known tiles are above unknown tiles
                self.update()

    @property
    def cross(self) ->bool:
        """cross tiles in kongbox"""
        return self._cross

    @cross.setter
    def cross(self, value:bool) ->None:
        """cross tiles in kongbox"""
        if self._cross == value:
            return
        self._cross = value
        self.update()

    @property
    def dark(self) ->bool:
        """show face?"""
        return self.__dark

    @dark.setter
    def dark(self, value:bool) ->None:
        """toggle and update display"""
        if value != self.__dark:
            self.__dark = value
            self.update()

    @property
    def focusable(self) ->bool:
        """as the name says"""
        return bool(self.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)

    @focusable.setter
    def focusable(self, value:bool) ->None:
        """redirect and generate Debug output"""
        if self.tile.name2() in Debug.focusable:
            newStr = 'focusable' if value else 'unfocusable'
            logDebug(f"{newStr}: {self.tile.name2()} from {stack('')[-2]}")
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, value)

    @property
    def board(self) ->Optional['Board']:
        """get current board of this tile. Readonly."""
        return self.__board

    @property
    def xoffset(self) ->float:
        """in logical board coordinates"""
        return self.__xoffset

    @xoffset.setter
    def xoffset(self, value:float) ->None:
        """in logical board coordinates"""
        if value != self.__xoffset:
            self.__xoffset = value
            if self.__board:
                self.__board.placeTile(self)

    @property
    def yoffset(self) ->int:
        """in logical board coordinates"""
        return self.__yoffset

    @yoffset.setter
    def yoffset(self, value:int) ->None:
        """in logical board coordinates. Update board display."""
        if value != self.__yoffset:
            self.__yoffset = value
            if self.__board:
                self.__board.placeTile(self)

    def __str__(self) ->str:
        """printable string with tile"""
        if not Debug.graphics:
            return (f"{self.__class__.__name__}_{id4(self)}({self.tile.name2()} on "
                    f"{self.board.debug_name() if self.board else 'None'} "
                    f"x/y {self.xoffset:.1f}/{int(self.yoffset)})")
        rotation = f' rot{int(self.rotation)}' if self.rotation else ''
        scale = f' scale={self.scale:.2f}' if self.scale != 1 else ''
        level = f' level={int(self.level)}' if self.level else ''
        _ = self.boundingRect()
        size = f' {int(_.width()):02}x{int(_.height()):02}'
        return (f"{self.__class__.__name__}_{id4(self)}({self.tile.name2()}"
                f" on {self.board.debug_name() if self.board else 'None'} "
                f" x/y/z {self.xoffset:.1f}/{self.x():.1f}/{self.yoffset:.1f} "
                f"{self.zValue():.1f}/{size}){rotation}{scale}{level}")

    @property
    def isBonus(self) ->bool:
        """proxy for tile"""
        return self.tile.isBonus

    @property
    def isKnown(self) ->bool:
        """proxy for tile"""
        return self.tile.isKnown

    @property
    def exposed(self) ->Tile:
        """proxy for tile"""
        return self.tile.exposed

    @property
    def concealed(self) ->Tile:
        """proxy for tile"""
        return self.tile.concealed

    @property
    def isConcealed(self) ->bool:
        """proxy for tile"""
        return self.tile.isConcealed

    @property
    def lowerGroup(self) ->str:
        """proxy for tile"""
        return self.tile.lowerGroup

    @property
    def char(self) ->str:
        """proxy for tile"""
        return self.tile.char

    def name2(self) ->str:
        """proxy for tile"""
        return self.tile.name2()


class UIMeld(list, ReprMixin):

    """represents a visible meld. Can be empty. Many Meld methods will
    raise exceptions if the meld is empty. But we do not care,
    those methods are not supposed to be called on empty melds.
    UIMeld is a list of UITile"""

    __hash__ = None  # type:ignore

    def __init__(self, newContent:Any) ->None:
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
    def meld(self) ->Meld:
        """return a logical meld"""
        return Meld(x.tile for x in self)

    def __str__(self) ->str:
        """shorter than str() of the list"""
        first_tile = self[0]
        return (f'UIMeld_{id4(self)}({self.meld} in {first_tile.board.debug_name()} '
                f'x/y {first_tile.xoffset:.1f}/{int(first_tile.yoffset)})')
