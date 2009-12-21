#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""
Copyright (C) 2009 Wolfgang Rohdewald <wolfgang@rohdewald.de>

kmj is free software you can redistribute it and/or modify
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

import socket, subprocess

from twisted.spread import pb
from twisted.cred import credentials
from twisted.internet.defer import Deferred
from PyQt4.QtCore import SIGNAL,  SLOT, Qt, QSize, QTimer
from PyQt4.QtGui import QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QGridLayout, \
    QLabel, QComboBox, QLineEdit, QPushButton, QPalette, QGraphicsProxyWidget, QGraphicsRectItem, \
    QWidget, QPixmap, QProgressBar, QColor, QGraphicsItem

from PyKDE4.kdeui import KDialogButtonBox
from PyKDE4.kdeui import KMessageBox

from util import m18n, m18nc,  logWarning, logException, logMessage
import syslog
from scoringengine import Ruleset, PredefinedRuleset, HandContent
from game import Players, RemoteGame
from query import Query
from move import Move
from board import Board
from tile import Tile

class Login(QDialog):
    """login dialog for server"""
    def __init__(self):
        QDialog.__init__(self, None)
        self.setWindowTitle(m18n('Login') + ' - kmj')
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
        lblPassword = QLabel(m18n('Password:'))
        grid.addWidget(lblPassword, 2, 0)
        self.edPassword = QLineEdit()
        self.edPassword.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        grid.addWidget(self.edPassword, 2, 1)
        lblPassword.setBuddy(self.edPassword)
        vbox.addLayout(grid)
        vbox.addWidget(self.buttonBox)

        # now load data:
        self.servers = Query('select url, lastname from server order by lasttime desc').data
        if not self.servers:
            self.servers = [('localhost:8082', ''), ]
        for server in self.servers:
            self.cbServer.addItem(server[0])
        if self.cbServer.count() == 0:
            self.cbServer.addItem('localhost')
        self.connect(self.cbServer, SIGNAL('editTextChanged(QString)'), self.serverChanged)
        self.connect(self.cbUser, SIGNAL('editTextChanged(QString)'), self.userChanged)
        self.serverChanged()

    def serverChanged(self, text=None):
        Players.load()
        self.cbUser.clear()
        self.cbUser.addItems(list(x[1] for x in Players.allNames.values() if x[0] == self.host))
        self.setServerDefaults(0)

    def setServerDefaults(self, idx):
        """set last username and password for the selected server"""
        userIdx = self.cbUser.findText(self.servers[idx][1])
        if userIdx >= 0:
            self.cbUser.setCurrentIndex(userIdx)

    def userChanged(self, text):
        if text == '':
            return
        passw = Query("select password from player where host='%s' and name='%s'" % \
            (self.host, str(text))).data
        if passw:
            self.edPassword.setText(passw[0][0])
        else:
            self.edPassword.clear()

    @apply
    def host():
        def fget(self):
            hostargs = str(self.cbServer.currentText()).rpartition(':')
            return ''.join(hostargs[0])
        return property(**locals())

    @apply
    def port():
        def fget(self):
            hostargs = str(self.cbServer.currentText()).rpartition(':')
            return int(hostargs[2])
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

