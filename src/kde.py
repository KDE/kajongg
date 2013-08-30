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

from PyQt4.QtCore import Qt, QStringList
from PyQt4.QtGui import QDialog, QMessageBox

from PyKDE4.kdecore import KUser, KGlobal, KStandardDirs, \
    KAboutData, KCmdLineArgs, KConfig, KConfigGroup, \
    KCmdLineOptions


from PyKDE4.kdecore import i18n, i18nc, ki18n
from PyKDE4.kdeui import KMessageBox, KIcon, KLineEdit, \
    KConfigSkeleton, KDialogButtonBox, KAction, KStandardAction, \
    KApplication, KToggleFullScreenAction, KXmlGuiWindow, \
    KConfigDialog, KDialog

from twisted.internet.defer import Deferred, succeed

from common import InternalParameters

class IgnoreEscape:
    """as the name says. Use as a mixin for dialogs"""
    # pylint: disable=W0232
    # we do not need __init__
    def keyPressEvent(self, event):
        """catch and ignore the Escape key"""
        if event.key() == Qt.Key_Escape:
            event.ignore()
        else:
            # pass on to the first declared ancestor class which
            # currently is either KDialog or QDialog
            self.__class__.__mro__[1].keyPressEvent(self, event) # pylint: disable=E1101

class DialogIgnoringEscape(QDialog, IgnoreEscape):
    """as the name says"""

class KDialogIgnoringEscape(KDialog, IgnoreEscape):
    """as the name says"""

class Prompt(Deferred):
    """we need to wrap the synchronous KMessageBox.XX calls with
    a deferred, or twisted-banana does strange things - it tries
    to parse the last part of the previous message as a new
    message and says list expression expected"""
    method = str # just some dummy
    def __init__(self, msg, caption=None):
        Deferred.__init__(self)
        self.msg = msg
        self.caption = caption or ''
        assert isinstance(self.caption, basestring), repr(self.caption)
        if InternalParameters.reactor:
            InternalParameters.reactor.callLater(0, self.__execute)
        else:
            self.__execute()

    def __execute(self):
        """now do the actual action"""
        self.callback(self.method(None, self.msg, self.caption) in (KMessageBox.Yes, KMessageBox.Ok))

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

class NonModalInformation(Deferred):
    """tell/ask user non modally"""
    def __init__(self, msg):
        Deferred.__init__(self)
        dlg = KDialogIgnoringEscape(InternalParameters.field)
        dlg.setButtons(KDialog.Ok)
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowStaysOnTopHint)
        dlg.setCaption('Kajongg')
        dlg.accepted.connect(self.accepted)
        dlg.rejected.connect(self.accepted)
        KMessageBox.createKMessageBox(dlg, QMessageBox.Question,
            msg, QStringList(), "", False, KMessageBox.NoExec)
        dlg.show()

    def accepted(self):
        """or rejected"""
        self.callback(True)

def NoPrompt(dummyMsg):
    """we just want to be able to add callbacks even if non-interactive"""
    return succeed(None)
