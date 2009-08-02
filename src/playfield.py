#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008,2009 Wolfgang Rohdewald <wolfgang@rohdewald.de>

kmj is free software you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

#from __future__  import print_function, unicode_literals, division

import sys
if sys.version_info < (2, 6, 0, 0, 0):
    bytes = str
else:
    str = unicode

import os,  datetime, syslog
import util
from PyKDE4.kdecore import i18n
from util import logMessage,  logException, m18n, m18nc, WINDS,  rotateCenter, StateSaver
import cgitb,  tempfile, webbrowser

class MyHook(cgitb.Hook):
    """override the standard cgitb hook: invoke the browser"""
    def __init__(self):
        self.tmpFileName = tempfile.mkstemp(suffix='.html', prefix='bt_', text=True)[1]
        cgitb.Hook.__init__(self, file=open(self.tmpFileName, 'w'))

    def handle(self,  info=None):
        """handling the exception: show backtrace in browser"""
        cgitb.Hook.handle(self, info)
        webbrowser.open(self.tmpFileName)

#sys.excepthook = MyHook()

NOTFOUND = []

try:
    from PyQt4.QtCore import Qt, QRectF,  QPointF, QVariant, SIGNAL, SLOT, \
        QEvent, QMetaObject, QSize, qVersion, PYQT_VERSION_STR
    from PyQt4.QtGui import QColor, QPushButton,  QMessageBox
    from PyQt4.QtGui import QWidget, QLabel, QPixmapCache, QTabWidget
    from PyQt4.QtGui import QGridLayout, QVBoxLayout, QHBoxLayout,  QSpinBox
    from PyQt4.QtGui import QDialog, QStringListModel, QListView, QSplitter
    from PyQt4.QtGui import QBrush, QIcon, QPixmap, QPainter, QDialogButtonBox
    from PyQt4.QtGui import QSizePolicy,  QComboBox,  QCheckBox, QTableView, QScrollBar
    from PyQt4.QtSql import QSqlDatabase, QSqlQueryModel
except ImportError,  e:
    NOTFOUND.append('PyQt4: %s' % e)

try:
    from PyKDE4.kdecore import ki18n, KGlobal, KAboutData
    from PyKDE4.kdeui import KApplication,  KStandardAction,  KAction, KToggleFullScreenAction,  KDialogButtonBox
    from PyKDE4.kdeui import KXmlGuiWindow, KIcon, KConfigDialog
except ImportError, e :
    NOTFOUND.append('PyKDE4: %s' % e)

try:
    from query import Query
    import board
    from tile import Tile
    from board import PlayerWind, PlayerWindLabel, Walls,  FittingView,  ROUNDWINDCOLOR, \
        HandBoard,  SelectorBoard, MJScene, WINDPIXMAPS
    from playerlist import PlayerList
    from tileset import Tileset, Elements, LIGHTSOURCES
    from background import Background
    from games import Games
    from genericdelegates import GenericDelegate,  IntegerColumnDelegate
    from config import Preferences, ConfigDialog
    from scoringengine import Ruleset, PredefinedRuleset, Hand, Score
    from rulesetselector import RuleTreeView
except ImportError,  e:
    NOTFOUND.append('kmj modules: %s' % e)

if len(NOTFOUND):
    MSG = "\n".join(" * %s" % s for s in NOTFOUND)
    logMessage(MSG)
    os.popen("kdialog --sorry '%s'" % MSG)
    sys.exit(3)

class ListComboBox(QComboBox):
    """easy to use with a python list. The elements must have an attribute 'name'."""
    def __init__(self, items,  parent=None):
        QComboBox.__init__(self, parent)
        self.items = items

    def __getItems(self):
        """getter for items"""
        return [self.itemData(idx).toPyObject() for idx in range(self.count())]

    def __setItems(self, items):
        """setter for items"""
        self.clear()
        for item in items:
            self.addItem(m18n(item.name), QVariant(item))

    items = property(__getItems, __setItems)

    def findItem(self, search):
        """returns the index or -1 of not found """
        for idx, item in enumerate(self.items):
            if item == search:
                return idx
        return -1

    def findName(self, search):
        """returns the index or -1 of not found """
        for idx, item in enumerate(self.items):
            if item.name == search:
                return idx
        return -1

    def names(self):
        """a list wiith all item names"""
        return list([x.name for x in self.items()])

    def __getCurrent(self):
        """getter for current"""
        return self.itemData(self.currentIndex()).toPyObject()

    def __setCurrent(self, item):
        """setter for current"""
        newIdx = self.findItem(item)
        if newIdx < 0:
            raise Exception('%s not found in ListComboBox' % item.name)
        self.setCurrentIndex(newIdx)

    current = property(__getCurrent, __setCurrent)

    def __getCurrentName(self):
        """getter for currentName"""
        return self.itemData(self.currentIndex()).toPyObject().name

    def __setCurrentName(self, name):
        """setter for currentName"""
        newIdx = self.findName(name)
        if newIdx < 0:
            raise Exception('%s not found in ListComboBox' % name)
        self.setCurrentIndex(newIdx)

    currentName = property(__getCurrentName, __setCurrentName)

class ScoreModel(QSqlQueryModel):
    """a model for our score table"""
    def __init__(self,  parent = None):
        super(ScoreModel, self).__init__(parent)

    def data(self, index, role=None):
        """score table data"""
        if role is None:
            role = Qt.DisplayRole
        if role == Qt.BackgroundRole and index.column() == 2:
            prevailing = self.field(index, 0).toString()
            if prevailing == self.data(index).toString():
                return QVariant(ROUNDWINDCOLOR)
        if role == Qt.BackgroundRole and index.column()==3:
            won = self.field(index, 1).toInt()[0]
            if won == 1:
                return QVariant(QColor(165, 255, 165))
        if role == Qt.ToolTipRole:
            tooltip = '<br />'.join(str(self.field(index, 7).toString()).split('||'))
            return QVariant(tooltip)
        return QSqlQueryModel.data(self, index, role)

    def field(self, index, column):
        """return a field of the column index points to"""
        return self.data(self.index(index.row(), column))

