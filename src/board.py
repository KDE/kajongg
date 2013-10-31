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

from PyQt4.QtCore import Qt, QPointF, QPoint, QRectF, QMimeData, QSize, QVariant
from PyQt4.QtGui import QGraphicsRectItem, QGraphicsItem, QSizePolicy, QFrame, QFont
from PyQt4.QtGui import QGraphicsView, QGraphicsEllipseItem, QGraphicsScene, QLabel
from PyQt4.QtGui import QColor, QPainter, QDrag, QPixmap, QStyleOptionGraphicsItem, QPen, QBrush
from PyQt4.QtGui import QFontMetrics, QTransform
from PyQt4.QtGui import QMenu, QCursor
from PyQt4.QtSvg import QGraphicsSvgItem
from tileset import Tileset, TileException
from tile import chiNext, Tile, elements
from uitile import UITile, UIMeld
from guiutil import Painter
from meld import Meld
from animation import Animation, Animated, animate
from message import Message

from util import logDebug, logException, m18n, m18nc, kprint, stack, uniqueList
from common import WINDS, LIGHTSOURCES, Internal, ZValues, Debug, Preferences, isAlive

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
                        with Painter(painter):
                            painter.translate(child.mapToParent(0.0, 0.0))
                            child.paint(painter, QStyleOptionGraphicsItem())
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
    # pylint: disable=too-many-instance-attributes

    arrows = [Qt.Key_Left, Qt.Key_Down, Qt.Key_Up, Qt.Key_Right]
    def __init__(self, width, height, tileset, boardRotation=0):
        QGraphicsRectItem.__init__(self)
        self.uiTiles = []
        self.isHandBoard = False
        self._focusTile = None
        self.__prevPos = 0
        self._noPen()
        self.tileDragEnabled = False
        self.setRotation(boardRotation)
        self._lightSource = 'NW'
        self.__xWidth = 0
        self.__xHeight = 0
        self.__yWidth = 0
        self.__yHeight = 0
        self.__fixedWidth = width
        self.__fixedHeight = height
        self._tileset = None
        self._showShadows = None
        self.tileset = tileset
        self.level = 0

    @property
    def name(self): # pylint: disable=no-self-use
        """default board name, used for debugging messages"""
        return 'board'

    def hide(self):
        """remove all uiTile references so they can be garbage collected"""
        for uiTile in self.uiTiles:
            uiTile.hide()
        self.uiTiles = []
        self._focusTile = None
        if isAlive(self):
            QGraphicsRectItem.hide(self)

    def autoSelectTile(self):
        """call this when kajongg should automatically focus
        on an appropriate uiTile"""
        focusCandidates = self._focusableTiles()
        if focusCandidates:
            firstCandidate = focusCandidates[0]
            if self._focusTile not in focusCandidates:
                focusCandidates = list(x for x in focusCandidates if x.sortKey() >= self.__prevPos)
                focusCandidates.append(firstCandidate)
                self.focusTile = focusCandidates[0]

    @property
    def currentFocusTile(self):
        """get focusTile without selecting one"""
        return self._focusTile

    @property
    def focusTile(self):
        """the uiTile of this board with focus. This is per Board!"""
        if self._focusTile is None:
            self.autoSelectTile()
        return self._focusTile

    @focusTile.setter
    def focusTile(self, uiTile):
        """the uiTile of this board with focus. This is per Board!"""
        if uiTile is self._focusTile:
            return
        if uiTile:
            assert uiTile.tile != b'Xy', uiTile
            if not isinstance(uiTile.board, DiscardBoard):
                assert uiTile.focusable, uiTile
            self.__prevPos = uiTile.sortKey()
        self._focusTile = uiTile
        if self._focusTile and self._focusTile.tile in Debug.focusable:
            logDebug('%s: new focus uiTile %s from %s' % (
                self.name(), self._focusTile.tile if self._focusTile else 'None', stack('')[-1]))
        if (self.isHandBoard and self.player
            and not self.player.game.isScoringGame()
            and Internal.field.clientDialog):
            Internal.field.clientDialog.focusTileChanged()
        if self.hasFocus:
            self.scene().focusBoard = self
        assert uiTile is self._focusTile

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
        return sorted([x for x in self.uiTiles if x.focusable], key=lambda x: x.sortKey(sortDir))

    @property
    def hasFocus(self):
        """defines if this board should show a focusRect
        if another board has focus, setting this to False does
        not change scene.focusBoard"""
        return self.scene() and self.scene().focusBoard == self and self._focusTile

    @hasFocus.setter
    def hasFocus(self, value):
        """sets focus on this board"""
        if isAlive(self):
            scene = self.scene()
            if scene.focusBoard == self or value:
                if self.focusTile:
                    assert self.focusTile.board == self, '%s not in self %s' % (self.focusTile, self)
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
            assert tiles, [str(x) for x in self.uiTiles]
            tiles.append(tiles[0])
            self.focusTile = tiles[tiles.index(self.focusTile)+1]

    def _uiMeldWithTile(self, uiTile): # pylint: disable=no-self-use
        """returns the UI Meld with uiTile. A Board does not know about melds,
        so default is to return a Meld with only uiTile"""
        return Meld(uiTile)

    def meldVariants(self, uiTile, lowerHalf): # pylint: disable=no-self-use,unused-argument
        """all possible melds that could be meant by dragging/dropping uiTile"""
        return [Meld(uiTile)]

    def chooseVariant(self, uiTile, lowerHalf=False):
        """make the user choose from a list of possible melds for the target.
        The melds do not contain real Tiles, just the scoring strings."""
        variants = self.meldVariants(uiTile, lowerHalf)
        idx = 0
        if len(variants) > 1:
            menu = QMenu(m18n('Choose from'))
            for idx, variant in enumerate(variants):
                action = menu.addAction(variant.typeName())
                action.setData(QVariant(idx))
            if Internal.field.centralView.dragObject:
                menuPoint = QCursor.pos()
            else:
                menuPoint = uiTile.board.tileFaceRect().bottomRight()
                view = Internal.field.centralView
                menuPoint = view.mapToGlobal(view.mapFromScene(uiTile.mapToScene(menuPoint)))
            action = menu.exec_(menuPoint)
            if not action:
                return None
            idx = action.data().toInt()[0]
        return variants[idx]

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
        """if there is a uiTile at this place, return it"""
        for uiTile in self.uiTiles:
            if (uiTile.xoffset, uiTile.yoffset, uiTile.level) == (xoffset, yoffset, level):
                return uiTile

    def tilesByElement(self, element):
        """returns all child items holding a uiTile for element"""
        return list(x for x in self.uiTiles if x.tile == element)

    def rotatedLightSource(self):
        """the light source we need for the original uiTile before it is rotated"""
        lightSourceIndex = LIGHTSOURCES.index(self.lightSource)
        lightSourceIndex = (lightSourceIndex+self.sceneRotation() // 90)%4
        return LIGHTSOURCES[lightSourceIndex]

    def tileFacePos(self):
        """the face pos of a uiTile relative to its origin"""
        if not self.showShadows:
            return QPointF()
        lightSource = self.rotatedLightSource()
        xoffset = self.tileset.shadowWidth() - 1 if 'E' in lightSource else 0
        yoffset = self.tileset.shadowHeight() - 1 if 'S' in lightSource else 0
        return QPointF(xoffset, yoffset)

    def tileFaceRect(self):
        """the face rect of a uiTile relative its origin"""
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
        self.__xWidth = xWidth
        self.__xHeight = xHeight
        self.__yWidth = yWidth
        self.__yHeight = yHeight
        self.setGeometry()

    def setRect(self, width, height):
        """gives the board a fixed size in uiTile coordinates"""
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
        newX = self.__xWidth*width+self.__xHeight*height + offsets[0]
        newY = self.__yWidth*width+self.__yHeight*height + offsets[1]
        QGraphicsRectItem.setPos(self, newX, newY)

    @property
    def showShadows(self):
        """the active lightSource"""
        return self._showShadows

    @showShadows.setter
    def showShadows(self, value):
        """set active lightSource"""
        if self._showShadows != value:
            for uiTile in self.uiTiles:
                uiTile.setClippingFlags()
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
            for uiTile in self.uiTiles:
                self.placeTile(uiTile)
                uiTile.update()
            self.computeRect()
            if self.hasFocus:
                self.scene().focusBoard = self

    def focusRectWidth(self): # pylint: disable=no-self-use
        """how many tiles are in focus rect?"""
        return 1

    def shiftZ(self, level):
        """used for 3D: compute the needed shift for the uiTile.
        level is the vertical position. 0 is the face position on
        ground level, -1 is the imprint a uiTile makes on the
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
        """the current uiTile size"""
        return self._tileset.tileSize

    def faceSize(self):
        """the current face size"""
        return self._tileset.faceSize

    def __tilePlace(self, uiTile):
        """compute all properties for uiTile in this board: pos, scale, rotation
        and return them in a dict"""
        assert isinstance(uiTile, UITile)
        if not uiTile.scene():
            self.scene().addItem(uiTile)
        width = self.tileset.faceSize.width()
        height = self.tileset.faceSize.height()
        shiftZ = self.shiftZ(uiTile.level)
        boardPos = QPointF(uiTile.xoffset*width, uiTile.yoffset*height) + shiftZ
        scenePos = self.mapToScene(boardPos)
        uiTile.setDrawingOrder()
        return {'pos': scenePos, 'rotation': self.sceneRotation(), 'scale': self.scale()}

    def placeTile(self, uiTile):
        """places the uiTile in the scene. With direct=False, animate"""
        assert isinstance(uiTile, UITile)
        for pName, newValue in self.__tilePlace(uiTile).items():
            animation = uiTile.queuedAnimation(pName)
            if animation:
                curValue = animation.unpackValue(animation.endValue())
                if curValue != newValue:
                    # change a queued animation
                    animation.setEndValue(newValue)
            else:
                animation = uiTile.activeAnimation.get(pName, None)
                if isAlive(animation):
                    curValue = animation.unpackValue(animation.endValue())
                else:
                    curValue = uiTile.getValue(pName)
                if pName != 'scale' or abs(curValue - newValue) > 0.00001:
                    if curValue != newValue:
                        Animation(uiTile, pName, newValue)

    def addUITile(self, uiTile):
        """add uiTile to this board"""
        self.uiTiles.append(uiTile)

    def removeUITile(self, uiTile):
        """remove uiTile from this board"""
        self.uiTiles.remove(uiTile)
        if self.currentFocusTile == uiTile:
            self.focusTile = None

class CourtBoard(Board):
    """A Board that is displayed within the wall"""
    def __init__(self, width, height):
        Board.__init__(self, width, height, Internal.field.tileset)
        self.setAcceptDrops(True)

    def maximize(self):
        """make it as big as possible within the wall"""
        cWall = Internal.field.game.wall
        newSceneX = cWall[3].sceneBoundingRect().right()
        newSceneY = cWall[2].sceneBoundingRect().bottom()
        tileset = self.tileset
        xAvail = cWall[1].sceneBoundingRect().left() - newSceneX
        yAvail = cWall[0].sceneBoundingRect().top() - newSceneY
        shadowHeight = tileset.shadowHeight()
        shadowWidth = tileset.shadowWidth()
        if self.showShadows:
            # this should use the real shadow values from the wall because the wall
            # tiles are smaller than those in the CourtBoard but this should be
            # good enough
            newSceneX -= shadowHeight / 2 if 'W' in self.lightSource else 0
            newSceneY -= shadowWidth / 2 if 'N' in self.lightSource else 0
            xAvail -= shadowHeight if 'E' in self.lightSource else 0
            yAvail -= shadowWidth if 'S' in self.lightSource else 0
        xNeeded = self.width * tileset.faceSize.width()
        yNeeded = self.height * tileset.faceSize.height()
        xScaleFactor = xAvail / xNeeded
        yScaleFactor = yAvail / yNeeded
        QGraphicsRectItem.setPos(self, newSceneX, newSceneY)
        Board.setScale(self, min(xScaleFactor, yScaleFactor))
        for uiTile in self.uiTiles:
            uiTile.board.placeTile(uiTile)

class SelectorBoard(CourtBoard):
    """a board containing all possible tiles for selection"""
    # pylint: disable=too-many-public-methods
    def __init__(self):
        CourtBoard.__init__(self, 9, 5)
        self.lastReceived = None
        self.allSelectorTiles = []

    def checkTiles(self):
        """does not apply"""
        pass

    def load(self, game):
        """load the tiles according to game.ruleset"""
        for uiTile in self.uiTiles:
            uiTile.setBoard(None)
        self.uiTiles = []
        self.allSelectorTiles = list(UITile(x) for x in elements.all(game.ruleset))
        self.refill()

    def refill(self):
        """move all tiles back into the selector"""
        with Animated(False):
            for uiTile in self.allSelectorTiles:
                uiTile.tile = Tile(uiTile.tile.lower())
                self.__placeAvailable(uiTile)
                uiTile.dark = False
                uiTile.focusable = True
            self.focusTile = self.tilesByElement(Tile('c1'))[0]

    @property
    def name(self): # pylint: disable=no-self-use
        """for debugging messages"""
        return 'selector'

    def dragMoveEvent(self, event):
        """allow dropping only from handboards, not from self"""
        uiTile = event.mimeData().uiTile
        event.setAccepted(uiTile.board != self)

    def dropEvent(self, event):
        """drop a uiTile into the selector"""
        uiTile = event.mimeData().uiTile
        self.dropTile(uiTile)
        event.accept()

    def dropTile(self, uiTile, lowerHalf=False): # pylint: disable=unused-argument
        """drop uiTile into selector board"""
        senderHand = uiTile.board
        if senderHand == self:
            return
        meld = uiTile.board.uiMeldWithTile(uiTile)
        self.lastReceived = uiTile
        for myTile in meld:
            self.__placeAvailable(myTile)
            myTile.focusable = True
        senderHand.deselect(meld)
        (senderHand if senderHand.uiTiles else self).hasFocus = True
        self._noPen()
        animate()

    def assignUITiles(self, uiTile, meld):
        """generate a UIMeld. First uiTile is given, the rest should be as defined by meld"""
        assert isinstance(uiTile, UITile), uiTile
        result = UIMeld(uiTile)
        for tile in meld[1:]:
            baseTiles = list(x for x in self.tilesByElement(tile.lower()) if x not in result)
            result.append(baseTiles[0])
        return result

    def deselect(self, meld):
        """we are going to lose those tiles or melds"""

    def __placeAvailable(self, uiTile):
        """place the uiTile in the selector at its place"""
        # define coordinates and order for tiles:
        offsets = {'d': (3, 6, 'bgr'), 'f': (4, 5, 'eswn'), 'y': (4, 0, 'eswn'),
            'w': (3, 0, 'eswn'), 'b': (1, 0, '123456789'), 's': (2, 0, '123456789'),
            'c': (0, 0, '123456789')}
        row, baseColumn, order = offsets[uiTile.tile[0].lower()]
        column = baseColumn + order.index(uiTile.tile[1])
        uiTile.dark = False
        uiTile.setBoard(self, column, row)

    def meldVariants(self, uiTile, lowerHalf):
        """returns a list of possible variants based on meld. Those are logical melds."""
        # pylint: disable=too-many-locals
        assert isinstance(uiTile, UITile)
        wantedTile = uiTile.tile
        for selectorTile in self.uiTiles:
            selectorTile.tile = selectorTile.tile.lower()
        lowerName = wantedTile.lower()
        upperName = wantedTile.upper()
        if lowerHalf:
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
            if lowerHalf:
                variants.append(lowerName + upperName * 2 + lowerName)
            else:
                variants.append(lowerName * 4)
                variants.append(lowerName * 3 + upperName)
        if not wantedTile.isHonor() and wantedTile[1] < '8':
            chow2 = chiNext(wantedTile, 1)
            chow3 = chiNext(wantedTile, 2)
            chow2 = self.tilesByElement(chow2.lower())
            chow3 = self.tilesByElement(chow3.lower())
            if chow2 and chow3:
                baseChar = scName[0]
                baseValue = ord(scName[1])
                varStr = '%s%s%s%s%s' % (scName, baseChar, chr(baseValue+1), baseChar, chr(baseValue+2))
                variants.append(varStr)
        return [Meld(x) for x in variants]

class MimeData(QMimeData):
    """we also want to pass a reference to the moved meld"""
    def __init__(self, uiTile):
        QMimeData.__init__(self)
        self.uiTile = uiTile
        self.setText(str(uiTile))

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

    def wheelEvent(self, event):  # pylint: disable=no-self-use
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

    def __matchingTile(self, position, uiTile):
        """is position in the clickableRect of this uiTile?"""
        if not isinstance(uiTile, UITile):
            return False
        itemPos = uiTile.mapFromScene(self.mapToScene(position))
        return uiTile.board.tileFaceRect().contains(itemPos)

    def tileAt(self, position):
        """find out which uiTile is clickable at this position. Always
        returns a list. If there are several tiles above each other,
        return all of them, highest first"""
        allTiles = [x for x in self.items(position) if isinstance(x, UITile)]
        items = [x for x in allTiles if self.__matchingTile(position, x)]
        if not items:
            return None
        for item in items[:]:
            for other in allTiles:
                if (other.xoffset, other.yoffset) == (item.xoffset, item.yoffset):
                    if other.level > item.level:
                        items.append(other)
        return uniqueList(sorted(items, key=lambda x: -x.level))

    def mousePressEvent(self, event):
        """set blue focus frame"""
        tiles = self.tileAt(event.pos())
        if tiles:
            if event.modifiers() & Qt.ShiftModifier:
                for uiTile in tiles:
                    kprint('%s: board.level:%s' % (str(uiTile), uiTile.board.level))
            uiTile = tiles[0]
            board = uiTile.board
            isRemote = board.isHandBoard and board.player and not board.player.game.isScoringGame()
            if board.isHandBoard and not isRemote and not uiTile.isBonus():
                uiTile = uiTile.board.uiMeldWithTile(uiTile)[0]
            if uiTile.focusable:
                board.focusTile = uiTile
                board.hasFocus = True
                if isRemote:
                    Internal.field.clientDialog.buttons[0].setFocus()
                self.tilePressed = uiTile
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
        """selects the correct uiTile"""
        tilePressed = self.tilePressed
        self.tilePressed = None
        if tilePressed:
            board = tilePressed.board
            if board and board.tileDragEnabled:
                self.dragObject = self.drag(tilePressed)
                self.dragObject.exec_(Qt.MoveAction)
                self.dragObject = None
                return
        return QGraphicsView.mouseMoveEvent(self, event)

    def drag(self, uiTile):
        """returns a drag object"""
        drag = QDrag(self)
        mimeData = MimeData(uiTile)
        drag.setMimeData(mimeData)
        tRect = uiTile.boundingRect()
        tRect = self.viewportTransform().mapRect(tRect)
        pmapSize = QSize(tRect.width() * uiTile.scale, tRect.height() * uiTile.scale)
        pMap = uiTile.pixmapFromSvg(pmapSize)
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

    @property
    def name(self): # pylint: disable=no-self-use
        """to be used in debug output"""
        return "discardBoard"

    def hide(self):
        """remove all uiTile references so they can be garbage collected"""
        self.lastDiscarded = None
        CourtBoard.hide(self)

    def setRandomPlaces(self, randomGenerator):
        """precompute random positions"""
        self.__places = [(x, y) for x in range(self.width) for y in range(self.height)]
        randomGenerator.shuffle(self.__places)

    def discardTile(self, uiTile):
        """add uiTile to a random position"""
        assert isinstance(uiTile, UITile)
        uiTile.setBoard(self, *self.__places.pop(0))
        uiTile.dark = False
        uiTile.focusable = False
        self.focusTile = uiTile
        self.hasFocus = True
        self.lastDiscarded = uiTile

    def dropEvent(self, event):
        """drop a uiTile into the discard board"""
        # TODO: now that tiles are top level scene items, maybe drag them
        # directly. Draggings melds: QGraphicsItemGroup?
        uiTile = event.mimeData().uiTile
        assert isinstance(uiTile, UITile), uiTile
        uiTile.setPos(event.scenePos() - uiTile.boundingRect().center())
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
           this will violate the assertion in UITile.keyPressEvent """
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
                and board.isVisible()
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
            focusTile.setFocus()
            self.placeFocusRect()
        self.focusRect.setVisible(self.__focusRectVisible())

    def placeFocusRect(self):
        """show a blue rect around uiTile"""
        board = self._focusBoard
        if isAlive(board) and board.isVisible() and board.focusTile:
            rect = board.tileFaceRect()
            rect.setWidth(rect.width()*board.focusRectWidth())
            self.focusRect.setRect(rect)
            self.focusRect.setPos(board.focusTile.pos)
            self.focusRect.setRotation(board.sceneRotation())
            self.focusRect.setScale(board.scale())
            self.focusRect.show()
        else:
            self.focusRect.hide()

    def graphicsTileItems(self):
        """returns all UITile in the scene"""
        return (x for x in self.items() if isinstance(x, UITile))

    def nonTiles(self):
        """returns all other items in the scene"""
        return (x for x in self.items() if not isinstance(x, UITile))

    def removeTiles(self):
        """remove all tiles from scene"""
        for item in self.graphicsTileItems():
            self.removeItem(item)
        self.focusRect.hide()
