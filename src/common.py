# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from collections import defaultdict
import datetime
import sys
import os
import shutil
import logging
import logging.handlers
import socket

from qt import QStandardPaths
try:
    from PyQt5.sip import unwrapinstance
except ImportError:
    try:
        from sip import unwrapinstance
    except ImportError:
        def unwrapinstance(dummy):
            """if there is no sip, we have no Qt objects anyway"""
            pass

# pylint: disable=invalid-name

if os.name == 'nt':
    # This is only needed for manual execution, and
    # we expect python to be the python3 interpreter.
    # The windows installer will use kajongg.exe and kajonggserver.exe
    interpreterName = 'python'
else:
    interpreterName = 'python3'

LIGHTSOURCES = ['NE', 'NW', 'SW', 'SE']

def isAlive(qobj):
    """is the underlying C++ object still valid?
    This function is taken from the book
    "Rapid GUI Programming with Python and Qt"
    by Mark Summerfield."""
    if qobj is None:
        return False
    try:
        unwrapinstance(qobj)
    except RuntimeError:
        return False
    else:
        return True


def appdataDir():
    """
    The per user directory with kajongg application information like the database.

    @return: The directory path.
    @rtype: C{str}.
    """
    serverDir = os.path.expanduser('~/.kajonggserver/')
    if Internal.isServer:
        # the server might or might not have KDE installed, so to be on
        # the safe side we use our own .kajonggserver directory
        # the following code moves an existing kajonggserver.db to .kajonggserver
        # but only if .kajonggserver does not yet exist
        kdehome = os.environ.get('KDEHOME', '~/.kde')
        oldPath = os.path.expanduser(
            kdehome +
            '/share/apps/kajongg/kajonggserver.db')
        if not os.path.exists(oldPath):
            oldPath = os.path.expanduser(
                '~/.kde' +'4/share/apps/kajongg/kajonggserver.db')
        if os.path.exists(oldPath) and not os.path.exists(serverDir):
            # upgrading an old kajonggserver installation
            os.makedirs(serverDir)
            shutil.move(oldPath, serverDir)
        if not os.path.exists(serverDir):
            try:
                os.makedirs(serverDir)
            except OSError:
                pass
        return serverDir
    else:
        if not os.path.exists(serverDir):
            # the client wants to place the socket in serverDir
            os.makedirs(serverDir)
        result = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        # this may end with kajongg.py or .pyw or whatever, so fix that:
        result = os.path.join(os.path.dirname(result), 'kajongg')
        if not os.path.exists(result):
            os.makedirs(result)
        return result


def cacheDir():
    """the cache directory for this user"""
    result = os.path.join(appdataDir(), '.cache')
    if not os.path.exists(result):
        os.makedirs(result)
    return result


def socketName():
    """client and server process use this socket to talk to each other"""
    serverDir = os.path.expanduser('~/.kajonggserver')
    if not os.path.exists(serverDir):
        appdataDir()
                   # allocate the directory and possibly move old databases
                   # there
    if Options.socket:
        return Options.socket
    else:
        return os.path.normpath('{}/socket{}'.format(serverDir, Internal.defaultPort))


