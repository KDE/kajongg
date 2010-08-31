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

import sys
import os
from util import logMessage, m18n, m18nc, isAlive
import common
from common import WINDS, LIGHTSOURCES, InternalParameters
import cgitb, tempfile, webbrowser

class MyHook(cgitb.Hook):
    """override the standard cgitb hook: invoke the browser"""
    def __init__(self):
        self.tmpFileName = tempfile.mkstemp(suffix='.html', prefix='bt_', text=True)[1]
        cgitb.Hook.__init__(self, file=open(self.tmpFileName, 'w'))

    def handle(self, info=None):
        """handling the exception: show backtrace in browser"""
        cgitb.Hook.handle(self, info)
        webbrowser.open(self.tmpFileName)

sys.excepthook = MyHook()

NOTFOUND = []

try:
    from PyQt4.QtCore import Qt, QVariant, SIGNAL, \
        QEvent, QMetaObject, PYQT_VERSION_STR, QString
    from PyQt4.QtGui import QPushButton, QMessageBox
    from PyQt4.QtGui import QWidget
    from PyQt4.QtGui import QGridLayout
    from PyQt4.QtGui import QDialogButtonBox
    from PyQt4.QtGui import QComboBox
    from PyQt4.QtGui import QVBoxLayout, QSpacerItem, QSizePolicy, QCheckBox
except ImportError, e:
    NOTFOUND.append('Package python-qt4: PyQt4: %s' % e)

try:
    from zope.interface import implements # pylint: disable-msg=W0611
except ImportError, e:
    NOTFOUND.append('Package python-zope-interface missing: %s' % e)

try:
    from PyKDE4.kdeui import KApplication, KStandardAction, KAction, KToggleFullScreenAction
    from PyKDE4.kdeui import KXmlGuiWindow, KIcon, KConfigDialog, KMessageBox
except ImportError, e :
    NOTFOUND.append('Package python-kde4: PyKDE4: %s' % e)

try:
    from query import Query
    from tile import Tile
    from board import WindLabel, FittingView, SelectorBoard, DiscardBoard, MJScene
    from handboard import HandBoard
    from playerlist import PlayerList
    from tileset import Tileset
    from background import Background
    from games import Games
    from statesaver import StateSaver
    from scoringengine import HandContent, Meld
    from scoring import ExplainView, ScoringDialog, ScoreTable
    from tables import TableList, SelectRuleset
    from humanclient import HumanClient
    from rulesetselector import RulesetSelector
    from tilesetselector import TilesetSelector
    from backgroundselector import BackgroundSelector
    from sound import Sound
    from uiwall import UIWall

    from game import Game, Players, Player

except ImportError, e:
    NOTFOUND.append('kajongg is not correctly installed: modules: %s' % e)

if len(NOTFOUND):
    MSG = "\n".join(" * %s" % s for s in NOTFOUND)
    logMessage(MSG)
    os.popen("kdialog --sorry '%s'" % MSG)
    sys.exit(3)

class PlayConfigTab( QWidget):
    """Display Config tab"""
    def __init__(self, parent):
        super(PlayConfigTab, self).__init__(parent)
        self.setupUi()

    def setupUi(self):
        """layout the window"""
        vlayout = QVBoxLayout(self)
        self.kcfg_showShadows = QCheckBox(m18n('Show tile shadows'), self)
        self.kcfg_showShadows.setObjectName('kcfg_showShadows')
        self.kcfg_rearrangeMelds = QCheckBox(m18n('Rearrange undisclosed tiles to melds'), self)
        self.kcfg_rearrangeMelds.setObjectName('kcfg_rearrangeMelds')
        self.kcfg_useSounds = QCheckBox(m18n('Use sounds if available'), self)
        self.kcfg_useSounds.setObjectName('kcfg_useSounds')
        self.kcfg_uploadVoice = QCheckBox(m18n('Let others hear my voice'), self)
        self.kcfg_uploadVoice.setObjectName('kcfg_uploadVoice')
        pol = QSizePolicy()
        pol.setHorizontalPolicy(QSizePolicy.Expanding)
        pol.setVerticalPolicy(QSizePolicy.Expanding)
        spacerItem = QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        vlayout.addWidget(self.kcfg_showShadows)
        vlayout.addWidget(self.kcfg_rearrangeMelds)
        vlayout.addWidget(self.kcfg_useSounds)
        vlayout.addWidget(self.kcfg_uploadVoice)
        vlayout.addItem(spacerItem)
        self.setSizePolicy(pol)
        self.retranslateUi()

    def retranslateUi(self):
        """translate to current language"""
        pass

