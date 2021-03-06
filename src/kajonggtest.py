#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Copyright (C) 2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

Kajongg is free software you can redistribute it and/or modify
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

import os
import sys
import subprocess
import random
import shutil
import time
import gc

from optparse import OptionParser

from common import Debug, StrMixin, cacheDir
from util import removeIfExists, gitHead, checkMemory
from util import Csv, CsvWriter, popenReadlines

# fields in row:
RULESETFIELD = 0
AIFIELD = 1
COMMITFIELD = 2
PYTHON23FIELD = 3
GAMEFIELD = 4
TAGSFIELD = 5
PLAYERSFIELD = 6

OPTIONS = None

KNOWNCOMMITS = set()

class Clone:

    """make a temp directory for commitId"""

    def __init__(self, commitId):
        self.commitId = commitId
        if commitId != 'current':
            tmpdir = os.path.expanduser(os.path.join(cacheDir(), commitId))
            if not os.path.exists(tmpdir):
                subprocess.Popen('git clone --shared --no-checkout -q .. {temp}'.format(
                    temp=tmpdir).split()).wait()
                subprocess.Popen('git checkout -q {commitId}'.format(
                    commitId=commitId).split(), cwd=tmpdir).wait()

    def sourceDirectory(self):
        """the source directory for this git commit"""
        if self.commitId == 'current':
            tmpdir = os.path.abspath('..')
            result = os.path.join(tmpdir, 'src')
        else:
            result = os.path.join(cacheDir(), self.commitId, 'src')
        assert os.path.exists(result), '{} does not exist'.format(result)
        return result

    @classmethod
    def removeObsolete(cls):
        """remove all clones for obsolete commits"""
        for commitDir in os.listdir(cacheDir()):
            if not any(x.startswith(commitDir) for x in KNOWNCOMMITS):
                removeDir = os.path.join(cacheDir(), commitDir)
                shutil.rmtree(removeDir)

class Client:

    """a simple container, assigning process to job"""

    def __init__(self, process=None, job=None):
        self.process = process
        self.job = job


class TooManyClients(UserWarning):

    """we would surpass options.clients"""


class TooManyServers(UserWarning):

    """we would surpass options.servers"""


class Server(StrMixin):

    """represents a kajongg server instance. Called when we want to start a job."""
    servers = []
    count = 0

    def __new__(cls, job):
        """can we reuse an existing server?"""
        running = Server.allRunningJobs()
        if len(running) >= OPTIONS.clients:
            raise TooManyClients
        maxClientsPerServer = OPTIONS.clients / OPTIONS.servers
        matchingServers = list(
            x for x in cls.servers
            if x.commitId == job.commitId
            and x.pythonVersion == job.pythonVersion
            and len(x.jobs) < maxClientsPerServer)
        if matchingServers:
            result = sorted(matchingServers, key=lambda x: len(x.jobs))[0]
        else:
            if len(cls.servers) >= OPTIONS.servers:
                # maybe we can kill a server without jobs?
                for server in cls.servers:
                    if len(server.jobs) == 0:
                        server.stop()
                        break  # we only need to stop one server
                else:
                    # no server without jobs found
                    raise TooManyServers
            result = object.__new__(cls)
            cls.servers.append(result)
        return result

    def __init__(self, job):
        if not hasattr(self, 'jobs'):
            self.jobs = []
            self.process = None
            self.socketName = None
            self.portNumber = None
            self.commitId = job.commitId
            self.pythonVersion = job.pythonVersion
            self.clone = Clone(job.commitId)
            self.start(job)
        else:
            self.jobs.append(job)

    @classmethod
    def allRunningJobs(cls):
        """a list of all jobs on all servers"""
        return sum((x.jobs for x in cls.servers), [])

    def start(self, job):
        """start this server"""
        job.server = self
        assert self.process is None, 'Server.start already has a process'
        self.jobs.append(job)
        assert self.commitId == job.commitId, 'Server.commitId {} != Job.commitId {}'.format(
            self.commitId, job.commitId)
        cmd = [os.path.join(
            job.srcDir(),
            'kajonggserver.py')]
        cmd.insert(0, 'python{}'.format(self.pythonVersion))
        if OPTIONS.usePort:
            self.portNumber = random.randrange(1025, 65000)
            cmd.append('--port={port}'.format(port=self.portNumber))
        else:
            Server.count += 1
            self.socketName = os.path.expanduser(
                os.path.join('~', '.kajongg',
                             'sock{commit}.py{py}.{ctr}'.format(
                                 commit=self.commitId, py=self.pythonVersion, ctr=Server.count)))
            cmd.append('--socket={sock}'.format(sock=self.socketName))
        if OPTIONS.debug:
            cmd.append('--debug={dbg}'.format(dbg=','.join(OPTIONS.debug)))
        if OPTIONS.log:
            self.process = subprocess.Popen(
                cmd, cwd=job.srcDir(),
                stdout=job.logFile, stderr=job.logFile)
        else:
            # reuse this server (otherwise it stops by itself)
            cmd.append('--continue')
            self.process = subprocess.Popen(cmd, cwd=job.srcDir())
        print('{} started'.format(self))

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
                try:
                    self.process.terminate()
                    self.process.wait()
                except OSError:
                    pass
                print('{} killed'.format(self))
            if self.socketName:
                removeIfExists(self.socketName)

    @classmethod
    def stopAll(cls):
        """stop all servers even if clients are still there"""
        for server in cls.servers:
            for job in server.jobs[:]:
                server.stop(job)
            assert len(server.jobs) == 0, 'stopAll expects no server jobs but found {}'.format(
                server.jobs)
            server.stop()

    def __str__(self):
        return 'Server {} Python{}{} {}'.format(
            self.commitId,
            self.pythonVersion,
            ' pid={}'.format(self.process.pid) if Debug.process else '',
            'port={}'.format(self.portNumber) if self.portNumber else 'socket={}'.format(self.socketName))


