#!/usr/bin/env python3
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

# pylint: disable=wrong-import-position

# keyboardinterrupt should simply terminate
# import signal
# signal.signal(signal.SIGINT, signal.SIG_DFL)
import sys
import os
import logging

from qt import QObject
from PyQt5.QtGui import QGuiApplication
from PyQt5 import QtCore
from kde import KApplication, KCmdLineArgs, KCmdLineOptions, KGlobal
from mi18n import i18n
from about import About

from common import Options, SingleshotOptions, Internal, Debug
# do not import modules using twisted before our reactor is running

def initRulesets():
    """exits if user only wanted to see available rulesets"""
    import predefined
    predefined.load()
    if Options.showRulesets or Options.rulesetName:
        from rule import Ruleset
        rulesets = dict((x.name, x) for x in Ruleset.selectableRulesets())
        if Options.showRulesets:
            for name in rulesets:
                print(name)
            Internal.db.close()
            sys.exit(0)
        elif Options.rulesetName in rulesets:
            # we have an exact match
            Options.ruleset = rulesets[Options.rulesetName]
        else:
            matches = list(x for x in rulesets if Options.rulesetName in x)
            if len(matches) != 1:
                if not matches:
                    msg = 'Ruleset %s is unknown' % Options.rulesetName
                else:
                    msg = 'Ruleset %s is ambiguous: %s' % (
                        Options.rulesetName,
                        ', '.join(matches))
                Internal.db.close()
                raise SystemExit(msg)
            Options.ruleset = rulesets[matches[0]]


def defineOptions():
    """this is the KDE way. Compare with kajonggserver.py"""
    options = KCmdLineOptions()
    options.add(
        "playopen",
        i18n("all robots play with visible concealed tiles"))
    options.add("demo", i18n("start with demo mode"))
    options.add("host <HOST>", i18n("login to HOST"))
    options.add("table <TABLE>", i18n("start new TABLE"))
    options.add("join <TABLE>", i18n("join TABLE "))
    options.add("ruleset <RULESET>", i18n("use ruleset without asking"))
    options.add(
        "rounds <ROUNDS>",
        i18n("play one ROUNDS rounds per game. Only for debugging!"))
    options.add("player <PLAYER>", i18n("prefer PLAYER for next login"))
    options.add(
        "ai <AI>",
        i18n("use AI variant for human player in demo mode"))
    options.add("csv <CSV>", i18n("write statistics to CSV"))
    options.add("rulesets", i18n("show all available rulesets"))
    options.add("game <seed(/(firsthand)(..(lasthand))>",
                i18n("for testing purposes: Initializes the random generator"), "0")
    options.add(
        "nogui",
        i18n("show no graphical user interface. Intended only for testing"))
    options.add(
        "socket <SOCKET>",
        i18n("use a dedicated server listening on SOCKET. Intended only for testing"))
    options.add(
        "port <PORT>",
        i18n("use a dedicated server listening on PORT. Intended only for testing"))
    options.add("debug <OPTIONS>", Debug.help())
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
        Options.player = args.getOption('player')
    if args.isSet('rounds'):
        Options.rounds = int(args.getOption('rounds'))
    if args.isSet('ai'):
        Options.AI = str(args.getOption('ai'))
    if args.isSet('csv'):
        Options.csv = str(args.getOption('csv'))
    if args.isSet('socket'):
        Options.socket = str(args.getOption('socket'))
    if args.isSet('port'):
        Options.port = str(args.getOption('port'))
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
    Options.fixed = True  # may not be changed anymore


class EvHandler(QObject):

    """an application wide event handler"""

    def eventFilter(self, receiver, event):
        """will be called for all events"""
        from log import EventData
        EventData(receiver, event)
        return QObject.eventFilter(self, receiver, event)

from util import gitHead

if os.name == 'nt':
    _ = os.path.dirname(os.path.realpath(__file__))
    if _.endswith('.zip'):
        # cx_freeze
        os.chdir(os.path.dirname(_))

ABOUT = About()
KCmdLineArgs.init(sys.argv, ABOUT.about)
KCmdLineArgs.addCmdLineOptions(defineOptions())
APP = KApplication()
parseOptions()

if hasattr(QGuiApplication, 'setDesktopFileName'):
    QGuiApplication.setDesktopFileName('org.kde.kajongg')

if Debug.neutral:
    KGlobal.translation = None

if Debug.events:
    EVHANDLER = EvHandler()
    APP.installEventFilter(EVHANDLER)

from config import SetupPreferences
SetupPreferences()

if Options.csv:
    if gitHead() == 'current':
        Internal.logger.debug(
            'You cannot write to %s with changes uncommitted to git',
            Options.csv)
        sys.exit(2)
from mainwindow import MainWindow
QGuiApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
MainWindow()
Internal.app.exec_()
