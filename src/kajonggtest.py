#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Copyright (C) 2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

import signal
import os
import sys
import subprocess
import random
import shutil
import time
import gc

import argparse
from locale import getpreferredencoding

from typing import List, Set, Optional, Any, Generator, Iterable, Union, TYPE_CHECKING, Tuple, cast

from common import Debug, ReprMixin, cacheDir
from util import removeIfExists, gitHead, checkMemory, popenReadlines
from kajcsv import Csv, CsvRow, CsvWriter

if TYPE_CHECKING:
    from io import FileIO


signal.signal(signal.SIGINT, signal.SIG_DFL)


OPTIONS: Any

class Clone:

    """make a temp directory for commitId"""

    def __init__(self, commitId:str) ->None:
        self.commitId = commitId
        if commitId != 'current':
            tmpdir = os.path.expanduser(os.path.join(cacheDir(), commitId))
            if not os.path.exists(tmpdir):
                with subprocess.Popen(
                    f'git clone --shared --no-checkout -q .. {tmpdir}'.split()) as _:
                    _.wait()
                with subprocess.Popen(
                    f'git checkout -q {commitId}'.split(), cwd=tmpdir) as _:
                    _.wait()

    def sourceDirectory(self) ->str:
        """the source directory for this git commit"""
        if self.commitId == 'current':
            tmpdir = os.path.abspath('..')
            result = os.path.join(tmpdir, 'src')
        else:
            result = os.path.join(cacheDir(), self.commitId, 'src')
        assert os.path.exists(result), f'{result} does not exist'
        return result

    @classmethod
    def removeObsolete(cls, knownCommits:Set) ->None:
        """remove all clones for obsolete commits"""
        for commitDir in os.listdir(cacheDir()):
            if not any(x.startswith(commitDir) for x in knownCommits):
                removeDir = os.path.join(cacheDir(), commitDir)
                shutil.rmtree(removeDir)


class TooManyClients(UserWarning):

    """we would surpass options.clients"""


class TooManyServers(UserWarning):

    """we would surpass options.servers"""


class Server(ReprMixin):

    """represents a kajongg server instance. Called when we want to start a job."""
    servers:List['Server'] = []
    count = 0

    def __new__(cls, job:'Job') ->'Server':
        """can we reuse an existing server?"""
        running = Server.allRunningJobs()
        if len(running) >= OPTIONS.clients:
            raise TooManyClients
        maxClientsPerServer = OPTIONS.clients / OPTIONS.servers
        matchingServers = [
            x for x in cls.servers
            if x.commitId == job.commitId
            and x.pythonVersion == job.pythonVersion
            and len(x.jobs) < maxClientsPerServer]
        if matchingServers:
            result = sorted(matchingServers, key=lambda x: len(x.jobs))[0]
        else:
            if len(cls.servers) >= OPTIONS.servers:
                # maybe we can kill a server without jobs?
                for server in cls.servers:
                    if not server.jobs:
                        server.stop()
                        break  # we only need to stop one server
                else:
                    # no server without jobs found
                    raise TooManyServers
            result = object.__new__(cls)
            cls.servers.append(result)
        return result

    def __init__(self, job:'Job') ->None:
        if not hasattr(self, 'jobs'):
            self.jobs = []
            self.process:Optional[subprocess.Popen] = None
            self.socketName:Optional[str] = None
            self.portNumber:Optional[int] = None
            self.commitId:str = job.commitId
            self.pythonVersion:str = job.pythonVersion
            self.clone = Clone(job.commitId)
            self.start(job)
        else:
            self.jobs.append(job)

    @classmethod
    def allRunningJobs(cls) ->List['Job']:
        """a list of all jobs on all servers"""
        return sum((x.jobs for x in cls.servers), [])

    def start(self, job:'Job') ->None:
        """start this server"""
        job.server = self
        assert self.process is None, 'Server.start already has a process'
        self.jobs.append(job)
        assert self.commitId == job.commitId, f'Server.commitId {self.commitId} != Job.commitId {job.commitId}'
        cmd = [os.path.join(
            job.srcDir(),
            'kajonggserver.py')]
        cmd.insert(0, f'python{self.pythonVersion}')
        if OPTIONS.usePort:
            self.portNumber = random.randrange(1025, 65000)
            cmd.append(f'--port={self.portNumber}')
        else:
            Server.count += 1
            self.socketName = os.path.expanduser(
                os.path.join('~', '.kajongg',
                             f'sock{self.commitId}.py{self.pythonVersion}.{Server.count}'))
            cmd.append(f'--socket={self.socketName}')
        if OPTIONS.debug:
            cmd.append(f"--debug={','.join(OPTIONS.debug)}")
        if OPTIONS.log:
            self.process = subprocess.Popen(
                cmd, cwd=job.srcDir(),
                stdout=job.logFile, stderr=job.logFile)
        else:
            # reuse this server (otherwise it stops by itself)
            cmd.append('--continue')
            self.process = subprocess.Popen(cmd, cwd=job.srcDir())  # pylint:disable=consider-using-with
        print(f'{self} started')

    def stop(self, job:Optional['Job']=None) ->None:
        """maybe stop the server"""
        if self not in self.servers:
            # already stopped
            return
        if job:
            self.jobs.remove(job)
        if not self.jobs:
            self.servers.remove(self)
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait()
                except OSError:
                    pass
                print(f'{self} killed')
            if self.socketName:
                removeIfExists(self.socketName)

    @classmethod
    def stopAll(cls) ->None:
        """stop all servers even if clients are still there"""
        for server in cls.servers:
            for job in server.jobs[:]:
                server.stop(job)
            assert not server.jobs, f'stopAll expects no server jobs but found {server.jobs}'
            server.stop()

    def __str__(self) ->str:
        return 'Server {} Python{}{} {}'.format( # pylint:disable=consider-using-f-string
            self.commitId,
            self.pythonVersion,
            ' pid={}'.format(self.process.pid) if Debug.process and self.process else '', # pylint:disable=consider-using-f-string
            ' port={}'.format(self.portNumber) if self.portNumber else ' socket={}'.format(self.socketName)) # pylint:disable=consider-using-f-string


