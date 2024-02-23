# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

from collections import defaultdict
import datetime
import sys
import os
import shutil
import logging
import logging.handlers
import socket
import string
from signal import signal, SIGABRT, SIGINT, SIGTERM
from typing import Optional, Any, Union, List, Sequence, Mapping
from typing import TYPE_CHECKING, Iterable, Generator, Literal, cast

from qtpy.compat import isalive as qtpy_isalive
from qt import QStandardPaths, QObject, QSize

if TYPE_CHECKING:
    from tile import Tile
    from mainwindow import MainWindow
    from twisted.internet.interfaces import IReactorCore
    from config import SetupPreferences
    from qt import QGraphicsItem
    from scene import GameScene

# pylint: disable=invalid-name

if sys.platform == 'win32':
    # This is only needed for manual execution, and
    # we expect python to be the python3 interpreter.
    # The windows installer will use kajongg.exe and kajonggserver.exe
    interpreterName = 'python'
else:
    interpreterName = 'python3'

# TODO: enumeration
LIGHTSOURCES = cast(Union[Literal['NE'], Literal['NW'], Literal['SW'], Literal['SE']], ['NE', 'NW', 'SW', 'SE'])


def isAlive(qobj: Union[QObject, 'QGraphicsItem', None]) ->bool:
    """check if the underlying C++ object still exists"""
    if qobj is None:
        return False
    result = qtpy_isalive(qobj)
    if not result and Debug.isalive:
        print('NOT alive:', repr(qobj))
    return result

def serverAppdataDir() ->str:
    """
    The per user directory with kajongg application information like the database.

    @return: The directory path.
    @rtype: C{str}.
    """
    serverDir = os.path.expanduser('~/.kajonggserver/')
    # the server might or might not have KDE installed, so to be on
    # the safe side we use our own .kajonggserver directory
    # the following code moves an existing kajonggserver.db to .kajonggserver
    # but only if .kajonggserver does not yet exist
    kdehome = os.environ.get('KDEHOME', '~/.kde')
    oldPath = os.path.expanduser(
        f"{kdehome}/share/apps/kajongg/kajonggserver.db")
    if not os.path.exists(oldPath):
        oldPath = os.path.expanduser(
            '~/.kde4/share/apps/kajongg/kajonggserver.db')
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


def clientAppdataDir() ->str:
    """
    The per user directory with kajongg application information like the database.

    @return: The directory path.
    @rtype: C{str}.
    """
    serverDir = os.path.expanduser('~/.kajonggserver/')
    if not os.path.exists(serverDir):
        # the client wants to place the socket in serverDir
        os.makedirs(serverDir)
    result = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    # this may end with kajongg.py or .pyw or whatever, so fix that:
    if not os.path.isdir(result):
        result = os.path.dirname(result)
    if not result.endswith('kajongg'):
        # when called first, QApplication.applicationName is not yet set
        result = result + '/kajongg'
    if not os.path.exists(result):
        os.makedirs(result)
    return result


def appdataDir() ->str:
    """
    The per user directory with kajongg application information like the database.

    @return: The directory path.
    @rtype: C{str}.
    """
    return serverAppdataDir() if Internal.isServer else clientAppdataDir()


def cacheDir() ->str:
    """the cache directory for this user"""
    result = os.path.join(appdataDir(), '.cache')
    if not os.path.exists(result):
        os.makedirs(result)
    return result


def socketName() ->str:
    """client and server process use this socket to talk to each other"""
    serverDir = os.path.expanduser('~/.kajonggserver')
    if not os.path.exists(serverDir):
        appdataDir()
                   # allocate the directory and possibly move old databases
                   # there
    if Options.socket:
        return Options.socket
    return os.path.normpath(f'{serverDir}/socket{Internal.defaultPort}')


def handleSignals(handler: Any) ->None:

    """set up signal handling"""

    signal(SIGABRT, handler)
    signal(SIGINT, handler)
    signal(SIGTERM, handler)
    if sys.platform != 'win32':
        from signal import SIGHUP, SIGQUIT
        signal(SIGHUP, handler)
        signal(SIGQUIT, handler)


