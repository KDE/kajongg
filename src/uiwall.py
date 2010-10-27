# -*- coding: utf-8 -*-

"""
Copyright (C) 2008,2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from util import m18nc
from common import InternalParameters, PREF
from PyQt4.QtCore import Qt, QRectF, QPointF
from PyQt4.QtGui import QColor, QBrush, QFont
from PyQt4.QtGui import QGraphicsSimpleTextItem

from board import PlayerWind, YellowText, Board, rotateCenter
from game import Wall

class UIWallSide(Board):
    """a Board representing a wall of tiles"""
    def __init__(self, tileset, boardRotation, length):
        Board.__init__(self, length, 1, tileset, boardRotation=boardRotation)
        self.length = length

    # pylint: disable=R0201
    def name(self):
        """name for debug messages"""
        return 'wall'

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
        Wall.__init__(self, game)
        self.__square = Board(1, 1, InternalParameters.field.tileset)
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
            font.setWeight(QFont.Bold)
            font.setPointSize(48)
            font.setStyleStrategy(QFont.ForceOutline)
            side.nameLabel.setFont(font)
            side.message = YellowText(side)
            side.message.setVisible(False)
            side.message.setPos(side.center())
            side.message.setZValue(1e30)
        self.__sides[0].setPos(yWidth=sideLength)
        self.__sides[3].setPos(xHeight=1)
        self.__sides[2].setPos(xHeight=1, xWidth=sideLength, yHeight=1)
        self.__sides[1].setPos(xWidth=sideLength, yWidth=sideLength, yHeight=1 )
        self.showShadows = PREF.showShadows
        InternalParameters.field.centralScene.addItem(self.__square)

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

    def build(self):
        """builds the wall without dividing"""
        # recycle used tiles
        for tile in self.tiles:
            tile.element = 'Xy'
            tile.focusable = False
            tile.dark = False
        tileIter = iter(self.tiles)
        tilesPerSide = len(self.tiles) // 4
        for side in (self.__sides[0], self.__sides[3], self.__sides[2], self.__sides[1]):
            upper = True     # upper tile is played first
            for position in range(tilesPerSide-1, -1, -1):
                tileIter.next().setBoard(side, position//2, level=int(upper))
                upper = not upper
        self.setDrawingOrder()

    @apply
    def lightSource():
        """setting this actually changes the visuals. For
        possible values see LIGHTSOURCES"""
        def fget(self):
            # pylint: disable=W0212
            return self.__square.lightSource
        def fset(self, lightSource):
            if self.lightSource != lightSource:
                # pylint: disable=W0212
                self.__square.lightSource = lightSource
                for side in self.__sides:
                    side.lightSource = lightSource
                self.setDrawingOrder()
        return property(**locals())

    @apply
    # pylint: disable=E0202
    def showShadows():
        """setting this actually changes the visuals. For
        possible values see LIGHTSOURCES"""
        def fget(self):
            # pylint: disable=W0212
            return self.__square.showShadows
        def fset(self, showShadows):
            if self.showShadows != showShadows:
                # pylint: disable=W0212
                self.__square.showShadows = showShadows
                for side in self.__sides:
                    side.showShadows = showShadows
                self.setDrawingOrder()
        return property(**locals())

    def setDrawingOrder(self):
        """set drawing order of the wall"""
        levels = {'NW': (2, 3, 1, 0), 'NE':(3, 1, 0, 2), 'SE':(1, 0, 2, 3), 'SW':(0, 2, 3, 1)}
        for idx, side in enumerate(self.__sides):
            side.level = levels[side.lightSource][idx]*1000
        self.__square.setDrawingOrder()

    def _moveDividedTile(self, tile, offset):
        """moves a tile from the divide hole to its new place"""
        board = tile.board
        newOffset = tile.xoffset + offset
        sideLength = len(self.tiles) // 8
        if newOffset >= sideLength:
            sideIdx = self.__sides.index(tile.board)
            board = self.__sides[(sideIdx+1) % 4]
        tile.setBoard(board, newOffset % sideLength, level=2)

    def placeLooseTiles(self):
        """place the last 2 tiles on top of kong box"""
        assert len(self.kongBox) % 2 == 0
        placeCount = len(self.kongBox) // 2
        if placeCount >= 4:
            first = min(placeCount-1, 5)
            second = max(first-2, 1)
            self._moveDividedTile(self.kongBox[-1], second)
            self._moveDividedTile(self.kongBox[-2], first)

    def divide(self):
        """divides a wall, building a living and and a dead end"""
        Wall.divide(self)
        for tile in self.living:
            tile.dark = False
        for tile in self.kongBox:
            tile.dark = True
        # move last two tiles onto the dead end:
        self.placeLooseTiles()

    def decorate(self):
        """show player info on the wall"""
        for player in self.game.players:
            self.decoratePlayer(player)

    def __nameColor(self, player):
        """the color to be used for showing the player name on the wall"""
        if player == self.game.activePlayer and self.game.client:
            return Qt.blue
        if InternalParameters.field.tileset.desktopFileName == 'jade':
            return Qt.white
        return Qt.black

    def decoratePlayer(self, player):
        """show player info on the wall"""
        side = player.front
        sideCenter = side.center()
        name = side.nameLabel
        if  player.handBoard:
            player.handContent = player.computeHandContent()
            name.setText(' - '.join([m18nc('kajongg', player.name), unicode(player.handContent.total())]))
        else:
            name.setText(m18nc('kajongg', player.name))
        name.resetTransform()
        if side.rotation() == 180:
            rotateCenter(name, 180)
        nameRect = QRectF()
        nameRect.setSize(name.mapToParent(name.boundingRect()).boundingRect().size())
        name.setPos(sideCenter  - nameRect.center())
        name.setZValue(99999999999)
        name.setBrush(QBrush(QColor(self.__nameColor(player))))
        side.windTile.setWind(player.wind, self.game.roundsFinished)
        side.windTile.resetTransform()
        side.windTile.setPos(sideCenter.x()*1.63, sideCenter.y()-side.windTile.rect().height()/2.5)
        side.windTile.setZValue(99999999999)
        side.nameLabel.show()
        side.windTile.show()
