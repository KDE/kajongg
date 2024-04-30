#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

# pylint: disable=wrong-import-position

import sys
import os
import logging
from typing import Tuple, List, Optional, Type, Any

from qtpy import QT5
from qt import QObject, QCommandLineParser, QCommandLineOption, Qt, QGuiApplication
from kde import KApplication
from mi18n import i18n, MLocale

from common import Options, SingleshotOptions, Internal, Debug
# do not import modules using twisted before our reactor is running

def __initRulesetsOrExit() ->None:
    """exits if user only wanted to see available rulesets
    or if the given ruleset does not exist"""
    import predefined
    predefined.load()
    if Options.showRulesets or Options.rulesetName:
        from rule import Ruleset
        rulesets = {x.name: x for x in Ruleset.selectableRulesets()}
        if Options.showRulesets:
            for name in rulesets:
                print(name)
            Internal.db.close()
            sys.exit(0)
        elif Options.rulesetName in rulesets:
            # we have an exact match
            Options.ruleset = rulesets[Options.rulesetName]
        else:
            matches = [x for x in rulesets if Options.rulesetName in x]
            if len(matches) != 1:
                if not matches:
                    msg = f'Ruleset {Options.rulesetName} is unknown'
                else:
                    msg = f"Ruleset {Options.rulesetName} is ambiguous: {', '.join(matches)}"
                Internal.db.close()
                raise SystemExit(msg)
            Options.ruleset = rulesets[matches[0]]


class CommandLineOption(QCommandLineOption):
    """add some helping attributes"""
    def __init__(self, name : str, description : str, valueName : Optional[str] =None,
        defaultValue : Optional[str]=None, optName : Optional[str]=None,
        argType : Optional[Type]=None, singleshot:bool=False) ->None:
        QCommandLineOption.__init__(self, [name], description, valueName or '', defaultValue or '')
        if argType is None:
            if valueName is None:
                argType = bool
            else:
                argType = str
        self.argType = argType
        self.optName = optName or name
        self.singleshot = singleshot

def defineOptions() -> Tuple[QCommandLineParser, List[CommandLineOption]]:
    """define command line options"""
    parser = QCommandLineParser()
    options = []
    def option(name:str, description:str, valueName:Optional[str]=None, defaultValue:Optional[str]=None,
        optName:Optional[str]=None, argType:Optional[Type]=None, singleshot:bool=False) ->None:
        """helper"""
        opt = CommandLineOption(name, description, valueName, defaultValue,
            optName=optName, argType=argType, singleshot=singleshot)
        options.append(opt)
        parser.addOption(opt)

    parser.setApplicationDescription(i18n('Mah Jongg - the ancient Chinese board game for 4 players'))

    parser.addHelpOption()
    parser.addVersionOption()
    option('playopen', i18n('all robots play with visible concealed tiles'), optName='playOpen')
    option('demo', i18n('start with demo mode'))
    option('host', i18n("login to HOST"), 'HOST', '')
    option('table', i18n('start new TABLE'), 'TABLE', '1', argType=int, singleshot=True)
    option('join', i18n('join TABLE'), 'TABLE', '1', argType=int, singleshot=True)
    option('ruleset', i18n('use RULESET without asking'), 'RULESET', '', optName='rulesetName')
    option('player', i18n('prefer PLAYER for next login'), 'PLAYER', '')
    option('ai', i18n('use AI variant for human player in demo mode'), 'AI', '', optName='AI')
    option('csv', i18n('write statistics to CSV'), 'CSV', '')
    option('rulesets', i18n('show all available rulesets'), optName='showRulesets')
    option('game', i18n('for testing purposes: Initializes the random generator'),
           'seed(/firsthand)(..(lasthand))', '0')
    option('nogui', i18n('show no graphical user interface. Intended only for testing'), optName='gui')
    option('socket', i18n(
        'use a dedicated server already running and listening on SOCKET. Intended only for testing'), 'SOCKET', '')
    option('port', i18n(
        'use a dedicated server already running and listening on PORT. Intended only for testing'), 'PORT', '')
    option('debug', Debug.help(), 'DEBUG', '')
    return parser, options

def parseOptions() ->None:
    """parse command line options and save the values"""
    Options.gui = True
    parser, options = defineOptions()
    parser.process(Internal.app)
    for option in options:
        if parser.isSet(option):
            value = parser.value(option)
            if option.optName == 'debug':
                msg = Debug.setOptions(value)
                if msg:
                    Internal.logger.debug(msg)
                    logging.shutdown()
                    sys.exit(2)
                continue
            target: Type
            if option.optName in SingleshotOptions.__dict__:
                target = SingleshotOptions
            else:
                target = Options
            if option.argType is bool:
                setattr(target, option.optName, not option.names()[0].startswith('no'))
            elif option.argType is int:
                setattr(target, option.optName, int(value))
            else:
                setattr(target, option.optName, value)

    Options.demo |= not Options.gui
    Internal.autoPlay = Options.demo

    from query import initDb
    if not initDb():
        raise SystemExit('Cannot initialize database')
    __initRulesetsOrExit()
    Options.fixed = True  # may not be changed anymore


class EvHandler(QObject):

    """an application wide event handler"""

    def eventFilter(self, receiver: Any, event: Any) ->bool:
        """will be called for all events"""
        from log import EventData
        EventData(receiver, event)
        return QObject.eventFilter(self, receiver, event)

from util import gitHead

if sys.platform == 'win32':
    _ = os.path.dirname(os.path.realpath(__file__))
    if _.endswith('.zip'):
        # cx_freeze
        os.chdir(os.path.dirname(_))

QGuiApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

Internal.app = KApplication()
parseOptions()

if hasattr(QGuiApplication, 'setDesktopFileName'):
    QGuiApplication.setDesktopFileName('org.kde.kajongg')

if Debug.neutral:
    MLocale.translation = None

if Debug.locate:
    # this has been read before Debug.locate is set
    Internal.logger.debug('Configuration in %s', Internal.kajonggrc.path)

if Debug.events:
    EVHANDLER = EvHandler()
    Internal.app.installEventFilter(EVHANDLER)

from config import SetupPreferences
SetupPreferences()

if Options.csv:
    if gitHead() == 'current':
        Internal.logger.debug(
            'You cannot write to %s with changes uncommitted to git',
            Options.csv)
        sys.exit(2)

from mainwindow import MainWindow
if QT5:
    QGuiApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)  # type:ignore[attr-defined]
MainWindow()
Internal.app.exec()
