# -*- coding: utf-8 -*-
"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

partially based on C++ code from:
Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

SPDX-License-Identifier: GPL-2.0

"""

from typing import TYPE_CHECKING, Tuple, List, Optional, Any, Union, Iterable, cast

from qt import Qt, QSize
from qt import QWidget, QHBoxLayout, QVBoxLayout, \
    QPushButton, QSpacerItem, QSizePolicy, \
    QTreeView, QFont, QAbstractItemView, QHeaderView
from qt import QModelIndex, QPersistentModelIndex
from kdestub import KApplication
from rule import Rule, Ruleset, PredefinedRuleset, ParameterRule, BoolRule
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

if TYPE_CHECKING:
    from qt import QShowEvent, QHideEvent, QItemSelection, QObject, QLayout
    from rule import RuleList


class RuleRootItem(RootItem):

    """the root item for the ruleset tree"""

    def columnCount(self) ->int:
        return len(self.raw)


class RuleTreeItem(TreeItem):

    """generic class for items in our rule tree"""
    # pylint: disable=abstract-method
    # we know content() is abstract, this class is too

    def columnCount(self) ->int:
        """can be different for every rule"""
        if hasattr(self, 'colCount'):
            return self.colCount
        return len(self.raw)

    def ruleset(self) ->Ruleset:
        """return the ruleset containing this item"""
        item:TreeItem = self
        while not isinstance(item.raw, Ruleset):
            assert item.parent
            item = item.parent
        return item.raw


class RulesetItem(RuleTreeItem):

    """represents a ruleset in the tree"""

    def __init__(self, content:Ruleset) ->None:
        RuleTreeItem.__init__(self, content)

    @property
    def raw(self) ->Ruleset:
        return cast(Ruleset, super().raw)

    def content(self, column:int) ->str:
        """return content stored in this item"""
        if column == 0:
            return self.raw.name
        return ''

    def columnCount(self) ->int:
        return 1

    def remove(self) ->None:
        """remove this ruleset from the model and the database"""
        self.raw.remove()

    def tooltip(self) ->str:
        """the tooltip for a ruleset"""
        return self.raw.description


class RuleListItem(RuleTreeItem):

    """represents a list of rules in the tree"""

    def __init__(self, content:List[ParameterRule]) ->None:
        RuleTreeItem.__init__(self, content)

    @property
    def raw(self) ->'RuleList':
        return cast('RuleList', super().raw)

    def content(self, column:int) ->str:
        """return content stored in this item"""
        if column == 0:
            return self.raw.name
        return ''

    def tooltip(self) ->str:
        """tooltip for a list item explaining the usage of this list"""
        ruleset = self.ruleset()
        return '<b>' + i18n(ruleset.name) + '</b><br><br>' + \
            i18n(self.raw.description)


class RuleItem(RuleTreeItem):

    """represents a rule in the tree"""

    def __init__(self, content:ParameterRule) ->None:
        RuleTreeItem.__init__(self, content)

    @property
    def raw(self) ->Rule:
        return cast(Rule, super().raw)

    def content(self, column:int) ->str:
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

    def tooltip(self) ->str:
        """tooltip for rule: just the name of the ruleset"""
        ruleset = self.ruleset()
        if self.raw.description:
            return '<b>' + i18n(ruleset.name) + '</b><br><br>' + \
                i18n(self.raw.description)
        return i18n(ruleset.name)


class RuleModel(TreeModel):

    """a model for our rule table"""

    def __init__(self, rulesets:List[Ruleset], title:str, parent:Optional['QObject']=None) ->None:
        super().__init__(parent)
        self.rulesets = rulesets
        self.loaded = False
        unitPairs:List[Tuple[str, int]] = []
        # unitPairs: int is the priority:show 0 leftmost, 9999 rightmost
        for ruleset in rulesets:
            ruleset.load()
            for rule in ruleset.allRules:
                unitPairs.extend(rule.score.unitNames.items())
        unitPairs = sorted(unitPairs, key=lambda x: x[1])
        unitNames = uniqueList(x[0] for x in unitPairs)
        rootData = [title]
        rootData.extend(unitNames)
        self.rootItem = RuleRootItem(rootData)

    def canFetchMore(self, unusedParent:Union[QModelIndex,QPersistentModelIndex]=QModelIndex()) ->bool:
        """did we already load the rules? We only want to do that
        when the config tab with rulesets is actually shown"""
        return not self.loaded

    def fetchMore(self, unusedParent:Union[QModelIndex,QPersistentModelIndex]=QModelIndex()) ->None:
        """load the rules"""
        for ruleset in self.rulesets:
            self.appendRuleset(ruleset)
        self.loaded = True

    def data(self, index:Union[QModelIndex,QPersistentModelIndex], role:int=Qt.ItemDataRole.DisplayRole) ->Any:
        """get data fom model"""
        # pylint: disable=too-many-branches
        # too many branches
        result = None
        if index.isValid() and isinstance(index, QModelIndex):
            item = cast(RuleTreeItem, index.internalPointer())
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
                assert isinstance(item, RulesetItem)
                tip = f'<b></b>{i18n(item.tooltip())}<b></b>' if item else ''
                result = tip
        return result

    @staticmethod
    def isCheckboxCell(index:QModelIndex) ->bool:
        """are we dealing with a checkbox?"""
        if index.column() != 1:
            return False
        item = index.internalPointer()
        return isinstance(item, RuleItem) and isinstance(item.raw, BoolRule)

    def headerData(self, section:int, orientation:Qt.Orientation, role:int=Qt.ItemDataRole.DisplayRole) ->Optional[Any]:
        """tell the view about the wanted headers"""
        if Qt is None:
            # happens when kajongg exits unexpectedly
            return None
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            assert self.rootItem
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

    def appendRuleset(self, ruleset:Ruleset) ->None:
        """append ruleset to the model"""
        if not ruleset:
            return
        ruleset.load()
        parent = QModelIndex()
        assert self.rootItem
        row = self.rootItem.childCount()
        rulesetItems = list([RulesetItem(ruleset)])
        self.insertRows(row, rulesetItems, parent)
        rulesetIndex = self.index(row, 0, parent)
        ruleLists:List[List[ParameterRule]] = [x for x in ruleset.ruleLists if len(x)]
        ruleListItems:List[RuleListItem] = [RuleListItem(x) for x in ruleLists]
        for item in ruleListItems:
            item.colCount = self.rootItem.columnCount()  # type:ignore
        self.insertRows(0, ruleListItems, rulesetIndex)
        for ridx, ruleList in enumerate(ruleLists):
            listIndex = self.index(ridx, 0, rulesetIndex)
            ruleItems = [RuleItem(x) for x in ruleList if 'internal' not in x.options]
            self.insertRows(0, ruleItems, listIndex)


class EditableRuleModel(RuleModel):

    """add methods needed for editing"""

    def __init__(self, rulesets:List[Ruleset], title:str, parent:Optional['QObject']=None) ->None:
        RuleModel.__init__(self, rulesets, title, parent)

    def __setRuleData(self, column:int, content:Union[Rule, ParameterRule],
        value:Union[str, int, bool]) ->Tuple[bool, Optional[str]]:
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
            assert self.rootItem
            unitName = self.rootItem.content(column)
            assert isinstance(value, (int, float))
            dirty, message = content.score.change(unitName, value)
        return dirty, message

    def setData(self, index:Union[QModelIndex,QPersistentModelIndex], value:str,
        role:int=Qt.ItemDataRole.EditRole) ->bool:
        """change data in the model"""
        # pylint:  disable=too-many-branches
        if not index.isValid() or not isinstance(index, QModelIndex):
            return False
        dirty = False
        column = index.column()
        item = cast(RuleTreeItem, index.internalPointer())
        ruleset = item.ruleset()
        content = item.raw
        if role == Qt.ItemDataRole.EditRole:
            if isinstance(content, Ruleset) and column == 0:
                oldName = content.name
                content.rename(english(value))
                dirty = oldName != content.name
            elif isinstance(content, (Rule, ParameterRule)):
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
            if isinstance(content, (Rule, ParameterRule)):
                ruleset.updateRule(content)
            self.dataChanged.emit(index, index)
        return True

    def flags(self, index:QModelIndex) ->Qt.ItemFlag:  # type:ignore[override]
        """tell the view what it can do with this item"""
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled
        column = index.column()
        item = cast(RuleTreeItem, index.internalPointer())
        content = item.raw
        checkable = False
        if isinstance(content, Ruleset) and column == 0:
            mayEdit = True
        elif isinstance(content, (Rule, ParameterRule)):
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
        return cast(Qt.ItemFlag, result)


class RuleTreeView(QTreeView):

    """Tree view for our rulesets"""

    def __init__(self, name:str,
                 btnCopy:Optional[QPushButton]=None,
                 btnRemove:Optional[QPushButton]=None,
                 btnCompare:Optional[QPushButton]=None, parent:Optional[QWidget]=None) ->None:
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
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.ruleModel:Optional[RuleModel] = None
        self.ruleModelTest = None
        self.rulesets:List[Ruleset] = []  # nasty: this generates self.ruleModel
        self.differs:List[RulesetDiffer] = []

    def dataChanged(self, unusedIndex1:Union[QModelIndex,QPersistentModelIndex],
        unusedIndex2:Union[QModelIndex,QPersistentModelIndex],
        unusedRoles:Optional[Iterable[int]]=None) ->None:
        """get called if the model has changed: Update all differs"""
        for differ in self.differs:
            differ.rulesetChanged()

    @property
    def rulesets(self) ->List[Ruleset]:
        """a list of rulesets made available by this model"""
        assert self.ruleModel
        return self.ruleModel.rulesets

    @rulesets.setter
    def rulesets(self, rulesets:List[Ruleset]) ->None:
        """a new list: update display"""
        if not self.ruleModel or self.ruleModel.rulesets != rulesets:
            if self.btnRemove and self.btnCopy:
                self.ruleModel = EditableRuleModel(rulesets, self.name)
            else:
                self.ruleModel = RuleModel(rulesets, self.name)
            delegate = RightAlignedCheckboxDelegate(self, self.ruleModel.isCheckboxCell)
            self.setItemDelegateForColumn(1, delegate)
            for  col in (2, 3):
                self.setItemDelegateForColumn(col, ZeroEmptyColumnDelegate(self))
            self.setModel(self.ruleModel)
            if Debug.modelTest:
                self.ruleModelTest = ModelTest(self.ruleModel, self)
            self.show()

    def selectionChanged(self, selected:'QItemSelection', unused_deselected:Optional['QItemSelection']=None) ->None:
        """update editing buttons"""
        assert self.ruleModel
        enableCopy = enableRemove = enableCompare = False
        if selected.indexes():
            item = cast(RuleTreeItem, selected.indexes()[0].internalPointer())
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

    def showEvent(self, unusedEvent:Optional['QShowEvent']) ->None:
        """reload the models when the view comes into sight"""
        # default: make sure the name column is wide enough
        assert self.ruleModel
        if self.ruleModel.canFetchMore():
            # we want to load all before adjusting column width
            self.ruleModel.fetchMore()
        header = self.header()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(-1)
        for col in range(1, header.count()):
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(header.count()):
            self.resizeColumnToContents(col)

    def selectedRow(self) ->Optional[QModelIndex]:
        """return the currently selected row index (with column 0)"""
        rows = self.selectionModel().selectedRows()
        return rows[0] if len(rows) == 1 else None

    def copyRow(self) ->None:
        """copy a ruleset"""
        row = self.selectedRow()
        if row:
            item = row.internalPointer()
            assert isinstance(item, RulesetItem)
            ruleset = item.raw.copyTemplate()
            cast(RuleModel, self.model()).appendRuleset(ruleset)
            self.rulesets.append(ruleset)
            self.selectionChanged(self.selectionModel().selection())

    def removeRow(self) ->None:
        """removes a ruleset or a rule"""
        row = self.selectedRow()
        if row:
            item = cast(RuleTreeItem, row.internalPointer())
            assert not isinstance(item.ruleset(), PredefinedRuleset)
            assert isinstance(item, RulesetItem)
            ruleset = item.ruleset()
            self.model().removeRow(row.row(), parent=row.parent())
            self.rulesets.remove(ruleset)
            self.selectionChanged(self.selectionModel().selection())

    def compareRow(self) ->None:
        """shows the difference between two rulesets"""
        rows = self.selectionModel().selectedRows()
        ruleset = cast(RuleTreeItem, rows[0].internalPointer()).raw
        assert isinstance(ruleset, Ruleset)
        differ = RulesetDiffer([ruleset], self.rulesets)
        differ.show()
        self.differs.append(differ)


class RulesetSelector(QWidget):

    """presents all available rulesets with previews"""

    def __init__(self, parent:Optional[QWidget]=None):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.setupUi()

    def setupUi(self) ->None:
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
        widgets:List[Union[QWidget, 'QLayout']] = [self.v1widget, hlayout, v1layout, v2layout]
        for widget in widgets:
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
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Expanding)
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

    def sizeHint(self) ->QSize:
        """we never want a horizontal scrollbar for player names,
        we always want to see them in full"""
        result = QWidget.sizeHint(self)
        available = KApplication.desktopSize()
        height = max(result.height(), available.height() * 2 // 3)
        width = max(result.width(), available.width() // 2)
        return QSize(width, height)

    def minimumSizeHint(self) ->QSize:
        """we never want a horizontal scrollbar for player names,
        we always want to see them in full"""
        return self.sizeHint()

    def showEvent(self, unusedEvent:Optional['QShowEvent']) ->None:
        """reload the rulesets"""
        self.refresh()

    def refresh(self) ->None:
        """retranslate and reload rulesets"""
        self.retranslateUi()
        self.rulesetView.rulesets = Ruleset.availableRulesets()

    def hideEvent(self, event:Optional['QHideEvent']) ->None:
        """close all differ dialogs"""
        marked:List[RulesetDiffer] = []
        differs = self.rulesetView.differs
        for differ in differs:
            differ.hide()
            marked.append(differ)
        if event:
            QWidget.hideEvent(self, event)
        for _ in marked:
            del differs[_]

    def retranslateUi(self) ->None:
        """translate to current language"""
        self.btnCopy.setText(i18n("C&opy"))
        self.btnCompare.setText(i18nc('Kajongg ruleset comparer', 'Co&mpare'))
        self.btnRemove.setText(i18n('&Remove'))
        self.btnClose.setText(i18n('&Close'))
