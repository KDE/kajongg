# -*- coding: utf-8 -*-
"""
    Copyright (C) 2008,2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
    QTreeView, QStyledItemDelegate, QSpinBox, QComboBox,  \
    QFont, QAbstractItemView
from PyQt4.QtCore import QAbstractItemModel, QModelIndex
from scoringengine import Ruleset, PredefinedRuleset, Rule, Score
from util import m18n, m18nc, i18nc, english, logException
from statesaver import StateSaver
from differ import RulesetDiffer

class RuleTreeItem(object):
    """generic class for items in our rule tree"""
    def __init__(self, content):
        self.rawContent = content
        self.parent = None
        self.children = []

    def insert(self, row, child):
        """add a new child to this tree node"""
        if not isinstance(child, RuleTreeItem):
            child = RuleTreeItem(child)
        child.parent = self
        self.children.insert(row, child)
        return child

    def remove(self): # pylint: disable=R0201
        """remove this item from the model and the database.
        This is an abstract method."""
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

    def content(self, column):
        """content held by this item"""
        raise NotImplementedError("Virtual Method")

    def row(self):
        """the row of this item in parent"""
        if self.parent:
            return self.parent.children.index(self)
        return 0

    def ruleset(self):
        """returns the ruleset containing this item"""
        item = self
        while not isinstance(item.rawContent, Ruleset):
            item = item.parent
        return item.rawContent

class RootItem(RuleTreeItem):
    """an item for header data"""
    def __init__(self, content):
        RuleTreeItem.__init__(self, content)

    def content(self, column):
        """content held by this item"""
        return self.rawContent[column]

class RulesetItem(RuleTreeItem):
    """represents a ruleset in the tree"""
    def __init__(self, content):
        RuleTreeItem.__init__(self, content)

    def content(self, column):
        """return content stored in this item"""
        if column == 0:
            return m18n(self.rawContent.name)
        elif column == 3:
            return m18n(self.rawContent.description)
        return ''

    def remove(self):
        """remove this ruleset from the model and the database"""
        self.rawContent.remove()

    def tooltip(self):
        """the tooltip for a ruleset"""
        return self.rawContent.description

class RuleListItem(RuleTreeItem):
    """represents a list of rules in the tree"""
    def __init__(self, content):
        RuleTreeItem.__init__(self, content)

    def content(self, column):
        """return content stored in this item"""
        if column == 0:
            return m18n(self.rawContent.name)
        return ''

    def tooltip(self):
        """tooltip for a list item explaining the usage of this list"""
        ruleset = self.ruleset()
        return '<b>' + m18n(ruleset.name) + '</b><br><br>' + \
            m18n(self.rawContent.description)

class RuleItem(RuleTreeItem):
    """represents a rule in the tree"""
    def __init__(self, content):
        RuleTreeItem.__init__(self, content)

    def content(self, column):
        """return the content stored in this node"""
        content = self.rawContent
        if column == 0:
            return m18n(content.name)
        else:
            if content.parType:
                if column == 1:
                    return content.parameter
            else:
                if column == 1:
                    return unicode(content.score.value)
                elif column == 2:
                    return Score.unitName(content.score.unit)
                elif column == 3:
                    return content.definition
        return ''

    def remove(self):
        """remove this rule from the model and the database"""
        ruleList = self.parent.rawContent
        ruleList.remove(self.rawContent)
        ruleset = self.parent.parent.rawContent
        ruleset.dirty = True

    def tooltip(self):
        """tooltip for rule: just the name of the ruleset"""
        ruleset = self.ruleset()
        if self.rawContent.description:
            return '<b>' + m18n(ruleset.name) + '</b><br><br>' + \
                m18n(self.rawContent.description)
        else:
            return m18n(ruleset.name)

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
        self.rootItem = RootItem(rootData)

    def canFetchMore(self, dummyParent):
        """did we already load the rules? We only want to do that
        when the config tab with rulesets is actually shown"""
        return not self.loaded

    def fetchMore(self, dummyParent):
        """load the rules"""
        for ruleset in self.rulesets:
            self.appendRuleset(ruleset)
        self.loaded = True

    def columnCount(self, parent):
        """how many columns does this node have?"""
        if parent.isValid():
            return parent.internalPointer().columnCount()
        else:
            return self.rootItem.columnCount()

    def data(self, index, role): # pylint: disable=R0201
        """get data fom model"""
        result = QVariant()
        if index.isValid():
            if role == Qt.DisplayRole:
                item = index.internalPointer()
                if index.column() == 1:
                    if isinstance(item, RuleItem) and item.rawContent.parType is bool:
                        return QVariant()
                result = QVariant(item.content(index.column()))
            elif role == Qt.CheckStateRole:
                if index.column() == 1:
                    item = index.internalPointer()
                    if isinstance(item, RuleItem) and item.rawContent.parType is bool:
                        bData = item.content(index.column())
                        result =  QVariant(Qt.Checked if bData else Qt.Unchecked)
            elif role == Qt.TextAlignmentRole:
                result = QVariant(int(Qt.AlignLeft|Qt.AlignVCenter))
                if index.column() == 1:
                    result = QVariant(int(Qt.AlignRight|Qt.AlignVCenter))
            elif role == Qt.FontRole and index.column() == 0:
                ruleset = index.internalPointer().ruleset()
                if isinstance(ruleset, PredefinedRuleset):
                    font = QFont()
                    font.setItalic(True)
                    result = QVariant(font)
            elif role == Qt.ToolTipRole:
                item = index.internalPointer()
                tip = '<b></b>%s<b></b>' % m18n(item.tooltip()) if item else ''
                result = QVariant(tip)
        return result

    def headerData(self, section, orientation, role):
        """tell the view about the wanted headers"""
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.rootItem.content(section)
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

    @staticmethod
    def __setRuleData(column, content, value):
        """change rule data in the model"""
        # pylint:  disable=R0912
        # allow more than 12 branches
        dirty = False
        if column == 0:
            name = unicode(value.toString())
            if content.name != english(name):
                dirty = True
                content.name = english(name)
        elif column == 1:
            if content.parType:
                if content.parType is int:
                    if content.parameter != value.toInt()[0]:
                        dirty = True
                        content.parameter = value.toInt()[0]
                elif content.parType is bool:
                    return False
                elif content.parType is unicode:
                    if content.parameter != unicode(value.toString()):
                        dirty = True
                        content.parameter = unicode(value.toString())
                else:
                    newval = value.toInt()[0]
                    if content.parameter != unicode(value.toString()):
                        dirty = True
                        content.parameter = unicode(value.toString())
            else:
                newval = value.toInt()[0]
                if content.score.value != newval:
                    content.score.value = newval
                    dirty = True
        elif column == 2:
            if content.score.unit != value.toInt()[0]:
                dirty = True
                content.score.unit = value.toInt()[0]
        elif column == 3:
            if content.definition != unicode(value.toString()):
                dirty = True
                content.definition = unicode(value.toString())
        return dirty

    def setData(self, index, value, role=Qt.EditRole):
        """change data in the model"""
        # pylint:  disable=R0912
        # allow more than 12 branches
        if not index.isValid():
            return False
        try:
            dirty = False
            column = index.column()
            item = index.internalPointer()
            ruleset = item.ruleset()
            content = item.rawContent
            if role == Qt.EditRole:
                if isinstance(content, Ruleset) and column == 0:
                    name = unicode(value.toString())
                    oldName = content.name
                    content.rename(english(name))
                    dirty |= oldName != content.name
                elif isinstance(content, Ruleset) and column == 3:
                    if content.description != unicode(value.toString()):
                        dirty = True
                        content.description = unicode(value.toString())
                elif isinstance(content, Rule):
                    if column >= 4:
                        logException('rule column %d not implemented' % column)
                        return False
                    dirty = self.__setRuleData(column, content, value)
                else:
                    return False
            elif role == Qt.CheckStateRole:
                if isinstance(content, Rule) and column ==1:
                    if not isinstance(ruleset, PredefinedRuleset):
                        if content.parType is bool:
                            newValue = value == Qt.Checked
                            if content.parameter != newValue:
                                dirty = True
                                content.parameter = newValue
                else:
                    return False
            if dirty:
                ruleset.dirty = True
                self.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"), index, index)
            return True
        except BaseException:
            return False

    def flags(self, index): # pylint: disable=R0201
        """tell the view what it can do with this item"""
        if not index.isValid():
            return Qt.ItemIsEnabled
        column = index.column()
        item = index.internalPointer()
        content = item.rawContent
        checkable = False
        if isinstance(content, Ruleset) and column in (0, 3):
            mayEdit = True
        elif isinstance(content, Rule):
            mayEdit = column in [0, 1, 2, 3]
            checkable = column == 1 and content.parType is bool
        else:
            mayEdit = False
        mayEdit = mayEdit and not isinstance(item.ruleset(), PredefinedRuleset)
        result = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if mayEdit:
            result |= Qt.ItemIsEditable
        if checkable:
            result |= Qt.ItemIsUserCheckable
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

class RuleDelegate(QStyledItemDelegate):
    """delegate for rule editing"""
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def createEditor(self, parent, option, index):
        """create field editors"""
        column = index.column()
        if column == 1:
            item = index.internalPointer()
            if item.rawContent.parType is int:
                spinBox = QSpinBox(parent)
                spinBox.setRange(-9999, 9999)
                spinBox.setSingleStep(2)
                spinBox.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
                return spinBox
        elif column == 2:
            comboBox = QComboBox(parent)
            comboBox.addItems(list([m18n(x) for x in Score.unitNames]))
            return comboBox
        return QStyledItemDelegate.createEditor(self, parent, option, index)

    def setEditorData(self, editor, index):
        """initialize editors"""
        text = index.model().data(index, Qt.DisplayRole).toString()
        column = index.column()
        if column in (0, 3):
            editor.setText(text)
        elif column == 1:
            item = index.internalPointer()
            if item.rawContent.parType is int:
                editor.setValue(text.toInt()[0])
            else:
                editor.setText(text)
        elif column == 2:
            rule = index.internalPointer().rawContent
            assert isinstance(rule, Rule)
            editor.setCurrentIndex(rule.score.unit)
        else:
            QStyledItemDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor, model, index):
        """move changes into model"""
        column = index.column()
        if column == 2:
            item = index.internalPointer()
            rule = item.rawContent
            assert isinstance(rule, Rule)
            if rule.score.unit != editor.currentIndex():
                rule.score.unit = editor.currentIndex()
                item.ruleset().dirty = True
                model.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"), index, index)
            return
        QStyledItemDelegate.setModelData(self, editor, model, index)

class RuleTreeView(QTreeView):
    """Tree view for our rulesets"""
    def __init__(self, name, btnCopy=None, btnRemove=None, btnCompare=None, parent=None):
        QTreeView.__init__(self, parent)
        self.name = name
        self.btnCopy = btnCopy
        self.btnRemove = btnRemove
        self.btnCompare = btnCompare
        for button in [self.btnCopy, self.btnRemove, self.btnCompare]:
            if button:
                button.setEnabled(False)
        self.header().setObjectName(name+'View')
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.ruleModel = None
        self.rulesets = []
        self.differs = []
        self.state = None

    def dataChanged(self, dummyIndex1, dummyIndex2):
        """gets called if the model has changed: Update all differs"""
        for differ in self.differs:
            differ.rulesetChanged()

    @apply
    def rulesets(): # pylint: disable=E0202
        """a list of rulesets made available by this model"""
        def fget(self):
            return self.ruleModel.rulesets
        def fset(self, rulesets):
            if not self.ruleModel or self.ruleModel.rulesets != rulesets:
                if self.btnRemove and self.btnCopy:
                    self.ruleModel = EditableRuleModel(rulesets, self.name)
                else:
                    self.ruleModel = RuleModel(rulesets, self.name)
                self.setModel(self.ruleModel)
        return property(**locals())

    def selectionChanged(self, selected, dummyDeselected):
        """update editing buttons"""
        enableCopy = enableRemove = enableCompare = False
        if selected.indexes():
            item = selected.indexes()[0].internalPointer()
            isPredefined = isinstance(item.ruleset(), PredefinedRuleset)
            if isinstance(item, RulesetItem):
                enableCopy = enableCompare = True
            elif isinstance(item, RuleItem):
                enableCopy = not isPredefined
            if not isPredefined:
                enableRemove = isinstance(item, (RulesetItem, RuleItem))
                if isinstance(item, RuleItem) and 'mandatory' in item.rawContent.actions:
                    enableRemove = False
        if self.btnCopy:
            self.btnCopy.setEnabled(enableCopy)
        if self.btnRemove:
            self.btnRemove.setEnabled(enableRemove)
        if self.btnCompare:
            self.btnCompare.setEnabled(enableCompare)

    def showEvent(self, dummyEvent):
        """reload the models when the view comes into sight"""
        # default: make sure the name column is wide enough
        self.expandAll() # because resizing only works for expanded fields
        for col in range(4):
            self.resizeColumnToContents(col)
        self.collapseAll()
        # now restore saved column widths
        StateSaver(self.header())

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
            self.model().appendRuleset(item.rawContent.copy())
        elif isinstance(item, RuleItem):
            ruleset = item.ruleset()
            newRule = ruleset.copyRule(item.rawContent)
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

    def compareRow(self):
        """shows the difference between two rulesets"""
        rows = self.selectionModel().selectedRows()
        ruleset = rows[0].internalPointer().rawContent
        assert isinstance(ruleset, Ruleset)
        differ = RulesetDiffer(ruleset, self.rulesets)
        differ.show()
        self.differs.append(differ)
        self.connect(differ, SIGNAL("dataChanged(QModelIndex,QModelIndex)"), self.dataChanged)

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
        self.btnCompare = QPushButton()
        self.rulesetView = RuleTreeView(m18nc('kajongg','Rule'), self.btnCopy, self.btnRemove, self.btnCompare)
        v1layout.addWidget(self.rulesetView)
        self.rulesetView.setWordWrap(True)
        self.rulesetView.setMouseTracking(True)
        spacerItem = QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        v2layout.addWidget(self.btnCopy)
        v2layout.addWidget(self.btnRemove)
        v2layout.addWidget(self.btnCompare)
        self.connect(self.btnCopy, SIGNAL('clicked(bool)'), self.rulesetView.copyRow)
        self.connect(self.btnRemove, SIGNAL('clicked(bool)'), self.rulesetView.removeRow)
        self.connect(self.btnCompare, SIGNAL('clicked(bool)'), self.rulesetView.compareRow)
        v2layout.addItem(spacerItem)
        self.rulesetView.setItemDelegate(RuleDelegate(self))
        self.retranslateUi()
        self.refresh()

    def refresh(self):
        """reload the rulesets"""
        self.rulesetView.rulesets = PredefinedRuleset.rulesets() + Ruleset.availableRulesets()

    def closeDiffers(self):
        """close all differ dialogs"""
        for differ in self.rulesetView.differs:
            differ.hide()
            del differ

    def cancel(self):
        """abort edititing, do not save"""
        self.closeDiffers()

    def save(self):
        """saves all customized rulesets"""
        self.closeDiffers()
        if self.rulesetView.model():
            for item in self.rulesetView.model().rootItem.children:
                ruleset = item.rawContent
                if not isinstance(ruleset, PredefinedRuleset):
                    if not ruleset.save():
                        return False
        return True

    def retranslateUi(self):
        """translate to current language"""
        self.btnCopy.setText(m18n("&Copy"))
        self.btnRemove.setText(m18n("R&emove"))
        self.btnCompare.setText(m18nc('Kajongg ruleset comparer', 'C&ompare'))