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
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
"""

from PyQt4.QtCore import QPointF, QRectF, QVariant
from PyQt4.QtGui import QGraphicsRectItem
from PyQt4.QtGui import QMenu, QCursor
from PyQt4.QtGui import QGraphicsSimpleTextItem
from tile import Tile, swapTitle
from meld import Meld, EXPOSED, CONCEALED, REST, tileKey, elementKey, shortcuttedMeldName
from scoringengine import HandContent
from board import Board, rotateCenter

from util import m18n
import common
from common import InternalParameters
from animation import animate

class TileAttr(object):
    """a helper class for syncing the hand board, holding relevant tile attributes"""
    def __init__(self, element, xoffset=None, yoffset=None):
        if isinstance(element, Tile):
            self.element = element.element
            self.xoffset = element.xoffset
            self.yoffset = element.yoffset
            self.dark = element.dark
            self.focusable = element.focusable
        else:
            self.element = element
            self.xoffset = xoffset
            self.yoffset = yoffset
            self.dark = False
            self.focusable = True
            isScoringGame = InternalParameters.field.game.isScoringGame()
            if yoffset == 0:
                self.dark = element.istitle()
            else:
                self.dark = element == 'Xy' or isScoringGame

    def __str__(self):
        return '%s %.1f/%.1f%s%s' % (self.element, self.xoffset, self.yoffset, ' dark' if self.dark else '', \
            ' focusable' if self.focusable else '')

class HandBoard(Board):
    """a board showing the tiles a player holds"""
    # pylint: disable=R0904
    # pylint - we need more than 40 public methods
    # pylint: disable=R0902
    # pylint - we need more than 10 instance attributes
    def __init__(self, player):
        self.exposedMeldDistance = 0.2
        self.concealedMeldDistance = 0.0
        self.lowerY = 1.0
        self.player = player
        Board.__init__(self, 15.4, 2.0, InternalParameters.field.tileset)
        self.isHandBoard = True
        self.tileDragEnabled = False
        self.setParentItem(player.front)
        self.setAcceptDrops(True)
        self.__moveHelper = None
        self.__sourceView = None
        self.rearrangeMelds = common.PREF.rearrangeMelds
        self.showShadows = common.PREF.showShadows

    def computeRect(self):
        """also adjust the scale for maximum usage of space"""
        Board.computeRect(self)
        sideRect = self.player.front.boundingRect()
        boardRect = self.boundingRect()
        scale = (sideRect.width() + sideRect.height()) / (boardRect.width() - boardRect.height())
        self.setScale(scale)

    def name(self):
        """for debugging messages"""
        return self.player.name

    @apply
    # pylint: disable=E0202
    def showShadows():
        """the active lightSource"""
        def fget(self):
            # pylint: disable=W0212
            return self._showShadows
        def fset(self, value):
            """set active lightSource"""
            # pylint: disable=W0212
            if self._showShadows is None or self._showShadows != value:
                if value:
                    self.setPos(yHeight= 1.5)
                else:
                    self.setPos(yHeight= 1.0)
                if value:
                    self.lowerY = 1.2
                else:
                    self.lowerY = 1.0
                self.setRect(15.4, 1.0 + self.lowerY)
                self._reload(self.tileset, showShadows=value)
                self.sync()
        return property(**locals())

    @apply
    def rearrangeMelds(): # pylint: disable=E0202
        """when setting this, concealed melds are grouped"""
        def fget(self):
            return bool(self.concealedMeldDistance)
        def fset(self, rearrangeMelds):
            if rearrangeMelds != self.rearrangeMelds:
                self.concealedMeldDistance = self.exposedMeldDistance if rearrangeMelds else 0.0
                self._reload(self.tileset, self._lightSource) # pylint: disable=W0212
                self.sync() # pylint: disable=W0212
        return property(**locals())

    def setEnabled(self, enabled):
        """enable/disable this board"""
        self.tileDragEnabled = enabled and \
        (self.player.game.isScoringGame() or self.player == self.player.game.myself)
        QGraphicsRectItem.setEnabled(self, enabled)

    def showMoveHelper(self, visible=True):
        """show help text In empty HandBoards"""
        if visible:
            if not self.__moveHelper:
                splitter = QGraphicsRectItem(self)
                hbCenter = self.rect().center()
                splitter.setRect(hbCenter.x() * 0.5, hbCenter.y(), hbCenter.x() * 1, 1)
                helpItems = [splitter]
                for name, yFactor in [(m18n('Move Exposed Tiles Here'), 0.5),
                                        (m18n('Move Concealed Tiles Here'), 1.5)]:
                    helper = QGraphicsSimpleTextItem(name, self)
                    helper.setScale(3)
                    nameRect = QRectF()
                    nameRect.setSize(helper.mapToParent(helper.boundingRect()).boundingRect().size())
                    center = QPointF(hbCenter)
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

    def focusRectWidth(self):
        """how many tiles are in focus rect? We want to focus
        the entire meld"""
        if not self.player.game.isScoringGame():
            # network game: always make only single tiles selectable
            return 1
        if self.focusTile.isBonus():
            return 1
        return len(self.meldWithTile(self.focusTile))

    def __str__(self):
        return self.player.scoringString()

    def meldWithTile(self, tile):
        """returns the meld holding tile"""
        if tile.isBonus():
            return [tile]
        for meld in self.player.concealedMelds + self.player.exposedMelds:
            if tile in meld.tiles:
                return meld
        assert False, 'meldWithThile: %s' % str(tile)

    def dragObject(self, tile):
        """if user wants to drag tile, he really might want to drag the meld"""
        if self.player.game.isScoringGame() and not tile.isBonus():
            return None, self.meldWithTile(tile)
        return tile, None

    def removing(self, tile=None, meld=None):
        """Called before the destination board gets those tiles or melds"""
        pass

    def remove(self, tile=None, meld=None):
        """return tile or meld to the selector board"""
        assert not (tile and meld), (str(tile), str(meld))
        if not (self.focusTile and self.focusTile.graphics.hasFocus()):
            hadFocus = False
        elif tile:
            hadFocus = self.focusTile == tile
        else:
            hadFocus = self.focusTile == meld[0]
        self.player.remove(tile, meld)
        if hadFocus:
            self.focusTile = None # force calculation of new focusTile
        InternalParameters.field.handSelectorChanged(self)

    def dragMoveEvent(self, event):
        """allow dropping of tile from ourself only to other state (open/concealed)"""
        tile = event.mimeData().tile or event.mimeData().meld[0]
        localY = self.mapFromScene(QPointF(event.scenePos())).y()
        centerY = self.rect().height()/2.0
        newLowerHalf = localY >= centerY
        noMansLand = centerY / 6
        if -noMansLand < localY - centerY < noMansLand and not tile.isBonus():
            doAccept = False
        elif tile.board != self:
            doAccept = True
        elif tile.isBonus():
            doAccept = False
        else:
            oldLowerHalf = tile.board.isHandBoard and tile in tile.board.lowerHalfTiles()
            doAccept = self.player.game.isScoringGame() and oldLowerHalf != newLowerHalf
        event.setAccepted(doAccept)

    def dropEvent(self, event):
        """drop into this handboard. Used only when isScoringGame"""
        tile = event.mimeData().tile
        meld = event.mimeData().meld
        lowerHalf = self.mapFromScene(QPointF(event.scenePos())).y() >= self.rect().height()/2.0
        if self.dropHere(tile, meld, lowerHalf):
            event.accept()
        else:
            event.ignore()
        self._noPen()

    def dropHere(self, tile, meld, lowerHalf):
        """drop meld or tile into lower or upper half of our hand"""
        if meld:
            meld.state = CONCEALED if lowerHalf else EXPOSED
            result = self.receive(meld=meld)
        else:
            if lowerHalf and not tile.isBonus():
                tile.element = tile.element.capitalize()
            result = self.receive(tile)
        animate()
        return result

    def receive(self, tile=None, meld=None):
        """receive a tile or meld and return the meld this tile becomes part of"""
        if tile:
            if tile.isBonus():
                if tile.board == self:
                    return
                meld = Meld(tile)
            else:
                meld = self.__chooseDestinationMeld(tile, meld) # from selector board.
                # if the source is a Handboard, we got a Meld, not a Tile
                if not meld:
                    # user pressed ESCAPE
                    return None
            assert not tile.element.istitle() or meld.pairs[0] != 'Xy', tile
            tile = None
        senderBoard = meld[0].board
        senderBoard.removing(meld=meld)
        if senderBoard == self:
            self.player.moveMeld(meld)
            self.sync()
        else:
            self.player.addMeld(meld)
            self.sync(adding=meld.tiles)
            senderBoard.remove(meld=meld)
        meld.tiles = sorted(meld.tiles, key=lambda x: x.xoffset)
        if any(x.focusable for x in meld.tiles):
            for idx, tile in enumerate(meld.tiles):
                tile.focusable = idx == 0
        return meld

    def lowerHalfTiles(self):
        """returns a list with all single tiles of the lower half melds without boni"""
        return list(x for x in self.tiles if x.yoffset > 0)

    def newTilePositions(self):
        """returns list(TileAttr) for all tiles except bonus tiles.
        The tiles are not associated to any board."""
        result = list()
        isScoringGame = self.player.game.isScoringGame()
        newUpperMelds = self.player.exposedMelds[:]
        if isScoringGame:
            newLowerMelds = self.player.concealedMelds[:]
        else:
            if self.player.concealedMelds:
                newLowerMelds = sorted(self.player.concealedMelds)
            else:
                tileStr = ''.join(self.player.concealedTileNames)
                content = HandContent.cached(self.player.game.ruleset, tileStr)
                newLowerMelds = list(Meld(x) for x in content.sortedMelds.split())
                if newLowerMelds:
                    if self.rearrangeMelds:
                        if newLowerMelds[0].pairs[0] == 'Xy':
                            newLowerMelds = sorted(newLowerMelds, key=len, reverse=True)
                    else:
                        # generate one meld with all sorted tiles
                        newLowerMelds = [Meld(sorted(sum((x.pairs for x in newLowerMelds), []), key=elementKey))]
        for yPos, melds in ((0, newUpperMelds), (self.lowerY, newLowerMelds)):
            meldDistance = self.concealedMeldDistance if yPos else self.exposedMeldDistance
            meldX = 0
            for meld in melds:
                for idx, tileName in enumerate(meld.pairs):
                    newTile = TileAttr(tileName, meldX, yPos)
                    if isScoringGame:
                        newTile.focusable = idx == 0
                    else:
                        newTile.focusable = (tileName[0] not in 'fy'
                            and tileName != 'Xy'
                            and self.player == self.player.game.activePlayer
                            and (meld.state == CONCEALED
                            and (len(meld) < 4 or meld.meldType == REST)))
                    result.append(newTile)
                    meldX += 1
                meldX += meldDistance
        return sorted(result, key=lambda x: x.yoffset * 100 + x.xoffset)

    def newBonusPositions(self, newTilePositions):
        """returns list(TileAttr)
        calculate places for bonus tiles. Put them all in one row,
        right adjusted. If necessary, extend to the right even outside of our board"""
        positions = list(x.xoffset for x in newTilePositions if x.yoffset==0)
        upperLen = max(positions) if positions else 0
        positions = list(x.xoffset for x in newTilePositions if x.yoffset!=0)
        lowerLen = max(positions) if positions else 0
        if upperLen < lowerLen :
            bonusY = 0
            tileLen = upperLen
        else:
            bonusY = self.lowerY
            tileLen = lowerLen
        tileLen += 1 + self.exposedMeldDistance
        newBonusTiles = list(TileAttr(x) for x in self.player.bonusTiles)
        xPos = 13 - len(newBonusTiles)
        xPos = max(xPos, tileLen)
        result = list()
        for bonus in sorted(newBonusTiles, key=tileKey):
            bonus.xoffset, bonus.yoffset = xPos, bonusY
            bonus.focusable = self.player.game.isScoringGame()
            bonus.dark = False
            result.append(bonus)
            xPos += 1
        return result

    def calcPlaces(self, adding=None):
        """returns a dict. Keys are existing tiles, Values are TileAttr instances.
        Values may be None: This is a tile to be removed from the board."""
        oldTiles = dict()
        allTiles = self.tiles[:]
        if adding:
            allTiles.extend(adding)
        # process bonus tiles last and separately
        allTiles = [x for x in allTiles if not x.isBonus()]
        for tile in allTiles:
            assert isinstance(tile, Tile)
            if not tile.element in oldTiles.keys():
                oldTiles[tile.element] = list()
            oldTiles[tile.element].append(tile)
        result = dict()
        newPositions = self.newTilePositions()
        for newPosition in newPositions:
            matches = oldTiles.get(newPosition.element) \
                or oldTiles.get(swapTitle(newPosition.element)) \
                or oldTiles.get('Xy')
            if not matches and newPosition.element == 'Xy':
                matches = oldTiles.values()[0]
            if matches:
                # no matches happen when we move a tile within a board,
                # here we simply ignore existing tiles with no matches
                matches = sorted(matches, key=lambda x: \
                    + abs(newPosition.yoffset-x.yoffset) * 100 \
                    + abs(newPosition.xoffset-x.xoffset))
                match = matches[0]
                result[match] = newPosition
                oldTiles[match.element].remove(match)
                if not len(oldTiles[match.element]):
                    del oldTiles[match.element]
        oldBoni = dict((x.element, x) for x in self.player.bonusTiles)
        for newBonusPosition in self.newBonusPositions(newPositions):
            result[oldBoni[newBonusPosition.element]] = newBonusPosition
        if result:
            self.__avoidCrossingMovements(result)
        return result

    def __avoidCrossingMovements(self, places):
        """"the above is a good approximation but if the board already had more
        than one identical tile they often switch places - this should not happen.
        So for each element, we make sure that the left-right order is still the
        same as before. For this check, ignore all new tiles"""
        for yoffset in 0, self.lowerY:
            items = [x for x in places.items() \
                     if (x[0].board == self) \
                        and x[0].yoffset == yoffset \
                        and x[1] and x[1].yoffset == yoffset \
                        and not x[0].isBonus()]
            for element in set(x[0].element for x in items):
                items = [x for x in places.items() if x[0].element == element]
                if len(items) > 1:
                    oldList = sorted(list(x[0] for x in items), key=lambda x:bool(x.board!=self)*1000+x.xoffset)
                    newList = sorted(list(x[1] for x in items), key=lambda x:x.xoffset)
                    for idx, oldTile in enumerate(oldList):
                        places[oldTile] = newList[idx]

    def __sortPlayerMelds(self):
        """sort player meld lists by their screen position"""
        if self.player.game.isScoringGame():
            # in a real game, the player melds do not have tiles
            self.player.concealedMelds = sorted(self.player.concealedMelds, key= lambda x: x[0].xoffset)
            self.player.exposedMelds = sorted(self.player.exposedMelds, key= lambda x: x[0].xoffset)

    def sync(self, adding=None):
        """place all tiles in HandBoard.
        adding tiles: their board is where they come from. Those tiles
        are already in the Player tile lists.
        The sender board must not be self, see VisiblePlayer.moveMeld"""
        if not self.tiles and not adding:
            return
        senderBoard = adding[0].board if adding else None
        newPlaces = self.calcPlaces(adding)
        if self.__moveHelper:
            self.__moveHelper.setVisible(len(newPlaces)>0)
        for tile, newPos in newPlaces.items():
            tile.level = 0 # for tiles coming from the wall
            tile.element = newPos.element
            tile.setBoard(self, newPos.xoffset, newPos.yoffset)
            tile.dark = newPos.dark
            tile.focusable = newPos.focusable
        self.__sortPlayerMelds()
        newFocusTile = None
        for tile in sorted(adding if adding else newPlaces.keys(), key=lambda x: x.xoffset):
            if tile.focusable:
                newFocusTile = tile
                break
        self.focusTile = newFocusTile
        if self.player.game.isScoringGame():
            if adding:
                self.hasFocus = not senderBoard.tiles
            else:
                self.hasFocus = bool(self.tiles)
        else:
            self.hasFocus = bool(adding)
        self.showMoveHelper(self.player.game.isScoringGame() and not self.tiles)
        InternalParameters.field.handSelectorChanged(self)
        if adding:
            assert len(self.tiles) >= len(adding)

    @staticmethod
    def chooseVariant(tile, variants):
        """make the user choose from a list of possible melds for the target.
        The melds do not contain real Tiles, just the scoring strings."""
        idx = 0
        if len(variants) > 1:
            menu = QMenu(m18n('Choose from'))
            for idx, variant in enumerate(variants):
                action = menu.addAction(shortcuttedMeldName(variant.meldType))
                action.setData(QVariant(idx))
            if InternalParameters.field.centralView.dragObject:
                menuPoint = QCursor.pos()
            else:
                menuPoint = tile.board.tileFaceRect().bottomRight()
                view = InternalParameters.field.centralView
                menuPoint = view.mapToGlobal(view.mapFromScene(tile.graphics.mapToScene(menuPoint)))
            action = menu.exec_(menuPoint)
            if not action:
                return None
            idx = action.data().toInt()[0]
        return variants[idx]

    def __chooseDestinationMeld(self, tile=None, meld=None):
        """returns a meld, lets user choose between possible meld types"""
        sourceBoard = tile.board
        if tile:
            assert not sourceBoard.isHandBoard # comes from SelectorBoard
            assert not meld
            result = self.chooseVariant(tile, sourceBoard.meldVariants(tile))
            if not result:
                return None
            for idx, myTile in enumerate(result.tiles):
                myTile.element = result.pairs[idx]
        else:
            assert meld
            assert sourceBoard.isHandBoard
            if tile.islower() and len(meld) == 4 and meld.state == CONCEALED:
                pair0 = meld.pairs[0].lower()
                meldVariants = [Meld(pair0*4), Meld(pair0*3 + pair0.capitalize())]
            else:
                result = self.chooseVariant(meld[0], meldVariants)
            if result:
                result.tiles = meld.tiles
                for tile, pair in zip(result.tiles, result.pairs):
                    tile.element = pair
        return result
