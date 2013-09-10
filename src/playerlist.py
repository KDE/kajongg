# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

kajongg is free software you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
"""

import sys

from kde import Sorry, KIcon
from PyQt4.QtCore import Qt, QVariant
from PyQt4.QtGui import QDialog, \
        QHBoxLayout, QVBoxLayout, QDialogButtonBox
from PyQt4.QtSql import QSqlTableModel

from query import Query, DBHandle

from util import logError, m18n, m18nc
from guiutil import MJTableView
from statesaver import StateSaver

class PlayerList(QDialog):
    """QtSQL Model view of the players"""
    def __init__(self, parent):
        QDialog.__init__(self)
        self.parent = parent
        self.model = QSqlTableModel(self, DBHandle.default)
        self.model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.model.setTable("player")
        self.model.setSort(1, 0)
        self.model.setHeaderData(1, Qt.Horizontal, QVariant(m18nc("Player", "Name")))
        self.model.setFilter('name not like "ROBOT %" and name not like "Robot %"')
        self.view = MJTableView(self)
        self.view.verticalHeader().show()
        self.view.setModel(self.model)
        self.view.hideColumn(0)
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.newButton = self.buttonBox.addButton(m18nc('define a new player', "&New"), QDialogButtonBox.ActionRole)
        self.newButton.setIcon(KIcon("document-new"))
        self.newButton.clicked.connect(self.slotInsert)
        self.deleteButton = self.buttonBox.addButton(m18n("&Delete"), QDialogButtonBox.ActionRole)
        self.deleteButton.setIcon(KIcon("edit-delete"))
        self.deleteButton.clicked.connect(self.delete)

        cmdLayout = QHBoxLayout()
        cmdLayout.addWidget(self.buttonBox)
        layout = QVBoxLayout()
        layout.addWidget(self.view)
        layout.addLayout(cmdLayout)
        self.setLayout(layout)

        self.setWindowTitle(m18n("Players") + ' - Kajongg')
        self.setObjectName('Players')

    def showEvent(self, dummyEvent):
        """adapt view to content"""
        if not self.model.select():
            logError("PlayerList: select failed")
            sys.exit(1)
        self.view.initView()
        StateSaver(self, self.view.horizontalHeader())
        if not self.view.isColumnHidden(2):
            # we loaded a kajonggrc written by an older kajongg version where this table
            # still had more columns. This should happen only once.
            self.view.hideColumn(2)
            self.view.hideColumn(3)

    def accept(self):
        """commit all modifications"""
        self.view.selectRow(0) # if ALT-O is entered while editing a new row, this is one way
        # to end editing and to pass the new value to the model
        if not self.model.submitAll():
            Sorry(m18n('Cannot save this. Possibly the name already exists. <br><br>' \
                    'Message from database:<br><br><message>%1</message>',
                    self.model.lastError().text()))
            return
        QDialog.accept(self)

    def slotInsert(self):
        """insert a record"""
        self.model.insertRow(self.model.rowCount())
        self.view.selectRow(self.model.rowCount()-1)

    def delete(self):
        """delete selected entries"""
        sel = self.view.selectionModel()
        maxDel = self.view.currentIndex().row() - 1
        for idx in sel.selectedIndexes():
            if idx.column() != 1:
                continue
            # sqlite3 does not enforce referential integrity.
            # we could add a trigger to sqlite3 but if it raises an exception
            # it will be thrown away silently.
            # if anybody knows how to propagate sqlite3 exceptions via QtSql
            # into python please tell me (wrohdewald)
            player = self.model.createIndex(idx.row(), 0).data().toInt()[0]
            # no query preparation, we don't expect lots of data
            if Query("select 1 from game where p0==%d or p1==%d or p2==%d or p3==%d" % \
                (player, player, player, player)).records:
                Sorry(m18n('This player cannot be deleted. There are games associated with %1.',
                        idx.data().toString()))
            else:
                self.model.removeRow(idx.row())
                maxDel = max(maxDel, idx.row())
        self.view.selectRow(maxDel+1)

    def keyPressEvent(self, event):
        """use insert/delete keys for insert/delete"""
        key = event.key()
        if key == Qt.Key_Insert:
            self.slotInsert()
            return
        QDialog.keyPressEvent(self, event)
