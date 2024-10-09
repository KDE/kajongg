# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

import random
from typing import List, Optional, TYPE_CHECKING, Type, Any, Tuple, Union, cast

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
from log import i18n, logWarning, logException, logDebug, logError
from message import Message, ChatMessage
from chat import ChatWindow
from common import Options, SingleshotOptions, Internal, Debug, isAlive
from query import Query
from board import Board
from client import Client, ClientTable
from tables import TableList, SelectRuleset
from sound import Voice
from login import Connection
from rule import Ruleset
from player import PlayingPlayer
from game import PlayingGame
from visible import VisiblePlayingGame



if TYPE_CHECKING:
    from qt import QEvent, QKeyEvent
    from deferredutil import Request
    from move import Move
    from tile import Tile, Meld, MeldList
    from uitile import UITile
    from message import ClientMessage, ServerMessage
    from scene import PlayingScene
    from wind import Wind


class SelectChow(KDialogIgnoringEscape):

    """asks which of the possible chows is wanted"""

    def __init__(self, chows:'MeldList', propose:Optional['Meld'], deferred:Deferred) ->None:
        KDialogIgnoringEscape.__init__(self)
        decorateWindow(self)
        self.setWindowFlags(cast(Qt.WindowType, Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint))
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
            button = QRadioButton('{}-{}-{}'.format(*(x.value for x in chow))) # pylint:disable=consider-using-f-string
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

    def toggled(self, unusedChecked:bool) ->None:
        """a radiobutton has been toggled"""
        button = cast(QRadioButton, self.sender())
        if button.isChecked():
            self.selectedChow = self.chows[self.buttons.index(button)]
            self.accept()
            self.deferred.callback((Message.Chow, self.selectedChow))


class SelectKong(KDialogIgnoringEscape):

    """asks which of the possible kongs is wanted"""

    def __init__(self, kongs:'MeldList', deferred:Deferred) ->None:
        KDialogIgnoringEscape.__init__(self)
        decorateWindow(self)
        self.setButtons(KDialog.NoButton)
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

    def toggled(self, unusedChecked:bool) ->None:
        """a radiobutton has been toggled"""
        button = cast(QRadioButton, self.sender())
        if button.isChecked():
            self.selectedKong = self.kongs[self.buttons.index(button)]
            self.accept()
            self.deferred.callback((Message.Kong, self.selectedKong))


class DlgButton(QPushButton):

    """special button for ClientDialog"""

    def __init__(self, message:'ClientMessage', parent:'ClientDialog') ->None:
        QPushButton.__init__(self, parent)
        self.message = message
        self.client:'HumanClient' = parent.client
        self.setMinimumHeight(25)
        self.setText(message.buttonCaption())  # type: ignore[call-arg]

    def setMeaning(self, uiTile:'UITile') ->None:
        """give me caption, shortcut, tooltip, icon"""
        txt, warn, _ = self.message.toolTip(self, uiTile.tile)
        if not txt:
            txt = self.message.i18nName  # .replace(i18nShortcut, '&'+i18nShortcut, 1)
        self.setToolTip(txt)
        self.setWarning(warn)

    def keyPressEvent(self, event:Optional['QKeyEvent']) ->None:
        """forward horizintal arrows to the hand board"""
        if event:
            key = Board.mapChar2Arrow(event)
            if key in [Qt.Key.Key_Left, Qt.Key.Key_Right]:
                game = self.client.game
                if game and game.activePlayer == game.myself:
                    if game.myself.handBoard:
                        game.myself.handBoard.keyPressEvent(event)
                    self.setFocus()
                    return
            QPushButton.keyPressEvent(self, event)

    def setWarning(self, warn:bool) ->None:
        """if warn, show a warning icon on the button"""
        if warn:
            self.setIcon(KIcon('dialog-warning'))
        else:
            self.setIcon(KIcon())


