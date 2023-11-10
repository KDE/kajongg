# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2014 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

from qt import Qt, QPointF, QPoint, QRectF, QMimeData, QSize
from qt import QGraphicsRectItem, QSizePolicy, QFrame, QFont
from qt import QGraphicsView, QLabel
from qt import QColor, QPainter, QDrag, QPixmap, QStyleOptionGraphicsItem, QPen, QBrush
from qt import QFontMetrics, QGraphicsObject
from qt import QMenu, QCursor
from qt import QGraphicsSvgItem
from tileset import Tileset
from tile import Tile, elements
from uitile import UITile, UIMeld
from guiutil import Painter, rotateCenter, sceneRotation
from meld import Meld
from animation import AnimationSpeed, animate, AnimatedMixin
from message import Message

from util import stack, uniqueList
from log import logDebug, logException
from mi18n import i18n, i18nc
from common import LIGHTSOURCES, Internal, Debug, isAlive, ReprMixin
from common import DrawOnTopMixin
from wind import Wind, East


class WindDisc(AnimatedMixin, QGraphicsObject, ReprMixin, DrawOnTopMixin):

    """a round wind tile"""

    roundWindColor = QColor(235, 235, 173)
    whiteColor = QColor('white')

    def __init__(self, wind, parent=None):
        """generate new wind disc"""
        super().__init__()
        assert not parent
        assert isinstance(wind, Wind), 'wind {}  must be a real Wind but is {}'.format(
            wind, type(wind))
        self.__wind = wind
        self.__brush = self.whiteColor
        self.board = None

    def debug_name(self):
        """for identification in animations"""
        return self.__wind.tile.name2()

    def moveDict(self):
        """a dict with attributes for the new position,
        normally pos, rotation and scale"""
        sideCenter = self.board.center()
        boardPos = QPointF(
            sideCenter.x() * 1.63,
            sideCenter.y() - self.boundingRect().height() / 2.0)
        scenePos = self.board.mapToScene(boardPos)
        return {'pos': scenePos, 'rotation': sceneRotation(self.board)}

    @property
    def wind(self):
        """our wind"""
        return self.__wind

    @property
    def prevailing(self):
        """is this the prevailing wind?"""
        return self.__brush is self.roundWindColor

    @prevailing.setter
    def prevailing(self, value):
        if isinstance(value, bool):
            newPrevailing = value
        else:
            newPrevailing = self.wind == Wind.all4[value % 4]
        self.__brush = self.roundWindColor if newPrevailing else self.whiteColor

    def paint(self, painter, unusedOption, unusedWidget=None):
        """paint the disc"""
        with Painter(painter):
            painter.setBrush(self.__brush)
            size = int(Internal.scene.windTileset.faceSize.height())
            ellRect = QRectF(QPointF(), QPointF(size, size))
            painter.drawEllipse(ellRect)
            renderer = Internal.scene.windTileset.renderer()
            painter.translate(12, 12)
            painter.scale(0.60, 0.60)
            renderer.render(painter, self.wind.discSvgName, self.boundingRect())

    def boundingRect(self):
        """define the part of the tile we want to see"""
        size = int(Internal.scene.windTileset.faceSize.height() * 1.1)
        return QRectF(QPointF(), QPointF(size, size))

    def __str__(self):
        """for debugging"""
        return 'WindDisc(%s x/y= %.1f/%1f)' % (
            self.debug_name(), self.x(), self.y())


class WindLabel(QLabel):

    """QLabel holding the wind tile"""

    def __init__(self, wind=None, roundsFinished=0, parent=None):
        QLabel.__init__(self, parent)
        self.__wind = None
        if wind is None:
            wind = East
        self.__roundsFinished = roundsFinished
        self.wind = wind

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

    @property
    def roundsFinished(self):
        """setting roundsFinished also changes graphics if needed"""
        return self.__roundsFinished

    @roundsFinished.setter
    def roundsFinished(self, roundsFinished):
        """setting roundsFinished also changes graphics if needed"""
        if self.__roundsFinished != roundsFinished:
            self.__roundsFinished = roundsFinished
            self._refresh()

    def _refresh(self):
        """update graphics"""
        self.setPixmap(self.genWindPixmap())

    def genWindPixmap(self):
        """prepare wind tiles"""
        pwind = WindDisc(self.__wind)
        pwind.prevailing = self.__wind == Wind.all4[min(self.__roundsFinished, 3)]
        pMap = QPixmap(40, 40)
        pMap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pMap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.scale(0.40, 0.40)
        pwind.paint(painter, QStyleOptionGraphicsItem())
        for child in pwind.childItems():
            if isinstance(child, QGraphicsSvgItem):
                with Painter(painter):
                    painter.translate(child.mapToParent(0.0, 0.0))
                    child.paint(painter, QStyleOptionGraphicsItem())
        return pMap


