#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2014 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
from tempfile import mkdtemp

from optparse import OptionParser

from common import Debug
from util import removeIfExists, gitHead
from log import initLog

# fields in row:
RULESETFIELD = 0
AIFIELD = 1
COMMITFIELD = 2
GAMEFIELD = 3
TAGSFIELD = 4
PLAYERSFIELD = 5

OPTIONS = None

class Clone(object):
    """make a temp directory for commitId"""
    clones = {}
    def __new__(cls, commitId):
        if commitId in cls.clones:
            return cls.clones[commitId]
        return object.__new__(cls)

    def __init__(self, commitId):
        self.commitId = commitId
        self.clones[commitId] = self
        if commitId is 'current':
            self.tmpdir = os.path.abspath('..')
            srcDir = os.path.join(self.tmpdir, 'src')
            assert os.path.exists(srcDir), '{} does not exist'.format(srcDir)
        else:
            self.tmpdir = mkdtemp(suffix='.' + commitId)
            subprocess.Popen('git clone --local --no-checkout -q .. {temp}'.format(
                temp=self.tmpdir).split()).wait()
            subprocess.Popen('git checkout -q {commitId}'.format(
                commitId=commitId).split(), cwd=self.tmpdir).wait()

    def remove(self):
        """remove my tmpdir"""
        del self.clones[self.commitId]
        if self.commitId != 'current' and '/tmp/' in self.tmpdir:
            shutil.rmtree(self.tmpdir)

    @classmethod
    def removeUnused(cls):
        """remove clones we do not use anymore"""
        for commitId in cls.clones.keys():
            if not any(x.commitId == commitId for x in Job.jobs):
                cls.clones[commitId].remove()

    @classmethod
    def removeAll(cls):
        """remove all clones even if they are in use"""
        for cloneKey in cls.clones.keys()[:]:
            cls.clones[cloneKey].remove()

class Client(object):
    """a simple container, assigning process to job"""
    def __init__(self, process=None, job=None):
        self.process = process
        self.job = job

class TooManyClients(UserWarning):
    """we would surpass options.clients"""

class TooManyServers(UserWarning):
    """we would surpass options.servers"""

class Server(object):
    """represents a kajongg server instance. Called when we want to start a job."""
    servers = []
    def __new__(cls, job):
        """can we reuse an existing server?"""
        if sum(len(x.jobs) for x in cls.servers) >= OPTIONS.clients:
            raise TooManyClients
        if len(cls.servers) >= OPTIONS.servers:
            # must re-use a server
            matchingServers = list(x for x in cls.servers if x.jobs[0].serverKey() == job.serverKey())
            matchingServers.sort(key=lambda x: len(x.jobs))
            if matchingServers:
                return matchingServers[0]
            raise TooManyServers
        result = object.__new__(cls)
        cls.servers.append(result)
        return result

    def __init__(self, job):
        if not hasattr(self, 'jobs'):
            self.jobs = []
            self.process = None
            self.socketName = None
            self.serverKey = None
            self.clone = Clone(job.commitId)
            self.start(job)
        else:
            self.jobs.append(job)
        job.server = self

    def start(self, job):
        """start this server"""
        assert self.process is None, 'Server.start already has a process'
        self.jobs.append(job)
        if os.name == 'nt':
            self.socketName = random.randrange(1025, 65000)
        else:
            self.socketName = os.path.expanduser(os.path.join('~', '.kajongg',
                'sock{id}.{rnd}'.format(id=id(self), rnd=random.randrange(10000000))))
        assert self.serverKey in (None, job.serverKey()), '{} not in (None, {})'.format(self.serverKey, job.serverKey())
        self.serverKey = job.serverKey()
        print('starting server for %s' % job)
        cmd = [os.path.join(job.srcDir(), 'kajonggserver.py')]
        if os.name == 'nt':
            cmd.insert(0, 'python')
            cmd.append('--port={sock}'.format(sock=self.socketName))
        else:
            cmd.append('--socket={sock}'.format(sock=self.socketName))
        if OPTIONS.debug:
            cmd.append('--debug={dbg}'.format(dbg=','.join(OPTIONS.debug)))
        if OPTIONS.qt5:
            cmd.append('--qt5')
        if OPTIONS.log:
            self.process = subprocess.Popen(cmd, cwd=job.srcDir(),
                stdout=job.logFile, stderr=job.logFile)
        else:
            # reuse this server (otherwise it stops by itself)
            cmd.append('--continue')
            self.process = subprocess.Popen(cmd, cwd=job.srcDir())

    def stop(self, job=None):
        """maybe stop the server"""
        if self not in self.servers:
            # already stopped
            return
        if job:
            self.jobs.remove(job)
        if len(self.jobs) == 0:
            self.servers.remove(self)
            if self.process:
                print('killing server %s for  %s' % (self, job))
                try:
                    self.process.terminate()
                    _ = self.process.wait()
                except OSError:
                    pass
            if self.socketName and os.name != 'nt':
                removeIfExists(self.socketName)
        Clone.removeUnused()

    @classmethod
    def stopAll(cls):
        """stop all servers even if clients are still there"""
        for server in cls.servers:
            for job in server.jobs[:]:
                server.stop(job)
            assert len(server.jobs) == 0, 'stopAll expects no server jobs but found {}'.format(server.jobs)
            server.stop()

    def __str__(self):
        return '{} pid={} sock={}'.format(self.serverKey, self.process.pid, self.socketName)

