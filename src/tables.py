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

from util import logWarning, m18n, m18nc, m18nE, logDebug
from statesaver import StateSaver
from rule import Ruleset
from guiutil import ListComboBox, MJTableView
from differ import RulesetDiffer
from common import InternalParameters, Debug
from client import ClientTable
from modeltest import ModelTest
from chat import ChatMessage, ChatWindow

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

    def rowCount(self, parent=None):
        """how many tables are in the model?"""
        if parent and parent.isValid():
            # we have only top level items
            return 0
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
            if role == Qt.DisplayRole and index.column() in (0, 1):
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
                status = table.status()
                if table.suspendedAt:
                    dateVal = ' ' + datetime.datetime.strptime(table.suspendedAt,
                        '%Y-%m-%dT%H:%M:%S').strftime('%c').decode('utf-8')
                    status = 'Suspended'
                else:
                    dateVal = ''
                result = QVariant(m18nc('table status', status) + dateVal)
            elif index.column() == 4:
                if role == Qt.DisplayRole:
                    result = QVariant(m18n((table.myRuleset if table.myRuleset else table.ruleset).name))
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
    def __init__(self, client):
        super(TableList, self).__init__(None)
        self.autoStarted = False
        self.client = client
        self.setObjectName('TableList')
        self.resize(700, 400)
        self.view = MJTableView(self)
        self.differ = None
        self.debugModelTest = None
        self.__requestedNewTable = False
        self.view.setItemDelegateForColumn(2, RichTextColumnDelegate(self.view))

        buttonBox = QDialogButtonBox(self)
        self.newButton = buttonBox.addButton(m18nc('allocate a new table', "&New"), QDialogButtonBox.ActionRole)
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
        self.chatButton = buttonBox.addButton(m18n('&Chat'), QDialogButtonBox.AcceptRole)
        self.chatButton.setIcon(KIcon("call-start"))
        self.chatButton.clicked.connect(self.chat)
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
        self.updateButtonsForTable(None)

    def hideEvent(self, dummyEvent): # pylint: disable=R0201
        """table window hides"""
        field = InternalParameters.field
        field.startingGame = False
        if not field.game or field.game.client != self.client:
            # do we still need this connection?
            self.client.logout()

    def chat(self):
        """chat. Only generate ChatWindow after the
        message has successfully been sent to the server.
        Because the server might have gone away."""
        def initChat(_):
            """now that we were able to send the message to the server
            instantiate the chat window"""
            table.chatWindow = ChatWindow(table)
            table.chatWindow.receiveLine(msg)
        table = self.selectedTable()
        if not table.chatWindow:
            line = m18nE('opens a chat window')
            msg = ChatMessage(table.tableid, table.client.username, line, isStatusMessage=True)
            table.client.sendChat(msg).addCallback(initChat).addErrback(self.tableError)
        elif table.chatWindow.isVisible():
            table.chatWindow.hide()
        else:
            table.chatWindow.show()

    def show(self):
        """prepare the view and show it"""
        assert not InternalParameters.demo
        if self.client.hasLocalServer():
            title = m18n('Local Games with Ruleset %1', self.client.ruleset.name)
        else:
            title = m18n('Tables at %1', self.client.url)
        self.setWindowTitle(' - '.join([self.client.username, title, 'Kajongg']))
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

    def newLocalTable(self, newId):
        """we just got newId from the server"""
        self.client.callServer('startGame', newId).addErrback(self.tableError)

    def selectTable(self, idx):
        """select table by idx"""
        self.view.selectRow(idx)
        self.updateButtonsForTable(self.selectedTable())

    def updateButtonsForTable(self, table):
        """update button status for the currently selected table"""
        hasTable = bool(table)
        suspended = hasTable and bool(table.suspendedAt)
        running = hasTable and table.running
        suspendedLocalGame = suspended and table.gameid and self.client.hasLocalServer()
        self.joinButton.setEnabled(hasTable and
            not running and
            not table.isOnline(self.client.username) and
            (self.client.username in table.playerNames) == suspended)
        self.leaveButton.setVisible(not (suspendedLocalGame))
        self.compareButton.setVisible(not (suspendedLocalGame))
        self.startButton.setVisible(not suspended)
        if suspendedLocalGame:
            self.newButton.setToolTip(m18n("Start a new game"))
            self.joinButton.setText(m18nc('resuming a local suspended game', '&Resume'))
            self.joinButton.setToolTip(m18n("Resume the selected suspended game"))
        else:
            self.newButton.setToolTip(m18n("Allocate a new table"))
            self.joinButton.setText(m18n('&Join'))
            self.joinButton.setToolTip(m18n("Join a table"))
        self.leaveButton.setEnabled(hasTable and not running and not self.joinButton.isEnabled())
        self.startButton.setEnabled(not running and not suspendedLocalGame and hasTable \
            and self.client.username == table.playerNames[0])
        self.compareButton.setEnabled(hasTable and table.myRuleset is None)
        self.chatButton.setVisible(not self.client.hasLocalServer())
        self.chatButton.setEnabled(not running and self.leaveButton.isEnabled())
        if self.chatButton.isEnabled():
            self.chatButton.setToolTip(m18n("Chat with others on this table"))
        else:
            self.chatButton.setToolTip(m18n("For chatting with others on this table, please first take a seat"))

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
        if InternalParameters.ruleset:
            ruleset = InternalParameters.ruleset
        elif self.client.hasLocalServer():
            ruleset = self.client.ruleset
        else:
            selectDialog = SelectRuleset(self.client.host)
            if not selectDialog.exec_():
                return
            ruleset = selectDialog.cbRuleset.current
        deferred = self.client.callServer('newTable', ruleset.toList(),
            InternalParameters.playOpen, InternalParameters.demo, self.__wantedGame()).addErrback(self.tableError)
        if self.client.hasLocalServer():
            deferred.addCallback(self.newLocalTable)
        self.__requestedNewTable = True

    def gotTables(self, tables):
        """got tables for first time. If we play a local game and we have no
        suspended game, automatically start a new one"""
        clientTables = list(ClientTable(self.client, *x) for x in tables) # pylint: disable=W0142
        if not InternalParameters.demo:
            if self.client.hasLocalServer():
                # when playing a local game, only show pending tables with
                # previously selected ruleset
                clientTables = list(x for x in clientTables if x.ruleset == self.client.ruleset)
        if InternalParameters.demo or (not clientTables and self.client.hasLocalServer()):
            deferred = self.client.callServer('newTable', self.client.ruleset.toList(), InternalParameters.playOpen,
                InternalParameters.demo,
                self.__wantedGame()).addErrback(self.tableError)
            if deferred:
                deferred.addCallback(self.newLocalTable)
        else:
            self.client.tables = clientTables
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

    def tableError(self, err):
        """log the twisted error"""
        if not self.client.connectedWithServer:
            # lost connection to server
            for table in self.view.model().tables:
                if table.chatWindow:
                    table.chatWindow.hide()
            self.hide()
            self.client.tableList = None
        else:
            logWarning(err.getErrorMessage())

    def leaveTable(self):
        """leave a table"""
        table = self.selectedTable()
        self.client.callServer('leaveTable', table.tableid).addErrback(self.tableError)

    def __keepChatWindows(self, tables):
        """copy chatWindows from the old table list which will be thrown away"""
        if self.view.model():
            chatWindows = dict((x.tableid, x.chatWindow) for x in self.view.model().tables)
            unusedWindows = set(x.chatWindow for x in self.view.model().tables)
            for table in tables:
                table.chatWindow = chatWindows.get(table.tableid, None)
                unusedWindows -= set([table.chatWindow])
            for unusedWindow in unusedWindows:
                if unusedWindow:
                    unusedWindow.hide()

    def __preselectTableId(self, tables):
        """which table should be preselected?
        If we just requested a new table:
          select first new table.
          Only in the rare case that two clients request a new table at the same
          moment, this could put the focus on the wrong table. Ignore that for now.
        else if we had one selected:
          select that again
        else:
          select first table"""
        if self.__requestedNewTable:
            self.__requestedNewTable = False
            newIds = sorted(list(set(x.tableid for x in tables) - set(x.tableid for x in self.view.model().tables)))
            if newIds:
                return newIds[0]
        if self.selectedTable():
            return self.selectedTable().tableid
        return 0

    def loadTables(self, tables):
        """build and use a model around the tables.
        Show all new tables (no gameid given yet) and all suspended
        tables that also exist locally. In theory all suspended games should
        exist locally but there might have been bugs or somebody might
        have removed the local database like when reinstalling linux"""
        if not InternalParameters.field:
            return
        if Debug.traffic:
            for table in tables:
                if not table.gameid:
                    logDebug('%s has no gameid' % table)
                elif not table.gameExistsLocally():
                    logDebug('%s does not exist locally' % table)
        tables = [x for x in tables if not x.gameid or x.gameExistsLocally()]
        tables.sort(key=lambda x: x.tableid)
        preselectTableId = self.__preselectTableId(tables)
        self.__keepChatWindows(tables)
        model = TablesModel(tables)
        self.view.setModel(model)
        if Debug.modelTest:
            self.debugModelTest = ModelTest(model, self.view)
        selection = QItemSelectionModel(model, self.view)
        self.view.initView()
        self.view.setSelectionModel(selection)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SingleSelection)
        selection.selectionChanged.connect(self.selectionChanged)
        if len(tables) == 1:
            self.selectTable(0)
            self.startButton.setFocus()
        elif not tables:
            self.newButton.setFocus()
        else:
            _ = [x for x in tables if x.tableid >= preselectTableId]
            self.selectTable(tables.index(_[0]) if _ else 0)
        self.updateButtonsForTable(self.selectedTable())
        self.view.setFocus()