class ConfigDialog(KConfigDialog):
    """configuration dialog with several pages"""
    def __init__(self, parent, name):
        super(ConfigDialog, self).__init__(parent, QString(name), common.PREF)
        self.rulesetSelector = RulesetSelector(self)
        self.pages = []
        self.pages.append(self.addPage(PlayConfigTab(self),
                m18nc('kajongg','Play'), "arrow-right"))
        self.pages.append(self.addPage(TilesetSelector(self),
                m18n("Tiles"), "games-config-tiles"))
        self.pages.append(self.addPage(BackgroundSelector(self),
                m18n("Backgrounds"), "games-config-background"))
        self.pages.append(self.addPage(self.rulesetSelector,
                m18n("Rulesets"), "games-kajongg-law"))
        StateSaver(self)

    def keyPressEvent(self, event):
        """The four tabs can be selected with CTRL-1 .. CTRL-4"""
        mod = event.modifiers()
        key = chr(event.key()%128)
        if Qt.ControlModifier | mod and key in '1234':
            self.setCurrentPage(self.pages[int(key)-1])
            return
        KConfigDialog.keyPressEvent(self, event)

    def showEvent(self, dummyEvent):
        """start transaction"""
        self.rulesetSelector.refresh()
        Query.dbhandle.transaction()

    def accept(self):
        """commit transaction"""
        if self.rulesetSelector.save():
            if Query.dbhandle.commit():
                KConfigDialog.accept(self)
                return
        KMessageBox.sorry(None, m18n('Cannot save your ruleset changes.<br>' \
            'You probably introduced a duplicate name. <br><br >Message from database:<br><br>' \
           '<message>%1</message>', Query.lastError))

    def reject(self):
        """rollback transaction"""
        self.rulesetSelector.cancel()
        Query.dbhandle.rollback()
        KConfigDialog.reject(self)


class SwapDialog(QMessageBox):
    """ask the user if two players should change seats"""
    def __init__(self, swappers):
        QMessageBox.__init__(self)
        self.setWindowTitle(m18n("Swap Seats") + ' - Kajongg')
        self.setText(m18n("By the rules, %1 and %2 should now exchange their seats. ",
            swappers[0].name, swappers[1].name))
        self.yesAnswer = QPushButton(m18n("&Exchange"))
        self.addButton(self.yesAnswer, QMessageBox.YesRole)
        self.noAnswer = QPushButton(m18n("&Keep seat"))
        self.addButton(self.noAnswer, QMessageBox.NoRole)

    def exec_(self):
        """I do not understand the logic of the exec return value. The yes button returns 0
        and the no button returns 1. According to the C++ doc, the return value is an
        opaque value that should not be used."""
        return  self.clickedButton() == self.yesAnswer

