# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""
from typing import List, TYPE_CHECKING, Optional, Literal, Dict, Any, Union, cast, Sequence

from common import Internal, ZValues, ReprMixin, Speeds, DrawOnTopMixin
from wind import Wind, East
from qt import QPointF, QGraphicsObject, QFontMetrics
from qt import QPen, QColor, QFont, QRectF

from guiutil import Painter, sceneRotation
from board import WindDisc, YellowText, Board
from wall import Wall, KongBox
from tile import Tile
from tileset import Tileset
from uitile import UITile
from animation import animate, afterQueuedAnimations, AnimationSpeed
from animation import ParallelAnimationGroup, AnimatedMixin, animateAndDo

if TYPE_CHECKING:
    from twisted.internet.defer import Deferred
    from qt import QGraphicsItem, QPainter, QStyleOptionGraphicsItem, QWidget
    from tile import Piece
    from visible import VisiblePlayingGame
    from scoring import ScoringGame
    from game import Game
    from scene import PlayingScene


class SideText(AnimatedMixin, QGraphicsObject, ReprMixin, DrawOnTopMixin): # type:ignore[misc]

    """The text written on the wall"""

    sideTexts : List['SideText'] = []

    def __init__(self, parent:Optional['QGraphicsItem']=None) ->None:
        assert parent is None
        assert len(self.sideTexts) < 4
        self.__name = f't{len(self.sideTexts)}'
        self.sideTexts.append(self)
        super().__init__()
        self.hide()
        assert Internal.scene
        Internal.scene.addItem(self)
        self.__text = ''
        self.__board:Optional['UIWallSide'] = None
        self.needsRefresh = False
        self.__color = QColor('black')
        self.__boundingRect:Optional[QRectF] = None
        self.__font:QFont = QFont()
        self.animateNextChange = False

    def adaptedFont(self) ->QFont:
        """Font with the correct point size for the wall"""
        result = QFont()
        size = 80
        result.setPointSize(size)
        assert self.__board
        tileHeight = self.__board.tileset.faceSize.height()
        while QFontMetrics(result).ascent() > tileHeight:
            size -= 1
            result.setPointSize(size)
        return result

    @staticmethod
    def refreshAll() ->None:
        """recompute ourself. Always do this for all for sides
        together because if two names change place we want the
        to move simultaneously"""
        sides = SideText.sideTexts
        if all(not x.needsRefresh for x in sides):
            return
        rotating = False
        for side in sides:
            side.show()
            if not side.needsRefresh:
                continue
            side.needsRefresh = False
            assert side.board
            rotating |= sceneRotation(side) != sceneRotation(side.board)

        alreadyMoved = any(x.x() for x in sides)
        speed = 99
        for side in sides:
            if side.animateNextChange:
                speed = Speeds.windDisc if rotating and alreadyMoved else 99
                side.animateNextChange = False
        with AnimationSpeed(speed=speed):
            # first round: just place the winds. Only animate moving them
            # for later rounds.
            for side in sides:
                side.setupAnimations()
        animate()

    @staticmethod
    def removeAll() ->None:
        """from the scene"""
        assert Internal.scene
        for side in SideText.sideTexts:
            Internal.scene.removeItem(side)
        SideText.sideTexts = []

    def moveDict(self) -> Dict[Literal['pos', 'rotation', 'scale'], Any]:
        """return a dict with new property values for our sidetext
        which move it onto us"""
        if not self.board or not self.__text:
            return {}
        rotation = sceneRotation(self.board)
        position = self.board.center()
        textCenter = self.boundingRect().center()
        if rotation == 180:
            rotation = 0
            position += textCenter
        else:
            position -= textCenter
        return {'pos': self.board.mapToScene(position), 'rotation': rotation, 'scale': self.board.scale()}

    def debug_name(self) ->str:
        """for identification in animations"""
        return self.__name

    @property
    def board(self) ->Optional['UIWallSide']:
        """the front we are sitting on"""
        return self.__board

    @board.setter
    def board(self, value:Optional['UIWallSide']) ->None:
        if self.__board != value:
            self.__board = value
            self.__font = self.adaptedFont()
            self.needsRefresh = True

    @property
    def color(self) ->QColor:
        """text color"""
        return self.__color

    @color.setter
    def color(self, value:QColor) ->None:
        if self.__color != value:
            self.__color = value
            self.update()

    @property
    def text(self) ->str:
        """what we are saying"""
        return self.__text

    @text.setter
    def text(self, value:str) ->None:
        if self.__text != value:
            self.__text = value
            self.prepareGeometryChange()
            txt = self.__text
            if ' - ' in txt:
                # this disables animated movement if only the score changes
                txt = txt[:txt.rfind(' - ')] + ' - 55'
            self.__boundingRect = QRectF(QFontMetrics(self.__font).boundingRect(txt))
            self.needsRefresh = True

    def paint(self, painter:'QPainter', unusedOption:'QStyleOptionGraphicsItem',
        unusedWidget:Optional['QWidget']=None) ->None:
        """paint the disc"""
        with Painter(painter):
            pen = QPen(self.color)
            painter.setPen(pen)
            painter.setFont(self.__font)
            painter.drawText(0, 0, self.__text)

    def boundingRect(self) ->QRectF:
        """around the text"""
        return self.__boundingRect or QRectF()

    def __str__(self) ->str:
        """for debugging"""
        return f'SideText({self.debug_name()} {self.text} x/y= {self.x():.1f}/{self.y():1f})'


