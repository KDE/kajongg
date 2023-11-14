# -*- coding: utf-8 -*-

"""
Copyright (C) 2013-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

from typing import List, Any, Optional, Tuple, TYPE_CHECKING, cast

from qt import QColor

from mi18n import i18nc
from message import Message
from common import Internal, isAlive
from player import Player, PlayingPlayer
from game import PlayingGame
from tile import Tile, TileList
from handboard import PlayingHandBoard
from animation import AnimationSpeed
from uiwall import UIWall, SideText
from wind import Wind

if TYPE_CHECKING:
    from tile import Tiles, Meld, MeldList
    from uitile import UITile
    from uiwall import UIWallSide
    from hand import Hand
    from rule import Ruleset
    from client import Client
    from scene import PlayingScene

class VisiblePlayer(Player):

    """Mixin for VisiblePlayingPlayer and ScoringPlayer"""

    def __init__(self) ->None:
        # pylint: disable=super-init-not-called
        assert self.game
        assert self.game.wall
        self.__front = cast(UIWall, self.game.wall)[self.idx]
        self.sideText = SideText()
        self.sideText.board = self.__front

    def hide(self) ->None:
        """clear visible data and hide"""
        self.clearHand()
        if isAlive(self.handBoard):
            assert self.handBoard
            self.handBoard.hide()

    @property
    def idx(self) ->int:
        """our index in the player list"""
        assert self.game
        if self not in self.game.players:
            # we will be added next
            return len(self.game.players)
        return self.game.players.index(self)

    @property
    def front(self) ->'UIWallSide':
        """front"""
        return self.__front

    @front.setter
    def front(self, value:'UIWallSide') ->None:
        """also assign handBoard to front"""
        self.__front = value
        if self.handBoard:
            self.handBoard.setParentItem(value)

    def syncHandBoard(self, adding:Optional[List['UITile']]=None) ->None:
        """update display of handBoard. Set Focus to tileName."""
        assert self.handBoard
        self.handBoard.sync(adding)

    def showInfo(self) ->None:
        """show player info on the wall"""
        side = self.front
        self.sideText.text = '{} - {}'.format(self.localName, self.explainHand().total())  # type:ignore[attr-defined]
        self.colorizeName()
        _ = Wind.all4[self.wind].disc
        assert _
        side.disc = _
        assert self.game
        side.disc.prevailing = self.game.roundsFinished > 0
        side.disc.board = self.front


class VisiblePlayingPlayer(VisiblePlayer, PlayingPlayer):

    """this player instance has a visual representation"""

    def __init__(self, game:'VisiblePlayingGame', name:str) ->None:
        assert game
        self.handBoard = None  # because Player.init calls clearHand()
        PlayingPlayer.__init__(self, game, name)
        VisiblePlayer.__init__(self)
        self.handBoard = PlayingHandBoard(self)
        self.voice = None

    def clearHand(self) ->None:
        """clears attributes related to current hand"""
        super().clearHand()
        if self.game and self.game.wall:
            # is None while __del__
            self.front = cast(UIWall, self.game.wall)[self.idx]
        if self.handBoard:
            self.handBoard.setEnabled(
                self.game is not None and self.game.belongsToHumanPlayer(
                ) and self == self.game.myself)

    def explainHand(self) ->'Hand':
        """return the hand to be explained. Same as current unless we need to discard.
        In that case, make an educated guess about the discard.
        For player==game.myself, use the focused tile."""
        hand = self.hand
        assert self.handBoard
        if hand and hand.tiles and self._concealedTiles:
            if hand.lenOffset == 1 and not hand.won:
                if any(not x.isKnown for x in self._concealedTiles):
                    hand -= Tile.unknown
                elif self.handBoard.focusTile:
                    hand -= self.handBoard.focusTile.tile
        return hand

    def colorizeName(self) ->None:
        """set the color to be used for showing the player name on the wall"""
        if not isAlive(self.sideText):
            return
        assert self.game
        assert Internal.Preferences
        if self == self.game.activePlayer and self.game.client:
            color = 'blue'
        elif Internal.Preferences.tilesetName == 'jade':
            color = 'white'
        else:
            color = 'black'
        self.sideText.color = QColor(color)

    def getsFocus(self, unusedResults:Any=None) ->None:
        """give this player focus on his handBoard"""
        assert self.handBoard
        self.handBoard.setEnabled(True)
        self.handBoard.hasLogicalFocus = True

    def popupMsg(self, msg:Message) ->None:
        """shows a yellow message from player"""
        if msg != Message.NoClaim:
            self.speak(msg.name.lower())
            yellow = self.front.message
            yellow.setText('{}  {}'.format(yellow.msg, i18nc('kajongg', msg.name)))
            yellow.setVisible(True)

    def hidePopup(self) ->None:
        """hide the yellow message from player"""
        if isAlive(self.front.message):
            self.front.message.msg = ''
            self.front.message.setVisible(False)

    def speak(self, txt:str) ->None:
        """speak if we have a voice"""
        if self.voice:
            self.voice.speak(txt, self.front.rotation())

    def robTileFrom(self, tile:Tile) ->None:
        """used for robbing the kong from this player"""
        PlayingPlayer.robTileFrom(self, tile)
        tile = tile.exposed
        assert self.handBoard
        hbTiles = self.handBoard.uiTiles
        lastDiscard = [x for x in hbTiles if x.tile == tile][-1]
        lastDiscard.change_name(lastDiscard.concealed)
        cast('PlayingScene', Internal.scene).discardBoard.discardTile(lastDiscard)
        assert lastDiscard.isConcealed
        self.syncHandBoard()

    def addConcealedTiles(self, tiles:'Tiles', animated:bool=True) ->None:
        """add to my tiles and sync the hand board"""
        assert Internal.Preferences
        _ = cast(List['UITile'], tiles)
        with AnimationSpeed(speed=int(Internal.Preferences.animationSpeed) if animated else 99):
            PlayingPlayer.addConcealedTiles(self, TileList(x.tile for x in _))
            self.syncHandBoard(_)

    def declaredMahJongg(self, concealed:'MeldList', withDiscard:Optional[Tile], lastTile:Tile, lastMeld:'Meld') ->None:
        """player declared mah jongg. Determine last meld, show
        concealed tiles grouped to melds"""
        PlayingPlayer.declaredMahJongg(
            self,
            concealed,
            withDiscard,
            lastTile,
            lastMeld)
        if withDiscard:
            # withDiscard is a Tile, we need the UITile
            discardedTile = cast('PlayingScene', Internal.scene).discardBoard.claimDiscard()
            if discardedTile.tile is not withDiscard:
                assert self.game
                self.game.debug(
                    '%s is not %s' %
                    (discardedTile.tile, withDiscard))
                assert False
            self.syncHandBoard([discardedTile])
        else:
            # show concealed tiles
            self.syncHandBoard()

    def removeConcealedTile(self, tile:Tile) ->None:
        """remove from my melds or tiles"""
        PlayingPlayer.removeConcealedTile(self, tile)
        self.syncHandBoard()

    def makeTileKnown(self, tile:Tile) ->None:
        """give an unknown tileItem a name"""
        PlayingPlayer.makeTileKnown(self, tile)
        assert tile.isKnown
        assert self.handBoard
        matchingTiles = sorted(
            self.handBoard.tilesByElement(Tile.unknown),
            key=lambda x: x.xoffset)
        matchingTiles[-1].change_name(tile)

    def exposeMeld(self, meldTiles:'Tiles', calledTile:Optional[Tile]=None) ->'Meld':
        result = PlayingPlayer.exposeMeld(
            self,
            meldTiles,
            cast('UITile', calledTile).tile if calledTile else None)  # type:ignore[arg-type]
        adding = [cast('UITile', calledTile)] if calledTile else None
        self.syncHandBoard(adding=adding)
        return result


class VisiblePlayingGame(PlayingGame):

    """for the client"""
    playerClass = VisiblePlayingPlayer
    wallClass = UIWall

    def __init__(self, names:List[Tuple['Wind', str]], ruleset:'Ruleset', gameid:Optional[int]=None,
                 wantedGame:Optional[str]=None, client:Optional['Client']=None,
                 playOpen:bool=False, autoPlay:bool=False) ->None:
        PlayingGame.__init__(
            self, names, ruleset, gameid, wantedGame=wantedGame,
            client=client, playOpen=playOpen, autoPlay=autoPlay)
#        Internal.mainWindow.adjustMainView()
#        Internal.mainWindow.updateGUI()
        assert self.wall
        self.wall.decorate4()

    def close(self) ->None:
        """close the game"""
        scene = cast('PlayingScene', Internal.scene)
        assert scene
        scene.discardBoard.hide()
        if isAlive(scene):
            scene.removeTiles()
        scene.clientDialog = None
        for player in self.players:
            player.hide()
        if self.wall:
            self.wall.hide()
        if isAlive(scene.mainWindow):
            scene.mainWindow.actionAutoPlay.setChecked(False)
        scene.startingGame = False
        scene.game = None
        SideText.removeAll()
        scene.mainWindow.updateGUI()
        return PlayingGame.close(self)