class Debug:

    """holds flags for debugging output. At a later time we might
    want to add command line parameters for initialisation, and
    look at kdebugdialog"""
    connections = False
    traffic = False
    process = False
    time = False
    timestamp:Optional[datetime.datetime] = None
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
    isalive = False

    def __init__(self) ->None:
        raise TypeError('Debug is not meant to be instantiated')

    @staticmethod
    def help() ->'str':
        """a string for help texts about debug options"""
        def optYielder(options: List[str]) -> Generator[str, None, None]:
            """yields options with markers for line separation"""
            for idx, opt in enumerate(options):
                yield opt
                if idx < len(options) - 1 and idx % 5 == 4:
                    yield 'SEPARATOR'
        options = [x for x in Debug.__dict__ if not x.startswith('_')]
        boolOptions = sorted(x for x in options
                             if isinstance(Debug.__dict__[x], bool))
        stringOptions = sorted(x for x in options
                               if isinstance(Debug.__dict__[x], str))
        stringExample = f'{stringOptions[0]}:s3s4'
        allOptions = sorted(boolOptions + stringOptions)
        opt = '\n'.join(
            ', '.join(optYielder(allOptions)).split(' SEPARATOR, '))
        # TODO: i18n for this string. First move i18n out of kde so we can import it here
        return f"""set debug options. Pass a comma separated list of options.
Options are: {opt}.
Options {', '.join(stringOptions)} take a string argument like {stringExample}.
--debug=events can get suboptions like in --debug=events:Mouse:Hide
     showing all event messages with 'Mouse' or 'Hide' in them"""

    @staticmethod
    def setOptions(args: 'str') ->'str':
        """args comes from the command line. Put this in the Debug class.
        If something goes wrong, return an error message."""
        if not args:
            return ''
        Debug.argString = args
        for arg in args.split(','):
            parts = arg.split(':')
            option = parts[0]
            value: Union[bool, str]
            if len(parts) == 1:
                value = True
            else:
                value = ':'.join(parts[1:])
            if option not in Debug.__dict__:
                return f'--debug: unknown option {option}'
            if not isinstance(Debug.__dict__[option], type(value)):
                return (f"--debug: wrong type for option {option}: "
                        f"given {value}/{type(value)}, should be {type(Debug.__dict__[option])}")
            if option != 'scores' or not Internal.isServer:
                type.__setattr__(Debug, option, value)
        if Debug.time:
            Debug.timestamp = datetime.datetime.now()
        if Debug.modelTest and not Debug.modeltest_is_supported():
            print('--debug=modelTest is not yet supported for pyside, use pyqt')
            sys.exit(2)
        return ''

    @staticmethod
    def modeltest_is_supported() ->bool:
        """Is the QT binding supported."""
        try:
            import sip  # type:ignore[import]
        except ImportError:
            return False
        try:
            _ = sip.cast(QSize(), QSize)
            return True
        except TypeError:
            return False

    @staticmethod
    def str() ->str:
        """__str__ does not work with class objects"""
        result = []
        for option in Debug.__dict__:
            if not option.startswith('_'):
                result.append(f'{option}={getattr(Debug, option)}')
        return ' '.join(result)


class FixedClass(type):

    """Metaclass: after the class variable fixed is set to True,
    all class variables become immutable"""
    def __setattr__(cls, key: str, value: object) ->None:
        if cls.fixed:  # type: ignore
            raise SystemExit(f'{cls.__name__}.{key} may not be changed')
        type.__setattr__(cls, key, value)


class ReprMixin:

    """
    A mixin defining a default for __repr__,
    using __str__. If __str__ is not defined, this runs
    into recursion. But I see no easy way without too much
    runtime overhead to check for this beforehand.
    """

    def __repr__(self) ->str:
        clsName = self.__class__.__name__
        content = str(self)
        if content.startswith(clsName):
            return content
        return f'{clsName}_{id4(self)}({content})'


