# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2013 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

import datetime

from PyQt4.QtCore import QPointF, QRectF
from PyQt4.QtGui import QGraphicsRectItem, QGraphicsSimpleTextItem
from PyQt4.QtGui import QPushButton, QMessageBox, QComboBox


from common import Internal, isAlive, WINDS
from animation import animate
from log import logError, logDebug, logWarning, m18n
from query import Query, Transaction
from meld import Meld
from uitile import UITile
from board import WindLabel, Board, rotateCenter
from game import Game
from games import Games
from hand import Hand
from handboard import HandBoard
from player import Player, Players
from visible import VisiblePlayer
from tables import SelectRuleset
from uiwall import UIWall

class SwapDialog(QMessageBox):
    """ask the user if two players should change seats"""
    def __init__(self, swappers):
        QMessageBox.__init__(self)
        self.setWindowTitle(m18n("Swap Seats") + ' - Kajongg')
        self.setText(m18n("By the rules, %1 and %2 should now exchange their seats. ",
            swappers[0].name, swappers[1].name))
        self.yesAnswer = QPushButton(m18n("&Exchange"))
        self.addButton(self.yesAnswer, QMessageBox.YesRole)
        self.noAnswer = QPushButton(m18n("&Keep seat"))
        self.addButton(self.noAnswer, QMessageBox.NoRole)

class SelectPlayers(SelectRuleset):
    """a dialog for selecting four players. Used only for scoring game."""
    def __init__(self):
        SelectRuleset.__init__(self)
        Players.load()
        self.setWindowTitle(m18n('Select four players') + ' - Kajongg')
        self.names = None
        self.nameWidgets = []
        for idx, wind in enumerate(WINDS):
            cbName = QComboBox()
            cbName.manualSelect = False
            # increase width, we want to see the full window title
            cbName.setMinimumWidth(350) # is this good for all platforms?
            cbName.addItems(Players.humanNames.values())
            self.grid.addWidget(cbName, idx+1, 1)
            self.nameWidgets.append(cbName)
            self.grid.addWidget(WindLabel(wind), idx+1, 0)
            cbName.currentIndexChanged.connect(self.slotValidate)

        query = Query("select p0,p1,p2,p3 from game where seed is null and game.id = (select max(id) from game)")
        if len(query.records):
            for pidx, playerId in enumerate(query.records[0]):
                try:
                    playerName = Players.humanNames[playerId]
                    cbName = self.nameWidgets[pidx]
                    playerIdx = cbName.findText(playerName)
                    if playerIdx >= 0:
                        cbName.setCurrentIndex(playerIdx)
                except KeyError:
                    logError('database is inconsistent: player with id %d is in game but not in player' \
                               % playerId)
        self.slotValidate()

    def showEvent(self, dummyEvent):
        """start with player 0"""
        self.nameWidgets[0].setFocus()

    def slotValidate(self):
        """try to find 4 different players and update status of the Ok button"""
        changedCombo = self.sender()
        if not isinstance(changedCombo, QComboBox):
            changedCombo = self.nameWidgets[0]
        changedCombo.manualSelect = True
        usedNames = set([unicode(x.currentText()) for x in self.nameWidgets if x.manualSelect])
        allNames = set(Players.humanNames.values())
        unusedNames = allNames - usedNames
        for combo in self.nameWidgets:
            combo.blockSignals(True)
        try:
            for combo in self.nameWidgets:
                if combo.manualSelect:
                    continue
                comboName = unusedNames.pop()
                combo.clear()
                combo.addItems([comboName])
                combo.addItems(sorted(allNames - usedNames - set([comboName])))
        finally:
            for combo in self.nameWidgets:
                combo.blockSignals(False)
        self.names = list(unicode(cbName.currentText()) for cbName in self.nameWidgets)
        assert len(set(self.names)) == 4

