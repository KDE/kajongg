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

from PyQt4.QtCore import SIGNAL, Qt, QVariant
from PyQt4.QtGui import QWidget, QHBoxLayout, QVBoxLayout, \
    QPushButton, QSpacerItem, QSizePolicy, \
    QTreeView, QItemDelegate, QSpinBox, QComboBox,  \
    QFont, QAbstractItemView
from PyQt4.QtCore import QAbstractItemModel, QModelIndex
from scoringengine import Ruleset, PredefinedRuleset, Rule,  Score
from util import m18n, i18nc, english, StateSaver
#make predefined rulesets known:
import predefined

class RuleTreeItem(object):
    """generic class for items in our rule tree"""
    def __init__(self, data):
        self.content = data
        self.parent = None
        self.children = []

    def insert(self, row, data):
        """add a new child to this tree node"""
        if not isinstance(data, RuleTreeItem):
            data = RuleTreeItem(data)
        data.parent = self
        self.children.insert(row, data)
        return data

    def remove(self):
        """remove this item from the model and the data base.
        This is an abstract method."""
        assert self  # quieten pylint
        raise Exception('cannot remove this RuleTreeItem. We should never get here.')

    def child(self, row):
        """return a specific child item"""
        return self.children[row]

    def childCount(self):
        """how many children does this item have?"""
        return len(self.children)

    @staticmethod
    def columnCount():
        """every item has 4 columns"""
        return 4

    def data(self, column):
        """data held by this item"""
        data = self.content
        if isinstance(data, list) and len(data) > column:
            return data[column]
        return ''

    def row(self):
        """the row of this item in parent"""
        if self.parent:
            return self.parent.children.index(self)
        return 0

    def ruleset(self):
        """returns the ruleset containing this item"""
        item = self
        while not isinstance(item.content, Ruleset):
            item = item.parent
        return item.content

class RulesetItem(RuleTreeItem):
    """represents a ruleset in the tree"""
    def __init__(self, data):
        RuleTreeItem.__init__(self, data)

    def data(self, column):
        """return data stored in this item"""
        data = self.content
        if column == 0:
            return m18n(data.name)
        elif column == 3:
            return m18n(data.description)
        return ''

    def remove(self):
        """remove this ruleset from the model and the data base"""
        self.content.remove()

    def tooltip(self):
        """the tooltip for a ruleset"""
        return self.content.description

class RuleListItem(RuleTreeItem):
    """represents a list of rules in the tree"""
    def __init__(self, data):
        RuleTreeItem.__init__(self, data)

    def data(self, column):
        """return data stored in this item"""
        if column == 0:
            return m18n(self.content.name)
        return ''

    def tooltip(self):
        """tooltip for a list item explaining the usage of this list"""
        ruleset = self.ruleset()
        return '<b>' + m18n(ruleset.name) + '</b><br><br>' + \
            m18n(self.content.description)

class RuleItem(RuleTreeItem):
    """represents a rule in the tree"""
    def __init__(self, data):
        RuleTreeItem.__init__(self, data)

    def data(self, column):
        """return the data stored in this node"""
        data = self.content
        ruleset = self.ruleset()
        ruleList = self.parent.content
        if column == 0:
            return m18n(data.name)
        else:
            if ruleList.listId == ruleset.intRules.listId:
                if column == 1:
                    return data.definition
            else:
                if column == 1:
                    return str(data.score.value)
                elif column == 2:
                    return Score.unitName(data.score.unit)
                elif column == 3:
                    return data.definition
        return ''

    def remove(self):
        """remove this rule from the model and the data base"""
        self.parent.content.remove(self.content)

    def tooltip(self):
        """tooltip for rule: just the name of the ruleset"""
        return self.ruleset().name

