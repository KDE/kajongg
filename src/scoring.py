# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

import datetime
from typing import Tuple, Optional, TYPE_CHECKING, List, cast, Any

from qt import QPointF, QRectF, QDialogButtonBox
from qt import QGraphicsRectItem, QGraphicsSimpleTextItem
from qt import QPushButton, QMessageBox, QComboBox


from common import Internal, isAlive, Debug
from tile import MeldList
from wind import Wind
from tilesource import TileSource
from animation import animate
from log import logException, logDebug, logWarning, i18n
from query import Query
from uitile import UITile, UIMeld
from board import WindLabel
from game import Game
from games import Games
from hand import Hand
from handboard import HandBoard, TileAttr
from player import Player, Players
from visible import VisiblePlayer
from tables import SelectRuleset
from uiwall import UIWall, SideText
from guiutil import decorateWindow, BlockSignals, rotateCenter, sceneRotation
from mi18n import i18nc
from util import callers

if TYPE_CHECKING:
    from qt import QWidget, QEvent, QGraphicsSceneDragDropEvent, QGraphicsItem, QGraphicsItemGroup, QObject
    from tile import Tile, Meld
    from board import MimeData, SelectorBoard
    from scoringdialog import RuleBox
    from scene import ScoringScene
    from rule import Score, UsedRule, Ruleset, Rule
    from client import Client

def scoringScene() ->'ScoringScene':
    """shortcut"""
    result = cast('ScoringScene', Internal.scene)
    assert result
    return result

class SwapDialog(QMessageBox):

    """ask the user if two players should change seats"""

    def __init__(self, swappers:List[Player], parent:Optional['QWidget']=None) ->None:
        super().__init__(parent)
        decorateWindow(self, i18nc("@title:window", "Swap Seats"))
        self.setText(
            i18n("By the rules, %1 and %2 should now exchange their seats. ",
                 swappers[0].name, swappers[1].name))
        self.yesAnswer = QPushButton(i18n("&Exchange"))
        self.addButton(self.yesAnswer, QMessageBox.ButtonRole.YesRole)
        self.noAnswer = QPushButton(i18n("&Keep seat"))
        self.addButton(self.noAnswer, QMessageBox.ButtonRole.NoRole)


class ScoringComboBox(QComboBox):

    """with flag manualSelect"""

    def __init__(self, parent:Optional['QWidget']=None):
        super().__init__(parent)
        self.manualSelect = False

class SelectPlayers(SelectRuleset):

    """a dialog for selecting four players. Used only for scoring game."""

    def __init__(self) ->None:
        super().__init__()
        Players.load()
        decorateWindow(self, i18nc("@title:window", "Select four players"))
        self.names:List[str]
        self.nameWidgets:List[ScoringComboBox] = []
        for idx, wind in enumerate(Wind.all4):
            cbName = ScoringComboBox()
            # increase width, we want to see the full window title
            cbName.setMinimumWidth(350)  # is this good for all platforms?
            cbName.addItems(list(Players.humanNames.values()))
            self.grid.addWidget(cbName, idx + 1, 1)
            self.nameWidgets.append(cbName)
            self.grid.addWidget(WindLabel(wind), idx + 1, 0)
            cbName.currentIndexChanged.connect(self.slotValidate)

        # scoring games have seed 0
        # a scoring game which only just started or threw an exception might have p0,p1,p2,p3 = null
        query = Query(
            "select id,p0,p1,p2,p3 from game where seed=0 and p0 is not null order by id desc limit 1")
        if query.records:
            record = query.record()
            max_game_id = record[0]
            with BlockSignals(self.nameWidgets):
                for cbName, playerId in zip(self.nameWidgets, record[1:]):
                    if playerId not in Players.humanNames:
                        logException(f'database {Internal.db.path} is inconsistent: '
                                     f'game {max_game_id}: player with id {playerId} '
                                     f'is in game but not in player')
                    playerName = Players.humanNames[playerId]
                    playerIdx = cbName.findText(playerName)
                    if playerIdx >= 0:
                        cbName.setCurrentIndex(playerIdx)
        self.slotValidate()

    def showEvent(self, unusedEvent:Optional['QEvent']) ->None:
        """start with player 0"""
        self.nameWidgets[0].setFocus()

    def __selectedNames(self) ->set[str]:
        """A set with the currently selected names"""
        return {cbName.currentText() for cbName in self.nameWidgets}

    def slotValidate(self) ->None:
        """try to find 4 different players and update status of the Ok button"""
        changedCombo = self.sender()
        if not isinstance(changedCombo, ScoringComboBox):
            changedCombo = self.nameWidgets[0]
        changedCombo.manualSelect = True
        allNames = set(Players.humanNames.values())
        unusedNames = allNames - self.__selectedNames()
        with BlockSignals(self.nameWidgets):
            used = {x.currentText() for x in self.nameWidgets if x.manualSelect}
            for combo in self.nameWidgets:
                if not combo.manualSelect:
                    if combo.currentText() in used:
                        comboName = unusedNames.pop()
                        combo.clear()
                        combo.addItems([comboName])
                        used.add(combo.currentText())
            for combo in self.nameWidgets:
                comboName = combo.currentText()
                combo.clear()
                combo.addItems([comboName])
                combo.addItems(sorted(
                    allNames - self.__selectedNames() - {comboName}))
                combo.setCurrentIndex(0)
        ok_button = self.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button:
            ok_button.setEnabled(len(self.__selectedNames()) == 4)
        self.names = [cbName.currentText() for cbName in self.nameWidgets]


