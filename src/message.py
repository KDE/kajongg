# -*- coding: utf-8 -*-

"""
Copyright (C) 2010-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

import datetime
from typing import Dict, Tuple, Optional, TYPE_CHECKING, List, Any, Union, cast

from log import logWarning, logException, logDebug
from mi18n import i18n, i18nc, i18ncE
from sound import Voice
from tile import Tile, TileTuple, Meld, MeldList
from common import Internal, Debug, Options, ReprMixin
from wind import Wind
from dialogs import Sorry

if TYPE_CHECKING:
    from servertable import ServerTable
    from twisted.internet.defer import Deferred
    from move import Move
    from client import Client
    from player import PlayingPlayer
    from deferredutil import Request
    from user import User
    from humanclient import HumanClient, DlgButton
    from scene import PlayingScene


# pylint: disable=super-init-not-called
# multiple inheritance: pylint thinks ServerMessage.__init__ does not get called.
# this is no problem: ServerMessage has no __init__ and its parent Message.__init__
# will be called anyway


class Message:

    """those are the message types between client and server. They have no state
    i.e. they never hold real attributes. They only describe the message and actions upon it"""

    defined : Dict[str, 'Message'] = {}
    sendScore = False

# only for mypy:
    Abort:'Message'
    Pung:'ServerMessage'
    Kong:'ServerMessage'
    Chow:'ServerMessage'
    Bonus:'Message'
    MahJongg:'ServerMessage'
    OriginalCall:'ServerMessage'
    Discard:Union['ServerMessage', 'ClientMessage']
    ProposeGameId:'Message'
    TableChanged:'Message'
    ReadyForGameStart:'ServerMessage'
    NoGameStart:'ServerMessage'
    ReadyForHandStart:'ServerMessage'
    InitHand:'ServerMessage'
    SetConcealedTiles:'Message'
    ShowConcealedTiles:'ServerMessage'
    SaveHand:'ServerMessage'
    AskForClaims:'ServerMessage'
    PickedTile:'ServerMessage'
    ActivePlayer:'ServerMessage'
    ViolatesOriginalCall:'Message'
    VoiceId:'Message'
    VoiceData:'Message'
    AssignVoices:'Message'
    ClientWantsVoiceData:'Message'
    ServerWantsVoiceData:'Message'
    ServerGetsVoiceData:'ServerMessage'
    DeclaredKong:'ServerMessage'
    RobbedTheKong:'Message'
    Calling:'Message'
    DangerousGame:'Message'
    NoChoice:'Message'
    UsedDangerousFrom:'Message'
    Draw:'Message'
    Error:'Message'
    NO:'Message'
    OK:'ClientMessage'
    NoClaim:'Message'



    def __init__(self, name:Optional[str]=None, shortcut:Optional[str]=None) ->None:
        """those are the english values"""
        self.name:str = name or self.__class__.__name__.replace('Message', '')
        self.__i18nName:Optional[str] = None
        self.shortcut = shortcut
        # do not use a numerical value because that could easier
        # change with software updates
        className = self.__class__.__name__.replace('Message', '')
        msgName = self.name.replace(' ', '')
        assert className == msgName, f'{className} != {msgName}'

    @property
    def i18nName(self) ->str:
        """only translate when needed - most messages never need this"""
        if self.__i18nName is None:
            self.__i18nName = i18nc('kajongg', self.name)
        return self.__i18nName

    def __str__(self) ->str:
        return self.name

    def __repr__(self) ->str:
        return f'Message.{self.name}'

    def __lt__(self, other:object) ->bool:
        return self.__class__.__name__ < other.__class__.__name__

    @staticmethod
    def jelly(key:Any, value:Any) ->Any:
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
                f'callRemote got illegal arg: {key} {type(value)}({str(value)})')
        return value

    @staticmethod
    def jellyAll(args:Any, kwargs:Any) ->Tuple[Any, Any]:
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

    def clientAction(self, client:'Client', move:'Move') ->Any: # pylint: disable=unused-argument
        """default client action: none - this is a virtual class"""
        logException(
            f'clientAction is not defined for {self}. msg:{move}')

    def serverAction(self, table:'ServerTable', msg:'Request') ->None:  # pylint: disable=unused-argument
        """the server mirrors that and tells all others"""
        logException(f'serverAction is not defined for msg:{msg}')


class ClientMessage(Message):

    """those classes are used for messages from client to server"""

    def __init__(self, name:Optional[str]=None, shortcut:Optional[str]=None) ->None:
        Message.__init__(self, name, shortcut)

    def buttonCaption(self) ->str:
        """localized, with a & for the shortcut"""
        assert self.shortcut
        i18nShortcut = i18nc(
            'kajongg game dialog:Key for ' +
            self.name,
            self.shortcut)
        return self.i18nName.replace(i18nShortcut, '&' + i18nShortcut, 1)

    def toolTip(self, button:'DlgButton', tile:Optional[Tile]) ->Tuple[str, bool, str]: # pylint: disable=unused-argument
        """return text and warning flag for button and text for tile for button and text for tile"""
        txt = f'toolTip is not defined for {self.name}'
        logWarning(txt)
        return txt, True, ''

    def serverAction(self, table:'ServerTable',  msg:'Request') ->None: # pylint: disable=unused-argument
        """default server action: none - this is a virtual class"""
        logException(
            f'serverAction is not defined for {self}. msg:{msg}')

    @staticmethod
    def isActivePlayer(table:'ServerTable',  msg:'Request') ->bool:
        """helper: does the message come from the active player?"""
        if table.game and msg.player == table.game.activePlayer:
            return True
        errMsg = f'{msg.player} said {msg.answer} but is not the active player'
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

    def __init__(self, name:Optional[str]=None, shortcut:Optional[str]=None) ->None:
        ClientMessage.__init__(self, name, shortcut)

    def notifyAction(self, client:'Client', move:'Move') ->Any: # pylint: disable=unused-argument
        """the default action for immediate notifications"""
        assert move.player
        move.player.popupMsg(self)

    @classmethod
    def receivers(cls, request:'Request') ->List['PlayingPlayer']:
        """who should get the notification? Default is all players except the
        player who triggered us"""
        # default: tell all except the source of the notification
        game = request.block.table.game
        if game:
            return [x for x in game.players if x != request.player]
        return []


class PungChowMessage(NotifyAtOnceMessage):

    """common code for Pung and Chow"""

    def __init__(self, name:Optional[str]=None, shortcut:Optional[str]=None) ->None:
        NotifyAtOnceMessage.__init__(self, name=name, shortcut=shortcut)

    def toolTip(self, button:'DlgButton', tile:Optional[Tile]) ->Tuple[str, bool, str]:
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
                    f'only some claimable melds are dangerous: {dangerousMelds}')
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

    def __init__(self) ->None:
        PungChowMessage.__init__(self,
                                 name=i18ncE('kajongg', 'Pung'),
                                 shortcut=i18ncE('kajongg game dialog:Key for Pung', 'P'))

    def serverAction(self, table:'ServerTable',  msg:'Request') ->None:
        """the server mirrors that and tells all others"""
        assert msg.player
        assert isinstance(msg.args, list)
        table.claimTile(msg.player, self, Meld(msg.args[0]), Message.Pung)

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """mirror pung call"""
        return client.claimed(move)


class MessageKong(NotifyAtOnceMessage, ServerMessage):

    """somebody said kong and gets the tile"""

    def __init__(self) ->None:
        NotifyAtOnceMessage.__init__(self,
                                     name=i18ncE('kajongg', 'Kong'),
                                     shortcut=i18ncE('kajongg game dialog:Key for Kong', 'K'))

    def serverAction(self, table:'ServerTable',  msg:'Request') ->None:
        """the server mirrors that and tells all others"""
        assert table.game
        assert msg.player
        assert isinstance(msg.args, list)
        if table.game.lastDiscard:
            table.claimTile(msg.player, self, Meld(msg.args[0]), Message.Kong)
        else:
            table.declareKong(msg.player, Meld(msg.args[0]))

    def toolTip(self, button:'DlgButton', tile:Optional[Tile]) ->Tuple[str, bool, str]:
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

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """mirror kong call"""
        assert client.game
        return client.claimed(move) if client.game.lastDiscard else client.declared(move)


class MessageChow(PungChowMessage, ServerMessage):

    """somebody said chow and gets the tile"""

    def __init__(self) ->None:
        PungChowMessage.__init__(self,
                                 name=i18ncE('kajongg', 'Chow'),
                                 shortcut=i18ncE('kajongg game dialog:Key for Chow', 'C'))

    def serverAction(self, table:'ServerTable',  msg:'Request') ->None:
        """the server mirrors that and tells all others"""
        assert table.game
        assert isinstance(msg.args, list)
        if table.game.nextPlayer() != msg.player:
            table.abort(
                f'player {msg.player} illegally said Chow, only {table.game.nextPlayer()} may')
        else:
            table.claimTile(msg.player, self, Meld(msg.args[0]), Message.Chow)

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """mirror chow call"""
        return client.claimed(move)


class MessageBonus(ClientMessage):

    """the client says he got a bonus"""

    def serverAction(self, table:'ServerTable', msg:'Request') ->None:
        """the server mirrors that"""
        if self.isActivePlayer(table, msg):
            table.pickTile()


class MessageMahJongg(NotifyAtOnceMessage, ServerMessage):

    """somebody sayd mah jongg and wins"""
    sendScore = True

    def __init__(self) ->None:
        NotifyAtOnceMessage.__init__(self,
                                     name=i18ncE('kajongg', 'Mah Jongg'),
                                     shortcut=i18ncE('kajongg game dialog:Key for Mah Jongg', 'M'))

    def serverAction(self, table:'ServerTable',  msg:'Request') ->None:
        """the server mirrors that and tells all others"""
        table.claimMahJongg(msg)

    def toolTip(self, button:'DlgButton', tile:Optional[Tile]) ->Tuple[str, bool, str]:
        """return text and warning flag for button and text for tile"""
        return i18n('Press here and you win'), False, ''

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """mirror the mahjongg action locally. Check if the balances are correct."""
        assert move.player
        return move.player.declaredMahJongg(move.melds, move.withDiscardTile,
                                            move.lastTile, move.lastMeld)


class MessageOriginalCall(NotifyAtOnceMessage, ServerMessage):

    """somebody made an original call"""

    def __init__(self) ->None:
        NotifyAtOnceMessage.__init__(self,
                                     name=i18ncE('kajongg', 'Original Call'),
                                     shortcut=i18ncE('kajongg game dialog:Key for Original Call', 'O'))

    def serverAction(self, table:'ServerTable',  msg:'Request') ->None:
        """the server tells all others"""
        table.clientDiscarded(msg)

    def toolTip(self, button:'DlgButton', tile:Optional[Tile]) ->Tuple[str, bool, str]:
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

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """mirror the original call"""
        player = move.player
        assert player
        if client.thatWasMe(player):
            player.originalCallingHand = player.hand
            if Debug.originalCall:
                logDebug(
                    f'{player} gets originalCallingHand:{player.originalCallingHand}')
        player.originalCall = True
        assert client.game
        client.game.addCsvTag('originalCall')
        return client.ask(move, [Message.OK])


class MessageDiscard(ClientMessage, ServerMessage):

    """somebody discarded a tile"""
 #   sendScore = True

    def __init__(self) ->None:
        ClientMessage.__init__(self,
                               name=i18ncE('kajongg', 'Discard'),
                               shortcut=i18ncE('kajongg game dialog:Key for Discard', 'D'))

    def serverAction(self, table:'ServerTable',  msg:'Request') ->None:
        """the server mirrors that action"""
        table.clientDiscarded(msg)

    def toolTip(self, button:'DlgButton', tile:Optional[Tile]) ->Tuple[str, bool, str]:
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

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """execute the discard locally"""
        assert move.player
        if client.isHumanClient() and Internal.scene:
            assert move.player.handBoard
            move.player.handBoard.setEnabled(False)
        move.player.speak(move.tile.name2())
        assert client.game
        return client.game.hasDiscarded(move.player, move.tile)


class MessageProposeGameId(ServerMessage):

    """the game server proposes a new game id. We check if it is available
    in our local data base - we want to use the same gameid everywhere"""
    needsGame = False

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """ask the client"""
        # move.playerNames are the players in seating order
        # we cannot just use table.playerNames - the seating order is now
        # different (random)
        assert move.gameid
        return client.reserveGameId(move.gameid)


class MessageTableChanged(ServerMessage):

    """somebody joined or left a table"""
    needsGame = False

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """update our copy"""
        client.tableChanged(move.source)


class MessageReadyForGameStart(ServerMessage):

    """the game server asks us if we are ready for game start"""
    needsGame = False

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """ask the client"""
        def hideTableList(result:Any) ->Any:
            """hide it only after player says I am ready"""
            # set scene.game first, otherwise tableList.hide()
            # sees no current game and logs out
            if result == Message.OK:
                if client.game and Internal.scene:
                    Internal.scene.game = client.game
            if result == Message.OK and client.tableList and client.tableList.isVisible():
                if Debug.table:
                    logDebug(
                        f'{client.name} hiding table list because game started')
                client.tableList.hide()
            return result
        # move.playerNames are the players in seating order
        # we cannot just use table.playerNames - the seating order is now
        # different (random)
        assert move.tableid
        assert move.gameid
        return client.readyForGameStart(  # type:ignore[attr-defined]
            move.tableid, move.gameid,
            move.wantedGame, move.playerNames, shouldSave=move.shouldSave).addCallback(
                hideTableList).addErrback(logException)


class MessageNoGameStart(NotifyAtOnceMessage):

    """the client says he does not want to start the game after all"""
    needsGame = False

    def notifyAction(self, client:'Client', move:'Move') ->Any:
        assert move.player
        client = cast('HumanClient', client)
        if client.beginQuestion or client.game:
            Sorry(i18n('%1 is not ready to start the game', move.player.name))
        if client.beginQuestion:
            client.beginQuestion.cancel()
        elif client.game:
            return client.game.close()
        return None

    @classmethod
    def receivers(cls, request:'Request') ->List['PlayingPlayer']:
        """notification is not needed for those who already said no game"""
        result = [x.player for x in request.block.requests if x.answer != Message.NoGameStart]
        return cast(List['PlayingPlayer'], result)


class MessageReadyForHandStart(ServerMessage):

    """the game server asks us if we are ready for a new hand"""

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """ask the client"""
        return client.readyForHandStart(move.playerNames, move.rotateWinds)


class MessageInitHand(ServerMessage):

    """the game server tells us to prepare a new hand"""

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """prepare a new hand"""
        assert client.game
        assert client.game.wall
        client.game.divideAt = move.divideAt
        client.game.wall.divide()
        if hasattr(client, 'shutdownHumanClients'):
            client.shutdownHumanClients(exception=client)
        scene = cast('PlayingScene', Internal.scene)
        if scene:
            scene.mainWindow.setWindowTitle(
                i18n(
                    'Kajongg <numid>%1</numid>',
                    client.game.handId.seed))
            scene.discardBoard.setRandomPlaces(client.game)
        client.game.initHand()


class MessageSetConcealedTiles(ServerMessage):

    """the game server assigns tiles to player"""

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """set tiles for player"""
        assert move.player
        assert client.game
        assert client.game.wall
        return move.player.addConcealedTiles(client.game.wall.deal(move.tiles), animated=False)  # type:ignore[arg-type]


class MessageShowConcealedTiles(ServerMessage):

    """the game server assigns tiles to player"""

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """set tiles for player"""
        assert move.player
        return move.player.showConcealedTiles(move.tiles, move.show)


class MessageSaveHand(ServerMessage):

    """the game server tells us to save the hand"""

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """save the hand"""
        assert client.game
        return client.game.saveHand()


class MessageAskForClaims(ServerMessage):

    """the game server asks us if we want to claim a tile"""

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """ask the player"""
        assert move.player
        if client.thatWasMe(move.player):
            raise ValueError(
                f'Server asked me({move.player}) for claims but I just discarded that tile!')
        _ = (Message.NoClaim, Message.Chow, Message.Pung, Message.Kong, Message.MahJongg)
        choice = list(cast(ClientMessage, x) for x in _)
        return client.ask(move, choice)


class MessagePickedTile(ServerMessage):

    """the game server tells us who picked a tile"""

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """mirror the picked tile"""
        assert move.player
        assert move.player.pickedTile(move.deadEnd, tileName=move.tile) == move.tile, \
            (move.player.lastTile, move.tile)
        if client.thatWasMe(move.player):
            return (Message.Bonus, move.tile) if move.tile.isBonus else client.myAction(move)
        return None


class MessageActivePlayer(ServerMessage):

    """the game server tells us whose turn it is"""

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """set the active player"""
        assert client.game
        assert move.player
        client.game.activePlayer = move.player


class MessageViolatesOriginalCall(ServerMessage):

    """the game server tells us who violated an original call"""

    def __init__(self) ->None:
        ServerMessage.__init__(
            self,
            name=i18ncE('kajongg',
                        'Violates Original Call'))

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """violation: player may not say mah jongg"""
        assert move.player
        move.player.popupMsg(self)
        move.player.mayWin = False
        if Debug.originalCall:
            logDebug(f'{move.player}: cleared mayWin')
        return client.ask(move, [Message.OK])


class MessageVoiceId(ServerMessage):

    """we got a voice id from the server. If we have no sounds for
    this voice, ask the server"""

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """the server gave us a voice id about another player"""
        assert Internal.Preferences
        if Internal.Preferences.useSounds and Options.gui:
            assert move.player
            move.player.voice = Voice.locate(cast(str, move.source))
            if not move.player.voice:
                return Message.ClientWantsVoiceData, move.source
        return None


class MessageVoiceData(ServerMessage):

    """we got voice sounds from the server, assign them to the player voice"""

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """server sent us voice sounds about somebody else"""
        assert move.md5sum
        assert move.player
        move.player.voice = Voice(move.md5sum, cast(bytes, move.source))
        if Debug.sound:
            logDebug(f'{move.player} gets voice data {move.player.voice} '
                     f'from server, language={move.player.voice.language()}')


class MessageAssignVoices(ServerMessage):

    """The server tells us that we now got all voice data available"""

    def clientAction(self, client:'Client', move:'Move') ->Any:
        assert Internal.Preferences
        if Internal.Preferences.useSounds and Options.gui:
            assert client.game
            client.game.assignVoices()


class MessageClientWantsVoiceData(ClientMessage):

    """This client wants voice sounds"""


class MessageServerWantsVoiceData(ServerMessage):

    """The server wants voice sounds from a client"""

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """send voice sounds as requested to server"""
        assert move.player
        assert move.player.voice
        if Debug.sound:
            logDebug(f'{move.player}: send wanted voice data {move.player.voice} to server')
        return Message.ServerGetsVoiceData, move.player.voice.archiveContent


class MessageServerGetsVoiceData(ClientMessage):

    """The server gets voice sounds from a client"""

    def serverAction(self, table:'ServerTable', msg:'Request') ->None:
        """save voice sounds on the server"""
        assert isinstance(msg.args, list)
        assert msg.player
        voice = msg.player.voice
        assert voice
        voice.archiveContent = msg.args[0]
        if Debug.sound:
            if voice.oggFiles():
                logDebug(f'{msg.player}: server got wanted voice data {voice}')
            else:
                logDebug(f'{msg.player}: server got empty voice data {voice} (arg0={repr(msg.args[0][:100])})')


class MessageDeclaredKong(ServerMessage):

    """the game server tells us who declared a kong"""

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """mirror the action locally"""
        prompts = None
        assert move.meld
        assert move.player
        if not client.thatWasMe(move.player):
            if len(move.meld) != 4 or move.meld[0].isConcealed:
                # do not do this when adding a 4th tile to an exposed pung
                move.player.showConcealedTiles(move.meld)
            else:
                move.player.showConcealedTiles(TileTuple(move.meld[3]))
            prompts = [cast(ClientMessage, Message.NoClaim), cast(ClientMessage, Message.MahJongg)]
        move.exposedMeld = move.player.exposeMeld(move.meld)
        return client.ask(move, prompts) if prompts else None


class MessageRobbedTheKong(NotifyAtOnceMessage, ServerMessage):

    """the game server tells us who robbed the kong"""

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """mirror the action locally"""
        assert client.game
        prevMove = next(client.game.lastMoves(only=[Message.DeclaredKong]))
        assert prevMove.player
        prevMove.player.robTileFrom(prevMove.meld[0].concealed)
        assert move.player
        move.player.robsTile()
        client.game.addCsvTag(
            f'robbedKong{prevMove.meld[1]}',
            forAllPlayers=True)


class MessageCalling(ServerMessage):

    """the game server tells us who announced a calling hand"""

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """tell user and save this information locally"""
        assert move.player
        move.player.popupMsg(self)
        move.player.isCalling = True
        return client.ask(move, [Message.OK])


class MessageDangerousGame(ServerMessage):

    """the game server tells us who played dangerous game"""

    def __init__(self) ->None:
        ServerMessage.__init__(self, name=i18ncE('kajongg', 'Dangerous Game'))

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """mirror the dangerous game action locally"""
        assert move.player
        move.player.popupMsg(self)
        move.player.playedDangerous = True
        return client.ask(move, [Message.OK])


class MessageNoChoice(ServerMessage):

    """the game server tells us who had no choice avoiding dangerous game"""

    def __init__(self) ->None:
        ServerMessage.__init__(self, name=i18ncE('kajongg', 'No Choice'))
        self.move:Optional['Move'] = None

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """mirror the no choice action locally"""
        self.move = move
        assert move.player
        move.player.popupMsg(self)
        move.player.claimedNoChoice = True
        move.player.showConcealedTiles(move.tiles)
        # otherwise we have a visible artifact of the discarded tile.
        # Only when animations are disabled. Why?
#        Internal.mainWindow.centralView.resizeEvent(None)
        return client.ask(move, [Message.OK]).addCallback(self.hideConcealedAgain).addErrback(logException)

    def hideConcealedAgain(self, result:Tuple[Message, None]) ->Tuple[Message, None]:
        """only show them for explaining the 'no choice'"""
        assert self.move
        assert self.move.player
        self.move.player.showConcealedTiles(self.move.tiles, False)
        return result


class MessageUsedDangerousFrom(ServerMessage):

    """the game server tells us somebody claimed a dangerous tile"""

    def clientAction(self, client:'Client', move:'Move') ->Any:
        assert client.game
        fromPlayer = cast('PlayingPlayer', client.game.playerByName(str(move.source)))
        assert move.player
        move.player.usedDangerousFrom = fromPlayer
        if Debug.dangerousGame:
            logDebug(f'{move.player} claimed a dangerous tile discarded by {fromPlayer}')


class MessageDraw(ServerMessage):

    """the game server tells us nobody said mah jongg"""
    sendScore = True


class MessageError(ServerMessage):

    """a client errors"""
    needsGame = False

    def clientAction(self, client:'Client', move:'Move') ->Any:
        """show the error message from server"""
        return logWarning(str(move.source))


class MessageNO(ClientMessage):

    """a client says no"""


class MessageOK(ClientMessage):

    """a client says OK"""

    def __init__(self) ->None:
        ClientMessage.__init__(self,
                               name=i18ncE('kajongg', 'OK'),
                               shortcut=i18ncE('kajongg game dialog:Key for OK', 'O'))

    def toolTip(self, button:'DlgButton', tile:Optional[Tile]) ->Tuple[str, bool, str]:
        """return text and warning flag for button and text for tile for button and text for tile"""
        return i18n('Confirm that you saw the message'), False, ''


class MessageNoClaim(NotifyAtOnceMessage, ServerMessage):

    """A player explicitly says he will not claim a tile"""

    def __init__(self) ->None:
        NotifyAtOnceMessage.__init__(self,
                                     name=i18ncE('kajongg', 'No Claim'),
                                     shortcut=i18ncE('kajongg game dialog:Key for No claim', 'N'))

    def toolTip(self, button:'DlgButton', tile:Optional[Tile]) ->Tuple[str, bool, str]:
        """return text and warning flag for button and text for tile for button and text for tile"""
        return i18n('You cannot or do not want to claim this tile'), False, ''

    @classmethod
    def receivers(cls, request:'Request') ->List['PlayingPlayer']:
        """no Claim notifications are not needed for those who already answered"""
        result = [x.player for x in request.block.requests if x.answer is None]
        return cast(List['PlayingPlayer'], result)


def __scanSelf() ->None:
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
                        logDebug(f'cannot instantiate {glob.__name__}')
                        raise
                    type.__setattr__(
                        Message, msg.name.replace(' ', ''), msg)
                    Message.defined[msg.name] = msg


class ChatMessage(ReprMixin):

    """holds relevant info about a chat message"""

    def __init__(self, tableid:Union[Tuple[Any, ...], int], fromUser:Optional[str]=None,
                 message:Optional[str]=None, isStatusMessage:bool=False) ->None:
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

    def localtimestamp(self) ->datetime.datetime:
        """convert from UTC to local"""
        now = datetime.datetime.now()
        utcnow = datetime.datetime.utcnow()
        result = datetime.datetime.combine(
            datetime.date.today(),
            self.timestamp)
        return result + (now - utcnow)

    def __str__(self) ->str:
        local = self.localtimestamp()
        # pylint says something about NotImplemented, check with later versions
        _ = i18n(self.message)
        if self.isStatusMessage:
            _ = f'[{_}]'
        return (f'{int(local.hour):02}:{int(local.minute):02}:{int(local.second):02} '
                f'{self.fromUser}: {i18n(self.message)}')

    def asList(self) ->Tuple[Any, ...]:
        """encode me for network transfer"""
        return (
            self.tableid, self.timestamp.hour, self.timestamp.minute, self.timestamp.second,
            self.fromUser, self.message, self.isStatusMessage)

__scanSelf()
