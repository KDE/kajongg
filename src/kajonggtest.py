#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

import os, sys, csv, subprocess, random

from optparse import OptionParser

from common import Debug
from util import removeIfExists

def neutralize(rows):
    """remove things we do not want to compare"""
    for row in rows:
        for idx, field in enumerate(row):
            if field.startswith('Tester '):
                row[idx] = 'Tester'
            if 'MEM' in field:
                parts = field.split(',')
                for part in parts[:]:
                    if part.startswith('MEM'):
                        parts.remove(part)
                row[idx] = ','.join(parts)
        yield row

def readGames(csvFile):
    """returns a dict holding a frozenset of games for each AI variant"""
    if not os.path.exists(csvFile):
        return
    allRows = neutralize(csv.reader(open(csvFile,'r'), delimiter=';'))
    if not allRows:
        return
    # we want unique tuples so we can work with sets
    allRows = set(tuple(x) for x in allRows)
    games = dict()
    # build set of rows for every ai
    for aiVariant in set(x[0] for x in allRows):
        games[aiVariant] = frozenset(x for x in allRows if x[0] == aiVariant)
    return games

def printDifferingResults(rowLists):
    """if most games get the same result with all tried AI variants,
    dump those games that do not"""
    allGameIds = {}
    for rows in rowLists:
        for row in rows:
            rowId = row[1]
            if rowId not in allGameIds:
                allGameIds[rowId] = []
            allGameIds[rowId].append(row)
    differing = []
    for key, value in allGameIds.items():
        if len(set(tuple(list(x)[1:]) for x in value)) != 1:
            differing.append(key)
    if not differing:
        print 'no games differ'
    elif float(len(differing)) / len(allGameIds) < 0.20:
        print 'differing games (%d out of %d): %s' % (len(differing), len(allGameIds),
             ', '.join(sorted(differing)))

def evaluate(games):
    """evaluate games"""
    if not games:
        return
    commonGames = None
    for aiVariant, rows in games.items():
        gameIds = set(x[1] for x in rows)
        if len(gameIds) != len(rows):
            print 'AI variant "%s" has different rows for games' % aiVariant,
            for game in gameIds:
                if len([x for x in rows if x[1] == game]) > 1:
                    print game,
            print
            return
        if not commonGames:
            commonGames = gameIds
        else:
            commonGames &= gameIds
    printDifferingResults(games.values())
    print
    print 'the 3 robot players always use the Default AI'
    print
    print 'common games:'
    print '{ai:<20} {games:>5}     {points:>4}                      human'.format(
        ai='AI variant', games='games', points='points')
    for aiVariant, rows in games.items():
        print '{ai:<20} {games:>5}  '.format(ai=aiVariant[:20], games=len(commonGames)),
        for playerIdx in range(4):
            print '{p:>8}'.format(p=sum(int(x[4+playerIdx*4]) for x in rows if x[1] in commonGames)),
        print
    print
    print 'all games:'
    for aiVariant, rows in games.items():
        if len(rows) > len(commonGames):
            print '{ai:<20} {rows:>5}  '.format(ai=aiVariant[:20], rows=len(rows)),
            for playerIdx in range(4):
                print '{p:>8}'.format(p=sum(int(x[4+playerIdx*4]) for x in rows)),
            print

def proposeGames(games, optionAIVariants):
    """fill holes: returns games for testing such that the csv file
    holds more games tested for all AI variants"""
    if not games:
        return []
    for key, value in games.items():
        games[key] = frozenset(int(x[1]) for x in value)  # we only want the game
    for aiVariant in optionAIVariants.split(','):
        if aiVariant not in games:
            games[aiVariant] = frozenset()
    allgames = reduce(lambda x, y: x|y, games.values())
    occ = []
    for game in allgames:
        count = sum(game in x for x in games.values())
        if count < len(games.values()):
            occ.append((game, count))
    result = []
    for game in list(x[0] for x in sorted(occ, key=lambda x: -x[1])):
        for aiVariant, ids in games.items():
            if game not in ids:
                result.append((aiVariant, game))
    return result

def startServers(options):
    """starts count servers and returns a list of them"""
    srcDir = os.path.dirname(sys.argv[0])
    serverProcesses = [None] * options.servers
    for idx in range(options.servers):
        socketName = 'sock{idx}.{rnd}'.format(idx=idx, rnd=random.randrange(10000000))
        cmd = ['{src}/kajonggserver.py'.format(src=srcDir),
                '--local', '--continue',
                '--socket={sock}'.format(sock=socketName)]
        if options.debug:
            cmd.append('--debug={dbg}'.format(dbg=options.debug))
        serverProcesses[idx] = (subprocess.Popen(cmd), socketName)
    return serverProcesses