class ScoringHandBoard(HandBoard):
    """a board showing the tiles a player holds"""
    # pylint: disable=too-many-public-methods,too-many-instance-attributes
    def __init__(self, player):
        self.__moveHelper = None
        self.uiMelds = []
        HandBoard.__init__(self, player)

    def meldVariants(self, tile, lowerHalf):
        """Kong might have variants"""
        result = []
        meld = Meld(self.uiMeldWithTile(tile))
        if lowerHalf:
            result.append(meld.toUpper())
        else:
            result.append(meld.toLower())
        if len(meld) == 4:
            if lowerHalf:
                meld = meld.toLower()
                meld = meld.toUpper(1, 3)
                result = [meld]
            else:
                meld = Meld(meld).expose(isClaiming=True)
                result.append(meld)
        return result

    def mapMouseTile(self, uiTile):
        """map the pressed tile to the wanted tile. For melds, this would
        be the first tile no matter which one is pressed"""
        return self.uiMeldWithTile(uiTile)[0]

    def uiMeldWithTile(self, uiTile):
        """returns the meld with uiTile"""
        for myMeld in self.uiMelds:
            if uiTile in myMeld:
                return myMeld

    def findUIMeld(self, meld):
        """find the first UIMeld matching the logical meld"""
        for result in self.uiMelds:
            if Meld(result) == meld:
                return result

    def assignUITiles(self, uiTile, meld): # pylint: disable=unused-argument
        """generate a UIMeld. First uiTile is given, the rest should be as defined by meld"""
        assert isinstance(uiTile, UITile), uiTile
        return self.uiMeldWithTile(uiTile)

    def sync(self, adding=None): # pylint: disable=unused-argument
        """place all tiles in ScoringHandBoard"""
        self.calcPlaces(sum(self.uiMelds, []))

    def deselect(self, meld):
        """remove meld from old board"""
        for idx, uiMeld in enumerate(self.uiMelds):
            if all(id(meld[x]) == id(uiMeld[x]) for x in range(len(meld))):
                del self.uiMelds[idx] # do not use uiMelds.remove: If we have 2
                break                 # identical melds, it removes the wrong one
        self.player.removeMeld(meld)  # uiMeld must already be deleted
        Internal.scene.handSelectorChanged(self)

    def dragMoveEvent(self, event):
        """allow dropping of uiTile from ourself only to other state (open/concealed)"""
        uiTile = event.mimeData().uiTile
        localY = self.mapFromScene(QPointF(event.scenePos())).y()
        centerY = self.rect().height()/2.0
        newLowerHalf = localY >= centerY
        noMansLand = centerY / 6
        if -noMansLand < localY - centerY < noMansLand and not uiTile.isBonus:
            doAccept = False
        elif uiTile.board != self:
            doAccept = True
        elif uiTile.isBonus:
            doAccept = False
        else:
            oldLowerHalf = uiTile.board.isHandBoard and uiTile in uiTile.board.lowerHalfTiles()
            doAccept = oldLowerHalf != newLowerHalf
        event.setAccepted(doAccept)

    def dropEvent(self, event):
        """drop into this handboard"""
        uiTile = event.mimeData().uiTile
        lowerHalf = self.mapFromScene(QPointF(event.scenePos())).y() >= self.rect().height()/2.0
        if self.dropTile(uiTile, lowerHalf):
            event.accept()
        else:
            event.ignore()
        self._noPen()

    def dropTile(self, uiTile, lowerHalf):
        """drop meld or uiTile into lower or upper half of our hand"""
        senderBoard = uiTile.board
        self.checkTiles()
        senderBoard.checkTiles()
        newMeld = senderBoard.chooseVariant(uiTile, lowerHalf)
        if not newMeld:
            self.checkTiles()
            senderBoard.checkTiles()
            return False
        uiMeld = senderBoard.assignUITiles(uiTile, newMeld)
        senderBoard.deselect(uiMeld)
        for uiTile, tile in zip(uiMeld, newMeld):
            uiTile.tile = tile
        self.uiMelds.append(uiMeld)
        self.player.addMeld(newMeld)
        self.sync()
        self.hasFocus = senderBoard == self or not senderBoard.uiTiles
        self.checkTiles()
        senderBoard.autoSelectTile()
        senderBoard.checkTiles()
        Internal.scene.handSelectorChanged(self)
        animate()
        self.checkTiles()
        return True

    def focusRectWidth(self):
        """how many tiles are in focus rect? We want to focus
        the entire meld"""
        meld = self.uiMeldWithTile(self.focusTile)
        if meld:
            return len(meld)
        else:
            return 1

    def addUITile(self, uiTile):
        Board.addUITile(self, uiTile)
        self.showMoveHelper()

    def removeUITile(self, uiTile):
        Board.removeUITile(self, uiTile)
        self.showMoveHelper()

    def showMoveHelper(self, visible=None):
        """show help text In empty HandBoards"""
        if visible is None:
            visible = not self.uiTiles
        if self.__moveHelper and not isAlive(self.__moveHelper):
            return
        if visible:
            if not self.__moveHelper:
                splitter = QGraphicsRectItem(self)
                hbCenter = self.rect().center()
                splitter.setRect(hbCenter.x() * 0.5, hbCenter.y(), hbCenter.x() * 1, 1)
                helpItems = [splitter]
                for name, yFactor in [(m18n('Move Exposed Tiles Here'), 0.5),
                                        (m18n('Move Concealed Tiles Here'), 1.5)]:
                    helper = QGraphicsSimpleTextItem(name, self)
                    helper.setScale(3)
                    nameRect = QRectF()
                    nameRect.setSize(helper.mapToParent(helper.boundingRect()).boundingRect().size())
                    center = QPointF(hbCenter)
                    center.setY(center.y() * yFactor)
                    helper.setPos(center - nameRect.center())
                    if self.sceneRotation() == 180:
                        rotateCenter(helper, 180)
                    helpItems.append(helper)
                self.__moveHelper = self.scene().createItemGroup(helpItems)
            self.__moveHelper.setVisible(True)
        else:
            if self.__moveHelper:
                self.__moveHelper.setVisible(False)

    def newLowerMelds(self):
        """a list of melds for the hand as it should look after sync"""
        return list(self.player.concealedMelds)

