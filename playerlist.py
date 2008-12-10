# -*- coding: utf-8 -*-

"""
Copyright (C) 2008 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from PyQt4 import QtCore, QtGui, QtSql

from playerlist_ui import Ui_PlayerWidget

class PlayerList(QtGui.QWidget, Ui_PlayerWidget):
    """QtSQL Model view of the players"""
    def __init__(self, parent):
        super(PlayerList, self).__init__()
        self.model = QtSql.QSqlTableModel(self, parent.dbhandle)
        self.model.setTable("player")
        if not self.model.select():
            print "select failed"
            sys.exit(1)
        self.model.setHeaderData(1, QtCore.Qt.Horizontal,
            QtCore.QVariant(QtGui.QApplication.translate("Player", "Name",
            None, QtGui.QApplication.UnicodeUTF8)))
        self.model.setEditStrategy(QtSql.QSqlTableModel.OnManualSubmit)
        self.setupUi(self)
        self.playerView.setModel(self.model)
        self.playerView.hideColumn(0)
        self.playerView.horizontalHeader().setStretchLastSection(True)
        self.setupActions()

    def slotOK(self):
        """commit all modifications"""
        self.model.submitAll()
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
            self.model.removeRow(idx.row())
    
    def setupActions(self):
        """connect buttons"""
        self.connect(self.btnInsert, QtCore.SIGNAL('clicked()'), self.slotInsert)
        self.connect(self.btnDelete, QtCore.SIGNAL('clicked()'), self.slotDelete)
        self.connect(self.btnOK, QtCore.SIGNAL('clicked()'), self.slotOK)
        self.connect(self.btnCancel, QtCore.SIGNAL('clicked()'), self.slotCancel)

    def keyPressEvent(self, event):
        """use insert/delete keys for insert/delete records"""
        key = event.key()
        if key == QtCore.Qt.Key_Insert:
            self.slotInsert()
            return
        if key == QtCore.Qt.Key_Delete:
            self.slotDelete()
            event.ignore() # yet clears the field. Why?
            return
        QtGui.QWidget.keyPressEvent(self, event)    
