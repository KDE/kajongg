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

from PyQt4.QtCore import Qt, QPointF, QPoint, QRectF, QMimeData, QSize
from PyQt4.QtGui import QGraphicsRectItem, QGraphicsItem, QSizePolicy, QFrame, QFont
from PyQt4.QtGui import QGraphicsView, QGraphicsEllipseItem, QGraphicsScene, QLabel
from PyQt4.QtGui import QColor, QPainter, QDrag, QPixmap, QStyleOptionGraphicsItem, QPen, QBrush
from PyQt4.QtGui import QFontMetrics, QTransform
from PyQt4.QtSvg import QGraphicsSvgItem
from tileset import Tileset, TileException
from tile import chiNext
from uitile import UITile, GraphicsTileItem
from meld import Meld
from animation import Animation, Animated, animate
from message import Message

from util import logDebug, logException, m18nc, kprint, stack, uniqueList
from common import elements, WINDS, LIGHTSOURCES, Internal, ZValues, Debug, Preferences, isAlive

ROUNDWINDCOLOR = QColor(235, 235, 173)

WINDPIXMAPS = {}

def rotateCenter(item, angle):
    """rotates a QGraphicsItem around its center"""
    center = item.boundingRect().center()
    centerX, centerY = center.x() * item.scale(), center.y() * item.scale()
    item.setTransform(QTransform().translate(
        centerX, centerY).rotate(angle).translate(-centerX, -centerY))
    return item

class PlayerWind(QGraphicsEllipseItem):
    """a round wind tile"""
    def __init__(self, name, tileset, roundsFinished=0, parent = None):
        """generate new wind tile"""
        if not len(WINDPIXMAPS):
            WINDPIXMAPS[('E', False)] = None # avoid recursion
            self.genWINDPIXMAPS()
        QGraphicsEllipseItem.__init__(self)
        if parent:
            self.setParentItem(parent)
        self.name = name
        self.face = QGraphicsSvgItem()
        self.face.setParentItem(self)
        self.prevailing = None
        self.setWind(name, roundsFinished)
        self.tileset = tileset
        self.__sizeFace()

    @staticmethod
    def genWINDPIXMAPS():
        """prepare wind tiles"""
        tileset = Tileset(Preferences.windTilesetName)
        for wind in WINDS:
            for prevailing in False, True:
                pwind = PlayerWind(wind, tileset, prevailing)
                pMap = QPixmap(40, 40)
                pMap.fill(Qt.transparent)
                painter = QPainter(pMap)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.scale(0.40, 0.40)
                pwind.paint(painter, QStyleOptionGraphicsItem())
                for child in pwind.childItems():
                    if isinstance(child, QGraphicsSvgItem):
                        painter.save()
                        painter.translate(child.mapToParent(0.0, 0.0))
                        child.paint(painter, QStyleOptionGraphicsItem())
                        painter.restore()
                WINDPIXMAPS[(wind, prevailing)] = pMap

    def __sizeFace(self):
        """size the chinese character depending on the wind tileset"""
        self.resetTransform()
        size = self.tileset.faceSize
        self.setFlag(QGraphicsItem.ItemClipsChildrenToShape)
        diameter = size.height() * 1.1
        scaleFactor = 0.9
        facePos = {'traditional':(10, 10), 'default':(15, 10),
                   'classic':(19, 1), 'jade':(19, 1)}
        self.setRect(0, 0, diameter, diameter)
        self.setScale(scaleFactor)
        faceX, faceY = facePos[self.tileset.desktopFileName]
        self.face.setPos(faceX, faceY)
        self.face.setSharedRenderer(self.tileset.renderer())

    def setWind(self, name, roundsFinished):
        """change the wind"""
        self.name = name
        if isinstance(roundsFinished, bool):
            self.prevailing = roundsFinished
        else:
            self.prevailing = name == WINDS[roundsFinished % 4]
        self.setBrush(ROUNDWINDCOLOR if self.prevailing else QColor('white'))
        windtilenr = {'N':1, 'S':2, 'E':3, 'W':4}
        self.face.setElementId('WIND_%d' % windtilenr[name])

