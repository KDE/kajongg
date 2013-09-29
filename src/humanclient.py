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

import csv, resource, random

from twisted.spread import pb
from twisted.python.failure import Failure
from twisted.internet.defer import Deferred, succeed, DeferredList
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
from common import Options, SingleshotOptions, Internal, Preferences, Debug, isAlive
from query import Query
from board import Board
from client import Client, ClientTable
from meld import Meld
from tables import TableList, SelectRuleset
from sound import Voice
import intelligence
import altint
from login import Connection
from rule import Ruleset

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
        if not self.client.game:
            return
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
        Internal.field.clientDialog = None
        self.deferred.callback(answer)

    def selectedAnswer(self, dummyChecked):
        """the user clicked one of the buttons"""
        game = self.client.game
        if game and not game.autoPlay:
            self.selectButton(self.sender())

class HumanClient(Client):
    """a human client"""
    # pylint: disable=R0904
    humanClients = []
    def __init__(self):
        aiClass = self.__findAI([intelligence, altint], Options.AI)
        if not aiClass:
            raise Exception('intelligence %s is undefined' % Options.AI)
        Client.__init__(self, intelligence=aiClass)
        HumanClient.humanClients.append(self)
        self.table = None
        self.ruleset = None
        self.beginQuestion = None
        self.tableList = TableList(self)
        Connection(self).login().addCallbacks(self.__loggedIn, self.__loginFailed)

    @staticmethod
    def shutdownHumanClients(exception=None):
        """close connections to servers except maybe one"""
        clients = HumanClient.humanClients
        def done():
            """return True if clients is cleaned"""
            return len(clients) == 0 or (exception and clients == [exception])
        def disconnectedClient(dummyResult, client):
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
                deferreds.append(client.logout().addCallback(disconnectedClient, client))
        return DeferredList(deferreds)

    def __loggedIn(self, connection):
        """callback after the server answered our login request"""
        self.connection = connection
        self.ruleset = connection.ruleset
        self.name = connection.username
        self.tableList.show()
        voiceId = None
        if Preferences.uploadVoice:
            voice = Voice.locate(self.name)
            if voice:
                voiceId = voice.md5sum
            if Debug.sound and voiceId:
                logDebug('%s sends own voice %s to server' % (self.name, voiceId))
        maxGameId = Query('select max(id) from game').records[0][0]
        maxGameId = int(maxGameId) if maxGameId else 0
        self.callServer('setClientProperties',
            Internal.dbIdent,
            voiceId, maxGameId, Internal.version).addCallbacks(self.__initTableList, self.__versionError)

    def __initTableList(self, dummy):
        """first load of the list. Process options like --demo, --table, --join"""
        self.showTableList()
        if SingleshotOptions.table:
            Internal.autoPlay = False
            self.__requestNewTableFromServer(SingleshotOptions.table).addCallback(
                self.__showTables).addErrback(self.tableError)
            if Debug.table:
                logDebug('%s: --table lets us open an new table %d' % (self.name, SingleshotOptions.table))
            SingleshotOptions.table = False
        elif SingleshotOptions.join:
            Internal.autoPlay = False
            self.callServer('joinTable', SingleshotOptions.join).addCallback(
                self.__showTables).addErrback(self.tableError)
            if Debug.table:
                logDebug('%s: --join lets us join table %s' % (self.name, self._tableById(SingleshotOptions.join)))
            SingleshotOptions.join = False
        elif not self.game and (Internal.autoPlay or (not self.tables and self.hasLocalServer())):
            self.__requestNewTableFromServer().addCallback(self.__newLocalTable).addErrback(self.tableError)
        else:
            self.__showTables()

    @staticmethod
    def __loginFailed(dummy):
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
        return self.connection and self.connection.useSocket

    def __updateTableList(self):
        """if it exists"""
        if self.tableList:
            self.tableList.loadTables(self.tables)

    def __showTables(self, dummy=None):
        """load and show tables. We may be used as a callback. In that case,
        clientTables is the id of a new table - which we do not need here"""
        self.tableList.loadTables(self.tables)
        self.tableList.show()

    def showTableList(self, dummy=None):
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
            if not self.name in args or not message.endswith('has logged out'):
                logWarning(m18n(message, *args))

    def __receiveTables(self, tables):
        """now we already know all rulesets for those tables"""
        Client.remote_newTables(self, tables)
        if not Internal.autoPlay:
            if self.hasLocalServer():
                # when playing a local game, only show pending tables with
                # previously selected ruleset
                self.tables = list(x for x in self.tables if x.ruleset == self.ruleset)
        if len(self.tables):
            self.__updateTableList()

    def remote_newTables(self, tables):
        """update table list"""
        assert len(tables)
        def gotRulesets(result):
            """the server sent us the wanted ruleset definitions"""
            for ruleset in result:
                Ruleset.cached(ruleset).save(copy=True) # make it known to the cache and save in db
            return tables
        rulesetHashes = set(x[1] for x in tables)
        needRulesets = list(x for x in rulesetHashes if not Ruleset.hashIsKnown(x))
        if needRulesets:
            self.callServer('needRulesets', needRulesets).addCallback(gotRulesets).addCallback(self.__receiveTables)
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
                        def sorried(dummy):
                            """user ack"""
                            game = self.game
                            if game:
                                self.game = None
                                return game.close()
                        if self.beginQuestion:
                            self.beginQuestion.cancel()
                        Sorry(m18n('Player %1 has left the table', name)).addCallback(
                            sorried).addCallback(self.showTableList)
                        break
        self.__updateTableList()

    def remote_chat(self, data):
        """others chat to me"""
        chatLine = ChatMessage(data)
        if Debug.chat:
            logDebug('got chatLine: %s' % chatLine)
        table = self._tableById(chatLine.tableid)
        if not chatLine.isStatusMessage and not table.chatWindow:
            ChatWindow(table)
        if table.chatWindow:
            table.chatWindow.receiveLine(chatLine)

    def readyForGameStart(self, tableid, gameid, wantedGame, playerNames, shouldSave=True):
        """playerNames are in wind order ESWN"""
        def answered(result):
            """callback, called after the client player said yes or no"""
            self.beginQuestion = None
            if self.connection and result:
                # still connected and yes, we are
                Client.readyForGameStart(self, tableid, gameid, wantedGame, playerNames, shouldSave)
                return Message.OK
            else:
                return Message.NoGameStart
        def cancelled(dummy):
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
            # we play against 3 robots and we already told the server to start: no need to ask again
            return Client.readyForGameStart(self, tableid, gameid, wantedGame, playerNames, shouldSave)
        assert not self.table
        assert self.tables
        self.table = self._tableById(tableid)
        if not self.table:
            raise pb.Error('client.readyForGameStart: tableid %d unknown' % tableid)
        msg = m18n("The game on table <numid>%1</numid> can begin. Are you ready to play now?", tableid)
        self.beginQuestion = QuestionYesNo(msg, modal=False, caption=self.name).addCallback(
            answered).addErrback(cancelled)
        return self.beginQuestion

    def readyForHandStart(self, playerNames, rotateWinds):
        """playerNames are in wind order ESWN. Never called for first hand."""
        def answered(dummy=None):
            """called after the client player said yes, I am ready"""
            if self.connection:
                return Client.readyForHandStart(self, playerNames, rotateWinds)
        if not self.connection:
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
        deferred.addErrback(self.__answerError, move, answers)
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

    def __selectChow(self, chows):
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

    def __selectKong(self, kongs):
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
            return self.__selectChow(args)
        if answer == Message.Kong:
            return self.__selectKong(args)
        self.game.hidePopups()
        if args is True or args == []:
            # this does not specify any tiles, the server does not need this. Robot players
            # also return None in this case.
            return answer
        else:
            return answer, args

    def __answerError(self, answer, move, answers):
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

    def remote_serverDisconnects(self, result=None):
        """we logged out or or lost connection to the server.
        Remove visual traces depending on that connection."""
        if Debug.connections and result:
            logDebug('server %s disconnects: %s' % (self.connection.url, result))
        self.connection = None
        game = self.game
        self.game = None # avoid races: messages might still arrive
        if self.tableList:
            self.tableList.hide()
            self.tableList = None
        if self in HumanClient.humanClients:
            HumanClient.humanClients.remove(self)
        if self.beginQuestion:
            self.beginQuestion.cancel()
        field = Internal.field
        if field and game and field.game == game:
            game.close() # TODO: maybe issue a Sorry first?

    def serverDisconnected(self, dummyReference):
        """perspective calls us back"""
        if self.connection and (Debug.traffic or Debug.connections):
            logDebug('perspective notifies disconnect: %s' % self.connection.url)
        self.remote_serverDisconnects()

    @staticmethod
    def __versionError(err):
        """log the twisted error"""
        logWarning(err.getErrorMessage())
        Internal.field.abortGame()
        return err

    @staticmethod
    def __wantedGame():
        """find out which game we want to start on the table"""
        result = SingleshotOptions.game
        if not result or result == '0':
            result = str(int(random.random() * 10**9))
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

    def logout(self, dummyResult=None):
        """clean visual traces and logout from server"""
        def loggedout(result, connection):
            """TODO: do we need this?"""
            connection.connector.disconnect()
            return result
        if self.connection:
            conn = self.connection
            self.connection = None
            return self.callServer('logout').addCallback(loggedout, conn)
        else:
            return succeed(None)

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
        return self.callServer('chat', chatLine.asList())
