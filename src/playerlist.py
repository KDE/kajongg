# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2014 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from kde import KIcon
from dialogs import Sorry
from PyQt4.QtCore import Qt
from PyQt4.QtGui import QDialog, QHBoxLayout, QVBoxLayout, QDialogButtonBox, \
        QTableWidget, QTableWidgetItem

from query import Query

from log import m18n, m18nc
from statesaver import StateSaver

class PlayerList(QDialog):
    """QtSQL Model view of the players"""
    def __init__(self, parent):
        QDialog.__init__(self)
        self.parent = parent
        self._data = {}
        self.table = QTableWidget(self)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemChanged.connect(self.itemChanged)
        self.updateTable()
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setStandardButtons(QDialogButtonBox.Close) # Close has the Rejected role
        self.buttonBox.rejected.connect(self.accept)
        self.newButton = self.buttonBox.addButton(m18nc('define a new player', "&New"), QDialogButtonBox.ActionRole)
        self.newButton.setIcon(KIcon("document-new"))
        self.newButton.clicked.connect(self.slotInsert)
        self.deleteButton = self.buttonBox.addButton(m18n("&Delete"), QDialogButtonBox.ActionRole)
        self.deleteButton.setIcon(KIcon("edit-delete"))
        self.deleteButton.clicked.connect(self.delete)

        cmdLayout = QHBoxLayout()
        cmdLayout.addWidget(self.buttonBox)
        layout = QVBoxLayout()
        layout.addWidget(self.table)
        layout.addLayout(cmdLayout)
        self.setLayout(layout)

        self.setWindowTitle(m18n("Players") + ' - Kajongg')
        self.setObjectName('Players')

    def showEvent(self, dummyEvent):
        """adapt view to content"""
        StateSaver(self, self.table)

    @staticmethod
    def sortKey(text):
        """display order in Table"""
        if len(text) == 0:
            return 'zzzzzzzzzzzz'
        else:
            return text.upper()

    def updateTable(self, data=None, currentName=None):
        """fills self.table from DB"""
        self.table.itemChanged.disconnect(self.itemChanged)
        table = self.table
        table.clear()
        if data is None:
            data = dict(Query('select name, id from player where name not like "ROBOT %"').records)
        self._data = data
        table.setColumnCount(1)
        table.setRowCount(len(self._data))
        table.setHorizontalHeaderLabels([m18n("Player")])
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        selectedItem = None
        for row, name in enumerate(sorted(self._data, key=self.sortKey)):
            item = QTableWidgetItem(name)
            if selectedItem is None:
                selectedItem = item
            table.setItem(row, 0, item)
            if name == currentName:
                selectedItem = item
        if selectedItem:
            table.setCurrentItem(selectedItem)
            table.scrollToItem(selectedItem)
        self.table.itemChanged.connect(self.itemChanged)

    def itemChanged(self, item):
        """this must be new because editing is disabled for others"""
        currentName = unicode(item.text())
        if currentName in self._data:
            Sorry(m18n('Player %1 already exists', currentName))
            self.setFocus()
            del self._data[unicode(self.table.item(self.table.currentRow(), 0).text())]
            self.updateTable(currentName=currentName)
            return
        query = Query('insert into player(name) values(?)', (currentName, ))
        if query.failure:
            Sorry(m18n('Error while adding player %1: %2', currentName, query.failure.message))
        self.updateTable(currentName=currentName)

    def slotInsert(self):
        """insert a record"""
        self._data[''] = 0
        self.updateTable(data=self._data, currentName='')
        for row in range(len(self._data)):
            item = self.table.item(row, 0)
            if len(item.text()) == 0:
                self.table.editItem(item)

    def delete(self):
        """delete selected entries"""
        items = self.table.selectedItems()
        currentRow = self.table.currentRow()
        if len(items):
            name = unicode(items[0].text())
            playerId = self._data[name]
            query = Query("select 1 from game where p0=? or p1=? or p2=? or p3=?",
                    (playerId, ) * 4)
            if len(query.records):
                Sorry(m18n('This player cannot be deleted. There are games associated with %1.', name))
                return
            Query("delete from player where name=?", (name,))
            self.updateTable()
        self.table.setCurrentCell(min(currentRow, len(self._data)-1), 0)

    def keyPressEvent(self, event):
        """use insert/delete keys for insert/delete"""
        key = event.key()
        if key == Qt.Key_Insert:
            self.slotInsert()
        elif key == Qt.Key_Delete:
            self.delete()
        else:
            QDialog.keyPressEvent(self, event)
