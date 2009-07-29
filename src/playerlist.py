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

from PyKDE4.kdeui import KMessageBox
from PyKDE4.kdecore import i18n
from PyQt4.QtCore import Qt, QVariant, SIGNAL
from PyQt4.QtGui import QWidget, QApplication
from PyQt4.QtSql import QSqlTableModel

from playerlist_ui import Ui_PlayerWidget
from query import Query

from util import logMessage, StateSaver

class PlayerList(QWidget, Ui_PlayerWidget):
    """QtSQL Model view of the players"""
    def __init__(self, parent):
        super(PlayerList, self).__init__()
        self.parent = parent
        self.model = QSqlTableModel(self, Query.dbhandle)
        self.model.setTable("player")
        if not self.model.select():
            logMessage("PlayerList: select failed")
            sys.exit(1)
        self.model.setHeaderData(1, Qt.Horizontal,
            QVariant(QApplication.translate("Player", "Name",
            None, QApplication.UnicodeUTF8)))
        self.model.setEditStrategy(QSqlTableModel.OnManualSubmit)
        self.setupUi(self)
        self.playerView.setModel(self.model)
        self.playerView.hideColumn(0)
        self.playerView.horizontalHeader().setStretchLastSection(True)
        self.setupActions()
        self.setWindowTitle(i18n("Players") + ' - kmj')
        self.setObjectName('Players')
        self.state = StateSaver(self)

    def moveEvent(self, event):
        """save current size and position"""
        self.state.save()

    def resizeEvent(self, event):
        """save current size and position"""
        self.state.save()

    def slotOK(self):
        """commit all modifications"""
        if not self.model.submitAll():
            KMessageBox.sorry(None, i18n('Cannot save this. Possibly the name already exists. <br><br>' \
                    'Message from database:<br><br><message>%1</message>',
                    self.model.lastError().text()))
            return
        self.close()

    def slotCancel(self):
        """cancel all modifications"""
        self.model.revertAll()
        self.close()

    def slotInsert(self):
        """insert a record"""
        rec = self.model.record(-1)
        self.model.insertRecord(-1, rec)
        self.playerView.selectRow(self.model.rowCount()-1)

    def slotDelete(self):
        """delete selected records"""
        sel = self.playerView.selectionModel()
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

    def setupActions(self):
        """connect buttons"""
        self.connect(self.btnInsert, SIGNAL('clicked()'), self.slotInsert)
        self.connect(self.btnDelete, SIGNAL('clicked()'), self.slotDelete)
        self.connect(self.btnOK, SIGNAL('clicked()'), self.slotOK)
        self.connect(self.btnCancel, SIGNAL('clicked()'), self.slotCancel)

    def keyPressEvent(self, event):
        """use insert/delete keys for insert/delete records"""
        key = event.key()
        if key == Qt.Key_Insert:
            self.slotInsert()
            return
        if key == Qt.Key_Delete:
            self.slotDelete()
            event.ignore() # yet clears the field. Why?
            return
        QWidget.keyPressEvent(self, event)
