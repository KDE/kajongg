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

from PyQt4.QtCore import Qt, QPointF, QPoint, QRectF, QMimeData
from PyQt4.QtGui import QGraphicsRectItem, QGraphicsItem, QSizePolicy, QFrame, QFont
from PyQt4.QtGui import QGraphicsView, QGraphicsEllipseItem, QGraphicsScene, QLabel
from PyQt4.QtGui import QColor, QPainter, QDrag, QPixmap, QStyleOptionGraphicsItem, QPen, QBrush
from PyQt4.QtGui import QFontMetrics, QTransform
from PyQt4.QtSvg import QGraphicsSvgItem
from tileset import Tileset, TileException
from tile import Tile, chiNext
from meld import Meld, elementKey

from message import Message

from util import logException, m18nc
import common
from common import elements, WINDS, LIGHTSOURCES, InternalParameters, ZValues

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
            WINDPIXMAPS[('E', False)] = None  # avoid recursion
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
        tileset = Tileset(common.PREF.windTilesetName)
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

    @apply
    def wind(): # pylint: disable=E0202
        """setting the wind also changes the pixmap"""
        def fget(self):
            # pylint: disable=W0212
            return self.__wind
        def fset(self, wind):
            # pylint: disable=W0212
            if self.__wind != wind:
                self.__wind = wind
                self._refresh()
        return property(**locals())

    def __init__(self, wind = None, roundsFinished = 0, parent=None):
        QLabel.__init__(self, parent)
        self.__wind = None
        if wind is None:
            wind = 'E'
        self.__roundsFinished = roundsFinished
        self.wind = wind

    @apply
    def roundsFinished():
        """setting roundsFinished also changes pixmaps if needed"""
        def fget(self):
            # pylint: disable=W0212
            return self.__roundsFinished
        def fset(self, roundsFinished):
            # pylint: disable=W0212
            if self.__roundsFinished != roundsFinished:
                self.__roundsFinished = roundsFinished
                self._refresh()
        return property(**locals())

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

    def autoSelectTile(self):
        """call this when kajongg should automatically focus
        on an appropriate tile"""
        focusableTiles = self._focusableTiles()
        if len(focusableTiles):
            return focusableTiles[0]

    @apply
    def focusTile(): # pylint: disable=E0202
        """the tile of this board with focus. This is per Board!"""
        def fget(self):
            # pylint: disable=W0212
            if self._focusTile is None:
                self._focusTile = self.autoSelectTile()
            return self._focusTile
        def fset(self, tile):
            # pylint: disable=W0212
            if tile:
                assert tile.element != 'Xy', tile
                if not isinstance(tile.board, DiscardBoard):
                    assert tile.focusable, tile
                self._focusTile = tile
            else:
                self._focusTile = self.autoSelectTile()
            if self.hasFocus:
                self.scene().focusBoard = self
        return property(**locals())

    def setEnabled(self, enabled):
        """enable/disable this board"""
        self.tileDragEnabled = enabled
        QGraphicsRectItem.setEnabled(self, enabled)

    def allTiles(self, sortDir=Qt.Key_Right):
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
        return sorted(list(x for x in self.childItems() if isinstance(x, Tile)),
            key=sortFunction)

    def _focusableTiles(self, sortDir=Qt.Key_Right):
        """returns a list of all focusable tiles in this board sorted by y then x"""
        return list(x for x in self.allTiles(sortDir) if x.focusable)

    @apply
    def hasFocus(): # pylint: disable=E0202
        """defines if this board should show a focusRect
        if another board has focus, setting this to False does
        not change scene.focusBoard"""
        def fget(self):
            # pylint: disable=W0212
            return self.scene() and self.scene().focusBoard == self
        def fset(self, value):
            # pylint: disable=W0212
            scene = self.scene()
            if scene.focusBoard == self or value:
                scene.focusBoard = self if value else None
        return property(**locals())

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
        oldPos = self.focusTile.xoffset, self.focusTile.yoffset
        tiles = list(x for x in tiles if (x.xoffset, x.yoffset) != oldPos or x == self.focusTile)
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
        for tile in self.allTiles():
            if (tile.xoffset, tile.yoffset, tile.level) == (xoffset, yoffset, level):
                return tile

    def tilesByElement(self, element):
        """returns all child items holding a tile for element"""
        return list(tile for tile in self.childItems() \
            if isinstance(tile, Tile) and tile.element == element)

    def lightDistance(self, item):
        """the distance of item from the light source"""
        rect = item.sceneBoundingRect()
        result = 0
        if 'E' in self.lightSource:
            result -= rect.right()
        if 'W' in self.lightSource:
            result += rect.left()
        if 'S' in self.lightSource:
            result -= rect.bottom()
        if 'N' in self.lightSource:
            result += rect.top()
        return result

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
        yoffset =  self.tileset.shadowHeight() - 1 if 'S' in lightSource else 0
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
            raise Exception('matrix unknown:%s' % matrix)
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
        self._setRect()

    def _setRect(self):
        """translate from our rect coordinates to scene coord"""
        sizeX = self.tileset.faceSize.width() * self.__fixedWidth
        sizeY = self.tileset.faceSize.height() * self.__fixedHeight
        if self.showShadows:
            sizeX += self.tileset.shadowWidth()
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
        if self.isHandBoard or not self.showShadows:
            offsets = (0, 0)
        else:
            offsets = self.tileset.shadowOffsets(self._lightSource, self.sceneRotation())
        newX = self.xWidth*width+self.xHeight*height + offsets[0]
        newY = self.yWidth*width+self.yHeight*height + offsets[1]
        QGraphicsRectItem.setPos(self, newX, newY)

    @apply
    def showShadows():
        """the active lightSource"""
        def fget(self):
            # pylint: disable=W0212
            return self._showShadows
        def fset(self, value):
            """set active lightSource"""
            # pylint: disable=W0212
            if self._showShadows != value:
                self._reload(self.tileset, showShadows=value)
        return property(**locals())

    @apply
    def lightSource():
        """the active lightSource"""
        def fget(self):
            # pylint: disable=W0212
            return self._lightSource
        def fset(self, lightSource):
            """set active lightSource"""
            # pylint: disable=W0212
            if self._lightSource != lightSource:
                if   lightSource not in LIGHTSOURCES:
                    logException(TileException('lightSource %s illegal' % lightSource))
                self._reload(self.tileset, lightSource)
        return property(**locals())

    @apply
    def tileset(): # pylint: disable=E0202
        """get/set the active tileset and resize accordingly"""
        def fget(self):
            # pylint: disable=W0212
            if self._tileset:
                return self._tileset
            elif self.parentItem():
                return self.parentItem().tileset
            elif isinstance(self, Board):
                return Tileset('default')
        def fset(self, tileset):
            self._reload(tileset, self._lightSource) # pylint: disable=W0212
        return property(**locals())

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
            for child in self.childItems():
                if isinstance(child, (Board, PlayerWind)):
                    child.tileset = tileset
                    child.lightSource = lightSource
                    child.showShadows = showShadows
                elif isinstance(child, Tile):
                    child.setBoard(self) # tile will reposition itself
            self._setRect()
            self.setGeometry()
            self.setDrawingOrder()
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

    def setDrawingOrder(self):
        """the tiles are painted by qt in the order in which they were
        added to the board widget. So if we place a tile between
        existing tiles, we have to reassign the following tiles.
        When calling setDrawingOrder, the tiles must already have positions
        and sizes"""
        for item in self.childItems():
            if isinstance(item, (Tile, Board)):
                item.setZValue((item.level+1)*ZValues.itemLevelFactor+self.lightDistance(item))

    def tileSize(self):
        """the current tile size"""
        return self._tileset.tileSize

    def faceSize(self):
        """the current face size"""
        return self._tileset.faceSize

