# -*- coding: utf-8 -*-
"""
    Copyright (C) 2008-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

    partially based on C++ code from:
    Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

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
    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
"""

from PyQt4.QtCore import Qt, QVariant
from PyQt4.QtGui import QWidget, QHBoxLayout, QVBoxLayout, \
    QPushButton, QSpacerItem, QSizePolicy, \
    QTreeView, QStyledItemDelegate, QSpinBox, QComboBox, \
    QFont, QAbstractItemView
from PyQt4.QtCore import QModelIndex
from scoringengine import Ruleset, PredefinedRuleset, Rule, Score
from util import m18n, m18nc, i18nc, english, logException
from statesaver import StateSaver
from differ import RulesetDiffer
from common import Debug
from tree import TreeItem, RootItem, TreeModel

from modeltest import ModelTest

class RuleRootItem(RootItem):
    """the root item for the ruleset tree"""

    def columnCount(self):
        return 3

class RuleTreeItem(TreeItem):
    """generic class for items in our rule tree"""
    # pylint: disable=W0223
    # we know content() is abstract, this class is too

    @staticmethod
    def columnCount():
        """every item has 4 columns"""
        return 3

    def ruleset(self):
        """returns the ruleset containing this item"""
        item = self
        while not isinstance(item.rawContent, Ruleset):
            item = item.parent
        return item.rawContent

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

class RuleModel(TreeModel):
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
        self.rootItem = RuleRootItem(rootData)

    def canFetchMore(self, dummyParent=None):
        """did we already load the rules? We only want to do that
        when the config tab with rulesets is actually shown"""
        return not self.loaded

    def fetchMore(self, dummyParent=None):
        """load the rules"""
        for ruleset in self.rulesets:
            self.appendRuleset(ruleset)
        self.loaded = True

    def data(self, index, role): # pylint: disable=R0201
        """get data fom model"""
        result = QVariant()
        if index.isValid():
            item = index.internalPointer()
            if role == Qt.DisplayRole:
                if index.column() == 1:
                    if isinstance(item, RuleItem) and item.rawContent.parType is bool:
                        return QVariant('')
                result = QVariant(item.content(index.column()))
            elif role == Qt.CheckStateRole:
                if index.column() == 1:
                    if isinstance(item, RuleItem) and item.rawContent.parType is bool:
                        bData = item.content(index.column())
                        result = QVariant(Qt.Checked if bData else Qt.Unchecked)
            elif role == Qt.TextAlignmentRole:
                result = QVariant(int(Qt.AlignLeft|Qt.AlignVCenter))
                if index.column() == 1:
                    result = QVariant(int(Qt.AlignRight|Qt.AlignVCenter))
            elif role == Qt.FontRole and index.column() == 0:
                ruleset = item.ruleset()
                if isinstance(ruleset, PredefinedRuleset):
                    font = QFont()
                    font.setItalic(True)
                    result = QVariant(font)
            elif role == Qt.ToolTipRole:
                tip = '<b></b>%s<b></b>' % m18n(item.tooltip()) if item else ''
                result = QVariant(tip)
        return result

    def headerData(self, section, orientation, role):
        """tell the view about the wanted headers"""
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.rootItem.content(section)
        else:
            return QVariant()

    def appendRuleset(self, ruleset):
        """append ruleset to the model"""
        if not ruleset:
            return
        ruleset.load()
        parent = QModelIndex()
        row = self.rootItem.childCount()
        self.insertRows(row, list([RulesetItem(ruleset)]), parent)
        rulesetIndex = self.index(row, 0, parent)
        self.insertRows(0, list([RuleListItem(x) for x in ruleset.ruleLists]), rulesetIndex)
        for ridx, ruleList in enumerate(ruleset.ruleLists):
            listIndex = self.index(ridx, 0, rulesetIndex)
            self.insertRows(0, list([RuleItem(x) for x in ruleList]), listIndex)

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
                elif isinstance(content, Rule):
                    if column >= 3:
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
                self.dataChanged.emit(index, index)
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
        if isinstance(content, Ruleset) and column == 0:
            mayEdit = True
        elif isinstance(content, Rule):
            mayEdit = column in [0, 1, 2]
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

