# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

Kajongg is free software you can redistribute it and/or modify
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

from common import Internal, ZValues, StrMixin
from wind import Wind, East
from qt import QPointF, QGraphicsObject, QFontMetrics
from qt import QPen, QColor, QFont, Qt, QRectF

from guiutil import Painter, sceneRotation
from board import PlayerWind, YellowText, Board
from wall import Wall, KongBox
from tile import Tile
from tileset import Tileset
from uitile import UITile
from animation import animate, afterQueuedAnimations, AnimationSpeed, \
    ParallelAnimationGroup, AnimatedMixin

class SideText(AnimatedMixin, QGraphicsObject, StrMixin):

    """The text written on the wall"""

    sideTexts = list()

    def __init__(self, parent=None):
        assert parent is None
        assert len(self.sideTexts) < 4
        self.__name = 't%d' % len(self.sideTexts)
        self.sideTexts.append(self)
        super(SideText, self).__init__()
        self.hide()
        Internal.scene.addItem(self)
        self.__text = u''
        self.__board = None
        self.needsRefresh = False
        self.__color = Qt.black
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
        with AnimationSpeed(speed=30 if rotating and alreadyMoved else 99):
            # first round: just place the winds. Only animate moving them
            # for later rounds.
            for side in sides:
                side.startAnimations()

    @staticmethod
    def removeAll():
        """from the scene"""
        for side in SideText.sideTexts:
            Internal.scene.removeItem(side)
        SideText.sideTexts = list()

    def moveDict(self):
        """returns a dict with new property values for our sidetext
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

    def name(self):
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

    def setDrawingOrder(self):
        """we want the text above all non moving tiles"""
        if self.activeAnimation.get('pos'):
            movingZ = ZValues.movingZ
        else:
            movingZ = 0
        self.setZValue(ZValues.markerZ + movingZ)

    def paint(self, painter, dummyOption, dummyWidget=None):
        """paint the marker"""
        with Painter(painter):
            pen = QPen(QColor(self.color))
            painter.setPen(pen)
            painter.setFont(self.__font)
            painter.drawText(0, 0, self.__text)

    def boundingRect(self):
        """around the text"""
        return self.__boundingRect or QRectF()

    def __unicode__(self):
        """for debugging"""
        return u'sideText %s %s x/y= %.1f/%1f' % (
            self.name(), self.text, self.x(), self.y())


class UIWallSide(Board, StrMixin):

    """a Board representing a wall of tiles"""
    penColor = 'red'

    def __init__(self, tileset, boardRotation, length):
        Board.__init__(self, length, 1, tileset, boardRotation=boardRotation)
        self.length = length

    @property
    def name(self):
        """name for debug messages"""
        game = Internal.scene.game
        if not game:
            return u'NOGAME'
        for player in game.players:
            if player.front == self:
                return u'UIWallSide %s' % player.name
        return  u'UIWallSide'

    def center(self):
        """returns the center point of the wall in relation to the
        faces of the upper level"""
        faceRect = self.tileFaceRect()
        result = faceRect.topLeft() + self.shiftZ(1) + \
            QPointF(self.length // 2 * faceRect.width(), faceRect.height() / 2)
        result.setX(result.x() + faceRect.height() / 2)  # corner tile
        return result

    def hide(self):
        """hide all my parts"""
        self.windTile.hide()
        Board.hide(self)

    def __unicode__(self):
        """for debugging"""
        return self.name


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
    tileClass = UITile
    kongBoxClass = UIKongBox

    def __init__(self, game):
        """init and position the wall"""
        # we use only white dragons for building the wall. We could actually
        # use any tile because the face is never shown anyway.
        self.initWindMarkers()
        game.wall = self
        Wall.__init__(self, game)
        self.__square = Board(1, 1, Tileset.activeTileset())
        self.__square.setZValue(ZValues.markerZ)
        sideLength = len(self.tiles) // 8
        self.__sides = [UIWallSide(
            Tileset.activeTileset(),
            boardRotation, sideLength) for boardRotation in (0, 270, 180, 90)]
        for idx, side in enumerate(self.__sides):
            side.setParentItem(self.__square)
            side.lightSource = self.lightSource
            side.windTile = Wind.all4[idx].marker
            side.windTile.hide()
            side.message = YellowText(side)
            side.message.setZValue(ZValues.popupZ)
            side.message.setVisible(False)
            side.message.setPos(side.center())
        self.__sides[0].setPos(yWidth=sideLength)
        self.__sides[3].setPos(xHeight=1)
        self.__sides[2].setPos(xHeight=1, xWidth=sideLength, yHeight=1)
        self.__sides[1].setPos(xWidth=sideLength, yWidth=sideLength, yHeight=1)
        Internal.scene.addItem(self.__square)
        Internal.Preferences.addWatch('showShadows', self.showShadowsChanged)

    @staticmethod
    def initWindMarkers():
        """the 4 round wind markers on the player walls"""
        if East.marker is None:
            for wind in Wind.all4:
                wind.marker = PlayerWind(wind)
                Internal.scene.addItem(wind.marker)

    @staticmethod
    def name():
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
            uiTile.tile = Tile.unknown
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
            return animate().addCallback(self.__placeWallTiles)

    def __placeWallTiles(self, dummyResult=None):
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
            assert ParallelAnimationGroup.current is None
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
    def showShadowsChanged(self, deferredResult, dummyOldValue, dummyNewValue): # pylint: disable=unused-argument
        """setting this actually changes the visuals."""
        assert ParallelAnimationGroup.current is None
        self.__resizeHandBoards()

    def __resizeHandBoards(self, dummyResults=None):
        """we are really calling _setRect() too often. But at least it works"""
        for player in self.game.players:
            player.handBoard.computeRect()
        Internal.mainWindow.adjustView()

    def __setDrawingOrder(self, dummyResults=None):
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
        """divides a wall, building a living and and a dead end"""
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

    def decorate(self):
        """show player info on the wall"""
        for player in self.game.players:
            player.decorate()
        SideText.refreshAll()
        animate() # move the wind markers
