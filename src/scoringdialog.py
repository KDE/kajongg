# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

from typing import Optional, cast, Union, TYPE_CHECKING, List, Tuple, Generator, Any

from qt import Qt, QPointF, QSize, QModelIndex, QEvent, QTimer
from qt import QColor, QPushButton, QPixmapCache
from qt import QWidget, QLabel, QTabWidget
from qt import QGridLayout, QVBoxLayout, QHBoxLayout, QSpinBox
from qt import QDialog, QStringListModel, QListView, QSplitter, QValidator
from qt import QIcon, QPixmap, QPainter, QDialogButtonBox
from qt import QSizePolicy, QComboBox, QCheckBox, QScrollBar
from qt import QAbstractItemView, QHeaderView
from qt import QTreeView, QFont, QFrame
from qt import QStyledItemDelegate
from qt import QBrush, QPalette
from qt import PYQT6
from kde import KDialogButtonBox, KApplication

from modeltest import ModelTest

from rulesetselector import RuleTreeView
from board import WindLabel
from mi18n import i18n, i18nc
from common import Internal, Debug
from statesaver import StateSaver
from query import Query
from guiutil import ListComboBox, Painter, decorateWindow, BlockSignals
from tree import TreeItem, RootItem, TreeModel
from tile import Tile, MeldList
from point import Point

if TYPE_CHECKING:
    from qt import QObject, QRect, QStyleOptionViewItem, QPersistentModelIndex
    from tile import Meld
    from rule import Rule, Score
    from scene import ScoringScene
    from uitile import UITile
    from hand import Hand
    from scoring import ScoringGame, ScoringPlayer
    from player import Player

class ScoreTreeItem(TreeItem):

    """generic class for items in our score tree"""
    # pylint: disable=abstract-method
    # we know content() is abstract, this class is too

    def columnCount(self) ->int:
        """count the hands of the first player"""
        child1 = self
        while not isinstance(child1, ScorePlayerItem) and child1.children:
            child1 = cast('ScoreTreeItem', child1.children[0])
        if isinstance(child1, ScorePlayerItem):
            return len(child1.raw[1]) + 1
        return 1


class ScoreRootItem(RootItem):

    """the root item for the score tree"""

    def columnCount(self) ->int:
        child1 = self
        while not isinstance(child1, ScorePlayerItem) and child1.children:
            child1 = cast('ScoreRootItem', child1.children[0])
        if isinstance(child1, ScorePlayerItem):
            return len(child1.raw[1]) + 1
        return 1


class ScoreGroupItem(ScoreTreeItem):

    """represents a group in the tree like Points, Payments, Balance"""

    def __init__(self, content:str) ->None:
        ScoreTreeItem.__init__(self, content)

    def content(self, column:int) ->str:
        """return content stored in this item"""
        return i18n(self.raw)


class ScorePlayerItem(ScoreTreeItem):

    """represents a player in the tree"""

    def __init__(self, content:Tuple[str, List[Any]]) ->None:
        ScoreTreeItem.__init__(self, content)

    def content(self, column:int) ->Union[str, Any, None]:
        """return the content stored in this node"""
        if column == 0:
            return i18n(self.raw[0])
        try:
            return self.hands()[column - 1]
        except IndexError:
            # we have a penalty but no hand yet. Should
            # not happen in practical use
            return None

    def hands(self) ->List[Any]:
        """a small helper"""
        return self.raw[1]

    def chartPoints(self, column:int, steps:int) ->Generator[float, None, None]:
        """the returned points spread over a height of four rows"""
        int_points = [x.balance for x in self.hands()]
        int_points.insert(0, 0)
        int_points.insert(0, 0)
        int_points.append(int_points[-1])
        column -= 1
        int_points = int_points[column:column + 4]
        points = [float(x) for x in int_points]
        for idx in range(1, len(points) - 2):  # skip the ends
            for step in range(steps):
                point_1, point0, point1, point2 = points[idx - 1:idx + 3]
                fstep = float(step) / steps
                # wikipedia Catmull-Rom -> Cubic_Hermite_spline
                # 0 -> point0, 1 -> point1, 1/2 -> (- point_1 + 9 point0 + 9
                # point1 - point2) / 16
                yield (
                    fstep * ((2 - fstep) * fstep - 1) * point_1
                    + (fstep * fstep * (
                        3 * fstep - 5) + 2) * point0
                    + fstep *
                    ((4 - 3 * fstep) * fstep + 1) * point1
                    + (fstep - 1) * fstep * fstep * point2) / 2
        yield points[-2]


class ScoreItemDelegate(QStyledItemDelegate):

    """since setting delegates for a row does not work as wanted with a
    tree view, we set the same delegate on ALL items."""
    # try to use colors that look good with all color schemes. Bright
    # contrast colors are not optimal as long as our lines have a width of
    # only one pixel: antialiasing is not sufficient
    colors = [KApplication.palette().color(x)
              for x in [QPalette.ColorRole.Text, QPalette.ColorRole.Link, QPalette.ColorRole.LinkVisited]]
    colors.append(QColor('orange'))

    def __init__(self, parent:Optional['QObject']=None) ->None:
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter:Optional[QPainter], option:'QStyleOptionViewItem',
        index:Union[QModelIndex,'QPersistentModelIndex']) ->None:
        """where the real work is done..."""
        assert painter
        assert isinstance(index, QModelIndex), index
        item = index.internalPointer()
        if isinstance(item, ScorePlayerItem) and item.parent and item.parent.row() == 3 and index.column() != 0:
            parent_item = cast(TreeItem, index.parent().internalPointer())
            for idx, playerItem in enumerate(parent_item.children):
                assert isinstance(playerItem, ScorePlayerItem), playerItem
                rect = option.rect  # type:ignore[attr-defined]
                chart = cast('ScoreModel', index.model()).chart(rect, index, playerItem)
                if chart:
                    with Painter(painter):
                        painter.translate(rect.topLeft())
                        painter.setPen(self.colors[idx])
                        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                        # if we want to use a pen width > 1, we can no longer directly drawPolyline
                        # separately per cell beause the lines spread vertically over two rows: We would
                        # have to draw the lines into one big pixmap and copy
                        # from the into the cells
                        if PYQT6:
                            # seems the annotations are wrong: list(QPointF) does work
                            painter.drawPolyline(chart)  # type:ignore[call-overload]
                        else:
                            painter.drawPolyline(chart)
            return
        QStyledItemDelegate.paint(self, painter, option, index)


