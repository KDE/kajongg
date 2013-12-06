# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from collections import defaultdict
import datetime

import sip
import traceback
import platform

# pylint: disable=invalid-name
if platform.python_version_tuple()[0] == '3':
    # pylint: disable=redefined-builtin
    unicode = str
    basestring = str
    isPython3 = True
else:
    # pylint: disable=redefined-builtin
    unicode = unicode
    basestring = basestring
    isPython3 = False

WINDS = 'ESWN'
LIGHTSOURCES = ['NE', 'NW', 'SW', 'SE']

def isAlive(qobj):
    """is the underlying C++ object still valid?
    This function is taken from the book
    "Rapid GUI Programming with Python and Qt"
    by Mark Summerfield."""
    if qobj is None:
        return False
    try:
        sip.unwrapinstance(qobj)
    except RuntimeError:
        return False
    else:
        return True

class Debug(object):
    """holds flags for debugging output. At a later time we might
    want to add command line parameters for initialisation, and
    look at kdebugdialog"""
    connections = False
    traffic = False
    process = False
    time = False
    sql = False
    animation = '' # 'yeysywynfefsfwfn'
    animationSpeed = False
    robotAI = False
    dangerousGame = False
    originalCall = False
    modelTest = False
    focusable = ''
    robbingKong = False
    mahJongg = False
    sound = False
    chat = False
    argString = None
    scores = False
    handCache = False
    explain = False
    random = False
    deferredBlock = False
    stack = False
    events = ''
    table = False
    gc = False
    delayChow = False
    locate = False
    neutral = False  # only neutral comparable debug output

    def __init__(self):
        raise Exception('Debug is not meant to be instantiated')

    @staticmethod
    def help():
        """a string for help texts about debug options"""
        def optYielder(options):
            """yields options with markers for line separation"""
            for idx, opt in enumerate(options):
                yield opt
                if idx < len(options) - 1 and idx % 5 == 4:
                    yield 'SEPARATOR'
        options = list(x for x in Debug.__dict__ if not x.startswith('_'))
        boolOptions = sorted(x for x in options if isinstance(Debug.__dict__[x], bool))
        stringOptions = sorted(x for x in options if isinstance(Debug.__dict__[x], basestring))
        stringExample = '%s=%s' % (stringOptions[0], 's3s4')
        allOptions = sorted(boolOptions + stringOptions)
        opt = '\n'.join(', '.join(optYielder(allOptions)).split(' SEPARATOR, '))
        return """set debug options. Pass a comma separated list of options.
Options are: {opt}.
Options {stropt} take a string argument like {example}""".format(
           opt=opt,
           stropt=', '.join(stringOptions), example=stringExample)

    @staticmethod
    def setOptions(args):
        """args comes from the command line. Put this in the Debug class.
        If something goes wrong, return an error message."""
        if not args:
            return
        Debug.argString = args
        for arg in args.split(','):
            parts = arg.split('=')
            if len(parts) == 1:
                parts.append(True)
            option, value = parts
            if option not in Debug.__dict__:
                return '--debug: unknown option %s' % option
            if type(Debug.__dict__[option]) != type(value):
                return '--debug: wrong value for option %s' % option
            type.__setattr__(Debug, option, value)
        if Debug.time:
            Debug.time = datetime.datetime.now()

class FixedClass(type):
    """Metaclass: after the class variable fixed is set to True,
    all class variables become immutable"""
    def __setattr__(cls, key, value):
        if cls.fixed:
            for line in traceback.format_stack()[:-2]:
                print(line, end='')
            raise SystemExit('{cls}.{key} may not be changed'.format(cls=cls.__name__, key=key))
        else:
            type.__setattr__(cls, key, value)

