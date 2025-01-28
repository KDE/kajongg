# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

import socket
import subprocess
import datetime
import os
import sys
from itertools import chain
from typing import List, Tuple, Union, Optional, TYPE_CHECKING, Any

from twisted.spread import pb
from twisted.cred import credentials
from twisted.internet.defer import CancelledError
from twisted.internet.task import deferLater
import twisted.internet.error
from twisted.python.failure import Failure

from qt import QDialogButtonBox, QVBoxLayout, \
    QLabel, QComboBox, QLineEdit, QFormLayout, \
    QSizePolicy, QWidget

from kde import KUser, KDialog, KDialogButtonBox
from mi18n import i18n, i18nc, english
from dialogs import DeferredDialog, QuestionYesNo

from log import logWarning, logException, logInfo, logDebug, SERVERMARK
from util import removeIfExists, which
from common import Internal, Options, SingleshotOptions, Debug, isAlive
from common import interpreterName
from common import ReprMixin
from common import appdataDir, socketName
from game import Players
from query import Query
from statesaver import StateSaver

from guiutil import ListComboBox, decorateWindow
from rule import Ruleset

if TYPE_CHECKING:
    from twisted.internet.defer import Deferred
    from twisted.internet.unix import Connector
    from humanclient import HumanClient
    from deferredutil import Request

class LoginAborted(Exception):

    """the user aborted the login"""


