#!/usr/bin/env python
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
        QEvent, QMetaObject, PYQT_VERSION_STR, QPointF
    from PyQt4.QtGui import QColor, QPushButton,  QMessageBox
    from PyQt4.QtGui import QWidget, QFont
    from PyQt4.QtGui import QGridLayout, QVBoxLayout
    from PyQt4.QtGui import QDialog, QGraphicsSimpleTextItem
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
    from tile import Tile
    from board import PlayerWind, WindLabel,  FittingView, \
        Board, HandBoard,  SelectorBoard, DiscardBoard, MJScene,  \
        YellowText
    from playerlist import PlayerList
    from tileset import Tileset, LIGHTSOURCES
    from background import Background
    from games import Games
    from game import Wall
    from config import Preferences, ConfigDialog
    from scoringengine import Ruleset, PredefinedRuleset, HandContent, Meld
    from scoring import ExplainView,  ScoringDialog, ScoreTable, ListComboBox, RuleBox
    from tables import TableList
    from client import HumanClient

    from game import Game,  Players,  Player

except ImportError,  e:
    NOTFOUND.append('kajongg modules: %s' % e)

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
        self.setWindowTitle(m18n('Select four players') + ' - Kajongg')
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

        query = Query("select p0,p1,p2,p3 from game where server='' and game.id = (select max(id) from game)")
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
    def __init__(self, game, idx):
        assert game
        Player.__init__(self, game)
        self.idx = idx
        self.front = game.wall[idx]
        self.manualRuleBoxes = []
        self.handBoard = HandBoard(self)
        self.handBoard.setVisible(False)
        self.handBoard.setPos(yHeight= 1.5)

    def addTile(self, tileName, sync=True):
        """player gets tile"""
        Player.addTile(self, tileName)
        if sync:
            self.syncHandBoard(tileName)

    def removeTile(self, tileName):
        """player loses tile"""
        Player.removeTile(self, tileName)
        self.syncHandBoard()

    def exposeMeld(self, meldTiles, claimed=True):
        """player exposes meld"""
        Player.exposeMeld(self, meldTiles, claimed)
        self.syncHandBoard()

    def clearHand(self):
        """clears data related to current hand"""
        self.manualRuleBoxes = []
        if self.handBoard:
            self.handBoard.clear()
        Player.clearHand(self)

    def hasManualScore(self):
        """True if no tiles are assigned to this player"""
        if self.game.field.scoringDialog:
            return self.game.field.scoringDialog.spValues[self.idx].isEnabled()
        return False

    def syncHandBoard(self, tileName=None):
        """update display of handBoard"""
        myBoard = self.handBoard
        myBoard.clear()
        for meld in self.exposedMelds:
            myBoard.receive(meld.pairs, None, False)
        for tile in self.bonusTiles:
            myBoard.receive(tile, None, False)
        if self.concealedMelds:
            # hand has ended
            for meld in self.concealedMelds:
                myBoard.receive(meld.pairs, None, True)
        else:
            tileStr = ''.join(self.concealedTiles)
            content = HandContent(self.game.ruleset, tileStr)
            for meld in content.sortedMelds.split():
                myBoard.receive(meld, None, True)
            for exposed in myBoard.exposedTiles():
                exposed.focusable = False
            tiles = myBoard.lowerHalfTiles()
            if tiles:
                if self == self.game.myself and tileName and tileName[0] not in 'fy':
                    myBoard.focusTile = [x for x in tiles if x.element == tileName][-1]
                elif tiles[-1].element != 'Xy':
                    myBoard.focusTile = tiles[-1]
            self.game.field.centralView.scene().setFocusItem(myBoard.focusTile)

    def refreshManualRules(self, sender=None):
        """update status of manual rules"""
        assert self.game.field
        senderChecked = sender and isinstance(sender, RuleBox) and sender.isChecked()
        self.handContent = self.computeHandContent()
        currentScore = self.handContent.score
        hasManualScore = self.hasManualScore()
        for box in self.manualRuleBoxes:
            if box.rule in self.handContent.computedRules:
                box.setVisible(True)
                box.setChecked(True)
                box.setEnabled(False)
            else:
                applicable = self.handContent.ruleMayApply(box.rule)
                if hasManualScore:
                    # only those rules which do not affect the score can be applied
                    applicable &= box.rule.hasNonValueAction()
                else:
                    # if the action would only influence the score and the rule does not change the score,
                    # ignore the rule. If however the action does other things like penalties leave it applicable
                    if not senderChecked:
                        applicable &= bool(box.rule.hasNonValueAction()) or self.computeHandContent(box.rule).score > currentScore
                box.setApplicable(applicable)

    def __mjString(self):
        """compile hand info into  a string as needed by the scoring engine"""
        winds = self.wind.lower() + 'eswn'[self.game.roundsFinished]
        wonChar = 'm'
        if self == self.game.winner:
            wonChar = 'M'
        lastSource = 'd'
        lastTile = self.game.field.lastTile()
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
        if self != self.game.winner:
            return ''
        return 'L%s%s' % (self.game.field.lastTile(), self.game.field.lastMeld().joined)

    def computeHandContent(self, singleRule=None, withTile=None):
        """returns a HandContent object, using a cache"""
        game = self.game
        if not game.isScoringGame():
            # maybe we need a more extended class hierarchy for Player, VisiblePlayer, ScoringPlayer,
            # PlayingPlayer but not now. Just make sure that ExplainView can always call the
            # same computeHandContent regardless of the game type
            return Player.computeHandContent(self, withTile=withTile)
        if not self.handBoard:
            return None
        string = ' '.join([self.handBoard.scoringString(), self.__mjString(), self.__lastString()])
        mRules = list(x.rule for x in self.manualRuleBoxes if x.isChecked())
        if game.eastMJCount == 8 and self == game.winner and self.wind == 'E':
            cRules = [game.ruleset.findManualRule('XXXE9')]
        else:
            cRules = None
        if singleRule:
            mRules.append(singleRule)
        return HandContent.cached(game.ruleset, string,
            manuallyDefinedRules=mRules, computedRules=cRules)

    def popupMsg(self, msg):
        """shows a yellow message from player"""
        self.front.message.setText(msg)
        self.front.message.setVisible(True)

    def  hidePopup(self, arg=None):
        """hide the yellow message from player"""
        self.front.message.setVisible(False)

