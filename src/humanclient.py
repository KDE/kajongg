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

import socket, subprocess, time, datetime, os, sys
import csv, re

from twisted.spread import pb
from twisted.cred import credentials
from twisted.internet.defer import Deferred, succeed
from twisted.internet.address import UNIXAddress
from PyQt4.QtCore import Qt, QTimer
from PyQt4.QtGui import QDialog, QDialogButtonBox, QVBoxLayout, QGridLayout, \
    QLabel, QComboBox, QLineEdit, QPushButton, QFormLayout, \
    QProgressBar, QRadioButton, QSpacerItem, QSizePolicy

from kde import KMessageBox, KDialogButtonBox, KUser, KIcon

from util import m18n, m18nc, logWarning, logException, socketName, english, \
    appdataDir, logInfo, logDebug, removeIfExists, which
from util import SERVERMARK, isAlive
from message import Message, ChatMessage
from chat import ChatWindow
from common import InternalParameters, PREF, Debug
from game import Players
from query import Transaction, Query
from board import Board
from client import Client
from statesaver import StateSaver
from meld import Meld
from tables import TableList
from sound import Voice
import intelligence
import altint

from guiutil import ListComboBox
from rule import Ruleset

class LoginAborted(Exception):
    """the user aborted the login"""
    pass

class NetworkOffline(Exception):
    """we are offline"""
    pass

class LoginDialog(QDialog):
    """login dialog for server"""
    def __init__(self):
        """self.servers is a list of tuples containing server and last playername"""
        QDialog.__init__(self, None)
        self.setWindowTitle(m18n('Login') + ' - Kajongg')
        self.setupUi()

        localName = m18nc('kajongg name for local game server', Query.localServerName)
        self.servers = Query('select url,lastname from server order by lasttime desc').records
        servers = [m18nc('kajongg name for local game server', x[0]) for x in self.servers]
        # the first server combobox item should be default: either the last used server
        # or localName for autoPlay
        if localName not in servers:
            servers.append(localName)
        if 'kajongg.org' not in servers:
            servers.append('kajongg.org')
        if InternalParameters.autoPlay:
            servers.remove(localName)    # we want a unique list, it will be re-used for all following games
            servers.insert(0, localName)   # in this process but they will not be autoPlay
        self.cbServer.addItems(servers)
        self.passwords = Query('select url, p.name, passwords.password from passwords, player p '
            'where passwords.player=p.id').records
        Players.load()
        self.cbServer.editTextChanged.connect(self.serverChanged)
        self.cbUser.editTextChanged.connect(self.userChanged)
        self.serverChanged()
        StateSaver(self)

    def setupUi(self):
        """create all Ui elements but do not fill them"""
        buttonBox = KDialogButtonBox(self)
        buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        # Ubuntu 11.10 unity is a bit strange - without this, it sets focus on
        # the cancel button (which it shows on the left). I found no obvious
        # way to use setDefault and setAutoDefault for fixing this.
        buttonBox.button(QDialogButtonBox.Ok).setFocus(True)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        vbox = QVBoxLayout(self)
        self.grid = QFormLayout()
        self.cbServer = QComboBox()
        self.cbServer.setEditable(True)
        self.grid.addRow(m18n('Game server:'), self.cbServer)
        self.cbUser = QComboBox()
        self.cbUser.setEditable(True)
        self.grid.addRow(m18n('Username:'), self.cbUser)
        self.edPassword = QLineEdit()
        self.edPassword.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.grid.addRow(m18n('Password:'), self.edPassword)
        self.cbRuleset = ListComboBox()
        self.grid.addRow(m18nc('kajongg', 'Ruleset:'), self.cbRuleset)
        vbox.addLayout(self.grid)
        vbox.addWidget(buttonBox)
        pol = QSizePolicy()
        pol.setHorizontalPolicy(QSizePolicy.Expanding)
        self.cbUser.setSizePolicy(pol)

    def accept(self):
        """user entered OK"""
        if self.url == 'localhost':
            # we have localhost if we play a Local Game: client and server are identical,
            # we have no security concerns about creating a new account
            Players.createIfUnknown(unicode(self.cbUser.currentText()))
        QDialog.accept(self)

    def serverChanged(self, dummyText=None):
        """the user selected a different server"""
        records = Query('select player.name from player, passwords '
                'where passwords.url=? and passwords.player = player.id', list([self.url])).records
        self.cbUser.clear()
        self.cbUser.addItems(list(x[0] for x in records))
        if not self.cbUser.count():
            user = KUser() if os.name == 'nt' else KUser(os.geteuid())
            self.cbUser.addItem(user.fullName() or user.loginName())
        userNames = [x[1] for x in self.servers if x[0] == self.url]
        if userNames:
            userIdx = self.cbUser.findText(userNames[0])
            if userIdx >= 0:
                self.cbUser.setCurrentIndex(userIdx)
        showPW = self.url != Query.localServerName
        self.grid.labelForField(self.edPassword).setVisible(showPW)
        self.edPassword.setVisible(showPW)
        self.grid.labelForField(self.cbRuleset).setVisible(not showPW)
        self.cbRuleset.setVisible(not showPW)
        if not showPW:
            self.cbRuleset.clear()
            self.cbRuleset.items = Ruleset.selectableRulesets(self.url)

    def userChanged(self, text):
        """the username has been changed, lookup password"""
        if text == '':
            self.edPassword.clear()
            return
        passw = None
        for entry in self.passwords:
            if entry[0] == self.url and entry[1] == unicode(text):
                passw = entry[2]
        if passw:
            self.edPassword.setText(passw)
        else:
            self.edPassword.clear()

    @apply
    def url():
        """abstracts the url of the dialog"""
        def fget(self):
            return english(unicode(self.cbServer.currentText()))
        return property(**locals())

    @apply
    def host():
        """abstracts the host of the dialog"""
        def fget(self):
            return self.url.partition(':')[0]
        return property(**locals())

    @apply
    def port():
        """abstracts the port of the dialog"""
        def fget(self):
            try:
                return int(self.url.partition(':')[2])
            except ValueError:
                return InternalParameters.defaultPort()
        return property(**locals())

    @apply
    def username():
        """abstracts the username of the dialog"""
        def fget(self):
            return unicode(self.cbUser.currentText())
        return property(**locals())

    @apply
    def password(): # pylint: disable=E0202
        """abstracts the password of the dialog"""
        def fget(self):
            return unicode(self.edPassword.text())
        def fset(self, password):
            self.edPassword.setText(password)
        return property(**locals())