class Url(str, ReprMixin):

    """holds connection related attributes: host, port, socketname"""

    def __init__(self, url:str) ->None:
        assert url
        super().__init__()
        self.host: str
        self.port:Optional[int]

    def __new__(cls, url:str) ->'Url':
        assert url
        host = None
        port = None
        urlParts = url.split(':')
        host = urlParts[0]
        if english(host) == Query.localServerName:
            host = '127.0.0.1'
        if len(urlParts) > 1:
            port = int(urlParts[1])
        obj = str.__new__(cls, url)
        obj.host = host
        obj.port = port
        if Options.port:
            obj.port = int(Options.port)
        if obj.port is None and obj.isLocalHost and not obj.useSocket:
            obj.port = obj.findFreePort()
        if obj.port is None and not obj.isLocalHost:
            obj.port = Internal.defaultPort
        if Debug.connections:
            logDebug(repr(obj))

        return obj

    def __str__(self) ->str:
        """show all info"""
        return socketName() if self.useSocket else f'{self.host}:{self.port}'

    @property
    def useSocket(self) ->bool:
        """do we use socket for current host?"""
        return (
            self.host == '127.0.0.1'
            and sys.platform != 'win32'
            and not Options.port)

    @property
    def isLocalGame(self) ->bool:
        """Are we playing a local game not needing the network?"""
        return self.host == '127.0.0.1'

    @property
    def isLocalHost(self) ->bool:
        """do server and client run on the same host?"""
        return self.host in ('127.0.0.1', 'localhost')

    def findFreePort(self) ->Optional[int]:
        """find an unused port on the current system.
        used when we want to start a local server on windows"""
        assert self.isLocalHost
        for port in chain([Internal.defaultPort], range(2000, 19000)):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            try:
                sock.connect((self.host, port))
                sock.close()
            except socket.error:
                return port
        logException('cannot find a free port')
        return None

    def startServer(self, result:Any, waiting:int=0) ->'Deferred':
        """make sure we have a running local server or network connectivity"""
        if self.isLocalHost:
            # just wait for that server to appear
            if self.__serverListening():
                return result
            if waiting == 0:
                self.__startLocalServer()
            elif waiting > 30:
                logDebug(f'Game {SingleshotOptions.game}: Server {self} not available after 30 seconds, aborting')
                raise CancelledError
            return deferLater(Internal.reactor, 1, self.startServer, result, waiting + 1)
        if which('qdbus'):
            try:
                stdoutdata, stderrdata = subprocess.Popen(  # pylint:disable=consider-using-with
                    ['qdbus',
                     'org.kde.kded',
                     '/modules/networkstatus',
                     'org.kde.Solid.Networking.status'],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate(timeout=1)
            except subprocess.TimeoutExpired as _:
                raise twisted.internet.error.ConnectError() from _
            stdoutdata = stdoutdata.strip()
            stderrdata = stderrdata.strip()
            if stderrdata == '' and stdoutdata != '4':
                raise twisted.internet.error.ConnectError()
            # if we have stderrdata, qdbus probably does not provide the
            # service we want, so ignore it
        return result

    @staticmethod
    def __findServerProgram() ->List[str]:
        """how should we start the server?"""
        result = []
        if sys.argv[0].endswith('kajongg.py'):
            tryServer = sys.argv[0].replace('.py', 'server.py')
            if os.path.exists(tryServer):
                result = [interpreterName, tryServer]
        elif sys.argv[0].endswith('kajongg.pyw'):
            tryServer = sys.argv[0].replace('.pyw', 'server.py')
            if os.path.exists(tryServer):
                result = [interpreterName, tryServer]
        elif sys.argv[0].endswith('kajongg.exe'):
            tryServer = sys.argv[0].replace('.exe', 'server.exe')
            if os.path.exists(tryServer):
                result = [tryServer]
        else:
            result = ['kajonggserver']
        if Debug.connections:
            logDebug(i18n('trying to start local server %1', result))
        return result

    def __startLocalServer(self) ->None:
        """start a local server"""
        try:
            args = self.__findServerProgram()
            if self.useSocket or sys.platform == 'win32':  # for win32 --socket tells the server to bind to 127.0.0.1
                args.append(f'--socket={socketName()}')
                if removeIfExists(socketName()):
                    logInfo(
                        i18n('removed stale socket <filename>%1</filename>', socketName()))
            if not self.useSocket:
                assert self.port
                args.append(f'--port={int(self.port)}')
            if self.isLocalGame:
                args.append(
                    f"--db={os.path.normpath(os.path.join(appdataDir(), 'local3.db'))}")
            if Debug.argString:
                args.append(f'--debug={Debug.argString}')
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()  # type: ignore
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore
            else:
                startupinfo = None
            process = subprocess.Popen(  # pylint:disable=consider-using-with
                args,
                startupinfo=startupinfo)  # , shell=sys.platform == 'win32')
            if Debug.connections:
                logDebug(
                    i18n(
                        'started the local kajongg server: pid=<numid>%1</numid> %2',
                        process.pid, ' '.join(args)))
        except OSError as exc:
            exc.filename = ' '.join(args)
            logException(exc)

    @staticmethod
    def __check_socket(proto:int, param:Union[str, Tuple[str, Optional[int]]]) ->bool:
        """check connection on socket"""
        sock = socket.socket(proto, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            sock.connect(param)
            sock.close()
            return True
        except socket.error:
            return False

    def __serverListening(self) ->bool:
        """is the expected server listening?"""
        if self.useSocket:
            socket_path = socketName()
            if not os.path.exists(socket_path):
                return False
            return self.__check_socket(socket.AF_UNIX, socket_path)
        return self.__check_socket(socket.AF_INET, (self.host, self.port))

    def connect(self, factory:pb.PBClientFactory) ->'Connector':
        """return a twisted connector"""
        assert Internal.reactor
        if self.useSocket:
            return Internal.reactor.connectUNIX(socketName(), factory, timeout=5)
        host = self.host
        return Internal.reactor.connectTCP(host, self.port, factory, timeout=5)


class LoginDlg(KDialog):

    """login dialog for server"""

    def __init__(self) ->None:
        """self.servers is a list of tuples containing server and last playername"""
        KDialog.__init__(self, None)
        decorateWindow(self, i18nc('kajongg', 'Login'))
        self.setupUi()

        localName = i18nc('kajongg name for local game server', Query.localServerName)
        self.servers = Query(
            'select url,lastname from server order by lasttime desc').records
        servers = [x[0] for x in self.servers if x[0] != Query.localServerName]
        # the first server combobox item should be default: either the last used server
        # or localName for autoPlay
        if localName not in servers:
            servers.append(localName)
        if 'kajongg.org' not in servers:
            servers.append('kajongg.org')
        if Internal.autoPlay:
            demoHost = Options.host or localName
            if demoHost in servers:
                servers.remove(
                    demoHost)  # we want a unique list, it will be re-used for all following games
            servers.insert(0, demoHost)
                           # in this process but they will not be autoPlay
        self.cbServer.addItems(servers)
        self.passwords = Query('select url, p.name, passwords.password from passwords, player p '
                               'where passwords.player=p.id').records
        Players.load()
        self.cbServer.editTextChanged.connect(self.serverChanged)
        self.cbUser.editTextChanged.connect(self.userChanged)
        self.serverChanged()
        StateSaver(self)

    def returns(self, button:Optional[QDialogButtonBox.StandardButton]=None) ->Any:
        """login data returned by this dialog"""
        return (Url(self.url), self.username, self.password, self.__defineRuleset())

    def setupUi(self) ->None:
        """create all Ui elements but do not fill them"""
        self.buttonBox = KDialogButtonBox(self)
        self.buttonBox.setStandardButtons(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        # Ubuntu 11.10 unity is a bit strange - without this, it sets focus on
        # the cancel button (which it shows on the left). I found no obvious
        # way to use setDefault and setAutoDefault for fixing this.
        if button := self.buttonBox.button(QDialogButtonBox.StandardButton.Ok):
            button.setFocus()
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        vbox = QVBoxLayout(self)
        self.grid = QFormLayout()
        self.cbServer = QComboBox()
        self.cbServer.setEditable(True)
        self.grid.addRow(i18n('Game server:'), self.cbServer)
        self.cbUser = QComboBox()
        self.cbUser.setEditable(True)
        self.grid.addRow(i18n('Username:'), self.cbUser)
        self.edPassword = QLineEdit()
        self.edPassword.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.grid.addRow(i18n('Password:'), self.edPassword)
        self.cbRuleset = ListComboBox([])
        self.grid.addRow(i18nc('kajongg', 'Ruleset:'), self.cbRuleset)
        vbox.addLayout(self.grid)
        vbox.addWidget(self.buttonBox)
        pol = QSizePolicy()
        pol.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
        self.cbUser.setSizePolicy(pol)

    def serverChanged(self, unusedText:Optional[str]=None) ->None:
        """the user selected a different server"""
        records = Query('select player.name from player, passwords '
                        'where passwords.url=? and passwords.player = player.id', (self.url,)).records
        players = [x[0] for x in records]
        preferPlayer = Options.player
        if preferPlayer:
            if preferPlayer in players:
                players.remove(preferPlayer)
            players.insert(0, preferPlayer)
        self.cbUser.clear()
        self.cbUser.addItems(players)
        if not self.cbUser.count():
            user = KUser() if sys.platform == 'win32' else KUser(os.geteuid())
            self.cbUser.addItem(user.fullName() or user.loginName())
        if not preferPlayer:
            userNames = [x[1] for x in self.servers if x[0] == self.url]
            if userNames:
                userIdx = self.cbUser.findText(userNames[0])
                if userIdx >= 0:
                    self.cbUser.setCurrentIndex(userIdx)
        showPW = bool(self.url) and not Url(self.url).isLocalHost
        if label := self.grid.labelForField(self.edPassword):
            label.setVisible(showPW)
        self.edPassword.setVisible(showPW)
        if label := self.grid.labelForField(self.cbRuleset):
            label.setVisible( not showPW and not Options.ruleset)
        self.cbRuleset.setVisible(not showPW and not Options.ruleset)
        if not showPW:
            self.cbRuleset.clear()
            if Options.ruleset:
                self.cbRuleset.items = [Options.ruleset]
            else:
                self.cbRuleset.items = Ruleset.selectableRulesets(self.url)
        if button := self.buttonBox.button(QDialogButtonBox.StandardButton.Ok):
            button.setEnabled(bool(self.url))

    def __defineRuleset(self) ->'Ruleset':
        """find out what ruleset to use"""
        if Options.ruleset:
            return Options.ruleset
        if Internal.autoPlay or bool(Options.host):
            return Ruleset.selectableRulesets()[0]
        return self.cbRuleset.current

    def userChanged(self, text:str) ->None:
        """the username has been changed, lookup password"""
        if text == '':
            self.edPassword.clear()
            return
        passw = None
        for entry in self.passwords:
            if entry[0] == self.url and entry[1] == text:
                passw = entry[2]
        if passw:
            self.edPassword.setText(passw)
        else:
            self.edPassword.clear()

    @property
    def url(self) ->str:
        """abstracts the url of the dialog"""
        return english(self.cbServer.currentText())

    @property
    def username(self) ->str:
        """abstracts the username of the dialog"""
        return self.cbUser.currentText()

    @property
    def password(self) ->str:
        """abstracts the password of the dialog"""
        return self.edPassword.text()

    @password.setter
    def password(self, password:str) ->None:
        """abstracts the password of the dialog"""
        self.edPassword.setText(password)


class AddUserDialog(KDialog):

    """add a user account on a server: This dialog asks for the needed attributes"""

    def __init__(self, url:str, username:str, password:str):
        KDialog.__init__(self)
        decorateWindow(self, i18nc("@title:window", "Create User Account"))
        self.setButtons(KDialog.Ok | KDialog.Cancel)
        vbox = QVBoxLayout()
        grid = QFormLayout()
        self.lbServer = QLabel()
        self.lbServer.setText(url)
        grid.addRow(i18n('Game server:'), self.lbServer)
        self.lbUser = QLabel()
        grid.addRow(i18n('Username:'), self.lbUser)
        self.edPassword = QLineEdit()
        self.edPassword.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        grid.addRow(i18n('Password:'), self.edPassword)
        self.edPassword2 = QLineEdit()
        self.edPassword2.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        grid.addRow(i18n('Repeat password:'), self.edPassword2)
        vbox.addLayout(grid)
        widget = QWidget(self)
        widget.setLayout(vbox)
        self.setMainWidget(widget)
        pol = QSizePolicy()
        pol.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
        self.lbUser.setSizePolicy(pol)

        self.edPassword.textChanged.connect(self.passwordChanged)
        self.edPassword2.textChanged.connect(self.passwordChanged)
        StateSaver(self)
        self.username = username
        self.password = password
        self.passwordChanged()
        self.edPassword2.setFocus()

    def passwordChanged(self, unusedText:Optional[str]=None) ->None:
        """password changed"""
        self.validate()

    def validate(self) ->None:
        """does the dialog hold valid data?"""
        equal = bool(self.edPassword.size(
        )) and self.edPassword.text(
        ) == self.edPassword2.text(
        )
        self.button(KDialog.Ok).setEnabled(equal)

    @property
    def username(self) ->str:
        """abstracts the username of the dialog"""
        return self.lbUser.text()

    @username.setter
    def username(self, username:str) ->None:
        """abstracts the username of the dialog"""
        self.lbUser.setText(username)

    @property
    def password(self) ->str:
        """abstracts the password of the dialog"""
        return self.edPassword.text()

    @password.setter
    def password(self, password:str) ->None:
        """abstracts the password of the dialog"""
        self.edPassword.setText(password)


class Connection:

    """creates a connection to server"""

    def __init__(self, client:'HumanClient'):
        self.client = client
        self.perspective:pb.RemoteReference
        self.connector: 'Connector'
        self.url: Url
        self.username: str
        self.password: str
        self.__ruleset: 'Ruleset'
        self.dlg = LoginDlg()

    @property
    def ruleset(self) ->'Ruleset':
        """reader"""
        return self.__ruleset

    @ruleset.setter
    def ruleset(self, value:'Ruleset') ->None:
        """save changed ruleset as last used ruleset for this server"""
        if not hasattr(self, '__ruleset'):
            self.__ruleset = value
            if value:
                def write() ->Query:
                    """write to database, returns 1 for success"""
                    return Query('update server set lastruleset=? where url=?', (value.rulesetId, self.url))
                value.save()
                           # make sure we have a valid rulesetId for predefined
                           # rulesets
                if not write():
                    self.__updateServerInfoInDatabase()
                    write()

    def login(self) ->DeferredDialog:
        """to be called from HumanClient"""
        result = DeferredDialog(self.dlg)
        result.addCallback(self.__haveLoginData)
        result.addCallback(self.__checkExistingConnections)
        result.addCallback(self.__startServer)
        result.addCallback(self.__loginToServer)
        result.addCallback(self.loggedIn)
        result.addErrback(self._loginReallyFailed)
        if Internal.autoPlay or SingleshotOptions.table or SingleshotOptions.join:
            result.clicked()
        return result

    def __haveLoginData(self, arguments:Tuple[Url, str, str, 'Ruleset']) ->None:
        """user entered login data, now try to login to server"""
        if not Internal.autoPlay and self.dlg.result() == 0:
            self._loginReallyFailed(Failure(CancelledError()))
        self.url, self.username, self.password, self.ruleset = arguments
        if self.url.isLocalHost:
            # we have localhost if we play a Local Game: client and server are identical,
            # we have no security concerns about creating a new account
            Players.createIfUnknown(self.dlg.cbUser.currentText())

    def __startServer(self, result:List['Request']) ->'Deferred':
        """if needed"""
        return self.url.startServer(result)

    def __loginToServer(self, unused:List['Request']) ->'Deferred':
        """login to server"""
        return self.loginCommand(self.username).addErrback(self._loginFailed)

    def loggedIn(self, perspective:pb.RemoteReference) ->'Connection':
        """successful login on server"""
        assert perspective, type(perspective)
        self.perspective = perspective
        self.perspective.notifyOnDisconnect(self.client.serverDisconnected)
        self.__updateServerInfoInDatabase()
        self.dlg = None  # type: ignore
        self.pingLater()  # not right now, client.connection is still None
        return self

    def __updateServerInfoInDatabase(self) ->None:
        """we are online. Update table server."""
        lasttime = datetime.datetime.now().replace(microsecond=0).isoformat()
        with Internal.db:
            serverKnown = Query(
                'update server set lastname=?,lasttime=? where url=?',
                (self.username, lasttime, self.url)).rowcount() == 1
            if not serverKnown:
                Query(
                    'insert into server(url,lastname,lasttime) values(?,?,?)',
                    (self.url, self.username, lasttime))
        # needed if the server knows our name but our local data base does not:
        Players.createIfUnknown(self.username)
        playerId = Players.allIds[self.username]
        with Internal.db:
            if Query('update passwords set password=? where url=? and player=?',
                     (self.password, self.url, playerId)).rowcount() == 0:
                Query('insert into passwords(url,player,password) values(?,?,?)',
                      (self.url, playerId, self.password))

    def __checkExistingConnections(self, unused:Optional[str]=None) ->None:
        """do we already have a connection to the wanted URL?"""
        for client in self.client.humanClients:
            if client.connection and client.connection.url == self.url:
                logWarning(
                    i18n('You are already connected to server %1', self.url))
                if client.tableList:
                    client.tableList.activateWindow()
                raise CancelledError

    def loginCommand(self, username:str) ->'Deferred':
        """send a login command to server. That might be a normal login
        or adduser/deluser/change passwd encoded in the username"""
        factory = pb.PBClientFactory(unsafeTracebacks=True)
        self.connector = self.url.connect(factory)
        assert self.dlg
        utf8Password = self.dlg.password.encode('utf-8')
        utf8Username = username.encode('utf-8')
        cred = credentials.UsernamePassword(utf8Username, utf8Password)
        return factory.login(cred, client=self.client)

    def __adduser(self) ->'Deferred':
        """create a user account"""
        assert self.dlg
        if not self.url.isLocalHost:
            if not AddUserDialog(self.url,
                                 self.dlg.username,
                                 self.dlg.password).exec():
                raise CancelledError
            Players.createIfUnknown(self.username)
        adduserCmd = SERVERMARK.join(
            ['adduser', self.dlg.username, self.dlg.password])
        return self.loginCommand(adduserCmd)

    def _loginFailed(self, failure:Failure) ->Union['Deferred', Failure]:
        """login failed"""
        def answered(result:bool) ->Union['Deferred', Failure]:
            """user finally answered our question"""
            return self.__adduser() if result else Failure(CancelledError())
        message = failure.getErrorMessage()
        if 'Wrong username' in message:
            if self.url.isLocalHost:
                return answered(True)
            assert self.dlg
            msg = i18nc('USER is not known on SERVER',
                        '%1 is not known on %2, do you want to open an account?', self.dlg.username, self.url.host)
            return QuestionYesNo(msg).addCallback(answered)
        self._loginReallyFailed(failure)
        return Failure() # only for mypy

    def _loginReallyFailed(self, failure:Failure) ->None:
        """login failed, not fixable by adding missing user"""
        msg = None
        if not isAlive(Internal.mainWindow):
            raise CancelledError
        if failure.check(CancelledError):
            pass
        elif failure.check(twisted.internet.error.TimeoutError):
            msg = i18n('Server %1 did not answer', self.url)
        elif failure.check(twisted.internet.error.ConnectionRefusedError):
            msg = i18n('Server %1 refused connection', self.url)
        elif failure.check(twisted.internet.error.ConnectionLost):
            msg = i18n('Server %1 does not run a kajongg server', self.url)
        elif failure.check(twisted.internet.error.DNSLookupError):
            msg = i18n('Address for server %1 cannot be found', self.url)
        elif failure.check(twisted.internet.error.ConnectError):
            msg = i18n(
                'Login to server %1 failed: You have no network connection',
                self.url)
        else:
            msg = (f'Login to server {self.url} failed: '
                   f'{failure.value.__class__.__name__}/{failure.getErrorMessage()} Callstack:{failure.getTraceback()}')
        assert msg
        # Maybe the server is running but something is wrong with it
        if self.url and self.url.useSocket:
            if removeIfExists(socketName()):
                logInfo(
                    i18n('removed stale socket <filename>%1</filename>', socketName()))
            msg += '\n\n\n' + i18n('Please try again')
        self.dlg = None  # type: ignore
        if msg:
            logWarning(msg)
        raise CancelledError

    def pingLater(self, unusedResult:Optional[str]=None) ->None:
        """ping the server every 5 seconds"""
        Internal.reactor.callLater(5, self.ping)

    def ping(self) ->None:
        """regularly check if server is still there"""
        def disconnected(unusedResult:Any) ->None:
            self.client.remote_serverDisconnects()
        if self.client.connection:
            # when pinging starts, we do have a connection and when the
            # connection goes away, it does not come back
            self.client.callServer(
                'ping').addCallback(
                    self.pingLater).addErrback(disconnected)

    def __str__(self) ->str:
        return f'{self.username}@{self.url}'
