# -*- coding: utf-8 -*-

"""Copyright (C) 2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

kajongg is free software you can redistribute it and/or modifys
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

# See the user manual for a description of how to define rulesets.
# Names and descriptions must be english and may only contain ascii chars.
# Because kdecore.i18n() only accepts 8bit characters, no unicode.
# The KDE translation teams will "automatically" translate name and
# description into many languages.

from scoringengine import Rule, PredefinedRuleset
from util import m18nE, m18n

class ClassicalChinese(PredefinedRuleset):
    """classical chinese rules expressed by regular expressions, not complete"""

    name = m18nE('Classical Chinese DMJL')

    def __init__(self):
        PredefinedRuleset.__init__(self, ClassicalChinese.name)

    def initRuleset(self):
        """sets the description"""
        self.description = m18n('Classical Chinese as defined by the Deutsche Mah Jongg Liga (DMJL) e.V.')

    def __addManualRules(self):
        """those are actually winner rules but in the kajongg scoring mode they must be selected manually"""
        # applicable only if we have a concealed meld and a declared kong:
        self.winnerRules.append(Rule('Last Tile Taken from Dead Wall',
                r' M..e||M /(....)*[A-Z].* -(....)*.4.* %.* M..w.* L[A-Z]||Alastsource=e', doubles=1))
        self.winnerRules.append(Rule('Last Tile is Last Tile of Wall',
                r' M..z||M M..w.* L[A-Z]||Alastsource=z', doubles=1))
        self.winnerRules.append(Rule('Last Tile is Last Tile of Wall Discarded',
                r' M..Z||M M..d.* L[a-z]||Alastsource=Z', doubles=1))
        self.winnerRules.append(Rule('Robbing the Kong',
                r'I M..k||M M..[kwd].* L([a-z].).* ,,, (?!.*?\1.*?\1[ 0-9a-zA-Z]* /)(.*?\1)||Alastsource=k', doubles=1))
        self.winnerRules.append(Rule('Mah Jongg with Original Call',
                r' M...a||M /([^a-z]*[a-z][^a-z]*){0,2} .* M||Adeclaration=a', doubles=1))
        self.winnerRules.append(Rule('Dangerous Game', r'xx||M m||Apayforall'))
        self.winnerRules.append(Rule('Twofold Fortune',
                r' M...t||M -((.\d\d\d)*[sbcdwSBCDW]4..(.\d\d\d)*){2,4} %. M.* L[A-Z]||Adeclaration=t', limits=1))
        # limit hands:
        self.winnerRules.append(Rule('Blessing of Heaven', r' Me.1||M Me.[wd][a ]||Alastsource=1', limits=1))
        self.winnerRules.append(Rule('Blessing of Earth', r' M[swn].1||M M[swn].[wd] ||Alastsource=1', limits=1))
        # the next rule is never proposed, the program applies it when appropriate. Do not change the XEAST9X.
        # XEAST9X is meant to never match a hand, and the program will identify this rule by searching for XEAST9X
        self.winnerRules.append(Rule('East won nine times in a row', r'XEAST9X||Aabsolute', limits=1))

    def __addPenaltyRules(self):
        """as the name says"""
        self.penaltyRules.append(Rule('False Naming of Discard, Claimed for Chow', r' ', points = -50))
        self.penaltyRules.append(Rule('False Naming of Discard, Claimed for Pung/Kong', r' ', points = -100))
        self.penaltyRules.append(Rule('False Naming of Discard, Claimed for Mah Jongg',
                r' ||Aabsolute payees=3', points = -300))
        self.penaltyRules.append(Rule(
                'False Naming of Discard, Claimed for Mah Jongg and False Declaration of Mah Jongg',
                r' ||Aabsolute payers=2 payees=2', points = -300))
        self.penaltyRules.append(Rule('False Declaration of Mah Jongg by One Player',
                r' ||Aabsolute payees=3', points = -300))
        self.penaltyRules.append(Rule('False Declaration of Mah Jongg by Two Players',
                r' ||Aabsolute payers=2 payees=2', points = -300))
        self.penaltyRules.append(Rule('False Declaration of Mah Jongg by Three Players',
                r' ||Aabsolute payers=3', points = -300))

    def __addHandRules(self):
        """as the name says"""
        self.handRules.append(Rule('Own Flower and Own Season',
                r'I f(.).* y\1 .* m\1', doubles=1))
        self.handRules.append(Rule('All Flowers', r'I f. f. f. f. ',
                                                doubles=1))
        self.handRules.append(Rule('All Seasons', r'I y. y. y. y. ',
                                                doubles=1))
        self.handRules.append(Rule('Three Concealed Pongs', r' -((\S\S\S\S){0,2}([DWSBC][34]\d\d)(\S\S\S\S){0,2}){3,} ',
                                                doubles=1))
        self.handRules.append(Rule('Little Three Dragons', r'I /d2..d[34]..d[34]..',
                                                doubles=1))
        self.handRules.append(Rule('Big Three Dragons', r'I /d[34]..d[34]..d[34]..',
                                                doubles=2))
        self.handRules.append(Rule('Little Four Joys', r'I /.*w2..(w[34]..){3,3}',
                                                 doubles=1))
        self.handRules.append(Rule('Big Four Joys', r'I /(....){0,1}(w[34]\d\d){4,4}',
                                                doubles=2))
        self.handRules.append(Rule('Flower 1', r' fe ', points=4))
        self.handRules.append(Rule('Flower 2', r' fs ', points=4))
        self.handRules.append(Rule('Flower 3', r' fw ', points=4))
        self.handRules.append(Rule('Flower 4', r' fn ', points=4))
        self.handRules.append(Rule('Season 1', r' ye ', points=4))
        self.handRules.append(Rule('Season 2', r' ys ', points=4))
        self.handRules.append(Rule('Season 3', r' yw ', points=4))
        self.handRules.append(Rule('Season 4', r' yn ', points=4))
        self.handRules.append(Rule('Long Hand', r' %l||Aabsolute', points=0))

    def __addParameterRules(self):
        """as the name says"""
        self.parameterRules.append(Rule('Points Needed for Mah Jongg', 'intminMJPoints||Amandatory', parameter=0))
        self.parameterRules.append(Rule('Points for a Limit Hand', 'intlimit||Amandatory', parameter=500))
        self.parameterRules.append(Rule('Claim Timeout', 'intclaimTimeout||Amandatory', parameter=10))
        self.parameterRules.append(Rule('Size of Kong Box', 'intkongBoxSize||Amandatory', parameter=16))
        self.parameterRules.append(Rule('Play with Bonus Tiles', 'boolwithBonusTiles||AMandatory', parameter=True))
        self.parameterRules.append(Rule('Minimum number of rounds in game', 'intminRounds||AMandatory', parameter=4))

    def loadRules(self):
        """define the rules"""
        self.__addPenaltyRules()
        self.__addHandRules()
        self.__addManualRules()
        self.__addParameterRules()
        self.winnerRules.append(Rule('Last Tile Completes Pair of 2..8', r' L(.[2-8])\1\1\b', points=2))
        self.winnerRules.append(Rule('Last Tile Completes Pair of Terminals or Honors',
                r' L((.[19])|([dwDW].))\1\1\b', points=4))
        self.winnerRules.append(Rule('Last Tile is Only Possible Tile', r'FLastOnlyPossible', points=4))
        self.winnerRules.append(Rule('Won with Last Tile Taken from Wall', r' L[A-Z]', points=2))

        self.winnerRules.append(Rule('Zero Point Hand', r'I /([dwsbc].00){5,5} ',
                                                doubles=1))
        self.winnerRules.append(Rule('No Chow', r'I /([dwsbc][^0]..){5,5} ',
                                                doubles=1))
        self.winnerRules.append(Rule('Only Concealed Melds', r' /([DWSBC]...){5,5} ', doubles=1))
        self.winnerRules.append(Rule('False Color Game', r'I /([dw]...){1,}(([sbc])...)(\3...)* ', doubles=1))
        self.winnerRules.append(Rule('True Color Game', r'I /(([sbc])...)(\2...){4,4} ',
                                                doubles=3))
        self.winnerRules.append(Rule('Concealed True Color Game', r' -(([SBC])...)(\2...){4,4} ',
                                                limits=1))
        self.winnerRules.append(Rule('Only Terminals and Honors', r'I^((([dw].)|(.[19])){1,4} )*[fy/]',
                                                doubles=1 ))
        self.winnerRules.append(Rule('Only Honors', r'I /([dw]...){5,5} ',
                                                doubles=2 ))
        self.winnerRules.append(Rule('Hidden Treasure', r' -([A-Z][234]..){5,5}.* L[A-Z]', limits=1))
        self.winnerRules.append(Rule('All Honors', r' /([DWdw]...){5,5} ', limits=1))
        self.winnerRules.append(Rule('All Terminals', r'^((.[19]){1,4} )*[fy/]', limits=1))
        self.winnerRules.append(Rule('Winding Snake',
                r'I^(([sbc])1\2[1]\2[1] \2[2]\2[2] \2[3]\2[4]\2[5] \2[6]\2[7]\2[8] \2[9]\2[9]\2[9] [fy/])' \
                r'|^(([sbc])1\4[1]\4[1] \4[2]\4[3]\4[4] \4[5]\4[5] \4[6]\4[7]\4[8] \4[9]\4[9]\4[9] [fy/])' \
                r'|^(([sbc])1\6[1]\6[1] \6[2]\6[3]\6[4] \6[5]\6[6]\6[7] \6[8]\6[8] \6[9]\6[9]\6[9] [fy/])',
                limits=1))
        self.winnerRules.append(Rule('Fourfold Plenty', r' /((.\d\d\d){0,1}(.4\d\d)(.\d\d\d){0,1}){4,4} -', limits=1))
        self.winnerRules.append(Rule('Three Great Scholars', r' /[Dd][34]..[Dd][34]..[Dd][34]', limits=1))
        self.winnerRules.append(Rule('Four Blessings Hovering Over the Door', r'I /\S*(w[34]\d\d){4,4}\S* -', limits=1))
        self.winnerRules.append(Rule('All Greens', r'^((([bB][23468])|([dD]g)) *)*[fy/]', limits=1))
        self.winnerRules.append(Rule('Gathering the Plum Blossom from the Roof',
                r' M..e.* LS5', limits=1))
        self.winnerRules.append(Rule('Plucking the Moon from the Bottom of the Sea',
                r' M..z.* LS1', limits=1))
        self.winnerRules.append(Rule('Scratching a Carrying Pole',
                r' M..k.* Lb2', limits=1))

        # only hands matching an mjRule can win. We do not give points here ore should we?
        self.mjRules.append(Rule('Standard Mah Jongg', r'/(.[0234]..){5,5} ', points=20))
        self.mjRules.append(Rule('Nine Gates', r'^(S1S1S1 S2S3S4 S5S6S7 S8 S9S9S9 s.|'
                'B1B1B1 B2B3B4 B5B6B7 B8 B9B9B9 b.|C1C1C1 C2C3C4 C5C6C7 C8 C9C9C9 c.)', limits=1))
        self.mjRules.append(Rule('Thirteen Orphans', \
            r'I^(db){1,2} (dg){1,2} (dr){1,2} (we){1,2} (ws){1,2} (ww){1,2} (wn){1,2} '
            '(s1){1,2} (s9){1,2} (b1){1,2} (b9){1,2} (c1){1,2} (c9){1,2} [fy/].*M||Amayrobhiddenkong', limits=1))

        # doubling melds:
        self.meldRules.append(Rule('Pung/Kong of Dragons', r'^([dD][brg])\1\1', doubles=1))
        self.meldRules.append(Rule('Pung/Kong of Own Wind', r'^(([wW])([eswn])){3,4}.*[mM]\3', doubles=1))
        self.meldRules.append(Rule('Pung/Kong of Round Wind', r'^(([wW])([eswn])){3,4}.*[mM].\3', doubles=1))

        # exposed melds:
        self.meldRules.append(Rule('Exposed Kong', r'^([sbc])([2-8])(\1\2\1\2.\2)\b', points=8))
        self.meldRules.append(Rule('Exposed Kong of Terminals', r'^([sbc])([19])(\1\2\1\2.\2)\b', points=16))
        self.meldRules.append(Rule('Exposed Kong of Honors', r'^([dw])([brgeswn])(\1\2\1\2.\2)\b', points=16))

        self.meldRules.append(Rule('Exposed Pung', r'^([sbc][2-8])(\1\1)\b', points=2))
        self.meldRules.append(Rule('Exposed Pung of Terminals', r'^([sbc][19])(\1\1)\b', points=4))
        self.meldRules.append(Rule('Exposed Pung of Honors', r'^(d[brg]|w[eswn])(\1\1)\b', points=4))

        # concealed melds:
        self.meldRules.append(Rule('Concealed Kong', r'^([sbc][2-8])([SBC][2-8])(\2)(\1)\b', points=16))
        self.meldRules.append(Rule('Concealed Kong of Terminals', r'^([sbc][19])([SBC][19])(\2)(\1)\b', points=32))
        self.meldRules.append(Rule('Concealed Kong of Honors', r'^(d[brg]|w[eswn])(D[brg]|W[eswn])(\2)(\1)\b',
                                                    points=32))

        self.meldRules.append(Rule('Concealed Pung', r'^([SBC][2-8])(\1\1)\b', points=4))
        self.meldRules.append(Rule('Concealed Pung of Terminals', r'^([SBC][19])(\1\1)\b', points=8))
        self.meldRules.append(Rule('Concealed Pung of Honors', r'^(D[brg]|W[eswn])(\1\1)\b', points=8))

        self.meldRules.append(Rule('Pair of Own Wind', r'^([wW])([eswn])(\1\2) [mM]\2', points=2))
        self.meldRules.append(Rule('Pair of Round Wind', r'^([wW])([eswn])(\1\2) [mM].\2', points=2))
        self.meldRules.append(Rule('Pair of Dragons', r'^([dD][brg])(\1)\b', points=2))

def loadPredefinedRulesets():
    """add new predefined rulesets here"""
    if not PredefinedRuleset.classes:
        PredefinedRuleset.classes.add(ClassicalChinese)
