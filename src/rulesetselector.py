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
from PyKDE4.kdeui import KDialogButtonBox
from PyQt4.QtGui import QWidget, QListWidget, QHBoxLayout, QVBoxLayout, QLabel, \
    QPushButton, QSpacerItem, QSizePolicy, QInputDialog, QLineEdit, \
    QDialog, QDialogButtonBox, QTabWidget, QTableView, QTreeWidget, QTreeWidgetItem, \
    QTreeView
from PyQt4.QtCore import QAbstractItemModel, QModelIndex
from PyQt4.QtSql import QSqlQueryModel
from scoring import Ruleset, Rule
from util import m18n, m18nc

class RuleTreeItem(object):
    def __init__(self, data, parent):
        self._data = data
        self.parent = parent
        self.children = []

    def appendChild(self, data):
        self.children.append(RuleTreeItem(data, self))
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
            if column == 0:
                return data.name
            elif column == 1:
                return str(data.score.value())
            elif column == 2:
                return data.score.name()
            elif column == 3:
                return data.value
        elif isinstance(data, int) and column == 0:
            return Ruleset.rulelistNames()[data]
        elif isinstance(data, Ruleset) and column == 0:
            return data.name
        elif isinstance(data, list) and len(data) > column:
            return data[column]
        return ''

    def row(self):
        if self.parent:
            return self.parent.children.index(self)
        return 0

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
        self.rootItem = RuleTreeItem(rootData, None)

    def columnCount(self, parent):
        if parent.isValid():
            return parent.internalPointer().columnCount()
        else:
            return self.rootItem.columnCount()

    def data(self, index, role):
        if not index.isValid():
            return QVariant()
        if role != Qt.DisplayRole:
            return QVariant()
        item = index.internalPointer()
        return QVariant(item.data(index.column()))

    def setData(self, index, value, role=Qt.EditRole):
        if index.isValid():
            column = index.column()
            item = index.internalPointer()
            data = item._data
            if isinstance(data, Ruleset) and column == 0:
                data.rename(str(value.toString()))
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
        if isinstance(data, Ruleset) and column == 0 and data.isCustomized():
            mayEdit = True
        elif isinstance(data, Rule) and item.parent.parent._data.isCustomized():
            mayEdit = column in [0, 3]
        else:
            mayEdit = False
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

    def setupModelData(self):
        for ruleset in self.rulesets:
            rulesetItem = self.rootItem.appendChild(ruleset)
            for ridx, ruleList in enumerate(ruleset.ruleLists):
                if len(ruleList):
                    listItem = rulesetItem.appendChild(ridx)
                    for rule in ruleList:
                        listItem.appendChild(rule)

class RuleTab(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        self.model = RuleModel(self, self.rulesetList)
        self.view = QTableView(self)
        vpol = QSizePolicy()
        vpol.setHorizontalPolicy(QSizePolicy.Expanding)
        vpol.setVerticalPolicy(QSizePolicy.Expanding)
        self.setSizePolicy(vpol)
        self.view.setSizePolicy(vpol)
        self.view.setModel(self.model)

class ModifyRuleset(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.ruleset = parent.ruleset
        self.setWindowTitle(m18n('Modify ruleset') + ' - kmj')
        vbox = QVBoxLayout(self)
        tabs = QTabWidget(self)
        hbox = QHBoxLayout()
        buttonBox = KDialogButtonBox(self)
        vbox.addWidget(tabs)
        vbox.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Fixed))
        vbox.addLayout(hbox)
        vbox.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Fixed))
        btnInsert = QPushButton(i18n('&Insert'))
        btnDelete = QPushButton(i18n('&Delete'))
        hbox.addWidget(btnInsert)
        hbox.addWidget(btnDelete)
        hbox.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        hbox.addWidget(buttonBox)
        buttonBox.setStandardButtons(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
        self.connect(buttonBox, SIGNAL("accepted()"), SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), SLOT("reject()"))
        self.generalTab = tabs.addTab(RuleTab(), m18nc("ModifyRuleset","General"))
        self.meldTab = tabs.addTab(RuleTab(), m18n('Melds'))
        self.handTab = tabs.addTab(RuleTab(), m18n('Hand'))
        self.winnerTab = tabs.addTab(RuleTab(), m18n('Winner'))
        self.manualTab= tabs.addTab(RuleTab(), m18n('Manual'))
        tabs.setCurrentIndex(1)

