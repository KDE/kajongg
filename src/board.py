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

from PyQt4.QtCore import Qt, QPointF, QPoint, QRectF, QMimeData, QVariant
from PyQt4.QtGui import QGraphicsRectItem, QGraphicsItem, QSizePolicy, QFrame, QFont
from PyQt4.QtGui import QMenu, QCursor, QGraphicsView, QGraphicsEllipseItem, QGraphicsScene, QLabel
from PyQt4.QtGui import QColor, QPainter, QDrag, QPixmap, QStyleOptionGraphicsItem, QPen, QBrush
from PyQt4.QtGui import QFontMetrics, QGraphicsSimpleTextItem
from PyQt4.QtSvg import QGraphicsSvgItem
from tileset import Tileset, TileException
from tile import Tile
from meld import Meld, EXPOSED, CONCEALED, tileKey, meldKey, shortcuttedMeldName

import weakref
from collections import defaultdict

from util import logException, logWarning, debugMessage, m18n, m18nc
import common
from common import elements, WINDS, LIGHTSOURCES, IntDict, InternalParameters
from tile import chiNext

ROUNDWINDCOLOR = QColor(235, 235, 173)

WINDPIXMAPS = {}

def rotateCenter(item, angle):
    """rotates a QGraphicsItem around its center"""
    center = item.boundingRect().center()
    centerX, centerY = center.x(), center.y()
    item.translate(centerX, centerY)
    item.rotate(angle)
    item.translate(-centerX, -centerY)
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
    def wind(): # pylint: disable-msg=E0202
        """setting the wind also changes the pixmap"""
        def fget(self):
            # pylint: disable-msg=W0212
            return self.__wind
        def fset(self, wind):
            # pylint: disable-msg=W0212
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
            # pylint: disable-msg=W0212
            return self.__roundsFinished
        def fset(self, roundsFinished):
            # pylint: disable-msg=W0212
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
    # pylint: disable-msg=R0902
    # pylint: we need more than 10 instance attributes

    arrows = [Qt.Key_Left, Qt.Key_Down, Qt.Key_Up, Qt.Key_Right]
    def __init__(self, width, height, tileset, tiles=None, rotation=0):
        QGraphicsRectItem.__init__(self)
        self._focusTile = None
        self.focusRect = None
        self.showingFocusRect = False
        self._noPen()
        self.tileDragEnabled = False
        self.rotation = rotation
        self.rotate(rotation)
        self._lightSource = 'NW'
        self.xWidth = 0
        self.xHeight = 0
        self.yWidth = 0
        self.yHeight = 0
        self.__fixedWidth = width
        self.__fixedHeight = height
        self._tileset = None
        self.tileset = tileset
        self.level = 0
        if tiles:
            for tile in tiles:
                tile.board = self

    def autoSelectTile(self):
        """call this when kajongg should automatically focus
        on an appropriate tile"""
        self._focusTile = None
        focusableTiles = self.__focusableTiles()
        if len(focusableTiles):
            tile = focusableTiles[0]
            self._focusTile = weakref.ref(tile)
            if tile:
                tile.setFocus()

    @apply
    def focusTile(): # pylint: disable-msg=E0202
        """the tile of this board with focus. This is per Board!"""
        def fget(self):
            # pylint: disable-msg=W0212
            if self._focusTile is None:
                self.autoSelectTile()
            return self._focusTile() if self._focusTile else None
        def fset(self, tile):
            # pylint: disable-msg=W0212
            if tile:
                assert tile.element != 'Xy', tile
                if not isinstance(tile.board, DiscardBoard):
                    assert tile.focusable, tile
                if self._focusTile != tile:
                    self._focusTile = weakref.ref(tile)
                    tile.setFocus()
            else:
                self.autoSelectTile()
        return property(**locals())

    def setEnabled(self, enabled):
        """enable/disable this board"""
        self.tileDragEnabled = enabled
        QGraphicsRectItem.setEnabled(self, enabled)

    def isEnabled(self, lowerHalf=None):
        """the upper half of a hand board is only focusable for scoring"""
        if isinstance(self, HandBoard) and not self.player.game.isScoringGame() and not lowerHalf:
            return False
        return QGraphicsRectItem.isEnabled(self)

    def clear(self):
        """remove all tiles from this board"""
        for tile in self.allTiles():
            tile.board = None
            del tile

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

    def __focusableTiles(self, sortDir=Qt.Key_Right):
        """returns a list of all focusable tiles in this board sorted by y then x"""
        return list(x for x in self.allTiles(sortDir) if x.focusable)

    def __row(self, yoffset):
        """a list with all tiles at yoffset sorted by xoffset"""
        return list(tile for tile in self.__focusableTiles() if tile.yoffset == yoffset)

    def __column(self, xoffset):
        """a list with all tiles at xoffset sorted by yoffset"""
        return list(tile for tile in self.__focusableTiles() if tile.xoffset == xoffset)

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
        tiles = self.__focusableTiles(key)
        tiles = list(x for x in tiles if x.opacity or x == self.focusTile)
        tiles.append(tiles[0])
        self.focusTile = tiles[tiles.index(self.focusTile)+1]

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
        if not common.PREF.showShadows:
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
        if common.PREF.showShadows:
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
        if isinstance(self, HandBoard) or not common.PREF.showShadows:
            offsets = (0, 0)
        else:
            offsets = self.tileset.shadowOffsets(self._lightSource, self.sceneRotation())
        newX = self.xWidth*width+self.xHeight*height + offsets[0]
        newY = self.yWidth*width+self.yHeight*height + offsets[1]
        QGraphicsRectItem.setPos(self, newX, newY)

    @apply
    def lightSource():
        """the active lightSource"""
        def fget(self):
            # pylint: disable-msg=W0212
            return self._lightSource
        def fset(self, lightSource):
            """set active lightSource"""
            # pylint: disable-msg=W0212
            if self._lightSource != lightSource:
                if   lightSource not in LIGHTSOURCES:
                    logException(TileException('lightSource %s illegal' % lightSource))
                self._reload(self.tileset, lightSource)
        return property(**locals())

    @apply
    def tileset(): # pylint: disable-msg=E0202
        """get/set the active tileset and resize accordingly"""
        def fget(self):
            # pylint: disable-msg=W0212
            if self._tileset:
                return self._tileset
            elif self.parentItem():
                return self.parentItem().tileset
            elif isinstance(self, Board):
                return Tileset('default')
        def fset(self, tileset):
            self._reload(tileset, self._lightSource) # pylint: disable-msg=W0212
        return property(**locals())

    def _reload(self, tileset=None, lightSource=None):
        """call this if tileset or lightsource change: recomputes the entire board"""
        if tileset is None:
            tileset = self.tileset
        if lightSource is None:
            lightSource = self._lightSource
        if self._tileset != tileset or self._lightSource != lightSource:
            self.prepareGeometryChange()
            self._tileset = tileset
            self._lightSource = lightSource
            for child in self.childItems():
                if isinstance(child, (Board, PlayerWind)):
                    child.tileset = tileset
                    child.lightSource = lightSource
                elif isinstance(child, Tile):
                    child.board = self # tile will reposition itself
            self._setRect()
            self.setGeometry()
            self.setDrawingOrder()
            self.__placeFocusRect()

    def showFocusRect(self, tile):
        """show a blue rect around tile"""
        if self.showingFocusRect:
            # avoid recursion since hideAllFocusRect()
            # can indirectly call focusInEvent which calls us
            return
        assert tile.element, tile
        assert tile.element != 'Xy'
        if isinstance(self, HandBoard):
            self.moveFocusToClientDialog()
        self.showingFocusRect = True
        try:
            InternalParameters.field.hideAllFocusRect()
            self.focusTile = tile
        finally:
            self.showingFocusRect = False
        self.focusRect = QGraphicsRectItem()
        pen = QPen(QColor(Qt.blue))
        pen.setWidth(6)
        self.focusRect.setPen(pen)
        self.focusRect.setParentItem(self)
        self.focusRect.setZValue(99999999999)
        self.__placeFocusRect()
        # if the board window is unselected and we select it
        # by clicking on another tile, the previous tile keeps
        # its focusRect unless we call update here. Qt4.5
        # it would be even nicer if the focusRect of the previous
        # tile would not show up for a split second.
        self.update()

    def __placeFocusRect(self):
        """size and position the blue focus rect"""
        if self.focusRect:
            rect = self.tileFaceRect()
            rect.setWidth(rect.width()*self._focusRectWidth())
            self.focusRect.setRect(self.focusTile.mapToParent(rect).boundingRect())

    def hideFocusRect(self):
        """hides the focus rect"""
        if self.focusRect:
            self.focusRect.hide()
            self.update()
        self.focusRect = None

    def _focusRectWidth(self): # pylint: disable-msg=R0201
        """how many tiles are in focus rect?"""
        return 1

    def shiftZ(self, level):
        """used for 3D: compute the needed shift for the tile.
        level is the vertical position. 0 is the face position on
        ground level, -1 is the imprint a tile makes on the
        surface it stands on"""
        if not common.PREF.showShadows:
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
                item.setZValue((item.level+1)*100000+self.lightDistance(item))

    def tileSize(self):
        """the current tile size"""
        return self._tileset.tileSize

    def faceSize(self):
        """the current face size"""
        return self._tileset.faceSize

