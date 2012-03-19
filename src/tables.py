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

import datetime, random

from kde import KIcon, KDialogButtonBox
from PyQt4.QtCore import Qt, QVariant, \
        QAbstractTableModel
from PyQt4.QtGui import QDialog, QDialogButtonBox, QWidget, \
        QHBoxLayout, QVBoxLayout, QAbstractItemView, \
        QItemSelectionModel, QGridLayout, QColor, QPalette

from kde import KApplication

from genericdelegates import RichTextColumnDelegate

from util import logWarning, m18n, m18nc, logDebug
from statesaver import StateSaver
from humanclient import HumanClient
from query import Query
from scoringengine import Ruleset
from guiutil import ListComboBox, MJTableView
from differ import RulesetDiffer
from sound import Voice
from common import InternalParameters, Debug, PREF
from client import ClientTable

class TablesModel(QAbstractTableModel):
    """a model for our tables"""
    def __init__(self, tables, parent = None):
        super(TablesModel, self).__init__(parent)
        self.tables = tables

    def headerData(self, section, orientation, role=Qt.DisplayRole): # pylint: disable=R0201
        """show header"""
        if role == Qt.TextAlignmentRole:
            if orientation == Qt.Horizontal:
                if section in [3, 4]:
                    return QVariant(int(Qt.AlignLeft))
                else:
                    return QVariant(int(Qt.AlignHCenter|Qt.AlignVCenter))
        if role != Qt.DisplayRole:
            return QVariant()
        if orientation != Qt.Horizontal:
            return QVariant(int(section+1))
        result = ''
        if section < 5:
            result = [m18n('Table'), '', m18n('Players'), m18nc('table status', 'Status'), m18n('Ruleset')][section]
        return QVariant(result)

    def rowCount(self, dummyParent=None):
        """how many tables are in the model?"""
        return len(self.tables)

    def columnCount(self, dummyParent=None): # pylint: disable=R0201
        """for now we only have id (invisible), id (visible), players, status, ruleset.name.
        id(invisible) always holds the real id, also 1000 for suspended tables.
        id(visible) is what should be displayed."""
        return 5

    def data(self, index, role=Qt.DisplayRole):
        """score table"""
        # pylint: disable=R0912,R0914
        # pylint too many branches
        result = QVariant()
        if role == Qt.TextAlignmentRole:
            if index.column() == 0:
                result = QVariant(int(Qt.AlignHCenter|Qt.AlignVCenter))
            else:
                result = QVariant(int(Qt.AlignLeft|Qt.AlignVCenter))
        if index.isValid() and (0 <= index.row() < len(self.tables)):
            table = self.tables[index.row()]
            if role == Qt.DisplayRole and index.column() == 1:
                result = QVariant(table.tableid)
            elif role == Qt.DisplayRole and index.column() == 0:
                if not table.status.startswith('Suspended'):
                    result = QVariant(table.tableid)
            elif role == Qt.DisplayRole and index.column() == 2:
                players = []
                zipped = zip(table.playerNames, table.playersOnline)
                for idx, pair in enumerate(zipped):
                    name, online = pair[0], pair[1]
                    if idx < len(zipped) - 1:
                        name += ', '
                    palette = KApplication.palette()
                    if online:
                        color = palette.color(QPalette.Active, QPalette.WindowText).name()
                        style = 'font-weight:normal;font-style:normal;color:%s' % color
                    else:
                        color = palette.color(QPalette.Disabled, QPalette.WindowText).name()
                        style = 'font-weight:100;font-style:italic;color:%s' % color
                    players.append('<nobr style="%s">' % style + name + '</nobr>')
                names = ''.join(players)
                result = QVariant(names)
            elif role == Qt.DisplayRole and index.column() == 3:
                status = table.status
                if status.startswith('Suspended'):
                    dateVal = ' ' + datetime.datetime.strptime(status.replace('Suspended', ''),
                        '%Y-%m-%dT%H:%M:%S').strftime('%c').decode('utf-8')
                    status = 'Suspended'
                else:
                    dateVal = ''
                result = QVariant(m18nc('table status', status) + dateVal)
            elif index.column() == 4:
                if role == Qt.DisplayRole:
                    result = QVariant(m18n(table.ruleset.name))
                elif role == Qt.ForegroundRole:
                    palette = KApplication.palette()
                    color = palette.windowText() if table.myRuleset else 'red'
                    result = QVariant(QColor(color))
        return result