class ScoringPlayer(VisiblePlayer, Player):
    """Player in a scoring game"""
    # pylint: disable=too-many-public-methods
    def __init__(self, game):
        self.handBoard = None # because Player.init calls clearHand()
        self.manualRuleBoxes = []
        Player.__init__(self, game)
        VisiblePlayer.__init__(self)
        self.handBoard = ScoringHandBoard(self)

    def clearHand(self):
        """clears attributes related to current hand"""
        Player.clearHand(self)
        if self.game and self.game.wall:
            # is None while __del__
            self.front = self.game.wall[self.idx]
        if isAlive(self.handBoard):
            self.handBoard.setEnabled(True)
            self.handBoard.showMoveHelper()
        self.manualRuleBoxes = []

    def explainHand(self):
        """returns the hand to be explained"""
        return self.hand

    @property
    def handTotal(self):
        """the hand total of this player"""
        if self.hasManualScore():
            spValue = Internal.scene.scoringDialog.spValues[self.idx]
            return spValue.value()
        else:
            return self.hand.total()

    def hasManualScore(self):
        """True if no tiles are assigned to this player"""
        if Internal.scene.scoringDialog:
            return Internal.scene.scoringDialog.spValues[self.idx].isEnabled()
        return False

    def refreshManualRules(self, sender=None):
        """update status of manual rules"""
        assert Internal.scene
        if not self.handBoard:
            # might happen at program exit
            return
        currentScore = self.hand.score
        hasManualScore = self.hasManualScore()
        for box in self.manualRuleBoxes:
            applicable = bool(self.hand.manualRuleMayApply(box.rule))
            if hasManualScore:
                # only those rules which do not affect the score can be applied
                applicable = applicable and box.rule.hasNonValueAction()
            elif box != sender:
                applicable = applicable and self.__ruleChangesScore(box, currentScore)
            box.setApplicable(applicable)

    def __ruleChangesScore(self, box, currentScore):
        """does the rule actually influence the result?
        if the action would only influence the score and the rule does not change the score,
        ignore the rule. If however the action does other things like penalties leave it applicable"""
        if box.rule.hasNonValueAction():
            return True
        try:
            box.blockSignals(True)
            checked = box.isChecked()
            box.setChecked(not checked)
            newHand = self.computeHand()
        finally:
            box.setChecked(checked)
            box.blockSignals(False)
        return newHand.score > currentScore

    def __mjstring(self):
        """compile hand info into a string as needed by the scoring engine"""
        if self.lastTile and self.lastTile.istitle():
            lastSource = 'w'
        else:
            lastSource = 'd'
        declaration = ''
        rules = [x.rule for x in self.manualRuleBoxes if x.isChecked()]
        for rule in rules:
            options = rule.options
            if 'lastsource' in options:
                if lastSource != '1':
                    # this defines precedences for source of last tile
                    lastSource = options['lastsource']
            if 'declaration' in options:
                declaration = options['declaration']
        return ''.join(['m', lastSource, declaration])

    def __lastString(self):
        """compile hand info into a string as needed by the scoring engine"""
        if not self.lastTile:
            return ''
        if not self.handBoard.tilesByElement(self.lastTile):
            # this happens if we remove the meld with lastTile from the hand again
            return ''
        return 'L%s%s' % (self.lastTile, self.lastMeld)

    def computeHand(self, dummyWithTile=None):
        """returns a Hand object, using a cache"""
        self.lastTile = Internal.scene.computeLastTile()
        self.lastMeld = Internal.scene.computeLastMeld()
        string = ' '.join([self.scoringString(), self.__mjstring(), self.__lastString()])
        return Hand(self, string)

    def sortRulesByX(self, rules):
        """if this game has a GUI, sort rules by GUI order of the melds they are applied to"""
        withMelds = list(x for x in rules if x.meld)
        withoutMelds = list(x for x in rules if x not in withMelds)
        tuples = list(tuple([x, self.handBoard.findUIMeld(x.meld)]) for x in withMelds)
        tuples = sorted(tuples, key=lambda x: x[1][0].sortKey())
        return list(x[0] for x in tuples) + withoutMelds

    def addMeld(self, meld):
        """add meld to this hand in a scoring game"""
        meld = Meld(meld)  # convert UITile to Tile
        if len(meld) == 1 and meld[0].isBonus:
            self._bonusTiles.append(meld[0])
        elif not meld.isExposed and not meld.isKong:
            self._concealedMelds.append(meld)
        else:
            self._exposedMelds.append(meld)
        self._hand = None

    def removeMeld(self, uiMeld):
        """remove a meld from this hand in a scoring game"""
        meld = Meld(uiMeld)
        if len(meld) == 1 and meld[0].isBonus:
            self._bonusTiles.remove(meld[0])
        else:
            popped = False
            for melds in [self._concealedMelds, self._exposedMelds]:
                for idx, myMeld in enumerate(melds):
                    if myMeld == meld:
                        melds.pop(idx)
                        popped = True
            if not popped:
                logDebug('%s: %s.removeMeld did not find %s' % (self.name, self.__class__.__name__, meld), showStack=3)
                logDebug('    concealed: %s' % self._concealedMelds)
                logDebug('      exposed: %s' % self._exposedMelds)
        self._hand = None

