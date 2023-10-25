# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

import random

from twisted.spread import pb
from twisted.python.failure import Failure
from twisted.internet.defer import Deferred, succeed, DeferredList
from qt import Qt, QTimer
from qt import QDialog, QVBoxLayout, QGridLayout, \
    QLabel, QPushButton, QWidget, \
    QProgressBar, QRadioButton, QSpacerItem, QSizePolicy

from kde import KIcon, KDialog
from dialogs import Sorry, Information, QuestionYesNo, KDialogIgnoringEscape
from guiutil import decorateWindow
from log import i18n, logWarning, logException, logDebug
from message import Message
from common import Options, SingleshotOptions, Internal, Debug, isAlive
from query import Query
from board import Board
from client import Client, ClientTable
from tables import TableList, SelectRuleset
from sound import Voice
from login import Connection
from rule import Ruleset
from game import PlayingGame
from visible import VisiblePlayingGame


class SelectChow(KDialogIgnoringEscape):

    """asks which of the possible chows is wanted"""

    def __init__(self, chows, propose, deferred):
        KDialogIgnoringEscape.__init__(self)
        decorateWindow(self)
        self.setButtons(KDialog.NoButton)
        self.chows = chows
        self.selectedChow = None
        self.deferred = deferred
        layout = QVBoxLayout()
        label = QLabel(i18n('Which chow do you want to expose?'))
        layout.addWidget(label)
        layout.setAlignment(label, Qt.AlignmentFlag.AlignHCenter)
        self.buttons = []
        for chow in chows:
            button = QRadioButton('{}-{}-{}'.format(*(x.value for x in chow)))
            self.buttons.append(button)
            layout.addWidget(button)
            layout.setAlignment(button, Qt.AlignmentFlag.AlignHCenter)
            button.toggled.connect(self.toggled)
        widget = QWidget(self)
        widget.setLayout(layout)
        self.setMainWidget(widget)
        for idx, chow in enumerate(chows):
            if chow == propose:
                self.buttons[idx].setFocus()

    def toggled(self, unusedChecked):
        """a radiobutton has been toggled"""
        button = self.sender()
        if button.isChecked():
            self.selectedChow = self.chows[self.buttons.index(button)]
            self.accept()
            self.deferred.callback((Message.Chow, self.selectedChow))


class SelectKong(KDialogIgnoringEscape):

    """asks which of the possible kongs is wanted"""

    def __init__(self, kongs, deferred):
        KDialogIgnoringEscape.__init__(self)
        decorateWindow(self)
        self.setButtons(0)
        self.kongs = kongs
        self.selectedKong = None
        self.deferred = deferred
        layout = QVBoxLayout()
        label = QLabel(i18n('Which kong do you want to declare?'))
        layout.addWidget(label)
        layout.setAlignment(label, Qt.AlignmentFlag.AlignHCenter)
        self.buttons = []
        for kong in kongs:
            button = QRadioButton((kong[0].name()), self)
            self.buttons.append(button)
            layout.addWidget(button)
            button.toggled.connect(self.toggled)
        widget = QWidget(self)
        widget.setLayout(layout)
        self.setMainWidget(widget)

    def toggled(self, unusedChecked):
        """a radiobutton has been toggled"""
        button = self.sender()
        if button.isChecked():
            self.selectedKong = self.kongs[self.buttons.index(button)]
            self.accept()
            self.deferred.callback((Message.Kong, self.selectedKong))


class DlgButton(QPushButton):

    """special button for ClientDialog"""

    def __init__(self, message, parent):
        QPushButton.__init__(self, parent)
        self.message = message
        self.client = parent.client
        self.setMinimumHeight(25)
        self.setText(message.buttonCaption())

    def setMeaning(self, uiTile):
        """give me caption, shortcut, tooltip, icon"""
        txt, warn, _ = self.message.toolTip(
            self, uiTile.tile if uiTile else None)
        if not txt:
            txt = self.message.i18nName  # .replace(i18nShortcut, '&'+i18nShortcut, 1)
        self.setToolTip(txt)
        self.setWarning(warn)

    def keyPressEvent(self, event):
        """forward horizintal arrows to the hand board"""
        key = Board.mapChar2Arrow(event)
        if key in [Qt.Key.Key_Left, Qt.Key.Key_Right]:
            game = self.client.game
            if game and game.activePlayer == game.myself:
                game.myself.handBoard.keyPressEvent(event)
                self.setFocus()
                return
        QPushButton.keyPressEvent(self, event)

    def setWarning(self, warn):
        """if warn, show a warning icon on the button"""
        if warn:
            self.setIcon(KIcon('dialog-warning'))
        else:
            self.setIcon(KIcon())


