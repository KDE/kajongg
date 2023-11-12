# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

partially based on C++ code from:
Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com

SPDX-License-Identifier: GPL-2.0

"""

from common import Internal

from qt import Qt, QWidget, QSlider, QHBoxLayout, QLabel
from qt import QVBoxLayout, QSpacerItem, QSizePolicy, QCheckBox

from kde import KConfigDialog
from mi18n import i18n, i18nc

from statesaver import StateSaver
from tilesetselector import TilesetSelector
from backgroundselector import BackgroundSelector

__all__ = ['ConfigDialog']


class PlayConfigTab(QWidget):

    """Display Config tab"""

    def __init__(self, parent):
        super().__init__(parent)
        self.setupUi()

    def setupUi(self):
        """layout the window"""
        self.setContentsMargins(0, 0, 0, 0)
        vlayout = QVBoxLayout(self)
        vlayout.setContentsMargins(0, 0, 0, 0)
        sliderLayout = QHBoxLayout()
        self.kcfg_showShadows = QCheckBox(i18n('Show tile shadows'), self)
        self.kcfg_showShadows.setObjectName('kcfg_showShadows')
        self.kcfg_rearrangeMelds = QCheckBox(
            i18n('Rearrange undisclosed tiles to melds'), self)
        self.kcfg_rearrangeMelds.setObjectName('kcfg_rearrangeMelds')
        self.kcfg_showOnlyPossibleActions = QCheckBox(i18n(
            'Show only possible actions'))
        self.kcfg_showOnlyPossibleActions.setObjectName(
            'kcfg_showOnlyPossibleActions')
        self.kcfg_propose = QCheckBox(i18n('Propose what to do'))
        self.kcfg_propose.setObjectName('kcfg_propose')
        self.kcfg_animationSpeed = QSlider(self)
        self.kcfg_animationSpeed.setObjectName('kcfg_animationSpeed')
        self.kcfg_animationSpeed.setOrientation(Qt.Orientation.Horizontal)
        self.kcfg_animationSpeed.setSingleStep(1)
        lblSpeed = QLabel(i18n('Animation speed:'))
        lblSpeed.setBuddy(self.kcfg_animationSpeed)
        sliderLayout.addWidget(lblSpeed)
        sliderLayout.addWidget(self.kcfg_animationSpeed)
        self.kcfg_useSounds = QCheckBox(i18n('Use sounds if available'), self)
        self.kcfg_useSounds.setObjectName('kcfg_useSounds')
        self.kcfg_uploadVoice = QCheckBox(i18n(
            'Let others hear my voice'), self)
        self.kcfg_uploadVoice.setObjectName('kcfg_uploadVoice')
        pol = QSizePolicy()
        pol.setHorizontalPolicy(QSizePolicy.Expanding)
        pol.setVerticalPolicy(QSizePolicy.Expanding)
        spacerItem = QSpacerItem(
            20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        vlayout.addWidget(self.kcfg_showShadows)
        vlayout.addWidget(self.kcfg_rearrangeMelds)
        vlayout.addWidget(self.kcfg_showOnlyPossibleActions)
        vlayout.addWidget(self.kcfg_propose)
        vlayout.addWidget(self.kcfg_useSounds)
        vlayout.addWidget(self.kcfg_uploadVoice)
        vlayout.addLayout(sliderLayout)
        vlayout.addItem(spacerItem)
        self.setSizePolicy(pol)
        self.retranslateUi()

    def retranslateUi(self):
        """translate to current language"""


class ConfigDialog(KConfigDialog):

    """configuration dialog with several pages"""

    def __init__(self, parent, name):
        assert Internal.Preferences
        KConfigDialog.__init__(
            self, parent, name, Internal.Preferences)
        StateSaver(self)
        self.pages = [
            self.addPage(
                PlayConfigTab(self),
                i18nc('kajongg', 'Play'), "arrow-right"),
            self.addPage(
                TilesetSelector(self),
                i18n("Tiles"), "games-config-tiles"),
            self.addPage(
                BackgroundSelector(self),
                i18n("Backgrounds"), "games-config-background")]

    def keyPressEvent(self, event):
        """The four tabs can be selected with CTRL-1 .. CTRL-4"""
        mod = event.modifiers()
        key = chr(event.key() % 128)
        if Qt.KeyboardModifier.ControlModifier | mod and key in '123456789'[:len(self.pages)]:
            self.setCurrentPage(self.pages[int(key) - 1])
            return
        KConfigDialog.keyPressEvent(self, event)