class ScoreTable(QWidget):
    """all player related data, GUI and internal together"""
    def __init__(self, game):
        super(ScoreTable, self).__init__(None)
        self.setWindowTitle(m18n('Scores for game <numid>%1</numid>' + ' - kmj', game.gameid))
        self.setAttribute(Qt.WA_AlwaysShowToolTips)
        self.game = game
        self.__tableFields = ['prevailing', 'won', 'wind',
                                'points', 'payments', 'balance', 'hand', 'manualrules']
        self.scoreModel = [ScoreModel(self) for player in range(0, 4)]
        self.scoreView = [QTableView(self)  for player in range(0, 4)]
        windowLayout = QVBoxLayout(self)
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setObjectName('ScoreTableSplitter')
        windowLayout.addWidget(self.splitter)
        tableWidget = QWidget()
        tableLayout = QVBoxLayout(tableWidget)
        playerLayout = QHBoxLayout()
        tableLayout.addLayout(playerLayout)
        self.splitter.addWidget(tableWidget)
        self.hscroll = QScrollBar(Qt.Horizontal)
        tableLayout.addWidget(self.hscroll)
        for idx, player in enumerate(game.players):
            vlayout = QVBoxLayout()
            playerLayout.addLayout(vlayout)
            nlabel = QLabel(player.name)
            nlabel.setAlignment(Qt.AlignCenter)
            view = self.scoreView[idx]
            vlayout.addWidget(nlabel)
            vlayout.addWidget(view)
            model = self.scoreModel[idx]
            view.verticalHeader().hide()
            view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            vpol = QSizePolicy()
            vpol.setHorizontalPolicy(QSizePolicy.Expanding)
            vpol.setVerticalPolicy(QSizePolicy.Expanding)
            view.setSizePolicy(vpol)
            view.setModel(model)
            delegate = GenericDelegate(self)
            delegate.insertColumnDelegate(self.__tableFields.index('payments'),
                IntegerColumnDelegate())
            delegate.insertColumnDelegate(self.__tableFields.index('balance'),
                IntegerColumnDelegate())
            view.setItemDelegate(delegate)
            view.setFocusPolicy(Qt.NoFocus)
            if idx != 3:
                view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            for scrollingView in self.scoreView:
                self.connect(scrollingView.verticalScrollBar(),
                        SIGNAL('valueChanged(int)'),
                        view.verticalScrollBar().setValue)
            for rcv_idx in range(0, 4):
                if idx != rcv_idx:
                    self.connect(view.horizontalScrollBar(),
                        SIGNAL('valueChanged(int)'),
                        self.scoreView[rcv_idx].horizontalScrollBar().setValue)
            self.retranslateUi(model)
            self.connect(view.horizontalScrollBar(),
                SIGNAL('rangeChanged(int, int)'),
                self.updateHscroll)
            self.connect(view.horizontalScrollBar(),
                SIGNAL('valueChanged(int)'),
                self.updateHscroll)
        self.splitter.addWidget(RuleTreeView(list([game.ruleset]), m18n('Used Rules')))
        self.connect(self.hscroll,
            SIGNAL('valueChanged(int)'),
            self.updateDetailScroll)
        self.connect(self.splitter, SIGNAL('splitterMoved(int,int)'), self.splitterMoved)
        self.loadTable()
        self.state = StateSaver(self, self.splitter)

    def splitterMoved(self, pos, index):
        """save changed state"""
        assert pos or index # quieten pylint
        self.state.save()

    def resizeEvent(self, event):
        """we can not reliably catch destruction"""
        assert event # quieten pylint
        self.state.save()

    def moveEvent(self, event):
        """also save current position"""
        assert event # quieten pylint
        self.state.save()

    def updateDetailScroll(self, value):
        """synchronise all four views"""
        for view in self.scoreView:
            view.horizontalScrollBar().setValue(value)

    def updateHscroll(self):
        """update the single horizontal scrollbar we have for all four tables"""
        needBar = False
        dst = self.hscroll
        for src in [x.horizontalScrollBar() for x in self.scoreView]:
            if src.minimum() == src.maximum():
                continue
            needBar = True
            dst.setMinimum(src.minimum())
            dst.setMaximum(src.maximum())
            dst.setPageStep(src.pageStep())
            dst.setValue(src.value())
            dst.setVisible(dst.minimum() != dst.maximum())
            break
        dst.setVisible(needBar)

    def retranslateUi(self, model):
        """m18n of the table"""
        model.setHeaderData(self.__tableFields.index('points'),
                Qt.Horizontal, QVariant(m18nc('kmj','Score')))
        model.setHeaderData(self.__tableFields.index('wind'),
                Qt.Horizontal, QVariant(''))
        # 0394 is greek big Delta, 2206 is mathematical Delta
        # this works with linux, on Windows we have to check if the used font
        # can display the symbol, otherwise use different font
        model.setHeaderData(self.__tableFields.index('payments'),
                Qt.Horizontal, QVariant(u"\u2206"))
        # 03A3 is greek big Sigma, 2211 is mathematical Sigma
        model.setHeaderData(self.__tableFields.index('balance'),
                Qt.Horizontal, QVariant(u"\u2211"))

    def loadTable(self):
        """load the data for this game and this player"""
        for idx, player in enumerate(self.game.players):
            model = self.scoreModel[idx]
            view = self.scoreView[idx]
            qStr = "select %s from score where game = %d and player = %d" % \
                (', '.join(self.__tableFields), self.game.gameid,  player.nameid)
            model.setQuery(qStr, Query.dbhandle)
            for col in (0, 1, 6, 7):
                view.hideColumn(col)
            view.resizeColumnsToContents()
            view.horizontalHeader().setStretchLastSection(True)
            view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())

# TODO: explainview und scoretable auch toggeln, wie ScoringDialog
class ExplainView(QListView):
    """show a list explaining all score computations"""
    def __init__(self, game, parent=None):
        QListView.__init__(self, parent)
        self.setWindowTitle(m18n('Explain Scores') + ' - kmj')
        self.setGeometry(0, 0, 300, 400)
        self.game = game
        self.model = QStringListModel()
        self.setModel(self.model)
        self.state = StateSaver(self)
        self.refresh()

    def moveEvent(self, event):
        """save current size and position"""
        assert event # quieten pylint
        self.state.save()

    def resizeEvent(self, event):
        """save current size and position"""
        assert event # quieten pylint
        self.state.save()

    def refresh(self):
        """refresh for new values"""
        lines = []
        if self.game.gameid == 0:
            lines.append(m18n('There is no active game'))
        else:
            i18nName = m18n(self.game.ruleset.name)
            lines.append(m18n('Ruleset: %1', i18nName))
            lines.append('')
            for player in self.game.players:
                total = 0
                pLines = []
                if player.handBoard.allTiles():
                    hand = player.hand(self.game)
                    total = hand.total()
                    pLines = hand.explain
                elif player.spValue:
                    total = player.spValue.value()
                    if total:
                        pLines.append(m18n('manual score: %1 points',  total))
                if total:
                    pLines = [m18n('Scoring for %1:', player.name)] + pLines
                pLines.append(m18n('Total for %1: %2 points', player.name, total))
                pLines.append('')
                lines.extend(pLines)
        self.model.setStringList(lines)