class Debug:

    """holds flags for debugging output. At a later time we might
    want to add command line parameters for initialisation, and
    look at kdebugdialog"""
    connections = False
    traffic = False
    process = False
    time = False
    sql = False
    animation = ''  # 'yeysywynG87gfefsfwfn' for tiles and G#g for groups where # is the uid
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
    hand = False
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
    callers = '0'
    git = False
    ruleCache = False
    quit = False
    preferences = False
    graphics = False
    scoring = False
    wallSize = '0'
    i18n = False

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
        boolOptions = sorted(x for x in options
                             if isinstance(Debug.__dict__[x], bool))
        stringOptions = sorted(x for x in options
                               if isinstance(Debug.__dict__[x], str))
        stringExample = '%s:%s' % (stringOptions[0], 's3s4')
        allOptions = sorted(boolOptions + stringOptions)
        opt = '\n'.join(
            ', '.join(optYielder(allOptions)).split(' SEPARATOR, '))
        # TODO: i18n for this string. First move i18n out of kde so we can import it here
        return """set debug options. Pass a comma separated list of options.
Options are: {opt}.
Options {stropt} take a string argument like {example}.
--debug=events can get suboptions like in --debug=events:Mouse:Hide
     showing all event messages with 'Mouse' or 'Hide' in them""".format(
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
            parts = arg.split(':')
            option = parts[0]
            if len(parts) == 1:
                value = True
            else:
                value = ':'.join(parts[1:]) # pylint: disable=redefined-variable-type
            if option not in Debug.__dict__:
                return '--debug: unknown option %s' % option
            if not isinstance(Debug.__dict__[option], type(value)):
                return ('--debug: wrong type for option %s: '
                        'given %s/%s, should be %s') % (
                            option, value, type(value),
                            type(Debug.__dict__[option]))
            if option != 'scores' or not Internal.isServer:
                type.__setattr__(Debug, option, value)
        if Debug.time:
            Debug.time = datetime.datetime.now()


class FixedClass(type):

    """Metaclass: after the class variable fixed is set to True,
    all class variables become immutable"""
    def __setattr__(cls, key, value):
        if cls.fixed:
            raise SystemExit('{cls}.{key} may not be changed'.format(
                cls=cls.__name__, key=key))
        else:
            type.__setattr__(cls, key, value)


class StrMixin:

    """
    A mixin defining a default for __repr__,
    using __str__. If __str__ is not defined, this runs
    into recursion. But I see no easy way without too much
    runtime overhead to check for this beforehand.
    """

    def __repr__(self):
        clsName = self.__class__.__name__
        content = str(self)
        if content.startswith(clsName):
            return content
        else:
            return '{cls}({content})'.format(cls=clsName, content=content)


class Options:

    """they are never saved in a config file. Some of them
    can be defined on the command line."""
    __metaclass__ = FixedClass
    demo = False
    showRulesets = False
    rulesetName = None	 # will only be set by command line --ruleset
    ruleset = None       # from rulesetName
    rounds = None
    host = None
    player = None
    dbPath = None
    socket = None
    port = None
    playOpen = False
    gui = False
    AI = 'Default'
    csv = None
    continueServer = False
    fixed = False

    def __init__(self):
        raise Exception('Options is not meant to be instantiated')


class SingleshotOptions:

    """Options which are cleared after having been used once"""
    table = False
    join = False
    game = None


class __Internal:

    """
    Global things.

    @cvar Preferences: The L{SetupPreferences}.
    @type Preferences: L{SetupPreferences}
    @cvar version: The version of Kajongg.
    @type version: C{str}
    @cvar logPrefix: C for client and S for server.
    @type logPrefix: C{str}
    @cvar isServer: True if this is the server process.
    @type isServer: C{bool}
    @cvar scaleScene: Defines if the scene is scaled.
        Disable for debugging only.
    @type scaleScene: C{bool}
    @cvar reactor: The twisted reactor instance.
    @type reactor: L{twisted.internet.reactor}
    @cvar app: The Qt or KDE app instance
    @type app: L{KApplication}
    @cvar db: The sqlite3 data base
    @type db: L{DBHandle}
    @cvar scene: The QGraphicsScene.
    @type scene: L{PlayingScene} or L{ScoringScene}
    """
    # pylint: disable=too-many-instance-attributes
    Preferences = None
    defaultPort = 8301
    logPrefix = 'C'
    isServer = False
    scaleScene = True
    reactor = None
    app = None
    db = None
    scene = None
    mainWindow = None
    game = None
    autoPlay = False
    logger = None
    kajonggrc = None

    def __init__(self):
        """init the loggers"""
        global Internal
        Internal = self
        logName = os.path.basename(sys.argv[0]).replace('.py', '').replace('.exe', '')  + '.log'
        self.logger = logging.getLogger(logName)
        if os.name == 'nt':
            haveDevLog = False
        else:
            try:
                handler = logging.handlers.SysLogHandler('/dev/log')
                haveDevLog = True
            except (AttributeError, socket.error):
                haveDevLog = False
        if not haveDevLog:
            # pylint: disable=redefined-variable-type
            logName = os.path.join(appdataDir(), logName)
            print('Logging into {}'.format(logName))
            handler = logging.handlers.RotatingFileHandler(
                logName, maxBytes=100000000, backupCount=10)
        self.logger.addHandler(handler)
        self.logger.addHandler(logging.StreamHandler(sys.stderr))
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(name)s: %(levelname)s %(message)s")
        handler.setFormatter(formatter)

__Internal()


class IntDict(defaultdict, StrMixin):

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
        # see https://www.logilab.org/ticket/23986
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

    def __ne__(self, other):
        return self.all() != other.all()

    def count(self, countFilter=None):
        """how many tiles defined by countFilter do we hold?
        countFilter is an iterator of element names. No countFilter: Take all
        So count(['we', 'ws']) should return 8"""
        return sum((defaultdict.get(self, x) or 0)
                   for x in countFilter or self)

    def all(self, countFilter=None):
        """returns a list of all tiles defined by countFilter,
        each tile multiplied by its occurrence.
        countFilter is an iterator of element names. No countFilter: take all
        So all(['we', 'fs']) should return ['we', 'we', 'we', 'we', 'fs']"""
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
        return ', '.join('{}:{}'.format(
            str(x), str(self[x])) for x in keys)


class ZValues:

    """here we collect all zValues used in Kajongg"""
    itemZFactor = 100000
    boardZFactor = itemZFactor * 100
    markerZ = boardZFactor * 100 + 1
    movingZ = markerZ + 1
    popupZ = movingZ + 1


class Speeds:
    """some fixed animation speeds"""
    windMarker = 20
    sideText = 60