class SelectorTile(Tile):
    """tile with count. If count>0, show tile"""
    def __init__(self, element, count, xoffset=0, yoffset=0):
        Tile.__init__(self, element, xoffset, yoffset)
        self.maxCount = count
        self.count = count

    def pop(self):
        """reduce count by 1"""
        if self.count == 0:
            logException('tile %s out of stock!' % self.element)
        self.count -= 1
        if not self.count:
            self.setOpacity(0.0)

    def push(self):
        """increase count by 1"""
        self.count += 1
        if self.count:
            self.setOpacity(1.0)

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

    def fill(self, game):
        """fill it with all selectable tiles"""
        self.clear()
        if not game:
            return
        allTiles = elements.all(game.ruleset.withBonusTiles)
        # now build a dict with element as key and occurrence as value
        tiles = IntDict()
        for tile in allTiles:
            tiles[tile] +=  1
        for element, occurrence in defaultdict.items(tiles):
            # see http://www.logilab.org/ticket/23986
            self.placeAvailable(SelectorTile(element, occurrence))
        self.setDrawingOrder()

    def dropEvent(self, event):
        """drop a tile into the selector"""
        self.receive(self.scene().focusItem())
        event.accept()

    def receive(self, tile):
        """self receives a tile"""
        senderHand = tile.board if isinstance(tile.board, HandBoard) else None
        if senderHand: # None if we are already in the selectorboard. Do not send to self.
            senderHand.remove(tile)
            self._noPen()
            InternalParameters.field.handSelectorChanged(senderHand)

    def placeAvailable(self, tile):
        """place the tile in the selector at its place"""
        # define coordinates and order for tiles:
        offsets = {'d': (3, 6, 'bgr'), 'f': (4, 5, 'eswn'), 'y': (4, 0, 'eswn'),
            'w': (3, 0, 'eswn'), 'b': (1, 0, '123456789'), 's': (2, 0, '123456789'),
            'c': (0, 0, '123456789')}
        row, baseColumn, order = offsets[tile.element[0]]
        column = baseColumn + order.index(tile.element[1])
        tile.board = self
        tile.setPos(column, row)