class ClientDialog(QDialog):
    """a simple popup dialog for asking the player what he wants to do"""
    def __init__(self, client):
        QDialog.__init__(self)
        self.client = client
        self.layout = QGridLayout(self)
        self.btnLayout = QHBoxLayout()
        self.layout.addLayout(self.btnLayout, 0, 0)
        self.progressBar = QProgressBar()
        self.timer = QTimer()
        self.timeCtr = 0
        self.connect(self.timer, SIGNAL('timeout()'), self.timeout)
        self.layout.addWidget(self.progressBar, 1, 0)
        self.layout.setAlignment(self.btnLayout, Qt.AlignCenter)
        self.move = None
        self.deferred = None
        self.orderedButtons = []
        self.visibleButtons = []
        self.buttons = {}
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.__default = None
        self.__declareButton('noClaim', m18nc('kmj','Do &not claim'))
        self.__declareButton('discard', m18nc('kmj','&Discard'))
        self.__declareButton('callPung', m18nc('kmj','&Pung'))
        self.__declareButton('callKong', m18nc('kmj','&Kong'))
        self.__declareButton('callChow', m18nc('kmj','&Chow'))
        self.__declareButton('declareKong', m18nc('kmj','&Kong'))
        self.__declareButton('declareMJ', m18nc('kmj','&Mah Jongg'))

    def keyPressEvent(self, event):
        """this is called by Board.keyPressEvent"""
        key = event.key()
        idx = self.visibleButtons.index(self.default)
        if key == Qt.Key_Up:
            if idx > 0:
                idx -= 1
        elif key == Qt.Key_Down:
            if idx < len(self.visibleButtons) - 1:
                idx += 1
        else:
            return QDialog.keyPressEvent(self, event)
        self.default = self.visibleButtons[idx]

    @apply
    def default():
        def fget(self):
            return self.__default
        def fset(self, default):
            self.__default = default
            for button in self.buttons.values():
                palette = button.palette()
                if button == default:
                    btnColor = QColor('lightblue')
                else:
                    btnColor = self.btnColor
                palette.setColor(QPalette.Button, btnColor)
                button.setPalette(palette)
        return property(**locals())

    def __declareButton(self, name, caption):
        """define a button"""
        btn = QPushButton(self)
        btn.setVisible(False)
        btn.setObjectName(name)
        btn.setText(caption)
        self.btnLayout.addWidget(btn)
        btn.setAutoDefault(True)
        self.connect(btn, SIGNAL('clicked(bool)'), self.selectedAnswer)
        self.orderedButtons.append(btn)
        font = btn.font()
        font.setPointSize(18)
        btn.setFont(font)
        self.buttons[name] = btn
        self.btnColor = btn.palette().color(QPalette.Button)

    def ask(self, move, answers, deferred, tile=None):
        """make buttons specified by answers visible. The first answer is default.
        The default button only appears with blue border when this dialog has
        focus but we always want it to be recognizable. Hence setBackgroundRole."""
        self.move = move
        self.deferred = deferred
        self.default = self.buttons[answers[0]]
        self.visibleButtons = []
        for btn in self.orderedButtons:
            name = btn.objectName()
            btn.setVisible(name in answers)
            if name in answers:
                self.visibleButtons.append(btn)
            btn.setEnabled(name in answers)
        self.show()
        self.client.clientDialog.show()
        needTimer = self.client.game.activePlayer != self.client.game.myself
        print needTimer, self.client.game.activePlayer, self.client.game.myself

        self.progressBar.setVisible(needTimer)
        if needTimer:
            self.progressBar.setMinimum(0)
            self.progressBar.setMaximum(self.client.game.ruleset.claimTimeout * 10)
            self.progressBar.reset()
            self.timeCtr = 0
            self.timer.start(100)

    def timeout(self):
        """the progressboard wants an update"""
        pBar = self.progressBar
        pBar.setValue(pBar.value()+1)
        if pBar.value() == pBar.maximum():
            self.selectDefault()

    def selectDefault(self):
        """select default answer"""
        self.timer.stop()
        answer = str(self.default.objectName())
        self.deferred.callback(answer)
        self.hide()

    def selectedAnswer(self, checked):
        """the user clicked one of the buttons"""
        self.default = self.sender()
        self.selectDefault()

