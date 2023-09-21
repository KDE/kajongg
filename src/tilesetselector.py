"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

partially based on C++ code from:
Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

SPDX-License-Identifier: GPL-2.0

"""

from qt import QWidget, QHBoxLayout, QLineEdit
from tile import Tile
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
        super().__init__(parent)

        loadUi(self)
        self.kcfg_tilesetName = QLineEdit(self)
        self.kcfg_tilesetName.setVisible(False)
        self.kcfg_tilesetName.setObjectName('kcfg_tilesetName')

        self.tileScene = SceneWithFocusRect()
        self.tileView = FittingView()
        self.tileView.setScene(self.tileScene)
        _ = Internal.Preferences.tilesetName
        assert isinstance(_, str)
        self.tileset = Tileset(_)
        self.uiTiles = [UITile(Tile('w' + s.char.lower())) for s in Wind.all4]
        self.board = Board(2, 2, self.tileset)
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
