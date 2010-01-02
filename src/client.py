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

import socket, subprocess, time

from twisted.spread import pb
from twisted.cred import credentials
from twisted.internet.defer import Deferred
from PyQt4.QtCore import SIGNAL,  SLOT, Qt, QSize, QTimer, QPoint
from PyQt4.QtGui import QDialog, QDialogButtonBox, QLayout, QVBoxLayout, QHBoxLayout, QGridLayout, \
    QLabel, QComboBox, QLineEdit, QPushButton, QPalette, QGraphicsProxyWidget, QGraphicsRectItem, \
    QWidget, QPixmap, QProgressBar, QColor, QGraphicsItem, QRadioButton, QApplication

from PyKDE4.kdeui import KDialogButtonBox
from PyKDE4.kdeui import KMessageBox

import util
from util import m18n, m18nc, m18ncE, logWarning, logException, logMessage
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
    def __init__(self, parent):
        QPushButton.__init__(self, parent)
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
        self.setWindowTitle(m18n('Choose') + ' - kmj')
        self.client = client
        self.layout = QGridLayout(self)
        self.btnLayout = QHBoxLayout()
        self.layout.addLayout(self.btnLayout, 0, 0)
        self.progressBar = QProgressBar()
        self.timer = QTimer()
        self.connect(self.timer, SIGNAL('timeout()'), self.timeout)
        self.layout.addWidget(self.progressBar, 1, 0)
        self.layout.setAlignment(self.btnLayout, Qt.AlignCenter)
        self.move = None
        self.deferred = None
        self.orderedButtons = []
        self.visibleButtons = []
        self.buttons = {}
        self.btnColor = None
        self.default = None
        self.__declareButton(m18ncE('kmj','&No Claim'))
        self.__declareButton(m18ncE('kmj','&Discard'))
        self.__declareButton(m18ncE('kmj','&Pung'))
        self.__declareButton(m18ncE('kmj','&Kong'))
        self.__declareButton(m18ncE('kmj','&Chow'))
        self.__declareButton(m18ncE('kmj','&Mah Jongg'))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.default = self.buttons[self.answers[0]]
            self.selectDefault()
            event.accept()
        else:
            QDialog.keyPressEvent(self, event)

    def __declareButton(self, caption):
        """define a button"""
        btn = DlgButton(self)
        btn.setVisible(False)
        name = caption.replace('&', '')
        btn.setObjectName(name)
        btn.setText(m18n(caption))
        self.btnLayout.addWidget(btn)
        btn.setAutoDefault(True)
        self.connect(btn, SIGNAL('clicked(bool)'), self.selectedAnswer)
        self.orderedButtons.append(btn)
        self.buttons[name] = btn

    def ask(self, move, answers, deferred, tile=None):
        """make buttons specified by answers visible. The first answer is default.
        The default button only appears with blue border when this dialog has
        focus but we always want it to be recognizable. Hence setBackgroundRole."""
        self.move = move
        self.answers = answers
        self.deferred = deferred
        self.visibleButtons = []
        for btn in self.orderedButtons:
            name = btn.objectName()
            btn.setVisible(name in self.answers)
            if name in self.answers:
                self.visibleButtons.append(btn)
            btn.setEnabled(name in self.answers)
        self.show()
        self.default = self.buttons[self.answers[0]]
        self.default.setFocus()
        myTurn = self.client.game.activePlayer == self.client.game.myself
        if util.PREF.demoMode:
            self.selectDefault()
            return

        self.progressBar.setVisible(not myTurn)
        if myTurn:
            self.client.game.field.centralView.scene().setFocusItem(self.client.game.myself.handBoard.focusTile)
        else:
            msecs = 50
            self.progressBar.setMinimum(0)
            self.progressBar.setMaximum(self.client.game.ruleset.claimTimeout * 1000 / msecs)
            self.progressBar.reset()
            self.timer.start(msecs)

    def showEvent(self, event):
        """try to place the dialog such that it does not cover interesting information"""
        if not self.parent().clientDialogGeometry:
            parentG = self.parent().geometry()
            parentHeight = parentG.height()
            geometry = self.geometry()
            geometry.moveTop(parentG.y() + 30)
            geometry.moveLeft(parentG.x() + parentG.width()/2) # - self.width()/2)
            self.parent().clientDialogGeometry = geometry
        self.setGeometry(self.parent().clientDialogGeometry)

    def timeout(self):
        """the progressboard wants an update"""
        pBar = self.progressBar
        pBar.setValue(pBar.value()+1)
        pBar.setVisible(True)
        if pBar.value() == pBar.maximum():
            # timeout: we always return the original default answer, not the one with focus
            self.default = self.buttons[self.answers[0]]
            self.selectDefault()
            pBar.setVisible(False)

    def selectDefault(self):
        """select default answer"""
        self.timer.stop()
        answer = str(self.default.objectName())
        self.deferred.callback(answer)
        self.parent().clientDialogGeometry = self.geometry()
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
        self.game.myself = self.game.players.byName(self.username)
        self.game.client = self

    def answer(self, answer, meld):
        if not isinstance(self, HumanClient):
            self.table.claim(self.username, answer)
        return answer, meld

    def ask(self, move, answers):
        """this is where the robot AI should go"""
        game = self.game
        myself = game.myself
        if 'Kong' in answers:
            if game.activePlayer == myself:
                for tryTile in set(myself.concealedTiles):
                    if tryTile[0] not in 'fy':
                        meld = myself.containsPossibleKong(tryTile)
                        if meld:
                            break
            else:
                meld = myself.possibleKong(game.lastDiscard)
            if meld:
                return self.answer('Kong', meld)
        if 'Pung' in answers:
            meld = myself.possiblePung(game.lastDiscard)
            if meld:
                return self.answer('Pung', meld)
        if 'Chow' in answers:
            for chow in myself.possibleChows(game.lastDiscard):
                belongsToPair = False
                for tileName in chow:
                    if myself.concealedTiles.count(tileName) == 2:
                        belongsToPair = True
                        break
                if not belongsToPair:
                    return self.answer('Chow', chow)

        answer = answers[0] # for now always return default answer
        if answer == 'Discard':
            # do not remove tile from hand here, the server will tell all players
            # including us that it has been discarded. Only then we will remove it.
            hand = move.player.hand()
            # TODO: also check what has been discarded an exposed
            for meldLen in range(1, 3):
                melds = [x for x in hand.hiddenMelds if len(x) == meldLen]
                if melds:
                    meld = melds[-1]
                    tileName = meld.contentPairs[-1]
                    return 'Discard', tileName
            raise Exception('Player %s has nothing to discard:%s' % (
                            move.player.name, string))
        else:
            # the other responses do not have a parameter
            return answer

    def hidePopups(self):
        """hide all popup messages"""
        for player in self.game.players:
            player.hidePopup()

    def remote_move(self, tableid, playerName, command, **kwargs):
        """the server sends us info or a question and always wants us to answer"""
        player = None
        thatWasMe = False
        if self.game:
            if not self.game.client:
                # we aborted the game, ignore what the server tells us
                return
            for p in self.game.players:
                if p.name == playerName:
                    player = p
            if not player:
                raise Exception('Move references unknown player %s' % playerName)
            myself = self.game.myself
            thatWasMe = player == myself
        print self.username + ': ', player, command, kwargs
        move = Move(player, command, kwargs)
        if command == 'readyForStart':
            return self.readyForStart(tableid, move.source)
        elif command == 'setDivide':
            self.game.divideAt = move.source
            self.game.showField()
        elif command == 'setTiles':
            self.game.setTiles(player, move.source)
        elif command == 'showTiles':
            self.game.showTiles(player, move.source)
        elif command == 'popupMsg':
            return player.popupMsg(move.msg)
        elif command == 'activePlayer':
            self.game.activePlayer = player
        elif command == 'pickedTile':
            self.hidePopups()
            if not move.deadEnd:
                self.game.lastDiscard = None
            self.game.pickedTile(player, move.source, move.deadEnd)
            if thatWasMe:
                if move.source[0] in 'fy':
                    return 'Bonus', move.source
                if self.game.lastDiscard:
                    return self.ask(move, ['Discard', 'Mah Jongg'])
                else:
                    return self.ask(move, ['Discard', 'Kong', 'Mah Jongg'])
        elif command == 'pickedBonus':
            if not thatWasMe:
                player.makeTilesKnown(move.source)
        elif command == 'declaredKong':
            if not thatWasMe:
                player.makeTilesKnown(move.source)
            player.exposeMeld(move.source, claimed=False)
        elif command == 'hasDiscarded':
            self.game.hasDiscarded(player, move.tile)
            if not thatWasMe:
                if self.game.IAmNext():
                    return self.ask(move, ['No Claim', 'Chow', 'Pung', 'Kong', 'Mah Jongg'])
                else:
                    return self.ask(move, ['No Claim', 'Pung', 'Kong', 'Mah Jongg'])
        elif command in ['calledChow', 'calledPung', 'calledKong']:
            assert self.game.lastDiscard in move.source, '%s %s'% (self.game.lastDiscard, move.source)
            if isinstance(self, HumanClient):
                self.discardBoard.lastDiscarded.board = None
                self.discardBoard.lastDiscarded = None
            if thatWasMe:
                player.addTile(self.game.lastDiscard)
            else:
                player.addTile('XY')
                player.makeTilesKnown(move.source)
            player.exposeMeld(move.source)
            if thatWasMe:
                if command != 'calledKong':
                    # we will get a replacement tile first
                    return self.ask(move, ['Discard', 'Mah Jongg'])
            elif self.game.prevActivePlayer == myself and isinstance(self, HumanClient):
                # even here we ask otherwise if all other players are robots we would
                # have no time to see it if the next player calls Chow
                return self.ask(move, ['No Claim'])
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
                    self.game.myself = self.game.players.byName(self.username)
                    self.game.client = self
        return self.table is not None

    def ask(self, move, answers):
        """server sends move. We ask the user. answers is a list with possible answers,
        the default answer being the first in the list."""
        self.answers = answers
        deferred = Deferred()
        deferred.addCallback(self.answered, move)
        handBoard = self.game.myself.handBoard
        IAmActive = self.game.myself == self.game.activePlayer
        handBoard.setEnabled(IAmActive)
        if not self.clientDialog or not self.clientDialog.isVisible():
            self.clientDialog = ClientDialog(self, self.game.field)
        self.clientDialog.setModal(not IAmActive)
        self.clientDialog.ask(move, answers, deferred)
        return deferred

    def selectChow(self, chows):
        """which possible chow do we want to expose?"""
        if len(chows) == 1:
            return chows[0]
        selDlg = SelectChow(chows)
        assert selDlg.exec_()
        return selDlg.selectedChow

    def answered(self, answer, move):
        """the user answered our question concerning move"""
        if util.PREF.demoMode:
            return Client.ask(self, move, self.answers)
        message = None
        myself = self.game.myself
        focusTile = myself.handBoard.focusTile.element
        try:
            if answer == 'Discard':
                # do not remove tile from hand here, the server will tell all players
                # including us that it has been discarded. Only then we will remove it.
                return answer, focusTile
            elif answer == 'Chow':
                chows = myself.possibleChows(self.game.lastDiscard)
                if len(chows):
                    meld = self.selectChow(chows)
                    self.remote('claim', self.table[0], answer)
                    return answer, meld
                message = m18n('You cannot call Chow for this tile')
            elif answer == 'Pung':
                meld = myself.possiblePung(self.game.lastDiscard)
                if meld:
                    self.remote('claim', self.table[0], answer)
                    return answer, meld
                message = m18n('You cannot call Pung for this tile')
            elif answer == 'Kong':
                if self.game.activePlayer == myself:
                    meld = myself.containsPossibleKong(focusTile)
                    if meld:
                        self.remote('claim', self.table[0], answer)
                        return answer, meld
                    message = m18n('You cannot declare Kong, you need to have 4 identical tiles')
                else:
                    meld = myself.possibleKong(self.game.lastDiscard)
                    if meld:
                        self.remote('claim', self.table[0], answer)
                        return answer, meld
                    message = m18n('You cannot call Kong for this tile')
            elif answer == 'Mah Jongg':
                # TODO: introduce player.tileSource and update it whenever adding a tile to player
                if self.game.lastDiscard:
                    myself.concealedTiles.append(self.game.lastDiscard)
                hand = myself.hand()
                if self.game.lastDiscard:
                    myself.concealedTiles.remove(self.game.lastDiscard)

                print 'MJ:hand:', hand
                print 'MJ:hiddenMelds:', hand.hiddenMelds
                if hand.maybeMahjongg():
                    return answer, hand.hiddenMelds
                message = m18n('You cannot say Mah Jongg with this hand')
            else:
                # the other responses do not have a parameter
                return answer
        finally:
            if message:
                KMessageBox.sorry(None, message)
                self.clientDialog.hide()
                return self.ask(move, self.clientDialog.answers)
            else:
                self.hidePopups()

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
        if self.clientDialog:
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
