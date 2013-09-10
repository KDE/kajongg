# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

import datetime
from kde import WarningYesNo, KIcon

from PyQt4.QtCore import Qt, QVariant
from PyQt4.QtGui import QDialogButtonBox, QDialog, \
        QHBoxLayout, QVBoxLayout, QCheckBox, \
        QItemSelectionModel, QAbstractItemView
from PyQt4.QtSql import QSqlQueryModel

from util import logException, m18n, m18nc
from guiutil import MJTableView
from statesaver import StateSaver
from query import Query, DBHandle
from common import Debug
from modeltest import ModelTest

class GamesModel(QSqlQueryModel):
    """a model for our games table"""
    def __init__(self, parent=None):
        super(GamesModel, self).__init__(parent)

    def data(self, index, role=None):
        """get score table from view"""
        if role is None:
            role = Qt.DisplayRole
        if role == Qt.DisplayRole:
            unformatted = unicode(self.record(index.row()).value(index.column()).toString())
            if index.column()==2:
                # we do not yet use this for listing remote games but if we do
                # this translation is needed for robot players
                names = [m18n(name) for name in unformatted.split('///')]
                return QVariant(', '.join(names))
            elif index.column()==1:
                dateVal = datetime.datetime.strptime(unformatted, '%Y-%m-%dT%H:%M:%S')
                return QVariant(dateVal.strftime('%c').decode('utf-8'))
        return QSqlQueryModel.data(self, index, role)

class Games(QDialog):
    """a dialog for selecting a game"""
    def __init__(self, parent=None):
        super(Games, self).__init__(parent)
        self.selectedGame = None
        self.onlyPending = True
        self.setWindowTitle(m18nc('kajongg', 'Games') + ' - Kajongg')
        self.setObjectName('Games')
        self.resize(700, 400)
        self.model = GamesModel(self)
        if Debug.modelTest:
            self.modelTest = ModelTest(self.model, self)

        self.view = MJTableView(self)
        self.view.setModel(self.model)
        self.selection = QItemSelectionModel(self.model, self.view)
        self.view.setSelectionModel(self.selection)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SingleSelection)

        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel)
        self.newButton = self.buttonBox.addButton(m18nc('start a new game', "&New"), QDialogButtonBox.ActionRole)
        self.newButton.setIcon(KIcon("document-new"))
        self.newButton.clicked.connect(self.accept)
        self.loadButton = self.buttonBox.addButton(m18n("&Load"), QDialogButtonBox.AcceptRole)
        self.loadButton.clicked.connect(self.loadGame)
        self.loadButton.setIcon(KIcon("document-open"))
        self.deleteButton = self.buttonBox.addButton(m18n("&Delete"), QDialogButtonBox.ActionRole)
        self.deleteButton.setIcon(KIcon("edit-delete"))
        self.deleteButton.clicked.connect(self.delete)

        chkPending = QCheckBox(m18n("Show only pending games"), self)
        chkPending.setChecked(True)
        cmdLayout = QHBoxLayout()
        cmdLayout.addWidget(chkPending)
        cmdLayout.addWidget(self.buttonBox)

        layout = QVBoxLayout()
        layout.addWidget(self.view)
        layout.addLayout(cmdLayout)
        self.setLayout(layout)
        StateSaver(self)

        self.selection.selectionChanged.connect(self.selectionChanged)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.view.doubleClicked.connect(self.loadGame)
        chkPending.stateChanged.connect(self.pendingOrNot)

    def showEvent(self, dummyEvent):
        """only now get the data set. Not doing this in__init__ would eventually
        make it easier to subclass from some generic TableEditor class"""
        self.setQuery()
        self.view.initView()
        self.selectionChanged()

    def keyPressEvent(self, event):
        """use insert/delete keys for insert/delete"""
        key = event.key()
        if key == Qt.Key_Insert:
            self.newEntry()
            return
        if key == Qt.Key_Delete:
            self.delete()
            event.ignore()
            return
        QDialog.keyPressEvent(self, event)

    def selectionChanged(self):
        """update button states according to selection"""
        selectedRows = len(self.selection.selectedRows())
        self.loadButton.setEnabled(selectedRows == 1)
        self.deleteButton.setEnabled(selectedRows >= 1)

    def setQuery(self):
        """define the query depending on self.OnlyPending"""
        query = "select g.id, g.starttime, " \
            "p0.name||'///'||p1.name||'///'||p2.name||'///'||p3.name " \
            "from game g, player p0," \
            "player p1, player p2, player p3 " \
            "where seed is null" \
            " and p0.id=g.p0 and p1.id=g.p1 " \
            " and p2.id=g.p2 and p3.id=g.p3 " \
            "%s" \
            "and exists(select 1 from score where game=g.id)" % \
            ("and g.endtime is null " if self.onlyPending else "")
        self.model.setQuery(query, DBHandle.default)
        self.model.setHeaderData(1, Qt.Horizontal,
            QVariant(m18n("Started")))
        self.model.setHeaderData(2, Qt.Horizontal,
            QVariant(m18n("Players")))
        self.view.hideColumn(0)

    def __idxForGame(self, game):
        """returns the model index for game"""
        for row in range(self.model.rowCount()):
            if self.model.record(row).field(0).value().toInt()[0] == game:
                return self.model.index(row, 0)
        return self.model.index(0, 0)

    def pendingOrNot(self, chosen):
        """do we want to see all games or only pending games?"""
        if self.onlyPending != chosen:
            self.onlyPending = chosen
            idx = self.view.currentIndex()
            selectedGame = self.model.record(idx.row()).value(0).toInt()[0]
            self.setQuery()
            idx = self.__idxForGame(selectedGame)
            self.view.selectRow(idx.row())
        self.view.setFocus()

    def loadGame(self):
        """load a game"""
        selnum = len(self.selection.selectedRows())
        if selnum != 1:
            # should never happen
            logException('loadGame: %d rows selected' % selnum)
        idx = self.view.currentIndex()
        self.selectedGame = self.model.record(idx.row()).value(0).toInt()[0]
        self.buttonBox.accepted.emit()

    def delete(self):
        """delete a game"""
        def answered(result, games):
            """question answered, result is True or False"""
            if result:
                cmdList = []
                for game in games:
                    cmdList.append("DELETE FROM score WHERE game = %d" % game)
                    cmdList.append("DELETE FROM game WHERE id = %d" % game)
                Query(cmdList)
                self.setQuery() # just reload entire table
        deleteGames = list(x.data().toInt()[0] for x in self.view.selectionModel().selectedRows(0))
        if len(deleteGames) == 0:
            # should never happen
            logException('delete: 0 rows selected')
        WarningYesNo(
            m18n("Do you really want to delete <numid>%1</numid> games?<br>" \
            "This will be final, you cannot cancel it with the cancel button",
            len(deleteGames))).addCallback(answered, deleteGames)
