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

from PyKDE4.kdeui import KIcon, KDialogButtonBox

from PyQt4.QtCore import SIGNAL, SLOT, Qt, QVariant,  \
        QAbstractTableModel
from PyQt4.QtGui import QDialog, QDialogButtonBox, QTableView, QWidget, \
        QHBoxLayout, QVBoxLayout, QSizePolicy, QAbstractItemView,  \
        QItemSelectionModel, QGridLayout, QColor

from util import logWarning, m18n, m18nc
from statesaver import StateSaver
from humanclient import HumanClient
from query import Query
from scoringengine import Ruleset, PredefinedRuleset
from guiutil import ListComboBox
from differ import RulesetDiffer
from sound import Voice
from common import InternalParameters

class TablesModel(QAbstractTableModel):
    """a model for our tables"""
    def __init__(self, tables, parent = None):
        super(TablesModel, self).__init__(parent)
        self.tables = tables

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """show header"""
        if role == Qt.TextAlignmentRole:
            if orientation == Qt.Horizontal:
                if section == 2:
                    return QVariant(int(Qt.AlignLeft))
                else:
                    return QVariant(int(Qt.AlignHCenter|Qt.AlignVCenter))
        if role != Qt.DisplayRole:
            return QVariant()
        if orientation == Qt.Horizontal:
            if section == 0:
                return QVariant(m18n('Table'))
            elif section == 1:
                return QVariant(m18n('Players'))
            elif section == 2:
                return QVariant(m18n('Ruleset'))
            else:
                return QVariant('')
        return QVariant(int(section+1))

    def rowCount(self, parent):
        """how many tables are in the model?"""
        if parent.isValid():
            return 0
        else:
            return len(self.tables)

    def columnCount(self, dummyParent):
        """for now we only have id, players, ruleset"""
        return 3

    def data(self, index, role=Qt.DisplayRole):
        """score table"""
        if role == Qt.TextAlignmentRole:
            if index.column() == 0:
                return QVariant(int(Qt.AlignHCenter|Qt.AlignVCenter))
            else:
                return QVariant(int(Qt.AlignLeft|Qt.AlignVCenter))
        if not index.isValid() or \
            not (0 <= index.row() < len(self.tables)):
            return QVariant()
        table = self.tables[index.row()]
        if role == Qt.DisplayRole and index.column() == 0:
            return QVariant(table.tableid)
        elif role == Qt.DisplayRole and index.column() == 1:
            table = self.tables[index.row()]
            names = ', '.join(table.playerNames)
            return QVariant(names)
        elif index.column() == 2:
            table = self.tables[index.row()]
            if role == Qt.DisplayRole:
                return QVariant(m18n(table.ruleset.name))
            elif role == Qt.ForegroundRole:
                color = 'black' if table.myRuleset else 'red'
                return QVariant(QColor(color))
        return QVariant()

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
    def __init__(self, field):
        super(TableList, self).__init__(None)
        self.field = field
        self.autoStarted = False
        self.client = None
        self.selection = None
        self.setObjectName('TableList')
        self.resize(700, 400)
        self.view = QTableView(self)
        pol = QSizePolicy()
        pol.setHorizontalPolicy(QSizePolicy.Expanding)
        pol.setVerticalPolicy(QSizePolicy.Expanding)
        self.view.setSizePolicy(pol)
        self.view.verticalHeader().hide()
        self.differ = None

        self.buttonBox = QDialogButtonBox(self)
        self.newButton = self.buttonBox.addButton(m18n("&New"), QDialogButtonBox.ActionRole)
        self.newButton.setIcon(KIcon("document-new"))
        self.connect(self.newButton, SIGNAL('clicked(bool)'), self.newTable)
        self.joinButton = self.buttonBox.addButton(m18n("&Join"), QDialogButtonBox.AcceptRole)
        self.connect(self.joinButton, SIGNAL('clicked(bool)'), self.joinTable)
        self.joinButton.setIcon(KIcon("list-add-user"))
        self.leaveButton = self.buttonBox.addButton(m18n("&Leave"), QDialogButtonBox.AcceptRole)
        self.connect(self.leaveButton, SIGNAL('clicked(bool)'), self.leaveTable)
        self.leaveButton.setIcon(KIcon("list-remove-user"))
        self.compareButton = self.buttonBox.addButton(m18nc('Kajongg-Ruleset','Compare'), QDialogButtonBox.AcceptRole)
        self.connect(self.compareButton, SIGNAL('clicked(bool)'), self.compareRuleset)
        self.compareButton.setIcon(KIcon("preferences-plugin-script"))
        self.compareButton.setToolTip(m18n('Compare the rules of this table with my own rulesets'))
        self.startButton = self.buttonBox.addButton(m18n('&Start'), QDialogButtonBox.AcceptRole)
        self.connect(self.startButton, SIGNAL('clicked(bool)'), self.startGame)
        self.startButton.setIcon(KIcon("arrow-right"))

        cmdLayout = QHBoxLayout()
        cmdLayout.addWidget(self.buttonBox)

        layout = QVBoxLayout()
        layout.addWidget(self.view)
        layout.addLayout(cmdLayout)
        self.setLayout(layout)

        self.connect(self.view, SIGNAL("doubleClicked(QModelIndex)"), self.joinTable)
        self.viewState = StateSaver(self.view.horizontalHeader())
        self.state = StateSaver(self)
        self.show()

    def show(self):
        """when not logged in, do not yet show, login first.
        The loginDialog callback will really show()"""
        if not self.client or not self.client.perspective:
            try:
                self.client = HumanClient(self, self.afterLogin)
            except Exception as exception:
                logWarning(str(exception))
                self.hide()
                return
            self.setWindowTitle(m18n('Tables at %1', self.client.host) + ' - Kajongg')
        if not self.client.hasLocalServer():
            QWidget.show(self)

    def afterLogin(self):
        """callback after the server answered our login request"""
        if self.client and self.client.perspective:
            voice = Voice(self.client.username)
            voice.buildArchive()
            voiceId = voice.voiceDirectory
            if not voiceId.startswith('MD5'):
                # we have no voice sounds for this user name
                voiceId = None
            self.client.callServer('setClientProperties',
                str(Query.dbhandle.databaseName()),
                voice.voiceDirectory).addErrback(self.error)
            self.client.callServer('requestTables')
            if self.client.hasLocalServer():
                self.client.callServer('newTable', self.client.ruleset.toList(), InternalParameters.playOpen)
            else:
                QWidget.show(self)
        else:
            self.hide()

    def closeEvent(self, dummyEvent):
        """closing table list: logout from server"""
        self.client.callServer('logout')
        self.client = None

    def selectTable(self, idx):
        """select table by idx"""
        self.view.selectionModel().setCurrentIndex(self.view.model().index(idx, 0), QItemSelectionModel.ClearAndSelect)
        table = self.selectedTable()
        for btn in [self.joinButton, self.leaveButton, self.startButton]:
            btn.setEnabled(bool(table))
        self.compareButton.setEnabled(bool(table and not table.myRuleset))

    def selectionChanged(self, selected, dummyDeselected):
        """update button states according to selection"""
        self.selectTable(selected.indexes()[0].row())

    def newTable(self):
        """I am a slot"""
        selectDialog = SelectRuleset(self.client.host)
        if not selectDialog.exec_():
            return
        self.client.callServer('newTable', selectDialog.cbRuleset.current.toList(), InternalParameters.playOpen)

    def selectedTable(self):
        """returns the selected table"""
        index = self.view.selectionModel().currentIndex()
        if index.isValid():
            tableid = index.data().toInt()[0]
            for table in self.view.model().tables:
                if table.tableid == tableid:
                    return table

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

    def load(self, tableid, tables):
        """build and use a model around the tables"""
        model = TablesModel(tables)
        self.view.setModel(model)
        self.selection = QItemSelectionModel(model, self.view)
        self.view.setSelectionModel(self.selection)
        self.view.resizeColumnsToContents()
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.setAlternatingRowColors(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.selectTable(0)
        self.connect(self.selection,
            SIGNAL("selectionChanged ( QItemSelection, QItemSelection)"),
            self.selectionChanged)
        if self.client.hasLocalServer() and tableid and not self.autoStarted:
            for idx, table in enumerate(tables):
                if table.tableid == tableid:
                    self.autoStarted = True
                    self.selectTable(idx)
                    self.startGame()
            if not self.view.model().tables:
                self.newButton.setFocus()
        if len(tables) == 1:
            self.startButton.setFocus()
        elif not tables:
            self.newButton.setFocus()