class CourtBoard(Board):
    """A Board that is displayed within the wall"""

    def __init__(self, width, height):
        Board.__init__(self, width, height, InternalParameters.field.tileset)

    def maximize(self):
        """make it as big as possible within the wall. This code is inefficient...
        but fast enough. When resizing, recomputing the SVG
         tiles takes much more time than this."""
        xWidth = 1.5
        yWidth = 1.5
        cWall = InternalParameters.field.game.wall
        while self.collidesWithItem(cWall[3]):
            xWidth += 0.01
            self.setPos(xWidth=xWidth, yWidth=yWidth)
        while self.collidesWithItem(cWall[2]):
            yWidth += 0.01
            self.setPos(xWidth=xWidth, yWidth=yWidth)
        scaleFactor = 2.0
        Board.setScale(self, scaleFactor)
        while self.collidesWithItem(cWall[0]) or \
            self.collidesWithItem(cWall[1]):
            scaleFactor *= 0.99
            self.resetTransform()
            Board.setScale(self, scaleFactor)

class SelectorBoard(CourtBoard):
    """a board containing all possible tiles for selection"""

    def __init__(self):
        CourtBoard.__init__(self, 9, 5)
        self.setAcceptDrops(True)
        self.lastReceived = None
        self.allSelectorTiles = []

    def load(self, game):
        """load the tiles according to game.ruleset"""
        allTiles = elements.all(game.ruleset)
        for tile in self.tiles:
            tile.setBoard(None)
        self.allSelectorTiles = list(Tile(x) for x in allTiles)
        self.refill()

    def refill(self):
        """move all tiles back into the selector"""
        for tile in self.allSelectorTiles:
            tile.dark = False
            tile.focusable = True
            tile.element = tile.element.lower()
            self.__placeAvailable(tile)
        self.setDrawingOrder()
        self.focusTile = self.childItems()[0]
        field = InternalParameters.field
        field.animate()

    # pylint: disable=R0201
    # pylint we know this could be static
    def name(self):
        """for debugging messages"""
        return 'selector'

    def dropEvent(self, event):
        """drop a tile into the selector"""
        mime = event.mimeData()
        self.receive(mime.tile, mime.meld)
        event.accept()

    def receive(self, tile=None, meld=None):
        """self receives tiles"""
        tiles = [tile] if tile else meld.tiles
        senderHand = tiles[0].board
        assert senderHand != self
        senderHand.removing(tile, meld)
        self.lastReceived = tiles[0]
        for myTile in tiles:
            myTile.dark = False
            self.__placeAvailable(myTile)
        self.setDrawingOrder()
        senderHand.remove(tile, meld)
        (senderHand if senderHand.allTiles() else self).hasFocus = True
        self._noPen()

    def dropHere(self, tile, meld, dummyLowerHalf):
        """drop tile or meld into selector board"""
        tile1 = tile or meld[0]
        if tile1.board != self:
            self.receive(tile, meld)

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
        tile.setBoard(self, column, row)

    def meldVariants(self, tile):
        """returns a list of possible variants based on tile."""
        # pylint: disable=R0914
        # pylint too many local variables
        wantedTileName = tile.element
        for selectorTile in self.allTiles():
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
        self.setFrameShadow(QFrame.Plain)
        self.tilePressed = None
        self.dragObject = None
        self.setFocus()

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
        if self.scene():
            self.fitInView(self.scene().itemsBoundingRect(), Qt.KeepAspectRatio)
        self.setFocus()

    def __matchingTile(self, position, item):
        """is position in the clickableRect of this tile?"""
        if not isinstance(item, Tile):
            return False
        itemPos = item.mapFromScene(self.mapToScene(position))
        return item.clickableRect().contains(itemPos)

    def tileAt(self, position):
        """find out which tile is clickable at this position"""
        allTiles = [x for x in self.items(position) if isinstance(x, Tile)]
        items = [x for x in allTiles if self.__matchingTile(position, x)]
        if not items:
            return None
        maxLevel = max(x.level for x in items)
        item = [x for x in items if x.level == maxLevel][0]
        for other in allTiles:
            if (other.xoffset, other.yoffset) == (item.xoffset, item.yoffset):
                if other.level > item.level:
                    item = other
        return item

    def mousePressEvent(self, event):
        """set blue focus frame"""
        board = InternalParameters.field.discardBoard
        tile = self.tileAt(event.pos())
        if tile:
            board = tile.board
            isRemote = board.isHandBoard and board.player and not board.player.game.isScoringGame()
            if board.isHandBoard and not isRemote:
                tile = tile.board.meldWithTile(tile)[0]
            if tile.focusable:
                board.focusTile = tile
                board.hasFocus = True
                if isRemote:
                    InternalParameters.field.clientDialog.buttons[0].setFocus()
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
                selBoard = InternalParameters.field.selectorBoard
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
        tSize = tile.boundingRect()
        tRect = QRectF(0.0, 0.0, tSize.width(), tSize.height())
        vRect = self.viewportTransform().mapRect(tRect)
        pmapSize = vRect.size().toSize()
        pMap = tile.pixmap(pmapSize)
        drag.setPixmap(pMap)
        drag.setHotSpot(QPoint(pMap.width()/2,  pMap.height()/2))
        return drag

