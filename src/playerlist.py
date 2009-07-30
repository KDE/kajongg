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

import sys

from PyKDE4.kdeui import KMessageBox, KIcon
from PyKDE4.kdecore import i18n
from PyQt4.QtCore import Qt, QVariant, SIGNAL
from PyQt4.QtGui import QWidget, QApplication, QAbstractItemView, QDialog,  \
        QHBoxLayout,  QVBoxLayout,  QSizePolicy, QTableView, QDialogButtonBox
from PyQt4.QtSql import QSqlTableModel

from query import Query

from util import logMessage, StateSaver, m18nc

# TODO: QDialog ohne Ui
# TODO: Icons

class PlayerList(QDialog):
    """QtSQL Model view of the players"""
    def __init__(self, parent):
        QDialog.__init__(self)
        self.parent = parent
        self.model = QSqlTableModel(self, Query.dbhandle)
        self.model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.model.setTable("player")
        self.model.setHeaderData(1, Qt.Horizontal, QVariant(m18nc("Player", "Name")))
        pol = QSizePolicy()
        pol.setHorizontalPolicy(QSizePolicy.Expanding)
        pol.setVerticalPolicy(QSizePolicy.Expanding)
        self.view = QTableView(self)
        self.view.setSizePolicy(pol)
        self.view.setModel(self.model)
        self.view.hideColumn(0)
        self.view.horizontalHeader().setStretchLastSection(True)
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.connect(self.buttonBox, SIGNAL("accepted()"), self.accept)
        self.connect(self.buttonBox, SIGNAL("rejected()"), self.reject)
        self.newButton = self.buttonBox.addButton(i18n("&New"), QDialogButtonBox.ActionRole)
        self.newButton.setIcon(KIcon("document-new"))
        self.connect(self.newButton, SIGNAL('clicked(bool)'), self.slotInsert)
        self.deleteButton = self.buttonBox.addButton(i18n("&Delete"), QDialogButtonBox.ActionRole)
        self.deleteButton.setIcon(KIcon("edit-delete"))
        self.connect(self.deleteButton, SIGNAL('clicked(bool)'), self.delete)

        cmdLayout = QHBoxLayout()
        cmdLayout.addWidget(self.buttonBox)
        layout = QVBoxLayout()
        layout.addWidget(self.view)
        layout.addLayout(cmdLayout)
        self.setLayout(layout)

        self.setWindowTitle(i18n("Players") + ' - kmj')
        self.setObjectName('Players')
        self.state = StateSaver(self)

    def showEvent(self, event):
        if not self.model.select():
            logMessage("PlayerList: select failed")
            sys.exit(1)
        self.view.selectRow(0)
        self.view.resizeColumnsToContents()
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.setAlternatingRowColors(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)

    def moveEvent(self, event):
        """save current size and position"""
        self.state.save()

    def resizeEvent(self, event):
        """save current size and position"""
        self.state.save()

    def accept(self):
        """commit all modifications"""
        if not self.model.submitAll():
            KMessageBox.sorry(None, i18n('Cannot save this. Possibly the name already exists. <br><br>' \
                    'Message from database:<br><br><message>%1</message>',
                    self.model.lastError().text()))
            return # TODO: richtig?
        QDialog.accept(self)

    def slotCancel(self):
        """cancel all modifications"""
        self.model.revertAll()
        self.close()

    def slotInsert(self):
        """insert a record"""
        self.model.insertRow(self.model.rowCount())
        self.view.selectRow(self.model.rowCount()-1)

    def delete(self):
        """delete selected records"""
        sel = self.view.selectionModel()
        maxDel = self.view.currentIndex().row() - 1
        for idx in sel.selectedIndexes():
            # sqlite3 does not enforce referential integrity.
            # we could add a trigger to sqlite3 but if it raises an exception
            # it will be thrown away silently.
            # if anybody knows how to propagate sqlite3 exceptions via QtSql
            # into python please tell me (wrohdewald)
            player = self.model.createIndex(idx.row(), 0).data().toInt()[0]
            # no query preparation, we don't expect lots of records
            if Query("select 1 from game where p0==%d or p1==%d or p2==%d or p3==%d" % \
                (player,  player,  player,  player)).data:
                KMessageBox.sorry(self,
                    i18n('This player cannot be deleted. There are games associated with %1.',
                        idx.data().toString()))
            else:
                self.model.removeRow(idx.row())
                maxDel = max(maxDel, idx.row())
        self.view.selectRow(maxDel+1)

    def keyPressEvent(self, event):
        """use insert/delete keys for insert/delete records"""
        key = event.key()
        if key == Qt.Key_Insert:
            self.slotInsert()
            return
        QDialog.keyPressEvent(self, event)
