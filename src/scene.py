# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

from twisted.internet.defer import succeed, Deferred

from log import logDebug
from mi18n import i18n, i18nc
from common import LIGHTSOURCES, Internal, isAlive, ZValues, Debug
from common import ReprMixin, Speeds, id4
from wind import Wind

from qt import Qt, QMetaObject
from qt import QGraphicsScene, QGraphicsItem, QGraphicsRectItem, QPen, QColor

from dialogs import QuestionYesNo
from guiutil import decorateWindow, sceneRotation
from board import SelectorBoard, DiscardBoard
from tileset import Tileset
from meld import Meld
from humanclient import HumanClient
from uitile import UITile
from uiwall import UIWall
from animation import AnimationSpeed, afterQueuedAnimations
from scoringdialog import ScoringDialog


class FocusRect(QGraphicsRectItem, ReprMixin):

    """show a focusRect with blue border around focused tile or meld.
    We can NOT do this as a child of the item or the focus rect would
    have to stay within tile face: The adjacent tile will cover the
    focus rect because Z order is only relevant for items having the
    same parent"""

    def __init__(self):
        QGraphicsRectItem.__init__(self)
        pen = QPen(QColor('blue'))
        pen.setWidth(6)
        self.setPen(pen)
        self.setZValue(ZValues.markerZ)
        self._board = None
        self.hide()

    @property
    def board(self):
        """current board the focusrect is on"""
        return self._board

    @board.setter
    def board(self, value):
        """assign and show/hide as needed"""
        if value and not isAlive(value):
            logDebug(
                'assigning focusRect to a non-alive board %s/%s' %
                (type(value), value))
            return
        if value:
            self._board = value
            self.refresh()

    @afterQueuedAnimations
    def refresh(self, unusedDeferredResult=None):
        """show/hide on correct position after queued animations end"""
        board = self.board
        if not board:
            # for mypy
            return
        if not isAlive(board) or not isAlive(self):
            if isAlive(self):
                self.setVisible(False)
            return
        rect = board.tileFaceRect()
        rect.setWidth(rect.width() * board.focusRectWidth())
        self.setRect(rect)
        self.setRotation(sceneRotation(board))
        self.setScale(board.scale())
        if board.focusTile:
            board.focusTile.setFocus()
            self.setPos(board.focusTile.pos)
        assert Internal.scene
        game = Internal.scene.game
        if game is None:
            self.setVisible(False)
        else:
            self.setVisible(board.isVisible() and bool(board.focusTile)
                        and board.isEnabled() and board.hasLogicalFocus and not game.autoPlay)

    def __str__(self):
        """for debugging"""
        return 'FocusRect({} on {})'.format(id4(self), self.board if self.board else 'NOBOARD')

class SceneWithFocusRect(QGraphicsScene):

    """our scene with a potential Qt bug fix. FocusRect is a blue frame around a tile or meld"""

    def __init__(self):
        QGraphicsScene.__init__(self)
        self.focusRect = FocusRect()
        self.addItem(self.focusRect)

    def focusInEvent(self, event):
        """
        Work around a qt bug. See U{https://bugreports.qt-project.org/browse/QTBUG-32890}.
        This can be reproduced as follows:
         - ./kajongg.py --game=2/E2 --demo --ruleset=BMJA
               such that the human player is the first one to discard a tile.
         - wait until the main screen has been built
         - click with the mouse into the middle of that window
         - press left arrow key
         - this will violate the assertion in UITile.keyPressEvent.
        """
        prev = self.focusItem()
        QGraphicsScene.focusInEvent(self, event)
        if prev and bool(prev.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsFocusable) and prev != self.focusItem():
            self.setFocusItem(prev)

    @property
    def focusBoard(self):
        """get / set the board that has its focusRect shown"""
        return self.focusRect.board

    @focusBoard.setter
    def focusBoard(self, board):
        """get / set the board that has its focusRect shown"""
        self.focusRect.board = board


