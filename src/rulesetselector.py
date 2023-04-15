# -*- coding: utf-8 -*-
"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

partially based on C++ code from:
Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

SPDX-License-Identifier: GPL-2.0

"""

from qt import Qt, QSize
from qt import QWidget, QHBoxLayout, QVBoxLayout, \
    QPushButton, QSpacerItem, QSizePolicy, \
    QTreeView, QFont, QAbstractItemView, QHeaderView
from qt import QModelIndex
from kdestub import KApplication
from rule import Ruleset, PredefinedRuleset, RuleBase, ParameterRule, BoolRule
from util import uniqueList
from mi18n import i18n, i18nc, i18ncE, english
from differ import RulesetDiffer
from common import Debug
from tree import TreeItem, RootItem, TreeModel
from dialogs import Sorry
from modeltest import ModelTest
from genericdelegates import RightAlignedCheckboxDelegate, ZeroEmptyColumnDelegate
from statesaver import StateSaver
from guiutil import decorateWindow


class RuleRootItem(RootItem):

    """the root item for the ruleset tree"""

    def columnCount(self):
        return len(self.raw)


class RuleTreeItem(TreeItem):

    """generic class for items in our rule tree"""
    # pylint: disable=abstract-method
    # we know content() is abstract, this class is too

    def columnCount(self):
        """can be different for every rule"""
        if hasattr(self, 'colCount'):
            return self.colCount
        return len(self.raw)

    def ruleset(self):
        """return the ruleset containing this item"""
        item = self
        while not isinstance(item.raw, Ruleset):
            item = item.parent
        return item.raw


class RulesetItem(RuleTreeItem):

    """represents a ruleset in the tree"""

    def __init__(self, content):
        RuleTreeItem.__init__(self, content)

    @property
    def raw(self) ->Ruleset:
        return super().raw

    def content(self, column):
        """return content stored in this item"""
        if column == 0:
            return self.raw.name
        return ''

    def columnCount(self):
        return 1

    def remove(self):
        """remove this ruleset from the model and the database"""
        self.raw.remove()

    def tooltip(self):
        """the tooltip for a ruleset"""
        return self.raw.description


class RuleListItem(RuleTreeItem):

    """represents a list of rules in the tree"""

    def __init__(self, content):
        RuleTreeItem.__init__(self, content)

    @property
    def raw(self) ->'RuleList':
        return super().raw

    def content(self, column):
        """return content stored in this item"""
        if column == 0:
            return self.raw.name
        return ''

    def tooltip(self):
        """tooltip for a list item explaining the usage of this list"""
        ruleset = self.ruleset()
        return '<b>' + i18n(ruleset.name) + '</b><br><br>' + \
            i18n(self.raw.description)


class RuleItem(RuleTreeItem):

    """represents a rule in the tree"""

    def __init__(self, content):
        RuleTreeItem.__init__(self, content)

    @property
    def raw(self):
        return super().raw

    def content(self, column):
        """return the content stored in this node"""
        colNames = self.parent.parent.parent.raw  # type:ignore
        if column == 0:
            return self.raw.name
        if isinstance(self.raw, ParameterRule):
            if column == 1:
                return self.raw.parameter
        else:
            _ = str(column)
            if not hasattr(self.raw.score, _):
                _ = colNames[column]
            return getattr(self.raw.score, _)
        return ''

    def tooltip(self):
        """tooltip for rule: just the name of the ruleset"""
        ruleset = self.ruleset()
        if self.raw.description:
            return '<b>' + i18n(ruleset.name) + '</b><br><br>' + \
                i18n(self.raw.description)
        return i18n(ruleset.name)


class RuleModel(TreeModel):

    """a model for our rule table"""

    def __init__(self, rulesets, title, parent=None):
        super().__init__(parent)
        self.rulesets = rulesets
        self.loaded = False
        unitNames = []
        for ruleset in rulesets:
            ruleset.load()
            for rule in ruleset.allRules:
                unitNames.extend(rule.score.unitNames.items())
        unitNames = sorted(unitNames, key=lambda x: x[1])
        unitNames = uniqueList(x[0] for x in unitNames)
        rootData = [title]
        rootData.extend(unitNames)
        self.rootItem = RuleRootItem(rootData)

    def canFetchMore(self, unusedParent=None):
        """did we already load the rules? We only want to do that
        when the config tab with rulesets is actually shown"""
        return not self.loaded

    def fetchMore(self, unusedParent=None):
        """load the rules"""
        for ruleset in self.rulesets:
            self.appendRuleset(ruleset)
        self.loaded = True

    def data(self, index, role):
        """get data fom model"""
        # pylint: disable=too-many-branches
        # too many branches
        result = None
        if index.isValid():
            item = index.internalPointer()
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
                if index.column() == 1:
                    if isinstance(item, RuleItem) and isinstance(item.raw, BoolRule):
                        return ''
                showValue = item.content(index.column())
                if isinstance(showValue, str) and showValue.endswith('.0'):
                    try:
                        showValue = str(int(float(showValue)))
                    except ValueError:
                        pass
                if showValue == '0':
                    showValue = ''
                result = showValue
            elif role == Qt.ItemDataRole.CheckStateRole:
                if self.isCheckboxCell(index):
                    bData = item.content(index.column())
                    result = Qt.CheckState.Checked if bData else Qt.CheckState.Unchecked
            elif role == Qt.ItemDataRole.TextAlignmentRole:
                result = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if index.column() > 0:
                    result = int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            elif role == Qt.ItemDataRole.FontRole and index.column() == 0:
                ruleset = item.ruleset()
                if isinstance(ruleset, PredefinedRuleset):
                    font = QFont()
                    font.setItalic(True)
                    result = font
            elif role == Qt.ItemDataRole.ToolTipRole:
                tip = '<b></b>%s<b></b>' % i18n(
                    item.tooltip()) if item else ''
                result = tip
        return result

    @staticmethod
    def isCheckboxCell(index):
        """are we dealing with a checkbox?"""
        if index.column() != 1:
            return False
        item = index.internalPointer()
        return isinstance(item, RuleItem) and isinstance(item.raw, BoolRule)

    def headerData(self, section, orientation, role):
        """tell the view about the wanted headers"""
        if Qt is None:
            # happens when kajongg exits unexpectedly
            return None
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if section >= self.rootItem.columnCount():
                return None
            result = self.rootItem.content(section)
            if result == 'doubles':
                return 'x2'
            return i18nc('kajongg', result)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            leftRight = Qt.AlignmentFlag.AlignLeft if section == 0 else Qt.AlignmentFlag.AlignRight
            return int(leftRight | Qt.AlignmentFlag.AlignVCenter)
        return None

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
        ruleLists = [x for x in ruleset.ruleLists if len(x)]
        ruleListItems = [RuleListItem(x) for x in ruleLists]
        for item in ruleListItems:
            item.colCount = self.rootItem.columnCount()
        self.insertRows(0, ruleListItems, rulesetIndex)
        for ridx, ruleList in enumerate(ruleLists):
            listIndex = self.index(ridx, 0, rulesetIndex)
            ruleItems = [RuleItem(x) for x in ruleList if 'internal' not in x.options]
            self.insertRows(0, ruleItems, listIndex)


class EditableRuleModel(RuleModel):

    """add methods needed for editing"""

    def __init__(self, rulesets, title, parent=None):
        RuleModel.__init__(self, rulesets, title, parent)

    def __setRuleData(self, column, content, value):
        """change rule data in the model"""
        dirty, message = False, None
        if column == 1 and isinstance(content, ParameterRule):
            oldParameter = content.parameter
            if isinstance(content, BoolRule):
                return False, ''
            if content.parameter != value:
                dirty = True
                content.parameter = value
            message = content.validate()
            if message:
                content.parameter = oldParameter
                dirty = False
        else:
            unitName = self.rootItem.content(column)
            dirty, message = content.score.change(unitName, value)
        return dirty, message

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        """change data in the model"""
        # pylint:  disable=too-many-branches
        if not index.isValid():
            return False
        dirty = False
        column = index.column()
        item = index.internalPointer()
        ruleset = item.ruleset()
        content = item.raw
        if role == Qt.ItemDataRole.EditRole:
            if isinstance(content, Ruleset) and column == 0:
                oldName = content.name
                content.rename(english(value))
                dirty = oldName != content.name
            elif isinstance(content, RuleBase):
                dirty, message = self.__setRuleData(column, content, value)
                if message:
                    Sorry(message)
                    return False
            else:
                return False
        elif role == Qt.ItemDataRole.CheckStateRole:
            if isinstance(content, BoolRule) and column == 1:
                if not isinstance(ruleset, PredefinedRuleset):
                    newValue = value == Qt.CheckState.Checked
                    if content.parameter != newValue:
                        dirty = True
                        content.parameter = newValue
            else:
                return False
        if dirty:
            if isinstance(content, RuleBase):
                ruleset.updateRule(content)
            self.dataChanged.emit(index, index)
        return True

    def flags(self, index):
        """tell the view what it can do with this item"""
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled
        column = index.column()
        item = index.internalPointer()
        content = item.raw
        checkable = False
        if isinstance(content, Ruleset) and column == 0:
            mayEdit = True
        elif isinstance(content, RuleBase):
            checkable = column == 1 and isinstance(content, BoolRule)
            mayEdit = bool(column)
        else:
            mayEdit = False
        mayEdit = mayEdit and not isinstance(item.ruleset(), PredefinedRuleset)
        result = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if mayEdit:
            result |= Qt.ItemFlag.ItemIsEditable
        if checkable:
            result |= Qt.ItemFlag.ItemIsUserCheckable
        return result


class RuleTreeView(QTreeView):

    """Tree view for our rulesets"""

    def __init__(self, name, btnCopy=None,
                 btnRemove=None, btnCompare=None, parent=None):
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
        self.rulesets = []  # nasty: this generates self.ruleModel
        self.differs = []

    def dataChanged(self, unusedIndex1, unusedIndex2, unusedRoles=None):
        """get called if the model has changed: Update all differs"""
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
            self.setItemDelegateForColumn(
                1,
                RightAlignedCheckboxDelegate(
                    self,
                    self.ruleModel.isCheckboxCell))
            for  col in (2, 3):
                self.setItemDelegateForColumn(col, ZeroEmptyColumnDelegate(self))
            self.setModel(self.ruleModel)
            if Debug.modelTest:
                self.ruleModelTest = ModelTest(self.ruleModel, self)
            self.show()

    def selectionChanged(self, selected, unusedDeselected=None):
        """update editing buttons"""
        enableCopy = enableRemove = enableCompare = False
        if selected.indexes():
            item = selected.indexes()[0].internalPointer()
            isPredefined = isinstance(item.ruleset(), PredefinedRuleset)
            if isinstance(item, RulesetItem):
                enableCompare = True
                enableCopy = sum(
                    x.hash == item.ruleset(
                    ).hash for x in self.ruleModel.rulesets) == 1
                enableRemove = not isPredefined
        if self.btnCopy:
            self.btnCopy.setEnabled(enableCopy)
        if self.btnRemove:
            self.btnRemove.setEnabled(enableRemove)
        if self.btnCompare:
            self.btnCompare.setEnabled(enableCompare)

    def showEvent(self, unusedEvent):
        """reload the models when the view comes into sight"""
        # default: make sure the name column is wide enough
        if self.ruleModel.canFetchMore():
            # we want to load all before adjusting column width
            self.ruleModel.fetchMore()
        header = self.header()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(-1)
        for col in range(1, header.count()):
            header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(header.count()):
            self.resizeColumnToContents(col)

    def selectedRow(self):
        """return the currently selected row index (with column 0)"""
        rows = self.selectionModel().selectedRows()
        return rows[0] if len(rows) == 1 else None

    def copyRow(self):
        """copy a ruleset"""
        row = self.selectedRow()
        if row:
            item = row.internalPointer()
            assert isinstance(item, RulesetItem)
            ruleset = item.raw.copyTemplate()
            self.model().appendRuleset(ruleset)
            self.rulesets.append(ruleset)
            self.selectionChanged(self.selectionModel().selection())

    def removeRow(self):
        """removes a ruleset or a rule"""
        row = self.selectedRow()
        if row:
            item = row.internalPointer()
            assert not isinstance(item.ruleset(), PredefinedRuleset)
            assert isinstance(item, RulesetItem)
            ruleset = item.ruleset()
            self.model().removeRow(row.row(), parent=row.parent())
            self.rulesets.remove(ruleset)
            self.selectionChanged(self.selectionModel().selection())

    def compareRow(self):
        """shows the difference between two rulesets"""
        rows = self.selectionModel().selectedRows()
        ruleset = rows[0].internalPointer().raw
        assert isinstance(ruleset, Ruleset)
        differ = RulesetDiffer([ruleset], self.rulesets)
        differ.show()
        self.differs.append(differ)


class RulesetSelector(QWidget):

    """presents all available rulesets with previews"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.setupUi()

    def setupUi(self):
        """layout the window"""
        decorateWindow(self, i18nc("@title:window", "Customize rulesets"))
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
        self.rulesetView = RuleTreeView(
            i18ncE('kajongg',
                   'Rule'),
            self.btnCopy,
            self.btnRemove,
            self.btnCompare)
        v1layout.addWidget(self.rulesetView)
        self.rulesetView.setWordWrap(True)
        self.rulesetView.setMouseTracking(True)
        spacerItem = QSpacerItem(
            20,
            20,
            QSizePolicy.Minimum,
            QSizePolicy.Expanding)
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
        available = KApplication.desktopSize()
        height = max(result.height(), available.height() * 2 // 3)
        width = max(result.width(), available.width() // 2)
        return QSize(width, height)

    def minimumSizeHint(self):
        """we never want a horizontal scrollbar for player names,
        we always want to see them in full"""
        return self.sizeHint()

    def showEvent(self, unusedEvent):
        """reload the rulesets"""
        self.refresh()

    def refresh(self):
        """retranslate and reload rulesets"""
        self.retranslateUi()
        self.rulesetView.rulesets = Ruleset.availableRulesets()

    def hideEvent(self, event):
        """close all differ dialogs"""
        marked = []
        for differ in self.rulesetView.differs:
            differ.hide()
            marked += differ
        QWidget.hideEvent(self, event)
        for _ in marked:
            del _

    def retranslateUi(self):
        """translate to current language"""
        self.btnCopy.setText(i18n("C&opy"))
        self.btnCompare.setText(i18nc('Kajongg ruleset comparer', 'Co&mpare'))
        self.btnRemove.setText(i18n('&Remove'))
        self.btnClose.setText(i18n('&Close'))