class YellowText(QGraphicsRectItem):
    """a yellow rect with a message,  used for claims"""
    def __init__(self, side):
        QGraphicsRectItem.__init__(self, side)
        self.side = side
        self.font = QFont()
        self.font.setWeight(QFont.Bold)
        self.font.setPointSize(36)
        self.height = 50
        self.width = 200
        self.msg = None
        self.setText('')

    def setText(self, msg):
        """set the text of self"""
        self.msg = msg
        metrics = QFontMetrics(self.font)
        self.width = metrics.width(msg)
        self.height = metrics.height()
        self.setRect(0, 0, self.width, self.height)
        self.resetTransform()
        rotateCenter(self, -self.side.rotation())
        if self.side.rotation() % 180 == 0:
            self.translate(-self.rect().width()/2, 0)
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

    # pylint: disable=R0201
    # pylint we do not want this to be staticmethod
    def name(self):
        """to be used in debug output"""
        return "discardBoard"

    def setRandomPlaces(self, randomGenerator):
        """precompute random positions"""
        self.__places = [(x, y) for x in range(self.width) for y in range(self.height)]
        randomGenerator.shuffle(self.__places)

    def discardTile(self, tile):
        """add tile to a random position"""
        assert isinstance(tile, Tile)
        tile.setBoard(self, *self.__places.pop(0))
        tile.focusable = False
        self.focusTile = tile
        self.hasFocus = True
        self.lastDiscarded = tile

    def dropEvent(self, event):
        """drop a tile into the selector"""
        InternalParameters.field.clientDialog.selectButton(Message.Discard)
        event.accept()
        self._noPen()