class GameScene(SceneWithFocusRect):

    """the game field"""

    def __init__(self, parent=None):
        Internal.scene = self
        assert parent
        self.mainWindow = parent
        self._game = None
        super().__init__()

        self.scoreTable = None
        self.explainView = None
        self.setupUi()
        assert Internal.Preferences
        Internal.Preferences.addWatch('showShadows', self.showShadowsChanged)

    @property
    def game(self):
        """a proxy"""
        return self._game

    @game.setter
    def game(self, value):
        """if it changes, update GUI"""
        changing = self._game != value
        game = self._game
        assert self.mainWindow
        self._game = value
        if changing:
            if value:
                self.mainWindow.updateGUI()
            else:
                assert game
                game.close()
                if self.scoreTable:
                    self.scoreTable.hide()
                if self.explainView:
                    self.explainView.hide()
                self.mainWindow.scene = None
        self.mainWindow.updateGUI()
        self.mainWindow.adjustMainView()

    @afterQueuedAnimations
    def showShadowsChanged(self, deferredResult, unusedOldValue, unusedNewValue): # pylint: disable=unused-argument
        """if the wanted shadow direction changed, apply that change now"""
        for uiTile in self.graphicsTileItems():
            uiTile.setClippingFlags()
        self.applySettings()

    def handSelectorChanged(self, handBoard):
        """update all relevant dialogs"""
        if self.game and not self.game.finished():
            assert handBoard.player
            handBoard.player.showInfo()
        # first decorate walls - that will compute player.handBoard for
        # explainView
        if self.explainView:
            self.explainView.refresh()

    def setupUi(self):
        """prepare scene"""
        assert Internal.Preferences
        assert isinstance(Internal.Preferences.windTilesetName, str)
        self.windTileset = Tileset(Internal.Preferences.windTilesetName)

    def showWall(self):
        """shows the wall according to the game rules (length may vary)"""
        if self.game:
            UIWall(self.game)   # sets self.game.wall

    def abort(self):
        """abort current game"""
        # to be implemented by children
        return Deferred()

    def adjustSceneView(self):
        """adjust the view such that exactly the wanted things are displayed
        without having to scroll"""
        if self.game:
            assert self.game.wall
            with AnimationSpeed():
                self.game.wall.decorate4()
                for uiTile in self.game.wall.tiles:
                    _ = uiTile
                    if _.board:
                        _.board.placeTile(_)

    def applySettings(self):
        """apply preferences"""
        assert self.mainWindow
        assert Internal.Preferences
        self.mainWindow.actionAngle.setEnabled(
            bool(self.game) and bool(Internal.Preferences.showShadows))
        with AnimationSpeed():
            for item in self.nonTiles():
                if hasattr(item, 'tileset'):
                    item.tileset = Tileset.current()

    def prepareHand(self):
        """redecorate wall"""
        self.mainWindow.updateGUI()
        if self.game:
            assert self.game.wall
            with AnimationSpeed(Speeds.windDisc):
                self.game.wall.decorate4()

    def updateSceneGUI(self):
        """update some actions, all auxiliary windows and the statusbar"""
        game = self.game
        assert Internal.Preferences
        mainWindow = self.mainWindow
        for action in [mainWindow.actionScoreGame, mainWindow.actionPlayGame]:
            action.setEnabled(not bool(game))
        mainWindow.actionAbortGame.setEnabled(bool(game))
        mainWindow.actionAngle.setEnabled(
            bool(game) and bool(Internal.Preferences.showShadows))
        for view in [self.explainView, self.scoreTable]:
            if view:
                view.refresh()
        self.__showBalance()

    def newLightSource(self):
        """next value"""
        assert self.game
        assert self.game.wall
        oldIdx = LIGHTSOURCES.index(self.game.wall.lightSource)
        return LIGHTSOURCES[(oldIdx + 1) % 4]

    def changeAngle(self):
        """change the lightSource"""
        assert self.game
        assert self.game.wall
        self.game.wall.lightSource = self.newLightSource()
        self.focusRect.refresh()
        self.mainWindow.adjustMainView()

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
                    sBar.setItemAlignment(idx, Qt.AlignmentFlag.AlignLeft)
        else:
            for idx in range(5):
                if sBar.hasItem(idx):
                    sBar.removeItem(idx)

    def graphicsTileItems(self):
        """return all UITile in the scene"""
        return (x for x in self.items() if isinstance(x, UITile))

    def nonTiles(self):
        """return all other items in the scene"""
        return (x for x in self.items() if not isinstance(x, UITile))

    def removeTiles(self):
        """remove all tiles from scene"""
        for item in self.graphicsTileItems():
            self.removeItem(item)
        for wind in Wind.all:
            if hasattr(wind, 'disc'):
                wind.disc.hide()
                delattr(wind, 'disc')
        self.focusRect.hide()