class ScoreModel(TreeModel):

    """a model for our score table"""
    steps = 30  # how fine do we want the stepping in the chart spline

    tupleType: Any = type(None)

    def __init__(self, scoreTable:'ScoreTable', parent:Optional['QObject']=None) ->None:
        super().__init__(parent)
        self.scoreTable = scoreTable
        self.rootItem = ScoreRootItem(None)
        self.minY = 9999999.9
        self.maxY = -9999999.9
        self.loadData()

    def chart(self, rect:'QRect', index:QModelIndex, playerItem:'ScorePlayerItem') ->List[QPointF]:
        """return list(QPointF) for a player in a specific tree cell"""
        chartHeight = float(rect.height()) * 4
        yScale = chartHeight / (self.minY - self.maxY)
        yOffset = rect.height() * index.row()
        _ = (playerItem.chartPoints(index.column(), self.steps))
        yValues = [(y - self.maxY) * yScale - yOffset for y in _]
        stepX = float(rect.width()) / self.steps
        xValues = [x * stepX for x in range(self.steps + 1)]
        return [QPointF(x, y) for x, y in zip(xValues, yValues)]

    def data(self, index:Union[QModelIndex,'QPersistentModelIndex'], role:int=Qt.ItemDataRole.DisplayRole) ->Any:  # pylint: disable=too-many-branches
        """score table"""
        # pylint: disable=too-many-return-statements
        assert isinstance(index, QModelIndex)
        if not index.isValid():
            return None
        column = index.column()
        item = cast(TreeItem, index.internalPointer())
        assert item.parent
        if role == Qt.ItemDataRole.DisplayRole:
            if isinstance(item, ScorePlayerItem):
                content = item.content(column)
                # if content.__class__.__name__ == 'Score':
                if isinstance(content, ScoreModel.tupleType):
                    parentRow = item.parent.row()
                    if parentRow == 0:
                        if not content.penalty:
                            content = f'{int(content.points)} {content.wind}'
                    elif parentRow == 1:
                        content = str(content.payments)
                    else:
                        content = str(content.balance)
                return content
            return '' if column > 0 else item.content(0)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter) \
                if index.column() == 0 else int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.FontRole:
            return QFont('Monospaced')
        if role == Qt.ItemDataRole.ForegroundRole:
            if isinstance(item, ScorePlayerItem) and item.parent.row() == 3:
                content = item.content(column)
                if not isinstance(content, ScoreModel.tupleType):
                    return QBrush(ScoreItemDelegate.colors[index.row()])
        if column > 0 and isinstance(item, ScorePlayerItem):
            content = item.content(column)  # type:ignore
            if role == Qt.ItemDataRole.BackgroundRole:
                assert isinstance(content, ScoreModel.tupleType)
                if content and content.won:
                    return QColor(165, 255, 165)
            if role == Qt.ItemDataRole.ToolTipRole:
                englishHints = content.manualrules.split('||')  # type:ignore
                tooltip = '<br />'.join(i18n(x) for x in englishHints)
                return tooltip
        return None

    def headerData(self, section:int, orientation:Qt.Orientation, role:int=Qt.ItemDataRole.DisplayRole) ->Any:
        """tell the view about the wanted headers"""
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if section == 0:
                return i18n('Round/Hand')
            assert self.rootItem
            child1 = self.rootItem.children[0]
            if child1 and child1.children:
                child1 = cast(ScorePlayerItem, child1.children[0])
                hands = child1.hands()
                handResult = hands[section - 1]
                if not handResult.penalty:
                    return self.handTitle(handResult)
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter) \
                if section == 0 else int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def loadData(self) ->None:
        """loads all data from the data base into a 2D matrix formatted like the wanted tree"""
        game = self.scoreTable.game
        assert game
        assert game.gameid

        fields = 'game,hand,player,rotated,notrotated,penalty,won,prevailing,wind,points,payments,balance,manualrules'
        tuples = Query('select {fields} from score where game=? order by hand', (game.gameid, ),
            fields=fields).tuples()
#        if not tuples:
#            return
        if tuples:
            ScoreModel.tupleType = tuples[0].__class__
        humans = sorted(
            (x for x in game.players if not x.name.startswith('Robot')))
        robots = sorted(
            (x for x in game.players if x.name.startswith('Robot')))
        data =  cast(List[Tuple[str, List[Any]]],
                    [tuple([player.localName, [x for x in tuples  # type:ignore
                    if x.player == player.nameid]]) for player in humans + robots])
#        print(f'players: {Players.allNames}')
#        for idx, _ in enumerate(data):
#            print(f'{idx}: {_}')
        self.__findMinMaxChartPoints(data)
        parent = QModelIndex()
        assert self.rootItem
        groupIndex = self.index(self.rootItem.childCount(), 0, parent)
        groupNames = [i18nc('kajongg', 'Score'), i18nc('kajongg', 'Payments'),
                      i18nc('kajongg', 'Balance'), i18nc('kajongg', 'Chart')]
        for idx, groupName in enumerate(groupNames):
            self.insertRows(idx, list([ScoreGroupItem(groupName)]), groupIndex)
            listIndex = self.index(idx, 0, groupIndex)
            for idx1, item in enumerate(data):
                self.insertRows(idx1, list([ScorePlayerItem(item)]), listIndex)

    def __findMinMaxChartPoints(self, data:List[Tuple[str, List[Any]]]) ->None:
        """find and save the extremes of the spline. They can be higher than
        the pure balance values"""
        self.minY = 9999999.9
        self.maxY = -9999999.9
        for item in data:
            playerItem = ScorePlayerItem(item)
            for col in range(len(playerItem.hands())):
                points = list(playerItem.chartPoints(col + 1, self.steps))
                self.minY = min(self.minY, min(points))  # pylint:disable=nested-min-max
                self.maxY = max(self.maxY, max(points))  # pylint:disable=nested-min-max
        self.minY -= 2  # antialiasing might cross the cell border
        self.maxY += 2

    def handTitle(self, handResult:Any) ->str:
        """identifies the hand for window title and scoring table"""
        return str(Point(handResult))


