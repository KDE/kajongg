"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

partially based on C++ code from:
Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

SPDX-License-Identifier: GPL-2.0

"""

from typing import cast
from qt import QWidget, QLineEdit
from qt import QSize, QMetaObject, QFormLayout, QVBoxLayout, QHBoxLayout, QSizePolicy
from qt import QLabel, QGroupBox, QListWidget, QFrame, QSpacerItem, QCoreApplication
from background import Background
from common import Internal
from mi18n import i18nc


class BackgroundSelector(QWidget):

    """presents all available backgrounds with previews"""

    # pylint: disable=too-many-instance-attributes,too-many-statements

    def __init__(self, parent:QWidget) ->None:
        super().__init__(parent)
        self.setupUi()
        self.kcfg_backgroundName = QLineEdit(self)
        self.kcfg_backgroundName.setVisible(False)
        self.kcfg_backgroundName.setObjectName('kcfg_backgroundName')
        self.backgroundNameList:'QListWidget'
        self.backgroundAuthor:'QLabel'
        self.backgroundContact:'QLabel'
        self.backgroundDescription:'QLabel'
        self.backgroundPreview:'QLabel'
        self.setUp()

    def setupUi(self) ->None:
        """created by pyuic from old backgroundselector.ui and adapted for direct use"""
        self.setObjectName("BackgroundSelector")
        self.resize(497, 446)
        self.setMaximumSize(QSize(800, 600))
        self.vboxlayout = QVBoxLayout(self)
        self.vboxlayout.setContentsMargins(0, 0, 0, 0)
        self.vboxlayout.setObjectName("vboxlayout")
        self.hboxlayout = QHBoxLayout()
        self.hboxlayout.setContentsMargins(0, 0, 0, 0)
        self.hboxlayout.setObjectName("hboxlayout")
        self.backgroundNameList = QListWidget(self)
        self.backgroundNameList.setMinimumSize(QSize(120, 0))
        self.backgroundNameList.setObjectName("backgroundNameList")
        self.hboxlayout.addWidget(self.backgroundNameList)
        self.groupBox_2 = QGroupBox(self)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.groupBox_2.sizePolicy().hasHeightForWidth())
        self.groupBox_2.setSizePolicy(sizePolicy)
        self.groupBox_2.setObjectName("groupBox_2")
        self.vboxlayout1 = QVBoxLayout(self.groupBox_2)
        self.vboxlayout1.setContentsMargins(0, 0, 0, 0)
        self.vboxlayout1.setObjectName("vboxlayout1")
        self.backgroundPreview = QLabel(self.groupBox_2)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.backgroundPreview.sizePolicy().hasHeightForWidth())
        self.backgroundPreview.setSizePolicy(sizePolicy)
        self.backgroundPreview.setMinimumSize(QSize(200, 160))
        self.backgroundPreview.setFrameShape(QFrame.Shape.Box)
        self.backgroundPreview.setObjectName("backgroundPreview")
        self.vboxlayout1.addWidget(self.backgroundPreview)
        self.hboxlayout.addWidget(self.groupBox_2)
        self.vboxlayout.addLayout(self.hboxlayout)
        self.groupBox = QGroupBox(self)
        self.groupBox.setObjectName("groupBox")
        self.formLayout = QFormLayout(self.groupBox)
        self.formLayout.setObjectName("formLayout")
        self.labelAuthor = QLabel(self.groupBox)
        self.labelAuthor.setObjectName("labelAuthor")
        self.formLayout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.labelAuthor)
        self.backgroundAuthor = QLabel(self.groupBox)
        self.backgroundAuthor.setObjectName("backgroundAuthor")
        self.formLayout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.backgroundAuthor)
        self.labelContact = QLabel(self.groupBox)
        self.labelContact.setObjectName("labelContact")
        self.formLayout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.labelContact)
        self.backgroundContact = QLabel(self.groupBox)
        self.backgroundContact.setObjectName("backgroundContact")
        self.formLayout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.backgroundContact)
        self.labelDescription = QLabel(self.groupBox)
        self.labelDescription.setObjectName("labelDescription")
        self.formLayout.setWidget(2, QFormLayout.ItemRole.LabelRole, self.labelDescription)
        self.backgroundDescription = QLabel(self.groupBox)
        self.backgroundDescription.setObjectName("backgroundDescription")
        self.formLayout.setWidget(2, QFormLayout.ItemRole.FieldRole, self.backgroundDescription)
        self.vboxlayout.addWidget(self.groupBox)
        spacerItem = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.vboxlayout.addItem(spacerItem)

        self.retranslateUi()
        QMetaObject.connectSlotsByName(self)

    def retranslateUi(self) ->None:
        """created by pyuic from old backgroundselector.ui and adapted for direct use"""
        self.groupBox_2.setTitle(i18nc("BackgroundSelector", "Preview"))
        self.groupBox.setTitle(i18nc("BackgroundSelector", "Properties"))
        self.labelAuthor.setText(i18nc("BackgroundSelector", "Author:"))
        self.labelContact.setText(i18nc("BackgroundSelector", "Contact:"))
        self.labelDescription.setText(i18nc("BackgroundSelector", "Description:"))

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
        selBackground = cast(Background, self.backgroundList[
            self.backgroundNameList.currentRow()])
        self.kcfg_backgroundName.setText(selBackground.desktopFileName)
        self.backgroundAuthor.setText(selBackground.author)
        self.backgroundContact.setText(selBackground.authorEmail)
        self.backgroundDescription.setText(selBackground.description)
        selBackground.setPalette(self.backgroundPreview)
        self.backgroundPreview.setAutoFillBackground(True)
