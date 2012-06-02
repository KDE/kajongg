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

from util import m18nc
from common import InternalParameters, PREF, ZValues
from PyQt4.QtCore import QRectF, QPointF
from PyQt4.QtGui import QGraphicsSimpleTextItem

from board import PlayerWind, YellowText, Board, rotateCenter
from game import Wall
from animation import animate, afterCurrentAnimationDo, Animated, \
    ParallelAnimationGroup

class UIWallSide(Board):
    """a Board representing a wall of tiles"""
    def __init__(self, tileset, boardRotation, length):
        Board.__init__(self, length, 1, tileset, boardRotation=boardRotation)
        self.length = length

    # pylint: disable=R0201
    def name(self):
        """name for debug messages"""
        game = InternalParameters.field.game
        if not game:
            return 'NOGAME'
        for player in game.players:
            if player.front == self:
                return 'wallside %s'% player.name

    def center(self):
        """returns the center point of the wall in relation to the faces of the upper level"""
        faceRect = self.tileFaceRect()
        result = faceRect.topLeft() + self.shiftZ(1) + \
            QPointF(self.length // 2 * faceRect.width(), faceRect.height()/2)
        result.setX(result.x() + faceRect.height()/2) # corner tile
        return result

class UIWall(Wall):
    """represents the wall with four sides. self.wall[] indexes them counter clockwise, 0..3. 0 is bottom."""
    def __init__(self, game):
        """init and position the wall"""
        # we use only white dragons for building the wall. We could actually
        # use any tile because the face is never shown anyway.
        game.wall = self
        Wall.__init__(self, game)
        self.__square = Board(1, 1, InternalParameters.field.tileset)
        self.__square.setZValue(ZValues.marker)
        sideLength = len(self.tiles) // 8
        self.__sides = [UIWallSide(InternalParameters.field.tileset, boardRotation, sideLength) \
            for boardRotation in (0, 270, 180, 90)]
        for side in self.__sides:
            side.setParentItem(self.__square)
            side.lightSource = self.lightSource
            side.windTile = PlayerWind('E', InternalParameters.field.windTileset, parent=side)
            side.windTile.hide()
            side.nameLabel = QGraphicsSimpleTextItem('', side)
            font = side.nameLabel.font()
            font.setPointSize(48)
            side.nameLabel.setFont(font)
            side.message = YellowText(side)
            side.message.setZValue(ZValues.popup)
            side.message.setVisible(False)
            side.message.setPos(side.center())
        self.__sides[0].setPos(yWidth=sideLength)
        self.__sides[3].setPos(xHeight=1)
        self.__sides[2].setPos(xHeight=1, xWidth=sideLength, yHeight=1)
        self.__sides[1].setPos(xWidth=sideLength, yWidth=sideLength, yHeight=1 )
        self.showShadows = PREF.showShadows
        InternalParameters.field.centralScene.addItem(self.__square)

    # pylint: disable=R0201
    def name(self):
        """name for debug messages"""
        return 'wall'

    def __getitem__(self, index):
        """make Wall index-able"""
        return self.__sides[index]

    def hide(self):
        """hide all four walls and their decorators"""
        for side in self.__sides:
            side.windTile.hide()
            side.nameLabel.hide()
            side.hide()
            del side
        InternalParameters.field.centralScene.removeItem(self.__square)

    def __shuffleTiles(self):
        """shuffle tiles for next hand"""
        discardBoard = InternalParameters.field.discardBoard
        places = [(x, y) for x in range(-3, discardBoard.width+3) for y in range(-3, discardBoard.height+3)]
        places = self.game.randomGenerator.sample(places, len(self.tiles))
        for idx, tile in enumerate(self.tiles):
            tile.dark = True
            tile.setBoard(discardBoard, *places[idx])

    def build(self):
        """builds the wall without dividing"""
        # recycle used tiles
        for tile in self.tiles:
            tile.element = 'Xy'
            tile.dark = True
#        field = InternalParameters.field
#        animateBuild = not field.game.isScoringGame() and not self.game.isFirstHand()
        animateBuild = False
        with Animated(animateBuild):
            self.__shuffleTiles()
            for tile in self.tiles:
                tile.focusable = False
            return animate().addCallback(self.__placeWallTiles)

    def __placeWallTiles(self, dummyResult=None):
        """place all wall tiles"""
        tileIter = iter(self.tiles)
        tilesPerSide = len(self.tiles) // 4
        for side in (self.__sides[0], self.__sides[3], self.__sides[2], self.__sides[1]):
            upper = True # upper tile is played first
            for position in range(tilesPerSide-1, -1, -1):
                tile = tileIter.next()
                tile.setBoard(side, position//2, 0, level=int(upper))
                upper = not upper
        self.__setDrawingOrder()
        return animate()

    @apply
    def lightSource():
        """setting this actually changes the visuals. For
        possible values see LIGHTSOURCES"""
        def fget(self):
            # pylint: disable=W0212
            return self.__square.lightSource
        def fset(self, lightSource):
            # pylint: disable=W0212
            if self.lightSource != lightSource:
                assert ParallelAnimationGroup.current is None
                self.__square.lightSource = lightSource
                for side in self.__sides:
                    side.lightSource = lightSource
                self.__setDrawingOrder()
        return property(**locals())

    @apply
    # pylint: disable=E0202
    def tileset():
        """setting this actually changes the visuals."""
        def fget(self):
            # pylint: disable=W0212
            return self.__square.tileset
        def fset(self, value):
            # pylint: disable=W0212
            if self.tileset != value:
                assert ParallelAnimationGroup.current is None
                self.__square.tileset = value
                for side in self.__sides:
                    side.tileset = value
                self.__resizeHandBoards()
        return property(**locals())

    @apply
    # pylint: disable=E0202
    def showShadows():
        """setting this actually changes the visuals."""
        def fget(self):
            # pylint: disable=W0212
            return self.__square.showShadows
        def fset(self, showShadows):
            # pylint: disable=W0212
            if self.showShadows != showShadows:
                assert ParallelAnimationGroup.current is None
                self.__square.showShadows = showShadows
                for side in self.__sides:
                    side.showShadows = showShadows
                self.__resizeHandBoards()
        return property(**locals())

    def __resizeHandBoards(self, dummyResults=None):
        """we are really calling _setRect() too often. But at least it works"""
        for player in self.game.players:
            player.handBoard.computeRect()
        InternalParameters.field.adjustView()

    def __setDrawingOrder(self, dummyResults=None):
        """set drawing order of the wall"""
        levels = {'NW': (2, 3, 1, 0), 'NE':(3, 1, 0, 2), 'SE':(1, 0, 2, 3), 'SW':(0, 2, 3, 1)}
        for idx, side in enumerate(self.__sides):
            side.level = (levels[side.lightSource][idx] + 1) * ZValues.boardLevelFactor

    def _moveDividedTile(self, tile, offset):
        """moves a tile from the divide hole to its new place"""
        board = tile.board
        newOffset = tile.xoffset + offset
        sideLength = len(self.tiles) // 8
        if newOffset >= sideLength:
            sideIdx = self.__sides.index(tile.board)
            board = self.__sides[(sideIdx+1) % 4]
        tile.setBoard(board, newOffset % sideLength, 0, level=2)

    def placeLooseTiles(self):
        """place the last 2 tiles on top of kong box"""
        assert len(self.kongBox) % 2 == 0
        afterCurrentAnimationDo(self.__placeLooseTiles2)

    def __placeLooseTiles2(self, dummyResult):
        """place the last 2 tiles on top of kong box, no animation is active"""
        placeCount = len(self.kongBox) // 2
        if placeCount >= 4:
            first = min(placeCount-1, 5)
            second = max(first-2, 1)
            self._moveDividedTile(self.kongBox[-1], second)
            self._moveDividedTile(self.kongBox[-2], first)

    def divide(self):
        """divides a wall, building a living and and a dead end"""
        with Animated(False):
            Wall.divide(self)
            for tile in self.tiles:
                # update graphics because tiles having been
                # in kongbox in a previous game
                # might not be there anymore. This gets rid
                # of the cross on them.
                tile.graphics.update()
            # move last two tiles onto the dead end:
            return animate().addCallback(self.__placeLooseTiles2)

    def decorate(self):
        """show player info on the wall"""
        for player in self.game.players:
            self.decoratePlayer(player)

    def decoratePlayer(self, player):
        """show player info on the wall"""
        side = player.front
        sideCenter = side.center()
        name = side.nameLabel
        if player.handBoard:
            player.handContent = player.computeHand()
            player.newHandContent = player.computeNewHand()
            name.setText(' - '.join([m18nc('kajongg', player.name), unicode(player.newHandContent.total())]))
        else:
            name.setText(m18nc('kajongg', player.name))
        name.resetTransform()
        if side.rotation() == 180:
            rotateCenter(name, 180)
        nameRect = QRectF()
        nameRect.setSize(name.mapToParent(name.boundingRect()).boundingRect().size())
        name.setPos(sideCenter - nameRect.center())
        player.colorizeName()
        side.windTile.setWind(player.wind, self.game.roundsFinished)
        side.windTile.resetTransform()
        side.windTile.setPos(sideCenter.x()*1.63, sideCenter.y()-side.windTile.rect().height()/2.5)
        side.nameLabel.show()
        side.windTile.show()
