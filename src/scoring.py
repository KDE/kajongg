# -*- coding: utf-8 -*-

"""
Copyright (C) 2008,2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

from PyQt4.QtCore import Qt, QPointF, QVariant, SIGNAL, SLOT, \
    QSize

from PyQt4.QtGui import QColor, QPushButton, QPixmapCache
from PyQt4.QtGui import QWidget, QLabel, QTabWidget
from PyQt4.QtGui import QGridLayout, QVBoxLayout, QHBoxLayout, QSpinBox
from PyQt4.QtGui import QDialog, QStringListModel, QListView, QSplitter, QValidator
from PyQt4.QtGui import QIcon, QPixmap, QPainter, QDialogButtonBox
from PyQt4.QtGui import QSizePolicy, QComboBox, QCheckBox, QTableView, QScrollBar
from PyQt4.QtSql import QSqlQueryModel
from PyKDE4.kdeui import KDialogButtonBox

from genericdelegates import GenericDelegate, IntegerColumnDelegate

from rulesetselector import RuleTreeView
from board import WindLabel, WINDPIXMAPS, ROUNDWINDCOLOR
from util import m18n, m18nc, m18np
from common import WINDS
from statesaver import StateSaver
from query import Query
from scoringengine import Score
from guiutil import ListComboBox

class ScoreModel(QSqlQueryModel):
    """a model for our score table"""
    def __init__(self, parent = None):
        super(ScoreModel, self).__init__(parent)

    def data(self, index, role=None):
        """score table"""
        if role is None:
            role = Qt.DisplayRole
        if role == Qt.BackgroundRole and index.column() == 2:
            prevailing = self.__field(index, 0).toString()
            if prevailing == self.data(index).toString():
                return QVariant(ROUNDWINDCOLOR)
        if role == Qt.BackgroundRole and index.column()==3:
            won = self.__field(index, 1).toInt()[0]
            if won == 1:
                return QVariant(QColor(165, 255, 165))
        if role == Qt.ToolTipRole:
            tooltip = '<br />'.join(str(self.__field(index, 7).toString()).split('||'))
            return QVariant(tooltip)
        return QSqlQueryModel.data(self, index, role)

    def __field(self, index, column):
        """return a field of the column index points to"""
        return self.data(self.index(index.row(), column))

class ScoreTable(QWidget):
    """show scores of current or last game, even if the last game is
    finished. To achieve this we keep our own reference to game."""
    def __init__(self, game):
        super(ScoreTable, self).__init__(None)
        self.game = None
        self.setWindowTitle(m18nc('kajongg', 'Scores') + ' - Kajongg')
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
            self.connect(view.horizontalScrollBar(),
                SIGNAL('rangeChanged(int, int)'),
                self.updateHscroll)
            self.connect(view.horizontalScrollBar(),
                SIGNAL('valueChanged(int)'),
                self.updateHscroll)
        self.ruleTree = RuleTreeView(m18nc('kajongg','Used Rules'))
        self.splitter.addWidget(self.ruleTree)
        self.connect(self.hscroll,
            SIGNAL('valueChanged(int)'),
            self.updateDetailScroll)
        self.state = StateSaver(self, self.splitter)
        self.refresh(game)

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
                Qt.Horizontal, QVariant(m18nc('kajongg','Score')))
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

    def refresh(self, game):
        """load this game and this player. Keep parameter list identical with
        ExplainView"""
        self.game = game
        if not self.game:
            return
        if self.game.finished():
            title = m18n('Final scores for game <numid>%1</numid>', str(self.game.seed))
        else:
            title = m18n('Scores for game <numid>%1</numid>', str(self.game.seed))
        self.setWindowTitle(title + ' - Kajongg')
        self.ruleTree.rulesets = list([self.game.ruleset])
        for idx, player in enumerate(self.game.players):
            self.nameLabels[idx].setText(m18nc('kajongg', player.name))
            model = self.scoreModel[idx]
            view = self.scoreView[idx]
            qStr = "select %s from score where game = %d and player = %d" % \
                (', '.join(self.__tableFields), self.game.gameid, player.nameid)
            model.setQuery(qStr, Query.dbhandle)
            for col in (0, 1, 6, 7):
                view.hideColumn(col)
            view.resizeColumnsToContents()
            view.horizontalHeader().setStretchLastSection(True)
            view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())
            self.retranslateUi(self.scoreModel[idx])

class ExplainView(QListView):
    """show a list explaining all score computations"""
    def __init__(self, game, parent=None):
        QListView.__init__(self, parent)
        self.game = None
        self.setWindowTitle(m18n('Explain Scores').replace('&', '') + ' - Kajongg')
        self.setGeometry(0, 0, 300, 400)
        self.model = QStringListModel()
        self.setModel(self.model)
        self.state = StateSaver(self)
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
                iName = m18nc('kajongg', player.name)
                pLines = []
                if player.handContent and player.handContent.tiles:
                    score = player.handContent.score
                    total = player.handContent.total()
                    pLines = player.handContent.explain()
                    pLines = [m18n('Computed scoring for %1:', iName)] + pLines
                    pLines.append(m18n('Total for %1: %2 base points, %3 doubles, %4 points',
                        iName, score.points, score.doubles, total))
                elif player.handTotal:
                    pLines.append(m18n('Manual score for %1: %2 points', iName, player.handTotal))
                pLines.append('')
                lines.extend(pLines)
        self.model.setStringList(lines)

class PenaltyBox(QSpinBox):
    """with its own validator, we only accept multiples of parties"""
    def __init__(self, parties, parent=None):
        QSpinBox.__init__(self, parent)
        self.parties = parties

    def validate(self, inputData, pos):
        """ensure the value is a multiple of parties"""
        result, newPos = QSpinBox.validate(self, inputData, pos)
        if result == QValidator.Acceptable:
            if int(inputData) % self.parties != 0:
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
        self.setWindowTitle(m18n("Penalty") + ' - Kajongg')
        self.game = game
        self.grid = QGridLayout(self)
        lblOffense = QLabel(m18n('Offense:'))
        crimes = list([x for x in game.ruleset.penaltyRules if not ('absolute' in x.actions and game.winner)])
        self.cbCrime = ListComboBox(crimes)
        lblOffense.setBuddy(self.cbCrime)
        self.grid.addWidget(lblOffense, 0, 0)
        self.grid.addWidget(self.cbCrime, 0, 1, 1, 4)
        lblPenalty = QLabel(m18n('Total Penalty'))
        self.spPenalty = PenaltyBox(2)
        self.spPenalty.setRange(0, 9999)
        lblPenalty.setBuddy(self.spPenalty)
        self.prevPenalty = 0
        self.lblUnits = QLabel(m18n('points'))
        self.grid.addWidget(lblPenalty, 1, 0)
        self.grid.addWidget(self.spPenalty, 1, 1)
        self.grid.addWidget(self.lblUnits, 1, 2)
        self.lblPayers = QLabel()
        self.grid.addWidget(self.lblPayers, 2, 0)
        self.lblPayees = QLabel()
        self.grid.addWidget(self.lblPayees, 2, 3)
        self.payers = []
        self.payees = []
        # a penalty can never involve the winner, neither as payer nor as payee
        for idx in range(3):
            self.payers.append(ListComboBox(game.losers()))
            self.payees.append(ListComboBox(game.losers()))
        for idx, payer in enumerate(self.payers):
            self.grid.addWidget(payer, 3+idx, 0)
            payer.lblPayment = QLabel()
            self.grid.addWidget(payer.lblPayment, 3+idx, 1)
        for idx, payee in enumerate(self.payees):
            self.grid.addWidget(payee, 3+idx, 3)
            payee.lblPayment = QLabel()
            self.grid.addWidget(payee.lblPayment, 3+idx, 4)
        self.grid.addWidget(QLabel(''), 6, 0)
        self.grid.setRowStretch(6, 10)
        for player in self.payers + self.payees:
            self.connect(player, SIGNAL('currentIndexChanged(int)'), self.playerChanged)
        self.connect(self.spPenalty, SIGNAL('valueChanged(int)'), self.penaltyChanged)
        self.connect(self.cbCrime, SIGNAL('currentIndexChanged(int)'), self.crimeChanged)
        self.buttonBox = KDialogButtonBox(self)
        self.grid.addWidget(self.buttonBox, 7, 0, 1, 5)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel)
        self.connect(self.buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        self.btnExecute = self.buttonBox.addButton(m18n("&Execute"), QDialogButtonBox.AcceptRole,
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
                        -offense.score.value//count, Score.unitName(offense.score.unit)))
        self.lblPayers.setText(m18np('Payer pays', 'Payers pay', payers))
        self.lblPayees.setText(m18np('Payee gets', 'Payees get', payees))
        self.playerChanged()

    def penaltyChanged(self):
        """total has changed, update payments"""
        offense = self.cbCrime.current
        penalty = self.spPenalty.value()
        payers = int(offense.actions.get('payers', 1))
        payees = int(offense.actions.get('payees', 1))
        payerAmount = -penalty // payers
        payeeAmount = penalty // payees
        for pList, amount in [(self.payers, payerAmount), (self.payees, payeeAmount)]:
            for player in pList:
                if player.isVisible():
                    player.lblPayment.setText('%d %s' % (
                        amount, Score.unitName(offense.score.unit)))
                else:
                    player.lblPayment.setText('')
        self.prevPenalty = penalty

class ScoringDialog(QWidget):
    """a dialog for entering the scores"""
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
        pGrid.addWidget(QLabel(m18nc('kajongg',  "Wind")), 0, 1)
        pGrid.addWidget(QLabel(m18nc('kajongg', 'Score')), 0, 2)
        pGrid.addWidget(QLabel(m18n("Winner")), 0, 3)
        self.detailTabs = QTabWidget()
        pGrid.addWidget(self.detailTabs, 0, 4, 8, 1)
        for idx in range(4):
            self.spValues[idx] = QSpinBox()
            self.nameLabels[idx] = QLabel()
            self.nameLabels[idx].setBuddy(self.spValues[idx])
            self.windLabels[idx] = WindLabel()
            pGrid.addWidget(self.nameLabels[idx], idx+2, 0)
            pGrid.addWidget(self.windLabels[idx], idx+2, 1)
            pGrid.addWidget(self.spValues[idx], idx+2, 2)
            self.wonBoxes[idx] = QCheckBox("")
            pGrid.addWidget(self.wonBoxes[idx], idx+2, 3)
            self.connect(self.wonBoxes[idx], SIGNAL('clicked(bool)'), self.wonChanged)
            self.connect(self.spValues[idx], SIGNAL('valueChanged(int)'), self.slotInputChanged)
            detailTab = QWidget()
            self.detailTabs.addTab(detailTab,'')
            self.details[idx] = QWidget()
            detailTabLayout = QVBoxLayout(detailTab)
            detailTabLayout.addWidget(self.details[idx])
            detailTabLayout.addStretch()
            self.detailsLayout[idx] = QVBoxLayout(self.details[idx])
        self.draw = QCheckBox(m18nc('kajongg','Draw'))
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
        self.prevLastTile = None
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
        self.refresh(game)

    def refresh(self, game):
        """reload game"""
        if game and not game.isScoringGame():
            return
        self.game = game
        self.clear()
        self.setVisible(game is not None)
        if game:
            for idx, player in enumerate(game.players):
                for child in self.details[idx].children():
                    if isinstance(child, RuleBox):
                        child.hide()
                        self.detailsLayout[idx].removeWidget(child)
                        del child
                if game:
                    self.spValues[idx].setRange(0, game.ruleset.limit)
                    self.nameLabels[idx].setText(m18nc('kajongg', player.name))
                    self.windLabels[idx].wind = player.wind
                    self.windLabels[idx].roundsFinished = game.roundsFinished
                    self.detailTabs.setTabText(idx, m18nc('kajongg', player.name))
                    player.manualRuleBoxes = [RuleBox(x) for x in game.ruleset.allRules.values() if x.manualRegex]
                    for ruleBox in player.manualRuleBoxes:
                        self.detailsLayout[idx].addWidget(ruleBox)
                        self.connect(ruleBox, SIGNAL('clicked(bool)'),
                            self.slotInputChanged)
                player.refreshManualRules()

    def show(self):
        """only now compute content"""
        self.slotInputChanged()
        QWidget.show(self)

    def penalty(self):
        """penalty button clicked"""
        dlg = PenaltyDialog(self.game)
        dlg.exec_()

    def slotLastTile(self):
        """called when the last tile changes"""
        newLastTile = self.computeLastTile()
        prevLower,  newLower = self.prevLastTile.islower(),  newLastTile.islower()
        if prevLower != newLower:
            # state of last tile (concealed/exposed) changed:
            # for all checked boxes check if they still are applicable
            winner = self.game.winner
            if winner:
                for box in  winner.manualRuleBoxes:
                    if box.isChecked():
                        box.setChecked(False)
                        hand = winner.computeHandContent()
                        if hand.manualRuleMayApply(box.rule):
                            box.setChecked(True)
        self.prevLastTile = newLastTile
        self.fillLastMeldCombo()

    def computeLastTile(self):
        """returns the currently selected last tile"""
        idx = self.cbLastTile.currentIndex()
        if idx >= 0:
            return str(self.cbLastTile.itemData(idx).toString())
        return ''

    def closeEvent(self, event):
        """the user pressed ALT-F4"""
        self.hide()
        event.ignore()
        self.emit(SIGNAL('scoringClosed()'))

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
                for player in self.game.players:
                    if ruleBox.parentWidget() != self.details[player.idx]:
                        for pBox in player.manualRuleBoxes:
                            if pBox.rule.name == ruleBox.rule.name:
                                pBox.setChecked(False)
        newState = bool(self.game and self.game.winner and self.game.winner.handBoard.allTiles())
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
                player.handBoard.clear()
                self.spValues[idx].clear()
                self.spValues[idx].setValue(0)
                self.wonBoxes[idx].setChecked(False)
                player.payment = 0
                player.handContent = None
        for box in self.wonBoxes:
            box.setVisible(False)
        self.draw.setChecked(False)
        self.updateManualRules()

        if self.game is None:
            self.hide()
        else:
            for idx, player in enumerate(self.game.players):
                self.windLabels[idx].setPixmap(WINDPIXMAPS[(player.wind,
                            player.wind == WINDS[self.game.roundsFinished])])
            self.computeScores()
            self.spValues[0].setFocus()

    def computeScores(self):
        """if tiles have been selected, compute their value"""
        if not self.game:
            return
        if self.game.finished():
            self.hide()
            return
        for idx, player in enumerate(self.game.players):
            self.spValues[idx].blockSignals(True) # we do not want that change to call computeScores again
            self.wonBoxes[idx].blockSignals(True) # we do not want that change to call computeScores again
            if player.handBoard and player.handBoard.allTiles():
                self.spValues[idx].setEnabled(False)
                for loop in range(10):
                    prevTotal = player.handTotal
                    player.handContent = player.computeHandContent()
                    self.wonBoxes[idx].setVisible(player.handContent.maybeMahjongg())
                    if not self.wonBoxes[idx].isVisibleTo(self) and self.wonBoxes[idx].isChecked():
                        self.wonBoxes[idx].setChecked(False)
                        self.game.winner = None
                    elif prevTotal == player.handTotal:
                        break
                    player.refreshManualRules()
                self.spValues[idx].setValue(player.handTotal)
            else:
                player.handContent = player.computeHandContent()
                if not self.spValues[idx].isEnabled():
                    self.spValues[idx].clear()
                    self.spValues[idx].setValue(0)
                    self.spValues[idx].setEnabled(True)
                self.wonBoxes[idx].setVisible(player.handTotal >= self.game.ruleset.minMJTotal)
                if not self.wonBoxes[idx].isVisibleTo(self) and self.wonBoxes[idx].isChecked():
                    self.wonBoxes[idx].setChecked(False)
            if not self.wonBoxes[idx].isVisibleTo(self) and player is self.game.winner:
                self.game.winner = None
            self.spValues[idx].blockSignals(False)
            self.wonBoxes[idx].blockSignals(False)
        if InternalParameters.field.explainView:
            InternalParameters.field.explainView.refresh(self.game)

    def fillLastTileCombo(self):
        """fill the drop down list with all possible tiles.
        If the drop down had content before try to preserve the
        current index. Even if the tile changed state meanwhile."""
        if self.game is None:
            return
        showTilePairs = set()
        winnerTiles = []
        if self.game.winner and self.game.winner.handBoard:
            winnerTiles = self.game.winner.handBoard.allTiles()
            winnerMelds = [m for m in self.game.winner.computeHandContent().melds if len(m) < 4]
            pairs = []
            for meld in winnerMelds:
                pairs.extend(meld.pairs)
            for tile in winnerTiles:
                if tile.element in pairs and not tile.isBonus():
                    showTilePairs.add(tile.element)
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
            if not winnerTiles:
                return
            pmSize = winnerTiles[0].tileset.faceSize
            pmSize = QSize(pmSize.width() * 0.5, pmSize.height() * 0.5)
            self.cbLastTile.setIconSize(pmSize)
            QPixmapCache.clear()
            self.__tilePixMaps = []
            shownTiles = set()
            for tile in winnerTiles:
                if tile.element in showTilePairs and tile.element not in shownTiles:
                    shownTiles.add(tile.element)
                    self.cbLastTile.addItem(QIcon(tile.pixmap(pmSize)), '', QVariant(tile.element))
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
        finally:
            self.cbLastTile.blockSignals(False)
            self.cbLastTile.emit(SIGNAL("currentIndexChanged(int)"), 0)


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
            restoredIdx = None
            self.cbLastMeld.clear()
            self.__meldPixMaps = []
            if not self.game.winner:
                return
            if self.cbLastTile.count() == 0:
                return
            lastTile = InternalParameters.field.computeLastTile()
            winner = self.game.winner
            winnerMelds = [m for m in winner.computeHandContent().melds if len(m) < 4 \
                and lastTile in m.pairs]
            assert len(winnerMelds)
            if len(winnerMelds) == 1:
                self.cbLastMeld.addItem(QIcon(), '', QVariant(winnerMelds[0].joined))
                self.cbLastMeld.setCurrentIndex(0)
                return
            showCombo = True
            winnerTiles = self.game.winner.handBoard.allTiles()
            tileset = winner.handBoard.tileset
            faceWidth = tileset.faceSize.width() * 0.5
            faceHeight = tileset.faceSize.height() * 0.5
            iconSize = QSize(faceWidth * 3, faceHeight)
            for meld in winnerMelds:
                thisSize = QSize(faceWidth  * len(meld), faceHeight)
                pixMap = QPixmap(thisSize)
                pixMap.fill(Qt.transparent)
                self.__meldPixMaps.append(pixMap)
                painter = QPainter(pixMap)
                for element in meld.pairs:
                    tile = [x for x in winnerTiles if x.element == element][0]
                    painter.drawPixmap(0, 0, tile.pixmap(QSize(faceWidth, faceHeight)))
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
            self.cbLastMeld.setIconSize(iconSize)
        finally:
            self.lblLastMeld.setVisible(showCombo)
            self.cbLastMeld.setVisible(showCombo)
            self.cbLastMeld.blockSignals(False)
            self.cbLastMeld.emit(SIGNAL("currentIndexChanged(int)"), 0)

    def slotInputChanged(self):
        """some input fields changed: update"""
        self.updateManualRules()
        self.computeScores()
        self.validate()

    def validate(self):
        """update the status of the OK button"""
        game = self.game
        if game:
            valid = True
            if game.winner and game.winner.handTotal < game.ruleset.minMJTotal:
                valid = False
            elif not game.winner and not self.draw.isChecked():
                valid = False
            self.btnSave.setEnabled(valid)
