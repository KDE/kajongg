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

from __future__ import print_function

import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)

import os, sys, csv, subprocess, random, shutil, time
from collections import OrderedDict, defaultdict
from tempfile import mkdtemp

from optparse import OptionParser

from common import Debug
from util import removeIfExists, commit
from log import initLog

# fields in row:
RULESETFIELD = 0
AIFIELD = 1
COMMITFIELD = 2
GAMEFIELD = 3
TAGSFIELD = 4
PLAYERSFIELD = 5

COMMIT = OrderedDict()
SERVERS = defaultdict(list)

class Job(object):
    """a simple container"""
    def __init__(self, ruleset, aiVariant, commitId, game):
        self.ruleset = ruleset
        self.aiVariant = aiVariant
        self.commitId = commitId
        self.game = game

    def __str__(self):
        return '{ruleset} AI={aiVariant} commit={commitId} {game}'.format(**self.__dict__)

    def __repr__(self):
        return 'Job(%s)' % str(self)

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

def onlyExistingCommits(commits):
    """filter out non-existing commits"""
    result = []
    for commitId in commits:
        try:
            subprocess.check_output('git cat-file commit {commitId}'.format(
                commitId=commitId).split())
            result.append(commitId)
        except subprocess.CalledProcessError:
            pass
    return result

def removeInvalidCommitsFromCsv(csvFile):
    """remove rows with invalid git commit ids"""
    if not os.path.exists(csvFile):
        return
    rows = list(csv.reader(open(csvFile, 'r'), delimiter=';'))
    _ = set(x[COMMITFIELD] for x in rows)
    csvCommits = set(x for x in _ if set(x) <= set('0123456789abcdef') and len(x) >= 7)
    nonExisting = set(csvCommits) - set(onlyExistingCommits(csvCommits))
    if nonExisting:
        print('removing rows from kajongg.csv for commits %s' % ','.join(nonExisting))
        writer = csv.writer(open(csvFile, 'w'), delimiter=';')
        for row in rows:
            if row[COMMITFIELD] not in nonExisting:
                writer.writerow(row)

def readGames(csvFile):
    """returns a dict holding a frozenset of games for each variant"""
    if not os.path.exists(csvFile):
        return
    allRows = neutralize(csv.reader(open(csvFile,'r'), delimiter=';'))
    if not allRows:
        return
    # we want unique tuples so we can work with sets
    allRows = set(tuple(x) for x in allRows)
    games = dict()
    # build set of rows for every ai
    for variant in set(tuple(x[:COMMITFIELD]) for x in allRows):
        games[variant] = frozenset(x for x in allRows if tuple(x[:COMMITFIELD]) == variant)
    return games

def printDifferingResults(rowLists):
    """if most games get the same result with all tried variants,
    dump those games that do not"""
    allGameIds = {}
    for rows in rowLists:
        for row in rows:
            rowId = row[GAMEFIELD]
            if rowId not in allGameIds:
                allGameIds[rowId] = []
            allGameIds[rowId].append(row)
    differing = []
    for key, value in allGameIds.items():
        if len(set(tuple(list(x)[GAMEFIELD:]) for x in value)) > len(set(tuple(list(x)[:COMMITFIELD]) for x in value)):
            differing.append(key)
    if not differing:
        print('no games differ')
    elif float(len(differing)) / len(allGameIds) < 0.20:
        print('differing games (%d out of %d): %s' % (len(differing), len(allGameIds),
             ' '.join(sorted(differing, key=int))))

def evaluate(games):
    """evaluate games"""
    if not games:
        return
    commonGames = set()
    for variant, rows in games.items():
        gameIds = set(x[GAMEFIELD] for x in rows)
        if len(gameIds) != len(set(tuple(list(x)[GAMEFIELD:]) for x in rows)):
            print('ruleset "%s" AI "%s" has different rows for games' % (variant[0], variant[1]), end=' ')
            for game in sorted(gameIds, key=int):
                if len(set(tuple(x[GAMEFIELD:] for x in rows if x[GAMEFIELD] == game))) > 1:
                    print(game, end=' ')
            print()
            break
        commonGames &= gameIds
    printDifferingResults(games.values())
    print()
    print('the 3 robot players always use the Default AI')
    print()
    print('common games:')
    print('{ruleset:<25} {ai:<20} {games:>5}     {points:>4}                      human'.format(
        ruleset='Ruleset', ai='AI variant', games='games', points='points'))
    for variant, rows in games.items():
        ruleset, aiVariant = variant
        print('{ruleset:<25} {ai:<20} {games:>5}  '.format(ruleset = ruleset[:25], ai=aiVariant[:20],
            games=len(commonGames)), end=' ')
        for playerIdx in range(4):
            print('{p:>8}'.format(p=sum(int(x[PLAYERSFIELD+1+playerIdx*4])
                    for x in rows if x[GAMEFIELD] in commonGames)), end=' ')
        print()
    print()
    print('all games:')
    for variant, rows in games.items():
        ruleset, aiVariant = variant
        if len(rows) > len(commonGames):
            print('{ruleset:<25} {ai:<20} {rows:>5}  '.format(ruleset=ruleset[:25], ai=aiVariant[:20],
                rows=len(rows)), end=' ')
            for playerIdx in range(4):
                print('{p:>8}'.format(p=sum(int(x[PLAYERSFIELD+1+playerIdx*4]) for x in rows)), end=' ')
            print()

