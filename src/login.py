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
import re

from twisted.spread import pb
from twisted.cred import credentials
from twisted.internet.defer import CancelledError
from twisted.python.failure import Failure

from PyQt4.QtGui import QDialog, QDialogButtonBox, QVBoxLayout, \
    QLabel, QComboBox, QLineEdit, QFormLayout, \
    QSizePolicy

from kde import DeferredDialog, QuestionYesNo, KDialogButtonBox, KUser, \
    MustChooseDialog

from util import m18n, m18nc, logWarning, logException, socketName, english, \
    appdataDir, logInfo, logDebug, removeIfExists, which
from util import SERVERMARK
from common import Internal, Options, SingleshotOptions, Internal, Debug
from game import Players
from query import Transaction, Query
from statesaver import StateSaver

from guiutil import ListComboBox
from rule import Ruleset

class LoginAborted(Exception):
    """the user aborted the login"""
    pass

class LoginDlg(QDialog):
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
            demoHost = Options.host or localName
            if demoHost in servers:
                servers.remove(demoHost)  # we want a unique list, it will be re-used for all following games
            servers.insert(0, demoHost)   # in this process but they will not be autoPlay
        self.cbServer.addItems(servers)
        self.passwords = Query('select url, p.name, passwords.password from passwords, player p '
            'where passwords.player=p.id').records
        Players.load()
        self.cbServer.editTextChanged.connect(self.serverChanged)
        self.cbUser.editTextChanged.connect(self.userChanged)
        self.serverChanged()
        StateSaver(self)

    def returns(self, dummyButton=None):
        """maybe we should return an class ServerConnection"""
        return (self.useSocket, self.url, self.username, self.__defineRuleset())

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

    def serverChanged(self, dummyText=None):
        """the user selected a different server"""
        records = Query('select player.name from player, passwords '
                'where passwords.url=? and passwords.player = player.id', list([self.url])).records
        players = list(x[0] for x in records)
        preferPlayer = Options.player
        if preferPlayer:
            if preferPlayer in players:
                players.remove(preferPlayer)
            players.insert(0, preferPlayer)
        self.cbUser.clear()
        self.cbUser.addItems(players)
        if not self.cbUser.count():
            user = KUser() if os.name == 'nt' else KUser(os.geteuid())
            self.cbUser.addItem(user.fullName() or user.loginName())
        if not preferPlayer:
            userNames = [x[1] for x in self.servers if x[0] == self.url]
            if userNames:
                userIdx = self.cbUser.findText(userNames[0])
                if userIdx >= 0:
                    self.cbUser.setCurrentIndex(userIdx)
        showPW = self.url != Query.localServerName
        self.grid.labelForField(self.edPassword).setVisible(showPW)
        self.edPassword.setVisible(showPW)
        self.grid.labelForField(self.cbRuleset).setVisible(not showPW and not Options.ruleset)
        self.cbRuleset.setVisible(not showPW and not Options.ruleset)
        if not showPW:
            self.cbRuleset.clear()
            if Options.ruleset:
                self.cbRuleset.items = [Options.ruleset]
            else:
                self.cbRuleset.items = Ruleset.selectableRulesets(self.url)

    def __defineRuleset(self):
        """find out what ruleset to use"""
        if Options.ruleset:
            return Options.ruleset
        elif Internal.autoPlay or bool(Options.host):
            return Ruleset.selectableRulesets()[0]
        else:
            return self.cbRuleset.current

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

    @property
    def url(self):
        """abstracts the url of the dialog"""
        return english(unicode(self.cbServer.currentText()))

    @property
    def host(self):
        """abstracts the host of the dialog"""
        return self.url.partition(':')[0]

    @property
    def useSocket(self):
        """do we use socket for current host?"""
        return self.host == Query.localServerName

    @property
    def port(self):
        """abstracts the port of the dialog"""
        try:
            return int(self.url.partition(':')[2])
        except ValueError:
            return Options.defaultPort()

    @property
    def username(self):
        """abstracts the username of the dialog"""
        return unicode(self.cbUser.currentText())

    @property
    def password(self):
        """abstracts the password of the dialog"""
        return unicode(self.edPassword.text())

    @password.setter
    def password(self, password):
        """abstracts the password of the dialog"""
        self.edPassword.setText(password)

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
                list([self.password, url, playerId])).rowcount() == 0:
                Query('insert into passwords(url,player,password) values(?,?,?)',
                    list([url, playerId, self.password]))

class AddUserDialog(MustChooseDialog):
    """add a user account on a server: This dialog asks for the needed attributes"""
    # pylint: disable=R0902
    # pylint we need more than 10 instance attributes

    def __init__(self, url, username, password):
        MustChooseDialog.__init__(self, None)
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

    @property
    def username(self):
        """abstracts the username of the dialog"""
        return unicode(self.lbUser.text())

    @username.setter
    def username(self, username):
        """abstracts the username of the dialog"""
        self.lbUser.setText(username)

    @property
    def password(self):
        """abstracts the password of the dialog"""
        return unicode(self.edPassword.text())

    @password.setter
    def password(self, password):
        """abstracts the password of the dialog"""
        self.edPassword.setText(password)