def stopServers(serverProcesses):
    """stop server processes"""
    for process, socketName in serverProcesses:
        process.terminate()
        _ = process.wait()
        removeIfExists(socketName)

def doJobs(jobs, options, serverProcesses):
    """now execute all jobs"""
    # pylint: disable=R0912
    # too many local branches
    srcDir = os.path.dirname(sys.argv[0])
    clients = [None] * options.clients
    srvIdx = 0
    try:
        while jobs:
            for qIdx, client in enumerate(clients):
                if client:
                    result = client.poll()
                    if result is None:
                        continue
                    clients[qIdx] = None
                if not jobs:
                    break
                aiVariant, game = jobs.pop(0)
                # never login to the same server twice at the
                # same time with the same player name
                player = qIdx // len(serverProcesses) + 1
                cmd = ['{src}/kajongg.py'.format(src=srcDir),
                      '--game={game}'.format(game=game),
                      '--socket={sock}'.format(sock=serverProcesses[srvIdx][1]),
                      '--csv={csv}'.format(csv=options.csv),
                      '--player=Tester {player}'.format(player=player),
                      '--ruleset={ap}'.format(ap=options.ruleset)]
                if aiVariant != 'Default':
                    cmd.append('--ai={ai}'.format(ai=aiVariant))
                if options.gui:
                    cmd.append('--demo')
                else:
                    cmd.append('--nogui')
                if options.playopen:
                    cmd.append('--playopen')
                if options.debug:
                    cmd.append('--debug={dbg}'.format(dbg=options.debug))
                clients[qIdx] = subprocess.Popen(cmd)
                srvIdx += 1
                srvIdx %= len(serverProcesses)
#    except KeyboardInterrupt:
#        pass
    finally:
        for client in clients:
            if client:
                _ = os.waitpid(client.pid, 0)[1]

def parse_options():
    """parse options"""
    parser = OptionParser()
    parser.add_option('', '--gui', dest='gui', action='store_true',
        default=False, help='show graphical user interface')
    parser.add_option('', '--ruleset', dest='ruleset',
        default='Testset', help='play like a robot using RULESET',
        metavar='RULESET')
    parser.add_option('', '--ai', dest='aiVariants',
        default=None, help='use AI variants: comma separated list',
        metavar='AI')
    parser.add_option('', '--csv', dest='csv',
        default='kajongg.csv', help='write results to CSV',
        metavar='CSV')
    parser.add_option('', '--game', dest='game',
        help='start first game with GAMEID, increment for following games.'
            ' Without this, random values are used.',
        metavar='GAMEID', type=int, default=0)
    parser.add_option('', '--count', dest='count',
        help='play COUNT games. Default is 99999',
        metavar='COUNT', type=int, default=99999)
    parser.add_option('', '--playopen', dest='playopen', action='store_true',
        help='all robots play with visible concealed tiles' , default=False)
    parser.add_option('', '--clients', dest='clients',
        help='start CLIENTS kajongg instances simultaneously',
        metavar='CLIENTS', type=int, default=1)
    parser.add_option('', '--servers', dest='servers',
        help='start SERVERS kajonggserver instances. Default is one server for two clients',
        metavar='SERVERS', type=int, default=0)
    parser.add_option('', '--fill', dest='fill', action='store_true',
        help='fill holes in results', default=False)
    parser.add_option('', '--debug', dest='debug',
        help=Debug.help())

    return parser.parse_args()

def improve_options(options):
    """add sensible defaults"""
    if options.game and not options.count:
        options.count = 1
    options.clients = min(options.clients, options.count)
    if options.servers == 0:
        options.servers = max(1, options.clients // 2)
    return options

def main():
    """parse options, play, evaluate results"""
    print

    (options, args) = parse_options()

    options = improve_options(options)

    errorMessage = Debug.setOptions(options.debug)
    if errorMessage:
        print errorMessage
        sys.exit(2)

    if args and ''.join(args):
        print 'unrecognized arguments:', ' '.join(args)
        sys.exit(2)

    evaluate(readGames(options.csv))

    if not options.count and not options.fill:
        sys.exit(0)

    if not options.aiVariants:
        options.aiVariants = 'Default'

    serverProcesses = startServers(options)
    try:
        if options.fill:
            jobs = proposeGames(readGames(options.csv), options.aiVariants)
            doJobs(jobs, options, serverProcesses)

        if options.count:
            if options.game:
                games = list(range(int(options.game), options.game+options.count))
            else:
                games = list(int(random.random() * 10**9) for _ in range(options.count))
            jobs = []
            allAis = options.aiVariants.split(',')
            for game in games:
                jobs.extend([(x, game) for x in allAis])
            doJobs(jobs, options, serverProcesses)
    finally:
        stopServers(serverProcesses)

    evaluate(readGames(options.csv))

# is one server for two clients.
if __name__ == '__main__':
    main()