class ScoringTileAttr(TileAttr):

    """Tile appearance is different in a ScoringHandBoard"""

    def _setDark(self) ->bool:
        """should the tile appear darker?"""
        return bool(self.yoffset) or self.tile.isConcealed

    def _setFocusable(self, hand:'HandBoard', meld:'Meld', idx:Optional[int]) ->bool:
        """in a scoring handboard, only the first tile of a meld is focusable"""
        return idx == 0


class ScoringHandBoard(HandBoard):

    """a board showing the tiles a player holds"""
    tileAttrClass = ScoringTileAttr

    def __init__(self, player:'ScoringPlayer') ->None:
        self.__moveHelper:Optional['QGraphicsItemGroup'] = None
        self.uiMelds:List[UIMeld] = []  # uiMelds and uiTiles are administered independently
        super().__init__(player)
        self.player:'ScoringPlayer'

    def meldVariants(self, tile:UITile, forLowerHalf:bool) ->MeldList:
        """Kong might have variants"""
        result = MeldList()
        uimeld = self.uiMeldWithTile(tile)
        if not uimeld:
            logWarning(f'ScoringHandBoard.meldVariants: no meld found for {tile}')
            return result
        meld = uimeld.meld
        result.append(meld.concealed if forLowerHalf else meld.exposed)
        if len(meld) == 4:
            if forLowerHalf:
                result.append(meld.declared)
            else:
                result.append(meld.exposedClaimed)
        return result

    def mapMouseTile(self, uiTile:UITile) ->UITile:
        """map the pressed tile to the wanted tile. For melds, this would
        be the first tile no matter which one is pressed"""
        uiMeld = self.uiMeldWithTile(uiTile)
        assert uiMeld
        return uiMeld[0]

    def uiMeldWithTile(self, uiTile:UITile, remove:bool=False) ->UIMeld:
        """return the meld with uiTile, optionally removing it"""
        for idx, myMeld in enumerate(self.uiMelds):
            if uiTile in myMeld:
                uiMeld = self.uiMelds[idx]
                if remove:
                    if Debug.uitiles:
                        logDebug(f'{callers()}.{self.debug_name()}.uiMeldWithTile({uiTile}) removes {uiMeld}')
                    del self.uiMelds[idx]
                    self.player.removeMeld(uiMeld.meld)
                    if Debug.uitiles:
                        logDebug(f'{self.debug_name()}.loseMeld({uiTile}) removed {uiMeld.meld} from {self.player}')
                    self.sync()
                return myMeld
        return UIMeld(uiTile)

    def findUIMeld(self, meld:Optional['Meld']) ->UIMeld:
        """find the first UIMeld matching the logical meld"""
        for result in self.uiMelds:
            if result.meld == meld:
                return result
        logWarning(f'Scoring game: cannot find UIMeld for {meld}')
        if self.uiMelds:
            # when could this happen?
            logWarning(f'XXXXXXXXXXXXXX findUIMeld returning uiMelds[1]: {self.uiMelds[1]}')
            return self.uiMelds[1] # FIXME why not 0 ?
        raise ValueError('Scoring Game: findUIMeld() in absence of any uiMelds')

    def loseMeld(self, uiTile:UITile, meld:'Meld') ->UIMeld:  # pylint: disable=unused-argument
        """loses a UIMeld. Only first uiTile is given"""
        assert isinstance(uiTile, UITile), uiTile
        uiMeld = self.uiMeldWithTile(uiTile, remove=True)
        scoringScene().handSelectorChanged(self)
        return uiMeld

    def sync(self, adding:Optional[List[UITile]]=None) ->None:
        """place all tiles in ScoringHandBoard"""
        col = [0.0, 0.0]
        boni:List[UITile] = []
        for uiMeld in self.uiMelds:
            if uiMeld[0].tile.isBonus:
                boni.append(uiMeld[0])
                continue
            row = 0 if uiMeld.meld[0].isExposed else 1
            for idx, tile in enumerate(uiMeld):
                tile.level = 0
                tile.setBoard(self, col[row], row)
                # FIXME Folgendes UIMeld sollte sich selber so einstellen
                tile.focusable = idx == 0
                tile.dark = bool(row) or tile.tile.isConcealed
                col[row] += 1
            col[row] += self.exposedMeldDistance
        self._placeBonusTiles(col, boni)
        # self.checkTiles() does not work here

    def dragMoveEvent(self, event:Optional['QGraphicsSceneDragDropEvent']) ->None:
        """allow dropping of uiTile from ourself only to other state (open/concealed)"""
        if not event:
            return
        uiTile = cast('MimeData', event.mimeData()).uiTile
        localY = self.mapFromScene(QPointF(event.scenePos())).y()
        centerY = self.rect().height() / 2.0
        newLowerHalf = localY >= centerY
        noMansLand = centerY / 6
        if -noMansLand < localY - centerY < noMansLand and not uiTile.isBonus:
            doAccept = False
        elif uiTile.board != self:
            doAccept = True
        elif uiTile.isBonus:
            doAccept = False
        else:
            oldLowerHalf = False
            if uiTile.board.isHandBoard:
                oldLowerHalf = uiTile in cast('HandBoard', uiTile.board).lowerHalfTiles()
            doAccept = oldLowerHalf != newLowerHalf
        event.setAccepted(doAccept)

    def dropEvent(self, event:Optional['QGraphicsSceneDragDropEvent']) ->None:
        """drop into this handboard"""
        if not event:
            return
        uiTile = cast('MimeData', event.mimeData()).uiTile
        forLowerHalf = self.mapFromScene(
            QPointF(event.scenePos())).y() >= self.rect().height() / 2.0
        if self.dropMeld(uiTile, forLowerHalf):
            event.accept()
        else:
            event.ignore()
        self._noPen()

    def dropMeld(self, uiTile:UITile, forLowerHalf:bool) ->bool:
        """drop UIMeld containing uiTile into lower or upper half of our hand"""
        senderBoard = cast('SelectorBoard', uiTile.board)
        assert senderBoard
        newMeld = senderBoard.chooseVariant(uiTile, forLowerHalf)
        if not newMeld:
            return False
        uiMeld = senderBoard.loseMeld(uiTile, newMeld)
        for uitile, tile in zip(uiMeld, newMeld):
            uitile.change_name(tile)
        self.uiMelds.append(uiMeld)
        if Debug.uitiles:
            logDebug(f'{self.debug_name()}.dropMeld({uiTile}) appends{uiMeld}')
        assert self.player
        self.player.addMeld(uiMeld.meld)
        if Debug.uitiles:
            logDebug(f'{self.debug_name()}.dropMeld({uiTile}) added {uiMeld.meld} to {self.player}')
        self.sync()
        self.hasLogicalFocus = senderBoard == self or senderBoard.empty
        self.checkTiles()
        senderBoard.autoSelectTile()
        senderBoard.checkTiles()
        if senderBoard is not self and senderBoard.isHandBoard:
            scoringScene().handSelectorChanged(cast('HandBoard', senderBoard))
        scoringScene().handSelectorChanged(self)
        animate()
        self.checkTiles()
        return True

    def focusRectWidth(self) ->int:
        """how many tiles are in focus rect? We want to focus
        the entire meld"""
        focus = self.focusTile
        if not focus:
            return 1
        meld = self.uiMeldWithTile(focus)
        if not meld:
            logWarning(f'ScoringBoard.focusRectWidth: there is no meld with focus tile {focus}')
            return 1
        if Debug.focusable:
            logDebug(f'{callers()}.{self}.focusRectWidth for focusTile {self.focusTile} '
                     f'found UIMeld {meld} with tiles {list(x for x in meld)}')
        return len(meld)

    def addUITile(self, uiTile:UITile) ->None:
        super().addUITile(uiTile)
        self.showMoveHelper()

    def removeUITile(self, uiTile:UITile) ->None:
        super().removeUITile(uiTile)
        self.showMoveHelper()

    def showMoveHelper(self, visible:Optional[bool]=None) ->None:
        """show help text In empty HandBoards"""
        if visible is None:
            visible = self.empty
        if self.__moveHelper and not isAlive(self.__moveHelper):
            return
        if visible:
            if not self.__moveHelper:
                splitter = QGraphicsRectItem(self)
                hbCenter = self.rect().center()
                splitter.setRect(
                    hbCenter.x() * 0.5,
                    hbCenter.y(),
                    hbCenter.x() * 1,
                    1)
                helpItems:List['QGraphicsItem'] = [splitter]
                for name, yFactor in [(i18n('Move Exposed Tiles Here'), 0.5),
                                      (i18n('Move Concealed Tiles Here'), 1.5)]:
                    helper = QGraphicsSimpleTextItem(name, self)
                    helper.setScale(3)
                    nameRect = QRectF()
                    nameRect.setSize(
                        helper.mapToParent(helper.boundingRect()).boundingRect().size())
                    center = QPointF(hbCenter)
                    center.setY(center.y() * yFactor)
                    _ = center
                    _ -= nameRect.center()
                    helper.setPos(_)
                    if sceneRotation(self) == 180:
                        rotateCenter(helper, 180)
                    helpItems.append(helper)
                scene = self.scene()
                if scene:
                    self.__moveHelper = scene.createItemGroup(helpItems)
            if self.__moveHelper:
                self.__moveHelper.setVisible(True)
        else:
            if self.__moveHelper:
                self.__moveHelper.setVisible(False)


