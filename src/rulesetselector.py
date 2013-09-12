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

from PyQt4.QtCore import Qt, QVariant, QSize
from PyQt4.QtGui import QWidget, QHBoxLayout, QVBoxLayout, \
    QPushButton, QSpacerItem, QSizePolicy, \
    QTreeView, QFont, QAbstractItemView, QHeaderView
from PyQt4.QtCore import QModelIndex
from rule import Ruleset, PredefinedRuleset, Rule
from util import m18n, m18nc, english, uniqueList
from differ import RulesetDiffer
from common import Debug
from tree import TreeItem, RootItem, TreeModel
from kde import Sorry, KApplication
from modeltest import ModelTest
from genericdelegates import RightAlignedCheckboxDelegate
from statesaver import StateSaver

class RuleRootItem(RootItem):
    """the root item for the ruleset tree"""

    def columnCount(self):
        return len(self.rawContent)

class RuleTreeItem(TreeItem):
    """generic class for items in our rule tree"""
    # pylint: disable=W0223
    # we know content() is abstract, this class is too

    def columnCount(self):
        """can be different for every rule"""
        if hasattr(self, 'colCount'):
            return self.colCount # pylint: disable=E1101
        else:
            return len(self.rawContent)

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
        return ''

    def columnCount(self):
        return 1

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
        colNames = [unicode(x.toString()) for x in self.parent.parent.parent.rawContent]
        content = self.rawContent
        if column == 0:
            return m18n(content.name)
        else:
            if content.parType:
                if column == 1:
                    return content.parameter
            else:
                if not hasattr(content.score, str(column)):
                    column = colNames[column]
                return unicode(getattr(content.score, column))
        return ''

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
        unitNames = list()
        for ruleset in rulesets:
            ruleset.load()
            for rule in ruleset.allRules:
                unitNames.extend(rule.score.unitNames.items())
        unitNames = sorted(unitNames, key=lambda x: x[1])
        unitNames = uniqueList(x[0] for x in unitNames)
        rootData = [QVariant(title)]
        for unitName in unitNames:
            rootData.append(QVariant(unitName))
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
        # pylint: disable=R0912
        # too many branches
        result = QVariant()
        if index.isValid():
            item = index.internalPointer()
            if role in (Qt.DisplayRole, Qt.EditRole):
                if index.column() == 1:
                    if isinstance(item, RuleItem) and item.rawContent.parType is bool:
                        return QVariant('')
                showValue = item.content(index.column())
                if isinstance(showValue, basestring) and showValue.endswith('.0'):
                    try:
                        showValue = str(int(float(showValue)))
                    except ValueError:
                        pass
                if showValue == '0':
                    showValue = ''
                result = QVariant(showValue)
            elif role == Qt.CheckStateRole:
                if self.isCheckboxCell(index):
                    bData = item.content(index.column())
                    result = QVariant(Qt.Checked if bData else Qt.Unchecked)
            elif role == Qt.TextAlignmentRole:
                result = QVariant(int(Qt.AlignLeft|Qt.AlignVCenter))
                if index.column() > 0:
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

    @staticmethod
    def isCheckboxCell(index):
        """are we dealing with a checkbox?"""
        if index.column() != 1:
            return False
        item = index.internalPointer()
        return isinstance(item, RuleItem) and item.rawContent.parType is bool

    def headerData(self, section, orientation, role):
        """tell the view about the wanted headers"""
        if Qt is None:
            # happens when kajongg exits unexpectedly
            return
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if section >= self.rootItem.columnCount():
                return QVariant()
            result = self.rootItem.content(section).toString()
            if result == 'doubles':
                result = 'x2'
            return m18n(result)
        elif role == Qt.TextAlignmentRole:
            leftRight = Qt.AlignLeft if section == 0 else Qt.AlignRight
            return QVariant(int(leftRight|Qt.AlignVCenter))
        else:
            return QVariant()

    def appendRuleset(self, ruleset):
        """append ruleset to the model"""
        if not ruleset:
            return
        ruleset.load()
        parent = QModelIndex()
        row = self.rootItem.childCount()
        rulesetItems = list([RulesetItem(ruleset)])
        self.insertRows(row, rulesetItems, parent)
        rulesetIndex = self.index(row, 0, parent)
        ruleListItems = list([RuleListItem(x) for x in ruleset.ruleLists])
        for item in ruleListItems:
            item.colCount = self.rootItem.columnCount()
        self.insertRows(0, ruleListItems, rulesetIndex)
        for ridx, ruleList in enumerate(ruleset.ruleLists):
            listIndex = self.index(ridx, 0, rulesetIndex)
            ruleItems = list([RuleItem(x) for x in ruleList if not 'internal' in x.options])
            self.insertRows(0, ruleItems, listIndex)