class ClientDialog(QDialog):  # pylint:disable=too-many-instance-attributes

    """a simple popup dialog for asking the player what he wants to do"""

    def __init__(self, client:'HumanClient', parent:Optional[QWidget]=None) ->None:
        QDialog.__init__(self, parent)
        decorateWindow(self, i18n('Choose'))
        self.tables:List[ClientTable]
        self.setObjectName('ClientDialog')
        self.client:'HumanClient' = client
        self.gridLayout = QGridLayout(self)
        self.progressBar = QProgressBar()
        self.progressBar.setMinimumHeight(25)
        self.timer = QTimer()
        assert client.game
        if not client.game.autoPlay:
            self.timer.timeout.connect(self.timeout)
        self.deferred:Optional[Deferred] = None
        self.buttons:List[DlgButton] = []
        self.setWindowFlags(cast(Qt.WindowType, Qt.WindowType.SubWindow | Qt.WindowType.WindowStaysOnTopHint))
        self.setModal(False)
        self.btnHeight = 0
        self.answered = False
        self.move:'Move'  # type:ignore[assignment]
        self.sorry:Optional[Sorry] = None

    def keyPressEvent(self, event:Optional['QKeyEvent']) ->None:
        """ESC selects default answer"""
        if not event or not self.client.game or self.client.game.autoPlay:
            return
        if event.key() in [Qt.Key.Key_Escape, Qt.Key.Key_Space]:
            self.selectButton()
            event.accept()
        else:
            for btn in self.buttons:
                if str(event.text()).upper() == btn.message.shortcut:
                    self.selectButton(btn.message)
                    event.accept()
                    return
            QDialog.keyPressEvent(self, event)

    def __declareButton(self, message:'ClientMessage') ->None:
        """define a button"""
        if not self.client.game:
            return
        maySay = cast(PlayingPlayer, self.client.game.myself).sayable[message]
        assert Internal.Preferences
        if Internal.Preferences.showOnlyPossibleActions and not maySay:
            return
        btn = DlgButton(message, self)
        btn.setAutoDefault(True)
        btn.clicked.connect(self.selectedAnswer)
        self.buttons.append(btn)

    def focusTileChanged(self) ->None:
        """update icon and tooltip for the discard button"""
        if not self.client.game:
            return
        assert self.client.game.myself  # FIXME: needed?
        assert self.client.game.myself.handBoard
        newFocusTile = self.client.game.myself.handBoard.focusTile
        if newFocusTile:
            for button in self.buttons:
                button.setMeaning(newFocusTile)
        for uiTile in self.client.game.myself.handBoard.lowerHalfTiles():
            txt = []
            for button in self.buttons:
                _, _, tileTxt = button.message.toolTip(button, uiTile.tile)
                if tileTxt:
                    txt.append(tileTxt)
            uiTile.setToolTip(f'<font color=yellow>{"<br><br>".join(txt)}')
        if self.client.game.activePlayer == self.client.game.myself:
            if Internal.scene:
                Internal.scene.handSelectorChanged(
                    self.client.game.myself.handBoard)

    def checkTiles(self) ->None:
        """does the logical state match the displayed tiles?"""
        if not self.client.game:
            return
        for player in self.client.game.players:
            player.handBoard.checkTiles()

    def messages(self) ->List[Message]:
        """a list of all messages returned by the declared buttons"""
        return [x.message for x in self.buttons]

    def proposeAction(self) ->DlgButton:
        """either intelligently or first button by default. May also
        focus a proposed tile depending on the action."""
        result = self.buttons[0]
        game = self.client.game
        assert game
        assert game.myself
        assert game.myself.handBoard
        assert Internal.Preferences
        if game.autoPlay or Internal.Preferences.propose:
            mess = self.messages()
            answer, parameter = game.myself.intelligence.selectAnswer(mess)
            result = [x for x in self.buttons if x.message == answer][0]
            result.setFocus()
            if answer in [Message.Discard, Message.OriginalCall]:
                for uiTile in game.myself.handBoard.uiTiles:
                    if uiTile.tile is parameter:
                        game.myself.handBoard.focusTile = uiTile
        return result

    def askHuman(self, move:'Move', answers:List['ClientMessage'], deferred:Deferred) ->None:
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
        assert game
        myTurn = game.activePlayer == game.myself
        prefButton = self.proposeAction()
        if game.autoPlay:
            self.selectButton(prefButton.message)
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

    def placeInField(self) ->None:
        """place the dialog at bottom or to the right depending on space."""
        if not Internal.scene:
            logError('placeInField: have no Internal.scene')
            return
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
            geometry.setX(int(cwi.width() - width))
            geometry.setY(int(min(cwi.height() // 3, cwi.height() - height)))
        else:
            assert self.client.game
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
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding)
        self.gridLayout.addItem(
            spacer,
            idx if vertical else 0,
            idx if not vertical else 0)

        geometry.setWidth(int(width))
        geometry.setHeight(int(height))
        self.setGeometry(geometry)

    def showEvent(self, unusedEvent:Optional['QEvent']) ->None:
        """try to place the dialog such that it does not cover interesting information"""
        self.placeInField()

    def timeout(self) ->None:
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

    def selectButton(self, message:Optional[Message]=None) ->None:
        """select default answer. button may also be of type Message."""
        if self.answered:
            # sometimes we get this event twice
            return
        if message is None:
            message = cast(DlgButton, self.focusWidget()).message
        assert any(x.message == message for x in self.buttons)
        assert self.client.game
        if not cast(PlayingPlayer, self.client.game.myself).sayable[message]:
            self.proposeAction().setFocus() # go back to default action
            self.sorry = Sorry(i18n('You cannot say %1', message.i18nName))
            return
        self.timer.stop()
        self.answered = True
        if self.sorry:
            self.sorry.cancel()
        self.sorry = None
        if Internal.scene:
            Internal.scene.clientDialog = None
        assert self.deferred
        self.deferred.callback(message)

    def selectedAnswer(self, unusedChecked:bool) ->None:
        """the user clicked one of the buttons"""
        game = self.client.game
        if game and not game.autoPlay:
            self.selectButton(cast(DlgButton, self.sender()).message)


class HumanClient(Client):

    """a human client"""
    humanClients : List['HumanClient'] = []

    def __init__(self) ->None:
        Client.__init__(self)
        HumanClient.humanClients.append(self)
        self.table = None
        self.ruleset:Ruleset
        self.connection:Optional[Connection]
        self.beginQuestion:Optional[Deferred] = None
        self.tableList:Optional[TableList] = TableList(self)
        Connection(self).login().addCallbacks(
            self.__loggedIn,
            self.__loginFailed)

    @staticmethod
    def shutdownHumanClients(exception:Optional[Exception]=None) ->Any: # Union[Deferred, DeferredList]:
        """close connections to servers except maybe one"""
        clients = HumanClient.humanClients

        def done() ->bool:
            """return True if clients is cleaned"""
            return len(clients) == 0 or (exception is not None and clients == [exception])

        def disconnectedClient(unusedResult:Deferred, client:'HumanClient') ->None:
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
                        client).addErrback(logException))
        return DeferredList(deferreds)

    def __loggedIn(self, connection:Connection) ->None:
        """callback after the server answered our login request"""
        self.connection = connection
        self.ruleset = connection.ruleset
        self.name = connection.username
        if self.tableList:
            self.tableList.show()
        voiceId = None
        assert Internal.Preferences
        if Internal.Preferences.uploadVoice:
            voice = Voice.locate(self.name)
            if voice:
                voiceId = voice.md5sum
            if Debug.sound and voiceId:
                logDebug(
                    f'{self.name} sends own voice {voiceId} to server')
        maxGameId = Query('select max(id) from game').records[0][0]
        maxGameId = int(maxGameId) if maxGameId else 0
        self.callServer('setClientProperties',
                        Internal.db.identifier,
                        voiceId, maxGameId,
                        Internal.defaultPort).addCallbacks(self.__initTableList, self.__versionError)

    def __initTableList(self, unused:str) ->None:
        """first load of the list. Process options like --demo, --table, --join"""
        self.showTableList()
        if SingleshotOptions.table:
            Internal.autoPlay = False
            self.__requestNewTableFromServer(SingleshotOptions.table).addCallback(
                self.__showTables).addErrback(self.tableError)
            if Debug.table:
                logDebug(
                    f'{self.name}: --table lets us open a new table')
            SingleshotOptions.table = False
        elif SingleshotOptions.join:
            Internal.autoPlay = False
            self.callServer('joinTable', SingleshotOptions.join).addCallback(
                self.__showTables).addErrback(self.tableError)
            if Debug.table:
                logDebug(
                    f'{self.name}: --join lets us join table {self._tableById(SingleshotOptions.join)}')
            SingleshotOptions.join = False
        elif not self.game and (Internal.autoPlay or (not self.tables and self.hasLocalServer())):
            self.__requestNewTableFromServer().addCallback(
                self.__newLocalTable).addErrback(self.tableError)
        else:
            self.__showTables()

    @staticmethod
    def __loginFailed(unused:List[Deferred]) ->None:
        """as the name says"""
        if Internal.scene:
            cast('PlayingScene', Internal.scene).startingGame = False

    def isRobotClient(self) ->bool:
        """avoid using isinstance, it would import too much for kajonggserver"""
        return False

    @staticmethod
    def isHumanClient() ->bool:
        """avoid using isinstance, it would import too much for kajonggserver"""
        return True

    def isServerClient(self) ->bool:
        """avoid using isinstance, it would import too much for kajonggserver"""
        return False

    def hasLocalServer(self) ->bool:
        """True if we are talking to a Local Game Server"""
        return self.connection is not None and self.connection.url.isLocalHost

    def __updateTableList(self) ->None:
        """if it exists"""
        if self.tableList:
            self.tableList.loadTables(self.tables)

    def __showTables(self, unused:Optional[str]=None) ->None:
        """load and show tables. We may be used as a callback. In that case,
        clientTables is the id of a new table - which we do not need here"""
        if self.tableList:
            self.tableList.loadTables(self.tables)
            self.tableList.show()

    def showTableList(self, unused:Optional[str]=None) ->None:
        """allocate it if needed"""
        if not self.tableList:
            self.tableList = TableList(self)
        self.tableList.loadTables(self.tables)
        self.tableList.activateWindow()

    def remote_tableRemoved(self, tableid:int, message:str, *args:Any) ->None:
        """update table list"""
        Client.remote_tableRemoved(self, tableid, message, *args)
        self.__updateTableList()
        if message:
            if self.name not in args or not message.endswith('has logged out'):
                logWarning(i18n(message, *args))

    def __receiveTables(self, tables:List[List[Any]]) ->None:
        """now we already know all rulesets for those tables"""
        Client.remote_newTables(self, tables)
        if not Internal.autoPlay:
            if self.hasLocalServer():
                # when playing a local game, only show pending tables with
                # previously selected ruleset
                self.tables = [x for x in self.tables if x.ruleset == self.ruleset]
        if self.tables:
            self.__updateTableList()

    def remote_newTables(self, tables:List[List[Any]]) ->None:
        """update table list"""
        assert tables

        def gotRulesets(result:List[Union[int, str]]) ->List[List[Any]]:
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
                    gotRulesets).addErrback(logException).addCallback(
                        self.__receiveTables).addErrback(logException)
        else:
            self.__receiveTables(tables)

    @staticmethod
    def remote_needRuleset(ruleset:str) ->List[List[Union[str, int, float]]]:
        """server only knows hash, needs full definition"""
        result = Ruleset.cached(ruleset)
        assert result and result.hash == ruleset
        return result.toList()

    def tableChanged(self, table:ClientTable) ->Tuple[Optional[ClientTable], ClientTable]:
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
                        def sorried(unused:List['Request']) ->Optional[Deferred]:
                            """user ack"""
                            game = self.game
                            if game:
                                self.game = None
                                return game.close()
                            return None
                        if self.beginQuestion:
                            self.beginQuestion.cancel()
                        Sorry(i18n('Player %1 has left the table', name)).addCallback(
                            sorried).addErrback(logException).addCallback(self.showTableList).addErrback(logException)
                        break
        self.__updateTableList()
        return oldTable, newTable

    def remote_chat(self, data):
        """others chat to me"""
        chatLine = ChatMessage(data)
        if Debug.chat:
            logDebug(f'got chatLine: {chatLine}')
        table = self._tableById(chatLine.tableid)
        if not chatLine.isStatusMessage and not table.chatWindow:
            ChatWindow(table=table)
        if table.chatWindow:
            table.chatWindow.receiveLine(chatLine)

    def readyForGameStart(
            self, tableid:int, gameid:int, wantedGame:str, playerNames:List[Tuple['Wind', str]], shouldSave:bool=True,
            gameClass:Optional[Type]=None) ->Deferred:
        """playerNames are in wind order ESWN"""
        if gameClass is None:
            if Options.gui:
                gameClass = VisiblePlayingGame
            else:
                gameClass = PlayingGame

        def clientReady() ->Deferred:
            """macro"""
            return Client.readyForGameStart(
                self, tableid, gameid, wantedGame, playerNames,
                shouldSave, gameClass)

        def answered(result:Deferred) ->Union[Message, Deferred]:
            """callback, called after the client player said yes or no"""
            self.beginQuestion = None
            if self.connection and result:
                # still connected and yes, we are
                return clientReady()
            return Message.NoGameStart

        def cancelled(unused:'Request') ->'ServerMessage':
            """the user does not want to start now. Back to table list"""
            if Debug.table:
                logDebug(f'{self.name}: Readyforgamestart returns Message.NoGameStart '
                         f'for table {self._tableById(tableid)}')
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
                f'client.readyForGameStart: tableid {int(tableid)} unknown')
        msg = i18n(
            "The game on table <numid>%1</numid> can begin. Are you ready to play now?",
            tableid)
        self.beginQuestion = QuestionYesNo(msg, modal=False, caption=self.name).addCallback(
            answered).addErrback(cancelled)
        return self.beginQuestion

    def readyForHandStart(self, playerNames:List[Tuple['Wind', str]], rotateWinds:bool) ->Optional[Deferred]:
        """playerNames are in wind order ESWN. Never called for first hand."""
        def answered(unused:Optional[List['Request']]=None) ->Optional[Deferred]:
            """called after the client player said yes, I am ready"""
            return Client.readyForHandStart(self, playerNames, rotateWinds) if self.connection else None
        if not self.connection:
            # disconnected meanwhile
            return None
        if Options.gui:
            # update the balances in the status bar:
            if Internal.mainWindow:
                Internal.mainWindow.updateGUI()
        assert self.game
        assert not self.game.isFirstHand()
        return Information(i18n("Ready for next hand?"), modal=False).addCallback(answered).addErrback(logException)

    def ask(self, move:'Move', answers:List['ClientMessage']) ->Deferred:
        """server sends move. We ask the user. answers is a list with possible answers,
        the default answer being the first in the list."""
        if not Options.gui:
            return Client.ask(self, move, answers)
        scene = Internal.scene
        assert scene
        assert self.game
        cast(PlayingPlayer, self.game.myself).computeSayable(move, answers)
        deferred:Deferred = Deferred()
        deferred.addCallback(self.__askAnswered)
        deferred.addErrback(self.__answerError, move, answers)
        iAmActive = self.game.myself == self.game.activePlayer
        assert self.game.myself.handBoard
        self.game.myself.handBoard.setEnabled(iAmActive)
        oldDialog = scene.clientDialog
        assert oldDialog is None or oldDialog.answered, (
            f'old dialog {str(oldDialog.move)}:{str([x.message.name for x in oldDialog.buttons])} '
            f'is unanswered, new Dialog: {str(move)}/{str(answers)}')
        if not oldDialog or not oldDialog.isVisible():
            # always build a new dialog because if we change its layout before
            # reshowing it, sometimes the old buttons are still visible in which
            # case the next dialog will appear at a lower position than it
            # should
            scene.clientDialog = ClientDialog(
                self,
                scene.mainWindow.centralWidget())
        assert scene.clientDialog
        assert scene.clientDialog.client is self
        scene.clientDialog.askHuman(move, answers, deferred)
        return deferred

    def __selectChow(self, chows:'MeldList') ->Union[Deferred, Tuple['ClientMessage', Union['Meld', None]]]:
        """which possible chow do we want to expose?
        Since we might return a Deferred to be sent to the server,
        which contains Message.Chow plus selected Chow, we should
        return the same tuple here"""
        assert self.game
        intelligence = self.game.myself.intelligence
        if self.game.autoPlay:
            return cast('ClientMessage', Message.Chow), intelligence.selectChow(chows)
        if len(chows) == 1:
            return cast('ClientMessage', Message.Chow), chows[0]
        assert Internal.Preferences
        if Internal.Preferences.propose:
            propose = intelligence.selectChow(chows)
        else:
            propose = None
        deferred:Deferred = Deferred()
        selDlg = SelectChow(chows, propose, deferred)
        assert selDlg.exec()
        return deferred

    def __selectKong(self, kongs:'MeldList') ->Union[Deferred, Tuple['ClientMessage', Optional['Meld']]]:
        """which possible kong do we want to declare?"""
        assert self.game
        if self.game.autoPlay:
            return cast('ClientMessage', Message.Kong), self.game.myself.intelligence.selectKong(kongs)
        if len(kongs) == 1:
            return cast('ClientMessage', Message.Kong), kongs[0]
        deferred:Deferred = Deferred()
        selDlg = SelectKong(kongs, deferred)
        assert selDlg.exec()
        return deferred

    def __askAnswered(self, answer:'ClientMessage') ->Union[
            Deferred,
            Tuple['ClientMessage', Union[bool, 'Tile', 'Meld',
                'MeldList', Tuple['MeldList', Optional['Tile'], 'Meld'], None ]]]:
        """the user answered our question concerning move"""
        if not self.game:
            return cast('ClientMessage', Message.NoClaim), None
        myself = self.game.myself
        if answer in [Message.Discard, Message.OriginalCall]:
            # do not remove tile from hand here, the server will tell all players
            # including us that it has been discarded. Only then we will remove
            # it.
            assert myself.handBoard
            assert myself.handBoard.focusTile
            myself.handBoard.setEnabled(False)
            return answer, myself.handBoard.focusTile.tile
        args = cast(PlayingPlayer, myself).sayable[answer]
        assert args
        if answer == Message.Chow:
            return self.__selectChow(cast('MeldList', args))
        if answer == Message.Kong:
            return self.__selectKong(cast('MeldList', args))
        self.game.hidePopups()
        if args is True or args == []:
            # this does not specify any tiles, the server does not need this. Robot players
            # also return None in this case.
            return answer, None
        return answer, args


    def __answerError(self, answer:Message, move:'Move', answers:List[Message]) ->None:
        """an error happened while determining the answer to server"""
        logException(
            f"{self.game.myself.name if self.game else 'NOGAME'} {answer} {move} {answers}")

    def remote_abort(self, tableid:int, message: str, *args:Any) ->None:
        """the server aborted this game"""
        if self.table and self.table.tableid == tableid:
            # translate Robot to Roboter:
            if self.game:
                args = self.game.players.translatePlayerNames(args)  # type:ignore[assignment]
            logWarning(i18n(message, *args))
            if self.game:
                self.game.close()
                self.game = None

    def remote_gameOver(self, tableid:int, message:str, *args:Any) ->None:
        """the game is over"""
        def yes(unused:'Request') ->None:
            """now that the user clicked the 'game over' prompt away, clean up"""
            if self.game:
                self.game.rotateWinds()
                _ = self.game.close()
                if Internal.mainWindow:
                    _.addCallback(Internal.mainWindow.close).addErrback(logException)
        assert self.table and self.table.tableid == tableid
        if Internal.scene:
            # update the balances in the status bar:
            Internal.scene.mainWindow.updateGUI()
        Information(i18n(message, *args)).addCallback(yes).addErrback(logException)

    def remote_serverDisconnects(self, result:Optional[str]=None) ->None:
        """we logged out or lost connection to the server.
        Remove visual traces depending on that connection."""
        if Debug.connections and result:
            logDebug(
                f'server {self.connection} disconnects: {result}')
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
            if Internal.mainWindow:
                Internal.mainWindow.close()

    def serverDisconnected(self, unusedReference:Deferred) ->None:
        """perspective calls us back"""
        if self.connection and (Debug.traffic or Debug.connections):
            logDebug(
                f'perspective notifies disconnect: {self.connection.url}')
        self.remote_serverDisconnects()

    @staticmethod
    def __versionError(err:Failure) ->Failure:
        """log the twisted error"""
        logWarning(err.getErrorMessage())
        if Internal.game:
            Internal.game.close()
            Internal.game = None
        return err

    @staticmethod
    def __wantedGame() ->str:
        """find out which game we want to start on the table"""
        result = SingleshotOptions.game
        if not result or result == '0':
            result = str(int(random.random() * 10 ** 9))
        SingleshotOptions.game = None
        return result

    def tableError(self, err:Failure) ->None:
        """log the twisted error"""
        if not self.connection:
            # lost connection to server
            if self.tableList:
                self.tableList.hide()
                self.tableList = None
        else:
            logWarning(err.getErrorMessage())

    def __newLocalTable(self, newId:int) ->Deferred:
        """we just got newId from the server"""
        return self.callServer('startGame', newId).addErrback(self.tableError)

    def __requestNewTableFromServer(self, tableid:Optional[int]=None, ruleset:Optional[Ruleset]=None) ->Deferred:
        """as the name says"""
        if ruleset is None:
            ruleset = self.ruleset
        assert self.connection
        self.connection.ruleset = ruleset  # side effect: saves ruleset as last used for server
        return self.callServer('newTable', ruleset.hash, Options.playOpen,
                               Internal.autoPlay, self.__wantedGame(), tableid).addErrback(self.tableError)

    def newTable(self) ->None:
        """TableList uses me as a slot"""
        if Options.ruleset:
            ruleset = Options.ruleset
        elif self.hasLocalServer():
            ruleset = self.ruleset
        else:
            assert self.connection
            selectDialog = SelectRuleset(self.connection.url)
            if not selectDialog.exec():
                return
            ruleset = selectDialog.cbRuleset.current
        deferred = self.__requestNewTableFromServer(ruleset=ruleset)
        if self.hasLocalServer():
            deferred.addCallback(self.__newLocalTable).addErrback(logException)
        assert self.tableList
        self.tableList.requestedNewTable = True

    def joinTable(self, table:Optional[ClientTable]=None) ->None:
        """join a table"""
        if not isinstance(table, ClientTable):
            assert self.tableList
            table = self.tableList.selectedTable()
            assert table
        self.callServer('joinTable', table.tableid).addErrback(self.tableError)

    def logout(self, unusedResult:Optional[List['Request']]=None) ->Deferred:
        """clean visual traces and logout from server"""
        def loggedout(result:List['Request'], connection:Connection) ->List['Request']:
            """end the connection from client side"""
            if Debug.connections:
                logDebug(f'server confirmed logout for {self}')
            connection.connector.disconnect()
            return result
        if self.connection:
            conn = self.connection
            self.connection = None
            if Debug.connections:
                logDebug(f'sending logout to server for {self}')
            return self.callServer('logout').addCallback(loggedout, conn).addErrback(logException)
        return succeed(None)

    def __logCallServer(self, *args:Any) ->None:
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
            self.game.debug(f'callServer({repr(debugArgs)})')
        else:
            logDebug(f'callServer({repr(debugArgs)})')

    def callServer(self, *args:Any) ->Deferred:
        """if we are online, call server"""
        if self.connection:
            if args[0] is None:
                args = args[1:]
            try:
                if Debug.traffic:
                    self.__logCallServer(*args)

                def callServerError(result:str) ->Optional[str]:
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

    def sendChat(self, chatLine:'ChatMessage') ->Deferred:
        """send chat message to server"""
        return self.callServer('chat', chatLine.asList())