class ScoreViewLeft(QTreeView):

    """subclass for defining sizeHint"""

    def __init__(self, parent:Optional[QWidget]=None) ->None:
        QTreeView.__init__(self, parent)
        self.setItemDelegate(ScoreItemDelegate(self))

    def __col0Width(self) ->int:
        """the width we need for displaying column 0
        without scrollbar"""
        return self.columnWidth(0) + self.frameWidth() * 2

    def sizeHint(self) ->QSize:
        """we never want a horizontal scrollbar for player names,
        we always want to see them in full"""
        return QSize(self.__col0Width(), QTreeView.sizeHint(self).height())

    def minimumSizeHint(self) ->QSize:
        """we never want a horizontal scrollbar for player names,
        we always want to see them in full"""
        return self.sizeHint()


class ScoreViewRight(QTreeView):

    """we need to subclass for catching events"""

    def __init__(self, parent:Optional[QWidget]=None) ->None:
        QTreeView.__init__(self, parent)
        self.setItemDelegate(ScoreItemDelegate(self))

    def changeEvent(self, event:Optional[QEvent]) ->None:
        """recompute column width if font changes"""
        if event:
            if event.type() == QEvent.Type.FontChange:
                self.setColWidth()

    def setColWidth(self) ->None:
        """we want a fixed column width sufficient for all values"""
        if header := self.header():
            colRange = range(1, header.count())
            if colRange:
                for col in colRange:
                    self.resizeColumnToContents(col)
                width = max(self.columnWidth(x) for x in colRange)
                for col in colRange:
                    self.setColumnWidth(col, width)


class HorizontalScrollBar(QScrollBar):

    """We subclass here because we want to react on show/hide"""

    def __init__(self, scoreTable:'ScoreTable', parent:Optional[QWidget]=None) ->None:
        QScrollBar.__init__(self, parent)
        self.scoreTable = scoreTable

    def showEvent(self, unusedEvent:Optional[QEvent]) ->None:
        """adjust the left view"""
        self.scoreTable.adaptLeftViewHeight()

    def hideEvent(self, unusedEvent:Optional[QEvent]) ->None:
        """adjust the left view"""
        if header := self.scoreTable.viewRight.header():
            header.setOffset(0)  # we should not have to do this...
        # how to reproduce problem without setOffset:
        # show table with hor scroll, scroll to right, extend window
        # width very fast. The faster we do that, the wronger the
        # offset of the first column in the viewport.
        self.scoreTable.adaptLeftViewHeight()