class RuleModel(QAbstractItemModel):
    """a model for our rule table"""
    def __init__(self, rulesets, title, parent = None):
        super(RuleModel, self).__init__(parent)
        self.rulesets = rulesets
        self.loaded = False
        rootData = [ \
            QVariant(title),
            QVariant(i18nc('Rulesetselector', "Score")),
            QVariant(i18nc('Rulesetselector', "Unit")),
            QVariant(i18nc('Rulesetselector', "Definition"))]
        self.rootItem = RuleTreeItem(rootData)

    def canFetchMore(self, parent):
        """did we already load the rules? We only want to do that
        when the config tab with rulesets is actually shown"""
        assert parent # quieten pylint
        return not self.loaded

    def fetchMore(self, parent):
        """load the rules"""
        assert parent # quieten pylint
        for ruleset in self.rulesets:
            self.appendRuleset(ruleset)
        self.loaded = True

    def columnCount(self, parent):
        """how many columns does this node have?"""
        if parent.isValid():
            return parent.internalPointer().columnCount()
        else:
            return self.rootItem.columnCount()

    def data(self, index, role):
        """get data fom model"""
        assert self or True # quieten pylint
        if not index.isValid():
            return QVariant()
        if role == Qt.DisplayRole:
            item = index.internalPointer()
            return QVariant(m18n(item.data(index.column())))
        elif role == Qt.TextAlignmentRole:
            if index.column() == 1:
                return QVariant(int(Qt.AlignRight|Qt.AlignVCenter))
            return QVariant(int(Qt.AlignLeft|Qt.AlignVCenter))
        elif role == Qt.FontRole and index.column() == 0:
            ruleset = index.internalPointer().ruleset()
            if isinstance(ruleset, PredefinedRuleset):
                font = QFont()
                font.setItalic(True)
                return QVariant(font)
        elif role == Qt.ToolTipRole:
            item = index.internalPointer()
            tip = '<b></b>%s<b></b>' % m18n(item.tooltip()) if item else ''
            return QVariant(tip)
        return QVariant()

    def headerData(self, section, orientation, role):
        """tell the view about the wanted headers"""
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.rootItem.data(section)
        else:
            return QVariant()

    def index(self, row, column, parent):
        """generate an index for this item"""
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
        """find the parent index"""
        if not index.isValid():
            return QModelIndex()
        childItem = index.internalPointer()
        parentItem = childItem.parent
        if parentItem == self.rootItem or parentItem is None:
            return QModelIndex()
        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent):
        """how many items?"""
        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()
        return parentItem.childCount()

    def insertItems(self, position, items, parent=QModelIndex()):
        """inserts items into the model"""
        parentItem = parent.internalPointer() if parent.isValid() else self.rootItem
        self.beginInsertRows(parent, position, position + len(items)- 1)
        for row, item in enumerate(items):
            parentItem.insert(position + row, item)
        self.endInsertRows()
        return True

    def appendRuleset(self, ruleset):
        """append ruleset to the model"""
        if not ruleset:
            return
        ruleset.load()
        root = self.rootItem
        parent = QModelIndex()
        row = root.childCount()
        self.insertItems(row, list([RulesetItem(ruleset)]), parent)
        rulesetIndex = self.index(row, 0, parent)
        self.insertItems(0, list([RuleListItem(x) for x in ruleset.ruleLists]), rulesetIndex)
        for ridx, ruleList in enumerate(ruleset.ruleLists):
            listIndex = self.index(ridx, 0, rulesetIndex)
            self.insertItems(0, list([RuleItem(x) for x in ruleList]), listIndex)

