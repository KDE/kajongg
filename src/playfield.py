#!/usr/bin/env python
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

import os
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
    from PyQt4.QtGui import QWidget, QLabel, QTabWidget
    from PyQt4.QtGui import QGridLayout, QVBoxLayout, QHBoxLayout,  QSpinBox
    from PyQt4.QtGui import QDialog, QStringListModel, QListView, QSplitter, QValidator
    from PyQt4.QtGui import QBrush, QIcon, QPixmap, QPainter, QDialogButtonBox
    from PyQt4.QtGui import QSizePolicy,  QComboBox,  QCheckBox, QTableView, QScrollBar
    from PyQt4.QtSql import QSqlQueryModel
except ImportError,  e:
    NOTFOUND.append('PyQt4: %s' % e)

try:
    from PyKDE4.kdecore import ki18n, KAboutData
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
    from game import Game,  Players,  Player
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
        return list([x.name for x in self.items])

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
    """show scores of current or last game, even if the last game is
    finished. To achieve this we keep our own reference to game."""
    def __init__(self, field):
        super(ScoreTable, self).__init__(None)
        self.field = field
        self.game = field.game
        self.__game = None
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
        self.state = StateSaver(self, self.splitter)
        self.refresh()

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
        """load the data for this game and this player. Keep parameter list identical with
        ExplainView"""
        if self.field.game:
            # if we have a new game, show that. Otherwise the last one, even if finished
            # (if last game is finished, self.field.game is None)
            self.game = self.field.game
        if not self.game:
            return
        if self.game.finished():
            title = m18n('Final scores for game <numid>%1</numid>' + ' - kmj', self.game.gameid)
        else:
            title = m18n('Scores for game <numid>%1</numid>' + ' - kmj', self.game.gameid)
        self.setWindowTitle(title)
        self.ruleTree.rulesets = list([self.game.ruleset])
        for idx, player in enumerate(self.game.players):
            self.nameLabels[idx].setText(player.name)
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
    def __init__(self, field, parent=None):
        QListView.__init__(self, parent)
        self.setWindowTitle(m18n('Explain Scores') + ' - kmj')
        self.setGeometry(0, 0, 300, 400)
        self.field = field
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
        if self.field.game is None:
            lines.append(m18n('There is no active game'))
        else:
            i18nName = m18n(self.field.game.ruleset.name)
            lines.append(m18n('Ruleset: %1', i18nName))
            lines.append('')
            for playerGUI in self.field.playersGUI:
                player = playerGUI.player
                pLines = []
                if player.hand.tiles:
                    score = player.hand.score
                    total = player.hand.total()
                    pLines = player.hand.explain()
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
        Players.load()
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
            cbName.addItems(Players.allNames.values())
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
                playerName  = Players.allNames[playerId]
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
        unusedNames = set(Players.allNames.values()) - usedNames
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
    def __init__(self, field):
        """selection for this player, tiles are the still available tiles"""
        QDialog.__init__(self, None)
        self.setWindowTitle(m18n("Penalty") + ' - kmj')
        self.field = field
        game = field.game
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
        for player in self.field.players:
            if player in payers:
                amount = -self.spPenalty.value() // len(payers)
            elif player in payees:
                amount = self.spPenalty.value() // len(payees)
            else:
                amount = 0
            player.getsPayment(amount)
            self.game.savePenalty(player, offense, amount)
            self.showBalance()
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
        unusedPlayers = set(self.field.game.losers()) - usedPlayers
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
    def __init__(self, field):
        QWidget.__init__(self, None)
        self.setWindowTitle(m18n('Scoring for this Hand') + ' - kmj')
        self.field = field
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
        for idx, playerGUI in enumerate(field.playersGUI):
            player = playerGUI.player
            self.spValues[idx] = QSpinBox()
            self.nameLabels[idx] = QLabel()
            self.nameLabels[idx].setBuddy(self.spValues[idx])
            self.windLabels[idx] = WindLabel(player.wind, field.game.roundsFinished)
            pGrid.addWidget(self.nameLabels[idx], idx+2, 0)
            pGrid.addWidget(self.windLabels[idx], idx+2, 1)
            pGrid.addWidget(self.spValues[idx], idx+2, 2)
            self.wonBoxes[idx] = QCheckBox("")
            pGrid.addWidget(self.wonBoxes[idx], idx+2, 3)
            self.connect(self.wonBoxes[idx], SIGNAL('clicked(bool)'), self.wonChanged)
            self.connect(self.spValues[idx], SIGNAL('valueChanged(int)'), self.slotInputChanged)
            playerGUI.detailTab = QWidget()
            self.detailTabs.addTab(playerGUI.detailTab,'')
            playerGUI.details = QWidget()
            playerGUI.detailTabLayout = QVBoxLayout(playerGUI.detailTab)
            playerGUI.detailTabLayout.addWidget(playerGUI.details)
            playerGUI.detailTabLayout.addStretch()
            playerGUI.detailsLayout = QVBoxLayout(playerGUI.details)
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
        self.state = StateSaver(self)
        self.loadGame()

    def loadGame(self):
        """reload game"""
        self.clear()
        game = self.field.game
        self.setVisible(game is not None)
        for idx, playerGUI in enumerate(self.field.playersGUI):
            player = playerGUI.player
            for child in playerGUI.manualRuleBoxes:
                child.hide()
                playerGUI.detailsLayout.removeWidget(child)
                del child
            if game:
                self.spValues[idx].setRange(0, game.ruleset.limit)
                self.nameLabels[idx].setText(player.name)
                self.windLabels[idx].wind = player.wind
                self.windLabels[idx].roundsFinished = game.roundsFinished
                self.detailTabs.setTabText(idx, player.name)
                playerGUI.manualRuleBoxes = [RuleBox(x) for x in game.ruleset.manualRules]
                for ruleBox in playerGUI.manualRuleBoxes:
                    playerGUI.detailsLayout.addWidget(ruleBox)
                    self.connect(ruleBox, SIGNAL('clicked(bool)'),
                        self.slotInputChanged)
            playerGUI.refreshManualRules()

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
        dlg = PenaltyDialog(self.field)
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
                newWinner = self.field.players[clicked]
        self.field.game.winner = newWinner
        for idx in range(4):
            if newWinner != self.field.players[idx]:
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
                for playerGUI in self.field.playersGUI:
                    if ruleBox.parentWidget() != playerGUI.details:
                        for pBox in playerGUI.manualRuleBoxes:
                            if pBox.rule.name == ruleBox.rule.name:
                                pBox.setChecked(False)

        newState = bool(self.field.game and self.field.game.winner and self.field.winnerGUI().handBoard.allTiles())
        self.lblLastTile.setEnabled(newState)
        self.cbLastTile.setEnabled(newState)
        self.lblLastMeld.setEnabled(newState)
        self.cbLastMeld.setEnabled(newState)
        for playerGUI in self.field.playersGUI:
            playerGUI.refreshManualRules()

    def clear(self):
        """prepare for next hand"""
        for idx, playerGUI in enumerate(self.field.playersGUI):
            playerGUI.handBoard.clear()
            self.spValues[idx].clear()
            self.wonBoxes[idx].setChecked(False)
            playerGUI.player.payment = 0
            playerGUI.player.total = 0
            playerGUI.player.hand = None
        self.draw.setChecked(False)
        self.updateManualRules()

