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
from about import About
from kde import ki18n, KApplication, KCmdLineArgs, KCmdLineOptions

from util import m18n
from common import InternalParameters, Debug

# do not import modules using twisted before our reactor is running
# do not import util directly or indirectly before InternalParameters.app
# is set

# pylint: disable=W0404
# pylint does not like imports within functions

def main(myReactor):
    """from guidance-power-manager.py:
    the old "not destroying KApplication last"
    make a real main(), and make app global. app will then be the last thing deleted (C++)
    """
    from query import Query, initDb
    Query.dbhandle = initDb()
    InternalParameters.reactor = myReactor
    from predefined import loadPredefinedRulesets
    loadPredefinedRulesets()
    if InternalParameters.showRulesets or InternalParameters.autoPlayRulesetName:
        from scoringengine import Ruleset
        from util import kprint
        rulesets = Ruleset.selectableRulesets()
        if InternalParameters.showRulesets:
            for ruleset in rulesets:
                kprint(ruleset.name)
            return
        else:
            for ruleset in rulesets:
                if ruleset.name == InternalParameters.autoPlayRulesetName:
                    InternalParameters.autoPlayRuleset = ruleset
                    break
            else:
                kprint('Ruleset %s is unknown' % InternalParameters.autoPlayRulesetName)
                return 1
    if InternalParameters.hasGUI:
        from playfield import PlayField
        PlayField().show()
    else:
        from humanclient import HumanClient
        HumanClient()
    InternalParameters.app.exec_()

def defineOptions():
    """this is the KDE way. Compare with kajonggserver.py"""
    options = KCmdLineOptions()
    options.add("playopen", ki18n("all robots play with visible concealed tiles"))
    options.add("autoplay <ruleset>", ki18n("play like a robot using ruleset"))
    # we need a KLocalizedString for ai but we are in
    # a string freeze. Since no end user starts kajongg from
    # the command line, prevent translation for now
    msg = "use AI variant for human player in demo mode"
    options.add("ai <AI>", ki18n(msg))
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
    InternalParameters.app = APP
    InternalParameters.playOpen |= args.isSet('playopen')
    InternalParameters.showRulesets|= args.isSet('rulesets')
    InternalParameters.autoPlay |= args.isSet('autoplay')
    InternalParameters.autoPlayRulesetName = str(args.getOption('autoplay'))
    if args.isSet('ai'):
        InternalParameters.AI = str(args.getOption('ai'))
    if args.isSet('csv'):
        InternalParameters.csv = str(args.getOption('csv'))
    if args.isSet('socket'):
        InternalParameters.socket = str(args.getOption('socket'))
    InternalParameters.game = str(args.getOption('game'))
    InternalParameters.hasGUI |= args.isSet('gui')
    if not InternalParameters.hasGUI and '/' in InternalParameters.game:
        print m18n('You cannot specify hand/discard with --game when starting with --nogui')
        sys.exit(2)
    msg = Debug.setOptions(str(args.getOption('debug')))
    if msg:
        print msg
        sys.exit(2)

if __name__ == "__main__":
    from util import initLog
    initLog('kajongg')
    ABOUT = About()
    KCmdLineArgs.init (sys.argv, ABOUT.about)
    KCmdLineArgs.addCmdLineOptions(defineOptions())
    KApplication.setGraphicsSystem('raster')
    APP = KApplication()
            # KApplication() says
            # QWidget: Cannot create a QWidget when no GUI is being used
    parseOptions()
    from config import Preferences
    Preferences()
    import qt4reactor
    qt4reactor.install()
    from twisted.internet import reactor
    reactor.runReturn(installSignalHandlers=False) # pylint: disable=E1101
    # pylint thinks reactor is missing runReturn

    sys.exit(main(reactor))