class Job(ReprMixin):

    """a simple container"""

    def __init__(self, pythonVersion:str, ruleset:str, aiVariant:str, commitId:str, game:str) ->None:
        self.pythonVersion = pythonVersion
        self.ruleset = ruleset
        self.aiVariant = aiVariant
        self.commitId = commitId
        self.game = game
        self.__logFile:'FileIO'
        self.logFileName:str
        self.process:Optional[subprocess.Popen] = None
        self.server:Server
        self.started = False

    def srcDir(self) ->str:
        """the path of the directory where the particular test is running"""
        assert self.server, f'Job {self} has no server'
        assert self.server.clone, f'Job {self} has no server.clone'
        return self.server.clone.sourceDirectory()

    def __startProcess(self, cmd:List[str]) ->None:
        """call Popen"""
        if OPTIONS.log:
            self.process = subprocess.Popen(
                cmd, cwd=self.srcDir(),
                stdout=self.logFile, stderr=self.logFile)
        else:
            self.process = subprocess.Popen(cmd, cwd=self.srcDir())  # pylint:disable=consider-using-with
        print(f'       {self} started')

    def start(self) ->None:
        """start this job"""
        self.server = Server(self)
        # never login to the same server twice at the
        # same time with the same player name
        player = self.server.jobs.index(self) + 1
        cmd = [os.path.join(self.srcDir(), 'kajongg.py'),
               f'--game={self.game}',
               f'--player=Tüster {player}',
               f'--ruleset={self.ruleset}']
        if self.server.socketName:
            cmd.append(f'--socket={self.server.socketName}')
        if self.server.portNumber:
            cmd.append(f'--port={self.server.portNumber}')
        cmd.insert(0, f'python{self.pythonVersion}')
        if self.aiVariant != 'DefaultAI':
            cmd.append(f'--ai={self.aiVariant}')
        if OPTIONS.csv:
            cmd.append(f'--csv={OPTIONS.csv}')
        if OPTIONS.gui:
            cmd.append('--demo')
        else:
            cmd.append('--nogui')
        if OPTIONS.playopen:
            cmd.append('--playopen')
        if OPTIONS.debug:
            cmd.append(f"--debug={','.join(OPTIONS.debug)}")
        self.__startProcess(cmd)
        self.started = True

    def check(self, silent:bool=False) ->None:
        """if done, cleanup"""
        if not self.started or not self.process:
            return
        result:Union[int, str, None] = self.process.poll()
        if result is not None:
            assert isinstance(result, int)
            self.process = None
            if not silent:
                if result < 0:
                    result = signal.Signals(-result).name
                if result:
                    result = f' with return {result}'
                else:
                    result = ''
                print(f'       {self} done{result}')
            self.server.jobs.remove(self)

    @property
    def logFile(self) ->'FileIO':
        """open if needed"""
        if not hasattr(self, '__logFile'):
            logDir = os.path.expanduser(
                os.path.join('~', '.kajongg', 'log', str(self.game),
                             self.ruleset, self.aiVariant, str(self.pythonVersion)))
            if not os.path.exists(logDir):
                os.makedirs(logDir)
            logFileName = self.commitId
            self.logFileName = os.path.join(logDir, logFileName)
            self.__logFile = open(self.logFileName, 'ab', buffering=0)  # pylint:disable=consider-using-with
        return self.__logFile

    def shortRulesetName(self) ->str:
        """strip leading chars if they are identical for all rulesets"""
        names = OPTIONS.knownRulesets
        for prefix in range(100):
            if sum(x.startswith(self.ruleset[:prefix]) for x in names) == 1:
                return self.ruleset[prefix - 1:]
        return self.ruleset

    def __str__(self) ->str:
        pid = f'pid={self.process.pid}' if self.process and Debug.process else ''
        game = f'game={self.game}'
        ruleset = self.shortRulesetName()
        aiName = f'AI={self.aiVariant}' if self.aiVariant != 'DefaultAI' else ''
        return ' '.join([
            self.commitId, f'Python{self.pythonVersion}', pid, game, ruleset, aiName]).replace('  ', ' ')




