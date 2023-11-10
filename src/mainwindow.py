# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

# pylint: disable=wrong-import-order

import sys
import codecs
from itertools import chain

import cgitb  # pylint:disable=deprecated-module
import tempfile
import webbrowser
import logging

from log import logError, logDebug
from common import Options, Internal, isAlive, Debug, handleSignals


class MyHook(cgitb.Hook):

    """override the standard cgitb hook: invoke the browser"""

    def __init__(self):
        self.tmpFileName = tempfile.mkstemp(
            suffix='.html',
            prefix='bt_',
            text=True)[1]
        # cgitb can only handle ascii, work around that.
        # See https://bugs.python.org/issue22746
        cgitb.Hook.__init__(self, file=codecs.open(self.tmpFileName, 'w',  # pylint:disable=consider-using-with
                                                   encoding='latin-1', errors='xmlcharrefreplace'))

    def handle(self, info=None):
        """handling the exception: show backtrace in browser"""
        if getattr(cgitb, 'Hook', None):
            # if we cannot import twisted (syntax error), Hook is not yet known
            cgitb.Hook.handle(self, info)
            webbrowser.open(self.tmpFileName)

# sys.excepthook = MyHook()


NOTFOUND = []

try:
    from qt import Qt, QEvent, QMetaObject, QTimer
    from qt import QWidget, QGridLayout, QAction
except ImportError as importError:
    NOTFOUND.append('Please install PyQt5: %s' % importError)

try:
    from twisted.spread import pb # pylint: disable=unused-import
    from twisted.internet.error import ReactorNotRunning
except ImportError as importError:
    NOTFOUND.append('Package python3-twisted is missing or too old (I need 16.6.0): %s' % importError)


try:
    from mi18n import i18n, i18nc
    from kde import KXmlGuiWindow, KStandardAction

    from board import FittingView
    from playerlist import PlayerList
    from tileset import Tileset
    from background import Background
    from scoring import scoreGame
    from scoringdialog import ScoreTable, ExplainView
    from humanclient import HumanClient
    from rulesetselector import RulesetSelector
    from animation import afterQueuedAnimations, AnimationSpeed
    from chat import ChatWindow
    from scene import PlayingScene, ScoringScene
    from configdialog import ConfigDialog
    from statesaver import StateSaver
    from util import checkMemory
    from kdestub import Action, KApplication

except ImportError as importError:
    NOTFOUND.append('Kajongg is not correctly installed: modules: %s' %
                    importError)

if NOTFOUND:
    logError("\n".join(" * %s" % s for s in NOTFOUND), showStack=False)
    sys.exit(3)


def cleanExit(*unusedArgs):
    """close sqlite3 files before quitting"""
    if isAlive(Internal.mainWindow):
        if Debug.quit:
            logDebug('cleanExit calling mainWindow.close')
        Internal.mainWindow.close()
    else:
        # this must be very early or very late
        if Debug.quit:
            logDebug('cleanExit calling sys.exit(0)')
        # sys.exit(0)
        MainWindow.aboutToQuit()

handleSignals(cleanExit)