class SelectRuleset(QDialog):
    """a dialog for selecting a ruleset"""
    def __init__(self, server):
        QDialog.__init__(self, None)
        self.setWindowTitle(m18n('Select a ruleset') + ' - Kajongg')
        self.buttonBox = KDialogButtonBox(self)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.cbRuleset = ListComboBox(Ruleset.selectableRulesets(server))
        self.grid = QGridLayout() # our child SelectPlayers needs this
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 6)
        vbox = QVBoxLayout(self)
        vbox.addLayout(self.grid)
        vbox.addWidget(self.cbRuleset)
        vbox.addWidget(self.buttonBox)

class TableList(QWidget):
    """a widget for viewing, joining, leaving tables"""
    # pylint: disable=R0902
    # pylint we have more than 10 attributes
    def __init__(self):
        super(TableList, self).__init__(None)
        self.autoStarted = False
        self.client = None
        self.setObjectName('TableList')
        self.resize(700, 400)
        self.view = MJTableView(self)
        self.differ = None
        self.__hideForever = False
        self.view.setItemDelegateForColumn(2, RichTextColumnDelegate(self.view))

        buttonBox = QDialogButtonBox(self)
        self.newButton = buttonBox.addButton(m18n("&New"), QDialogButtonBox.ActionRole)
        self.newButton.setIcon(KIcon("document-new"))
        self.newButton.setToolTip(m18n("Allocate a new table"))
        self.newButton.clicked.connect(self.newTable)
        self.joinButton = buttonBox.addButton(m18n("&Join"), QDialogButtonBox.AcceptRole)
        self.joinButton.clicked.connect(self.joinTable)
        self.joinButton.setIcon(KIcon("list-add-user"))
        self.joinButton.setToolTip(m18n("Join a table"))
        self.leaveButton = buttonBox.addButton(m18n("&Leave"), QDialogButtonBox.AcceptRole)
        self.leaveButton.clicked.connect(self.leaveTable)
        self.leaveButton.setIcon(KIcon("list-remove-user"))
        self.leaveButton.setToolTip(m18n("Leave a table"))
        self.compareButton = buttonBox.addButton(m18nc('Kajongg-Ruleset','Compare'), QDialogButtonBox.AcceptRole)
        self.compareButton.clicked.connect(self.compareRuleset)
        self.compareButton.setIcon(KIcon("preferences-plugin-script"))
        self.compareButton.setToolTip(m18n('Compare the rules of this table with my own rulesets'))
        self.startButton = buttonBox.addButton(m18n('&Start'), QDialogButtonBox.AcceptRole)
        self.startButton.clicked.connect(self.startGame)
        self.startButton.setIcon(KIcon("arrow-right"))
        self.startButton.setToolTip(m18n("Start playing on a table. Empty seats will be taken by robot players."))

        cmdLayout = QHBoxLayout()
        cmdLayout.addWidget(buttonBox)

        layout = QVBoxLayout()
        layout.addWidget(self.view)
        layout.addLayout(cmdLayout)
        self.setLayout(layout)

        self.view.doubleClicked.connect(self.joinTable)
        StateSaver(self, self.view.horizontalHeader())
        self.login()

    @apply
    def hideForever(): # pylint: disable=E0202
        """we never want to see this table list for local games,
        after joining a table or with autoPlay active"""
        def fget(self):
            # pylint: disable=W0212
            return self.__hideForever
        def fset(self, value):
            # pylint: disable=W0212
            self.__hideForever = value
            if value:
                self.hide()
        return property(**locals())

    def login(self):
        """when not logged in, do not yet show, login first.
        The loginDialog callback will really show()"""
        if not self.client or not self.client.perspective:
            try:
                self.client = HumanClient(self, self.afterLogin)
            except Exception as exception: # pylint: disable=W0703
                # yes we want to catch all exceptions
                logWarning(exception)
                self.hide()

    def show(self):
        """prepare the view and show it"""
        if self.hideForever:
            return
        assert not InternalParameters.autoPlay
        if self.client.hasLocalServer():
            title = m18n('Local Games with Ruleset %1', self.client.ruleset.name)
        else:
            title = m18n('Tables at %1', self.client.host)
        self.setWindowTitle(title + ' - Kajongg')
        self.view.hideColumn(1)
        tableCount = self.view.model().rowCount(None) if self.view.model() else 0
        self.view.showColumn(0)
        self.view.showColumn(2)
        self.view.showColumn(4)
        if tableCount or not self.client.hasLocalServer():
            QWidget.show(self)
            if self.client.hasLocalServer():
                self.view.hideColumn(0)
                self.view.hideColumn(2)
                self.view.hideColumn(4)

    def afterLogin(self):
        """callback after the server answered our login request"""
        if self.client and self.client.perspective:
            voiceId = None
            if PREF.uploadVoice:
                voice = Voice.locate(self.client.username)
                if voice:
                    voiceId = voice.md5sum
                if Debug.sound and voiceId:
                    logDebug('%s sends own voice %s to server' % (self.client.username, voiceId))
            maxGameId = Query('select max(id) from game').records[0][0]
            maxGameId = int(maxGameId) if maxGameId else 0
            self.client.callServer('setClientProperties',
                str(Query.dbhandle.databaseName()),
                voiceId, maxGameId, InternalParameters.version). \
                    addErrback(self.versionError). \
                    addCallback(self.client.callServer, 'sendTables'). \
                    addCallback(self.gotTables)
        else:
            self.hide()

    def newLocalTable(self, newId):
        """we just got newId from the server"""
        self.client.callServer('startGame', newId).addErrback(self.tableError)

    def closeEvent(self, dummyEvent):
        """closing table list: logout from server"""
        self.client.callServer('logout')
        self.client = None

    def selectTable(self, idx):
        """select table by idx"""
        self.view.selectRow(idx)
        self.updateButtonsForTable(self.selectedTable())

    def updateButtonsForTable(self, table):
        """update button status for the currently selected table"""
        hasTable = bool(table)
        suspended = hasTable and table.status.startswith('Suspended')
        suspendedLocalGame = suspended and table.gameid and self.client.hasLocalServer()
        self.joinButton.setEnabled(hasTable and \
            (self.client.username in table.playerNames) == suspended)
        for btn in [self.leaveButton, self.startButton, self.compareButton]:
            btn.setVisible(not (suspendedLocalGame))
        if suspendedLocalGame:
            self.newButton.setToolTip(m18n("Start a new game"))
            self.joinButton.setText(m18nc('resuming a local suspended game', '&Resume'))
            self.joinButton.setToolTip(m18n("Resume the selected suspended game"))
        else:
            self.newButton.setToolTip(m18n("Allocate a new table"))
            self.joinButton.setText(m18n('&Join'))
            self.joinButton.setToolTip(m18n("Join a table"))
        self.leaveButton.setEnabled(not self.joinButton.isEnabled())
        self.startButton.setEnabled(not suspendedLocalGame and hasTable \
            and self.client.username == table.playerNames[0])
        self.compareButton.setEnabled(hasTable and table.myRuleset is None)

    def selectionChanged(self, selected, dummyDeselected):
        """update button states according to selection"""
        if selected.indexes():
            self.selectTable(selected.indexes()[0].row())

    @staticmethod
    def __wantedGame():
        """find out which game we want to start on the table"""
        result = InternalParameters.game
        if not result or result == '0':
            result = str(int(random.random() * 10**9))
        InternalParameters.game = None
        return result

    def newTable(self):
        """I am a slot"""
        if self.client.hasLocalServer():
            ruleset = self.client.ruleset
        else:
            selectDialog = SelectRuleset(self.client.host)
            if not selectDialog.exec_():
                return
            ruleset = selectDialog.cbRuleset.current
        deferred = self.client.callServer('newTable', ruleset.toList(),
            InternalParameters.playOpen, InternalParameters.autoPlay, self.__wantedGame())
        if self.client.hasLocalServer():
            self.hideForever = True
            deferred.addCallback(self.newLocalTable)

    def gotTables(self, tables):
        """got tables for first time. If we play a local game and we have no
        suspended game, automatically start a new one"""
        clientTables = ClientTable.parseTables(tables)
        if not InternalParameters.autoPlay:
            if self.client.hasLocalServer():
                # when playing a local game, only show pending tables with
                # previously selected ruleset
                clientTables = list(x for x in clientTables if x.ruleset == self.client.ruleset)
        if InternalParameters.autoPlay or (not clientTables and self.client.hasLocalServer()):
            self.hideForever = True
            self.client.callServer('newTable', self.client.ruleset.toList(), InternalParameters.playOpen,
                InternalParameters.autoPlay,
                self.__wantedGame()).addCallback(self.newLocalTable)
        else:
            self.loadTables(clientTables)
            self.show()

    def selectedTable(self):
        """returns the selected table"""
        if self.view.selectionModel():
            index = self.view.selectionModel().currentIndex()
            if index.isValid() and self.view.model():
                return self.view.model().tables[index.row()]

    def joinTable(self):
        """join a table"""
        table = self.selectedTable()
        if len(table.humanPlayerNames()) - 1 == sum(table.playersOnline):
            # we are the last human player joining, so the server will start the game
            self.hideForever = True
        self.client.callServer('joinTable', table.tableid).addErrback(self.tableError)

    def compareRuleset(self):
        """compare the ruleset of this table against ours"""
        table = self.selectedTable()
        self.differ = RulesetDiffer(table.ruleset, Ruleset.availableRulesets())
        self.differ.show()

    def startGame(self):
        """start playing at the selected table"""
        table = self.selectedTable()
        self.startButton.setEnabled(False)
        self.client.callServer('startGame', table.tableid).addErrback(self.tableError)

    @staticmethod
    def versionError(err):
        """log the twisted error"""
        logWarning(err.getErrorMessage())
        InternalParameters.field.abortGame()
        return err

    @staticmethod
    def tableError(err):
        """log the twisted error"""
        logWarning(err.getErrorMessage())

    def leaveTable(self):
        """leave a table"""
        self.client.callServer('leaveTable', self.selectedTable().tableid)

    def loadTables(self, tables):
        """build and use a model around the tables.
        Show all new tables (no gameid given yet) and all suspended
        tables that also exist locally. In theory all suspended games should
        exist locally but there might have been bugs or somebody might
        have removed the local database like when reinstalling linux"""
        if Debug.traffic:
            for table in tables:
                if not table.gameid:
                    logDebug('%s has no gameid' % table)
                elif not table.gameExistsLocally():
                    logDebug('%s does not exist locally' % table)
        tables = [x for x in tables if not x.gameid or x.gameExistsLocally()]
        model = TablesModel(tables)
        self.view.setModel(model)
        selection = QItemSelectionModel(model, self.view)
        self.view.initView()
        self.view.setSelectionModel(selection)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SingleSelection)
        selection.selectionChanged.connect(self.selectionChanged)
        if len(tables) == 1:
            self.startButton.setFocus()
        elif not tables:
            self.newButton.setFocus()
        if not InternalParameters.autoPlay:
            self.show()
        if not self.selectedTable() and self.view.model().rowCount():
            self.selectTable(0)
        self.view.setFocus()