class ClientDialog(QDialog):

    """a simple popup dialog for asking the player what he wants to do"""

    def __init__(self, client, parent=None):
        QDialog.__init__(self, parent)
        decorateWindow(self, i18n('Choose'))
        self.setObjectName('ClientDialog')
        self.client = client
        self.gridLayout = QGridLayout(self)
        self.progressBar = QProgressBar()
        self.progressBar.setMinimumHeight(25)
        self.timer = QTimer()
        if not client.game.autoPlay:
            self.timer.timeout.connect(self.timeout)
        self.deferred = None
        self.buttons = []
        self.setWindowFlags(Qt.WindowType.SubWindow | Qt.WindowType.WindowStaysOnTopHint)
        self.setModal(False)
        self.btnHeight = 0
        self.answered = False
        self.sorry = None

    def keyPressEvent(self, event):
        """ESC selects default answer"""
        if not self.client.game or self.client.game.autoPlay:
            return
        if event.key() in [Qt.Key.Key_Escape, Qt.Key.Key_Space]:
            self.selectButton()
            event.accept()
        else:
            for btn in self.buttons:
                if str(event.text()).upper() == btn.message.shortcut:
                    self.selectButton(btn)
                    event.accept()
                    return
            QDialog.keyPressEvent(self, event)

    def __declareButton(self, message):
        """define a button"""
        maySay = self.client.game.myself.sayable[message]
        if Internal.Preferences.showOnlyPossibleActions and not maySay:
            return
        btn = DlgButton(message, self)
        btn.setAutoDefault(True)
        btn.clicked.connect(self.selectedAnswer)
        self.buttons.append(btn)

    def focusTileChanged(self):
        """update icon and tooltip for the discard button"""
        if not self.client.game:
            return
        assert self.client.game.myself  # FIXME: needed?
        assert self.client.game.myself.handBoard
        for button in self.buttons:
            button.setMeaning(self.client.game.myself.handBoard.focusTile)
        for uiTile in self.client.game.myself.handBoard.lowerHalfTiles():
            txt = []
            for button in self.buttons:
                _, _, tileTxt = button.message.toolTip(button, uiTile.tile)
                if tileTxt:
                    txt.append(tileTxt)
            uiTile.setToolTip('<br><br>'.join(txt))
        if self.client.game.activePlayer == self.client.game.myself:
            Internal.scene.handSelectorChanged(
                self.client.game.myself.handBoard)

    def checkTiles(self):
        """does the logical state match the displayed tiles?"""
        for player in self.client.game.players:
            player.handBoard.checkTiles()

    def messages(self):
        """a list of all messages returned by the declared buttons"""
        return [x.message for x in self.buttons]

    def proposeAction(self):
        """either intelligently or first button by default. May also
        focus a proposed tile depending on the action."""
        result = self.buttons[0]
        game = self.client.game
        if game.autoPlay or Internal.Preferences.propose:
            answer, parameter = game.myself.intelligence.selectAnswer(
                self.messages())
            result = [x for x in self.buttons if x.message == answer][0]
            result.setFocus()
            if answer in [Message.Discard, Message.OriginalCall]:
                for uiTile in game.myself.handBoard.uiTiles:
                    if uiTile.tile is parameter:
                        game.myself.handBoard.focusTile = uiTile
        return result

    def askHuman(self, move, answers, deferred):
        """make buttons specified by answers visible. The first answer is default.
        The default button only appears with blue border when this dialog has
        focus but we always want it to be recognizable. Hence setBackgroundRole."""
        self.move = move
        self.deferred = deferred
        for answer in answers:
            self.__declareButton(answer)
        self.focusTileChanged()
        self.show()
        self.checkTiles()
        game = self.client.game
        myTurn = game.activePlayer == game.myself
        prefButton = self.proposeAction()
        if game.autoPlay:
            self.selectButton(prefButton)
            return
        prefButton.setFocus()

        self.progressBar.setVisible(not myTurn)
        if not myTurn:
            msecs = 50
            self.progressBar.setMinimum(0)
            self.progressBar.setMaximum(
                game.ruleset.claimTimeout * 1000 // msecs)
            self.progressBar.reset()
            self.timer.start(msecs)

    def placeInField(self):
        """place the dialog at bottom or to the right depending on space."""
        mainWindow = Internal.scene.mainWindow
        cwi = mainWindow.centralWidget()
        view = mainWindow.centralView
        geometry = self.geometry()
        if not self.btnHeight:
            self.btnHeight = self.buttons[0].height()
        vertical = view.width() > view.height() * 1.2
        if vertical:
            height = (len(self.buttons) + 1) * self.btnHeight * 1.2
            width = (cwi.width() - cwi.height()) // 2
            geometry.setX(cwi.width() - width)
            geometry.setY(min(cwi.height() // 3, cwi.height() - height))
        else:
            handBoard = self.client.game.myself.handBoard
            if not handBoard:
                # we are in the progress of logging out
                return
            hbLeftTop = view.mapFromScene(
                handBoard.mapToScene(handBoard.rect().topLeft()))
            hbRightBottom = view.mapFromScene(
                handBoard.mapToScene(handBoard.rect().bottomRight()))
            width = hbRightBottom.x() - hbLeftTop.x()
            height = self.btnHeight
            geometry.setY(cwi.height() - height)
            geometry.setX(hbLeftTop.x())
        for idx, btn in enumerate(self.buttons + [self.progressBar]):
            self.gridLayout.addWidget(
                btn,
                idx +
                1 if vertical else 0,
                idx +
                1 if not vertical else 0)
        idx = len(self.buttons) + 2
        spacer = QSpacerItem(
            20,
            20,
            QSizePolicy.Expanding,
            QSizePolicy.Expanding)
        self.gridLayout.addItem(
            spacer,
            idx if vertical else 0,
            idx if not vertical else 0)

        geometry.setWidth(int(width))
        geometry.setHeight(int(height))
        self.setGeometry(geometry)

    def showEvent(self, unusedEvent):
        """try to place the dialog such that it does not cover interesting information"""
        self.placeInField()

    def timeout(self):
        """the progressboard wants an update"""
        pBar = self.progressBar
        if isAlive(pBar):
            pBar.setValue(pBar.value() + 1)
            pBar.setVisible(True)
            if pBar.value() == pBar.maximum():
                # timeout: we always return the original default answer, not
                # the one with focus
                self.selectButton()
                pBar.setVisible(False)

    def selectButton(self, button=None):
        """select default answer. button may also be of type Message."""
        if self.answered:
            # sometimes we get this event twice
            return
        if button is None:
            button = self.focusWidget()
        if isinstance(button, Message):
            assert any(x.message == button for x in self.buttons)
            answer = button
        else:
            answer = button.message
        if not self.client.game.myself.sayable[answer]:
            self.proposeAction().setFocus() # go back to default action
            self.sorry = Sorry(i18n('You cannot say %1', answer.i18nName))
            return
        self.timer.stop()
        self.answered = True
        if self.sorry:
            self.sorry.cancel()
        self.sorry = None
        Internal.scene.clientDialog = None
        self.deferred.callback(answer)

    def selectedAnswer(self, unusedChecked):
        """the user clicked one of the buttons"""
        game = self.client.game
        if game and not game.autoPlay:
            self.selectButton(self.sender())


class HumanClient(Client):

    """a human client"""
    humanClients = []

    def __init__(self):
        Client.__init__(self)
        HumanClient.humanClients.append(self)
        self.table = None
        self.ruleset = None
        self.beginQuestion = None
        self.tableList = TableList(self)
        Connection(self).login().addCallbacks(
            self.__loggedIn,
            self.__loginFailed)

    @staticmethod
    def shutdownHumanClients(exception=None):
        """close connections to servers except maybe one"""
        clients = HumanClient.humanClients

        def done():
            """return True if clients is cleaned"""
            return len(clients) == 0 or (exception and clients == [exception])

        def disconnectedClient(unusedResult, client):
            """now the client is really disconnected from the server"""
            if client in clients:
                # HumanClient.serverDisconnects also removes it!
                clients.remove(client)
        if isinstance(exception, Failure):
            logException(exception)
        for client in clients[:]:
            if client.tableList:
                client.tableList.hide()
        if done():
            return succeed(None)
        deferreds = []
        for client in clients[:]:
            if client != exception and client.connection:
                deferreds.append(
                    client.logout(
                    ).addCallback(
                        disconnectedClient,
                        client))
        return DeferredList(deferreds)

    def __loggedIn(self, connection):
        """callback after the server answered our login request"""
        self.connection = connection
        self.ruleset = connection.ruleset
        self.name = connection.username
        self.tableList.show()
        voiceId = None
        if Internal.Preferences.uploadVoice:
            voice = Voice.locate(self.name)
            if voice:
                voiceId = voice.md5sum
            if Debug.sound and voiceId:
                logDebug(
                    '%s sends own voice %s to server' %
                    (self.name, voiceId))
        maxGameId = Query('select max(id) from game').records[0][0]
        maxGameId = int(maxGameId) if maxGameId else 0
        self.callServer('setClientProperties',
                        Internal.db.identifier,
                        voiceId, maxGameId,
                        Internal.defaultPort).addCallbacks(self.__initTableList, self.__versionError)

    def __initTableList(self, unused):
        """first load of the list. Process options like --demo, --table, --join"""
        self.showTableList()
        if SingleshotOptions.table:
            Internal.autoPlay = False
            self.__requestNewTableFromServer(SingleshotOptions.table).addCallback(
                self.__showTables).addErrback(self.tableError)
            if Debug.table:
                logDebug(
                    '%s: --table lets us open a new table' % self.name)
            SingleshotOptions.table = False
        elif SingleshotOptions.join:
            Internal.autoPlay = False
            self.callServer('joinTable', SingleshotOptions.join).addCallback(
                self.__showTables).addErrback(self.tableError)
            if Debug.table:
                logDebug(
                    '%s: --join lets us join table %s' %
                    (self.name, self._tableById(SingleshotOptions.join)))
            SingleshotOptions.join = False
        elif not self.game and (Internal.autoPlay or (not self.tables and self.hasLocalServer())):
            self.__requestNewTableFromServer().addCallback(
                self.__newLocalTable).addErrback(self.tableError)
        else:
            self.__showTables()

    @staticmethod
    def __loginFailed(unused):
        """as the name says"""
        if Internal.scene:
            Internal.scene.startingGame = False

    def isRobotClient(self):
        """avoid using isinstance, it would import too much for kajonggserver"""
        return False

    @staticmethod
    def isHumanClient():
        """avoid using isinstance, it would import too much for kajonggserver"""
        return True

    def isServerClient(self):
        """avoid using isinstance, it would import too much for kajonggserver"""
        return False

    def hasLocalServer(self):
        """True if we are talking to a Local Game Server"""
        return self.connection and self.connection.url.isLocalHost

    def __updateTableList(self):
        """if it exists"""
        if self.tableList:
            self.tableList.loadTables(self.tables)

    def __showTables(self, unused=None):
        """load and show tables. We may be used as a callback. In that case,
        clientTables is the id of a new table - which we do not need here"""
        self.tableList.loadTables(self.tables)
        self.tableList.show()

    def showTableList(self, unused=None):
        """allocate it if needed"""
        if not self.tableList:
            self.tableList = TableList(self)
        self.tableList.loadTables(self.tables)
        self.tableList.activateWindow()

    def remote_tableRemoved(self, tableid, message, *args):
        """update table list"""
        Client.remote_tableRemoved(self, tableid, message, *args)
        self.__updateTableList()
        if message:
            if self.name not in args or not message.endswith('has logged out'):
                logWarning(i18n(message, *args))

    def __receiveTables(self, tables):
        """now we already know all rulesets for those tables"""
        Client.remote_newTables(self, tables)
        if not Internal.autoPlay:
            if self.hasLocalServer():
                # when playing a local game, only show pending tables with
                # previously selected ruleset
                self.tables = [x for x in self.tables if x.ruleset == self.ruleset]
        if self.tables:
            self.__updateTableList()

    def remote_newTables(self, tables):
        """update table list"""
        assert tables

        def gotRulesets(result):
            """the server sent us the wanted ruleset definitions"""
            for ruleset in result:
                Ruleset.cached(ruleset).save()  # make it known to the cache and save in db
            return tables
        rulesetHashes = {x[1] for x in tables}
        needRulesets = [x for x in rulesetHashes if not Ruleset.hashIsKnown(x)]
        if needRulesets:
            self.callServer(
                'needRulesets',
                needRulesets).addCallback(
                    gotRulesets).addCallback(
                        self.__receiveTables)
        else:
            self.__receiveTables(tables)

    @staticmethod
    def remote_needRuleset(ruleset):
        """server only knows hash, needs full definition"""
        result = Ruleset.cached(ruleset)
        assert result and result.hash == ruleset
        return result.toList()

    def tableChanged(self, table):
        """update table list"""
        oldTable, newTable = Client.tableChanged(self, table)
        if oldTable and oldTable == self.table:
            # this happens if a table has more than one human player and
            # one of them leaves the table. In that case, the other players
            # need this code.
            self.table = newTable
            if len(newTable.playerNames) == 3:
                # only tell about the first player leaving, because the
                # others will then automatically leave too
                for name in oldTable.playerNames:
                    if name != self.name and not newTable.isOnline(name):
                        def sorried(unused):
                            """user ack"""
                            game = self.game
                            if game:
                                self.game = None
                                return game.close()
                            return None
                        if self.beginQuestion:
                            self.beginQuestion.cancel()
                        Sorry(i18n('Player %1 has left the table', name)).addCallback(
                            sorried).addCallback(self.showTableList)
                        break
        self.__updateTableList()
        return oldTable, newTable

    def readyForGameStart(
            self, tableid, gameid, wantedGame, playerNames, shouldSave=True,
            gameClass=None):
        """playerNames are in wind order ESWN"""
        if gameClass is None:
            if Options.gui:
                gameClass = VisiblePlayingGame
            else:
                gameClass = PlayingGame

        def clientReady():
            """macro"""
            return Client.readyForGameStart(
                self, tableid, gameid, wantedGame, playerNames,
                shouldSave, gameClass)

        def answered(result):
            """callback, called after the client player said yes or no"""
            self.beginQuestion = None
            if self.connection and result:
                # still connected and yes, we are
                return clientReady()
            return Message.NoGameStart

        def cancelled(unused):
            """the user does not want to start now. Back to table list"""
            if Debug.table:
                logDebug('%s: Readyforgamestart returns Message.NoGameStart for table %s' % (
                    self.name, self._tableById(tableid)))
            self.table = None
            self.beginQuestion = None
            if self.tableList:
                self.__updateTableList()
                self.tableList.show()
            return Message.NoGameStart
        if sum(not x[1].startswith('Robot ') for x in playerNames) == 1:
            # we play against 3 robots and we already told the server to start:
            # no need to ask again
            return clientReady()
        assert not self.table
        assert self.tables
        self.table = self._tableById(tableid)
        if not self.table:
            raise pb.Error(
                'client.readyForGameStart: tableid %d unknown' %
                tableid)
        msg = i18n(
            "The game on table <numid>%1</numid> can begin. Are you ready to play now?",
            tableid)
        self.beginQuestion = QuestionYesNo(msg, modal=False, caption=self.name).addCallback(
            answered).addErrback(cancelled)
        return self.beginQuestion

    def readyForHandStart(self, playerNames, rotateWinds):
        """playerNames are in wind order ESWN. Never called for first hand."""
        def answered(unused=None):
            """called after the client player said yes, I am ready"""
            return Client.readyForHandStart(self, playerNames, rotateWinds) if self.connection else None
        if not self.connection:
            # disconnected meanwhile
            return None
        if Options.gui:
            # update the balances in the status bar:
            Internal.mainWindow.updateGUI()
        assert not self.game.isFirstHand()
        return Information(i18n("Ready for next hand?"), modal=False).addCallback(answered)

    def ask(self, move, answers):
        """server sends move. We ask the user. answers is a list with possible answers,
        the default answer being the first in the list."""
        if not Options.gui:
            return Client.ask(self, move, answers)
        self.game.myself.computeSayable(move, answers)
        deferred = Deferred()
        deferred.addCallback(self.__askAnswered)
        deferred.addErrback(self.__answerError, move, answers)
        iAmActive = self.game.myself == self.game.activePlayer
        self.game.myself.handBoard.setEnabled(iAmActive)
        scene = Internal.scene
        oldDialog = scene.clientDialog
        assert oldDialog is None or oldDialog.answered, \
            'old dialog %s:%s is unanswered, new Dialog: %s/%s' % (
                str(oldDialog.move),
                str([x.message.name for x in oldDialog.buttons]),
                str(move), str(answers))
        if not oldDialog or not oldDialog.isVisible():
            # always build a new dialog because if we change its layout before
            # reshowing it, sometimes the old buttons are still visible in which
            # case the next dialog will appear at a lower position than it
            # should
            scene.clientDialog = ClientDialog(
                self,
                scene.mainWindow.centralWidget())
        assert scene.clientDialog.client is self
        scene.clientDialog.askHuman(move, answers, deferred)
        return deferred

    def __selectChow(self, chows):
        """which possible chow do we want to expose?
        Since we might return a Deferred to be sent to the server,
        which contains Message.Chow plus selected Chow, we should
        return the same tuple here"""
        intelligence = self.game.myself.intelligence
        if self.game.autoPlay:
            return Message.Chow, intelligence.selectChow(chows)
        if len(chows) == 1:
            return Message.Chow, chows[0]
        if Internal.Preferences.propose:
            propose = intelligence.selectChow(chows)
        else:
            propose = None
        deferred = Deferred()
        selDlg = SelectChow(chows, propose, deferred)
        assert selDlg.exec_()
        return deferred

    def __selectKong(self, kongs):
        """which possible kong do we want to declare?"""
        if self.game.autoPlay:
            return Message.Kong, self.game.myself.intelligence.selectKong(kongs)
        if len(kongs) == 1:
            return Message.Kong, kongs[0]
        deferred = Deferred()
        selDlg = SelectKong(kongs, deferred)
        assert selDlg.exec_()
        return deferred

    def __askAnswered(self, answer):
        """the user answered our question concerning move"""
        if not self.game:
            return Message.NoClaim
        myself = self.game.myself
        if answer in [Message.Discard, Message.OriginalCall]:
            # do not remove tile from hand here, the server will tell all players
            # including us that it has been discarded. Only then we will remove
            # it.
            myself.handBoard.setEnabled(False)
            return answer, myself.handBoard.focusTile.tile
        args = myself.sayable[answer]
        assert args
        if answer == Message.Chow:
            return self.__selectChow(args)
        if answer == Message.Kong:
            return self.__selectKong(args)
        self.game.hidePopups()
        if args is True or args == []:
            # this does not specify any tiles, the server does not need this. Robot players
            # also return None in this case.
            return answer
        return answer, args

    def __answerError(self, answer, move, answers):
        """an error happened while determining the answer to server"""
        logException(
            '%s %s %s %s' %
            (self.game.myself.name if self.game else 'NOGAME', answer, move, answers))

    def remote_abort(self, tableid, message: str, *args):
        """the server aborted this game"""
        if self.table and self.table.tableid == tableid:
            # translate Robot to Roboter:
            if self.game:
                args = self.game.players.translatePlayerNames(args)
            logWarning(i18n(message, *args))
            if self.game:
                self.game.close()
                self.game = None

    def remote_gameOver(self, tableid, message, *args):
        """the game is over"""
        def yes(unused):
            """now that the user clicked the 'game over' prompt away, clean up"""
            if self.game:
                self.game.rotateWinds()
                self.game.close().addCallback(Internal.mainWindow.close)
        assert self.table and self.table.tableid == tableid
        if Internal.scene:
            # update the balances in the status bar:
            Internal.scene.mainWindow.updateGUI()
        Information(i18n(message, *args)).addCallback(yes)

    def remote_serverDisconnects(self, result=None):
        """we logged out or lost connection to the server.
        Remove visual traces depending on that connection."""
        if Debug.connections and result:
            logDebug(
                'server %s disconnects: %s' %
                (self.connection, result))
        self.connection = None
        game = self.game
        self.game = None  # avoid races: messages might still arrive
        if self.tableList:
            self.tableList.hide()
            self.tableList = None
        if self in HumanClient.humanClients:
            HumanClient.humanClients.remove(self)
        if self.beginQuestion:
            self.beginQuestion.cancel()
        scene = Internal.scene
        if scene and game and scene.game == game:
            scene.game = None
        if not Options.gui:
            Internal.mainWindow.close()

    def serverDisconnected(self, unusedReference):
        """perspective calls us back"""
        if self.connection and (Debug.traffic or Debug.connections):
            logDebug(
                'perspective notifies disconnect: %s' %
                self.connection.url)
        self.remote_serverDisconnects()

    @staticmethod
    def __versionError(err):
        """log the twisted error"""
        logWarning(err.getErrorMessage())
        if Internal.game:
            Internal.game.close()
            Internal.game = None
        return err

    @staticmethod
    def __wantedGame():
        """find out which game we want to start on the table"""
        result = SingleshotOptions.game
        if not result or result == '0':
            result = str(int(random.random() * 10 ** 9))
        SingleshotOptions.game = None
        return result

    def tableError(self, err):
        """log the twisted error"""
        if not self.connection:
            # lost connection to server
            if self.tableList:
                self.tableList.hide()
                self.tableList = None
        else:
            logWarning(err.getErrorMessage())

    def __newLocalTable(self, newId):
        """we just got newId from the server"""
        return self.callServer('startGame', newId).addErrback(self.tableError)

    def __requestNewTableFromServer(self, tableid=None, ruleset=None):
        """as the name says"""
        if ruleset is None:
            ruleset = self.ruleset
        self.connection.ruleset = ruleset  # side effect: saves ruleset as last used for server
        return self.callServer('newTable', ruleset.hash, Options.playOpen,
                               Internal.autoPlay, self.__wantedGame(), tableid).addErrback(self.tableError)

    def newTable(self):
        """TableList uses me as a slot"""
        if Options.ruleset:
            ruleset = Options.ruleset
        elif self.hasLocalServer():
            ruleset = self.ruleset
        else:
            selectDialog = SelectRuleset(self.connection.url)
            if not selectDialog.exec_():
                return
            ruleset = selectDialog.cbRuleset.current
        deferred = self.__requestNewTableFromServer(ruleset=ruleset)
        if self.hasLocalServer():
            deferred.addCallback(self.__newLocalTable)
        self.tableList.requestedNewTable = True

    def joinTable(self, table=None):
        """join a table"""
        if not isinstance(table, ClientTable):
            table = self.tableList.selectedTable()
        self.callServer('joinTable', table.tableid).addErrback(self.tableError)

    def logout(self, unusedResult=None):
        """clean visual traces and logout from server"""
        def loggedout(result, connection):
            """end the connection from client side"""
            if Debug.connections:
                logDebug('server confirmed logout for {}'.format(self))
            connection.connector.disconnect()
            return result
        if self.connection:
            conn = self.connection
            self.connection = None
            if Debug.connections:
                logDebug('sending logout to server for {}'.format(self))
            return self.callServer('logout').addCallback(loggedout, conn)
        return succeed(None)

    def __logCallServer(self, *args):
        """for Debug.traffic"""
        debugArgs = list(args[:])
        if Debug.neutral:
            if debugArgs[0] == 'ping':
                return
            if debugArgs[0] == 'setClientProperties':
                debugArgs[1] = 'DBID'
                debugArgs[3] = 'GAMEID'
                if debugArgs[4] >= 8300:
                    debugArgs[4] -= 300
        if self.game:
            self.game.debug('callServer(%s)' % repr(debugArgs))
        else:
            logDebug('callServer(%s)' % repr(debugArgs))

    def callServer(self, *args):
        """if we are online, call server"""
        if self.connection:
            if args[0] is None:
                args = args[1:]
            try:
                if Debug.traffic:
                    self.__logCallServer(*args)

                def callServerError(result):
                    """if serverDisconnected has been called meanwhile, just ignore msg about
                    connection lost in a non-clean fashion"""
                    return result if self.connection else None
                return self.connection.perspective.callRemote(*args).addErrback(callServerError)
            except pb.DeadReferenceError:
                logWarning(
                    i18n(
                        'The connection to the server %1 broke, please try again later.',
                        self.connection.url))
                self.remote_serverDisconnects()
                return succeed(None)
        else:
            return succeed(None)

    def sendChat(self, chatLine):
        """send chat message to server"""
        return self.callServer('chat', chatLine.asList())