def cleanup_data(csv:'CSV') ->None:
    """remove all data referencing obsolete commits"""
    logDir = os.path.expanduser(os.path.join('~', '.kajongg', 'log'))
    knownCommits = csv.commits()
    for dirName, _, fileNames in os.walk(logDir):
        for fileName in fileNames:
            if fileName not in knownCommits and fileName != 'current':
                os.remove(os.path.join(dirName, fileName))
        try:
            os.removedirs(dirName)
        except OSError:
            pass  # not yet empty
    Clone.removeObsolete(knownCommits)

def pairs(data:List[CsvRow]) ->Generator[Tuple[CsvRow, CsvRow], None, None]:
    """return all consecutive pairs"""
    prev = None
    for _ in data:
        if prev:
            yield prev, _
        prev = _


class CSV(ReprMixin):
    """represent kajongg.csv"""

    knownCommits : Set[str] = set()

    def __init__(self) ->None:
        self.findKnownCommits()
        self.rows:List[CsvRow] = []
        if os.path.exists(OPTIONS.csv):
            self.rows = list(sorted({CsvRow(x) for x in Csv.reader(OPTIONS.csv)}))
        self.removeInvalidCommits()

    def neutralize(self) ->None:
        """remove things we do not want to compare"""
        for row in self.rows:
            row.neutralize()

    def commits(self) ->Set[str]:
        """return set of all our commit ids"""
        # TODO: sorted by date
        return {x.commit for x in self.rows}

    def games(self) ->List[str]:
        """return a sorted unique list of all games"""
        return sorted({x.game for x in self.rows})

    @classmethod
    def findKnownCommits(cls) ->None:
        """find known commits"""
        if not cls.knownCommits:
            cls.knownCommits = set()
            for branch in subprocess.check_output(b'git branch'.split()).decode().split('\n'):
                if 'detached' not in branch and 'no branch' not in branch:
                    cls.knownCommits |= set(subprocess.check_output(
                        f'git log --max-count=800 --pretty=%H {branch[2:]} --abbrev=10'.split()).decode().split('\n'))

    @classmethod
    def onlyExistingCommits(cls, commits:Iterable[str]) ->Set[str]:
        """return a set with only  existing commits"""
        result = set()
        for commit in commits:
            if any(x.startswith(commit) for x in cls.knownCommits):
                result.add(commit)
        return result

    def removeInvalidCommits(self) ->None:
        """remove rows with invalid git commit ids"""
        csvCommits = {x.commit for x in self.rows}
        csvCommits = {
            x for x in csvCommits if set(
                x) <= set(
                    '0123456789abcdef') and len(
                        x) >= 7}
        nonExisting = csvCommits - self.onlyExistingCommits(set(x.commit for x in self.rows))
        if nonExisting:
            print(
                f"removing rows from kajongg.csv for commits {','.join(nonExisting)}")
            self.rows = [x for x in self.rows if x.commit not in nonExisting]
            self.write()

    def write(self) ->None:
        """write new csv file"""
        writer = CsvWriter(OPTIONS.csv)
        for row in self.rows:
            writer.writerow(row)
        del writer

    def evaluate(self) ->None:
        """evaluate the data. Show differences as helpful as possible"""
        found_difference = False
        for ruleset, aiVariant, game in {(x.ruleset, x.aiVariant, x.game) for x in self.rows}:
            rows = list(reversed(sorted(
                x for x in self.rows
                if ruleset == x.ruleset and aiVariant == x.aiVariant and game == x.game)))
            for fixedField in (CsvRow.Fields.PY_VERSION, CsvRow.Fields.COMMIT):
                for fixedValue in set(x[fixedField] for x in rows):
                    checkRows = [x for x in rows if x[fixedField] == fixedValue]
                    for warned in self.compareRows(checkRows):
                        found_difference = True
                        rows.remove(warned)
            found_difference |= len(self.compareRows(rows)) > 0
            self.compareRows(rows)
        if not found_difference:
            print(f'found no differences in {OPTIONS.csv}')

    @staticmethod
    def compareRows(rows:List[CsvRow]) ->List[CsvRow]:
        """in absence of differences, there should be only one row.
        return a list of rows which appeared in warnings"""
        if not rows:
            return []
        msgHeader = None
        result:List[CsvRow] = []
        ruleset = rows[0].ruleset
        aiVariant = rows[0].aiVariant
        game = rows[0].game
        differences:List[Tuple[CsvRow, CsvRow, Tuple[str, str]]] = []
        for pair in pairs(rows):
            causes = pair[1].differs_for(pair[0])
            if causes:
                triple = cast(Tuple[CsvRow, CsvRow, Tuple[str, str]], tuple([pair[0], pair[1], causes]))
                differences.append(triple)
        for difference in sorted(differences, key=lambda x: len(x[2])):
            if not set(difference[:2]) & set(result):
                if msgHeader is None:
                    msgHeader = f'looking at game={game} ruleset={ruleset} AI={aiVariant}'
                    print(msgHeader)
                print('   {} {}'.format(*difference[2])) # pylint:disable=consider-using-f-string
                result.extend(difference[:2])
        return result


