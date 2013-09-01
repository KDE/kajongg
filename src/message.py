# -*- coding: utf-8 -*-

"""
Copyright (C) 2010-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from util import m18n, m18nc, m18ncE, logWarning, logException, logDebug, SERVERMARK
from sound import Voice, Sound
from meld import Meld
from common import InternalParameters, Debug

# pylint: disable=W0231
# multiple inheritance: pylint thinks ServerMessage.__init__ does not get called.
# this is no problem: ServerMessage has no __init__ and its parent Message.__init__
# will be called via the other path thru ClientMessage

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

class ServerMessage(Message):
    """those classes are used for messages from server to client"""
    # if sendScore is True, this message will send info about player scoring, so the clients can compare
    sendScore = False
    needsGame = True   # message only applies to an existing game

    def clientAction(self, dummyClient, move):
        """default client action: none - this is a virtual class"""
        logException('clientAction is not defined for %s. msg:%s' % (self, move))

class ClientMessage(Message):
    """those classes are used for messages from client to server"""
    def __init__(self, name=None, shortcut=None):
        Message.__init__(self, name, shortcut)
        self.i18nName = m18nc('kajongg', self.name)
        self.notifyAtOnce = False

    def buttonCaption(self):
        """localized, with a & for the shortcut"""
        i18nShortcut = m18nc('kajongg game dialog:Key for '+self.name, self.shortcut)
        return self.i18nName.replace(i18nShortcut, '&'+i18nShortcut, 1)

    def toolTip(self, dummyButton, dummyTile):
        """returns text and warning flag for button and text for tile for button and text for tile"""
        txt = 'toolTip is not defined for %s' % self.name
        logWarning(txt)
        return txt, True, ''

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

class NotifyAtOnceMessage(ClientMessage):
    """those classes are for messages that should pop up at the
    other clients right away"""
    def __init__(self, name, shortcut=None):
        ClientMessage.__init__(self, name, shortcut)
        self.notifyAtOnce = True

class PungChowMessage(NotifyAtOnceMessage):
    """common code for Pung and Chow"""
    def __init__(self, name=None, shortcut=None):
        NotifyAtOnceMessage.__init__(self, name=name, shortcut=shortcut)

    def toolTip(self, button, dummyTile):
        """decorate the action button which will send this message"""
        maySay = button.client.sayable[self]
        if not maySay:
            return '', False, ''
        myself = button.client.game.myself
        txt = []
        warn = False
        if myself.originalCall and myself.mayWin:
            warn = True
            txt.append(m18n('saying %1 violates Original Call',
                self.i18nName))
        dangerousMelds = button.client.maybeDangerous(self)
        if dangerousMelds:
            lastDiscardName = Meld.tileName(button.client.game.lastDiscard.element)
            warn = True
            if Debug.dangerousGame and len(dangerousMelds) != len(maySay):
                button.client.game.debug('only some claimable melds are dangerous: %s' % dangerousMelds)
            if len(dangerousMelds) == 1:
                txt.append(m18n(
                   'claiming %1 is dangerous because you will have to discard a dangerous tile',
                   lastDiscardName))
            else:
                for meld in dangerousMelds:
                    txt.append(m18n(
                   'claiming %1 for %2 is dangerous because you will have to discard a dangerous tile',
                   lastDiscardName, str(meld)))
        if not txt:
            txt = [m18n('You may say %1', self.i18nName)]
        return '<br><br>'.join(txt), warn, ''

class MessagePung(PungChowMessage, ServerMessage):
    """somebody said pung"""
    def __init__(self):
        PungChowMessage.__init__(self,
            name=m18ncE('kajongg','Pung'),
            shortcut=m18ncE('kajongg game dialog:Key for Pung', 'P'))
    def serverAction(self, table, msg):
        """the server mirrors that and tells all others"""
        table.claimTile(msg.player, self, msg.args[0], Message.Pung)
    def clientAction(self, client, move):
        """mirror pung call"""
        return client.claimed(move)

class MessageKong(NotifyAtOnceMessage, ServerMessage):
    """somebody said kong"""
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name=m18ncE('kajongg','Kong'),
            shortcut=m18ncE('kajongg game dialog:Key for Kong', 'K'))
    def serverAction(self, table, msg):
        """the server mirrors that and tells all others"""
        if table.game.lastDiscard:
            table.claimTile(msg.player, self, msg.args[0], Message.Kong)
        else:
            table.declareKong(msg.player, msg.args[0])
    def toolTip(self, button, dummyTile):
        """decorate the action button which will send this message"""
        maySay = button.client.sayable[self]
        if not maySay:
            return '', False, ''
        myself = button.client.game.myself
        txt = []
        warn = False
        if myself.originalCall and myself.mayWin:
            warn = True
            txt.append(m18n('saying Kong for %1 violates Original Call',
                Meld.tileName(maySay[0])))
        if not txt:
            txt = [m18n('You may say Kong for %1',
                Meld.tileName(maySay[0][0]))]
        return '<br><br>'.join(txt), warn, ''
    def clientAction(self, client, move):
        """mirror kong call"""
        if client.game.lastDiscard:
            return client.claimed(move)
        else:
            return client.declared(move)

class MessageChow(PungChowMessage, ServerMessage):
    """somebody said chow"""
    def __init__(self):
        PungChowMessage.__init__(self,
            name=m18ncE('kajongg','Chow'),
            shortcut=m18ncE('kajongg game dialog:Key for Chow', 'C'))
    def serverAction(self, table, msg):
        """the server mirrors that and tells all others"""
        if table.game.nextPlayer() != msg.player:
            table.abort('player %s illegally said Chow, only %s may' % (msg.player, table.game.nextPlayer()))
        else:
            table.claimTile(msg.player, self, msg.args[0], Message.Chow)

    def clientAction(self, client, move):
        """mirror chow call"""
        return client.claimed(move)

class MessageBonus(ClientMessage):
    """the client says he got a bonus"""
    def serverAction(self, table, msg):
        """the server mirrors that"""
        if self.isActivePlayer(table, msg):
            table.pickTile()

class MessageMahJongg(NotifyAtOnceMessage, ServerMessage):
    """somebody sayd mah jongg"""
    sendScore = True
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name=m18ncE('kajongg','Mah Jongg'),
            shortcut=m18ncE('kajongg game dialog:Key for Mah Jongg', 'M'))
    def serverAction(self, table, msg):
        """the server mirrors that and tells all others"""
        table.claimMahJongg(msg)
    def toolTip(self, dummyButton, dummyTile):
        """returns text and warning flag for button and text for tile"""
        return m18n('Press here and you win'), False, ''
    def clientAction(self, dummyClient, move):
        """mirror the mahjongg action locally. Check if the balances are correct."""
        return move.player.declaredMahJongg(move.source, move.withDiscard,
            move.lastTile, move.lastMeld)

class MessageOriginalCall(NotifyAtOnceMessage, ServerMessage):
    """somebody made an original call"""
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name=m18ncE('kajongg','Original Call'),
            shortcut=m18ncE('kajongg game dialog:Key for Original Call', 'O'))
    def serverAction(self, table, msg):
        """the server tells all others"""
        table.clientDiscarded(msg)
    def toolTip(self, button, tile):
        """decorate the action button which will send this message"""
        myself = button.client.game.myself
        isCalling = bool((myself.hand - tile.element).callingHands())
        if not isCalling:
            txt = m18n('discarding %1 and declaring Original Call makes this hand unwinnable',
                Meld.tileName(tile.element))
            return txt, True, txt
        else:
            return (m18n(
                'Discard a tile, declaring Original Call meaning you need only one '
                'tile to complete the hand and will not alter the hand in any way (except bonus tiles)'),
                False, '')
    def clientAction(self, client, move):
        """mirror the original call"""
        player = move.player
        if client.thatWasMe(player):
            player.originalCallingHand = player.hand
            if Debug.originalCall:
                logDebug('%s gets originalCallingHand:%s' % (player, player.originalCallingHand))
        player.originalCall = True
        client.game.addCsvTag('originalCall')
        return client.ask(move, [Message.OK])

class MessageDiscard(ClientMessage, ServerMessage):
    """somebody discarded a tile"""
 #   sendScore = True
    def __init__(self):
        ClientMessage.__init__(self,
            name=m18ncE('kajongg','Discard'),
            shortcut=m18ncE('kajongg game dialog:Key for Discard', 'D'))
    def serverAction(self, table, msg):
        """the server mirrors that action"""
        table.clientDiscarded(msg)
    def toolTip(self, button, tile):
        """decorate the action button which will send this message"""
        game = button.client.game
        myself = game.myself
        txt = []
        warn = False
        if myself.violatesOriginalCall(tile):
            txt.append(m18n('discarding %1 violates Original Call',
                Meld.tileName(tile.element)))
            warn = True
        if game.dangerousFor(myself, tile):
            txt.append(m18n('discarding %1 is Dangerous Game',
                Meld.tileName(tile.element)))
            warn = True
        if not txt:
            txt = [m18n('discard the least useful tile')]
        txt = '<br><br>'.join(txt)
        return txt, warn, txt
    def clientAction(self, client, move):
        """execute the discard locally"""
        if client.isHumanClient() and InternalParameters.field:
            move.player.handBoard.setEnabled(False)
        move.player.speak(move.tile)
        return client.game.hasDiscarded(move.player, move.tile)

class MessageProposeGameId(ServerMessage):
    """the game server proposes a new game id. We check if it is available
    in our local data base - we want to use the same gameid everywhere"""
    needsGame = False
    def clientAction(self, client, move):
        """ask the client"""
        # move.source are the players in seating order
        # we cannot just use table.playerNames - the seating order is now different (random)
        return client.reserveGameId(move.gameid)

class MessageReadyForGameStart(ServerMessage):
    """the game server asks us if we are ready for game start"""
    needsGame = False
    def clientAction(self, client, move):
        """ask the client"""
        def hideTableList(dummy):
            """hide it only after player says I am ready"""
            if client.tableList:
                client.tableList.hide()
        # move.source are the players in seating order
        # we cannot just use table.playerNames - the seating order is now different (random)
        return client.readyForGameStart(move.tableid, move.gameid,
            move.wantedGame, move.source, shouldSave=move.shouldSave).addCallback(hideTableList)

class MessageReadyForHandStart(ServerMessage):
    """the game server asks us if we are ready for a new hand"""
    def clientAction(self, client, move):
        """ask the client"""
        return client.readyForHandStart(move.source, move.rotateWinds)

class MessageInitHand(ServerMessage):
    """the game server tells us to prepare a new hand"""
    def clientAction(self, client, move):
        """prepare a new hand"""
        client.game.divideAt = move.divideAt
        client.game.wall.divide()
        client.shutdownClients(exception=client)
        field = InternalParameters.field
        if field:
            field.setWindowTitle(m18n('Kajongg <numid>%1</numid>', client.game.handId()))
            field.discardBoard.setRandomPlaces(client.game.randomGenerator)
        client.game.initHand()

class MessageSetConcealedTiles(ServerMessage):
    """the game server assigns tiles to player"""
    def clientAction(self, client, move):
        """set tiles for player"""
        return client.game.setConcealedTiles(move.source)

class MessageShowConcealedTiles(ServerMessage):
    """the game server assigns tiles to player"""
    def clientAction(self, dummyClient, move):
        """set tiles for player"""
        return move.player.showConcealedTiles(move.source, move.show)

class MessageSaveHand(ServerMessage):
    """the game server tells us to save the hand"""
    def clientAction(self, client, move):
        """save the hand"""
        return client.game.saveHand()

class MessagePopupMsg(ServerMessage):
    """the game server tells us to show a popup for a player"""
    def clientAction(self, dummyClient, move):
        """popup the message"""
        return move.player.popupMsg(move.msg)

class MessageAskForClaims(ServerMessage):
    """the game server asks us if we want to claim a tile"""
    def clientAction(self, client, move):
        """ask the player"""
        if not client.thatWasMe(move.player):
            return client.ask(move, [Message.NoClaim, Message.Chow, Message.Pung, Message.Kong, Message.MahJongg])

class MessagePickedTile(ServerMessage):
    """the game server tells us who picked a tile"""
    def clientAction(self, client, move):
        """mirror the picked tile"""
        assert move.player.pickedTile(move.deadEnd, tileName=move.source).element == move.source, \
            (move.player.lastTile, move.source)
        if client.thatWasMe(move.player):
            if move.source[0] in 'fy':
                return Message.Bonus, move.source
            else:
                return client.myAction(move)

class MessageActivePlayer(ServerMessage):
    """the game server tells us whose turn it is"""
    def clientAction(self, client, move):
        """set the active player"""
        client.game.activePlayer = move.player

class MessageViolatedOriginalCall(ServerMessage):
    """the game server tells us who violated an original call"""
    def clientAction(self, client, move):
        """violation: player may not say mah jongg"""
        move.player.popupMsg(m18n('Violates Original Call'))
        move.player.mayWin = False
        if Debug.originalCall:
            logDebug('%s: cleared mayWin' % move.player)
        return client.ask(move, [Message.OK])

class MessageVoiceId(ServerMessage):
    """we got a voice id from the server. If we have no sounds for
    this voice, ask the server"""
    def clientAction(self, dummyClient, move):
        """the server gave us a voice id about another player"""
        if Sound.enabled:
            move.player.voice = Voice.locate(move.source)
            if not move.player.voice:
                return Message.ClientWantsVoiceData, move.source

class MessageVoiceData(ServerMessage):
    """we got voice sounds from the server, assign them to the player voice"""
    def clientAction(self, dummyClient, move):
        """server sent us voice sounds about somebody else"""
        move.player.voice = Voice(move.md5sum, move.source)
        if Debug.sound:
            logDebug('%s gets voice data %s from server, language=%s' % (
                move.player, move.player.voice, move.player.voice.language()))

class MessageAssignVoices(ServerMessage):
    """The server tells us that we now got all voice data available"""
    def clientAction(self, client, move):
        if Sound.enabled:
            client.game.assignVoices()

class MessageClientWantsVoiceData(ClientMessage):
    """This client wants voice sounds"""
    pass

class MessageServerWantsVoiceData(ServerMessage):
    """The server wants voice sounds from a client"""
    def clientAction(self, dummyClient, move):
        """send voice sounds as requested to server"""
        if Debug.sound:
            logDebug('%s: send wanted voice data %s to server' % (
                move.player, move.player.voice))
        return Message.ServerGetsVoiceData, move.player.voice.archiveContent

class MessageServerGetsVoiceData(ClientMessage):
    """The server gets voice sounds from a client"""
    def serverAction(self, dummyTable, msg):
        """save voice sounds on the server"""
        voice = msg.player.voice
        voice.archiveContent = msg.args[0]
        if Debug.sound:
            if voice.oggFiles():
                logDebug('%s: server got wanted voice data %s' % (
                    msg.player, voice))
            else:
                logDebug('%s: server got empty voice data %s (arg0=%s)' % (
                    msg.player, voice, repr(msg.args[0][:100])))

class MessageDeclaredKong(ServerMessage):
    """the game server tells us who declared a kong"""
    def clientAction(self, client, move):
        """mirror the action locally"""
        prompts = None
        if not client.thatWasMe(move.player):
            if len(move.source) != 4 or move.source[0].istitle():
                # do not do this when adding a 4th tile to an exposed pung
                move.player.showConcealedTiles(move.source)
            else:
                move.player.showConcealedTiles(move.source[3:4])
            prompts = [Message.NoClaim, Message.MahJongg]
        move.exposedMeld = move.player.exposeMeld(move.source)
        if prompts:
            return client.ask(move, prompts)

class MessageRobbedTheKong(ServerMessage):
    """the game server tells us who robbed the kong"""
    def clientAction(self, client, move):
        """mirror the action locally"""
        prevMove = client.game.lastMoves(only=[Message.DeclaredKong]).next()
        prevKong = Meld(prevMove.source)
        prevMove.player.robTile(prevKong.pairs[0].capitalize())
        move.player.lastSource = 'k'
        client.game.addCsvTag('robbedKong', forAllPlayers=True)

class MessageCalling(ServerMessage):
    """the game server tells us who announced a calling hand"""
    def clientAction(self, client, move):
        """tell user and save this information locally"""
        move.player.popupMsg(m18n('Calling'))
        move.player.isCalling = True
        # otherwise we have a visible artifact of the discarded tile.
        # Only when animations are disabled. Why?
        if InternalParameters.field:
            InternalParameters.field.centralView.resizeEvent(None)
        return client.ask(move, [Message.OK])

class MessagePlayedDangerous(ServerMessage):
    """the game server tells us who played dangerous game"""
    def clientAction(self, client, move):
        """mirror the dangerous game action locally"""
        move.player.popupMsg(m18n('Dangerous Game'))
        move.player.playedDangerous = True
        return client.ask(move, [Message.OK])

class MessageHasNoChoice(ServerMessage):
    """the game server tells us who had no choice avoiding dangerous game"""
    def __init__(self):
        ServerMessage.__init__(self)
        self.move = None

    def clientAction(self, client, move):
        """mirror the no choice action locally"""
        self.move = move
        move.player.popupMsg(m18n('No Choice'))
        move.player.claimedNoChoice = True
        move.player.showConcealedTiles(move.tile)
        # otherwise we have a visible artifact of the discarded tile.
        # Only when animations are disabled. Why?
        if InternalParameters.field:
            InternalParameters.field.centralView.resizeEvent(None)
        return client.ask(move, [Message.OK]).addCallback(self.hideConcealedAgain)

    def hideConcealedAgain(self, dummyResult):
        """only show them for explaining the 'no choice'"""
        self.move.player.showConcealedTiles(self.move.tile, False)

class MessageUsedDangerousFrom(ServerMessage):
    """the game server tells us somebody claimed a dangerous tile"""
    def clientAction(self, client, move):
        fromPlayer = client.game.playerByName(move.source)
        move.player.usedDangerousFrom = fromPlayer
        if Debug.dangerousGame:
            logDebug('%s claimed a dangerous tile discarded by %s' % \
                (move.player, fromPlayer))

class MessageDraw(ServerMessage):
    """the game server tells us nobody said mah jongg"""
    sendScore = True

class MessageError(ServerMessage):
    """a client errors"""
    needsGame = False
    def clientAction(self, dummyClient, move):
        """show the error message from server"""
        return logWarning(move.source)

class MessageNO(ClientMessage):
    """a client says no"""
    pass

class MessageOK(ClientMessage):
    """a client says OK"""
    def __init__(self):
        ClientMessage.__init__(self,
            name=m18ncE('kajongg','OK'),
            shortcut=m18ncE('kajongg game dialog:Key for OK', 'O'))
    def toolTip(self, dummyButton, dummyTile):
        """returns text and warning flag for button and text for tile for button and text for tile"""
        return m18n('Confirm that you saw the message'), False, ''

class MessageNoClaim(ClientMessage):
    """A player does not claim"""
    def __init__(self):
        ClientMessage.__init__(self,
            name=m18ncE('kajongg','No Claim'),
            shortcut=m18ncE('kajongg game dialog:Key for No claim', 'N'))
    def toolTip(self, dummyButton, dummyTile):
        """returns text and warning flag for button and text for tile for button and text for tile"""
        return m18n('You cannot or do not want to claim this tile'), False, ''

def __scanSelf():
    """for every message defined in this module which can actually be used for traffic,
    generate a class variable Message.msg where msg is the name (without spaces)
    of the message. Example: 'Message.NoClaim'.
    Those will be used as stateless constants. Also add them to dict Message.defined."""
    if not Message.defined:
        for glob in globals().values():
            if hasattr(glob, "__mro__"):
                if glob.__mro__[-2] == Message and len(glob.__mro__) > 2:
                    if glob.__name__.startswith('Message'):
                        msg = glob()
                        type.__setattr__(Message, msg.name.replace(' ', ''), msg)

class ChatMessage:
    """holds relevant info about a chat message"""
    def __init__(self, tableid, fromUser=None, message=None, isStatusMessage=False):
        if isinstance(tableid, basestring) and SERVERMARK in tableid:
            parts = tableid.split(SERVERMARK)
            self.tableid = int(parts[0])
            self.timestamp = datetime.time(hour=int(parts[1]), minute=int(parts[2]), second=int(parts[3]))
            self.fromUser = parts[4]
            self.message = parts[5]
            self.isStatusMessage = bool(int(parts[6]))
        else:
            self.tableid = tableid
            self.fromUser = fromUser
            self.message = message
            self.isStatusMessage = isStatusMessage
            self.timestamp = datetime.datetime.utcnow().time()

    def localtimestamp(self):
        """convert from UTC to local"""
        now = datetime.datetime.now()
        utcnow = datetime.datetime.utcnow()
        result = datetime.datetime.combine(datetime.date.today(), self.timestamp)
        return result + (now - utcnow)

    def __unicode__(self):
        local = self.localtimestamp()
        return 'statusMessage=%s %02d:%02d:%02d %s: %s' % (
            str(self.isStatusMessage),
            local.hour,
            local.minute,
            local.second,
            self.fromUser,
            m18n(self.message))

    def __repr__(self):
        return unicode(self)

    def serialize(self):
        """encode me in a string for network transfer"""
        return SERVERMARK.join([
            str(self.tableid),
            str(self.timestamp.hour),
            str(self.timestamp.minute),
            str(self.timestamp.second),
            self.fromUser,
            self.message,
            str(int(self.isStatusMessage))])

__scanSelf()
