#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

from util import m18nc, m18ncE, logWarning

class Message(object):
    """those are the message types between client and server. They have no state
    i.e. they never hold real data. They only describe the message and actions upon it"""

    defined = {}

    def __init__(self, name, shortcut=None):
        """those are the english values"""
        self.name = name
        self.methodName = name.replace(' ', '')
        self.id = len(Message.defined)
        Message.defined[self.id] = self
        Message.defined[self.name] = self

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<Message: %s>" % self

    def isActivePlayer(self, table, msg):
        if msg.player == table.game.activePlayer:
            return True
        errMsg = '%s said %s but is not the active player' % (msg.player, msg.answer.name)
        self.abort(errMsg)

class MessageFromServer(Message):
    def __init__(self, name):
        Message.__init__(self, name)

    def clientAction(self, client, move):
        logException('clientAction is not defined for %s. msg:%s' % (self, move))

class MessageFromClient(Message):
    def __init__(self, name, shortcut=None):
        Message.__init__(self, name, shortcut)
        self.shortcut = shortcut
        self.i18nName = m18nc('kajongg', self.name)
        self.notifyAtOnce = False

    def buttonCaption(self):
        """localized, with a & for the shortcut"""
        i18nShortcut = m18nc('kajongg game dialog:Key for '+self.name, self.shortcut)
        return self.i18nName.replace(i18nShortcut, '&'+i18nShortcut, 1)

    def serverAction(self, table, msg):
        logException('serverAction is not defined for %s. msg:%s' % (self, msg))

class NotifyAtOnceMessage(MessageFromClient):
    def __init__(self, name, shortcut=None):
        MessageFromClient.__init__(self, name, shortcut)
        self.notifyAtOnce = True

class MessagePung(NotifyAtOnceMessage):
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name=m18ncE('kajongg','Pung'),
            shortcut=m18ncE('kajongg game dialog:Key for Pung', 'P'))
    def serverAction(self, table, msg):
        table.claimTile(msg.player, self, msg.args[0], Message.CalledPung)

class MessageKong(NotifyAtOnceMessage):
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name=m18ncE('kajongg','Kong'),
            shortcut=m18ncE('kajongg game dialog:Key for Kong', 'K'))
    def serverAction(self, table, msg):
        if msg.player == table.game.activePlayer:
            table.declareKong(msg.player, msg.args[0])
        else:
            table.claimTile(msg.player, self, msg.args[0], Message.CalledKong)

class MessageChow(NotifyAtOnceMessage):
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name=m18ncE('kajongg','Chow'),
            shortcut=m18ncE('kajongg game dialog:Key for Chow', 'C'))
    def serverAction(self, table, msg):
        if table.game.nextPlayer() != msg.player:
            table.abort('player %s illegally said Chow' % msg.player)
        else:
            table.claimTile(msg.player, self, msg.args[0], Message.CalledChow)

class MessageBonus(MessageFromClient):
    def __init__(self):
        MessageFromClient.__init__(self, 'Bonus')
    def serverAction(self, table, msg):
        if self.isActivePlayer(table, msg):
            table.pickedBonus(msg.player, msg.args[0])

class MessageMahJongg(NotifyAtOnceMessage):
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name=m18ncE('kajongg','Mah Jongg'),
            shortcut=m18ncE('kajongg game dialog:Key for Mah Jongg', 'M'))
    def serverAction(self, table, msg):
        table.claimMahJongg(msg)

class MessageOriginalCall(NotifyAtOnceMessage):
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name=m18ncE('kajongg','Original Call'),
            shortcut=m18ncE('kajongg game dialog:Key for Original Call', 'O'))
    def serverAction(self, table, msg):
        if self.isActivePlayer(table, msg):
            msg.player.originalCall = True
            table.tellAll(msg.player, Message.MadeOriginalCall, table.moved)

class MessageViolatesOriginalCall(NotifyAtOnceMessage):
    def __init__(self):
        NotifyAtOnceMessage.__init__(self,
            name = m18ncE('kajongg', 'Violates Original Call'))
    def serverAction(self, table, msg):
        if self.isActivePlayer(table, msg):
            msg.player.mayWin = False
            table.tellAll(msg.player, Message.ViolatedOriginalCall, table.moved)

