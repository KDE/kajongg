# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

import datetime

from qt import Qt, QModelIndex
from qt import QAbstractTableModel, QDialogButtonBox, QDialog
from qt import QHBoxLayout, QVBoxLayout, QCheckBox
from qt import QItemSelectionModel, QAbstractItemView

from dialogs import WarningYesNo
from kde import KIcon
from mi18n import i18n, i18nc
from log import logException
from query import Query
from guiutil import MJTableView, decorateWindow
from statesaver import StateSaver
from common import Debug
from modeltest import ModelTest


class GamesModel(QAbstractTableModel):

    """data for the list of games"""

    def __init__(self):
        QAbstractTableModel.__init__(self)
        self._resultRows = []

    def columnCount(self, unusedParent=QModelIndex()):
        """including the hidden col 0"""
        return 3

    def rowCount(self, parent=QModelIndex()):
        """how many games"""
        if parent.isValid():
            # we have only top level items
            return 0
        return len(self._resultRows)

    def setResultset(self, rows):
        """new data"""
        self.beginResetModel()
        try:
            self._resultRows = rows
        finally:
            self.endResetModel()

    def index(self, row, column, parent=QModelIndex()):
        """helper"""
        if (row < 0
                or column < 0
                or row >= self.rowCount(parent)
                or column >= self.columnCount(parent)):
	    # similar in tree.py
            return QModelIndex()
        return self.createIndex(row, column, 0)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """get score table from view"""
        if role is None:
            role = Qt.ItemDataRole.DisplayRole
        if not (index.isValid() and role == Qt.ItemDataRole.DisplayRole):
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            unformatted = str(
                self._resultRows[index.row()][index.column()]) # TODO: brauche ich str?
            if index.column() == 2:
                # we do not yet use this for listing remote games but if we do
                # this translation is needed for robot players
                names = [i18n(name) for name in unformatted.split('///')]
                return ', '.join(names)
            if index.column() == 1:
                dateVal = datetime.datetime.strptime(
                    unformatted, '%Y-%m-%dT%H:%M:%S')
                return dateVal.strftime('%c')
            if index.column() == 0:
                return int(unformatted)
        return QAbstractTableModel.data(self, index, role)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        """for the two visible columns"""
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return i18n('Players') if section == 2 else i18n('Started')
        return None


class Games(QDialog):

    """a dialog for selecting a game"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selectedGame = None
        self.onlyPending = True
        decorateWindow(self, i18nc("@title:window", "Games"))
        self.setObjectName('Games')
        self.resize(700, 400)
        self.model = GamesModel()
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
        self.newButton = self.buttonBox.addButton(
            i18nc('start a new game', "&New"), QDialogButtonBox.ActionRole)
        self.newButton.setIcon(KIcon("document-new"))
        self.newButton.clicked.connect(self.accept)
        self.loadButton = self.buttonBox.addButton(
            i18n("&Load"), QDialogButtonBox.AcceptRole)
        self.loadButton.clicked.connect(self.loadGame)
        self.loadButton.setIcon(KIcon("document-open"))
        self.deleteButton = self.buttonBox.addButton(
            i18n("&Delete"), QDialogButtonBox.ActionRole)
        self.deleteButton.setIcon(KIcon("edit-delete"))
        self.deleteButton.clicked.connect(self.delete)

        chkPending = QCheckBox(i18n("Show only pending games"), self)
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

    def showEvent(self, unusedEvent):
        """only now get the data set. Not doing this in__init__ would eventually
        make it easier to subclass from some generic TableEditor class"""
        self.setQuery()
        self.view.initView()
        self.selectionChanged()

    def keyPressEvent(self, event):
        """use insert/delete keys for insert/delete"""
        key = event.key()
        if key == Qt.Key.Key_Insert:
            self.newEntry()
            return
        if key == Qt.Key.Key_Delete:
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
        query = Query(
            "select g.id, g.starttime, "
            "p0.name||'///'||p1.name||'///'||p2.name||'///'||p3.name "
            "from game g, player p0,"
            "player p1, player p2, player p3 "
            "where seed is null"
            " and p0.id=g.p0 and p1.id=g.p1 "
            " and p2.id=g.p2 and p3.id=g.p3 "
            "%s"
            "and exists(select 1 from score where game=g.id)" %
            ("and g.endtime is null " if self.onlyPending else ""))
        self.model.setResultset(query.records)
        self.view.hideColumn(0)

    def __idxForGame(self, game):
        """return the model index for game"""
        for row in range(self.model.rowCount()):
            idx = self.model.index(row, 0)
            if self.model.data(idx, 0) == game:
                return idx
        return self.model.index(0, 0)

    def __getSelectedGame(self):
        """return the game id of the selected game"""
        rows = self.selection.selectedRows()
        return self.model.data(rows[0], 0) if rows else QModelIndex()

    def pendingOrNot(self, chosen):
        """do we want to see all games or only pending games?"""
        if self.onlyPending != bool(chosen):
            self.onlyPending = bool(chosen)
            prevSelected = self.__getSelectedGame()
            self.setQuery()
            idx = self.__idxForGame(prevSelected)
            self.view.selectRow(idx.row())
        self.view.setFocus()

    def loadGame(self):
        """load a game"""
        self.selectedGame = self.__getSelectedGame()
        self.buttonBox.accepted.emit()

    def delete(self):
        """delete a game"""
        def answered(result, games):
            """question answered, result is True or False"""
            if result:
                for game in games:
                    Query("DELETE FROM score WHERE game = ?", (game, ))
                    Query("DELETE FROM game WHERE id = ?", (game, ))
                self.setQuery()  # just reload entire table
        allGames = self.view.selectionModel().selectedRows(0)
        deleteGames = [x.data() for x in allGames]
        if not deleteGames:
            # should never happen
            logException('delete: 0 rows selected')
        WarningYesNo(
            i18n(
                "Do you really want to delete <numid>%1</numid> games?<br>"
                "This will be final, you cannot cancel it with "
                "the cancel button",
                len(deleteGames))).addCallback(answered, deleteGames)
