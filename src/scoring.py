# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

kajongg is free software you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
"""

from PyQt4.QtCore import Qt, QPointF, QVariant, SLOT, pyqtSignal, \
    QSize, QModelIndex, QEvent, QTimer

from PyQt4.QtGui import QColor, QPushButton, QPixmapCache
from PyQt4.QtGui import QWidget, QLabel, QTabWidget
from PyQt4.QtGui import QGridLayout, QVBoxLayout, QHBoxLayout, QSpinBox
from PyQt4.QtGui import QDialog, QStringListModel, QListView, QSplitter, QValidator
from PyQt4.QtGui import QIcon, QPixmap, QPainter, QDialogButtonBox
from PyQt4.QtGui import QSizePolicy, QComboBox, QCheckBox, QScrollBar
from PyQt4.QtGui import QAbstractItemView, QHeaderView
from PyQt4.QtGui import QTreeView, QFont, QFrame
from PyQt4.QtGui import QStyledItemDelegate
from PyQt4.QtGui import QBrush, QPalette
from kde import KDialogButtonBox, KApplication

from modeltest import ModelTest

from rulesetselector import RuleTreeView
from board import WindLabel, WINDPIXMAPS
from util import m18n, m18nc
from common import WINDS, Internal, Debug
from statesaver import StateSaver
from query import Query
from guiutil import ListComboBox
from tree import TreeItem, RootItem, TreeModel

class ScoreTreeItem(TreeItem):
    """generic class for items in our score tree"""
    # pylint: disable=W0223
    # we know content() is abstract, this class is too

    def columnCount(self):
        """count the hands of the first player"""
        child1 = self
        while not isinstance(child1, ScorePlayerItem) and child1.children:
            child1 = child1.children[0]
        if isinstance(child1, ScorePlayerItem):
            return len(child1.rawContent[1]) + 1
        return 1

class ScoreRootItem(RootItem):
    """the root item for the score tree"""

    def columnCount(self):
        child1 = self
        while not isinstance(child1, ScorePlayerItem) and child1.children:
            child1 = child1.children[0]
        if isinstance(child1, ScorePlayerItem):
            return len(child1.rawContent[1]) + 1
        return 1

class ScoreGroupItem(ScoreTreeItem):
    """represents a group in the tree like Points, Payments, Balance"""
    def __init__(self, content):
        ScoreTreeItem.__init__(self, content)

    def content(self, column):
        """return content stored in this item"""
        return m18n(self.rawContent)

class ScorePlayerItem(ScoreTreeItem):
    """represents a player in the tree"""
    def __init__(self, content):
        ScoreTreeItem.__init__(self, content)

    def content(self, column):
        """return the content stored in this node"""
        if column == 0:
            return m18n(self.rawContent[0])
        else:
            return self.hands()[column-1]

    def hands(self):
        """a small helper"""
        return self.rawContent[1]

    def chartPoints(self, column, steps):
        """the returned points spread over a height of four rows"""
        points = [x.balance for x in self.hands()]
        points.insert(0, 0)
        points.insert(0, 0)
        points.append(points[-1])
        column -= 1
        points = points[column:column+4]
        points = [float(x) for x in points]
        for idx in range( 1, len(points)-2 ):  # skip the ends
            for step in range(steps ):
                point_1, point0, point1, point2 = points[idx-1:idx+3]
                fstep = float(step) / steps
                # wikipedia Catmull-Rom -> Cubic_Hermite_spline
                # 0 -> point0, 1 -> point1, 1/2 -> (- point_1 + 9 point0 + 9 point1 - point2) / 16
                yield (
                          fstep*((2-fstep)*fstep - 1) * point_1
                                + (fstep*fstep*(3*fstep - 5) + 2) * point0
                                + fstep*((4 - 3*fstep)*fstep + 1) * point1
                                + (fstep-1)*fstep*fstep * point2 ) / 2
        yield points[-2]


class ScoreItemDelegate(QStyledItemDelegate):
    """since setting delegates for a row does not work as wanted with a
    tree view, we set the same delegate on ALL items."""
    # try to use colors that look good with all color schemes. Bright
    # contrast colors are not optimal as long as our lines have a width of
    # only one pixel: antialiasing is not sufficient
    colors = [KApplication.palette().color(x) for x in [QPalette.Text, QPalette.Link, QPalette.LinkVisited]]
    colors.append(QColor('orange'))

    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        """where the real work is done..."""
        item = index.internalPointer()
        if isinstance(item, ScorePlayerItem) and item.parent.row() == 3 and index.column() != 0:
            for idx, playerItem in enumerate(index.parent().internalPointer().children):
                chart = index.model().chart(option.rect, index, playerItem)
                if chart:
                    painter.save()
                    painter.translate(option.rect.topLeft())
                    painter.setPen(self.colors[idx])
                    painter.setRenderHint(QPainter.Antialiasing)
                    # if we want to use a pen width > 1, we can no longer directly drawPolyline
                    # separately per cell beause the lines spread vertically over two rows: We would
                    # have to draw the lines into one big pixmap and copy from the into the cells
                    painter.drawPolyline(*chart) # pylint: disable=W0142
                    painter.restore()
            return
        return QStyledItemDelegate.paint(self, painter, option, index)

class ScoreModel(TreeModel):
    """a model for our score table"""
    steps = 30 # how fine do we want the stepping in the chart spline
    def __init__(self, parent = None):
        super(ScoreModel, self).__init__(parent)
        self.scoreTable = parent
        self.rootItem = ScoreRootItem(None)
        self.minY = self.maxY = None
        self.loadData()

    def chart(self, rect, index, playerItem):
        """returns list(QPointF) for a player in a specific tree cell"""
        chartHeight = float(rect.height()) * 4
        yScale = chartHeight / (self.minY - self.maxY)
        yOffset = rect.height() * index.row()
        yValues = list(playerItem.chartPoints(index.column(), self.steps))
        yValues = [(y - self.maxY) * yScale - yOffset for y in yValues]
        stepX = float(rect.width()) / self.steps
        xValues = list(x * stepX for x in range(self.steps + 1))
        return list(QPointF(x, y) for x, y in zip(xValues, yValues))

    def data(self, index, role=None): # pylint: disable=R0201
        """score table"""
        # pylint: disable=R0911,R0912
        # pylint - too many returns and branches
        if not index.isValid():
            return QVariant()
        column = index.column()
        item = index.internalPointer()
        if role is None:
            role = Qt.DisplayRole
        if role == Qt.DisplayRole:
            if isinstance(item, ScorePlayerItem):
                content = item.content(column)
                if isinstance(content, HandResult):
                    parentRow = item.parent.row()
                    if parentRow == 0:
                        if not content.penalty:
                            content = '%d %s'% (content.points, content.wind)
                    elif parentRow == 1:
                        content = str(content.payments)
                    else:
                        content = str(content.balance)
                return QVariant(content)
            else:
                if column > 0:
                    return QVariant('')
                else:
                    return QVariant(item.content(0))
        if role == Qt.TextAlignmentRole:
            if index.column() == 0:
                return QVariant(int(Qt.AlignLeft|Qt.AlignVCenter))
            else:
                return QVariant(int(Qt.AlignRight|Qt.AlignVCenter))
        if role == Qt.FontRole:
            return QFont('Monospaced')
        if role == Qt.ForegroundRole:
            if isinstance(item, ScorePlayerItem) and item.parent.row() == 3:
                content = item.content(column)
                if not isinstance(content, HandResult):
                    return QVariant(QBrush(ScoreItemDelegate.colors[index.row()]))
        if column > 0 and isinstance(item, ScorePlayerItem) :
            content = item.content(column)
            # pylint: disable=E1103
            # pylint thinks content is a str
            if role == Qt.BackgroundRole:
                if content.won:
                    return QVariant(QColor(165, 255, 165))
            if role == Qt.ToolTipRole:
                englishHints = content.manualrules.split('||')
                tooltip = '<br />'.join(m18n(x) for x in englishHints)
                return QVariant(tooltip)
        return QVariant()

    def headerData(self, section, orientation, role):
        """tell the view about the wanted headers"""
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if section == 0:
                return m18n('Round/Hand')
            child1 = self.rootItem.children[0]
            if child1 and child1.children:
                child1 = child1.children[0]
                hands = child1.hands()
                handResult = hands[section-1]
                if not handResult.penalty:
                    return handResult.handId()
        elif role == Qt.TextAlignmentRole:
            if section == 0:
                return QVariant(int(Qt.AlignLeft|Qt.AlignVCenter))
            else:
                return QVariant(int(Qt.AlignRight|Qt.AlignVCenter))
        return QVariant()

    def loadData(self):
        """loads all data from the data base into a 2D matrix formatted like the wanted tree"""
        game = self.scoreTable.game
        data = []
        records = Query(
                'select player,rotated,notrotated,penalty,won,prevailing,wind,points,payments,balance,manualrules'
                ' from score where game=? order by player,hand',
                list([game.gameid])).records
        # pylint: disable=W0142
        # pylint * magic
        data = list(tuple([player.localName, [HandResult(*x[1:]) for x in records \
                if x[0] == player.nameid]]) for player in game.players)
        self.__findMinMaxChartPoints(data)
        parent = QModelIndex()
        groupIndex = self.index(self.rootItem.childCount(), 0, parent)
        groupNames = [m18nc('kajongg','Score'), m18nc('kajongg','Payments'),
                m18nc('kajongg','Balance'), m18nc('kajongg', 'Chart')]
        for idx, groupName in enumerate(groupNames):
            self.insertRows(idx, list([ScoreGroupItem(groupName)]), groupIndex)
            listIndex = self.index(idx, 0, groupIndex)
            for idx1, item in enumerate(data):
                self.insertRows(idx1, list([ScorePlayerItem(item)]), listIndex)

    def __findMinMaxChartPoints(self, data):
        """find and save the extremes of the spline. They can be higher than
        the pure balance values"""
        self.minY = 9999999
        self.maxY = -9999999
        for item in data:
            playerItem = ScorePlayerItem(item)
            for col in range(len(playerItem.hands())):
                points = list(playerItem.chartPoints(col+1, self.steps))
                self.minY = min(self.minY, min(points))
                self.maxY = max(self.maxY, max(points))
        self.minY -= 2 # antialiasing might cross the cell border
        self.maxY += 2

class HandResult(object):
    """holds the results of a hand for the scoring table"""
    # pylint: disable=R0913
    # we have too many arguments
    def __init__(self, rotated, notRotated, penalty, won, prevailing, wind, points, payments, balance, manualrules):
        self.rotated = rotated
        self.notRotated = notRotated
        self.penalty = bool(penalty)
        self.won = won
        self.prevailing = prevailing
        self.wind = wind
        self.points = points
        self.payments = payments
        self.balance = balance
        self.manualrules = manualrules

    def __str__(self):
        return '%d %d %s %d %d %s' % (
                self.penalty, self.points, self.wind, self.payments, self.balance, self.manualrules)

    def handId(self):
        """identifies the hand for window title and scoring table"""
        character = chr(ord('a') - 1 + self.notRotated) if self.notRotated else ''
        return '%s%s%s' % (self.prevailing, self.rotated + 1, character)

    def roundHand(self, allHands):
        """the nth hand in the current round, starting with 1"""
        idx = allHands.index(self)
        allHands = list(reversed(allHands[:idx]))
        allHands = list(x for x in allHands if not x.penalty)
        if not allHands:
            return 1
        for idx, hand in enumerate(allHands):
            if hand.prevailing != self.prevailing:
                return idx + 1
        return idx + 2

class ScoreViewLeft(QTreeView):
    """subclass for defining sizeHint"""
    def __init__(self, parent=None):
        QTreeView.__init__(self, parent)
        self.setItemDelegate(ScoreItemDelegate(self))

    def __col0Width(self):
        """the width we need for displaying column 0
        without scrollbar"""
        return self.columnWidth(0) + self.frameWidth() * 2

    def sizeHint(self):
        """we never want a horizontal scrollbar for player names,
        we always want to see them in full"""
        return QSize(self.__col0Width(), QTreeView.sizeHint(self).height())

    def minimumSizeHint(self):
        """we never want a horizontal scrollbar for player names,
        we always want to see them in full"""
        return self.sizeHint()

class ScoreViewRight(QTreeView):
    """we need to subclass for catching events"""
    def __init__(self, parent=None):
        QTreeView.__init__(self, parent)
        self.setItemDelegate(ScoreItemDelegate(self))

    def changeEvent(self, event):
        """recompute column width if font changes"""
        if event.type() == QEvent.FontChange:
            self.setColWidth()

    def setColWidth(self):
        """we want a fixed column width sufficient for all values"""
        colRange = range(1, self.header().count())
        if colRange:
            for col in colRange:
                self.resizeColumnToContents(col)
            width = max(self.columnWidth(x) for x in colRange)
            for col in colRange:
                self.setColumnWidth(col, width)

class HorizontalScrollBar(QScrollBar):
    """We subclass here because we want to react on show/hide"""
    def __init__(self, scoreTable, parent=None):
        QScrollBar.__init__(self, parent)
        self.scoreTable = scoreTable

    def showEvent(self, dummyEvent):
        """adjust the left view"""
        self.scoreTable.adaptLeftViewHeight()

    def hideEvent(self, dummyEvent):
        """adjust the left view"""
        self.scoreTable.viewRight.header().setOffset(0) # we should not have to do this...
        # how to reproduce problem without setOffset:
        # show table with hor scroll, scroll to right, extend window
        # width very fast. The faster we do that, the wronger the
        # offset of the first column in the viewport.
        self.scoreTable.adaptLeftViewHeight()

class ScoreTable(QWidget):
    """show scores of current or last game, even if the last game is
    finished. To achieve this we keep our own reference to game."""
    def __init__(self, game):
        super(ScoreTable, self).__init__(None)
        self.setObjectName('ScoreTable')
        self.game = None
        self.scoreModel = None
        self.scoreModelTest = None
        self.setWindowTitle(m18nc('kajongg', 'Scores') + ' - Kajongg')
        self.setAttribute(Qt.WA_AlwaysShowToolTips)
        self.setMouseTracking(True)
        self.__tableFields = ['prevailing', 'won', 'wind',
                                'points', 'payments', 'balance', 'hand', 'manualrules']
        self.setupUi()
        self.refresh(game)
        StateSaver(self, self.splitter)

    def setColWidth(self):
        """we want to accomodate 5 digits plus minus sign
        and all column widths should be the same, making
        horizontal scrolling per item more pleasant"""
        self.viewRight.setColWidth()

    def setupUi(self):
        """setup UI elements"""
        self.viewLeft = ScoreViewLeft(self)
        self.viewRight = ScoreViewRight(self)
        self.viewRight.setHorizontalScrollBar(HorizontalScrollBar(self))
        self.viewRight.setHorizontalScrollMode(QAbstractItemView.ScrollPerItem)
        self.viewRight.setFocusPolicy(Qt.NoFocus)
        self.viewRight.header().setClickable(False)
        self.viewRight.header().setMovable(False)
        self.viewRight.setSelectionMode(QAbstractItemView.NoSelection)
        windowLayout = QVBoxLayout(self)
        self.splitter = QSplitter(Qt.Vertical)
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
        self.ruleTree = RuleTreeView(m18nc('kajongg','Used Rules'))
        self.splitter.addWidget(self.ruleTree)
        # this shows just one line for the ruleTree - so we just see the
        # name of the ruleset:
        self.splitter.setSizes(list([1000, 1]))

    def sizeHint(self):
        """give the scoring table window a sensible default size"""
        result = QWidget.sizeHint(self)
        result.setWidth(result.height() * 3 / 2)
        # the default is too small. Use at least 2/5 of screen height and 1/4 of screen width:
        available = KApplication.kApplication().desktop().availableGeometry()
        height = max(result.height(), available.height() * 2 / 5)
        width = max(result.width(), available.width() / 4)
        result.setHeight(height)
        result.setWidth(width)
        return result

    def refresh(self, game):
        """load this game and this player. Keep parameter list identical with
        ExplainView"""
        if not game:
            # keep scores of previous game on display
            return
        if self.scoreModel:
            expandGroups = [
                self.viewLeft.isExpanded(self.scoreModel.index(x, 0, QModelIndex()))
                for x in range(4)]
        else:
            expandGroups = [True, False, True, True]
        self.game = game
        gameid = str(self.game.seed or self.game.gameid)
        if self.game.finished():
            title = m18n('Final scores for game <numid>%1</numid>', gameid)
        else:
            title = m18n('Scores for game <numid>%1</numid>', gameid)
        self.setWindowTitle(title + ' - Kajongg')
        self.ruleTree.rulesets = list([self.game.ruleset])
        self.scoreModel = ScoreModel(self)
        if Debug.modelTest:
            self.scoreModelTest = ModelTest(self.scoreModel, self)
        for view in [self.viewLeft, self.viewRight]:
            view.setModel(self.scoreModel)
            header = view.header()
            header.setStretchLastSection(False)
            view.setAlternatingRowColors(True)
        self.viewRight.header().setResizeMode(QHeaderView.Fixed)
        for col in range(self.viewLeft.header().count()):
            self.viewLeft.header().setSectionHidden(col, col > 0)
            self.viewRight.header().setSectionHidden(col, col == 0)
        self.scoreLayout.setStretch(1, 100)
        self.scoreLayout.setSpacing(0)
        self.viewLeft.setFrameStyle(QFrame.NoFrame)
        self.viewRight.setFrameStyle(QFrame.NoFrame)
        self.viewLeft.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for master, slave in ((self.viewRight, self.viewLeft), (self.viewLeft, self.viewRight)):
            master.expanded.connect(slave.expand)
            master.collapsed.connect(slave.collapse)
            master.verticalScrollBar().valueChanged.connect(slave.verticalScrollBar().setValue)
        for row, expand in enumerate(expandGroups):
            self.viewLeft.setExpanded(self.scoreModel.index(row, 0, QModelIndex()), expand)
        self.viewLeft.resizeColumnToContents(0)
        self.viewRight.setColWidth()
        # we need a timer since the scrollbar is not yet visible
        QTimer.singleShot(0, self.scrollRight)

    def scrollRight(self):
        """make sure the latest hand is visible"""
        scrollBar = self.viewRight.horizontalScrollBar()
        scrollBar.setValue(scrollBar.maximum())

    def showEvent(self, dummyEvent):
        """Only now the views and scrollbars have useful sizes, so we can compute the spacer
        for the left view"""
        self.adaptLeftViewHeight()

    def adaptLeftViewHeight(self):
        """if the right view has a horizontal scrollbar, make sure both
        view have the same vertical scroll area. Otherwise scrolling to
        bottom results in unsyncronized views."""
        if self.viewRight.horizontalScrollBar().isVisible():
            height = self.viewRight.horizontalScrollBar().height()
        else:
            height = 0
        if self.leftLayout.count() > 1:
            # remove previous spacer
            self.leftLayout.takeAt(1)
        if height:
            self.leftLayout.addSpacing(height)

class ExplainView(QListView):
    """show a list explaining all score computations"""
    def __init__(self, game, parent=None):
        QListView.__init__(self, parent)
        self.game = None
        self.setWindowTitle(m18n('Explain Scores').replace('&', '') + ' - Kajongg')
        self.setGeometry(0, 0, 300, 400)
        self.model = QStringListModel()
        self.setModel(self.model)
        StateSaver(self)
        self.refresh(game)

    def refresh(self, game):
        """refresh for new values"""
        self.game = game
        lines = []
        if self.game is None:
            lines.append(m18n('There is no active game'))
        else:
            i18nName = m18n(self.game.ruleset.name)
            lines.append(m18n('Ruleset: %1', i18nName))
            lines.append('')
            for player in self.game.players:
                pLines = []
                if player.hand and player.hand.tileNames:
                    total = player.hand.total()
                    if total:
                        pLines = ['%s: %s' % (player.localName, total)]
                        for line in player.hand.explain():
                            pLines.append('- ' + line)
                elif player.handTotal:
                    pLines.append(m18n('Manual score for %1: %2 points', player.localName, player.handTotal))
                if pLines:
                    pLines.append('')
                lines.extend(pLines)
        if 'xxx'.join(lines) != 'xxx'.join(unicode(x) for x in self.model.stringList()):
            # QStringListModel does not optimize identical lists away, so we do
            self.model.setStringList(lines)

class PenaltyBox(QSpinBox):
    """with its own validator, we only accept multiples of parties"""
    def __init__(self, parties, parent=None):
        QSpinBox.__init__(self, parent)
        self.parties = parties
        self.prevValue = None

    def validate(self, inputData, pos):
        """check if value is a multiple of parties"""
        result, newPos = QSpinBox.validate(self, inputData, pos)
        if result == QValidator.Acceptable:
            if int(inputData) % self.parties != 0:
                result = QValidator.Intermediate
        if result == QValidator.Acceptable:
            self.prevValue = str(inputData)
        return (result, newPos)

    def fixup(self, data):
        """change input to a legal value"""
        value = int(str(data))
        prevValue = int(str(self.prevValue))
        assert value != prevValue
        common = int(self.parties * 10)
        small = value // common
        if value > prevValue:
            newV = str(int((small + 1) * common))
        else:
            newV = str(int(small * common))
        data.clear()
        data.append(newV)

class RuleBox(QCheckBox):
    """additional attribute: ruleId"""
    def __init__(self, rule):
        QCheckBox.__init__(self, m18n(rule.name))
        self.rule = rule

    def setApplicable(self, applicable):
        """update box"""
        self.setVisible(applicable)
        if not applicable:
            self.setChecked(False)

class PenaltyDialog(QDialog):
    """enter penalties"""
    def __init__(self, game):
        """selection for this player, tiles are the still available tiles"""
        QDialog.__init__(self, None)
        self.setWindowTitle(m18n("Penalty") + ' - Kajongg')
        self.game = game
        grid = QGridLayout(self)
        lblOffense = QLabel(m18n('Offense:'))
        crimes = list([x for x in game.ruleset.penaltyRules if not ('absolute' in x.options and game.winner)])
        self.cbCrime = ListComboBox(crimes)
        lblOffense.setBuddy(self.cbCrime)
        grid.addWidget(lblOffense, 0, 0)
        grid.addWidget(self.cbCrime, 0, 1, 1, 4)
        lblPenalty = QLabel(m18n('Total Penalty'))
        self.spPenalty = PenaltyBox(2)
        self.spPenalty.setRange(0, 9999)
        lblPenalty.setBuddy(self.spPenalty)
        self.lblUnits = QLabel(m18n('points'))
        grid.addWidget(lblPenalty, 1, 0)
        grid.addWidget(self.spPenalty, 1, 1)
        grid.addWidget(self.lblUnits, 1, 2)
        self.payers = []
        self.payees = []
        # a penalty can never involve the winner, neither as payer nor as payee
        for idx in range(3):
            self.payers.append(ListComboBox(game.losers()))
            self.payees.append(ListComboBox(game.losers()))
        for idx, payer in enumerate(self.payers):
            grid.addWidget(payer, 3+idx, 0)
            payer.lblPayment = QLabel()
            grid.addWidget(payer.lblPayment, 3+idx, 1)
        for idx, payee in enumerate(self.payees):
            grid.addWidget(payee, 3+idx, 3)
            payee.lblPayment = QLabel()
            grid.addWidget(payee.lblPayment, 3+idx, 4)
        grid.addWidget(QLabel(''), 6, 0)
        grid.setRowStretch(6, 10)
        for player in self.payers + self.payees:
            player.currentIndexChanged.connect(self.playerChanged)
        self.spPenalty.valueChanged.connect(self.penaltyChanged)
        self.cbCrime.currentIndexChanged.connect(self.crimeChanged)
        buttonBox = KDialogButtonBox(self)
        grid.addWidget(buttonBox, 7, 0, 1, 5)
        buttonBox.setStandardButtons(QDialogButtonBox.Cancel)
        buttonBox.rejected.connect(self.reject)
        self.btnExecute = buttonBox.addButton(m18n("&Execute"), QDialogButtonBox.AcceptRole,
            self, SLOT("accept()"))
        self.crimeChanged()
        StateSaver(self)

    def accept(self):
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

    def usedCombos(self, partyCombos):
        """return all used player combos for this offense"""
        return [x for x in partyCombos if x.isVisibleTo(self)]

    def allParties(self):
        """return all parties involved in penalty payment"""
        return [x.current for x in self.usedCombos(self.payers+self.payees)]

    def playerChanged(self):
        """shuffle players to ensure everybody only appears once.
        enable execution if all input is valid"""
        changedCombo = self.sender()
        if not isinstance(changedCombo, ListComboBox):
            changedCombo = self.payers[0]
        usedPlayers = set(self.allParties())
        unusedPlayers = set(self.game.losers()) - usedPlayers
        foundPlayers = [changedCombo.current]
        for combo in self.usedCombos(self.payers+self.payees):
            if combo is not changedCombo:
                if combo.current in foundPlayers:
                    combo.current = unusedPlayers.pop()
                foundPlayers.append(combo.current)

    def crimeChanged(self):
        """another offense has been selected"""
        offense = self.cbCrime.current
        payers = int(offense.options.get('payers', 1))
        payees = int(offense.options.get('payees', 1))
        self.spPenalty.prevValue = str(-offense.score.points)
        self.spPenalty.setValue(-offense.score.points)
        self.spPenalty.parties = max(payers, payees)
        self.spPenalty.setSingleStep(10 )
        self.lblUnits.setText(m18n('points'))
        self.playerChanged()
        self.penaltyChanged()

    def penaltyChanged(self):
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
                player.setVisible(idx<count)
                player.lblPayment.setVisible(idx<count)
                if idx < count:
                    if pList == self.payers:
                        player.lblPayment.setText(m18nc('penalty dialog, appears behind paying player combobox',
                            'pays %1 points', -amount))
                    else:
                        player.lblPayment.setText(m18nc('penalty dialog, appears behind profiting player combobox',
                            'gets %1 points', amount))

class ScoringDialog(QWidget):
    """a dialog for entering the scores"""
    # pylint: disable=R0902
    # pylint we need more than 10 instance attributes

    scoringClosed = pyqtSignal()

    def __init__(self, game):
        QWidget.__init__(self, None)
        self.game = None
        self.setWindowTitle(m18n('Scoring for this Hand') + ' - Kajongg')
        self.nameLabels = [None] * 4
        self.spValues = [None] * 4
        self.windLabels = [None] * 4
        self.wonBoxes = [None] * 4
        self.detailsLayout = [None] * 4
        self.details = [None] * 4
        self.__tilePixMaps = []
        self.__meldPixMaps = []
        grid = QGridLayout(self)
        pGrid = QGridLayout()
        grid.addLayout(pGrid, 0, 0, 2, 1)
        pGrid.addWidget(QLabel(m18nc('kajongg', "Player")), 0, 0)
        pGrid.addWidget(QLabel(m18nc('kajongg', "Wind")), 0, 1)
        pGrid.addWidget(QLabel(m18nc('kajongg', 'Score')), 0, 2)
        pGrid.addWidget(QLabel(m18n("Winner")), 0, 3)
        self.detailTabs = QTabWidget()
        self.detailTabs.setDocumentMode(True)
        pGrid.addWidget(self.detailTabs, 0, 4, 8, 1)
        for idx in range(4):
            self.setupUiForPlayer(pGrid, idx)
        self.draw = QCheckBox(m18nc('kajongg','Draw'))
        self.draw.clicked.connect(self.wonChanged)
        btnPenalties = QPushButton(m18n("&Penalties"))
        btnPenalties.clicked.connect(self.penalty)
        self.btnSave = QPushButton(m18n('&Save Hand'))
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
        self.refresh(game)

    def setupUILastTileMeld(self, pGrid):
        """setup UI elements for last tile and last meld"""
        self.lblLastTile = QLabel(m18n('&Last Tile:'))
        self.cbLastTile = QComboBox()
        self.cbLastTile.setMinimumContentsLength(1)
        vpol = QSizePolicy()
        vpol.setHorizontalPolicy(QSizePolicy.Fixed)
        self.cbLastTile.setSizePolicy(vpol)
        self.cbLastTile.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.lblLastTile.setBuddy(self.cbLastTile)
        self.lblLastMeld = QLabel(m18n('L&ast Meld:'))
        self.prevLastTile = None
        self.cbLastMeld = QComboBox()
        self.cbLastMeld.setMinimumContentsLength(1)
        self.cbLastMeld.setSizePolicy(vpol)
        self.cbLastMeld.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.lblLastMeld.setBuddy(self.cbLastMeld)
        self.comboTilePairs = set()
        pGrid.setRowStretch(6, 5)
        pGrid.addWidget(self.lblLastTile, 7, 0, 1, 2)
        pGrid.addWidget(self.cbLastTile, 7, 2, 1, 1)
        pGrid.addWidget(self.lblLastMeld, 8, 0, 1, 2)
        pGrid.addWidget(self.cbLastMeld, 8, 2, 1, 2)

    def setupUiForPlayer(self, pGrid, idx):
        """setup UI elements for a player"""
        self.spValues[idx] = QSpinBox()
        self.nameLabels[idx] = QLabel()
        self.nameLabels[idx].setBuddy(self.spValues[idx])
        self.windLabels[idx] = WindLabel()
        pGrid.addWidget(self.nameLabels[idx], idx+2, 0)
        pGrid.addWidget(self.windLabels[idx], idx+2, 1)
        pGrid.addWidget(self.spValues[idx], idx+2, 2)
        self.wonBoxes[idx] = QCheckBox("")
        pGrid.addWidget(self.wonBoxes[idx], idx+2, 3)
        self.wonBoxes[idx].clicked.connect(self.wonChanged)
        self.spValues[idx].valueChanged.connect(self.slotInputChanged)
        detailTab = QWidget()
        self.detailTabs.addTab(detailTab,'')
        self.details[idx] = QWidget()
        detailTabLayout = QVBoxLayout(detailTab)
        detailTabLayout.addWidget(self.details[idx])
        detailTabLayout.addStretch()
        self.detailsLayout[idx] = QVBoxLayout(self.details[idx])


    def refresh(self, game):
        """reload game"""
        if game and not game.isScoringGame():
            return
        self.game = game
        self.clear()
        self.setVisible(game is not None and not game.finished())
        if game:
            for idx, player in enumerate(game.players):
                for child in self.details[idx].children():
                    if isinstance(child, RuleBox):
                        child.hide()
                        self.detailsLayout[idx].removeWidget(child)
                        del child
                if game:
                    self.spValues[idx].setRange(0, game.ruleset.limit or 99999)
                    self.nameLabels[idx].setText(player.localName)
                    self.windLabels[idx].wind = player.wind
                    self.windLabels[idx].roundsFinished = game.roundsFinished
                    self.detailTabs.setTabText(idx, player.localName)
                    player.manualRuleBoxes = [RuleBox(x) for x in game.ruleset.allRules if x.hasSelectable]
                    for ruleBox in player.manualRuleBoxes:
                        self.detailsLayout[idx].addWidget(ruleBox)
                        ruleBox.clicked.connect(self.slotInputChanged)
                player.refreshManualRules()

    def show(self):
        """only now compute content"""
        if self.game and not self.game.finished():
            self.slotInputChanged()
            QWidget.show(self)

    def penalty(self):
        """penalty button clicked"""
        dlg = PenaltyDialog(self.game)
        dlg.exec_()

    def slotLastTile(self):
        """called when the last tile changes"""
        newLastTile = self.computeLastTile()
        if not newLastTile:
            return
        prevLower, newLower = self.prevLastTile.islower(), newLastTile.islower()
        if prevLower != newLower:
            # state of last tile (concealed/exposed) changed:
            # for all checked boxes check if they still are applicable
            winner = self.game.winner
            if winner:
                for box in winner.manualRuleBoxes:
                    if box.isChecked():
                        box.setChecked(False)
                        if winner.hand.manualRuleMayApply(box.rule):
                            box.setChecked(True)
        self.prevLastTile = newLastTile
        self.fillLastMeldCombo()
        self.slotInputChanged()

    def computeLastTile(self):
        """returns the currently selected last tile"""
        idx = self.cbLastTile.currentIndex()
        if idx >= 0:
            return str(self.cbLastTile.itemData(idx).toString())

    def closeEvent(self, event):
        """the user pressed ALT-F4"""
        self.hide()
        event.ignore()
        self.scoringClosed.emit()

    def clickedPlayerIdx(self, checkbox):
        """the player whose box has been clicked"""
        for idx in range(4):
            if checkbox == self.wonBoxes[idx]:
                return idx
        assert False

    def wonChanged(self):
        """if a new winner has been defined, uncheck any previous winner"""
        newWinner = None
        if self.sender() != self.draw:
            clicked = self.clickedPlayerIdx(self.sender())
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
        self.fillLastTileCombo()
        self.slotInputChanged()

    def updateManualRules(self):
        """enable/disable them"""
        # if an exclusive rule has been activated, deactivate it for
        # all other players
        if isinstance(self.sender(), RuleBox):
            ruleBox = self.sender()
            if ruleBox.isChecked() and ruleBox.rule.exclusive():
                for idx, player in enumerate(self.game.players):
                    if ruleBox.parentWidget() != self.details[idx]:
                        for pBox in player.manualRuleBoxes:
                            if pBox.rule.name == ruleBox.rule.name:
                                pBox.setChecked(False)
        try:
            newState = bool(self.game.winner.handBoard.tiles)
        except AttributeError:
            newState = False
        self.lblLastTile.setEnabled(newState)
        self.cbLastTile.setEnabled(newState)
        self.lblLastMeld.setEnabled(newState)
        self.cbLastMeld.setEnabled(newState)
        if self.game:
            for player in self.game.players:
                player.refreshManualRules(self.sender())

    def clear(self):
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
            for idx, player in enumerate(self.game.players):
                self.windLabels[idx].setPixmap(WINDPIXMAPS[(player.wind,
                            player.wind == WINDS[self.game.roundsFinished % 4])])
            self.computeScores()
            self.spValues[0].setFocus()
            self.spValues[0].selectAll()

    def computeScores(self):
        """if tiles have been selected, compute their value"""
        # pylint: disable=R0912
        # too many branches
        if not self.game:
            return
        if self.game.finished():
            self.hide()
            return
        for idx, player in enumerate(self.game.players):
            self.spValues[idx].blockSignals(True) # we do not want that change to call computeScores again
            self.wonBoxes[idx].blockSignals(True) # we do not want that change to call computeScores again
            if player.handBoard and player.handBoard.tiles:
                self.spValues[idx].setEnabled(False)
                self.nameLabels[idx].setBuddy(self.wonBoxes[idx])
                for loop in range(10):
                    prevTotal = player.handTotal
                    handContent = player.computeHand(asWinner=True)
                    self.wonBoxes[idx].setVisible(handContent.won)
                    if not self.wonBoxes[idx].isVisibleTo(self) and self.wonBoxes[idx].isChecked():
                        self.wonBoxes[idx].setChecked(False)
                        self.game.winner = None
                    elif prevTotal == player.handTotal:
                        break
                    player.refreshManualRules()
                self.spValues[idx].setValue(player.handTotal)
            else:
                if not self.spValues[idx].isEnabled():
                    self.spValues[idx].clear()
                    self.spValues[idx].setValue(0)
                    self.spValues[idx].setEnabled(True)
                    self.nameLabels[idx].setBuddy(self.spValues[idx])
                self.wonBoxes[idx].setVisible(player.handTotal >= self.game.ruleset.minMJTotal())
                if not self.wonBoxes[idx].isVisibleTo(self) and self.wonBoxes[idx].isChecked():
                    self.wonBoxes[idx].setChecked(False)
            if not self.wonBoxes[idx].isVisibleTo(self) and player is self.game.winner:
                self.game.winner = None
            self.spValues[idx].blockSignals(False)
            self.wonBoxes[idx].blockSignals(False)
        if Internal.field.explainView:
            Internal.field.explainView.refresh(self.game)

    def __lastMeldContent(self):
        """prepare content for lastmeld combo"""
        lastTiles = set()
        winnerTiles = []
        if self.game.winner and self.game.winner.handBoard:
            winnerTiles = self.game.winner.handBoard.tiles
            pairs = []
            for meld in self.game.winner.hand.melds:
                if len(meld) < 4:
                    pairs.extend(meld.pairs)
            for tile in winnerTiles:
                if tile.element in pairs and not tile.isBonus():
                    lastTiles.add(tile.element)
        return lastTiles, winnerTiles

    def __fillLastTileComboWith(self, lastTiles, winnerTiles):
        """fill last meld combo with prepared content"""
        self.comboTilePairs = lastTiles
        idx = self.cbLastTile.currentIndex()
        if idx < 0:
            idx = 0
        indexedTile = str(self.cbLastTile.itemData(idx).toPyObject())
        restoredIdx = None
        self.cbLastTile.clear()
        if not winnerTiles:
            return
        pmSize = winnerTiles[0].board.tileset.faceSize
        pmSize = QSize(pmSize.width() * 0.5, pmSize.height() * 0.5)
        self.cbLastTile.setIconSize(pmSize)
        QPixmapCache.clear()
        self.__tilePixMaps = []
        shownTiles = set()
        for tile in winnerTiles:
            if tile.element in lastTiles and tile.element not in shownTiles:
                shownTiles.add(tile.element)
                self.cbLastTile.addItem(QIcon(tile.graphics.pixmapFromSvg(pmSize, withBorders=False)),
                        '', QVariant(tile.element))
                if indexedTile == tile.element:
                    restoredIdx = self.cbLastTile.count() - 1
        if not restoredIdx and indexedTile:
            # try again, maybe the tile changed between concealed and exposed
            indexedTile = indexedTile.lower()
            for idx in range(self.cbLastTile.count()):
                if indexedTile == str(self.cbLastTile.itemData(idx).toPyObject()).lower():
                    restoredIdx = idx
                    break
        if not restoredIdx:
            restoredIdx = 0
        self.cbLastTile.setCurrentIndex(restoredIdx)
        self.prevLastTile = self.computeLastTile()

    def clearLastTileCombo(self):
        """as the name says"""
        self.comboTilePairs = None
        self.cbLastTile.clear()

    def fillLastTileCombo(self):
        """fill the drop down list with all possible tiles.
        If the drop down had content before try to preserve the
        current index. Even if the tile changed state meanwhile."""
        if self.game is None:
            return
        lastTiles, winnerTiles = self.__lastMeldContent()
        if self.comboTilePairs == lastTiles:
            return
        self.cbLastTile.blockSignals(True) # we only want to emit the changed signal once
        try:
            self.__fillLastTileComboWith(lastTiles, winnerTiles)
        finally:
            self.cbLastTile.blockSignals(False)
            self.cbLastTile.currentIndexChanged.emit(0)

    def __fillLastMeldComboWith(self, winnerMelds, indexedMeld, lastTile):
        """fill last meld combo with prepared content"""
        winner = self.game.winner
        faceWidth = winner.handBoard.tileset.faceSize.width() * 0.5
        faceHeight = winner.handBoard.tileset.faceSize.height() * 0.5
        restoredIdx = None
        for meld in winnerMelds:
            pixMap = QPixmap(faceWidth * len(meld), faceHeight)
            pixMap.fill(Qt.transparent)
            self.__meldPixMaps.append(pixMap)
            painter = QPainter(pixMap)
            for element in meld.pairs:
                painter.drawPixmap(0, 0,
                    winner.handBoard.tilesByElement(element) \
                    [0].graphics.pixmapFromSvg(QSize(faceWidth, faceHeight), withBorders=False))
                painter.translate(QPointF(faceWidth, 0.0))
            self.cbLastMeld.addItem(QIcon(pixMap), '', QVariant(meld.joined))
            if indexedMeld == meld.joined:
                restoredIdx = self.cbLastMeld.count() - 1
        if not restoredIdx and indexedMeld:
            # try again, maybe the meld changed between concealed and exposed
            indexedMeld = indexedMeld.lower()
            for idx in range(self.cbLastMeld.count()):
                meldContent = str(self.cbLastMeld.itemData(idx).toPyObject())
                if indexedMeld == meldContent.lower():
                    restoredIdx = idx
                    if lastTile not in meldContent:
                        if lastTile.lower() == lastTile:
                            lastTile = lastTile.capitalize()
                        else:
                            lastTile = lastTile.lower()
                        assert lastTile in meldContent
                        self.cbLastTile.blockSignals(True) # we want to continue right here
                        idx = self.cbLastTile.findData(QVariant(lastTile))
                        self.cbLastTile.setCurrentIndex(idx)
                        self.cbLastTile.blockSignals(False)
                    break
        if not restoredIdx:
            restoredIdx = 0
        self.cbLastMeld.setCurrentIndex(restoredIdx)
        self.cbLastMeld.setIconSize(QSize(faceWidth * 3, faceHeight))

    def fillLastMeldCombo(self):
        """fill the drop down list with all possible melds.
        If the drop down had content before try to preserve the
        current index. Even if the meld changed state meanwhile."""
        self.cbLastMeld.blockSignals(True) # we only want to emit the changed signal once
        try:
            showCombo = False
            idx = self.cbLastMeld.currentIndex()
            if idx < 0:
                idx = 0
            indexedMeld = str(self.cbLastMeld.itemData(idx).toPyObject())
            self.cbLastMeld.clear()
            self.__meldPixMaps = []
            if not self.game.winner:
                return
            if self.cbLastTile.count() == 0:
                return
            lastTile = Internal.field.computeLastTile()
            winnerMelds = [m for m in self.game.winner.hand.melds if len(m) < 4 \
                and lastTile in m.pairs]
            assert len(winnerMelds)
            if len(winnerMelds) == 1:
                self.cbLastMeld.addItem(QIcon(), '', QVariant(winnerMelds[0].joined))
                self.cbLastMeld.setCurrentIndex(0)
                return
            showCombo = True
            self.__fillLastMeldComboWith(winnerMelds, indexedMeld, lastTile)
        finally:
            self.lblLastMeld.setVisible(showCombo)
            self.cbLastMeld.setVisible(showCombo)
            self.cbLastMeld.blockSignals(False)
            self.cbLastMeld.currentIndexChanged.emit(0)

    def slotInputChanged(self):
        """some input fields changed: update"""
        for player in self.game.players:
            player.invalidateHand()
        self.updateManualRules()
        self.computeScores()
        self.validate()

    def validate(self):
        """update the status of the OK button"""
        game = self.game
        if game:
            valid = True
            if game.winner and game.winner.handTotal < game.ruleset.minMJTotal():
                valid = False
            elif not game.winner and not self.draw.isChecked():
                valid = False
            self.btnSave.setEnabled(valid)