class Options(object):
    """they are never saved in a config file. Some of them
    can be defined on the command line."""
    __metaclass__ = FixedClass
    demo = False
    showRulesets = False
    rulesetName = None	# will only be set by command line --ruleset
    ruleset = None # from rulesetName
    rounds = None
    host = None
    player = None
    dbPath = None
    socket = None
    playOpen = False
    gui = False
    AI = 'Default'
    csv = None
    continueServer = False
    fixed = False

    def __init__(self):
        raise Exception('Options is not meant to be instantiated')

    @staticmethod
    def defaultPort():
        """8000 plus version: for version 4.9.5 we use 8409"""
        parts = Internal.version.split('.')
        return 8000 + int(parts[0]) * 100 + int(parts[1])

class SingleshotOptions(object):
    """Options which are cleared after having been used once"""
    table = False
    join = False
    game = None

class Internal(object):
    """global things"""
    Preferences = None
    version = '4.13.0'
    logPrefix = 'C'
    isServer = False
    scaleScene = True
    reactor = None
    app = None
    dbIdent = None
    scene = None
    mainWindow = None
    game = None
    autoPlay = False
    quitWaitTime = 0 # in milliseconds

    def __init__(self):
        raise Exception('Internal is not meant to be instantiated')

class IntDict(defaultdict):
    """a dict where the values are expected to be numeric, so
    we can add dicts.If parent is given, parent is expected to
    be another IntDict, and our changes propagate into parent.
    This allows us to have a tree of IntDicts, and we only have
    to update the leaves, getting the sums for free"""

    def __init__(self, parent=None):
        defaultdict.__init__(self, int)
        self.parent = parent

    def copy(self):
        """need to reimplement this because the __init__ signature of
        IntDict is not identical to that of defaultdict"""
        result = IntDict(self.parent)
        defaultdict.update(result, self)
        # see http://www.logilab.org/ticket/23986
        return result

    def __add__(self, other):
        """add two IntDicts"""
        result = self.copy()
        for key, value in other.items():
            result[key] += value
        return result

    def __radd__(self, other):
        """we want sum to work (no start value)"""
        assert other == 0
        return self.copy()

    def __sub__(self, other):
        """self - other"""
        result = self.copy()
        for key, value in other.items():
            result[key] -= value
        for key in defaultdict.keys(result):
            if result[key] == 0:
                del result[key]
        return result

    def __eq__(self, other):
        return self.all() == other.all()

    def count(self, countFilter=None):
        """how many tiles defined by countFilter do we hold?
        countFilter is an iterator of element names. No countFilter: Take all
        So count(['we','ws']) should return 8"""
        return sum((defaultdict.get(self, x) or 0) for x in countFilter or self)

    def all(self, countFilter=None):
        """returns a list of all tiles defined by countFilter, each tile multiplied by its occurrence
        countFilter is an iterator of element names. No countFilter: take all
        So all(['we','fs']) should return ['we', 'we', 'we', 'we', 'fs']"""
        result = []
        for element in countFilter or self:
            result.extend([element] * self[element])
        return sorted(result)

    def __contains__(self, tile):
        """does not contain tiles with count 0"""
        return defaultdict.__contains__(self, tile) and self[tile] > 0

    def __setitem__(self, key, value):
        """also update parent if given"""
        if self.parent is not None:
            self.parent[key] += value - defaultdict.get(self, key, 0)
        defaultdict.__setitem__(self, key, value)

    def __delitem__(self, key):
        """also update parent if given"""
        if self.parent is not None:
            self.parent[key] -= defaultdict.get(self, key, 0)
        defaultdict.__delitem__(self, key)

    def clear(self):
        """also update parent if given"""
        if self.parent is not None:
            for key, value in defaultdict.items(self):
                self.parent[key] -= value
        defaultdict.clear(self)

    def __str__(self):
        """sort the result for better log comparison"""
        keys = sorted(self.keys())
        return ', '.join('{}:{}'.format(x, self[x]) for x in keys)

    def __repr__(self):
        return "<IntDict: %s>" % self

class ZValues(object):
    """here we collect all zValues used in Kajongg"""
    itemLevelFactor = 100000
    boardLevelFactor = itemLevelFactor * 100
    marker = boardLevelFactor * 100 + 1
    moving = marker + 1
    popup = moving + 1
