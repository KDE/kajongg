# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

import csv, resource

from twisted.spread import pb
from twisted.internet.defer import Deferred, succeed
from PyQt4.QtCore import Qt, QTimer
from PyQt4.QtGui import QDialog, QVBoxLayout, QGridLayout, \
    QLabel, QPushButton, \
    QProgressBar, QRadioButton, QSpacerItem, QSizePolicy

from kde import Sorry, Information, QuestionYesNo, KIcon, \
    DialogIgnoringEscape

from util import m18n, logWarning, logException, \
    logInfo, logDebug
from message import Message, ChatMessage
from chat import ChatWindow
from common import Options, Internal, Preferences, Debug, isAlive
from query import Query
from board import Board
from client import Client, ClientTable
from meld import Meld
from tables import TableList
from sound import Voice
import intelligence
import altint
from login import Connection

class SelectChow(DialogIgnoringEscape):
    """asks which of the possible chows is wanted"""
    def __init__(self, chows, propose, deferred):
        DialogIgnoringEscape.__init__(self)
        self.setWindowTitle('Kajongg')
        self.chows = chows
        self.selectedChow = None
        self.deferred = deferred
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(m18n('Which chow do you want to expose?')))
        self.buttons = []
        for chow in chows:
            button = QRadioButton('-'.join([chow[0][1], chow[1][1], chow[2][1]]), self)
            self.buttons.append(button)
            layout.addWidget(button)
            button.toggled.connect(self.toggled)
        for idx, chow in enumerate(chows):
            if chow == propose:
                self.buttons[idx].setFocus()

    def toggled(self, dummyChecked):
        """a radiobutton has been toggled"""
        button = self.sender()
        if button.isChecked():
            self.selectedChow = self.chows[self.buttons.index(button)]
            self.accept()
            self.deferred.callback((Message.Chow, self.selectedChow))

    def closeEvent(self, event):
        """allow close only if a chow has been selected"""
        if self.selectedChow:
            event.accept()
        else:
            event.ignore()

class SelectKong(DialogIgnoringEscape):
    """asks which of the possible kongs is wanted"""
    def __init__(self, kongs, deferred):
        DialogIgnoringEscape.__init__(self)
        self.setWindowTitle('Kajongg')
        self.kongs = kongs
        self.selectedKong = None
        self.deferred = deferred
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(m18n('Which kong do you want to declare?')))
        self.buttons = []
        for kong in kongs:
            button = QRadioButton(Meld.tileName(kong[0]), self)
            self.buttons.append(button)
            layout.addWidget(button)
            button.toggled.connect(self.toggled)

    def toggled(self, dummyChecked):
        """a radiobutton has been toggled"""
        button = self.sender()
        if button.isChecked():
            self.selectedKong = self.kongs[self.buttons.index(button)]
            self.accept()
            self.deferred.callback((Message.Kong, self.selectedKong))

    def closeEvent(self, event):
        """allow close only if a chow has been selected"""
        if self.selectedKong:
            event.accept()
        else:
            event.ignore()