class UIWallSide(Board, ReprMixin):

    """a Board representing a wall of tiles"""
    penColor = QColor('red')

    def __init__(self, tileset:Tileset, boardRotation:int, length:float):
        Board.__init__(self, length, 1, tileset, boardRotation=boardRotation)
        self.length = length
        self.disc:'WindDisc'
        self.message:YellowText

    def debug_name(self) ->str:
        """name for debug messages"""
        return f'UIWallSide {UIWall.sideNames[int(self.rotation())]}'

    def center(self) ->QPointF:
        """return the center point of the wall in relation to the
        faces of the upper level"""
        faceRect = self.tileFaceRect()
        result = faceRect.topLeft()
        result += self.shiftZ(1)
        result += QPointF(self.length // 2 * faceRect.width(), faceRect.height() / 2)
        result.setX(result.x() + faceRect.height() / 2)  # corner tile
        return result

    def hide(self) ->None:
        """hide all my parts"""
        self.disc.hide()
        Board.hide(self)

    def __str__(self) ->str:
        """for debugging"""
        return self.debug_name()


class UIKongBox(KongBox):

    """Kong box with UITiles"""

    def __init__(self) ->None:
        KongBox.__init__(self)

    def fill(self, tiles:List[Union['Piece', UITile]]) ->None:
        """fill the box"""
        for uiTile in self._tiles:
            cast(UITile, uiTile).cross = False
        KongBox.fill(self, tiles)
        for uiTile in self._tiles:
            cast(UITile, uiTile).cross = True

    def pop(self, count:int) ->List[Union['Piece', UITile]]:
        """get count tiles from kong box"""
        result = KongBox.pop(self, count)
        for uiTile in result:
            cast(UITile, uiTile).cross = False
        return result


class UIWall(Wall):

    """represents the wall with four sides. self.wall[] indexes them
    counter clockwise, 0..3. 0 is bottom."""

    Lower, Right, Upper, Left = range(4)
    sideAngles = (0, 270, 180, 90)
    sideNames = {0:'Lower', 1:'Right', 2:'Upper', 3:'Left'}
    sideNames[270] = 'Right'
    sideNames[180] = 'Upper'
    sideNames[90] = 'Left'

    tileClass = UITile
    kongBoxClass = UIKongBox

    def __init__(self, game:'Game') ->None:
        """init and position the wall"""
        # we use only white dragons for building the wall. We could actually
        # use any tile because the face is never shown anyway.
        self.initWindDiscs()
        game.wall = self
        Wall.__init__(self, game)
        self.tiles:Sequence[UITile] = [cast(UITile, x) for x in self.tiles]  # type:ignore[assignment]
        self.__square = Board(1, 1, Tileset.current())
        self.__square.setZValue(ZValues.markerZ)
        sideLength = len(self.tiles) // 8
        self.__sides = [UIWallSide(
            Tileset.current(),
            boardRotation, sideLength) for boardRotation in self.sideAngles]
        for idx, side in enumerate(self.__sides):
            side.setParentItem(self.__square)
            side.lightSource = self.lightSource
            side.disc = Wind.all4[idx].disc
            side.disc.hide()
            side.message = YellowText(side)
            side.message.setZValue(ZValues.popupZ)
            side.message.setVisible(False)
            side.message.setPos(side.center())
        self.__sides[self.Lower].setTilePos(yWidth=sideLength)
        self.__sides[self.Left].setTilePos(xHeight=1)
        self.__sides[self.Upper].setTilePos(xHeight=1, xWidth=sideLength, yHeight=1)
        self.__sides[self.Right].setTilePos(xWidth=sideLength, yWidth=sideLength, yHeight=1)
        assert Internal.scene
        Internal.scene.addItem(self.__square)
        assert Internal.Preferences
        Internal.Preferences.addWatch('showShadows', self.showShadowsChanged)

    @staticmethod
    def initWindDiscs() ->None:
        """the 4 round wind discs on the player walls"""
        assert Internal.scene
        if not hasattr(East, 'disc'):
            for wind in Wind.all4:
                wind.disc = WindDisc(wind)
                Internal.scene.addItem(wind.disc)

    @staticmethod
    def debug_name() ->str:
        """name for debug messages"""
        return 'wall'

    def __getitem__(self, index:int) ->'UIWallSide':
        """make Wall index-able"""
        return self.__sides[index]

    def __setitem__(self, index:int, value:'UIWallSide') ->None:
        """only for pylint, currently not used"""
        self.__sides[index] = value

    def __delitem__(self, index:int) ->None:
        """only for pylint, currently not used"""
        del self.__sides[index]

    def __len__(self) ->int:
        """only for pylint, currently not used"""
        return len(self.__sides)

    def hide(self) ->None:
        """hide all four walls and their decorators"""
        # may be called twice
        self.living = []
        self.kongBox.fill([])
        for side in self.__sides:
            side.hide()
        self.tiles = []
        if self.__square.scene():
            self.__square.scene().removeItem(self.__square)

    def __shuffleTiles(self) ->None:
        """shuffle tiles for next hand"""
        assert Internal.scene
        discardBoard = cast('PlayingScene', Internal.scene).discardBoard
        places = [(x, y) for x in range(-3, int(discardBoard.width) + 3)
                  for y in range(-3, int(discardBoard.height) + 3)]
        assert self.game
        places = self.game.randomGenerator.sample(places, len(self.tiles))
        for idx, uiTile in enumerate(self.tiles):
            uiTile.dark = True
            uiTile.setBoard(discardBoard, *places[idx])

    def build(self, shuffleFirst:bool=False) ->'Deferred':
        """builds the wall without dividing"""
        # recycle used tiles
        for uiTile in self.tiles:
            uiTile.change_name(Tile.unknown)
            uiTile.dark = True
#        scene = Internal.scene
# if not scene.game.isScoringGame() and not self.game.isFirstHand():
#    speed = Internal.preferences.animationSpeed
# else:
        speed = 99
        with AnimationSpeed(speed=speed):
            if shuffleFirst:
                self.__shuffleTiles()
            for uiTile in self.tiles:
                uiTile.focusable = False
            return animateAndDo(self.__placeWallTiles)

    def __placeWallTiles(self, unusedResult:Any=None) ->'Deferred':
        """place all wall tiles"""
        tileIter = iter(self.tiles)
        tilesPerSide = len(self.tiles) // 4
        for side in (self.__sides[0], self.__sides[3],
                     self.__sides[2], self.__sides[1]):
            upper = True  # upper tile is played first
            for position in range(tilesPerSide - 1, -1, -1):
                uiTile = next(tileIter)
                uiTile.setBoard(side, position // 2, 0, level=int(upper))
                upper = not upper
        self.__setDrawingOrder()
        return animate()

    @property
    def lightSource(self) ->Union[Literal['NE'], Literal['NW'], Literal['SW'], Literal['SE']]:
        """see LIGHTSOURCES"""
        return cast(Union[Literal['NE'], Literal['NW'], Literal['SW'], Literal['SE']], self.__square.lightSource)

    @lightSource.setter
    def lightSource(self, lightSource:Union[Literal['NE'], Literal['NW'], Literal['SW'], Literal['SE']]) ->None:
        """setting this actually changes the visuals"""
        if self.lightSource != lightSource:
#            assert ParallelAnimationGroup.current is None # may trigger, reason unknown
            self.__square.lightSource = lightSource
            for side in self.__sides:
                side.lightSource = lightSource
            self.__setDrawingOrder()
            SideText.refreshAll()

    @property
    def tileset(self) ->Tileset:
        """The tileset of this wall"""
        return self.__square.tileset

    @tileset.setter
    def tileset(self, value:Tileset) ->None:
        """setting this actually changes the visuals."""
        if self.tileset != value:
            assert ParallelAnimationGroup.current is None
            self.__square.tileset = value
            self.__resizeHandBoards()
            SideText.refreshAll()

    @afterQueuedAnimations  # type:ignore[arg-type]
    def showShadowsChanged(self, deferredResult:Any, # pylint: disable=unused-argument
        unusedOldValue:bool, unusedNewValue:bool) ->None:
        """setting this actually changes the visuals."""
        self.__resizeHandBoards()

    def __resizeHandBoards(self, unusedResults:Any=None) ->None:
        """we are really calling _setRect() too often. But at least it works"""
        assert self.game
        for player in self.game.players:
            player.handBoard.computeRect()
        assert Internal.mainWindow
        Internal.mainWindow.adjustMainView()

    def __setDrawingOrder(self, unusedResults:Any=None) ->None:
        """set drawing order of the wall"""
        levels = {'NW': (2, 3, 1, 0), 'NE': (
            3, 1, 0, 2), 'SE': (1, 0, 2, 3), 'SW': (0, 2, 3, 1)}
        for idx, side in enumerate(self.__sides):
            side.level = (
                levels[
                    side.lightSource][
                        idx] + 1) * ZValues.boardZFactor

    def __moveDividedTile(self, uiTile:UITile, offset:float) ->None:
        """moves a uiTile from the divide hole to its new place"""
        board = uiTile.board
        newOffset = uiTile.xoffset + offset
        sideLength = len(self.tiles) // 8
        if newOffset >= sideLength:
            assert board
            sideIdx = self.__sides.index(cast(UIWallSide, board))
            board = self.__sides[(sideIdx + 1) % 4]
        uiTile.setBoard(board, newOffset % sideLength, 0, level=2)
        uiTile.update()

    @afterQueuedAnimations  # type:ignore[arg-type]
    def _placeLooseTiles(self, deferredResult:Any=None) ->None:
        """place the last 2 tiles on top of kong box"""
        assert len(self.kongBox) % 2 == 0
        placeCount = len(self.kongBox) // 2
        if placeCount >= 4:
            first = min(placeCount - 1, 5)
            second = max(first - 2, 1)
            self.__moveDividedTile(cast(UITile, self.kongBox[-1]), second)
            self.__moveDividedTile(cast(UITile, self.kongBox[-2]), first)

    def divide(self) ->None:
        """divides a wall, building a living end and a dead end"""
        with AnimationSpeed():
            Wall.divide(self)
            for uiTile in self.tiles:
                # update graphics because tiles having been
                # in kongbox in a previous game
                # might not be there anymore. This gets rid
                # of the cross on them.
                # FIXME: Piece/UITile
                uiTile.update()  # type:ignore[union_attr]
            # move last two tiles onto the dead end:
            return self._placeLooseTiles()

    def decorate4(self, deferredResult:Any=None) ->None:
        """show player info on the wall. The caller must ensure
        all are moved simultaneously and at which speed by using
        AnimationSpeed.
        already queued animations keep their speed, only the windDiscs
        are moved without animation.
        """
        assert self.game
        with AnimationSpeed(99):
            for player in self.game.players:
                player.showInfo()
            SideText.refreshAll()
        animateAndDo(self.showWindDiscs)

    def showWindDiscs(self, unusedDeferred:Optional['Deferred']=None) ->None:
        """animate all windDiscs. The caller must ensure
        all are moved simultaneously and at which speed
        by using AnimationSpeed."""
        assert self.game
        for player in self.game.players:
            side = player.front
            side.disc.setupAnimations()
            side.disc.show()
