# -*- coding: utf-8 -*-

"""
Copyright (C) 2013-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

Kajongg is free software you can redistribute it and/or modify
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

from qt import Qt

from log import m18nc
from message import Message
from common import Internal, isAlive, unicode
from player import Player, PlayingPlayer
from game import PlayingGame
from tile import Tile
from handboard import PlayingHandBoard
from animation import AnimationSpeed
from uiwall import UIWall, SideText
from wind import Wind


class VisiblePlayer(Player):

    """Mixin for VisiblePlayingPlayer and ScoringPlayer"""

    def __init__(self):
        # pylint: disable=super-init-not-called
        self.__front = self.game.wall[self.idx]
        self.sideText = SideText()
        self.sideText.board = self.__front

    def hide(self):
        """clear visible data and hide"""
        self.clearHand()
        self.handBoard.hide()

    @property
    def idx(self):
        """our index in the player list"""
        if self not in self.game.players:
            # we will be added next
            return len(self.game.players)
        return self.game.players.index(self)

    @property
    def front(self):
        """front"""
        return self.__front

    @front.setter
    def front(self, value):
        """also assign handBoard to front"""
        self.__front = value
        if value and self.handBoard:
            self.handBoard.setParentItem(value)

    def syncHandBoard(self, adding=None):
        """update display of handBoard. Set Focus to tileName."""
        self.handBoard.sync(adding)

    def decorate(self):
        """show player info on the wall"""
        side = self.front
        self.sideText.text = u' - '.join(
            [self.localName,
             unicode(self.explainHand().total())])
        self.colorizeName()
        side.windTile = Wind.all4[self.wind].marker
        side.windTile.prevailing = self.game.roundsFinished
        side.windTile.board = self.front
        side.windTile.setupAnimations()
        side.windTile.show()


class VisiblePlayingPlayer(VisiblePlayer, PlayingPlayer):

    """this player instance has a visual representation"""
    # pylint: disable=too-many-public-methods

    def __init__(self, game, name):
        assert game
        self.handBoard = None  # because Player.init calls clearHand()
        PlayingPlayer.__init__(self, game, name)
        VisiblePlayer.__init__(self)
        self.handBoard = PlayingHandBoard(self)
        self.voice = None

    def clearHand(self):
        """clears attributes related to current hand"""
        super(VisiblePlayingPlayer, self).clearHand()
        if self.game and self.game.wall:
            # is None while __del__
            self.front = self.game.wall[self.idx]
        if self.handBoard:
            self.handBoard.setEnabled(
                self.game and self.game.belongsToHumanPlayer(
                ) and self == self.game.myself)

    def explainHand(self):
        """returns the hand to be explained. Same as current unless we need to discard.
        In that case, make an educated guess about the discard.
        For player==game.myself, use the focused tile."""
        hand = self.hand
        if hand and hand.tiles and self._concealedTiles:
            if hand.lenOffset == 1 and not hand.won:
                if any(not x.isKnown for x in self._concealedTiles):
                    hand -= Tile.unknown
                elif self.handBoard.focusTile:
                    hand -= self.handBoard.focusTile.tile
        return hand

    def colorizeName(self):
        """set the color to be used for showing the player name on the wall"""
        if not isAlive(self.sideText):
            return
        if self == self.game.activePlayer and self.game.client:
            color = Qt.blue
        elif Internal.Preferences.tilesetName == 'jade':
            color = Qt.white
        else:
            color = Qt.black
        self.sideText.color = color

    def getsFocus(self, dummyResults=None):
        """give this player focus on his handBoard"""
        self.handBoard.setEnabled(True)
        self.handBoard.hasFocus = True

    def popupMsg(self, msg):
        """shows a yellow message from player"""
        if msg != Message.NoClaim:
            self.speak(msg.name.lower())
            yellow = self.front.message
            yellow.setText(
                '  '.join([unicode(yellow.msg), m18nc('kajongg', msg.name)]))
            yellow.setVisible(True)

    def hidePopup(self):
        """hide the yellow message from player"""
        if isAlive(self.front.message):
            self.front.message.msg = ''
            self.front.message.setVisible(False)

    def speak(self, text):
        """speak if we have a voice"""
        if self.voice:
            self.voice.speak(text, self.front.rotation())

    def robTileFrom(self, tile):
        """used for robbing the kong from this player"""
        PlayingPlayer.robTileFrom(self, tile)
        tile = tile.exposed
        hbTiles = self.handBoard.uiTiles
        lastDiscard = [x for x in hbTiles if x.tile == tile][-1]
        lastDiscard.tile = lastDiscard.tile.concealed
        Internal.scene.discardBoard.lastDiscarded = lastDiscard
        # remove from board of robbed player, otherwise syncHandBoard would
        # not fix display for the robbed player
        lastDiscard.setBoard(None)
        assert lastDiscard.tile.isConcealed
        self.syncHandBoard()

    def addConcealedTiles(self, uiTiles, animated=True):
        """add to my tiles and sync the hand board"""
        with AnimationSpeed(speed=Internal.Preferences.animationSpeed if animated else 99):
            PlayingPlayer.addConcealedTiles(
                self,
                list(x.tile for x in uiTiles))
            self.syncHandBoard(uiTiles)

    def declaredMahJongg(self, concealed, withDiscard, lastTile, lastMeld):
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
            discardTile = Internal.scene.discardBoard.lastDiscarded
            if discardTile.tile is not withDiscard:
                self.game.debug(
                    '%s is not %s' %
                    (discardTile.tile, withDiscard))
                assert False
            self.syncHandBoard([discardTile])
        else:
            # show concealed tiles
            self.syncHandBoard()

    def removeTile(self, tile):
        """remove from my melds or tiles"""
        PlayingPlayer.removeTile(self, tile)
        self.syncHandBoard()

    def makeTileKnown(self, tile):
        """give an unknown tileItem a name"""
        PlayingPlayer.makeTileKnown(self, tile)
        assert tile.isKnown
        matchingTiles = sorted(
            self.handBoard.tilesByElement(Tile.unknown),
            key=lambda x: x.xoffset)
        matchingTiles[-1].tile = tile

    def exposeMeld(self, meldTiles, calledTile=None):
        result = PlayingPlayer.exposeMeld(
            self,
            meldTiles,
            calledTile.tile if calledTile else None)
        adding = [calledTile] if calledTile else None
        self.syncHandBoard(adding=adding)
        return result


class VisiblePlayingGame(PlayingGame):

    """for the client"""
    # pylint: disable=too-many-arguments, too-many-public-methods
    playerClass = VisiblePlayingPlayer
    wallClass = UIWall

    def __init__(self, names, ruleset, gameid=None,
                 wantedGame=None, client=None, playOpen=False, autoPlay=False):
        PlayingGame.__init__(
            self, names, ruleset, gameid, wantedGame=wantedGame,
            client=client, playOpen=playOpen, autoPlay=autoPlay)
#        Internal.mainWindow.adjustView()
#        Internal.mainWindow.updateGUI()
        self.wall.decorate()

    def close(self):
        """close the game"""
        scene = Internal.scene
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
