#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008,2009 Wolfgang Rohdewald <wolfgang@rohdewald.de>

kmj is free software you can redistribute it and/or modify
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

#from __future__  import print_function, unicode_literals, division

import sys
if sys.version_info < (2, 6, 0, 0, 0):
    bytes = str
else:
    str = unicode

import os
import util
from util import logMessage,  logException, m18n, m18nc, WINDS,  rotateCenter
import cgitb,  tempfile, webbrowser

class MyHook(cgitb.Hook):
    """override the standard cgitb hook: invoke the browser"""
    def __init__(self):
        self.tmpFileName = tempfile.mkstemp(suffix='.html', prefix='bt_', text=True)[1]
        cgitb.Hook.__init__(self, file=open(self.tmpFileName, 'w'))

    def handle(self,  info=None):
        """handling the exception: show backtrace in browser"""
        cgitb.Hook.handle(self, info)
        webbrowser.open(self.tmpFileName)

#sys.excepthook = MyHook()

NOTFOUND = []

try:
    from PyQt4.QtCore import Qt, QRectF,  QVariant, SIGNAL, SLOT, \
        QEvent, QMetaObject, PYQT_VERSION_STR
    from PyQt4.QtGui import QColor, QPushButton,  QMessageBox
    from PyQt4.QtGui import QWidget
    from PyQt4.QtGui import QGridLayout, QVBoxLayout
    from PyQt4.QtGui import QDialog
    from PyQt4.QtGui import QBrush, QDialogButtonBox
    from PyQt4.QtGui import QComboBox
except ImportError,  e:
    NOTFOUND.append('PyQt4: %s' % e)

try:
    from PyKDE4.kdeui import KApplication,  KStandardAction,  KAction, KToggleFullScreenAction,  KDialogButtonBox
    from PyKDE4.kdeui import KXmlGuiWindow, KIcon, KConfigDialog
except ImportError, e :
    NOTFOUND.append('PyKDE4: %s' % e)

try:
    from query import Query
    import board
    from tile import Tile
    from board import PlayerWind, WindLabel, Walls,  FittingView, \
        HandBoard,  SelectorBoard, MJScene
    from playerlist import PlayerList
    from tileset import Tileset, Elements, LIGHTSOURCES
    from background import Background
    from games import Games
    from config import Preferences, ConfigDialog
    from scoringengine import Ruleset, PredefinedRuleset, HandContent
    from scoring import ExplainView,  ScoringDialog, ScoreTable, ListComboBox
    from tables import TableList

    from game import Game,  Players,  Player
    from client import Client
except ImportError,  e:
    NOTFOUND.append('kmj modules: %s' % e)

if len(NOTFOUND):
    MSG = "\n".join(" * %s" % s for s in NOTFOUND)
    logMessage(MSG)
    os.popen("kdialog --sorry '%s'" % MSG)
    sys.exit(3)

