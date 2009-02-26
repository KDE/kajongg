#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008,2009 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
from backgroundselector import BackgroundSelector
from general_ui import Ui_General
import util
from util import logException

class PrefDefaults(object):
    """holds default values.
        This is the only place where they are defined."""
    def __init__(self):
        self.upperLimit = 300
        self.tileset = 'default'
        self.background = 'default'
        
class Preferences(kdeui.KConfigSkeleton):
    """holds all preference values"""
    def __init__(self):
        kdeui.KConfigSkeleton.__init__(self)
        if util.PREF:
            logException(BaseException('PREF is not None'))
        util.PREF = self
        self.setCurrentGroup('General')
        self.dflt = PrefDefaults()
        self._upperLimitValue = 0
        self._tilesetValue = QtCore.QString()
        self._backgroundValue = QtCore.QString()
        self._upperLimit = self.addItemInt('UpperLimit',
                self._upperLimitValue,  self.dflt.upperLimit)
        self._tileset = self.addItemString('Tileset',
                self._tilesetValue, QtCore.QString(self.dflt.tileset))
        self._background = self.addItemString('Background',
                self._backgroundValue, QtCore.QString(self.dflt.background))
        self.readConfig()
        
    @property
    def upperLimit(self):
        """the upper limit for the score a hand can get"""
        return self._upperLimit.value()

    @property
    def tileset(self):
        """the tileset to be used"""
        # do not return a QString but a python string. QString is
        # mutable, python string is not. If we save the result of this
        # method elsewhere and later compare it with the current
        # value, they would always be identical. The saved value
        # would change with the current value because they are the same
        # mutable QString. I wonder how removal of QString from pyqt
        # will deal with this (see roadmap)
        return str(self._tileset.value())

    @property
    def background(self):
        """the background to be used"""
        return str(self._background.value())

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
        self.tilesetSelector = TilesetSelector(self, pref)
        self.backgroundSelector = BackgroundSelector(self, pref)
        self.kpagegeneral = self.addPage(self.general, 
                i18n("General"), "games-config-options")
        self.kpagetilesel = self.addPage(self.tilesetSelector,
                i18n("Tiles"), "games-config-tiles")
        self.kpagebackgrsel = self.addPage(self.backgroundSelector,
                i18n("Backgrounds"), "games-config-background")


