#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008,2009 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

import datetime
from PyQt4 import  QtGui,  QtSql
from PyKDE4 import  kdeui
from PyKDE4.kdecore import  i18n
from PyKDE4.kdeui import KDialogButtonBox,  KMessageBox

from PyQt4.QtCore import SIGNAL,  SLOT,  Qt,  QVariant,  QString
from PyQt4.QtGui import QDialogButtonBox,  QTableView,  QDialog,  QApplication, \
        QHBoxLayout,  QVBoxLayout,  QSizePolicy,  QAbstractItemView,  QCheckBox
from PyQt4.QtSql import QSqlQuery

from util import logException

class GamesModel(QtSql.QSqlQueryModel):
    """a model for our games table"""
    def __init__(self,  parent = None):
        super(GamesModel, self).__init__(parent)

    def data(self, index, role=None):
        """score table data"""
        if role is None:
            role = Qt.DisplayRole
        if role == Qt.DisplayRole and index.column()==1:
            unformatted = str(self.record(index.row()).value(1).toString())
            dateVal = datetime.datetime.strptime(unformatted, '%Y-%m-%dT%H:%M:%S')
            return QVariant(dateVal.strftime('%c'))
        return QtSql.QSqlQueryModel.data(self, index, role)


class Games(QDialog):
    """a dialog for selecting a game"""
    def __init__(self, parent=None):
        super(Games, self).__init__(parent)
        self.selectedGame = None
        self.onlyPending = True
        self.setWindowTitle(m18nc('kmj', 'Games') + ' - kmj')
        self.resize(700, 400)
        self.model = GamesModel(self)

        self.view = QTableView(self)
        self.view.setModel(self.model)
        pol = QSizePolicy()
        pol.setHorizontalPolicy(QSizePolicy.Expanding)
        pol.setVerticalPolicy(QSizePolicy.Expanding)
        self.view.setSizePolicy(pol)
        self.view.verticalHeader().hide()
        self.selection = QtGui.QItemSelectionModel(self.model, self.view)
        self.view.setSelectionModel(self.selection)

        self.buttonBox = KDialogButtonBox(self)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel)
        self.buttonBox.addButton(i18n("&New"), QDialogButtonBox.AcceptRole,
            self, SLOT("accept()"))
        self.loadButton = self.buttonBox.addButton(i18n("&Load"), QDialogButtonBox.ActionRole,
            self.loadGame)
        self.deleteButton = self.buttonBox.addButton(i18n("&Delete"), QDialogButtonBox.ActionRole,
            self.delete)

        chkPending = QCheckBox(i18n("Show only pending games"), self)
        chkPending.setChecked(True)
        cmdLayout = QHBoxLayout()
        cmdLayout.addWidget(chkPending)
        cmdLayout.addWidget(self.buttonBox)

        layout = QVBoxLayout()
        layout.addWidget(self.view)
        layout.addLayout(cmdLayout)
        self.setLayout(layout)

        self.connect(self.selection,
            SIGNAL("selectionChanged ( QItemSelection, QItemSelection)"),
            self.selectionChanged)
        self.connect(self.buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(self.buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        self.connect(self.view, SIGNAL("doubleClicked(QModelIndex)"), self.loadGame)
        self.connect(chkPending, SIGNAL("stateChanged(int)"), self.pendingOrNot)

        self.setQuery()

    def selectionChanged(self):
        """update button states according to selection"""
        selectedRows = len(self.selection.selectedRows())
        self.loadButton.setEnabled(selectedRows == 1)
        self.deleteButton.setEnabled(selectedRows >= 1)

    def setQuery(self):
        """define the query depending on self.OnlyPending"""
        query = "select g.id, g.starttime, " \
            "p0.name||', '||p1.name||', '||p2.name||', '||p3.name " \
            "from game g, player p0," \
            "player p1, player p2, player p3 " \
            "where p0.id=g.p0 and p1.id=g.p1 and p2.id=g.p2 " \
            "and p3.id=g.p3 " \
            "%s" \
            "and exists(select 1 from score where game=g.id)" % \
            ("and g.endtime is null " if self.onlyPending else "")
        self.model.setQuery(query,  self.parent().dbhandle)
        self.model.setHeaderData(1, Qt.Horizontal,
            QVariant(QApplication.translate("Games","started",
            None, QApplication.UnicodeUTF8)))
        self.model.setHeaderData(2, Qt.Horizontal,
            QVariant(QApplication.translate("Games","players",
            None, QApplication.UnicodeUTF8)))
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.hideColumn(0)
        self.view.resizeColumnsToContents()
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.setAlternatingRowColors(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.selection.clear() # should emit selectionChanged but does not
        self.selectionChanged()

    def pendingOrNot(self, chosen):
        """do we want to see all games or only pending games?"""
        if self.onlyPending != chosen:
            self.onlyPending = chosen
            self.setQuery()

    def loadGame(self):
        """load a game"""
        selnum = len(self.selection.selectedRows())
        if  selnum != 1:
            # should never happen
            logException(Exception('loadGame: %d rows selected' % selnum))
        idx = self.view.currentIndex()
        self.selectedGame = self.model.record(idx.row()).value(0).toInt()[0]
        self.buttonBox.emit (SIGNAL("accepted()"))

    def delete(self):
        """delete a game"""
        selnum = len(self.selection.selectedRows())
        if  selnum == 0:
            # should never happen
            logException(Exception('delete: %d rows selected' % selnum))
        if KMessageBox.questionYesNo (self,
            i18n("Do you really want to delete %1 games?", selnum),
            QString(), kdeui.KStandardGuiItem.no(), kdeui.KStandardGuiItem.yes()) \
            == KMessageBox.Yes:
            # we call it with the yes and no buttons exchanged because no
            # should be the default. But the yes&no return value is not
            # exchanged!
            return
        query1 = QSqlQuery(self.parent().dbhandle)
        query2 = QSqlQuery(self.parent().dbhandle)
        query1.prepare("DELETE FROM score WHERE game = :game")
        query2.prepare("DELETE FROM game WHERE id = :game")
        for  index in self.view.selectionModel().selectedRows(0):
            game = index.data()
            for query in query1,  query2:
                query.bindValue(':game', game)
                query.exec_()
