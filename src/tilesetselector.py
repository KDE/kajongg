"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

partially based on C++ code from:
Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

SPDX-License-Identifier: GPL-2.0-only

"""

from typing import cast

from qt import QWidget, QHBoxLayout, QLineEdit
from qt import QSize, QVBoxLayout, QSizePolicy, QGroupBox, QListWidget
from qt import QFormLayout, QLabel, QSpacerItem, QMetaObject
from tile import Tile
from tileset import Tileset
from uitile import UITile
from board import Board, FittingView
from scene import SceneWithFocusRect
from common import Internal
from wind import Wind
from animation import AnimationSpeed
from mi18n import i18nc


class TilesetSelector(QWidget):

    # pylint:disable=too-many-instance-attributes

    """presents all available tiles with previews"""

    def __init__(self, parent:QWidget) ->None:
        super().__init__(parent)

        self.tilesetNameList:'QListWidget'
        self.tilesetAuthor:'QLabel'
        self.tilesetContact:'QLabel'
        self.tilesetDescription:'QLabel'
        self.tilesetPreview:'QWidget'

        assert Internal.Preferences
        self.setupUi()
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

    def setupUi(self) ->None:
        """created by pyuic from old tilesetselector.ui and adapted for direct use"""

        # pylint:disable=too-many-statements
        self.setObjectName("TilesetSelector")
        self.resize(497, 446)
        self.setMaximumSize(QSize(800, 600))
        self.vboxlayout = QVBoxLayout(self)
        self.vboxlayout.setContentsMargins(0, 0, 0, 0)
        self.vboxlayout.setObjectName("vboxlayout")
        self.hboxlayout = QHBoxLayout()
        self.hboxlayout.setContentsMargins(0, 0, 0, 0)
        self.hboxlayout.setObjectName("hboxlayout")
        self.tilesetNameList = QListWidget(self)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(2)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.tilesetNameList.sizePolicy().hasHeightForWidth())
        self.tilesetNameList.setSizePolicy(sizePolicy)
        self.tilesetNameList.setMinimumSize(QSize(120, 0))
        self.tilesetNameList.setObjectName("tilesetNameList")
        self.hboxlayout.addWidget(self.tilesetNameList)
        self.groupBox_2 = QGroupBox(self)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.groupBox_2.sizePolicy().hasHeightForWidth())
        self.groupBox_2.setSizePolicy(sizePolicy)
        self.groupBox_2.setObjectName("groupBox_2")
        self.vboxlayout1 = QVBoxLayout(self.groupBox_2)
        self.vboxlayout1.setContentsMargins(0, 0, 0, 0)
        self.vboxlayout1.setObjectName("vboxlayout1")
        self.tilesetPreview = QWidget(self.groupBox_2)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.tilesetPreview.sizePolicy().hasHeightForWidth())
        self.tilesetPreview.setSizePolicy(sizePolicy)
        self.tilesetPreview.setMinimumSize(QSize(120, 160))
        self.tilesetPreview.setObjectName("tilesetPreview")
        self.vboxlayout1.addWidget(self.tilesetPreview)
        self.hboxlayout.addWidget(self.groupBox_2)
        self.vboxlayout.addLayout(self.hboxlayout)
        self.groupBox = QGroupBox(self)
        self.groupBox.setObjectName("groupBox")
        self.formLayout = QFormLayout(self.groupBox)
        self.formLayout.setObjectName("formLayout")
        self.labelAuthor = QLabel(self.groupBox)
        self.labelAuthor.setObjectName("labelAuthor")
        self.formLayout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.labelAuthor)
        self.tilesetAuthor = QLabel(self.groupBox)
        self.tilesetAuthor.setObjectName("tilesetAuthor")
        self.formLayout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.tilesetAuthor)
        self.labelContact = QLabel(self.groupBox)
        self.labelContact.setObjectName("labelContact")
        self.formLayout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.labelContact)
        self.tilesetContact = QLabel(self.groupBox)
        self.tilesetContact.setObjectName("tilesetContact")
        self.formLayout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.tilesetContact)
        self.labelDescription = QLabel(self.groupBox)
        self.labelDescription.setObjectName("labelDescription")
        self.formLayout.setWidget(2, QFormLayout.ItemRole.LabelRole, self.labelDescription)
        self.tilesetDescription = QLabel(self.groupBox)
        self.tilesetDescription.setObjectName("tilesetDescription")
        self.formLayout.setWidget(2, QFormLayout.ItemRole.FieldRole, self.tilesetDescription)
        self.vboxlayout.addWidget(self.groupBox)
        spacerItem = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.vboxlayout.addItem(spacerItem)

        self.retranslateUi()
        QMetaObject.connectSlotsByName(self)

    def retranslateUi(self) ->None:
        """created by pyuic from old tilesetselector.ui and adapted for direct use"""
        self.groupBox_2.setTitle(i18nc("TilesetSelector", "Preview"))
        self.groupBox.setTitle(i18nc("TilesetSelector", "Properties"))
        self.labelAuthor.setText(i18nc("TilesetSelector", "Author:"))
        self.labelContact.setText(i18nc("TilesetSelector", "Contact:"))
        self.labelDescription.setText(i18nc("TilesetSelector", "Description:"))

    def setUp(self) ->None:
        """set-up the selector"""

        assert Internal.Preferences
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
        self.kcfg_tilesetName.setText(cast(str, Internal.Preferences.tilesetName))

    def tilesetNameChanged(self, name:str) ->None:
        """the name changed: update the current row"""
        igrindex = 0
        for idx, aset in enumerate(self.tilesetList):
            if aset.desktopFileName == name:
                igrindex = idx
                break
        self.tilesetNameList.setCurrentRow(igrindex)

    def tilesetRowChanged(self) ->None:
        """user selected a new tileset, update our information about it and
        paint preview"""
        selTileset = cast(Tileset, self.tilesetList[self.tilesetNameList.currentRow()])
        self.kcfg_tilesetName.setText(selTileset.desktopFileName)
        self.tilesetAuthor.setText(selTileset.author)
        self.tilesetContact.setText(selTileset.authorEmail)
        self.tilesetDescription.setText(selTileset.description)
        with AnimationSpeed():
            self.board.tileset = selTileset
