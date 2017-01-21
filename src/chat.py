# -*- coding: utf-8 -*-

"""
Copyright (C) 2009-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

Kajongg is free software you can redistribute it and/or modify
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

from qt import Qt, QAbstractTableModel, QModelIndex, QSize
from qt import QWidget, QLineEdit, QVBoxLayout, QColor, QAbstractItemView

from log import i18n, logDebug
from guiutil import MJTableView, decorateWindow
from statesaver import StateSaver
from message import ChatMessage
from common import Debug, Internal
from modeltest import ModelTest


class ChatModel(QAbstractTableModel):

    """a model for the chat view"""

    def __init__(self, parent=None):
        super(ChatModel, self).__init__(parent)
        self.chatLines = []

    def headerData(self, section, orientation, role=Qt.DisplayRole):  # pylint: disable=no-self-use
        """show header"""
        if role == Qt.TextAlignmentRole:
            if orientation == Qt.Horizontal:
                if section == 1:
                    return int(Qt.AlignRight)
                else:
                    return int(Qt.AlignLeft)
        if orientation != Qt.Horizontal:
            return int(section + 1)
        if role != Qt.DisplayRole:
            return
        result = ''
        if section < self.columnCount():
            result = [i18n('Time'), i18n('Player'), i18n('Message')][section]
        return result

    def rowCount(self, parent=None):
        """how many lines are in the model?"""
        if parent and parent.isValid():
            # we have only top level items
            return 0
        return len(self.chatLines)

    def columnCount(self, dummyParent=None):  # pylint: disable=no-self-use
        """for now we only have time, who, message"""
        return 3

    def data(self, index, role=Qt.DisplayRole):
        """score table"""
        result = None
        if role == Qt.TextAlignmentRole:
            if index.column() == 1:
                return int(Qt.AlignRight)
            else:
                return int(Qt.AlignLeft)
        if index.isValid() and (0 <= index.row() < len(self.chatLines)):
            chatLine = self.chatLines[index.row()]
            if role == Qt.DisplayRole and index.column() == 0:
                local = chatLine.localtimestamp()
                result = '%02d:%02d:%02d' % (
                    local.hour,
                    local.minute,
                    local.second)
            elif role == Qt.DisplayRole and index.column() == 1:
                result = chatLine.fromUser
            elif role == Qt.DisplayRole and index.column() == 2:
                result = i18n(chatLine.message)
            elif role == Qt.ForegroundRole and index.column() == 2:
                palette = Internal.app.palette() # pylint: disable=no-member
                color = 'blue' if chatLine.isStatusMessage else palette.windowText(
                )
                result = QColor(color)
        return result

    def appendLines(self, lines):
        """insert a chatline"""
        if not isinstance(lines, list):
            lines = [lines]
        self.beginInsertRows(
            QModelIndex(),
            self.rowCount(),
            self.rowCount() + len(lines) - 1)
        self.chatLines.extend(lines)
        self.endInsertRows()


class ChatView(MJTableView):

    """define a minimum size"""

    def __init__(self):
        MJTableView.__init__(self)

    def sizeHint(self):  # pylint: disable=no-self-use
        """sizeHint"""
        return QSize(400, 100)

    def minimumSizeHint(self):
        """minimumSizeHint"""
        return self.sizeHint()


class ChatWindow(QWidget):

    """a widget for showing chat messages"""

    def __init__(self, scene=None, table=None):
        super(ChatWindow, self).__init__(None)
        self.scene = scene
        self.table = table or scene.game.client.table
        self.table.chatWindow = self
        self.setObjectName('chatWindow')
        title = i18n(
            'Chat on table %1 at %2',
            self.table.tableid,
            self.table.client.connection.url)
        decorateWindow(self, title)
        self.messageView = ChatView()
        self.messageView.setModel(ChatModel())
        self.messageView.setFocusPolicy(Qt.NoFocus)
        self.messageView.setShowGrid(False)
        self.messageView.setWordWrap(False)
        self.messageView.setSelectionMode(QAbstractItemView.NoSelection)
        if Debug.modelTest:
            self.debugModelTest = ModelTest(
                self.messageView.model(),
                self.messageView)
        self.edit = QLineEdit()
        layout = QVBoxLayout()
        layout.addWidget(self.messageView)
        layout.addWidget(self.edit)
        self.setLayout(layout)
        self.edit.returnPressed.connect(self.sendLine)
        self.edit.setFocus()
        self.show()
        StateSaver(self)

    def show(self):
        """not only show but also restore and raise"""
        self.activateWindow()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        QWidget.show(self)

    def isVisible(self):
        """not only visible but also not minimized"""
        return QWidget.isVisible(self) and not self.windowState() & Qt.WindowMinimized

    def kill(self):
        """hide and null on table"""
        if Debug.chat:
            logDebug('chat.kill for %s on table %s' % (self, self.table))
        self.hide()
        self.table.chatWindow = None

    def sendLine(self, line=None, isStatusMessage=False):
        """send line to others. Either the edited line or parameter line."""
        if line is None:
            line = self.edit.text()
            self.edit.clear()
        if line:
            if Debug.chat:
                logDebug('sending line %s to others' % line)
            msg = ChatMessage(
                self.table.tableid,
                self.table.client.name,
                line,
                isStatusMessage)
            self.table.client.sendChat(msg).addErrback(self.chatError)

    def chatError(self, result):
        """tableList may already have gone away"""
        if self.table.client.tableList:
            self.table.client.tableList.tableError(result)

    def leave(self):
        """leaving the chat"""
        self.hide()

    def receiveLine(self, chatLine):
        """show a new line in protocol"""
        self.show()
        self.messageView.model().appendLines(chatLine)
        for row in range(self.messageView.model().rowCount()):
            self.messageView.setRowHeight(
                row,
                self.messageView.fontMetrics().height())
        self.messageView.resizeColumnsToContents()
        self.messageView.scrollToBottom()
