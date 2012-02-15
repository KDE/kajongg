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

import os, sys, csv, subprocess, time, random

from optparse import OptionParser

from common import Debug

def readGames(csvFile):
    """returns a dict holding a frozenset of games for each AI variant"""
    if not os.path.exists(csvFile):
        return
    allRows = list(csv.reader(open(csvFile,'r'), delimiter=';'))
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
    # TODO: dump details for the hand with the largest difference
    # between default and tested intelligence for the human player

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
    print '{:<20} {:>5}     {:>4}                      human'.format('AI variant', 'games', 'points')
    for aiVariant, rows in games.items():
        print '{:<20} {:>5}  '.format(aiVariant[:20], len(commonGames)),
        for playerIdx in range(4):
            print '{:>8}'.format(sum(int(x[3+playerIdx*4]) for x in rows if x[1] in commonGames)),
        print
    print
    print 'all games:'
    for aiVariant, rows in games.items():
        if len(rows) > len(commonGames):
            print '{:<20} {:>5}  '.format(aiVariant[:20], len(rows)),
            for playerIdx in range(4):
                print '{:>8}'.format(sum(int(x[3+playerIdx*4]) for x in rows)),
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
    serverProcesses = [None] * options.jobs
    for idx in range(options.jobs):
        socketName = 'sock{}.{}'.format(idx, random.randrange(10000000))
        cmd = ['{}/kajonggserver.py'.format(srcDir),
                '--local', '--continue',
                '--socket={}'.format(socketName)]
        cmd.extend(common_options(options))
        serverProcesses[idx] = (subprocess.Popen(cmd), socketName)
    return serverProcesses

def stopServers(serverProcesses):
    """stop server processes"""
    for process, socketName in serverProcesses:
        process.terminate()
        os.remove(socketName)

def doJobs(jobs, options, serverProcesses):
    """now execute all jobs"""
    srcDir = os.path.dirname(sys.argv[0])
    processes = [None] * options.jobs
    try:
        while jobs:
            time.sleep(1)
            for qIdx, process in enumerate(processes):
                if process:
                    result = process.poll()
                    if result is None:
                        continue
                    processes[qIdx] = None
                if not jobs:
                    break
                aiVariant, game = jobs.pop(0)
                cmd = ['{}/kajongg.py'.format(srcDir),
                      '--ai={}'.format(aiVariant),
                      '--game={}'.format(game),
                      '--socket={}'.format(serverProcesses[qIdx][1]),
                      '--csv={}'.format(options.csv),
                      '--autoplay={}'.format(options.ruleset)]
                if not options.gui:
                    cmd.append('--nogui')
                if options.playopen:
                    cmd.append('--playopen')
                cmd.extend(common_options(options))
                processes[qIdx] = subprocess.Popen(cmd)
#    except KeyboardInterrupt:
#        pass
    finally:
        for process in processes:
            if process:
                _ = os.waitpid(process.pid, 0)[1]

def common_options(options):
    """common options for kajonggtest.py and kajongg.py"""
    result = []
    if options.showtraffic:
        result.append('--showtraffic')
    if options.showsql:
        result.append('--showsql')
    if options.debug:
        result.append('--debug={}'.format(options.debug))
    return result

def parse_options():
    """parse options"""
    parser = OptionParser()
    parser.add_option('', '--gui', dest='gui', action='store_true',
        default=False, help='show graphical user interface')
    parser.add_option('', '--autoplay', dest='ruleset',
        default='Testset', help='play like a robot using RULESET',
        metavar='RULESET')
    parser.add_option('', '--ai', dest='aiVariants',
        default=None, help='use AI variants: comma separated list',
        metavar='AI')
    parser.add_option('', '--csv', dest='csv',
        default='kajongg.csv', help='write results to CSV',
        metavar='CSV')
    parser.add_option('', '--game', dest='game',
        help='start first game with GAMEID, increment for following games',
        metavar='GAMEID', type=int, default=0)
    parser.add_option('', '--count', dest='count',
        help='play COUNT games',
        metavar='COUNT', type=int, default=0)
    parser.add_option('', '--showtraffic', dest='showtraffic', action='store_true',
        help='show network messages', default=False)
    parser.add_option('', '--playopen', dest='playopen', action='store_true',
        help='all robots play with visible concealed tiles' , default=False)
    parser.add_option('', '--showsql', dest='showsql', action='store_true',
        help='show database SQL commands', default=False)
    parser.add_option('', '--jobs', dest='jobs',
        help='start JOBS kajongg instances simultaneously, each with a dedicated server',
        metavar='JOBS', type=int, default=1)
    parser.add_option('', '--fill', dest='fill', action='store_true',
        help='fill holes in results', default=False)
    parser.add_option('', '--debug', dest='debug',
        help=Debug.help())

    return parser.parse_args()

def main():
    """parse options, play, evaluate results"""
    print

    (options, args) = parse_options()

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

        if options.game and options.count:
            games = list(range(int(options.game), options.game+options.count))
            jobs = []
            allAis = options.aiVariants.split(',')
            for game in games:
                jobs.extend([(x, game) for x in allAis])
            doJobs(jobs, options, serverProcesses)
    finally:
        stopServers(serverProcesses)

    evaluate(readGames(options.csv))


if __name__ == '__main__':
    main()
