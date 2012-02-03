# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2011 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
import csv

from twisted.spread import pb
from twisted.cred import credentials
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure
from twisted.internet.address import UNIXAddress
from PyQt4.QtCore import Qt, QTimer
from PyQt4.QtGui import QDialog, QDialogButtonBox, QVBoxLayout, QGridLayout, \
    QLabel, QComboBox, QLineEdit, QPushButton, QFormLayout, \
    QProgressBar, QRadioButton, QSpacerItem, QSizePolicy

from kde import KMessageBox, KDialogButtonBox, KUser, KIcon

from util import m18n, m18nc, logWarning, logException, socketName, english, \
    appdataDir, logInfo, logDebug
from util import SERVERMARK, isAlive
from message import Message
import common
from common import InternalParameters, PREF, Debug
from game import Players
from query import Transaction, Query
from board import Board
from client import Client
from statesaver import StateSaver
from meld import Meld
from intelligence import INTELLIGENCES
from altint import ALTINTELLIGENCES

from guiutil import ListComboBox
from scoringengine import Ruleset

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
        if self.host == 'localhost':
            # we have localhost if we play a Local Game: client and server are identical,
            # we have no security concerns about creating a new account
            Players.createIfUnknown(unicode(self.cbUser.currentText()))
        QDialog.accept(self)

    def serverChanged(self, dummyText=None):
        """the user selected a different server"""
        records = Query('select player.name from player, passwords '
                'where passwords.url=? and passwords.player = player.id', list([self.host])).records
        self.cbUser.clear()
        self.cbUser.addItems(list(x[0] for x in records))
        if not self.cbUser.count():
            user = KUser() if os.name == 'nt' else KUser(os.geteuid())
            self.cbUser.addItem(user.fullName() or user.loginName())
        hostName = self.host
        userNames = [x[1] for x in self.servers if x[0] == hostName]
        if userNames:
            userIdx = self.cbUser.findText(userNames[0])
            if userIdx >= 0:
                self.cbUser.setCurrentIndex(userIdx)
        showPW = self.host != Query.localServerName
        self.grid.labelForField(self.edPassword).setVisible(showPW)
        self.edPassword.setVisible(showPW)
        self.grid.labelForField(self.cbRuleset).setVisible(not showPW)
        self.cbRuleset.setVisible(not showPW)
        if not showPW:
            self.cbRuleset.clear()
            self.cbRuleset.items = Ruleset.selectableRulesets(self.host)

    def userChanged(self, text):
        """the username has been changed, lookup password"""
        if text == '':
            self.edPassword.clear()
            return
        passw = None
        for entry in self.passwords:
            if entry[0] == self.host and entry[1] == unicode(text):
                passw = entry[2]
        if passw:
            self.edPassword.setText(passw)
        else:
            self.edPassword.clear()

    @apply
    def host():
        """abstracts the host of the dialog"""
        def fget(self):
            text = english(unicode(self.cbServer.currentText()))
            if ':' not in text:
                return text
            hostargs = text.rpartition(':')
            return ''.join(hostargs[0])
        return property(**locals())

    @apply
    def port():
        """abstracts the port of the dialog"""
        def fget(self):
            text = unicode(self.cbServer.currentText())
            if ':' not in text:
                return common.PREF.serverPort
            hostargs = unicode(self.cbServer.currentText()).rpartition(':')
            try:
                return int(hostargs[2])
            except ValueError:
                return common.PREF.serverPort
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

    def __init__(self):
        QDialog.__init__(self, None)
        self.setWindowTitle(m18n('Create User Account') + ' - Kajongg')
        self.buttonBox = KDialogButtonBox(self)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        vbox = QVBoxLayout(self)
        grid = QFormLayout()
        self.cbServer = QComboBox()
        self.cbServer.setEditable(True)
        grid.addRow(m18n('Game server:'), self.cbServer)
        self.edUser = QLineEdit()
        grid.addRow(m18n('Username:'), self.edUser)
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
        self.edUser.setSizePolicy(pol)

        self.servers = Query('select url from server order by lasttime desc').records
        for server in self.servers:
            if server[0] != Query.localServerName:
                self.cbServer.addItem(server[0])
        self.cbServer.editTextChanged.connect(self.serverChanged)
        self.edUser.textChanged.connect(self.userChanged)
        self.edPassword.textChanged.connect(self.passwordChanged)
        self.edPassword2.textChanged.connect(self.passwordChanged)
        self.serverChanged()
        StateSaver(self)
        self.passwordChanged()
        self.edPassword2.setFocus()

    def serverChanged(self, dummyText=None):
        """the user selected a different server"""
        self.edUser.clear()

    def userChanged(self, dummyText):
        """the user name has been edited"""
        self.edPassword.clear()
        self.edPassword2.clear()
        self.validate()

    def passwordChanged(self, dummyText=None):
        """password changed"""
        self.validate()

    def validate(self):
        """does the dialog hold valid data?"""
        equal = self.edPassword.size() and self.edPassword.text() == self.edPassword2.text()
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(equal and self.edUser.text().size())

    @apply
    def host():
        """abstracts the host of the dialog"""
        def fget(self):
            text = english(unicode(self.cbServer.currentText()))
            if ':' not in text:
                return text
            hostargs = text.rpartition(':')
            return ''.join(hostargs[0])
        return property(**locals())

    @apply
    def port():
        """abstracts the port of the dialog"""
        def fget(self):
            text = unicode(self.cbServer.currentText())
            if ':' not in text:
                return common.PREF.serverPort
            hostargs = unicode(self.cbServer.currentText()).rpartition(':')
            try:
                return int(hostargs[2])
            except ValueError:
                return common.PREF.serverPort
        return property(**locals())

    @apply
    def username(): # pylint: disable=E0202
        """abstracts the username of the dialog"""
        def fget(self):
            return unicode(self.edUser.text())
        def fset(self, username):
            self.edUser.setText(username)
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

    def answer(self):
        """return the Message of this button"""
        return Message.defined[str(self.objectName())]

    def setToolTip(self, player, dangerousMelds):
        """tooltip depending of current situation"""
        # pylint: disable=R0912
        # too many branches
        answer = self.answer()
        assert answer != Message.Discard
        txt = ''
        maySay = self.parent.client.sayable[answer]
        if maySay:
            if answer == Message.Pung:
                txt = m18n('You may say Pung for %1',
                    Meld.tileName(maySay[0]))
            elif answer == Message.Kong:
                txt = m18n('You may say Kong for %1',
                    answer.i18nName, Meld.tileName(maySay[0][0]))
            elif answer == Message.Chow:
                chow1 = maySay[0]
                txt = m18n('You may say Chow for %1 %2,%3,%4',
                    Meld.colorNames[chow1[0][0].lower()],
                    chow1[0][1],
                    chow1[1][1],
                    chow1[2][1])
            elif answer == Message.OriginalCall:
                txt = m18n(
                'Just before the first discard, a player can declare Original Call meaning she needs only one '
                'tile to complete the hand and announces she will not alter the hand in any way (except bonus tiles)')
            elif answer == Message.NoClaim:
                txt = m18n('Default action: You cannot or do not want to claim this tile')
            elif answer == Message.OK:
                txt = m18n('Confirm that you saw the message')
            elif answer == Message.MahJongg:
                txt = m18n('Press here and you win')
            game = self.parent.client.game
            if answer not in (Message.NoClaim, Message.OK) and game.lastDiscard:
                lastDiscardName = Meld.tileName(game.lastDiscard.element)
                if len(dangerousMelds) == 0:
                    if player.handBoard.focusTile:
                        txt = player.handBoard.focusTile.graphics.toolTip()
                else:
                    if len(dangerousMelds) == 1:
                        txt = m18n(
                           'claiming %1 is dangerous because you will have to discard a dangerous tile',
                           lastDiscardName)
                    else:
                        for meld in dangerousMelds:
                            txt = m18n(
                           'claiming %1 for %2 is dangerous because you will have to discard a dangerous tile',
                           lastDiscardName, str(meld))
        else:
            txt = m18n('this action is currently not possible')
        QPushButton.setToolTip(self, txt)

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

    def keyPressEvent(self, event):
        """ESC selects default answer"""
        if self.client.game.autoPlay:
            return
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

    def __declareButton(self, move, message):
        """define a button"""
        maySay = self.client.sayable[message]
        if PREF.showOnlyPossibleActions and not maySay:
            return
        btn = DlgButton(message.shortcut, self)
        btn.setObjectName(message.name)
        btn.setText(message.buttonCaption())
        btn.setAutoDefault(True)
        btn.clicked.connect(self.selectedAnswer)
        self.buttons.append(btn)
        if message == Message.Discard:
            self.updateDiscardButton()
            return
        if maySay:
            dangerousMelds = self.client.maybeDangerous(message)
            if dangerousMelds:
                btn.setIcon(KIcon('dialog-warning'))
                if Debug.dangerousGame and message in [Message.Chow, Message.Kong] \
                      and len(dangerousMelds) != len(maySay):
                    logDebug('%s: only some claimable melds are dangerous: %s' % \
                       (self.game.handId(), dangerousMelds))
            btn.setToolTip(move.player, dangerousMelds)

    def updateDiscardButton(self, tile=None):
        """update icon and tooltip for the discard button"""
        game = self.client.game
        if tile is None:
            tile = game.myself.handBoard.focusTile
        if not tile:
            return
        game.myself.setTileToolTip(tile)
        txt = unicode(tile.graphics.toolTip())
        btn = self.buttons[0]
        if btn.answer() == Message.Discard:
            if game.dangerousFor(game.myself, tile):
                btn.setIcon(KIcon('dialog-warning'))
            else:
                btn.setIcon(KIcon())
            QPushButton.setToolTip(btn, txt)

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

    def askHuman(self, move, answers, deferred):
        """make buttons specified by answers visible. The first answer is default.
        The default button only appears with blue border when this dialog has
        focus but we always want it to be recognizable. Hence setBackgroundRole."""
        self.move = move
        self.deferred = deferred
        for answer in answers:
            self.__declareButton(move, answer)
        self.show()
        self.checkTiles()
        game = self.client.game
        myTurn = game.activePlayer == game.myself
        prefButton = self.buttons[0]
        if game.autoPlay or PREF.propose:
            answer, parameter = self.client.intelligence.selectAnswer(
                [x.answer() for x in self.buttons])
            prefButton = [x for x in self.buttons if x.answer() == answer][0]
            prefButton.setFocus()
            if answer == Message.Discard:
                for tile in game.myself.handBoard.tiles:
                    if tile.element == parameter:
                        game.myself.handBoard.focusTile = tile

        if game.autoPlay:
            self.selectButton(prefButton)
            return
        prefButton.setFocus()

        self.progressBar.setVisible(not myTurn)
        if myTurn:
            hBoard = game.myself.handBoard
            hBoard.hasFocus = True
        else:
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
        if self.isVisible():
            if button is None:
                button = self.buttons[0]
            if isinstance(button, Message):
                assert any(x.objectName() == button.name for x in self.buttons)
                answer = button
            else:
                answer = button.answer()
            if not self.client.sayable[answer]:
                message = m18n('You cannot say %1', answer.i18nName)
                KMessageBox.sorry(None, message)
                return
            self.timer.stop()
            self.deferred.callback(answer)
        self.hide()

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