class Client(pb.Referenceable):
    """interface to the server. This class only implements the logic,
    so we can also use it on the server for robot clients. Compare
    with HumanClient(Client)"""

    def __init__(self, username=None):
        """username is something like ROBOT 1"""
        self.username = username
        self.game = None
        self.host = 'SERVER'

    def readyForStart(self, tableid, playerNames):
        rulesets = Ruleset.availableRulesets() + PredefinedRuleset.rulesets()
        self.game = RemoteGame(self.host, playerNames.split('//'), rulesets[0])
        for player in self.game.players:
            if player.name == self.username:
                self.game.myself = player
        self.game.client = self

    def ask(self, move, answers):
        """this is where the robot AI should go"""
        answer = answers[0] # for now always return default answer
        if answer == 'discard':
            # do not remove tile from hand here, the server will tell all players
            # including us that it has been discarded. Only then we will remove it.
            string = ''.join(move.player.concealedTiles)
            hand = HandContent.cached(self.game.ruleset, string)
            for meldLen in range(1, 3):
                melds = [x for x in hand.melds if len(x) == meldLen]
                if melds:
                    meld = melds[-1]
                    tileName = meld.contentPairs[-1] # TODO: need AI
                    return 'discard', tileName
            raise Exception('Player %s has nothing to discard:%s' % (
                            move.player.name, string))
        else:
            # the other responses do not have a parameter
            return answer

    def remote_move(self, tableid, playerName, command, **kwargs):
        """the server sends us info or a question and always wants us to answer"""
        player = None
        thatWasMe = False
        if self.game:
            for p in self.game.players:
                if p.name == playerName:
                    player = p
            if not player:
                raise Exception('Move references unknown player %s' % playerName)
            thatWasMe = player == self.game.myself
        print self.username + ': ', player, command, kwargs
        move = Move(player, command, kwargs)
        if command == 'readyForStart':
            return self.readyForStart(tableid, move.source)
        elif command == 'setDiceSum':
            self.game.diceSum = move.source
            self.game.showField()
        elif command == 'setTiles':
            self.game.setTiles(player, move.source)
        elif command == 'activePlayer':
            self.game.activePlayer = player
        elif command == 'pickedTile':
            self.game.pickedTile(player, move.source)
            if thatWasMe:
                return self.ask(move, ['discard', 'declareKong', 'declareMJ'])
        elif command == 'hasDiscarded':
            self.game.hasDiscarded(player, move.tile)
            if not thatWasMe:
                return self.ask(move, ['noClaim', 'callChow', 'callPung', 'callKong', 'declareMJ'])
        elif command in ['calledChow', 'calledPung', 'calledKong', 'declaredMJ']:
            self.game.calledTile(player, command)
            if thatWasMe:
                if command == 'calledKong':
                    return 'declareKong'
                if command == 'declaredMJ':
                    return
                return self.ask(move, ['discard',  'declareMJ'])
        elif command == 'error':
            if isinstance(self, HumanClient):
                logWarning(move.source) # show messagebox
            else:
                logMessage(move.source, prio=syslog.LOG_WARNING)