class SelectPlayers(SelectRuleset):
    """a dialog for selecting four players"""
    def __init__(self, game):
        SelectRuleset.__init__(self, game.client.host if game and game.client else None)
        self.game = game
        Players.load()
        self.setWindowTitle(m18n('Select four players') + ' - Kajongg')
        self.names = None
        self.nameWidgets = []
        for idx, wind in enumerate(WINDS):
            cbName = QComboBox()
            # increase width, we want to see the full window title
            cbName.setMinimumWidth(350) # is this good for all platforms?
            # add all player names belonging to no host
            cbName.addItems(list(x[1] for x in Players.allNames.values() if x[0] == ''))
            self.grid.addWidget(cbName, idx+1, 1)
            self.nameWidgets.append(cbName)
            self.grid.addWidget(WindLabel(wind), idx+1, 0)
            self.connect(cbName, SIGNAL('currentIndexChanged(int)'),
                self.slotValidate)

        query = Query("select p0,p1,p2,p3 from game where server='' and game.id = (select max(id) from game)")
        if len(query.records):
            for pidx in range(4):
                playerId = query.records[0][pidx]
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

    def showEvent(self, dummyEvent):
        """start with player 0"""
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
    """this player instance has a visual representation"""
    def __init__(self, game, idx):
        assert game
        self.handBoard = None # because Player.init calls clearHand()
        Player.__init__(self, game)
        self.idx = idx
        self.front = game.wall[idx]
        self.manualRuleBoxes = []
        self.handBoard = HandBoard(self)
        self.handBoard.setVisible(False)

    def removeTile(self, tileName):
        """player loses tile"""
        Player.removeTile(self, tileName)
        self.syncHandBoard()

    def exposeMeld(self, meldTiles, claimed=True):
        """player exposes meld"""
        result = Player.exposeMeld(self, meldTiles, claimed)
        self.syncHandBoard()
        return result

    def clearHand(self):
        """clears attributes related to current hand"""
        self.manualRuleBoxes = []
        if self.handBoard:
            self.handBoard.clear()
        Player.clearHand(self)

    def hasManualScore(self):
        """True if no tiles are assigned to this player"""
        if InternalParameters.field.scoringDialog:
            return InternalParameters.field.scoringDialog.spValues[self.idx].isEnabled()
        return False

    def syncHandBoard(self, tileName=None):
        """update display of handBoard. Set Focus to tileName."""
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
            content = HandContent.cached(self.game.ruleset, tileStr)
            for meld in content.sortedMelds.split():
                myBoard.receive(meld, None, True)
            for exposed in myBoard.exposedTiles():
                exposed.focusable = False
            tiles = myBoard.lowerHalfTiles()
            if tiles:
                if self == self.game.myself and tileName and tileName[0] not in 'fy':
                    myBoard.focusTile = [x for x in tiles if x.element == tileName][-1]
                elif tiles[-1].element != 'Xy' and tiles[-1].focusable:
                    myBoard.focusTile = tiles[-1]

    def robTile(self, tileName):
        """used for robbing the kong"""
        Player.robTile(self, tileName)
        self.syncHandBoard()

    def refreshManualRules(self, sender=None):
        """update status of manual rules"""
        assert InternalParameters.field
        if not self.handBoard:
            # might happen at program exit
            return
        self.handContent = self.computeHandContent()
        currentScore = self.handContent.score
        hasManualScore = self.hasManualScore()
        for box in self.manualRuleBoxes:
            if box.rule in self.handContent.computedRules:
                box.setVisible(True)
                box.setChecked(True)
                box.setEnabled(False)
            else:
                applicable = bool(self.handContent.manualRuleMayApply(box.rule))
                if hasManualScore:
                    # only those rules which do not affect the score can be applied
                    applicable = applicable and box.rule.hasNonValueAction()
                else:
                    # if the action would only influence the score and the rule does not change the score,
                    # ignore the rule. If however the action does other things like penalties leave it applicable
                    if box != sender:
                        if applicable:
                            applicable = bool(box.rule.hasNonValueAction()) \
                                or (self.computeHandContent(singleRule=box.rule).score > currentScore)
                box.setApplicable(applicable)

    def __mjstring(self, singleRule):
        """compile hand info into a string as needed by the scoring engine"""
        winds = self.wind.lower() + 'eswn'[self.game.roundsFinished % 4]
        wonChar = 'm'
        if self == self.game.winner:
            wonChar = 'M'
        lastSource = 'd'
        lastTile = InternalParameters.field.computeLastTile()
        if len(lastTile) and lastTile[0].isupper():
            lastSource = 'w'
        declaration = ''
        rules = [x.rule for x in self.manualRuleBoxes if x.isChecked()]
        if singleRule:
            rules.append(singleRule)
        for rule in rules:
            actions = rule.actions
            if'lastsource' in actions:
                if lastSource != '1':
                    # this defines precedences for source of last tile
                    lastSource = actions['lastsource']
            if 'declaration' in actions:
                declaration = actions['declaration']
        return ''.join([wonChar, winds, lastSource, declaration])

    def __lastString(self):
        """compile hand info into a string as needed by the scoring engine"""
        if self != self.game.winner:
            return ''
        return 'L%s%s' % (InternalParameters.field.computeLastTile(), InternalParameters.field.computeLastMeld().joined)

    def computeHandContent(self, withTile=None, robbedTile=None, singleRule=None):
        """returns a HandContent object, using a cache"""
        game = self.game
        if not game.isScoringGame():
            # maybe we need a more extended class hierarchy for Player, VisiblePlayer, ScoringPlayer,
            # PlayingPlayer but not now. Just make sure that ExplainView can always call the
            # same computeHandContent regardless of the game type
            return Player.computeHandContent(self, withTile=withTile, robbedTile=robbedTile)
        if not self.handBoard:
            return None
        string = ' '.join([self.handBoard.scoringString(), self.__mjstring(singleRule), self.__lastString()])
        if game.eastMJCount == 8 and self == game.winner and self.wind == 'E':
            cRules = [game.ruleset.findRule('XEAST9X')]
        else:
            cRules = []
        if singleRule:
            cRules.append(singleRule)
        return HandContent.cached(game.ruleset, string,
            computedRules=cRules)

    def popupMsg(self, msg):
        """shows a yellow message from player"""
        self.speak(msg.lower())
        self.front.message.setText(m18nc('kajongg', msg))
        self.front.message.setVisible(True)

    def hidePopup(self):
        """hide the yellow message from player"""
        if isAlive(self.front.message):
            self.front.message.setVisible(False)

