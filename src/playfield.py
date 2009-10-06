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
        QEvent, QMetaObject, QSize, PYQT_VERSION_STR
    from PyQt4.QtGui import QColor, QPushButton,  QMessageBox, QPixmapCache
    from PyQt4.QtGui import QWidget, QLabel, QTabWidget, QStyleOptionGraphicsItem
    from PyQt4.QtGui import QGridLayout, QVBoxLayout, QHBoxLayout,  QSpinBox
    from PyQt4.QtGui import QDialog, QStringListModel, QListView, QSplitter, QValidator
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
    from board import PlayerWind, WindLabel, Walls,  FittingView,  ROUNDWINDCOLOR, \
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

    @apply
    def items():
        """combo box items"""
        def fget(self):
            return [self.itemData(idx).toPyObject() for idx in range(self.count())]
        def fset(self, items):
            self.clear()
            for item in items:
                self.addItem(m18n(item.name), QVariant(item))
        return property(**locals())

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

    @apply
    def current():
        """current item"""
        def fget(self):
            return self.itemData(self.currentIndex()).toPyObject()
        def fset(self, item):
            newIdx = self.findItem(item)
            if newIdx < 0:
                raise Exception('%s not found in ListComboBox' % item.name)
            self.setCurrentIndex(newIdx)
        return property(**locals())

    @apply
    def currentName():
        """name of current item"""
        def fget(self):
            return self.itemData(self.currentIndex()).toPyObject().name
        def fset(self, name):
            newIdx = self.findName(name)
            if newIdx < 0:
                raise Exception('%s not found in ListComboBox' % name)
            self.setCurrentIndex(newIdx)
        return property(**locals())

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
        self.__game = None
        self.__gameId = None
        self.setAttribute(Qt.WA_AlwaysShowToolTips)
        self.__tableFields = ['prevailing', 'won', 'wind',
                                'points', 'payments', 'balance', 'hand', 'manualrules']
        self.scoreModel = [ScoreModel(self) for idx in range(4)]
        self.scoreView = [QTableView(self)  for idx in range(4)]
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
        self.nameLabels = [None] * 4
        for idx in range(4):
            vlayout = QVBoxLayout()
            playerLayout.addLayout(vlayout)
            nLabel = QLabel()
            self.nameLabels[idx] = nLabel
            nLabel.setAlignment(Qt.AlignCenter)
            view = self.scoreView[idx]
            vlayout.addWidget(self.nameLabels[idx])
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
        self.ruleTree = RuleTreeView(list([]), m18n('Used Rules'))
        self.splitter.addWidget(self.ruleTree)
        self.connect(self.hscroll,
            SIGNAL('valueChanged(int)'),
            self.updateDetailScroll)
        self.connect(self.splitter, SIGNAL('splitterMoved(int,int)'), self.splitterMoved)
        self.game = game
        self.state = StateSaver(self, self.splitter)

    @apply
    def game():
        def fget(self):
            return self.__game
        def fset(self, game):
            if self.__gameId != game.gameid:
                self.__game = game
                self.__gameId = game.gameid
                for idx, player in enumerate(game.players):
                    self.nameLabels[idx].setText(player.name)
                self.ruleTree.rulesets = list([game.ruleset])
                self.refresh()
        return property(**locals())
            
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

    def refresh(self):
        """load the data for this game and this player"""
        self.setWindowTitle(m18n('Scores for game <numid>%1</numid>' + ' - kmj', self.game.gameid))
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
                pLines = []
                if player.handBoard.allTiles():
                    hand = player.hand(self.game)
                    score = hand.score
                    total = hand.total()
                    pLines = hand.explain()
                    pLines = [m18n('Computed scoring for %1:', player.name)] + pLines
                    pLines.append(m18n('Total for %1: %2 base points, %3 doubles, %4 points',
                        player.name, score.points, score.doubles, total))
                elif player.total:
                    pLines.append(m18n('Manual score for %1: %2 points',  player.name, player.total))
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
            grid.addWidget(WindLabel(wind), idx+1, 0)
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

