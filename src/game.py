#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008,2009 Wolfgang Rohdewald <wolfgang@rohdewald.de>

kmj is free software you can redistribute it and/or modify
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

import sys, datetime, syslog, string
from random import randrange, shuffle

from util import logMessage,  logException, m18n, WINDS

from query import Query
from scoringengine import Ruleset
from tileset import Elements

class Players(list):
    """a list of players where the player can also be indexed by wind"""

    allNames = {}
    allIds = {}

    def __init__(self, players):
        list.__init__(self)
        self.extend(players)

    def __getitem__(self, index):
        """allow access by idx or by wind"""
        if isinstance(index, (bytes, str)) and len(index) == 1:
            # bytes for Python 2.6, str for 3.0
            for player in self:
                if player.wind == index:
                    return player
            logException(Exception("no player has wind %s" % index))
        return list.__getitem__(self, index)

    def __str__(self):
        return ', '.join(list('%s: %s' % (x.name, x.wind) for x in self))

    def byId(self, playerid):
        """lookup the player by id"""
        for player in self:
            if player.nameid == playerid:
                return player
        logException(Exception("no player has id %d" % playerid))

    @staticmethod
    def load():
        """load all defined players into self.allIds and self.allNames"""
        query = Query("select id,host,name from player")
        if not query.success:
            sys.exit(1)
        Players.allIds = {}
        Players.allNames = {}
        for record in query.data:
            (nameid, host,  name) = record
            Players.allIds[(host, name)] = nameid
            Players.allNames[nameid] = (host, name)

    @staticmethod
    def createIfUnknown(host, name):
        if (host, name) not in Players.allNames.values():
            Query("insert into player(host,name) values('%s','%s')" % (host, name))
            Players.load()
        assert (host, name) in Players.allNames.values()

class Player(object):
    """all player related data without GUI stuff"""
    def __init__(self, game, handContent=None):
        self.game = game
        self.handContent = handContent
        self.__balance = 0
        self.__payment = 0
        self.name = ''
        self.wind = WINDS[0]
        self.total = 0
        self.tiles = []

    @apply
    def nameid():
        """the name id of this player"""
        def fget(self):
            return Players.allIds[(self.game.host,  self.name)]
        return property(**locals())

    @apply
    def balance():
        """the balance of this player"""
        def fget(self):
            return self.__balance
        def fset(self, balance):
            assert balance == 0
            self.__balance = 0
            self.__payment = 0
        return property(**locals())

    def getsPayment(self, payment):
        """make a payment to this player"""
        self.__balance += payment
        self.__payment += payment

    @apply
    def payment():
        """the payments for the current hand"""
        def fget(self):
            return self.__payment
        def fset(self, payment):
            assert payment == 0
            self.__payment = 0
        return property(**locals())

    def __repr__(self):
        return '%s %s' % (self.name,  self.wind)

