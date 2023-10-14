# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

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


class SideText(AnimatedMixin, QGraphicsObject, ReprMixin, DrawOnTopMixin):

    """The text written on the wall"""

    sideTexts = []

    def __init__(self, parent=None):
        assert parent is None
        assert len(self.sideTexts) < 4
        self.__name = 't%d' % len(self.sideTexts)
        self.sideTexts.append(self)
        super().__init__()
        self.hide()
        Internal.scene.addItem(self)
        self.__text = ''
        self.__board = None
        self.needsRefresh = False
        self.__color = QColor('black')
        self.__boundingRect = None
        self.__font = None

    def adaptedFont(self):
        """Font with the correct point size for the wall"""
        result = QFont()
        size = 80
        result.setPointSize(size)
        tileHeight = self.board.tileset.faceSize.height()
        while QFontMetrics(result).ascent() > tileHeight:
            size -= 1
            result.setPointSize(size)
        return result

    @staticmethod
    def refreshAll():
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
            rotating |= sceneRotation(side) != sceneRotation(side.board)

        alreadyMoved = any(x.x() for x in sides)
        with AnimationSpeed(speed=Speeds.windDisc if rotating and alreadyMoved else 99):
            # first round: just place the winds. Only animate moving them
            # for later rounds.
            for side in sides:
                side.setupAnimations()
        animate()

    @staticmethod
    def removeAll():
        """from the scene"""
        for side in SideText.sideTexts:
            Internal.scene.removeItem(side)
        SideText.sideTexts = []

    def moveDict(self):
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

    def debug_name(self):
        """for identification in animations"""
        return self.__name

    @property
    def board(self):
        """the front we are sitting on"""
        return self.__board

    @board.setter
    def board(self, value):
        if self.__board != value:
            self.__board = value
            self.__font = self.adaptedFont()
            self.needsRefresh = True

    @property
    def color(self):
        """text color"""
        return self.__color

    @color.setter
    def color(self, value):
        if self.__color != value:
            self.__color = value
            self.update()

    @property
    def text(self):
        """what we are saying"""
        return self.__text

    @text.setter
    def text(self, value):
        if self.__text != value:
            self.__text = value
            self.prepareGeometryChange()
            txt = self.__text
            if ' - ' in txt:
                # this disables animated movement if only the score changes
                txt = txt[:txt.rfind(' - ')] + ' - 55'
            self.__boundingRect = QRectF(QFontMetrics(self.__font).boundingRect(txt))
            self.needsRefresh = True

    def paint(self, painter, unusedOption, unusedWidget=None):
        """paint the disc"""
        with Painter(painter):
            pen = QPen(self.color)
            painter.setPen(pen)
            painter.setFont(self.__font)
            painter.drawText(0, 0, self.__text)

    def boundingRect(self):
        """around the text"""
        return self.__boundingRect or QRectF()

    def __str__(self):
        """for debugging"""
        return 'SideText(%s %s x/y= %.1f/%1f)' % (
            self.debug_name(), self.text, self.x(), self.y())