class SelectPlayers(QDialog):
    """a dialog for selecting four players"""
    def __init__(self, game):
        QDialog.__init__(self, None)
        self.game = game
        self.allPlayerNames = game.allPlayerNames.values()
        self.setWindowTitle(m18n('Select four players') + ' - kmj')
        self.buttonBox = KDialogButtonBox(self)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
        self.connect(self.buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(self.buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        grid = QGridLayout()
        self.names = None
        self.nameWidgets = []
        self.cbRuleset = ListComboBox(Ruleset.availableRulesets() + PredefinedRuleset.rulesets())
        if not self.cbRuleset.count():
            logException(Exception(m18n('No rulesets defined')))
        for idx, wind in enumerate(WINDS):
            cbName = QComboBox()
            # increase width, we want to see the full window title
            cbName.setMinimumWidth(350) # is this good for all platforms?
            cbName.addItems(self.allPlayerNames)
            grid.addWidget(cbName, idx+1, 1)
            self.nameWidgets.append(cbName)
            grid.addWidget(PlayerWindLabel(wind), idx+1, 0)
            self.connect(cbName, SIGNAL('currentIndexChanged(int)'),
                self.slotValidate)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 6)
        vbox = QVBoxLayout(self)
        vbox.addLayout(grid)
        vbox.addWidget(self.cbRuleset)
        vbox.addWidget(self.buttonBox)
        self.resize(300, 200)
        query = Query("select p0,p1,p2,p3 from game where game.id = (select max(id) from game)")
        if len(query.data):
            for pidx in range(4):
                playerId = query.data[0][pidx]
                playerName  = game.allPlayerNames[playerId]
                cbName = self.nameWidgets[pidx]
                playerIdx = cbName.findText(playerName)
                if playerIdx >= 0:
                    cbName.setCurrentIndex(playerIdx)
        self.slotValidate()

    def showEvent(self, event):
        """start with player 0"""
        assert event # quieten pylint
        self.nameWidgets[0].setFocus()

    def slotValidate(self):
        """try to find 4 different players and update status of the Ok button"""
        changedCombo = self.sender()
        if not isinstance(changedCombo, QComboBox):
            changedCombo = self.nameWidgets[0]
        usedNames = set([str(x.currentText()) for x in self.nameWidgets])
        unusedNames = set(self.allPlayerNames) - usedNames
        foundNames = [str(changedCombo.currentText())]
        for combo in self.nameWidgets:
            if combo is not changedCombo:
                if str(combo.currentText()) in foundNames:
                    if not unusedNames:
                        break
                    combo.setItemText(combo.currentIndex(), unusedNames.pop())
                foundNames.append(str(combo.currentText()))
        self.names = list(str(cbName.currentText()) for cbName in self.nameWidgets)
        valid = len(set(self.names)) == 4
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(valid)

class RuleBox(QCheckBox):
    """additional attribute: ruleId"""
    def __init__(self, rule):
        QCheckBox.__init__(self, m18n(rule.name))
        self.rule = rule

    def refresh(self, hand):
        """adjust state to hand"""
        applicable = self.rule.appliesToHand(hand)
        self.setVisible(applicable)
        if not applicable:
            self.setChecked(False)

class PenaltyDialog(QDialog):
    """enter penalties"""
    def __init__(self, players, winner, ruleset):
        """selection for this player, tiles are the still available tiles"""
        QDialog.__init__(self, None)
        self.setWindowTitle(m18n("Penalty") + ' - kmj')
        self.players = players
        self.winner = winner
        self.ruleset = ruleset
        grid = QGridLayout(self)
        lblOffense = QLabel(m18n('Offense:'))
        crimes = list([x for x in self.ruleset.penaltyRules if not ('absolute' in x.actions and self.winner)])
        self.cbCrime = ListComboBox(crimes)
        lblOffense.setBuddy(self.cbCrime)
        grid.addWidget(lblOffense, 0, 0)
        grid.addWidget(self.cbCrime, 0, 1, 1, 4)
        lblPenalty = QLabel(m18n('Total Penalty'))
        self.spPenalty = QSpinBox()
        self.spPenalty.setRange(0, 9999)
        self.spPenalty.setSingleStep(50)
        lblPenalty.setBuddy(self.spPenalty)
        self.lblUnits = QLabel(m18n('points'))
        grid.addWidget(lblPenalty, 1, 0)
        grid.addWidget(self.spPenalty, 1, 1)
        grid.addWidget(self.lblUnits, 1, 2)
        grid.addWidget(QLabel(m18n('Payers')), 2, 0)
        grid.addWidget(QLabel(m18n('pay')), 2, 1)
        grid.addWidget(QLabel(m18n('Payees')), 2, 3)
        grid.addWidget(QLabel(m18n('get')), 2, 4)
        self.payers = []
        self.payees = []
        # a penalty can never involve the winner, neither as payer nor as payee
        nonWinners = [p for p in players if p is not winner]
        for idx in range(3):
            self.payers.append(ListComboBox(nonWinners))
            self.payees.append(ListComboBox(nonWinners))
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
            self.connect(player, SIGNAL('currentIndexChanged(int)'), self.playerChanged)
        self.connect(self.cbCrime, SIGNAL('currentIndexChanged(int)'), self.crimeChanged)
        self.buttonBox = KDialogButtonBox(self)
        grid.addWidget(self.buttonBox, 7, 0, 1, 5)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel)
        self.connect(self.buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        self.btnExecute = self.buttonBox.addButton(i18n("&Execute"), QDialogButtonBox.AcceptRole,
            self, SLOT("accept()"))
        self.crimeChanged()
        self.state = StateSaver(self)

    def accept(self):
        """execute the penalty"""
        offense = self.cbCrime.current
        value = offense.score.value
        for allCombos, factor in ((self.payers, -1), (self.payees, 1)):
            combos = self.usedCombos(allCombos)
            for combo in combos:
                combo.current.getsPayment(-value//len(combos)*factor)
        QDialog.accept(self)

    def resizeEvent(self, event):
        """we can not reliably catch destruction"""
        assert event # quieten pylint
        self.state.save()

    def moveEvent(self, event):
        """also save current position"""
        assert event # quieten pylint
        self.state.save()

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
        unusedPlayers = set(self.players) - usedPlayers
        foundPlayers = [changedCombo.current]
        for combo in self.usedCombos(self.payers+self.payees):
            if combo is not changedCombo:
                if combo.current in foundPlayers:
                    combo.current = unusedPlayers.pop()
                foundPlayers.append(combo.current)

    def crimeChanged(self):
        """another offense has been selected"""
        payers = 0
        payees = 0
        offense = self.cbCrime.current
        payers = int(offense.actions.get('payers', 1))
        payees = int(offense.actions.get('payees', 1))
        self.spPenalty.setValue(-offense.score.value)
        self.lblUnits.setText(Score.unitName(offense.score.unit))
        for pList, count in ((self.payers, payers), (self.payees, payees)):
            for idx, payer in enumerate(pList):
                payer.setVisible(idx<count)
                payer.lblPayment.setVisible(idx<count)
                if idx < count:
                    payer.lblPayment.setText('%d %s' % (
                        -offense.score.value//count,  Score.unitName(offense.score.unit)))
        self.playerChanged()

class ScoringDialog(QWidget):
    """a dialog for entering the scores"""
    def __init__(self, game):
        QWidget.__init__(self, None)
        self.setWindowTitle(m18n('Scoring for this Hand') + ' - kmj')
        self._winner = None
        self.game = game
        self.players = game.players
        self.windLabels = [None] * 4
        self.__tilePixMaps = []
        self.__meldPixMaps = []
        grid = QGridLayout(self)
        pGrid = QGridLayout()
        grid.addLayout(pGrid, 0, 0, 2, 1)
        pGrid.addWidget(QLabel(m18nc('kmj', "Player")), 0, 0)
        pGrid.addWidget(QLabel(m18nc('kmj',  "Wind")), 0, 1)
        pGrid.addWidget(QLabel(m18nc('kmj', 'Score')), 0, 2)
        pGrid.addWidget(QLabel(m18n("Winner")), 0, 3)
        for idx, player in enumerate(self.players):
            player.spValue = QSpinBox()
            player.spValue.setRange(0, game.ruleset.limit)
            name = QLabel(player.name)
            name.setBuddy(player.spValue)
            pGrid.addWidget(name, idx+2, 0)
            self.windLabels[idx] = PlayerWindLabel(player.wind.name, self.game.roundsFinished)
            pGrid.addWidget(self.windLabels[idx], idx+2, 1)
            pGrid.addWidget(player.spValue, idx+2, 2)
            player.wonBox = QCheckBox("")
            pGrid.addWidget(player.wonBox, idx+2, 3)
            self.connect(player.wonBox, SIGNAL('clicked(bool)'), self.wonChanged)
            self.connect(player.spValue, SIGNAL('valueChanged(int)'), self.slotScoreChanged)
        self.draw = QCheckBox(m18nc('kmj','Draw'))
        self.connect(self.draw, SIGNAL('clicked(bool)'), self.wonChanged)
        self.btnPenalties = QPushButton(m18n("&Penalties"))
        self.connect(self.btnPenalties, SIGNAL('clicked(bool)'), self.penalty)
        self.btnSave = QPushButton(m18n('&Save Hand'))
        self.btnSave.setEnabled(False)
        vpol = QSizePolicy()
        vpol.setHorizontalPolicy(QSizePolicy.Fixed)
        self.lblLastTile = QLabel(m18n('&Last Tile:'))
        self.cbLastTile = QComboBox()
        self.cbLastTile.setMinimumContentsLength(1)
        self.cbLastTile.setSizePolicy(vpol)
        self.cbLastTile.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.lblLastTile.setBuddy(self.cbLastTile)
        self.lblLastMeld = QLabel(m18n('L&ast Meld:'))
        self.cbLastMeld = QComboBox()
        self.cbLastMeld.setMinimumContentsLength(1)
        self.cbLastMeld.setSizePolicy(vpol)
        self.cbLastMeld.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.lblLastMeld.setBuddy(self.cbLastMeld)
        pGrid.setRowStretch(6, 5)
        pGrid.addWidget(self.lblLastTile, 7, 0, 1, 2)
        pGrid.addWidget(self.cbLastTile, 7 , 2,  1,  1)
        pGrid.addWidget(self.lblLastMeld, 8, 0, 1, 2)
        pGrid.addWidget(self.cbLastMeld, 8 , 2,  1,  2)
        pGrid.setRowStretch(87, 10)
        pGrid.addWidget(self.draw, 7, 3)
        self.connect(self.cbLastTile, SIGNAL('currentIndexChanged(int)'),
            self.slotLastTile)
        self.connect(self.cbLastMeld, SIGNAL('currentIndexChanged(int)'),
            self.slotInputChanged)
        self.detailTabs = QTabWidget()
        pGrid.addWidget(self.detailTabs, 0, 4, 8, 1)
        for player in self.players:
            player.detailTab = QWidget()
            self.detailTabs.addTab(player.detailTab, player.name)
            player.detailGrid = QVBoxLayout(player.detailTab)
            player.manualRuleBoxes = [RuleBox(x) for x in self.game.ruleset.manualRules]
            ruleVBox = player.detailGrid
            for ruleBox in player.manualRuleBoxes:
                ruleVBox.addWidget(ruleBox)
                self.connect(ruleBox, SIGNAL('clicked(bool)'),
                    self.slotInputChanged)
            ruleVBox.addStretch()
        btnBox = QHBoxLayout()
        btnBox.addWidget(self.btnPenalties)
        btnBox.addWidget(self.btnSave)
        pGrid.addLayout(btnBox, 8, 4)
        self.players[0].spValue.setFocus()
        self.clear()
        self.state = StateSaver(self)

    def resizeEvent(self, event):
        """we can not reliably catch destruction"""
        assert event # quieten pylint
        self.state.save()

    def moveEvent(self, event):
        """also save current position"""
        assert event # quieten pylint
        self.state.save()

    def penalty(self):
        """penalty button clicked"""
        dlg = PenaltyDialog(self.players, self.winner, self.game.ruleset)
        if dlg.exec_():
            self.game.saveScores(list([dlg.cbCrime.current]))
            for player in self.players:
                player.clear()

    def slotLastTile(self):
        """called when the last tile changes"""
        self.fillLastMeldCombo()

    def closeEvent(self, event):
        """the user pressed ALT-F4"""
        self.hide()
        event.ignore()
        self.emit(SIGNAL('scoringClosed()'))

    def __getWinner(self):
        """getter for winner"""
        return self._winner

    def __setWinner(self, winner):
        """setter for winner"""
        if self._winner != winner:
            if self._winner and not winner:
                self._winner.wonBox.setChecked(False)
            self._winner = winner
            for player in self.players:
                if player != winner:
                    player.wonBox.setChecked(False)
            if winner:
                self.draw.setChecked(False)
            self.fillLastTileCombo()

    winner = property(__getWinner, __setWinner)

    def updateManualRules(self):
        """enable/disable them"""
        # if an exclusive rule has been activated, deactivate it for
        # all other players
        if isinstance(self.sender(), RuleBox):
            ruleBox = self.sender()
            if ruleBox.isChecked() and ruleBox.rule.exclusive():
                for player in self.players:
                    if ruleBox.parentWidget() != player.detailTab:
                        for pBox in player.manualRuleBoxes:
                            if pBox.rule.name == ruleBox.rule.name:
                                pBox.setChecked(False)

        newState = bool(self.winner and self.winner.handBoard.allTiles())
        self.lblLastTile.setEnabled(newState)
        self.cbLastTile.setEnabled(newState)
        self.lblLastMeld.setEnabled(newState)
        self.cbLastMeld.setEnabled(newState)
        for player in self.players:
            hand = player.hand(self.game)
            for ruleBox in player.manualRuleBoxes:
                ruleBox.refresh(hand)

    def clear(self):
        """prepare for next hand"""
        self.winner = None
        self.updateManualRules()
        for player in self.players:
            player.clear()
        if self.game.gameOver():
            self.hide()
        else:
            for idx, player in enumerate(self.players):
                self.windLabels[idx].setPixmap(WINDPIXMAPS[(player.wind.name,
                            player.wind.name == WINDS[self.game.roundsFinished])])
            self.computeScores()
            self.players[0].spValue.setFocus()

    def computeScores(self):
        """if tiles have been selected, compute their value"""
        if self.game.gameOver():
            self.hide()
            return
        for player in self.players:
            if player.handBoard.allTiles():
                player.spValue.setEnabled(False)
                hand = player.hand(self.game)
                player.wonBox.setVisible(hand.maybeMahjongg())
                if not player.wonBox.isVisible:
                    player.wonBox.setChecked(False)
                player.spValue.setValue(hand.total())
            else:
                if not player.spValue.isEnabled():
                    player.spValue.clear()
                    player.spValue.setEnabled(True)
                player.wonBox.setVisible(player.spValue.value() >= self.game.ruleset.minMJPoints)
            if not player.wonBox.isVisible() and player is self.winner:
                self.winner = None
        if self.game.explainView:
            self.game.explainView.refresh()

    def wonPlayer(self, checkbox):
        """the player who said mah jongg"""
        for player in self.players:
            if checkbox == player.wonBox:
                return player

    def wonChanged(self):
        """if a new winner has been defined, uncheck any previous winner"""
        newWinner = None
        if self.sender() != self.draw:
            clicked = self.wonPlayer(self.sender())
            if clicked.wonBox.isChecked():
                newWinner = clicked
        self.winner = newWinner
        self.slotInputChanged()

    def fillLastTileCombo(self):
        """fill the drop down list with all possible tiles"""
        self.cbLastTile.clear()
        self.__tilePixMaps = []
        if not self.winner:
            return
        winnerTiles = self.winner.handBoard.allTiles()
        if winnerTiles:
            pmSize = winnerTiles[0].tileset.faceSize
            pmSize = QSize(pmSize.width() * 0.5, pmSize.height() * 0.5)
            shownTiles = set()
        winnerMelds = [m for m in self.winner.hand(self.game).melds if len(m) < 4]
        pairs = []
        for meld in winnerMelds:
            pairs.extend(meld.contentPairs)
        for tile in winnerTiles:
            if tile.content in pairs and not tile.isBonus() and not tile.element in shownTiles:
                shownTiles.add(tile.element)
                pixMap = QPixmap(pmSize)
                pixMap.fill(Qt.transparent)
                self.__tilePixMaps.append(pixMap)
                painter = QPainter(pixMap)
                tile.renderer().render(painter, tile.element)
                self.cbLastTile.setIconSize(pixMap.size())
                self.cbLastTile.addItem(QIcon(pixMap), '', QVariant(tile.scoringStr()))

    def fillLastMeldCombo(self):
        """fill the drop down list with all possible melds"""
        self.cbLastMeld.blockSignals(True) # we only want to emit the changed signal once
        try:
            self.cbLastMeld.clear()
            self.__meldPixMaps = []
            if not self.winner:
                return
            if self.cbLastTile.count() == 0:
                return
            tileName = self.game.lastTile()
            winnerMelds = [m for m in self.winner.hand(self.game).melds if len(m) < 4 and tileName in m.contentPairs]
            assert len(winnerMelds)
            tile = self.winner.handBoard.allTiles()[0]
            tileWidth = tile.tileset.faceSize.width()
            pmSize = tile.tileset.faceSize
            pmSize = QSize(tileWidth * 0.5 * 3, pmSize.height() * 0.5)
            for meld in winnerMelds:
                pixMap = QPixmap(pmSize)
                pixMap.fill(Qt.transparent)
                self.__meldPixMaps.append(pixMap)
                painter = QPainter(pixMap)
                for idx, tileName in enumerate(meld.contentPairs):
                    element = Elements.elementName[tileName.lower()]
                    rect = QRectF(QPointF(idx * tileWidth * 0.5, 0.0), tile.tileset.faceSize * 0.5)
                    tile.renderer().render(painter, element, rect)
                self.cbLastMeld.setIconSize(pixMap.size())
                self.cbLastMeld.addItem(QIcon(pixMap), '', QVariant(meld.content))
        finally:
            self.cbLastMeld.blockSignals(False)
            self.cbLastMeld.emit(SIGNAL("currentIndexChanged(int)"), 0)

    def slotScoreChanged(self):
        """player score changed: check if saveable"""
        self.validate()

    def slotInputChanged(self):
        """some input fields changed: update"""
        self.updateManualRules()
        self.computeScores()
        self.validate()

    def validate(self):
        """update the status of the OK button"""
        valid = True
        if self.winner and self.winner.score < 20:
            valid = False
        elif not self.winner and not self.draw.isChecked():
            valid = False
        self.btnSave.setEnabled(valid)

class Player(object):
    """all player related data, GUI and internal together"""
    def __init__(self, wind, scene,  wall):
        self.scene = scene
        self.wall = wall
        self.wonBox = None
        self.manualRuleBoxes = []
        self.__proxy = None
        self.spValue = None
        self.nameItem = None
        self.__balance = 0
        self.__payment = 0
        self.nameid = 0
        self.__name = ''
        self.name = ''
        self.wind = PlayerWind(wind, 0, wall)
        self.handBoard = HandBoard(self)
        self.handBoard.setPos(yHeight= 1.5)
        self._hand = None

    def isWinner(self, game):
        """check in the scoringDialog"""
        winner = game.scoringDialog.winner or None
        return self == winner

    def mjString(self, game):
        """compile hand info into  a string as needed by the scoring engine"""
        winds = self.wind.name.lower() + 'eswn'[game.roundsFinished]
        wonChar = 'm'
        if self.isWinner(game):
            wonChar = 'M'
        return ''.join([wonChar, winds])

    def lastString(self, game):
        """compile hand info into  a string as needed by the scoring engine"""
        if not self.isWinner(game):
            return ''
        return 'L%s%s' % (game.lastTile(), game.lastMeld())

    def hand(self, game):
        """builds a Hand object"""
        string = ' '.join([self.handBoard.scoringString(), self.mjString(game), self.lastString(game)])
        rules = list(x.rule for x in self.manualRuleBoxes if x.isChecked())
        if not self._hand or self._hand.string != string or self._hand.rules != rules:
            self._hand = Hand(game.ruleset, string, rules)
        return self._hand

    def placeOnWall(self):
        """place name and wind on the wall"""
        center = self.wall.center()
        self.wind.setPos(center.x()*1.66, center.y()-self.wind.rect().height()/2.5)
        self.wind.setZValue(99999999999)
        if self.nameItem:
            self.nameItem.setParentItem(self.wall)
            nameRect = QRectF()
            nameRect.setSize(self.nameItem.mapToParent(self.nameItem.boundingRect()).boundingRect().size())
            self.nameItem.setPos(self.wall.center() - nameRect.center())
            self.nameItem.setZValue(99999999999)

    def getName(self):
        """the name of the player"""
        return self.__name

    def getTileset(self):
        """getter for tileset"""
        return self.wall.tileset

    def setTileset(self, tileset):
        """sets the name color matching to the wall color"""
        self.placeOnWall()
        if self.nameItem:
            if tileset.desktopFileName == 'jade':
                color = Qt.white
            else:
                color = Qt.black
            self.nameItem.setBrush(QBrush(QColor(color)))

    tileset = property(getTileset, setTileset)

    @staticmethod
    def getWindTileset():
        """getter for windTileset"""
        return None

    def setWindTileset(self, tileset):
        """setter for windTileset"""
        self.wind.setFaceTileset(tileset)
        self.placeOnWall()

    windTileset  = property(getWindTileset, setWindTileset)

    def setName(self, name):
        """change the name of the player, write it on the wall"""
        if self.__name == name:
            return
        self.__name = name
        if self.nameItem:
            self.scene.removeItem(self.nameItem)
        if name == '':
            return
        self.nameItem = self.scene.addSimpleText(name)
        self.tileset = self.wall.tileset
        self.nameItem.scale(3, 3)
        if self.wall.rotation == 180:
            rotateCenter(self.nameItem, 180)
        self.placeOnWall()

    name = property(getName, setName)

    def clear(self):
        """clear tiles and counters"""
        self.handBoard.clear()
        self.spValue.setValue(0)
        self.spValue.clear()
        self.wonBox.setChecked(False)
        self.__payment = 0

    def clearBalance(self):
        """sets the balance and the payments to 0"""
        self.__balance = 0
        self.__payment = 0

    @property
    def balance(self):
        """the balance of this player"""
        return self.__balance

    def getsPayment(self, payment):
        """make a payment to this player"""
        self.__balance += payment
        self.__payment += payment

    @property
    def payment(self):
        """the payments for the current hand"""
        return self.__payment

    def __get_score(self):
        """why does pylint want a doc string for this private method?"""
        return self.spValue.value()

    def __set_score(self,  score):
        """why does pylint want a doc string for this private method?"""
        if self.spValue is not None:
            self.spValue.setValue(score)
        if score == 0:
            # do not display 0 but an empty field
            if self.spValue is not None:
                self.spValue.clear()
            self.__payment = 0

    score = property(__get_score,  __set_score)

class PlayField(KXmlGuiWindow):
    """the main window"""

    def __init__(self):
        # see http://lists.kde.org/?l=kde-games-devel&m=120071267328984&w=2
        self.ignoreResizing = 1
        super(PlayField, self).__init__()
        board.PLAYFIELD = self
        Preferences() # defines PREF
        self.background = None
        self.settingsChanged = False

        Query.dbhandle = QSqlDatabase("QSQLITE")
        dbpath = KGlobal.dirs().locateLocal("appdata","kmj.db")
        Query.dbhandle.setDatabaseName(dbpath)
        dbExists = os.path.exists(dbpath)
        if not Query.dbhandle.open():
            logMessage(Query.dbhandle.lastError().text())
            sys.exit(1)
        if not dbExists:
            self.createTables()
            self.addTestData()
        self.playerwindow = None
        self.scoreTableWindow = None
        self.explainView = None
        self.scoringDialog = None
        self.allPlayerIds = {}
        self.allPlayerNames = {}
        self.roundsFinished = 0
        self.gameid = 0
        self.handctr = 0
        self.__rotated = None
        self.winner = None
        self.ruleset = None
        # shift rules taken from the OEMC 2005 rules
        # 2nd round: S and W shift, E and N shift
        self.shiftRules = 'SWEN,SE,WE'
        self.setupUi()
        KStandardAction.preferences(self.showSettings, self.actionCollection())
        self.applySettings()
        self.setupGUI()
        self.retranslateUi()

    def resizeEvent(self, event):
        """Use this hook to determine if we want to ignore one more resize
        event happening for maximized / almost maximized windows.
        this misses a few cases where the window is almost maximized because at
        this point the window has no border yet: event.size, self.geometry() and
        self.frameGeometry are all the same. So we cannot check if the bordered
        window would fit into availableGeometry.
        """
        available = KApplication.kApplication().desktop().availableGeometry()
        if self.ignoreResizing == 1: # at startup
            if available.width() <= event.size().width() \
            or available.height() <= event.size().height():
                self.ignoreResizing += 1
        KXmlGuiWindow.resizeEvent(self, event)

    def updateHandDialog(self):
        """refresh the enter dialog if it exists"""
        if self.scoringDialog:
            self.scoringDialog.computeScores()
        if self.explainView:
            self.explainView.refresh()

    def getRotated(self):
        """getter for rotated"""
        return self.__rotated

    def setRotated(self, rotated):
        """sets rotation, builds walls"""
        if self.__rotated != rotated:
            self.__rotated = rotated
            self.walls.build(self.tiles, rotated % 4,  8)

    rotated = property(getRotated, setRotated)

    def playerById(self, playerid):
        """lookup the player by id"""
        for player in self.players:
            if player.name == self.allPlayerNames[playerid]:
                return player

    def playerByWind(self, wind):
        """lookup the player by wind"""
        for player in self.players:
            if player.wind.name == wind:
                return player

    @staticmethod
    def createTables():
        """creates empty tables"""
        Query(["""CREATE TABLE player (
            id INTEGER PRIMARY KEY,
            name TEXT,
            unique(name))""",
        """CREATE TABLE game (
            id integer primary key,
            starttime text default current_timestamp,
            endtime text,
            ruleset integer references usedruleset(id),
            p0 integer constraint fk_p0 references player(id),
            p1 integer constraint fk_p1 references player(id),
            p2 integer constraint fk_p2 references player(id),
            p3 integer constraint fk_p3 references player(id))""",
        """CREATE TABLE score(
            game integer constraint fk_game references game(id),
            hand integer,
            data text,
            manualrules text,
            rotated integer,
            player integer constraint fk_player references player(id),
            scoretime text,
            won integer,
            prevailing text,
            wind text,
            points integer,
            payments integer,
            balance integer)""",
        """CREATE TABLE ruleset(
            id integer primary key,
            name text unique,
            hash text,
            lastused text,
            description text)""",
        """CREATE TABLE rule(
            ruleset integer,
            list integer,
            position integer,
            name text,
            value text,
            points integer,
            doubles integer,
            limits integer,
            primary key(ruleset,list,position),
            unique (ruleset,name))""",
        """CREATE TABLE usedruleset(
            id integer primary key,
            name text,
            hash text,
            lastused text,
            description text)""",
        """CREATE TABLE usedrule(
            ruleset integer,
            list integer,
            position integer,
            name text,
            value text,
            points integer,
            doubles integer,
            limits integer,
            primary key(ruleset,list,position),
            unique (ruleset,name))"""])

    @staticmethod
    def addTestData():
        """adds test data to an empty data base"""
        names = ['Wolfgang',  'Petra',  'Klaus',  'Heide']
        Query(['insert into player(name) values("%s")' % x for x in names])

    def kmjAction(self,  name, icon, slot=None, shortcut=None, data=None):
        """simplify defining actions"""
        res = KAction(self)
        res.setIcon(KIcon(icon))
        if slot:
            self.connect(res, SIGNAL('triggered()'), slot)
        self.actionCollection().addAction(name, res)
        if shortcut:
            res.setShortcut( Qt.CTRL + shortcut)
            res.setShortcutContext(Qt.ApplicationShortcut)
        res.setData(QVariant(data))
        return res

    def tileClicked(self, event, tile):
        """save the clicked tile, we need it when dropping things into boards"""
        self.centralScene.clickedTile = tile
        self.centralScene.clickedTileEvent = event
        self.selectorBoard.setAcceptDrops(tile.board != self.selectorBoard)

    def setupUi(self):
        """create all other widgets
        we could make the scene view the central widget but I did
        not figure out how to correctly draw the background with
        QGraphicsView/QGraphicsScene.
        QGraphicsView.drawBackground always wants a pixmap
        for a huge rect like 4000x3000 where my screen only has
        1920x1200"""
        self.setObjectName("MainWindow")
        centralWidget = QWidget()
        scene = MJScene()
        scene.game = self
        self.centralScene = scene
        self.centralView = FittingView()
        layout = QGridLayout(centralWidget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.centralView)
        self.tileset = None # just for pylint
        self.background = None # just for pylint
        self.tilesetName = util.PREF.tilesetName
        self.tiles = [Tile(element) for element in Elements.elements.all()]
        self.walls = Walls(self.tileset, self.tiles)
        # TODO: Immer nur Tile ohne Face zeichen, und die Tiles von einem Serverprozess holen
        scene.addItem(self.walls)
        self.selectorBoard = SelectorBoard(self.tileset)
        self.selectorBoard.setEnabled(False)
        self.selectorBoard.scale(1.7, 1.7)
        self.selectorBoard.setPos(xWidth=1.7, yWidth=3.9)
        scene.addItem(self.selectorBoard)
#        self.soli = board.Solitaire(self.tileset, [Tile(element) for element in elements.all()])
#        scene.addItem(self.soli)

        self.connect(scene, SIGNAL('tileClicked'), self.tileClicked)

        self.windTileset = Tileset(util.PREF.windTilesetName)
        self.players =  [Player(WINDS[idx], self.centralScene, self.walls[idx]) \
            for idx in range(0, 4)]

        for player in self.players:
            player.windTileset = self.windTileset
            player.handBoard.selector = self.selectorBoard

        self.setCentralWidget(centralWidget)
        self.centralView.setScene(scene)
        self.centralView.setFocusPolicy(Qt.StrongFocus)
        self.backgroundName = util.PREF.backgroundName
        self._adjustView()
        self.actionNewGame = self.kmjAction("new", "document-new", self.newGame, Qt.Key_N)
        self.actionQuit = self.kmjAction("quit", "application-exit", self.quit, Qt.Key_Q)
        self.actionPlayers = self.kmjAction("players",  "personal",  self.slotPlayers)
        self.actionScoring = self.kmjAction("scoring", "draw-freehand", shortcut=Qt.Key_S, data=ScoringDialog)
        self.actionScoring.setEnabled(False)
        self.actionScoring.setCheckable(True)
        self.connect(self.actionScoring, SIGNAL('toggled(bool)'), self.toggleWidget)
        self.actionAngle = self.kmjAction("angle",  "object-rotate-left",  self.changeAngle, Qt.Key_G)
        self.actionFullscreen = KToggleFullScreenAction(self.actionCollection())
        self.actionFullscreen.setShortcut(Qt.CTRL + Qt.Key_F)
        self.actionFullscreen.setShortcutContext(Qt.ApplicationShortcut)
        self.actionFullscreen.setWindow(self)
        self.actionCollection().addAction("fullscreen", self.actionFullscreen)
        self.connect(self.actionFullscreen, SIGNAL('toggled(bool)'), self.fullScreen)
        self.actionGames = self.kmjAction("load", "document-open", self.games, Qt.Key_L)
        self.actionScoreTable = self.kmjAction("scoreTable", "format-list-ordered",
            self.showScoreTable, Qt.Key_T)
        self.actionScoreTable.setEnabled(False)
        self.actionExplain = self.kmjAction("explain", "applications-education",
            self.explain)
        self.actionExplain.setEnabled(True)
        QMetaObject.connectSlotsByName(self)

    def fullScreen(self, toggle):
        """toggle between full screen and normal view"""
        self.actionFullscreen.setFullScreen(self, toggle)

    @staticmethod
    def quit():
        """exit the application"""
        sys.exit(0)

    def keyPressEvent(self, event):
        """navigate in the selectorboard"""
        mod = event.modifiers()
        if not mod in (Qt.NoModifier, Qt.ShiftModifier):
            # no other modifier is allowed
            KXmlGuiWindow.keyPressEvent(self, event)
            return
        key = event.key()
        tile = self.centralScene.focusItem()
        currentBoard = tile.board if isinstance(tile, Tile) else None
        wind = chr(key%256)
        moveCommands = m18nc('kmj:keyboard commands for moving tiles to the players ' \
            'with wind ESWN or to the central tile selector (X)', 'ESWNX')
        if wind in moveCommands:
            # this tells the receiving board that this is keyboard, not mouse navigation>
            # needed for useful placement of the popup menu
            self.centralScene.clickedTile = None
            # check opacity because we might be positioned on a hole
            if isinstance(tile, Tile) and tile.opacity:
                if wind == moveCommands[4]:
                    receiver = self.selectorBoard
                    receiver.sendTile(tile)
                else:
                    receiver = self.playerByWind(WINDS[moveCommands.index(wind)]).handBoard
                    receiver.sendTile(tile, self.centralView, lowerHalf=mod & Qt.ShiftModifier)
                if not currentBoard.allTiles():
                    self.centralView.scene().setFocusItem(receiver.focusTile)
            return
        if key == Qt.Key_Tab:
            tabItems = [self.selectorBoard]
            tabItems.extend(list(p.handBoard for p in self.players if p.handBoard.focusTile))
            tabItems.append(tabItems[0])
            currIdx = 0
            while tabItems[currIdx] != currentBoard and currIdx < len(tabItems) -2:
                currIdx += 1
            newItem = tabItems[currIdx+1].focusTile
            self.centralView.scene().setFocusItem(newItem)
            return
        KXmlGuiWindow.keyPressEvent(self, event)

    def retranslateUi(self):
        """retranslate"""
        self.actionNewGame.setText(m18n("&New"))
        self.actionQuit.setText(m18n("&Quit"))
        self.actionPlayers.setText(m18n("&Players"))
        self.actionAngle.setText(m18n("&Change Visual Angle"))
        self.actionGames.setText(m18n("&Load"))
        self.actionScoring.setText(m18n("&Scoring"))
        self.actionScoreTable.setText(m18nc('kmj', "&Score Table"))
        self.actionExplain.setText(m18n("&Explain Scores"))

    def changeEvent(self, event):
        """when the applicationwide language changes, recreate GUI"""
        if event.type() == QEvent.LanguageChange:
            self.setupGUI()
            self.retranslateUi()

    def slotPlayers(self):
        """show the player list"""
        if not self.playerwindow:
            self.playerwindow = PlayerList(self)
        self.playerwindow.show()

    def showScoreTable(self):
        """show the score table"""
        if self.gameid == 0:
            logException(Exception('showScoreTable: gameid is 0'))
        if not self.scoreTableWindow:
            self.scoreTableWindow = ScoreTable(self)
        self.scoreTableWindow.show()

    def explain(self):
        """explain the scores"""
        if not self.explainView:
            self.explainView = ExplainView(self)
        self.explainView.show()

    def findPlayer(self, wind):
        """returns the index and the player for wind"""
        for player in self.players:
            if player.wind.name == wind:
                return player
        logException(Exception("no player has wind %s" % wind))

    def games(self):
        """show all games"""
        gameSelector = Games(self)
        if gameSelector.exec_():
            if gameSelector.selectedGame is not None:
                self.loadGame(gameSelector.selectedGame)
            else:
                self.newGame()

    def _adjustView(self):
        """adjust the view such that exactly the wanted things are displayed
        without having to scroll"""
        view, scene = self.centralView, self.centralScene
        oldRect = view.sceneRect()
        view.setSceneRect(scene.itemsBoundingRect())
        newRect = view.sceneRect()
        if oldRect != newRect:
            view.fitInView(scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    def getTilesetName(self):
        """getter for tilesetName"""
        return self.tileset.desktopFileName

    def setTilesetName(self, name):
        """setter for tilesetName"""
        self.tileset = Tileset(name)

    tilesetName = property(getTilesetName, setTilesetName)

    def getBackgroundName(self):
        """getter for backgroundName"""
        return self.background.desktopFileName

    def setBackgroundName(self, name):
        """setter for backgroundName"""
        self.background = Background(name)
        self.background.setPalette(self.centralWidget())
        self.centralWidget().setAutoFillBackground(True)

    backgroundName = property(getBackgroundName, setBackgroundName)

    def applySettings(self):
        """apply preferences"""
        self.settingsChanged = True
        if self.tilesetName != util.PREF.tilesetName:
            self.tilesetName = util.PREF.tilesetName
            for item in self.centralScene.items():
                if not isinstance(item, Tile): # shortcut
                    try:
                        item.tileset = self.tileset
                    except AttributeError:
                        continue
            # change players last because we need the wall already to be repositioned
            for player in self.players: # class Player is no graphicsitem
                player.tileset = self.tileset
            self._adjustView() # the new tiles might be larger
            # maybe bug in qt4.5: after qgraphicssvgitem.setElementId(),
            # the previous cache content continues to be shown
            # cannot yet reproduce in small example
            QPixmapCache.clear()
        if self.backgroundName != util.PREF.backgroundName:
            self.backgroundName = util.PREF.backgroundName

    def showSettings(self):
        """show preferences dialog. If it already is visible, do nothing"""
        if  KConfigDialog.showDialog("settings"):
            return
        confDialog = ConfigDialog(self, "settings")
        self.connect(confDialog, SIGNAL('settingsChanged(QString)'),
           self.applySettings)
        confDialog.show()

    def swapPlayers(self, winds):
        """swap the winds for the players with wind in winds"""
        swappers = list(self.findPlayer(winds[x]) for x in (0, 1))
        mbox = QMessageBox()
        mbox.setWindowTitle(m18n("Swap Seats") + ' - kmj')
        mbox.setText("By the rules, %s and %s should now exchange their seats. " % \
            (swappers[0].name, swappers[1].name))
        yesAnswer = QPushButton("&Exchange")
        mbox.addButton(yesAnswer, QMessageBox.YesRole)
        noAnswer = QPushButton("&Keep seat")
        mbox.addButton(noAnswer, QMessageBox.NoRole)
        mbox.exec_()
        if mbox.clickedButton() == yesAnswer:
            wind0 = swappers[0].wind
            wind1 = swappers[1].wind
            new0,  new1 = wind1.name,  wind0.name
            wind0.setWind(new0,  self.roundsFinished)
            wind1.setWind(new1,  self.roundsFinished)

    def exchangeSeats(self):
        """propose and execute seat exchanges according to the rules"""
        myRules = self.shiftRules.split(',')[self.roundsFinished-1]
        while len(myRules):
            self.swapPlayers(myRules[0:2])
            myRules = myRules[2:]

    def loadPlayers(self):
        """load all defined players into self.allPlayerIds and self.allPlayerNames"""
        query = Query("select id,name from player")
        if not query.success:
            sys.exit(1)
        self.allPlayerIds = {}
        self.allPlayerNames = {}
        for record in query.data:
            (nameid, name) = record
            self.allPlayerIds[name] = record[0]
            self.allPlayerNames[nameid] = record[1]

    def newGameId(self):
        """write a new entry in the game table with the selected players
        and returns the game id of that new entry"""
        starttime = datetime.datetime.now().replace(microsecond=0).isoformat()
        # first insert and then find out which game id we just generated. Clumsy and racy.
        return Query(['insert into game(starttime,ruleset,p0,p1,p2,p3) values("%s", %d, %s)' % \
                (starttime, self.ruleset.rulesetId, ','.join(str(p.nameid) for p in self.players)),
              "update usedruleset set lastused='%s' where id=%d" %\
                (starttime, self.ruleset.rulesetId),
              "update ruleset set lastused='%s' where hash='%s'" %\
                (starttime, self.ruleset.hash),
              "select id from game where starttime = '%s'" % \
            starttime]).data[0][0]

    def newGame(self):
        """init the first hand of a new game"""
        self.loadPlayers() # we want to make sure we have the current definitions
        selectDialog = SelectPlayers(self)
        # if we have a selectable ruleset with the same name as the last used ruleset
        # use that selectable ruleset. We do not want to use the exact same last used
        # ruleset because we might have made some fixes to the ruleset meanwhile
        qData = Query("select name from usedruleset order by lastused desc").data
        if qData:
            selectDialog.cbRuleset.currentName = qData[0][0]
        if not selectDialog.exec_():
            return
        self.initGame()
        self.ruleset = selectDialog.cbRuleset.current
        self.ruleset.load()
        query = Query('select id from usedruleset where hash="%s"' % \
              (self.ruleset.hash))
        if query.data:
            # reuse that usedruleset
            self.ruleset.rulesetId = query.data[0][0]
        else:
            # generate a new usedruleset
            self.ruleset.rulesetId = self.ruleset.newId(used=True)
            self.ruleset.save()
        # initialise the four winds with the first four players:
        for idx, player in enumerate(self.players):
            player.name = selectDialog.names[idx]
            player.nameid = self.allPlayerIds[player.name]
            player.clearBalance()
        self.gameid = self.newGameId()
        self.showBalance()
        if self.explainView:
            self.explainView.refresh()
        self.actionScoring.setEnabled(True)

    def toggleWidget(self, checked):
        """user has toggled widget visibility with an action"""
        action = self.sender()
        data = action.data().toPyObject()
        if checked:
            if isinstance(data, type):
                data = data(self)
                self.sender().setData(QVariant(data))
                if isinstance(data, ScoringDialog):
                    self.scoringDialog = data
                    self.connect(data.btnSave, SIGNAL('clicked(bool)'), self.saveHand)
                    self.connect(data, SIGNAL('scoringClosed()'),self.scoringClosed)
            data.show()
            data.raise_()
        else:
            assert data
            data.hide()

    def scoringClosed(self):
        """the scoring window has been closed with ALT-F4 or similar"""
        self.actionScoring.setChecked(False)

    def saveHand(self):
        """save hand to data base, update score table and balance in status line"""
        self.winner = self.scoringDialog.winner
        self.payHand()
        self.saveScores()
        self.rotate()
        self.scoringDialog.clear()

    def saveScores(self, penaltyRules=None):
        """save computed values to data base, update score table and balance in status line"""
        scoretime = datetime.datetime.now().replace(microsecond=0).isoformat()
        cmdList = []
        penaltyRules = [(x, None) for x in penaltyRules or []] # add meld=None
        for player in self.players:
            hand = player.hand(self)
            manualrules = '||'.join(x.name for x, meld in hand.usedRules + penaltyRules)
            cmdList.append("INSERT INTO SCORE "
            "(game,hand,data,manualrules,player,scoretime,won,prevailing,wind,points,payments, balance,rotated) "
            "VALUES(%d,%d,'%s','%s',%d,'%s',%d,'%s','%s',%d,%d,%d,%d)" % \
            (self.gameid, self.handctr, hand.string, manualrules, player.nameid,
                scoretime, int(player.wonBox.isChecked()),
            WINDS[self.roundsFinished], player.wind.name, player.score,
            player.payment, player.balance, self.rotated))
        Query(cmdList)
        self.actionScoreTable.setEnabled(True)
        self.showBalance()

    def rotate(self):
        """initialise the values for a new hand"""
        if self.winner is not None and self.winner.wind.name != 'E':
            self.rotateWinds()
        self.handctr += 1
        self.walls.build(self.tiles, self.rotated % 4,  8)

    def initGame(self):
        """reset things to empty"""
        self.actionScoring.setChecked(False)
        for dlg in [self.scoreTableWindow]:
            if dlg:
                dlg.hide()
                dlg.setParent(None)
        self.scoreTableWindow = None
        self.scoringDialog = None
        self.roundsFinished = 0
        self.handctr = 0
        self.rotated = 0
        self.selectorBoard.setEnabled(True)
        self.centralView.scene().setFocusItem(self.selectorBoard.childItems()[0])
        for player in self.players:
            player.handBoard.clear()
            player.handBoard.setEnabled(True)

    def changeAngle(self):
        """change the lightSource"""
        oldIdx = LIGHTSOURCES.index(self.walls.lightSource)
        newLightSource = LIGHTSOURCES[(oldIdx + 1) % 4]
        self.walls.lightSource = newLightSource
        self.selectorBoard.lightSource = newLightSource
        for player in self.players:
            player.placeOnWall()
        self._adjustView()
        # bug in qt4.5: after qgraphicssvgitem.setElementId(),
        # the previous cache content continues to be shown
        QPixmapCache.clear()

    def loadGame(self, game):
        """load game data by game id"""
        qGame = Query("select p0, p1, p2, p3, ruleset from game where id = %d" %game)
        if not qGame.data:
            return
        self.initGame()
        rulesetId = qGame.data[0][4] or 1
        self.ruleset = Ruleset(rulesetId, used=True)
        self.ruleset.load()
        self.loadPlayers() # we want to make sure we have the current definitions
        for idx, player in enumerate(self.players):
            player.nameid = qGame.data[0][idx]
            try:
                player.name = self.allPlayerNames[player.nameid]
            except KeyError:
                player.name = m18n('Player %1 not known', player.nameid)

        qLastHand = Query("select hand,rotated from score where game=%d and hand="
            "(select max(hand) from score where game=%d)" % (game, game))
        if qLastHand.data:
            (self.handctr, self.rotated) = qLastHand.data[0]

        qScores = Query("select player, wind, balance, won from score "
            "where game=%d and hand=%d" % (game, self.handctr))
        for record in qScores.data:
            playerid = record[0]
            wind = str(record[1])
            player = self.playerById(playerid)
            if not player:
                logMessage(
                'game %d data inconsistent: player %d missing in game table' % \
                    (game, playerid), syslog.LOG_ERR)
            else:
                player.clearBalance()
                player.getsPayment(record[2])
                player.wind.setWind(wind,  self.roundsFinished)
            if record[3]:
                self.winner = player
        self.gameid = game
        self.actionScoreTable.setEnabled(True)
        self.showScoreTable()
        self.showBalance()
        self.rotate()
        self.actionScoring.setEnabled(self.roundsFinished < 4)
        if self.explainView:
            self.explainView.refresh()

    def showBalance(self):
        """show the player balances in the status bar"""
        if self.scoreTableWindow:
            self.scoreTableWindow.loadTable()
        sBar = self.statusBar()
        for idx, player in enumerate(self.players):
            sbMessage = player.name + ': ' + str(player.balance)
            if sBar.hasItem(idx):
                sBar.changeItem(sbMessage, idx)
            else:
                sBar.insertItem(sbMessage, idx, 1)
                sBar.setItemAlignment(idx, Qt.AlignLeft)

    def gameOver(self):
        """The game is over after 4 completed rounds"""
        result = self.roundsFinished == 4
        if result:
            self.selectorBoard.setEnabled(False)
            self.actionScoring.setEnabled(False)
            self.actionScoring.setChecked(False)
        return  result

    def rotateWinds(self):
        """surprise: rotates the winds"""
        self.rotated += 1
        if self.rotated == 4:
            if self.roundsFinished < 4:
                self.roundsFinished += 1
            self.rotated = 0
        if self.gameOver():
            endtime = datetime.datetime.now().replace(microsecond=0).isoformat()
            Query('UPDATE game set endtime = "%s" where id = :%d' % \
                  (endtime, self.gameid))
            self.gameid = 0
        else:
            winds = [player.wind.name for player in self.players]
            winds = winds[3:] + winds[0:3]
            for idx,  newWind in enumerate(winds):
                self.players[idx].wind.setWind(newWind,  self.roundsFinished)
            if 0 < self.roundsFinished < 4 and self.rotated == 0:
                self.exchangeSeats()

    def payHand(self):
        """pay the scores"""
        for player in self.players:
            if player.hand(self).hasAction('payforall'):
                if self.winner.wind.name == 'E':
                    score = self.winner.score * 6
                else:
                    score = self.winner.score * 4
                player.getsPayment(-score)
                self.winner.getsPayment(score)
                return

        for idx1, player1 in enumerate(self.players):
            for idx2, player2 in enumerate(self.players):
                if idx1 != idx2:
                    if player1.wind.name == 'E' or player2.wind.name == 'E':
                        efactor = 2
                    else:
                        efactor = 1
                    if player2 != self.winner:
                        player1.getsPayment(player1.score * efactor)
                    if player1 != self.winner:
                        player1.getsPayment(-player2.score * efactor)

    def lastTile(self):
        """compile hand info into  a string as needed by the scoring engine"""
        cbLastTile = self.scoringDialog.cbLastTile
        idx = cbLastTile.currentIndex()
        if idx >= 0:
            return bytes(cbLastTile.itemData(idx).toString())
        return ''

    def lastMeld(self):
        """compile hand info into  a string as needed by the scoring engine"""
        cbLastMeld = self.scoringDialog.cbLastMeld
        idx = cbLastMeld.currentIndex()
        if idx >= 0:
            return bytes(cbLastMeld.itemData(idx).toString())
        return ''

class About(object):
    """we need persistent data but do not want to spoil global name space"""
    def __init__(self):
        self.appName     = bytes("kmj")
        self.catalog     = bytes('')
        self.homePage    = bytes('http://www.kde-apps.org/content/show.php/kmj?content=103206')
        self.bugEmail    = bytes('wolfgang@rohdewald.de')
        self.version     = bytes('0.3.2')
        self.programName = ki18n ("kmj")
        self.description = ki18n ("kmj - computes scorings and makes payments among the 4 players")
        self.kmjlicense     = KAboutData.License_GPL
        self.kmjcopyright   = ki18n ("(c) 2008,2009 Wolfgang Rohdewald")
        self.aboutText        = ki18n("This is the classical Mah Jongg for four players. "
            "If you are looking for the Mah Jongg solitaire please use the "
            "application kmahjongg. Right now this program only allows to "
            "enter the scores, it will then compute the payments and show "
            "the ranking of the players.")

        self.about  = KAboutData (self.appName, self.catalog,
                        self.programName,
                        self.version, self.description,
                        self.kmjlicense, self.kmjcopyright, self.aboutText,
                        self.homePage, self.bugEmail)