class PenaltyBox(QSpinBox):
    """with its own validator, we only accept multiples of parties"""
    def __init__(self, parties, parent=None):
        QSpinBox.__init__(self, parent)
        self.parties = parties
        
    def validate(self, input, pos):
        result, newPos = QSpinBox.validate(self, input, pos)
        if result == QValidator.Acceptable:
            if int(input) % self.parties != 0:
                result = QValidator.Intermediate
        return (result, newPos)
        
    def stepBy(self, steps):
        """this does not go thru the validator..."""
        newExpected = self.value() + steps * self.singleStep()
        remainder = newExpected % self.parties
        self.setValue(newExpected - remainder)
        self.selectAll() 
        
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
        self.setWindowTitle(m18n("Penalty") + ' - kmj')
        self.game = game
        grid = QGridLayout(self)
        lblOffense = QLabel(m18n('Offense:'))
        crimes = list([x for x in game.ruleset.penaltyRules if not ('absolute' in x.actions and game.winner)])
        self.cbCrime = ListComboBox(crimes)
        lblOffense.setBuddy(self.cbCrime)
        grid.addWidget(lblOffense, 0, 0)
        grid.addWidget(self.cbCrime, 0, 1, 1, 4)
        lblPenalty = QLabel(m18n('Total Penalty'))
        self.spPenalty = PenaltyBox(2)
        self.spPenalty.setRange(0, 9999)
        lblPenalty.setBuddy(self.spPenalty)
        self.prevPenalty = 0
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
            self.connect(player, SIGNAL('currentIndexChanged(int)'), self.playerChanged)
        self.connect(self.spPenalty, SIGNAL('valueChanged(int)'), self.penaltyChanged)
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
        payers = int(offense.actions.get('payers', 1))
        payees = int(offense.actions.get('payees', 1))
        self.spPenalty.setValue(-offense.score.value)
        self.spPenalty.parties = max(payers, payees)
        self.spPenalty.setSingleStep(10 )
        self.lblUnits.setText(Score.unitName(offense.score.unit))
        for pList, count in ((self.payers, payers), (self.payees, payees)):
            for idx, payer in enumerate(pList):
                payer.setVisible(idx<count)
                payer.lblPayment.setVisible(idx<count)
                if idx < count:
                    payer.lblPayment.setText('%d %s' % (
                        -offense.score.value//count,  Score.unitName(offense.score.unit)))
        self.playerChanged()
        
    def penaltyChanged(self):
        """total has changed, update payments"""
        offense = self.cbCrime.current
        penalty = self.spPenalty.value()
        payers = int(offense.actions.get('payers', 1))
        payees = int(offense.actions.get('payees', 1))
        payerAmount = -penalty // payers
        payeeAmount = penalty // payees
        for pList, amount  in [(self.payers, payerAmount), (self.payees, payeeAmount)]:
            for player in pList:
                if player.isVisible():
                    player.lblPayment.setText('%d %s' % (
                        amount,  Score.unitName(offense.score.unit)))
                else:
                    player.lblPayment.setText('')
        self.prevPenalty = penalty

class ScoringDialog(QWidget):
    """a dialog for entering the scores"""
    def __init__(self, game):
        QWidget.__init__(self, None)
        self.setWindowTitle(m18n('Scoring for this Hand') + ' - kmj')
        self.__game = None
        self.__gameid = None # TODO: remove this again after GUI separation of class Game
        self.nameLabels = [None] * 4
        self.spValues = [None] * 4
        self.windLabels = [None] * 4
        self.wonBoxes = [None] * 4
        self.__tilePixMaps = []
        self.__meldPixMaps = []
        grid = QGridLayout(self)
        pGrid = QGridLayout()
        grid.addLayout(pGrid, 0, 0, 2, 1)
        pGrid.addWidget(QLabel(m18nc('kmj', "Player")), 0, 0)
        pGrid.addWidget(QLabel(m18nc('kmj',  "Wind")), 0, 1)
        pGrid.addWidget(QLabel(m18nc('kmj', 'Score')), 0, 2)
        pGrid.addWidget(QLabel(m18n("Winner")), 0, 3)
        self.detailTabs = QTabWidget()
        pGrid.addWidget(self.detailTabs, 0, 4, 8, 1)
        for idx, player in enumerate(game.players):
            self.spValues[idx] = QSpinBox()
            self.nameLabels[idx] = QLabel()
            self.nameLabels[idx].setBuddy(self.spValues[idx])
            self.windLabels[idx] = WindLabel(player.wind.name, game.roundsFinished)
            pGrid.addWidget(self.nameLabels[idx], idx+2, 0)
            pGrid.addWidget(self.windLabels[idx], idx+2, 1)
            pGrid.addWidget(self.spValues[idx], idx+2, 2)
            self.wonBoxes[idx] = QCheckBox("")
            pGrid.addWidget(self.wonBoxes[idx], idx+2, 3)
            self.connect(self.wonBoxes[idx], SIGNAL('clicked(bool)'), self.wonChanged)
            self.connect(self.spValues[idx], SIGNAL('valueChanged(int)'), self.slotInputChanged)
            player.detailTab = QWidget()
            self.detailTabs.addTab(player.detailTab,'')
            player.detailGrid = QVBoxLayout(player.detailTab)
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
        self.comboTilePairs = set()
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
        btnBox = QHBoxLayout()
        btnBox.addWidget(self.btnPenalties)
        btnBox.addWidget(self.btnSave)
        pGrid.addLayout(btnBox, 8, 4)
        self.spValues[0].setFocus()
        self.game = game
        self.state = StateSaver(self)

    @apply
    def game():
        def fget(self):
            return self.__game
        def fset(self, game):
            if self.__gameid and  self.__gameid != game.gameid:
                self.clearScoringDialog()
            for idx, player in enumerate(game.players):
                self.spValues[idx].setRange(0, game.ruleset.limit)
                self.nameLabels[idx].setText(player.name)
                self.windLabels[idx].wind = player.wind.name
                self.windLabels[idx].roundsFinished = game.roundsFinished
                self.detailTabs.setTabText(idx,player.name)
                for child in player.manualRuleBoxes:
                    child.hide()
                    player.detailGrid.removeWidget(child)
                    del child
                player.manualRuleBoxes = [RuleBox(x) for x in game.ruleset.manualRules]
                for idx,ruleBox in enumerate(player.manualRuleBoxes):
                    player.detailGrid.insertWidget(idx,ruleBox) # insert above stretchitem
                    self.connect(ruleBox, SIGNAL('clicked(bool)'),
                        self.slotInputChanged)
                if not self.__game:
                    player.detailGrid.addStretch()            
                player.refreshManualRules(game)
            self.__game = game
            self.__gameid = game.gameid
        return property(**locals())
        
    def show(self):
        """only now compute content"""
        self.slotInputChanged()
        QWidget.show(self)

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
        dlg = PenaltyDialog(self.game)
        dlg.exec_()

    def slotLastTile(self):
        """called when the last tile changes"""
        self.fillLastMeldCombo()

    def closeEvent(self, event):
        """the user pressed ALT-F4"""
        self.hide()
        event.ignore()
        self.emit(SIGNAL('scoringClosed()'))

    def clickedPlayerIdx(self, checkbox):
        """the player whose box has been clicked"""
        for idx in range(4): #,player in self.game.players:
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
                for player in self.game.players:
                    if ruleBox.parentWidget() != player.detailTab:
                        for pBox in player.manualRuleBoxes:
                            if pBox.rule.name == ruleBox.rule.name:
                                pBox.setChecked(False)

        newState = bool(self.game.winner and self.game.winner.handBoard.allTiles())
        self.lblLastTile.setEnabled(newState)
        self.cbLastTile.setEnabled(newState)
        self.lblLastMeld.setEnabled(newState)
        self.cbLastMeld.setEnabled(newState)
        for player in self.game.players:
            player.refreshManualRules(self.game)

    def clearScoringDialog(self):
        """prepare for next hand"""
        self.game.winner = None
        for idx, player in enumerate(self.game.players):
            player.handBoard.clear()
            self.spValues[idx].clear()
            self.wonBoxes[idx].setChecked(False)
            player.payment = 0
            player.total = 0
        self.draw.setChecked(False)
        self.updateManualRules()

        self.fillLastTileCombo()
        if self.game.gameOver():
            self.hide()
        else:
            for idx, player in enumerate(self.game.players):
                self.windLabels[idx].setPixmap(WINDPIXMAPS[(player.wind.name,
                            player.wind.name == WINDS[self.game.roundsFinished])])
            self.computeScores()
            self.spValues[0].setFocus()

    def computeScores(self):
        """if tiles have been selected, compute their value"""
        if self.game.gameOver():
            self.hide()
            return
        for idx, player in enumerate(self.game.players):
            if player.handBoard.allTiles():
                self.spValues[idx].blockSignals(True) # we do not want that change to call computeScores again
                self.wonBoxes[idx].blockSignals(True) # we do not want that change to call computeScores again
                self.spValues[idx].setEnabled(False)
                for loop in range(10):
                    hand = player.hand(self.game)
                    self.wonBoxes[idx].setVisible(hand.maybeMahjongg())
                    if not self.wonBoxes[idx].isVisibleTo(self) and self.wonBoxes[idx].isChecked():
                        self.wonBoxes[idx].setChecked(False)
                        player.refreshManualRules(self.game)
                        continue
                    if player.total == hand.total():
                        break
                    self.spValues[idx].setValue(hand.total())
                    player.total = hand.total()
                    player.refreshManualRules(self.game)
                self.spValues[idx].blockSignals(False)
                self.wonBoxes[idx].blockSignals(False)
            else:
                if not self.spValues[idx].isEnabled():
                    self.spValues[idx].clear()
                    player.total = 0
                    self.spValues[idx].setEnabled(True)
                self.wonBoxes[idx].setVisible(player.total >= self.game.ruleset.minMJPoints)
            if not self.wonBoxes[idx].isVisibleTo(self) and player is self.game.winner:
                self.game.winner = None
        if self.game.explainView:
            self.game.explainView.refresh()

    def fillLastTileCombo(self):
        """fill the drop down list with all possible tiles.
        If the drop down had content before try to preserve the
        current index. Even if the tile changed state meanwhile."""
        showTilePairs = set()
        winnerTiles = []
        if self.game.winner:
            winnerTiles = self.game.winner.handBoard.allTiles()
            winnerMelds = [m for m in self.game.winner.hand(self.game).melds if len(m) < 4]
            pairs = []
            for meld in winnerMelds:
                pairs.extend(meld.contentPairs)
            for tile in winnerTiles:
                if tile.content in pairs and not tile.isBonus():
                    showTilePairs.add(tile.content)
        if self.comboTilePairs == showTilePairs:
            return
        self.cbLastTile.blockSignals(True) # we only want to emit the changed signal once
        try:
            self.comboTilePairs = showTilePairs
            idx = self.cbLastTile.currentIndex()
            if idx < 0: 
                idx = 0
            indexedTile = str(self.cbLastTile.itemData(idx).toPyObject())
            restoredIdx = None
            self.cbLastTile.clear()
            QPixmapCache.clear()
            self.__tilePixMaps = []
            pmSize = None
            shownTiles = set()
            for tile in winnerTiles:
                if tile.content in showTilePairs and tile.content not in shownTiles:
                    shownTiles.add(tile.content)
                    if not pmSize:
                        pmSize = winnerTiles[0].tileset.faceSize
                        pmSize = QSize(pmSize.width() * 0.5, pmSize.height() * 0.5)
                    pixMap = QPixmap(pmSize)
                    pixMap.fill(Qt.transparent)
                    self.__tilePixMaps.append(pixMap)
                    painter = QPainter(pixMap)
                    faceSize = tile.tileset.faceSize
                    painter.scale(pmSize.width() / faceSize.width(), pmSize.height() / faceSize.height())
		    painter.translate(-tile.facePos())
		    tile.paintAll(painter)
                    painter.end()	 # otherwise moving a meld to another player segfaults.
                                         # why exactly do we need this? Because python defers deletion?
                                         # and why is it not needed in fillLastMeldCombo?
                    self.cbLastTile.setIconSize(pixMap.size())
                    self.cbLastTile.addItem(QIcon(pixMap), '', QVariant(tile.content))
                    if indexedTile == tile.content:
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
        finally:
            self.cbLastTile.blockSignals(False)
            self.cbLastTile.emit(SIGNAL("currentIndexChanged(int)"), 0)
               

    def fillLastMeldCombo(self):
# TODO: if only one, make it disabled. if more than one, set currentItem to -1
# and when saving ensure a meld is selected here
        """fill the drop down list with all possible melds.
        If the drop down had content before try to preserve the
        current index. Even if the meld changed state meanwhile."""
        self.cbLastMeld.blockSignals(True) # we only want to emit the changed signal once
        try:
            idx = self.cbLastMeld.currentIndex()
            if idx < 0: 
                idx = 0
            indexedMeld = str(self.cbLastMeld.itemData(idx).toPyObject())
            restoredIdx = None
            self.cbLastMeld.clear()
            self.__meldPixMaps = []
            if not self.game.winner:
                return
            if self.cbLastTile.count() == 0:
                return
            lastTile = self.game.lastTile()
            allMelds =  [m for m in self.game.winner.hand(self.game).melds]
            winnerMelds = [m for m in self.game.winner.hand(self.game).melds if len(m) < 4 \
                and lastTile.lower() in m.contentPairs or lastTile[0].upper()+lastTile[1] in m.contentPairs]
            assert len(winnerMelds)
            boardTiles = self.game.winner.handBoard.allTiles()
            # TODO: the winner board might be rotated giving us a wrong lightSource. 
            # the best solution would be a boolean attribute Board.showTileBorders, also good
            # for netbooks
            tileset = self.game.winner.handBoard.tileset
            faceWidth = tileset.faceSize.width()
            faceHeight = tileset.faceSize.height()
            iconSize = QSize(faceWidth * 0.5 * 3, faceHeight * 0.5)
            for meld in winnerMelds:
                thisSize = QSize(faceWidth * 0.5 * len(meld), faceHeight * 0.5)
                pixMap = QPixmap(thisSize)
                pixMap.fill(Qt.transparent)
                self.__meldPixMaps.append(pixMap)
                painter = QPainter(pixMap)
                painter.scale(0.5, 0.5)
                pairs = [(idx, pair) for idx, pair in enumerate(meld.contentPairs)]
            # this could be greatly simplified if we could tell Tile to only draw the surface without
            # borders and shadows.
                if 'E' in self.game.walls.lightSource:
                    pairs.reverse()
                    facePos = boardTiles[0].facePos()
                    painter.translate(QPointF((len(pairs) - 1) * faceWidth - facePos.x(), -facePos.y()))
                    step = - faceWidth
                else:
                    painter.translate(-boardTiles[0].facePos())
                    step = faceWidth
                for idx, content in pairs:
                    boardTile = (x for x in boardTiles if x.content == content).next()
                    boardTile.paintAll(painter)
		    painter.translate(QPointF(step, 0.0))
                icon = QPixmap(iconSize)
                icon.fill(Qt.transparent)
                painter = QPainter(icon)
                painter.drawPixmap(0, 0, pixMap)
                self.cbLastMeld.addItem(QIcon(icon), '', QVariant(str(meld.content)))
                saved = str(self.cbLastMeld.itemData(self.cbLastMeld.count()-1).toPyObject())
                if indexedMeld == meld.content:
                    restoredIdx = self.cbLastMeld.count() - 1
            if not restoredIdx and indexedMeld:
                # try again, maybe the meld changed between concealed and exposed
                indexedMeld = indexedMeld.lower()
                for idx in range(self.cbLastMeld.count()):
                    meldContent = str(self.cbLastMeld.itemData(idx).toPyObject())
                    if indexedMeld == meldContent.lower():
                        restoredIdx = idx
                        if lastTile not in meldContent:
                           lastTile = lastTile.swapcase()
                           assert lastTile in meldContent
                           self.cbLastTile.blockSignals(True) # we want to continue right here
                           idx = self.cbLastTile.findData(QVariant(lastTile))
			   self.cbLastTile.setCurrentIndex(idx) 
                           self.cbLastTile.blockSignals(False)
                        break
            if not restoredIdx:
                restoredIdx = 0
            self.cbLastMeld.setCurrentIndex(restoredIdx)
            self.cbLastMeld.setIconSize(iconSize)
        finally:
            self.cbLastMeld.blockSignals(False)
            self.cbLastMeld.emit(SIGNAL("currentIndexChanged(int)"), 0)

    def slotInputChanged(self):
        """some input fields changed: update"""
        for idx in range(4):
            if self.sender() == self.spValues[idx]:
                self.game.players[idx].total = self.spValues[idx].value()
                break
        self.updateManualRules()
        self.computeScores()
        self.validate()

    def validate(self):
        """update the status of the OK button"""
        valid = True
        if self.game.winner and self.game.winner.total <self.game.ruleset.minMJPoints:
            valid = False
        elif not self.game.winner and not self.draw.isChecked():
            valid = False
        self.btnSave.setEnabled(valid)

class Players(list):
    """a list of players where the player can also be indexed by wind"""
    def __init__(self, players):
        list.__init__(self)
        self.extend(players)
        
    def __getitem__(self, index):
        """allow access by idx or by wind"""
        if isinstance(index, (bytes, str)) and len(index) == 1:
            # bytes for Python 2.6, str for 3.0
            for player in self:
                if player.wind.name == index:
                    return player
            logException(Exception("no player has wind %s" % index))
        return list.__getitem__(self, index)
        
class Player(object):
    """all player related data, GUI and internal together"""
    handCache = dict()
    cachedRulesetId = None
    def __init__(self, wind, scene,  wall):
        self.scene = scene
        self.wall = wall
        self.manualRuleBoxes = []
        self.__proxy = None
        self.nameItem = None
        self.__balance = 0
        self.__payment = 0
        self.nameid = 0
        self.__name = ''
        self.name = ''
        self.wind = PlayerWind(wind, 0, wall)
        self.handBoard = HandBoard(self)
        self.handBoard.setPos(yHeight= 1.5)
        self.total = 0

    def refreshManualRules(self, game):
        """update status of manual rules"""
        hand = self.hand(game)
        currentScore = hand.score
        for box in self.manualRuleBoxes:
            if box.rule not in [x[0] for x in hand.usedRules]:
                applicable = hand.ruleMayApply(box.rule)
                applicable &= bool(box.rule.actions) or self.hand(game, box.rule).score != currentScore
                box.setApplicable(applicable)

    def mjString(self, game):
        """compile hand info into  a string as needed by the scoring engine"""
        winds = self.wind.name.lower() + 'eswn'[game.roundsFinished]
        wonChar = 'm'
        if self == game.winner:
            wonChar = 'M'
        lastSource = 'd'
        lastTile = game.lastTile()
        if len(lastTile) and lastTile[0].isupper():
            lastSource = 'w'
        for box in self.manualRuleBoxes:
            if box.isChecked() and 'lastsource' in box.rule.actions:
                if lastSource != '1':
                    # this defines precedences for source of last tile
                    lastSource = box.rule.actions['lastsource']
        return ''.join([wonChar, winds, lastSource])

    def lastString(self, game):
        """compile hand info into  a string as needed by the scoring engine"""
        if self != game.winner:
            return ''
        return 'L%s%s' % (game.lastTile(), game.lastMeld())

    def hand(self, game, singleRule=None):
        """returns a Hand object, using a cache"""
        if Player.cachedRulesetId != game.ruleset.rulesetId:
           Player.handCache.clear()
           Player.cachedRulesetId = game.ruleset.rulesetId
        string = ' '.join([self.handBoard.scoringString(), self.mjString(game), self.lastString(game)])
        rules = list(x.rule for x in self.manualRuleBoxes if x.isChecked())
	if singleRule:
             rules.append(singleRule)
        cacheKey = (string,'&&'.join([rule.name for rule in rules]))
        if cacheKey in Player.handCache:
            result = Player.handCache[cacheKey]
        else:
            result = Hand(game.ruleset, string, rules)
            Player.handCache[cacheKey] = result
        return result

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

    @apply
    def tileset():
        """places name on wall and sets its color such that it is readable on the wall"""
        def fget(self):
            return self.wall.tileset
        def fset(self, tileset):
            self.placeOnWall()
            if self.nameItem:
                if tileset.desktopFileName == 'jade':
                    color = Qt.white
                else:
                    color = Qt.black
                self.nameItem.setBrush(QBrush(QColor(color)))
        return property(**locals())

    @apply
    def windTileset():
        """setter for windTileset"""
        def fset(self, tileset):
            self.wind.setFaceTileset(tileset)
            self.placeOnWall()
        return property(**locals())

    @apply
    def name():
        """the name of the player"""
        def fget(self):
            return self.__name
        def fset(self, name):
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
        return property(**locals())

    @apply
    def balance():
        """the balance of this player"""
        def fget(self):
            return self.__balance
        def fset(self, balance):
            assert balance == 0
            self.__balance = 0
            self.__payment = 0
        return property(**locals())

    def getsPayment(self, payment):
        """make a payment to this player"""
        self.__balance += payment
        self.__payment += payment

    @apply
    def payment():
        """the payments for the current hand"""
        def fget(self):
            return self.__payment
        def fset(self, payment):
            assert payment == 0
            self.__payment = 0
        return property(**locals())

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
        self.scoreTable = None
        self.explainView = None
        self.scoringDialog = None
        self.allPlayerIds = {}
        self.allPlayerNames = {}
        self.roundsFinished = 0
        self.gameid = 0
        self.handctr = 0
        self.__rotated = None
        self.ruleset = None
        # shift rules taken from the OEMC 2005 rules
        # 2nd round: S and W shift, E and N shift
        self.shiftRules = 'SWEN,SE,WE'
        self.setupUi()
        KStandardAction.preferences(self.showSettings, self.actionCollection())
        self.applySettings()
        self.setupGUI()
        self.retranslateUi()

    def losers(self):
        """the 3 or 4 losers: All players without the winner"""
        return list([x for x in self.players if x is not self.winner])
            
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
            self.scoringDialog.fillLastTileCombo()
            self.scoringDialog.computeScores()
        if self.explainView:
            self.explainView.refresh()

    @apply
    def rotated():
        """changing rotation builds the walls"""
        def fget(self):
            return self.__rotated
        def fset(self, rotated):
            if self.__rotated != rotated:
                self.__rotated = rotated
                self.walls.build(self.tiles, rotated % 4,  8)
        return property(**locals())

    def playerById(self, playerid):
        """lookup the player by id"""
        for player in self.players:
            if player.name == self.allPlayerNames[playerid]:
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
            definition text,
            points text,
            doubles integer,
            limits integer,
            kmjinteger integer,
            kmjstring text,
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
            definition text,
            points text,
            doubles integer,
            limits integer,
            kmjinteger integer,
            kmjstring text,
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
	if PYQT_VERSION_STR != '4.5.2' or data is not None:
            res.setData(QVariant(data))
        return res

    def kmjToggleAction(self, name, icon, shortcut=None, data=None):
        """a checkable action"""
        res = self.kmjAction(name, icon, shortcut=shortcut, data=data)
        res.setCheckable(True)
        self.connect(res, SIGNAL('toggled(bool)'), self.toggleWidget)
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
        self.players = Players([Player(WINDS[idx], self.centralScene, self.walls[idx]) \
            for idx in range(0, 4)])
        self.winner = None
        for player in self.players:
            player.windTileset = self.windTileset
            player.handBoard.selector = self.selectorBoard

        self.setCentralWidget(centralWidget)
        self.centralView.setScene(scene)
        self.centralView.setFocusPolicy(Qt.StrongFocus)
        self.backgroundName = util.PREF.backgroundName
        self._adjustView()
        self.actionScoreGame = self.kmjAction("scoreGame", "draw-freehand", self.scoreGame, Qt.Key_C)
        self.actionLocalGame = self.kmjAction("local", "media-playback-start", self.localGame, Qt.Key_L)
        self.actionLocalGame.setEnabled(False)
        self.actionRemoteGame = self.kmjAction("network", "network-connect", self.networkGame, Qt.Key_N)
        self.actionRemoteGame.setEnabled(False)
        self.actionQuit = self.kmjAction("quit", "application-exit", self.quit, Qt.Key_Q)
        self.actionPlayers = self.kmjAction("players",  "im-user",  self.slotPlayers)
        self.actionScoring = self.kmjToggleAction("scoring", "draw-freehand", shortcut=Qt.Key_S, data=ScoringDialog)
        self.actionScoring.setEnabled(False)
        self.actionAngle = self.kmjAction("angle",  "object-rotate-left",  self.changeAngle, Qt.Key_G)
        self.actionFullscreen = KToggleFullScreenAction(self.actionCollection())
        self.actionFullscreen.setShortcut(Qt.CTRL + Qt.Key_F)
        self.actionFullscreen.setShortcutContext(Qt.ApplicationShortcut)
        self.actionFullscreen.setWindow(self)
        self.actionCollection().addAction("fullscreen", self.actionFullscreen)
        self.connect(self.actionFullscreen, SIGNAL('toggled(bool)'), self.fullScreen)
        self.actionScoreTable = self.kmjToggleAction("scoreTable", "format-list-ordered",
            Qt.Key_T, data=ScoreTable)
        self.actionExplain = self.kmjToggleAction("explain", "applications-education",
            Qt.Key_E, data=ExplainView)
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
                    receiver.receive(tile)
                else:
                    receiver = self.players[WINDS[moveCommands.index(wind)]].handBoard
                    receiver.receive(tile, self.centralView, lowerHalf=mod & Qt.ShiftModifier)
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
        self.actionScoreGame.setText(m18n("&Score Manual Game"))
        self.actionLocalGame.setText(m18n("Play &Local Game"))
        self.actionRemoteGame.setText(m18n("Play &Network Game"))
        self.actionQuit.setText(m18n("&Quit"))
        self.actionPlayers.setText(m18n("&Players"))
        self.actionAngle.setText(m18n("&Change Visual Angle"))
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

    def networkGame(self):
        """connect to a game server"""
        pass

    def selectGame(self):
        """show all games"""
        gameSelector = Games(self)
        result = gameSelector.exec_()
        if  result:
            if gameSelector.selectedGame is not None:
                result = self.loadGame(gameSelector.selectedGame)
            else:
                result = self.newGame()
        if self.scoreTable:
            self.scoreTable.game = self
        if self.scoringDialog:
            self.scoringDialog.game = self
        return result
        
    def scoreGame(self):
        """score a local game"""
        if self.selectGame():
            self.scoringOnly = True
            self.actionScoring.setChecked(True)

    def localGame(self):
        """play a local game"""
        if self.selectGame():
            self.scoringOnly = False

    def _adjustView(self):
        """adjust the view such that exactly the wanted things are displayed
        without having to scroll"""
        view, scene = self.centralView, self.centralScene
        oldRect = view.sceneRect()
        view.setSceneRect(scene.itemsBoundingRect())
        newRect = view.sceneRect()
        if oldRect != newRect:
            view.fitInView(scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    @apply
    def tilesetName():
        def fget(self):
            return self.tileset.desktopFileName
        def fset(self, name):
            self.tileset = Tileset(name)
        return property(**locals())

    @apply
    def backgroundName():
        def fget(self):
            return self.background.desktopFileName
        def fset(self, name):
            """setter for backgroundName"""
            self.background = Background(name)
            self.background.setPalette(self.centralWidget())
            self.centralWidget().setAutoFillBackground(True)
        return property(**locals())

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
        swappers = list(self.players[winds[x]] for x in (0, 1))
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
            return False
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
            player.balance = 0
        self.gameid = self.newGameId()
        self.showBalance()
        if self.explainView:
            self.explainView.refresh()
        self.actionScoring.setEnabled(True)
        return True

    def toggleWidget(self, checked):
        """user has toggled widget visibility with an action"""
        action = self.sender()
        data = action.data().toPyObject()
        if checked:
            if isinstance(data, type):
                data = data(self)
                action.setData(QVariant(data))
                if isinstance(data, ScoringDialog):
                    self.scoringDialog = data
                    self.connect(data.btnSave, SIGNAL('clicked(bool)'), self.saveHand)
                    self.connect(data, SIGNAL('scoringClosed()'), self.scoringClosed)
                elif isinstance(data, ExplainView):
                    self.explainView = data
                elif isinstance(data, ScoreTable):
                    self.scoreTable = data
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
        self.payHand()
        self.saveScores()
        self.rotate()
        if self.scoringDialog:
            self.scoringDialog.clearScoringDialog()

    def saveScores(self):
        """save computed values to data base, update score table and balance in status line"""
        scoretime = datetime.datetime.now().replace(microsecond=0).isoformat()
        cmdList = []
        for player in self.players:
            hand = player.hand(self)
            if player.handBoard.scoringString():
                manualrules = '||'.join(x.name for x, meld in hand.usedRules)
            else:
                manualrules =m18n('Score computed manually')
            cmdList.append("INSERT INTO SCORE "
            "(game,hand,data,manualrules,player,scoretime,won,prevailing,wind,points,payments, balance,rotated) "
            "VALUES(%d,%d,'%s','%s',%d,'%s',%d,'%s','%s',%d,%d,%d,%d)" % \
            (self.gameid, self.handctr, hand.string, manualrules, player.nameid,
                scoretime, int(player == self.winner),
            WINDS[self.roundsFinished], player.wind.name, player.total,
            player.payment, player.balance, self.rotated))
        Query(cmdList)
        self.showBalance()

    def savePenalty(self, player, offense, amount):
        """save computed values to data base, update score table and balance in status line"""
        scoretime = datetime.datetime.now().replace(microsecond=0).isoformat()
        cmdList = []
        hand = player.hand(self)
        cmdList.append("INSERT INTO SCORE "
            "(game,hand,data,manualrules,player,scoretime,won,prevailing,wind,points,payments, balance,rotated) "
            "VALUES(%d,%d,'%s','%s',%d,'%s',%d,'%s','%s',%d,%d,%d,%d)" % \
            (self.gameid, self.handctr, hand.string, offense.name, player.nameid,
                scoretime, int(player == self.winner),
            WINDS[self.roundsFinished], player.wind.name, 0,
            amount, player.balance, self.rotated))
        Query(cmdList)
        self.showBalance()

    def rotate(self):
        """initialise the values for a new hand"""
        if self.winner and self.winner.wind.name != 'E':
            self.rotateWinds()
        self.handctr += 1
        self.walls.build(self.tiles, self.rotated % 4,  8)

    def initGame(self):
        """reset things to empty"""
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
        scoringDialog = self.actionScoring.data().toPyObject()
	if isinstance(scoringDialog, ScoringDialog):
            scoringDialog.computeScores()

    def loadGame(self, game):
        """load game data by game id"""
        qGame = Query("select p0, p1, p2, p3, ruleset from game where id = %d" %game)
        if not qGame.data:
            return False
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
                player.balance = 0
                player.getsPayment(record[2])
                player.wind.setWind(wind,  self.roundsFinished)
            if record[3]:
                self.winner = player
        self.gameid = game
        self.actionScoreTable.setChecked(True)
        self.showBalance()
        self.rotate()
        self.actionScoring.setEnabled(self.roundsFinished < 4)
        if self.explainView:
            self.explainView.refresh()
        return True

    def showBalance(self):
        """show the player balances in the status bar"""
        if self.scoreTable:
                self.scoreTable.refresh()
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
        winner = self.winner
        for player in self.players:
            if player.hand(self).hasAction('payforall'):
                if winner.wind.name == 'E':
                    score = winner.score * 6
                else:
                    score = winner.score * 4
                player.getsPayment(-score)
                winner.getsPayment(score)
                return

        for idx1, player1 in enumerate(self.players):
            for idx2, player2 in enumerate(self.players):
                if idx1 != idx2:
                    if player1.wind.name == 'E' or player2.wind.name == 'E':
                        efactor = 2
                    else:
                        efactor = 1
                    if player2 != winner:
                        player1.getsPayment(player1.total * efactor)
                    if player1 != winner:
                        player1.getsPayment(-player2.total * efactor)

    def lastTile(self):
        """compile hand info into  a string as needed by the scoring engine"""
        if self.scoringDialog:
            cbLastTile = self.scoringDialog.cbLastTile
            idx = cbLastTile.currentIndex()
            if idx >= 0:
                return bytes(cbLastTile.itemData(idx).toString())
        return ''

    def lastMeld(self):
        """compile hand info into  a string as needed by the scoring engine"""
        if self.scoringDialog:
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

