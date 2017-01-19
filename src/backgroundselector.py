"""
    Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from qt import QWidget, QLineEdit
from kde import KConfig
from background import Background
from common import Internal
from guiutil import loadUi
from log import m18n


class BackgroundSelector(QWidget):

    """presents all available backgrounds with previews"""

    def __init__(self, parent):
        super(BackgroundSelector, self).__init__(parent)
        loadUi(self)
        self.kcfg_backgroundName = QLineEdit(self)
        self.kcfg_backgroundName.setVisible(False)
        self.kcfg_backgroundName.setObjectName('kcfg_backgroundName')
        self.setUp()

    def setUp(self):
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
        self.kcfg_backgroundName.setText(Internal.Preferences.backgroundName)

    def backgroundNameChanged(self, name):
        """the name changed: update the current row"""
        igrindex = 0
        for idx, aset in enumerate(self.backgroundList):
            if aset.desktopFileName == name:
                igrindex = idx
        self.backgroundNameList.setCurrentRow(igrindex)

    def backgroundRowChanged(self):
        """user selected a new background, update our information about it and paint preview"""
        selBackground = self.backgroundList[
            self.backgroundNameList.currentRow()]
        self.kcfg_backgroundName.setText(selBackground.desktopFileName)

        config = KConfig(selBackground.path)
        group = config.group("KMahjonggBackground")

        author = group.readEntry("Author") or m18n("unknown author")
        description = group.readEntry("Description") or ""
        authorEmail = group.readEntry(
            "AuthorEmail") or m18n(
                "no E-Mail address available")

        self.backgroundAuthor.setText(author)
        self.backgroundContact.setText(authorEmail)
        self.backgroundDescription.setText(description)
        selBackground.setPalette(self.backgroundPreview)
        self.backgroundPreview.setAutoFillBackground(True)