class ScoringGame(Game):
    """we play manually on a real table with real tiles and use
    kajongg only for scoring"""
    playerClass =  ScoringPlayer
    wallClass = UIWall

    def __init__(self, names, ruleset, gameid=None, client=None, wantedGame=None):
        Game.__init__(self, names, ruleset, gameid=gameid, client=client, wantedGame=wantedGame)
        scene = Internal.scene
        scene.selectorBoard.load(self)
        self.prepareHand()
        self.initHand()
        Internal.scene.mainWindow.adjustView()
        Internal.scene.mainWindow.updateGUI()
        self.wall.decorate()
        self.throwDices()

    @Game.seed.getter
    def seed(self):
        """a scoring game never has a seed"""
        return None

    def _setHandSeed(self):
        """a scoring game does not need this"""
        return None

    def prepareHand(self):
        """prepare a scoring game hand"""
        Game.prepareHand(self)
        if not self.finished():
            selector = Internal.scene.selectorBoard
            selector.refill()
            selector.hasFocus = True
            self.wall.build(shuffleFirst=False)

    def nextScoringHand(self):
        """save hand to database, update score table and balance in status line, prepare next hand"""
        if self.winner:
            for player in self.players:
                player.usedDangerousFrom = None
                for ruleBox in player.manualRuleBoxes:
                    rule = ruleBox.rule
                    if rule.name == 'Dangerous Game' and ruleBox.isChecked():
                        self.winner.usedDangerousFrom = player
        self.saveHand()
        self.maybeRotateWinds()
        self.prepareHand()
        self.initHand()
        Internal.scene.scoringDialog.clear()

    def close(self):
        """log off from the server and return a Deferred"""
        scene = Internal.scene
        scene.selectorBoard.uiTiles = []
        scene.selectorBoard.allSelectorTiles = []
        if isAlive(scene):
            scene.removeTiles()
        for player in self.players:
            player.hide()
        if self.wall:
            self.wall.hide()
        return Game.close(self)

    @staticmethod
    def isScoringGame():
        """are we scoring a manual game?"""
        return True

    def saveStartTime(self):
        """write a new entry in the game table with the selected players"""
        Game.saveStartTime(self)
        # for PlayingGame, this one is already done in Connection.__updateServerInfoInDatabase
        known = Query('update server set lastruleset=? where url=?',
            list([self.ruleset.rulesetId, Query.localServerName]))
        if not known:
            Query('insert into server(url,lastruleset) values(?,?)',
                list([self.ruleset.rulesetId, Query.localServerName]))

    def _setGameId(self):
        """get a new id"""
        if not self.gameid:
            # a loaded game has gameid already set
            self.gameid = self._newGameId()

    def _mustExchangeSeats(self, pairs):
        """filter: which player pairs should really swap places?"""
        # pylint: disable=no-self-use
        # I do not understand the logic of the exec return value. The yes button returns 0
        # and the no button returns 1. According to the C++ doc, the return value is an
        # opaque value that should not be used."""
        return list(x for x in pairs if SwapDialog(x).exec_() == 0)

    def savePenalty(self, player, offense, amount):
        """save computed values to database, update score table and balance in status line"""
        scoretime = datetime.datetime.now().replace(microsecond=0).isoformat()
        with Transaction():
            Query("INSERT INTO SCORE "
                "(game,penalty,hand,data,manualrules,player,scoretime,"
                "won,prevailing,wind,points,payments, balance,rotated,notrotated) "
                "VALUES(%d,1,%d,?,?,%d,'%s',%d,'%s','%s',%d,%d,%d,%d,%d)" % \
                (self.gameid, self.handctr, player.nameid,
                    scoretime, int(player == self.winner),
                    WINDS[self.roundsFinished % 4], player.wind, 0,
                    amount, player.balance, self.rotated, self.notRotated),
                list([player.hand.string, offense.name]))
        Internal.mainWindow.updateGUI()

def scoreGame():
    """show all games, select an existing game or create a new game"""
    Players.load()
    if len(Players.humanNames) < 4:
        logWarning(m18n('Please define four players in <interface>Settings|Players</interface>'))
        return
    gameSelector = Games(Internal.mainWindow)
    selected = None
    if not gameSelector.exec_():
        return
    selected = gameSelector.selectedGame
    gameSelector.close()
    if selected is not None:
        return ScoringGame.loadFromDB(selected)
    else:
        selectDialog = SelectPlayers()
        if not selectDialog.exec_():
            return
        return ScoringGame(selectDialog.names, selectDialog.cbRuleset.current)