class SelectPlayers(QDialog):
    """a dialog for selecting four players"""
    def __init__(self, game):
        QDialog.__init__(self, None)
        self.game = game
        Players.load()
        self.setWindowTitle(m18n('Select four players') + ' - kmj')
        self.buttonBox = KDialogButtonBox(self)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
        self.connect(self.buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(self.buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        grid = QGridLayout()
        self.names = None
        self.nameWidgets = []
        self.cbRuleset = ListComboBox(Ruleset.availableRulesets() + PredefinedRuleset.rulesets())
        if not self.cbRuleset.count():
            logException(Exception(m18n('No rulesets defined')))
        for idx, wind in enumerate(WINDS):
            cbName = QComboBox()
            # increase width, we want to see the full window title
            cbName.setMinimumWidth(350) # is this good for all platforms?
            # add all player names belonging to no host
            cbName.addItems(list(x[1] for x in Players.allNames.values() if x[0] == ''))
            grid.addWidget(cbName, idx+1, 1)
            self.nameWidgets.append(cbName)
            grid.addWidget(WindLabel(wind), idx+1, 0)
            self.connect(cbName, SIGNAL('currentIndexChanged(int)'),
                self.slotValidate)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 6)
        vbox = QVBoxLayout(self)
        vbox.addLayout(grid)
        vbox.addWidget(self.cbRuleset)
        vbox.addWidget(self.buttonBox)
        self.resize(300, 200)
        query = Query("select p0,p1,p2,p3 from game where game.id = (select max(id) from game)")
        if len(query.data):
            for pidx in range(4):
                playerId = query.data[0][pidx]
                try:
                    (host, playerName)  = Players.allNames[playerId]
                    assert host == ''
                    cbName = self.nameWidgets[pidx]
                    playerIdx = cbName.findText(playerName)
                    if playerIdx >= 0:
                        cbName.setCurrentIndex(playerIdx)
                except KeyError:
                    logMessage('database is inconsistent: player with id %d is in game but not in player' \
                               % playerId)
        self.slotValidate()

    def showEvent(self, event):
        """start with player 0"""
        assert event # quieten pylint
        self.nameWidgets[0].setFocus()

    def slotValidate(self):
        """try to find 4 different players and update status of the Ok button"""
        changedCombo = self.sender()
        if not isinstance(changedCombo, QComboBox):
            changedCombo = self.nameWidgets[0]
        usedNames = set([str(x.currentText()) for x in self.nameWidgets])
        allNames = set(x[1] for x in Players.allNames.values() if x[0] == '')
        unusedNames = allNames - usedNames
        foundNames = [str(changedCombo.currentText())]
        for combo in self.nameWidgets:
            if combo is not changedCombo:
                if str(combo.currentText()) in foundNames:
                    if not unusedNames:
                        break
                    combo.setItemText(combo.currentIndex(), unusedNames.pop())
                foundNames.append(str(combo.currentText()))
        self.names = list(str(cbName.currentText()) for cbName in self.nameWidgets)
        valid = len(set(self.names)) == 4
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(valid)

class VisiblePlayer(Player):
    def __init__(self,  field,  idx):
        Player.__init__(self, idx)
        self.field = field
        self.wall = field.walls[idx]
        self.wallWind = PlayerWind('E', field.windTileset, 0, self.wall)
        self.wallWind.hide()
        self.wallLabel = field.centralScene.addSimpleText('')
        self.manualRuleBoxes = []
        self.handBoard = HandBoard(self)
        self.handBoard.setVisible(False)
        self.handBoard.setPos(yHeight= 1.5)

    def refresh(self):
        self.wallLabel.setVisible(self.field.game is not None)
        self.wallWind.setVisible(self.field.game is not None)

    def refreshManualRules(self):
        """update status of manual rules"""
        if self.field.game:
            self.handContent = self.computeHandContent()
            if self.handContent:
                currentScore = self.handContent.score
                for box in self.manualRuleBoxes:
                    if box.rule not in [x[0] for x in self.handContent.usedRules]:
                        applicable = self.handContent.ruleMayApply(box.rule)
                        applicable &= bool(box.rule.actions) or self.computeHandContent(box.rule).score != currentScore
                        box.setApplicable(applicable)

    def __mjString(self):
        """compile hand info into  a string as needed by the scoring engine"""
        game = self.field.game
        assert game
        winds = self.wind.lower() + 'eswn'[game.roundsFinished]
        wonChar = 'm'
        if self == game.winner:
            wonChar = 'M'
        lastSource = 'd'
        lastTile = self.field.lastTile()
        if len(lastTile) and lastTile[0].isupper():
            lastSource = 'w'
        for box in self.manualRuleBoxes:
            if box.isChecked() and 'lastsource' in box.rule.actions:
                if lastSource != '1':
                    # this defines precedences for source of last tile
                    lastSource = box.rule.actions['lastsource']
        return ''.join([wonChar, winds, lastSource])

    def __lastString(self):
        """compile hand info into  a string as needed by the scoring engine"""
        game = self.field.game
        if game is None:
            return ''
        if self != game.winner:
            return ''
        return 'L%s%s' % (game.field.lastTile(), game.field.lastMeld())

    def computeHandContent(self, singleRule=None):
        """returns a HandContent object, using a cache"""
        game = self.field.game
        assert game
        string = ' '.join([self.handBoard.scoringString(), self.__mjString(), self.__lastString()])
        rules = list(x.rule for x in self.manualRuleBoxes if x.isChecked())
        if singleRule:
            rules.append(singleRule)
        return HandContent.cached(game.ruleset, string, rules)

class PlayField(KXmlGuiWindow):
    """the main window"""

    def __init__(self,  reactor):
        # see http://lists.kde.org/?l=kde-games-devel&m=120071267328984&w=2
        self.reactor = reactor
        self.client = None
        self.__game = None
        self.ignoreResizing = 1
        super(PlayField, self).__init__()
        Preferences() # defines PREF
        board.PLAYFIELD = self
        self.background = None
        self.settingsChanged = False

        self.playerWindow = None
        self.scoreTable = None
        self.explainView = None
        self.scoringDialog = None
        self.tableLists = []
        self.setupUi()
        KStandardAction.preferences(self.showSettings, self.actionCollection())
        self.applySettings()
        self.setupGUI()
        self.retranslateUi()

    def resizeEvent(self, event):
        """Use this hook to determine if we want to ignore one more resize
        event happening for maximized / almost maximized windows.
        this misses a few cases where the window is almost maximized because at
        this point the window has no border yet: event.size, self.geometry() and
        self.frameGeometry are all the same. So we cannot check if the bordered
        window would fit into availableGeometry.
        """
        available = KApplication.kApplication().desktop().availableGeometry()
        if self.ignoreResizing == 1: # at startup
            if available.width() <= event.size().width() \
            or available.height() <= event.size().height():
                self.ignoreResizing += 1
        KXmlGuiWindow.resizeEvent(self, event)

    def handSelectorChanged(self, handBoard):
        """update all relevant dialogs"""
        self.scoringDialog.fillLastTileCombo()
        self.scoringDialog.computeScores()
        if self.explainView:
            self.explainView.refresh()

    def kmjAction(self,  name, icon, slot=None, shortcut=None, data=None):
        """simplify defining actions"""
        res = KAction(self)
        res.setIcon(KIcon(icon))
        if slot:
            self.connect(res, SIGNAL('triggered()'), slot)
        self.actionCollection().addAction(name, res)
        if shortcut:
            res.setShortcut( Qt.CTRL + shortcut)
            res.setShortcutContext(Qt.ApplicationShortcut)
        if PYQT_VERSION_STR != '4.5.2' or data is not None:
            res.setData(QVariant(data))
        return res

    def kmjToggleAction(self, name, icon, shortcut=None, data=None):
        """a checkable action"""
        res = self.kmjAction(name, icon, shortcut=shortcut, data=data)
        res.setCheckable(True)
        self.connect(res, SIGNAL('toggled(bool)'), self.toggleWidget)
        return res

    def tileClicked(self, event, tile):
        """save the clicked tile, we need it when dropping things into boards"""
        self.centralScene.clickedTile = tile
        self.centralScene.clickedTileEvent = event
        self.selectorBoard.setAcceptDrops(tile.board != self.selectorBoard)

    def setupUi(self):
        """create all other widgets
        we could make the scene view the central widget but I did
        not figure out how to correctly draw the background with
        QGraphicsView/QGraphicsScene.
        QGraphicsView.drawBackground always wants a pixmap
        for a huge rect like 4000x3000 where my screen only has
        1920x1200"""
        self.setObjectName("MainWindow")
        centralWidget = QWidget()
        scene = MJScene()
        scene.field = self
        self.centralScene = scene
        self.centralView = FittingView()
        layout = QGridLayout(centralWidget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.centralView)
        self.tileset = None # just for pylint
        self.background = None # just for pylint
        self.tilesetName = util.PREF.tilesetName
        self.walls = Walls(self.tileset)
        scene.addItem(self.walls)
        self.selectorBoard = SelectorBoard(self.tileset)
        self.selectorBoard.setVisible(False)
        self.selectorBoard.scale(1.7, 1.7)
        self.selectorBoard.setPos(xWidth=1.7, yWidth=3.9)
# TODO:       self.gameOverLabel = QLabel(m18n('The game is over!'))
        scene.addItem(self.selectorBoard)

        self.connect(scene, SIGNAL('tileClicked'), self.tileClicked)

        self.windTileset = Tileset(util.PREF.windTilesetName)
        self.players = list([VisiblePlayer(self, idx) for idx in range(4)])

        self.setCentralWidget(centralWidget)
        self.centralView.setScene(scene)
        self.centralView.setFocusPolicy(Qt.StrongFocus)
        self.backgroundName = util.PREF.backgroundName
        self._adjustView()
        self.actionScoreGame = self.kmjAction("scoreGame", "draw-freehand", self.scoreGame, Qt.Key_C)
        self.actionLocalGame = self.kmjAction("local", "media-playback-start", self.localGame, Qt.Key_L)
        self.actionRemoteGame = self.kmjAction("network", "network-connect", self.remoteGame, Qt.Key_N)
        self.actionQuit = self.kmjAction("quit", "application-exit", self.quit, Qt.Key_Q)
        self.actionPlayers = self.kmjAction("players",  "im-user",  self.slotPlayers)
        self.actionScoring = self.kmjToggleAction("scoring", "draw-freehand", shortcut=Qt.Key_S, data=ScoringDialog)
        self.actionScoring.setEnabled(False)
        self.actionAngle = self.kmjAction("angle",  "object-rotate-left",  self.changeAngle, Qt.Key_G)
        self.actionFullscreen = KToggleFullScreenAction(self.actionCollection())
        self.actionFullscreen.setShortcut(Qt.CTRL + Qt.Key_F)
        self.actionFullscreen.setShortcutContext(Qt.ApplicationShortcut)
        self.actionFullscreen.setWindow(self)
        self.actionCollection().addAction("fullscreen", self.actionFullscreen)
        self.connect(self.actionFullscreen, SIGNAL('toggled(bool)'), self.fullScreen)
        self.actionScoreTable = self.kmjToggleAction("scoreTable", "format-list-ordered",
            Qt.Key_T, data=ScoreTable)
        self.actionExplain = self.kmjToggleAction("explain", "applications-education",
            Qt.Key_E, data=ExplainView)
        QMetaObject.connectSlotsByName(self)

    def fullScreen(self, toggle):
        """toggle between full screen and normal view"""
        self.actionFullscreen.setFullScreen(self, toggle)

    def quit(self):
        """exit the application"""
        if self.reactor.running:
            self.reactor.stop()
        sys.exit(0)

    def closeEvent(self, event):
        self.quit()

    def keyPressEvent(self, event):
        """navigate in the selectorboard"""
        mod = event.modifiers()
        if not mod in (Qt.NoModifier, Qt.ShiftModifier):
            # no other modifier is allowed
            KXmlGuiWindow.keyPressEvent(self, event)
            return
        key = event.key()
        tile = self.centralScene.focusItem()
        currentBoard = tile.board if isinstance(tile, Tile) else None
        wind = chr(key%256)
        moveCommands = m18nc('kmj:keyboard commands for moving tiles to the players ' \
            'with wind ESWN or to the central tile selector (X)', 'ESWNX')
        if wind in moveCommands:
            # this tells the receiving board that this is keyboard, not mouse navigation>
            # needed for useful placement of the popup menu
            self.centralScene.clickedTile = None
            # check opacity because we might be positioned on a hole
            if isinstance(tile, Tile) and tile.opacity:
                if wind == moveCommands[4]:
                    receiver = self.selectorBoard
                    receiver.receive(tile)
                else:
                    targetWind = WINDS[moveCommands.index(wind)]
                    for p in self.players:
                        if p.wind == targetWind:
                            p.handBoard.receive(tile, self.centralView, lowerHalf=mod & Qt.ShiftModifier)
                if not currentBoard.allTiles():
                    self.centralView.scene().setFocusItem(receiver.focusTile)
            return
        if key == Qt.Key_Tab:
            tabItems = [self.selectorBoard]
            tabItems.extend(list(p.handBoard for p in self.players if p.handBoard.focusTile))
            tabItems.append(tabItems[0])
            currIdx = 0
            while tabItems[currIdx] != currentBoard and currIdx < len(tabItems) -2:
                currIdx += 1
            newItem = tabItems[currIdx+1].focusTile
            self.centralView.scene().setFocusItem(newItem)
            return
        KXmlGuiWindow.keyPressEvent(self, event)

    def retranslateUi(self):
        """retranslate"""
        self.actionScoreGame.setText(m18n("&Score Manual Game"))
        self.actionLocalGame.setText(m18n("Play &Local Game"))
        self.actionRemoteGame.setText(m18n("Play &Network Game"))
        self.actionQuit.setText(m18n("&Quit"))
        self.actionPlayers.setText(m18n("&Players"))
        self.actionAngle.setText(m18n("&Change Visual Angle"))
        self.actionScoring.setText(m18n("&Scoring"))
        self.actionScoreTable.setText(m18nc('kmj', "&Score Table"))
        self.actionExplain.setText(m18n("&Explain Scores"))

    def changeEvent(self, event):
        """when the applicationwide language changes, recreate GUI"""
        if event.type() == QEvent.LanguageChange:
            self.setupGUI()
            self.retranslateUi()

    def slotPlayers(self):
        """show the player list"""
        if not self.playerWindow:
            self.playerWindow = PlayerList(self)
        self.playerWindow.show()

    def selectGame(self):
        """show all games, select an existing game or create a new game"""
        gameSelector = Games(self)
        if gameSelector.exec_():
            selected = gameSelector.selectedGame
            if selected is not None:
                game = Game(field=self,  gameid=selected)
            else:
                game = self.newGame()
            if game:
                self.game = game
        return self.game

    def __decorateWalls(self):
        if self.game is None:
            for player in self.players:
                player.wallWind.hide()
            return
        for idx, player in enumerate(self.players):
            wall = self.walls[idx]
            center = wall.center()
            name = player.wallLabel
            name.setText(player.name)
            name.resetTransform()
            name.scale(3, 3)
            if wall.rotation == 180:
                rotateCenter(name, 180)
            name.setParentItem(wall)
            nameRect = QRectF()
            nameRect.setSize(name.mapToParent(name.boundingRect()).boundingRect().size())
            name.setPos(center - nameRect.center())
            name.setZValue(99999999999)
            if self.tileset.desktopFileName == 'jade':
                color = Qt.white
            else:
                color = Qt.black
            name.setBrush(QBrush(QColor(color)))
            windTile = player.wallWind
            windTile.setWind(player.wind,  self.game.roundsFinished)
            windTile.resetTransform()
            rotateCenter(windTile,  -wall.rotation)
            windTile.setPos(center.x()*1.63, center.y()-windTile.rect().height()/2.5)
            windTile.setZValue(99999999999)

    def scoreGame(self):
        """score a local game"""
        if self.selectGame():
            self.actionScoring.setChecked(True)

    def localGame(self):
        pass

    def remoteGame(self):
        """play a remote game"""
        self.tableLists.append(TableList(self.reactor))

    def _adjustView(self):
        """adjust the view such that exactly the wanted things are displayed
        without having to scroll"""
        view, scene = self.centralView, self.centralScene
        oldRect = view.sceneRect()
        view.setSceneRect(scene.itemsBoundingRect())
        newRect = view.sceneRect()
        if oldRect != newRect:
            view.fitInView(scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    @apply
    def tilesetName():
        def fget(self):
            return self.tileset.desktopFileName
        def fset(self, name):
            self.tileset = Tileset(name)
        return property(**locals())

    @apply
    def backgroundName():
        def fget(self):
            return self.background.desktopFileName
        def fset(self, name):
            """setter for backgroundName"""
            self.background = Background(name)
            self.background.setPalette(self.centralWidget())
            self.centralWidget().setAutoFillBackground(True)
        return property(**locals())

    def applySettings(self):
        """apply preferences"""
        self.settingsChanged = True
        if self.tilesetName != util.PREF.tilesetName:
            self.tilesetName = util.PREF.tilesetName
            for item in self.centralScene.items():
                if not isinstance(item, Tile): # shortcut
                    try:
                        item.tileset = self.tileset
                    except AttributeError:
                        continue
            # change players last because we need the wall already to be repositioned
            self.__decorateWalls()
            self._adjustView() # the new tiles might be larger
        if self.backgroundName != util.PREF.backgroundName:
            self.backgroundName = util.PREF.backgroundName

    def showSettings(self):
        """show preferences dialog. If it already is visible, do nothing"""
        if  KConfigDialog.showDialog("settings"):
            return
        confDialog = ConfigDialog(self, "settings")
        self.connect(confDialog, SIGNAL('settingsChanged(QString)'),
           self.applySettings)
        confDialog.show()

    def newGame(self):
        """asks user for players and ruleset for a new game and returns that new game"""
        Players.load() # we want to make sure we have the current definitions
        selectDialog = SelectPlayers(self.game)
        # if we have a selectable ruleset with the same name as the last used ruleset
        # use that selectable ruleset. We do not want to use the exact same last used
        # ruleset because we might have made some fixes to the ruleset meanwhile
        qData = Query("select name from usedruleset order by lastused desc").data
        if qData:
            lastUsed = qData[0][0]
            if lastUsed in selectDialog.cbRuleset.names():
                selectDialog.cbRuleset.currentName = lastUsed
        if not selectDialog.exec_():
            return
        # initialise the four winds with the first four players:
        for idx, player in enumerate(self.players):
            player.name = selectDialog.names[idx]
            player.wind = WINDS[idx]
            player.balance = 0
        return Game(self.players,  field=self, ruleset=selectDialog.cbRuleset.current)

    def toggleWidget(self, checked):
        """user has toggled widget visibility with an action"""
        action = self.sender()
        data = action.data().toPyObject()
        if checked:
            if isinstance(data, type):
                data = data(self)
                action.setData(QVariant(data))
                if isinstance(data, ScoringDialog):
                    self.scoringDialog = data
                    self.connect(data.btnSave, SIGNAL('clicked(bool)'), self.saveHand)
                    self.connect(data, SIGNAL('scoringClosed()'), self.scoringClosed)
                elif isinstance(data, ExplainView):
                    self.explainView = data
                elif isinstance(data, ScoreTable):
                    self.scoreTable = data
            data.show()
            data.raise_()
        else:
            assert data
            data.hide()

    def scoringClosed(self):
        """the scoring window has been closed with ALT-F4 or similar"""
        self.actionScoring.setChecked(False)

    @staticmethod
    def __windOrder(player):
        return 'ESWN'.index(player.wind)

    def saveHand(self):
        """save hand to data base, update score table and balance in status line"""
        self.game.saveHand()
        self.showBalance()
        if self.game.finished():
            self.game = None
        else:
            if self.game.rotated == 0:
                # players may have swapped seats but we want ESWN order
                # in the scoring dialog
                handBoards = list([p.handBoard for p in self.players])
                self.players.sort(key=PlayField.__windOrder)
                for idx, player in enumerate(self.players):
                    player.handBoard = handBoards[idx]
        self.scoringDialog.refresh()
        self.__decorateWalls()

    @apply
    def game():
        """the currently show game in the GUI"""
        def fget(self):
            return self.__game
        def fset(self, game):
            if self.__game != game:
                self.__game = game
                self.selectorBoard.setVisible(game is not None)
                self.centralView.scene().setFocusItem(self.selectorBoard.childItems()[0])
                if game:
                    self.__decorateWalls()
                    self.actionScoreTable.setChecked(game.handctr)
                    self.actionScoring.setEnabled(game is not None and game.roundsFinished < 4)
                else:
                    self.actionScoring.setChecked(False)
                    self.walls.build()
                self.showBalance()
                for player in self.players:
                    player.handBoard.clear()
                    player.handBoard.setVisible(game is not None)
                    player.handBoard.helperGroup.setVisible(True)
                for view in [self.scoringDialog, self.explainView,  self.scoreTable]:
                    if view:
                        view.refresh()
                for player in self.players:
                    player.refresh()
        return property(**locals())

    def changeAngle(self):
        """change the lightSource"""
        oldIdx = LIGHTSOURCES.index(self.walls.lightSource)
        newLightSource = LIGHTSOURCES[(oldIdx + 1) % 4]
        self.walls.lightSource = newLightSource
        self.selectorBoard.lightSource = newLightSource
        self.__decorateWalls()
        self._adjustView()
        scoringDialog = self.actionScoring.data().toPyObject()
        if isinstance(scoringDialog, ScoringDialog):
            scoringDialog.computeScores()

    def showBalance(self):
        """show the player balances in the status bar"""
        if self.scoreTable:
            self.scoreTable.refresh()
        sBar = self.statusBar()
        if self.game:
            for idx, player in enumerate(self.game.players):
                sbMessage = player.name + ': ' + str(player.balance)
                if sBar.hasItem(idx):
                    sBar.changeItem(sbMessage, idx)
                else:
                    sBar.insertItem(sbMessage, idx, 1)
                    sBar.setItemAlignment(idx, Qt.AlignLeft)
        else:
            for idx in range(5):
                if sBar.hasItem(idx):
                    sBar.removeItem(idx)

    def lastTile(self):
        """compile hand info into  a string as needed by the scoring engine"""
        if self.scoringDialog:
            cbLastTile = self.scoringDialog.cbLastTile
            idx = cbLastTile.currentIndex()
            if idx >= 0:
                return bytes(cbLastTile.itemData(idx).toString())
        return ''

    def lastMeld(self):
        """compile hand info into  a string as needed by the scoring engine"""
        if self.scoringDialog:
            cbLastMeld = self.scoringDialog.cbLastMeld
            idx = cbLastMeld.currentIndex()
            if idx >= 0:
                return bytes(cbLastMeld.itemData(idx).toString())
        return ''

    def winner(self):
        """return the player GUI of the winner"""
        for idx in range(4):
            if self.game.winner == self.game.players[idx]:
                return self.players[idx]
        return None

    def askSwap(self, swappers):
        """ask the user if two players should change seats"""
        # do not make this a staticmethod because we do not want
        # to import PlayField in game.py
        mbox = QMessageBox()
        mbox.setWindowTitle(m18n("Swap Seats") + ' - kmj')
        mbox.setText("By the rules, %s and %s should now exchange their seats. " % \
            (swappers[0].name, swappers[1].name))
        yesAnswer = QPushButton("&Exchange")
        mbox.addButton(yesAnswer, QMessageBox.YesRole)
        noAnswer = QPushButton("&Keep seat")
        mbox.addButton(noAnswer, QMessageBox.NoRole)
        mbox.exec_()
        return mbox.clickedButton() == yesAnswer