def startingDir() ->str:
    """the path of the directory where kajonggtest has been started in"""
    return os.path.dirname(sys.argv[0])


def getJobs(jobs:List[Job]) ->List[Job]:
    """fill the queue"""
    try:
        while len(jobs) < OPTIONS.clients:
            jobs.append(next(OPTIONS.jobs))
    except StopIteration:
        pass
    return jobs


def doJobs() ->None:
    """now execute all jobs"""
    # pylint: disable=too-many-branches

    if not OPTIONS.git and OPTIONS.csv:
        if gitHead() in ('current', None):
            print(
                f"Disabling CSV output: {'You have uncommitted changes' if gitHead() == 'current' else 'No git'}")
            print()
            OPTIONS.csv = None

    try:
        jobs:List[Job] = []
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
                        print(f'Waiting for   {job}')
                        job.process.wait()
            time.sleep(1)


def parse_options() ->argparse.Namespace:
    """parse options"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--gui', dest='gui', action='store_true',
        default=False, help='show graphical user interface')
    parser.add_argument(
        '--ruleset', dest='rulesets', default='ALL',
        help='play like a robot using RULESET: comma separated list. If missing, test all rulesets',
        metavar='RULESET')
    parser.add_argument(
        '--ai', dest='aiVariants',
        default=None, help='use AI variants: comma separated list',
        metavar='AI')
    parser.add_argument(
        '--python', dest='pyVersions',
        default=None, help='use python versions: comma separated list',
        metavar='PY_VERSION')
    parser.add_argument(
        '--log', dest='log', action='store_true',
        default=False, help='write detailled debug info to ~/.kajongg/log/game/ruleset/commit.'
                            ' This starts a separate server process per job, it sets --servers to --clients.')
    parser.add_argument(
        '--game', dest='game',
        help='start first game with GAMEID, increment for following games.' +
        ' Without this, random values are used.',
        metavar='GAMEID', type=int, default=0)
    parser.add_argument(
        '--count', dest='count',
        help='play COUNT games. Default is unlimited',
        metavar='COUNT', type=int, default=999999999)
    parser.add_argument(
        '--playopen', dest='playopen', action='store_true',
        help='all robots play with visible concealed tiles', default=False)
    parser.add_argument(
        '--clients', dest='clients',
        help='start a maximum of CLIENTS kajongg instances. Default is 2',
        metavar='CLIENTS', type=int, default=2)
    parser.add_argument(
        '--servers', dest='servers',
        help='start a maximum of SERVERS kajonggserver instances. Default is 1',
        metavar='SERVERS', type=int, default=1)
    parser.add_argument(
        '--git', dest='git',
        help='check all commits: either a comma separated list or a range from..until')
    parser.add_argument(
        '--debug', dest='debug',
        help=Debug.help())
    return parser.parse_args()


def improve_options() ->None:
    """add sensible defaults"""
    # pylint: disable=too-many-branches,too-many-statements
    OPTIONS.servers = max(OPTIONS.servers, 1)

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
            matches = [x for x in OPTIONS.knownRulesets if ruleset in x]
            if not matches:
                print('ruleset', ruleset, 'is not known', end=' ')
                wrong = True
            elif len(matches) > 1:
                exactMatch = [x for x in OPTIONS.knownRulesets if ruleset == x]
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
                f'git log --grep _SILENT --invert-grep --pretty=%h {OPTIONS.git} --abbrev=10'.split()).decode()
            _ = list(x.strip() for x in commits.split('\n') if x.strip())
            OPTIONS.git = list(reversed(_))
        else:
            OPTIONS.git = CSV.onlyExistingCommits(OPTIONS.git.split(','))
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
        OPTIONS.aiVariants = 'DefaultAI'
    if OPTIONS.pyVersions:
        OPTIONS.pyVersions = OPTIONS.pyVersions.split(',')
    else:
        OPTIONS.pyVersions = ['3']
    OPTIONS.allAis = OPTIONS.aiVariants.split(',')
    if OPTIONS.count:
        print('rulesets:', ', '.join(OPTIONS.rulesets))
        _ = ' '.join(OPTIONS.allAis)
        if _ != 'DefaultAI':
            print('AIs:', _)
    if OPTIONS.git:
        print('commits:', ' '.join(OPTIONS.git))
        # since we order jobs by game, commit we want one permanent server per
        # commit
    OPTIONS.jobs = allJobs()
    OPTIONS.games = allGames()
    OPTIONS.jobCount = 0
    OPTIONS.usePort = sys.platform == 'win32'


def allGames() ->Generator[str, None, None]:
    """a generator returning game ids"""
    while True:
        if OPTIONS.game:
            result = OPTIONS.game
            OPTIONS.game += 1
        else:
            result = int(random.random() * 10 ** 9)
        yield result


def allJobs() ->Generator[Job, None, None]:
    """a generator returning Job instances"""
    # pylint: disable=too-many-nested-blocks
    for game in OPTIONS.games:
        for commitId in OPTIONS.git or ['current']:
            for ruleset in OPTIONS.rulesets:
                for aiVariant in OPTIONS.allAis:
                    for pyVersion in OPTIONS.pyVersions:
                        OPTIONS.jobCount += 1
                        if OPTIONS.jobCount > OPTIONS.count:
                            return
                        yield Job(pyVersion, ruleset, aiVariant, commitId, game)

def main() ->None:
    """parse options, play, evaluate results"""
    global OPTIONS  # pylint: disable=global-statement

    locale_encoding = getpreferredencoding()
    if locale_encoding.lower() != 'utf-8':
        print(f'we need default encoding utf-8 but have {locale_encoding}')
        sys.exit(2)

    # we want only english in the logs because i18n and friends
    # behave differently in kde and kde
    os.environ['LANG'] = 'en_US.UTF-8'
    OPTIONS = parse_options()
    OPTIONS.csv = os.path.expanduser(
        os.path.join('~', '.kajongg', 'kajongg.csv'))
    if not os.path.exists(os.path.dirname(OPTIONS.csv)):
        os.makedirs(os.path.dirname(OPTIONS.csv))

    csv = CSV()

    improve_options()

    csv.evaluate()
    cleanup_data(csv)

    errorMessage = Debug.setOptions(','.join(OPTIONS.debug))
    if errorMessage:
        print(errorMessage)
        sys.exit(2)

    print()

    if OPTIONS.count:
        doJobs()
        if OPTIONS.csv:
            CSV().evaluate()

def cleanup(sig: Any, unusedFrame: Any) ->None:
    """at program end"""
    Server.stopAll()
    sys.exit(sig)

# is one server for two clients.
if __name__ == '__main__':
    signal.signal(signal.SIGABRT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    if sys.platform != 'win32':
        signal.signal(signal.SIGHUP, cleanup)
        signal.signal(signal.SIGQUIT, cleanup)

    main()
    gc.collect()
    checkMemory()