class HumanClient(Client):
    def __init__(self, tableList, callback=None):
        Client.__init__(self)
        self.tableList = tableList
        self.tables = []
        self.callback = callback
        self.perspective = None
        self.connector = None
        self.table = None
        self.discardBoard = tableList.field.discardBoard
        self.serverProcess = None
        self.clientDialog = None
        self.login = Login()
        if self.login.host == 'localhost':
            if not self.serverListening():
                self.startLocalServer()

        if not self.login.exec_():
            raise Exception(m18n('Login aborted'))
        self.username = self.login.username
        self.root = self.connect()
        self.root.addCallback(self.connected).addErrback(self._loginFailed)
        field = self.tableList.field
        scene = field.centralScene
        wall0 = field.walls[0]
        for child in scene.items():
            if isinstance(child, QGraphicsProxyWidget) and isinstance(child.widget(), ClientDialog):
                self.clientDialog = child.widget()
                break
        if not self.clientDialog:
            self.clientDialog = ClientDialog(self)
            proxy = scene.addWidget(self.clientDialog)
            proxy.setZValue(1e20)
            proxy.setPos(wall0.scenePos())
            proxy.translate(0.0, 50.0)
            proxy.scale(1.5, 1.5)
            proxy.hide()

    def serverListening(self):
        """is somebody listening on that port?"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            sock.connect((self.login.host, self.login.port))
        except socket.error:
            return False
        else:
            return True

    def startLocalServer(self):
        """start a local server"""
        try:
            self.serverProcess = subprocess.Popen(['./server.py'])
            print 'started the local kmj server: pid=%d' % self.serverProcess.pid
        except Exception as exc:
            logException(exc)

    def __del__(self):
        if self.serverProcess:
            print 'killing the local kmj server'
            self.serverProcess.kill()

    def remote_tablesChanged(self, tables):
        """update table list"""
        self.tables = tables
        self.tableList.load(tables)

    def readyForStart(self, tableid, playerNames):
        """playerNames are in wind order ESWN"""
        self.table = None
        msg = m18n("The game can begin. Are you ready to play now?\n" \
            "If you answer with NO, you will be removed from the table.")
        if KMessageBox.questionYesNo (None, msg) == KMessageBox.Yes:
            for table in self.tables:
                if table[0] == tableid:
                    self.table = table
                    field = self.tableList.field
                    # TODO: ruleset should come from the server
                    rulesets = Ruleset.availableRulesets() + PredefinedRuleset.rulesets()
                    self.game = RemoteGame(self.host, playerNames.split('//'), rulesets[0],  field=field)
                    for player in self.game.players:
                        if player.name == self.username:
                            self.game.myself = player
                    self.game.client = self
        return self.table is not None

    def ask(self, move, answers):
        """server sends move. We ask the user. answers is a list with possible answers,
        the default answer being the first in the list."""
        deferred = Deferred()
        deferred.addCallback(self.answered, move)
        handBoard = self.game.myself.handBoard
        if move.command in ('discard', 'pickedTile'):
            handBoard.focusTile.setFocus()
        else:
            handBoard.focusTile = None # this is not about a tile we have
            handBoard.setFlag(QGraphicsItem.ItemIsFocusable, True)
            handBoard.setFocus() # handBoard catches the Space key
        self.clientDialog.ask(move, answers, deferred)
        return deferred

    def answered(self, answer, move):
        """the user answered our question concerning move"""
        if answer == 'discard':
            # do not remove tile from hand here, the server will tell all players
            # including us that it has been discarded. Only then we will remove it.
            return answer, self.game.myself.handBoard.focusTile.element
        else:
            # the other responses do not have a parameter
            return answer

    def checkRemoteArgs(self, tableid):
        """as the name says"""
        if self.table and tableid != self.table[0]:
            raise Exception('HumanClient.remote_move for wrong tableid %d instead %d' % \
                            (tableid,  self.table[0]))

    def remote_move(self, tableid, playerName, command, **args):
        """the server sends us info or a question and always wants us to answer"""
        self.checkRemoteArgs(tableid)
        return Client.remote_move(self, tableid, playerName, command,  **args)

    def remote_abort(self, tableid):
        """the server aborted this game"""
        print 'abort:', type(tableid), tableid
        self.checkRemoteArgs(tableid)
        self.game.field.game = None

    def remote_serverDisconnects(self):
        """the kmj server ends our connection"""
        self.perspective = None

    def connect(self):
        """connect self to server"""
        factory = pb.PBClientFactory()
        self.connector = self.tableList.field.reactor.connectTCP(self.login.host, self.login.port, factory)
        cred = credentials.UsernamePassword(self.login.username,  self.login.password)
        self.login = None  # no longer needed
        return factory.login(cred, client=self)

    def _loginFailed(self, failure):
        """login failed"""
        self.login = None  # no longer needed
        logWarning(failure.getErrorMessage())
        if self.callback:
            self.callback()

    def connected(self, perspective):
        """we are online"""
        self.perspective = perspective
        if self.callback:
            self.callback()

    @apply
    def host():
        def fget(self):
            return self.connector.getDestination().host
        return property(**locals())

    def logout(self):
        """clean visual traces and logout from server"""
        self.remote('logout')
        self.discardBoard.setVisible(False)
        self.clientDialog.hide()

    def remote(self, *args):
        """if we are online, call remote"""
        if self.perspective:
            try:
                return self.perspective.callRemote(*args)
            except pb.DeadReferenceError:
                self.perspective = None
                logWarning(m18n('The connection to the server %1 broke, please try again later.',
                                  self.host))
