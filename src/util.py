# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

# util must not import from log because util should not
# depend on kde.py

from __future__ import print_function
import traceback
import os
import datetime
import subprocess
import gc
import csv


from locale import getpreferredencoding
from sys import stdout

from common import Debug

try:
    STDOUTENCODING = stdout.encoding
except AttributeError:
    STDOUTENCODING = None
if not STDOUTENCODING:
    STDOUTENCODING = getpreferredencoding()


def stack(msg, limit=6):
    """returns a list of lines with msg as prefix"""
    result = []
    for idx, values in enumerate(
            traceback.extract_stack(limit=limit + 2)[:-2]):
        fileName, line, function, txt = values
        result.append(
            '%2d: %s %s/%d %s: %s' %
            (idx, msg, os.path.splitext(
                os.path.basename(fileName))[0],
             line, function, txt))
    return result


def callers(count=5, exclude=None):
    """returns the name of the calling method"""
    stck = traceback.extract_stack(limit=30)
    excluding = list(exclude) if exclude else []
    excluding.extend(['<genexpr>', '__call__', 'run', '<module>', 'runTests'])
    excluding.extend(['_startRunCallbacks', '_runCallbacks', 'remote_move', 'exec_move'])
    excluding.extend(['proto_message', '_recvMessage', 'remoteMessageReceived'])
    excluding.extend(['clientAction', 'myAction', 'expressionReceived'])
    excluding.extend(['_read', 'callWithLogger'])
    excluding.extend(['callbackIfDone', 'callback', '__gotAnswer'])
    excluding.extend(['callExpressionReceived', 'proto_answer'])
    excluding.extend(['_dataReceived', 'dataReceived', 'gotItem'])
    excluding.extend(['callWithContext', '_doReadOrWrite', 'doRead'])
    excluding.extend(['callers', 'debug', 'logMessage', 'logDebug'])
    _ = list(([x[2] for x in stck if x[2] not in excluding]))
    names = reversed(_[-count:])
    result = '.'.join(names)
    return '[{}]'.format(result)


def elapsedSince(since):
    """returns seconds since since"""
    delta = datetime.datetime.now() - since
    return float(
        delta.microseconds
        + (delta.seconds + delta.days * 24 * 3600) * 10 ** 6) / 10 ** 6


def which(program):
    """returns the full path for the binary or None"""
    for path in os.environ['PATH'].split(os.pathsep):
        fullName = os.path.join(path, program)
        if os.path.exists(fullName):
            return fullName


def removeIfExists(filename):
    """remove file if it exists. Returns True if it existed"""
    exists = os.path.exists(filename)
    if exists:
        os.remove(filename)
    return exists


def uniqueList(seq):
    """makes list content unique, keeping only the first occurrence"""
    seen = set()
    seen_add = seen.add
    return [x for x in seq if x not in seen and not seen_add(x)]


def _getr(slist, olist, seen):
    """Recursively expand slist's objects into olist, using seen to track
    already processed objects."""
    for element in slist:
        if id(element) in seen:
            continue
        seen[id(element)] = None
        olist.append(element)
        tlist = gc.get_referents(element)
        if tlist:
            _getr(tlist, olist, seen)

# The public function.


def get_all_objects():
    """Return a list of all live Python objects, not including the
    list itself. May use this in Duration for showing where
    objects are leaking"""
    gc.collect()
    gcl = gc.get_objects()
    olist = []
    seen = {}
    # Just in case:
    seen[id(gcl)] = None
    seen[id(olist)] = None
    seen[id(seen)] = None
    # _getr does the real work.
    _getr(gcl, olist, seen)
    return olist


class Duration:

    """a helper class for checking code execution duration"""

    def __init__(self, name, threshold=None, bug=False):
        """name describes where in the source we are checking
        threshold in seconds: do not warn below
        if bug is True, throw an exception if threshold is exceeded"""
        self.name = name
        self.threshold = threshold or 1.0
        self.bug = bug
        self.__start = datetime.datetime.now()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trback):
        """now check time passed"""
        if not Debug.neutral:
            diff = datetime.datetime.now() - self.__start
            if diff > datetime.timedelta(seconds=self.threshold):
                msg = '%s took %d.%02d seconds' % (
                    self.name,
                    diff.seconds,
                    diff.microseconds)
                if self.bug:
                    raise UserWarning(msg)
                else:
                    print(msg)


def checkMemory():
    """as the name says"""
    # pylint: disable=too-many-branches
    if not Debug.gc:
        return
    gc.set_threshold(0)
    gc.set_debug(gc.DEBUG_LEAK)
    gc.enable()
    print('collecting {{{')
    gc.collect()        # we want to eliminate all output
    print('}}} done')

    # code like this may help to find specific things
    if True: # pylint: disable=using-constant-test
        interesting = ('Client', 'Player', 'Game')
        for obj in gc.garbage:
            if hasattr(obj, 'cell_contents'):
                obj = obj.cell_contents
            if not any(x in repr(obj) for x in interesting):
                continue
            for referrer in gc.get_referrers(obj):
                if referrer is gc.garbage:
                    continue
                if hasattr(referrer, 'cell_contents'):
                    referrer = referrer.cell_contents
                if referrer.__class__.__name__ in interesting:
                    for referent in gc.get_referents(referrer):
                        print('%s refers to %s' % (referrer, referent))
                else:
                    print('referrer of %s/%s is: id=%s type=%s %s' %
                          (type(obj), obj, id(referrer),
                           type(referrer), referrer))
    print('unreachable:%s' % gc.collect())
    gc.set_debug(0)


def gitHead():
    """the current git commit. 'current' if there are uncommitted changes
    and None if no .git found"""
    if not os.path.exists(os.path.join('..', '.git')):
        return None
    subprocess.Popen(['git', 'update-index', '-q', '--refresh'])
    uncommitted = list(popenReadlines('git diff-index --name-only HEAD --'))
    return 'current' if uncommitted else next(popenReadlines('git log -1 --format=%h'))


class CsvWriter:
    """hide differences between Python 2 and 3"""
    def __init__(self, filename, mode='w'):
        self.outfile = open(filename, mode)
        self.__writer = csv.writer(self.outfile, delimiter=Csv.delimiter)

    def writerow(self, row):
        """write one row"""
        self.__writer.writerow([str(cell) for cell in row])

    def __del__(self):
        """clean up"""
        self.outfile.close()

class Csv:
    """hide differences between Python 2 and 3"""

    delimiter = ';'

    @staticmethod
    def reader(filename):
        """returns a generator for decoded strings"""
        return csv.reader(open(filename, 'r', encoding='utf-8'), delimiter=Csv.delimiter)

def popenReadlines(args):
    """runs a subprocess and returns stdout as a list of unicode encodes lines"""
    if isinstance(args, str):
        args = args.split()
    my_env = os.environ.copy()
    my_env["LANG"] = "C"
    result = subprocess.Popen(args, universal_newlines=True, stdout=subprocess.PIPE, env=my_env).communicate()[0]
    return (x.strip() for x in result.split('\n') if x.strip())