class Job(StrMixin):

    """a simple container"""

    def __init__(self, pythonVersion, ruleset, aiVariant, commitId, game):
        self.pythonVersion = pythonVersion
        self.ruleset = ruleset
        self.aiVariant = aiVariant
        self.commitId = commitId
        self.game = game
        self.__logFile = None
        self.logFileName = None
        self.process = None
        self.server = None
        self.started = False

    def srcDir(self):
        """the path of the directory where the particular test is running"""
        assert self.server, 'Job {} has no server'.format(self)
        assert self.server.clone, 'Job {} has no server.clone'.format(self)
        return self.server.clone.sourceDirectory()

    def __startProcess(self, cmd):
        """call Popen"""
        if OPTIONS.log:
            self.process = subprocess.Popen(
                cmd, cwd=self.srcDir(),
                stdout=self.logFile, stderr=self.logFile)
        else:
            self.process = subprocess.Popen(cmd, cwd=self.srcDir())
        print('       %s started' % (self))

    def start(self):
        """start this job"""
        # pylint: disable=too-many-branches
        self.server = Server(self)
        # never login to the same server twice at the
        # same time with the same player name
        player = self.server.jobs.index(self) + 1
        cmd = [os.path.join(self.srcDir(), 'kajongg.py'),
               '--game={game}'.format(game=self.game),
               '--player={tester} {player}'.format(
                   player=player,
                   tester='Tüster'),
               '--ruleset={ap}'.format(ap=self.ruleset)]
        if self.server.socketName:
            cmd.append('--socket={sock}'.format(sock=self.server.socketName))
        if self.server.portNumber:
            cmd.append('--port={port}'.format(port=self.server.portNumber))
        cmd.insert(0, 'python{}'.format(self.pythonVersion))
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
        if OPTIONS.playopen:
            cmd.append('--playopen')
        if OPTIONS.debug:
            cmd.append('--debug={dbg}'.format(dbg=','.join(OPTIONS.debug)))
        self.__startProcess(cmd)
        self.started = True

    def check(self, silent=False):
        """if done, cleanup"""
        if not self.started or not self.process:
            return
        result = self.process.poll()
        if result is not None:
            self.process = None
            if not silent:
                print('       {} done{}'.format(self, 'Return code: {}'.format(result) if result else ''))
            self.server.jobs.remove(self)

    @property
    def logFile(self):
        """open if needed"""
        if self.__logFile is None:
            logDir = os.path.expanduser(
                os.path.join('~', '.kajongg', 'log', str(self.game),
                             self.ruleset, self.aiVariant, str(self.pythonVersion)))
            if not os.path.exists(logDir):
                os.makedirs(logDir)
            logFileName = self.commitId
            self.logFileName = os.path.join(logDir, logFileName)
            self.__logFile = open(self.logFileName, 'wb', buffering=0)
        return self.__logFile

    def shortRulesetName(self):
        """strip leading chars if they are identical for all rulesets"""
        names = OPTIONS.knownRulesets
        for prefix in range(100):
            if sum(x.startswith(self.ruleset[:prefix]) for x in names) == 1:
                return self.ruleset[prefix - 1:]

    def __str__(self):
        pid = 'pid={}'.format(
            self.process.pid) if self.process and Debug.process else ''
        game = 'game={}'.format(self.game)
        ruleset = self.shortRulesetName()
        aiName = 'AI={}'.format(
            self.aiVariant) if self.aiVariant != 'Default' else ''
        return ' '.join([
            self.commitId, 'Python{}'.format(self.pythonVersion), pid, game, ruleset, aiName]).replace('  ', ' ')