class WindLabel(QLabel):
    """QLabel holding the wind tile"""

    @property
    def wind(self):
        """the current wind on this label"""
        return self.__wind

    @wind.setter
    def wind(self, wind):
        """setting the wind also changes the pixmap"""
        if self.__wind != wind:
            self.__wind = wind
            self._refresh()

    def __init__(self, wind = None, roundsFinished = 0, parent=None):
        QLabel.__init__(self, parent)
        self.__wind = None
        if wind is None:
            wind = 'E'
        self.__roundsFinished = roundsFinished
        self.wind = wind

    @property
    def roundsFinished(self):
        """setting roundsFinished also changes pixmaps if needed"""
        return self.__roundsFinished

    @roundsFinished.setter
    def roundsFinished(self, roundsFinished):
        """setting roundsFinished also changes pixmaps if needed"""
        if self.__roundsFinished != roundsFinished:
            self.__roundsFinished = roundsFinished
            self._refresh()

    def _refresh(self):
        """update pixmaps"""
        PlayerWind.genWINDPIXMAPS()
        self.setPixmap(WINDPIXMAPS[(self.__wind,
            self.__wind == WINDS[min(self.__roundsFinished, 3)])])

class Board(QGraphicsRectItem):
    """ a board with any number of positioned tiles"""
    # pylint: disable=R0902
    # pylint we need more than 10 instance attributes

    arrows = [Qt.Key_Left, Qt.Key_Down, Qt.Key_Up, Qt.Key_Right]
    def __init__(self, width, height, tileset, boardRotation=0):
        QGraphicsRectItem.__init__(self)
        self.tiles = []
        self.isHandBoard = False
        self._focusTile = None
        self._noPen()
        self.tileDragEnabled = False
        self.setRotation(boardRotation)
        self._lightSource = 'NW'
        self.xWidth = 0
        self.xHeight = 0
        self.yWidth = 0
        self.yHeight = 0
        self.__fixedWidth = width
        self.__fixedHeight = height
        self._tileset = None
        self._showShadows = None
        self.tileset = tileset
        self.level = 0

    # pylint: disable=R0201
    def name(self):
        """default board name, used for debugging messages"""
        return 'board'

    def hide(self):
        """remove all tile references so they can be garbage collected"""
        for tile in self.tiles:
            tile.hide()
        self.tiles = []
        self._focusTile = None
        if isAlive(self):
            QGraphicsRectItem.hide(self)

    def autoSelectTile(self):
        """call this when kajongg should automatically focus
        on an appropriate tile"""
        focusableTiles = self._focusableTiles()
        if len(focusableTiles):
            return focusableTiles[0]

    @property
    def focusTile(self):
        """the tile of this board with focus. This is per Board!"""
        if self._focusTile is None:
            self._focusTile = self.autoSelectTile()
        return self._focusTile

    @focusTile.setter
    def focusTile(self, tile):
        """the tile of this board with focus. This is per Board!"""
        prevTile = self._focusTile
        if tile:
            assert tile.element != 'Xy', tile
            if not isinstance(tile.board, DiscardBoard):
                assert tile.focusable, tile
            self._focusTile = tile
        else:
            self._focusTile = self.autoSelectTile()
        if self._focusTile and self._focusTile.element in Debug.focusable:
            logDebug('new focus tile %s from %s' % (self._focusTile.element, stack('')[-1]))
        if (self._focusTile != prevTile
            and self.isHandBoard and self.player
            and not self.player.game.isScoringGame()
            and Internal.field.clientDialog):
            Internal.field.clientDialog.focusTileChanged()
        if self.hasFocus:
            self.scene().focusBoard = self

    def setEnabled(self, enabled):
        """enable/disable this board"""
        self.tileDragEnabled = enabled
        QGraphicsRectItem.setEnabled(self, enabled)

    def _focusableTiles(self, sortDir=Qt.Key_Right):
        """returns a list of all tiles in this board sorted such that
        moving in the sortDir direction corresponds to going to
        the next list element.
        respect board orientation: Right Arrow should always move right
        relative to the screen, not relative to the board"""
        dirs = [Qt.Key_Right, Qt.Key_Down, Qt.Key_Left, Qt.Key_Up] * 2
        sorter = dirs[dirs.index(sortDir) + self.sceneRotation()//90]
        if sorter == Qt.Key_Down:
            sortFunction = lambda x: x.xoffset * 100 + x.yoffset
        elif sorter == Qt.Key_Up:
            sortFunction = lambda x: -x.xoffset * 100 - x.yoffset
        elif sorter == Qt.Key_Left:
            sortFunction = lambda x: -x.yoffset * 100 - x.xoffset
        else:
            sortFunction = lambda x: x.yoffset * 100 + x.xoffset
        return sorted([x for x in self.tiles if x.focusable], key=sortFunction)

    @property
    def hasFocus(self):
        """defines if this board should show a focusRect
        if another board has focus, setting this to False does
        not change scene.focusBoard"""
        return self.scene() and self.scene().focusBoard == self

    @hasFocus.setter
    def hasFocus(self, value):
        """sets focus on this board"""
        if isAlive(self):
            scene = self.scene()
            if scene.focusBoard == self or value:
                scene.focusBoard = self if value else None

    @staticmethod
    def mapChar2Arrow(event):
        """maps the keys hjkl to arrows like in vi and konqueror"""
        key = event.key()
        if key in Board.arrows:
            return key
        charArrows = m18nc('kajongg:arrow keys hjkl like in konqueror', 'hjklHJKL')
        key = unicode(event.text())
        if key and key in charArrows:
            key = Board.arrows[charArrows.index(key) % 4]
        return key

    def keyPressEvent(self, event):
        """navigate in the board"""
        key = Board.mapChar2Arrow(event)
        if key in Board.arrows:
            self.__moveCursor(key)
        else:
            QGraphicsRectItem.keyPressEvent(self, event)

    def __moveCursor(self, key):
        """move focus"""
        tiles = self._focusableTiles(key)
        if tiles:
            # sometimes the handBoard still has focus but
            # has no focusable tiles. Like after declaring
            # Original Call.
            oldPos = self.focusTile.xoffset, self.focusTile.yoffset
            tiles = list(x for x in tiles if (x.xoffset, x.yoffset) != oldPos or x == self.focusTile)
            assert tiles, [str(x) for x in self.tiles]
            tiles.append(tiles[0])
            self.focusTile = tiles[tiles.index(self.focusTile)+1]

    def dragObject(self, tile):
        """returns the object that should be dragged when the user tries to drag
        tile. This is either only the tile or the meld containing this tile"""
        # pylint: disable=R0201
        return tile, None

    def dragEnterEvent(self, dummyEvent):
        """drag enters the HandBoard: highlight it"""
        self.setPen(QPen(QColor('blue')))

    def dragLeaveEvent(self, dummyEvent):
        """drag leaves the HandBoard"""
        self._noPen()

    def _noPen(self):
        """remove pen for this board. The pen defines the border"""
        self.setPen(QPen(Qt.NoPen))

    def tileAt(self, xoffset, yoffset, level=0):
        """if there is a tile at this place, return it"""
        for tile in self.tiles:
            if (tile.xoffset, tile.yoffset, tile.level) == (xoffset, yoffset, level):
                return tile

    def tilesByElement(self, element):
        """returns all child items holding a tile for element"""
        return list(x for x in self.tiles if x.element == element)

    def rotatedLightSource(self):
        """the light source we need for the original tile before it is rotated"""
        lightSourceIndex = LIGHTSOURCES.index(self.lightSource)
        lightSourceIndex = (lightSourceIndex+self.sceneRotation() // 90)%4
        return LIGHTSOURCES[lightSourceIndex]

    def tileFacePos(self):
        """the face pos of a tile relative to the tile origin"""
        if not self.showShadows:
            return QPointF()
        lightSource = self.rotatedLightSource()
        xoffset = self.tileset.shadowWidth() - 1 if 'E' in lightSource else 0
        yoffset = self.tileset.shadowHeight() - 1 if 'S' in lightSource else 0
        return QPointF(xoffset, yoffset)

    def tileFaceRect(self):
        """the face rect of a tile relative to the tile origin"""
        return QRectF(self.tileFacePos(), self.tileset.faceSize)

    def sceneRotation(self):
        """the combined rotation of self and all parents"""
        matrix = self.sceneTransform()
        matrix = (int(matrix.m11()), int(matrix.m12()), int(matrix.m21()), int(matrix.m22()))
        rotations = {(0, 0, 0, 0):0, (1, 0, 0, 1):0, (0, 1, -1, 0):90, (-1, 0, 0, -1):180, (0, -1, 1, 0):270}
        if matrix not in rotations:
            raise Exception('matrix unknown:%s' % str(matrix))
        return rotations[matrix]

    def setPos(self, xWidth=0, xHeight=0, yWidth=0, yHeight=0):
        """sets the position in the parent item expressing the position in tile face units.
        The X position is xWidth*facewidth + xHeight*faceheight, analog for Y"""
        self.xWidth = xWidth
        self.xHeight = xHeight
        self.yWidth = yWidth
        self.yHeight = yHeight
        self.setGeometry()

    def setRect(self, width, height):
        """gives the board a fixed size in tile coordinates"""
        self.__fixedWidth = width
        self.__fixedHeight = height
        self.computeRect()

    def computeRect(self):
        """translate from our rect coordinates to scene coord"""
        sizeX = self.tileset.faceSize.width() * self.__fixedWidth
        sizeY = self.tileset.faceSize.height() * self.__fixedHeight
        if self.showShadows:
            sizeX += self.tileset.shadowWidth() + 2 * self.tileset.shadowHeight()
            sizeY += self.tileset.shadowHeight()
        rect = self.rect()
        rect.setWidth(sizeX)
        rect.setHeight(sizeY)
        self.prepareGeometryChange()
        QGraphicsRectItem.setRect(self, rect)

    @property
    def width(self):
        """getter for width"""
        return self.__fixedWidth

    @property
    def height(self):
        """getter for width"""
        return self.__fixedHeight

    def setGeometry(self):
        """move the board to the correct position and set its rect surrounding all its
        items. This is needed for enabling drops into the board.
        This is also called when the tileset or the light source for this board changes"""
        width = self.tileset.faceSize.width()
        height = self.tileset.faceSize.height()
        if not self.showShadows:
            offsets = (0, 0)
        elif self.isHandBoard:
            offsets = (-self.tileset.shadowHeight() * 2, 0)
        else:
            offsets = self.tileset.shadowOffsets(self._lightSource, self.sceneRotation())
        newX = self.xWidth*width+self.xHeight*height + offsets[0]
        newY = self.yWidth*width+self.yHeight*height + offsets[1]
        QGraphicsRectItem.setPos(self, newX, newY)

    @property
    def showShadows(self):
        """the active lightSource"""
        return self._showShadows

    @showShadows.setter
    def showShadows(self, value):
        """set active lightSource"""
        if self._showShadows != value:
            for tile in self.tiles:
                tile.graphics.setClippingFlags()
            self._reload(self.tileset, showShadows=value)

    @property
    def lightSource(self):
        """the active lightSource"""
        return self._lightSource

    @lightSource.setter
    def lightSource(self, lightSource):
        """set active lightSource"""
        if self._lightSource != lightSource:
            if lightSource not in LIGHTSOURCES:
                logException(TileException('lightSource %s illegal' % lightSource))
            self._reload(self.tileset, lightSource)

    @property
    def tileset(self):
        """get/set the active tileset and resize accordingly"""
        return self._tileset

    @tileset.setter
    def tileset(self, tileset):
        """get/set the active tileset and resize accordingly"""
        self._reload(tileset, self._lightSource)

    def _reload(self, tileset=None, lightSource=None, showShadows=None):
        """call this if tileset or lightsource change: recomputes the entire board"""
        if tileset is None:
            tileset = self.tileset
        if lightSource is None:
            lightSource = self._lightSource
        if showShadows is None:
            showShadows = self._showShadows
        if self._tileset != tileset or self._lightSource != lightSource or self._showShadows != showShadows:
            self.prepareGeometryChange()
            self._tileset = tileset
            self._lightSource = lightSource
            self._showShadows = showShadows
            self.setGeometry()
            for child in self.childItems():
                if isinstance(child, (Board, PlayerWind)):
                    child.tileset = tileset
                    child.lightSource = lightSource
                    child.showShadows = showShadows
            for tile in self.tiles:
                self.placeTile(tile)
                tile.graphics.update()
            self.computeRect()
            if self.hasFocus:
                self.scene().focusBoard = self

    def focusRectWidth(self): # pylint: disable=R0201
        """how many tiles are in focus rect?"""
        return 1

    def shiftZ(self, level):
        """used for 3D: compute the needed shift for the tile.
        level is the vertical position. 0 is the face position on
        ground level, -1 is the imprint a tile makes on the
        surface it stands on"""
        if not self.showShadows:
            return QPointF()
        shiftX = 0
        shiftY = 0
        if level != 0:
            lightSource = self.rotatedLightSource()
            stepX = level*self.tileset.shadowWidth()/2
            stepY = level*self.tileset.shadowHeight()/2
            if 'E' in lightSource:
                shiftX = stepX
            if 'W' in lightSource:
                shiftX = -stepX
            if 'N' in lightSource:
                shiftY = -stepY
            if 'S' in lightSource:
                shiftY = stepY
        return QPointF(shiftX, shiftY)

    def tileSize(self):
        """the current tile size"""
        return self._tileset.tileSize

    def faceSize(self):
        """the current face size"""
        return self._tileset.faceSize

    def __tilePlace(self, tile):
        """compute all properties for tile in this board: pos, scale, rotation
        and return them in a dict"""
        assert isinstance(tile, UITile)
        if not tile.graphics.scene():
            self.scene().addItem(tile.graphics)
        width = self.tileset.faceSize.width()
        height = self.tileset.faceSize.height()
        shiftZ = self.shiftZ(tile.level)
        boardPos = QPointF(tile.xoffset*width, tile.yoffset*height) + shiftZ
        scenePos = self.mapToScene(boardPos)
        tile.graphics.setDrawingOrder()
        return {'pos': scenePos, 'rotation': self.sceneRotation(), 'scale': self.scale()}

    def placeTile(self, tile):
        """places the tile in the scene. With direct=False, animate"""
        assert isinstance(tile, UITile)
        for pName, newValue in self.__tilePlace(tile).items():
            animation = tile.queuedAnimation(pName)
            if animation:
                curValue = animation.unpackValue(animation.endValue())
                if curValue != newValue:
                    # change a queued animation
                    animation.setEndValue(newValue)
            else:
                animation = tile.activeAnimation.get(pName, None)
                if isAlive(animation):
                    curValue = animation.unpackValue(animation.endValue())
                else:
                    curValue = tile.getValue(pName)
                if pName != 'scale' or abs(curValue - newValue) > 0.00001:
                    if curValue != newValue:
                        Animation(tile, pName, newValue)

class CourtBoard(Board):
    """A Board that is displayed within the wall"""
    def __init__(self, width, height):
        Board.__init__(self, width, height, Internal.field.tileset)

    def maximize(self):
        """make it as big as possible within the wall"""
        cWall = Internal.field.game.wall
        newSceneX = cWall[3].sceneBoundingRect().right()
        newSceneY = cWall[2].sceneBoundingRect().bottom()
        QGraphicsRectItem.setPos(self, newSceneX, newSceneY)
        tileset = self.tileset
        avail = (cWall[2].sceneBoundingRect().width()
            - 2 * tileset.shadowHeight()
            - tileset.faceSize.height())
        xScaleFactor = avail / (self.width * tileset.faceSize.width() + tileset.shadowWidth())
        yScaleFactor = avail / (self.height * tileset.faceSize.height() + tileset.shadowHeight())
        Board.setScale(self, min(xScaleFactor, yScaleFactor))
        for tile in self.tiles:
            tile.board.placeTile(tile)

class SelectorBoard(CourtBoard):
    """a board containing all possible tiles for selection"""
    # pylint: disable=R0904
    # pylint we have more than 40 public methods, shame on me!
    def __init__(self):
        CourtBoard.__init__(self, 9, 5)
        self.setAcceptDrops(True)
        self.lastReceived = None
        self.allSelectorTiles = []

    def load(self, game):
        """load the tiles according to game.ruleset"""
        for tile in self.tiles:
            tile.setBoard(None)
        self.tiles = []
        self.allSelectorTiles = list(UITile(x) for x in elements.all(game.ruleset))
        self.refill()

    def refill(self):
        """move all tiles back into the selector"""
        with Animated(False):
            for tile in self.allSelectorTiles:
                tile.element = tile.element.lower()
                self.__placeAvailable(tile)
                tile.dark = False
                tile.focusable = True
            self.focusTile = self.tilesByElement('c1')[0]

    # pylint: disable=R0201
    # pylint we know this could be static
    def name(self):
        """for debugging messages"""
        return 'selector'

    def dropEvent(self, event):
        """drop a tile into the selector"""
        mime = event.mimeData()
        self.dropHere(mime.tile, mime.meld)
        event.accept()

    def receive(self, tile=None, meld=None):
        """self receives tiles"""
        tiles = [tile] if tile else meld.tiles
        senderHand = tiles[0].board
        assert senderHand != self
        senderHand.removing(tile, meld)
        self.lastReceived = tiles[0]
        for myTile in tiles:
            self.__placeAvailable(myTile)
            myTile.focusable = True
        senderHand.remove(tile, meld)
        (senderHand if senderHand.tiles else self).hasFocus = True
        self._noPen()

    def dropHere(self, tile, meld, dummyLowerHalf=None):
        """drop tile or meld into selector board"""
        tile1 = tile or meld[0]
        if tile1.board != self:
            self.receive(tile, meld)
        animate()

    def removing(self, tile=None, meld=None):
        """we are going to lose those tiles or melds"""
        # pylint: disable=W0613
        tiles = [tile] if tile else meld.tiles
        if not self.focusTile in tiles:
            return
        focusCandidates = [x for x in self._focusableTiles() if x not in tiles or x == self.focusTile]
        focusCandidates.append(focusCandidates[0])
        self.focusTile = focusCandidates[focusCandidates.index(self.focusTile)+1]

    def remove(self, tile=None, meld=None):
        """Default: nothing to do after something has been removed"""
        # pylint: disable=W0613

    def __placeAvailable(self, tile):
        """place the tile in the selector at its place"""
        # define coordinates and order for tiles:
        offsets = {'d': (3, 6, 'bgr'), 'f': (4, 5, 'eswn'), 'y': (4, 0, 'eswn'),
            'w': (3, 0, 'eswn'), 'b': (1, 0, '123456789'), 's': (2, 0, '123456789'),
            'c': (0, 0, '123456789')}
        row, baseColumn, order = offsets[tile.element[0].lower()]
        column = baseColumn + order.index(tile.element[1])
        tile.dark = False
        tile.setBoard(self, column, row)

    def meldVariants(self, tile):
        """returns a list of possible variants based on tile."""
        # pylint: disable=R0914
        # pylint too many local variables
        wantedTileName = tile.element
        for selectorTile in self.tiles:
            selectorTile.element = selectorTile.element.lower()
        lowerName = wantedTileName.lower()
        upperName = wantedTileName.capitalize()
        if wantedTileName.istitle():
            scName = upperName
        else:
            scName = lowerName
        variants = [scName]
        baseTiles = len(self.tilesByElement(lowerName))
        if baseTiles >= 2:
            variants.append(scName * 2)
        if baseTiles >= 3:
            variants.append(scName * 3)
        if baseTiles == 4:
            if wantedTileName.istitle():
                variants.append(lowerName + upperName * 2 + lowerName)
            else:
                variants.append(lowerName * 4)
                variants.append(lowerName * 3 + upperName)
        if not tile.isHonor() and tile.element[-1] < '8':
            chow2 = chiNext(wantedTileName, 1)
            chow3 = chiNext(wantedTileName, 2)
            chow2 = self.tilesByElement(chow2.lower())
            chow3 = self.tilesByElement(chow3.lower())
            if chow2 and chow3:
                baseChar = scName[0]
                baseValue = ord(scName[1])
                varStr = '%s%s%s%s%s' % (scName, baseChar, chr(baseValue+1), baseChar, chr(baseValue+2))
                variants.append(varStr)
        result = [Meld(x) for x in variants]
        for meld in result:
            meld.tiles = [tile]
            for idx, pair in enumerate(meld.pairs[1:]):
                baseTiles = list(x for x in self.tilesByElement(pair.lower()) if x != tile)
                meld.tiles.append(baseTiles[0 if meld.isChow() else idx])
        return result


class MimeData(QMimeData):
    """we also want to pass a reference to the moved tile"""
    def __init__(self, tile=None, meld=None):
        assert bool(tile) != bool(meld)
        QMimeData.__init__(self)
        self.tile = tile
        self.meld = meld
        if self.tile:
            self.setText(tile.element)
        else:
            self.setText(meld.joined)

class FittingView(QGraphicsView):
    """a graphics view that always makes sure the whole scene is visible"""
    def __init__(self, parent=None):
        """generate a fitting view with our favourite properties"""
        QGraphicsView.__init__(self, parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        vpol = QSizePolicy()
        vpol.setHorizontalPolicy(QSizePolicy.Expanding)
        vpol.setVerticalPolicy(QSizePolicy.Expanding)
        self.setSizePolicy(vpol)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setStyleSheet('background: transparent')
        self.setFrameStyle(QFrame.NoFrame)
        self.tilePressed = None
        self.dragObject = None
        self.setFocus()

    def wheelEvent(self, event):  # pylint: disable=R0201
        """we do not want scrolling for the scene view.
        Instead scrolling down changes perspective like in kmahjongg"""
        if event.orientation() == Qt.Vertical and event.delta() < 0:
            Internal.field.changeAngle()
        # otherwise do not call ignore() because we do want
        # to consume this

    def resizeEvent(self, dummyEvent):
        """scale the scene for new view size"""
        # also adjust the background to the container. Do this here because this way
        # it is easier to minimize calls to setBackground()
        parent = self.parentWidget()
        if parent:
            grandpa = parent.parentWidget()
            if grandpa and grandpa.objectName() == 'MainWindow':
                if grandpa.ignoreResizing:
                    grandpa.ignoreResizing -= 1
                    return
                grandpa.applySettings()
                # resize background:
                grandpa.backgroundName = grandpa.backgroundName
        if Internal.scaleScene and self.scene():
            self.fitInView(self.scene().itemsBoundingRect(), Qt.KeepAspectRatio)
        self.setFocus()

    def __matchingTile(self, position, item):
        """is position in the clickableRect of this tile?"""
        if not isinstance(item, GraphicsTileItem):
            return False
        itemPos = item.mapFromScene(self.mapToScene(position))
        return item.tile.board.tileFaceRect().contains(itemPos)

    def tileAt(self, position):
        """find out which tile is clickable at this position. Always
        returns a list. If there are several tiles above each other,
        return all of them, highest first"""
        allTiles = [x for x in self.items(position) if isinstance(x, GraphicsTileItem)]
        items = [x for x in allTiles if self.__matchingTile(position, x)]
        if not items:
            return None
        items = [x.tile for x in items]
        for item in items[:]:
            for other in [x.tile for x in allTiles]:
                if (other.xoffset, other.yoffset) == (item.xoffset, item.yoffset):
                    if other.level > item.level:
                        items.append(other)
        return uniqueList(sorted(items, key=lambda x: -x.level))

    def mousePressEvent(self, event):
        """set blue focus frame"""
        tiles = self.tileAt(event.pos())
        if tiles:
            if event.modifiers() & Qt.ShiftModifier:
                for tile in tiles:
                    kprint('%s: board.level:%s' % (str(tile), tile.board.level))
            tile = tiles[0]
            board = tile.board
            isRemote = board.isHandBoard and board.player and not board.player.game.isScoringGame()
            if board.isHandBoard and not isRemote:
                tile = tile.board.meldWithTile(tile)[0]
            if tile.focusable:
                board.focusTile = tile
                board.hasFocus = True
                if isRemote:
                    Internal.field.clientDialog.buttons[0].setFocus()
                self.tilePressed = tile
            else:
                event.ignore()
        else:
            self.tilePressed = None
            event.ignore()

    def mouseReleaseEvent(self, event):
        """release self.tilePressed"""
        self.tilePressed = None
        return QGraphicsView.mouseReleaseEvent(self, event)

    def mouseMoveEvent(self, event):
        """selects the correct tile"""
        tilePressed = self.tilePressed
        self.tilePressed = None
        if tilePressed:
            board = tilePressed.board
            if board and board.tileDragEnabled:
                selBoard = Internal.field.selectorBoard
                selBoard.setAcceptDrops(tilePressed.board != selBoard)
                tile, meld = board.dragObject(tilePressed)
                self.dragObject = self.drag(tile, meld)
                self.dragObject.exec_(Qt.MoveAction)
                self.dragObject = None
                return
        return QGraphicsView.mouseMoveEvent(self, event)

    def drag(self, tile=None, meld=None):
        """returns a drag object"""
        drag = QDrag(self)
        mimeData = MimeData(tile, meld)
        drag.setMimeData(mimeData)
        tile = tile or meld[0]
        graphics = tile.graphics
        tRect = graphics.boundingRect()
        tRect = self.viewportTransform().mapRect(tRect)
        pmapSize = QSize(tRect.width() * graphics.scale(), tRect.height() * graphics.scale())
        pMap = graphics.pixmapFromSvg(pmapSize)
        drag.setPixmap(pMap)
        drag.setHotSpot(QPoint(pMap.width()/2, pMap.height()/2))
        return drag

class YellowText(QGraphicsRectItem):
    """a yellow rect with a message, used for claims"""
    def __init__(self, side):
        QGraphicsRectItem.__init__(self, side)
        self.side = side
        self.font = QFont()
        self.font.setPointSize(48)
        self.height = 62
        self.width = 200
        self.msg = None
        self.setText('')

    def setText(self, msg):
        """set the text of self"""
        self.msg = '%s  ' % msg
        metrics = QFontMetrics(self.font)
        self.width = metrics.width(self.msg)
        self.height = metrics.lineSpacing() * 1.1
        self.setRect(0, 0, self.width, self.height)
        self.resetTransform()
        rotation = self.side.rotation()
        rotateCenter(self, -rotation)
        if rotation % 180 == 0:
            yOffset = self.rect().height()
            if rotation == 0:
                yOffset = 2 * -yOffset
            if rotation == 180:
                self.translate(self.rect().width()/2, yOffset)
            else:
                self.translate(-self.rect().width()/2, yOffset)
        else:
            self.translate(-self.rect().width()/2, -self.rect().height()/2)
    def paint(self, painter, dummyOption, dummyWidget):
        """override predefined paint"""
        painter.setFont(self.font)
        painter.fillRect(self.rect(), QBrush(QColor('yellow')))
        painter.drawText(self.rect(), self.msg)

class DiscardBoard(CourtBoard):
    """A special board for discarded tiles"""
    def __init__(self):
        CourtBoard.__init__(self, 11, 9)
        self.__places = None
        self.lastDiscarded = None
        self.setAcceptDrops(True)

    @staticmethod
    def name(): # pylint: disable=W0221
        """to be used in debug output"""
        return "discardBoard"

    def hide(self):
        """remove all tile references so they can be garbage collected"""
        self.lastDiscarded = None
        CourtBoard.hide(self)

    def setRandomPlaces(self, randomGenerator):
        """precompute random positions"""
        self.__places = [(x, y) for x in range(self.width) for y in range(self.height)]
        randomGenerator.shuffle(self.__places)

    def discardTile(self, tile):
        """add tile to a random position"""
        assert isinstance(tile, UITile)
        tile.setBoard(self, *self.__places.pop(0))
        tile.dark = False
        tile.focusable = False
        self.focusTile = tile
        self.hasFocus = True
        self.lastDiscarded = tile

    def dropEvent(self, event):
        """drop a tile into the discard board"""
        # now that tiles are top level scene items, maybe drag them
        # directly. Draggings melds: QGraphicsItemGroup?
        mime = event.mimeData()
        graphics = mime.tile.graphics
        graphics.setPos(event.scenePos() - graphics.boundingRect().center())
        Internal.field.clientDialog.selectButton(Message.Discard)
        event.accept()
        self._noPen()

class MJScene(QGraphicsScene):
    """our scene with a potential Qt bug fix"""
    def __init__(self):
        QGraphicsScene.__init__(self)
        self.__disableFocusRect = False
        self._focusBoard = None
        self.focusRect = QGraphicsRectItem()
        pen = QPen(QColor(Qt.blue))
        pen.setWidth(6)
        self.focusRect.setPen(pen)
        self.addItem(self.focusRect)
        self.focusRect.setZValue(ZValues.marker)
        self.focusRect.hide()

    def focusInEvent(self, event):
        """work around a qt bug. See https://bugreports.qt-project.org/browse/QTBUG-32890
        This can be reproduced as follows:
           ./kajongg.py --game=whatever --autoplay=SomeRuleset
               such that the human player is the first one to discard a tile.
           wait until the main screen has been built
           click with the mouse into the middle of that window
           press left arrow key
           this will violate the assertion in GraphicsTileItem.keyPressEvent """
        prev = self.focusItem()
        QGraphicsScene.focusInEvent(self, event)
        if prev and bool(prev.flags() & QGraphicsItem.ItemIsFocusable) and prev != self.focusItem():
            self.setFocusItem(prev)

    def __focusRectVisible(self):
        """should we show it?"""
        game = Internal.field.game
        board = self._focusBoard
        return bool(not self.__disableFocusRect
                and board
                and board.hasFocus
                and board.focusTile
                and game
                and not game.autoPlay)

    @property
    def disableFocusRect(self):
        """suppress focusrect"""
        return self.__disableFocusRect

    @disableFocusRect.setter
    def disableFocusRect(self, value):
        """always place or hide, even if value does not change"""
        self.__disableFocusRect = value
        if value:
            self.focusRect.hide()
        else:
            self.placeFocusRect()

    @property
    def focusBoard(self):
        """get / set the board that has its focusRect shown"""
        return self._focusBoard

    @focusBoard.setter
    def focusBoard(self, board):
        """get / set the board that has its focusRect shown"""
        self._focusBoard = board
        focusTile = board.focusTile if board else None
        if focusTile:
            focusTile.graphics.setFocus()
            self.placeFocusRect()
        self.focusRect.setVisible(self.__focusRectVisible())

    def placeFocusRect(self):
        """show a blue rect around tile"""
        board = self._focusBoard
        if isAlive(board) and self.__focusRectVisible():
            rect = board.tileFaceRect()
            rect.setWidth(rect.width()*board.focusRectWidth())
            self.focusRect.setRect(rect)
            self.focusRect.setPos(board.focusTile.graphics.pos())
            self.focusRect.setRotation(board.sceneRotation())
            self.focusRect.setScale(board.scale())
            self.focusRect.show()
        else:
            self.focusRect.hide()

    def graphicsTileItems(self):
        """returns all GraphicsTileItems in the scene"""
        return (x for x in self.items() if isinstance(x, GraphicsTileItem))

    def nonTiles(self):
        """returns all other items in the scene"""
        return (x for x in self.items() if not isinstance(x, GraphicsTileItem))

    def removeTiles(self):
        """remove all tiles from scene"""
        for item in self.graphicsTileItems():
            self.removeItem(item)
        self.focusRect.hide()
