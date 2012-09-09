"""
    Copyright (C) 2008-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

    partially based on C++ code from:
    Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

    Libkmahjongg is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
"""

from PyQt4 import QtGui
from kde import KLineEdit
from background import Background
from common import Preferences
from guiutil import loadUi, konfigGroup

class BackgroundSelector( QtGui.QWidget):
    """presents all available backgrounds with previews"""
    def __init__(self, parent):
        super(BackgroundSelector, self).__init__(parent)
        loadUi(self)
        self.kcfg_backgroundName = KLineEdit(self)
        self.kcfg_backgroundName.setVisible(False)
        self.kcfg_backgroundName.setObjectName('kcfg_backgroundName')
        self.setUp()

    def setUp(self):
        """fill the selector"""

        #The lineEdit widget holds our background path, but the user does
        # not manipulate it directly
        self.kcfg_backgroundName.hide()

        self.backgroundNameList.currentRowChanged.connect(self.backgroundRowChanged)
        self.kcfg_backgroundName.textChanged.connect(self.backgroundNameChanged)
        self.backgroundList = Background.backgroundsAvailable()
        for aset in self.backgroundList:
            self.backgroundNameList.addItem(aset.name)
        self.kcfg_backgroundName.setText(Preferences.backgroundName)

    def backgroundNameChanged(self, name):
        """the name changed: update the current row"""
        igrindex = 0
        for idx, aset in enumerate(self.backgroundList):
            if aset.desktopFileName == name:
                igrindex = idx
        self.backgroundNameList.setCurrentRow(igrindex)

    def backgroundRowChanged(self):
        """user selected a new background, update our information about it and paint preview"""
        selBackground = self.backgroundList[self.backgroundNameList.currentRow()]
        self.kcfg_backgroundName.setText(selBackground.desktopFileName)

        config, group = konfigGroup(selBackground.path, "KMahjonggBackground")
        assert config

        author = group.readEntry("Author", "unknown author").toString()
        description = group.readEntry("Description", "").toString()
        authorEmail = group.readEntry("AuthorEmail", "no E-Mail address available").toString()

        self.backgroundAuthor.setText(author)
        self.backgroundContact.setText(authorEmail)
        self.backgroundDescription.setText(description)
        selBackground.setPalette(self.backgroundPreview)
        self.backgroundPreview.setAutoFillBackground(True)