class RulesetSelector( QWidget):
    """presents all available rulesets with previews"""
    def __init__(self, parent,  pref):
        assert pref # quieten pylint
        super(RulesetSelector, self).__init__(parent)
        self.ruleset = None
        self.rulesetList = Ruleset.availableRulesets()
        self.setupUi()
        self.connect(self.rulesetNameList, SIGNAL(
                'currentRowChanged ( int)'), self.rulesetRowChanged)

    def showEvent(self, event):
        self.refresh()
        QWidget.showEvent(self, event)

    def refresh(self):
        """reload the ruleset lists"""
        self.rulesetList = Ruleset.availableRulesets()
        idx = self.rulesetNameList.currentRow()
        self.rulesetNameList.clear()
        for aset in  self.rulesetList:
            self.rulesetNameList.addItem(m18n(aset.name))
        self.rulesetNameList.setCurrentRow(min(idx, self.rulesetNameList.count()-1))
        self.rulesetRowChanged()
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
        self.rulesetNameList = QListWidget()
        self.rulesetDescription = QLabel()
        self.rulesetDescription.setWordWrap(True)
        v1layout.addWidget(self.rulesetNameList)
        v1layout.addWidget(self.rulesetDescription)
        self.btnCopy = QPushButton()
        self.btnModify = QPushButton()
        self.btnRename = QPushButton()
        self.btnRemove = QPushButton()
        spacerItem = QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        v2layout.addWidget(self.btnCopy)
        v2layout.addWidget(self.btnModify)
        v2layout.addWidget(self.btnRename)
        v2layout.addWidget(self.btnRemove)
        self.connect(self.btnCopy, SIGNAL('clicked(bool)'), self.copy)
        self.connect(self.btnModify, SIGNAL('clicked(bool)'), self.modify)
        self.connect(self.btnRename, SIGNAL('clicked(bool)'), self.rename)
        self.connect(self.btnRemove, SIGNAL('clicked(bool)'), self.remove)
        v2layout.addItem(spacerItem)
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        self.rulesetDescription.setSizePolicy(sizePolicy)
        self.retranslateUi()
        self.treeView = QTreeView()
        v1layout.addWidget(self.treeView)

    def copy(self):
        """copy the ruleset"""
        newRuleset = self.ruleset.copy()
        if newRuleset:
            self.rulesetList.append(newRuleset)
            self.rulesetNameList.addItem(m18n(newRuleset.name))

    def modify(self):
        """edit the rules"""
        dlg = ModifyRuleset(self)
        dlg.exec_()

    def rename(self):
        """rename the ruleset"""
        entry = self.rulesetNameList.currentItem()
        (txt, txtOk) = QInputDialog.getText(self, i18n('rename ruleset'), entry.text(),
                    QLineEdit.Normal, entry.text())
        if txtOk:
            entry.setText(txt)
            self.ruleset.rename(unicode(txt))

    def remove(self):
        """removes a ruleset"""
        if self.ruleset.isCustomized(True):
            self.ruleset.remove()
            self.refresh()

    def save(self):
        """saves all ruleset lists"""
        for ruleset in self.rulesetList:
            ruleset.save()

    def retranslateUi(self):
        """translate to current language"""
        self.rulesetRowChanged()
        self.btnCopy.setText(m18n("&Copy"))
        self.btnModify.setText(m18n("&Modify"))
        self.btnRename.setText(m18n("&Rename"))
        self.btnRemove.setText(m18n("R&emove"))

    def rulesetRowChanged(self):
        """user selected a new ruleset, update our information about it"""
        if self.rulesetList and len(self.rulesetList):
            self.ruleset = self.rulesetList[self.rulesetNameList.currentRow()]
            self.rulesetDescription.setText(m18n(self.ruleset.description))
