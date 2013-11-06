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

from util import m18n, m18nc
from common import LIGHTSOURCES, Internal, Preferences, isAlive
from twisted.internet.defer import succeed, fail

from PyQt4.QtCore import Qt, QMetaObject

from zope.interface import implements # pylint: disable=unused-import

from kde import QuestionYesNo

from board import SelectorBoard, DiscardBoard, MJScene
from tileset import Tileset
from meld import Meld
from client import Client
from humanclient import HumanClient
from uiwall import UIWall
from animation import Animated
from scoringdialog import ScoringDialog


class Scene(MJScene):
    """the game field"""
    # pylint: disable=too-many-instance-attributes

    def __init__(self, parent=None):
        Internal.scene = self
        self.mainWindow = parent
        self._game = None
        super(Scene, self).__init__()
        self.showShadows = True

        self.scoreTable = None
        self.explainView = None
        self.confDialog = None
        self.setupUi()

    @property
    def game(self):
        """a proxy"""
        return self._game

    @game.setter
    def game(self, value):
        """if it changes, update GUI"""
        changing = self._game != value
        game = self._game
        self._game = value
        if changing:
            if value:
                self.mainWindow.updateGUI()
            else:
                game.close()
                if self.scoreTable:
                    self.scoreTable.hide()
                if self.explainView:
                    self.explainView.hide()
                self.mainWindow.scene = None
        self.mainWindow.updateGUI()
        self.mainWindow.adjustView()

    def handSelectorChanged(self, handBoard):
        """update all relevant dialogs"""
        if self.game and not self.game.finished():
            self.game.wall.decoratePlayer(handBoard.player) # pylint:disable=no-member
        # first decorate walls - that will compute player.handBoard for explainView
        if self.explainView:
            self.explainView.refresh()

    def setupUi(self):
        """prepare scene"""
        # pylint: disable=too-many-statements
        self.tileset = None # just for pylint
        self.tilesetName = Preferences.tilesetName
        self.windTileset = Tileset(Preferences.windTilesetName)

    def showWall(self):
        """shows the wall according to the game rules (lenght may vary)"""
        UIWall(self.game)   # sets self.game.wall

    def abort(self):
        """abort current game"""
        # to be implemented by children

    def closeEvent(self, event):
        """somebody wants us to close, maybe ALT-F4 or so"""
        event.ignore()
        def doNotQuit(dummy):
            """ignore failure to abort"""
        self.abort().addCallback(HumanClient.shutdownHumanClients).addCallbacks(Client.quitProgram, doNotQuit)

    def adjustView(self):
        """adjust the view such that exactly the wanted things are displayed
        without having to scroll"""
        if self.game:
            with Animated(False):
                self.game.wall.decorate()
                for uiTile in self.game.wall.tiles:
                    if uiTile.board:
                        uiTile.board.placeTile(uiTile)

    @property
    def tilesetName(self):
        """the name of the current tileset"""
        return self.tileset.desktopFileName

    @tilesetName.setter
    def tilesetName(self, name):
        """the name of the current tileset"""
        self.tileset = Tileset(name)

    def applySettings(self):
        """apply preferences"""
        self.mainWindow.actionAngle.setEnabled(bool(self.game) and Preferences.showShadows)
        with Animated(False):
            if self.tilesetName != Preferences.tilesetName:
                self.tilesetName = Preferences.tilesetName
                if self.game:
                    self.game.wall.tileset = self.tileset
                for item in self.nonTiles():
                    try:
                        item.tileset = self.tileset
                    except AttributeError:
                        continue
                # change players last because we need the wall already to be repositioned
            if self.game:
                for player in self.game.players:
                    if player.handBoard:
                        player.handBoard.rearrangeMelds = Preferences.rearrangeMelds
            if self.showShadows is None or self.showShadows != Preferences.showShadows:
                self.showShadows = Preferences.showShadows
                if self.game:
                    wall = self.game.wall
                    wall.showShadows = self.showShadows
                for uiTile in self.graphicsTileItems():
                    uiTile.setClippingFlags()

    def prepareHand(self):
        """redecorate wall"""
        self.mainWindow.updateGUI()
        if self.game:
            self.game.wall.decorate()

    def updateSceneGUI(self):
        """update some actions, all auxiliary windows and the statusbar"""
        game = self.game
        mainWindow = self.mainWindow
        for action in [mainWindow.actionScoreGame, mainWindow.actionPlayGame]:
            action.setEnabled(not bool(game))
        mainWindow.actionAbortGame.setEnabled(bool(game))
        mainWindow.actionAngle.setEnabled(bool(game) and self.showShadows)
        for view in [self.explainView, self.scoreTable]:
            if view:
                view.refresh()
        self.__showBalance()

    def newLightSource(self):
        """next value"""
        oldIdx = LIGHTSOURCES.index(self.game.wall.lightSource)
        return LIGHTSOURCES[(oldIdx + 1) % 4]

    def changeAngle(self, dummyResult):
        """change the lightSource"""
        self.game.wall.lightSource = self.newLightSource()
        self.focusRect.refresh()
        self.mainWindow.adjustView()

    def __showBalance(self):
        """show the player balances in the status bar"""
        sBar = self.mainWindow.statusBar()
        if self.game:
            for idx, player in enumerate(self.game.players):
                sbMessage = player.localName + ': ' + str(player.balance)
                if sBar.hasItem(idx):
                    sBar.changeItem(sbMessage, idx)
                else:
                    sBar.insertItem(sbMessage, idx, 1)
                    sBar.setItemAlignment(idx, Qt.AlignLeft)
        else:
            for idx in range(5):
                if sBar.hasItem(idx):
                    sBar.removeItem(idx)

