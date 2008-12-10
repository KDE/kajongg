"""
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
from tilesetselector_ui import Ui_TilesetSelector
from tileset import Tileset
from board import Board

class TilesetSelector( QtGui.QWidget,  Ui_TilesetSelector):
    """presents all available tiles with previews"""
    def __init__(self, parent,  pref):
        super(TilesetSelector, self).__init__(parent)
        self.previewBoard = None
        self.setupUi(self)
        self.setUp(pref)

    def setUp(self, pref):
        """setup the data in the selector"""
        currentTileset = pref.tileset
        #The lineEdit widget holds our tileset path, but the user does 
        # not manipulate it directly
        self.kcfg_Tileset.hide()
    
        self.tilesetList = Tileset.tilesAvailable()
        igrindex = 0
        for idx, aset in  enumerate(self.tilesetList):
            self.tilesetNameList.addItem(aset.name)
            if aset.desktopFileName == currentTileset:
                igrindex = idx
        self.tilesetNameList.setCurrentRow(igrindex)
        self.tilesetChanged()
        self.connect(self.tilesetNameList, QtCore.SIGNAL(
                'currentRowChanged ( int)'), self.tilesetChanged)

    def tilesetChanged(self):
        """user selected a new tileset, update our information about it and paint preview"""
        selTileset = self.tilesetList[self.tilesetNameList.currentRow()]
        self.kcfg_Tileset.setText(selTileset.desktopFileName)
        self.tilesetAuthor.setText(selTileset.author)
        self.tilesetContact.setText(selTileset.authorEmail)
        self.tilesetDescription.setText(selTileset.description)
        if self.previewBoard is None:
            self.previewBoard = Board(self.tilesetPreview)
            self.previewBoard.setTile('WIND_1', 0, 0)
            self.previewBoard.setTile('WIND_2', 0, 1)
            self.previewBoard.setTile('WIND_3', 1, 0)
            self.previewBoard.setTile('WIND_4', 1, 1)
        self.previewBoard.tileset = selTileset