class RuleDelegate(QStyledItemDelegate):
    """delegate for rule editing"""
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def createEditor(self, parent, option, index):
        """create field editors"""
        editor = None
        column = index.column()
        if column == 1:
            item = index.internalPointer()
            if item.rawContent.parType is int:
                editor = QSpinBox(parent)
                editor.setRange(-9999, 9999)
                editor.setSingleStep(2)
                editor.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        elif column == 2:
            editor = QComboBox(parent)
            editor.addItems(list(m18n(x) for x in Score.unitNames))
            editor.setAutoFillBackground(True)
        if not editor:
            editor = QStyledItemDelegate.createEditor(self, parent, option, index)
        editor.setFrame(False)  # make the editor use all available place
        return editor

    def setEditorData(self, editor, index):
        """initialize editors"""
        text = index.model().data(index, Qt.DisplayRole).toString()
        column = index.column()
        item = index.internalPointer()
        if column == 0:
            editor.setText(text)
        elif column == 1:
            if item.rawContent.parType is int:
                editor.setValue(text.toInt()[0])
            else:
                editor.setText(text)
        elif column == 2:
            rule = item.rawContent
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
                model.dataChanged.emit(index, index)
            return
        QStyledItemDelegate.setModelData(self, editor, model, index)

class RuleTreeView(QTreeView):
    """Tree view for our rulesets"""
    def __init__(self, name, btnCopy=None, btnRemove=None, btnCompare=None, parent=None):
        QTreeView.__init__(self, parent)
        self.name = name
        self.setObjectName('RuleTreeView')
        self.btnCopy = btnCopy
        self.btnRemove = btnRemove
        self.btnCompare = btnCompare
        for button in [self.btnCopy, self.btnRemove, self.btnCompare]:
            if button:
                button.setEnabled(False)
        self.header().setObjectName('RuleTreeViewHeader')
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.ruleModel = None
        self.rulesets = []
        self.differs = []
        self.state = None
        StateSaver(self.header())

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
                if Debug.modelTest:
                    self.ruleModelTest = ModelTest(self.ruleModel, self)
                self.show()
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
        if self.ruleModel.canFetchMore():
            # we want to load all before adjusting column width
            self.ruleModel.fetchMore()
        self.expandAll() # because resizing only works for expanded fields
        for col in range(4):
            self.resizeColumnToContents(col)
        self.setColumnWidth(0, min(self.columnWidth(0), self.geometry().width()//2))
        self.collapseAll()

    def selectedRow(self):
        """returns the currently selected row index (with column 0)"""
        rows = self.selectionModel().selectedRows()
        if len(rows) == 1:
            return rows[0]

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
            self.model().insertRows(row.row()+1, list([RuleItem(newRule)]), row.parent())
            ruleset.dirty = True

    def removeRow(self):
        """removes a ruleset or a rule"""
        row = self.selectedRow()
        if row:
            assert not isinstance(row.internalPointer().ruleset(), PredefinedRuleset)
            self.model().removeRows(row.row(), parent=row.parent())

    def compareRow(self):
        """shows the difference between two rulesets"""
        rows = self.selectionModel().selectedRows()
        ruleset = rows[0].internalPointer().rawContent
        assert isinstance(ruleset, Ruleset)
        differ = RulesetDiffer(ruleset, self.rulesets)
        differ.show()
        self.differs.append(differ)

class RulesetSelector( QWidget):
    """presents all available rulesets with previews"""
    def __init__(self, parent):
        super(RulesetSelector, self).__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
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
        for widget in [self.v1widget, hlayout, v1layout, v2layout]:
            widget.setContentsMargins(0, 0, 0, 0)
        v1layout.setContentsMargins(0, 0, 0, 0)
        v2layout.setContentsMargins(0, 0, 0, 0)
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
        self.btnCopy.clicked.connect(self.rulesetView.copyRow)
        self.btnRemove.clicked.connect(self.rulesetView.removeRow)
        self.btnCompare.clicked.connect(self.rulesetView.compareRow)
        v2layout.addItem(spacerItem)
        self.rulesetView.setItemDelegate(RuleDelegate(self))
        self.retranslateUi()
        self.refresh()

    def refresh(self):
        """reload the rulesets"""
        self.rulesetView.rulesets = Ruleset.availableRulesets()

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
