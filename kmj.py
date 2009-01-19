#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

import sys, os,  datetime
import functools
from util import logMessage,  logException
    
NOTFOUND = []

try:
    from PyQt4 import  QtCore,  QtGui,  QtSql
    from PyQt4.QtCore import Qt, QVariant, QString, SIGNAL, SLOT, QEvent, QMetaObject
    from PyQt4.QtGui import QColor, QPushButton,  QMessageBox, QWidget, QLabel
    from PyQt4.QtGui import QGridLayout, QVBoxLayout, QHBoxLayout,  QSpinBox
    from PyQt4.QtGui import QSizePolicy,  QComboBox,  QCheckBox, QTableView, QScrollBar
    from PyQt4.QtSql import QSqlDatabase, QSqlQueryModel, QSqlQuery
except ImportError,  e:
    NOTFOUND.append('PyQt4: %s' % e.message) 
    
try:
    from PyKDE4 import kdecore,  kdeui
    from PyKDE4.kdecore import ki18n,  i18n
    from PyKDE4.kdeui import KApplication,  KStandardAction,  KAction
except ImportError, e :
    NOTFOUND.append('PyKDE4: %s' % e.message) 
    
try:
    from board import Board,  Tile
    from playerlist import PlayerList
    from tilesetselector import TilesetSelector
    from tileset import Tileset
    from games import Games
    from genericdelegates import GenericDelegate,  IntegerColumnDelegate
    from config import Preferences,  ConfigDialog
except ImportError,  e:
    NOTFOUND.append('kmj modules: %s' % e.message)

if len(NOTFOUND):
    MSG = "\n".join(" * %s" % s for s in NOTFOUND)
    logMessage(MSG)
    os.popen("kdialog --sorry '%s'" % MSG)
    sys.exit(3)


WINDS = 'ESWN'

class PlayerWind(Board):
    """a board containing just one wind"""
    windtilenr = {'N':'1', 'S':'2', 'E':'3', 'W':'4'}
    def __init__(self, name, player):
        Board.__init__(self, player)
        self.player = player
        self.name = '' # make pylint happy
        self.prevailing = False
        self.setWind(name, 0)

    def setWind(self, name,  roundsFinished):
        """change the wind"""
        self.name = name
        self.prevailing = name == WINDS[roundsFinished]
        self.__show()
        
    def __show(self):
        """why does pylint want a doc string for this private method?"""
        tile = self.addTile("WIND_"+PlayerWind.windtilenr[self.name])
        if self.prevailing:
            tile.select()

class Walls(Board):
    """the 4 walls with 72 tiles, only one level for now"""
    def __init__(self, parent=None):
        length = 18
        super(Walls, self).__init__(parent)
        leftTop = self.attachDouble()
        tile = leftTop
        for position in range(0, length-1):
            tile = self.attachDouble(tile, xoffset=1)
        tile = self.attachDouble(tile, xoffset=1,  rotation=90)
        for position in range(0, length-1):
            tile = self.attachDouble(tile, yoffset=1, rotation=90)
        tile = leftTop
        for position in range(0, length):
            tile = self.attachDouble(tile, yoffset=1, rotation=90)
        tile = self.attachDouble(tile, xoffset=1, yoffset=-0.3)
        for position in range(0, length-1):
            tile = self.attachDouble(tile, xoffset=1)
        
    def attachDouble(self, tile=None, xoffset=0, yoffset=0, rotation=0):
        """attach 2 tiles over each other"""
        if tile:
            tile = tile.attach('', xoffset, yoffset, rotation)
        else:
            tile = self.addTile('')
        tile.attachOver('')
        return tile
        
    def resizeEvent(self, event=None):
        """if the board resizes we might want to adjust the player widget sizes"""
        Board.resizeEvent(self, event)
        if event:
            wallSize = min(event.size().width(), event.size().height())
            self.emit (SIGNAL('wallSizeChanged'), wallSize)
        