class Connection(object):
    """creates a connection to server"""
    def __init__(self, client):
        self.client = client
        self.perspective = None
        self.connector = None
        self.useSocket = False
        self.url = None
        self.username = None
        self.ruleset = None
        self.dlg = LoginDlg()

    def login(self):
        """to be called from HumanClient"""
        result = DeferredDialog(self.dlg).addCallback(self.__haveLoginData
            ).addCallbacks(self.assertConnectivity, self._loginReallyFailed
            ).addCallbacks(self.loginToServer, self._loginReallyFailed
            ).addCallback(self.loggedIn)
        if Internal.autoPlay or SingleshotOptions.table or SingleshotOptions.join:
            result.clicked()
        return result

    def loginToServer(self, dummy=None):
        """login to server"""
        return self.loginCommand(self.username).addErrback(self._loginFailed)

    def __haveLoginData(self, arguments):
        """user entered login data, now try to login to server"""
        if self.url == 'localhost':
            # we have localhost if we play a Local Game: client and server are identical,
            # we have no security concerns about creating a new account
            Players.createIfUnknown(unicode(self.dlg.cbUser.currentText()))
        self.useSocket, self.url, self.username, self.ruleset = arguments
        self.__checkExistingConnections()

    def loggedIn(self, perspective):
        """successful login on server"""
        assert perspective
        self.perspective = perspective
        self.perspective.notifyOnDisconnect(self.client.serverDisconnected)
        self.pingLater() # not right now, client.connection is still None
        return self

    def __checkExistingConnections(self):
        """do we already have a connection to the wanted URL?"""
        for client in self.client.humanClients:
            if client.connection and client.connection.url == self.url:
                logWarning(m18n('You are already connected to server %1', self.url))
                client.tableList.activateWindow()
                raise CancelledError

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
            except socket.error as exception:
                if os.path.exists(socketName()):
                    # try again, avoiding a race
                    try:
                        sock.connect(socketName())
                    except socket.error as exception:
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
                sock.connect((self.dlg.host, self.dlg.port))
            except socket.error:
                return False
            else:
                return True

    def assertConnectivity(self, result):
        """make sure we have a running local server or network connectivity"""
        if self.useSocket or self.dlg.url in ('localhost', '127.0.0.1'):
            if not self.serverListening():
                if os.name == 'nt':
                    port = self.findFreePort()
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
            answer = subprocess.Popen(['qdbus',
                'org.kde.kded',
                '/modules/networkstatus',
                'org.kde.Solid.Networking.status'], stdout=subprocess.PIPE).communicate()[0].strip()
            if answer != '4':
                # pylint: disable=W0710
                raise Failure(m18n('You have no network connectivity: %1', answer))
        return result

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
            if Options.socket:
                args.append('--socket=%s' % Options.socket)
            process = subprocess.Popen(args, shell=os.name=='nt')
            if Debug.connections:
                logDebug(m18n('started the local kajongg server: pid=<numid>%1</numid> %2',
                    process.pid, ' '.join(args)))
        except OSError as exc:
            logException(exc)

    def loginCommand(self, username):
        """send a login command to server. That might be a normal login
        or adduser/deluser/change passwd encoded in the username"""
        factory = pb.PBClientFactory()
        reactor = Internal.reactor
        if self.useSocket and os.name != 'nt':
            self.connector = reactor.connectUNIX(socketName(), factory, timeout=2)
        else:
            self.connector = reactor.connectTCP(self.dlg.host, self.dlg.port, factory, timeout=5)
        utf8Password = self.dlg.password.encode('utf-8')
        utf8Username = username.encode('utf-8')
        cred = credentials.UsernamePassword(utf8Username, utf8Password)
        return factory.login(cred, client=self.client)

    def __adduser(self):
        """create a user account"""
        assert self.url is not None
        if self.dlg.host != Query.localServerName:
            if not AddUserDialog(self.dlg.url,
                self.dlg.username,
                self.dlg.password).exec_():
                return
            Players.createIfUnknown(self.username)
        adduserCmd = SERVERMARK.join(['adduser', self.dlg.username, self.dlg.password])
        return self.loginCommand(adduserCmd)

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
        # current twisted (version 12.3) returns different messages:
        if not match:
            match = re.search(r".*DNS lookup failed: address u'(.*)' not found.*", message)
            if match:
                return u'%s: %s' % (match.group(1), m18n('DNS lookup failed, address not found'))
        if not match:
            match = re.search(r".*DNS lookup.*\[Errno 110\] (.*)", message)
        if not match:
            match = re.search(r".*while connecting: 113: (.*)", message)
        if match:
            message = match.group(1).decode('string-escape').decode('string-escape')
        return u'%s: %s' % (url, message.decode('utf-8'))

    def _loginFailed(self, failure):
        """login failed"""
        def answered(result):
            """user finally answered our question"""
            if result:
                return self.__adduser()
            else:
                return Failure(CancelledError)
        message = failure.getErrorMessage()
        if 'Wrong username' in message:
            if self.dlg.host == Query.localServerName:
                return answered(True)
            else:
                msg = m18nc('USER is not known on SERVER',
                    '%1 is not known on %2, do you want to open an account?', self.dlg.username, self.dlg.host)
                return QuestionYesNo(msg).addCallback(answered)
        else:
            return self._loginReallyFailed(failure)

    def _loginReallyFailed(self, failure):
        """login failed, not fixable by adding missing user"""
        msg = self._prettifyErrorMessage(failure)
        if failure.check(CancelledError):
            # show no warning, just leave
            return failure
        if 'Errno 5' in msg:
            # The server is running but something is wrong with it
            if self.useSocket and os.name != 'nt':
                if removeIfExists(socketName()):
                    logInfo(m18n('removed stale socket <filename>%1</filename>', socketName()))
                msg += '\n\n\n' + m18n('Please try again')
        logWarning(msg)
        return failure

    def pingLater(self, dummyResult=None):
        """ping the server every 5 seconds"""
        Internal.reactor.callLater(5, self.ping) # pylint: disable=E1101

    def ping(self):
        """regularly check if server is still there"""
        if self.client.connection:
            # when pinging starts, we do have a connection and when the
            # connection goes away, it does not come back
            self.client.callServer('ping').addCallback(self.pingLater).addErrback(self.client.remote_serverDisconnects)
