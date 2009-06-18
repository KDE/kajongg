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

# TODO: update manual about new HandDialog

import sys
if sys.version_info < (2, 6, 0, 0, 0):
    bytes = str
else:
    str = unicode

import os,  datetime, syslog
import util
from util import logMessage,  logException, m18n, m18nc, WINDS,  rotateCenter
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
    from PyQt4 import  QtGui
    from PyQt4.QtCore import Qt, QRectF,  QPointF, QVariant, SIGNAL, SLOT, \
        QEvent, QMetaObject, QSize, qVersion
    from PyQt4.QtGui import QColor, QPushButton,  QMessageBox
    from PyQt4.QtGui import QWidget, QLabel, QPixmapCache
    from PyQt4.QtGui import QGridLayout, QVBoxLayout, QHBoxLayout,  QSpinBox
    from PyQt4.QtGui import QGraphicsScene,  QDialog, QStringListModel, QListView
    from PyQt4.QtGui import QBrush, QIcon, QPixmap, QPainter
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
    from board import Tile, PlayerWind, PlayerWindLabel, Walls,  FittingView,  ROUNDWINDCOLOR, \
        HandBoard,  SelectorBoard, MJScene, WINDPIXMAPS
    from playerlist import PlayerList
    from tileset import Tileset, elements, LIGHTSOURCES
    from background import Background
    from games import Games
    from genericdelegates import GenericDelegate,  IntegerColumnDelegate
    from config import Preferences, ConfigDialog
    from scoring import Ruleset, Hand
    from rulesets import defaultRulesets
except ImportError,  e:
    NOTFOUND.append('kmj modules: %s' % e)

if len(NOTFOUND):
    MSG = "\n".join(" * %s" % s for s in NOTFOUND)
    logMessage(MSG)
    os.popen("kdialog --sorry '%s'" % MSG)
    sys.exit(3)

class ScoreModel(QSqlQueryModel):
    """a model for our score table"""
    def __init__(self,  parent = None):
        super(ScoreModel, self).__init__(parent)

    def data(self, index, role=None):
        """score table data"""
        if role is None:
            role = Qt.DisplayRole
        if role == Qt.BackgroundRole and index.column() == 2:
            prevailing = self.data(self.index(index.row(), 0)).toString()
            if prevailing == self.data(index).toString():
                return QVariant(ROUNDWINDCOLOR)
        if role == Qt.BackgroundRole and index.column()==3:
            won = self.data(self.index(index.row(), 1)).toInt()[0]
            if won == 1:
                return QVariant(QColor(165, 255, 165))
        return QSqlQueryModel.data(self, index, role)

class ScoreTable(QWidget):
    """all player related data, GUI and internal together"""
    def __init__(self, game):
        super(ScoreTable, self).__init__(None)
        self.setWindowTitle(m18n('Scores for game <numid>%1</numid>', game.gameid))
        self.game = game
        self.__tableFields = ['prevailing', 'won', 'wind',
                                'points', 'payments', 'balance']
        self.scoreModel = [ScoreModel(self) for player in range(0, 4)]
        self.scoreView = [QTableView(self)  for player in range(0, 4)]
        windowLayout = QVBoxLayout(self)
        playerLayout = QHBoxLayout()
        windowLayout.addLayout(playerLayout)
        self.hscroll = QScrollBar(Qt.Horizontal)
        windowLayout.addWidget(self.hscroll)
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
        self.connect(self.hscroll,
            SIGNAL('valueChanged(int)'),
            self.updateDetailScroll)
        self.loadTable()

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
            view.hideColumn(0)
            view.hideColumn(1)
            view.resizeColumnsToContents()
            view.horizontalHeader().setStretchLastSection(True)
            view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())