class Options(metaclass=FixedClass):

    """they are never saved in a config file. Some of them
    can be defined on the command line."""
    demo = False
    showRulesets = False
    rulesetName = None  # will only be set by command line --ruleset
    ruleset = None       # from rulesetName
    rounds = None
    host = None
    player = None
    dbPath = None
    socket : Optional[str] = None
    port = None
    playOpen = False
    gui = False
    AI = 'DefaultAI'
    csv = None
    continueServer = False
    fixed = False

    def __init__(self) ->None:
        raise TypeError('Options is not meant to be instantiated')

    @staticmethod
    def str() -> str:
        """__str__ does not work with class objects"""
        result = []
        for option in Options.__dict__:
            if not option.startswith('_'):
                value = getattr(Options, option)
                if isinstance(value, (bool, int, str)):
                    result.append(f'{option}={value}')
        return ' '.join(result)

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
    @cvar reactor: The twisted reactor instance.
    @type reactor: L{twisted.internet.reactor}
    @cvar app: The Qt or KDE app instance
    @type app: L{KApplication}
    @cvar db: The sqlite3 data base
    @type db: L{DBHandle}
    @cvar scene: The game scene.
    @type scene: L{GameScene}: L{PlayingScene} or L{ScoringScene}
    """
    Preferences:Optional['SetupPreferences'] = None
    defaultPort = 8301
    logPrefix = 'C'
    isServer = False
    reactor:'IReactorCore'
    app : Any = None
    db : Any = None
    scene:Optional['GameScene'] = None
    mainWindow : Optional['MainWindow'] = None
    game = None
    autoPlay = False
    logger : Any = None
    kajonggrc : Any = None

    def __init__(self) ->None:
        """init the loggers"""
        handler: Any
        logName = f"{os.path.basename(sys.argv[0]).replace('.py', '').replace('.exe', '')}.log"
        self.logger = logging.getLogger(logName)
        if sys.platform == 'win32':
            haveDevLog = False
        else:
            try:
                handler = logging.handlers.SysLogHandler('/dev/log')
                haveDevLog = True
            except (AttributeError, socket.error):
                haveDevLog = False
        if not haveDevLog:
            logName = os.path.join(appdataDir(), logName)
            handler = logging.handlers.RotatingFileHandler(
                logName, maxBytes=100000000, backupCount=10)
        self.logger.addHandler(handler)
        self.logger.addHandler(logging.StreamHandler(sys.stderr))
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(name)s: %(levelname)s %(message)s")
        handler.setFormatter(formatter)

Internal = __Internal()


class IntDict(defaultdict, ReprMixin):

    """a dict where the values are expected to be numeric, so
    we can add dicts.If parent is given, parent is expected to
    be another IntDict, and our changes propagate into parent.
    This allows us to have a tree of IntDicts, and we only have
    to update the leaves, getting the sums for free"""

    def __init__(self, parent: Optional['IntDict']=None) ->None:
        defaultdict.__init__(self, int)
        self.parent = parent

    def copy(self) -> 'IntDict':
        """need to reimplement this because the __init__ signature of
        IntDict is not identical to that of defaultdict"""
        result = IntDict(self.parent)
        defaultdict.update(result, self)
        # see https://www.logilab.org/ticket/23986
        return result

    def __add__(self, other: object) -> 'IntDict':
        """add two IntDicts"""
        assert isinstance(other, IntDict), other
        result = self.copy()
        for key, value in other.items():
            result[key] += value
        return result

    def __radd__(self, other: object) -> 'IntDict':
        """we want sum to work (no start value)"""
        assert other == 0
        return self.copy()

    def __sub__(self, other: object) -> 'IntDict':
        """self - other"""
        assert isinstance(other, IntDict), other
        result = self.copy()
        for key, value in other.items():
            result[key] -= value
        for key in defaultdict.keys(result):
            if result[key] == 0:
                del result[key]
        return result

    def __eq__(self, other: object) ->bool:
        assert isinstance(other, IntDict), other
        return self.all() == other.all()

    def __ne__(self, other: object) ->bool:
        assert isinstance(other, IntDict), other
        return self.all() != other.all()

    def count(self, countFilter: Optional[Iterable]=None) ->int:
        """how many tiles defined by countFilter do we hold?
        countFilter is an iterator of element names. No countFilter: Take all
        So count(['we', 'ws']) should return 8"""
        return sum((defaultdict.get(self, x) or 0)  # type: ignore
                   for x in countFilter or self)

    def all(self, countFilter: Optional[Iterable]=None) ->List['Tile']:
        """return a list of all tiles defined by countFilter,
        each tile multiplied by its occurrence.
        countFilter is an iterator of element names. No countFilter: take all
        So all(['we', 'fs']) should return ['we', 'we', 'we', 'we', 'fs']"""
        result : List['Tile'] = []
        for element in countFilter or self:
            result.extend([element] * self[element])
        return sorted(result)

    def __contains__(self, tile: object) ->bool:
        """does not contain tiles with count 0"""
        return defaultdict.__contains__(self, tile) and self[tile] > 0

    def __setitem__(self, key: Any, value: Any) ->None:
        """also update parent if given"""
        if self.parent is not None:
            self.parent[key] += value - defaultdict.get(self, key, cast(Any, 0))
        defaultdict.__setitem__(self, key, value)

    def __delitem__(self, key: Any) ->None:
        """also update parent if given"""
        if self.parent is not None:
            self.parent[key] -= defaultdict.get(self, key, cast(Any, 0))
        defaultdict.__delitem__(self, key)

    def clear(self) ->None:
        """also update parent if given"""
        if self.parent is not None:
            for key, value in defaultdict.items(self):
                self.parent[key] -= value
        defaultdict.clear(self)

    def __str__(self) ->str:
        """sort the result for better log comparison"""
        keys = sorted(self.keys())
        return ', '.join(f'{str(x)}:{str(self[x])}' for x in keys)


class ZValues:

    """here we collect all zValues used in Kajongg"""
    itemZFactor = 100000
    boardZFactor = itemZFactor * 100
    markerZ = boardZFactor * 100 + 1
    movingZ = markerZ + 1
    popupZ = movingZ + 1


class Speeds:
    """some fixed animation speeds"""
    windDisc = 20
    sideText = 60


class DrawOnTopMixin:

    """The inheriting QGraphicsObject will draw itself above all non moving tiles"""

    def setDrawingOrder(self) ->None:
        """we want us above all non moving tiles"""
        if self.activeAnimation.get('pos'):  # type: ignore
            movingZ = ZValues.movingZ
        else:
            movingZ = 0
        self.setZValue(ZValues.markerZ + movingZ)  # type: ignore


def id4(obj: object) ->str:
    """object id for debug messages"""
    if obj is None:
        return 'NONE'
    try:
        if hasattr(obj, 'uid'):
            return obj.uid
    except Exception:  # pylint: disable=broad-except
        pass
    return '.' if Debug.neutral else Fmt.num_encode(id(obj))


class Fmt(string.Formatter):

    """this formatter can parse {id(x)} and output a short ascii form for id"""
    alphabet = string.ascii_uppercase + string.ascii_lowercase
    base = len(alphabet)
    formatter : Optional['Fmt'] = None

    @staticmethod
    def num_encode(number: int, length: int=4) ->str:
        """make a short unique ascii string out of number, truncate to length"""
        result : List[str] = []
        while number and len(result) < length:
            number, remainder = divmod(number, Fmt.base)
            result.append(Fmt.alphabet[remainder])
        return ''.join(reversed(result))

    def get_value(self, key : Union[int, str], args: Sequence[Any], kwargs: Mapping[str, Any]) ->str:
        assert isinstance(key, str), key
        if key.startswith('id(') and key.endswith(')'):
            idpar = key[3:-1]
            if idpar == 'self':
                idpar = 'SELF'
            if kwargs[idpar] is None:
                return 'None'
            if Debug.neutral:
                return '....'
            return Fmt.num_encode(id(kwargs[idpar]))
        if key == 'self':
            return kwargs['SELF']
        return kwargs[key]

Fmt.formatter = Fmt()


def fmt(text: str, **kwargs: Any) ->str:
    """use the context dict for finding arguments.
    For something like {self} output 'self:selfValue'"""
    if '}' in text:
        parts = []
        for part in text.split('}'):
            if '{' not in part:
                parts.append(part)
            else:
                part2 = part.split('{')
                if part2[1] == 'callers':
                    if part2[0]:
                        parts.append(f'{part2[0]}:{{{part2[1]}}}')
                    else:
                        parts.append(f'{{{part2[1]}}}')
                else:
                    showName = f"{part2[1]}:"
                    if showName.startswith('_hide'):
                        showName = ''
                    if showName.startswith('self.'):
                        showName = showName[5:]
                    parts.append(f'{part2[0]}{showName}{{{part2[1]}}}')
        text = ''.join(parts)
    argdict = sys._getframe(1).f_locals  # pylint: disable=protected-access
    argdict.update(kwargs)
    if 'self' in argdict:
        # formatter.format will not accept 'self' as keyword
        argdict['SELF'] = argdict['self']
        del argdict['self']
    assert Fmt.formatter is not None
    return Fmt.formatter.format(text, **argdict)
