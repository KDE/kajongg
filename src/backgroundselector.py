"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

partially based on C++ code from:
Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

SPDX-License-Identifier: GPL-2.0

"""

from qt import QWidget, QLineEdit
from background import Background
from common import Internal
from guiutil import loadUi


class BackgroundSelector(QWidget):

    """presents all available backgrounds with previews"""

    def __init__(self, parent:QWidget) ->None:
        super().__init__(parent)
        loadUi(self)
        self.kcfg_backgroundName = QLineEdit(self)
        self.kcfg_backgroundName.setVisible(False)
        self.kcfg_backgroundName.setObjectName('kcfg_backgroundName')
        self.setUp()

    def setUp(self) ->None:
        """fill the selector"""

        # The lineEdit widget holds our background path, but the user does
        # not manipulate it directly
        self.kcfg_backgroundName.hide()

        self.backgroundNameList.currentRowChanged.connect(
            self.backgroundRowChanged)
        self.kcfg_backgroundName.textChanged.connect(
            self.backgroundNameChanged)
        self.backgroundList = Background.available()
        for aset in self.backgroundList:
            self.backgroundNameList.addItem(aset.name)
        assert Internal.Preferences
        self.kcfg_backgroundName.setText(str(Internal.Preferences.backgroundName))

    def backgroundNameChanged(self, name:str) ->None:
        """the name changed: update the current row"""
        igrindex = 0
        for idx, aset in enumerate(self.backgroundList):
            if aset.desktopFileName == name:
                igrindex = idx
                break
        self.backgroundNameList.setCurrentRow(igrindex)

    def backgroundRowChanged(self) ->None:
        """user selected a new background, update our information about it and paint preview"""
        selBackground = self.backgroundList[
            self.backgroundNameList.currentRow()]
        self.kcfg_backgroundName.setText(selBackground.desktopFileName)
        self.backgroundAuthor.setText(selBackground.author)
        self.backgroundContact.setText(selBackground.authorEmail)
        self.backgroundDescription.setText(selBackground.description)
        selBackground.setPalette(self.backgroundPreview)
        self.backgroundPreview.setAutoFillBackground(True)