class AddUserDialog(QDialog):
    """add a user account on a server: This dialog asks for the needed attributes"""
    # pylint: disable=R0902
    # pylint we need more than 10 instance attributes

    def __init__(self, url, username, password):
        QDialog.__init__(self, None)
        self.setWindowTitle(m18n('Create User Account') + ' - Kajongg')
        self.buttonBox = KDialogButtonBox(self)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        vbox = QVBoxLayout(self)
        grid = QFormLayout()
        self.lbServer = QLabel()
        self.lbServer.setText(url)
        grid.addRow(m18n('Game server:'), self.lbServer)
        self.lbUser = QLabel()
        grid.addRow(m18n('Username:'), self.lbUser)
        self.edPassword = QLineEdit()
        self.edPassword.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        grid.addRow(m18n('Password:'), self.edPassword)
        self.edPassword2 = QLineEdit()
        self.edPassword2.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        grid.addRow(m18n('Repeat password:'), self.edPassword2)
        vbox.addLayout(grid)
        vbox.addWidget(self.buttonBox)
        pol = QSizePolicy()
        pol.setHorizontalPolicy(QSizePolicy.Expanding)
        self.lbUser.setSizePolicy(pol)

        self.edPassword.textChanged.connect(self.passwordChanged)
        self.edPassword2.textChanged.connect(self.passwordChanged)
        StateSaver(self)
        self.username = username
        self.password = password
        self.passwordChanged()
        self.edPassword2.setFocus()

    def passwordChanged(self, dummyText=None):
        """password changed"""
        self.validate()

    def validate(self):
        """does the dialog hold valid data?"""
        equal = self.edPassword.size() and self.edPassword.text() == self.edPassword2.text()
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(equal)

    @apply
    def username(): # pylint: disable=E0202
        """abstracts the username of the dialog"""
        def fget(self):
            return unicode(self.lbUser.text())
        def fset(self, username):
            self.lbUser.setText(username)
        return property(**locals())

    @apply
    def password(): # pylint: disable=E0202
        """abstracts the password of the dialog"""
        def fget(self):
            return unicode(self.edPassword.text())
        def fset(self, password):
            self.edPassword.setText(password)
        return property(**locals())