class Job(object):
    """a simple container"""
    jobs = []
    def __init__(self, ruleset, aiVariant, commitId, game):
        self.ruleset = ruleset
        self.aiVariant = aiVariant
        self.commitId = commitId
        self.game = game
        self.__logFile = None
        self.logFileName = None
        self.process = None
        self.server = None
        self.started = False
        self.jobs.append(self)

    def srcDir(self):
        """the path of the directory where the particular test is running"""
        return os.path.join(Clone.clones[self.commitId].tmpdir, 'src')

    def start(self):
        """start this job"""
        self.server = Server(self)
        # never login to the same server twice at the
        # same time with the same player name
        player = self.server.jobs.index(self) + 1
        cmd = [os.path.join(self.srcDir(), 'kajongg.py'),
              '--game={game}'.format(game=self.game),
              '--socket={sock}'.format(sock=self.server.socketName),
              '--player=Tester {player}'.format(player=player),
              '--ruleset={ap}'.format(ap=self.ruleset)]
        if os.name == 'nt':
            cmd.insert(0, 'python')
        if OPTIONS.rounds:
            cmd.append('--rounds={rounds}'.format(rounds=OPTIONS.rounds))
        if self.aiVariant != 'Default':
            cmd.append('--ai={ai}'.format(ai=self.aiVariant))
        if OPTIONS.csv:
            cmd.append('--csv={csv}'.format(csv=OPTIONS.csv))
        if OPTIONS.gui:
            cmd.append('--demo')
        else:
            cmd.append('--nogui')
        if OPTIONS.qt5:
            cmd.append('--qt5')
        if OPTIONS.playopen:
            cmd.append('--playopen')
        if OPTIONS.debug:
            cmd.append('--debug={dbg}'.format(dbg=','.join(OPTIONS.debug)))
        print('starting            %s' % self)
        if OPTIONS.log:
            self.process = subprocess.Popen(cmd, cwd=self.srcDir(),
                stdout=self.logFile, stderr=self.logFile)
        else:
            self.process = subprocess.Popen(cmd, cwd=self.srcDir())
        self.started = True

    def check(self, silent=False):
        """if done, cleanup"""
        if not self.started or not self.process:
            return
        result = self.process.poll()
        if result is not None:
            self.process = None
            if not silent:
                print('   Game over: %s%s' % ('Return code: %s ' % result if result else '', self))
            self.jobs.remove(self)
            self.server.stop(self)
        else:
            if all(x.process for x in self.jobs):
                time.sleep(1) # all jobs are busy

    def serverKey(self):
        """this defines what a server can be used for"""
        if OPTIONS.log:
            # because we want the server debug data only for this
            # job, each job needs its own server instance
            return '/'.join([str(self.game), self.ruleset, self.aiVariant, self.commitId])
        else:
            return self.commitId

    @property
    def logFile(self):
        """open if needed"""
        if self.__logFile is None:
            logDir = os.path.expanduser(os.path.join('~', '.kajongg', 'log', str(self.game),
                self.ruleset, self.aiVariant))
            if not os.path.exists(logDir):
                os.makedirs(logDir)
            logFileName = self.commitId
            self.logFileName = os.path.join(logDir, logFileName)
            self.__logFile = open(self.logFileName, 'w', buffering=0)
        return self.__logFile

    def shortRulesetName(self):
        """strip leading chars if they are identical for all rulesets"""
        names = OPTIONS.knownRulesets
        for prefix in range(100):
            if sum(x.startswith(self.ruleset[:prefix]) for x in names) == 1:
                return self.ruleset[prefix-1:]

    def __str__(self):
        game = 'game={}'.format(self.game)
        ruleset = self.shortRulesetName()
        aiName = 'AI={}'.format(self.aiVariant) if self.aiVariant != 'Default' else ''
        commit = 'commit={}'.format(self.commitId)
        return ' '.join([game, ruleset, aiName, commit]).replace('  ', ' ')

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