def startingDir():
    """the path of the directory where kajonggtest has been started in"""
    return os.path.dirname(sys.argv[0])

def srcDir(commitId):
    """the path of the directory where the particular test is running"""
    if commitId:
        return os.path.join(COMMIT[commitId], 'src')
    else:
        return '.'

def startServersFor(job, options):
    """starts count servers and returns a list of them"""
    if job.commitId not in COMMIT:
        COMMIT[job.commitId] = cloneSource(job.commitId) if job.commitId else '.'
    if job.commitId not in SERVERS:
        SERVERS[job.commitId] = [None] * options.servers
        for idx in range(options.servers):
            socketName = 'sock{idx}.{rnd}'.format(idx=idx, rnd=random.randrange(10000000))
            print('starting server for commit %s' % (job.commitId))
            cmd = ['{src}/kajonggserver.py'.format(src=srcDir(job.commitId)),
                    '--local', '--continue',
                    '--socket={sock}'.format(sock=socketName)]
            if options.debug:
                cmd.append('--debug={dbg}'.format(dbg=options.debug))
            popen = subprocess.Popen(cmd, cwd=srcDir(job.commitId))
            SERVERS[job.commitId][idx] = (popen, socketName)
            time.sleep(1) # make sure server runs before client is started

def stopServers():
    """stop all server processes"""
    for commitId in COMMIT.keys()[:]:
        stopServerFor(commitId)

def stopServerFor(commitId):
    """stop servers for commitId"""
    print('stopping server for commit %s' % commitId)
    for process, socketName in SERVERS[commitId]:
        try:
            process.terminate()
            _ = process.wait()
        except OSError:
            pass
        removeIfExists(socketName)
    del SERVERS[commitId]
    removeClone(COMMIT[commitId])
    del COMMIT[commitId]

def doJobs(jobs, options):
    """now execute all jobs"""
    # pylint: disable=too-many-branches, too-many-locals, too-many-statements

    if not options.git and options.csv:
        try:
            commit() # make sure we are at a point where comparisons make sense
        except UserWarning as exc:
            print(exc)
            print()
            print('Disabling CSV output')
            options.csv = None

    clients = [(None, '')] * options.clients
    srvIdx = 0
    try:
        while jobs:
            for qIdx, client in enumerate(clients):
                if client[0]:
                    result = client[0].poll()
                    if result is not None:
                        print('   Game over: %s%s' % ('Return code: %s ' % result if result else '', client[1]))
                        commitId = client[2]
                        clients[qIdx] = (None, '', None)
                        if commitId not in (x[2] for x in clients):
                            stopServerFor(commitId)
                    else:
                        if all(x[0] for x in clients):
                            time.sleep(1) # all clients are busy
                        continue
                if not jobs:
                    break
                job = jobs.pop(0)
                # never login to the same server twice at the
                # same time with the same player name
                startServersFor(job, options)
                player = qIdx // len(SERVERS[job.commitId]) + 1
                cmd = ['{src}/kajongg.py'.format(src=srcDir(job.commitId)),
                      '--game={game}'.format(game=job.game),
                      '--socket={sock}'.format(sock=SERVERS[job.commitId][srvIdx][1]),
                      '--player=Tester {player}'.format(player=player),
                      '--ruleset={ap}'.format(ap=job.ruleset)]
                if options.rounds:
                    cmd.append('--rounds={rounds}'.format(rounds=options.rounds))
                if job.aiVariant != 'Default':
                    cmd.append('--ai={ai}'.format(ai=job.aiVariant))
                if options.csv:
                    cmd.append('--csv={csv}'.format(csv=options.csv))
                if options.gui:
                    cmd.append('--demo')
                else:
                    cmd.append('--nogui')
                if options.playopen:
                    cmd.append('--playopen')
                if options.debug:
                    cmd.append('--debug={dbg}'.format(dbg=options.debug))
                msg = '{game} {ruleset} AI={ai} commit={commit} in {dir}'.format(
                    game=job.game, ruleset=job.ruleset, ai=job.aiVariant, commit=job.commitId, dir=COMMIT[job.commitId])
                print('Starting game %s' % msg)
                clients[qIdx] = (subprocess.Popen(cmd, cwd=srcDir(job.commitId)), msg, job.commitId)
                srvIdx += 1
                srvIdx %= len(SERVERS[job.commitId])
    except KeyboardInterrupt:
        for client, msg in clients:
            try:
                print('killing %s' % client[1])
                client[0].terminate()
                _ = client[0].wait()
            except OSError:
                pass
    finally:
        for client in clients:
            if client[0]:
                print('Waiting for   %s' % client[1])
                _ = os.waitpid(client[0].pid, 0)[1]

