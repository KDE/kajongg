# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from PyQt4.QtCore import Qt, QVariant, QAbstractTableModel, QModelIndex
from PyQt4.QtGui import QLabel, QDialog, \
        QHBoxLayout, QVBoxLayout, QDialogButtonBox

from util import m18n, m18nc
from statesaver import StateSaver
from guiutil import ListComboBox, MJTableView
from common import Debug
from modeltest import ModelTest

class DifferModel(QAbstractTableModel):
    """a model for our ruleset differ"""
    def __init__(self, diffs, view):
        super(DifferModel, self).__init__()
        self.diffs = diffs
        self.view = view

    def columnCount(self, dummyIndex=QModelIndex()): # pylint: disable=R0201
        """how many columns does this node have?"""
        return 3 # rule name, left values, right values

    def rowCount(self, parent):
        """how many items?"""
        if parent.isValid():
            # we have only top level items
            return 0
        return len(self.diffs)

    def data(self, index, role=Qt.DisplayRole):
        """get from model"""
        if not index.isValid() or not (0 <= index.row() < len(self.diffs)):
            return QVariant()
        diff = self.diffs[index.row()]
        column = index.column()
        if role == Qt.DisplayRole:
            return QVariant(diff[column])
        elif role == Qt.TextAlignmentRole:
            return QVariant(int(Qt.AlignLeft|Qt.AlignVCenter))
        return QVariant()

    def headerData(self, section, orientation, role):
        """tell the view about the wanted headers"""
        if role == Qt.TextAlignmentRole:
            if orientation == Qt.Horizontal:
                return QVariant(int(Qt.AlignLeft|Qt.AlignVCenter))
        if role != Qt.DisplayRole:
            return QVariant()
        if orientation == Qt.Horizontal:
            if section == 0:
                return QVariant(m18nc('Kajongg', 'Rule'))
            if section == 1:
                return QVariant(m18n(self.view.cbRuleset1.current.name))
            if section == 2:
                return QVariant(m18n(self.view.cbRuleset2.current.name))
            return QVariant()


class RulesetDiffer(QDialog):
    """Shows differences between rulesets"""
    def __init__(self, leftRulesets, rightRulesets, parent=None):
        QDialog.__init__(self, parent)
        if not isinstance(leftRulesets, list):
            leftRulesets = list([leftRulesets])
        if not isinstance(rightRulesets, list):
            rightRulesets = list([rightRulesets])
        leftRulesets, rightRulesets = leftRulesets[:], rightRulesets[:]
        # remove rulesets from right which are also on the left side
        for left in leftRulesets:
            left.load()
        for right in rightRulesets:
            right.load()
        for left in leftRulesets:
            for right in rightRulesets[:]:
                if left == right and left.name == right.name:
                    rightRulesets.remove(right)
        self.leftRulesets = leftRulesets
        self.rightRulesets = rightRulesets
        self.model = None
        self.modelTest = None
        self.view = MJTableView(self)
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        cbLayout = QHBoxLayout()
        self.cbRuleset1 = ListComboBox(self.leftRulesets)
        if len(self.leftRulesets) == 1:
            self.lblRuleset1 = QLabel(self.leftRulesets[0].name)
            cbLayout.addWidget(self.lblRuleset1)
        else:
            cbLayout.addWidget(self.cbRuleset1)
        self.cbRuleset2 = ListComboBox(self.rightRulesets)
        cbLayout.addWidget(self.cbRuleset2)
        cmdLayout = QHBoxLayout()
        cmdLayout.addWidget(self.buttonBox)
        layout = QVBoxLayout()
        layout.addLayout(cbLayout)
        layout.addWidget(self.view)
        layout.addLayout(cmdLayout)
        self.setLayout(layout)

        self.setWindowTitle(m18n("Compare") + ' - Kajongg')
        self.setObjectName('RulesetDiffer')

        self.cbRuleset1.currentIndexChanged.connect(self.leftRulesetChanged)
        self.cbRuleset2.currentIndexChanged.connect(self.rulesetChanged)
        self.leftRulesetChanged()
        StateSaver(self)

    def leftRulesetChanged(self):
        """slot to be called if the left ruleset changes"""
        if len(self.leftRulesets) == 1:
            self.orderRight()
        self.rulesetChanged()

    def rulesetChanged(self):
        """slot to be called if the right ruleset changes"""
        self.model = DifferModel(self.formattedDiffs(), self)
        if Debug.modelTest:
            self.modelTest = ModelTest(self.model, self)
        self.view.setModel(self.model)

    def orderRight(self):
        """order the right rulesets by similarity to current left ruleset.
        Similarity is defined by the length of the diff list."""
        leftRuleset = self.cbRuleset1.current
        diffPairs = sorted([(len(x.diff(leftRuleset)), x) for x in self.rightRulesets])
        combo = self.cbRuleset2
        try:
            combo.blockSignals(True)
            combo.items = [x[1] for x in diffPairs]
        finally:
            combo.blockSignals(False)
        combo.setCurrentIndex(0)

    def formattedDiffs(self):
        """a list of tuples with 3 values: name, left, right"""
        formatted = []
        leftRuleset = self.cbRuleset1.current
        rightRuleset = self.cbRuleset2.current
        assert rightRuleset, self.cbRuleset2.count()
        leftRuleset.load()
        rightRuleset.load()
        for rule1, rule2 in leftRuleset.diff(rightRuleset):
            name = m18n(rule1.name if rule1 else rule2.name)
            left = rule1.contentStr() if rule1 else m18nc('Kajongg-Rule', 'not defined')
            right = rule2.contentStr() if rule2 else m18nc('Kajongg-Rule', 'not defined')
            formatted.append((name, left, right))
            if rule1 and rule2 and rule1.definition != rule2.definition:
                formatted.append(('', rule1.definition, rule2.definition))
        return formatted
