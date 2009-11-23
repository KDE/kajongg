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

from twisted.spread import pb
from twisted.cred import credentials
from PyQt4.QtCore import SIGNAL,  SLOT
from PyQt4.QtGui import QDialog,  QDialogButtonBox,  QVBoxLayout,  QGridLayout, \
    QLabel,  QComboBox, QLineEdit

from PyKDE4.kdeui import KDialogButtonBox
from util import m18n, logWarning
from game import Players
from query import Query

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
        lblUsername = QLabel(m18n('User name:'))
        grid.addWidget(lblUsername, 1, 0)
        self.cbUser = QComboBox()
        self.cbUser.setEditable(True)
        self.cbUser.setMinimumWidth(350) # is this good for all platforms?
        lblUsername.setBuddy(self.cbUser)
        grid.addWidget(self.cbUser, 1, 1)
        lblPassword = QLabel(m18n('Password:'))
        grid.addWidget(lblPassword, 2, 0)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        grid.addWidget(self.password, 2, 1)
        lblPassword.setBuddy(self.password)
        vbox.addLayout(grid)
        vbox.addWidget(self.buttonBox)

        # now load data:
        Players.load()
        self.cbUser.addItems(Players.allNames.values())
        self.servers = Query('select url, lastname, password from server order by lasttime desc').data
        if not self.servers:
            self.servers = tuple('localhost:8082', '', '')
        for server in self.servers:
            self.cbServer.addItem(server[0])
        if self.cbServer.count() == 0:
            self.cbServer.addItem('localhost')
        self.setServerDefaults(0)

    def setServerDefaults(self, idx):
        """set last username and password for the selected server"""
        userIdx = self.cbUser.findText(self.servers[idx][1])
        if userIdx >= 0:
            self.cbUser.setCurrentIndex(userIdx)
        self.password.setText(self.servers[idx][2])


class Client(pb.Referenceable):
    """interface to the server"""
    def __init__(self, field, callback=None):
        self.field = field
        self.callback = callback
        self.perspective = None
        self.connector = None
        self.login = Login()
        login = self.login
        if not login.exec_():
            raise Exception(m18n('Login aborted'))
        hostargs = str(login.cbServer.currentText()).split(':')
        self.host = ''.join(hostargs[:-1])
        self.port = int(hostargs[-1])
        self.username = str(login.cbUser.currentText())
        self.password = str(login.password.text())
        self.root = self.connect()
        self.root.addCallback(self.connected).addErrback(self._loginFailed)

    def remote_tablesChanged(self, tables):
        """update table list"""
        self.field.tableList.load(tables)

    def connect(self):
        """connect self to server"""
        factory = pb.PBClientFactory()
        self.connector = self.field.reactor.connectTCP(self.host, self.port, factory)
        cred = credentials.UsernamePassword(self.username,  self.password)
        return factory.login(cred, client=self)

    def _loginFailed(self, failure):
        """login failed"""
        logWarning(failure.getErrorMessage())
        if self.callback:
            self.callback()

    def connected(self, perspective):
        """we are online"""
        self.perspective = perspective
        if self.callback:
            self.callback()

    def remote(self, *args):
        """if we are online, call remote"""
        if self.perspective:
            try:
                return self.perspective.callRemote(*args)
            except pb.DeadReferenceError:
                self.perspective = None
                self.field.actionRemoteGame.setChecked(False)
                logWarning(m18n('The connection to the server %1 broke, please try again later.',
                                  self.host))