def parse_options():
    """parse options"""
    parser = OptionParser()
    parser.add_option('', '--gui', dest='gui', action='store_true',
        default=False, help='show graphical user interface')
    parser.add_option('', '--ruleset', dest='rulesets',
        default='ALL', help='play like a robot using RULESET: comma separated list. If missing, test all rulesets',
        metavar='RULESET')
    parser.add_option('', '--rounds', dest='rounds',
        help='play only # ROUNDS per game',
        metavar='ROUNDS')
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
    parser.add_option('', '--git', dest='git',
        help='check all commits: either a comma separated list or a range from..until')
    parser.add_option('', '--debug', dest='debug',
        help=Debug.help())

    return parser.parse_args()

def improve_options(options):
    """add sensible defaults"""
    # pylint: disable=too-many-branches
    if options.game and not options.count:
        options.count = 1
    if options.servers == 0:
        options.servers = max(1, options.clients // 2)

    cmd = ['{src}/kajongg.py'.format(src=startingDir()), '--rulesets=']
    knownRulesets = subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0].split('\n')
    knownRulesets = list(x.strip() for x in knownRulesets if x.strip())
    if options.rulesets == 'ALL':
        options.rulesets = ','.join(knownRulesets)
    else:
        wantedRulesets = options.rulesets.split(',')
        wrong = False
        for ruleset in wantedRulesets:
            matches = list(x for x in knownRulesets if ruleset in x)
            if len(matches) == 0:
                print('ruleset', ruleset, 'is not known', end=' ')
                wrong = True
            elif len(matches) > 1:
                print('ruleset', ruleset, 'is ambiguous:', matches)
                wrong = True
        if wrong:
            sys.exit(1)
    if options.git is not None:
        if '..' in options.git:
            commits = subprocess.check_output('git log --pretty=%h {range}'.format(range=options.git).split())
            options.git = list(reversed(list(x.strip() for x in commits.split('\n') if x.strip())))
        else:
            options.git = onlyExistingCommits(options.git.split(','))
            if not options.git:
                sys.exit(1)
        if options.csv:
            options.csv = os.path.abspath(options.csv)
    return options

def cloneSource(commitId):
    """make a temp directory for commitId"""
    tmpdir = mkdtemp(suffix='.' + commitId)
    subprocess.Popen('git clone --local --no-checkout -q .. {temp}'.format(
            temp=tmpdir).split()).wait()
    subprocess.Popen('git checkout -q {commitId}'.format(
            commitId=commitId).split(), cwd=tmpdir).wait()
    return tmpdir

def createJobs(options):
    """the complete list"""
    if not options.count:
        return []
    if options.game:
        games = list(range(int(options.game), options.game+options.count))
    else:
        games = list(int(random.random() * 10**9) for _ in range(options.count))
    jobs = []
    rulesets = options.rulesets.split(',')
    allAis = options.aiVariants.split(',')
    print('rulesets:', ' '.join(rulesets))
    print('AIs:', ' '.join(allAis))
    if options.git:
        print('commits:', ' '.join(options.git))
    print('games:', ' '.join(str(x) for x in games[:20]))
    options.servers = min(len(rulesets) * len(allAis) * len(games), options.servers)
    for commitId in options.git or [None]:
        for game in games:
            for ruleset in rulesets:
                for aiVariant in allAis:
                    jobs.append(Job(ruleset, aiVariant, commitId, game))
    return jobs

def main():
    """parse options, play, evaluate results"""

    initLog('kajonggtest')

    (options, args) = parse_options()

    removeInvalidCommitsFromCsv(options.csv)

    evaluate(readGames(options.csv))

    options = improve_options(options)

    errorMessage = Debug.setOptions(options.debug)
    if errorMessage:
        print(errorMessage)
        sys.exit(2)

    if args and ''.join(args):
        print('unrecognized arguments:', ' '.join(args))
        sys.exit(2)

    if not options.count:
        sys.exit(0)

    if not options.aiVariants:
        options.aiVariants = 'Default'

    print()

    jobs = createJobs(options)
    if jobs:
        try:
            doJobs(jobs, options)
        finally:
            stopServers()

    if options.csv:
        evaluate(readGames(options.csv))

def removeClone(tmpdir):
    """remove its tmpdir"""
    if tmpdir is not None and '/tmp/' in tmpdir:
        shutil.rmtree(tmpdir)

def cleanup(sig, dummyFrame):
    """at program end"""
    stopServers()
    sys.exit(sig)

# is one server for two clients.
if __name__ == '__main__':
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    main()
