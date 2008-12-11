#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008 Wolfgang Rohdewald <wolfgang@rohdewald.de>

partially based on C++ code from:
    Copyright (C) 2006 Mauricio Piacentini  <mauricio@tabuleiro.com>

kmj is free software you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""


from PyKDE4 import kdeui
from PyQt4 import QtCore,  QtGui
from PyKDE4.kdecore import i18n
from tilesetselector import TilesetSelector
from general_ui import Ui_General

class PrefDefaults(object):
    """holds default values.
        This is the only place where they are defined."""
    def __init__(self):
        self.upperLimit = 300
        self.tileset = 'default'
        
class Preferences(kdeui.KConfigSkeleton):
    """holds all preference values"""
    def __init__(self):
        kdeui.KConfigSkeleton.__init__(self)
        self.setCurrentGroup('General')
        self.dflt = PrefDefaults()
        self._upperLimitValue = 0
        self._tilesetValue = QtCore.QString()
        self._upperLimit = self.addItemInt('UpperLimit',
                self._upperLimitValue,  self.dflt.upperLimit)
        self._tileset = self.addItemString('Tileset',
                self._tilesetValue, QtCore.QString(self.dflt.tileset))
        self.readConfig()
        
    @property
    def upperLimit(self):
        """the upper limit for the score a hand can get"""
        return self._upperLimit.value()

    @property
    def tileset(self):
        """the tileset to be used"""
        return self._tileset.value()

class General(QtGui.QWidget,  Ui_General):
    """general settings page"""
    def __init__(self,  parent = None):
        super(General, self).__init__(parent)
        self.setupUi(self)
        
class ConfigDialog(kdeui.KConfigDialog):
    """configuration dialog with several pages"""
    def __init__(self, parent,  name,  pref):
        super(ConfigDialog, self).__init__(parent,  QtCore.QString(name), pref )
        self.pref = pref
        self.general = General(self)
        self.selector = TilesetSelector(self, pref)
        self.kpagegeneral = self.addPage(self.general, 
                i18n("General"), "games-config-options")
        self.kpagesel = self.addPage(self.selector,
                i18n("Tiles"), "games-config-tiles")