class UIWallSide(Board, ReprMixin):

    """a Board representing a wall of tiles"""
    penColor = QColor('red')

    def __init__(self, tileset, boardRotation, length):
        Board.__init__(self, length, 1, tileset, boardRotation=boardRotation)
        self.length = length

    def debug_name(self):
        """name for debug messages"""
        return 'UIWallSide {}'.format(UIWall.sideNames[self.rotation()])

    def center(self):
        """return the center point of the wall in relation to the
        faces of the upper level"""
        faceRect = self.tileFaceRect()
        result = faceRect.topLeft() + self.shiftZ(1) + \
            QPointF(self.length // 2 * faceRect.width(), faceRect.height() / 2)
        result.setX(result.x() + faceRect.height() / 2)  # corner tile
        return result

    def hide(self):
        """hide all my parts"""
        self.disc.hide()
        Board.hide(self)

    def __str__(self):
        """for debugging"""
        return self.debug_name()


class UIKongBox(KongBox):

    """Kong box with UITiles"""

    def __init__(self):
        KongBox.__init__(self)

    def fill(self, tiles):
        """fill the box"""
        for uiTile in self._tiles:
            uiTile.cross = False
        KongBox.fill(self, tiles)
        for uiTile in self._tiles:
            uiTile.cross = True

    def pop(self, count):
        """get count tiles from kong box"""
        result = KongBox.pop(self, count)
        for uiTile in result:
            uiTile.cross = False
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

    def __init__(self, game):
        """init and position the wall"""
        # we use only white dragons for building the wall. We could actually
        # use any tile because the face is never shown anyway.
        self.initWindDiscs()
        game.wall = self
        Wall.__init__(self, game)
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
        Internal.scene.addItem(self.__square)
        Internal.Preferences.addWatch('showShadows', self.showShadowsChanged)

    @staticmethod
    def initWindDiscs():
        """the 4 round wind discs on the player walls"""
        if not hasattr(East, 'disc'):
            for wind in Wind.all4:
                wind.disc = WindDisc(wind)
                Internal.scene.addItem(wind.disc)

    @staticmethod
    def debug_name():
        """name for debug messages"""
        return 'wall'

    def __getitem__(self, index):
        """make Wall index-able"""
        return self.__sides[index]

    def __setitem__(self, index, value):
        """only for pylint, currently not used"""
        self.__sides[index] = value

    def __delitem__(self, index):
        """only for pylint, currently not used"""
        del self.__sides[index]

    def __len__(self):
        """only for pylint, currently not used"""
        return len(self.__sides)

    def hide(self):
        """hide all four walls and their decorators"""
        # may be called twice
        self.living = []
        self.kongBox.fill([])
        for side in self.__sides:
            side.hide()
        self.tiles = []
        if self.__square.scene():
            self.__square.scene().removeItem(self.__square)

    def __shuffleTiles(self):
        """shuffle tiles for next hand"""
        discardBoard = Internal.scene.discardBoard
        places = [(x, y) for x in range(-3, discardBoard.width + 3)
                  for y in range(-3, discardBoard.height + 3)]
        places = self.game.randomGenerator.sample(places, len(self.tiles))
        for idx, uiTile in enumerate(self.tiles):
            uiTile.dark = True
            uiTile.setBoard(discardBoard, *places[idx])

    def build(self, shuffleFirst=False):
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

    def __placeWallTiles(self, unusedResult=None):
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
    def lightSource(self):
        """For possible values see LIGHTSOURCES"""
        return self.__square.lightSource

    @lightSource.setter
    def lightSource(self, lightSource):
        """setting this actually changes the visuals"""
        if self.lightSource != lightSource:
#            assert ParallelAnimationGroup.current is None # may trigger, reason unknown
            self.__square.lightSource = lightSource
            for side in self.__sides:
                side.lightSource = lightSource
            self.__setDrawingOrder()
            SideText.refreshAll()

    @property
    def tileset(self):
        """The tileset of this wall"""
        return self.__square.tileset

    @tileset.setter
    def tileset(self, value):
        """setting this actually changes the visuals."""
        if self.tileset != value:
            assert ParallelAnimationGroup.current is None
            self.__square.tileset = value
            self.__resizeHandBoards()
            SideText.refreshAll()

    @afterQueuedAnimations
    def showShadowsChanged(self, deferredResult, unusedOldValue, unusedNewValue): # pylint: disable=unused-argument
        """setting this actually changes the visuals."""
        assert ParallelAnimationGroup.current is None
        self.__resizeHandBoards()

    def __resizeHandBoards(self, unusedResults=None):
        """we are really calling _setRect() too often. But at least it works"""
        for player in self.game.players:
            player.handBoard.computeRect()
        Internal.mainWindow.adjustMainView()

    def __setDrawingOrder(self, unusedResults=None):
        """set drawing order of the wall"""
        levels = {'NW': (2, 3, 1, 0), 'NE': (
            3, 1, 0, 2), 'SE': (1, 0, 2, 3), 'SW': (0, 2, 3, 1)}
        for idx, side in enumerate(self.__sides):
            side.level = (
                levels[
                    side.lightSource][
                        idx] + 1) * ZValues.boardZFactor

    def __moveDividedTile(self, uiTile, offset):
        """moves a uiTile from the divide hole to its new place"""
        board = uiTile.board
        newOffset = uiTile.xoffset + offset
        sideLength = len(self.tiles) // 8
        if newOffset >= sideLength:
            sideIdx = self.__sides.index(uiTile.board)
            board = self.__sides[(sideIdx + 1) % 4]
        uiTile.setBoard(board, newOffset % sideLength, 0, level=2)
        uiTile.update()

    @afterQueuedAnimations
    def _placeLooseTiles(self, deferredResult=None):
        """place the last 2 tiles on top of kong box"""
        assert len(self.kongBox) % 2 == 0
        placeCount = len(self.kongBox) // 2
        if placeCount >= 4:
            first = min(placeCount - 1, 5)
            second = max(first - 2, 1)
            self.__moveDividedTile(self.kongBox[-1], second)
            self.__moveDividedTile(self.kongBox[-2], first)

    def divide(self):
        """divides a wall, building a living end and a dead end"""
        with AnimationSpeed():
            Wall.divide(self)
            for uiTile in self.tiles:
                # update graphics because tiles having been
                # in kongbox in a previous game
                # might not be there anymore. This gets rid
                # of the cross on them.
                uiTile.update()
            # move last two tiles onto the dead end:
            return self._placeLooseTiles()

    def decorate4(self, deferredResult=None):
        """show player info on the wall. The caller must ensure
        all are moved simultaneously and at which speed by using
        AnimationSpeed.
        already queued animations keep their speed, only the windDiscs
        are moved without animation.
        """
        with AnimationSpeed():
            for player in self.game.players:
                player.showInfo()
            SideText.refreshAll()
        animateAndDo(self.showWindDiscs)

    def showWindDiscs(self, unusedDeferred=None):
        """animate all windDiscs. The caller must ensure
        all are moved simultaneously and at which speed
        by using AnimationSpeed."""
        for player in self.game.players:
            side = player.front
            side.disc.setupAnimations()
            side.disc.show()