class PlayingScene(Scene):
    """scene with a playing game"""
    def __init__(self, parent):
        super(PlayingScene, self).__init__(parent)
        self.game = None
        self.__startingGame = True
        self._clientDialog = None

        self.confDialog = None
        self.setupUi()

    @Scene.game.setter
    def game(self, value): # pylint: disable=arguments-differ
        game = self._game
        changing = value != game
        Scene.game.fset(self, value)
        if changing:
            self.__startingGame = False

    @property
    def clientDialog(self):
        """wrapper: hide dialog when it is set to None"""
        return self._clientDialog

    @clientDialog.setter
    def clientDialog(self, value):
        """wrapper: hide dialog when it is set to None"""
        if isAlive(self._clientDialog) and not value:
            self._clientDialog.timer.stop()
            self._clientDialog.hide()
        self._clientDialog = value

    def resizeEvent(self, dummyEvent):
        """main window changed size"""
        if self.clientDialog:
            self.clientDialog.placeInField()

    def setupUi(self):
        """create all other widgets
        we could make the scene view the central widget but I did
        not figure out how to correctly draw the background with
        QGraphicsView/QGraphicsScene.
        QGraphicsView.drawBackground always wants a pixmap
        for a huge rect like 4000x3000 where my screen only has
        1920x1200"""
        # pylint: disable=too-many-statements
        Scene.setupUi(self)
        self.setObjectName("PlayingField")

        self.discardBoard = DiscardBoard()
        #self.discardBoard.setVisible(True)
        self.addItem(self.discardBoard)

        self.adjustView()
        game = self.game
        self.mainWindow.actionChat.setEnabled(bool(game) and bool(game.client) and not game.client.hasLocalServer())
        self.mainWindow.actionChat.setChecked(bool(game) and bool(game.client) and bool(game.client.table.chatWindow))

    def showWall(self):
        """shows the wall according to the game rules (lenght may vary)"""
        Scene.showWall(self)
        self.discardBoard.maximize()

    def abort(self):
        """abort current game"""
        def gotAnswer(result, autoPlaying):
            """user answered"""
            if result:
                self.game = None
                return succeed(None)
            else:
                self.mainWindow.actionAutoPlay.setChecked(autoPlaying)
                return fail(Exception('no abort'))
        if not self.game:
            return succeed(None)
        autoPlaying = self.mainWindow.actionAutoPlay.isChecked()
        self.mainWindow.actionAutoPlay.setChecked(False)
        if self.game.finished():
            self.game = None
            return succeed(None)
        else:
            return QuestionYesNo(m18n("Do you really want to abort this game?"), always=True).addCallback(
                gotAnswer, autoPlaying)

    def keyPressEvent(self, event):
        """if we have a clientDialog, pass event to it"""
        mod = event.modifiers()
        if mod in (Qt.NoModifier, Qt.ShiftModifier):
            if self.clientDialog:
                self.clientDialog.keyPressEvent(event)
        Scene.keyPressEvent(self, event)

    def adjustView(self):
        """adjust the view such that exactly the wanted things are displayed
        without having to scroll"""
        if self.game:
            with Animated(False):
                self.discardBoard.maximize()
        Scene.adjustView(self)

    @property
    def startingGame(self):
        """are we trying to start a game?"""
        return self.__startingGame

    @startingGame.setter
    def startingGame(self, value):
        """are we trying to start a game?"""
        if value != self.__startingGame:
            self.__startingGame = value
            self.mainWindow.updateGUI()

    def applySettings(self):
        """apply preferences"""
        Scene.applySettings(self)
        self.discardBoard.showShadows = self.showShadows

    def toggleDemoMode(self, checked):
        """switch on / off for autoPlay"""
        if self.game:
            self.focusRect.refresh() # show/hide it
            self.game.autoPlay = checked
            if checked and self.clientDialog:
                self.clientDialog.proposeAction() # an illegal action might have focus
                self.clientDialog.selectButton() # select default, abort timeout

    def updateSceneGUI(self):
        """update some actions, all auxiliary windows and the statusbar"""
        if not isAlive(self):
            return
        Scene.updateSceneGUI(self)
        game = self.game
        mainWindow = self.mainWindow
        if not game:
            connections = list(x.connection for x in HumanClient.humanClients if x.connection)
            title = ', '.join('{name}/{url}'.format(name=x.username, url=x.url) for x in connections)
            if title:
                mainWindow.setWindowTitle('%s - Kajongg' % title)
        else:
            mainWindow.setWindowTitle('%s - Kajongg' % game.seed)
        for action in [mainWindow.actionScoreGame, mainWindow.actionPlayGame]:
            action.setEnabled(not bool(game))
        mainWindow.actionAbortGame.setEnabled(bool(game))
        self.discardBoard.setVisible(bool(game))
        mainWindow.actionAutoPlay.setEnabled(not self.startingGame)
        mainWindow.actionChat.setEnabled(bool(game) and bool(game.client)
            and not game.client.hasLocalServer() and not self.startingGame)
            # chatting on tables before game started works with chat button per table
        mainWindow.actionChat.setChecked(mainWindow.actionChat.isEnabled() and bool(game.client.table.chatWindow))

    def changeAngle(self, result):
        """now that no animation is running, really change"""
        self.discardBoard.lightSource = self.newLightSource()
        Scene.changeAngle(self, result)

