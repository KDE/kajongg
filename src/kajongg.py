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

#from __future__  import print_function, unicode_literals, division

import sys
from query import InitDb
from about import About
from PyKDE4.kdecore import KCmdLineArgs, KCmdLineOptions, ki18n
from PyKDE4.kdeui import KApplication

from util import InternalParameters

# do not import modules using twisted before our reactor is running

def main(reactor, app):
    """from guidance-power-manager.py:
    the old "not destroying KApplication last"
    make a real main(), and make app global. app will then be the last thing deleted (C++)
    """
    InitDb()
    from playfield import PlayField
    mainWindow =  PlayField(reactor, app)
    mainWindow.show()
    app.exec_()

if __name__ == "__main__":
    ABOUT = About()
    KCmdLineArgs.init (sys.argv, ABOUT.about)
    options = KCmdLineOptions()
    options.add(str("automode"), ki18n("play like a robot"))
    options.add(str("showsql"), ki18n("show database SQL commands"))
    KCmdLineArgs.addCmdLineOptions(options)
    APP = KApplication()
    args = KCmdLineArgs.parsedArgs()
    import util
    from config import Preferences
    Preferences()
    InternalParameters.autoMode |= args.isSet('automode')
    InternalParameters.showSql |= args.isSet('showsql')
    import qt4reactor
    qt4reactor.install()
    from twisted.internet import reactor
    reactor.runReturn(installSignalHandlers=False)
    main(reactor, APP)