class Game(object):
    """the game without GUI"""
    def __init__(self, host, names, ruleset, gameid=None, field=None):
        """a new game instance. May be shown on a field, comes from database if gameid is set"""
        if not host:
            host = ''
        self.host = host
        self.rotated = 0
        self.field = field
        self.ruleset = None
        self.winner = None
        self.roundsFinished = 0
        self.gameid = gameid
        self.handctr = 0
        self.tiles = None
        self.diceSum = None
        self.client = None # default: no network game
        # shift rules taken from the OEMC 2005 rules
        # 2nd round: S and W shift, E and N shift
        self.shiftRules = 'SWEN,SE,WE'
        if field:
            self.players = field.genPlayers(self)
        else:
            self.players = Players([Player(self) for idx in range(4)])
        for idx, player in enumerate(self.players):
            Players.createIfUnknown(host, names[idx])
            player.name = names[idx]
        self.__useRuleset(ruleset)
        if not self.gameid:
            self.gameid = self.__newGameId()

    def losers(self):
        """the 3 or 4 losers: All players without the winner"""
        return list([x for x in self.players if x is not self.winner])

    @staticmethod
    def __windOrder(player):
        """cmp function for __exchangeSeats"""
        return 'ESWN'.index(player.wind)

    def __exchangeSeats(self):
        """execute seat exchanges according to the rules"""
        windPairs = self.shiftRules.split(',')[self.roundsFinished-1]
        while len(windPairs):
            windPair = windPairs[0:2]
            windPairs = windPairs[2:]
            swappers = list(self.players[windPair[x]] for x in (0, 1))
            if self.field is None or self.field.askSwap(swappers):
                swappers[0].wind,  swappers[1].wind = swappers[1].wind,  swappers[0].wind
        self.players.sort(key=Game.__windOrder)

    def __newGameId(self):
        """write a new entry in the game table with the selected players
        and returns the game id of that new entry"""
        starttime = datetime.datetime.now().replace(microsecond=0).isoformat()
        # first insert and then find out which game id we just generated. Clumsy and racy.
        return Query([
            "insert into game(starttime,ruleset,p0,p1,p2,p3) values('%s', %d, %s)" % \
                (starttime, self.ruleset.rulesetId, ','.join(str(p.nameid) for p in self.players)),
            "update usedruleset set lastused='%s' where id=%d" %\
                (starttime, self.ruleset.rulesetId),
            "update ruleset set lastused='%s' where hash='%s'" %\
                (starttime, self.ruleset.hash),
            "select id from game where starttime = '%s'" % \
                starttime]).data[0][0]

    def __useRuleset(self,  ruleset):
        """use a copy of ruleset for this game, reusing an existing copy"""
        self.ruleset = ruleset
        self.ruleset.load()
        query = Query('select id from usedruleset where hash="%s"' % \
              (self.ruleset.hash))
        if query.data:
            # reuse that usedruleset
            self.ruleset.rulesetId = query.data[0][0]
        else:
            # generate a new usedruleset
            self.ruleset.rulesetId = self.ruleset.newId(used=True)
            self.ruleset.save()

    def saveHand(self):
        """save hand to data base, update score table and balance in status line"""
        self.__payHand()
        self.__saveScores()
        self.rotate()

    def deal(self):
        """generate new tile list and new diceSum"""
        self.tiles = map(string.upper, Elements.all())
        shuffle(self.tiles)
        self.diceSum = randrange(1, 7) + randrange(1, 7)
        for wind in WINDS:
            count = 14 if wind == 'E' else 13
            player = self.players[wind]
            player.tiles = self.tiles[:count]
            self.tiles = self.tiles[count:]
            print 'deal:player:tiles:', player.name, player.wind, player.tiles

    def __saveScores(self):
        """save computed values to data base, update score table and balance in status line"""
        scoretime = datetime.datetime.now().replace(microsecond=0).isoformat()
        cmdList = []
        for player in self.players:
            if player.handContent:
                manualrules = '||'.join(x.name for x, meld in player.handContent.usedRules)
            else:
                manualrules = m18n('Score computed manually')
            cmdList.append("INSERT INTO SCORE "
            "(game,hand,data,manualrules,player,scoretime,won,prevailing,wind,points,payments, balance,rotated) "
            "VALUES(%d,%d,'%s','%s',%d,'%s',%d,'%s','%s',%d,%d,%d,%d)" % \
            (self.gameid, self.handctr, player.handContent.string, manualrules, player.nameid,
                scoretime, int(player == self.winner),
            WINDS[self.roundsFinished], player.wind, player.total,
            player.payment, player.balance, self.rotated))
        Query(cmdList)

    def savePenalty(self, player, offense, amount):
        """save computed values to data base, update score table and balance in status line"""
        scoretime = datetime.datetime.now().replace(microsecond=0).isoformat()
        cmdList = []
        cmdList.append("INSERT INTO SCORE "
            "(game,hand,data,manualrules,player,scoretime,won,prevailing,wind,points,payments, balance,rotated) "
            "VALUES(%d,%d,'%s','%s',%d,'%s',%d,'%s','%s',%d,%d,%d,%d)" % \
            (self.gameid, self.handctr, player.handContent.string, offense.name, player.nameid,
                scoretime, int(player == self.winner),
            WINDS[self.roundsFinished], player.wind, 0,
            amount, player.balance, self.rotated))
        Query(cmdList)
        if self.field:
            self.field.showBalance()


    def rotate(self):
        """rotate winds, exchange seats. If finished, update database"""
        self.handctr += 1
        if self.winner and self.winner.wind != 'E':
            self.rotated += 1
            if self.rotated == 4:
                if not self.finished():
                    self.roundsFinished += 1
                self.rotated = 0
            if self.finished():
                endtime = datetime.datetime.now().replace(microsecond=0).isoformat()
                Query('UPDATE game set endtime = "%s" where id = %d' % \
                      (endtime, self.gameid))
            else:
                winds = [player.wind for player in self.players]
                winds = winds[3:] + winds[0:3]
                for idx,  newWind in enumerate(winds):
                    self.players[idx].wind = newWind
                if 0 < self.roundsFinished < 4 and self.rotated == 0:
                    self.__exchangeSeats()

    @staticmethod
    def load(gameid, field=None):
        """load game data by game id and return a new Game instance"""
        qGame = Query("select p0, p1, p2, p3, ruleset from game where id = %d" % gameid)
        if not qGame.data:
            return None
        rulesetId = qGame.data[0][4] or 1
        ruleset = Ruleset(rulesetId, used=True)
        Players.load() # we want to make sure we have the current definitions
        hosts = []
        names = []
        for idx in range(4):
            nameid = qGame.data[0][idx]
            try:
                (host, name) = Players.allNames[nameid]
            except KeyError:
                name = m18n('Player %1 not known', nameid)
            hosts.append(host)
            names.append(name)
        if len(set(hosts)) != 1:
            logException('Game %d has players from different hosts' % gameid)
        game = Game(hosts[0], names, ruleset, gameid=gameid, field=field)

        qLastHand = Query("select hand,rotated from score where game=%d and hand="
            "(select max(hand) from score where game=%d)" % (gameid, gameid))
        if qLastHand.data:
            (game.handctr, game.rotated) = qLastHand.data[0]

        qScores = Query("select player, wind, balance, won, prevailing from score "
            "where game=%d and hand=%d" % (gameid, game.handctr))
        for record in qScores.data:
            playerid = record[0]
            wind = str(record[1])
            player = game.players.byId(playerid)
            if not player:
                logMessage(
                'game %d data inconsistent: player %d missing in game table' % \
                    (gameid, playerid), syslog.LOG_ERR)
            else:
                player.getsPayment(record[2])
                player.wind = wind
            if record[3]:
                game.winner = player
            prevailing = record[4]
        game.roundsFinished = WINDS.index(prevailing)
        game.rotate()
        return game

    def finished(self):
        """The game is over after 4 completed rounds"""
        return self.roundsFinished == 4

    def __payHand(self):
        """pay the scores"""
        winner = self.winner
        for player in self.players:
            if player.handContent.hasAction('payforall'):
                score = winner.total
                if winner.wind == 'E':
                    score = score * 6
                else:
                    score = score * 4
                player.getsPayment(-score)
                winner.getsPayment(score)
                return

        for idx1, player1 in enumerate(self.players):
            for idx2, player2 in enumerate(self.players):
                if idx1 != idx2:
                    if player1.wind == 'E' or player2.wind == 'E':
                        efactor = 2
                    else:
                        efactor = 1
                    if player2 != winner:
                        player1.getsPayment(player1.total * efactor)
                    if player1 != winner:
                        player1.getsPayment(-player2.total * efactor)

