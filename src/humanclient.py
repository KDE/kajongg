# -*- coding: utf-8 -*-

"""
Copyright (C) 2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

import socket, subprocess, time, datetime, os

from twisted.spread import pb
from twisted.cred import credentials
from twisted.internet.defer import Deferred
from twisted.internet.address import UNIXAddress
from PyQt4.QtCore import SIGNAL, SLOT, Qt, QTimer
from PyQt4.QtCore import QByteArray, QString
from PyQt4.QtGui import QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QGridLayout, \
    QLabel, QComboBox, QLineEdit, QPushButton, \
    QProgressBar, QRadioButton, QSpacerItem, QSizePolicy

from PyKDE4.kdecore import KUser
from PyKDE4.kdeui import KDialogButtonBox
from PyKDE4.kdeui import KMessageBox

from util import m18n, m18nc, m18ncE, logWarning, logException, syslogMessage, socketName, english
from message import Message
import common
from common import InternalParameters
from scoringengine import meldsContent
from game import Players
from query import Query
from board import Board
from client import Client
from statesaver import StateSaver

from guiutil import ListComboBox
from scoringengine import Ruleset, PredefinedRuleset

class LoginDialog(QDialog):
    """login dialog for server"""
    def __init__(self):
        QDialog.__init__(self, None)
        self.setWindowTitle(m18n('Login') + ' - Kajongg')
        self.buttonBox = KDialogButtonBox(self)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.connect(self.buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(self.buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        vbox = QVBoxLayout(self)
        grid = QGridLayout()
        lblServer = QLabel(m18n('Game server:'))
        grid.addWidget(lblServer, 0, 0)
        self.cbServer = QComboBox()
        self.cbServer.setEditable(True)
        grid.addWidget(self.cbServer, 0, 1)
        lblServer.setBuddy(self.cbServer)
        lblUsername = QLabel(m18n('Username:'))
        grid.addWidget(lblUsername, 1, 0)
        self.cbUser = QComboBox()
        self.cbUser.setEditable(True)
        self.cbUser.setMinimumWidth(350) # is this good for all platforms?
        lblUsername.setBuddy(self.cbUser)
        grid.addWidget(self.cbUser, 1, 1)
        self.lblPassword = QLabel(m18n('Password:'))
        grid.addWidget(self.lblPassword, 2, 0)
        self.edPassword = QLineEdit()
        self.edPassword.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        grid.addWidget(self.edPassword, 2, 1)
        self.lblPassword.setBuddy(self.edPassword)
        self.lblRuleset = QLabel(m18nc('kajongg', 'Ruleset:'))
        grid.addWidget(self.lblRuleset, 3, 0)
        self.cbRuleset = ListComboBox()
        grid.addWidget(self.cbRuleset, 3, 1)
        self.lblRuleset.setBuddy(self.cbRuleset)
        vbox.addLayout(grid)
        vbox.addWidget(self.buttonBox)
        pol = QSizePolicy()
        pol.setHorizontalPolicy(QSizePolicy.Expanding)
        self.cbUser.setSizePolicy(pol)

        localName = m18nc('kajongg name for local game server', Query.localServerName)
        if InternalParameters.autoPlay:
            self.cbServer.addItem(localName)
        self.servers = Query('select url, lastname from server order by lasttime desc').records
        for server in self.servers:
            if server[0] == Query.localServerName:
                self.cbServer.addItem(localName)
            else:
                self.cbServer.addItem(server[0])
        if self.cbServer.findText(localName) < 0:
            self.cbServer.addItem(localName)
        self.connect(self.cbServer, SIGNAL('editTextChanged(QString)'), self.serverChanged)
        self.connect(self.cbUser, SIGNAL('editTextChanged(QString)'), self.userChanged)
        self.serverChanged()
        self.state = StateSaver(self)
        if InternalParameters.autoPlay:
            self.timer = QTimer()
            self.connect(self.timer, SIGNAL('timeout()'), self.accept)
            self.timer.start(1)
            self.emit (SIGNAL("accepted()"))

    def accept(self):
        """user entered OK"""
        if self.host == Query.localServerName:
            # client and server use the same database, and we
            # have no security concerns
            Players.createIfUnknown(self.host, str(self.cbUser.currentText()))
        QDialog.accept(self)

    def serverChanged(self, text=None):
        """the user selected a different server"""
        Players.load()
        self.cbUser.clear()
        self.cbUser.addItems(list(x[1] for x in Players.allNames.values() if x[0] == self.host))
        if not self.cbUser.count():
            self.cbUser.addItem(KUser(os.geteuid()).fullName())
        hostName = self.host
        userNames = [x[1] for x in self.servers if x[0] == hostName]
        if userNames:
            userIdx = self.cbUser.findText(userNames[0])
            if userIdx >= 0:
                self.cbUser.setCurrentIndex(userIdx)
        showPW = self.host != Query.localServerName
        self.lblPassword.setVisible(showPW)
        self.edPassword.setVisible(showPW)
        self.lblRuleset.setVisible(not showPW)
        self.cbRuleset.setVisible(not showPW)
        if not showPW:
            self.cbRuleset.clear()
            self.cbRuleset.items = Ruleset.selectableRulesets(self.host)

    def userChanged(self, text):
        if text == '':
            self.edPassword.clear()
            return
        passw = Query("select password from player where host=? and name=?",
            list([self.host, str(text)])).records
        if passw:
            self.edPassword.setText(passw[0][0])
        else:
            self.edPassword.clear()

    @apply
    def host():
        def fget(self):
            text = english(str(self.cbServer.currentText()))
            if ':' not in text:
                return text
            hostargs = text.rpartition(':')
            return ''.join(hostargs[0])
        return property(**locals())

    @apply
    def port():
        def fget(self):
            text = str(self.cbServer.currentText())
            if ':' not in text:
                return common.PREF.serverPort
            hostargs = str(self.cbServer.currentText()).rpartition(':')
            try:
                return int(hostargs[2])
            except Exception:
                return common.PREF.serverPort
        return property(**locals())

    @apply
    def username():
        def fget(self):
            return str(self.cbUser.currentText())
        return property(**locals())

    @apply
    def password():
        def fget(self):
            return str(self.edPassword.text())
        return property(**locals())

class SelectChow(QDialog):
    """asks which of the possible chows is wanted"""
    def __init__(self, chows):
        QDialog.__init__(self)
        self.chows = chows
        self.selectedChow = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(m18n('Which chow do you want to expose?')))
        self.buttons = []
        for chow in chows:
            button = QRadioButton('-'.join([chow[0][1], chow[1][1], chow[2][1]]), self)
            self.buttons.append(button)
            layout.addWidget(button)
            self.connect(button, SIGNAL('toggled(bool)'), self.toggled)

    def toggled(self, checked):
        """a radiobutton has been toggled"""
        button = self.sender()
        if button.isChecked():
            self.selectedChow = self.chows[self.buttons.index(button)]
            self.accept()

    def closeEvent(self, event):
        """allow close only if a chow has been selected"""
        if self.selectedChow:
            event.accept()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        """catch and ignore the Escape key"""
        if event.key() == Qt.Key_Escape:
            event.ignore()
        else:
            QDialog.keyPressEvent(self, event)

class DlgButton(QPushButton):
    """special button for ClientDialog"""
    def __init__(self, key, parent):
        QPushButton.__init__(self, parent)
        self.key = key
        self.parent = parent

    def keyPressEvent(self, event):
        """forward horizintal arrows to the hand board"""
        key = Board.mapChar2Arrow(event)
        if key in [Qt.Key_Left, Qt.Key_Right]:
            game = self.parent.client.game
            if game.activePlayer == game.myself:
                game.myself.handBoard.keyPressEvent(event)
                self.setFocus()
                return
        QPushButton.keyPressEvent(self, event)

class ClientDialog(QDialog):
    """a simple popup dialog for asking the player what he wants to do"""
    def __init__(self, client, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(m18n('Choose') + ' - Kajongg')
        self.setObjectName('ClientDialog')
        self.client = client
        self.relativePos = None
        self.layout = QGridLayout(self)
        self.progressBar = QProgressBar()
        self.timer = QTimer()
        self.connect(self.timer, SIGNAL('timeout()'), self.timeout)
        self.deferred = None
        self.buttons = []
        self.setWindowFlags(Qt.SubWindow | Qt.WindowStaysOnTopHint)
        self.setModal(False)

    def keyPressEvent(self, event):
        """ESC selects default answer"""
        if event.key() in [Qt.Key_Escape, Qt.Key_Space]:
            self.selectButton()
            event.accept()
        else:
            for btn in self.buttons:
                if str(event.text()).upper() == btn.key:
                    self.selectButton(btn)
                    event.accept()
                    return
            QDialog.keyPressEvent(self, event)

    def __declareButton(self, message):
        """define a button"""
        btn = DlgButton(message.shortcut, self)
        btn.setObjectName(message.name)
        btn.setText(message.buttonCaption())
        btn.setAutoDefault(True)
        self.connect(btn, SIGNAL('clicked(bool)'), self.selectedAnswer)
        self.buttons.append(btn)

    def ask(self, move, answers, deferred):
        """make buttons specified by answers visible. The first answer is default.
        The default button only appears with blue border when this dialog has
        focus but we always want it to be recognizable. Hence setBackgroundRole."""
        self.deferred = deferred
        for answer in answers:
            self.__declareButton(answer)
        self.show()
        self.buttons[0].setFocus()
        myTurn = self.client.game.activePlayer == self.client.game.myself
        if InternalParameters.autoPlay:
            self.selectButton()
            return

        self.progressBar.setVisible(not myTurn)
        if myTurn:
            hBoard = self.client.game.myself.handBoard
            hBoard.showFocusRect(hBoard.focusTile)
        else:
            msecs = 50
            self.progressBar.setMinimum(0)
            self.progressBar.setMaximum(self.client.game.ruleset.claimTimeout * 1000 / msecs)
            self.progressBar.reset()
            self.timer.start(msecs)

    def placeInField(self):
        """place the dialog at bottom or to the right depending on space."""
        field = self.client.game.field
        cwi = field.centralWidget()
        view = field.centralView
        geometry = self.geometry()
        btnHeight = self.buttons[0].height()
        vertical = view.width() > view.height() * 1.2
        if vertical:
            h = (len(self.buttons) + 1) * btnHeight * 1.2
            w = (cwi.width() - cwi.height() ) / 2
            geometry.setX(cwi.width() - w)
            geometry.setY(cwi.height()/2  - h/2)
        else:
            handBoard = self.client.game.myself.handBoard
            if not handBoard:
                # we are in the progress of logging out
                return
            hbLeftTop = view.mapFromScene(handBoard.mapToScene(handBoard.rect().topLeft()))
            hbRightBottom = view.mapFromScene(handBoard.mapToScene(handBoard.rect().bottomRight()))
            w = hbRightBottom.x() - hbLeftTop.x()
            h = btnHeight
            geometry.setY(cwi.height()  - h)
            geometry.setX(hbLeftTop.x())
        spacer1 = QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Expanding)
        spacer2 = QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addItem(spacer1, 0, 0)
        for idx, btn in enumerate(self.buttons + [self.progressBar]):
            self.layout.addWidget(btn, idx+1 if vertical else 0, idx+1 if not vertical else 0)
        idx = len(self.buttons) + 2
        self.layout.addItem(spacer2, idx if vertical else 0, idx if not vertical else 0)

        geometry.setWidth(w)
        geometry.setHeight(h)
        self.setGeometry(geometry)

    def showEvent(self, event):
        """try to place the dialog such that it does not cover interesting information"""
        self.placeInField()

    def timeout(self):
        """the progressboard wants an update"""
        pBar = self.progressBar
        pBar.setValue(pBar.value()+1)
        pBar.setVisible(True)
        if pBar.value() == pBar.maximum():
            # timeout: we always return the original default answer, not the one with focus
            self.selectButton()
            pBar.setVisible(False)

    def selectButton(self, button=None):
        """select default answer"""
        if self.isVisible():
            self.timer.stop()
            if button is None:
                button = self.buttons[0]
            answer = Message.defined[str(button.objectName())]
            self.deferred.callback(answer)
        self.hide()

    def selectedAnswer(self, checked):
        """the user clicked one of the buttons"""
        self.selectButton(self.sender())

class ReadyHandQuestion(QDialog):
    """ask user if he is ready for the hand"""
    def __init__(self, deferred, parent=None):
        QDialog.__init__(self, parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.deferred = deferred
        layout = QVBoxLayout(self)
        buttonBox = QDialogButtonBox()
        layout.addWidget(buttonBox)
        self.okButton = buttonBox.addButton(m18n("&Ready for next hand?"),
          QDialogButtonBox.AcceptRole)
        self.connect(self.okButton, SIGNAL('clicked(bool)'), self.accept)
        self.setWindowTitle('Kajongg')
        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("accept()"))

    def accept(self):
        if self.isVisible():
            self.deferred.callback(None)
            self.hide()

    def keyPressEvent(self, event):
        """catch and ignore the Escape key"""
        if event.key() == Qt.Key_Escape:
            event.ignore()
        else:
            QDialog.keyPressEvent(self, event)


class HumanClient(Client):

    serverProcess = None
    socketServerProcess = None

    def __init__(self, tableList, callback):
        Client.__init__(self)
        self.tableList = tableList
        self.callback = callback
        self.connector = None
        self.table = None
        self.discardBoard = tableList.field.discardBoard
        self.readyHandQuestion = None
        self.loginDialog = LoginDialog()
        if not self.loginDialog.exec_():
            raise Exception(m18n('Login aborted'))
        self.useSocket = self.loginDialog.host == Query.localServerName
        if self.useSocket or self.loginDialog.host == 'localhost':
            if not self.serverListening():
                # give the server up to 5 seconds time to start
                HumanClient.startLocalServer(self.useSocket)
                for second in range(5):
                    if self.serverListening():
                        break
                    time.sleep(1)
        self.username = self.loginDialog.username
        self.ruleset = self.loginDialog.cbRuleset.current
        self.root = self.connect()
        self.root.addCallback(self.connected).addErrback(self._loginFailed)

    def isRobotClient(self):
        """avoid using isinstance, it would import too much for kajonggserver"""
        return False

    def isHumanClient(self):
        """avoid using isinstance, it would import too much for kajonggserver"""
        return True

    def isServerClient(self):
        """avoid using isinstance, it would import too much for kajonggserver"""
        return False

    def hasLocalServer(self):
        """True if we are talking to a Local Game Server"""
        return self.useSocket

    def serverListening(self):
        """is somebody listening on that port?"""
        if self.useSocket:
            sock = socket.socket(socket.AF_UNIX,  socket.SOCK_STREAM)
            sock.settimeout(1)
            try:
                sock.connect(socketName())
            except socket.error, exc:
                if os.path.exists(socketName()):
                    syslogMessage(m18n('removed stale socket <filename>%1</filename>', socketName()))
                    os.remove(socketName())
                return False
            else:
                return True
        else:
            sock = socket.socket(socket.AF_INET,  socket.SOCK_STREAM)
            sock.settimeout(1)
            try:
                sock.connect((self.loginDialog.host, self.loginDialog.port))
            except socket.error:
                return False
            else:
                return True

    @staticmethod
    def startLocalServer(useSocket):
        """start a local server"""
        try:
            args = ' '.join([
                '--seed=%d' % InternalParameters.seed if InternalParameters.seed else '',
                '--showtraffic'  if InternalParameters.showTraffic else '',
                '--socket=%s' % socketName() if useSocket else ''])
            process = subprocess.Popen(['kajonggserver', args])
            syslogMessage(m18n('started the local kajongg server: pid=<numid>%1</numid> %2',
                process.pid, args))
            if useSocket:
                HumanClient.socketServerProcess = process
            else:
                HumanClient.serverProcess = process
        except Exception, exc:
            logException(exc)

    @staticmethod
    def stopLocalServers():
        """stop the local servers we started"""
        for process in [HumanClient.serverProcess, HumanClient.socketServerProcess]:
            if process:
                syslogMessage(m18n('stopped the local kajongg server: pid=<numid>%1</numid>',
                    process.pid))
                process.terminate()
        HumanClient.serverProcess = None
        HumanClient.socketServerProcess = None

    def __del__(self):
        """if we go away and we started a local server, stop it again"""
        HumanClient.stopLocalServers()

    def remote_tablesChanged(self, tableid, tables):
        """update table list"""
        Client.remote_tablesChanged(self, tableid, tables)
        self.tableList.load(tableid, self.tables)

    def readyForGameStart(self, tableid, seed, playerNames, shouldSave=True):
        """playerNames are in wind order ESWN"""
        if sum(not x.startswith('ROBOT') for x in playerNames.split('//')) == 1:
            # we play against 3 robots and we already told the server to start: no need to ask again
            wantStart = True
        else:
            msg = m18n("The game can begin. Are you ready to play now?\n" \
                "If you answer with NO, you will be removed from the table.")
            wantStart = KMessageBox.questionYesNo (None, msg) == KMessageBox.Yes
        if wantStart:
            Client.readyForGameStart(self, tableid, seed, playerNames, self.tableList.field, shouldSave=shouldSave)
        else:
            self.answers.append(Message.NO)

    def readyForHandStart(self, playerNames, rotate):
        """playerNames are in wind order ESWN"""
        if self.game.handctr:
            if InternalParameters.autoPlay:
                self.clientReadyForHandStart(None, playerNames, rotate)
                return
            deferred = Deferred()
            deferred.addCallback(self.clientReadyForHandStart, playerNames, rotate)
            self.readyHandQuestion = ReadyHandQuestion(deferred, self.game.field)
            self.readyHandQuestion.show()
            self.answers.append(deferred)

    def clientReadyForHandStart(self, none, playerNames, rotate):
        Client.readyForHandStart(self, playerNames, rotate)

    def ask(self, move, answers):
        """server sends move. We ask the user. answers is a list with possible answers,
        the default answer being the first in the list."""
        deferred = Deferred()
        deferred.addCallback(self.answered, move, answers)
        handBoard = self.game.myself.handBoard
        IAmActive = self.game.myself == self.game.activePlayer
        handBoard.setEnabled(IAmActive)
        field = self.game.field
        if not field.clientDialog or not field.clientDialog.isVisible():
            # always build a new dialog because if we change its layout before
            # reshowing it, sometimes the old buttons are still visible in which
            # case the next dialog will appear at a lower position than it should
            field.clientDialog = ClientDialog(self, field.centralWidget())
        field.clientDialog.ask(move, answers, deferred)
        self.answers.append(deferred)

    def selectChow(self, chows):
        """which possible chow do we want to expose?"""
        if InternalParameters.autoPlay:
            return Client.selectChow(self, chows)
        if len(chows) == 1:
            return chows[0]
        selDlg = SelectChow(chows)
        assert selDlg.exec_()
        return selDlg.selectedChow

    def answered(self, answer, move, answers):
        """the user answered our question concerning move"""
        if InternalParameters.autoPlay:
            self.game.hidePopups()
            return Client.ask(self, move, answers)
        message = None
        myself = self.game.myself
        try:
            if answer == Message.Discard:
                # do not remove tile from hand here, the server will tell all players
                # including us that it has been discarded. Only then we will remove it.
                myself.handBoard.setEnabled(False)
                return answer.name, myself.handBoard.focusTile.element
            args = self.maySay(move, answer)
            if args:
                return answer.name, args
            else:
                message = m18n('You cannot say %1', answer.i18nName)
        finally:
            if message:
                KMessageBox.sorry(None, message)
                self.game.field.clientDialog.hide()
                return self.ask(move, self.game.field.clientDialog.answers)
            else:
                self.game.hidePopups()

    def remote_abort(self, tableid, message, *args):
        """the server aborted this game"""
        if self.table and self.table.tableid == tableid:
            # translate ROBOT to Roboter:
            args = [m18nc('kajongg', x) for x in args]
            logWarning(m18n(message, *args))
            if self.game:
                self.game.close()
        if InternalParameters.autoPlay:
            if self.game and self.game.field:
                self.game.field.quit()

    def remote_gameOver(self, tableid, message, *args):
        """the server aborted this game"""
        if self.table and self.table.tableid == tableid:
            logWarning(m18n(message, *args))
            if self.game:
                self.game.rotateWinds()
                self.game.close()
        if InternalParameters.autoPlay:
            self.game.field.quit()

    def remote_serverDisconnects(self):
        """the kajongg server ends our connection"""
        self.perspective = None

    def connect(self):
        """connect self to server"""
        factory = pb.PBClientFactory()
        reactor = self.tableList.field.reactor
        if self.useSocket:
            self.connector = reactor.connectUNIX(socketName(), factory)
        else:
            self.connector = reactor.connectTCP(self.loginDialog.host, self.loginDialog.port, factory)
        cred = credentials.UsernamePassword(self.loginDialog.username, self.loginDialog.password)
        return factory.login(cred, client=self)

    def _loginFailed(self, failure):
        """login failed"""
        self.loginDialog = None  # no longer needed
        logWarning(failure.getErrorMessage())
        if self.callback:
            self.callback()

    def connected(self, perspective):
        """we are online. Update table server and continue"""
        lasttime = datetime.datetime.now().replace(microsecond=0).isoformat()
        qData = Query('select url from server where url=?',
            list([self.host])).records
        if not qData:
            Query('insert into server(url,lastname,lasttime) values(?,?,?)',
                list([self.host, self.username, lasttime]))
        else:
            Query('update server set lastname=?,lasttime=? where url=?',
                list([self.username, lasttime, self.host]))
            Query('update player set password=? where host=? and name=?',
                list([self.loginDialog.password, self.host, self.username]))
        self.loginDialog = None  # no longer needed
        self.perspective = perspective
        if self.callback:
            self.callback()

    @apply
    def host():
        def fget(self):
            if not self.connector:
                return None
            dest = self.connector.getDestination()
            if isinstance(dest, UNIXAddress):
                return Query.localServerName
            else:
                return dest.host
        return property(**locals())

    def logout(self):
        """clean visual traces and logout from server"""
        d = self.callServer('logout')
        if d:
            d.addBoth(self.loggedOut)
        return d

    def loggedOut(self, result):
        self.discardBoard.hide()
        if self.readyHandQuestion:
            self.readyHandQuestion.hide()
        if self.game.field.clientDialog:
            self.game.field.clientDialog.hide()

    def callServer(self, *args):
        """if we are online, call server"""
        if self.perspective:
            try:
                return self.perspective.callRemote(*args)
            except pb.DeadReferenceError:
                self.perspective = None
                logWarning(m18n('The connection to the server %1 broke, please try again later.',
                                  self.host))