class PlayingScene(GameScene):

    """scene with a playing game"""

    def __init__(self, parent):
        self._game = None
        self.__startingGame = True
        self._clientDialog = None

        super().__init__(parent)

    @GameScene.game.setter
    def game(self, value):
        game = self._game
        changing = value != game
        GameScene.game.fset(self, value)
        if changing:
            self.__startingGame = False
        self.mainWindow.actionChat.setEnabled(
            bool(value)
            and bool(value.client)
            and bool(value.client.connection)
            and not value.client.connection.url.isLocalGame)
        self.mainWindow.actionChat.setChecked(
            bool(value)
            and bool(value.client)
            and bool(value.client.table.chatWindow))

    @property
    def clientDialog(self):
        """wrapper: hide dialog when it is set to None"""
        return self._clientDialog

    @clientDialog.setter
    def clientDialog(self, value):
        """wrapper: hide dialog when it is set to None"""
        if self._clientDialog and isAlive(self._clientDialog) and not value:
            self._clientDialog.timer.stop()
            self._clientDialog.hide()
        self._clientDialog = value

    def setupUi(self):
        """create all other widgets
        we could make the scene view the central widget but I did
        not figure out how to correctly draw the background with
        QGraphicsView/QGraphicsScene.
        QGraphicsView.drawBackground always wants a pixmap
        for a huge rect like 4000x3000 where my screen only has
        1920x1200"""
        GameScene.setupUi(self)
        self.setObjectName("PlayingField")

        self.discardBoard = DiscardBoard()
        self.addItem(self.discardBoard)

        self.adjustSceneView()

    def showWall(self):
        """shows the wall according to the game rules (length may vary)"""
        GameScene.showWall(self)
        self.discardBoard.maximize()

    def abort(self):
        """abort current game"""
        def gotAnswer(gotResult, autoPlaying):
            """user answered"""
            result = gotResult
            if result is True:
                self.game = None
            else:
                self.mainWindow.actionAutoPlay.setChecked(autoPlaying)
            return result
        if not self.game:
            return succeed(True)
        self.mainWindow.actionAutoPlay.setChecked(False)
        if self.game.finished():
            self.game = None
            return succeed(True)
        autoPlaying = self.mainWindow.actionAutoPlay.isChecked()
        return QuestionYesNo(i18n("Do you really want to abort this game?"), always=True).addCallback(
            gotAnswer, autoPlaying)

    def keyPressEvent(self, event):
        """if we have a clientDialog, pass event to it"""
        mod = event.modifiers()
        if mod in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ShiftModifier):
            if self.clientDialog:
                self.clientDialog.keyPressEvent(event)
        GameScene.keyPressEvent(self, event)

    def adjustSceneView(self):
        """adjust the view such that exactly the wanted things are displayed
        without having to scroll"""
        if self.game:
            with AnimationSpeed():
                self.discardBoard.maximize()
        GameScene.adjustSceneView(self)

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
        GameScene.applySettings(self)

    def toggleDemoMode(self, checked):
        """switch on / off for autoPlay"""
        if self.game:
            self.focusRect.refresh()  # show/hide it
            self.game.autoPlay = checked
            if checked and self.clientDialog:
                self.clientDialog.proposeAction()
                                                # an illegal action might have
                                                # focus
                self.clientDialog.selectButton()
                                               # select default, abort timeout

    def updateSceneGUI(self):
        """update some actions, all auxiliary windows and the statusbar"""
        if not isAlive(self):
            return
        GameScene.updateSceneGUI(self)
        game = self.game
        mainWindow = self.mainWindow
        if not game:
            connections = [x.connection for x in HumanClient.humanClients if x.connection]
            title = ', '.join('{name}/{url}'.format(name=x.username, url=x.url) for x in connections)
            if title:
                decorateWindow(mainWindow, title)
        else:
            decorateWindow(mainWindow, str(game.seed))
        for action in [mainWindow.actionScoreGame, mainWindow.actionPlayGame]:
            action.setEnabled(not bool(game))
        mainWindow.actionAbortGame.setEnabled(bool(game))
        self.discardBoard.setVisible(bool(game))
        mainWindow.actionAutoPlay.setEnabled(not self.startingGame)
        mainWindow.actionChat.setEnabled(bool(game) and bool(game.client)
                                         and bool(game.client.connection)
                                         and not game.client.connection.url.isLocalGame and not self.startingGame)
            # chatting on tables before game started works with chat button per
            # table
        mainWindow.actionChat.setChecked(
            mainWindow.actionChat.isEnabled(
            ) and bool(
                game.client.table.chatWindow))

    def changeAngle(self):
        """now that no animation is running, really change"""
        self.discardBoard.lightSource = self.newLightSource()
        GameScene.changeAngle(self)


