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

import sys
import os
from util import logError, m18n, m18nc, logWarning, logDebug
from common import WINDS, LIGHTSOURCES, Options, Internal, Preferences, isAlive
import cgitb, tempfile, webbrowser
from twisted.internet.defer import succeed, fail

class MyHook(cgitb.Hook):
    """override the standard cgitb hook: invoke the browser"""
    def __init__(self):
        self.tmpFileName = tempfile.mkstemp(suffix='.html', prefix='bt_', text=True)[1]
        cgitb.Hook.__init__(self, file=open(self.tmpFileName, 'w'))

    def handle(self, info=None):
        """handling the exception: show backtrace in browser"""
        cgitb.Hook.handle(self, info)
        webbrowser.open(self.tmpFileName)

#sys.excepthook = MyHook()

NOTFOUND = []

try:
    from PyQt4.QtCore import Qt, QVariant, \
        QEvent, QMetaObject, PYQT_VERSION_STR, QString
    from PyQt4.QtGui import QPushButton, QMessageBox
    from PyQt4.QtGui import QWidget, QColor, QBrush
    from PyQt4.QtGui import QGridLayout, QAction
    from PyQt4.QtGui import QComboBox, QSlider, QHBoxLayout, QLabel
    from PyQt4.QtGui import QVBoxLayout, QSpacerItem, QSizePolicy, QCheckBox
except ImportError as importError:
    NOTFOUND.append('Package python-qt4: PyQt4: %s' % importError)

try:
    from zope.interface import implements # pylint: disable=W0611
except ImportError as importError:
    NOTFOUND.append('Package python-zope-interface missing: %s' % importError)

from kde import QuestionYesNo, KIcon, KAction, KApplication, KToggleFullScreenAction, \
    KXmlGuiWindow, KConfigDialog, KStandardAction

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
    from hand import Hand
    from meld import Meld
    from scoring import ExplainView, ScoringDialog, ScoreTable
    from tables import SelectRuleset
    from client import Client
    from humanclient import HumanClient
    from rulesetselector import RulesetSelector
    from tilesetselector import TilesetSelector
    from backgroundselector import BackgroundSelector
    from sound import Sound
    from uiwall import UIWall
    from animation import animate, afterCurrentAnimationDo, Animated
    from player import Player, Players, PlayingPlayer
    from game import ScoringGame
    from chat import ChatWindow
    from message import Message

except ImportError as importError:
    NOTFOUND.append('kajongg is not correctly installed: modules: %s' % importError)

if len(NOTFOUND):
    MSG = "\n".join(" * %s" % s for s in NOTFOUND)
    logError(MSG)
    os.popen("kdialog --sorry '%s'" % MSG)
    sys.exit(3)

class PlayConfigTab( QWidget):
    """Display Config tab"""
    def __init__(self, parent):
        super(PlayConfigTab, self).__init__(parent)
        self.setupUi()

    def setupUi(self):
        """layout the window"""
        self.setContentsMargins(0, 0, 0, 0)
        vlayout = QVBoxLayout(self)
        vlayout.setContentsMargins(0, 0, 0, 0)
        sliderLayout = QHBoxLayout()
        self.kcfg_showShadows = QCheckBox(m18n('Show tile shadows'), self)
        self.kcfg_showShadows.setObjectName('kcfg_showShadows')
        self.kcfg_rearrangeMelds = QCheckBox(m18n('Rearrange undisclosed tiles to melds'), self)
        self.kcfg_rearrangeMelds.setObjectName('kcfg_rearrangeMelds')
        self.kcfg_showOnlyPossibleActions = QCheckBox(m18n('Show only possible actions'))
        self.kcfg_showOnlyPossibleActions.setObjectName('kcfg_showOnlyPossibleActions')
        self.kcfg_propose = QCheckBox(m18n('Propose what to do'))
        self.kcfg_propose.setObjectName('kcfg_propose')
        self.kcfg_animationSpeed = QSlider(self)
        self.kcfg_animationSpeed.setObjectName('kcfg_animationSpeed')
        self.kcfg_animationSpeed.setOrientation(Qt.Horizontal)
        self.kcfg_animationSpeed.setSingleStep(1)
        lblSpeed = QLabel(m18n('Animation speed:'))
        lblSpeed.setBuddy(self.kcfg_animationSpeed)
        sliderLayout.addWidget(lblSpeed)
        sliderLayout.addWidget(self.kcfg_animationSpeed)
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
        vlayout.addWidget(self.kcfg_showOnlyPossibleActions)
        vlayout.addWidget(self.kcfg_propose)
        vlayout.addWidget(self.kcfg_useSounds)
        vlayout.addWidget(self.kcfg_uploadVoice)
        vlayout.addLayout(sliderLayout)
        vlayout.addItem(spacerItem)
        self.setSizePolicy(pol)
        self.retranslateUi()

    def retranslateUi(self):
        """translate to current language"""
        pass

