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
from PyQt4.QtCore import SIGNAL,  SLOT
from PyQt4.QtGui import QDialog, QDialogButtonBox, QVBoxLayout, QGridLayout, \
    QLabel, QComboBox, QLineEdit, QPushButton, QPalette

from PyKDE4.kdeui import KDialogButtonBox
from PyKDE4.kdeui import KMessageBox

from util import m18n, logWarning, logException
from scoringengine import Ruleset, PredefinedRuleset
from game import Players, Game
from query import Query
from move import Move
from scoringengine import HandContent

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

class ClientButton(QPushButton):
    """a button for the ClientDialog"""
    def __init__(self, parent=None):
        QPushButton.__init__(self, parent)
    def keyPressEvent(self, event):
        """as soon as we move by key in ClientDialog, unmark the default answer"""
        self.setAutoFillBackground(False)
        self.setBackgroundRole(QPalette.NoRole)
        return QPushButton.keyPressEvent(self, event)

class ClientDialog(QDialog):
    """a simple popup dialog for asking the player what he wants to do"""
    def __init__(self, client):
        QDialog.__init__(self)
        self.client = client
        self.layout = QVBoxLayout(self)
        self.command = None
        self.deferred = None
        self.buttons = {}
        self.__declareButton('discard', m18n('&Discard'))
        self.__declareButton('declareKong', m18n('&Kong'))
        self.__declareButton('declareMJ', m18n('&Mah Jongg'))
        self.__declareButton('noClaim', m18n('Do &not claim'))
        self.__declareButton('callChow', m18n('&Chow'))
        self.__declareButton('callPung', m18n('&Pung'))
        self.__declareButton('callKong', m18n('&Kong'))

    def __declareButton(self, name, caption):
        """define a button"""
        btn = ClientButton()
        btn.setVisible(False)
        btn.setObjectName(name)
        btn.setText(caption)
        self.layout.addWidget(btn)
        btn.setAutoDefault(True)
        self.connect(btn, SIGNAL('clicked(bool)'), self.selected)
        self.buttons[name] = btn

    def prepare(self, command, answers, deferred):
        """make buttons specified by answers visible. The first answer is default.
        The default button only appears with blue border when this dialog has
        focus but we always want it to be recognizable. Hence setBackgroundRole."""
        self.command = command
        self.deferred = deferred
        self.show()
        self.graphicsProxyWidget().show()
        default = self.buttons[answers[0]]
        default.setDefault(True)
        for name, btn in self.buttons.items():
            btn.setVisible(name in answers)
            btn.setEnabled(name in answers)
            btn.setBackgroundRole(QPalette.NoRole)
        default.setAutoFillBackground(True)
        default.setBackgroundRole(QPalette.Highlight)

    def selected(self, checked):
        """the user clicked one of the buttons"""
        button = self.sender()
        self.deferred.callback(str(button.objectName()))
        self.hide()