class EditableRuleModel(RuleModel):
    """add methods needed for editing"""
    def __init__(self, rulesets, title, parent=None):
        RuleModel.__init__(self, rulesets, title, parent)

    def setData(self, index, value, role=Qt.EditRole):
        """change data in the model"""
        try:
            if index.isValid() and role == Qt.EditRole:
                column = index.column()
                item = index.internalPointer()
                data = item.content
                if isinstance(data, Ruleset) and column == 0:
                    name = str(value.toString())
                    data.rename(english.get(name, name))
                elif isinstance(data, Ruleset) and column == 3:
                    data.description = unicode(value.toString())
                elif isinstance(data, Rule):
                    if column == 0:
                        name = str(value.toString())
                        data.name = english.get(name, name)
                    elif column ==1:
                        data.score.value = value.toInt()[0]
                    elif column ==2:
                        data.score.unit = value.toInt()[0]
                    elif column ==3:
                        data.definition = str(value.toString())
                    else:
                        print 'rule column not implemented', column
                else:
                    return False
                self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"), index, index)
                return True
            return False
        except BaseException:
            return False

    def flags(self, index):
        """tell the view what it can do with this item"""
        assert self # quieten pylint
        if not index.isValid():
            return Qt.ItemIsEnabled
        column = index.column()
        item = index.internalPointer()
        data = item.content
        if isinstance(data, Ruleset) and column in (0, 3):
            mayEdit = True
        elif isinstance(data, Rule):
            mayEdit = column in [0, 1, 2, 3]
        else:
            mayEdit = False
        mayEdit = mayEdit and not isinstance(item.ruleset(), PredefinedRuleset)
        result = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if mayEdit:
            result |= Qt.ItemIsEditable
        return result

    def removeRows(self, position, rows=1, parent=QModelIndex()):
        """reimplement QAbstractItemModel.removeRows"""
        if parent.isValid():
            parentItem = parent.internalPointer()
        else:
            parentItem = self.rootItem
        self.beginRemoveRows(parent, position, position + rows - 1)
        for row in parentItem.children[position:position + rows]:
            row.remove()
        parentItem.children = parentItem.children[:position] + parentItem.children[position + rows:]
        self.endRemoveRows()
        return True

class RuleDelegate(QItemDelegate):
    """delegate for rule editing"""
    def __init__(self, parent=None):
        QItemDelegate.__init__(self, parent)

    def createEditor(self, parent, option, index):
        """create field editors"""
        column = index.column()
        if column == 1:
            spinBox = QSpinBox(parent)
            spinBox.setRange(-9999, 9999)
            spinBox.setSingleStep(2)
            spinBox.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
            return spinBox
        elif column == 2:
            comboBox = QComboBox(parent)
            comboBox.addItems(list([m18n(x) for x in Score.unitNames]))
            return comboBox
        else:
            return QItemDelegate.createEditor(self, parent, option, index)

    def setEditorData(self, editor, index):
        """initialize editors"""
        text = index.model().data(index, Qt.DisplayRole).toString()
        column = index.column()
        if column in (0, 3):
            editor.setText(text)
        elif column == 1:
            editor.setValue(text.toInt()[0])
        elif column == 2:
            rule = index.internalPointer().content
            assert isinstance(rule, Rule)
            editor.setCurrentIndex(rule.score.unit)
        else:
            QItemDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor, model, index):
        """move data changes into model"""
        column = index.column()
        if column == 2:
            rule = index.internalPointer().content
            assert isinstance(rule, Rule)
            rule.score.unit = editor.currentIndex()
        else:
            QItemDelegate.setModelData(self, editor, model, index)