class PlayField(KXmlGuiWindow):
    """the main window"""
    # pylint: disable-msg=R0902
    # pylint: we need more than 10 instance attributes

    def __init__(self):
        # see http://lists.kde.org/?l=kde-games-devel&m=120071267328984&w=2
        InternalParameters.field = self
        self.game = None
        self.ignoreResizing = 1
        super(PlayField, self).__init__()
        self.background = None
        self.showShadows = None
        self.settingsChanged = False
        self.clientDialog = None

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
        if InternalParameters.autoPlay:
            self.playGame()

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
        if self.clientDialog:
            self.clientDialog.placeInField()


    def showEvent(self, event):
        """force a resize which calculates the correct background image size"""
        self.centralView.resizeEvent(True)
        KXmlGuiWindow.showEvent(self, event)

    def handSelectorChanged(self, handBoard):
        """update all relevant dialogs"""
        if self.scoringDialog:
            self.scoringDialog.slotInputChanged()
        if self.game and not self.game.finished():
            self.game.checkSelectorTiles()
            self.game.wall.decoratePlayer(handBoard.player)
        # first decorate walls - that will compute player.handBoard for explainView
        if self.explainView:
            self.explainView.refresh(self.game)

    def kajonggAction(self, name, icon, slot=None, shortcut=None, actionData=None):
        """simplify defining actions"""
        res = KAction(self)
        res.setIcon(KIcon(icon))
        if slot:
            self.connect(res, SIGNAL('triggered()'), slot)
        self.actionCollection().addAction(name, res)
        if shortcut:
            res.setShortcut( Qt.CTRL + shortcut)
            res.setShortcutContext(Qt.ApplicationShortcut)
        if PYQT_VERSION_STR != '4.5.2' or actionData is not None:
            res.setData(QVariant(actionData))
        return res

    def kajonggToggleAction(self, name, icon, shortcut=None, actionData=None):
        """a checkable action"""
        res = self.kajonggAction(name, icon, shortcut=shortcut, actionData=actionData)
        res.setCheckable(True)
        self.connect(res, SIGNAL('toggled(bool)'), self.__toggleWidget)
        return res

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
        self.centralScene = scene
        self.centralView = FittingView()
        layout = QGridLayout(centralWidget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.centralView)
        self.tileset = None # just for pylint
        self.background = None # just for pylint
        self.tilesetName = common.PREF.tilesetName
        self.windTileset = Tileset(common.PREF.windTilesetName)

        self.discardBoard = DiscardBoard()
        self.discardBoard.setVisible(False)
        scene.addItem(self.discardBoard)

        self.selectorBoard = SelectorBoard()
        self.selectorBoard.setVisible(False)
        scene.addItem(self.selectorBoard)

        self.setCentralWidget(centralWidget)
        self.centralView.setScene(scene)
        self.centralView.setFocusPolicy(Qt.StrongFocus)
        self.adjustView()
        self.actionScoreGame = self.kajonggAction("scoreGame", "draw-freehand", self.scoreGame, Qt.Key_C)
        self.actionPlayGame = self.kajonggAction("play", "arrow-right", self.playGame, Qt.Key_N)
        self.actionAbortGame = self.kajonggAction("abort", "dialog-close", self.abortGame, Qt.Key_W)
        self.actionAbortGame.setEnabled(False)
        self.actionQuit = self.kajonggAction("quit", "application-exit", self.quit, Qt.Key_Q)
        self.actionPlayers = self.kajonggAction("players",  "im-user", self.slotPlayers)
        self.actionScoring = self.kajonggToggleAction("scoring", "draw-freehand",
            shortcut=Qt.Key_S, actionData=ScoringDialog)
        self.actionScoring.setEnabled(False)
        self.actionAngle = self.kajonggAction("angle",  "object-rotate-left", self.changeAngle, Qt.Key_G)
        self.actionFullscreen = KToggleFullScreenAction(self.actionCollection())
        self.actionFullscreen.setShortcut(Qt.CTRL + Qt.Key_F)
        self.actionFullscreen.setShortcutContext(Qt.ApplicationShortcut)
        self.actionFullscreen.setWindow(self)
        self.actionCollection().addAction("fullscreen", self.actionFullscreen)
        self.connect(self.actionFullscreen, SIGNAL('toggled(bool)'), self.fullScreen)
        self.actionScoreTable = self.kajonggToggleAction("scoreTable", "format-list-ordered",
            Qt.Key_T, actionData=ScoreTable)
        self.actionExplain = self.kajonggToggleAction("explain", "applications-education",
            Qt.Key_E, actionData=ExplainView)
        QMetaObject.connectSlotsByName(self)

    def showWall(self):
        """shows the wall according to the game rules (lenght may vary)"""
        self.game.wall = UIWall(self.game)
        if self.discardBoard:
            # scale it such that it uses the place within the wall optimally.
            # we need to redo this because the wall length can vary between games.
            self.discardBoard.maximize()

    def genPlayers(self):
        """generate four default VisiblePlayers"""
        return Players([VisiblePlayer(self.game, idx) for idx in range(4)])

    def fullScreen(self, toggle):
        """toggle between full screen and normal view"""
        self.actionFullscreen.setFullScreen(self, toggle)

    def quit(self):
        """exit the application"""
        return self.abortGame(HumanClient.gameClosed)

    def abortGame(self, callback=None):
        """if a game is active, abort it"""
        if self.game:
            if self.game.client:
                return self.game.client.abortGame(callback)
            else:
                self.game.close()
        callback()
        return True

    def closeEvent(self, event):
        """somebody wants us to close, maybe ALT-F4 or so"""
        if not self.quit():
            event.ignore()

    def __moveTile(self, tile, windIndex, lowerHalf):
        """the user pressed a wind letter or X for center, wanting to move a tile there"""
        # this tells the receiving board that this is keyboard, not mouse navigation>
        # needed for useful placement of the popup menu
        # check opacity because we might be positioned on a hole
        if isinstance(tile, Tile) and tile.opacity:
            currentBoard = tile.board
            if windIndex == 4:
                receiver = self.selectorBoard
                if receiver.isEnabled():
                    receiver.receive(tile)
            else:
                targetWind = WINDS[windIndex]
                for player in self.game.players:
                    if player.wind == targetWind:
                        receiver = player.handBoard
                        if receiver.isEnabled(lowerHalf):
                            receiver.receive(tile, self.centralView, lowerHalf=lowerHalf)
            if receiver.isEnabled() and not currentBoard.allTiles():
                receiver.focusTile.setFocus()
            else:
                currentBoard.focusTile.setFocus()

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
            self.__moveTile(tile, moveCommands.index(wind), mod &Qt.ShiftModifier)
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
            newItem.setFocus()
            return
        if self.clientDialog:
            self.clientDialog.keyPressEvent(event)
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
                Game.load(selected)
            else:
                self.newGame()
            if self.game:
                self.selectorBoard.fill(self.game)
                if self.game.isScoringGame():
                    self.selectorBoard.childItems()[0].setFocus()
                self.game.throwDices()
        gameSelector.close()
        self.refresh()
        return bool(self.game)

    def scoreGame(self):
        """score a local game"""
        if self.selectGame():
            self.actionScoring.setChecked(True)

    def playGame(self):
        """play a remote game: log into a server and show its tables"""
        self.tableLists.append(TableList())

    def adjustView(self):
        """adjust the view such that exactly the wanted things are displayed
        without having to scroll"""
        if self.game:
            if self.discardBoard:
                self.discardBoard.maximize()
            if self.selectorBoard:
                self.selectorBoard.maximize()
        view, scene = self.centralView, self.centralScene
        oldRect = view.sceneRect()
        view.setSceneRect(scene.itemsBoundingRect())
        newRect = view.sceneRect()
        if oldRect != newRect:
            view.fitInView(scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    @apply
    def tilesetName(): # pylint: disable-msg=E0202
        """the name of the current tileset"""
        def fget(self):
            return self.tileset.desktopFileName
        def fset(self, name):
            self.tileset = Tileset(name)
        return property(**locals())

    @apply
    def backgroundName(): # pylint: disable-msg=E0202
        """setting this also actually changes the background"""
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
        if self.tilesetName != common.PREF.tilesetName:
            self.tilesetName = common.PREF.tilesetName
            for item in self.centralScene.items():
                if not isinstance(item, Tile): # shortcut
                    try:
                        item.tileset = self.tileset
                    except AttributeError:
                        continue
            # change players last because we need the wall already to be repositioned
            if self.game:
                self.game.wall.decorate()
            self.adjustView() # the new tiles might be larger
        if self.game:
            for player in self.game.players:
                if player.handBoard:
                    player.handBoard.rearrangeMelds = common.PREF.rearrangeMelds
        if self.isVisible():
            if self.backgroundName != common.PREF.backgroundName:
                self.backgroundName = common.PREF.backgroundName
            if self.showShadows is None or self.showShadows != common.PREF.showShadows:
                self.showShadows = common.PREF.showShadows
                if self.game:
                    wall = self.game.wall
                    wall.showShadows = self.showShadows
                    wall.decorate()
                self.selectorBoard.showShadows = self.showShadows
                if self.discardBoard:
                    self.discardBoard.showShadows = self.showShadows
                self.adjustView()
        Sound.enabled = common.PREF.useSounds

    def showSettings(self):
        """show preferences dialog. If it already is visible, do nothing"""
        if KConfigDialog.showDialog("settings"):
            return
        confDialog = ConfigDialog(self, "settings")
        self.connect(confDialog, SIGNAL('settingsChanged(QString)'),
           self.applySettings)
        confDialog.show()

    def newGame(self):
        """asks user for players and ruleset for a new game and returns that new game"""
        Players.load() # we want to make sure we have the current definitions
        selectDialog = SelectPlayers(self.game)
        if not selectDialog.exec_():
            return
        return Game(selectDialog.names, selectDialog.cbRuleset.current)

    def __toggleWidget(self, checked):
        """user has toggled widget visibility with an action"""
        action = self.sender()
        actionData = action.data().toPyObject()
        if checked:
            if isinstance(actionData, type):
                actionData = actionData(self.game)
                action.setData(QVariant(actionData))
                if isinstance(actionData, ScoringDialog):
                    self.scoringDialog = actionData
                    self.connect(actionData.btnSave, SIGNAL('clicked(bool)'), self.nextHand)
                    self.connect(actionData, SIGNAL('scoringClosed()'), self.scoringClosed)
                elif isinstance(actionData, ExplainView):
                    self.explainView = actionData
                elif isinstance(actionData, ScoreTable):
                    self.scoreTable = actionData
            actionData.show()
            actionData.raise_()
        else:
            assert actionData
            actionData.hide()

    def scoringClosed(self):
        """the scoring window has been closed with ALT-F4 or similar"""
        self.actionScoring.setChecked(False)

    def nextHand(self):
        """save hand to database, update score table and balance in status line, prepare next hand"""
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
        self.refresh()
        self.game.wall.decorate()

    def refresh(self):
        """update some actions, all auxiliary windows and the statusbar"""
        game = self.game
        for action in [self.actionScoreGame, self.actionPlayGame]:
            action.setEnabled(not bool(game))
        self.actionAbortGame.setEnabled(bool(game))
        scoring = bool(game and game.isScoringGame())
        self.selectorBoard.setVisible(scoring)
        self.selectorBoard.setEnabled(scoring)
        self.discardBoard.setVisible(bool(game) and not scoring)
        self.actionScoring.setEnabled(scoring and not game.finished())
        if self.actionScoring.isChecked():
            self.actionScoring.setChecked(scoring and not game.finished())
        for view in [self.scoringDialog, self.explainView, self.scoreTable]:
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
        self.adjustView()
        scoringDialog = self.actionScoring.data().toPyObject()
        if isinstance(scoringDialog, ScoringDialog):
            scoringDialog.computeScores()

    def __showBalance(self):
        """show the player balances in the status bar"""
        sBar = self.statusBar()
        if self.game:
            for idx, player in enumerate(self.game.players):
                sbMessage = m18nc('kajongg', player.name) + ': ' + str(player.balance)
                if sBar.hasItem(idx):
                    sBar.changeItem(sbMessage, idx)
                else:
                    sBar.insertItem(sbMessage, idx, 1)
                    sBar.setItemAlignment(idx, Qt.AlignLeft)
        else:
            for idx in range(5):
                if sBar.hasItem(idx):
                    sBar.removeItem(idx)

    def computeLastTile(self):
        """compile hand info into a string as needed by the scoring engine"""
        if self.scoringDialog:
            return self.scoringDialog.computeLastTile()
        return ''

    def computeLastMeld(self):
        """compile hand info into a string as needed by the scoring engine"""
        if self.scoringDialog:
            cbLastMeld = self.scoringDialog.cbLastMeld
            idx = cbLastMeld.currentIndex()
            if idx >= 0:
                return Meld(str(cbLastMeld.itemData(idx).toString()))
        return Meld()

    @staticmethod
    def askSwap(swappers):
        """use this as a proxy such that module game does not have to import playfield.
        Game should also run on a server without KDE being installed"""
        return SwapDialog(swappers).exec_()

    def hideAllFocusRect(self):
        """hide all blue focus rects around tiles. There may be more than
        one at the same time: The last discarded tile and a hidden tile of the player"""
        if self.game:
            boards = [x.handBoard for x in self.game.players]
            boards.append(self.selectorBoard)
            boards.append(self.discardBoard)
            for board in boards:
                if board:
                    board.hideFocusRect()
