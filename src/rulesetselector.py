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

from PyQt4.QtCore import SIGNAL
from PyKDE4.kdecore import i18n
from PyQt4.QtGui import QWidget, QListWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, \
    QSpacerItem, QSizePolicy, QInputDialog, QLineEdit
from scoring import Ruleset
from util import m18n

class RulesetSelector( QWidget):
    """presents all available rulesets with previews"""
    def __init__(self, parent,  pref):
        assert pref # quieten pylint
        super(RulesetSelector, self).__init__(parent)
        self.ruleset = None
        self.rulesetList = None
        self.setupUi()
        self.refresh()
        self.connect(self.rulesetNameList, SIGNAL(
                'currentRowChanged ( int)'), self.rulesetRowChanged)

    def refresh(self):
        """reload the ruleset lists"""
        self.rulesetList = Ruleset.availableRulesets()
        idx = self.rulesetNameList.currentRow()
        self.rulesetNameList.clear()
        for aset in  self.rulesetList:
            self.rulesetNameList.addItem(m18n(aset.name))
        self.rulesetNameList.setCurrentRow(min(idx, self.rulesetNameList.count()-1))
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
        spacerItem = QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        v2layout.addWidget(self.btnCopy)
        v2layout.addWidget(self.btnModify)
        v2layout.addWidget(self.btnRename)
        v2layout.addWidget(self.btnRemove)
        self.connect(self.btnCopy, SIGNAL('clicked(bool)'), self.copy)
        self.connect(self.btnModify, SIGNAL('clicked(bool)'), self.modify)
        self.connect(self.btnRename, SIGNAL('clicked(bool)'), self.rename)
        self.connect(self.btnRemove, SIGNAL('clicked(bool)'), self.remove)
        v2layout.addItem(spacerItem)
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        self.rulesetDescription.setSizePolicy(sizePolicy)
        self.retranslateUi()

    def copy(self):
        """copy the ruleset"""
        newRuleset = self.ruleset.copy()
        if newRuleset:
            self.rulesetList.append(newRuleset)
            self.rulesetNameList.addItem(m18n(newRuleset.name))

    def modify(self):
        """edit the rules"""
        pass

    def rename(self):
        """rename the ruleset"""
        entry = self.rulesetNameList.currentItem()
        (txt, txtOk) = QInputDialog.getText(self, i18n('rename ruleset'), entry.text(),
                    QLineEdit.Normal, entry.text())
        if txtOk:
            entry.setText(txt)
            self.ruleset.rename(unicode(txt))

    def remove(self):
        """removes a ruleset"""
        if self.ruleset.isCustomized(True):
            self.ruleset.remove()
            self.refresh()

    def retranslateUi(self):
        """translate to current language"""
        self.rulesetRowChanged()
        self.btnCopy.setText(m18n("&Copy"))
        self.btnModify.setText(m18n("&Modify"))
        self.btnRename.setText(m18n("&Rename"))
        self.btnRemove.setText(m18n("R&emove"))

    def rulesetRowChanged(self):
        """user selected a new ruleset, update our information about it"""
        if self.rulesetList and len(self.rulesetList):
            self.ruleset = self.rulesetList[self.rulesetNameList.currentRow()]
            self.rulesetDescription.setText(m18n(self.ruleset.description))