KNOWNCOMMITS = set()

def onlyExistingCommits(commits):
    """filter out non-existing commits"""
    global KNOWNCOMMITS # pylint: disable=global-statement
    if len(KNOWNCOMMITS) == 0:
        for branch in subprocess.check_output('git branch'.split(), env={'LANG':'C'}).split('\n'):
            if not 'detached' in branch and not 'no branch' in branch:
                KNOWNCOMMITS |= set(subprocess.check_output(
                    'git log --max-count=200 --pretty=%h {branch}'.format(
                        branch=branch[2:]).split()).split('\n'))
    return list(x for x in commits if x in KNOWNCOMMITS)

def removeInvalidCommits(csvFile):
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
    # now remove all logs referencing obsolete commits
    for dirName, _, fileNames in os.walk('log'):
        for fileName in fileNames:
            fullName = os.path.join(dirName, fileName)
            if fileName not in KNOWNCOMMITS and fileName != 'current':
                os.remove(fullName)
        try:
            os.removedirs(dirName)
        except OSError:
            pass # not yet empty

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

def doJobs(jobs):
    """now execute all jobs"""
    # pylint: disable=too-many-branches, too-many-locals, too-many-statements

    if not OPTIONS.git and OPTIONS.csv:
        if gitHead() in ('current', None):
            print('Disabling CSV output: %s' % ('You have uncommitted changes' if gitHead() == 'current' else 'No git'))
            print()
            OPTIONS.csv = None

    try:
        while jobs:
            for checkJob in Job.jobs[:]:
                checkJob.check()
            try:
                jobs[0].start()
                jobs = jobs[1:]
            except TooManyClients :
                time.sleep(3)
            except TooManyServers:
                time.sleep(3)
            Clone.removeUnused()
    except KeyboardInterrupt:
        Server.stopAll()
    except BaseException as exc:
        print(exc)
        raise exc
    finally:
        while True:
            for job in Job.jobs[:]:
                if not job.started:
                    Job.jobs.remove(job)
                else:
                    job.check()
                    if job.process:
                        print('Waiting for   %s' % job)
                        job.process.wait()
            if not Server.servers:
                if Job.jobs:
                    print('we have jobs %s but no servers' % list(id(x) for x in Job.jobs))
                break
            time.sleep(1)

def parse_options():
    """parse options"""
    parser = OptionParser()
    parser.add_option('', '--gui', dest='gui', action='store_true',
        default=False, help='show graphical user interface')
    parser.add_option('', '--qt5', dest='qt5', action='store_true',
        default=False, help='Force using Qt5')
    parser.add_option('', '--ruleset', dest='rulesets',
        default='ALL', help='play like a robot using RULESET: comma separated list. If missing, test all rulesets',
        metavar='RULESET')
    parser.add_option('', '--rounds', dest='rounds',
        help='play only # ROUNDS per game',
        metavar='ROUNDS')
    parser.add_option('', '--ai', dest='aiVariants',
        default=None, help='use AI variants: comma separated list',
        metavar='AI')
    parser.add_option('', '--log', dest='log', action='store_true',
        default=False, help='write detailled debug info to ~/.kajongg/log/game/ruleset/commit.' \
                ' This starts a separate server process per job.')
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