class Board(QGraphicsRectItem, ReprMixin):

    """ a board with any number of positioned tiles"""
    # pylint: disable=too-many-instance-attributes

    penColor = QColor('black')

    arrows = [Qt.Key.Key_Left, Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_Right]

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
        self._tileset = Tileset()
        self.tileset = tileset
        self.level = 0
        Internal.Preferences.addWatch('showShadows', self.showShadowsChanged)

    def debug_name(self):
        """default board name, used for debugging messages"""
        return 'board'

    def __str__(self):
        """for debugging"""
        return self.debug_name()

    def setVisible(self, value):
        """also update focusRect if it belongs to this board"""
        if self.scene() and isAlive(self):
            QGraphicsRectItem.setVisible(self, value)
            self.scene().focusRect.refresh()

    def hide(self):
        """remove all uiTile references so they can be garbage collected"""
        for uiTile in self.uiTiles:
            uiTile.hide()
        self.uiTiles = []
        self._focusTile = None
        if isAlive(self):
            self.setVisible(False)

    def autoSelectTile(self):
        """call this when Kajongg should automatically focus
        on an appropriate uiTile"""
        focusCandidates = self._focusableTiles()
        if focusCandidates:
            firstCandidate = focusCandidates[0]
            if self._focusTile not in focusCandidates:
                focusCandidates = [x for x in focusCandidates if x.sortKey() >= self.__prevPos]
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
            assert uiTile.isKnown, uiTile
            if not isinstance(uiTile.board, DiscardBoard):
                assert uiTile.focusable, uiTile
            self.__prevPos = uiTile.sortKey()
        self._focusTile = uiTile
        if self._focusTile and self._focusTile.tile.name2() in Debug.focusable:
            logDebug('%s: new focus uiTile %s from %s' % (
                self.debug_name(), self._focusTile.tile if self._focusTile else 'None', stack('')[-1]))
        if self.hasLogicalFocus:
            self.scene().focusBoard = self

    def setEnabled(self, enabled):
        """enable/disable this board"""
        self.tileDragEnabled = enabled
        QGraphicsRectItem.setEnabled(self, enabled)

    def _focusableTiles(self, sortDir=Qt.Key.Key_Right):
        """return a list of all tiles in this board sorted such that
        moving in the sortDir direction corresponds to going to
        the next list element.
        respect board orientation: Right Arrow should always move right
        relative to the screen, not relative to the board"""
        return sorted((x for x in self.uiTiles if x.focusable), key=lambda x: x.sortKey(sortDir))

    @property
    def hasLogicalFocus(self):
        """defines if this board should show a focusRect
        if another board has focus, setting this to False does
        not change scene.focusBoard

        Up to May 2021, this was called hasFocus, overriding QGraphicsItem.hasFocus
        but pylint did not like that."""
        return self.scene() and self.scene().focusBoard == self and self._focusTile

    @hasLogicalFocus.setter
    def hasLogicalFocus(self, value):
        """set focus on this board"""
        if isAlive(self):
            scene = self.scene()
            if isAlive(scene):
                if scene.focusBoard == self or value:
                    if self.focusTile:
                        assert self.focusTile.board == self, '%s not in self %s' % (
                            self.focusTile, self)
                if value:
                    scene.focusBoard = self

    @staticmethod
    def mapChar2Arrow(event):
        """map the keys hjkl to arrows like in vi and konqueror"""
        key = event.key()
        if key in Board.arrows:
            return key
        charArrows = i18nc(
            'kajongg:arrow keys hjkl like in konqueror',
            'hjklHJKL')
        key = event.text()
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
            tiles = [
                x for x in tiles if (x.xoffset,
                                     x.yoffset) != oldPos or x == self.focusTile]
            assert tiles, [str(x) for x in self.uiTiles]
            tiles.append(tiles[0])
            self.focusTile = tiles[tiles.index(self.focusTile) + 1]

    def mapMouseTile(self, uiTile):
        """map the pressed tile to the wanted tile. For melds, this would
        be the first tile no matter which one is pressed"""
        return uiTile

    def uiMeldWithTile(self, uiTile):
        """return the UI Meld with uiTile. A Board does not know about melds,
        so default is to return a Meld with only uiTile"""
        return UIMeld(uiTile)

    def meldVariants(self, tile, lowerHalf):  # pylint: disable=unused-argument
        """all possible melds that could be meant by dragging/dropping uiTile"""
        return [Meld(tile)]

    def chooseVariant(self, uiTile, lowerHalf=False):
        """make the user choose from a list of possible melds for the target.
        The melds do not contain real Tiles, just the scoring strings."""
        variants = self.meldVariants(uiTile, lowerHalf)
        idx = 0
        if len(variants) > 1:
            menu = QMenu(i18n('Choose from'))
            for idx, variant in enumerate(variants):
                action = menu.addAction(variant.typeName())
                action.setData(idx)
            if Internal.scene.mainWindow.centralView.dragObject:
                menuPoint = QCursor.pos()
            else:
                menuPoint = uiTile.board.tileFaceRect().bottomRight()
                view = Internal.scene.mainWindow.centralView
                menuPoint = view.mapToGlobal(
                    view.mapFromScene(uiTile.mapToScene(menuPoint)))
            action = menu.exec_(menuPoint)
            if not action:
                return None
            idx = action.data()
        return variants[idx]

    def dragEnterEvent(self, unusedEvent):
        """drag enters the HandBoard: highlight it"""
        self.setPen(QPen(self.penColor))

    def dragLeaveEvent(self, unusedEvent):
        """drag leaves the HandBoard"""
        self._noPen()

    def _noPen(self):
        """remove pen for this board. The pen defines the border"""
        if Debug.graphics:
            self.setPen(QPen(self.penColor))
        else:
            self.setPen(QPen(Qt.PenStyle.NoPen))

    def tileAt(self, xoffset, yoffset, level=0):
        """if there is a uiTile at this place, return it"""
        for uiTile in self.uiTiles:
            if (uiTile.xoffset, uiTile.yoffset, uiTile.level) == (xoffset, yoffset, level):
                return uiTile
        return None

    def tilesByElement(self, element):
        """return all child items holding a uiTile for element"""
        return [x for x in self.uiTiles if x.tile is element]

    def rotatedLightSource(self):
        """the light source we need for the original uiTile before it is rotated"""
        lightSourceIndex = LIGHTSOURCES.index(self.lightSource)
        lightSourceIndex = (lightSourceIndex + sceneRotation(self) // 90) % 4
        return LIGHTSOURCES[lightSourceIndex]

    def tileFacePos(self, showShadows=None):
        """the face pos of a uiTile relative to its origin"""
        if showShadows is None:
            showShadows = Internal.Preferences.showShadows
        if not showShadows:
            return QPointF()
        lightSource = self.rotatedLightSource()
        xoffset = self.tileset.shadowWidth() - 1 if 'E' in lightSource else 0
        yoffset = self.tileset.shadowHeight() - 1 if 'S' in lightSource else 0
        return QPointF(xoffset, yoffset)

    def tileFaceRect(self):
        """the face rect of a uiTile relative its origin"""
        return QRectF(self.tileFacePos(), self.tileset.faceSize)

    def setTilePos(self, xWidth=0, xHeight=0, yWidth=0, yHeight=0):
        """set the position in the parent item expressing the position in tile face units.
        The X position is xWidth*facewidth + xHeight*faceheight, analog for Y"""
        self.__xWidth = xWidth
        self.__xHeight = xHeight
        self.__yWidth = yWidth
        self.__yHeight = yHeight
        self.setGeometry()

    def setBoardRect(self, width, height):
        """gives the board a fixed size in uiTile coordinates"""
        self.__fixedWidth = width
        self.__fixedHeight = height
        self.computeRect()

    def computeRect(self):
        """translate from our rect coordinates to scene coord"""
        sizeX = self.tileset.faceSize.width() * self.__fixedWidth
        sizeY = self.tileset.faceSize.height() * self.__fixedHeight
        if Internal.Preferences.showShadows:
            sizeX += self.tileset.shadowWidth() + \
                2 * self.tileset.shadowHeight()
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
        if not Internal.Preferences.showShadows:
            offsets = (0, 0)
        elif self.isHandBoard:
            offsets = (-self.tileset.shadowHeight() * 2, 0)
        else:
            offsets = self.tileset.shadowOffsets(
                self._lightSource,
                sceneRotation(self))
        newX = self.__xWidth * width + self.__xHeight * height + offsets[0]
        newY = self.__yWidth * width + self.__yHeight * height + offsets[1]
        self.setPos(newX, newY)

    def showShadowsChanged(self, unusedOldValue, newValue):
        """set active lightSource"""
        for uiTile in self.uiTiles:
            uiTile.setClippingFlags()
        self._reload(self.tileset, showShadows=newValue)

    @property
    def lightSource(self):
        """the active lightSource"""
        return self._lightSource

    @lightSource.setter
    def lightSource(self, lightSource):
        """set active lightSource"""
        if self._lightSource != lightSource:
            if lightSource not in LIGHTSOURCES:
                logException('lightSource %s illegal' % lightSource)
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
            showShadows = Internal.Preferences.showShadows
        if (self._tileset != tileset
                or self.__yHeight == 0
                or self._lightSource != lightSource
                or Internal.Preferences.showShadows != showShadows):
            self.prepareGeometryChange()
            self._tileset = tileset
            self._lightSource = lightSource
            self.setGeometry()
            for child in self.childItems():
                if isinstance(child, Board):
                    child.lightSource = lightSource
                    child.showShadows = showShadows
            for uiTile in self.uiTiles:
                self.placeTile(uiTile)
                uiTile.update()
            self.computeRect()
            if self.hasLogicalFocus:
                self.scene().focusBoard = self

    def focusRectWidth(self):
        """how many tiles are in focus rect?"""
        return 1

    def shiftZ(self, level):
        """used for 3D: compute the needed shift for the uiTile.
        level is the vertical position. 0 is the face position on
        ground level, -1 is the imprint a uiTile makes on the
        surface it stands on"""
        if not Internal.Preferences.showShadows:
            return QPointF()
        shiftX = 0
        shiftY = 0
        if level != 0:
            lightSource = self.rotatedLightSource()
            stepX = level * self.tileset.shadowWidth() / 2
            stepY = level * self.tileset.shadowHeight() / 2
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

    def placeTile(self, uiTile):
        """places the uiTile in the scene"""
        assert isinstance(uiTile, UITile)
        assert uiTile.board == self
        uiTile.setupAnimations()

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
    penColor = QColor('green')

    def __init__(self, width, height):
        Board.__init__(self, width, height, Tileset.current())
        self.setAcceptDrops(True)

    def maximize(self):
        """make it as big as possible within the wall"""
        cWall = Internal.scene.game.wall
        newSceneX = cWall[3].sceneBoundingRect().right()
        newSceneY = cWall[2].sceneBoundingRect().bottom()
        tileset = self.tileset
        xAvail = cWall[1].sceneBoundingRect().left() - newSceneX
        yAvail = cWall[0].sceneBoundingRect().top() - newSceneY
        shadowHeight = tileset.shadowHeight()
        shadowWidth = tileset.shadowWidth()
        if Internal.Preferences.showShadows:
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
        self.setPos(newSceneX, newSceneY)
        self.setScale(min(xScaleFactor, yScaleFactor))
        for uiTile in self.uiTiles:
            uiTile.board.placeTile(uiTile)


class SelectorBoard(CourtBoard):

    """a board containing all possible tiles for selection"""

    def __init__(self):
        CourtBoard.__init__(self, 9, 5)
        self.allSelectorTiles = []

    def checkTiles(self):
        """does not apply"""

    def load(self, game):
        """load the tiles according to game.ruleset"""
        for uiTile in self.uiTiles:
            uiTile.setBoard(None)
        self.uiTiles = []
        self.allSelectorTiles = [UITile(x) for x in elements.all(game.ruleset)]
        self.refill()

    def refill(self):
        """move all tiles back into the selector"""
        with AnimationSpeed():
            for uiTile in self.allSelectorTiles:
                uiTile.change_name(uiTile.exposed)
                self.__placeAvailable(uiTile)
                uiTile.dark = False
                uiTile.focusable = True
            self.focusTile = self.tilesByElement(Tile('c1'))[0]

    def debug_name(self):
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

    def dropTile(self, uiTile, lowerHalf=False):  # pylint: disable=unused-argument
        """drop uiTile into selector board"""
        uiMeld = uiTile.board.uiMeldWithTile(uiTile)
        self.dropMeld(uiMeld)

    def dropMeld(self, uiMeld):
        """drop uiMeld into selector board"""
        senderHand = uiMeld[0].board
        if senderHand == self:
            return
        for myTile in uiMeld:
            self.__placeAvailable(myTile)
            myTile.focusable = True
        senderHand.deselect(uiMeld)
        (senderHand if senderHand.uiTiles else self).hasLogicalFocus = True
        self._noPen()
        animate()

    def assignUITiles(self, uiTile, meld):
        """generate a UIMeld. First uiTile is given, the rest should be as defined by meld"""
        assert isinstance(uiTile, UITile), uiTile
        result = UIMeld(uiTile)
        for tile in meld[1:]:
            baseTiles = [
                x for x in self.tilesByElement(
                    tile.exposed) if x not in result]
            result.append(baseTiles[0])
        return result

    def deselect(self, meld):
        """we are going to lose those tiles or melds"""

    def __placeAvailable(self, uiTile):
        """place the uiTile in the selector at its place"""
        # define coordinates and order for tiles:
        offsets = {
            Tile.dragon: (3, 6, Tile.dragons),
            Tile.flower: (4, 5, Tile.winds),
            Tile.season: (4, 0, Tile.winds),
            Tile.wind: (3, 0, Tile.winds),
            Tile.bamboo: (1, 0, '123456789'),
            Tile.stone: (2, 0, '123456789'),
            Tile.character: (0, 0, '123456789')}
        row, baseColumn, order = offsets[uiTile.lowerGroup]
        column = baseColumn + order.index(uiTile.char)
        uiTile.dark = False
        uiTile.setBoard(self, column, row)

    def meldVariants(self, tile, lowerHalf):
        """return a list of possible variants based on meld. Those are logical melds."""
        assert isinstance(tile, UITile)
        wantedTile = tile.tile
        for selectorTile in self.uiTiles:
            selectorTile.change_name(selectorTile.exposed)
        lowerName = wantedTile.exposed
        upperName = wantedTile.concealed
        if lowerHalf:
            scName = upperName
        else:
            scName = lowerName
        result = [scName.single]
        baseTiles = len(self.tilesByElement(lowerName))
        if baseTiles >= 2:
            result.append(scName.pair)
        if baseTiles >= 3:
            result.append(scName.pung)
        if baseTiles == 4:
            if lowerHalf:
                result.append(lowerName.kong.declared)
            else:
                result.append(lowerName.kong)
                result.append(lowerName.kong.exposedClaimed)
        if wantedTile.isNumber and wantedTile.value < 8:
            chow2 = scName.nextForChow
            chow3 = chow2.nextForChow
            if self.tilesByElement(chow2.exposed) and self.tilesByElement(chow3.exposed):
                result.append(scName.chow)
        # result now holds a list of melds
        return result


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
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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

    def wheelEvent(self, event):
        """we do not want scrolling for the scene view.
        Instead scrolling down changes perspective like in kmahjongg"""
        angleX = event.angleDelta().x()
        angleY = event.angleDelta().y()
        if angleX > 15 or angleY > -50:
            return
        Internal.mainWindow.changeAngle()

    def resizeEvent(self, unusedEvent):
        """scale the scene and its background for new view size"""
        Internal.Preferences.callTrigger(
            'tilesetName')  # this redraws and resizes
        Internal.Preferences.callTrigger('backgroundName')  # redraw background
        if self.scene():
            self.fitInView(
                self.scene().itemsBoundingRect(),
                Qt.AspectRatioMode.KeepAspectRatio)
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
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                for uiTile in tiles:
                    print(
                        '%s: board.level:%s' %
                        (str(uiTile), uiTile.board.level))
            board = tiles[0].board
            uiTile = board.mapMouseTile(tiles[0])
            if uiTile.focusable:
                board.focusTile = uiTile
                board.hasLogicalFocus = True
                if hasattr(Internal.scene, 'clientDialog'):
                    if Internal.scene.clientDialog:
                        Internal.scene.clientDialog.buttons[0].setFocus()
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
                self.dragObject.exec_(Qt.DropAction.MoveAction)
                self.dragObject = None
                return None
        return QGraphicsView.mouseMoveEvent(self, event)

    def drag(self, uiTile):
        """return a drag object"""
        drag = QDrag(self)
        mimeData = MimeData(uiTile)
        drag.setMimeData(mimeData)
        tRect = uiTile.boundingRect()
        tRect = self.viewportTransform().mapRect(tRect)
        pmapSize = QSize(
            int(tRect.width() * uiTile.scale),
            int(tRect.height() * uiTile.scale))
        pMap = uiTile.pixmapFromSvg(pmapSize)
        drag.setPixmap(pMap)
        drag.setHotSpot(QPoint(pMap.width() // 2, pMap.height() // 2))
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
        self.setPos(self.side.center())
        rotation = self.side.rotation()
        rotateCenter(self, -rotation)
        xOffset = -self.rect().width() / 2
        yOffset = -self.rect().height() / 2
        if rotation % 180 == 0:
            self.moveBy(xOffset, yOffset * 4)
        else:
            self.moveBy(xOffset, yOffset)

    def paint(self, painter, unusedOption, unusedWidget):
        """override predefined paint"""
        painter.setFont(self.font)
        painter.fillRect(self.rect(), QBrush(QColor('yellow')))
        painter.drawText(self.rect(), self.msg)


class DiscardBoard(CourtBoard):

    """A special board for discarded tiles"""
    penColor = QColor('orange')

    def __init__(self):
        CourtBoard.__init__(self, 11, 9)
        self.__places = None
        self.__lastDiscarded = None
        self.__discardTilesOrderedLeaveHole = True

    def debug_name(self):
        """to be used in debug output"""
        return "discardBoard"

    def hide(self):
        """remove all uiTile references so they can be garbage collected"""
        self.__lastDiscarded = None
        CourtBoard.hide(self)

    def setRandomPlaces(self, game):
        """precompute random positions"""
        self.__places = [(x, y) for x in range(self.width)
                         for y in range(self.height)]
        if game.ruleset.discardTilesOrdered:
            self.__places.sort(key=lambda p: p[0] + p[1] * 1000)
        else:
            game.randomGenerator.shuffle(self.__places)
        self.__discardTilesOrderedLeaveHole = game.ruleset.discardTilesOrderedLeaveHole

    def discardTile(self, uiTile):
        """add uiTile to the discard board"""
        assert isinstance(uiTile, UITile)
        uiTile.setBoard(self, *self.__places.pop(0))
        uiTile.dark = False
        uiTile.focusable = False
        self.focusTile = uiTile
        self.hasLogicalFocus = True
        self.__lastDiscarded = uiTile

    def claimDiscard(self):
        """claim last discarded tile"""
        result = self.__lastDiscarded
        self.__lastDiscarded = None
        if not self.__discardTilesOrderedLeaveHole:
            self.__places.insert(0, (result.xoffset, result.yoffset))
        return result

    def dropEvent(self, event):
        """drop a uiTile into the discard board

        The user uses the mouse for discarding a tile"""
        uiTile = event.mimeData().uiTile
        assert isinstance(uiTile, UITile), uiTile
        uiTile.setPos(event.scenePos() - uiTile.boundingRect().center())
        Internal.scene.clientDialog.selectButton(Message.Discard)
        event.accept()
        self._noPen()
