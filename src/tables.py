# -*- coding: utf-8 -*-

"""
Copyright (C) 2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

import datetime

from PyKDE4.kdeui import KIcon, KDialogButtonBox

from PyQt4.QtCore import SIGNAL, SLOT, Qt, QVariant,  \
        QAbstractTableModel
from PyQt4.QtGui import QDialog, QDialogButtonBox, QWidget, \
        QHBoxLayout, QVBoxLayout, QAbstractItemView,  \
        QItemSelectionModel, QGridLayout, QColor

from genericdelegates import RichTextColumnDelegate

from util import logWarning, m18n, m18nc
from statesaver import StateSaver
from humanclient import HumanClient
from query import Query
from scoringengine import Ruleset, PredefinedRuleset
from guiutil import ListComboBox, MJTableView
from differ import RulesetDiffer
from sound import Voice
from common import InternalParameters

class TablesModel(QAbstractTableModel):
    """a model for our tables"""
    def __init__(self, tables, parent = None):
        super(TablesModel, self).__init__(parent)
        self.tables = tables

    def headerData(self, section, orientation, role=Qt.DisplayRole): # pylint: disable-msg=R0201
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

    def rowCount(self, parent):
        """how many tables are in the model?"""
        if parent.isValid():
            return 0
        else:
            return len(self.tables)

    def columnCount(self, dummyParent): # pylint: disable-msg=R0201
        """for now we only have id (invisible), id (visible), players, status, ruleset.name.
        id(invisible) always holds the real id, also 1000 for suspended tables.
        id(visible) is what should be displayed."""
        return 5

    def data(self, index, role=Qt.DisplayRole):
        """score table"""
        # pylint: disable-msg=R0912
        # pylint: too many branches
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
                for name, online in zip(table.playerNames, table.playersOnline):
                    if online:
                        style = 'font-weight:normal;font-style:normal;color:black'
                    else:
                        style = 'font-weight:100;font-style:italic;color:gray'
                    players.append('<nobr style="%s">' % style + name + '</nobr>')
                names = ', '.join(players)
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
                    color = 'black' if table.myRuleset else 'red'
                    result = QVariant(QColor(color))
        return result

class SelectRuleset(QDialog):
    """a dialog for selecting a ruleset"""
    def __init__(self, server):
        QDialog.__init__(self, None)
        self.setWindowTitle(m18n('Select a ruleset') + ' - Kajongg')
        self.buttonBox = KDialogButtonBox(self)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.connect(self.buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(self.buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
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
    def __init__(self):
        super(TableList, self).__init__(None)
        self.autoStarted = False
        self.client = None
        self.setObjectName('TableList')
        self.resize(700, 400)
        self.view = MJTableView(self)
        self.differ = None
        self.view.setItemDelegateForColumn(2, RichTextColumnDelegate(self.view))

        buttonBox = QDialogButtonBox(self)
        self.newButton = buttonBox.addButton(m18n("&New"), QDialogButtonBox.ActionRole)
        self.newButton.setIcon(KIcon("document-new"))
        self.newButton.setToolTip(m18n("Allocate a new table"))
        self.connect(self.newButton, SIGNAL('clicked(bool)'), self.newTable)
        self.joinButton = buttonBox.addButton(m18n("&Join"), QDialogButtonBox.AcceptRole)
        self.connect(self.joinButton, SIGNAL('clicked(bool)'), self.joinTable)
        self.joinButton.setIcon(KIcon("list-add-user"))
        self.joinButton.setToolTip(m18n("Join a table"))
        self.leaveButton = buttonBox.addButton(m18n("&Leave"), QDialogButtonBox.AcceptRole)
        self.connect(self.leaveButton, SIGNAL('clicked(bool)'), self.leaveTable)
        self.leaveButton.setIcon(KIcon("list-remove-user"))
        self.leaveButton.setToolTip(m18n("Leave a table"))
        self.compareButton = buttonBox.addButton(m18nc('Kajongg-Ruleset','Compare'), QDialogButtonBox.AcceptRole)
        self.connect(self.compareButton, SIGNAL('clicked(bool)'), self.compareRuleset)
        self.compareButton.setIcon(KIcon("preferences-plugin-script"))
        self.compareButton.setToolTip(m18n('Compare the rules of this table with my own rulesets'))
        self.startButton = buttonBox.addButton(m18n('&Start'), QDialogButtonBox.AcceptRole)
        self.connect(self.startButton, SIGNAL('clicked(bool)'), self.startGame)
        self.startButton.setIcon(KIcon("arrow-right"))
        self.startButton.setToolTip(m18n("Start playing on a table. Empty seats will be taken by robot players."))

        cmdLayout = QHBoxLayout()
        cmdLayout.addWidget(buttonBox)

        layout = QVBoxLayout()
        layout.addWidget(self.view)
        layout.addLayout(cmdLayout)
        self.setLayout(layout)

        self.connect(self.view, SIGNAL("doubleClicked(QModelIndex)"), self.joinTable)
        StateSaver(self, self.view.horizontalHeader())
        self.show()

    def show(self):
        """when not logged in, do not yet show, login first.
        The loginDialog callback will really show()"""
        if not self.client or not self.client.perspective:
            try:
                self.client = HumanClient(self, self.afterLogin)
            except Exception as exception: # pylint: disable-msg=W0703
                # yes we want to catch all exceptions
                logWarning(exception)
                self.hide()
                return
            self.setWindowTitle(m18n('Tables at %1', self.client.host) + ' - Kajongg')
        if not self.client.hasLocalServer():
            QWidget.show(self)
            self.updateButtonsForTable(None)
        self.view.hideColumn(1)

    def afterLogin(self):
        """callback after the server answered our login request"""
        if self.client and self.client.perspective:
            voice = Voice(self.client.username)
            voice.buildArchive()
            voiceId = voice.voiceDirectory
            if not voiceId.startswith('MD5'):
                # we have no voice sounds for this user name
                voiceId = None
            maxGameId = int(Query('select max(id) from game').records[0][0])
            self.client.callServer('setClientProperties',
                str(Query.dbhandle.databaseName()),
                voice.voiceDirectory,
                maxGameId).addErrback(self.error)
            if self.client.hasLocalServer():
                self.client.callServer('newTable', self.client.ruleset.toList(), InternalParameters.playOpen,
                    InternalParameters.seed).addCallback(self.newLocalTable)
            else:
                self.client.callServer('sendTables')
                QWidget.show(self)
        else:
            self.hide()

    def newLocalTable(self, newId):
        """we just got newId from the server"""
        self.client.callServer('startGame', newId).addErrback(self.error)

    def closeEvent(self, dummyEvent):
        """closing table list: logout from server"""
        self.client.callServer('logout')
        self.client = None

    def selectTable(self, idx):
        """select table by idx"""
        self.view.selectionModel().setCurrentIndex(self.view.model().index(idx, 0), QItemSelectionModel.ClearAndSelect)
        self.updateButtonsForTable(self.selectedTable())

    def updateButtonsForTable(self, table):
        """update button status for the currently selected table"""
        hasTable = bool(table)
        suspended = hasTable and table.status.startswith('Suspended')
        self.joinButton.setEnabled(hasTable and \
            (self.client.username in table.playerNames) == suspended)
        self.leaveButton.setEnabled(not self.joinButton.isEnabled())
        self.startButton.setEnabled(hasTable and self.client.username == table.playerNames[0])
        self.compareButton.setEnabled(hasTable and table.myRuleset is None)

    def selectionChanged(self, selected, dummyDeselected):
        """update button states according to selection"""
        self.selectTable(selected.indexes()[0].row())

    def newTable(self):
        """I am a slot"""
        selectDialog = SelectRuleset(self.client.host)
        if not selectDialog.exec_():
            return
        self.client.callServer('newTable', selectDialog.cbRuleset.current.toList(), InternalParameters.playOpen,
            InternalParameters.seed)

    def selectedTable(self):
        """returns the selected table"""
        index = self.view.selectionModel().currentIndex()
        if index.isValid():
            return self.view.model().tables[index.row()]

    def joinTable(self):
        """join a table"""
        self.client.callServer('joinTable', self.selectedTable().tableid).addErrback(self.error)

    def compareRuleset(self):
        """compare the ruleset of this table against ours"""
        table = self.selectedTable()
        self.differ = RulesetDiffer(table.ruleset, Ruleset.availableRulesets() + PredefinedRuleset.rulesets())
        self.differ.show()

    def startGame(self):
        """start playing at the selected table"""
        table = self.selectedTable()
        self.startButton.setEnabled(False)
        self.client.callServer('startGame', table.tableid).addErrback(self.error)

    @staticmethod
    def error(err):
        """log the twisted error"""
        logWarning(err.getErrorMessage())

    def leaveTable(self):
        """leave a table"""
        self.client.callServer('leaveTable', self.selectedTable().tableid)

    def load(self, tables):
        """build and use a model around the tables"""
        model = TablesModel(tables)
        self.view.setModel(model)
        selection = QItemSelectionModel(model, self.view)
        self.view.initView()
        self.view.setSelectionModel(selection)
        self.view.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.selectTable(0)
        self.connect(selection,
            SIGNAL("selectionChanged ( QItemSelection, QItemSelection)"),
            self.selectionChanged)
        if len(tables) == 1:
            self.startButton.setFocus()
        elif not tables:
            self.newButton.setFocus()