class ScoreModel(QSqlQueryModel):
    """a model for our score table"""
    def __init__(self,  parent = None):
        super(ScoreModel, self).__init__(parent)

    def data(self, index, role=Qt.DisplayRole):
        """score table data"""
        if role == Qt.BackgroundRole and index.column()==2:
            prevailing = self.data(self.index(index.row(), 0)).toString()
            if prevailing == self.data(index).toString():
                return QVariant(QColor(235, 235, 173))
        if role == Qt.BackgroundRole and index.column()==3:
            won = self.data(self.index(index.row(), 1)).toString()
            if won == 'true':
                return QVariant(QColor(165, 255, 165))
        return QSqlQueryModel.data(self, index, role)

class ScoreTable(QWidget):
    """all player related data, GUI and internal together"""
    def __init__(self, game):
        super(ScoreTable, self).__init__(None)
        self.setWindowTitle(QString('%1 - %2').arg(ABOUT.appName).arg(i18n('Scores')))
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
            view =self.scoreView[idx]
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
                self.connect(self.scoreView[3].verticalScrollBar(),
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
        for view in self.scoreView:
            view.horizontalScrollBar().setValue(value)
            
    def updateHscroll(self):
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
        model.setHeaderData(self.__tableFields.index('points'),
                Qt.Horizontal, QVariant(i18n('Score')))
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
            model.setQuery("select %s from score "
            "where game = %d and player = %d" % \
                (', '.join(self.__tableFields), self.game.gameid,  player.nameid),
                self.game.dbhandle)
            view.hideColumn(0)
            view.hideColumn(1)
            view.resizeColumnsToContents()
            view.horizontalHeader().setStretchLastSection(True)


class Player(QWidget):
    """all player related data, GUI and internal together"""
    def __init__(self, wind, parent,  vertical):
        super(Player, self).__init__(parent)
        self.vertical = vertical
        self.__balance = 0
        self.__payment = 0
        self.nameid = 0 
        self.wind = PlayerWind(wind, self)
        self.cbName = QComboBox()
        self.spValue = QSpinBox()
        self.lblName = QLabel()
        self.lblScore = QLabel()
        self.lblScore.setBuddy(self.spValue)
        self.lblName.setBuddy(self.spValue)
        self.won = QCheckBox("Mah Jongg")
        self.lblBalance = QLabel()
        if vertical:
            self.glayout = QGridLayout(self)
            self.glayout.addWidget(self.wind, 0, 0, 3, 2)
            self.glayout.addWidget(self.cbName, 4, 0, 1, 3)
            self.glayout.addWidget(self.lblBalance, 5, 0, 1, 3)
            self.glayout.addWidget(self.lblScore, 6, 0)
            self.glayout.addWidget(self.spValue, 6, 1)
            self.glayout.addWidget(self.won, 7, 0, 1, 2)
        else:
            self.glayout = QGridLayout()
            self.glayout.addWidget(self.cbName, 0, 0, 1, 3)
            self.glayout.addWidget(self.lblBalance, 1, 0, 1, 3)
            self.glayout.addWidget(self.lblScore, 2, 0)
            self.glayout.addWidget(self.spValue, 2, 1)
            self.glayout.addWidget(self.won, 3, 0, 1, 2)            
            self.hlayout = QHBoxLayout(self)
            self.hlayout.addWidget(self.wind)
            self.hlayout.addLayout(self.glayout)
        pol = QSizePolicy()
        pol.setHorizontalPolicy(QSizePolicy.Maximum)
        pol.setVerticalPolicy(QSizePolicy.Maximum)
        self.setSizePolicy(pol)

        self.retranslateUi()

    def retranslateUi(self):
        self.lblScore.setText(i18n('Score:'))
        
    def clearBalance(self):
        """sets the balance and the payments to 0"""
        self.spValue.clear()
        self.__balance = 0
        self.__payment = 0
        
    def setNameList(self, names):
        """initialize the name combo box"""
        cb = self.cbName
        oldName = cb.currentText()
        cb.clear()
        cb.addItems(names)
        if oldName in names:
            cb.setCurrentIndex(cb.findText(oldName))

    @property
    def balance(self):
        """the balance of this player"""
        return self.__balance

    def pay(self, payment):
        """make a payment to this player"""
        self.__balance += payment
        self.__payment += payment
        color ='green' if self.balance >= 0 else 'red'
        self.lblBalance.setText(QString(
            '<font color=%1>%2  %3</font>').arg(color).arg(u"\u2211").arg(self.balance))
    
    def getName(self):
        """the name of the player"""
        return str(self.cbName.currentText())
    
    def setName(self, name):
        """change the name of this player"""
        cb = self.cbName
        idx = cb.findText(QString(name))
        cb.setCurrentIndex(idx)

    name = property(getName,  setName)
    
    @property
    def payment(self):
        """the payments for the current hand"""
        return self.__payment
        
    def __get_score(self):
        """why does pylint want a doc string for this private method?"""
        return self.spValue.value()
            
    def __set_score(self,  score):
        """why does pylint want a doc string for this private method?"""
        self.spValue.setValue(score)
        if score == 0:
            # do not display 0 but an empty field
            self.spValue.clear()
            self.__payment = 0

    score = property(__get_score,  __set_score)
    
    def fixName(self, nameid,  fix=True):
        """make the name of this player mutable(with combobox)
            or immutable (with label)"""
        self.nameid = nameid
        cbNameRow = 4 if self.vertical else 0
        if fix:
            self.lblName.setText(self.name)
            self.glayout.removeWidget(self.cbName)
            self.glayout.addWidget(self.lblName, cbNameRow, 0, 1, 3)
        else:
            self.glayout.removeWidget(self.lblName)
            self.glayout.addWidget(self.cbName, cbNameRow, 0, 1, 3)
        self.cbName.setVisible(not fix)
        self.lblName.setVisible(fix)
        self.lblBalance.setVisible(fix)
         
class MahJongg(kdeui.KXmlGuiWindow):
    """the main window"""
    def __init__(self):
        super(MahJongg, self).__init__()
        self.dbhandle = QSqlDatabase("QSQLITE")
        self.dbpath = kdecore.KGlobal.dirs().locateLocal("appdata","kmj.db")
        self.dbhandle.setDatabaseName(self.dbpath)
        dbExists = os.path.exists(self.dbpath)
        if not self.dbhandle.open():
            logMessage(self.dbhandle.lastError().text())
            sys.exit(1)
        if not dbExists:
            self.createTables()
            self.addTestData()
        self.playerwindow = None
        self.scoreTableWindow= None
        self.Players = [None, None, None, None]
        self.roundsFinished = 0
        self.winner = None
        """shift rules taken from the OEMC 2005 rules
        2nd round: S and W shift, E and N shift"""
        self.shiftRules = 'SWEN,SE,WE' 
        self.setupUi()
        self.setupActions()
        self.creategui()
        self.newGame()

    def loadGame(self, game):
        """load game data by game id"""
        self.gameid = game
        self.actionScoreTable.setEnabled(True)
        query = QSqlQuery(self.dbhandle)
        fields = ['hand', 'prevailing', 'player', 'wind', 
                                'balance', 'rotated']
        
        query.exec_("select %s from score where game=%d and hand="
            "(select max(hand) from score where game=%d)" \
            % (', '.join(fields), game, game))
        if query.next():
            roundwind = str(query.value(fields.index('prevailing')).toString())
            self.roundsFinished = WINDS.index(roundwind)
            self.handctr = query.value(fields.index('hand')).toInt()[0]
            self.rotated = query.value(fields.index('rotated')).toInt()[0]
        else:
            self.roundsFinished = 0
            self.handctr = 0
            self.rotated = 0
            
        query.exec_("select p0, p1, p2, p3 from game where id = %d" %game)
        query.next()
        for idx, player in enumerate(self.players):
            player.setNameList(self.playerNames.values()) # needed?
            playerid = query.value(idx).toInt()[0]
            player.name = self.playerNames[playerid]
        
        query.exec_("select player, wind, balance from score "
            "where game=%d and hand=%d" % (game, self.handctr))
        while query.next():
            playerid = query.value(0).toInt()[0]
            wind = str(query.value(1).toString())
            player = self.playerById(playerid)
            if not player:
                logException(BaseException(
                'game %d data inconsistent: player %d missing in game table' % \
                    (game, playerid)))
            player.clearBalance()
            player.pay(query.value(2).toInt()[0])
            player.wind.setWind(wind,  self.roundsFinished)
            player.fixName(playerid)
        self.initHand()

    def playerById(self, playerid):
        """lookup the player by id"""
        for player in self.players:
            if player.name == self.playerNames[playerid]:
                return player
        return None

    def createTables(self):
        """creates empty tables"""
        query = QSqlQuery(self.dbhandle)
        query.exec_("""CREATE TABLE player (
            id INTEGER PRIMARY KEY,
            name TEXT)""")
        query.exec_("""CREATE TABLE game (
            id integer primary key,
            starttime text default current_timestamp,
            endtime text,
            p0 integer constraint fk_p0 references player(id),
            p1 integer constraint fk_p1 references player(id),
            p2 integer constraint fk_p2 references player(id),
            p3 integer constraint fk_p3 references player(id))""")
        query.exec_("""CREATE TABLE score(
            game integer constraint fk_game references game(id),
            hand integer,
            rotated integer,
            player integer constraint fk_player references player(id),
            scoretime text,
            won integer references player(id),
            prevailing text,
            wind text,
            points integer,
            payments integer,
            balance integer)""")
            
    def addTestData(self):
        """adds test data to an empty data base"""
        query = QSqlQuery(self.dbhandle)
        for name in ['Wolfgang',  'Petra',  'Klaus',  'Heide']:
            query.exec_('INSERT INTO player (name) VALUES("%s")' % name)
        
    def creategui(self):
        """create and translate GUI from the ui.rc file: Menu and toolbars"""
        xmlFile = os.path.join(os.getcwd(), 'kmjui.rc')
        if os.path.exists(xmlFile):
            self.setupGUI(kdeui.KXmlGuiWindow.Default, xmlFile)
        else:
            self.setupGUI()
        self.retranslateUi()
        
    def kmjAction(self,  name, icon, slot):
        """simplify defining actions"""
        res = KAction(self)
        res.setIcon(kdeui.KIcon(icon))
        self.connect(res, SIGNAL('triggered()'), slot)
        self.actionCollection().addAction(name, res)
        return res
        
    def setupUi(self):
        """create all other widgets"""
        self.setObjectName("MainWindow")
        self.resize(793, 636)
        self.centralwidget = QWidget(self)
        self.widgetLayout = QGridLayout(self.centralwidget)
        self.widgetLayout.setColumnStretch(0, 1)
        self.widgetLayout.setRowStretch(0, 1)
        self.widgetLayout.setColumnStretch(1, 100)
        self.widgetLayout.setRowStretch(1, 100)
        self.widgetLayout.setColumnStretch(2, 1)
        self.widgetLayout.setRowStretch(2, 1)

        self.players =  [Player(WINDS[idx], self, (idx==0 or idx==2)) for idx in range(0, 4)]

        self.widgetLayout.addWidget(self.players[0], 1, 2, Qt.AlignLeft|Qt.AlignVCenter)
        self.widgetLayout.addWidget(self.players[1], 0, 1, Qt.AlignBottom|Qt.AlignHCenter)
        self.widgetLayout.addWidget(self.players[2], 1, 0, Qt.AlignRight|Qt.AlignVCenter)
        self.widgetLayout.addWidget(self.players[3], 2, 1, Qt.AlignTop|Qt.AlignHCenter)
    
        self.walls = Walls()
        self.widgetLayout.addWidget(self.walls, 1, 1, Qt.AlignCenter)
        
        # the player widgets should not exceed the wall length
        for player in self.players[1:4:2]:
            self.connect(self.walls, SIGNAL('wallSizeChanged'), player.setMaximumWidth)
        for player in self.players[0:4:2]:
            self.connect(self.walls, SIGNAL('wallSizeChanged'), player.setMaximumHeight)
        
        # try to ensure that the left and right player do not have greater wind tiles
        self.players[0].wind.sizeSource = self.players[1].wind
        self.players[2].wind.sizeSource = self.players[1].wind
        self.setCentralWidget(self.centralwidget)

        self.actionNewGame = self.kmjAction("new", "document-new", self.newGame)
        self.actionPlayers = self.kmjAction("players",  "personal",  self.slotPlayers)
        self.actionNewHand = self.kmjAction("newhand",  "object-rotate-left",  self.newHand)
        self.actionGames = self.kmjAction("load", "document-open", self.games)
        self.actionScoreTable = self.kmjAction("scoreTable", "format-list-ordered",self.scoreTable)
        self.actionScoreTable.setEnabled(False)
                               
        QMetaObject.connectSlotsByName(self)

    def retranslateUi(self):
        """retranslate"""
        self.actionNewGame.setText(i18n("&New"))
        self.actionPlayers.setText(i18n("&Players"))
        self.actionNewHand.setText(i18n("&New hand"))
        self.actionGames.setText(i18n("&Load"))
        self.actionScoreTable.setText(i18n("&Score Table"))
        for player in self.players:
            player.retranslateUi()
    
    def changeEvent(self, event):
        """when the applicationwide language changes, recreate GUI"""
        if event.type() == QEvent.LanguageChange:
            self.creategui()
                
    def slotPlayers(self):
        """show the player list"""
        if not self.playerwindow:
            self.playerwindow = PlayerList(self)
        self.playerwindow.show()

    def scoreTable(self):
        """show the score table"""
        if not self.scoreTableWindow:
            self.scoreTableWindow = ScoreTable(self)
        self.scoreTableWindow.show()

    def games(self):
        """show all games"""
        ps = Games(self)
        if ps.exec_():
            if ps.selectedGame is not None:
                self.loadGame(ps.selectedGame)
                self.scoreTable()
            else:
                self.newGame()
    
    def slotValidate(self):
        """validate data: Saving is only possible for valid data"""
        valid = not self.gameOver()
        if valid:
            if self.winner is not None and self.winner.score < 20:
                valid = False
        if valid:
            names = [p.name for p in self.players]
            for i in names:
                if names.count(i)>1:
                    valid = False
        self.actionNewHand.setEnabled(valid)

    def wonChanged(self):
        """if a new winner has been defined, uncheck any previous winner"""
        clicked = self.sender().parent()
        active = clicked.won.isChecked()
        if active:
            self.winner = clicked
            for player in self.players:
                if player != self.winner:
                    player.won.setChecked(False)
        else:
            if clicked == self.winner:
                self.winner = None
        self.slotValidate()

    def setupActions(self):
        """set up actions"""
        for idx, player in enumerate(self.players):
            self.connect(player.cbName, SIGNAL(
                'currentIndexChanged(const QString&)'),
                self.slotValidate)
            self.connect(player.spValue, SIGNAL(
                'valueChanged(int)'),
                self.slotValidate)
            self.connect(player.won, SIGNAL('stateChanged(int)'), self.wonChanged)
        kapp = KApplication.kApplication()
        KStandardAction.preferences(self.showSettings, self.actionCollection())
        KStandardAction.quit(kapp.quit, self.actionCollection())
        self.pref = Preferences()
        self.applySettings("settings")

    def applySettings(self,  name):
        """apply preferences"""
        for player in self.players:
            player.spValue.setRange(0, self.pref.upperLimit)
            player.wind.tileset = Tileset(self.pref.tileset)
        self.walls.tileset = Tileset(self.pref.tileset)
        
    def showSettings(self):
        """show preferences dialog. If it already is visible, do nothing"""
        if  kdeui.KConfigDialog.showDialog("settings"):
            return
        self.confDialog = ConfigDialog(self, "settings", self.pref)
        self.connect(self.confDialog, SIGNAL('settingsChanged(QString)'), 
           self.applySettings);
        self.confDialog.show()
        
    def newGame(self):
        """init a new game"""
        query = QSqlQuery(self.dbhandle)
        if not query.exec_("select id,name from player"):
            logMessage(query.lastError().text())
            sys.exit(1)
        idField, nameField = range(2)
        self.playerIds = {}
        self.playerNames = {}
        while query.next():
            nameid = query.value(idField).toInt()[0]
            name = str(query.value(nameField).toString())
            self.playerIds[name] = nameid
            self.playerNames[nameid] = name
        self.gameid = 0
        self.roundsFinished = 0
        self.handctr = 0
        self.rotated = 0
        self.starttime = datetime.datetime.now().replace(microsecond=0)
        # initialize the four winds with the first four players:
        names = self.playerNames.values()
        for idx, player in enumerate(self.players):
            player.fixName(0, False)
            player.setNameList(names)
            player.name = names[idx]
            player.wind.setWind(WINDS[idx],  0)
            player.clearBalance()
        self.initHand()

    def saveHand(self):
        """compute and save the scores. Makes player names immutable."""
        if self.winner is None:
            ret = QMessageBox.question(None, i18n("Draw?"),
                        i18n("Nobody said Mah Jongg. Is this a draw?"),
                        QMessageBox.Yes, QMessageBox.No)
            if ret == QMessageBox.No:
                return False
        self.payHand()      
        query = QSqlQuery(self.dbhandle)
        query.prepare("INSERT INTO SCORE "
            "(game,hand,player,scoretime,won,prevailing,wind,points,payments, balance,rotated) "
            "VALUES(:game,:hand,:player,:scoretime,"
            ":won,:prevailing,:wind,:points,:payments,:balance,:rotated)")
        query.bindValue(':game', QVariant(self.gameid))
        scoretime = datetime.datetime.now().replace(microsecond=0).isoformat()
        query.bindValue(':scoretime', QVariant(scoretime))
        for player in self.players:
            name = player.name
            playerid = self.playerIds[name]
            if self.handctr == 1:
                player.fixName(playerid)
            query.bindValue(':hand', QVariant(self.handctr))
            query.bindValue(':player', QVariant(playerid))
            query.bindValue(':wind', QVariant(player.wind.name))
            query.bindValue(':won', QVariant(player.won.isChecked()))
            query.bindValue(':prevailing', QVariant(WINDS[self.roundsFinished]))
            query.bindValue(':points', QVariant(player.score))
            query.bindValue(':payments', QVariant(player.payment))
            query.bindValue(':balance', QVariant(player.balance))
            query.bindValue(':rotated', QVariant(self.rotated))
            if not query.exec_():
                log('inserting into score:', query.lastError().text())
                sys.exit(1)
        self.actionScoreTable.setEnabled(True)
        return True
        
    def newHand(self):
        """save this hand and start the next"""
        if self.gameOver():
            ret = QMessageBox.question(None, i18n("New game?"),
                        i18n("This game is over. Do you want to start another game?"),
                        QMessageBox.Yes, QMessageBox.No)
            if ret == QMessageBox.Yes:
                self.newGame()
        elif self.handctr > 0:
            if not self.saveHand():
                return
        self.initHand()
                
    def initHand(self):
        """initialize the values for a new hand"""
        if self.handctr > 0:
            if self.winner is None or self.winner.wind.name != 'E':
                self.rotateWinds()
        else:
            self.initGame()
        for player in self.players:
            player.score = 0
        if self.winner:
            self.winner.won.setChecked(False)
        self.handctr += 1
        if self.scoreTableWindow:
            self.scoreTableWindow.loadTable()

    def initGame(self):
        """start a new game. If no hand is ever entered we have a game
            without hands in the database. So what - when loading old games
            those entries are ignored."""
        query = QSqlQuery(self.dbhandle)
        query.prepare("INSERT INTO GAME (starttime,p0,p1,p2,p3)"
            " VALUES(:starttime,:p0,:p1,:p2,:p3)")
        query.bindValue(":starttime", QVariant(self.starttime.isoformat()))
        for idx, player in enumerate(self.players):
            query.bindValue(":p%d" % idx, QVariant(
                    self.playerIds[player.name]))
        if not query.exec_():
            logMessage('inserting into game:' + query.lastError().text())
            sys.exit(1)
        # now find out which game id we just generated. Clumsy and racy.
        if not query.exec_("select id from game where starttime = '%s'" % \
                           self.starttime.isoformat()):
            logMessage('getting gameid:' + query.lastError().text())
            sys.exit(1)
        query.first()
        self.gameid = query.value(0).toInt()[0]
        
    def gameOver(self):
        """The game is over after 4 completed rounds"""
        return self.roundsFinished == 4
        
    def rotateWinds(self):
        """suprise: rotates the winds"""
        self.rotated += 1
        if self.rotated == 4:
            if self.roundsFinished < 4:
                self.roundsFinished += 1
            self.rotated = 0
        if self.gameOver():
            endtime = datetime.datetime.now().replace(microsecond=0).isoformat()
            query = QSqlQuery(self.dbhandle)
            query.prepare('UPDATE game set endtime = :endtime where id = :id')
            query.bindValue(':endtime', QVariant(endtime))
            query.bindValue(':id', QVariant(self.gameid))
            if not query.exec_():
                logMessage('updating game.endtime:'+ query.lastError().text())
                sys.exit(1)
        else:
            winds = [player.wind.name for player in self.players]
            winds = winds[3:] + winds[0:3]
            for idx,  newWind in enumerate(winds):
                self.players[idx].wind.setWind(newWind,  self.roundsFinished)
            if 0 < self.roundsFinished < 4 and self.rotated == 0:
                self.exchangeSeats()

    def findPlayer(self, wind):
        """returns the index and the player for wind"""
        for player in self.players:
            if player.wind.name == wind:
                return player
        logException(BaseException("no player has wind %s" % wind))
                
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
                        player1.pay(player1.score * efactor)
                    if player1 != self.winner:
                        player1.pay(-player2.score * efactor)

class About(object):
    """we need persistent data but do not want to spoil global namespace"""
    def __init__(self):
        self.appName     = "kmj"
        self.catalog     = ""
        self.programName = ki18n ("kmj")
        self.version     = "0.1"
        self.description = ki18n ("kmj - computes payments among the 4 players")
        self.kmjlicense     = kdecore.KAboutData.License_GPL
        self.kmjcopyright   = ki18n ("(c) 2008 Wolfgang Rohdewald")
        self.aboutText        = ki18n("This is the classical Mah Jongg for four players. "
            "If you are looking for the Mah Jongg solitaire please use the "
            "application kmahjongg. Right now this programm only allows to "
            "enter the scores, it will then compute the payments and show "
            "the ranking of the players.")
        self.homePage    = ""
        self.bugEmail    = "wolfgang@rohdewald.de"
        
        self.about  = kdecore.KAboutData (self.appName, self.catalog,
                        self.programName,
                        self.version, self.description,
                        self.kmjlicense, self.kmjcopyright, self.aboutText,
                        self.homePage, self.bugEmail)
                                
ABOUT = About()

kdecore.KCmdLineArgs.init (sys.argv, ABOUT.about)
APP = kdeui.KApplication()
MAINWINDOW =  MahJongg()
MAINWINDOW.show()
APP.exec_()