class DlgButton(QPushButton):
    """special button for ClientDialog"""
    def __init__(self, message, parent):
        QPushButton.__init__(self, parent)
        self.message = message
        self.client = parent.client
        self.setText(message.buttonCaption())

    def decorate(self, tile):
        """give me caption, shortcut, tooltip, icon"""
        txt, warn, _ = self.message.toolTip(self, tile)
        if not txt:
            txt = self.message.i18nName  # .replace(i18nShortcut, '&'+i18nShortcut, 1)
        self.setToolTip(txt)
        self.setWarning(warn)

    def keyPressEvent(self, event):
        """forward horizintal arrows to the hand board"""
        key = Board.mapChar2Arrow(event)
        if key in [Qt.Key_Left, Qt.Key_Right]:
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
        self.setWindowTitle(m18n('Choose') + ' - Kajongg')
        self.setObjectName('ClientDialog')
        self.client = client
        self.layout = QGridLayout(self)
        self.progressBar = QProgressBar()
        self.timer = QTimer()
        if not client.game.autoPlay:
            self.timer.timeout.connect(self.timeout)
        self.deferred = None
        self.buttons = []
        self.setWindowFlags(Qt.SubWindow | Qt.WindowStaysOnTopHint)
        self.setModal(False)
        self.btnHeight = 0
        self.answered = False

    def keyPressEvent(self, event):
        """ESC selects default answer"""
        if not self.client.game or self.client.game.autoPlay:
            return
        if event.key() in [Qt.Key_Escape, Qt.Key_Space]:
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
        maySay = self.client.sayable[message]
        if Preferences.showOnlyPossibleActions and not maySay:
            return
        btn = DlgButton(message, self)
        btn.setAutoDefault(True)
        btn.clicked.connect(self.selectedAnswer)
        self.buttons.append(btn)

    def focusTileChanged(self):
        """update icon and tooltip for the discard button"""
        for button in self.buttons:
            button.decorate(self.client.game.myself.handBoard.focusTile)
        for tile in self.client.game.myself.handBoard.lowerHalfTiles():
            txt = []
            for button in self.buttons:
                _, _, tileTxt = button.message.toolTip(button, tile)
                if tileTxt:
                    txt.append(tileTxt)
            txt = '<br><br>'.join(txt)
            tile.graphics.setToolTip(txt)
        if self.client.game.activePlayer == self.client.game.myself:
            Internal.field.handSelectorChanged(self.client.game.myself.handBoard)

    def checkTiles(self):
        """does the logical state match the displayed tiles?"""
        for player in self.client.game.players:
            logExposed = list()
            physExposed = list()
            physConcealed = list()
            for tile in player.bonusTiles:
                logExposed.append(tile.element)
            for tile in player.handBoard.tiles:
                if tile.yoffset == 0 or tile.element[0] in 'fy':
                    physExposed.append(tile.element)
                else:
                    physConcealed.append(tile.element)
            for meld in player.exposedMelds:
                logExposed.extend(meld.pairs)
            logConcealed = sorted(player.concealedTileNames)
            logExposed.sort()
            physExposed.sort()
            physConcealed.sort()
            assert logExposed == physExposed, '%s != %s' % (logExposed, physExposed)
            assert logConcealed == physConcealed, '%s != %s' % (logConcealed, physConcealed)

    def messages(self):
        """a list of all messages returned by the declared buttons"""
        return list(x.message for x in self.buttons)

    def proposeAction(self):
        """either intelligently or first button by default. May also
        focus a proposed tile depending on the action."""
        result = self.buttons[0]
        game = self.client.game
        if game.autoPlay or Preferences.propose:
            answer, parameter = self.client.intelligence.selectAnswer(
                self.messages())
            result = [x for x in self.buttons if x.message == answer][0]
            result.setFocus()
            if answer in [Message.Discard, Message.OriginalCall]:
                for tile in game.myself.handBoard.tiles:
                    if tile.element == parameter:
                        game.myself.handBoard.focusTile = tile
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
            self.progressBar.setMaximum(game.ruleset.claimTimeout * 1000 // msecs)
            self.progressBar.reset()
            self.timer.start(msecs)

    def placeInField(self):
        """place the dialog at bottom or to the right depending on space."""
        field = Internal.field
        cwi = field.centralWidget()
        view = field.centralView
        geometry = self.geometry()
        if not self.btnHeight:
            self.btnHeight = self.buttons[0].height()
        vertical = view.width() > view.height() * 1.2
        if vertical:
            height = (len(self.buttons) + 1) * self.btnHeight * 1.2
            width = (cwi.width() - cwi.height() ) // 2
            geometry.setX(cwi.width() - width)
            geometry.setY(min(cwi.height()//3, cwi.height() - height))
        else:
            handBoard = self.client.game.myself.handBoard
            if not handBoard:
                # we are in the progress of logging out
                return
            hbLeftTop = view.mapFromScene(handBoard.mapToScene(handBoard.rect().topLeft()))
            hbRightBottom = view.mapFromScene(handBoard.mapToScene(handBoard.rect().bottomRight()))
            width = hbRightBottom.x() - hbLeftTop.x()
            height = self.btnHeight
            geometry.setY(cwi.height() - height)
            geometry.setX(hbLeftTop.x())
        for idx, btn in enumerate(self.buttons + [self.progressBar]):
            self.layout.addWidget(btn, idx+1 if vertical else 0, idx+1 if not vertical else 0)
        idx = len(self.buttons) + 2
        spacer = QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addItem(spacer, idx if vertical else 0, idx if not vertical else 0)

        geometry.setWidth(width)
        geometry.setHeight(height)
        self.setGeometry(geometry)

    def showEvent(self, dummyEvent):
        """try to place the dialog such that it does not cover interesting information"""
        self.placeInField()

    def timeout(self):
        """the progressboard wants an update"""
        pBar = self.progressBar
        if isAlive(pBar):
            pBar.setValue(pBar.value()+1)
            pBar.setVisible(True)
            if pBar.value() == pBar.maximum():
                # timeout: we always return the original default answer, not the one with focus
                self.selectButton()
                pBar.setVisible(False)

    def selectButton(self, button=None):
        """select default answer. button may also be of type Message."""
        self.timer.stop()
        if self.isVisible():
            self.answered = True
            if button is None:
                button = self.focusWidget()
            if isinstance(button, Message):
                assert any(x.message == button for x in self.buttons)
                answer = button
            else:
                answer = button.message
            if not self.client.sayable[answer]:
                Sorry(m18n('You cannot say %1', answer.i18nName))
                return
            self.deferred.callback(answer)
        self.hide()
        Internal.field.clientDialog = None

    def selectedAnswer(self, dummyChecked):
        """the user clicked one of the buttons"""
        game = self.client.game
        if game and not game.autoPlay:
            self.selectButton(self.sender())

class HumanClient(Client):
    """a human client"""
    def __init__(self):
        aiClass = self.__findAI([intelligence, altint], Options.AI)
        if not aiClass:
            raise Exception('intelligence %s is undefined' % Options.AI)
        Client.__init__(self, intelligence=aiClass)
        self.tableList = None
        self.table = None
        self.username = None
        self.ruleset = None
        self.connection = Connection(self)
        self.connection.login().addCallbacks(self.loggedIn, self.loginFailed)

    def loggedIn(self, ruleset):
        """callback after the server answered our login request"""
        if not self.connection.perspective:
            self.connection = None
            return
        self.ruleset = ruleset
        self.username = self.connection.username
        self.tableList = TableList(self)
        voiceId = None
        if Preferences.uploadVoice:
            voice = Voice.locate(self.username)
            if voice:
                voiceId = voice.md5sum
            if Debug.sound and voiceId:
                logDebug('%s sends own voice %s to server' % (self.username, voiceId))
        maxGameId = Query('select max(id) from game').records[0][0]
        maxGameId = int(maxGameId) if maxGameId else 0
        self.callServer('setClientProperties',
            Internal.dbIdent,
            voiceId, maxGameId, Internal.version). \
                addErrback(self.__versionError). \
                addCallback(self.callServer, 'sendTables'). \
                addCallback(self.tableList.gotTables)

    @staticmethod
    def loginFailed(dummy):
        """as the name says"""
        Internal.field.startingGame = False

    @staticmethod
    def __findAI(modules, aiName):
        """list of all alternative AIs defined in altint.py"""
        for modul in modules:
            for key, value in modul.__dict__.items():
                if key == 'AI' + aiName:
                    return value

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
        return self.connection.useSocket

    def __updateTableList(self):
        """if it exists"""
        if self.tableList:
            self.tableList.loadTables(self.tables)

    def remote_tableRemoved(self, tableid, message, *args):
        """update table list"""
        Client.remote_tableRemoved(self, tableid, message, *args)
        self.__updateTableList()
        if message:
            # do not tell me that I just logged out
            if not self.username in args or not message.endswith('has logged out'):
                logWarning(m18n(message, *args))

    def remote_newTables(self, tables):
        """update table list"""
        Client.remote_newTables(self, tables)
        self.__updateTableList()

    def remote_tableChanged(self, table):
        """update table list"""
        newClientTable = ClientTable(self, *table) # pylint: disable=W0142
        oldTable = self._tableById(newClientTable.tableid)
        if oldTable:
            # this happens if a game has more than one human player and
            # one of them answers "no" to "are you ready to begin". In
            # that case, the other clients need this code. Otherwise they
            # would start the game anyway, and the user would have to abort it
            if newClientTable.isOnline(self.username):
                for name in newClientTable.playerNames:
                    if name != self.username:
                        if oldTable.isOnline(name) and not newClientTable.isOnline(name):
                            Sorry(m18n('Player %1 has left the table', name)).addCallback(self.logout)
            self.tables.remove(oldTable)
            self.tables.append(newClientTable)
            self.__updateTableList()

    def remote_chat(self, data):
        """others chat to me"""
        chatLine = ChatMessage(data)
        if Debug.chat:
            logDebug('got chatLine: %s' % chatLine)
        if self.table:
            table = self.table
        else:
            table = None
            for _ in self.tableList.view.model().tables:
                if _.tableid == chatLine.tableid:
                    table = _
            if table is None:
                # TODO: chatting on a table with suspended game does
                # not yet work because such a table has no tableid. Maybe it should.
                return
        if not chatLine.isStatusMessage and not table.chatWindow:
            ChatWindow(table)
        if table.chatWindow:
            table.chatWindow.receiveLine(chatLine)

    def readyForGameStart(self, tableid, gameid, wantedGame, playerNames, shouldSave=True):
        """playerNames are in wind order ESWN"""
        def answered(result):
            """callback, called after the client player said yes or no"""
            if self.connection.perspective and result:
                # still connected and yes, we are
                return Client.readyForGameStart(self, tableid, gameid, wantedGame, playerNames, shouldSave)
            else:
                return Message.NO
        if sum(not x[1].startswith('Robot ') for x in playerNames) == 1:
            # we play against 3 robots and we already told the server to start: no need to ask again
            return Client.readyForGameStart(self, tableid, gameid, wantedGame, playerNames, shouldSave)
        msg = m18n("The game can begin. Are you ready to play now?\n" \
            "If you answer with NO, you will be removed from table %1.", tableid)
        return QuestionYesNo(msg, caption=self.username).addCallback(answered)

    def readyForHandStart(self, playerNames, rotateWinds):
        """playerNames are in wind order ESWN. Never called for first hand."""
        def answered(dummy=None):
            """called after the client player said yes, I am ready"""
            if self.connection.perspective:
                return Client.readyForHandStart(self, playerNames, rotateWinds)
        if not self.connection.perspective:
            # disconnected meanwhile
            return
        if Internal.field:
            # update the balances in the status bar:
            Internal.field.updateGUI()
        assert not self.game.isFirstHand()
        return Information(m18n("Ready for next hand?"), modal=False).addCallback(answered)

    def ask(self, move, answers):
        """server sends move. We ask the user. answers is a list with possible answers,
        the default answer being the first in the list."""
        if not Internal.field:
            return Client.ask(self, move, answers)
        self._computeSayable(move, answers)
        deferred = Deferred()
        deferred.addCallback(self.__askAnswered)
        deferred.addErrback(self.answerError, move, answers)
        iAmActive = self.game.myself == self.game.activePlayer
        self.game.myself.handBoard.setEnabled(iAmActive)
        field = Internal.field
        oldDialog = field.clientDialog
        if oldDialog and not oldDialog.answered:
            raise Exception('old dialog %s:%s is unanswered, new Dialog: %s/%s' % (
                str(oldDialog.move),
                str([x.name for x in oldDialog.buttons]),
                str(move), str(answers)))
        if not oldDialog or not oldDialog.isVisible():
            # always build a new dialog because if we change its layout before
            # reshowing it, sometimes the old buttons are still visible in which
            # case the next dialog will appear at a lower position than it should
            field.clientDialog = ClientDialog(self, field.centralWidget())
        assert field.clientDialog.client is self
        field.clientDialog.askHuman(move, answers, deferred)
        return deferred

    def selectChow(self, chows):
        """which possible chow do we want to expose?
        Since we might return a Deferred to be sent to the server,
        which contains Message.Chow plus selected Chow, we should
        return the same tuple here"""
        if self.game.autoPlay:
            return Message.Chow, self.intelligence.selectChow(chows)
        if len(chows) == 1:
            return Message.Chow, chows[0]
        if Preferences.propose:
            propose = self.intelligence.selectChow(chows)
        else:
            propose = None
        deferred = Deferred()
        selDlg = SelectChow(chows, propose, deferred)
        assert selDlg.exec_()
        return deferred

    def selectKong(self, kongs):
        """which possible kong do we want to declare?"""
        if self.game.autoPlay:
            return Message.Kong, self.intelligence.selectKong(kongs)
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
            # including us that it has been discarded. Only then we will remove it.
            myself.handBoard.setEnabled(False)
            return answer, myself.handBoard.focusTile.element
        args = self.sayable[answer]
        assert args
        if answer == Message.Chow:
            return self.selectChow(args)
        if answer == Message.Kong:
            return self.selectKong(args)
        self.game.hidePopups()
        if args is True or args == []:
            # this does not specify any tiles, the server does not need this. Robot players
            # also return None in this case.
            return answer
        else:
            return answer, args

    def answerError(self, answer, move, answers):
        """an error happened while determining the answer to server"""
        logException('%s %s %s %s' % (self.game.myself.name if self.game else 'NOGAME', answer, move, answers))

    def remote_abort(self, tableid, message, *args):
        """the server aborted this game"""
        if self.table and self.table.tableid == tableid:
            # translate Robot to Roboter:
            if self.game:
                args = self.game.players.translatePlayerNames(args)
            logWarning(m18n(message, *args))
            if self.game:
                self.game.close()
                if self.game.autoPlay:
                    if Internal.field:
                        Internal.field.close()

    def remote_gameOver(self, tableid, message, *args):
        """the game is over"""
        def yes(dummy):
            """now that the user clicked the 'game over' prompt away, clean up"""
            if self.game:
                self.game.rotateWinds()
                if Options.csv:
                    gameWinner = max(self.game.players, key=lambda x: x.balance)
                    writer = csv.writer(open(Options.csv,'a'), delimiter=';')
                    if Debug.process:
                        self.game.csvTags.append('MEM:%s' % resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
                    row = [Options.AI, str(self.game.seed), ','.join(self.game.csvTags)]
                    for player in sorted(self.game.players, key=lambda x: x.name):
                        row.append(player.name.encode('utf-8'))
                        row.append(player.balance)
                        row.append(player.wonCount)
                        row.append(1 if player == gameWinner else 0)
                    writer.writerow(row)
                    del writer
                if self.game.autoPlay and Internal.field:
                    Internal.field.close()
                else:
                    self.game.close().addCallback(Client.quitProgram)
        assert self.table and self.table.tableid == tableid
        if Internal.field:
            # update the balances in the status bar:
            Internal.field.updateGUI()
        logInfo(m18n(message, *args), showDialog=True).addCallback(yes)

    def remote_serverDisconnects(self, dummyResult=None):
        """we logged out or or lost connection to the server.
        Remove visual traces depending on that connection."""
        game = self.game
        self.game = None # avoid races: messages might still arrive
        if self.tableList:
            model = self.tableList.view.model()
            if model:
                for table in model.tables:
                    if table.chatWindow:
                        table.chatWindow.hide()
                        table.chatWindow = None
            self.tableList.hide()
            self.tableList = None
        if self in self.clients:
            self.clients.remove(self)
        field = Internal.field
        if field and field.game == game:
            field.hideGame()

    def serverDisconnected(self, remoteReference):
        """perspective calls us back"""
        if Debug.traffic:
            logDebug('perspective notifies disconnect: %s' % remoteReference)
        self.connection = None

    @staticmethod
    def __versionError(err):
        """log the twisted error"""
        logWarning(err.getErrorMessage())
        Internal.field.abortGame()
        return err

    def logout(self, dummyResult=None):
        """clean visual traces and logout from server"""
        def loggedout(result):
            """TODO: do we need this?"""
            self.connection.connector.disconnect()
            self.connection = None
            return result
        return self.callServer('logout').addCallback(loggedout)

    def callServer(self, *args):
        """if we are online, call server"""
        if self.connection:
            if args[0] is None:
                args = args[1:]
            try:
                if Debug.traffic:
                    if self.game:
                        self.game.debug('callServer(%s)' % repr(args))
                    else:
                        logDebug('callServer(%s)' % repr(args))
                def callServerError(result):
                    """if serverDisconnected has been called meanwhile, just ignore msg about
                    connection lost in a non-clean fashion"""
                    if self.connection:
                        return result
                return self.connection.perspective.callRemote(*args).addErrback(callServerError)
            except pb.DeadReferenceError:
                logWarning(m18n('The connection to the server %1 broke, please try again later.',
                                  self.connection.url))
                self.remote_serverDisconnects()
                return succeed(None)
        else:
            return succeed(None)

    def sendChat(self, chatLine):
        """send chat message to server"""
        return self.callServer('chat', chatLine.serialize())