class MainWindow(KXmlGuiWindow):

    """the main window"""
    # pylint: disable=too-many-instance-attributes

    def __init__(self):
        # see https://marc.info/?l=kde-games-devel&m=120071267328984&w=2
        super().__init__()
        Internal.app.aboutToQuit.connect(self.aboutToQuit)
        self.exitConfirmed = None
        self.exitReady = None
        self.exitWaitTime = None
        Internal.mainWindow = self
        self._scene = None
        self.centralView = None
        self.background = Background()
        self.playerWindow = None
        self.rulesetWindow = None
        self.confDialog = None
        self.__installReactor()
        if Options.gui:
            KStandardAction.preferences(
                self.showSettings,
                self.actionCollection())
            self.setupUi()
            self.setupGUI()
            Internal.Preferences.addWatch(
                'tilesetName',
                self.tilesetNameChanged)
            Internal.Preferences.addWatch(
                'backgroundName',
                self.backgroundChanged)
            self.retranslateUi()
            for action in self.toolBar().actions():
                if 'onfigure' in action.text():
                    action.setPriority(QAction.Priority.LowPriority)
            if Options.host and not Options.demo:
                self.scene = PlayingScene(self)
                HumanClient()
            StateSaver(self)
            self.show()
        else:
            HumanClient()

    @staticmethod
    def __installReactor():
        """install the twisted reactor"""
        if not hasattr(Internal, 'reactor'):
            import qtreactor
            qtreactor.install()
            from twisted.internet import reactor
            reactor.runReturn(installSignalHandlers=False)
            Internal.reactor = reactor
            if Debug.quit:
                logDebug('Installed qtreactor')

    @property
    def scene(self):
        """a proxy"""
        return self._scene

    @scene.setter
    def scene(self, value):
        """if changing, updateGUI"""
        if not isAlive(self):
            return
        if self._scene == value:
            return
        if not value:
            self.actionChat.setChecked(False)
            self.actionExplain.setChecked(False)
            self.actionScoreTable.setChecked(False)
            self.actionExplain.setData(ExplainView)
            self.actionScoreTable.setData(ScoreTable)
        self._scene = value
        self.centralView.setScene(value)
        self.adjustMainView()
        self.updateGUI()
        canDemo = not value or isinstance(value, PlayingScene)
        self.actionChat.setEnabled(canDemo)
        self.actionAutoPlay.setEnabled(canDemo)
        self.actionExplain.setEnabled(value is not None)
        self.actionScoreTable.setEnabled(value is not None)

    def sizeHint(self):
        """give the main window a sensible default size"""
        result = KXmlGuiWindow.sizeHint(self)
        result.setWidth(result.height() * 3 // 2)
                        # we want space to the right for the buttons
        # the default is too small. Use at least 2/3 of screen height and 1/2
        # of screen width:
        available = KApplication.desktopSize()
        height = max(result.height(), available.height() * 2 // 3)
        width = max(result.width(), available.width() // 2)
        result.setHeight(height)
        result.setWidth(width)
        return result

    def _kajonggToggleAction(self, name, icon, shortcut=None, actionData=None):
        """a checkable action"""
        res = Action(self,
            name,
            icon,
            shortcut=shortcut,
            actionData=actionData)
        res.setCheckable(True)
        if actionData is not None:
            res.toggled.connect(self._toggleWidget)
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
        self.centralView = FittingView()
        layout = QGridLayout(centralWidget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.centralView)
        self.setCentralWidget(centralWidget)
        self.centralView.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.background = None  # just for pylint
        self.windTileset = Tileset(Internal.Preferences.windTilesetName)
        self.adjustMainView()
        self.actionScoreGame = Action(
            self,
            "scoreGame",
            "draw-freehand",
            self.scoringScene,
            Qt.Key.Key_C)
        self.actionPlayGame = Action(
            self,
            "play",
            "arrow-right",
            self.playGame,
            Qt.Key.Key_N)
        self.actionAbortGame = Action(
            self,
            "abort",
            "dialog-close",
            self.abortAction,
            Qt.Key.Key_W)
        self.actionAbortGame.setEnabled(False)
        self.actionQuit = Action(
            self,
            "quit",
            "application-exit",
            self.close,
            Qt.Key.Key_Q)
        self.actionPlayers = Action(
            self,
            "players", "im-user", self.slotPlayers)
        self.actionRulesets = Action(
            self,
            "rulesets",
            "games-kajongg-law",
            self.slotRulesets)
        self.actionChat = self._kajonggToggleAction("chat", "call-start",
                                                    shortcut=Qt.Key.Key_H, actionData=ChatWindow)
        self.actionChat.setEnabled(False)
        self.actionAngle = Action(
            self,
            "angle",
            "object-rotate-left",
            self.changeAngle,
            Qt.Key.Key_G)
        self.actionAngle.setEnabled(False)
        self.actionScoreTable = self._kajonggToggleAction(
            "scoreTable", "format-list-ordered",
            Qt.Key.Key_T, actionData=ScoreTable)
        self.actionScoreTable.setEnabled(False)
        self.actionExplain = self._kajonggToggleAction(
            "explain", "applications-education",
            Qt.Key.Key_E, actionData=ExplainView)
        self.actionExplain.setEnabled(False)
        self.actionFullscreen = self._kajonggToggleAction(
            "fullscreen", "view-fullscreen", shortcut=Qt.Key.Key_F | Qt.KeyboardModifier.ShiftModifier)
        self.actionFullscreen.toggled.connect(self.fullScreen)
        self.actionAutoPlay = Action(
            self,
            "demoMode",
            "arrow-right-double",
            None,
            Qt.Key.Key_D)
        self.actionAutoPlay.setCheckable(True)
        self.actionAutoPlay.setEnabled(True)
        self.actionAutoPlay.toggled.connect(self._toggleDemoMode)
        self.actionAutoPlay.setChecked(Internal.autoPlay)
        QMetaObject.connectSlotsByName(self)

    def playGame(self):
        """manual wish for a new game"""
        if not Internal.autoPlay:
            # only if no demo game is running
            self.playingScene()

    def playingScene(self):
        """play a computer game: log into a server and show its tables"""
        self.scene = PlayingScene(self)
        HumanClient()

    def scoringScene(self):
        """start a scoring scene"""
        scene = ScoringScene(self)
        game = scoreGame()
        if game:
            self.scene = scene
            scene.game = game
            game.throwDices()
            self.updateGUI()

    def fullScreen(self, toggle):
        """toggle between full screen and normal view"""
        if toggle:
            self.setWindowState(self.windowState() | Qt.WindowState.WindowFullScreen)
        else:
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowFullScreen)

    def close(self, unusedResult=None):
        """wrap close() because we call it with a QTimer"""
        if isAlive(self):
            return KXmlGuiWindow.close(self)
        return True  # is closed

    def closeEvent(self, event):
        KXmlGuiWindow.closeEvent(self, event)
        if event.isAccepted() and self.exitReady:
            QTimer.singleShot(5000, self.aboutToQuit)

    def queryClose(self):
        """queryClose, queryExit and aboutToQuit are no
        ideal match for the async Deferred approach.

        At app start, self.exitConfirmed and exitReady are None.

        queryClose will show a confirmation prompt if needed, but
        it will not wait for the answer. queryClose always returns True.

        Later, when the user confirms exit, self.exitConfirmed will be set.
        If the user cancels exit, self.exitConfirmed = False, otherwise
        self.close() is called. This time, no prompt will appear because the
        game has already been aborted.

        queryExit will return False if exitConfirmed or exitReady are not True.
        Otherwise, queryExit will set exitReady to False and asynchronously start
        shutdown. After the reactor stops running, exitReady is set to True,
        and self.close() is called. This time it should fall through everywhere,
        having queryClose() and queryExit() return True.

        and it will reset exitConfirmed to None.

        Or in other words: If queryClose or queryExit find something that they
        should do async like asking the user for confirmation or terminating
        the client/server connection, they start async operation and append
        a callback which will call self.close() when the async operation is
        done. This repeats until queryClose() and queryExit() find nothing
        more to do async. At that point queryExit says True
        and we really end the program.
        """

        def confirmed(result):
            """quit if the active game has been aborted"""
            self.exitConfirmed = bool(result)
            if Debug.quit:
                if self.exitConfirmed:
                    logDebug('mainWindow.queryClose confirmed')
                else:
                    logDebug('mainWindow.queryClose not confirmed')
            # start closing again. This time no question will appear, the game
            # is already aborted
            if self.exitConfirmed:
                assert isAlive(self)
                self.close()
            else:
                self.exitConfirmed = None

        def cancelled(result):
            """just do nothing"""
            if Debug.quit:
                logDebug('mainWindow.queryClose.cancelled: {}'.format(result))
            self.exitConfirmed = None
        if self.exitConfirmed is False:
            # user is currently being asked
            return False
        if self.exitConfirmed is None:
            if self.scene:
                self.exitConfirmed = False
                self.abortAction().addCallbacks(confirmed, cancelled)
            else:
                self.exitConfirmed = True
                if Debug.quit:
                    logDebug(
                        'MainWindow.queryClose not asking, exitConfirmed=True')
        return True

    def queryExit(self):
        """see queryClose"""
        def quitDebug(msg):
            """reducing branches in queryExit"""
            if Debug.quit:
                logDebug(msg)

        if self.exitReady:
            quitDebug('MainWindow.queryExit returns True because exitReady is set')
            return True
        if self.exitConfirmed:
            # now we can get serious
            self.exitReady = False
            for widget in chain(
                    (x.tableList for x in HumanClient.humanClients), [
                        self.confDialog,
                        self.rulesetWindow, self.playerWindow]):
                if isAlive(widget):
                    widget.hide()
            if self.exitWaitTime is None:
                self.exitWaitTime = 0
            if hasattr(Internal, 'reactor') and Internal.reactor.running:
                self.exitWaitTime += 10
                if self.exitWaitTime % 1000 == 0:
                    logDebug(
                        'waiting since %d seconds for reactor to stop' %
                        (self.exitWaitTime // 1000))
                try:
                    quitDebug('now stopping reactor')
                    Internal.reactor.stop()
                    assert isAlive(self)
                    QTimer.singleShot(10, self.close)
                except ReactorNotRunning:
                    self.exitReady = True
                    quitDebug(
                        'MainWindow.queryExit returns True: It got exception ReactorNotRunning')
            else:
                self.exitReady = True
                quitDebug('MainWindow.queryExit returns True: Reactor is not running')
        return bool(self.exitReady)

    @staticmethod
    def aboutToQuit():
        """now all connections to servers are cleanly closed"""
        mainWindow = Internal.mainWindow
        Internal.mainWindow = None
        if mainWindow:
            if Debug.quit:
                logDebug('aboutToQuit starting')
            if mainWindow.exitWaitTime is not None and mainWindow.exitWaitTime > 1000.0 or Debug.quit:
                logDebug(
                    'reactor stopped after %d ms' %
                    (mainWindow.exitWaitTime))
        else:
            if Debug.quit:
                logDebug('aboutToQuit: mainWindow is already None')
            # this does not happen with PyQt5/6 or PySide2, only with PySide6
            # return here to avoid recursion in StateSaver
            return
        StateSaver.saveAll()
        Internal.app.quit()
        try:
            # if we are killed while loading, Internal.db may not yet be
            # defined
            if Internal.db:
                Internal.db.close()
        except NameError:
            pass
        checkMemory()
        logging.shutdown()
        if Debug.quit:
            logDebug('aboutToQuit ending')

    def abortAction(self):
        """abort current game"""
        if Debug.quit:
            logDebug('mainWindow.abortAction invoked')
        return self.scene.abort()

    def retranslateUi(self):
        """retranslate"""
        self.actionScoreGame.setText(
            i18nc('@action:inmenu', "&Score Manual Game"))
        self.actionScoreGame.setIconText(
            i18nc('@action:intoolbar', 'Manual Game'))
        self.actionScoreGame.setWhatsThis(
            i18nc('kajongg @info:tooltip',
                  '&Score a manual game.'))

        self.actionPlayGame.setText(i18nc('@action:intoolbar', "&Play"))
        self.actionPlayGame.setPriority(QAction.Priority.LowPriority)
        self.actionPlayGame.setWhatsThis(
            i18nc('kajongg @info:tooltip', 'Start a new game.'))

        self.actionAbortGame.setText(i18nc('@action:inmenu', "&Abort Game"))
        self.actionAbortGame.setPriority(QAction.Priority.LowPriority)
        self.actionAbortGame.setWhatsThis(
            i18nc('kajongg @info:tooltip',
                  'Abort the current game.'))

        self.actionQuit.setText(i18nc('@action:inmenu', "&Quit Kajongg"))
        self.actionQuit.setPriority(QAction.Priority.LowPriority)

        self.actionPlayers.setText(i18nc('@action:intoolbar', "&Players"))
        self.actionPlayers.setWhatsThis(
            i18nc('kajongg @info:tooltip',
                  'define your players.'))

        self.actionRulesets.setText(i18nc('@action:intoolbar', "&Rulesets"))
        self.actionRulesets.setWhatsThis(
            i18nc('kajongg @info:tooltip',
                  'customize rulesets.'))

        self.actionAngle.setText(
            i18nc('@action:inmenu',
                  "&Change Visual Angle"))
        self.actionAngle.setIconText(i18nc('@action:intoolbar', "Angle"))
        self.actionAngle.setWhatsThis(
            i18nc('kajongg @info:tooltip',
                  "Change the visual appearance of the tiles."))

        self.actionFullscreen.setText(
            i18nc('@action:inmenu',
                  "F&ull Screen Mode"))

        self.actionScoreTable.setText(
            i18nc('kajongg @action:inmenu', "&Score Table"))
        self.actionScoreTable.setIconText(
            i18nc('kajongg @action:intoolbar', "&Scores"))
        self.actionScoreTable.setWhatsThis(i18nc('kajongg @info:tooltip',
                                                 "Show or hide the score table for the current game."))

        self.actionExplain.setText(i18nc('@action:inmenu', "&Explain Scores"))
        self.actionExplain.setIconText(i18nc('@action:intoolbar', "&Explain"))
        self.actionExplain.setWhatsThis(i18nc('kajongg @info:tooltip',
                                              'Explain the scoring for all players in the current game.'))

        self.actionAutoPlay.setText(i18nc('@action:inmenu', "&Demo Mode"))
        self.actionAutoPlay.setPriority(QAction.Priority.LowPriority)
        self.actionAutoPlay.setWhatsThis(i18nc('kajongg @info:tooltip',
                                               'Let the computer take over for you. Start a new local game if needed.'))

        self.actionChat.setText(i18n("C&hat"))
        self.actionChat.setWhatsThis(
            i18nc('kajongg @info:tooltip',
                  'Chat with the other players.'))

    def changeEvent(self, event):
        """when the applicationwide language changes, recreate GUI"""
        if event.type() == QEvent.Type.LanguageChange:
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

    def adjustMainView(self):
        """adjust the view such that exactly the wanted things are displayed
        without having to scroll"""
        if not isAlive(self):
            return
        view, scene = self.centralView, self.scene
        if scene:
            scene.adjustSceneView()
            view.fitInView(scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    @afterQueuedAnimations
    def backgroundChanged(self, unusedDeferredResult, unusedOldName, newName):
        """if the wanted background changed, apply the change now"""
        centralWidget = self.centralWidget()
        if centralWidget:
            self.background = Background(newName)
            self.background.setPalette(centralWidget)
            centralWidget.setAutoFillBackground(True)

    @afterQueuedAnimations
    def tilesetNameChanged(
            self, unusedDeferredResult, unusedOldValue=None,
            unusedNewValue=None):
        """if the wanted tileset changed, apply the change now"""
        if self.centralView:
            with AnimationSpeed():
                if self.scene:
                    self.scene.applySettings()
            self.adjustMainView()

    @afterQueuedAnimations
    def showSettings(self, unusedDeferredResult, unusedChecked=None):
        """show preferences dialog. If it already is visible, do nothing"""
        # This is called by the triggered() signal. So why does KDE
        # not return the bool checked?
        if ConfigDialog.showDialog("settings"):
            return
        # if an animation is running, Qt segfaults somewhere deep
        # in the SVG renderer rendering the wind tiles for the tile
        # preview
        self.confDialog = ConfigDialog(self, "settings")
        self.confDialog.show()

    def _toggleWidget(self, checked):
        """user has toggled widget visibility with an action"""
        assert self.scene
        action = self.sender()
        actionData = action.data()
        if checked:
            if isinstance(actionData, type):
                clsName = actionData.__name__
                actionData = actionData(scene=self.scene)
                action.setData(actionData)
                setattr(
                    self.scene,
                    clsName[0].lower() + clsName[1:],
                    actionData)
            actionData.show()
            actionData.raise_()
        else:
            assert actionData
            actionData.hide()

    def _toggleDemoMode(self, checked):
        """switch on / off for autoPlay"""
        if self.scene:
            self.scene.toggleDemoMode(checked)
        else:
            Internal.autoPlay = checked
            if checked and Internal.db:
                self.playingScene()

    def updateGUI(self):
        """update some actions, all auxiliary windows and the statusbar"""
        if not isAlive(self):
            return
        self.setCaption('')
        for action in [self.actionScoreGame, self.actionPlayGame]:
            action.setEnabled(not bool(self.scene))
        self.actionAbortGame.setEnabled(bool(self.scene))
        scene = self.scene
        if isAlive(scene):
            scene.updateSceneGUI()

    @afterQueuedAnimations
    def changeAngle(self, deferredResult, unusedButtons=None, unusedModifiers=None): # pylint: disable=unused-argument
        """change the lightSource"""
        if self.scene:
            with AnimationSpeed():
                self.scene.changeAngle()
