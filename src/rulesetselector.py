"""
    Copyright (C) 2008,2009 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
from PyQt4.QtGui import QWidget, QListWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from scoring import Ruleset
from util import m18n

class RulesetSelector( QWidget):
    """presents all available rulesets with previews"""
    def __init__(self, parent,  pref, dbhandle):
        super(RulesetSelector, self).__init__(parent)
        self.dbhandle = dbhandle
        self.rulesetList = Ruleset.availableRulesets(self.dbhandle)
        self.setupUi()
        self.connect(self.rulesetNameList, QtCore.SIGNAL(
                'currentRowChanged ( int)'), self.rulesetRowChanged)
        for aset in  self.rulesetList:
            self.rulesetNameList.addItem(m18n(aset.name))
        self.rulesetNameList.setCurrentRow(0)
        self.rulesetRowChanged()

    def setupUi(self):
        """layout the window"""
        hlayout = QHBoxLayout(self)
        v1layout = QVBoxLayout()
        v2layout = QVBoxLayout()
        hlayout.addLayout(v1layout)
        hlayout.addLayout(v2layout)
        self.rulesetNameList = QListWidget()
        self.rulesetDescription = QLabel()
        self.rulesetDescription.setWordWrap(True)
        v1layout.addWidget(self.rulesetNameList)
        v1layout.addWidget(self.rulesetDescription)
        self.btnCopy = QPushButton()
        self.btnModify = QPushButton()
        self.btnRename = QPushButton()
        self.btnRemove = QPushButton()
        spacerItem = QtGui.QSpacerItem(20, 20, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        v2layout.addWidget(self.btnCopy)
        v2layout.addWidget(self.btnModify)
        v2layout.addWidget(self.btnRename)
        v2layout.addWidget(self.btnRemove)
        v2layout.addItem(spacerItem)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        self.rulesetDescription.setSizePolicy(sizePolicy)

        self.retranslateUi()

    def retranslateUi(self):
        """translate to current language"""
        self.rulesetRowChanged()
        self.btnCopy.setText(m18n("&Copy"))
        self.btnModify.setText(m18n("&Modify"))
        self.btnRemove.setText(m18n("&Rename"))
        self.btnRename.setText(m18n("R&emove"))

    def rulesetRowChanged(self):
        """user selected a new ruleset, update our information about it"""
        selRuleset = self.rulesetList[self.rulesetNameList.currentRow()]
        self.rulesetDescription.setText(m18n(selRuleset.description))