class MessageDiscard(MessageFromClient):
    def __init__(self):
        MessageFromClient.__init__(self,
            name=m18ncE('kajongg','Discard'),
            shortcut=m18ncE('kajongg game dialog:Key for Discard', 'D'))
    def serverAction(self, table, msg):
        if self.isActivePlayer(table, msg):
            tile = msg.args[0]
            if tile not in msg.player.concealedTiles:
                table.abort('player %s discarded %s but does not have it' % (msg.player, tile))
                return
            table.game.hasDiscarded(msg.player, tile)
            table.tellAll(msg.player,Message.HasDiscarded, table.askForClaims, tile=tile)

class MessageReadyForGameStart(MessageFromServer):
    def __init__(self):
        MessageFromServer.__init__(self, 'readyForGameStart')

    def clientAction(self, client, move):
        # move.source are the players in seating order
        # we cannot just use table.playerNames - the seating order is now different (random)
        client.readyForGameStart(move.tableid, move.seed, move.source, shouldSave=move.shouldSave)

class MessageReadyForHandStart(MessageFromServer):
    def __init__(self):
        MessageFromServer.__init__(self, 'readyForHandStart')

    def clientAction(self, client, move):
        client.readyForHandStart(move.source, move.rotate)

class MessageInitHand(MessageFromServer):
    def __init__(self):
        MessageFromServer.__init__(self, 'initHand')

    def clientAction(self, client, move):
        client.game.divideAt = move.divideAt
        client.game.showField()

class MessageSetTiles(MessageFromServer):
    def __init__(self):
        MessageFromServer.__init__(self, 'setTiles')

    def clientAction(self, client, move):
        client.game.setTiles(move.player, move.source)

class MessageShowTiles(MessageFromServer):
    def __init__(self):
        MessageFromServer.__init__(self, 'showTiles')

    def clientAction(self, client, move):
        client.game.showTiles(move.player, move.source)

class MessageSaveHand(MessageFromServer):
    def __init__(self):
        MessageFromServer.__init__(self, 'saveHand')

    def clientAction(self, client, move):
        client.game.saveHand()

class MessagePopupMsg(MessageFromServer):
    def __init__(self):
        MessageFromServer.__init__(self, 'popupMsg')

    def clientAction(self, client, move):
        move.player.popupMsg(move.msg)

class MessageHasDiscarded(MessageFromServer):
    def __init__(self):
        MessageFromServer.__init__(self, 'hasDiscarded')

    def clientAction(self, client, move):
        move.player.speak(move.tile)
        if move.tile != move.player.lastTile:
            client.invalidateOriginalCall(move.player)
        client.game.hasDiscarded(move.player, move.tile)

class MessageAskForClaims(MessageFromServer):
    def __init__(self):
        MessageFromServer.__init__(self, 'askForClaims')

    def clientAction(self, client, move):
        if not client.thatWasMe(move.player):
            if client.game.IAmNext():
                client.ask(move, [Message.NoClaim, Message.Chow, Message.Pung, Message.Kong, Message.MahJongg])
            else:
                client.ask(move, [Message.NoClaim, Message.Pung, Message.Kong, Message.MahJongg])

class MessagePickedTile(MessageFromServer):
    def __init__(self):
        MessageFromServer.__init__(self, 'pickedTile')

    def clientAction(self, client, move):
        client.game.wall.dealTo(deadEnd=move.deadEnd)
        client.game.pickedTile(move.player, move.source, move.deadEnd)
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
    def __init__(self):
        MessageFromServer.__init__(self, 'calledChow')

    def clientAction(self, client, move):
        client.called(move)

class MessageCalledPung(MessageFromServer):
    def __init__(self):
        MessageFromServer.__init__(self, 'calledPung')

    def clientAction(self, client, move):
        client.called(move)

class MessageCalledKong(MessageFromServer):
    def __init__(self):
        MessageFromServer.__init__(self, 'calledKong')

    def clientAction(self, client, move):
        client.called(move)

class MessagePickedBonus(MessageFromServer):
    def __init__(self):
        MessageFromServer.__init__(self, 'pickedBonus')

    def clientAction(self, client, move):
        assert not client.thatWasMe(move.player)
        move.player.makeTilesKnown(move.source)

class MessageActivePlayer(MessageFromServer):
    def __init__(self):
        MessageFromServer.__init__(self, 'activePlayer')

    def clientAction(self, client, move):
        client.game.activePlayer = move.player