class ConfigDialog(KConfigDialog):
    """configuration dialog with several pages"""
    def __init__(self, parent, name):
        super(ConfigDialog, self).__init__(parent, QString(name), Preferences)
        self.pages = [
            self.addPage(PlayConfigTab(self),
                m18nc('kajongg','Play'), "arrow-right"),
            self.addPage(TilesetSelector(self),
                m18n("Tiles"), "games-config-tiles"),
            self.addPage(BackgroundSelector(self),
                m18n("Backgrounds"), "games-config-background")]
        StateSaver(self)

    def keyPressEvent(self, event):
        """The four tabs can be selected with CTRL-1 .. CTRL-4"""
        mod = event.modifiers()
        key = chr(event.key()%128)
        if Qt.ControlModifier | mod and key in '1234':
            self.setCurrentPage(self.pages[int(key)-1])
            return
        KConfigDialog.keyPressEvent(self, event)

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

class SelectPlayers(SelectRuleset):
    """a dialog for selecting four players. Used only for scoring game."""
    def __init__(self, game):
        SelectRuleset.__init__(self)
        self.game = game
        Players.load()
        self.setWindowTitle(m18n('Select four players') + ' - Kajongg')
        self.names = None
        self.nameWidgets = []
        for idx, wind in enumerate(WINDS):
            cbName = QComboBox()
            cbName.manualSelect = False
            # increase width, we want to see the full window title
            cbName.setMinimumWidth(350) # is this good for all platforms?
            cbName.addItems(Players.humanNames.values())
            self.grid.addWidget(cbName, idx+1, 1)
            self.nameWidgets.append(cbName)
            self.grid.addWidget(WindLabel(wind), idx+1, 0)
            cbName.currentIndexChanged.connect(self.slotValidate)

        query = Query("select p0,p1,p2,p3 from game where seed is null and game.id = (select max(id) from game)")
        if len(query.records):
            for pidx, playerId in enumerate(query.records[0]):
                try:
                    playerName = Players.humanNames[playerId]
                    cbName = self.nameWidgets[pidx]
                    playerIdx = cbName.findText(playerName)
                    if playerIdx >= 0:
                        cbName.setCurrentIndex(playerIdx)
                except KeyError:
                    logError('database is inconsistent: player with id %d is in game but not in player' \
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
        changedCombo.manualSelect = True
        usedNames = set([unicode(x.currentText()) for x in self.nameWidgets if x.manualSelect])
        allNames = set(Players.humanNames.values())
        unusedNames = allNames - usedNames
        for combo in self.nameWidgets:
            combo.blockSignals(True)
        try:
            for combo in self.nameWidgets:
                if combo.manualSelect:
                    continue
                comboName = unusedNames.pop()
                combo.clear()
                combo.addItems([comboName])
                combo.addItems(sorted(allNames - usedNames - set([comboName])))
        finally:
            for combo in self.nameWidgets:
                combo.blockSignals(False)
        self.names = list(unicode(cbName.currentText()) for cbName in self.nameWidgets)
        assert len(set(self.names)) == 4

class VisiblePlayingPlayer(PlayingPlayer):
    """this player instance has a visual representation"""
    # pylint: disable=R0904
    # too many public methods
    def __init__(self, game):
        assert game
        self.handBoard = None # because Player.init calls clearHand()
        PlayingPlayer.__init__(self, game)
        self.__front = self.game.wall[self.idx] # need front before setting handBoard
        self.manualRuleBoxes = []
        self.handBoard = HandBoard(self)
        self.voice = None

    def clearHand(self):
        """clears attributes related to current hand"""
        Player.clearHand(self)
        if self.game and self.game.wall:
            # is None while __del__
            self.front = self.game.wall[self.idx]
        self.manualRuleBoxes = []

    @property
    def idx(self):
        """our index in the player list"""
        if not self in self.game.players:
            # we will be added next
            return len(self.game.players)
        return self.game.players.index(self)

    @property
    def front(self):
        """front"""
        return self.__front

    @front.setter
    def front(self, value):
        """also assign handBoard to front"""
        self.__front = value
        if value and self.handBoard:
            self.handBoard.setParentItem(value)

    def hasManualScore(self):
        """True if no tiles are assigned to this player"""
        if Internal.field.scoringDialog:
            return Internal.field.scoringDialog.spValues[self.idx].isEnabled()
        return False

    @property
    def handTotal(self):
        """the hand total of this player"""
        if self.hasManualScore():
            spValue = Internal.field.scoringDialog.spValues[self.idx]
            return spValue.value()
        else:
            return Player.handTotal.fget(self)

    def handTotalForWall(self):
        """returns the totale for the new hand. Same as current unless we need to discard.
        In that case, make an educated guess about the discard. For player==game.myself, use
        the focussed tile."""
        if self.game.isScoringGame():
            return self.handTotal
        hand = self.hand
        if hand and hand.tileNames and self._concealedTileNames:
            if hand.lenOffset == 1 and not hand.won:
                if self == self.game.myself:
                    removeTile = self.handBoard.focusTile.element
                elif self.lastTile:
                    removeTile = self.lastTile
                else:
                    removeTile = self._concealedTileNames[0]
                assert removeTile[0] not in 'fy', 'hand:%s remove:%s lastTile:%s' % (
                    hand, removeTile, self.lastTile)
                hand -= removeTile
                assert not hand.lenOffset
        return hand.total()

    def syncHandBoard(self, adding=None):
        """update display of handBoard. Set Focus to tileName."""
        self.handBoard.sync(adding)

    def moveMeld(self, meld):
        """a meld moves within our handBoard"""
        assert meld.tiles[0].board == self.handBoard
        self.removeMeld(meld)
        self.addMeld(meld)

    def sortMeldsByX(self):
        """sorts the melds by their position on screen"""
        if self.game.isScoringGame():
            # in a real game, the player melds do not have tiles
            self._concealedMelds = sorted(self._concealedMelds, key=lambda x: x[0].xoffset)
            self._exposedMelds = sorted(self._exposedMelds, key=lambda x: x[0].xoffset)

    def colorizeName(self):
        """set the color to be used for showing the player name on the wall"""
        if not isAlive(self.front.nameLabel):
            # TODO: should never happen
            logDebug('colorizeName: nameLabel is not alive')
            return
        if self == self.game.activePlayer and self.game.client:
            color = Qt.blue
        elif Internal.field.tilesetName == 'jade':
            color = Qt.white
        else:
            color = Qt.black
        self.front.nameLabel.setBrush(QBrush(QColor(color)))

    def getsFocus(self, dummyResults=None):
        """give this player focus on his handBoard"""
        self.handBoard.setEnabled(True)
        self.handBoard.hasFocus = True

    def refreshManualRules(self, sender=None):
        """update status of manual rules"""
        assert Internal.field
        if not self.handBoard:
            # might happen at program exit
            return
        currentScore = self.hand.score
        hasManualScore = self.hasManualScore()
        for box in self.manualRuleBoxes:
            if box.rule in self.hand.computedRules:
                box.setVisible(True)
                box.setChecked(True)
                box.setEnabled(False)
            else:
                applicable = bool(self.hand.manualRuleMayApply(box.rule))
                if hasManualScore:
                    # only those rules which do not affect the score can be applied
                    applicable = applicable and box.rule.hasNonValueAction()
                else:
                    # if the action would only influence the score and the rule does not change the score,
                    # ignore the rule. If however the action does other things like penalties leave it applicable
                    if box != sender:
                        if applicable:
                            applicable = bool(box.rule.hasNonValueAction()) \
                                or (self.computeHand(singleRule=box.rule).score > currentScore)
                box.setApplicable(applicable)

    def __mjstring(self, singleRule, asWinner):
        """compile hand info into a string as needed by the scoring engine"""
        winds = self.wind.lower() + 'eswn'[self.game.roundsFinished % 4]
        if asWinner or self == self.game.winner:
            wonChar = 'M'
        else:
            wonChar = 'm'
        lastTile = Internal.field.computeLastTile()
        if lastTile and lastTile.istitle():
            lastSource = 'w'
        else:
            lastSource = 'd'
        declaration = ''
        rules = [x.rule for x in self.manualRuleBoxes if x.isChecked()]
        if singleRule:
            rules.append(singleRule)
        for rule in rules:
            options = rule.options
            if 'lastsource' in options:
                if lastSource != '1':
                    # this defines precedences for source of last tile
                    lastSource = options['lastsource']
            if 'declaration' in options:
                declaration = options['declaration']
        return ''.join([wonChar, winds, lastSource, declaration])

    def __lastString(self, asWinner):
        """compile hand info into a string as needed by the scoring engine"""
        if not asWinner or self != self.game.winner:
            return ''
        lastTile = Internal.field.computeLastTile()
        if not lastTile:
            return ''
        return 'L%s%s' % (lastTile, Internal.field.computeLastMeld().joined)

    def computeHand(self, withTile=None, robbedTile=None, singleRule=None, asWinner=False):
        """returns a Hand object, using a cache"""
        game = self.game
        if not game.isScoringGame():
            return Player.computeHand(self, withTile=withTile, robbedTile=robbedTile, asWinner=asWinner)
        if not self.handBoard:
            return None
        string = ' '.join([self.scoringString(), self.__mjstring(singleRule, asWinner), self.__lastString(asWinner)])
        return Hand.cached(self, string, computedRules=singleRule)

    def popupMsg(self, msg):
        """shows a yellow message from player"""
        if msg != Message.NoClaim:
            self.speak(msg.name.lower())
            yellow = self.front.message
            yellow.setText('  '.join([unicode(yellow.msg), m18nc('kajongg', msg.name)]))
            yellow.setVisible(True)

    def hidePopup(self):
        """hide the yellow message from player"""
        if isAlive(self.front.message):
            self.front.message.msg = ''
            self.front.message.setVisible(False)

    def speak(self, text):
        """speak if we have a voice"""
        if self.voice:
            self.voice.speak(text, self.front.rotation())

class PlayField(KXmlGuiWindow):
    """the main window"""
    # pylint: disable=R0902
    # pylint we need more than 10 instance attributes

    def __init__(self):
        # see http://lists.kde.org/?l=kde-games-devel&m=120071267328984&w=2
        Internal.field = self
        self.game = None
        self.__startingGame = False
        self.ignoreResizing = 1
        super(PlayField, self).__init__()
        self.background = None
        self.showShadows = None
        self._clientDialog = None

        self.playerWindow = None
        self.rulesetWindow = None
        self.scoreTable = None
        self.explainView = None
        self.scoringDialog = None
        self.confDialog = None
        self.setupUi()
        KStandardAction.preferences(self.showSettings, self.actionCollection())
        self.applySettings()
        self.setupGUI()
        self.retranslateUi()
        for action in self.toolBar().actions():
            if 'onfigure' in action.text():
                action.setPriority(QAction.LowPriority)
        if Options.host:
            self.playGame()

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

    def sizeHint(self):
        """give the main window a sensible default size"""
        result = KXmlGuiWindow.sizeHint(self)
        result.setWidth(result.height() * 3 // 2) # we want space to the right for the buttons
        # the default is too small. Use at least 2/3 of screen height and 1/2 of screen width:
        available = KApplication.kApplication().desktop().availableGeometry()
        height = max(result.height(), available.height() * 2 // 3)
        width = max(result.width(), available.width() // 2)
        result.setHeight(height)
        result.setWidth(width)
        return result

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
            self.game.wall.decoratePlayer(handBoard.player) # pylint: disable=E1101
        # first decorate walls - that will compute player.handBoard for explainView
        if self.explainView:
            self.explainView.refresh(self.game)

    def __kajonggAction(self, name, icon, slot=None, shortcut=None, actionData=None):
        """simplify defining actions"""
        res = KAction(self)
        res.setIcon(KIcon(icon))
        if slot:
            res.triggered.connect(slot)
        self.actionCollection().addAction(name, res)
        if shortcut:
            res.setShortcut( Qt.CTRL + shortcut)
            res.setShortcutContext(Qt.ApplicationShortcut)
        if PYQT_VERSION_STR != '4.5.2' or actionData is not None:
            res.setData(QVariant(actionData))
        return res

    def __kajonggToggleAction(self, name, icon, shortcut=None, actionData=None):
        """a checkable action"""
        res = self.__kajonggAction(name, icon, shortcut=shortcut, actionData=actionData)
        res.setCheckable(True)
        res.toggled.connect(self.__toggleWidget)
        return res

    def setupUi(self):
        """create all other widgets
        we could make the scene view the central widget but I did
        not figure out how to correctly draw the background with
        QGraphicsView/QGraphicsScene.
        QGraphicsView.drawBackground always wants a pixmap
        for a huge rect like 4000x3000 where my screen only has
        1920x1200"""
        # pylint: disable=R0915
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
        self.tilesetName = Preferences.tilesetName
        self.windTileset = Tileset(Preferences.windTilesetName)

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
        self.actionScoreGame = self.__kajonggAction("scoreGame", "draw-freehand", self.scoreGame, Qt.Key_C)
        self.actionPlayGame = self.__kajonggAction("play", "arrow-right", self.playGame, Qt.Key_N)
        self.actionAbortGame = self.__kajonggAction("abort", "dialog-close", self.abortAction, Qt.Key_W)
        self.actionAbortGame.setEnabled(False)
        self.actionQuit = self.__kajonggAction("quit", "application-exit", self.close, Qt.Key_Q)
        self.actionPlayers = self.__kajonggAction("players", "im-user", self.slotPlayers)
        self.actionRulesets = self.__kajonggAction("rulesets", "games-kajongg-law", self.slotRulesets)
        self.actionChat = self.__kajonggToggleAction("chat", "call-start",
            shortcut=Qt.Key_H, actionData=ChatWindow)
        game = self.game
        self.actionChat.setEnabled(bool(game) and bool(game.client) and not game.client.hasLocalServer())
        self.actionChat.setChecked(bool(game) and bool(game.client) and bool(game.client.table.chatWindow))
        self.actionScoring = self.__kajonggToggleAction("scoring", "draw-freehand",
            shortcut=Qt.Key_S, actionData=ScoringDialog)
        self.actionScoring.setEnabled(False)
        self.actionAngle = self.__kajonggAction("angle", "object-rotate-left", self.changeAngle, Qt.Key_G)
        self.actionAngle.setEnabled(False)
        self.actionFullscreen = KToggleFullScreenAction(self.actionCollection())
        self.actionFullscreen.setShortcut(Qt.CTRL + Qt.Key_F)
        self.actionFullscreen.setShortcutContext(Qt.ApplicationShortcut)
        self.actionFullscreen.setWindow(self)
        self.actionCollection().addAction("fullscreen", self.actionFullscreen)
        self.actionFullscreen.toggled.connect(self.fullScreen)
        self.actionScoreTable = self.__kajonggToggleAction("scoreTable", "format-list-ordered",
            Qt.Key_T, actionData=ScoreTable)
        self.actionExplain = self.__kajonggToggleAction("explain", "applications-education",
            Qt.Key_E, actionData=ExplainView)
        self.actionAutoPlay = self.__kajonggAction("demoMode", "arrow-right-double", None, Qt.Key_D)
        self.actionAutoPlay.setCheckable(True)
        self.actionAutoPlay.toggled.connect(self.__toggleDemoMode)
        self.actionAutoPlay.setChecked(Internal.autoPlay)
        QMetaObject.connectSlotsByName(self)

    def showWall(self):
        """shows the wall according to the game rules (lenght may vary)"""
        UIWall(self.game)   # sets self.game.wall
        if self.discardBoard:
            # scale it such that it uses the place within the wall optimally.
            # we need to redo this because the wall length can vary between games.
            self.discardBoard.maximize()

    def genPlayer(self):
        """generate a default VisiblePlayingPlayer"""
        return VisiblePlayingPlayer(self.game)

    def fullScreen(self, toggle):
        """toggle between full screen and normal view"""
        self.actionFullscreen.setFullScreen(self, toggle)

    def abortAction(self):
        """abort current game"""
        def doNotQuit(dummy):
            """ignore failure to abort"""
        self.abort().addErrback(doNotQuit)

    def abort(self):
        """abort current game"""
        def gotAnswer(result, autoPlaying):
            """user answered"""
            if result:
                return self.abortGame()
            else:
                self.actionAutoPlay.setChecked(autoPlaying)
                return fail(Exception('no abort'))
        def gotError(result):
            """abortGame failed"""
            logDebug('abortGame error:%s/%s ' % (str(result), result.getErrorMessage()))
        if not self.game:
            self.startingGame = False
            return succeed(None)
        autoPlaying = self.actionAutoPlay.isChecked()
        self.actionAutoPlay.setChecked(False)
        if self.game.finished():
            return self.abortGame()
        else:
            return QuestionYesNo(m18n("Do you really want to abort this game?"), always=True).addCallback(
                gotAnswer, autoPlaying).addErrback(gotError)

    def abortGame(self):
        """if a game is active, abort it"""
        if self.game is None: # meanwhile somebody else might have aborted
            return succeed(None)
        game = self.game
        self.game = None
        return game.close()

    def closeEvent(self, event):
        """somebody wants us to close, maybe ALT-F4 or so"""
        event.ignore()
        def doNotQuit(dummy):
            """ignore failure to abort"""
        self.abort().addCallback(HumanClient.shutdownHumanClients).addCallbacks(Client.quitProgram, doNotQuit)

    def __moveTile(self, tile, wind, lowerHalf):
        """the user pressed a wind letter or X for center, wanting to move a tile there"""
        # this tells the receiving board that this is keyboard, not mouse navigation>
        # needed for useful placement of the popup menu
        assert self.game.isScoringGame()
        assert isinstance(tile, Tile), (tile, str(tile))
        currentBoard = tile.board
        dragTile, dragMeld = currentBoard.dragObject(tile)
        if wind == 'X':
            receiver = self.selectorBoard
        else:
            receiver = self.game.players[wind].handBoard
        if receiver != currentBoard or bool(lowerHalf) != bool(tile.yoffset):
            movingLastMeld = tile.element in self.computeLastMeld().pairs
            if movingLastMeld:
                self.scoringDialog.clearLastTileCombo()
            receiver.dropHere(dragTile, dragMeld, lowerHalf)
            if movingLastMeld and receiver == currentBoard:
                self.scoringDialog.fillLastTileCombo()

    def __navigateScoringGame(self, event):
        """keyboard navigation in a scoring game"""
        mod = event.modifiers()
        key = event.key()
        wind = chr(key%128)
        moveCommands = m18nc('kajongg:keyboard commands for moving tiles to the players ' \
            'with wind ESWN or to the central tile selector (X)', 'ESWNX')
        tile = self.centralScene.focusItem().tile
        if wind in moveCommands:
            # translate i18n wind key to ESWN:
            wind = 'ESWNX'[moveCommands.index(wind)]
            self.__moveTile(tile, wind, mod &Qt.ShiftModifier)
            return True
        if key == Qt.Key_Tab and self.game:
            tabItems = [self.selectorBoard]
            tabItems.extend(list(p.handBoard for p in self.game.players if p.handBoard.tiles))
            tabItems.append(tabItems[0])
            currentBoard = tile.board if isinstance(tile, Tile) else None
            currIdx = 0
            while tabItems[currIdx] != currentBoard and currIdx < len(tabItems) -2:
                currIdx += 1
            tabItems[currIdx+1].hasFocus = True
            return True

    def keyPressEvent(self, event):
        """navigate in the selectorboard"""
        mod = event.modifiers()
        if mod in (Qt.NoModifier, Qt.ShiftModifier):
            if self.game and self.game.isScoringGame():
                if self.__navigateScoringGame(event):
                    return
            if self.clientDialog:
                self.clientDialog.keyPressEvent(event)
        KXmlGuiWindow.keyPressEvent(self, event)

    def retranslateUi(self):
        """retranslate"""
        self.actionScoreGame.setText(m18nc('@action:inmenu', "&Score Manual Game"))
        self.actionScoreGame.setIconText(m18nc('@action:intoolbar', 'Manual Game'))
        self.actionScoreGame.setHelpText(m18nc('kajongg @info:tooltip', '&Score a manual game.'))

        self.actionPlayGame.setText(m18nc('@action:intoolbar', "&Play"))
        self.actionPlayGame.setPriority(QAction.LowPriority)
        self.actionPlayGame.setHelpText(m18nc('kajongg @info:tooltip', 'Start a new game.'))

        self.actionAbortGame.setText(m18nc('@action:inmenu', "&Abort Game"))
        self.actionAbortGame.setPriority(QAction.LowPriority)
        self.actionAbortGame.setHelpText(m18nc('kajongg @info:tooltip', 'Abort the current game.'))

        self.actionQuit.setText(m18nc('@action:inmenu', "&Quit Kajongg"))
        self.actionQuit.setPriority(QAction.LowPriority)

        self.actionPlayers.setText(m18nc('@action:intoolbar', "&Players"))
        self.actionPlayers.setHelpText(m18nc('kajongg @info:tooltip', 'define your players.'))

        self.actionRulesets.setText(m18nc('@action:intoolbar', "&Rulesets"))
        self.actionRulesets.setHelpText(m18nc('kajongg @info:tooltip', 'customize rulesets.'))

        self.actionAngle.setText(m18nc('@action:inmenu', "&Change Visual Angle"))
        self.actionAngle.setIconText(m18nc('@action:intoolbar', "Angle"))
        self.actionAngle.setHelpText(m18nc('kajongg @info:tooltip', "Change the visual appearance of the tiles."))

        self.actionScoring.setText(m18nc('@action:inmenu', "&Show Scoring Editor"))
        self.actionScoring.setIconText(m18nc('@action:intoolbar', "&Scoring"))
        self.actionScoring.setHelpText(m18nc('kajongg @info:tooltip',
                "Show or hide the scoring editor for a manual game."))

        self.actionScoreTable.setText(m18nc('kajongg @action:inmenu', "&Score Table"))
        self.actionScoreTable.setIconText(m18nc('kajongg @action:intoolbar', "&Scores"))
        self.actionScoreTable.setHelpText(m18nc('kajongg @info:tooltip',
                "Show or hide the score table for the current game."))

        self.actionExplain.setText(m18nc('@action:inmenu', "&Explain Scores"))
        self.actionExplain.setIconText(m18nc('@action:intoolbar', "&Explain"))
        self.actionExplain.setHelpText(m18nc('kajongg @info:tooltip',
                'Explain the scoring for all players in the current game.'))

        self.actionAutoPlay.setText(m18nc('@action:inmenu', "&Demo Mode"))
        self.actionAutoPlay.setPriority(QAction.LowPriority)
        self.actionAutoPlay.setHelpText(m18nc('kajongg @info:tooltip',
                'Let the computer take over for you. Start a new local game if needed.'))

        self.actionChat.setText(m18n("C&hat"))
        self.actionChat.setHelpText(m18nc('kajongg @info:tooltip', 'Chat with the other players.'))

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

    def slotRulesets(self):
        """show the player list"""
        if not self.rulesetWindow:
            self.rulesetWindow = RulesetSelector()
        self.rulesetWindow.show()

    def selectScoringGame(self):
        """show all games, select an existing game or create a new game"""
        Players.load()
        if len(Players.humanNames) < 4:
            logWarning(m18n('Please define four players in <interface>Settings|Players</interface>'))
            return False
        gameSelector = Games(self)
        if gameSelector.exec_():
            selected = gameSelector.selectedGame
            if selected is not None:
                ScoringGame.loadFromDB(selected)
            else:
                self.newGame()
            if self.game:
                self.game.throwDices()
        gameSelector.close()
        self.updateGUI()
        return bool(self.game)

    def scoreGame(self):
        """score a local game"""
        if self.selectScoringGame():
            self.actionScoring.setChecked(True)

    def playGame(self):
        """play a remote game: log into a server and show its tables"""
        self.startingGame = True
        HumanClient()

    def adjustView(self):
        """adjust the view such that exactly the wanted things are displayed
        without having to scroll"""
        if not Internal.scaleScene:
            return
        if self.game:
            with Animated(False):
                self.game.wall.decorate()
                if self.discardBoard:
                    self.discardBoard.maximize()
                if self.selectorBoard:
                    self.selectorBoard.maximize()
                for tile in self.game.wall.tiles:
                    if tile.board:
                        tile.board.placeTile(tile)
        view, scene = self.centralView, self.centralScene
        oldRect = view.sceneRect()
        view.setSceneRect(scene.itemsBoundingRect())
        newRect = view.sceneRect()
        if oldRect != newRect:
            view.fitInView(scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    @property
    def startingGame(self):
        """are we trying to start a game?"""
        return self.__startingGame

    @startingGame.setter
    def startingGame(self, value):
        """are we trying to start a game?"""
        if value != self.__startingGame:
            self.__startingGame = value
            self.updateGUI()

    @property
    def tilesetName(self):
        """the name of the current tileset"""
        return self.tileset.desktopFileName

    @tilesetName.setter
    def tilesetName(self, name):
        """the name of the current tileset"""
        self.tileset = Tileset(name)

    @property
    def backgroundName(self):
        """setting this also actually changes the background"""
        return self.background.desktopFileName if self.background else ''

    @backgroundName.setter
    def backgroundName(self, name):
        """setter for backgroundName"""
        self.background = Background(name)
        self.background.setPalette(self.centralWidget())
        self.centralWidget().setAutoFillBackground(True)

    def applySettings(self):
        """apply preferences"""
        # pylint: disable=R0912
        # too many branches
        self.actionAngle.setEnabled(bool(self.game) and Preferences.showShadows)
        animate() # drain the queue
        afterCurrentAnimationDo(self.__applySettings2)

    def __applySettings2(self, dummyResults):
        """now no animation is running"""
        with Animated(False):
            if self.tilesetName != Preferences.tilesetName:
                self.tilesetName = Preferences.tilesetName
                if self.game:
                    self.game.wall.tileset = self.tileset
                for item in self.centralScene.nonTiles():
                    try:
                        item.tileset = self.tileset
                    except AttributeError:
                        continue
                # change players last because we need the wall already to be repositioned
                self.adjustView() # the new tiles might be larger
            if self.game:
                for player in self.game.players:
                    if player.handBoard:
                        player.handBoard.rearrangeMelds = Preferences.rearrangeMelds
            if self.backgroundName != Preferences.backgroundName:
                self.backgroundName = Preferences.backgroundName
            if self.showShadows is None or self.showShadows != Preferences.showShadows:
                self.showShadows = Preferences.showShadows
                if self.game:
                    wall = self.game.wall
                    wall.showShadows = self.showShadows
                self.selectorBoard.showShadows = self.showShadows
                if self.discardBoard:
                    self.discardBoard.showShadows = self.showShadows
                for tile in self.centralScene.graphicsTileItems():
                    tile.setClippingFlags()
                self.adjustView()
        Sound.enabled = Preferences.useSounds
        self.centralScene.placeFocusRect()

    def showSettings(self):
        """show preferences dialog. If it already is visible, do nothing"""
        if KConfigDialog.showDialog("settings"):
            return
        # if an animation is running, Qt segfaults somewhere deep
        # in the SVG renderer rendering the wind tiles for the tile
        # preview
        afterCurrentAnimationDo(self.__showSettings2)

    def __showSettings2(self, dummyResult):
        """now that no animation is running, show settings dialog"""
        self.confDialog = ConfigDialog(self, "settings")
        self.confDialog.settingsChanged.connect(self.applySettings)
        self.confDialog.show()

    def newGame(self):
        """asks user for players and ruleset for a new game and returns that new game"""
        Players.load() # we want to make sure we have the current definitions
        selectDialog = SelectPlayers(self.game)
        if not selectDialog.exec_():
            return
        return ScoringGame(selectDialog.names, selectDialog.cbRuleset.current)

    def __toggleWidget(self, checked):
        """user has toggled widget visibility with an action"""
        action = self.sender()
        actionData = action.data().toPyObject()
        if checked:
            if isinstance(actionData, type):
                actionData = actionData(game=self.game)
                action.setData(QVariant(actionData))
                if isinstance(actionData, ScoringDialog):
                    self.scoringDialog = actionData
                    actionData.btnSave.clicked.connect(self.nextScoringHand)
                    actionData.scoringClosed.connect(self.__scoringClosed)
                elif isinstance(actionData, ExplainView):
                    self.explainView = actionData
                elif isinstance(actionData, ScoreTable):
                    self.scoreTable = actionData
            actionData.show()
            actionData.raise_()
        else:
            assert actionData
            actionData.hide()

    def __toggleDemoMode(self, checked):
        """switch on / off for autoPlay"""
        if self.game:
            self.centralScene.placeFocusRect() # show/hide it
            self.game.autoPlay = checked
            if checked and self.clientDialog:
                self.clientDialog.proposeAction() # an illegal action might have focus
                self.clientDialog.selectButton() # select default, abort timeout
        else:
            Internal.autoPlay = checked
            if checked:
                # TODO: use the last used ruleset. Right now it always takes the first of the list.
                self.playGame()

    def __scoringClosed(self):
        """the scoring window has been closed with ALT-F4 or similar"""
        self.actionScoring.setChecked(False)

    def nextScoringHand(self):
        """save hand to database, update score table and balance in status line, prepare next hand"""
        if self.game.winner:
            for player in self.game.players:
                player.usedDangerousFrom = None
                for ruleBox in player.manualRuleBoxes:
                    rule = ruleBox.rule
                    if rule.name == 'Dangerous Game' and ruleBox.isChecked():
                        self.game.winner.usedDangerousFrom = player
        self.game.saveHand()
        self.game.maybeRotateWinds()
        self.game.prepareHand()
        self.game.initHand()

    def prepareHand(self):
        """redecorate wall"""
        self.updateGUI()
        if self.game:
            self.game.wall.decorate()
        if self.scoringDialog:
            self.scoringDialog.clearLastTileCombo()

    def updateGUI(self):
        """update some actions, all auxiliary windows and the statusbar"""
        if not isAlive(self):
            return
        title = ''
        connections = list(x.connection for x in HumanClient.humanClients if x.connection)
        game = self.game
        if not game:
            title = ', '.join('{name}/{url}'.format(name=x.username, url=x.url) for x in connections)
            if title:
                self.setWindowTitle('%s - Kajongg' % title)
        for action in [self.actionScoreGame, self.actionPlayGame]:
            action.setEnabled(not bool(game))
        self.actionAbortGame.setEnabled(bool(game))
        self.actionAngle.setEnabled(bool(game) and self.showShadows)
        scoring = bool(game and game.isScoringGame())
        self.selectorBoard.setVisible(scoring)
        self.selectorBoard.setEnabled(scoring)
        self.discardBoard.setVisible(bool(game) and not scoring)
        self.actionScoring.setEnabled(scoring and not game.finished())
        self.actionAutoPlay.setEnabled(not self.startingGame and not scoring)
        self.actionChat.setEnabled(bool(game) and bool(game.client)
            and not game.client.hasLocalServer() and not self.startingGame)
            # chatting on tables before game started works with chat button per table
        self.actionChat.setChecked(self.actionChat.isEnabled() and bool(game.client.table.chatWindow))
        if self.actionScoring.isChecked():
            self.actionScoring.setChecked(scoring and not game.finished())
        for view in [self.scoringDialog, self.explainView, self.scoreTable]:
            if view:
                view.refresh(game)
        self.__showBalance()

    def changeAngle(self):
        """change the lightSource"""
        if self.game:
            afterCurrentAnimationDo(self.__changeAngle2)

    def __changeAngle2(self, dummyResult):
        """now that no animation is running, really change"""
        if self.game: # might be finished meanwhile
            with Animated(False):
                wall = self.game.wall
                oldIdx = LIGHTSOURCES.index(wall.lightSource) # pylint: disable=E1101
                newLightSource = LIGHTSOURCES[(oldIdx + 1) % 4]
                wall.lightSource = newLightSource
                self.selectorBoard.lightSource = newLightSource
                self.discardBoard.lightSource = newLightSource
                self.adjustView()
                scoringDialog = self.actionScoring.data().toPyObject()
                if isinstance(scoringDialog, ScoringDialog):
                    scoringDialog.computeScores()
                self.centralScene.placeFocusRect()

    def __showBalance(self):
        """show the player balances in the status bar"""
        sBar = self.statusBar()
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

    def computeLastTile(self):
        """compile hand info into a string as needed by the scoring engine"""
        if self.scoringDialog:
            return self.scoringDialog.computeLastTile()

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
        return SwapDialog(swappers).exec_() == 0
        # I do not understand the logic of the exec return value. The yes button returns 0
        # and the no button returns 1. According to the C++ doc, the return value is an
        # opaque value that should not be used."""