def neutralize(rows):
    """remove things we do not want to compare"""
    for row in rows:
        for idx, field in enumerate(row):
            field = field.replace(' ', '')
            if field.startswith('Tester ') or field.startswith('Tüster'):
                field = 'Tester'
            if 'MEM' in field:
                parts = field.split(',')
                for part in parts[:]:
                    if part.startswith('MEM'):
                        parts.remove(part)
                field = ','.join(parts)
            row[idx] = field
        yield row


def onlyExistingCommits(commits):
    """filter out non-existing commits"""
    global KNOWNCOMMITS  # pylint: disable=global-statement
    if len(KNOWNCOMMITS) == 0:
        for branch in subprocess.check_output(b'git branch'.split()).decode().split('\n'):
            if 'detached' not in branch and 'no branch' not in branch:
                KNOWNCOMMITS |= set(subprocess.check_output(
                    'git log --max-count=200 --pretty=%H {branch}'.format(
                        branch=branch[2:]).split()).decode().split('\n'))
    result = list()
    for commit in commits:
        if any(x.startswith(commit) for x in KNOWNCOMMITS):
            result.append(commit)
    return result


def removeInvalidCommits(csvFile):
    """remove rows with invalid git commit ids"""
    if not os.path.exists(csvFile):
        return
    rows = list(Csv.reader(csvFile))
    _ = set(x[COMMITFIELD] for x in rows)
    csvCommits = set(
        x for x in _ if set(
            x) <= set(
                '0123456789abcdef') and len(
                    x) >= 7)
    nonExisting = set(csvCommits) - set(onlyExistingCommits(csvCommits))
    if nonExisting:
        print(
            'removing rows from kajongg.csv for commits %s' %
            ','.join(nonExisting))
        writer = CsvWriter(csvFile)
        for row in rows:
            if row[COMMITFIELD] not in nonExisting:
                writer.writerow(row)
    # remove all logs referencing obsolete commits
    logDir = os.path.expanduser(os.path.join('~', '.kajongg', 'log'))
    for dirName, _, fileNames in os.walk(logDir):
        for fileName in fileNames:
            if fileName not in KNOWNCOMMITS and fileName != 'current':
                os.remove(os.path.join(dirName, fileName))
        try:
            os.removedirs(dirName)
        except OSError:
            pass  # not yet empty

    Clone.removeObsolete()

def readGames(csvFile):
    """returns a dict holding a frozenset of games for each variant"""
    if not os.path.exists(csvFile):
        return
    allRowsGenerator = neutralize(Csv.reader(csvFile))
    if not allRowsGenerator:
        return
    # we want unique tuples so we can work with sets
    allRows = set(tuple(x) for x in allRowsGenerator)
    games = dict()
    # build set of rows for every ai
    for variant in set(tuple(x[:COMMITFIELD]) for x in allRows):
        games[variant] = frozenset(
            x for x in allRows if tuple(x[:COMMITFIELD]) == variant)
    return games

def hasDifferences(rows):
    """True if rows have unwanted differences"""
    return (len(set(tuple(list(x)[GAMEFIELD:]) for x in rows))
            > len(set(tuple(list(x)[:COMMITFIELD]) for x in rows)))

def firstDifference(rows):
    """reduce to two rows showing a difference"""
    result = rows
    last = rows[-1]
    while hasDifferences(result):
        last = result[-1]
        result = result[:-1]
    return list([result[-1], last])

def closerLook(gameId, gameIdRows):
    """print detailled info about one difference"""
    for ruleset in OPTIONS.rulesets:
        for intelligence in OPTIONS.allAis:
            shouldBeIdentical = list(x for x in gameIdRows if x[RULESETFIELD] == ruleset and x[AIFIELD] == intelligence)
            for commit in list(x[COMMITFIELD] for x in shouldBeIdentical):
                rows2 = list(x for x in shouldBeIdentical if x[COMMITFIELD] == commit)
                if hasDifferences(rows2):
                    first = firstDifference(rows2)
                    print('Game {} {} {} {} has differences between Python2 and Python3'.format(
                        gameId, ruleset, intelligence, commit))
            for py23 in '23':
                rows2 = list(x for x in shouldBeIdentical if x[PYTHON23FIELD] == py23)
                if hasDifferences(rows2):
                    first = firstDifference(rows2)
                    print('Game {} {} {} Python{} has differences between commits {} and {}'.format(
                        gameId, ruleset, intelligence, py23, first[0][COMMITFIELD], first[1][COMMITFIELD]))

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
        if hasDifferences(value):
            differing.append(key)
    if not differing:
        print('no games differ')
    else:
        print(
            'differing games (%d out of %d): %s' % (
                len(differing), len(allGameIds),
                ' '.join(sorted(differing, key=int))))
        # now look closer at one example. Differences may be caused by git commits or by py2/p3
        for gameId in sorted(differing):
            closerLook(gameId, allGameIds[gameId])

