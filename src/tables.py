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

from PyKDE4.kdeui import KIcon

from PyQt4.QtCore import SIGNAL,  Qt,  QVariant,  \
        QAbstractTableModel
from PyQt4.QtGui import QDialogButtonBox,  QTableView,  QWidget, \
        QHBoxLayout,  QVBoxLayout,  QSizePolicy,  QAbstractItemView,  \
        QItemSelectionModel

from util import logException, logWarning, m18n, StateSaver
from client import HumanClient
from query import Query

class TablesModel(QAbstractTableModel):
    """a model for our  tables"""
    def __init__(self,  tables, parent = None):
        super(TablesModel, self).__init__(parent)
        self.tables = tables

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """show header data"""
        if role == Qt.TextAlignmentRole:
            if orientation == Qt.Horizontal:
                return QVariant(int(Qt.AlignHCenter|Qt.AlignVCenter))
        if role != Qt.DisplayRole:
            return QVariant()
        if orientation == Qt.Horizontal:
            if section == 0:
                return QVariant(m18n('Table'))
            elif section == 1:
                return QVariant(m18n('Players'))
            else:
                return QVariant('')
        return QVariant(int(section+1))

    def rowCount(self, parent):
        """how many tables are in the model?"""
        if parent.isValid():
            return 0
        else:
            return len(self.tables)

    def columnCount(self, parent):
        """for now we only have id and players"""
        return 2

    def data(self, index, role=None):
        """score table data"""
        if role == Qt.TextAlignmentRole:
            if index.column() == 0:
                return QVariant(int(Qt.AlignHCenter|Qt.AlignVCenter))
            else:
                return QVariant(int(Qt.AlignLeft|Qt.AlignVCenter))
        if role != Qt.DisplayRole:
            return QVariant()
        if not index.isValid() or \
            not (0 <= index.row() < len(self.tables)):
                return QVariant()
        table = self.tables[index.row()]
        if role is None:
            role = Qt.DisplayRole
        if role == Qt.DisplayRole and index.column() == 0:
            return QVariant(table[0])
        elif role == Qt.DisplayRole and index.column() == 1:
            table = self.tables[index.row()]
            names = ', '.join(list(table[1:][0]))
            return QVariant(names)
        return None

class TableList(QWidget):
    """a widget for viewing, joining, leaving tables"""
    def __init__(self, field):
        super(TableList, self).__init__(None)
        self.field = field
        self.client = None
        self.selection = None
        self.selectedTable = None
        self.setObjectName('TableList')
        self.resize(700, 400)
        self.view = QTableView(self)
        pol = QSizePolicy()
        pol.setHorizontalPolicy(QSizePolicy.Expanding)
        pol.setVerticalPolicy(QSizePolicy.Expanding)
        self.view.setSizePolicy(pol)
        self.view.verticalHeader().hide()

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
        self.startButton = self.buttonBox.addButton(m18n('&Start'), QDialogButtonBox.AcceptRole)
        self.connect(self.startButton, SIGNAL('clicked(bool)'), self.startGame)
        self.startButton.setIcon(KIcon("arrow-right"))

        cmdLayout = QHBoxLayout()
        cmdLayout.addWidget(self.buttonBox)

        layout = QVBoxLayout()
        layout.addWidget(self.view)
        layout.addLayout(cmdLayout)
        self.setLayout(layout)
        self.state = StateSaver(self)

        self.connect(self.view, SIGNAL("doubleClicked(QModelIndex)"), self.joinTable)
        self.show()

    def show(self):
        """when not logged in, do not yet show, login first.
        The login callback will really show()"""
        if not self.client or not self.client.perspective:
            try:
                self.client = HumanClient(self, self.afterLogin)
            except Exception as exception:
                logWarning(str(exception))
                self.hide()
                return
            self.setWindowTitle(m18n('Tables at %1',  self.client.host) + ' - kmj')
        else:
            QWidget.show(self)

    def afterLogin(self):
        """callback after the server answered our login request"""
        if self.client and self.client.perspective:
            self.client.callServer('setDbPath', str(Query.dbhandle.databaseName())).addErrback(self.error)
            QWidget.show(self)
        else:
            self.hide()

    def closeEvent(self, event):
        self.client.callServer('logout')
        self.client = None

    def selectionChanged(self):
        """update button states according to selection"""
        selectedRows = len(self.selection.selectedRows())
        self.joinButton.setEnabled(selectedRows == 1)
        self.leaveButton.setEnabled(selectedRows == 1)

    def newTable(self):
        """I am a slot"""
        self.client.callServer('newTable')

    def selectedTables(self, single=True):
        """returns a list of selected tableids"""
        selnum = len(self.selection.selectedRows())
        if  selnum < 1 or (single and selnum != 1):
            # should never happen
            logException(Exception('%d rows selected' % selnum))
        result = list()
        for  index in self.view.selectionModel().selectedRows(0):
            result.append(index.data().toInt()[0])
        return result

    def joinTable(self):
        """join a table"""
        self.client.callServer('joinTable', self.selectedTables()[0]).addErrback(self.error)

    def startGame(self):
        """start playing at the selected table"""
        table = self.selectedTables()[0]
        self.startButton.setEnabled(False)
        self.client.callServer('startGame', table).addErrback(self.error)

    @staticmethod
    def error(err):
        """log the twisted error"""
        logWarning(err.getErrorMessage())

    def leaveTable(self):
        """leave a table"""
        self.client.callServer('leaveTable', self.selectedTables()[0])

    def load(self, tables):
        """build and use a model around the tables"""
        model = TablesModel(tables)
        self.view.setModel(model)
        self.selection = QItemSelectionModel(model, self.view)
        self.view.setSelectionModel(self.selection)
        self.view.resizeColumnsToContents()
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.setAlternatingRowColors(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.selectionChanged()
        self.connect(self.selection,
            SIGNAL("selectionChanged ( QItemSelection, QItemSelection)"),
            self.selectionChanged)


