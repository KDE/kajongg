# -*- coding: utf-8 -*-

"""
Copyright (C) 2010-2011 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from util import m18nc, m18ncE, logWarning, logException, logDebug
from sound import Voice, Sound
from meld import Meld
from common import InternalParameters, Debug

class Message(object):
    """those are the message types between client and server. They have no state
    i.e. they never hold real attributes. They only describe the message and actions upon it"""

    defined = {}

    def __init__(self, name=None, shortcut=None):
        """those are the english values"""
        self.name = name or self.__class__.__name__.replace('Message', '')
        self.i18nName = self.name
        self.shortcut = shortcut
        # do not use a numerical value because that could easier
        # change with software updates
        Message.defined[self.name] = self

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<Message: %s>" % self

class MessageFromServer(Message):
    """those classes are used for messages from server to client"""
    # if sendScore is True, this message will send info about player scoring, so the clients can compare
    sendScore = False
    def __init__(self, name=None):
        Message.__init__(self, name)

    def clientAction(self, dummyClient, move):
        """default client action: none - this is a virtual class"""
        logException('clientAction is not defined for %s. msg:%s' % (self, move))

class MessageFromClient(Message):
    """those classes are used for messages from client to server"""
    def __init__(self, name=None, shortcut=None):
        Message.__init__(self, name, shortcut)
        self.i18nName = m18nc('kajongg', self.name)
        self.notifyAtOnce = False

    def buttonCaption(self):
        """localized, with a & for the shortcut"""
        i18nShortcut = m18nc('kajongg game dialog:Key for '+self.name, self.shortcut)
        return self.i18nName.replace(i18nShortcut, '&'+i18nShortcut, 1)

    def serverAction(self, dummyTable, msg):
        """default server action: none - this is a virtual class"""
        logException('serverAction is not defined for %s. msg:%s' % (self, msg))

    @staticmethod
    def isActivePlayer(table, msg):
        """helper: does the message come from the active player?"""
        if msg.player == table.game.activePlayer:
            return True
        errMsg = '%s said %s but is not the active player' % (msg.player, msg.answer.i18nName)
        table.abort(errMsg)

class NotifyAtOnceMessage(MessageFromClient):
    """those classes are for messages that should pop up at the
    other clients right away"""
    def __init__(self, name, shortcut=None):
        MessageFromClient.__init__(self, name, shortcut)
        self.notifyAtOnce = True

class MessagePung(NotifyAtOnceMessage):
    """the client said pung"""
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name=m18ncE('kajongg','Pung'),
            shortcut=m18ncE('kajongg game dialog:Key for Pung', 'P'))
    def serverAction(self, table, msg):
        """the server mirrors that and tells all others"""
        table.claimTile(msg.player, self, msg.args[0], Message.CalledPung)

class MessageKong(NotifyAtOnceMessage):
    """the client said kong"""
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name=m18ncE('kajongg','Kong'),
            shortcut=m18ncE('kajongg game dialog:Key for Kong', 'K'))
    def serverAction(self, table, msg):
        """the server mirrors that and tells all others"""
        table.claimTile(msg.player, self, msg.args[0], Message.CalledKong)

class MessageChow(NotifyAtOnceMessage):
    """the client said chow"""
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name=m18ncE('kajongg','Chow'),
            shortcut=m18ncE('kajongg game dialog:Key for Chow', 'C'))
    def serverAction(self, table, msg):
        """the server mirrors that and tells all others"""
        if table.game.nextPlayer() != msg.player:
            table.abort('player %s illegally said Chow' % msg.player)
        else:
            table.claimTile(msg.player, self, msg.args[0], Message.CalledChow)

class MessageBonus(MessageFromClient):
    """the client says he got a bonus"""
    def serverAction(self, table, msg):
        """the server mirrors that"""
        if self.isActivePlayer(table, msg):
            table.pickTile()

class MessageMahJongg(NotifyAtOnceMessage):
    """the client says mah jongg"""
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name=m18ncE('kajongg','Mah Jongg'),
            shortcut=m18ncE('kajongg game dialog:Key for Mah Jongg', 'M'))
    def serverAction(self, table, msg):
        """the server mirrors that and tells all others"""
        table.claimMahJongg(msg)

class MessageOriginalCall(NotifyAtOnceMessage):
    """the client tells the server he just made an original call"""
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name=m18ncE('kajongg','Original Call'),
            shortcut=m18ncE('kajongg game dialog:Key for Original Call', 'O'))
    def serverAction(self, table, msg):
        """the server tells all others"""
        if self.isActivePlayer(table, msg):
            msg.player.originalCall = True
            table.tellAll(msg.player, Message.MadeOriginalCall, table.moved)

class MessageViolatesOriginalCall(NotifyAtOnceMessage):
    """the client tells the server that he violated the original call"""
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name = m18ncE('kajongg', 'Violates Original Call'))
    def serverAction(self, table, msg):
        """the server tells all others"""
        if self.isActivePlayer(table, msg):
            msg.player.mayWin = False
            table.tellAll(msg.player, Message.ViolatedOriginalCall, table.notMoved)

class MessageDiscard(MessageFromClient):
    """the client tells the server whilch tile he discarded"""
    def __init__(self):
        MessageFromClient.__init__(self,
            name=m18ncE('kajongg','Discard'),
            shortcut=m18ncE('kajongg game dialog:Key for Discard', 'D'))
    def serverAction(self, table, msg):
        """the server mirrors that action"""
        table.discard(msg)

class MessageProposeGameId(MessageFromServer):
    """the game server proposes a new game id. We check if it is available
    in our local data base - we want to use the same gameid everywhere"""
    def clientAction(self, client, move):
        """ask the client"""
        # move.source are the players in seating order
        # we cannot just use table.playerNames - the seating order is now different (random)
        client.reserveGameId(move.gameid)

class MessageReadyForGameStart(MessageFromServer):
    """the game server asks us if we are ready for game start"""
    def clientAction(self, client, move):
        """ask the client"""
        # move.source are the players in seating order
        # we cannot just use table.playerNames - the seating order is now different (random)
        client.readyForGameStart(move.tableid, move.gameid, move.seed, move.source, shouldSave=move.shouldSave)

class MessageReadyForHandStart(MessageFromServer):
    """the game server asks us if we are ready for a new hand"""
    def clientAction(self, client, move):
        """ask the client"""
        client.readyForHandStart(move.source, move.rotateWinds)

class MessageInitHand(MessageFromServer):
    """the game server tells us to prepare a new hand"""
    def clientAction(self, client, move):
        """prepare a new hand"""
        client.game.divideAt = move.divideAt
        client.game.showField()

class MessageSetConcealedTiles(MessageFromServer):
    """the game server assigns tiles to player"""
    def clientAction(self, client, move):
        """set tiles for player"""
        client.game.setConcealedTiles(move.source)

class MessageShowConcealedTiles(MessageFromServer):
    """the game server assigns tiles to player"""
    def clientAction(self, dummyClient, move):
        """set tiles for player"""
        move.player.showConcealedTiles(move.source, move.show)

class MessageSaveHand(MessageFromServer):
    """the game server tells us to save the hand"""
    def clientAction(self, client, move):
        """save the hand"""
        client.game.saveHand()

class MessagePopupMsg(MessageFromServer):
    """the game server tells us to show a popup for a player"""
    def clientAction(self, dummyClient, move):
        """popup the message"""
        move.player.popupMsg(move.msg)

class MessageHasDiscarded(MessageFromServer):
    """the game server tells us who discarded which tile"""
 #   sendScore = True

    def clientAction(self, client, move):
        """execute the discard locally"""
        if client.isHumanClient() and InternalParameters.field:
            move.player.handBoard.setEnabled(False)
        move.player.speak(move.tile)
        if move.tile != move.player.lastTile:
            client.invalidateOriginalCall(move.player)
        client.game.hasDiscarded(move.player, move.tile)

class MessageAskForClaims(MessageFromServer):
    """the game server asks us if we want to claim a tile"""
    def clientAction(self, client, move):
        """ask the player"""
        if not client.thatWasMe(move.player):
            if client.game.myself == client.game.nextPlayer():
                client.ask(move, [Message.NoClaim, Message.Chow, Message.Pung, Message.Kong, Message.MahJongg])
            else:
                client.ask(move, [Message.NoClaim, Message.Pung, Message.Kong, Message.MahJongg])

class MessagePickedTile(MessageFromServer):
    """the game server tells us who picked a tile"""
    def clientAction(self, client, move):
        """mirror the picked tile"""
        assert client.game.pickedTile(move.player, move.deadEnd, tileName=move.source).element == move.source, \
            (move.player.lastTile, move.source)
        if client.thatWasMe(move.player):
            if move.source[0] in 'fy':
                client.answers.append((Message.Bonus, move.source))
            else:
                if client.game.lastDiscard:
                    answers = [Message.Discard, Message.MahJongg]
                else:
                    answers = [Message.Discard, Message.Kong, Message.MahJongg]
                if not move.player.discarded and not move.player.originalCall:
                    answers.append(Message.OriginalCall)
                client.ask(move, answers)

class MessageCalledChow(MessageFromServer):
    """the game server tells us who called chow"""
    def clientAction(self, client, move):
        """mirror chow call"""
        client.called(move)

class MessageCalledPung(MessageFromServer):
    """the game server tells us who called pung"""
    def clientAction(self, client, move):
        """mirror pung call"""
        client.called(move)

class MessageCalledKong(MessageFromServer):
    """the game server tells us who called kong"""
    def clientAction(self, client, move):
        """mirror kong call"""
        client.called(move)

class MessageActivePlayer(MessageFromServer):
    """the game server tells us whose turn it is"""
    def clientAction(self, client, move):
        """set the active player"""
        client.game.activePlayer = move.player
        if client.isHumanClient() and InternalParameters.field:
            move.player.handBoard.setEnabled(True)

class MessageMadeOriginalCall(MessageFromServer):
    """the game server tells us who made an original call"""
    def clientAction(self, client, move):
        """mirror the original call"""
        move.player.originalCall = True
        if client.thatWasMe(move.player):
            answers = [Message.Discard, Message.MahJongg]
            client.ask(move, answers)
        else:
            client.ask(move, [Message.OK])

class MessageViolatedOriginalCall(MessageFromServer):
    """the game server tells us who violated an original call"""
    def clientAction(self, client, move):
        """violation: player may not say mah jongg"""
        move.player.mayWin = False
        if not client.thatWasMe(move.player):
            client.ask(move, [Message.OK])

class MessageVoiceId(MessageFromServer):
    """we got a voice id from the server. If we have no sounds for
    this voice, ask the server"""
    def clientAction(self, client, move):
        """the server gave us a voice id about another player"""
        move.player.voice = Voice(move.source)
        if Sound.enabled and not move.player.voice.hasData():
            client.answers.append((Message.ClientWantsVoiceData, move.source))

class MessageVoiceData(MessageFromServer):
    """we got voice sounds from the server, assign them to the player voice"""
    def clientAction(self, dummyClient, move):
        """server sent us voice sounds about somebody else"""
        move.player.voice.archiveContent = move.source

class MessageClientWantsVoiceData(MessageFromClient):
    """This client wants voice sounds"""
    pass

class MessageServerWantsVoiceData(MessageFromServer):
    """The server wants voice sounds from a client"""
    def clientAction(self, client, move):
        """send voice sounds as requested to server"""
        client.answers.append((Message.ServerGetsVoiceData, move.player.voice.archiveContent))

class MessageServerGetsVoiceData(MessageFromClient):
    """The server gets voice sounds from a client"""
    def serverAction(self, dummyTable, msg):
        """save voice sounds on the server"""
        msg.player.voice.archiveContent = msg.args[0]

class MessageDeclaredKong(MessageFromServer):
    """the game server tells us who declared a kong"""
    def clientAction(self, client, move):
        """mirror the action locally"""
        prompts = None
        client.invalidateOriginalCall(move.player)
        if not client.thatWasMe(move.player):
            if len(move.source) != 4 or move.source[0].istitle():
                # do not do this when adding a 4th tile to an exposed pung
                move.player.showConcealedTiles(move.source)
            else:
                move.player.showConcealedTiles(move.source[3:4])
            prompts = [Message.NoClaim, Message.MahJongg]
        move.exposedMeld = move.player.exposeMeld(move.source)
        if prompts:
            client.ask(move, prompts)

class MessageRobbedTheKong(MessageFromServer):
    """the game server tells us who robbed the kong"""
    def clientAction(self, client, move):
        """mirror the action locally"""
        prevMove = client.game.lastMoves(only=[Message.DeclaredKong]).next()
        prevKong = Meld(prevMove.source)
        prevMove.player.robTile(prevKong.pairs[0].capitalize())
        move.player.lastSource = 'k'

class MessagePlayedDangerous(MessageFromServer):
    """the game server tells us who played dangerous game"""
    def clientAction(self, client, move):
        """mirror the dangerous game action locally"""
        move.player.popupMsg(m18nc('kajongg', 'Dangerous Game'))
        move.player.playedDangerous = True
        client.ask(move, [Message.OK])

class MessageHasNoChoice(MessageFromServer):
    """the game server tells us who had no choice avoiding dangerous game"""
    def __init__(self):
        MessageFromServer.__init__(self)
        self.move = None

    def clientAction(self, client, move):
        """mirror the no choice action locally"""
        self.move = move
        move.player.popupMsg(m18nc('kajongg', 'No Choice'))
        move.player.claimedNoChoice = True
        move.player.showConcealedTiles(move.tile)
        client.ask(move, [Message.OK], self.hideConcealedAgain)

    def hideConcealedAgain(self, dummyResult=None):
        """only show them for explaining the 'no choice'"""
        self.move.player.showConcealedTiles(self.move.tile, False)

class MessageUsedDangerousFrom(MessageFromServer):
    """the game server tells us somebody claimed a dangerous tile"""
    def clientAction(self, client, move):
        fromPlayer = client.game.playerByName(move.source)
        move.player.usedDangerousFrom = fromPlayer
        if Debug.dangerousGame:
            logDebug('%s claimed a dangerous tile discarded by %s' % \
                (move.player, fromPlayer))

class MessageDeclaredMahJongg(MessageFromServer):
    """the game server tells us who said mah jongg"""
    sendScore = True

    def clientAction(self, dummyClient, move):
        """mirror the mahjongg action locally. Check if the balances are correct."""
        move.player.declaredMahJongg(move.source, move.withDiscard,
            move.lastTile, move.lastMeld)

class MessageDraw(MessageFromServer):
    """the game server tells us nobody said mah jongg"""
    sendScore = True

class MessageError(MessageFromServer):
    """a client errors"""
    def clientAction(self, dummyClient, move):
        """show the error message from server"""
        logWarning(move.source)

class MessageNO(MessageFromClient):
    """a client says no"""
    pass

class MessageOK(MessageFromClient):
    """a client says OK"""
    def __init__(self):
        MessageFromClient.__init__(self,
            name=m18ncE('kajongg','OK'),
            shortcut=m18ncE('kajongg game dialog:Key for OK', 'O'))

class MessageNoClaim(MessageFromClient):
    """A player does not claim"""
    def __init__(self):
        MessageFromClient.__init__(self,
            name=m18ncE('kajongg','No Claim'),
            shortcut=m18ncE('kajongg game dialog:Key for No claim', 'N'))

def __scanSelf():
    """for every message defined in this module which can actually be used for traffic,
    generate a class variable Message.msg where msg is the name (without spaces)
    of the message. Example: 'Message.NoClaim'.
    Those will be used as stateless constants. Also add them to dict Message.defined."""
    if not Message.defined:
        for glob in globals().values():
            if hasattr(glob, "__mro__"):
                if glob.__mro__[-2] == Message and len(glob.__mro__) > 2:
                    if glob not in [MessageFromClient, MessageFromServer, NotifyAtOnceMessage]:
                        msg = glob()
                        type.__setattr__(Message, msg.name.replace(' ', ''), msg)

__scanSelf()