def evaluate(games):
    """evaluate games"""
    if not games:
        return
    for variant, rows in games.items():
        gameIds = set(x[GAMEFIELD] for x in rows)
        if len(gameIds) != len(set(tuple(list(x)[GAMEFIELD:]) for x in rows)):
            print(
                'ruleset "%s" AI "%s" has different rows for games' %
                (variant[0], variant[1]), end=' ')
            for game in sorted(gameIds, key=int):
                if len(set(tuple(x[GAMEFIELD:] for x in rows if x[GAMEFIELD] == game))) > 1:
                    print(game, end=' ')
            print()
            break
    printDifferingResults(games.values())
    print()
    print('the 3 robot players always use the Default AI')
    print()
    print('{ruleset:<25} {ai:<20} {games:>5}     {points:>4}                      human'.format(
        ruleset='Ruleset', ai='AI variant', games='games', points='points'))
    for variant, rows in games.items():
        ruleset, aiVariant = variant
        print('{ruleset:<25} {ai:<20} {rows:>5}  '.format(
            ruleset=ruleset[:25], ai=aiVariant[:20],
            rows=len(rows)), end=' ')
        for playerIdx in range(4):
            print(
                '{p:>8}'.format(
                    p=sum(
                        int(x[
                            PLAYERSFIELD + 1 + playerIdx * 4]) for x in rows)),
                end=' ')
        print()


def startingDir():
    """the path of the directory where kajonggtest has been started in"""
    return os.path.dirname(sys.argv[0])


def getJobs(jobs):
    """fill the queue"""
    try:
        while len(jobs) < OPTIONS.clients:
            jobs.append(next(OPTIONS.jobs))
    except StopIteration:
        pass
    return jobs


def doJobs():
    """now execute all jobs"""
    # pylint: disable=too-many-branches, too-many-locals, too-many-statements

    if not OPTIONS.git and OPTIONS.csv:
        if gitHead() in ('current', None):
            print(
                'Disabling CSV output: %s' %
                ('You have uncommitted changes' if gitHead() == 'current' else 'No git'))
            print()
            OPTIONS.csv = None

    try:
        jobs = []
        while getJobs(jobs):
            for checkJob in Server.allRunningJobs()[:]:
                checkJob.check()
            try:
                jobs[0].start()
                jobs = jobs[1:]
            except TooManyServers:
                time.sleep(3)
            except TooManyClients:
                time.sleep(3)
    except KeyboardInterrupt:
        Server.stopAll()
    except BaseException as exc:
        print(exc)
        raise exc
    finally:
        while True:
            running = Server.allRunningJobs()
            if not running:
                break
            for job in running:
                if not job.started:
                    if job.server:
                        job.server.jobs.remove(job)
                else:
                    job.check()
                    if job.process:
                        print('Waiting for   %s' % job)
                        job.process.wait()
            time.sleep(1)


def parse_options():
    """parse options"""
    parser = OptionParser()
    parser.add_option(
        '', '--gui', dest='gui', action='store_true',
        default=False, help='show graphical user interface')
    parser.add_option(
        '', '--ruleset', dest='rulesets', default='ALL',
        help='play like a robot using RULESET: comma separated list. If missing, test all rulesets',
        metavar='RULESET')
    parser.add_option(
        '', '--rounds', dest='rounds',
        help='play only # ROUNDS per game',
        metavar='ROUNDS')
    parser.add_option(
        '', '--ai', dest='aiVariants',
        default=None, help='use AI variants: comma separated list',
        metavar='AI')
    parser.add_option(
        '', '--log', dest='log', action='store_true',
        default=False, help='write detailled debug info to ~/.kajongg/log/game/ruleset/commit.'
                            ' This starts a separate server process per job, it sets --servers to --clients.')
    parser.add_option(
        '', '--game', dest='game',
        help='start first game with GAMEID, increment for following games.' +
        ' Without this, random values are used.',
        metavar='GAMEID', type=int, default=0)
    parser.add_option(
        '', '--count', dest='count',
        help='play COUNT games. Default is unlimited',
        metavar='COUNT', type=int, default=999999999)
    parser.add_option(
        '', '--playopen', dest='playopen', action='store_true',
        help='all robots play with visible concealed tiles', default=False)
    parser.add_option(
        '', '--clients', dest='clients',
        help='start a maximum of CLIENTS kajongg instances. Default is 2',
        metavar='CLIENTS', type=int, default=1)
    parser.add_option(
        '', '--servers', dest='servers',
        help='start a maximum of SERVERS kajonggserver instances. Default is 1',
        metavar='SERVERS', type=int, default=1)
    parser.add_option(
        '', '--git', dest='git',
        help='check all commits: either a comma separated list or a range from..until')
    parser.add_option(
        '', '--debug', dest='debug',
        help=Debug.help())

    return parser.parse_args()


