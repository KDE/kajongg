# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

from typing import Optional, TYPE_CHECKING, Dict, Any
import sqlite3

from mi18n import i18n, i18nc
from kde import KIcon
from dialogs import Sorry, QuestionYesNo
from qt import Qt
from qt import QDialog, QHBoxLayout, QVBoxLayout, QDialogButtonBox, \
    QTableWidget, QTableWidgetItem, QWidget

from common import Internal
from query import Query
from guiutil import decorateWindow
from statesaver import StateSaver

if TYPE_CHECKING:
    from qt import QEvent, QKeyEvent


class PlayerList(QDialog):

    """QtSQL Model view of the players"""

    def __init__(self, parent:Optional['QWidget']=None):
        super().__init__(parent)
        self._data:Dict[str, int] = {}
        self.table = QTableWidget(self)
        if header := self.table.horizontalHeader():
            header.setStretchLastSection(True)
        if header := self.table.verticalHeader():
            header.setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemChanged.connect(self.itemChanged)
        self.updateTable()
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setStandardButtons(
            QDialogButtonBox.StandardButton.Close)  # Close has the Rejected role
        self.buttonBox.rejected.connect(self.accept)
        self.newButton = self.buttonBox.addButton(
            i18nc('define a new player',
                  "&New"),
            QDialogButtonBox.ButtonRole.ActionRole)
        if button := self.newButton:
            button.setIcon(KIcon("document-new"))
            button.clicked.connect(self.slotInsert)
        self.deleteButton = self.buttonBox.addButton(
            i18n("&Delete"), QDialogButtonBox.ButtonRole.ActionRole)
        assert self.deleteButton
        self.deleteButton.setIcon(KIcon("edit-delete"))
        self.deleteButton.clicked.connect(self.delete)

        cmdLayout = QHBoxLayout()
        cmdLayout.addWidget(self.buttonBox)
        layout = QVBoxLayout()
        layout.addWidget(self.table)
        layout.addLayout(cmdLayout)
        self.setLayout(layout)
        decorateWindow(self, i18n("Players"))
        self.setObjectName('Players')

    def showEvent(self, unusedEvent:Optional['QEvent']) ->None:
        """adapt view to content"""
        StateSaver(self, self.table)

    @staticmethod
    def sortKey(text:str) ->str:
        """display order in Table"""
        return text.upper() if text else 'zzzzzzzzzzzz'

    def updateTable(self, data:Optional[Dict[str, int]]=None, currentName:Optional[str]=None) ->None:
        """fills self.table from DB"""
        self.table.itemChanged.disconnect(self.itemChanged)
        table = self.table
        table.clear()
        if data is None:
            data = dict(
                Query('select name, id from player where name not like "ROBOT %"').records)
        self._data = data
        table.setColumnCount(1)
        table.setRowCount(len(self._data))
        table.setHorizontalHeaderLabels([i18n("Player")])
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
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

    def itemChanged(self, item:QTableWidgetItem) ->None:
        """this must be new because editing is disabled for others"""
        currentName = item.text()
        if currentName in self._data:
            Sorry(i18n('Player %1 already exists', currentName))
            self.setFocus()
            if _ := self.table.item(self.table.currentRow(), 0):
                del self._data[_.text()]
            self.updateTable(currentName=currentName)
            return
        try:
            Query('insert into player(name) values(?)', (currentName, ))
        except sqlite3.Error as exc:
            Sorry(
                i18n(
                    'Error while adding player %1: %2',
                    currentName,
                    str(exc)))
        self.updateTable(currentName=currentName)

    def slotInsert(self) ->None:
        """insert a record"""
        self._data[''] = 0
        self.updateTable(data=self._data, currentName='')
        for row in range(len(self._data)):
            if item := self.table.item(row, 0):
                if not item.text():
                    self.table.editItem(item)

    @staticmethod
    def __deletePlayer(playerId:int) ->None:
        """delete this player and all associated games"""
        with Internal.db: # transaction
            Query("delete from score where player=?", (playerId, ))
            Query("delete from game where p0=? or p1=? or p2=? or p3=?", (playerId, ) * 4)
            Query("delete from player where id=?", (playerId,))

    def delete(self) ->None:
        """delete selected entry"""
        def answered(result:Any) ->None:
            """coming from QuestionYesNo"""
            if result is True:
                self.__deletePlayer(playerId)
            cleanup()
        def cleanup() ->None:
            """update table view"""
            self.updateTable()
            self.table.setCurrentCell(min(currentRow, len(self._data) - 1), 0)
            # the main window gets focus after QuestionYesNo
            self.activateWindow()

        items = self.table.selectedItems()
        if not items:
            return
        currentRow = self.table.currentRow()
        assert len(items) == 1
        name = items[0].text()
        playerId = self._data[name]

        fullCount = int(Query(
            "select count(1) from game where p0=? or p1=? or p2=? or p3=?",
            (playerId, ) * 4).records[0][0])
        if not fullCount:
            self.__deletePlayer(playerId)
            cleanup()
        else:
            finishedCount = int(Query(
                "select count(1) from game where (p0=? or p1=? or p2=? or p3=?) and endtime is not null",
                (playerId, ) * 4).records[0][0])
            QuestionYesNo(i18n(
                'There are %1 finished and %2 unfinished games for %3, delete %3 anyway?'
                '  This will also delete all games played by %3!',
                finishedCount, fullCount - finishedCount, name)).addBoth(answered)

    def keyPressEvent(self, event:Optional['QKeyEvent']) ->None:
        """use insert/delete keys for insert/delete"""
        if event:
            key = event.key()
            if key == Qt.Key.Key_Insert:
                self.slotInsert()
            elif key == Qt.Key.Key_Delete:
                self.delete()
            else:
                super().keyPressEvent(event)