class SelectChow(QDialog):
    """asks which of the possible chows is wanted"""
    def __init__(self, chows, propose):
        QDialog.__init__(self)
        self.setWindowTitle('Kajongg')
        self.chows = chows
        self.selectedChow = None
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

class SelectKong(QDialog):
    """asks which of the possible kongs is wanted"""
    def __init__(self, kongs):
        QDialog.__init__(self)
        self.setWindowTitle('Kajongg')
        self.kongs = kongs
        self.selectedKong = None
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

    def closeEvent(self, event):
        """allow close only if a chow has been selected"""
        if self.selectedKong:
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
            if game.activePlayer == game.myself:
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
        if self.client.game.autoPlay:
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
        if PREF.showOnlyPossibleActions and not maySay:
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

    def checkTiles(self):
        """does the logical state match the displayed tiles?"""
        for player in self.client.game.players:
            logExposed = list()
            logConcealed = list()
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
            logConcealed = player.concealedTileNames
            logExposed.sort()
            logConcealed.sort()
            physExposed.sort()
            physConcealed.sort()
            assert logExposed == physExposed, '%s != %s' % (logExposed, physExposed)
            assert logConcealed == physConcealed, '%s != %s' % (logConcealed, physConcealed)

    def messages(self):
        """a list of all messages returned by the declared buttons"""
        return list(x.message for x in self.buttons)

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
        prefButton = self.buttons[0]
        if game.autoPlay or PREF.propose:
            answer, parameter = self.client.intelligence.selectAnswer(
                self.messages())
            prefButton = [x for x in self.buttons if x.message == answer][0]
            prefButton.setFocus()
            if answer in [Message.Discard, Message.OriginalCall]:
                for tile in game.myself.handBoard.tiles:
                    if tile.element == parameter:
                        game.myself.handBoard.focusTile = tile

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
        field = InternalParameters.field
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
                button = self.buttons[0]
            if isinstance(button, Message):
                assert any(x.message == button for x in self.buttons)
                answer = button
            else:
                answer = button.message
            if not self.client.sayable[answer]:
                message = m18n('You cannot say %1', answer.i18nName)
                KMessageBox.sorry(None, message)
                return
            self.deferred.callback(answer)
        self.hide()
        InternalParameters.field.clientDialog = None

    def selectedAnswer(self, dummyChecked):
        """the user clicked one of the buttons"""
        if not self.client.game.autoPlay:
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
        self.okButton.clicked.connect(self.accept)
        self.setWindowTitle('Kajongg')
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.accept)

    def accept(self):
        """player is ready"""
        if self.isVisible():
            self.deferred.callback(None)
            self.hide()

    def keyPressEvent(self, event):
        """catch and ignore the Escape key"""
        if event.key() == Qt.Key_Escape:
            event.ignore()
        else:
            QDialog.keyPressEvent(self, event)

class AlreadyConnected(Exception):
    """we already have a connection to the server"""
    def __init__(self, url):
        Exception.__init__(self, m18n('You are already connected to server %1', url))

