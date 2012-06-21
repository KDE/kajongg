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

# pylint: disable=C0103,W0611
# invalid names, unused imports

from PyQt4.QtCore import Qt
from PyQt4.QtGui import QLabel, QVBoxLayout, QDialog, QDialogButtonBox

from PyKDE4.kdecore import KUser, KGlobal, KStandardDirs, \
    KAboutData, KCmdLineArgs, KConfig, KConfigGroup, \
    KCmdLineOptions


from PyKDE4.kdecore import i18n, i18nc, ki18n
from PyKDE4.kdeui import KMessageBox, KIcon, KLineEdit, \
    KConfigSkeleton, KDialogButtonBox, KAction, KStandardAction, \
    KApplication, KToggleFullScreenAction, KXmlGuiWindow, \
    KConfigDialog

from twisted.internet.defer import Deferred

from common import InternalParameters

class Prompt(Deferred):
    """we need to wrap the synchronous KMessageBox.XX calls with
    a deferred, or twisted-banana does strange things - it tries
    to parse the last part of the previous message as a new
    message and says list expression expected"""
    method = str # just some dummy
    def __init__(self, msg, callback=None, *cbargs, **cbkw):
        Deferred.__init__(self)
        self.msg = msg
        if callback:
            self.addCallback(callback, *cbargs, **cbkw)
        InternalParameters.reactor.callLater(0, self.__execute)

    def __execute(self):
        """now do the actual action"""
        self.callback(self.method(None, self.msg) in (KMessageBox.Yes, KMessageBox.Ok))

class QuestionYesNo(Prompt):
    """wrapper, see class Prompt"""
    method = KMessageBox.questionYesNo

class WarningYesNo(Prompt):
    """wrapper, see class Prompt"""
    method = KMessageBox.warningYesNo

class Information(Prompt):
    """wrapper, see class Prompt"""
    method = KMessageBox.information

class Sorry(Prompt):
    """wrapper, see class Prompt"""
    method = KMessageBox.sorry
