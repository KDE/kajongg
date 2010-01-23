"""
    Copyright (C) 2008,2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

    partially based on C++ code from:
    Copyright (C) 2006 Mauricio Piacentini  <mauricio@tabuleiro.com>

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
    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

from PyQt4 import QtCore, QtGui
from PyQt4.QtGui import QHBoxLayout
from PyQt4.QtGui import QGraphicsScene
from tilesetselector_ui import Ui_TilesetSelector
from tileset import Tileset
from tile import Tile
from board import Board, FittingView
import util

class TilesetSelector( QtGui.QWidget,  Ui_TilesetSelector):
    """presents all available tiles with previews"""
    def __init__(self, parent):
        super(TilesetSelector, self).__init__(parent)
        self.setupUi(self)

        self.tileScene = QGraphicsScene()
        self.tileView = FittingView()
        self.tileView.setScene(self.tileScene)
        self.tileset = Tileset(util.PREF.tilesetName)
        self.tiles = [Tile('w'+s) for s in util.WINDS.lower()]
        self.board = Board(2, 2, self.tileset, self.tiles)
        self.tileScene.addItem(self.board)
        self.tileView.setParent(self.tilesetPreview)
        layout = QHBoxLayout(self.tilesetPreview)
        layout.addWidget(self.tileView)
        self.tiles[1].setPos(yoffset=1)
        self.tiles[2].setPos(xoffset=1)
        self.tiles[3].setPos(xoffset=1, yoffset=1)
        self.setUp()

    def setUp(self):
        """set-up the data in the selector"""

        #The lineEdit widget holds our tileset path, but the user does
        # not manipulate it directly
        self.kcfg_tilesetName.hide()

        self.connect(self.tilesetNameList, QtCore.SIGNAL(
                'currentRowChanged ( int)'), self.tilesetRowChanged)
        self.connect(self.kcfg_tilesetName, QtCore.SIGNAL('textChanged(QString)'),
                self.tilesetNameChanged)
        self.tilesetList = Tileset.tilesAvailable()
        for aset in  self.tilesetList:
            self.tilesetNameList.addItem(aset.name)
        self.kcfg_tilesetName.setText(util.PREF.tilesetName)

    def tilesetNameChanged(self, name):
        """the name changed: update the current row"""
        igrindex = 0
        for idx, aset in  enumerate(self.tilesetList):
            if aset.desktopFileName == name:
                igrindex = idx
        self.tilesetNameList.setCurrentRow(igrindex)

    def tilesetRowChanged(self):
        """user selected a new tileset, update our information about it and paint preview"""
        selTileset = self.tilesetList[self.tilesetNameList.currentRow()]
        self.kcfg_tilesetName.setText(selTileset.desktopFileName)
        self.tilesetAuthor.setText(selTileset.author)
        self.tilesetContact.setText(selTileset.authorEmail)
        self.tilesetDescription.setText(selTileset.description)
        self.board.tileset = selTileset