class HumanClient(Client):
    """a human client"""
    # pylint: disable=R0904
    # disable warning about too many public methods
    # pylint: disable=R0902
    # we have 11 instance attributes, more than pylint likes

    def __init__(self):
        aiClass = self.__findAI([intelligence, altint], InternalParameters.AI)
        if not aiClass:
            raise Exception('intelligence %s is undefined' % InternalParameters.AI)
        Client.__init__(self, intelligence=aiClass)
        self.root = None
        self.tableList = None
        self.connector = None
        self.table = None
        self.readyHandQuestion = None
        self.loginDialog = LoginDialog()
        if InternalParameters.autoPlay:
            self.loginDialog.accept()
        else:
            if not self.loginDialog.exec_():
                InternalParameters.field.startingGame = False
                InternalParameters.field.updateGUI()
                raise LoginAborted
        self.useSocket = self.loginDialog.host == Query.localServerName
        self.assertConnectivity()
        self.username = self.loginDialog.username
        self.__url = self.loginDialog.url
        self.ruleset = self.__defineRuleset()
        self.__msg = None # helper for delayed error messages
        self.__checkExistingConnections()
        self.login()

    def __checkExistingConnections(self):
        """do we already have a connection to the wanted URL?"""
        for client in self.clients:
            if client.perspective and client.url == self.__url:
                client.callServer('sendTables').addCallback(client.tableList.gotTables)
                client.tableList.activateWindow()
                raise AlreadyConnected(self.__url)

    @staticmethod
    def __findAI(modules, aiName):
        """list of all alternative AIs defined in altint.py"""
        for modul in modules:
            for key, value in modul.__dict__.items():
                if key == 'AI' + aiName:
                    return value

    def __defineRuleset(self):
        """find out what ruleset to use"""
        if InternalParameters.autoPlayRuleset:
            return InternalParameters.autoPlayRuleset
        elif InternalParameters.autoPlay:
            return Ruleset.selectableRulesets()[0]
        else:
            return self.loginDialog.cbRuleset.current

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
        return self.useSocket

    @staticmethod
    def findFreePort():
        """find an unused port on the current system.
        used when we want to start a local server on windows"""
        for port in range(2000, 9000):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            try:
                sock.connect(('127.0.0.1', port))
            except socket.error:
                return port
        logException('cannot find a free port')

    def serverListening(self):
        """is somebody listening on that port?"""
        if self.useSocket and os.name != 'nt':
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(1)
            try:
                sock.connect(socketName())
            except socket.error, exception:
                if os.path.exists(socketName()):
                    # try again, avoiding a race
                    try:
                        sock.connect(socketName())
                    except socket.error, exception:
                        if removeIfExists(socketName()):
                            logInfo(m18n('removed stale socket <filename>%1</filename>', socketName()))
                        logInfo('socket error:%s' % str(exception))
                        return False
                    else:
                        return True
            else:
                return True
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            try:
                sock.connect((self.loginDialog.host, self.loginDialog.port))
            except socket.error:
                return False
            else:
                return True

    def assertConnectivity(self):
        """make sure we have a running local server or network connectivity"""
        if self.useSocket or self.loginDialog.url == 'localhost':
            if not self.serverListening():
                if os.name == 'nt':
                    port = HumanClient.findFreePort()
                else:
                    port = None
                self.startLocalServer(port)
                # give the server up to 5 seconds time to start
                for loop in range(50):
                    if self.serverListening():
                        break
                    time.sleep(0.1)
        elif which('qdbus'):
            # the state of QtDBus is unclear to me.
            # riverbank.computing says module dbus is deprecated
            # for Python 3. And Ubuntu has no package with
            # PyQt4.QtDBus. So we use good old subprocess.
            answer = str(subprocess.check_output(['qdbus',
                'org.kde.kded',
                '/modules/networkstatus',
                'org.kde.Solid.Networking.status'])).strip()
            if answer != '4':
                raise NetworkOffline(answer)

    def startLocalServer(self, port):
        """start a local server"""
        try:
            args = ['kajonggserver'] # the default
            if sys.argv[0].endswith('kajongg.py'):
                tryServer = sys.argv[0].replace('.py', 'server.py')
                if os.path.exists(tryServer):
                    args = ['python', tryServer]
            if self.useSocket or os.name == 'nt':
                args.append('--local')
            if port:
                args.append('--port=%d' % port)
            if self.useSocket:
                args.append('--db=%slocal.db' % appdataDir())
            if Debug.argString:
                args.append('--debug=%s' % Debug.argString)
            if InternalParameters.socket:
                args.append('--socket=%s' % InternalParameters.socket)
            process = subprocess.Popen(args, shell=os.name=='nt')
            logInfo(m18n('started the local kajongg server: pid=<numid>%1</numid> %2',
                process.pid, ' '.join(args)))
        except OSError, exc:
            logException(exc)

    def remote_tablesChanged(self, tables):
        """update table list"""
        Client.remote_tablesChanged(self, tables)
        self.tableList.loadTables(self.tables)

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
            assert table.tableid == chatLine.tableid
        if not chatLine.isStatusMessage:
            ChatWindow.createFor(table)
        if table.chatWindow:
            table.chatWindow.receiveLine(chatLine)

    def readyForGameStart(self, tableid, gameid, wantedGame, playerNames, shouldSave=True):
        """playerNames are in wind order ESWN"""
        self.tableList.hide()
        if sum(not x[1].startswith('ROBOT') for x in playerNames) == 1:
            # we play against 3 robots and we already told the server to start: no need to ask again
            wantStart = True
        else:
            msg = m18n("The game can begin. Are you ready to play now?\n" \
                "If you answer with NO, you will be removed from the table.")
            wantStart = KMessageBox.questionYesNo (None, msg) == KMessageBox.Yes
        if wantStart:
            return Client.readyForGameStart(self, tableid, gameid, wantedGame, playerNames, shouldSave=shouldSave)
        else:
            return Message.NO

    def readyForHandStart(self, playerNames, rotateWinds):
        """playerNames are in wind order ESWN. Never called for first hand."""
        if InternalParameters.field:
            # update the balances in the status bar:
            InternalParameters.field.updateGUI()
        assert not self.game.isFirstHand()
        if self.game.autoPlay:
            self.clientReadyForHandStart(None, playerNames, rotateWinds)
            return
        deferred = Deferred()
        deferred.addCallback(self.clientReadyForHandStart, playerNames, rotateWinds)
        self.readyHandQuestion = ReadyHandQuestion(deferred, InternalParameters.field)
        self.readyHandQuestion.show()
        return deferred

    def clientReadyForHandStart(self, dummy, playerNames, rotateWinds):
        """callback, called after the client player said yes, I am ready"""
        return Client.readyForHandStart(self, playerNames, rotateWinds)

    def ask(self, move, answers):
        """server sends move. We ask the user. answers is a list with possible answers,
        the default answer being the first in the list."""
        if not InternalParameters.field:
            return Client.ask(self, move, answers)
        self.computeSayable(move, answers)
        deferred = Deferred()
        deferred.addCallback(self.answered)
        deferred.addErrback(self.answerError, move, answers)
        iAmActive = self.game.myself == self.game.activePlayer
        self.game.myself.handBoard.setEnabled(iAmActive)
        field = InternalParameters.field
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
        """which possible chow do we want to expose?"""
        if self.game.autoPlay:
            return self.intelligence.selectChow(chows)
        if len(chows) == 1:
            return chows[0]
        if PREF.propose:
            propose = self.intelligence.selectChow(chows)
        else:
            propose = None
        selDlg = SelectChow(chows, propose)
        assert selDlg.exec_()
        return selDlg.selectedChow

    def selectKong(self, kongs):
        """which possible kong do we want to declare?"""
        if self.game.autoPlay:
            return self.intelligence.selectKong(kongs)
        if len(kongs) == 1:
            return kongs[0]
        selDlg = SelectKong(kongs)
        assert selDlg.exec_()
        return selDlg.selectedKong

    def answered(self, answer):
        """the user answered our question concerning move"""
        myself = self.game.myself
        if answer in [Message.Discard, Message.OriginalCall]:
            # do not remove tile from hand here, the server will tell all players
            # including us that it has been discarded. Only then we will remove it.
            myself.handBoard.setEnabled(False)
            return answer.name, myself.handBoard.focusTile.element
        args = self.sayable[answer]
        if answer == Message.Chow:
            args = self.selectChow(args)
        if answer == Message.Kong:
            args = self.selectKong(args)
        assert args
        self.game.hidePopups()
        return answer.name, args

    def answerError(self, answer, move, answers):
        """an error happened while determining the answer to server"""
        logException('%s %s %s %s' % (self.game.myself.name, answer, move, answers))

    def remote_abort(self, tableid, message, *args):
        """the server aborted this game"""
        if self.table and self.table.tableid == tableid:
            # translate ROBOT to Roboter:
            args = [m18nc('kajongg', x) for x in args]
            logWarning(m18n(message, *args))
            if self.game:
                self.game.close()
                if self.game.autoPlay:
                    if InternalParameters.field:
                        InternalParameters.field.quit()

    def remote_gameOver(self, tableid, message, *args):
        """the game is over"""
        assert self.table and self.table.tableid == tableid
        if self.table and self.table.tableid == tableid:
            if not self.game.autoPlay:
                logInfo(m18n(message, *args), showDialog=True)
            if self.game:
                self.game.rotateWinds()
                if InternalParameters.csv:
                    gameWinner = max(self.game.players, key=lambda x: x.balance)
                    writer = csv.writer(open(InternalParameters.csv,'a'), delimiter=';')
                    row = [InternalParameters.AI, str(self.game.seed), ','.join(self.game.csvTags)]
                    for player in sorted(self.game.players, key=lambda x: x.name):
                        row.append(player.name)
                        row.append(player.balance)
                        row.append(player.wonCount)
                        row.append(1 if player == gameWinner else 0)
                    writer.writerow(row)
                    del writer
                if self.game.autoPlay and InternalParameters.field:
                    InternalParameters.field.quit()
                else:
                    self.game.close().addCallback(Client.quitProgram)

    def remote_serverDisconnects(self):
        """the kajongg server ends our connection. We remove ourself
        fromt the list of clients, so we might disappear anytime"""
        self.perspective = None
        if self in self.clients:
            self.clients.remove(self)

    def loginCommand(self, username):
        """send a login command to server. That might be a normal login
        or adduser/deluser/change passwd encoded in the username"""
        factory = pb.PBClientFactory()
        reactor = InternalParameters.reactor
        if self.useSocket and os.name != 'nt':
            self.connector = reactor.connectUNIX(socketName(), factory, timeout=2)
        else:
            self.connector = reactor.connectTCP(self.loginDialog.host, self.loginDialog.port, factory, timeout=5)
        utf8Password = self.loginDialog.password.encode('utf-8')
        utf8Username = username.encode('utf-8')
        cred = credentials.UsernamePassword(utf8Username, utf8Password)
        return factory.login(cred, client=self)

    def adduser(self, url, name, passwd):
        """create a user account"""
        assert url is not None
        if url != Query.localServerName:
            adduserDialog = AddUserDialog(url,
                self.loginDialog.username,
                self.loginDialog.password)
            if not adduserDialog.exec_():
                raise Exception(m18n('Aborted creating a user account'))
            passwd = adduserDialog.password
        self.loginDialog.password = passwd
        adduserCmd = SERVERMARK.join(['adduser', name, passwd])
        return self.loginCommand(adduserCmd).addCallback(
            self.adduserOK).addErrback(self._loginReallyFailed)

    def _prettifyErrorMessage(self, failure):
        """instead of just failure.getErrorMessage(), return something more user friendly.
        That will be a localized error text, the original english text will be removed"""
        url = self.url
        message = failure.getErrorMessage()
        match = re.search(r".*gaierror\(-\d, '(.*)'.*", message)
        if not match:
            match = re.search(r".*ConnectError\('(.*)',\)", message)
        if not match:
            match = re.search(r".*ConnectionRefusedError\('(.*)',\)", message)
        if not match:
            match = re.search(r".*DNS lookup.*\[Errno -5\] (.*)", message)
            if match:
                url = url.split(':')[0] # remove the port
        if not match:
            match = re.search(r".*while connecting: 113: (.*)", message)
        if match:
            message = match.group(1).decode('string-escape').decode('string-escape')
        return u'%s: %s' % (url, message.decode('utf-8'))

    def _loginFailed(self, failure):
        """login failed"""
        message = failure.getErrorMessage()
        dlg = self.loginDialog
        if 'Wrong username' in message:
            url, name, passwd = dlg.url, dlg.username, dlg.password
            host = url.split(':')[0]
            msg = m18nc('USER is not known on SERVER',
                '%1 is not known on %2, do you want to open an account?', name, host)
            if url == Query.localServerName \
            or KMessageBox.questionYesNo (None, msg) == KMessageBox.Yes:
                return self.adduser(url, name, passwd)
        else:
            self._loginReallyFailed(failure)

    def _loginReallyFailed(self, failure):
        """login failed, not fixable by adding missing user"""
        message = self._prettifyErrorMessage(failure)
        InternalParameters.reactor.setEnabled(False)
        try:
            logWarning(message)
        finally:
            InternalParameters.reactor.setEnabled(True)

    def adduserOK(self, dummyFailure):
        """adduser succeeded"""
        Players.createIfUnknown(self.username)
        self.login()

    def login(self):
        """login to server"""
        self.root = self.loginCommand(self.username)
        self.root.addCallback(self.loggedIn).addErrback(self._loginFailed)

    def loggedIn(self, perspective):
        """callback after the server answered our login request"""
        self.perspective = perspective
        self.tableList = TableList(self)
        self.updateServerInfoInDatabase()
        voiceId = None
        if PREF.uploadVoice:
            voice = Voice.locate(self.username)
            if voice:
                voiceId = voice.md5sum
            if Debug.sound and voiceId:
                logDebug('%s sends own voice %s to server' % (self.username, voiceId))
        maxGameId = Query('select max(id) from game').records[0][0]
        maxGameId = int(maxGameId) if maxGameId else 0
        self.callServer('setClientProperties',
            str(Query.dbhandle.databaseName()),
            voiceId, maxGameId, InternalParameters.version). \
                addErrback(self.versionError). \
                addCallback(self.callServer, 'sendTables'). \
                addCallback(self.tableList.gotTables)

    @staticmethod
    def versionError(err):
        """log the twisted error"""
        logWarning(err.getErrorMessage())
        InternalParameters.field.abortGame()
        return err

    def updateServerInfoInDatabase(self):
        """we are online. Update table server."""
        lasttime = datetime.datetime.now().replace(microsecond=0).isoformat()
        url = english(self.url) # use unique name for Local Game
        with Transaction():
            serverKnown = Query('update server set lastname=?,lasttime=? where url=?',
                list([self.username, lasttime, url])).rowcount() == 1
            if not serverKnown:
                Query('insert into server(url,lastname,lasttime) values(?,?,?)',
                    list([url, self.username, lasttime]))
        # needed if the server knows our name but our local data base does not:
        Players.createIfUnknown(self.username)
        playerId = Players.allIds[self.username]
        with Transaction():
            if Query('update passwords set password=? where url=? and player=?',
                list([self.loginDialog.password, url, playerId])).rowcount() == 0:
                Query('insert into passwords(url,player,password) values(?,?,?)',
                    list([url, playerId, self.loginDialog.password]))

    @apply
    def host():
        """the host name of the server"""
        def fget(self):
            if not self.connector:
                return None
            dest = self.connector.getDestination()
            if isinstance(dest, UNIXAddress):
                return Query.localServerName
            else:
                return dest.host
        return property(**locals())

    @apply
    def port():
        """the port name of the server"""
        def fget(self):
            if not self.connector:
                return None
            dest = self.connector.getDestination()
            if isinstance(dest, UNIXAddress):
                return None
            else:
                return dest.port
        return property(**locals())

    @apply
    def url():
        """the url of the server"""
        def fget(self):
            # pylint: disable=W0212
            if not self.connector:
                return None
            return self.__url
        return property(**locals())

    def logout(self):
        """clean visual traces and logout from server"""
        result = None
        if self.perspective:
            result = self.callServer('logout')
        field = InternalParameters.field
        if field:
            field.hideGame()
        if self.readyHandQuestion:
            self.readyHandQuestion.hide()
        if self.table and self.table.chatWindow:
            self.table.chatWindow.hide()
            self.table.chatWindow = None
        return result or succeed(None)

    def callServer(self, *args):
        """if we are online, call server"""
        if self.perspective:
            if args[0] is None:
                args = args[1:]
            try:
                if Debug.traffic:
                    if self.game:
                        self.game.debug('callServer(%s)' % repr(args))
                    else:
                        logDebug('callServer(%s)' % repr(args))
                return self.perspective.callRemote(*args)
            except pb.DeadReferenceError:
                self.perspective = None
                self.clients.remove(self)
                logWarning(m18n('The connection to the server %1 broke, please try again later.',
                                  self.url))

    def sendChat(self, chatLine):
        """send chat message to server"""
        self.callServer('chat', chatLine.serialize())