class ExplainView(QListView):
    """show a list explaining all score computations"""
    def __init__(self, game, parent=None):
        QListView.__init__(self, parent)
        self.setWindowTitle(m18n('Explain scores'))
        self.setGeometry(0, 0, 300, 400)
        self.game = game
        self.model = QStringListModel()
        self.setModel(self.model)
        self.refresh()

    def refresh(self):
        """refresh for new favalues"""
        lines = []
        if self.game.gameid == 0:
            lines.append(m18n('There is no active game'))
        else:
            lines.append(m18n('Ruleset: %s') % m18n(self.game.ruleset.name))
            lines.append('')
            for player in self.game.players:
                total = 0
                pLines = []
                if player.handBoard.hasTiles():
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
        playerNames = game.allPlayerNames.values()
        self.setWindowTitle(m18n('Select four players') + ' - kmj')
        self.buttonBox = KDialogButtonBox(self)
        self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)
        self.buttonBox.button(QtGui.QDialogButtonBox.Ok).setEnabled(False)
        self.connect(self.buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(self.buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        grid = QGridLayout()
        self.names = None
        self.nameWidgets = []
        self.cbRuleset = QComboBox()
        self.rulesetNames = Ruleset.availableRulesetNames()
        self.cbRuleset.addItems([m18n(x) for x in self.rulesetNames])
        for idx, wind in enumerate(WINDS):
            cbName = QComboBox()
            # increase width, we want to see the full window title
            cbName.setMinimumWidth(350) # is this good for all platforms?
            cbName.addItems(playerNames)
            grid.addWidget(cbName, idx+1, 1)
            self.nameWidgets.append(cbName)
            grid.addWidget(PlayerWindLabel(wind), idx+1, 0)
            self.connect(cbName, SIGNAL('currentIndexChanged(const QString&)'),
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

    def rulesetName(self):
        """return the selected ruleset"""
        return self.rulesetNames[self.cbRuleset.currentIndex()]

    def showEvent(self, event):
        """start with player 0"""
        assert event # quieten pylint
        self.nameWidgets[0].setFocus()

    def slotValidate(self):
        """update status of the Ok button"""
        self.names = list(str(cbName.currentText()) for cbName in self.nameWidgets)
        valid = len(set(self.names)) == 4
        self.buttonBox.button(QtGui.QDialogButtonBox.Ok).setEnabled(valid)

class SelectTiles(QDialog):
    """a dialog for selecting the tiles at the end of the hand"""
    def __init__(self, players):
        """selection for this player, tiles are the still available tiles"""
        QDialog.__init__(self, None)
        self.players = players
        buttonBox = KDialogButtonBox(self)
        buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)
        buttonBox.button(QtGui.QDialogButtonBox.Ok).setEnabled(False)
        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        vbox = QVBoxLayout(self)
        self.scene = QGraphicsScene()
        for player in players:
            player.melds = []
        self.selectedBoard = None
        self.view = FittingView()
        self.view.setScene(self.scene)
        vbox.addWidget(self.view)
        vbox.addWidget(buttonBox)
        self.player = None

class BonusBox(QCheckBox):
    """additional attribute: ruleId"""
    def __init__(self, rule):
        QCheckBox.__init__(self, m18n(rule.name))
        self.rule = rule

class EnterHand(QWidget):
    """a dialog for entering the scores"""
    def __init__(self, game):
        QWidget.__init__(self, None)
        if qVersion() >= '4.5.0' and util.PYQTVERSION >='4.5.0':
            flags = self.windowFlags()
            flags = flags & ~  Qt.WindowCloseButtonHint
            self.setWindowFlags(flags)
        self.setWindowTitle(m18n('Enter the hand results'))
        self._winner = None
        self.game = game
        self.players = game.players
        self.windLabels = [None] * 4
        self.__tilePixMaps = []
        self.__meldPixMaps = []
        grid = QGridLayout(self)
        pGrid = QGridLayout()
        grid.addLayout(pGrid, 0, 0, 2, 1)
        bonusGrid = QGridLayout()
        grid.addLayout(bonusGrid, 0, 1)
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
            self.connect(player.spValue, SIGNAL('valueChanged(int)'), self.slotValidate)
        self.draw = QCheckBox(m18nc('kmj','Draw'))
        self.connect(self.draw, SIGNAL('clicked(bool)'), self.wonChanged)
        self.btnPenalties = QPushButton(m18n("&Penalties"))
        self.btnSave = QPushButton(m18n('&Save hand'))
        self.btnSave.setEnabled(False)
        vpol = QSizePolicy()
        vpol.setHorizontalPolicy(QSizePolicy.Fixed)
        self.lblLastTile = QLabel(m18n('&Last tile:'))
        self.cbLastTile = QComboBox()
        self.cbLastTile.setMinimumContentsLength(1)
        self.cbLastTile.setSizePolicy(vpol)
        self.cbLastTile.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.lblLastTile.setBuddy(self.cbLastTile)
        self.lblLastMeld = QLabel(m18n('L&ast meld:'))
        self.cbLastMeld = QComboBox()
        self.cbLastMeld.setMinimumContentsLength(1)
        self.cbLastMeld.setSizePolicy(vpol)
        self.cbLastMeld.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.lblLastMeld.setBuddy(self.cbLastMeld)
        pGrid.setRowStretch(6, 5)
        pGrid.addWidget(self.lblLastTile, 7, 0, 1, 2)
        pGrid.addWidget(self.cbLastTile, 7 , 2)
        pGrid.addWidget(self.lblLastMeld, 8, 0, 1, 2)
        pGrid.addWidget(self.cbLastMeld, 8 , 2)
        pGrid.setRowStretch(87, 10)
        pGrid.addWidget(self.btnPenalties, 99, 0)
        pGrid.addWidget(self.draw, 99, 3)
        grid.addWidget(self.btnSave, 1, 1)
        self.connect(self.cbLastTile, SIGNAL('currentIndexChanged(const QString&)'),
            self.slotLastTile)
        self.connect(self.cbLastMeld, SIGNAL('currentIndexChanged(const QString&)'),
            self.slotValidate)
        self.boni = [BonusBox(x) for x in self.game.ruleset.manualRules]
        for idx, bonusBox in enumerate(self.boni):
            bonusGrid.addWidget(bonusBox, idx + 1, 0, 1, 2)
            self.connect(bonusBox, SIGNAL('clicked(bool)'),
                self.slotValidate)
        self.players[0].spValue.setFocus()
        self.clear()

    def slotLastTile(self):
        """called when the last tile changes"""
        self.fillLastMeldCombo()
        self.slotValidate()

    def closeEvent(self, event):
        """the user pressed ALT-F4"""
        event.ignore()

    def __getWinner(self):
        """getter for winner"""
        return self._winner

    def __setWinner(self, winner):
        """setter for winner"""
        if self._winner and not winner:
            self._winner.wonBox.setChecked(False)
        self._winner = winner
        self.updateBonusItems()

    winner = property(__getWinner, __setWinner)

    def updateBonusItems(self):
        """enable/disable them"""
        if self.winner:
            winnerTiles = self.winner.handBoard.allTiles()
        newState = self.winner is not None and len(winnerTiles)
        self.lblLastTile.setEnabled(newState)
        self.cbLastTile.setEnabled(newState)
        self.lblLastMeld.setEnabled(newState)
        self.cbLastMeld.setEnabled(newState)
        for bonusBox in self.boni:
            bonusBox.setEnabled(newState)

    def clear(self):
        """prepare for next hand"""
        self.winner = None
        self.updateBonusItems()
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
            if player.handBoard.hasTiles():
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
        return None

    def wonChanged(self):
        """if a new winner has been defined, uncheck any previous winner"""
        self.winner = None
        if self.sender() != self.draw:
            clicked = self.wonPlayer(self.sender())
            active = clicked.wonBox.isChecked()
            if active:
                self.winner = clicked
        for player in self.players:
            if player.wonBox != self.sender():
                player.wonBox.setChecked(False)
        if self.winner:
            self.draw.setChecked(False)
        self.fillLastTileCombo()
        self.fillLastMeldCombo()
        self.computeScores()
        self.updateBonusItems()
        self.slotValidate()

    def fillLastTileCombo(self):
        """fill the drop down list with all possible tiles"""
        self.cbLastTile.clear()
        self.__tilePixMaps = []
        if not self.winner:
            return
        winnerTiles = self.winner.handBoard.allTiles()
        if len(winnerTiles):
            pmSize = winnerTiles[0].tileset.faceSize
            pmSize = QSize(pmSize.width() * 0.5, pmSize.height() * 0.5)
            shownTiles = set()
        for tile in winnerTiles:
            if not tile.isBonus() and not tile.element in shownTiles:
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
        self.cbLastMeld.clear()
        self.__meldPixMaps = []
        if not self.winner:
            return
        if self.cbLastTile.count() == 0:
            return
        tileName = self.winner.lastTile(self.game)
        winnerMelds = [m for m in self.winner.hand(self.game).melds if tileName in m.contentPairs]
        assert len(winnerMelds)
        tile = self.winner.handBoard.allTiles()[0]
        tileWidth = tile.tileset.faceSize.width()
        pmSize = tile.tileset.faceSize
        pmSize = QSize(tileWidth * 0.5 * 4, pmSize.height() * 0.5)
        for meld in winnerMelds:
            pixMap = QPixmap(pmSize)
            pixMap.fill(Qt.transparent)
            self.__meldPixMaps.append(pixMap)
            painter = QPainter(pixMap)
            for idx, tileName in enumerate(meld.contentPairs):
                element = elements.elementName[tileName.lower()]
                rect = QRectF(QPointF(idx * tileWidth * 0.5, 0.0), tile.tileset.faceSize * 0.5)
                tile.renderer().render(painter, element, rect)
            self.cbLastMeld.setIconSize(pixMap.size())
            self.cbLastMeld.addItem(QIcon(pixMap), '', QVariant(meld.content))

    def slotSelectTiles(self, checked):
        """the user wants to enter the tiles"""
        assert isinstance(checked, bool) # quieten pylint
        btn = self.sender()
        for player in self.players:
            if btn == player.btnTiles:
                self.selectTileDialog.selectPlayer(player)
                self.selectTileDialog.exec_()

    def slotValidate(self):
        """update the status of the OK button"""
        self.computeScores()
        valid = True
        if self.winner is not None and self.winner.score < 20:
            valid = False
        elif self.winner is None and not self.draw.isChecked():
            valid = False
        self.btnSave.setEnabled(valid)

class Player(object):
    """all player related data, GUI and internal together"""
    def __init__(self, wind, scene,  wall):
        self.scene = scene
        self.wall = wall
        self.wonBox = None
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

    def isWinner(self, game):
        """check in the handDialog"""
        winner = game.handDialog.winner if game.handDialog else None
        return self == winner

    def mjString(self, game):
        """compile hand info into  a string as needed by the scoring engine"""
        winds = self.wind.name.lower() + 'eswn'[game.roundsFinished]
        wonChar = 'm'
        if self.isWinner(game):
            wonChar = 'M'
        return ''.join([wonChar, winds])

    def lastTile(self, game):
        """compile hand info into  a string as needed by the scoring engine"""
        lastTile = ' '
        cbLastTile = game.handDialog.cbLastTile
        idx = cbLastTile.currentIndex()
        if idx >= 0:
            lastTile = bytes(cbLastTile.itemData(idx).toString())
        return lastTile

    def lastMeld(self, game):
        """compile hand info into  a string as needed by the scoring engine"""
        lastMeld = ' '
        cbLastMeld = game.handDialog.cbLastMeld
        idx = cbLastMeld.currentIndex()
        if idx >= 0:
            lastMeld = bytes(cbLastMeld.itemData(idx).toString())
        return lastMeld

    def lastString(self, game):
        """compile hand info into  a string as needed by the scoring engine"""
        if not self.isWinner(game):
            return ''
        return 'L%s%s' % (self.lastTile(game), self.lastMeld(game))

    def hand(self, game):
        """builds a Hand object"""
        return Hand(game.ruleset, ' '.join([self.handBoard.scoringString(),
            self.mjString(game), self.lastString(game)]),
            list(x.rule for x in game.handDialog.boni if x.isChecked()) if self.isWinner(game) else None)

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
            for idx, clsRuleset in enumerate(defaultRulesets()):
                ruleset = clsRuleset()
                ruleset.rulesetId = idx + 1
                ruleset.save()
            self.addTestData()
        self.playerwindow = None
        self.scoreTableWindow = None
        self.explainView = None
        self.handDialog = None
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
        if self.handDialog:
            self.handDialog.computeScores()
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
        return None

    def playerByWind(self, wind):
        """lookup the player by wind"""
        for player in self.players:
            if player.wind.name == wind:
                return player
        return None

    def createTables(self):
        """creates empty tables"""
        Query(["""CREATE TABLE player (
            id INTEGER PRIMARY KEY,
            name TEXT)""",
        """CREATE TABLE game (
            id integer primary key,
            starttime text default current_timestamp,
            endtime text,
            ruleset integer references ruleset(id),
            p0 integer constraint fk_p0 references player(id),
            p1 integer constraint fk_p1 references player(id),
            p2 integer constraint fk_p2 references player(id),
            p3 integer constraint fk_p3 references player(id))""",
        """CREATE TABLE score(
            game integer constraint fk_game references game(id),
            hand integer,
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
            description text)""",
        """CREATE TABLE rule(
            ruleset integer,
            name text,
            list integer,
            value text,
            points integer,
            doubles integer,
            limits integer,
            primary key(ruleset,name))"""])

    def addTestData(self):
        """adds test data to an empty data base"""
        names = ['Wolfgang',  'Petra',  'Klaus',  'Heide']
        Query(['insert into player(name) values("%s")' % x for x in names])

    def kmjAction(self,  name, icon, slot):
        """simplify defining actions"""
        res = KAction(self)
        res.setIcon(KIcon(icon))
        self.connect(res, SIGNAL('triggered()'), slot)
        self.actionCollection().addAction(name, res)
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
        # setBrush(QColor(Qt.transparent) should work too but does  not
        self.tileset = None # just for pylint
        self.background = None # just for pylint
        self.tilesetName = util.PREF.tilesetName
        self.tiles = [Tile(element) for element in elements.all()]
        self.walls = Walls(self.tileset, self.tiles)
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
        self.actionNewGame = self.kmjAction("new", "document-new", self.newGame)
        self.actionNewGame.setShortcut( Qt.CTRL + Qt.Key_N)
        self.actionQuit = self.kmjAction("quit", "application-exit", self.quit)
        self.actionQuit.setShortcut( Qt.CTRL + Qt.Key_Q)
        self.actionPlayers = self.kmjAction("players",  "personal",  self.slotPlayers)
        self.actionAngle = self.kmjAction("angle",  "object-rotate-left",  self.changeAngle)
        self.actionAngle.setShortcut( Qt.CTRL + Qt.Key_A)
        self.actionFullscreen = KToggleFullScreenAction(self.actionCollection())
        self.actionFullscreen.setWindow(self)
        self.actionFullscreen.setShortcut( Qt.CTRL + Qt.SHIFT + Qt.Key_F)
        self.actionCollection().addAction("fullscreen", self.actionFullscreen)
        self.connect(self.actionFullscreen, SIGNAL('toggled(bool)'), self.fullScreen)
        self.actionGames = self.kmjAction("load", "document-open", self.games)
        self.actionGames.setShortcut( Qt.CTRL + Qt.Key_L)
        self.actionScoreTable = self.kmjAction("scoreTable", "format-list-ordered",
            self.showScoreTable)
        self.actionScoreTable.setShortcut( Qt.CTRL + Qt.Key_T)
        self.actionScoreTable.setEnabled(False)
        self.actionExplain = self.kmjAction("explain", "applications-education",
            self.explain)
        self.actionExplain.setEnabled(True)

        QMetaObject.connectSlotsByName(self)

    def fullScreen(self, toggle):
        """toggle between full screen and normal view"""
        self.actionFullscreen.setFullScreen(self, toggle)

    def quit(self):
        """exit the application"""
        sys.exit(0)

    def keyPressEvent(self, event):
        """navigate in the selectorboard"""
        key = event.key()
        tile = self.centralScene.focusItem()
        currentBoard = tile.board if isinstance(tile, Tile) else None
        wind = chr(key%256)
        moveCommands = m18nc('kmj:keyboard commands for moving tiles to the players with wind ESWN or to the central tile selector (X)', 'ESWNX')
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
                    receiver.sendTile(tile, self.centralView, lowerHalf=event.modifiers() & Qt.ShiftModifier)
                if not currentBoard.hasTiles():
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
                        pass
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
        confDialog = ConfigDialog(self, "settings", util.PREF)
        self.connect(confDialog, SIGNAL('settingsChanged(QString)'),
           self.applySettings)
        confDialog.show()

    def swapPlayers(self, winds):
        """swap the winds for the players with wind in winds"""
        swappers = list(self.findPlayer(winds[x]) for x in (0, 1))
        mbox = QMessageBox()
        mbox.setWindowTitle("Swap seats")
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
        starttime = datetime.datetime.now().replace(microsecond=0)
        # first insert and then find out which game id we just generated. Clumsy and racy.
        return Query(['insert into game(starttime,ruleset,p0,p1,p2,p3) values("%s", %d, %s)' % \
              (starttime.isoformat(), self.ruleset.rulesetId, ','.join(str(p.nameid) for p in self.players)),
              "select id from game where starttime = '%s'" % \
            starttime.isoformat()]).data[0][0]

    def newGame(self):
        """init the first hand of a new game"""
        self.loadPlayers() # we want to make sure we have the current definitions
        selectDialog = SelectPlayers(self)
        query = Query("select ruleset from game order by id desc")
        if query.data:
            rulesetId = query.data[0][0]
            ruleset = Ruleset(rulesetId)
            selectDialog.cbRuleset.setCurrentIndex(selectDialog.rulesetNames.index(ruleset.name))
        if not selectDialog.exec_():
            return
        self.initGame()
        self.ruleset = Ruleset(selectDialog.rulesetName())
        # initialise the four winds with the first four players:
        for idx, player in enumerate(self.players):
            player.name = selectDialog.names[idx]
            player.nameid = self.allPlayerIds[player.name]
            player.clearBalance()
        self.gameid = self.newGameId()
        self.showBalance()
        if self.explainView:
            self.explainView.refresh()
        self.enterHand()

    def enterHand(self):
        """compute and save the scores. Makes player names immutable."""
        if not self.handDialog:
            self.handDialog = EnterHand(self)
            self.connect(self.handDialog.btnSave, SIGNAL('clicked(bool)'), self.saveHand)
        else:
            self.handDialog.clear()
        self.handDialog.show()
        self.handDialog.raise_()

    def saveHand(self):
        """save hand to data base, update score table and balance in status line"""
        self.winner = self.handDialog.winner
        self.payHand()
        scoretime = datetime.datetime.now().replace(microsecond=0).isoformat()
        cmdList = []
        for player in self.players:
            cmdList.append("INSERT INTO SCORE "
            "(game,hand,player,scoretime,won,prevailing,wind,points,payments, balance,rotated) "
            "VALUES(%d,%d,%d,'%s',%d,'%s','%s',%d,%d,%d,%d)" % \
            (self.gameid, self.handctr, player.nameid, scoretime, int(player.wonBox.isChecked()),
            WINDS[self.roundsFinished], player.wind.name, player.score,
            player.payment, player.balance, self.rotated))
        Query(cmdList)
        self.actionScoreTable.setEnabled(True)
        self.showBalance()
        self.rotate()
        self.handDialog.clear()

    def rotate(self):
        """initialise the values for a new hand"""
        if self.winner is not None and self.winner.wind.name != 'E':
            self.rotateWinds()
        self.handctr += 1
        self.walls.build(self.tiles, self.rotated % 4,  8)

    def initGame(self):
        """reset things to empty"""
        for dlg in [self.scoreTableWindow, self.handDialog]:
            if dlg:
                dlg.hide()
                dlg.setParent(None)
        self.scoreTableWindow = None
        self.handDialog = None
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
        self.ruleset = Ruleset(rulesetId)
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
        if self.roundsFinished < 4:
            self.enterHand()
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
            if self.handDialog:
                self.handDialog.hide()
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

class About(object):
    """we need persistent data but do not want to spoil global name space"""
    def __init__(self):
        self.appName     = bytes("kmj")
        self.catalog     = bytes('')
        self.homePage    = bytes('http://www.kde-apps.org/content/show.php/kmj?content=103206')
        self.bugEmail    = bytes('wolfgang@rohdewald.de')
        self.version     = bytes('0.2')
        self.programName = ki18n ("kmj")
        self.description = ki18n ("kmj - computes payments among the 4 players")
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