class ScoringPlayer(VisiblePlayer, Player):

    """Player in a scoring game"""

    def __init__(self, game:'ScoringGame', name:str) ->None:
        self.handBoard = None  # because Player.init calls clearHand()
        self.manualRuleBoxes:List['RuleBox'] = []
        Player.__init__(self, game, name)
        VisiblePlayer.__init__(self)
        self.handBoard = ScoringHandBoard(self)
        self.game:'ScoringGame'

    def clearHand(self) ->None:
        """clears attributes related to current hand"""
        super().clearHand()
        if self.game and self.game.wall:
            assert self.game
            assert self.game.wall
            # is None while __del__
            self.front = self.game.wall[self.idx]
            if hasattr(self, 'sideText'):
                self.sideText.board = self.front
        if isAlive(self.handBoard):
            assert (_ := cast(ScoringHandBoard, self.handBoard))
            _.setEnabled(True)
            _.showMoveHelper()
            _.uiMelds = []
        self.manualRuleBoxes = []

    def explainHand(self) ->'Hand':
        """return the hand to be explained"""
        return self.hand

    @property
    def handTotal(self) ->int:
        """the hand total of this player"""
        if self.hasManualScore():
            assert (_ := scoringScene().scoringDialog)
            spValue = _.spValues[self.idx]
            return spValue.value()
        return self.hand.total()

    def hasManualScore(self) ->bool:
        """True if no tiles are assigned to this player"""
        if _ := scoringScene().scoringDialog:
            return _.spValues[self.idx].isEnabled()
        return False

    def refreshManualRules(self, sender:Optional['QObject']=None) ->None:
        """update status of manual rules"""
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
                applicable = applicable and self.__ruleChangesScore(
                    box, currentScore)
            box.setApplicable(applicable)

    def __ruleChangesScore(self, box:'RuleBox', currentScore:'Score') ->bool:
        """does the rule actually influence the result?
        if the action would only influence the score and the rule does not change the score,
        ignore the rule. If however the action does other things like penalties leave it applicable"""
        if box.rule.hasNonValueAction():
            return True
        with BlockSignals([box]):
            try:
                checked = box.isChecked()
                box.setChecked(not checked)
                newHand = self.computeHand()
            finally:
                box.setChecked(checked)
        return newHand.score > currentScore

    def __mjstring(self) ->str:
        """compile hand info into a string as needed by the scoring engine"""
        if self.lastTile and self.lastTile.isConcealed:
            lastSource = TileSource.LivingWall.char
        else:
            lastSource = TileSource.LivingWallDiscard.char
        announcements = set()
        rules = [x.rule for x in self.manualRuleBoxes if x.isChecked()]
        for rule in rules:
            options = rule.options
            if 'lastsource' in options:
                if lastSource != TileSource.East14th.char:
                    # this defines precedences for source of last tile
                    lastSource = options['lastsource']
            if 'announcements' in options:
                announcements |= set(options['announcements'])
        return ''.join(['m', lastSource, ''.join(sorted(announcements))])

    def __lastString(self) ->str:
        """compile hand info into a string as needed by the scoring engine"""
        if not self.lastTile:
            return ''
        assert self.handBoard
        if not self.handBoard.tilesByElement(self.lastTile):
            # this happens if we remove the meld with lastTile from the hand
            # again
            return ''
        return f'L{self.lastTile}{self.lastMeld}'

    def computeHand(self) ->Hand:
        """return a Hand object, using a cache"""
        self.lastTile = scoringScene().computeLastTile()
        self.lastMeld = scoringScene().computeLastMeld()
        string = ' '.join(
            [self.scoringString(),
             self.__mjstring(),
             self.__lastString()])
        return Hand(self, string)

    def sortRulesByX(self, rules:List['UsedRule']) ->List['UsedRule']:
        """if this game has a GUI, sort rules by GUI order of the melds they are applied to"""
        rulesWithMelds = [x for x in rules if x.meld]
        rulesWithoutMelds = [x for x in rules if x not in rulesWithMelds]
        assert (handBoard := cast('ScoringHandBoard', self.handBoard))
        tuples:Any = [tuple([x, handBoard.findUIMeld(x.meld)]) for x in rulesWithMelds]
        sorted_tuples = sorted(tuples, key=lambda x: x[1][0].sortKey())
        return [x[0] for x in sorted_tuples] + rulesWithoutMelds

    def addMeld(self, meld:'Meld') ->None:
        """add meld to this hand in a scoring game"""
        if meld.isBonus:
            self._bonusTiles.append(meld[0])
            if Debug.scoring:
                logDebug(f'{self} gets bonus tile {meld[0]}')
        elif meld.isConcealed and not meld.isKong:
            self._concealedMelds.append(meld)
            if Debug.scoring:
                logDebug(f'{self} gets concealed meld {meld}')
        else:
            self._exposedMelds.append(meld)
            if Debug.scoring:
                logDebug(f'{self} gets exposed meld {meld}')
        self._hand = None

    def removeMeld(self, meld:'Meld') ->None:
        """remove a meld from this hand in a scoring game"""
        if meld.isBonus:
            self._bonusTiles.remove(meld[0])
            if Debug.scoring:
                logDebug(f'{self} loses bonus tile {meld[0]}')
        else:
            popped = None
            for melds in [self._concealedMelds, self._exposedMelds]:
                for idx, myMeld in enumerate(melds):
                    if myMeld == meld:
                        popped = melds.pop(idx)
                        break
            if not popped:
                logDebug(
                    f'{self.name}: {self.__class__.__name__}.removeMeld did not find {meld}', showStack=True)
                logDebug(f'    concealed: {self._concealedMelds}')
                logDebug(f'      exposed: {self._exposedMelds}')
            else:
                if Debug.scoring:
                    logDebug(f'{self} lost meld {popped}')
        self._hand = None