def improve_options():
    """add sensible defaults"""
    # pylint: disable=too-many-branches,too-many-statements
    if OPTIONS.servers < 1:
        OPTIONS.servers = 1

    cmdPath = os.path.join(startingDir(), 'kajongg.py')
    cmd = ['python3', cmdPath, '--rulesets']
    OPTIONS.knownRulesets = list(popenReadlines(cmd))
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
                exactMatch = list(
                    x for x in OPTIONS.knownRulesets if ruleset == x)
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
            if '^' not in OPTIONS.git:
                OPTIONS.git = OPTIONS.git.replace('..', '^..')
            commits = subprocess.check_output(
                'git log --pretty=%h {range}'.format(
                    range=OPTIONS.git).split()).decode()
            OPTIONS.git = list(reversed(list(x.strip()
                                             for x in commits.split('\n') if x.strip())))
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
    if gitHead() not in ('current', None) and not OPTIONS.log:
        OPTIONS.debug.append('git')
    if not OPTIONS.aiVariants:
        OPTIONS.aiVariants = 'Default'
    OPTIONS.allAis = OPTIONS.aiVariants.split(',')
    if OPTIONS.count:
        print('rulesets:', ', '.join(OPTIONS.rulesets))
        _ = ' '.join(OPTIONS.allAis)
        if _ != 'Default':
            print('AIs:', _)
    if OPTIONS.git:
        print('commits:', ' '.join(OPTIONS.git))
        # since we order jobs by game, commit we want one permanent server per
        # commit
    OPTIONS.jobs = allJobs()
    OPTIONS.games = allGames()
    OPTIONS.jobCount = 0
    OPTIONS.usePort = os.name == 'nt'


def allGames():
    """a generator returning game ids"""
    while True:
        if OPTIONS.game:
            result = OPTIONS.game
            OPTIONS.game += 1
        else:
            result = int(random.random() * 10 ** 9)
        yield result


def allJobs():
    """a generator returning Job instances"""
    for game in OPTIONS.games:
        for commitId in OPTIONS.git or ['current']:
            for ruleset in OPTIONS.rulesets:
                for aiVariant in OPTIONS.allAis:
                    OPTIONS.jobCount += 1
                    if OPTIONS.jobCount > OPTIONS.count:
                        raise StopIteration
                    yield Job(3, ruleset, aiVariant, commitId, game)

def main():
    """parse options, play, evaluate results"""
    global OPTIONS  # pylint: disable=global-statement

    # we want only english in the logs because i18n and friends
    # behave differently in kde and kde
    os.environ['LANG'] = 'en_US.UTF-8'
    (OPTIONS, args) = parse_options()
    OPTIONS.csv = os.path.expanduser(
        os.path.join('~', '.kajongg', 'kajongg.csv'))
    if not os.path.exists(os.path.dirname(OPTIONS.csv)):
        os.makedirs(os.path.dirname(OPTIONS.csv))

    removeInvalidCommits(OPTIONS.csv)

    improve_options()

    evaluate(readGames(OPTIONS.csv))

    errorMessage = Debug.setOptions(','.join(OPTIONS.debug))
    if errorMessage:
        print(errorMessage)
        sys.exit(2)

    if args and ''.join(args):
        print('unrecognized arguments:', ' '.join(args))
        sys.exit(2)

    print()

    if OPTIONS.count:
        doJobs()
        if OPTIONS.csv:
            evaluate(readGames(OPTIONS.csv))


def cleanup(sig, dummyFrame):
    """at program end"""
    Server.stopAll()
    sys.exit(sig)

# is one server for two clients.
if __name__ == '__main__':
    signal.signal(signal.SIGABRT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    if os.name != 'nt':
        signal.signal(signal.SIGHUP, cleanup)
        signal.signal(signal.SIGQUIT, cleanup)

    main()
    gc.collect()
    checkMemory()