def improve_options():
    """add sensible defaults"""
    # pylint: disable=too-many-branches,too-many-statements
    if OPTIONS.count > 10000:
        if OPTIONS.game:
            OPTIONS.count = 1
        elif OPTIONS.log:
            OPTIONS.count = 5
    if OPTIONS.servers == 0:
        OPTIONS.servers = max(1, OPTIONS.clients // 2)

    cmdPath = os.path.join(startingDir(), 'kajongg.py')
    cmd = ['python', cmdPath, '--rulesets=']
    OPTIONS.knownRulesets = subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0].split('\n')
    OPTIONS.knownRulesets = list(x.strip() for x in OPTIONS.knownRulesets if x.strip())
    if OPTIONS.rulesets == 'ALL':
        OPTIONS.rulesets = OPTIONS.knownRulesets
    else:
        wantedRulesets = OPTIONS.rulesets.split(',')
        usingRulesets = []
        wrong = False
        for ruleset in wantedRulesets:
            matches = list(x for x in OPTIONS.knownRulesets if ruleset in x)
            if len(matches) == 0:
                print('ruleset', ruleset, 'is not known', end=' ')
                wrong = True
            elif len(matches) > 1:
                exactMatch = list(x for x in OPTIONS.knownRulesets if ruleset == x)
                if len(exactMatch) == 1:
                    usingRulesets.append(exactMatch[0])
                else:
                    print('ruleset', ruleset, 'is ambiguous:', matches)
                    wrong = True
            else:
                usingRulesets.append(matches[0])
        if wrong:
            sys.exit(1)
        OPTIONS.rulesets = usingRulesets
    if OPTIONS.git is not None:
        if '..' in OPTIONS.git:
            if not '^' in OPTIONS.git:
                OPTIONS.git = OPTIONS.git.replace('..', '^..')
            commits = subprocess.check_output('git log --pretty=%h {range}'.format(range=OPTIONS.git).split())
            OPTIONS.git = list(reversed(list(x.strip() for x in commits.split('\n') if x.strip())))
        else:
            OPTIONS.git = onlyExistingCommits(OPTIONS.git.split(','))
            if not OPTIONS.git:
                sys.exit(1)
    if OPTIONS.debug is None:
        OPTIONS.debug = []
    else:
        OPTIONS.debug = [OPTIONS.debug]
    if OPTIONS.log:
        OPTIONS.servers = OPTIONS.clients
        OPTIONS.debug.extend(
            'neutral,dangerousGame,explain,originalCall,robbingKong,robotAI,scores,traffic,hand'.split(','))
    if gitHead() not in ('current', None):
        OPTIONS.debug.append('git')

def createJobs():
    """the complete list"""
    if not OPTIONS.count:
        return []
    if OPTIONS.game:
        games = list(range(int(OPTIONS.game), OPTIONS.game+OPTIONS.count))
    else:
        games = list(int(random.random() * 10**9) for _ in range(OPTIONS.count))
    jobs = []
    allAis = OPTIONS.aiVariants.split(',')
    print('rulesets:', ', '.join(OPTIONS.rulesets))
    print('AIs:', ' '.join(allAis))
    if OPTIONS.git:
        print('commits:', ' '.join(OPTIONS.git))
    print('games:', ' '.join(str(x) for x in games[:20]))
    for commitId in OPTIONS.git or ['current']:
        for game in games:
            for ruleset in OPTIONS.rulesets:
                for aiVariant in allAis:
                    jobs.append(Job(ruleset, aiVariant, commitId, game))
    OPTIONS.servers = min(len(jobs), OPTIONS.servers)
    print('jobs:', len(jobs))
    return jobs

def main():
    """parse options, play, evaluate results"""
    global OPTIONS # pylint: disable=global-statement
    initLog('kajonggtest')

    (OPTIONS, args) = parse_options()
    OPTIONS.csv = os.path.expanduser(os.path.join('~', '.kajongg', 'kajongg.csv'))
    if not os.path.exists(os.path.dirname(OPTIONS.csv)):
        os.makedirs(os.path.dirname(OPTIONS.csv))

    removeInvalidCommits(OPTIONS.csv)

    evaluate(readGames(OPTIONS.csv))

    improve_options()

    errorMessage = Debug.setOptions(','.join(OPTIONS.debug))
    if errorMessage:
        print(errorMessage)
        sys.exit(2)

    if args and ''.join(args):
        print('unrecognized arguments:', ' '.join(args))
        sys.exit(2)

    if not OPTIONS.count:
        sys.exit(0)

    if not OPTIONS.aiVariants:
        OPTIONS.aiVariants = 'Default'

    print()

    jobs = createJobs()
    if jobs:
        doJobs(jobs)
        if OPTIONS.csv:
            evaluate(readGames(OPTIONS.csv))

def cleanup(sig, dummyFrame):
    """at program end"""
    Server.stopAll()
    Clone.removeAll()
    sys.exit(sig)

# is one server for two clients.
if __name__ == '__main__':
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    main()
