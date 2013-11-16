# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2013 Wolfgang Rohdewald <wolfgang@rohdewald.de>

partially based on C++ code from:
Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com

kajongg is free software you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
"""

__all__ = ['ConfigDialog']

from log import m18n, m18nc
from common import Internal

from PyQt4.QtCore import Qt, QString
from PyQt4.QtGui import QWidget
from PyQt4.QtGui import QSlider, QHBoxLayout, QLabel
from PyQt4.QtGui import QVBoxLayout, QSpacerItem, QSizePolicy, QCheckBox

from kde import KConfigDialog

from statesaver import StateSaver
from tilesetselector import TilesetSelector
from backgroundselector import BackgroundSelector

class PlayConfigTab( QWidget):
    """Display Config tab"""
    def __init__(self, parent):
        super(PlayConfigTab, self).__init__(parent)
        self.setupUi()

    def setupUi(self):
        """layout the window"""
        self.setContentsMargins(0, 0, 0, 0)
        vlayout = QVBoxLayout(self)
        vlayout.setContentsMargins(0, 0, 0, 0)
        sliderLayout = QHBoxLayout()
        self.kcfg_showShadows = QCheckBox(m18n('Show tile shadows'), self)
        self.kcfg_showShadows.setObjectName('kcfg_showShadows')
        self.kcfg_rearrangeMelds = QCheckBox(m18n('Rearrange undisclosed tiles to melds'), self)
        self.kcfg_rearrangeMelds.setObjectName('kcfg_rearrangeMelds')
        self.kcfg_showOnlyPossibleActions = QCheckBox(m18n('Show only possible actions'))
        self.kcfg_showOnlyPossibleActions.setObjectName('kcfg_showOnlyPossibleActions')
        self.kcfg_propose = QCheckBox(m18n('Propose what to do'))
        self.kcfg_propose.setObjectName('kcfg_propose')
        self.kcfg_animationSpeed = QSlider(self)
        self.kcfg_animationSpeed.setObjectName('kcfg_animationSpeed')
        self.kcfg_animationSpeed.setOrientation(Qt.Horizontal)
        self.kcfg_animationSpeed.setSingleStep(1)
        lblSpeed = QLabel(m18n('Animation speed:'))
        lblSpeed.setBuddy(self.kcfg_animationSpeed)
        sliderLayout.addWidget(lblSpeed)
        sliderLayout.addWidget(self.kcfg_animationSpeed)
        self.kcfg_useSounds = QCheckBox(m18n('Use sounds if available'), self)
        self.kcfg_useSounds.setObjectName('kcfg_useSounds')
        self.kcfg_uploadVoice = QCheckBox(m18n('Let others hear my voice'), self)
        self.kcfg_uploadVoice.setObjectName('kcfg_uploadVoice')
        pol = QSizePolicy()
        pol.setHorizontalPolicy(QSizePolicy.Expanding)
        pol.setVerticalPolicy(QSizePolicy.Expanding)
        spacerItem = QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
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
        pass

class ConfigDialog(KConfigDialog): # pylint: disable=too-many-ancestors,too-many-public-methods
    """configuration dialog with several pages"""
    def __init__(self, parent, name):
        # pylint: disable=super-init-not-called
        KConfigDialog.__init__(self, parent, QString(name), Internal.Preferences)
        self.pages = [
            self.addPage(PlayConfigTab(self),
                m18nc('kajongg','Play'), "arrow-right"),
            self.addPage(TilesetSelector(self),
                m18n("Tiles"), "games-config-tiles"),
            self.addPage(BackgroundSelector(self),
                m18n("Backgrounds"), "games-config-background")]
        StateSaver(self)

    def keyPressEvent(self, event):
        """The four tabs can be selected with CTRL-1 .. CTRL-4"""
        mod = event.modifiers()
        key = chr(event.key()%128)
        if Qt.ControlModifier | mod and key in '123456789'[:len(self.pages)]:
            self.setCurrentPage(self.pages[int(key)-1])
            return
        KConfigDialog.keyPressEvent(self, event)