class ScoreTable(QWidget):

    """show scores of current or last game, even if the last game is
    finished. To achieve this we keep our own reference to game."""

    def __init__(self, scene:'ScoringScene') ->None:
        super().__init__(None)
        self.setObjectName('ScoreTable')
        self.scene = scene
        self.scoreModel:Optional[ScoreModel] = None
        self.scoreModelTest:Optional[ModelTest] = None
        decorateWindow(self, i18nc('kajongg', 'Scores'))
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips)
        self.setMouseTracking(True)
        self.setupUi()
        self.refresh()
        StateSaver(self, self.splitter)

    @property
    def game(self) ->'ScoringGame':
        """a proxy"""
        return self.scene.game

    def setColWidth(self) ->None:
        """we want to accommodate for 5 digits plus minus sign
        and all column widths should be the same, making
        horizontal scrolling per item more pleasant"""
        self.viewRight.setColWidth()

    def setupUi(self) ->None:
        """setup UI elements"""
        self.viewLeft = ScoreViewLeft(self)
        self.viewRight = ScoreViewRight(self)
        self.viewRight.setHorizontalScrollBar(HorizontalScrollBar(self))
        self.viewRight.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerItem)
        self.viewRight.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        if header := self.viewRight.header():
            header.setSectionsClickable(False)
            header.setSectionsMovable(False)
        self.viewRight.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        windowLayout = QVBoxLayout(self)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setObjectName('ScoreTableSplitter')
        windowLayout.addWidget(self.splitter)
        scoreWidget = QWidget()
        self.scoreLayout = QHBoxLayout(scoreWidget)
        leftLayout = QVBoxLayout()
        leftLayout.addWidget(self.viewLeft)
        self.leftLayout = leftLayout
        self.scoreLayout.addLayout(leftLayout)
        self.scoreLayout.addWidget(self.viewRight)
        self.splitter.addWidget(scoreWidget)
        self.ruleTree = RuleTreeView(i18nc('kajongg', 'Used Rules'))
        self.splitter.addWidget(self.ruleTree)
        # this shows just one line for the ruleTree - so we just see the
        # name of the ruleset:
        self.splitter.setSizes(list([1000, 1]))

    def sizeHint(self) ->QSize:
        """give the scoring table window a sensible default size"""
        result = QWidget.sizeHint(self)
        result.setWidth(result.height() * 3 // 2)
        # the default is too small. Use at least 2/5 of screen height and 1/4
        # of screen width:
        available = KApplication.desktopSize()
        height = max(result.height(), available.height() * 2 // 5)
        width = max(result.width(), available.width() // 4)
        result.setHeight(height)
        result.setWidth(width)
        return result

    def refresh(self) ->None:
        """load this game and this player. Keep parameter list identical with
        ExplainView"""
        # pylint:disable=too-many-branches
        if not self.game:
            # keep scores of previous game on display
            return
        if self.scoreModel:
            expandGroups = [
                self.viewLeft.isExpanded(
                    self.scoreModel.index(x, 0, QModelIndex()))
                for x in range(4)]
        else:
            expandGroups = [True, False, True, True]
        gameid = str(self.game.seed or self.game.gameid)
        if self.game.finished():
            title = i18n('Final scores for game <numid>%1</numid>', gameid)
        else:
            title = i18n('Scores for game <numid>%1</numid>', gameid)
        decorateWindow(self, title)
        self.ruleTree.rulesets = list([self.game.ruleset])
        self.scoreModel = ScoreModel(self)
        if Debug.modelTest:
            self.scoreModelTest = ModelTest(self.scoreModel, self)
        for view in [self.viewLeft, self.viewRight]:
            view.setModel(self.scoreModel)
            if header := view.header():
                header.setStretchLastSection(False)
            view.setAlternatingRowColors(True)
        left_header = self.viewLeft.header()
        right_header = self.viewRight.header()
        if not left_header or not right_header:
            return
        right_header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        for col in range(left_header.count()):
            left_header.setSectionHidden(col, col > 0)
            right_header.setSectionHidden(col, col == 0)
        self.scoreLayout.setStretch(1, 100)
        self.scoreLayout.setSpacing(0)
        self.viewLeft.setFrameStyle(QFrame.Shape.NoFrame)
        self.viewRight.setFrameStyle(QFrame.Shape.NoFrame)
        self.viewLeft.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for master, slave in ((self.viewRight, self.viewLeft), (self.viewLeft, self.viewRight)):
            master.expanded.connect(slave.expand)
            master.collapsed.connect(slave.collapse)
            master_sb = master.verticalScrollBar()
            slave_sb = slave.verticalScrollBar()
            if master_sb and slave_sb:
                master_sb.valueChanged.connect(slave_sb.setValue)
        for row, expand in enumerate(expandGroups):
            self.viewLeft.setExpanded(
                self.scoreModel.index(row,
                                      0,
                                      QModelIndex()),
                expand)
        self.viewLeft.resizeColumnToContents(0)
        self.viewRight.setColWidth()
        # we need a timer since the scrollbar is not yet visible
        QTimer.singleShot(0, self.scrollRight)

    def scrollRight(self) ->None:
        """make sure the latest hand is visible"""
        if scrollBar := self.viewRight.horizontalScrollBar():
            scrollBar.setValue(scrollBar.maximum())

    def showEvent(self, unusedEvent:Optional[QEvent]) ->None:
        """Only now the views and scrollbars have useful sizes, so we can compute the spacer
        for the left view"""
        self.adaptLeftViewHeight()

    def adaptLeftViewHeight(self) ->None:
        """if the right view has a horizontal scrollbar, make sure both
        view have the same vertical scroll area. Otherwise scrolling to
        bottom results in unsyncronized views."""
        h_bar = self.viewRight.horizontalScrollBar()
        if h_bar and h_bar.isVisible():
            height = h_bar.height()
        else:
            height = 0
        if self.leftLayout.count() > 1:
            # remove previous spacer
            self.leftLayout.takeAt(1)
        if height:
            self.leftLayout.addSpacing(height)

    def closeEvent(self, unusedEvent:Optional[QEvent]) ->None:
        """update action button state"""
        assert Internal.mainWindow
        Internal.mainWindow.actionScoreTable.setChecked(False)


class ExplainView(QListView):

    """show a list explaining all score computations"""

    def __init__(self, scene:'ScoringScene') ->None:
        QListView.__init__(self)
        self.scene = scene
        decorateWindow(self, i18nc("@title:window", "Explain Scores").replace('&', ''))
        self.setGeometry(0, 0, 300, 400)
        self._model = QStringListModel()
        self.setModel(self._model)
        StateSaver(self)
        self.refresh()

    @property
    def game(self) ->'ScoringGame':
        """a proxy"""
        return self.scene.game

    def refresh(self) ->None:
        """refresh for new values"""
        lines = []
        if self.game is None:
            lines.append(i18n('There is no active game'))
        else:
            i18nName = i18n(self.game.ruleset.name)
            lines.append(i18n('%1', i18nName))
            lines.append('')
            for player in self.game.players:
                pLines = []
                explainHand = player.explainHand()
                if explainHand.hasTiles():
                    total = explainHand.total()
                    if total:
                        pLines = [f'{player.localName}: {total}']
                        for line in explainHand.explain():
                            pLines.append('- ' + line)
                elif player.handTotal:
                    pLines.append(
                        i18n(
                            'Manual score for %1: %2 points',
                            player.localName,
                            player.handTotal))
                if pLines:
                    pLines.append('')
                lines.extend(pLines)
        if 'xxx'.join(lines) != 'xxx'.join(str(x) for x in self._model.stringList()): # TODO: ohne?
            # QStringListModel does not optimize identical lists away, so we do
            self._model.setStringList(lines)

    def closeEvent(self, unusedEvent:Optional[QEvent]) ->None:
        """update action button state"""
        assert Internal.mainWindow
        Internal.mainWindow.actionExplain.setChecked(False)


class PenaltyBox(QSpinBox):

    """with its own validator, we only accept multiples of parties"""

    def __init__(self, parties:int, parent:Optional[QWidget]=None) ->None:
        QSpinBox.__init__(self, parent)
        self.parties = parties
        self.prevValue = 0

    def validate(self, inputData:str, pos:int) -> Tuple[QValidator.State, str, int]:  # type:ignore[override]
        """check if value is a multiple of parties"""
        _ = QSpinBox.validate(self, inputData, pos)
        result = _[0]
        inputData = _[1]
        newPos = _[2]
        if result == QValidator.State.Acceptable:
            try:
                int_data = int(inputData)
            except ValueError:
                return (QValidator.State.Invalid, inputData, pos)
            if int_data % self.parties != 0:
                result = QValidator.State.Intermediate
        if result == QValidator.State.Acceptable:
            self.prevValue = int(inputData)
        return (result, inputData, newPos)

    def fixup(self, data:str) ->str:  # type:ignore[override]
        """change input to a legal value"""
        # The Qt doc says return type is None but annotation says str
        value = int(str(data))
        prevValue = self.prevValue
        assert value != prevValue
        common = int(self.parties * 10)
        small = value // common
        if value > prevValue:
            newV = str(int((small + 1) * common))
        else:
            newV = str(int(small * common))
        return newV


class RuleBox(QCheckBox):

    """additional attribute: ruleId"""

    def __init__(self, rule:'Rule') ->None:
        QCheckBox.__init__(self, i18n(rule.name))
        self.rule = rule

    def setApplicable(self, applicable:bool) ->None:
        """update box"""
        self.setVisible(applicable)
        if not applicable:
            self.setChecked(False)

class PlayerSelection(ListComboBox):

    """just add a label"""

    def __init__(self, items:List[Any], parent:Optional['QWidget']=None) ->None:
        super().__init__(items, parent)
        self.label = QLabel()


class PenaltyDialog(QDialog):

    """enter penalties"""

    def __init__(self, game:'ScoringGame', parent:Optional[QWidget]=None) ->None:
        """selection for this player, tiles are the still available tiles"""
        QDialog.__init__(self, parent)
        decorateWindow(self, i18n("Penalty"))
        self.game = game
        grid = QGridLayout(self)
        lblOffense = QLabel(i18n('Offense:'))
        crimes = list(
            x for x in game.ruleset.penaltyRules if not ('absolute' in x.options and game.winner))
        self.cbCrime = ListComboBox(crimes)
        lblOffense.setBuddy(self.cbCrime)
        grid.addWidget(lblOffense, 0, 0)
        grid.addWidget(self.cbCrime, 0, 1, 1, 4)
        lblPenalty = QLabel(i18n('Total Penalty'))
        self.spPenalty = PenaltyBox(2)
        self.spPenalty.setRange(0, 9999)
        lblPenalty.setBuddy(self.spPenalty)
        self.lblUnits = QLabel(i18n('points'))
        grid.addWidget(lblPenalty, 1, 0)
        grid.addWidget(self.spPenalty, 1, 1)
        grid.addWidget(self.lblUnits, 1, 2)
        # a penalty can never involve the winner, neither as payer nor as payee, so max 3
        self.payers = list(PlayerSelection(game.losers()) for x in range(3))
        self.payees = list(PlayerSelection(game.losers()) for x in range(3))
        for idx, payer in enumerate(self.payers):
            grid.addWidget(payer, 3 + idx, 0)
            grid.addWidget(payer.label, 3 + idx, 1)
        for idx, payee in enumerate(self.payees):
            grid.addWidget(payee, 3 + idx, 3)
            grid.addWidget(payee.label, 3 + idx, 4)
        grid.addWidget(QLabel(''), 6, 0)
        grid.setRowStretch(6, 10)
        for player in self.payers + self.payees:
            player.currentIndexChanged.connect(self.playerChanged)
        self.spPenalty.valueChanged.connect(self.penaltyChanged)
        self.cbCrime.currentIndexChanged.connect(self.crimeChanged)
        buttonBox = KDialogButtonBox(self)
        grid.addWidget(buttonBox, 7, 0, 1, 5)
        buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel)
        buttonBox.rejected.connect(self.reject)
        self.btnExecute = buttonBox.addButton(
            i18n("&Execute"),
            QDialogButtonBox.ButtonRole.AcceptRole)
        assert self.btnExecute
        self.btnExecute.clicked.connect(self.accept)
        self.crimeChanged()
        StateSaver(self)

    def accept(self) ->None:
        """execute the penalty"""
        offense = self.cbCrime.current
        payers = [x.current for x in self.payers if x.isVisible()]
        payees = [x.current for x in self.payees if x.isVisible()]
        for player in self.game.players:
            if player in payers:
                amount = -self.spPenalty.value() // len(payers)
            elif player in payees:
                amount = self.spPenalty.value() // len(payees)
            else:
                amount = 0
            player.getsPayment(amount)
            self.game.savePenalty(player, offense, amount)
        QDialog.accept(self)

    def usedCombos(self, partyCombos:List[PlayerSelection]) ->List[PlayerSelection]:
        """return all used player combos for this offense"""
        return [x for x in partyCombos if x.isVisibleTo(self)]

    def allParties(self) ->List['Player']:
        """return all parties involved in penalty payment"""
        return [cast('Player', x.current) for x in self.usedCombos(self.payers + self.payees)]

    def playerChanged(self) ->None:
        """shuffle players to ensure everybody only appears once.
        enable execution if all input is valid"""
        changedCombo = self.sender()
        if not isinstance(changedCombo, PlayerSelection):
            changedCombo = self.payers[0]
        usedPlayers = set(self.allParties())
        unusedPlayers = set(self.game.losers()) - usedPlayers
        foundPlayers = [cast('Player', changedCombo.current)]
        for combo in self.usedCombos(self.payers + self.payees):
            if combo is not changedCombo:
                if combo.current in foundPlayers:
                    combo.current = unusedPlayers.pop()
                foundPlayers.append(combo.current)

    def crimeChanged(self) ->None:
        """another offense has been selected"""
        offense = self.cbCrime.current
        payers = int(offense.options.get('payers', 1))
        payees = int(offense.options.get('payees', 1))
        self.spPenalty.prevValue = -offense.score.points
        self.spPenalty.setValue(-offense.score.points)
        self.spPenalty.parties = max(payers, payees)
        self.spPenalty.setSingleStep(10)
        self.lblUnits.setText(i18n('points'))
        self.playerChanged()
        self.penaltyChanged()

    def penaltyChanged(self) ->None:
        """total has changed, update payments"""
        # normally value is only validated when leaving the field
        self.spPenalty.interpretText()
        offense = self.cbCrime.current
        penalty = self.spPenalty.value()
        payers = int(offense.options.get('payers', 1))
        payees = int(offense.options.get('payees', 1))
        payerAmount = -penalty // payers
        payeeAmount = penalty // payees
        for pList, amount, count in ((self.payers, payerAmount, payers), (self.payees, payeeAmount, payees)):
            for idx, player in enumerate(pList):
                player.setVisible(idx < count)
                player.label.setVisible(idx < count)
                if idx < count:
                    if pList == self.payers:
                        player.label.setText(
                            i18nc(
                                'penalty dialog, appears behind paying player combobox',
                                'pays %1 points', -amount))
                    else:
                        player.label.setText(
                            i18nc(
                                'penalty dialog, appears behind profiting player combobox',
                                'gets %1 points', amount))


class ScoringDialog(QWidget):

    """a dialog for entering the scores"""
    # pylint: disable=too-many-instance-attributes

    def __init__(self, scene:'ScoringScene', parent:Optional[QWidget]=None) ->None:
        QWidget.__init__(self, parent)
        self.scene = scene
        decorateWindow(self, i18nc("@title:window", "Scoring for this Hand"))
        self.nameLabels = list(QLabel() for x in range(4))
        self.spValues:List[QSpinBox] = list(QSpinBox() for x in range(4))
        self.windLabels = list(WindLabel() for x in range(4))
        self.wonBoxes = list(QCheckBox("") for x in range(4))
        self.detailsLayout = list(QVBoxLayout() for x in range(4))
        self.details = list(QWidget() for x in range(4))
        self.__meldPixMaps:List[QPixmap] = []
        grid = QGridLayout(self)
        pGrid = QGridLayout()
        grid.addLayout(pGrid, 0, 0, 2, 1)
        pGrid.addWidget(QLabel(i18nc('kajongg', "Player")), 0, 0)
        pGrid.addWidget(QLabel(i18nc('kajongg', "Wind")), 0, 1)
        pGrid.addWidget(QLabel(i18nc('kajongg', 'Score')), 0, 2)
        pGrid.addWidget(QLabel(i18n("Winner")), 0, 3)
        self.detailTabs = QTabWidget()
        self.detailTabs.setDocumentMode(True)
        pGrid.addWidget(self.detailTabs, 0, 4, 8, 1)
        for idx in range(4):
            self.setupUiForPlayer(pGrid, idx)
        self.draw = QCheckBox(i18nc('kajongg', 'Draw'))
        self.draw.clicked.connect(self.wonChanged)
        btnPenalties = QPushButton(i18n("&Penalties"))
        btnPenalties.clicked.connect(self.penalty)
        self.btnSave = QPushButton(i18n('&Save Hand'))
        self.btnSave.clicked.connect(self.game.nextScoringHand)
        self.btnSave.setEnabled(False)
        self.setupUILastTileMeld(pGrid)
        pGrid.setRowStretch(87, 10)
        pGrid.addWidget(self.draw, 7, 3)
        self.cbLastTile.currentIndexChanged.connect(self.slotLastTile)
        self.cbLastMeld.currentIndexChanged.connect(self.slotInputChanged)
        btnBox = QHBoxLayout()
        btnBox.addWidget(btnPenalties)
        btnBox.addWidget(self.btnSave)
        pGrid.addLayout(btnBox, 8, 4)
        StateSaver(self)
        self.refresh()

    @property
    def game(self) ->'ScoringGame':
        """proxy"""
        return self.scene.game

    def setupUILastTileMeld(self, pGrid:QGridLayout) ->None:
        """setup UI elements for last tile and last meld"""
        self.lblLastTile = QLabel(i18n('&Last Tile:'))
        self.cbLastTile = QComboBox()
        self.cbLastTile.setMinimumContentsLength(1)
        vpol = QSizePolicy()
        vpol.setHorizontalPolicy(QSizePolicy.Policy.Fixed)
        self.cbLastTile.setSizePolicy(vpol)
        self.cbLastTile.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.lblLastTile.setBuddy(self.cbLastTile)
        self.lblLastMeld = QLabel(i18n('L&ast Meld:'))
        self.prevLastTile:Optional['Tile'] = None
        self.cbLastMeld = QComboBox()
        self.cbLastMeld.setMinimumContentsLength(1)
        self.cbLastMeld.setSizePolicy(vpol)
        self.cbLastMeld.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.lblLastMeld.setBuddy(self.cbLastMeld)
        self.comboTilePairs:set['Tile'] = set()
        pGrid.setRowStretch(6, 5)
        pGrid.addWidget(self.lblLastTile, 7, 0, 1, 2)
        pGrid.addWidget(self.cbLastTile, 7, 2, 1, 1)
        pGrid.addWidget(self.lblLastMeld, 8, 0, 1, 2)
        pGrid.addWidget(self.cbLastMeld, 8, 2, 1, 2)

        self.lblLastTile.setVisible(False)
        self.cbLastTile.setVisible(False)
        self.cbLastMeld.setVisible(False)
        self.lblLastMeld.setVisible(False)

    def setupUiForPlayer(self, pGrid:QGridLayout, idx:int) ->None:
        """setup UI elements for a player"""
        self.spValues[idx] = QSpinBox()
        self.nameLabels[idx] = QLabel()
        self.nameLabels[idx].setBuddy(self.spValues[idx])
        self.windLabels[idx] = WindLabel()
        pGrid.addWidget(self.nameLabels[idx], idx + 2, 0)
        pGrid.addWidget(self.windLabels[idx], idx + 2, 1)
        pGrid.addWidget(self.spValues[idx], idx + 2, 2)
        pGrid.addWidget(self.wonBoxes[idx], idx + 2, 3)
        self.wonBoxes[idx].clicked.connect(self.wonChanged)
        self.spValues[idx].valueChanged.connect(self.slotInputChanged)
        detailTab = QWidget()
        self.detailTabs.addTab(detailTab, '')
        self.details[idx] = QWidget()
        detailTabLayout = QVBoxLayout(detailTab)
        detailTabLayout.addWidget(self.details[idx])
        detailTabLayout.addStretch()
        self.detailsLayout[idx] = QVBoxLayout(self.details[idx])

    def refresh(self) ->None:
        """reload game"""
        self.clear()
        game = self.game
        self.setVisible(game is not None and not game.finished())
        if game:
            for idx, player in enumerate(game.players):
                for child in self.details[idx].children():
                    if isinstance(child, RuleBox):
                        child.hide()
                        self.detailsLayout[idx].removeWidget(child)
                        del child
                if game:
                    self.spValues[idx].setRange(0, int(game.ruleset.limit) or 99999)
                    self.nameLabels[idx].setText(player.localName)
                    self.refreshWindLabels()
                    self.detailTabs.setTabText(idx, player.localName)
                    player.manualRuleBoxes = [RuleBox(x)
                                              for x in game.ruleset.allRules if x.hasSelectable]
                    for ruleBox in player.manualRuleBoxes:
                        self.detailsLayout[idx].addWidget(ruleBox)
                        ruleBox.clicked.connect(self.slotInputChanged)
                player.refreshManualRules()

    def show(self) ->None:
        """only now compute content"""
        if self.game and not self.game.finished():
            self.slotInputChanged()
            QWidget.show(self)

    def penalty(self) ->None:
        """penalty button clicked"""
        dlg = PenaltyDialog(self.game)
        dlg.exec()

    def slotLastTile(self) ->None:
        """called when the last tile changes"""
        newLastTile = self.computeLastTile()
        if not newLastTile:
            return
        if self.prevLastTile and self.prevLastTile.isExposed != newLastTile.isExposed:
            # state of last tile (concealed/exposed) changed:
            # for all checked boxes check if they still are applicable
            winner = cast('ScoringPlayer', self.game.winner)
            if winner:
                for box in winner.manualRuleBoxes:
                    if box.isChecked():
                        box.setChecked(False)
                        if winner.hand.manualRuleMayApply(box.rule):
                            box.setChecked(True)
        self.prevLastTile = newLastTile
        self.fillLastMeldCombo()
        self.slotInputChanged()

    def computeLastTile(self) ->Tile:
        """return the currently selected last tile"""
        idx = self.cbLastTile.currentIndex()
        if idx >= 0:
            return self.cbLastTile.itemData(idx)
        return Tile.none

    def clickedPlayerIdx(self, checkbox:'QObject') ->int:
        """the player whose box has been clicked"""
        for idx in range(4):
            if checkbox == self.wonBoxes[idx]:
                return idx
        assert False
        return 0

    def wonChanged(self) ->None:
        """if a new winner has been defined, uncheck any previous winner"""
        newWinner = None
        if sender := self.sender():
            if sender != self.draw:
                clicked = self.clickedPlayerIdx(sender)
                if self.wonBoxes[clicked].isChecked():
                    newWinner = self.game.players[clicked]
                else:
                    newWinner = None
        self.game.winner = newWinner
        for idx in range(4):
            if newWinner != self.game.players[idx]:
                self.wonBoxes[idx].setChecked(False)
        if newWinner:
            self.draw.setChecked(False)
            self.lblLastTile.setVisible(True)
            self.cbLastTile.setVisible(True)
        self.lblLastMeld.setVisible(False)
        self.cbLastMeld.setVisible(False)
        self.fillLastTileCombo()
        self.slotInputChanged()

    def updateManualRules(self) ->None:
        """enable/disable them"""
        # if an exclusive rule has been activated, deactivate it for
        # all other players
        ruleBox = self.sender()
        if isinstance(ruleBox, RuleBox) and ruleBox.isChecked() and ruleBox.rule.exclusive():
            for idx, player in enumerate(self.game.players):
                if ruleBox.parentWidget() != self.details[idx]:
                    for pBox in player.manualRuleBoxes:
                        if pBox.rule.name == ruleBox.rule.name:
                            pBox.setChecked(False)
        try:
            newState = bool(self.game.winner.handBoard.uiTiles) # type:ignore[union-attr]
        except AttributeError:
            newState = False
        self.lblLastTile.setVisible(newState)
        self.cbLastTile.setVisible(newState)
        if self.game:
            for player in self.game.players:
                player.refreshManualRules(self.sender())

    def clear(self) ->None:
        """prepare for next hand"""
        if self.game:
            for idx, player in enumerate(self.game.players):
                self.spValues[idx].clear()
                self.spValues[idx].setValue(0)
                self.wonBoxes[idx].setChecked(False)
                player.payment = 0
                player.invalidateHand()
        for box in self.wonBoxes:
            box.setVisible(False)
        self.draw.setChecked(False)
        self.updateManualRules()

        if self.game is None:
            self.hide()
        else:
            self.refreshWindLabels()
            self.computeScores()
            self.spValues[0].setFocus()
            self.spValues[0].selectAll()

    def refreshWindLabels(self) ->None:
        """update their wind and prevailing"""
        for idx, player in enumerate(self.game.players):
            self.windLabels[idx].wind = player.wind
            self.windLabels[idx].prevailing = self.game.point.prevailing

    def computeScores(self) ->None:
        """if tiles have been selected, compute their value"""
        # too many branches
        if not self.game:
            return
        if self.game.finished():
            self.hide()
            return
        for nameLabel, wonBox, spValue, player in zip(
                self.nameLabels, self.wonBoxes, self.spValues, self.game.players):
            with BlockSignals([spValue, wonBox]):
                # we do not want that change to call computeScores again
                if player.handBoard and player.handBoard.uiTiles:
                    spValue.setEnabled(False)
                    nameLabel.setBuddy(wonBox)
                    for _ in range(10):
                        prevTotal = player.handTotal
                        player.invalidateHand()
                        wonBox.setVisible(player.hand.won)
                        if not wonBox.isVisibleTo(self) and wonBox.isChecked():
                            wonBox.setChecked(False)
                            self.game.winner = None
                        elif prevTotal == player.handTotal:
                            break
                        player.refreshManualRules()
                    spValue.setValue(player.handTotal)
                else:
                    if not spValue.isEnabled():
                        spValue.clear()
                        spValue.setValue(0)
                        spValue.setEnabled(True)
                        nameLabel.setBuddy(spValue)
                    wonBox.setVisible(
                        player.handTotal >= self.game.ruleset.minMJTotal())
                    if not wonBox.isVisibleTo(self) and wonBox.isChecked():
                        wonBox.setChecked(False)
                if not wonBox.isVisibleTo(self) and player is self.game.winner:
                    self.game.winner = None
        assert Internal.scene
        if Internal.scene.explainView:
            Internal.scene.explainView.refresh()

    def __lastMeldContent(self) ->Tuple[set[Tile], List['UITile']]:
        """prepare content for lastmeld combo"""
        lastTiles = set()
        winnerTiles = []
        if self.game.winner and self.game.winner.handBoard:
            winnerTiles = self.game.winner.handBoard.uiTiles
            pairs = []
            for meld in self.game.winner.hand.melds:
                if len(meld) < 4:
                    pairs.extend(meld)
            for tile in winnerTiles:
                if tile.tile in pairs and not tile.isBonus:
                    lastTiles.add(tile.tile)
        return lastTiles, winnerTiles

    def __fillLastTileComboWith(self, lastTiles:set[Tile], winnerTiles:List['UITile']) ->None:
        """fill last meld combo with prepared content"""
        self.comboTilePairs = lastTiles
        idx = max(self.cbLastTile.currentIndex(), 0)
        indexedTile = self.cbLastTile.itemData(idx)
        restoredIdx = None
        self.cbLastTile.clear()
        if not winnerTiles:
            return
        assert winnerTiles[0].board
        # the following is OK with pyside6 annotations. PyQt6 cannot find a matching overload, which seems wrong
        pmSize = (winnerTiles[0].board.tileset.faceSize * 0.5).toSize()  # type:ignore[operator]
        self.cbLastTile.setIconSize(pmSize)
        QPixmapCache.clear()
        shownTiles = set()
        for tile in winnerTiles:
            if tile.tile in lastTiles and tile.tile not in shownTiles:
                shownTiles.add(tile.tile)
                self.cbLastTile.addItem(
                    QIcon(tile.pixmapFromSvg(pmSize, withBorders=False)),
                    '', tile.tile)
                if indexedTile is tile.tile:
                    restoredIdx = self.cbLastTile.count() - 1
        if not restoredIdx and indexedTile:
            # try again, maybe the tile changed between concealed and exposed
            indexedTile = indexedTile.exposed
            for idx in range(self.cbLastTile.count()):
                if indexedTile is self.cbLastTile.itemData(idx).exposed:
                    restoredIdx = idx
                    break
        if not restoredIdx:
            restoredIdx = 0
        self.cbLastTile.setCurrentIndex(restoredIdx)
        self.prevLastTile = self.computeLastTile()

    def clearLastTileCombo(self) ->None:
        """as the name says"""
        self.comboTilePairs = set()
        self.cbLastTile.clear()

    def fillLastTileCombo(self) ->None:
        """fill the drop down list with all possible tiles.
        If the drop down had content before try to preserve the
        current index. Even if the tile changed state meanwhile."""
        if self.game is None:
            return
        lastTiles, winnerTiles = self.__lastMeldContent()
        if self.comboTilePairs == lastTiles:
            return
        with BlockSignals([self.cbLastTile]):
            # we only want to emit the changed signal once
            self.__fillLastTileComboWith(lastTiles, winnerTiles)
        self.cbLastTile.currentIndexChanged.emit(0)

    def __fillLastMeldComboWith(self, winnerMelds:MeldList, indexedMeld:'Meld', lastTile:Optional[Tile]) ->None:
        """fill last meld combo with prepared content"""
        winner = self.game.winner
        assert winner
        assert winner.handBoard
        faceWidth = int(winner.handBoard.tileset.faceSize.width() * 0.5)
        faceHeight = int(winner.handBoard.tileset.faceSize.height() * 0.5)
        restoredIdx = None
        for meld in winnerMelds:
            pixMap = QPixmap(faceWidth * len(meld), faceHeight)
            pixMap.fill(Qt.GlobalColor.transparent)
            self.__meldPixMaps.append(pixMap)
            painter = QPainter(pixMap)
            for element in meld:
                painter.drawPixmap(0, 0,
                                   winner.handBoard.tilesByElement(element)
                                   [0].pixmapFromSvg(QSize(faceWidth, faceHeight), withBorders=False))
                painter.translate(QPointF(faceWidth, 0.0))
            self.cbLastMeld.addItem(QIcon(pixMap), '', meld)
            if indexedMeld == meld:
                restoredIdx = self.cbLastMeld.count() - 1
        if not restoredIdx and indexedMeld:
            # try again, maybe the meld changed between concealed and exposed
            indexedMeld = indexedMeld.exposed
            for idx in range(self.cbLastMeld.count()):
                meldContent = self.cbLastMeld.itemData(idx)
                if indexedMeld == meldContent.exposed:
                    restoredIdx = idx
                    if lastTile is not None and lastTile not in meldContent:
                        lastTile = lastTile.swapped
                        assert lastTile in meldContent
                        with BlockSignals([self.cbLastTile]):  # we want to continue right here
                            idx = self.cbLastTile.findData(lastTile)
                            self.cbLastTile.setCurrentIndex(idx)
                    break
        if not restoredIdx:
            restoredIdx = 0
        self.cbLastMeld.setCurrentIndex(restoredIdx)
        self.cbLastMeld.setIconSize(QSize(faceWidth * 3, faceHeight))

    def fillLastMeldCombo(self) ->None:
        """fill the drop down list with all possible melds.
        If the drop down had content before try to preserve the
        current index. Even if the meld changed state meanwhile."""
        with BlockSignals([self.cbLastMeld]):  # we only want to emit the changed signal once
            showCombo = False
            idx = max(self.cbLastMeld.currentIndex(), 0)
            indexedMeld = self.cbLastMeld.itemData(idx)
            self.cbLastMeld.clear()
            self.__meldPixMaps = []
            if not self.game.winner:
                return
            if self.cbLastTile.count() == 0:
                return
            assert Internal.scene
            lastTile = cast('ScoringScene', Internal.scene).computeLastTile()
            winnerMelds = MeldList(m for m in self.game.winner.hand.melds if len(m) < 4
                           and lastTile in m)
            assert winnerMelds, f'lastTile {lastTile} missing in {self.game.winner.hand.melds}'
            if len(winnerMelds) == 1:
                self.cbLastMeld.addItem(QIcon(), '', winnerMelds[0])
                self.cbLastMeld.setCurrentIndex(0)
                self.lblLastMeld.setVisible(False)
                self.cbLastMeld.setVisible(False)
                return
            showCombo = True
            self.__fillLastMeldComboWith(winnerMelds, indexedMeld, lastTile)
            self.lblLastMeld.setVisible(showCombo)
            self.cbLastMeld.setVisible(showCombo)
        self.cbLastMeld.currentIndexChanged.emit(0)

    def slotInputChanged(self) ->None:
        """some input fields changed: update"""
        for player in self.game.players:
            player.invalidateHand()
        self.updateManualRules()
        self.computeScores()
        self.validate()
        for player in self.game.players:
            player.showInfo()
        assert Internal.mainWindow
        Internal.mainWindow.updateGUI()

    def validate(self) ->None:
        """update the status of the OK button"""
        game = self.game
        if game:
            valid = True
            if game.winner and game.winner.handTotal < game.ruleset.minMJTotal():
                valid = False
            elif not game.winner and not self.draw.isChecked():
                valid = False
            self.btnSave.setEnabled(valid)