class ScoringScene(Scene):
    """a scoring game"""
    # pylint: disable=too-many-instance-attributes

    def __init__(self, parent=None):
        super(ScoringScene, self).__init__(parent)
        self.scoringDialog = None
        self.setupUi()
        self.selectorBoard.hasFocus = True

    @Scene.game.setter
    def game(self, value): # pylint: disable=arguments-differ
        game = self._game
        changing = value != game
        Scene.game.fset(self, value)
        if changing:
            if value is not None:
                self.scoringDialog = ScoringDialog(scene=self)
            else:
                self.scoringDialog.hide()
                self.scoringDialog = None

    def handSelectorChanged(self, handBoard):
        """update all relevant dialogs"""
        Scene.handSelectorChanged(self, handBoard)
        if self.scoringDialog:
            self.scoringDialog.slotInputChanged()

    def setupUi(self):
        """create all other widgets"""
        Scene.setupUi(self)
        self.setObjectName("ScoringScene")
        self.selectorBoard = SelectorBoard()
        self.addItem(self.selectorBoard)
        QMetaObject.connectSlotsByName(self)

    def abort(self):
        """abort current game"""
        def answered(result):
            """got answer"""
            if result:
                self.game = None
        if not self.game:
            return succeed(None)
        elif self.game.finished():
            self.game = None
            return succeed(None)
        else:
            return QuestionYesNo(m18n("Do you really want to abort this game?"), always=True).addCallback(answered)

    def __moveTile(self, uiTile, wind, lowerHalf):
        """the user pressed a wind letter or X for center, wanting to move a uiTile there"""
        # this tells the receiving board that this is keyboard, not mouse navigation>
        # needed for useful placement of the popup menu
        currentBoard = uiTile.board
        if wind == 'X':
            receiver = self.selectorBoard
        else:
            receiver = self.game.players[wind].handBoard
        if receiver != currentBoard or bool(lowerHalf) != bool(uiTile.yoffset):
            movingLastMeld = uiTile.tile in self.computeLastMeld()
            if movingLastMeld:
                self.scoringDialog.clearLastTileCombo()
            receiver.dropTile(uiTile, lowerHalf)
            if movingLastMeld and receiver == currentBoard:
                self.scoringDialog.fillLastTileCombo()

    def __navigateScoringGame(self, event):
        """keyboard navigation in a scoring game"""
        mod = event.modifiers()
        key = event.key()
        wind = chr(key%128)
        moveCommands = m18nc('kajongg:keyboard commands for moving tiles to the players ' \
            'with wind ESWN or to the central tile selector (X)', 'ESWNX')
        uiTile = self.focusItem()
        if wind in moveCommands:
            # translate i18n wind key to ESWN:
            wind = 'ESWNX'[moveCommands.index(wind)]
            self.__moveTile(uiTile, wind, bool(mod &Qt.ShiftModifier))
            return True
        if key == Qt.Key_Tab and self.game:
            tabItems = [self.selectorBoard]
            tabItems.extend(list(p.handBoard for p in self.game.players if p.handBoard.uiTiles))
            tabItems.append(tabItems[0])
            currentBoard = uiTile.board
            currIdx = 0
            while tabItems[currIdx] != currentBoard and currIdx < len(tabItems) -2:
                currIdx += 1
            tabItems[currIdx+1].hasFocus = True
            return True

    def keyPressEvent(self, event):
        """navigate in the selectorboard"""
        mod = event.modifiers()
        if mod in (Qt.NoModifier, Qt.ShiftModifier):
            if self.game:
                if self.__navigateScoringGame(event):
                    return
        Scene.keyPressEvent(self, event)

    def adjustView(self):
        """adjust the view such that exactly the wanted things are displayed
        without having to scroll"""
        if self.game:
            with Animated(False):
                self.selectorBoard.maximize()
        Scene.adjustView(self)

    def applySettings(self):
        """apply preferences"""
        Scene.applySettings(self)
        self.selectorBoard.showShadows = self.showShadows

    def scoringClosed(self):
        """the scoring window has been closed with ALT-F4 or similar"""
        assert self.game is None

    def prepareHand(self):
        """redecorate wall"""
        Scene.prepareHand(self)
        if self.scoringDialog:
            self.scoringDialog.clearLastTileCombo()

    def updateSceneGUI(self):
        """update some actions, all auxiliary windows and the statusbar"""
        if not isAlive(self):
            return
        Scene.updateSceneGUI(self)
        game = self.game
        mainWindow = self.mainWindow
        for action in [mainWindow.actionScoreGame, mainWindow.actionPlayGame]:
            action.setEnabled(not bool(game))
        mainWindow.actionAbortGame.setEnabled(bool(game))
        self.selectorBoard.setVisible(bool(game))
        self.selectorBoard.setEnabled(bool(game))

    def changeAngle(self, result):
        """now that no animation is running, really change"""
        self.selectorBoard.lightSource = self.newLightSource()
        Scene.changeAngle(self, result)

    def computeLastTile(self):
        """compile hand info into a string as needed by the scoring engine"""
        if self.scoringDialog:
            # is None while ScoringGame is created
            return self.scoringDialog.computeLastTile()

    def computeLastMeld(self):
        """compile hand info into a string as needed by the scoring engine"""
        if self.scoringDialog:
            # is None while ScoringGame is created
            cbLastMeld = self.scoringDialog.cbLastMeld
            idx = cbLastMeld.currentIndex()
            if idx >= 0:
                return Meld(str(cbLastMeld.itemData(idx).toString()))
        return Meld()