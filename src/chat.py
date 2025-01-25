# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

from typing import List, Optional, Union, TYPE_CHECKING, cast

from qt import Qt, QAbstractTableModel, QModelIndex, QPersistentModelIndex, QSize
from qt import QWidget, QLineEdit, QVBoxLayout, QColor, QAbstractItemView

from log import i18n, logDebug
from guiutil import MJTableView, decorateWindow
from statesaver import StateSaver
from message import ChatMessage
from common import Debug, Internal
from modeltest import ModelTest

if TYPE_CHECKING:
    from twisted.python.failure import Failure
    from qt import QObject
    from client import ClientTable
    from scene import GameScene
    from humanclient import HumanClient

class ChatModel(QAbstractTableModel):

    """a model for the chat view"""

    def __init__(self, parent:Optional['QObject']=None) ->None:
        super().__init__(parent)
        self.chatLines:List[ChatMessage] = []

    def headerData(self, section:int, orientation:Qt.Orientation,
        role:int=Qt.ItemDataRole.DisplayRole) ->Union[int, str, None]:
        """show header"""
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if orientation == Qt.Orientation.Horizontal:
                if section == 1:
                    return int(Qt.AlignmentFlag.AlignRight)
                return int(Qt.AlignmentFlag.AlignLeft)
        if orientation != Qt.Orientation.Horizontal:
            return int(section + 1)
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        result = ''
        if section < self.columnCount():
            result = [i18n('Time'), i18n('Player'), i18n('Message')][section]
        return result

    def rowCount(self, parent:Union[QModelIndex,QPersistentModelIndex]=QModelIndex()) ->int:
        """how many lines are in the model?"""
        if parent.isValid():
            # similar in tables.py
            # we have only top level items
            return 0
        return len(self.chatLines)

    def columnCount(self, unusedParent:Union[QModelIndex,QPersistentModelIndex]=QModelIndex()) ->int:
        """for now we only have time, who, message"""
        return 3

    def data(self, index:Union[QModelIndex,QPersistentModelIndex],
        role:int=Qt.ItemDataRole.DisplayRole) ->Union[int, str, QColor, None]:
        """score table"""
        result:Union[int, str, QColor, None] = None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if index.column() == 1:
                return int(Qt.AlignmentFlag.AlignRight)
            return int(Qt.AlignmentFlag.AlignLeft)
        if index.isValid() and (0 <= index.row() < len(self.chatLines)):
            chatLine = self.chatLines[index.row()]
            if role == Qt.ItemDataRole.DisplayRole and index.column() == 0:
                local = chatLine.localtimestamp()
                result = f'{int(local.hour):02}:{int(local.minute):02}:{int(local.second):02}'
            elif role == Qt.ItemDataRole.DisplayRole and index.column() == 1:
                result = chatLine.fromUser
            elif role == Qt.ItemDataRole.DisplayRole and index.column() == 2:
                result = i18n(chatLine.message)
            elif role == Qt.ItemDataRole.ForegroundRole and index.column() == 2:
                palette = Internal.app.palette()
                color = 'blue' if chatLine.isStatusMessage else palette.windowText(
                )
                result = QColor(color)
        return result

    def appendLine(self, line:ChatMessage) ->None:
        """insert a chatline"""
        old_rowCount = self.rowCount()
        self.beginInsertRows(QModelIndex(), old_rowCount, old_rowCount)
        self.chatLines.append(line)
        self.endInsertRows()


class ChatView(MJTableView):

    """define a minimum size"""

    def __init__(self) ->None:
        MJTableView.__init__(self)

    def sizeHint(self) ->QSize:
        """sizeHint"""
        return QSize(400, 100)

    def minimumSizeHint(self) ->QSize:
        """minimumSizeHint"""
        return self.sizeHint()


class ChatWindow(QWidget):

    """a widget for showing chat messages"""

    def __init__(self, table:'ClientTable') ->None:
        super().__init__(None)
        assert table.client.connection
        self.table = table
        table.chatWindow = self
        self.setObjectName('chatWindow')
        title = i18n(
            'Chat on table %1 at %2',
            table.tableid,
            table.client.connection.url)
        decorateWindow(self, title)
        self.messageView = ChatView()
        self.messageView.setModel(ChatModel())
        self.messageView.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.messageView.setShowGrid(False)
        self.messageView.setWordWrap(False)
        self.messageView.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        if Debug.modelTest:
            if model := self.messageView.model():
                self.debugModelTest = ModelTest(model, self.messageView)
        self.edit = QLineEdit()
        layout = QVBoxLayout()
        layout.addWidget(self.messageView)
        layout.addWidget(self.edit)
        self.setLayout(layout)
        self.edit.returnPressed.connect(self.sendLine)
        self.edit.setFocus()
        self.show()
        StateSaver(self)

    def show(self) ->None:
        """not only show but also restore and raise"""
        self.activateWindow()
        self.setWindowState(cast(Qt.WindowState, self.windowState() & ~Qt.WindowState.WindowMinimized))
        self.raise_()
        QWidget.show(self)

    def isVisible(self) ->bool:
        """not only visible but also not minimized"""
        return QWidget.isVisible(self) and not self.windowState() & Qt.WindowState.WindowMinimized

    def kill(self) ->None:
        """hide and null on table"""
        if Debug.chat:
            logDebug(f'chat.kill for {self} on table {self.table}')
        self.hide()
        assert self.table
        self.table.chatWindow = None

    def sendLine(self, line:Optional[str]=None, isStatusMessage:bool=False) ->None:
        """send line to others. Either the edited line or parameter line."""
        if line is None:
            line = self.edit.text()
            self.edit.clear()
        if line:
            assert self.table
            assert self.table.client
            if Debug.chat:
                logDebug(f'sending line {line} to others')
            msg = ChatMessage(
                self.table.tableid,
                self.table.client.name,
                line,
                isStatusMessage)
            cast('HumanClient', self.table.client).sendChat(msg).addErrback(self.chatError)

    def chatError(self, result:'Failure') ->None:
        """tableList may already have gone away"""
        assert self.table
        assert self.table.client
        cast('HumanClient', self.table.client).tableError(result)

    def leave(self) ->None:
        """leaving the chat"""
        self.hide()

    def receiveLine(self, chatLine:ChatMessage) ->None:
        """show a new line in protocol"""
        self.show()
        if model := self.messageView.model():
            cast(ChatModel, model).appendLine(chatLine)
            for row in range(model.rowCount()):
                self.messageView.setRowHeight(
                    row,
                    self.messageView.fontMetrics().height())
        self.messageView.resizeColumnsToContents()
        self.messageView.scrollToBottom()