class EditableRuleModel(RuleModel):
    """add methods needed for editing"""
    def __init__(self, rulesets, title, parent=None):
        RuleModel.__init__(self, rulesets, title, parent)

    def __setRuleData(self, column, content, value):
        """change rule data in the model"""
        # pylint:  disable=R0912
        # allow more than 12 branches
        dirty, message = False, None
        if column == 0:
            name = unicode(value.toString())
            if content.name != english(name):
                dirty = True
                content.name = english(name)
        elif column == 1 and content.parType:
            oldParameter = content.parameter
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
                if content.parameter != unicode(value.toString()):
                    dirty = True
                    content.parameter = unicode(value.toString())
            message = content.validateParameter()
            if message:
                content.parameter = oldParameter
                dirty = False
        else:
            unitName = str(self.rootItem.content(column).toString())
            dirty, message = content.score.change(unitName, value)
        return dirty, message

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
                    dirty = oldName != content.name
                elif isinstance(content, Rule):
                    dirty, message = self.__setRuleData(column, content, value)
                    if message:
                        Sorry(message)
                        return False
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
                if isinstance(content, Rule):
                    ruleset.updateRule(content)
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
            checkable = column == 1 and content.parType is bool
            mayEdit = column
        else:
            mayEdit = False
        mayEdit = mayEdit and not isinstance(item.ruleset(), PredefinedRuleset)
        result = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if mayEdit:
            result |= Qt.ItemIsEditable
        if checkable:
            result |= Qt.ItemIsUserCheckable
        return result

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
        self.ruleModelTest = None
        self.rulesets = []
        self.differs = []

    def dataChanged(self, dummyIndex1, dummyIndex2):
        """gets called if the model has changed: Update all differs"""
        for differ in self.differs:
            differ.rulesetChanged()

    @property
    def rulesets(self):
        """a list of rulesets made available by this model"""
        return self.ruleModel.rulesets

    @rulesets.setter
    def rulesets(self, rulesets):
        """a new list: update display"""
        if not self.ruleModel or self.ruleModel.rulesets != rulesets:
            if self.btnRemove and self.btnCopy:
                self.ruleModel = EditableRuleModel(rulesets, self.name)
            else:
                self.ruleModel = RuleModel(rulesets, self.name)
            self.setItemDelegateForColumn(1, RightAlignedCheckboxDelegate(self, self.ruleModel.isCheckboxCell))
            self.setModel(self.ruleModel)
            if Debug.modelTest:
                self.ruleModelTest = ModelTest(self.ruleModel, self)
            self.show()

    def selectionChanged(self, selected, dummyDeselected):
        """update editing buttons"""
        enableCopy = enableRemove = enableCompare = False
        if selected.indexes():
            item = selected.indexes()[0].internalPointer()
            isPredefined = isinstance(item.ruleset(), PredefinedRuleset)
            if isinstance(item, RulesetItem):
                enableCopy = enableCompare = True
                enableRemove = not isPredefined
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
        header = self.header()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(-1)
        for col in range(1, header.count()):
            header.setResizeMode(0, QHeaderView.ResizeToContents)
        header.setResizeMode(0, QHeaderView.Stretch)
        for col in range(header.count()):
            self.resizeColumnToContents(col)

    def selectedRow(self):
        """returns the currently selected row index (with column 0)"""
        rows = self.selectionModel().selectedRows()
        if len(rows) == 1:
            return rows[0]

    def copyRow(self):
        """copy a ruleset"""
        row = self.selectedRow()
        if not row:
            return
        item = row.internalPointer()
        assert isinstance(item, RulesetItem)
        self.model().appendRuleset(item.rawContent.copy(minus=True))

    def removeRow(self):
        """removes a ruleset or a rule"""
        row = self.selectedRow()
        if row:
            item = row.internalPointer()
            assert not isinstance(item.ruleset(), PredefinedRuleset)
            assert isinstance(item, RulesetItem)
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
    def __init__(self, parent=None):
        super(RulesetSelector, self).__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.setupUi()

    def setupUi(self):
        """layout the window"""
        self.setWindowTitle(m18n('Customize rulesets') + ' - Kajongg')
        self.setObjectName('Rulesets')
        hlayout = QHBoxLayout(self)
        v1layout = QVBoxLayout()
        self.v1widget = QWidget()
        v1layout = QVBoxLayout(self.v1widget)
        v2layout = QVBoxLayout()
        hlayout.addWidget(self.v1widget)
        hlayout.addLayout(v2layout)
        for widget in [self.v1widget, hlayout, v1layout, v2layout]:
            widget.setContentsMargins(0, 0, 0, 0)
        hlayout.setStretchFactor(self.v1widget, 10)
        self.btnCopy = QPushButton()
        self.btnRemove = QPushButton()
        self.btnCompare = QPushButton()
        self.btnClose = QPushButton()
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
        self.btnClose.clicked.connect(self.hide)
        v2layout.addItem(spacerItem)
        v2layout.addWidget(self.btnClose)
        self.retranslateUi()
        StateSaver(self)
        self.show()

    def sizeHint(self):
        """we never want a horizontal scrollbar for player names,
        we always want to see them in full"""
        result = QWidget.sizeHint(self)
        available = KApplication.kApplication().desktop().availableGeometry()
        height = max(result.height(), available.height() * 2 // 3)
        width = max(result.width(), available.width() // 2)
        return QSize(width, height)

    def minimumSizeHint(self):
        """we never want a horizontal scrollbar for player names,
        we always want to see them in full"""
        return self.sizeHint()

    def showEvent(self, dummyEvent):
        """reload the rulesets"""
        self.refresh()

    def refresh(self):
        """retranslate and reload rulesets"""
        self.retranslateUi()
        self.rulesetView.rulesets = Ruleset.availableRulesets()

    def hideEvent(self, event):
        """close all differ dialogs"""
        for differ in self.rulesetView.differs:
            differ.hide()
            del differ
        QWidget.hideEvent(self, event)

    def retranslateUi(self):
        """translate to current language"""
        self.btnCopy.setText(m18n("Copy"))
        self.btnCompare.setText(m18nc('Kajongg ruleset comparer', 'Compare'))
        self.btnRemove.setText(m18n("Remove"))
        self.btnClose.setText(m18n('Close'))