class ScoringScene(GameScene):

    """a scoring game"""

    def __init__(self, parent=None):
        self.scoringDialog = None
        super().__init__(parent)
        self.selectorBoard.hasLogicalFocus = True

    @GameScene.game.setter
    def game(self, value):
        game = self._game
        changing = value != game
        GameScene.game.fset(self, value)
        if changing:
            if value is not None:
                self.scoringDialog = ScoringDialog(scene=self)
            else:
                self.scoringDialog.hide()
                self.scoringDialog = None

    def handSelectorChanged(self, handBoard):
        """update all relevant dialogs"""
        GameScene.handSelectorChanged(self, handBoard)
        if self.scoringDialog:
            self.scoringDialog.slotInputChanged()

    def setupUi(self):
        """create all other widgets"""
        GameScene.setupUi(self)
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
            return result
        if Debug.quit:
            logDebug('ScoringScene.abort invoked')
        if not self.game:
            return succeed(True)
        if self.game.finished():
            self.game = None
            return succeed(True)
        return QuestionYesNo(i18n("Do you really want to abort this game?"), always=True).addCallback(answered)

    def __moveTile(self, uiTile, wind, toConcealed):
        """the user pressed a wind letter or X for center, wanting to move a uiTile there"""
        # this tells the receiving board that this is keyboard, not mouse navigation>
        # needed for useful placement of the popup menu
        if wind == 'X':
            receiver = self.selectorBoard
        else:
            receiver = self.game.players[Wind(wind)].handBoard
        currentBoard = uiTile.board
        assert currentBoard
        movingMeld = currentBoard.uiMeldWithTile(uiTile)
        if receiver != currentBoard or toConcealed != movingMeld.meld.isConcealed:
            movingLastMeld = movingMeld.meld == self.computeLastMeld()
            assert self.scoringDialog
            if movingLastMeld:
                self.scoringDialog.clearLastTileCombo()
            receiver.dropTile(uiTile, toConcealed)
            if movingLastMeld and receiver == currentBoard:
                self.scoringDialog.fillLastTileCombo()

    def __navigateScoringGame(self, event):
        """keyboard navigation in a scoring game"""
        mod = event.modifiers()
        key = event.key()
        wind = chr(key % 128)
        windsX = ''.join(x.char for x in Wind.all)
        moveCommands = i18nc('kajongg:keyboard commands for moving tiles to the players '
                             'with wind ESWN or to the central tile selector (X)', windsX)
        uiTile = self.focusItem()
        if wind in moveCommands:
            # translate i18n wind key to ESWN:
            wind_chr = windsX[moveCommands.index(wind)]
            self.__moveTile(uiTile, wind_chr, bool(mod & Qt.KeyboardModifier.ShiftModifier))
            return True
        if key == Qt.Key.Key_Tab and self.game:
            tabItems = [self.selectorBoard]
            tabItems.extend(p.handBoard for p in self.game.players if p.handBoard.uiTiles)
            tabItems.append(tabItems[0])
            currentBoard = uiTile.board
            currIdx = 0
            while tabItems[currIdx] != currentBoard and currIdx < len(tabItems) - 2:
                currIdx += 1
            tabItems[currIdx + 1].hasLogicalFocus = True
            return True
        return False

    def keyPressEvent(self, event):
        """navigate in the selectorboard"""
        mod = event.modifiers()
        if mod in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ShiftModifier):
            if self.game:
                if self.__navigateScoringGame(event):
                    return
        GameScene.keyPressEvent(self, event)

    def adjustSceneView(self):
        """adjust the view such that exactly the wanted things are displayed
        without having to scroll"""
        if self.game:
            with AnimationSpeed():
                self.selectorBoard.maximize()
        GameScene.adjustSceneView(self)

    def prepareHand(self):
        """redecorate wall"""
        GameScene.prepareHand(self)
        if self.scoringDialog:
            self.scoringDialog.clearLastTileCombo()

    def updateSceneGUI(self):
        """update some actions, all auxiliary windows and the statusbar"""
        if not isAlive(self):
            return
        GameScene.updateSceneGUI(self)
        game = self.game
        mainWindow = self.mainWindow
        for action in [mainWindow.actionScoreGame, mainWindow.actionPlayGame]:
            action.setEnabled(not bool(game))
        mainWindow.actionAbortGame.setEnabled(bool(game))
        self.selectorBoard.setVisible(bool(game))
        self.selectorBoard.setEnabled(bool(game))

    def changeAngle(self):
        """now that no animation is running, really change"""
        self.selectorBoard.lightSource = self.newLightSource()
        GameScene.changeAngle(self)

    def computeLastTile(self):
        """compile hand info into a string as needed by the scoring engine"""
        if self.scoringDialog:
            # is None while ScoringGame is created
            return self.scoringDialog.computeLastTile()
        return None

    def computeLastMeld(self):
        """compile hand info into a string as needed by the scoring engine"""
        if self.scoringDialog:
            # is None while ScoringGame is created
            cbLastMeld = self.scoringDialog.cbLastMeld
            idx = cbLastMeld.currentIndex()
            if idx >= 0:
                return Meld(cbLastMeld.itemData(idx))
        return Meld()