class HandBoard(Board):
    """a board showing the tiles a player holds"""
    # pylint: disable-msg=R0904
    # pylint - we need more than 40 public methods
    # pylint: disable-msg=R0902
    # pylint - we need more than 10 instance attributes
    def __init__(self, player):
        self.exposedMeldDistance = 0.2
        self.concealedMeldDistance = 0.0
        if common.PREF.showShadows:
            self.rowDistance = 0.2
        else:
            self.rowDistance = 0
        Board.__init__(self, 15.4, 2.0 + self.rowDistance, InternalParameters.field.tileset)
        self.tileDragEnabled = False
        self.player = player
        self.setParentItem(player.front)
        self.setAcceptDrops(True)
        self.upperMelds = []
        self.lowerMelds = []
        self.flowers = []
        self.seasons = []
        self.lowerHalf = False
        self.__moveHelper = None
        self.__sourceView = None
        self.rearrangeMelds = common.PREF.rearrangeMelds
        self.setScale(1.5)

    @apply
    def rearrangeMelds(): # pylint: disable-msg=E0202
        """when setting this, concealed melds are grouped"""
        def fget(self):
            return bool(self.concealedMeldDistance)
        def fset(self, rearrangeMelds):
            if rearrangeMelds != self.rearrangeMelds:
                self.concealedMeldDistance = self.exposedMeldDistance if rearrangeMelds else 0.0
                self._reload(self.tileset, self._lightSource) # pylint: disable-msg=W0212
                self.placeTiles()
                if self.focusTile:
                    self.showFocusRect(self.focusTile)
        return property(**locals())

    def setEnabled(self, enabled):
        """enable/disable this board"""
        self.tileDragEnabled = enabled and self.player.game.isScoringGame()
        QGraphicsRectItem.setEnabled(self, enabled)

    def showMoveHelper(self, visible=True):
        """show help text In empty HandBoards"""
        if visible:
            if not self.__moveHelper:
                splitter = QGraphicsRectItem(self)
                center = self.rect().center()
                center.setX(self.player.front.center().x())
                splitter.setRect(center.x() * 0.5, center.y(), center.x() * 1, 1)
                helpItems = [splitter]
                for name, yFactor in [(m18n('Move Exposed Tiles Here'), 0.5), (m18n('Move Concealed Tiles Here'), 3)]:
                    helper = QGraphicsSimpleTextItem(name, self)
                    helper.setScale(3)
                    nameRect = QRectF()
                    nameRect.setSize(helper.mapToParent(helper.boundingRect()).boundingRect().size())
                    center.setY(center.y() * yFactor)
                    helper.setPos(center - nameRect.center())
                    if self.sceneRotation() == 180:
                        rotateCenter(helper, 180)
                    helpItems.append(helper)
                self.__moveHelper = self.scene().createItemGroup(helpItems)
            self.__moveHelper.setVisible(True)
        else:
            if self.__moveHelper:
                self.__moveHelper.setVisible(False)

    def hide(self):
        """make self invisible"""
        self.showMoveHelper(False)
        Board.hide(self)

    def _focusRectWidth(self):
        """how many tiles are in focus rect? We want to focus
        the entire meld"""
        if not self.player.game.isScoringGame():
            # network game: always make only single tiles selectable
            return 1
        return len(self.meldWithTile(self.focusTile) or [1])

    @staticmethod
    def moveFocusToClientDialog():
        """if there is an active clientDialog, give it the focus"""
        field = InternalParameters.field
        if field and field.clientDialog and field.clientDialog.isVisible():
            field.clientDialog.activateWindow()

    def scoringString(self):
        """helper for __str__"""
        parts = [x.joined for x in self.lowerMelds + self.upperMelds]
        parts.extend(x.element for x in self.flowers + self.seasons)
        return ' '.join(parts)

    def __str__(self):
        return self.scoringString()

    def meldWithTile(self, tile):
        """returns the meld holding tile"""
        for melds in self.upperMelds, self.lowerMelds:
            for meld in melds:
                if tile in meld:
                    return meld

    @staticmethod
    def __removeTile(tile):
        """return the tile to the selector board"""
        if tile.element != 'Xy':
            InternalParameters.field.selectorBoard.tilesByElement(tile.element.lower())[0].push()
        tile.board = None
        del tile
        if InternalParameters.field.game:
            InternalParameters.field.game.checkSelectorTiles()

    def __addTile(self, tile):
        """get tile from the selector board, return tile"""
        if tile.element != 'Xy':
            selectorTiles = InternalParameters.field.selectorBoard.tilesByElement(tile.element.lower())
            assert selectorTiles, 'board.addTile: %s not available in selector' % tile.element
            if selectorTiles[0].count == 0:
                logWarning('Cannot add tile %s to handBoard for player %s' % (tile.element, self.player))
                for line in self.player.game.locateTile(tile.element):
                    logWarning(line)
            selectorTiles[0].pop()
        tile.board = self
        InternalParameters.field.game.checkSelectorTiles()
        return tile

    def remove(self, removeData):
        """return tile or meld to the selector board"""
        if not (self.focusTile and self.focusTile.hasFocus()):
            hadFocus = False
        elif isinstance(removeData, Tile):
            hadFocus = self.focusTile == removeData
        else:
            hadFocus = self.focusTile == removeData[0]
        if isinstance(removeData, Tile) and removeData.isBonus():
            self.__removeTile(removeData) # flower, season
        else:
            if not self.player.game.isScoringGame() and isinstance(removeData, Tile):
                self.__removeTile(removeData)
            else:
                if isinstance(removeData, Tile):
                    removeData = self.meldWithTile(removeData)
                assert removeData
                for tile in removeData.tiles:
                    self.__removeTile(tile)
        self.placeTiles()
        if hadFocus:
            self.focusTile = None # force calculation of new focusTile

    def clear(self):
        """return all tiles to the selector board"""
        for melds in self.upperMelds, self.lowerMelds:
            for meld in melds:
                self.remove(meld)
        for tiles in self.flowers, self.seasons:
            for tile in tiles:
                self.remove(tile)
        InternalParameters.field.handSelectorChanged(self)

    def _add(self, addData, lowerHalf=None):
        """get tile or meld from the selector board"""
        if isinstance(addData, Meld):
            addData.tiles = []
            for pair in addData.pairs:
                addData.tiles.append(self.__addTile(Tile(pair)))
            self.placeTiles()
            if self.player.game.isScoringGame():
                for tile in addData.tiles[1:]:
                    tile.focusable = False
            else:
                focusable = True
                if lowerHalf is not None and lowerHalf == False:
                    focusable = False
                if self.player != self.player.game.myself:
                    focusable = False
                for tile in addData.tiles:
                    tile.focusable = focusable
            if addData.tiles[0].focusable:
                self.focusTile = addData.tiles[0]
        else:
            tile = Tile(addData) # flower, season
            self.__addTile(tile)
            self.placeTiles()
            if self.player.game.isScoringGame():
                self.focusTile = tile
            else:
                tile.focusable = False

    def dragMoveEvent(self, event):
        """allow dropping of tile from ourself only to other state (open/concealed)"""
        tile = self.scene().focusItem()
        localY = self.mapFromScene(QPointF(event.scenePos())).y()
        centerY = self.rect().height()/2.0
        newLowerHalf =  localY >= centerY
        noMansLand = centerY / 6
        if -noMansLand < localY - centerY < noMansLand and not tile.isBonus():
            doAccept = False
        elif tile.board != self:
            doAccept = True
        elif tile.isBonus():
            doAccept = False
        else:
            oldLowerHalf = isinstance(tile.board, HandBoard) and tile in tile.board.lowerHalfTiles()
            doAccept = oldLowerHalf != newLowerHalf
        event.setAccepted(doAccept)

    def dropEvent(self, event):
        """drop a tile into this handboard"""
        tile = self.scene().focusItem()
        lowerHalf = self.mapFromScene(QPointF(event.scenePos())).y() >= self.rect().height()/2.0
        if self.receive(tile, event.source(), lowerHalf):
            event.accept()
        else:
            event.ignore()
        self._noPen()

    def receive(self, tile, sourceView, lowerHalf):
        """self receives a tile, lowerHalf says into which part"""
        self.__sourceView = sourceView
        self.lowerHalf = lowerHalf
        if not sourceView: # network game: dealt tiles
            if tile[0] in 'fy':
                assert len(tile) == 2
                if tile[0] == 'f':
                    self.flowers.append(Tile(tile))
                else:
                    self.seasons.append(Tile(tile))
                self._add(tile)
            else:
                meld = Meld(tile)
                assert lowerHalf or meld.pairs[0] != 'Xy', tile
                (self.lowerMelds if self.lowerHalf else self.upperMelds).append(meld)
                self._add(meld, lowerHalf)
        else:
            senderHand = tile.board if isinstance(tile.board, HandBoard) else None
            if senderHand == self and tile.isBonus():
                return tile
            added = self.integrate(tile)
            if added:
                if senderHand == self:
                    self.placeTiles()
                    self.showFocusRect(added.tiles[0])
                else:
                    if senderHand:
                        senderHand.remove(added)
                    self._add(added)
                InternalParameters.field.handSelectorChanged(self)
            return added

    @staticmethod
    def __lineLength(melds):
        """the length of the melds in meld sizes when shown in the board"""
        return sum(len(meld) for meld in melds) + len(melds)//2

    def lowerHalfTiles(self):
        """returns a list with all single tiles of the lower half melds without boni"""
        result = []
        for meld in self.lowerMelds:
            result.extend(meld)
        return result

    def exposedTiles(self):
        """returns a list with all single tiles of the lower half melds without boni"""
        result = []
        for meld in self.upperMelds:
            result.extend(meld)
        return result

    def integrate(self, tile):
        """place the dropped tile in its new board, possibly using
        more tiles from the source to build a meld"""
        if tile.isBonus():
            if tile.isFlower():
                self.flowers.append(tile)
            else:
                self.seasons.append(tile)
            return tile
        else:
            meld = self.__meldFromTile(tile) # from other hand
            if not meld:
                return None
            meld.state = EXPOSED if not self.lowerHalf else CONCEALED
            assert self.lowerHalf or meld.pairs[0] != 'Xy', tile
            (self.lowerMelds if self.lowerHalf else self.upperMelds).append(meld)
            return meld

    def placeTiles(self):
        """place all tiles in HandBoard"""
        self.__removeForeignTiles()
        boni = self.flowers + self.seasons
        bonusY = 1.0 + self.rowDistance
        upperLen = self.__lineLength(self.upperMelds) + self.exposedMeldDistance
        lowerLen = self.__lineLength(self.lowerMelds) + self.concealedMeldDistance
        if upperLen < lowerLen :
            bonusY = 0
        self.upperMelds = sorted(self.upperMelds, key=meldKey)
        self.lowerMelds = sorted(self.lowerMelds, key=meldKey)

        if common.PREF.rearrangeMelds:
            lowerMelds = self.lowerMelds
        else:
            # generate one meld with all sorted tiles
            lowerMelds = [Meld(sorted(sum((x.tiles for x in self.lowerMelds), []), key=tileKey))]
        for yPos, melds in ((0, self.upperMelds), (1.0 + self.rowDistance, lowerMelds)):
            meldDistance = self.concealedMeldDistance if yPos else self.exposedMeldDistance
            meldX = 0
            meldY = yPos
            for meld in melds:
                for idx, tile in enumerate(meld):
                    tile.setPos(meldX, meldY)
                    tile.dark = meld.pairs[idx].istitle() and (yPos== 0 or self.player.game.isScoringGame())
                    meldX += 1
                meldX += meldDistance
        lastBonusX = max(lowerLen,  upperLen) + len(boni)
        if lastBonusX > self.xWidth:
            lastBonusX = self.xWidth
        self.__showBoni(boni, lastBonusX, bonusY)
        self.setDrawingOrder()

    def __showBoni(self, bonusTiles, lastBonusX, bonusY):
        """show bonus tiles in HandBoard"""
        xPos = 13 - len(bonusTiles)
        if lastBonusX > xPos:
            xPos = lastBonusX
        for bonus in sorted(bonusTiles, key=tileKey):
            bonus.board = self
            bonus.setPos(xPos, bonusY)
            xPos += 1

    def __removeForeignTiles(self):
        """remove tiles/melds from our lists that no longer belong to our board"""
        normalMelds = set(meld for meld in self.upperMelds + self.lowerMelds \
                        if len(meld.tiles) and meld[0].board == self)
        self.upperMelds = list(meld for meld in normalMelds if meld.state !=
                        CONCEALED or meld.isKong()) # includes CLAIMEDKONG
        self.lowerMelds = list(meld for meld in normalMelds if meld not in self.upperMelds)
        tiles = self.allTiles()
        unknownTiles = list([tile for tile in tiles if not tile.isBonus() \
                        and not self.meldWithTile(tile)])
        if len(unknownTiles):
            debugMessage('%s upper melds:%s' % (self.player, ' '.join([x.joined for x in self.upperMelds])))
            debugMessage('%s lower melds:%s' % (self.player, ' '.join([x.joined for x in self.lowerMelds])))
            debugMessage('%s unknown tiles: %s' % (self.player, ' '.join(unknownTiles)))
            logException("board %s is inconsistent, see debug output" % self.player.name)
        self.flowers = list(tile for tile in tiles if tile.isFlower())
        self.seasons = list(tile for tile in tiles if tile.isSeason())
        if self.__moveHelper:
            self.__moveHelper.setVisible(not tiles)

    def __meldVariants(self, tile):
        """returns a list of possible variants based on the dropped tile.
        The Variants are scoring strings. Do not use the real tiles because we
        change their properties"""
        lowerName = tile.lower()
        upperName = tile.upper()
        if self.lowerHalf:
            scName = upperName
        else:
            scName = lowerName
        variants = [scName]
        baseTiles = InternalParameters.field.selectorBoard.tilesByElement(tile.element.lower())[0].count
        if baseTiles >= 2:
            variants.append(scName * 2)
        if baseTiles >= 3:
            variants.append(scName * 3)
        if baseTiles == 4:
            if self.lowerHalf:
                variants.append(lowerName + upperName * 2 + lowerName)
            else:
                variants.append(lowerName * 4)
                variants.append(lowerName * 3 + upperName)
        if not tile.isHonor() and tile.element[-1] < '8':
            chow2 = chiNext(tile.element, 1)
            chow3 = chiNext(tile.element, 2)
            chow2 = InternalParameters.field.selectorBoard.tilesByElement(chow2.lower())[0]
            chow3 = InternalParameters.field.selectorBoard.tilesByElement(chow3.lower())[0]
            if chow2.count and chow3.count:
                baseChar = scName[0]
                baseValue = ord(scName[1])
                varStr = '%s%s%s%s%s' % (scName, baseChar, chr(baseValue+1), baseChar, chr(baseValue+2))
                variants.append(varStr)
        return [Meld(x) for x in variants]

    def __meldFromTile(self, tile):
        """returns a meld, lets user choose between possible meld types"""
        if isinstance(tile.board, HandBoard):
            meld = tile.board.meldWithTile(tile)
            assert meld
            if not self.lowerHalf and len(meld) == 4 and meld.state == CONCEALED:
                pair0 = meld.pairs[0].lower()
                meldVariants = [Meld(pair0*4), Meld(pair0*3 + pair0[0].upper() + pair0[1])]
                for variant in meldVariants:
                    variant.tiles = meld.tiles
            else:
                return meld
        else:
            meldVariants = self.__meldVariants(tile)
        idx = 0
        if len(meldVariants) > 1:
            menu = QMenu(m18n('Choose from'))
            for idx, variant in enumerate(meldVariants):
                action = menu.addAction(shortcuttedMeldName(variant.meldType))
                action.setData(QVariant(idx))
            if InternalParameters.field.centralView.dragObject:
                menuPoint = QCursor.pos()
            else:
                menuPoint = self.tileFaceRect().bottomRight()
                view = self.__sourceView
                menuPoint = view.mapToGlobal(view.mapFromScene(tile.mapToScene(menuPoint)))
            action = menu.exec_(menuPoint)
            if not action:
                return None
            idx = action.data().toInt()[0]
        if tile.board == self:
            meld.tiles = []
        return meldVariants[idx]

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
        tile = self.tileAt(event.pos())
        if tile and tile.opacity:
            board = tile.board
            isRemote = isinstance(board, HandBoard) and board.player and not board.player.game.isScoringGame()
            if not tile.focusable and isinstance(board, HandBoard) and not isRemote:
                tile = tile.board.meldWithTile(tile)[0]
            if tile.focusable:
                tile.setFocus()
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
        if tilePressed and tilePressed.opacity:
            board = tilePressed.board
            if board and board.tileDragEnabled:
                selectorBoard = InternalParameters.field.selectorBoard
                selectorBoard.setAcceptDrops(tilePressed.board != selectorBoard)
                self.dragObject = self.drag(tilePressed)
                self.dragObject.exec_(Qt.MoveAction)
                self.dragObject = None
                return
        return QGraphicsView.mouseMoveEvent(self, event)

    def drag(self, item):
        """returns a drag object"""
        drag = QDrag(self)
        mimeData = QMimeData()
        mimeData.setText(item.element)
        drag.setMimeData(mimeData)
        tSize = item.boundingRect()
        tRect = QRectF(0.0, 0.0, tSize.width(), tSize.height())
        vRect = self.viewportTransform().mapRect(tRect)
        pmapSize = vRect.size().toSize()
        pMap = item.pixmap(pmapSize)
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
        rotateCenter(self, -self.side.rotation)
        if self.side.rotation % 180 == 0:
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

    def setRandomPlaces(self, randomGenerator):
        """precompute random positions"""
        self.__places = [(x, y) for x in range(self.width) for y in range(self.height)]
        randomGenerator.shuffle(self.__places)

    def addTile(self, tileName):
        """add tile to a random position"""
        tile = Tile(tileName)
        tile.board = self
        tile.setPos(*self.__places[0])
        tile.focusable = False
        self.showFocusRect(tile)
        del self.__places[0]
        self.lastDiscarded = tile
        return tile

    def removeLastDiscard(self):
        """removes the last diiscard again"""
        self.lastDiscarded.board = None
        self.lastDiscarded = None

class MJScene(QGraphicsScene):
    """our scene with a potential Qt bug fix"""
    def __init__(self):
        QGraphicsScene.__init__(self)

    def focusInEvent(self, event):
        """here the scene will focus on lastFocusItem (see C++ source) but that
        is the previous tile and not the last tile that had focus.
        Might be my bug, might be a Qt bug. I believe
        Qt does not always update lastFocusItem when it should.
        So after QGraphicsScene.focusInEvent did its work,
        we force focus back to the correct item"""
        item = self.focusItem()
        result = QGraphicsScene.focusInEvent(self, event)
        if item:
            item.setFocus()
        return result