class RuleTreeView(QTreeView):
    """Tree view for our rulesets"""
    def __init__(self, rulesets, name, btnCopy=None, btnRemove=None, parent=None):
        QTreeView.__init__(self, parent)
        if btnRemove and btnCopy:
            self.ruleModel = EditableRuleModel(rulesets, name)
        else:
            self.ruleModel = RuleModel(rulesets, name)
        self.btnCopy = btnCopy
        self.btnRemove = btnRemove
        if btnCopy:
            btnCopy.setEnabled(False)
        if btnRemove:
            btnRemove.setEnabled(False)
        self.setModel(self.ruleModel)
        self.header().setObjectName(name)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.state = None

    def selectionChanged(self, selected, deselected):
        """update editing buttons"""
        assert deselected or True # Quieten pylint
        enableCopy, enableRemove = False, False
        if selected.indexes():
            item = selected.indexes()[0].internalPointer()
            predefined = isinstance(item.ruleset(), PredefinedRuleset)
            if isinstance(item, RulesetItem):
                enableCopy = True
            elif isinstance(item, RuleItem):
                enableCopy = not predefined
            if not predefined:
                enableRemove = isinstance(item, (RulesetItem, RuleItem))
        if self.btnCopy:
            self.btnCopy.setEnabled(enableCopy)
        if self.btnRemove:
            self.btnRemove.setEnabled(enableRemove)

    def showEvent(self, event):
        """reload the models when the view comes into sight"""
        # default: make sure the name column is wide enough
        assert event # quieten pylint
        self.expandAll() # because resizing only works for expanded fields
        for col in range(4):
            self.resizeColumnToContents(col)
        self.collapseAll()
        # now restore saved column widths
        self.state = StateSaver(self.header())

    def hideEvent(self, event):
        """hiding: save state"""
        assert event # quieten pylint
        if self.state:
            self.state.save()

    def selectedRow(self):
        """returns the currently selected row index (with column 0)"""
        rows = self.selectionModel().selectedRows()
        if len(rows) == 1:
            return rows[0]

    def selectedItem(self):
        """returns the currently selected item"""
        row = self.selectedRow()
        if row:
            return row.internalPointer()

    def copyRow(self):
        """copy a ruleset or a rule"""
        row = self.selectedRow()
        if not row:
            return
        item = row.internalPointer()
        assert isinstance(item, RulesetItem) or not isinstance(item.ruleset(), PredefinedRuleset)
        if isinstance(item, RulesetItem):
            self.model().appendRuleset(item.content.copy())
        elif isinstance(item, RuleItem):
            ruleset = item.ruleset()
            newRule = ruleset.copyRule(item.content)
            # we could make this faster by passing the rulelist and position
            # within from the model to copyRule but not time critical.
            # the model and ruleset are expected to be in sync.
            self.model().insertItems(row.row()+1, list([RuleItem(newRule)]), row.parent())

    def removeRow(self):
        """removes a ruleset or a rule"""
        row = self.selectedRow()
        if row:
            assert not isinstance(row.internalPointer().ruleset(), PredefinedRuleset)
            self.model().removeRow(row.row(), row.parent())

class RulesetSelector( QWidget):
    """presents all available rulesets with previews"""
    def __init__(self, parent):
        super(RulesetSelector, self).__init__(parent)
        self.setupUi()

    def setupUi(self):
        """layout the window"""
        hlayout = QHBoxLayout(self)
        v1layout = QVBoxLayout()
        self.v1widget = QWidget()
        v1layout = QVBoxLayout(self.v1widget)
        v2layout = QVBoxLayout()
        hlayout.addWidget(self.v1widget)
        hlayout.addLayout(v2layout)
        hlayout.setStretchFactor(self.v1widget, 10)
        self.btnCopy = QPushButton()
        self.btnRemove = QPushButton()
        self.rulesetView = RuleTreeView(PredefinedRuleset.rulesets() + Ruleset.availableRulesets(),
                m18n('Rule'), self.btnCopy, self.btnRemove)
        v1layout.addWidget(self.rulesetView)
        self.rulesetView.setWordWrap(True)
        self.rulesetView.setMouseTracking(True)
        spacerItem = QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        v2layout.addWidget(self.btnCopy)
        v2layout.addWidget(self.btnRemove)
        self.connect(self.btnCopy, SIGNAL('clicked(bool)'), self.rulesetView.copyRow)
        self.connect(self.btnRemove, SIGNAL('clicked(bool)'), self.rulesetView.removeRow)
        v2layout.addItem(spacerItem)
        self.rulesetView.setItemDelegate(RuleDelegate(self))
        self.retranslateUi()

    def save(self):
        """saves all customized rulesets"""
        if self.rulesetView.model():
            for item in self.rulesetView.model().rootItem.children:
                ruleset = item.content
                if not isinstance(ruleset, PredefinedRuleset):
                    if not item.content.save():
                        return False
        return True

    def retranslateUi(self):
        """translate to current language"""
        self.btnCopy.setText(m18n("&Copy"))
        self.btnRemove.setText(m18n("R&emove"))
