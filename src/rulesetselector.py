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
from scoring import Ruleset, Rule, DefaultRuleset
from rulesets import defaultRulesets
from util import m18n, m18nc, i18nc

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
        if isinstance(data, list) and len(data) > column:
            return data[column]
        return ''

    def row(self):
        if self.parent:
            return self.parent.children.index(self)
        return 0

    def ruleset(self):
        """returns the ruleset containing this item"""
        item = self
        while not isinstance(item._data, Ruleset):
            item = item.parent
        return item._data

    def tooltip(self):
        return 'tooltip not yet implemented for class ' + self.__class__.__name__

class RulesetItem(RuleTreeItem):
    def __init__(self, data):
        RuleTreeItem.__init__(self, data)

    def data(self, column):
        data = self._data
        if column == 0:
            return data.name
        elif column == 3:
            return data.description
        return ''

    def tooltip(self):
        return self._data.description

class RuleListItem(RuleTreeItem):
    def __init__(self, data):
        RuleTreeItem.__init__(self, data)

    def data(self, column):
        if column == 0:
            data = self._data
            return Ruleset.rulelistNames()[data]
        return ''

    def tooltip(self):
        return '<b>' + self.ruleset().name + '</b><br><br>' + \
            Ruleset.rulelistDescriptions()[self._data]

class RuleItem(RuleTreeItem):
    def __init__(self, data):
        RuleTreeItem.__init__(self, data)

    def data(self, column):
        data = self._data
        ruleset = self.ruleset()
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
        return ''

    def tooltip(self):
        return self.ruleset().name

class RuleModel(QAbstractItemModel):
    """a model for our rule table"""
    def __init__(self,  rulesets, parent = None):
        super(RuleModel, self).__init__(parent)
        self.rulesets = rulesets
        rootData = []
        if len(rulesets) and isinstance(rulesets[0], DefaultRuleset):
            rootData.append(QVariant(i18nc('Rulesetselector', "Unchangeable default Rulesets")))
        else:
            rootData.append(QVariant(i18nc('Rulesetselector', "Changeable customized Rulesets")))
        rootData.append(QVariant(i18nc('Rulesetselector', "Score")))
        rootData.append(QVariant(i18nc('Rulesetselector', "Unit")))
        rootData.append(QVariant(i18nc('Rulesetselector', "Definition")))
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
            listItem = rulesetItem.appendChild(RuleListItem(ridx))
            for rule in ruleList:
                listItem.appendChild(RuleItem(rule))

    def setupModelData(self):
        for ruleset in self.rulesets:
            self.addRuleset(ruleset)

class RuleTreeView(QTreeView):
    def __init__(self, parent=None):
        QTreeView.__init__(self, parent)

    def selectedItem(self):
        rows = self.selectionModel().selectedRows()
        if len(rows) == 1:
            return rows[0].internalPointer()

    def selectedData(self):
        item = self.selectedItem()
        if item:
            return item._data

    def mouseMoveEvent(self, event):
        item = self.indexAt(event.pos()).internalPointer()
        self.setToolTip('<b></b>'+item.tooltip()+'<b></b>' if item else '')

class RulesetSelector( QWidget):
    """presents all available rulesets with previews"""
    def __init__(self, parent,  pref):
        assert pref # quieten pylint
        super(RulesetSelector, self).__init__(parent)
        self.setupUi()

    def showEvent(self, event):
        self.refresh()
        QWidget.showEvent(self, event)

    def refresh(self):
        """reload all ruleset trees"""
        self.customizedRulesets = Ruleset.availableRulesets()
        self.customizedModel = RuleModel(self.customizedRulesets)
        self.customizedView.setModel(self.customizedModel)

        self.defaultRulesets = defaultRulesets()
        self.defaultModel = RuleModel(self.defaultRulesets)
        self.defaultView.setModel(self.defaultModel)

        for model in list([self.customizedModel, self.defaultModel]):
            model.setupModelData()
        for view in list([self.customizedView, self.defaultView]):
            view.expandAll() # because resizing only works for expanded fields
            for col in range(4):
                view.resizeColumnToContents(col)
            view.collapseAll()

    def setupUi(self):
        """layout the window"""
        hlayout = QHBoxLayout(self)
        v1layout = QVBoxLayout()
        self.v1widget = QWidget()
        v1layout = QVBoxLayout(self.v1widget)
        v2layout = QVBoxLayout()
        hlayout.addWidget(self.v1widget)
        hlayout.addLayout(v2layout)
        self.defaultView= RuleTreeView()
        self.customizedView = RuleTreeView()
        v1layout.addWidget(self.defaultView)
        v1layout.addWidget(self.customizedView)
        for view in [self.defaultView, self.customizedView]:
            view.setWordWrap(True)
            view.setMouseTracking(True)
        self.btnCopy = QPushButton()
        self.btnRemove = QPushButton()
        spacerItem = QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        v2layout.addWidget(self.btnCopy)
        v2layout.addWidget(self.btnRemove)
        self.connect(self.btnCopy, SIGNAL('clicked(bool)'), self.copy)
        self.connect(self.btnRemove, SIGNAL('clicked(bool)'), self.remove)
        v2layout.addItem(spacerItem)
        self.retranslateUi()

    def selectedItem(self):
        """returns the selected ruleset/rule or None.
        If None, tells user to select an entire ruleset or a single rule"""
        view = self.v1widget.focusWidget()
        if isinstance(view, RuleTreeView):
            result = view.selectedItem()
            if isinstance(result._data, (Ruleset, Rule)):
                return result
        KMessageBox.sorry(None, i18n('Please select an entire ruleset or a single rule'))

    def selectedData(self):
        """returns the selected ruleset/rule or None.
        If None, tells user to select an entire ruleset or a single rule"""
        return self.selectedItem()._data

    def copy(self):
        """copy the ruleset"""
        data = self.selectedData()
        if isinstance(data, Ruleset):
            newRuleset = data.copy()
            if newRuleset:
                self.customizedModel.addRuleset(newRuleset)
                self.customizedModel.reset()
        elif isinstance(data, Rule):
            newRule = data.copy()
            item = self.selectedItem()
            ruleset = item.ruleset()
            ruleset.ruleLists[item.parent._data].append(newRule)
            ruleset.save()
            self.refresh()

    def remove(self):
        """removes a ruleset"""
        data = self.selectedData()
        if isinstance(data, DefaultRuleset):
            KMessageBox.sorry(None, i18n('Cannot remove a default ruleset'))
        elif isinstance(data, Ruleset):
            data.remove()
            self.refresh()
        elif isinstance(data, Rule):
            item = self.selectedItem()
            ruleset = item.ruleset()
            ruleList = ruleset.ruleLists[item.parent._data]
            ruleList.remove(data)
            ruleset.save()
            self.refresh()

    def save(self):
        """saves all customized rulesets"""
        for ruleset in self.customizedRulesets:
            ruleset.save()

    def retranslateUi(self):
        """translate to current language"""
        self.btnCopy.setText(m18n("&Copy"))
        self.btnRemove.setText(m18n("R&emove"))
