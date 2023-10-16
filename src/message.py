# -*- coding: utf-8 -*-

"""
Copyright (C) 2010-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

import datetime

from log import logWarning, logException, logDebug
from mi18n import i18n, i18nc, i18ncE
from sound import Voice
from tile import Tile, TileTuple
from meld import Meld, MeldList
from common import Internal, Debug, Options, ReprMixin
from wind import Wind
from dialogs import Sorry

# pylint: disable=super-init-not-called
# multiple inheritance: pylint thinks ServerMessage.__init__ does not get called.
# this is no problem: ServerMessage has no __init__ and its parent Message.__init__
# will be called anyway


class Message:

    """those are the message types between client and server. They have no state
    i.e. they never hold real attributes. They only describe the message and actions upon it"""

    defined = {}

    def __init__(self, name=None, shortcut=None):
        """those are the english values"""
        self.name = name or self.__class__.__name__.replace('Message', '')
        self.__i18nName = None
        self.shortcut = shortcut
        # do not use a numerical value because that could easier
        # change with software updates
        className = self.__class__.__name__.replace('Message', '')
        msgName = self.name.replace(' ', '')
        assert className == msgName, '%s != %s' % (className, msgName)

    @property
    def i18nName(self):
        """only translate when needed - most messages never need this"""
        if self.__i18nName is None:
            self.__i18nName = i18nc('kajongg', self.name)
        return self.__i18nName

    def __str__(self):
        return self.name

    def __repr__(self):
        return 'Message.{}'.format(self.name)

    def __lt__(self, other):
        return self.__class__.__name__ < other.__class__.__name__

    @staticmethod
    def jelly(key, value):
        """serialize value for wire transfer. The twisted.pb mechanism with
        pb.Copyable is too much overhead"""
        # pylint: disable=too-many-return-statements
        cls = value.__class__
        if cls in (Tile, Meld, MeldList, TileTuple):
            return str(value)
        if isinstance(value, Wind):
            return str(value)
        if isinstance(value, Message):
            return value.name
        if isinstance(value, (list, tuple)):
            if isinstance(value, tuple) and isinstance(value[0], Message):
                if value[1] is None or value[1] == []:
                    return value[0].name
            return type(value)([Message.jelly(key, x) for x in value])
        if isinstance(value, dict):
            return {Message.jelly('key', x): Message.jelly('value', y) for x, y in value.items()}
        if not isinstance(value, (int, bytes, str, float, type(None))):
            raise TypeError(
                'callRemote got illegal arg: %s %s(%s)' %
                (key, type(value), str(value)))
        return value

    @staticmethod
    def jellyAll(args, kwargs):
        """serialize args and kwargs for wire transfer. The twisted.pb mechanism with
        pb.Copyable is too much overhead"""
        args2 = Message.jelly('args', args)
        kwargs2 = {}
        for key, value in kwargs.items():
            kwargs2[key] = Message.jelly(key, value)
        return args2, kwargs2


class ServerMessage(Message):

    """those classes are used for messages from server to client"""
    # if sendScore is True, this message will send info about player scoring,
    # so the clients can compare
    sendScore = False
    needsGame = True   # message only applies to an existing game

    def clientAction(self, client, move): # pylint: disable=unused-argument
        """default client action: none - this is a virtual class"""
        logException(
            'clientAction is not defined for %s. msg:%s' %
            (self, move))

    def serverAction(self, table, msg):  # pylint: disable=unused-argument
        """the server mirrors that and tells all others"""
        logException('serverAction is not defined for msg:%s' % msg)


class ClientMessage(Message):

    """those classes are used for messages from client to server"""

    def __init__(self, name=None, shortcut=None):
        Message.__init__(self, name, shortcut)

    def buttonCaption(self):
        """localized, with a & for the shortcut"""
        i18nShortcut = i18nc(
            'kajongg game dialog:Key for ' +
            self.name,
            self.shortcut)
        return self.i18nName.replace(i18nShortcut, '&' + i18nShortcut, 1)

    def toolTip(self, button, tile): # pylint: disable=unused-argument
        """return text and warning flag for button and text for tile for button and text for tile"""
        txt = 'toolTip is not defined for %s' % self.name
        logWarning(txt)
        return txt, True, ''

    def serverAction(self, table, msg): # pylint: disable=unused-argument
        """default server action: none - this is a virtual class"""
        logException(
            'serverAction is not defined for %s. msg:%s' %
            (self, msg))

    @staticmethod
    def isActivePlayer(table, msg):
        """helper: does the message come from the active player?"""
        if msg.player == table.game.activePlayer:
            return True
        errMsg = '%s said %s but is not the active player' % (
            msg.player, msg.answer.i18nName)
        table.abort(errMsg)
        return False


class MessageAbort(ClientMessage):

    """If a client aborts, the server will set the answer for all open requests
    to Message.AbortMessage"""


class NotifyAtOnceMessage(ClientMessage):

    """those classes are for messages from clients that might have to be relayed to the
    other clients right away.

    Example: If a client says Pung, it sends Message.Pung with the flag 'notifying=True'.
    This is relayed to the other 3 clients, helping them in their thinking. When the
    server decides that the Pung is actually to be executed, it sends Message.Pung
    to all 4 clients, but without 'notifying=True'"""

    sendScore = False

    def __init__(self, name=None, shortcut=None):
        ClientMessage.__init__(self, name, shortcut)

    def notifyAction(self, client, move): # pylint: disable=unused-argument
        """the default action for immediate notifications"""
        move.player.popupMsg(self)

    @classmethod
    def receivers(cls, request):
        """who should get the notification? Default is all players except the
        player who triggered us"""
        # default: tell all except the source of the notification
        game = request.block.table.game
        if game:
            return [x for x in game.players if x != request.player]
        return []


class PungChowMessage(NotifyAtOnceMessage):

    """common code for Pung and Chow"""

    def __init__(self, name=None, shortcut=None):
        NotifyAtOnceMessage.__init__(self, name=name, shortcut=shortcut)

    def toolTip(self, button, tile):
        """for the action button which will send this message"""
        myself = button.client.game.myself
        maySay = myself.sayable[self]
        if not maySay:
            return '', False, ''
        txt = []
        warn = False
        if myself.originalCall and myself.mayWin:
            warn = True
            txt.append(i18n('saying %1 violates Original Call',
                            self.i18nName))
        dangerousMelds = myself.maybeDangerous(self)
        if dangerousMelds:
            lastDiscard = myself.game.lastDiscard
            warn = True
            if Debug.dangerousGame and len(dangerousMelds) != len(maySay):
                button.client.game.debug(
                    'only some claimable melds are dangerous: %s' %
                    dangerousMelds)
            if len(dangerousMelds) == 1:
                txt.append(i18n(
                    'claiming %1 is dangerous because you will have to discard a dangerous tile',
                    lastDiscard.name()))
            else:
                for meld in dangerousMelds:
                    txt.append(i18n(
                        'claiming %1 for %2 is dangerous because you will have to discard a dangerous tile',
                        lastDiscard.name(), str(meld)))
        if not txt:
            txt = [i18n('You may say %1', self.i18nName)]
        return '<br><br>'.join(txt), warn, ''


class MessagePung(PungChowMessage, ServerMessage):

    """somebody said pung and gets the tile"""

    def __init__(self):
        PungChowMessage.__init__(self,
                                 name=i18ncE('kajongg', 'Pung'),
                                 shortcut=i18ncE('kajongg game dialog:Key for Pung', 'P'))

    def serverAction(self, table, msg):
        """the server mirrors that and tells all others"""
        table.claimTile(msg.player, self, Meld(msg.args[0]), Message.Pung)

    def clientAction(self, client, move):
        """mirror pung call"""
        return client.claimed(move)


class MessageKong(NotifyAtOnceMessage, ServerMessage):

    """somebody said kong and gets the tile"""

    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
                                     name=i18ncE('kajongg', 'Kong'),
                                     shortcut=i18ncE('kajongg game dialog:Key for Kong', 'K'))

    def serverAction(self, table, msg):
        """the server mirrors that and tells all others"""
        if table.game.lastDiscard:
            table.claimTile(msg.player, self, Meld(msg.args[0]), Message.Kong)
        else:
            table.declareKong(msg.player, Meld(msg.args[0]))

    def toolTip(self, button, tile):
        """for the action button which will send this message"""
        myself = button.client.game.myself
        maySay = myself.sayable[self]
        if not maySay:
            return '', False, ''
        txt = []
        warn = False
        if myself.originalCall and myself.mayWin:
            warn = True
            txt.append(
                i18n('saying Kong for %1 violates Original Call',
                     Tile(maySay[0][0]).name()))
        if not txt:
            txt = [i18n('You may say Kong for %1', Tile(maySay[0][0]).name())]
        return '<br><br>'.join(txt), warn, ''

    def clientAction(self, client, move):
        """mirror kong call"""
        return client.claimed(move) if client.game.lastDiscard else client.declared(move)


class MessageChow(PungChowMessage, ServerMessage):

    """somebody said chow and gets the tile"""

    def __init__(self):
        PungChowMessage.__init__(self,
                                 name=i18ncE('kajongg', 'Chow'),
                                 shortcut=i18ncE('kajongg game dialog:Key for Chow', 'C'))

    def serverAction(self, table, msg):
        """the server mirrors that and tells all others"""
        if table.game.nextPlayer() != msg.player:
            table.abort(
                'player %s illegally said Chow, only %s may' %
                (msg.player, table.game.nextPlayer()))
        else:
            table.claimTile(msg.player, self, Meld(msg.args[0]), Message.Chow)

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

    """somebody sayd mah jongg and wins"""
    sendScore = True

    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
                                     name=i18ncE('kajongg', 'Mah Jongg'),
                                     shortcut=i18ncE('kajongg game dialog:Key for Mah Jongg', 'M'))

    def serverAction(self, table, msg):
        """the server mirrors that and tells all others"""
        table.claimMahJongg(msg)

    def toolTip(self, button, tile):
        """return text and warning flag for button and text for tile"""
        return i18n('Press here and you win'), False, ''

    def clientAction(self, client, move):
        """mirror the mahjongg action locally. Check if the balances are correct."""
        return move.player.declaredMahJongg(move.melds, move.withDiscardTile,
                                            move.lastTile, move.lastMeld)


class MessageOriginalCall(NotifyAtOnceMessage, ServerMessage):

    """somebody made an original call"""

    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
                                     name=i18ncE('kajongg', 'Original Call'),
                                     shortcut=i18ncE('kajongg game dialog:Key for Original Call', 'O'))

    def serverAction(self, table, msg):
        """the server tells all others"""
        table.clientDiscarded(msg)

    def toolTip(self, button, tile):
        """for the action button which will send this message"""
        assert isinstance(tile, Tile), tile
        myself = button.client.game.myself
        isCalling = bool((myself.hand - tile).callingHands)
        if not isCalling:
            txt = i18n(
                'discarding %1 and declaring Original Call makes this hand unwinnable',
                tile.name())
            return txt, True, txt
        return (i18n(
            'Discard a tile, declaring Original Call meaning you need only one '
            'tile to complete the hand and will not alter the hand in any way (except bonus tiles)'),
                False, '')

    def clientAction(self, client, move):
        """mirror the original call"""
        player = move.player
        if client.thatWasMe(player):
            player.originalCallingHand = player.hand
            if Debug.originalCall:
                logDebug(
                    '%s gets originalCallingHand:%s' %
                    (player, player.originalCallingHand))
        player.originalCall = True
        client.game.addCsvTag('originalCall')
        return client.ask(move, [Message.OK])


class MessageDiscard(ClientMessage, ServerMessage):

    """somebody discarded a tile"""
 #   sendScore = True

    def __init__(self):
        ClientMessage.__init__(self,
                               name=i18ncE('kajongg', 'Discard'),
                               shortcut=i18ncE('kajongg game dialog:Key for Discard', 'D'))

    def serverAction(self, table, msg):
        """the server mirrors that action"""
        table.clientDiscarded(msg)

    def toolTip(self, button, tile):
        """for the action button which will send this message"""
        assert isinstance(tile, Tile), tile
        game = button.client.game
        myself = game.myself
        txt = []
        warn = False
        if myself.violatesOriginalCall(tile):
            txt.append(
                i18n('discarding %1 violates Original Call', tile.name()))
            warn = True
        if game.dangerousFor(myself, tile):
            txt.append(i18n('discarding %1 is Dangerous Game', tile.name()))
            warn = True
        if not txt:
            txt = [i18n('discard the least useful tile')]
        txtStr = '<br><br>'.join(txt)
        return txtStr, warn, txtStr

    def clientAction(self, client, move):
        """execute the discard locally"""
        if client.isHumanClient() and Internal.scene:
            move.player.handBoard.setEnabled(False)
        move.player.speak(move.tile)
        return client.game.hasDiscarded(move.player, move.tile)


class MessageProposeGameId(ServerMessage):

    """the game server proposes a new game id. We check if it is available
    in our local data base - we want to use the same gameid everywhere"""
    needsGame = False

    def clientAction(self, client, move):
        """ask the client"""
        # move.playerNames are the players in seating order
        # we cannot just use table.playerNames - the seating order is now
        # different (random)
        return client.reserveGameId(move.gameid)


class MessageTableChanged(ServerMessage):

    """somebody joined or left a table"""
    needsGame = False

    def clientAction(self, client, move):
        """update our copy"""
        return client.tableChanged(move.source)


class MessageReadyForGameStart(ServerMessage):

    """the game server asks us if we are ready for game start"""
    needsGame = False

    def clientAction(self, client, move):
        """ask the client"""
        def hideTableList(result):
            """hide it only after player says I am ready"""
            # set scene.game first, otherwise tableList.hide()
            # sees no current game and logs out
            if result == Message.OK:
                if client.game and Internal.scene:
                    Internal.scene.game = client.game
            if result == Message.OK and client.tableList and client.tableList.isVisible():
                if Debug.table:
                    logDebug(
                        '%s hiding table list because game started' %
                        client.name)
                client.tableList.hide()
            return result
        # move.playerNames are the players in seating order
        # we cannot just use table.playerNames - the seating order is now
        # different (random)
        return client.readyForGameStart(
            move.tableid, move.gameid,
            move.wantedGame, move.playerNames, shouldSave=move.shouldSave).addCallback(hideTableList)


class MessageNoGameStart(NotifyAtOnceMessage):

    """the client says he does not want to start the game after all"""
    needsGame = False

    def notifyAction(self, client, move):
        if client.beginQuestion or client.game:
            Sorry(i18n('%1 is not ready to start the game', move.player.name))
        if client.beginQuestion:
            client.beginQuestion.cancel()
        elif client.game:
            return client.game.close()
        return None

    @classmethod
    def receivers(cls, request):
        """notification is not needed for those who already said no game"""
        return [x.player for x in request.block.requests if x.answer != Message.NoGameStart]


class MessageReadyForHandStart(ServerMessage):

    """the game server asks us if we are ready for a new hand"""

    def clientAction(self, client, move):
        """ask the client"""
        return client.readyForHandStart(move.playerNames, move.rotateWinds)


class MessageInitHand(ServerMessage):

    """the game server tells us to prepare a new hand"""

    def clientAction(self, client, move):
        """prepare a new hand"""
        client.game.divideAt = move.divideAt
        client.game.wall.divide()
        if hasattr(client, 'shutdownHumanClients'):
            client.shutdownHumanClients(exception=client)
        scene = Internal.scene
        if scene:
            scene.mainWindow.setWindowTitle(
                i18n(
                    'Kajongg <numid>%1</numid>',
                    client.game.handId.seed))
            scene.discardBoard.setRandomPlaces(client.game)
        client.game.initHand()


class MessageSetConcealedTiles(ServerMessage):

    """the game server assigns tiles to player"""

    def clientAction(self, client, move):
        """set tiles for player"""
        return move.player.addConcealedTiles(client.game.wall.deal(move.tiles), animated=False)


class MessageShowConcealedTiles(ServerMessage):

    """the game server assigns tiles to player"""

    def clientAction(self, client, move):
        """set tiles for player"""
        return move.player.showConcealedTiles(move.tiles, move.show)


class MessageSaveHand(ServerMessage):

    """the game server tells us to save the hand"""

    def clientAction(self, client, move):
        """save the hand"""
        return client.game.saveHand()


class MessageAskForClaims(ServerMessage):

    """the game server asks us if we want to claim a tile"""

    def clientAction(self, client, move):
        """ask the player"""
        if client.thatWasMe(move.player):
            raise ValueError(
                'Server asked me(%s) for claims but I just discarded that tile!' %
                move.player)
        return client.ask(move, [Message.NoClaim, Message.Chow, Message.Pung, Message.Kong, Message.MahJongg])


class MessagePickedTile(ServerMessage):

    """the game server tells us who picked a tile"""

    def clientAction(self, client, move):
        """mirror the picked tile"""
        assert move.player.pickedTile(move.deadEnd, tileName=move.tile) == move.tile, \
            (move.player.lastTile, move.tile)
        if client.thatWasMe(move.player):
            return (Message.Bonus, move.tile) if move.tile.isBonus else client.myAction(move)
        return None


class MessageActivePlayer(ServerMessage):

    """the game server tells us whose turn it is"""

    def clientAction(self, client, move):
        """set the active player"""
        client.game.activePlayer = move.player


class MessageViolatesOriginalCall(ServerMessage):

    """the game server tells us who violated an original call"""

    def __init__(self):
        ServerMessage.__init__(
            self,
            name=i18ncE('kajongg',
                        'Violates Original Call'))

    def clientAction(self, client, move):
        """violation: player may not say mah jongg"""
        move.player.popupMsg(self)
        move.player.mayWin = False
        if Debug.originalCall:
            logDebug('%s: cleared mayWin' % move.player)
        return client.ask(move, [Message.OK])


class MessageVoiceId(ServerMessage):

    """we got a voice id from the server. If we have no sounds for
    this voice, ask the server"""

    def clientAction(self, client, move):
        """the server gave us a voice id about another player"""
        if Internal.Preferences.useSounds and Options.gui:
            move.player.voice = Voice.locate(move.source)
            if not move.player.voice:
                return Message.ClientWantsVoiceData, move.source
        return None


class MessageVoiceData(ServerMessage):

    """we got voice sounds from the server, assign them to the player voice"""

    def clientAction(self, client, move):
        """server sent us voice sounds about somebody else"""
        move.player.voice = Voice(move.md5sum, move.source)
        if Debug.sound:
            logDebug('%s gets voice data %s from server, language=%s' % (
                move.player, move.player.voice, move.player.voice.language()))


class MessageAssignVoices(ServerMessage):

    """The server tells us that we now got all voice data available"""

    def clientAction(self, client, move):
        if Internal.Preferences.useSounds and Options.gui:
            client.game.assignVoices()


class MessageClientWantsVoiceData(ClientMessage):

    """This client wants voice sounds"""


class MessageServerWantsVoiceData(ServerMessage):

    """The server wants voice sounds from a client"""

    def clientAction(self, client, move):
        """send voice sounds as requested to server"""
        if Debug.sound:
            logDebug('%s: send wanted voice data %s to server' % (
                move.player, move.player.voice))
        return Message.ServerGetsVoiceData, move.player.voice.archiveContent


class MessageServerGetsVoiceData(ClientMessage):

    """The server gets voice sounds from a client"""

    def serverAction(self, table, msg):
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
            if len(move.meld) != 4 or move.meld[0].isConcealed:
                # do not do this when adding a 4th tile to an exposed pung
                move.player.showConcealedTiles(move.meld)
            else:
                move.player.showConcealedTiles(TileTuple(move.meld[3]))
            prompts = [Message.NoClaim, Message.MahJongg]
        move.exposedMeld = move.player.exposeMeld(move.meld)
        return client.ask(move, prompts) if prompts else None


class MessageRobbedTheKong(NotifyAtOnceMessage, ServerMessage):

    """the game server tells us who robbed the kong"""

    def clientAction(self, client, move):
        """mirror the action locally"""
        prevMove = next(client.game.lastMoves(only=[Message.DeclaredKong]))
        prevMove.player.robTileFrom(prevMove.meld[0].concealed)
        move.player.robsTile()
        client.game.addCsvTag(
            'robbedKong%s' % prevMove.meld[1],
            forAllPlayers=True)


class MessageCalling(ServerMessage):

    """the game server tells us who announced a calling hand"""

    def clientAction(self, client, move):
        """tell user and save this information locally"""
        move.player.popupMsg(self)
        move.player.isCalling = True
        return client.ask(move, [Message.OK])


class MessageDangerousGame(ServerMessage):

    """the game server tells us who played dangerous game"""

    def __init__(self):
        ServerMessage.__init__(self, name=i18ncE('kajongg', 'Dangerous Game'))

    def clientAction(self, client, move):
        """mirror the dangerous game action locally"""
        move.player.popupMsg(self)
        move.player.playedDangerous = True
        return client.ask(move, [Message.OK])


class MessageNoChoice(ServerMessage):

    """the game server tells us who had no choice avoiding dangerous game"""

    def __init__(self):
        ServerMessage.__init__(self, name=i18ncE('kajongg', 'No Choice'))
        self.move = None

    def clientAction(self, client, move):
        """mirror the no choice action locally"""
        self.move = move
        move.player.popupMsg(self)
        move.player.claimedNoChoice = True
        move.player.showConcealedTiles(move.tiles)
        # otherwise we have a visible artifact of the discarded tile.
        # Only when animations are disabled. Why?
#        Internal.mainWindow.centralView.resizeEvent(None)
        return client.ask(move, [Message.OK]).addCallback(self.hideConcealedAgain)

    def hideConcealedAgain(self, result):
        """only show them for explaining the 'no choice'"""
        self.move.player.showConcealedTiles(self.move.tiles, False)
        return result


class MessageUsedDangerousFrom(ServerMessage):

    """the game server tells us somebody claimed a dangerous tile"""

    def clientAction(self, client, move):
        fromPlayer = client.game.playerByName(move.source)
        move.player.usedDangerousFrom = fromPlayer
        if Debug.dangerousGame:
            logDebug('%s claimed a dangerous tile discarded by %s' %
                     (move.player, fromPlayer))


class MessageDraw(ServerMessage):

    """the game server tells us nobody said mah jongg"""
    sendScore = True


class MessageError(ServerMessage):

    """a client errors"""
    needsGame = False

    def clientAction(self, client, move):
        """show the error message from server"""
        return logWarning(move.source)


class MessageNO(ClientMessage):

    """a client says no"""


class MessageOK(ClientMessage):

    """a client says OK"""

    def __init__(self):
        ClientMessage.__init__(self,
                               name=i18ncE('kajongg', 'OK'),
                               shortcut=i18ncE('kajongg game dialog:Key for OK', 'O'))

    def toolTip(self, button, tile):
        """return text and warning flag for button and text for tile for button and text for tile"""
        return i18n('Confirm that you saw the message'), False, ''


class MessageNoClaim(NotifyAtOnceMessage, ServerMessage):

    """A player explicitly says he will not claim a tile"""

    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
                                     name=i18ncE('kajongg', 'No Claim'),
                                     shortcut=i18ncE('kajongg game dialog:Key for No claim', 'N'))

    def toolTip(self, button, tile):
        """return text and warning flag for button and text for tile for button and text for tile"""
        return i18n('You cannot or do not want to claim this tile'), False, ''

    @classmethod
    def receivers(cls, request):
        """no Claim notifications are not needed for those who already answered"""
        return [x.player for x in request.block.requests if x.answer is None]


def __scanSelf():
    """for every message defined in this module which can actually be used for traffic,
    generate a class variable Message.msg where msg is the name (without spaces)
    of the message. Example: 'Message.NoClaim'.
    Those will be used as stateless constants. Also add them to dict Message.defined, but with spaces."""
    if Message.defined:
        return
    for glob in globals().values():
        if hasattr(glob, "__mro__"):
            if glob.__mro__[-2] == Message and len(glob.__mro__) > 2:
                if glob.__name__.startswith('Message'):
                    try:
                        msg = glob()
                    except Exception:
                        logDebug('cannot instantiate %s' % glob.__name__)
                        raise
                    type.__setattr__(
                        Message, msg.name.replace(' ', ''), msg)
                    Message.defined[msg.name] = msg


class ChatMessage(ReprMixin):

    """holds relevant info about a chat message"""

    def __init__(self, tableid, fromUser=None,
                 message=None, isStatusMessage=False):
        if isinstance(tableid, tuple):
            self.tableid, hour, minute, second, self.fromUser, self.message, self.isStatusMessage = tableid
            self.timestamp = datetime.time(
                hour=hour,
                minute=minute,
                second=second)
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
        result = datetime.datetime.combine(
            datetime.date.today(),
            self.timestamp)
        return result + (now - utcnow)

    def __str__(self):
        local = self.localtimestamp()
        # pylint says something about NotImplemented, check with later versions
        _ = i18n(self.message)
        if self.isStatusMessage:
            _ = '[{}]'.format(_)
        return '%02d:%02d:%02d %s: %s' % (
            local.hour,
            local.minute,
            local.second,
            self.fromUser,
            i18n(self.message))

    def asList(self):
        """encode me for network transfer"""
        return (
            self.tableid, self.timestamp.hour, self.timestamp.minute, self.timestamp.second,
            self.fromUser, self.message, self.isStatusMessage)

__scanSelf()