#        self.fillLastTileCombo()
        if self.field.game is None:
            self.hide()
        else:
            for idx, player in enumerate(self.field.players):
                self.windLabels[idx].setPixmap(WINDPIXMAPS[(player.wind,
                            player.wind == WINDS[self.field.game.roundsFinished])])
            self.computeScores()
            self.spValues[0].setFocus()

    def computeScores(self):
        """if tiles have been selected, compute their value"""
        if self.field.game.finished():
            self.hide()
            return
        for idx, playerGUI in enumerate(self.field.playersGUI):
            player = playerGUI.player
            if playerGUI.handBoard.allTiles():
                self.spValues[idx].blockSignals(True) # we do not want that change to call computeScores again
                self.wonBoxes[idx].blockSignals(True) # we do not want that change to call computeScores again
                self.spValues[idx].setEnabled(False)
                for loop in range(10):
                    player.hand = playerGUI.hand()
                    self.wonBoxes[idx].setVisible(player.hand.maybeMahjongg())
                    if not self.wonBoxes[idx].isVisibleTo(self) and self.wonBoxes[idx].isChecked():
                        self.wonBoxes[idx].setChecked(False)
                        playerGUI.refreshManualRules()
                        continue
                    if player.total == player.hand.total():
                        break
                    player.total = player.hand.total()
                    self.spValues[idx].setValue(player.total)
                    playerGUI.refreshManualRules()
                self.spValues[idx].blockSignals(False)
                self.wonBoxes[idx].blockSignals(False)
            else:
                player.hand = playerGUI.hand()
                if not self.spValues[idx].isEnabled():
                    self.spValues[idx].clear()
                    player.total = 0
                    self.spValues[idx].setEnabled(True)
                self.wonBoxes[idx].setVisible(player.total >= self.field.game.ruleset.minMJPoints)
            if not self.wonBoxes[idx].isVisibleTo(self) and player is self.field.game.winner:
                self.field.game.winner = None
        if self.field.explainView:
            self.field.explainView.refresh()

    def fillLastTileCombo(self):
        """fill the drop down list with all possible tiles.
        If the drop down had content before try to preserve the
        current index. Even if the tile changed state meanwhile."""
        if self.field.game is None:
            return
        showTilePairs = set()
        winnerTiles = []
        if self.field.game.winner:
            winnerTiles = self.field.winnerGUI().handBoard.allTiles()
            winnerMelds = [m for m in self.field.winnerGUI().hand().melds if len(m) < 4]
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
                    painter.end()        # otherwise moving a meld to another player segfaults.
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
            if not self.field.game.winner:
                return
            if self.cbLastTile.count() == 0:
                return
            lastTile = self.field.lastTile()
            winnerMelds = [m for m in self.field.winnerGUI().hand().melds if len(m) < 4 \
                and lastTile.lower() in m.contentPairs or lastTile[0].upper()+lastTile[1] in m.contentPairs]
            assert len(winnerMelds)
            boardTiles = self.field.winnerGUI().handBoard.allTiles()
            # TODO: the winner board might be rotated giving us a wrong lightSource.
            # the best solution would be a boolean attribute Board.showTileBorders, also good
            # for netbooks
            tileset = self.field.winnerGUI().handBoard.tileset
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
                if 'E' in self.field.walls.lightSource:
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
                self.field.players[idx].total = self.spValues[idx].value()
                break
        self.updateManualRules()
        self.computeScores()
        self.validate()

    def validate(self):
        """update the status of the OK button"""
        valid = True
        game = self.field.game
        if game.winner and game.winner.total < game.ruleset.minMJPoints:
            valid = False
        elif not game.winner and not self.draw.isChecked():
            valid = False
        self.btnSave.setEnabled(valid)