class WallSide(Board):
    """a Board representing a wall of tiles"""
    def __init__(self, tileset, rotation, length):
        Board.__init__(self, length, 1, tileset, rotation=rotation)
        self.length = length

    def center(self):
        """returns the center point of the wall in relation to the faces of the upper level"""
        faceRect = self.tileFaceRect()
        result = faceRect.topLeft() + self.shiftZ(1) + \
            QPointF(self.length // 2 * faceRect.width(), faceRect.height()/2)
        result.setX(result.x() + faceRect.height()/2) # corner tile
        return result

class VisibleWall(Wall):
    """represents the wall with four sides. self.wall[] indexes them counter clockwise, 0..3. 0 is bottom."""
    def __init__(self, game):
        """init and position the wall"""
        # we use only white dragons for building the wall. We could actually
        # use any tile because the face is never shown anyway.
        Wall.__init__(self, game)
        self.__square = Board(self.length+1, self.length+1, self.game.field.tileset)
        self.__sides = [WallSide(self.game.field.tileset, rotation, self.length) for rotation in (0, 270, 180, 90)]
        for side in self.__sides:
            side.setParentItem(self.__square)
            side.lightSource = self.lightSource
            side.windTile = PlayerWind('E', self.game.field.windTileset, parent=side)
            side.windTile.hide()
            side.nameLabel = QGraphicsSimpleTextItem('', side)
            font = side.nameLabel.font()
            font.setWeight(QFont.Bold)
            font.setPointSize(36)
            side.nameLabel.setFont(font)
            side.message = YellowText(side)
            side.message.setVisible(False)
            side.message.setPos(side.center())
            side.message.setZValue(1e30)
        self.__sides[0].setPos(yWidth=self.length)
        self.__sides[3].setPos(xHeight=1)
        self.__sides[2].setPos(xHeight=1, xWidth=self.length, yHeight=1)
        self.__sides[1].setPos(xWidth=self.length, yWidth=self.length, yHeight=1 )
        self.game.field.centralScene.addItem(self.__square)

    def __getitem__(self, index):
        """make Wall index-able"""
        return self.__sides[index]

    def hide(self):
        for side in self.__sides:
            side.windTile.hide()
            side.nameLabel.hide()
            side.hide()
            del side
        self.game.field.centralScene.removeItem(self.__square)

    def build(self, tiles=None):
        """builds the wall from tiles without dividing them"""

        # first do a normal build without divide
        # replenish the needed tiles
        Wall.build(self, tiles)
        for tile in self.tiles:
            tile.focusable = False
            tile.dark = False
            tile.show()
        tileIter = iter(self.tiles)
        for side in (self.__sides[0], self.__sides[3], self.__sides[2],  self.__sides[1]):
            upper = True     # upper tile is played first
            for position in range(self.length*2-1, -1, -1):
                tile = tileIter.next()
                tile.board = side
                tile.setPos(position//2, level=1 if upper else 0)
                upper = not upper
        self.setDrawingOrder()

    @apply
    def lightSource():
        def fget(self):
            return self.__square.lightSource
        def fset(self, lightSource):
            if self.lightSource != lightSource:
                self.__square.lightSource = lightSource
                for side in self.__sides:
                    side.lightSource = lightSource
                self.setDrawingOrder()
        return property(**locals())

    def setDrawingOrder(self):
        """set drawing order of the wall"""
        levels = {'NW': (2, 3, 1, 0), 'NE':(3, 1, 0, 2), 'SE':(1, 0, 2, 3), 'SW':(0, 2, 3, 1)}
        for idx, side in enumerate(self.__sides):
            side.level = levels[side.lightSource][idx]*1000
        self.__square.setDrawingOrder()

    def _moveDividedTile(self,  tile, offset):
        """moves a tile from the divide hole to its new place"""
        newOffset = tile.xoffset + offset
        if newOffset >= self.length:
            sideIdx = self.__sides.index(tile.board)
            tile.board = self.__sides[(sideIdx+1) % 4]
        tile.setPos(newOffset % self.length, level=2)

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

    def _setRect(self):
        """translate from our rect coordinates to scene coord"""
        bottom = self.__sides[0]
        sideLength = bottom.rect().width() + bottom.rect().height()
        # not quite correct - should be adjusted by shadows, but
        # sufficient for our needs
        rect = self.rect()
        rect.setWidth(sideLength)
        rect.setHeight(sideLength)
        self.prepareGeometryChange()
        QGraphicsRectItem.setRect(self, rect)

    def decorate(self):
        """show player info on the wall"""
        for player in self.game.players:
            side = player.front
            sideCenter = side.center()
            name = side.nameLabel
            name.setText(m18nc('kajongg', player.name))
            name.resetTransform()
            if side.rotation == 180:
                rotateCenter(name, 180)
            nameRect = QRectF()
            nameRect.setSize(name.mapToParent(name.boundingRect()).boundingRect().size())
            name.setPos(sideCenter  - nameRect.center())
            name.setZValue(99999999999)
            if player == self.game.activePlayer:
                color = Qt.blue
            elif self.game.field.tileset.desktopFileName == 'jade':
                color = Qt.white
            else:
                color = Qt.black
            name.setBrush(QBrush(QColor(color)))
            side.windTile.setWind(player.wind, self.game.roundsFinished)
            side.windTile.resetTransform()
            side.windTile.setPos(sideCenter.x()*1.63, sideCenter.y()-side.windTile.rect().height()/2.5)
            side.windTile.setZValue(99999999999)
            side.nameLabel.show()
            side.windTile.show()


class PlayField(KXmlGuiWindow):
    """the main window"""

    def __init__(self,  reactor):
        # see http://lists.kde.org/?l=kde-games-devel&m=120071267328984&w=2
        self.reactor = reactor
        self.reactorStopped = False
        self.game = None
        self.ignoreResizing = 1
        super(PlayField, self).__init__()
        Preferences() # defines PREF
        self.background = None
        self.settingsChanged = False
        self.clientDialogGeometry = None

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

    def showEvent(self, event):
        """force a resize which calculates the correct background image size"""
        self.centralView.resizeEvent(True)
        KXmlGuiWindow.showEvent(self, event)

    def handSelectorChanged(self, handBoard):
        """update all relevant dialogs"""
        if self.scoringDialog:
            self.scoringDialog.fillLastTileCombo()
            self.scoringDialog.computeScores()
        if self.explainView:
            self.explainView.refresh(self.game)
        if self.game:
            self.game.checkSelectorTiles()

    def kajonggAction(self,  name, icon, slot=None, shortcut=None, data=None):
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

    def kajonggToggleAction(self, name, icon, shortcut=None, data=None):
        """a checkable action"""
        res = self.kajonggAction(name, icon, shortcut=shortcut, data=data)
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
        self.windTileset = Tileset(util.PREF.windTilesetName)

        self.discardBoard = DiscardBoard(self)
        self.discardBoard.setVisible(False)
        scene.addItem(self.discardBoard)

        self.selectorBoard = SelectorBoard(self)
        self.selectorBoard.setVisible(False)
# TODO:       self.gameOverLabel = QLabel(m18n('The game is over!'))
        scene.addItem(self.selectorBoard)

        self.connect(scene, SIGNAL('tileClicked'), self.tileClicked)

        self.setCentralWidget(centralWidget)
        self.centralView.setScene(scene)
        self.centralView.setFocusPolicy(Qt.StrongFocus)
        self._adjustView()
        self.actionScoreGame = self.kajonggAction("scoreGame", "draw-freehand", self.scoreGame, Qt.Key_C)
        self.actionPlayGame = self.kajonggAction("play", "arrow-right", self.playGame, Qt.Key_P)
        self.actionAbortGame = self.kajonggAction("abort", "dialog-close", self.abortGame, Qt.Key_W)
        self.actionAbortGame.setEnabled(False)
        self.actionQuit = self.kajonggAction("quit", "application-exit", self.quit, Qt.Key_Q)
        self.actionPlayers = self.kajonggAction("players",  "im-user",  self.slotPlayers)
        self.actionScoring = self.kajonggToggleAction("scoring", "draw-freehand", shortcut=Qt.Key_S, data=ScoringDialog)
        self.actionScoring.setEnabled(False)
        self.actionAngle = self.kajonggAction("angle",  "object-rotate-left",  self.changeAngle, Qt.Key_G)
        self.actionFullscreen = KToggleFullScreenAction(self.actionCollection())
        self.actionFullscreen.setShortcut(Qt.CTRL + Qt.Key_F)
        self.actionFullscreen.setShortcutContext(Qt.ApplicationShortcut)
        self.actionFullscreen.setWindow(self)
        self.actionCollection().addAction("fullscreen", self.actionFullscreen)
        self.connect(self.actionFullscreen, SIGNAL('toggled(bool)'), self.fullScreen)
        self.actionScoreTable = self.kajonggToggleAction("scoreTable", "format-list-ordered",
            Qt.Key_T, data=ScoreTable)
        self.actionExplain = self.kajonggToggleAction("explain", "applications-education",
            Qt.Key_E, data=ExplainView)
        QMetaObject.connectSlotsByName(self)

    def showWall(self):
        self.game.wall = VisibleWall(self.game)
        if self.discardBoard:
            # scale it such that it uses the place within the wall optimally.
            # we need to redo this because the wall length can vary between games.
            self.discardBoard.scale()

    def genPlayers(self):
        return Players([VisiblePlayer(self.game, idx) for idx in range(4)])

    def fullScreen(self, toggle):
        """toggle between full screen and normal view"""
        self.actionFullscreen.setFullScreen(self, toggle)

    def quit(self):
        """exit the application"""
        if  self.reactorStopped:
            sys.exit()
        if self.game:
            self.game.close(self.gameClosed)
        else:
            self.gameClosed()

    def gameClosed(self, result=None):
        if not self.reactorStopped:
            self.reactor.stop()
            self.reactorStopped = True
        HumanClient.stopLocalServer()
        # we are in a Deferred callback which would catch sys.exit as an exception
        # and the qt4reactor does not quit the app when being stopped
        self.connect(self, SIGNAL('reactorStopped'), self.quit)
        self.emit(SIGNAL('reactorStopped'))

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
        wind = chr(key%128)
        moveCommands = m18nc('kajongg:keyboard commands for moving tiles to the players ' \
            'with wind ESWN or to the central tile selector (X)', 'ESWNX')
        if wind in moveCommands:
            # this tells the receiving board that this is keyboard, not mouse navigation>
            # needed for useful placement of the popup menu
            self.centralScene.clickedTile = None
            # check opacity because we might be positioned on a hole
            if isinstance(tile, Tile) and tile.opacity:
                if wind == moveCommands[4]:
                    receiver = self.selectorBoard
                    if receiver.isEnabled():
                        receiver.receive(tile)
                else:
                    targetWind = WINDS[moveCommands.index(wind)]
                    for p in self.game.players:
                        if p.wind == targetWind:
                            receiver = p.handBoard
                            lowerHalf = mod & Qt.ShiftModifier
                            if receiver.isEnabled(lowerHalf):
                                receiver.receive(tile, self.centralView, lowerHalf=lowerHalf)
                if receiver.isEnabled() and not currentBoard.allTiles():
                    self.centralView.scene().setFocusItem(receiver.focusTile)
                else:
                    self.centralView.scene().setFocusItem(currentBoard.focusTile)
            return
        if key == Qt.Key_Tab and self.game:
            tabItems = []
            if self.selectorBoard.isEnabled():
                tabItems = [self.selectorBoard]
            tabItems.extend(list(p.handBoard for p in self.game.players if p.handBoard.focusTile))
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
        self.actionPlayGame.setText(m18n("&Play"))
        self.actionAbortGame.setText(m18n("&Abort"))
        self.actionQuit.setText(m18n("&Quit"))
        self.actionPlayers.setText(m18n("&Players"))
        self.actionAngle.setText(m18n("&Change Visual Angle"))
        self.actionScoring.setText(m18n("&Scoring"))
        self.actionScoreTable.setText(m18nc('kajongg', "&Score Table"))
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
                Game.load(selected, self)
            else:
                self.newGame()
            if self.game:
                self.selectorBoard.fill(self.game)
                if self.game.isScoringGame():
                    self.centralView.scene().setFocusItem(self.selectorBoard.childItems()[0])
                self.game.throwDices()
        self.refresh()
        return bool(self.game)

    def scoreGame(self):
        """score a local game"""
        if self.selectGame():
            self.actionScoring.setChecked(True)

    def playGame(self):
        """play a remote game: log into a server and show its tables"""
        self.tableLists.append(TableList(self))

    def abortGame(self):
        """aborts current game"""
        # TODO: ask for confirmation
        # TODO: other human players wait forever
        self.game.close()

    def _adjustView(self):
        """adjust the view such that exactly the wanted things are displayed
        without having to scroll"""
        if self.game:
            if self.discardBoard:
                self.discardBoard.scale()
            if self.selectorBoard:
                self.selectorBoard.scale()
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
            return self.background.desktopFileName if self.background else ''
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
            if self.game:
                self.game.wall.decorate()
            self._adjustView() # the new tiles might be larger
        if self.isVisible() and self.backgroundName != util.PREF.backgroundName:
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
        return Game(selectDialog.names, selectDialog.cbRuleset.current, field=self)

    def toggleWidget(self, checked):
        """user has toggled widget visibility with an action"""
        action = self.sender()
        data = action.data().toPyObject()
        if checked:
            if isinstance(data, type):
                data = data(self.game)
                action.setData(QVariant(data))
                if isinstance(data, ScoringDialog):
                    self.scoringDialog = data
                    self.connect(data.btnSave, SIGNAL('clicked(bool)'), self.nextHand)
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

    def nextHand(self):
        """save hand to data base, update score table and balance in status line, prepare next hand"""
        self.game.saveHand()
        self.game.maybeRotateWinds()
        self.game.prepareHand()

    def prepareHand(self):
        """redecorate wall"""
        if not self.game:
            self.refresh()
            return
        if not self.game.finished():
            self.discardBoard.clear()
            if self.scoringDialog and self.game.rotated == 0:
                # players may have swapped seats but we want ESWN order
                # in the scoring dialog
                self.game.sortPlayers()
        self.refresh()
        self.game.wall.decorate()

    def refresh(self):
        game = self.game
        for action in [self.actionScoreGame, self.actionPlayGame]:
            action.setEnabled(not bool(game))
        self.actionAbortGame.setEnabled(bool(game))
        scoring = bool(game and game.isScoringGame())
        self.selectorBoard.setVisible(scoring)
        self.selectorBoard.setEnabled(scoring)
        self.discardBoard.setVisible(bool(game) and not scoring)
        if game:
            self.actionScoring.setEnabled(game is not None and game.roundsFinished < 4)
        else:
            self.actionScoring.setChecked(False)
        for view in [self.scoringDialog, self.explainView,  self.scoreTable]:
            if view:
                view.refresh(game)
        self.__showBalance()

    def changeAngle(self):
        """change the lightSource"""
        if self.game:
            wall = self.game.wall
            oldIdx = LIGHTSOURCES.index(wall.lightSource)
            newLightSource = LIGHTSOURCES[(oldIdx + 1) % 4]
            wall.lightSource = newLightSource
            wall.decorate()
        self.selectorBoard.lightSource = newLightSource
        self._adjustView()
        scoringDialog = self.actionScoring.data().toPyObject()
        if isinstance(scoringDialog, ScoringDialog):
            scoringDialog.computeScores()

    def __showBalance(self):
        """show the player balances in the status bar"""
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
                return Meld(bytes(cbLastMeld.itemData(idx).toString()))
        return Meld()

    def askSwap(self, swappers):
        """ask the user if two players should change seats"""
        # do not make this a staticmethod because we do not want
        # to import PlayField in game.py
        mbox = QMessageBox()
        mbox.setWindowTitle(m18n("Swap Seats") + ' - Kajongg')
        mbox.setText("By the rules, %s and %s should now exchange their seats. " % \
            (swappers[0].name, swappers[1].name))
        yesAnswer = QPushButton("&Exchange")
        mbox.addButton(yesAnswer, QMessageBox.YesRole)
        noAnswer = QPushButton("&Keep seat")
        mbox.addButton(noAnswer, QMessageBox.NoRole)
        mbox.exec_()
        return mbox.clickedButton() == yesAnswer

    def hideAllFocusRect(self):
        if self.game:
            boards = [x.handBoard for x in self.game.players]
            boards.append(self.selectorBoard)
            boards.append(self.discardBoard)
            for board in boards:
                if board:
                    board.hideFocusRect()
