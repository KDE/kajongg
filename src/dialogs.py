# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

# pylint: disable=invalid-name

import inspect

from twisted.internet.defer import Deferred, succeed

from kde import KMessageBox, KDialog

from qt import Qt, QDialog, QMessageBox, QWidget

from common import Options, Internal, isAlive, ReprMixin


class IgnoreEscape:

    """as the name says. Use as a mixin for dialogs"""

    def keyPressEvent(self, event):
        """catch and ignore the Escape key"""
        if event.key() == Qt.Key_Escape:
            event.ignore()
        else:
            # pass on to the first declared ancestor class which
            # currently is either KDialog or QDialog
            _ = self.__class__.__mro__[1]
            assert isinstance(_, QDialog), 'dialog is:{} {}'.format(type(_), repr(_))
            _.keyPressEvent(self, event)


class KDialogIgnoringEscape(KDialog, IgnoreEscape):

    """as the name says"""


class MustChooseKDialog(KDialogIgnoringEscape):

    """this dialog can only be closed if a choice has been done. Currently,
    the self.chosen thing is not used, code removed.
    So this dialog can only be closed by calling accept() or reject()"""

    def __init__(self):
        parent = Internal.mainWindow  # default
        # if we are (maybe indirectly) called from a method belonging to a QWidget, take that as parent
        # this does probably not work for classmethod or staticmethod but it is
        # good enough right now
        for frametuple in inspect.getouterframes(inspect.currentframe())[1:]:
            if 'self' in frametuple[0].f_locals:
                obj = frametuple[0].f_locals['self']
                if isinstance(obj, QWidget) and not isinstance(obj, QDialog) and isAlive(obj):
                    parent = obj
                    break
        if not isAlive(parent):
            parent = None
        KDialogIgnoringEscape.__init__(self, parent)

    def closeEvent(self, event):
        """self.chosen is currently not used, never allow this"""
        event.ignore()


class Prompt(MustChooseKDialog, ReprMixin):

    """common code for things like QuestionYesNo, Information"""

    def __init__(self, msg, icon=QMessageBox.Information,
                 buttons=KDialog.Ok, caption=None, default=None):
        """buttons is button codes or-ed like KDialog.Ok | KDialog.Cancel. First one is default."""
        if r'\n' in msg:
            print(r'*********************** Fix this! Prompt gets \n in', msg)
            msg = msg.replace(r'\n', '\n')
        self.msg = msg
        self.default = default
        if Options.gui:
            MustChooseKDialog.__init__(self)
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.setCaption(caption or '')
            KMessageBox.createKMessageBox(
                self, icon, msg,
                [], "", False,
                KMessageBox.Options(KMessageBox.NoExec | KMessageBox.AllowLink))
            self.setButtons(KDialog.ButtonCode(buttons))
            # buttons is either Yes/No or Ok
            defaultButton = KDialog.Yes if KDialog.Yes & buttons else KDialog.Ok
            assert defaultButton & buttons, buttons
            self.button(defaultButton).setFocus()

    def returns(self, button=None):
        """the user answered"""
        if button is None:
            button = self.default
        return button in (KDialog.Yes, KDialog.Ok)

    def __str__(self):
        return self.msg


class DeferredDialog(Deferred):

    """make dialogs usable as Deferred"""

    def __init__(self, dlg, modal=True, always=False):
        Deferred.__init__(self)
        self.dlg = dlg
        self.modal = modal
        self.always = always
        if Options.gui:
            if hasattr(self.dlg, 'buttonClicked'):
                self.dlg.buttonClicked.connect(self.clicked)
            else:
                self.dlg.accepted.connect(self.clicked)
                self.dlg.rejected.connect(self.cancel)
        if Internal.reactor:
            # sometimes pylint 2.7.2 warns, sometimes not
            Internal.reactor.callLater(0, self.__execute)
        else:
            # we do not yet have a reactor in initDb()
            self.__execute()

    def __execute(self):
        """now do the actual action"""
        if self.dlg is None:
            return None
        scene = Internal.scene
        if not Options.gui or not isAlive(self.dlg):
            return self.clicked()
        autoPlay = scene and scene.game and scene.game.autoPlay
        autoAnswerDelayed = autoPlay and not self.always
        if self.modal and not autoAnswerDelayed:
            self.dlg.exec_()
        else:
            self.dlg.show()
        if autoAnswerDelayed:
            Internal.reactor.callLater(
                Internal.Preferences.animationDuration() / 500.0,
                self.clicked)
        return None

    def clicked(self, button=None):
        """we got a reaction"""
        if self.dlg:
            result = self.dlg.returns(button)
        else:
            result = None
        self.__removeFromScene()
        self.callback(result)

    def cancel(self):
        """we want no answer, just let the dialog disappear"""
        self.__removeFromScene()
        Deferred.cancel(self)

    def __removeFromScene(self):
        """remove ourself"""
        if self.dlg and Internal.scene and isAlive(self.dlg):
            self.dlg.hide()
        self.dlg = None


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

    def __init__(self, msg, modal=True, caption=None, always=False):
        dialog = Prompt(msg, icon=QMessageBox.Information,
                        buttons=KDialog.Ok, caption=caption or 'Sorry')
        DeferredDialog.__init__(self, dialog, modal=modal, always=always)


def NoPrompt(unusedMsg):
    """we just want to be able to add callbacks even if non-interactive"""
    return succeed(None)
