# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

# pylint: disable=invalid-name

import inspect
from typing import TYPE_CHECKING, Optional

from twisted.internet.defer import Deferred, succeed

from kde import KMessageBox, KDialog

from qt import Qt, QDialog, QMessageBox, QWidget

from common import Options, Internal, isAlive, ReprMixin

if TYPE_CHECKING:
    from qt import QEvent, QKeyEvent, QPushButton, QIcon, QDialogButtonBox

class KDialogIgnoringEscape(KDialog):

    """as the name says"""

    def keyPressEvent(self, event:'QKeyEvent') ->None:
        """catch and ignore the Escape key"""
        if event.key() == Qt.Key.Key_Escape:
            event.ignore()
        else:
            KDialog.keyPressEvent(self, event)


class MustChooseKDialog(KDialogIgnoringEscape):

    """this dialog can only be closed if a choice has been done. Currently,
    the self.chosen thing is not used, code removed.
    So this dialog can only be closed by calling accept() or reject()"""

    def __init__(self) ->None:
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

    def closeEvent(self, event:'QEvent') ->None:
        """self.chosen is currently not used, never allow this"""
        event.ignore()


class Prompt(MustChooseKDialog, ReprMixin):

    """common code for things like QuestionYesNo, Information"""

    def __init__(self, msg:str, icon:'QIcon'=QMessageBox.Information,
                 buttons:'QDialogButtonBox.StandardButtons'=KDialog.Ok,
                 caption:Optional[str]=None, default:Optional['QPushButton']=None) ->None:
        """buttons is button codes or-ed like KDialog.Ok | KDialog.Cancel. First one is default."""
        if r'\n' in msg:
            print(r'*********************** Fix this! Prompt gets \n in', msg)
            msg = msg.replace(r'\n', '\n')
        self.msg = msg
        self.default = default
        if Options.gui:
            MustChooseKDialog.__init__(self)
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            self.setCaption(caption or '')
            KMessageBox.createKMessageBox(
                self, icon, msg,
                [], "", False,
                KMessageBox.Options(KMessageBox.NoExec | KMessageBox.AllowLink))
            self.setButtons(buttons)
            # buttons is either Yes/No or Ok
            defaultButton = KDialog.Yes if KDialog.Yes & buttons else KDialog.Ok
            assert defaultButton & buttons, buttons
            self.button(defaultButton).setFocus()

    def returns(self, button:Optional['QPushButton']=None) ->bool:
        """the user answered"""
        if button is None:
            button = self.default
        return button in (KDialog.Yes, KDialog.Ok)

    def __str__(self) ->str:
        return self.msg


class DeferredDialog(Deferred):

    """make dialogs usable as Deferred"""

    def __init__(self, dlg:QDialog, modal:bool=True, always:bool=False) ->None:
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
        if hasattr(Internal, 'reactor'):
            # sometimes pylint 2.7.2 warns, sometimes not
            Internal.reactor.callLater(0, self.__execute)
        else:
            # we do not yet have a reactor in initDb()
            self.__execute()

    def __execute(self) ->None:
        """now do the actual action"""
        if self.dlg is None:
            return
        scene = Internal.scene
        if not Options.gui or not isAlive(self.dlg):
            self.clicked()
            return
        autoPlay = bool(scene and scene.game and scene.game.autoPlay)
        autoAnswerDelayed = autoPlay and not self.always
        if self.modal and not autoAnswerDelayed:
            self.dlg.exec_()
        else:
            self.dlg.show()
        if autoAnswerDelayed:
            assert Internal.Preferences
            Internal.reactor.callLater(
                Internal.Preferences.animationDuration() / 500.0,
                self.clicked)

    def clicked(self, button:Optional['QPushButton']=None) ->None:
        """we got a reaction"""
        if self.dlg:
            result = self.dlg.returns(button)
        else:
            result = None
        self.__removeFromScene()
        self.callback(result)

    def cancel(self) ->None:
        """we want no answer, just let the dialog disappear"""
        self.__removeFromScene()
        Deferred.cancel(self)

    def __removeFromScene(self) ->None:
        """remove ourself"""
        if self.dlg and Internal.scene and isAlive(self.dlg):
            self.dlg.hide()
        self.dlg = None


class QuestionYesNo(DeferredDialog):

    """wrapper, see class Prompt"""

    def __init__(self, msg:str, modal:bool=True, always:bool=False, caption:Optional[str]=None) ->None:
        dialog = Prompt(msg, icon=QMessageBox.Question,
                        buttons=KDialog.Yes | KDialog.No, default=KDialog.Yes, caption=caption)
        DeferredDialog.__init__(self, dialog, modal=modal, always=always)


class WarningYesNo(DeferredDialog):

    """wrapper, see class Prompt"""

    def __init__(self, msg:str, modal:bool=True, caption:Optional[str]=None) ->None:
        dialog = Prompt(msg, icon=QMessageBox.Warning,
                        buttons=KDialog.Yes | KDialog.No, default=KDialog.Yes, caption=caption)
        DeferredDialog.__init__(self, dialog, modal=modal)


class Information(DeferredDialog):

    """wrapper, see class Prompt"""

    def __init__(self, msg:str, modal:bool=True, caption:Optional[str]=None) ->None:
        dialog = Prompt(msg, icon=QMessageBox.Information,
                        buttons=KDialog.Ok, caption=caption)
        DeferredDialog.__init__(self, dialog, modal=modal)


class Sorry(DeferredDialog):

    """wrapper, see class Prompt"""

    def __init__(self, msg:str, modal:bool=True, caption:Optional[str]=None, always:bool=False) ->None:
        dialog = Prompt(msg, icon=QMessageBox.Information,
                        buttons=KDialog.Ok, caption=caption or 'Sorry')
        DeferredDialog.__init__(self, dialog, modal=modal, always=always)


def NoPrompt(unusedMsg:str) ->Deferred:
    """we just want to be able to add callbacks even if non-interactive"""
    return succeed(None)
