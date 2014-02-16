#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2014 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
#import signal
#signal.signal(signal.SIGINT, signal.SIG_DFL)
import sys, logging

from qt import QObject, usingQt4
from kde import ki18n, KApplication, KCmdLineArgs, KCmdLineOptions
from about import About

from common import Options, SingleshotOptions, Internal, Debug
from util import kprint

# do not import modules using twisted before our reactor is running

def initRulesets():
    """exits if user only wanted to see available rulesets"""
    import predefined # pylint: disable=unused-variable
    if Options.showRulesets or Options.rulesetName:
        from rule import Ruleset
        rulesets = dict((x.name, x) for x in Ruleset.selectableRulesets())
        if Options.showRulesets:
            for name in rulesets:
                kprint(name)
            Internal.db.close()
            sys.exit(0)
        elif Options.rulesetName in rulesets:
            # we have an exact match
            Options.ruleset = rulesets[Options.rulesetName]
        else:
            matches = list(x for x in rulesets if Options.rulesetName in x)
            if len(matches) != 1:
                if len(matches) == 0:
                    msg = 'Ruleset %s is unknown' % Options.rulesetName
                else:
                    msg = 'Ruleset %s is ambiguous: %s' % (Options.rulesetName, ', '.join(matches))
                Internal.db.close()
                raise SystemExit(msg)
            Options.ruleset = rulesets[matches[0]]

def defineOptions():
    """this is the KDE way. Compare with kajonggserver.py"""
    options = KCmdLineOptions()
    options.add("playopen", ki18n("all robots play with visible concealed tiles"))
    options.add("demo", ki18n("start with demo mode"))
    options.add("host <HOST>", ki18n("login to HOST"))
    options.add("table <TABLE>", ki18n("start new TABLE"))
    options.add("join <TABLE>", ki18n("join TABLE "))
    options.add("ruleset <RULESET>", ki18n("use ruleset without asking"))
    options.add("rounds <ROUNDS>", ki18n("play one ROUNDS rounds per game. Only for debugging!"))
    options.add("player <PLAYER>", ki18n("prefer PLAYER for next login"))
    options.add("ai <AI>", ki18n("use AI variant for human player in demo mode"))
    options.add("csv <CSV>", ki18n("write statistics to CSV"))
    options.add("rulesets", ki18n("show all available rulesets"))
    options.add("game <seed(/(firsthand)(..(lasthand))>",
        ki18n("for testing purposes: Initializes the random generator"), "0")
    options.add("nogui", ki18n("show no graphical user interface. Intended only for testing"))
    options.add("nokde", ki18n("Do not use KDE bindings. Intended only for testing"))
    options.add("qt5", ki18n("Force using Qt5. Currently Qt4 is used by default"))
    options.add("socket <SOCKET>", ki18n("use a dedicated server listening on SOCKET. Intended only for testing"))
    options.add("debug <OPTIONS>", ki18n(Debug.help()))
    return options

def parseOptions():
    """parse command line options and save the values"""
    args = KCmdLineArgs.parsedArgs()
    Internal.app = APP
    Options.playOpen |= args.isSet('playopen')
    Options.showRulesets |= args.isSet('rulesets')
    Options.rulesetName = str(args.getOption('ruleset'))
    if args.isSet('host'):
        Options.host = str(args.getOption('host'))
    if args.isSet('player'):
        Options.player = str(args.getOption('player'))
    if args.isSet('rounds'):
        Options.rounds = str(args.getOption('rounds'))
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
        Internal.logger.debug(msg)
        logging.shutdown()
        sys.exit(2)
    from query import initDb
    if not initDb():
        raise SystemExit('Cannot initialize database')
    initRulesets()
    Options.fixed = True # may not be changed anymore

class EvHandler(QObject):
    """an application wide event handler"""

    def eventFilter(self, receiver, event):
        """will be called for all events"""
        from log import EventData
        EventData(receiver, event)
        return QObject.eventFilter(self, receiver, event)

if __name__ == "__main__":
    from util import gitHead

    ABOUT = About()
    KCmdLineArgs.init(sys.argv, ABOUT.about)
    KCmdLineArgs.addCmdLineOptions(defineOptions())
    if usingQt4:
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
    reactor.runReturn(installSignalHandlers=False)
    Internal.reactor = reactor

    if Options.csv:
        if gitHead() == 'current':
            Internal.logger.debug('You cannot write to %s with changes uncommitted to git' % Options.csv)
            sys.exit(2)
    from mainwindow import MainWindow
    MainWindow()
    Internal.app.exec_()
