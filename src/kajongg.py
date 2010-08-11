#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008,2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

import syslog
syslog.openlog('kajongg')

import sys
from about import About
from PyKDE4.kdecore import KCmdLineArgs, KCmdLineOptions, ki18n
from PyKDE4.kdeui import KApplication

from common import InternalParameters


# do not import modules using twisted before our reactor is running

def main(myReactor):
    """from guidance-power-manager.py:
    the old "not destroying KApplication last"
    make a real main(), and make app global. app will then be the last thing deleted (C++)
    """
    from query import initDb
    initDb()
    InternalParameters.reactor = myReactor
    from predefined import loadPredefinedRulesets
    loadPredefinedRulesets()
    if InternalParameters.hasGUI:
        from playfield import PlayField
        PlayField().show()
    else:
        from tables import TableList
        TableList()
    InternalParameters.app.exec_()

def defineOptions():
    """this is the KDE way. Compare with kajonggserver.py"""
    options = KCmdLineOptions()
    options.add("playopen", ki18n("all robots play with visible concealed tiles"))
    options.add("autoplay <ruleset>", ki18n("play like a robot using ruleset"))
    options.add("showtraffic", ki18n("show traffic with game server"))
    options.add("showsql", ki18n("show database SQL commands"))
    options.add("seed <seed>", ki18n("for testing purposes: Initializes the random generator"), "0")
    options.add("nogui", ki18n("show no graphical user interface. Intended only for testing"))
    return options

def parseOptions():
    """parse command line options and save the values"""
    args = KCmdLineArgs.parsedArgs()
    InternalParameters.app = APP
    InternalParameters.playOpen |= args.isSet('playopen')
    InternalParameters.autoPlay |= args.isSet('autoplay')
    InternalParameters.autoPlayRuleset = str(args.getOption('autoplay'))
    InternalParameters.showTraffic |= args.isSet('showtraffic')
    InternalParameters.showSql |= args.isSet('showsql')
    InternalParameters.seed = int(args.getOption('seed'))
    InternalParameters.hasGUI |= args.isSet('gui')

if __name__ == "__main__":
    ABOUT = About()
    KCmdLineArgs.init (sys.argv, ABOUT.about)
    KCmdLineArgs.addCmdLineOptions(defineOptions())
    APP = KApplication()
    parseOptions()
    from config import Preferences
    Preferences()
    import qt4reactor
    qt4reactor.install()
    from twisted.internet import reactor
    reactor.runReturn(installSignalHandlers=False) # pylint: disable-msg=E1101
    # pylint thinks reactor is missing runReturn

    main(reactor)
