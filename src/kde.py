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

import common
from common import Internal, isAlive

class IgnoreEscape(object):
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

class MustChooseDialog(DialogIgnoringEscape):
    """this dialog can only be closed if a choice has been done"""
    def __init__(self, parent=None):
        DialogIgnoringEscape.__init__(self, parent)
        self.chosen = None

    def closeEvent(self, event):
        """allow close only if a choice has been done"""
        if self.chosen is not None:
            event.accept()
        else:
            event.ignore()

class MustChooseKDialog(KDialogIgnoringEscape):
    """this dialog can only be closed if a choice has been done"""
    def __init__(self, parent=None):
        KDialogIgnoringEscape.__init__(self, parent)
        self.chosen = None

    def closeEvent(self, event):
        """allow close only if a choice has been done"""
        if self.chosen is not None:
            event.accept()
        else:
            event.ignore()

class Prompt(MustChooseKDialog):
    """common code for things like QuestionYesNo, Information"""
    def __init__(self, msg, icon=QMessageBox.Information, buttons=KDialog.Ok, caption=None, default=None):
        """buttons is button codes or-ed like KDialog.Ok | KDialog.Cancel. First one is default."""
        self.msg = msg
        self.default = default
        if Internal.field:
            MustChooseKDialog.__init__(self, Internal.field)
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            if caption:
                caption += ' - Kajongg'
            else:
                caption = 'Kajongg'
            self.setCaption(caption)
            KMessageBox.createKMessageBox(self, icon, msg,
                QStringList(), "", False, KMessageBox.NoExec)
            self.setButtons(KDialog.ButtonCode(buttons))

    def returns(self, button=None):
        """the user answered"""
        if button is None:
            button = self.default
        return button in (KDialog.Yes, KDialog.Ok)

class DeferredDialog(Deferred):
    """make dialogs usable as Deferred"""
    def __init__(self, dlg, modal=True, always=False):
        Deferred.__init__(self)
        self.dlg = dlg
        self.modal = modal
        self.always = always
        if Internal.field:
            if hasattr(self.dlg, 'buttonClicked'):
                self.dlg.buttonClicked.connect(self.clicked)
            else:
                self.dlg.accepted.connect(self.clicked)
                self.dlg.rejected.connect(self.cancel)
        if Internal.reactor:
            # pylint: disable=E1101
            Internal.reactor.callLater(0, self.__execute)
        else:
            # we do not yet have a reactor in initDb()
            self.__execute()

    def __execute(self):
        """now do the actual action"""
        if self.dlg is None:
            return
        field = Internal.field
        if not field or not isAlive(self.dlg):
            return self.autoAnswer()
        autoPlay = field.game and field.game.autoPlay
        autoAnswerDelayed = autoPlay and not self.always
        if self.modal and not autoAnswerDelayed:
            self.dlg.exec_()
        else:
            self.dlg.show()
        if autoAnswerDelayed:
            # pylint: disable=E1101
            Internal.reactor.callLater(common.Preferences.animationDuration()/ 500.0,
                self.autoAnswer)

    def autoAnswer(self):
        """autoPlay gets autoAnswer"""
        result = self.dlg.returns()
        if Internal.field and isAlive(self.dlg):
            self.dlg.hide()
        self.dlg = None
        self.callback(result)

    def clicked(self, button=None):
        """we got a reaction"""
        assert self.dlg
        if self.dlg:
            result = self.dlg.returns(button)
            self.dlg.hide()
            self.dlg = None
            self.callback(result)

    def cancel(self):
        """we want no answer, just let the dialog disappear"""
        if self.dlg:
            self.dlg.hide()
        self.dlg = None
        Deferred.cancel(self)

class QuestionYesNo(DeferredDialog):
    """wrapper, see class Prompt"""
    def __init__(self, msg, modal=True, always=False, caption=None):
        dialog = Prompt(msg, icon=QMessageBox.Question,
            buttons=KDialog.Yes | KDialog.No, default=KDialog.Yes, caption=caption)
        DeferredDialog.__init__(self, dialog, modal=modal, always=always)

class WarningYesNo(DeferredDialog):
    """wrapper, see class Prompt"""
    def __init__(self, msg, modal=True, caption=None):
        dialog = Prompt(msg, icon=QMessageBox.Warning,
            buttons=KDialog.Yes | KDialog.No, default=KDialog.Yes, caption=caption)
        DeferredDialog.__init__(self, dialog, modal=modal)

class Information(DeferredDialog):
    """wrapper, see class Prompt"""
    def __init__(self, msg, modal=True, caption=None):
        dialog = Prompt(msg, icon=QMessageBox.Information,
            buttons=KDialog.Ok, caption=caption)
        DeferredDialog.__init__(self, dialog, modal=modal)

class Sorry(DeferredDialog):
    """wrapper, see class Prompt"""
    def __init__(self, msg, modal=True, caption=None):
        dialog = Prompt(msg, icon=QMessageBox.Information,
            buttons=KDialog.Ok, caption=caption or 'Sorry')
        DeferredDialog.__init__(self, dialog, modal=modal)

def NoPrompt(dummyMsg):
    """we just want to be able to add callbacks even if non-interactive"""
    return succeed(None)
