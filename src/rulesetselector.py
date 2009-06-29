"""
    Copyright (C) 2008,2009 Wolfgang Rohdewald <wolfgang@rohdewald.de>

    partially based on C++ code from:
    Copyright (C) 2006 Mauricio Piacentini  <mauricio@tabuleiro.com>

    Libkmahjongg is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

from PyQt4.QtCore import SIGNAL, SLOT, Qt, QVariant
from PyKDE4.kdecore import i18n
from PyKDE4.kdeui import KDialogButtonBox, KMessageBox
from PyQt4.QtGui import QWidget, QListWidget, QHBoxLayout, QVBoxLayout, QLabel, \
    QPushButton, QSpacerItem, QSizePolicy, QInputDialog, QLineEdit, \
    QDialog, QDialogButtonBox, QTabWidget, QTableView, QTreeWidget, QTreeWidgetItem, \
    QTreeView
from PyQt4.QtCore import QAbstractItemModel, QModelIndex, QPoint
from PyQt4.QtSql import QSqlQueryModel
from scoring import Ruleset, Rule
from util import m18n, m18nc

class RuleTreeItem(object):
    def __init__(self, data):
        self._data = data
        self.parent = None
        self.children = []

    def appendChild(self, data):
        if not isinstance(data, RuleTreeItem):
            data = RuleTreeItem(data)
        data.parent = self
        self.children.append(data)
        return self.children[-1]

    def child(self, row):
        return self.children[row]

    def childCount(self):
        return len(self.children)

    def columnCount(self):
        return 4

    def data(self, column):
        data = self._data
        if isinstance(data, Rule):
            ruleset = self.parent.parent._data
            ruleList = self.parent._data
            if column == 0:
                return data.name
            else:
                if ruleList == ruleset.ruleLists.index(ruleset.intRules):
                    if column == 1:
                        return data.value
                else:
                    if column == 1:
                        return str(data.score.value())
                    elif column == 2:
                        return data.score.name()
                    elif column == 3:
                        return data.value
        elif isinstance(data, int) and column == 0:
            return Ruleset.rulelistNames()[data]
        elif isinstance(data, Ruleset) and column == 0:
            return data.name
        elif isinstance(data, Ruleset) and column == 3:
            return data.description
        elif isinstance(data, list) and len(data) > column:
            return data[column]
        return ''

    def row(self):
        if self.parent:
            return self.parent.children.index(self)
        return 0

    def ruleset(self):
        """returns the ruleset containing this item. If you need
        speed, you may not want to use this"""
        if isinstance(self._data, Ruleset):
            return self._data
        else:
            return self.parent.ruleset()

    def tooltip(self):
        return 'tooltip not yet implemented for class ' + self.__class__.__name__
        return '<b></b>'+self.ruleset().description

class RulesetItem(RuleTreeItem):
    def __init__(self, data):
        RuleTreeItem.__init__(self, data)

    def tooltip(self):
        return '<b></b>'+self._data.description+'<b></b>'

class RuleModel(QAbstractItemModel):
    """a model for our rule table"""
    def __init__(self,  rulesets, parent = None):
        super(RuleModel, self).__init__(parent)
        self.rulesets = rulesets
        rootData = []
        rootData.append(QVariant("Name"))
        rootData.append(QVariant("Score"))
        rootData.append(QVariant("Unit"))
        rootData.append(QVariant("Definition"))
        self.rootItem = RuleTreeItem(rootData)

    def columnCount(self, parent):
        if parent.isValid():
            return parent.internalPointer().columnCount()
        else:
            return self.rootItem.columnCount()

    def data(self, index, role):
        if not index.isValid():
            return QVariant()
        if role == Qt.DisplayRole:
            item = index.internalPointer()
            return QVariant(item.data(index.column()))
        elif role == Qt.TextAlignmentRole:
            if index.column() == 1:
                return QVariant(int(Qt.AlignRight|Qt.AlignVCenter))
            return QVariant(int(Qt.AlignLeft|Qt.AlignVCenter))
        else:
            return QVariant()

    def setData(self, index, value, role=Qt.EditRole):
        if index.isValid():
            column = index.column()
            item = index.internalPointer()
            data = item._data
            if isinstance(data, Ruleset) and column == 0:
                data.rename(str(value.toString()))
            elif isinstance(data, Ruleset) and column == 3:
                data.description =unicode(value.toString())
            elif isinstance(data, Rule):
                if column == 0:
                    data.name = str(value.toString())
                elif column ==3:
                    data.value = value.toString()
                else:
                    print 'rule column not implemented', column
            else:
                print 'unknown: column, oldRow:', column, type(oldRow), oldRow
                return False
            self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"), index, index)
            return True
        return False

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        column = index.column()
        item = index.internalPointer()
        data = item._data
        if isinstance(data, Ruleset) and column in (0, 3):
            mayEdit = True
        elif isinstance(data, Rule):
            mayEdit = column in [0, 3]
        else:
            mayEdit = False
        mayEdit = mayEdit and item.ruleset().isCustomized()
        result = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if mayEdit:
            result |= Qt.ItemIsEditable
        return result

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.rootItem.data(section)
        else:
            return QVariant()

    def index(self, row, column, parent):
        if row < 0 or column < 0 or row >= self.rowCount(parent) or column >= self.columnCount(parent):
            return QModelIndex()
        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()
        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        childItem = index.internalPointer()
        parentItem = childItem.parent
        if parentItem == self.rootItem:
            return QModelIndex()
        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0
        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()
        return parentItem.childCount()

    def addRuleset(self, ruleset):
        rulesetItem = self.rootItem.appendChild(RulesetItem(ruleset))
        for ridx, ruleList in enumerate(ruleset.ruleLists):
            listItem = rulesetItem.appendChild(ridx)
            for rule in ruleList:
                listItem.appendChild(rule)

    def setupModelData(self):
        for ruleset in self.rulesets:
            self.addRuleset(ruleset)

class RuleTreeView(QTreeView):
    def __init__(self, parent=None):
        QTreeView.__init__(self, parent)

    def selected(self):
        rows = self.selectionModel().selectedRows()
        if len(rows) != 1:
            return None
        return rows[0].internalPointer()._data

    def mouseMoveEvent(self, event):
        item = self.indexAt(event.pos()).internalPointer()
        self.setToolTip(item.tooltip() if item else '')

class RulesetSelector( QWidget):
    """presents all available rulesets with previews"""
    def __init__(self, parent,  pref):
        assert pref # quieten pylint
        super(RulesetSelector, self).__init__(parent)
        self.rulesetList = Ruleset.availableRulesets()
        self.setupUi()

    def showEvent(self, event):
        self.refresh()
        QWidget.showEvent(self, event)

    def refresh(self):
        """reload the ruleset lists"""
        self.rulesetList = Ruleset.availableRulesets()
        self.treeModel = RuleModel(self.rulesetList)
        self.treeView.setModel(self.treeModel)
        self.treeModel.setupModelData()
        self.treeView.expandAll() # because resizing only works for expanded fields
        for col in range(4):
            self.treeView.resizeColumnToContents(col)
        self.treeView.collapseAll()

    def setupUi(self):
        """layout the window"""
        hlayout = QHBoxLayout(self)
        v1layout = QVBoxLayout()
        v2layout = QVBoxLayout()
        hlayout.addLayout(v1layout)
        hlayout.addLayout(v2layout)
        self.treeView = RuleTreeView()
        self.treeView.setWordWrap(True)
        self.treeView.setMouseTracking(True)
        v1layout.addWidget(self.treeView)
        self.btnCopy = QPushButton()
        self.btnRemove = QPushButton()
        spacerItem = QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        v2layout.addWidget(self.btnCopy)
        v2layout.addWidget(self.btnRemove)
        self.connect(self.btnCopy, SIGNAL('clicked(bool)'), self.copy)
        self.connect(self.btnRemove, SIGNAL('clicked(bool)'), self.remove)
        v2layout.addItem(spacerItem)
        self.retranslateUi()

    def copy(self):
        """copy the ruleset"""
        data = self.treeView.selected()
        if isinstance(data, Ruleset):
            newRuleset = data.copy()
            if newRuleset:
                self.treeModel.addRuleset(newRuleset)
                self.treeModel.reset()
        else:
            KMessageBox.sorry(None, i18n('This is only implemented for entire rulesets'))

    def remove(self):
        """removes a ruleset"""
        data = self.treeView.selected()
        if isinstance(data, Ruleset):
            data.remove()
            self.refresh()
        else:
            KMessageBox.sorry(None, i18n('This is only implemented for entire rulesets'))

    def save(self):
        """saves all ruleset lists"""
        for ruleset in self.rulesetList:
            ruleset.save()

    def retranslateUi(self):
        """translate to current language"""
        self.btnCopy.setText(m18n("&Copy"))
        self.btnRemove.setText(m18n("R&emove"))