class MJScene(QGraphicsScene):
    """our scene with a potential Qt bug fix"""
    def __init__(self):
        QGraphicsScene.__init__(self)
        self._focusBoard = None
        self.focusRect = QGraphicsRectItem()
        pen = QPen(QColor(Qt.blue))
        pen.setWidth(12)
        self.focusRect.setPen(pen)
        self.addItem(self.focusRect)
        self.focusRect.setZValue(ZValues.marker)
        self.focusRect.hide()

    @apply
    def focusBoard(): # pylint: disable=E0202
        """get / set the board that has its focusRect shown"""
        def fget(self):
            # pylint: disable=W0212
            return self._focusBoard
        def fset(self, board):
            # pylint: disable=W0212
            self._focusBoard = board
            focusTile = board.focusTile if board else None
            if focusTile:
                focusTile.setFocus()
                self.placeFocusRect()
            self.focusRect.setVisible(bool(focusTile))
        return property(**locals())

    def placeFocusRect(self):
        """show a blue rect around tile"""
        board = self._focusBoard
        if board and board.hasFocus and board.focusTile and not board.focusTile.animated:
            rect = board.focusTile.mapToParent(board.tileFaceRect()).boundingRect()
            rect.setWidth(rect.width()*board.focusRectWidth())
            rect = board.mapToScene(rect).boundingRect()
            self.focusRect.setRect(rect)
            self.focusRect.show()
        else:
            self.focusRect.hide()
