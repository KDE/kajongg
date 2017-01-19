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

from qt import QWidget, QHBoxLayout, QLineEdit
from tileset import Tileset
from uitile import UITile
from board import Board, FittingView
from scene import SceneWithFocusRect
from common import Internal
from wind import Wind
from guiutil import loadUi
from animation import AnimationSpeed


class TilesetSelector(QWidget):

    """presents all available tiles with previews"""

    def __init__(self, parent):
        super(TilesetSelector, self).__init__(parent)

        loadUi(self)
        self.kcfg_tilesetName = QLineEdit(self)
        self.kcfg_tilesetName.setVisible(False)
        self.kcfg_tilesetName.setObjectName('kcfg_tilesetName')

        self.tileScene = SceneWithFocusRect()
        self.tileView = FittingView()
        self.tileView.setScene(self.tileScene)
        self.tileset = Tileset(Internal.Preferences.tilesetName)
        self.uiTiles = [UITile('w' + s.char.lower()) for s in Wind.all4]
        self.board = Board(2, 2, self.tileset)
        self.board.showShadows = True
        self.tileScene.addItem(self.board)
        self.tileView.setParent(self.tilesetPreview)
        layout = QHBoxLayout(self.tilesetPreview)
        layout.addWidget(self.tileView)
        for idx, offsets in enumerate([(0, 0), (0, 1), (1, 0), (1, 1)]):
            self.uiTiles[idx].setBoard(
                self.board,
                *offsets)
            self.uiTiles[idx].focusable = False
        self.setUp()

    def setUp(self):
        """set-up the selector"""

        # The lineEdit widget holds our tileset path, but the user does
        # not manipulate it directly
        self.kcfg_tilesetName.hide()

        self.tilesetNameList.currentRowChanged.connect(self.tilesetRowChanged)
        self.kcfg_tilesetName.textChanged.connect(self.tilesetNameChanged)

        Tileset.loadAll()
        # list default tileset first
        self.tilesetList = Tileset.available()
        for aset in self.tilesetList:
            self.tilesetNameList.addItem(aset.name)
        self.kcfg_tilesetName.setText(Internal.Preferences.tilesetName)

    def tilesetNameChanged(self, name):
        """the name changed: update the current row"""
        igrindex = 0
        for idx, aset in enumerate(self.tilesetList):
            if aset.desktopFileName == name:
                igrindex = idx
                break
        self.tilesetNameList.setCurrentRow(igrindex)

    def tilesetRowChanged(self):
        """user selected a new tileset, update our information about it and
        paint preview"""
        selTileset = self.tilesetList[self.tilesetNameList.currentRow()]
        self.kcfg_tilesetName.setText(selTileset.desktopFileName)
        self.tilesetAuthor.setText(selTileset.author)
        self.tilesetContact.setText(selTileset.authorEmail)
        self.tilesetDescription.setText(selTileset.description)
        with AnimationSpeed():
            self.board.tileset = selTileset