class PlayerGUI(object):
    def __init__(self, player,  field,  wall):
        self.player = player
        self.field = field
        self.wall = wall
        self.wallWind = PlayerWind(player.wind, field.windTileset, 0, wall)
        self.wallWind.hide()
        self.wallLabel = field.centralScene.addSimpleText('')
        self.manualRuleBoxes = []
        self.handBoard = HandBoard(self)
        self.handBoard.setPos(yHeight= 1.5)

    def refresh(self):
        self.wallLabel.setVisible(self.field.game is not None)
        self.wallWind.setVisible(self.field.game is not None)

    def refreshManualRules(self):
        """update status of manual rules"""
        if self.field.game:
            hand = self.hand()
            self.player.hand = hand
            if hand:
                currentScore = hand.score
                for box in self.manualRuleBoxes:
                    if box.rule not in [x[0] for x in hand.usedRules]:
                        applicable = hand.ruleMayApply(box.rule)
                        applicable &= bool(box.rule.actions) or self.hand(box.rule).score != currentScore
                        box.setApplicable(applicable)

    def __mjString(self):
        """compile hand info into  a string as needed by the scoring engine"""
        game = self.field.game
        assert game
        winds = self.player.wind.lower() + 'eswn'[game.roundsFinished]
        wonChar = 'm'
        if self.player == game.winner:
            wonChar = 'M'
        lastSource = 'd'
        lastTile = self.field.lastTile()
        if len(lastTile) and lastTile[0].isupper():
            lastSource = 'w'
        for box in self.manualRuleBoxes:
            if box.isChecked() and 'lastsource' in box.rule.actions:
                if lastSource != '1':
                    # this defines precedences for source of last tile
                    lastSource = box.rule.actions['lastsource']
        return ''.join([wonChar, winds, lastSource])

    def __lastString(self):
        """compile hand info into  a string as needed by the scoring engine"""
        game = self.field.game
        if game is None:
            return ''
        if self.player != game.winner:
            return ''
        return 'L%s%s' % (game.field.lastTile(), game.field.lastMeld())

    def hand(self, singleRule=None):
        """returns a Hand object, using a cache"""
        game = self.field.game
        assert game
        string = ' '.join([self.handBoard.scoringString(), self.__mjString(), self.__lastString()])
        rules = list(x.rule for x in self.manualRuleBoxes if x.isChecked())
        if singleRule:
            rules.append(singleRule)
        cacheKey = (string, '&&'.join([rule.name for rule in rules]))
        if Player.cachedRulesetId != game.ruleset.rulesetId:
            Player.handCache.clear()
            Player.cachedRulesetId = game.ruleset.rulesetId
        if cacheKey in Player.handCache:
            return Player.handCache[cacheKey]
        result = Hand(game.ruleset, string, rules)
        Player.handCache[cacheKey] = result
        return result