class Client(pb.Referenceable):
    """interface to the server"""
    def __init__(self, tableList, callback=None):
        self.tableList = tableList
        self.tables = []
        self.callback = callback
        self.perspective = None
        self.connector = None
        self.table = None
        self.game = None
        self.player = None # myself
        self.serverProcess = None
        self.login = Login()
        if self.login.host == 'localhost':
            if not self.serverListening():
                self.startLocalServer()

        if not self.login.exec_():
            raise Exception(m18n('Login aborted'))
        self.username = self.login.username
        self.root = self.connect()
        self.root.addCallback(self.connected).addErrback(self._loginFailed)
        self.askDlg = ClientDialog(self)
        self.askProxy = self.tableList.field.centralScene.addWidget(self.askDlg)
        askItem = self.askProxy
        askItem.hide()
        askItem.scale(3, 3)
        wall0 = self.tableList.field.walls[0]
        wallRect = wall0.mapRectToParent(wall0.rect())
        center = wallRect.width() / 2
        itemRect = askItem.mapRectToParent(askItem.rect())
        askItem.setPos(center - itemRect.width() - itemRect.height()/2 - wallRect.height(), center - itemRect.height())

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

    def remote_readyForStart(self, tableid, playerNames):
        """playerNames are in wind order ESWN"""
        if KMessageBox.questionYesNo (None,
            m18n('The game can begin. Are you ready to play now?')) \
            == KMessageBox.Yes:
            self.table = None
            for table in self.tables:
                if table[0] == tableid:
                    self.table = table
                    field = self.tableList.field
                    # TODO: ruleset should come from the server
                    rulesets = Ruleset.availableRulesets() + PredefinedRuleset.rulesets()
                    self.game = Game(self.host, playerNames.split('//'), rulesets[0],  field=field)
                    self.player = self.game.players[0] # myself
                    self.game.client = self
                else:
                    # if we reserved several seats, give up all others
                    self.remote('leaveTable', table[0])
            self.remote('ready', tableid)

    def gotTiles(self, player, tiles):
        """tiles is a list of paired chars"""
        game = self.game
        field = game.field
        field.walls.removeTiles(len(tiles)//2)
        myBoard = player.handBoard
        newTiles = ''.join(x.element for x in myBoard.allTiles()) + ''.join(tiles)
        myBoard.clear()
        content = HandContent(game.ruleset, newTiles)
        for meld in content.sortedMelds.split():
            myBoard.receive(meld, None, True)
        tiles = [x for x in myBoard.allTiles() if not x.isBonus()]
        if tiles and player.name == self.username:
            myBoard.focusTile = tiles[-1]
        field.centralView.scene().setFocusItem(myBoard.focusTile)

    def putNameAtBottom(self, name):
        """rotate the players until name is at bottom"""
        players = self.game.players
        rotations = 0
        while players[0].name != name:
            rotations += 1
            name0, wind0 = players[0].name, players[0].wind
            for idx in range(4, 0, -1):
                this, prev = players[idx % 4], players[idx - 1]
                this.name, this.wind = prev.name, prev.wind
            players[1].name,  players[1].wind = name0, wind0
        # now we are seated at the bottom
        return rotations

    def showField(self):
        """show current game in field"""
        rotations = self.putNameAtBottom(self.username)
        field = self.game.field
        for tableList in field.tableLists:
            tableList.hide()
        field.tableLists = []
        field.game = self.game
        field.walls.build(rotations, self.game.diceSum)

    def ask(self, command, answers):
        """server sends command. We ask the user. answers is a list with possible answers,
        the default answer being the first in the list."""
        deferred = Deferred()
        deferred.addCallback(self.answered, command)
        self.askDlg.prepare(command, answers, deferred)
        self.askProxy.show()
        return deferred

    def answered(self, answer, command):
        """the user answered our question concerning command"""
        if answer == 'discard':
            # do not remove tile from hand here, the server will tell all players
            # including us that it has been discarded. Only then we will remove it.
            return answer, self.player.handBoard.focusTile.element
        else:
            # the other responses do not have a parameter
            return answer

    def checkRemoteArgs(self, tableid):
        """as the name says"""
        if tableid != self.table[0]:
            raise Exception('Client.remote_move for wrong tableid %d instead %d' % \
                            (tableid,  self.table[0]))

    def remote_move(self, tableid, playerName, command, args):
        """the server sends us info or a question and always wants us to answer"""
        self.checkRemoteArgs(tableid)
        move = Move(self.game, playerName, command, args)
        print 'got move:', playerName, command, args
        player = move.player
        if command == 'setDiceSum':
            self.game.diceSum = move.source
            self.showField()
        elif command == 'setTiles':
            self.gotTiles(player, move.source)
        elif command == 'firstMove':
            if player.name == self.username:
                return self.ask(command, ['discard', 'declareKong', 'declareMJ'])
        elif command == 'hasDiscarded':
            print 'player %s discarded %s' % (player, move.tile)
            self.discardTile(player, move.tile)
        elif command == 'error':
            logWarning(move.source)

    def remote_abort(self, tableid):
        print 'abort:', type(tableid), tableid
        """the server aborted this game"""
        self.checkRemoteArgs(tableid)
        self.game.field.game = None

    def discardTile(self, player, tileName):
        """discards a tile from a player board"""
        self.game.field.discardBoard.addTile(tileName)
        if player.name != self.username: # not myself
            tileName = 'Db'
        tiles = [x.element for x in player.handBoard.allTiles()]
        if not tileName in tiles:
            raise pb.Error('Player %s is told to show discard of tile %s but does not have it' % \
                           (player.name, tileName))
        tiles.remove(tileName)
        player.handBoard.clear()
        self.gotTiles(player, tiles)

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

    def remote(self, *args):
        """if we are online, call remote"""
        if self.perspective:
            try:
                return self.perspective.callRemote(*args)
            except pb.DeadReferenceError:
                self.perspective = None
                logWarning(m18n('The connection to the server %1 broke, please try again later.',
                                  self.login.host))