class MessageMadeOriginalCall(MessageFromServer):
    def __init__(self):
        MessageFromServer.__init__(self, 'madeOriginalCall')

    def clientAction(self, client, move):
        move.player.originalCall = True
        if client.thatWasMe(move.player):
            answers = [Message.Discard, Message.MahJongg]
            client.ask(move, answers)

class MessageViolatedOriginalCall(MessageFromServer):
    def __init__(self):
        MessageFromServer.__init__(self, 'violatedOriginalCall')

    def clientAction(self, client, move):
        move.player.mayWin = False
        if client.thatWasMe(move.player):
            client.ask(move, [Message.OK])

class MessageDeclaredKong(MessageFromServer):
    def __init__(self):
        MessageFromServer.__init__(self, 'declaredKong')

    def clientAction(self, client, move):
        prompts = None
        client.invalidateOriginalCall(move.player)
        if not client.thatWasMe(move.player):
            move.player.makeTilesKnown(move.source)
            prompts = [Message.NoClaim, Message.MahJongg]
        move.exposedMeld = move.player.exposeMeld(move.source, claimed=False)
        if prompts:
            client.ask(move, prompts)

class MessageRobbedTheKong(MessageFromServer):
    def __init__(self):
        MessageFromServer.__init__(self, 'robbedTheKong')

    def clientAction(self, client, move):
        prevMove = None
        for move in reversed(client.moves):
            if move.command == Message.DeclaredKong:
                prevMove = move
                break
        assert prevMove.message == Message.DeclaredKong
        prevKong = Meld(prevMove.source)
        prevMove.player.robTile(prevKong.pairs[0])
        move.player.lastSource = 'k'

class MessageDeclaredMahJongg(MessageFromServer):
    def __init__(self):
        MessageFromServer.__init__(self, 'declaredMahJongg')

    def clientAction(self, client, move):
        move.player.declaredMahJongg(move.source, move.withDiscard,
            move.lastTile, move.lastMeld)
        if move.player.balance != move.winnerBalance:
            logException('WinnerBalance is different for %s! player:%d, remote:%d,hand:%s' % \
                (move.player, move.player.balance, move.winnerBalance, move.player.computeHandContent()))

class MessageError(MessageFromServer):
    def __init__(self):
        MessageFromServer.__init__(self, 'error')

    def clientAction(self, client, move):
        if client.perspective:
            logWarning(move.source) # show messagebox
        else:
            logMessage(move.source, prio=syslog.LOG_WARNING)

if not Message.defined:
    """The text after 'Key for ' must be identical to the name"""
    Message.NO= MessageFromClient('NO')
    Message.OK = MessageFromClient(
        name=m18ncE('kajongg','OK'),
        shortcut=m18ncE('kajongg game dialog:Key for OK', 'O'))
    Message.NoClaim = MessageFromClient(
        name=m18ncE('kajongg','No Claim'),
        shortcut=m18ncE('kajongg game dialog:Key for No claim', 'N'))
    Message.Discard = MessageDiscard()
    Message.Pung = MessagePung()
    Message.Kong = MessageKong()
    Message.Chow = MessageChow()
    Message.MahJongg = MessageMahJongg()
    Message.OriginalCall = MessageOriginalCall()
    Message.ViolatesOriginalCall = MessageViolatesOriginalCall()
    Message.Bonus = MessageBonus()
    Message.ReadyForGameStart = MessageReadyForGameStart()
    Message.ReadyForHandStart = MessageReadyForHandStart()
    Message.InitHand = MessageInitHand()
    Message.SetTiles = MessageSetTiles()
    Message.ShowTiles = MessageShowTiles()
    Message.SaveHand = MessageSaveHand()
    Message.DeclaredKong = MessageDeclaredKong()
    Message.RobbedTheKong = MessageRobbedTheKong()
    Message.DeclaredMahJongg = MessageDeclaredMahJongg()
    Message.PopupMsg = MessagePopupMsg()
    Message.HasDiscarded = MessageHasDiscarded()
    Message.AskForClaims = MessageAskForClaims()
    Message.PickedTile = MessagePickedTile()
    Message.PickedBonus = MessagePickedBonus()
    Message.CalledChow = MessageCalledChow()
    Message.CalledPung = MessageCalledPung()
    Message.CalledKong = MessageCalledKong()
    Message.ActivePlayer = MessageActivePlayer()
    Message.MadeOriginalCall = MessageMadeOriginalCall()
    Message.ViolatedOriginalCall = MessageViolatedOriginalCall()
    Message.Error = MessageError()