class PlayField(KXmlGuiWindow):
    """the main window"""

    def __init__(self):
        # see http://lists.kde.org/?l=kde-games-devel&m=120071267328984&w=2
        self.__game = None
        self.ignoreResizing = 1
        super(PlayField, self).__init__()
        Preferences() # defines PREF
        board.PLAYFIELD = self
        self.background = None
        self.settingsChanged = False

        self.playerWindow = None
        self.scoreTable = None
        self.explainView = None
        self.scoringDialog = None
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

    def handSelectorChanged(self, handBoard):
        """update all relevant dialogs"""
        self.scoringDialog.fillLastTileCombo()
        self.scoringDialog.computeScores()
        if self.explainView:
            self.explainView.refresh()

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
        scene.field = self
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
# TODO:       self.gameOverLabel = QLabel(m18n('The game is over!'))
        scene.addItem(self.selectorBoard)

        self.connect(scene, SIGNAL('tileClicked'), self.tileClicked)

        self.windTileset = Tileset(util.PREF.windTilesetName)
        self.players = Players([Player(idx) for idx in range(4)])
        self.playersGUI = list([PlayerGUI(self.players[idx],  self, self.walls[idx]) for idx in range(4)])

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
                    targetWind = WINDS[moveCommands.index(wind)]
                    for p in self.playersGUI:
                        if p.player.wind == targetWind:
                            p.handBoard.receive(tile, self.centralView, lowerHalf=mod & Qt.ShiftModifier)
                if not currentBoard.allTiles():
                    self.centralView.scene().setFocusItem(receiver.focusTile)
            return
        if key == Qt.Key_Tab:
            tabItems = [self.selectorBoard]
            tabItems.extend(list(p.handBoard for p in self.playersGUI if p.handBoard.focusTile))
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
        if not self.playerWindow:
            self.playerWindow = PlayerList(self)
        self.playerWindow.show()

    def networkGame(self):
        """connect to a game server"""
        pass

    def selectGame(self):
        """show all games"""
        gameSelector = Games(self)
        if gameSelector.exec_():
            selected = gameSelector.selectedGame # also fills self.players
            if selected is not None:
                newGame = Game(self.players,  field=self,  gameid=selected)
                if newGame is not None:
                    self.game = newGame
                    self.actionScoreTable.setChecked(True)
            else:
                newGame = self.newGame()
                if newGame is not None:
                    self.game = newGame
        return self.game

    def __decorateWalls(self):
        if self.game is None:
            for playerGUI in self.playersGUI:
                playerGUI.wallWind.hide()
            return
        for idx, playerGUI in enumerate(self.playersGUI):
            player = playerGUI.player
            wall = self.walls[idx]
            center = wall.center()
            name = playerGUI.wallLabel
            name.setText(player.name)
            name.resetTransform()
            name.scale(3, 3)
            if wall.rotation == 180:
                rotateCenter(name, 180)
            name.setParentItem(wall)
            nameRect = QRectF()
            nameRect.setSize(name.mapToParent(name.boundingRect()).boundingRect().size())
            name.setPos(center - nameRect.center())
            name.setZValue(99999999999)
            if self.tileset.desktopFileName == 'jade':
                color = Qt.white
            else:
                color = Qt.black
            name.setBrush(QBrush(QColor(color)))
            windTile = playerGUI.wallWind
            windTile.setWind(player.wind,  self.game.roundsFinished)
            windTile.resetTransform()
            rotateCenter(windTile,  -wall.rotation)
            windTile.setPos(center.x()*1.66, center.y()-windTile.rect().height()/2.5)
            windTile.setZValue(99999999999)

    def scoreGame(self):
        """score a local game"""
        if self.selectGame():
            #self.scoringOnly = True
            self.actionScoring.setChecked(True)

    def localGame(self):
        """play a local game"""
        if self.selectGame():
            pass
            #self.scoringOnly = False

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
            self.__decorateWalls()
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

    def newGame(self):
        """asks user for players and ruleset for a new game and returns that new game"""
        Players.load() # we want to make sure we have the current definitions
        selectDialog = SelectPlayers(self.game)
        # if we have a selectable ruleset with the same name as the last used ruleset
        # use that selectable ruleset. We do not want to use the exact same last used
        # ruleset because we might have made some fixes to the ruleset meanwhile
        qData = Query("select name from usedruleset order by lastused desc").data
        if qData:
            lastUsed = qData[0][0]
            if lastUsed in selectDialog.cbRuleset.names():
                selectDialog.cbRuleset.currentName = lastUsed
        if not selectDialog.exec_():
            return
        # initialise the four winds with the first four players:
        for idx, player in enumerate(self.players):
            player.name = selectDialog.names[idx]
            player.nameid = Players.allIds[player.name]
            player.wind = WINDS[idx]
            player.balance = 0
        return Game(self.players,  field=self, ruleset=selectDialog.cbRuleset.current)

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

    @staticmethod
    def __windOrder(p):
        return 'ESWN'.index(p.player.wind)

    def saveHand(self):
        """save hand to data base, update score table and balance in status line"""
        self.game.saveHand()
        self.showBalance()
        if self.game.finished():
            self.game = None
        else:
            if self.game.rotated == 0:
                # players may have swapped seats but we want ESWN order
                # in the scoring dialog
                handBoards = list([p.handBoard for p in self.playersGUI])
                self.playersGUI.sort(key=PlayField.__windOrder)
                for idx,  p in enumerate(self.playersGUI):
                    p.handBoard = handBoards[idx]
        self.scoringDialog.loadGame()
        self.__decorateWalls()

    @apply
    def game():
        """the currently show game in the GUI"""
        def fget(self):
            return self.__game
        def fset(self, game):
            if self.__game != game:
                self.__game = game
                wallIndex = game.rotated % 4 if game else None
                self.walls.build(self.tiles, wallIndex,  8)
                self.selectorBoard.setEnabled(game is not None)
                self.centralView.scene().setFocusItem(self.selectorBoard.childItems()[0])
                self.__decorateWalls()
                self.showBalance()
                self.actionScoring.setEnabled(game is not None and game.roundsFinished < 4)
                if game is None:
                    self.actionScoring.setChecked(False)
                for playerGUI in self.playersGUI:
                    playerGUI.handBoard.clear()
                    playerGUI.handBoard.setEnabled(True)
                if self.scoringDialog:
                    self.scoringDialog.loadGame()
                for view in [self.explainView,  self.scoreTable]:
                    if view:
                        view.refresh()
                for playerGUI in self.playersGUI:
                    playerGUI.refresh()
        return property(**locals())

    def changeAngle(self):
        """change the lightSource"""
        oldIdx = LIGHTSOURCES.index(self.walls.lightSource)
        newLightSource = LIGHTSOURCES[(oldIdx + 1) % 4]
        self.walls.lightSource = newLightSource
        self.selectorBoard.lightSource = newLightSource
        self.__decorateWalls()
        self._adjustView()
        scoringDialog = self.actionScoring.data().toPyObject()
        if isinstance(scoringDialog, ScoringDialog):
            scoringDialog.computeScores()

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

    def winnerGUI(self):
        for idx in range(4):
            if self.game.winner == self.players[idx]:
                return self.playersGUI[idx]
        return None

    def askSwap(self, swappers):
        """ask the user if two players should change seats"""
        # do not make this a staticmethod because we do not want
        # to import PlayField in game.py
        mbox = QMessageBox()
        mbox.setWindowTitle(m18n("Swap Seats") + ' - kmj')
        mbox.setText("By the rules, %s and %s should now exchange their seats. " % \
            (swappers[0].name, swappers[1].name))
        yesAnswer = QPushButton("&Exchange")
        mbox.addButton(yesAnswer, QMessageBox.YesRole)
        noAnswer = QPushButton("&Keep seat")
        mbox.addButton(noAnswer, QMessageBox.NoRole)
        mbox.exec_()
        return mbox.clickedButton() == yesAnswer

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