class HumanClient(Client):
    """a human client"""
    # pylint: disable=R0904
    # disable warning about too many public methods
    # pylint: disable=R0902
    # we have 11 instance attributes, more than pylint likes

    def __init__(self, tableList, callback):
        allInt = dict(list(INTELLIGENCES.items()) + list(ALTINTELLIGENCES.items()))
        if InternalParameters.AI not in allInt:
            raise Exception('intelligence %s is undefined' % InternalParameters.AI)
        Client.__init__(self, intelligence=allInt[InternalParameters.AI])
        self.root = None
        self.tableList = tableList
        self.connector = None
        self.table = None
        self.readyHandQuestion = None
        self.loginDialog = LoginDialog()
        if InternalParameters.autoPlay:
            self.loginDialog.accept()
        else:
            if not self.loginDialog.exec_():
                raise Exception(m18n('Login aborted'))
        self.useSocket = self.loginDialog.host == Query.localServerName
        self.assertLocalServer()
        self.username = self.loginDialog.username
        self.ruleset = self.__defineRuleset()
        self.__msg = None # helper for delayed error messages
        self.login(callback)

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
                        if os.path.exists(socketName()):
                            logInfo(m18n('removed stale socket <filename>%1</filename>', socketName()))
                            os.remove(socketName())
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

    def assertLocalServer(self):
        """make sure we have a running local server"""
        if self.useSocket or self.loginDialog.host == 'localhost':
            if not self.serverListening():
                if os.name == 'nt':
                    port = HumanClient.findFreePort()
                    common.PREF.serverPort = port
                else:
                    port = None
                self.startLocalServer(port)
                # give the server up to 5 seconds time to start
                for loop in range(50):
                    if self.serverListening():
                        break
                    time.sleep(0.1)

    def startLocalServer(self, port):
        """start a local server"""
        try:
            args = ['kajonggserver'] # the default
            if sys.argv[0].endswith('kajongg.py'):
                tryServer = sys.argv[0].replace('.py', 'server.py')
                if os.path.exists(tryServer):
                    args = ['python', tryServer]
            if InternalParameters.showTraffic:
                args.append('--showtraffic')
            if InternalParameters.showSql:
                args.append('--showsql')
            if self.useSocket or os.name == 'nt':
                args.append('--local')
            if port:
                args.append('--port=%d' % port)
            if self.useSocket:
                args.append('--db=%slocal.db' % appdataDir())
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

    def readyForGameStart(self, tableid, gameid, seed, playerNames, shouldSave=True):
        """playerNames are in wind order ESWN"""
        self.tableList.hideForever = True
        if sum(not x.startswith('ROBOT') for x in playerNames.split('//')) == 1:
            # we play against 3 robots and we already told the server to start: no need to ask again
            wantStart = True
        else:
            msg = m18n("The game can begin. Are you ready to play now?\n" \
                "If you answer with NO, you will be removed from the table.")
            wantStart = KMessageBox.questionYesNo (None, msg) == KMessageBox.Yes
        if wantStart:
            self.__msg = Client.readyForGameStart(self, tableid, gameid, seed, playerNames, shouldSave=shouldSave)
            if self.__msg:
                # if we call KMessageBox directly here, the twisted reactor somehow gets out of sync.
                # it will try to parse the last atomic item again and fail because that is not a list. Happens
                # with twisted 10.2 and twisted 11.0
                QTimer.singleShot(0, self.warnData)
        else:
            self.answers.append(Message.NO)

    def warnData(self):
        """see comment above about calling KMessageBox directly"""
        logWarning(m18n(*self.__msg))

    def readyForHandStart(self, playerNames, rotateWinds):
        """playerNames are in wind order ESWN. Never called for first hand."""
        if InternalParameters.field:
            # update the balances in the status bar:
            InternalParameters.field.refresh()
        assert not self.game.isFirstHand()
        if self.game.autoPlay:
            self.clientReadyForHandStart(None, playerNames, rotateWinds)
            return
        deferred = Deferred()
        deferred.addCallback(self.clientReadyForHandStart, playerNames, rotateWinds)
        self.readyHandQuestion = ReadyHandQuestion(deferred, InternalParameters.field)
        self.readyHandQuestion.show()
        self.answers.append(deferred)

    def clientReadyForHandStart(self, dummy, playerNames, rotateWinds):
        """callback, called after the client player said yes, I am ready"""
        Client.readyForHandStart(self, playerNames, rotateWinds)

    def ask(self, move, answers):
        """server sends move. We ask the user. answers is a list with possible answers,
        the default answer being the first in the list."""
        if not InternalParameters.field:
            return Client.ask(self, move, answers)
        self.computeSayable(move, answers)
        deferred = Deferred()
        deferred.addCallback(self.answered, move, answers)
        deferred.addErrback(self.answerError, move, answers)
        iAmActive = self.game.myself == self.game.activePlayer
        self.game.myself.handBoard.setEnabled(iAmActive)
        field = InternalParameters.field
        if not field.clientDialog or not field.clientDialog.isVisible():
            # always build a new dialog because if we change its layout before
            # reshowing it, sometimes the old buttons are still visible in which
            # case the next dialog will appear at a lower position than it should
            field.clientDialog = ClientDialog(self, field.centralWidget())
        assert field.clientDialog.client is self
        field.clientDialog.askHuman(move, answers, deferred)
        self.answers.append(deferred)
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
            return self.intelligence.selectKong(self, kongs)
        if len(kongs) == 1:
            return kongs[0]
        selDlg = SelectKong(kongs)
        assert selDlg.exec_()
        return selDlg.selectedKong

    def answered(self, answer, move, answers):
        """the user answered our question concerning move"""
        if self.game.autoPlay:
            self.game.hidePopups()
            return Client.ask(self, move, answers)
        myself = self.game.myself
        if answer == Message.Discard:
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
                        InternalParameters.field.game = None
                        InternalParameters.field.quit()

    def remote_gameOver(self, tableid, message, *args):
        """the game is over"""
        if self.table and self.table.tableid == tableid:
            if not self.game.autoPlay:
                logInfo(m18n(message, *args), showDialog=True)
            if self.game:
                self.game.rotateWinds()
                if InternalParameters.csv:
                    gameWinner = max(self.game.players, key=lambda x: x.balance)
                    writer = csv.writer(open(InternalParameters.csv,'a'), delimiter=';')
                    row = [InternalParameters.AI, str(self.game.seed)]
                    for player in sorted(self.game.players, key=lambda x: x.name):
                        row.append(player.name)
                        row.append(player.balance)
                        row.append(player.wonCount)
                        row.append(1 if player == gameWinner else 0)
                    writer.writerow(row)
                    del writer
                self.game.close()
                if self.game.autoPlay:
                    self.abortGame(HumanClient.gameClosed)

    def abortGame(self, callback=None):
        """aborts current game"""
        msg = m18n("Do you really want to abort this game?")
        if self.game is None or self.game.autoPlay or \
            self.game.finished() or \
            KMessageBox.questionYesNo (None, msg) == KMessageBox.Yes:
            if self.game:
                self.game.close(callback)
            if InternalParameters.field:
                InternalParameters.field.game = None
                InternalParameters.field.refresh()
            return True
        else:
            return False

    @staticmethod
    def gameClosed(result=None):
        """called if we want to quit, after the game has been closed"""
        if isinstance(result, Failure):
            logException(result)
        InternalParameters.reactor.stop()
        # we may be in a Deferred callback generated in abortGame which would
        # catch sys.exit as an exception
        # and the qt4reactor does not quit the app when being stopped
        QTimer.singleShot(0, HumanClient.quit2)

    @staticmethod
    def quit2():
        """2nd stage: twisted reactor is already stopped"""
        StateSaver.saveAll()
        InternalParameters.app.quit()
    #       sys.exit(0)
        # pylint: disable=W0212
        os._exit(0) # TODO: should be sys.exit but that hangs since updating
        # from karmic 32 bit to lucid 64 bit. os._exit does not clean up or flush buffers
        # for reproduction, say "play" which opens the table list. Now close table list
        # and try to quit.

    def remote_serverDisconnects(self):
        """the kajongg server ends our connection"""
        self.perspective = None

    def loginCommand(self, username):
        """send a login command to server. That might be a normal login
        or adduser/deluser/change passwd encoded in the username"""
        factory = pb.PBClientFactory()
        reactor = InternalParameters.reactor
        if self.useSocket and os.name != 'nt':
            self.connector = reactor.connectUNIX(socketName(), factory)
        else:
            self.connector = reactor.connectTCP(self.loginDialog.host, self.loginDialog.port, factory)
        utf8Password = self.loginDialog.password.encode('utf-8')
        utf8Username = username.encode('utf-8')
        cred = credentials.UsernamePassword(utf8Username, utf8Password)
        return factory.login(cred, client=self)

    def adduser(self, host, name, passwd, callback, callbackParameter):
        """create a user account"""
        assert host is not None
        if self.loginDialog.host != Query.localServerName:
            adduserDialog = AddUserDialog()
            hostIdx = adduserDialog.cbServer.findText(host)
            if hostIdx >= 0:
                adduserDialog.cbServer.setCurrentIndex(hostIdx)
            else:
                adduserDialog.cbServer.insertItem(0, host)
                adduserDialog.cbServer.setCurrentIndex(0)
            adduserDialog.username = self.loginDialog.username
            adduserDialog.password = self.loginDialog.password
            if not adduserDialog.exec_():
                raise Exception(m18n('Aborted creating a user account'))
            name, passwd = adduserDialog.username, adduserDialog.password
        self.loginDialog.password = passwd
        adduserCmd = SERVERMARK.join(['adduser', name, passwd])
        self.loginCommand(adduserCmd).addCallback(callback,
            callbackParameter).addErrback(self._loginFailed, callbackParameter)

    def _loginFailed(self, failure, callback):
        """login failed"""
        message = failure.getErrorMessage()
        dlg = self.loginDialog
        host, name, passwd = dlg.host, dlg.username, dlg.password
        if 'Wrong username' in message:
            msg = m18nc('USER is not known on SERVER',
                '%1 is not known on %2, do you want to open an account?', name, host)
            if self.loginDialog.host == Query.localServerName \
            or KMessageBox.questionYesNo (None, msg) == KMessageBox.Yes:
                self.adduser(host, name, passwd, self.adduserOK, callback)
                return #failure
        else:
            if self.useSocket and os.name != 'nt':
                connectMsg = m18n('calling kajongg server on UNIX socket %1', socketName())
            else:
                connectMsg = m18n('calling kajongg server on %1:<numid>%2</numid>',
                    self.loginDialog.host, self.loginDialog.port)
            logWarning(connectMsg + ': ' + message)
        if callback:
            callback()

    def adduserOK(self, dummyFailure, callback):
        """adduser succeeded"""
        Players.createIfUnknown(self.username)
        self.login(callback)

    def login(self, callback):
        """login to server"""
        self.root = self.loginCommand(self.username)
        self.root.addCallback(self.loggedIn, callback).addErrback(self._loginFailed, callback)

    def loggedIn(self, perspective, callback):
        """we are online. Update table server and continue"""
        lasttime = datetime.datetime.now().replace(microsecond=0).isoformat()
        host = english(self.host) # use unique name for Local Game
        with Transaction():
            qData = Query('select 1 from server where url=?',
                list([host])).records
            if not qData:
                Query('insert into server(url,lastname,lasttime) values(?,?,?)',
                    list([host, self.username, lasttime]))
            else:
                Query('update server set lastname=?,lasttime=? where url=?',
                    list([self.username, lasttime, host]))
                playerId = Players.allIds[self.username]
                if Query('select 1 from passwords where url=? and player=?',
                         list([host, playerId ])).records:
                    Query('update passwords set password=? where url=? and player=?',
                        list([self.loginDialog.password, host, playerId]))
                else:
                    Query('insert into passwords(url,player,password) values(?,?,?)',
                        list([host, playerId, self.loginDialog.password]))
        self.perspective = perspective
        if callback:
            callback()

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

    def logout(self):
        """clean visual traces and logout from server"""
        deferred = self.callServer('logout')
        if deferred:
            deferred.addBoth(self.loggedOut)
        return deferred

    def loggedOut(self, dummyResult):
        """client logged out from server"""
        field = InternalParameters.field
        field.discardBoard.hide()
        if self.readyHandQuestion:
            self.readyHandQuestion.hide()
        if field.clientDialog:
            field.clientDialog.hide()

    def callServer(self, *args):
        """if we are online, call server"""
        if self.perspective:
            try:
                return self.perspective.callRemote(*args)
            except pb.DeadReferenceError:
                self.perspective = None
                logWarning(m18n('The connection to the server %1 broke, please try again later.',
                                  self.host))
