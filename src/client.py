#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""
Copyright (C) 2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

import socket, subprocess, time, datetime

from twisted.spread import pb
from twisted.cred import credentials
from twisted.internet.defer import Deferred
import util
from util import m18n, m18nc, m18ncE, logWarning, logException, logMessage, WINDS, syslogMessage, debugMessage, InternalParameters
import syslog
from scoringengine import Ruleset, PredefinedRuleset, meldsContent, Meld
from game import Players, Game, RemoteGame
from query import Query
from move import Move
from tile import Tile

class ClientTable(object):
    """the table as seen by the client"""
    def __init__(self, tableid, rulesetStr, playerNames):
        self.tableid = tableid
        self.ruleset = Ruleset.fromString(rulesetStr)
        self.playerNames = list(playerNames)
        
    def __str__(self):
        return 'Table %d rules %s players %s' % (self.tableid, self.ruleset.name, 
            ', '.join(self.playerNames))
    
class Client(pb.Referenceable):
    """interface to the server. This class only implements the logic,
    so we can also use it on the server for robot clients. Compare
    with HumanClient(Client)"""

    def __init__(self, username=None):
        """username is something like ROBOT 1 or None for the game server"""
        self.username = username
        self.game = None
        self.moves = []
        self.perspective = None # always None for a robot client
        self.tableList = None
        self.tables = []

    @apply
    def host():
        def fget(self):
            return Query.serverName
        return property(**locals())

    def isRobotClient(self):
        return bool(self.username)

    def isHumanClient(self):
        return False

    def isServerClient(self):
        return bool(not self.username)

    def remote_tablesChanged(self, tables):
        """update table list"""
        self.tables = [ClientTable(*x) for x in tables]
            
    def readyForGameStart(self, seed, playerNames, field=None, shouldSave=True):
        self.game = RemoteGame(playerNames.split('//'), self.table.ruleset,
            field=field, shouldSave=shouldSave, seed=seed, client=self)
        self.game.prepareHand()

    def readyForHandStart(self, tableid, playerNames, rotate):
        for idx, playerName in enumerate(playerNames.split('//')):
            self.game.players.byName(playerName).wind = WINDS[idx]
        if rotate:
            self.game.rotateWinds()
        self.game.prepareHand()

    def __answer(self, answer, meld, withDiscard=None, lastMeld=None):
        if self.perspective:
            # we might be called for a human client in demo mode
            self.callServer('claim', self.table[0], answer)
        else:
            self.table.claim(self.username, answer)
        if not lastMeld:
            lastMeld = Meld()
        return answer, meld, withDiscard, list(lastMeld.pairs)

    def ask(self, move, answers):
        """this is where the robot AI should go"""
        game = self.game
        myself = game.myself
        if 'Mah Jongg' in answers:
            withDiscard = game.lastDiscard if self.moves[-1].command == 'hasDiscarded' else None
            try:
                game.winner = myself
                hand = myself.computeHandContent(withTile=withDiscard)
            finally:
                game.winner = None
            if hand.maybeMahjongg():
                lastTile = withDiscard or myself.lastTile
                return self.__answer('Mah Jongg', meldsContent(hand.hiddenMelds),
                    withDiscard, hand.lastMeld(lastTile))
        if 'Kong' in answers:
            if game.activePlayer == myself:
                for tryTile in set(myself.concealedTiles):
                    if tryTile[0] not in 'fy':
                        meld = myself.containsPossibleKong(tryTile)
                        if meld:
                            break
            else:
                meld = myself.possibleKong(game.lastDiscard)
            if meld:
                return self.__answer('Kong', meld)
        if 'Pung' in answers:
            meld = myself.possiblePung(game.lastDiscard)
            if meld:
                return self.__answer('Pung', meld)
        if 'Chow' in answers:
            for chow in myself.possibleChows(game.lastDiscard):
                belongsToPair = False
                for tileName in chow:
                    if myself.concealedTiles.count(tileName) == 2:
                        belongsToPair = True
                        break
                if not belongsToPair:
                    return self.__answer('Chow', chow)

        answer = answers[0] # for now always return default answer
        if answer == 'Discard':
            # do not remove tile from hand here, the server will tell all players
            # including us that it has been discarded. Only then we will remove it.
            hand = move.player.computeHandContent()
            # TODO: also check what has been discarded an exposed
            for meldLen in range(1, 3):
                # hand.hiddenMelds are built from a set, order undefined. But
                # we want to be able to replay a game exactly, so sort them
                melds = sorted(list(x for x in hand.hiddenMelds if len(x) == meldLen),
                    key=lambda x: x.joined)
                if melds:
                    meld = melds[-1]
                    tileName = sorted(meld.pairs)[-1]
                    return 'Discard', tileName
            raise Exception('Player %s has nothing to discard:concTiles=%s concMelds=%s hand=%s' % (
                            move.player.name, move.player.concealedTiles, move.player.concealedMelds, hand))
        else:
            # the other responses do not have a parameter
            return answer

    def remote_move(self, tableid, playerName, command, **kwargs):
        """the server sends us info or a question and always wants us to answer"""
        player = None
        thatWasMe = False
        if self.game:
            self.game.checkSelectorTiles()
            if not self.game.client:
                # we aborted the game, ignore what the server tells us
                return
            myself = self.game.myself
            for p in self.game.players:
                if p.name == playerName:
                    player = p
            if not player:
                logException('Move references unknown player %s' % playerName)
            thatWasMe = player == myself
        if InternalParameters.debugTraffic:
            debugMessage('%s %s %s' % (player, command, kwargs))
        move = Move(player, command, kwargs)
        self.moves.append(move)
        if command == 'readyForGameStart':
            if self.isHumanClient():
                # the robot client gets self.table set directly
                self.table = None
                for table in self.tables:
                    if table.tableid == tableid:
                        self.table = table
                if not self.table:
                    logException('no table found with id %d, we have %s' % (tableid, ' '.join(x.tableid for x in self.tables)))
            # move.source are the players in seating order
            # we cannot just use table.playerNames - the seating order is now different (random)
            return self.readyForGameStart(move.seed, move.source, shouldSave=move.shouldSave)
        elif command == 'readyForHandStart':
            return self.readyForHandStart(tableid, ruleset, move.source, move.rotate)
        elif command == 'initHand':
            self.game.divideAt = move.divideAt
            self.game.showField()
        elif command == 'setTiles':
            self.game.setTiles(player, move.source)
        elif command == 'showTiles':
            self.game.showTiles(player, move.source)
        elif command == 'declaredMahJongg':
            player.declaredMahJongg(move.source, move.withDiscard,
                move.lastTile, Meld(move.lastMeld))
            if player.balance != move.winnerBalance:
                logException('WinnerBalance is different for %s! player:%d, remote:%d,hand:%s' % \
                    (player, player.balance, move.winnerBalance, player.computeHandContent()))
        elif command == 'saveHand':
            self.game.saveHand()
        elif command == 'popupMsg':
            return player.popupMsg(move.msg)
        elif command == 'activePlayer':
            self.game.activePlayer = player
        elif command == 'pickedTile':
            self.game.wall.dealTo(deadEnd=move.deadEnd)
            self.game.pickedTile(player, move.source, move.deadEnd)
            if thatWasMe:
                if move.source[0] in 'fy':
                    return 'Bonus', move.source
                if self.game.lastDiscard:
                    return self.ask(move, ['Discard', 'Mah Jongg'])
                else:
                    return self.ask(move, ['Discard', 'Kong', 'Mah Jongg'])
        elif command == 'pickedBonus':
            assert not thatWasMe
            player.makeTilesKnown(move.source)
        elif command == 'declaredKong':
            if not thatWasMe:
                player.makeTilesKnown(move.source)
            player.exposeMeld(move.source, claimed=False)
            if self.game.prevActivePlayer == myself and self.perspective:
                # even here we ask otherwise if all other players are robots we would
                # have no time to see it if a robot calls MJ on my discarded tile
                return self.ask(move, ['OK'])
        elif command == 'hasDiscarded':
            self.game.hasDiscarded(player, move.tile)
            if not thatWasMe:
                if self.game.IAmNext():
                    return self.ask(move, ['No Claim', 'Chow', 'Pung', 'Kong', 'Mah Jongg'])
                else:
                    return self.ask(move, ['No Claim', 'Pung', 'Kong', 'Mah Jongg'])
        elif command in ['calledChow', 'calledPung', 'calledKong']:
            assert self.game.lastDiscard in move.source, '%s %s'% (self.game.lastDiscard, move.source)
            if self.perspective:
                self.discardBoard.lastDiscarded.board = None
                self.discardBoard.lastDiscarded = None
            if thatWasMe:
                player.addTile(self.game.lastDiscard)
                player.lastTile = self.game.lastDiscard.lower()
            else:
                player.addTile('Xy')
                player.makeTilesKnown(move.source)
            player.lastSource = 'd'
            player.exposeMeld(move.source)
            if thatWasMe:
                if command != 'calledKong':
                    # we will get a replacement tile first
                    return self.ask(move, ['Discard', 'Mah Jongg'])
            elif self.game.prevActivePlayer == myself and self.perspective:
                # even here we ask otherwise if all other players are robots we would
                # have no time to see it if the next player calls Chow
                return self.ask(move, ['OK'])
        elif command == 'error':
            if self.perspective:
                logWarning(move.source) # show messagebox
            else:
                logMessage(move.source, prio=syslog.LOG_WARNING)

