#!/usr/bin/env python
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

# keyboardinterrupt should simply terminate
import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)
import sys

from PyQt4.QtCore import QObject, QEvent, Qt
from about import About
from kde import ki18n, KApplication, KCmdLineArgs, KCmdLineOptions

from common import Options, SingleshotOptions, Internal, Debug

# do not import modules using twisted before our reactor is running
# do not import util directly or indirectly before Internal.app
# is set

# pylint: disable=W0404
# pylint does not like imports within functions

def initRulesets():
    """exits if user only wanted to see available rulesets"""
    import predefined # pylint: disable=W0612
    if Options.showRulesets or Options.rulesetName:
        from rule import Ruleset
        from util import kprint
        from query import DBHandle
        rulesets = Ruleset.selectableRulesets()
        if Options.showRulesets:
            for ruleset in rulesets:
                kprint(ruleset.name)
            DBHandle.default = None
            sys.exit(0)
        else:
            for ruleset in rulesets:
                if ruleset.name == Options.rulesetName:
                    Options.ruleset = ruleset
                    break
            else:
                DBHandle.default = None
                raise SystemExit('Ruleset %s is unknown' % Options.rulesetName)

def defineOptions():
    """this is the KDE way. Compare with kajonggserver.py"""
    options = KCmdLineOptions()
    options.add("playopen", ki18n("all robots play with visible concealed tiles"))
    options.add("demo", ki18n("start with demo mode"))
    options.add("host <HOST>", ki18n("login to HOST"))
    options.add("table <TABLE>", ki18n("start new TABLE"))
    options.add("join <TABLE>", ki18n("join TABLE "))
    options.add("ruleset <RULESET>", ki18n("use ruleset without asking"))
    options.add("player <PLAYER>", ki18n("prefer PLAYER for next login"))
    options.add("ai <AI>", ki18n("use AI variant for human player in demo mode"))
    options.add("csv <CSV>", ki18n("write statistics to CSV"))
    options.add("rulesets", ki18n("show all available rulesets"))
    options.add("game <seed/hand/discard>", ki18n("for testing purposes: Initializes the random generator"), "0")
    options.add("nogui", ki18n("show no graphical user interface. Intended only for testing"))
    options.add("socket <SOCKET>", ki18n("use a dedicated server listening on SOCKET. Intended only for testing"))
    options.add("debug <OPTIONS>", ki18n(Debug.help()))
    return options

def parseOptions():
    """parse command line options and save the values"""
    args = KCmdLineArgs.parsedArgs()
    Internal.app = APP
    Options.playOpen |= args.isSet('playopen')
    Options.showRulesets|= args.isSet('rulesets')
    Options.rulesetName = str(args.getOption('ruleset'))
    if args.isSet('host'):
        Options.host = str(args.getOption('host'))
    if args.isSet('player'):
        Options.player = str(args.getOption('player'))
    if args.isSet('ai'):
        Options.AI = str(args.getOption('ai'))
    if args.isSet('csv'):
        Options.csv = str(args.getOption('csv'))
    if args.isSet('socket'):
        Options.socket = str(args.getOption('socket'))
    SingleshotOptions.game = str(args.getOption('game'))
    Options.gui |= args.isSet('gui')
    if args.isSet('table'):
        SingleshotOptions.table = int(args.getOption('table'))
    if args.isSet('join'):
        SingleshotOptions.join = int(args.getOption('join'))
    Options.demo |= args.isSet('demo')
    Options.demo |= not Options.gui
    Internal.autoPlay = Options.demo
    msg = Debug.setOptions(str(args.getOption('debug')))
    if msg:
        print msg
        sys.exit(2)
    from query import initDb
    if not initDb():
        raise SystemExit('Cannot initialize database')
    initRulesets()
    Options.fixed = True # may not be changed anymore

class EvHandler(QObject):
    """an application wide event handler"""
    events = {y:x for x, y in QEvent.__dict__.items() if isinstance(y, int)}
    keys = {y:x for x, y in Qt.__dict__.items() if isinstance(y, int)}
    def eventFilter(self, receiver, event):
        """will be called for all events"""
        from util import logDebug
        if event.type() in self.events:
            # ignore unknown event types
            name = self.events[event.type()]
            if 'all' in Debug.events or name in Debug.events:
                if hasattr(event, 'key'):
                    value = self.keys[event.key()]
                elif hasattr(event, 'text'):
                    value = str(event.text())
                else:
                    value = ''
                if value:
                    value = '(%s)' % value
                msg = '%s%s->%s' % (name, value, receiver)
                if hasattr(receiver, 'text'):
                    msg += '(%s)' % receiver.text()
                elif hasattr(receiver, 'objectName'):
                    msg += '(%s)' % receiver.objectName()
                logDebug(msg)
        return QObject.eventFilter(self, receiver, event)

if __name__ == "__main__":
    from util import initLog
    initLog('kajongg')

    ABOUT = About()
    KCmdLineArgs.init (sys.argv, ABOUT.about)
    KCmdLineArgs.addCmdLineOptions(defineOptions())
    KApplication.setGraphicsSystem('raster')
    APP = KApplication()
    parseOptions()

    if Debug.events:
        EVHANDLER = EvHandler()
        APP.installEventFilter(EVHANDLER)

    from config import SetupPreferences
    SetupPreferences()

    import qt4reactor
    qt4reactor.install()
    from twisted.internet import reactor
    reactor.runReturn(installSignalHandlers=False) # pylint: disable=E1101
    # pylint thinks reactor is missing runReturn
    Internal.reactor = reactor

    if Options.gui:
        from playfield import PlayField
        PlayField().show()
    else:
        from humanclient import HumanClient
        HumanClient()
    Internal.app.exec_()
