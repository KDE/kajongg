# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2014 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

# util must not import from log because util should not
# depend on kde.py

from __future__ import print_function
import traceback, os, datetime
import time
import subprocess

from locale import getpreferredencoding
from sys import stdout
try:
    STDOUTENCODING = stdout.encoding
except AttributeError:
    STDOUTENCODING = None
if not STDOUTENCODING:
    STDOUTENCODING = getpreferredencoding()

# util must not depend on kde

from common import Debug, isPython3

def stack(msg, limit=6):
    """returns a list of lines with msg as prefix"""
    result = []
    for idx, values in enumerate(traceback.extract_stack(limit=limit+2)[:-2]):
        fileName, line, function, txt = values
        result.append('%2d: %s %s/%d %s: %s' % (idx, msg, os.path.splitext(os.path.basename(fileName))[0],
                                line, function, txt))
    return result

def callers(count=1, exclude=None):
    """returns the name of the calling method"""
    stck = traceback.extract_stack(limit=30)
    excluding = list(exclude) or []
    excluding.extend(['<genexpr>', '__call__', 'run', '<module>', 'runTests'])
    names = list(x[2] for x in stck[:-2] if x[2] not in excluding)
    result = '.'.join(names[-count-2:])
    return result

def elapsedSince(since):
    """returns seconds since since"""
    delta = datetime.datetime.now() - since
    return float(delta.microseconds + (delta.seconds + delta.days * 24 * 3600) * 10**6) / 10**6

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

import gc

def _getr(slist, olist, seen):
    """Recursively expand slist's objects into olist, using seen to track
    already processed objects."""
    for elment in slist:
        if id(elment) in seen:
            continue
        seen[id(elment)] = None
        olist.append(elment)
        tlist = gc.get_referents(elment)
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

def kprint(*args, **kwargs):
    """a wrapper around print, always encoding unicode to something sensible"""
    newArgs = []
    for arg in args:
        try:
            arg = arg.decode('utf-8')
        except BaseException:
            arg = repr(arg)
        arg = arg.encode(STDOUTENCODING, 'ignore')
        newArgs.append(arg)
    # we need * magic: pylint: disable=star-args
    try:
        print(*newArgs, sep=kwargs.get('sep', ' '), end=kwargs.get('end', '\n'), file=kwargs.get('file'))
    except IOError as exception:
        # very big konsole, busy system: sometimes Python says
        # resource temporarily not available
        time.sleep(0.1)
        print(exception)
        print(*newArgs, sep=kwargs.get('sep', ' '), end=kwargs.get('end', '\n'), file=kwargs.get('file'))

class Duration(object):
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
                msg = '%s took %d.%02d seconds' % (self.name, diff.seconds, diff.microseconds)
                if self.bug:
                    raise UserWarning(msg)
                else:
                    print(msg)

def checkMemory():
    """as the name says"""
    #pylint: disable=too-many-branches
    if not Debug.gc:
        return
    gc.set_threshold(0)
    gc.set_debug(gc.DEBUG_LEAK)
    gc.enable()
    print('collecting {{{')
    gc.collect()        # we want to eliminate all output
    print('}}} done')

    # code like this may help to find specific things
    if True:
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
                    print('referrer of %s/%s is: id=%s type=%s %s' % (
                        type(obj), obj, id(referrer), type(referrer), referrer))
    print('unreachable:%s' % gc.collect())
    gc.set_debug(0)

def gitHead():
    """the current git commit. 'current' if there are uncommitted changes and None if no .git found"""
    if not os.path.exists(os.path.join('..', '.git')):
        return None
    subprocess.Popen(['git', 'update-index', '-q', '--refresh'])
    _ = subprocess.Popen(['git', 'diff-index', '--name-only', 'HEAD', '--'], stdout=subprocess.PIPE).communicate()[0]
    uncommitted = list(x.strip() for x in _.split('\n') if len(x.strip()))
    if uncommitted:
        return 'current'
    result = subprocess.Popen(['git', 'log', '-1', '--format="%h"'],
            stdout=subprocess.PIPE).communicate()[0]
    return result.split('\n')[0].replace('"', '')[:15]

def xToUtf8(msg, args=None):
    """makes sure msg and all args are utf-8"""
    if isPython3:
        if args is not None:
            return msg, args
        else:
            return msg
    if isinstance(msg, unicode):
        msg = msg.encode('utf-8')
    elif not isinstance(msg, str):
        msg = unicode(msg).encode('utf-8')
    if args is not None:
        args = list(args[:])
        for idx, arg in enumerate(args):
            if isinstance(arg, unicode):
                args[idx] = arg.encode('utf-8')
            elif not isinstance(arg, str):
                args[idx] = unicode(arg).encode('utf-8')
        return msg, args
    else:
        return msg