class ScoringGame(Game):

    """we play manually on a real table with real tiles and use
    Kajongg only for scoring"""
    playerClass = ScoringPlayer
    wallClass = UIWall

    def __init__(self, names:List[Tuple[Wind, str]], ruleset:'Ruleset', gameid:Optional[int]=None,
        wantedGame:Optional[str]=None, client:Optional['Client']=None) ->None:
        super().__init__(
            names,
            ruleset,
            gameid=gameid,
            client=client,
            wantedGame=wantedGame)
        self.wall:'UIWall'
        self.shouldSave = True
        scoringScene().selectorBoard.load(self)
        self.prepareHand()
        self.initHand()
        scoringScene().mainWindow.adjustMainView()
        scoringScene().mainWindow.updateGUI()
        self.wall.decorate4()
        self.throwDices()

    @Game.seed.getter  # type:ignore[attr-defined]
    def seed(self) ->int: # looks like a pylint bug pylint: disable=invalid-overridden-method
        """a scoring game never has a seed"""
        return 0

    def _setHandSeed(self) ->None:
        """a scoring game does not need this"""
        return None

    def prepareHand(self) ->None:
        """prepare a scoring game hand"""
        Game.prepareHand(self)
        if not self.finished():
            selector = scoringScene().selectorBoard
            selector.refill()
            selector.hasLogicalFocus = True
            self.wall.build(shuffleFirst=False)

    def nextScoringHand(self) ->None:
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
        if _ := scoringScene().scoringDialog:
            _.clear()

    def close(self) ->None:
        """log off from the server and return a Deferred"""
        scoringScene().selectorBoard.uiTiles = []
        scoringScene().selectorBoard.allSelectorTiles = []
        if isAlive(scoringScene()):
            scoringScene().removeTiles()
        for player in self.players:
            player.hide()
        if self.wall:
            self.wall.hide()
        SideText.removeAll()
        return super().close()

    @staticmethod
    def isScoringGame() ->bool:
        """are we scoring a manual game?"""
        return True

    def saveStartTime(self) ->None:
        """write a new entry in the game table with the selected players"""
        Game.saveStartTime(self)
        # for PlayingGame, this one is already done in
        # Connection.__updateServerInfoInDatabase
        known = Query('update server set lastruleset=? where url=?',
                      (self.ruleset.rulesetId, Query.localServerName))
        if not known:
            Query('insert into server(url,lastruleset) values(?,?)',
                  (self.ruleset.rulesetId, Query.localServerName))

    def _setGameId(self) ->None:
        """get a new id"""
        if not self.gameid:
            # a loaded game has gameid already set
            self.gameid = Query("insert into game(seed) values(0)").cursor.lastrowid

    def _mustExchangeSeats(self, pairs:List[List[Player]]) ->List[List[Player]]:
        """filter: which player pairs should really swap places?"""
        # I do not understand the logic of the exec return value. The yes button returns 0
        # and the no button returns 1. According to the C++ doc, the return value is an
        # opaque value that should not be used."""
        return [x for x in pairs if SwapDialog(x).exec() == 0]

    def savePenalty(self, player:'ScoringPlayer', offense:'Rule', amount:int) ->None:
        """save computed values to database, update score table and balance in status line"""
        scoretime = datetime.datetime.now().replace(microsecond=0).isoformat()
        assert self.gameid
        Query("INSERT INTO SCORE "
              "(game,penalty,hand,data,manualrules,player,scoretime,"
              "won,prevailing,wind,points,payments, balance,rotated,notrotated) "
              f"VALUES({int(self.gameid)},1,{int(self.point.handCount)},?,?,{player.nameid},'{scoretime}',"
              f"{int(player == self.winner)},'{self.point.prevailing}','{player.wind}',0,{amount},"
              f"{player.balance},{int(self.point.rotated)}, {int(self.point.notRotated)})",
              (player.hand.string, offense.name))
        assert Internal.mainWindow
        Internal.mainWindow.updateGUI()

def scoreGame() ->Optional[ScoringGame]:
    """show all games, select an existing game or create a new game"""
    Players.load()
    if len(Players.humanNames) < 4:
        logWarning(
            i18n('Please define four players in <interface>Settings|Players</interface>'))
        return None
    gameSelector = Games(Internal.mainWindow)
    selected = None
    if not gameSelector.exec():
        return None
    selected = gameSelector.selectedGame
    gameSelector.close()
    if selected:
        return cast(ScoringGame, ScoringGame.loadFromDB(selected))
    selectDialog = SelectPlayers()
    if not selectDialog.exec():
        return None
    return ScoringGame(list(zip(Wind.all4, selectDialog.names)), selectDialog.cbRuleset.current)
