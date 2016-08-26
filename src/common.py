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

from __future__ import print_function

from collections import defaultdict
import datetime
import sys
import os
import logging
import logging.handlers
import socket
import platform

try:
    from sip import unwrapinstance
except ImportError:
    def unwrapinstance(dummy):
        """if there is no sip, we have no Qt objects anyway"""
        pass

# pylint: disable=invalid-name
if platform.python_version_tuple()[0] == '3':
    # pylint: disable=redefined-builtin
    unicode = str  # pylint: disable=W0622
    bytes = bytes
    long = int
    isPython3 = True
    interpreterName = 'python3'
    xrange = range
else:
    # pylint: disable=redefined-builtin
    unicode = unicode
    bytes = str
    long = long
    isPython3 = False
    if os.name == 'nt':
        interpreterName = 'python'
    else:
        interpreterName = 'python2'
    xrange = xrange

LIGHTSOURCES = [u'NE', u'NW', u'SW', u'SE']
ENGLISHDICT = {}


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


class Debug(object):

    """holds flags for debugging output. At a later time we might
    want to add command line parameters for initialisation, and
    look at kdebugdialog"""
    connections = False
    traffic = False
    process = False
    time = False
    sql = False
    animation = ''  # 'yeysywynfefsfwfn'
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
    git = False
    ruleCache = False
    quit = False
    preferences = False
    graphics = False

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


class StrMixin(object):

    """
    A mixin defining defaults for __str__ and __repr__,
    using __unicode__.
    """

    def __str__(self):
        return nativeString(self.__unicode__())

    def __repr__(self):
        return '{cls}({content})'.format(
            cls=self.__class__.__name__,
            content=self.__str__())


class Options(object):

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


class SingleshotOptions(object):

    """Options which are cleared after having been used once"""
    table = False
    join = False
    game = None


class __Internal(object):

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
    if isPython3:
        defaultPort = 8300
    else:
        defaultPort = 8200
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

    def __init__(self):
        """init the loggers"""
        logName = sys.argv[0].replace('.py', '') + '.log'
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
            handler = logging.handlers.RotatingFileHandler(
                'kajongg.log', maxBytes=100000000, backupCount=10)
        self.logger.addHandler(handler)
        self.logger.addHandler(logging.StreamHandler(sys.stderr))
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(name)s: %(levelname)s %(message)s")
        handler.setFormatter(formatter)

Internal = __Internal()


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

    def __ne__(self, other):
        return self.all() != other.all()

    def count(self, countFilter=None):
        """how many tiles defined by countFilter do we hold?
        countFilter is an iterator of element names. No countFilter: Take all
        So count(['we','ws']) should return 8"""
        return sum((defaultdict.get(self, x) or 0)
                   for x in countFilter or self)

    def all(self, countFilter=None):
        """returns a list of all tiles defined by countFilter,
        each tile multiplied by its occurrence.
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
        return ', '.join('{}:{}'.format(
            str(x), str(self[x])) for x in keys)

    def __unicode__(self):
        """sort the result for better log comparison"""
        keys = sorted(self.keys())
        return u', '.join('{}:{}'.format(
            unicodeString(x), unicodeString(self[x])) for x in keys)


class ZValues(object):

    """here we collect all zValues used in Kajongg"""
    itemLevelFactor = 100000
    boardLevelFactor = itemLevelFactor * 100
    marker = boardLevelFactor * 100 + 1
    moving = marker + 1
    popup = moving + 1


def english(i18nstring):
    """translate back from local language"""
    return ENGLISHDICT.get(i18nstring, i18nstring)


def unicodeString(s, encoding='utf-8'):
    """
    If s is not unicode, make it so.

    @param s: The original string or None.
    @type s: C{QString}, C{unicode}, C{str} or C{bytes}
    @rtype: C{unicode} or None.
    """
    if s is None:
        return s
    if s.__class__.__name__ == 'QString':  # avoid import of QString
        return unicode(s)
    elif isinstance(s, unicode):
        return s
    elif hasattr(s, 'decode'):
        return s.decode(encoding)
    else:
        return repr(s)


def isStringType(s):
    """Returns True for QString, QByteArray, str, bytes, unicode."""
    if s.__class__.__name__ in ('QString', 'QByteArray'):
        return True
    return isinstance(s, (bytes, unicode))


def nativeString(s, encoding='utf-8'):
    """
    Code inspired by twisted.python.compat.

    Convert C{QByteArray}, C{QString}, C{bytes} or C{unicode}
    to the native C{str} type, using the given encoding if
    conversion is necessary.

    @param s: The original string or None.
    @type s: C{QByteArray}, C{QString}, C{unicode}, C{str} or C{bytes}
    @param encoding: The encoding for the given string, if it is
                not of type C{unicode}. Default is utf-8.
    @returns: The string.
    @rtype: C{str}

    @raise UnicodeError: The input string is not encodable/decodable.
    @raise TypeError: The input is not of string type.
    """
    if s is None:
        return s
    if s.__class__.__name__ == 'QString':  # avoid import of QString
        s = unicode(s)
    if s.__class__.__name__ == 'QByteArray':  # avoid import of QByteArray
        s = bytes(s)
    if not isStringType(s):
        return s
    if isPython3:
        if isinstance(s, bytes):
            return s.decode(encoding)
        else:
            # Ensure we're limited to the given encoding subset:
            s.encode(encoding)
    else:
        if isinstance(s, unicode):
            return s.encode(encoding)
        else:
            # Ensure we're limited to the given encoding subset:
            s.decode(encoding)
    return s


def nativeStringArgs(args, encoding='utf-8'):
    """
    Convert string elements of a tuple to the native C{str} type,
    Those elements which are not of some string type are left alone.
    For acceptable string types see L{common.nativeString}.

    @param args: A sequence of L{nativeString}.
    @param encoding: The encoding for the strings. Default is utf-8.
    @returns: A tuple with the converted strings.
    @rtype: C{tuple}
    """
    return tuple((nativeString(x, encoding)
                  if isStringType(x) else x for x in args))


def unicodeStringArgs(args, encoding='utf-8'):
    """
    Convert string elements of a tuple to C{unicode},
    Those elements which are not of some string type are left alone.
    For acceptable string types see L{common.nativeString}.

    @param s: None or a string to convert to C{str} if necessary.
    @param encoding: The encoding for the strings. Default is utf-8.
    @returns: A tuple with the converted strings.
    @rtype: C{tuple}
    """
    return tuple((unicodeString(x, encoding)
                  if isStringType(x) else x for x in args))
