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

from collections import defaultdict

import sip

# common must not import util

Preferences = None # pylint: disable=C0103
# pylint - just like Debug, InternalParameters
# Preferences being a class or an instance is irrelevant for the user

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

class Debug:
    """holds flags for debugging output. At a later time we might
    want to add command line parameters for initialisation, and
    look at kdebugdialog"""
    connections = False
    traffic = False
    process = False
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
            Debug.__dict__[option] = value

class InternalParameters:
    """they are never saved in a config file. Some of them
    can be defined on the command line."""
    version = '4.11.0'
    scaleScene = True
    reactor = None
    game = None # will only be set by command line --game
    demo = False
    showRulesets = False
    rulesetName = None	# will only be set by command line --ruleset
    ruleset = None # from rulesetName
    player = None
    dbPath = None
    dbIdent = None
    app = None
    socket = None
    playOpen = False
    field = None
    gui = False
    isServer = False
    AI = 'Default'
    csv = None
    logPrefix = 'C'
    continueServer = False
    try:
        from PyKDE4.kdeui import KMessageBox
        haveKDE = True
    except BaseException:
        haveKDE = False

    def __init__(self):
        raise Exception('InternalParameters is not meant to be instantiated')

    @staticmethod
    def defaultPort():
        """8000 plus version: for version 4.9.5 we use 8409"""
        parts = InternalParameters.version.split('.')
        return 8000 + int(parts[0]) * 100 + int(parts[1])

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
        return str(dict(self))

    def __repr__(self):
        return "<IntDict: %s>" % self

class Elements(object):
    """represents all elements"""
    # pylint: disable=R0902
    # too many attributes
    def __init__(self):
        self.occurrence = IntDict() # key: db, s3 etc. value: occurrence
        self.winds = set(['we', 'ws', 'ww', 'wn'])
        self.wINDS = set(['We', 'Ws', 'Ww', 'Wn'])
        self.dragons = set(['db', 'dg', 'dr'])
        self.dRAGONS = set(['Db', 'Dg', 'Dr'])
        self.honors = self.winds | self.dragons
        self.hONORS = self.wINDS | self.dRAGONS
        self.terminals = set(['s1', 's9', 'b1', 'b9', 'c1', 'c9'])
        self.tERMINALS = set(['S1', 'S9', 'B1', 'B9', 'C1', 'C9'])
        self.majors = self.honors | self.terminals
        self.mAJORS = self.hONORS | self.tERMINALS
        self.minors = set()
        self.mINORS = set()
        self.greenHandTiles = set(['dg', 'b2', 'b3', 'b4', 'b6', 'b8'])
        for color in 'sbc':
            for value in '2345678':
                self.minors |= set(['%s%s' % (color, value)])
        for tile in self.majors:
            self.occurrence[tile] = 4
        for tile in self.minors:
            self.occurrence[tile] = 4
        for bonus in 'fy':
            for wind in 'eswn':
                self.occurrence['%s%s' % (bonus, wind)] = 1

    def __filter(self, ruleset):
        """returns element names"""
        return (x for x in self.occurrence if ruleset.withBonusTiles or (x[0] not in 'fy'))

    def count(self, ruleset):
        """how many tiles are to be used by the game"""
        return self.occurrence.count(self.__filter(ruleset))

    def all(self, ruleset):
        """a list of all elements, each of them occurrence times"""
        return self.occurrence.all(self.__filter(ruleset))


class ZValues(object):
    """here we collect all zValues used in Kajongg"""
    itemLevelFactor = 100000
    boardLevelFactor = itemLevelFactor * 100
    marker = boardLevelFactor * 100 + 1
    moving = marker + 1
    popup = moving + 1

elements = Elements()  # pylint: disable=C0103
