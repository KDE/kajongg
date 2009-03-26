#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""Copyright (C) 2009 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

"""use space as separator between melds
 s = stone :1 .. 9
 b = bamboo: 1 .. 9
 c = character: 1.. 9
 w = wind: eswn
 d = dragon: wrg (white, red, green)
 we use a special syntax for kans:
  c1c1c1c1 open kong
 c1c1c1C1 open kong, 4th tile was called for, completing a concealed pung.
    Needed for the limit game 'concealed true color game'
 c1C1C1c1 concealed declared kong
 C1C1C1C1 this would be a concealed undeclared kong. But since it is undeclared, it is handled
 as a pung. So this string would be split into pung C1C1C1 and single C1
 f = flower: 1 .. 4
 y = seasonal: 1 .. 4
 lower characters: tile is open
 upper characters: tile is concealed
  Morxxyd = said mah jongg,
       o is the own wind, r is the round wind,
       xx is the last drawn stone
       y defines where the last tile for the mah jongg comes from:
           d=discarded,
           w=wall,
           d=dead end,
           z=last tile of living end
           Z=last tile of living end, discarded
            k=robbing the kong,
           1=blessing of  heaven/earth
       d defines the declarations a player made
          a=call at beginning
  mor = did not say mah jongg
       o is the own wind, r is the round wind,
 L0500: limit 500 points
"""

import re, types, copy
from inspect import isclass

LIMIT = 5000

CONCEALED, EXPOSED, ALLSTATES = 1, 2, 3
SINGLE, PAIR, CHOW, PUNG, KONG, CLAIMEDKONG, ALLMELDS = 1, 2, 4, 8, 16, 32, 63

def meldName(meld):
    """convert int to speaking name"""
    if meld == ALLMELDS:
        return ''
    parts = []
    if SINGLE & meld:
        parts.append('single')
    if PAIR & meld:
        parts.append('pair')
    if CHOW & meld:
        parts.append('chow')
    if PUNG & meld:
        parts.append('pung')
    if KONG & meld:
        parts.append('kong')
    if CLAIMEDKONG & meld:
        parts.append('claimed kong')
    return '|'.join(parts)

def stateName(state):
    """convert int to speaking name"""
    if state == ALLSTATES:
        return ''
    parts = []
    if CONCEALED & state:
        parts.append('concealed')
    if EXPOSED & state:
        parts.append('exposed')
    return '|'.join(parts)


def tileSort(aVal, bVal):
    """we want to sort tiles for simpler regex patterns"""
    tileOrder = 'dwsbc'
    aPos = tileOrder.index(aVal[0].lower())
    bPos = tileOrder.index(bVal[0].lower())
    if aPos == bPos:
        return cmp(aVal.lower(), bVal.lower())
    return aPos - bPos

def meldSort(aVal, bVal):
    """sort the melds by their first tile"""
    return tileSort(aVal.content,bVal.content)

class Ruleset(object):
    """holds a full set of rules: splitRules,meldRules,handRules,mjRules,limitHands"""
    def __init__(self, name):
        self.name = name
        self.splitRules = []
        self.meldRules = []
        self.handRules = []
        self.mjRules = []
        self.limitHands = []
        self.loadSplitRules()
        if name == 'CCP':
            self.loadClassicalPatternRules()
        elif name == 'CCR':
            self.loadClassicalRegexRules()

    def loadSplitRules(self):
        """loads the split rules"""
        self.splitRules.append(Splitter('kong', r'([dwsbc][1-9eswnbrg])([DWSBC][1-9eswnbrg])(\2)(\2)'))
        self.splitRules.append(Splitter('pung', r'([DWSBC][1-9eswnbrg])(\1\1)'))
        for chi1 in xrange(1, 8):
            rule =  r'(?P<g>[SBC])(%d)((?P=g)%d)((?P=g)%d) ' % (chi1, chi1+1, chi1+2)
            self.splitRules.append(Splitter('chow', rule))
            # discontinuous chow:
            rule =  r'(?P<g>[SBC])(%d).*((?P=g)%d).*((?P=g)%d)' % (chi1, chi1+1, chi1+2)
            self.splitRules.append(Splitter('chow', rule))
            self.splitRules.append(Splitter('chow', rule))
        self.splitRules.append(Splitter('pair', r'([DWSBC][1-9eswnbrg])(\1)'))
        self.splitRules.append(Splitter('single', r'(..)'))

    def loadClassicalPatternRules(self):
        """classical chinese rules expressed by patterns, not complete"""
        self.mjRules.append(Rule('mah jongg', 'PMahJongg()', value=20))
        self.mjRules.append(Rule('last tile from wall', r'.*M..[A-Z]', value=2))
        self.mjRules.append(Rule('last tile completes simple pair', 'PLastTileCompletes(Simple(Pair))', value=2))
        self.mjRules.append(Rule('last tile completes pair of terminals or honours',
            'PLastTileCompletes(NoSimple(Pair))', value=4))

        self.handRules.append(Rule('own flower and own season',
                Regex(r'.* f(.).* y\1 .*m\1', ignoreCase=True), factor=1))
        self.handRules.append(Rule('all flowers', Regex(r'.*( f[eswn]){4,4}', ignoreCase=True), factor=1))
        self.handRules.append(Rule('all seasons', Regex(r'.*( y[eswn]){4,4}', ignoreCase=True), factor=1))
        self.handRules.append(Rule('three concealed pongs',  'PConcealed(PungKong)*3  +  Rest', factor=1))
        self.handRules.append(Rule('little 3 dragons', 'PDragons(PungKong)*2 +  Dragons(Pair) +   Rest', factor=1))
        self.handRules.append(Rule('big 3 dragons', 'PDragons(PungKong)*3  +  Rest', factor=2))
        self.handRules.append(Rule('kleine 4 Freuden', 'PWinds(PungKong)*3 + Winds(Pair) +   Rest', factor=1))
        self.handRules.append(Rule('große 4 Freuden', 'PWinds(PungKong)*4  +  Rest', factor=2))

        self.mjRules.append(Rule('zero point hand', Regex(r'.*/([dwsbc].00)*M', ignoreCase=True), factor=1))
        self.mjRules.append(Rule('no chow', 'PNoChow(MahJongg)', factor=1))
        self.mjRules.append(Rule('only concealed melds', 'PConcealed(MahJongg)', factor=1))
        self.mjRules.append(Rule('false color game',
                                        ['PHonours() + Character + NoBamboo(NoStone)*3' ,
                                        'PHonours() + Stone + NoBamboo(NoCharacter)*3' ,
                                        'PHonours() + Bamboo + NoStone(NoCharacter)*3'], factor=1 ))
        self.mjRules.append(Rule('true color game', 'POneColor(NoHonours(MahJongg))', factor=3))
        self.mjRules.append(Rule('only terminals and honours', 'PNoSimple(MahJongg)', factor=1))
        self.mjRules.append(Rule('only honours',  'PHonours(MahJongg)', factor=2))
        self.mjRules.append(Rule('won with last tile taken from wall', 'PMahJongg()', lastTileFrom='w', value=2))
        self.mjRules.append(Rule('won with last tile taken from dead wall', 'PMahJongg()',  lastTileFrom='d', factor=1))
        self.mjRules.append(Rule('won with last tile of wall', 'PMahJongg()', lastTileFrom='z', factor=1))
        self.mjRules.append(Rule('won with last tile of wall discarded', 'PMahJongg()', lastTileFrom='Z', factor=1))
        self.mjRules.append(Rule('robbing the kong', 'PMahJongg()', lastTileFrom='k', factor=1))
        self.mjRules.append(Rule('mah jongg with call at beginning', r'.*M.....a', factor=1))

        # limit hands:
        self.limitHands.append(Rule('blessing of heaven', r'.*Me...1'))
        self.limitHands.append(Rule('blessing of earth', r'.*M[swn]...1'))
        self.limitHands.append(Rule('concealed true color game',
                'PConcealed(ClaimedKongAsConcealed(OneColor(NoHonours(MahJongg))))'))
        self.limitHands.append(Rule('hidden treasure',
                'PConcealed(ClaimedKongAsConcealed(PungKong())*4+Pair())', lastTileFrom='w'))
        self.limitHands.append(Rule('all honours', 'PHonours(MahJongg)'))
        self.limitHands.append(Rule('all terminals', 'PTerminals(MahJongg)'))
        self.limitHands.append(Rule('winding snake',
                ['POneColor(PungKong(1)+Chow(2)+Chow(5)+PungKong(9)+Pair(8))',
               'POneColor(PungKong(1)+Chow(3)+Chow(6)+PungKong(9)+Pair(2))',
               'POneColor(PungKong(1)+Chow(2)+Chow(6)+PungKong(9)+Pair(5))']))
        self.limitHands.append(Rule('four kans', 'PKong()*4 + Rest'))
        self.limitHands.append(Rule('three great scholars', 'PDragons(PungKong)*3 + Rest'))
        self.limitHands.append(Rule('Vier Segen über der Tür', 'PWinds(PungKong)*4 + Rest'))
        self.limitHands.append(Rule('All greens', 'PAllGreen(MahJongg)'))
        self.limitHands.append(Rule('nine gates',
                'POneColor(Concealed(Pung(1)+Chow(2)+Chow(5)+Single(8)+Pung(9))+Exposed(Single))'))
        self.limitHands.append(Rule('thirteen orphans', "PBamboo(Single(1)+Single(9))+Character(Single(1)+Single(9))"
            "+Stone(Single(1)+Single(9))+Single('b')+Single('g')+Single('r')"
            "+Single('e')+Single('s')+Single('w')+Single('n')+Single(NoSimple)"))

        self.handRules.append(Rule('flower 1', Regex(r'.* fe ', ignoreCase=True), value=4))
        self.handRules.append(Rule('flower 2', Regex(r'.* fs ', ignoreCase=True), value=4))
        self.handRules.append(Rule('flower 3', Regex(r'.* fw ', ignoreCase=True), value=4))
        self.handRules.append(Rule('flower 4', Regex(r'.* fn ', ignoreCase=True), value=4))
        self.handRules.append(Rule('season 1', Regex(r'.* ye ', ignoreCase=True), value=4))
        self.handRules.append(Rule('season 2', Regex(r'.* ys ', ignoreCase=True), value=4))
        self.handRules.append(Rule('season 3', Regex(r'.* yw ', ignoreCase=True), value=4))
        self.handRules.append(Rule('season 4', Regex(r'.* yn ', ignoreCase=True), value=4))



        # doubling melds:
        self.meldRules.append(Rule('pung/kong of dragons', 'PDragons(PungKong)', factor=1))
        self.meldRules.append(Rule('pung/kong of own wind', 'POwnWind(PungKong)', factor=1))
        self.meldRules.append(Rule('pung/kong of round wind', 'PRoundWind(PungKong)', factor=1))

        # exposed melds:
        self.meldRules.append(Rule('exposed kong', 'PSimple(Exposed(Kong))', value=8))
        self.meldRules.append(Rule('exposed kong of terminals', 'PTerminals(Exposed(Kong))', value=16))
        self.meldRules.append(Rule('exposed kong of honours', 'PHonours(Exposed(Kong))', value=16))

        self.meldRules.append(Rule('exposed pung', 'PSimple(Exposed(Pung))', value=2))
        self.meldRules.append(Rule('exposed pung of terminals', 'PTerminals(Exposed(Pung))', value=4))
        self.meldRules.append(Rule('exposed pung of honours', 'PHonours(Exposed(Pung))', value=4))

        # concealed melds:
        self.meldRules.append(Rule('concealed kong', 'PSimple(Concealed(Kong))', value=16))
        self.meldRules.append(Rule('concealed kong of terminals', 'PTerminals(Concealed(Kong))', value=32))
        self.meldRules.append(Rule('concealed kong of honours', 'PHonours(Concealed(Kong))', value=32))

        self.meldRules.append(Rule('concealed pung', 'PSimple(Concealed(Pung))', value=4))
        self.meldRules.append(Rule('concealed pung of terminals', 'PTerminals(Concealed(Pung))', value=8))
        self.meldRules.append(Rule('concealed pung of honours', 'PHonours(Concealed(Pung))', value=8))

        self.meldRules.append(Rule('pair of own wind', 'POwnWind(Pair)', value=2))
        self.meldRules.append(Rule('pair of round wind', 'PRoundWind(Pair)', value=2))
        self.meldRules.append(Rule('pair of dragons', 'PDragons(Pair)', value=2))

    def loadClassicalRegexRules(self):
        """classical chinese rules expressed by regex, not complete"""
        self.mjRules.append(Rule('mah jongg',   r'.*M', value=20))
        self.mjRules.append(Rule('last tile from wall', r'.*M..[A-Z]', value=2))
        self.mjRules.append(Rule('last tile completes pair of 2..8', r'.* (.[2-8])\1 .*M..\1', value=2))
        self.mjRules.append(Rule('last tile completes pair of 1/9/wind/dragon', r'.* ((.[19])|([dwDW].))\1 .*M..\1',
                                                value=4))

        self.handRules.append(Rule('own flower and own season',
                Regex(r'.* f(.).* y\1 .*m\1', ignoreCase=True), factor=1))
        self.handRules.append(Rule('all flowers', Regex(r'.*( f[eswn]){4,4}',
                                                ignoreCase=True), factor=1))
        self.handRules.append(Rule('all seasons', Regex(r'.*( y[eswn]){4,4}',
                                                ignoreCase=True), factor=1))
        self.handRules.append(Rule('3 concealed pongs', Regex(r'.*/.*(([DWSBC][34]..).*?){3,}'), factor=1))
        self.handRules.append(Rule('little 3 dragons', Regex(r'.*/d2..d[34]..d[34]..',
                                                ignoreCase=True), factor=1))
        self.handRules.append(Rule('big 3 dragons', Regex(r'.*/d[34]..d[34]..d[34]..',
                                                ignoreCase=True), factor=2))
        self.handRules.append(Rule('kleine 4 Freuden', Regex(r'.*/.*w2..(w[34]..){3,3}',
                                                ignoreCase=True),  factor=1))
        self.handRules.append(Rule('große 4 Freuden', Regex(r'.*/.*(w[34]..){4,4}',
                                                ignoreCase=True), factor=2))

        self.mjRules.append(Rule('zero point hand', Regex(r'.*/([dwsbc].00)*M',
                                                ignoreCase=True), factor=1))
        self.mjRules.append(Rule('no chow', Regex(r'.*/([dwsbc][^0]..)*M',
                                                ignoreCase=True), factor=1))
        self.mjRules.append(Rule('only concealed melds', r'.*/([DWSBC]...)*M', factor=1))
        self.mjRules.append(Rule('false color game', Regex(r'.*/([dw]...){1,}(([sbc])...)(\3...)*M',
                                                ignoreCase=True), factor=1))
        self.mjRules.append(Rule('true color game',   Regex(r'.*/(([sbc])...)(\2...)*M',
                                                ignoreCase=True), factor=3))
        self.mjRules.append(Rule('only 1/9 and honours', Regex(r'( (([dw].)|(.[19])){1,4})* /.*M',
                                                ignoreCase=True), factor=1 ))
        self.mjRules.append(Rule('only honours', Regex(r'.*/([dw]...)*M',
                                                ignoreCase=True), factor=2 ))
        self.mjRules.append(Rule('won with last tile taken from wall', r'.*M....w', value=2))
        self.mjRules.append(Rule('won with last tile taken from dead wall', r'.*M....d', factor=1))
        self.mjRules.append(Rule('won with last tile of wall', r'.*M....z', factor=1))
        self.mjRules.append(Rule('won with last tile of wall discarded', r'.*M....Z', factor=1))
        self.mjRules.append(Rule('robbing the kong', r'.*M....k', factor=1))
        self.mjRules.append(Rule('mah jongg with call at beginning', r'.*M.....a', factor=1))

        # limit hands:
        self.limitHands.append(Rule('blessing of heaven', r'.*Me...1'))
        self.limitHands.append(Rule('blessing of earth', r'.*M[swn]...1'))
        # concealed true color game ist falsch, da es nicht auf korrekte Aufteilung in Gruppen achtet
        self.limitHands.append(Rule('concealed true color game',   r'( ([sbc][1-9])*([SBC].){1,3})* [fy/]'))
        self.limitHands.append(Rule('hidden treasure', MJHiddenTreasure()))
        self.limitHands.append(Rule('all honours', r'.*/([DWdw]...)*M'))
        self.limitHands.append(Rule('all terminals', r'( (.[19]){1,4})* [fy/]'))
        self.limitHands.append(Rule('winding snake',
                                           ['POneColor(PungKong(1)+Chow(2)+Chow(5)+PungKong(9)+Pair(8))',
                                           'POneColor(PungKong(1)+Chow(3)+Chow(6)+PungKong(9)+Pair(2))',
                                           'POneColor(PungKong(1)+Chow(2)+Chow(6)+PungKong(9)+Pair(5))']))
        self.limitHands.append(Rule('four kans', r'.*/((....)*(.4..)(....)?){4,4}'))
        self.limitHands.append(Rule('three great scholars', r'.*/[Dd][34]..[Dd][34]..[Dd][34]'))
        self.limitHands.append(Rule('Vier Segen über der Tür', r'.*/.*([Ww][34]..){4,4}'))
        self.limitHands.append(Rule('All greens', r'( |[bB][23468]|[dD]g)* [fy/]'))
        self.limitHands.append(Rule('nine gates', r'(S1S1S1S2S3S4S5S6S7S8S9S9S9 s.|'
                'B1B1B1B2B3B4B5B6B7B8B9B9B9 b.|C1C1C1C2C3C4C5C6C7C8C9C9C9 c.)'))
        self.limitHands.append(Rule('thirteen orphans', Regex(
            r'( db){1,2}( dg){1,2}( dr){1,2}( we){1,2}( wn){1,2}( ws){1,2}( ww){1,2}'
            '( s1){1,2}( s9){1,2}( b1){1,2}( b9){1,2}( c1){1,2}( c9){1,2} [fy/].*M', ignoreCase=True), value=LIMIT))


        self.handRules.append(Rule('flower 1', Regex(r'.* fe ', ignoreCase=True), value=4))
        self.handRules.append(Rule('flower 2', Regex(r'.* fs ', ignoreCase=True), value=4))
        self.handRules.append(Rule('flower 3', Regex(r'.* fw ', ignoreCase=True), value=4))
        self.handRules.append(Rule('flower 4', Regex(r'.* fn ', ignoreCase=True), value=4))
        self.handRules.append(Rule('season 1', Regex(r'.* ye ', ignoreCase=True), value=4))
        self.handRules.append(Rule('season 2', Regex(r'.* ys ', ignoreCase=True), value=4))
        self.handRules.append(Rule('season 3', Regex(r'.* yw ', ignoreCase=True), value=4))
        self.handRules.append(Rule('season 4', Regex(r'.* yn ', ignoreCase=True), value=4))

        # doubling melds:
        self.meldRules.append(Rule('pung/kong of dragons', r'([dD][brg])\1\1', factor=1))
        self.meldRules.append(Rule('pung/kong of own wind', r'(([wW])([eswn])){3,4}.*[mM]\3', factor=1))
        self.meldRules.append(Rule('pung/kong of round wind', r'(([wW])([eswn])){3,4}.*[mM].\3', factor=1))

        # exposed melds:
        self.meldRules.append(Rule('exposed kong', r'([sbc])([2-8])(\1\2\1\2.\2)[mM]', value=8))
        self.meldRules.append(Rule('exposed kong 1/9', r'([sbc])([19])(\1\2\1\2.\2)[mM]', value=16))
        self.meldRules.append(Rule('exposed kong of honours', r'([dw])([brgeswn])(\1\2\1\2.\2)[mM]', value=16))

        self.meldRules.append(Rule('exposed pung', r'([sbc][2-8])(\1\1)[mM]', value=2))
        self.meldRules.append(Rule('exposed pung 1/9', r'([sbc][19])(\1\1)[mM]', value=4))
        self.meldRules.append(Rule('exposed pung of honours', r'(d[brg]|w[eswn])(\1\1)[mM]', value=4))

        # concealed melds:
        self.meldRules.append(Rule('concealed kong', r'([sbc][2-8])([SBC][2-8])(\2)(\1)[mM]', value=16))
        self.meldRules.append(Rule('concealed kong 1/9', r'([sbc][19])([SBC][19])(\2)(\1)[mM]', value=32))
        self.meldRules.append(Rule('concealed kong of honours', r'(d[brg]|w[eswn])(D[brg]|W[eswn])(\2)(\1)[mM]',
                                                    value=32))

        self.meldRules.append(Rule('concealed pung', r'([SBC][2-8])(\1\1)[mM]', value=4))
        self.meldRules.append(Rule('concealed pung 1/9', r'([SBC][19])(\1\1)[mM]', value=8))
        self.meldRules.append(Rule('concealed pung of honours', r'(D[brg]|W[eswn])(\1\1)[mM]', value=8))

        self.meldRules.append(Rule('pair of own wind', r'([wW])([eswn])(\1\2)[mM]\2', value=2))
        self.meldRules.append(Rule('pair of round wind', r'([wW])([eswn])(\1\2)[mM].\2', value=2))
        self.meldRules.append(Rule('pair of dragons', r'([dD][brg])(\1)[mM]', value=2))


class Hand(object):
    """represent the hand to be evaluated"""
    def __init__(self, ruleset, tiles, mjStr):
        """evaluate tiles with mjStr using ruleset"""
        self.ruleset = ruleset
        self.tiles = tiles
        self.original = None
        self.mjStr = mjStr
        self.fsMelds = []
        self.invalidMelds = []
        self.foundLimitHands = None
        self.normalized = ''
        self.basePoints = 0
        self.factor = 0
        self.melds = None
        self.total = 0
        self.explain = None
        self.__summary = None
        self.separateMelds()
        self.applyMeldRules()

    def split(self, rest):
        """split self.tiles into melds as good as possible"""
        melds = []
        for rule in self.ruleset.splitRules:
            splits = rule.apply(rest)
            while len(splits) >1:
                for split in splits[:-1]:
                    melds.append(Meld(split))
                rest = splits[-1]
                splits = rule.apply(rest)
            if len(splits) == 0:
                break
        if len(splits) == 1 :
            assert Meld(splits[0]).isValid()   # or the splitRules are wrong
        return melds

    def countMelds(self, key):
        """count melds having key"""
        result = 0
        if isinstance(key, str):
            for meld in self.melds:
                if meld.tileType() in key:
                    result += 1
        else:
            for meld in self.melds:
                if key(meld):
                    result += 1
        return result

    def matchingRules(self, rules):
        """return all matching rules for this hand"""
        return set(rule for rule in rules if rule.applies(self, self.melds))

    def applyMeldRules(self):
        """apply all rules for single melds"""
        for  rule in self.ruleset.meldRules:
            for meld in self.melds + self.fsMelds:
                if rule.applies(self, [meld]):
                    if rule.value:
                        meld.basePoints += rule.value
                    if rule.factor:
                        meld.factor += rule.factor

    def useRule(self, rule):
        """use this rule for scoring"""
        if rule.value:
            self.basePoints += rule.value
        if rule.factor:
            self.factor += rule.factor
        self.explain.append('%s: %d base points, %d factor' % ( rule.name,  rule.value, rule.factor))

    def separateMelds(self):
        """build a meld list from the hand string"""
        self.explain = []
        self.total = 0
        self.original = str(self.tiles)
        self.tiles = str(self.original)
        splits = self.tiles.split()
        self.melds = []
        rest = []
        for split in splits:
            if len(split) > 8:
                rest.append(split)
                continue
            meld = Meld(split)
            if split[0].islower() or split[0] in 'mM' or meld.isValid():
                self.melds.append(meld)
            else:
                rest.append(split)
        if len(rest) > 1:
            raise Exception('hand has more than 1 unsorted part: ', self.original)
        if len(rest) == 1:
            rest = rest[0]
            rest = ''.join(sorted([rest[x:x+2] for x in range(0, len(rest), 2)]))
            self.melds.extend(self.split(rest))
        self.fsMelds = list()
        self.invalidMelds = list()
        for meld in self.melds:
            if not meld.isValid():
                self.invalidMelds.append(meld)
            if meld.tileType() in 'fy':
                self.fsMelds.append(meld)
        for meld in self.fsMelds:
            self.melds.remove(meld)

    def score(self):
        """returns the value of the hand. Also sets some attributes with intermediary results"""
        tileCount = sum(len(meld) for meld in self.melds)
        kanCount = self.countMelds(Meld.isKong)
        if self.invalidMelds:
            raise Exception('has invalid melds: ' + ','.join(meld.str for meld in self.invalidMelds))
        won = self.mjStr[0] == 'M'
        if won and tileCount - kanCount != 14:
            raise Exception('wrong number of tiles for mah jongg: ' + self.tiles)
        if not won and tileCount < 13:
            raise Exception('no mahjongg and less than 13 tiles in ' + self.tiles)

        self.basePoints = sum(meld.basePoints for meld in self.melds)
        self.factor = sum(meld.factor for meld in self.melds)
        self.original += self.summary
        self.normalized =  ' ' + ' '.join(sorted([meld.content for meld in self.melds], tileSort))+ self.summary
        if won:
            self.foundLimitHands = self.matchingRules(self.ruleset.limitHands)
            if len(self.foundLimitHands):  # we have a limit hand
                for rule in self.foundLimitHands:
                    self.explain.append('limit hand with %d points:%s' % (LIMIT,  rule.name))
                self.total = LIMIT
        if not self.total: # we have no limit hand:
            for meld in self.melds:
                self.explain.append(meld.__str__())
            for rule in self.matchingRules(self.ruleset.handRules):
                self.useRule(rule)
            if self.mjStr[0] == 'M':
                for rule in self.matchingRules(self.ruleset.mjRules):
                    self.useRule(rule)
            self.total = self.basePoints * (2**self.factor)
        return self.total

    def getSummary(self):
        """returns a summarizing string for this hand"""
        if self.__summary is None:
            self.__summary = ' ' + ' '.join(sorted(meld.content for meld in self.fsMelds)) if len(self.fsMelds) else ''
            self.__summary += ' /' + ''.join(sorted([meld.regex() for meld in self.melds], tileSort))
        return self.__summary

    summary = property(getSummary)

    def __str__(self):
        return ' '.join(x.content for x in self.melds) + self.summary

class Variant(object):
    """all classes derived from variant are allowed to be used
    as rule variants. Examples: Pattern and all its derivations, Regex, MJHiddenTreasure"""

    def applies(self, hand, melds):
        """when deriving from variant, please override this. It should return bool."""
        pass

class Rule(object):
    """a mahjongg rule with a name, matching variants, and resulting score.
    The rule applies if at least one of the variants matches the hand"""
    def __init__(self, name, variants,  lastTileFrom=None, value = 0,  factor = 0):
        self.name = name
        self.lastTileFrom = lastTileFrom
        self.value = value
        self.factor = factor
        self.variants = []
        if not variants:
            return  # may happen with special programmed rules
        if not isinstance(variants, list):
            variants = list([variants])
        for variant in variants:
            if isinstance(variant, Variant):
                self.variants.append(variant)
            elif isinstance(variant, str):
                if variant[0] == 'P':
                    newVariant = eval(variant[1:], {"__builtins__":None}, Pattern.evalDict)
                    newVariant.expression = variant
                    self.variants.append(newVariant)
                else:
                    self.variants.append(Regex(variant))
            elif type(variant) == type:
                self.variants.append(variant())
            else:
                self.variants.append(Pattern(variant))

    def applies(self, hand, melds):
        """does the rule apply to this hand?"""
        if self.lastTileFrom is not None:
            if hand.mjStr[5] != self.lastTileFrom:
                print 'wrong last tile'
                return False
        return any(variant.applies(hand, melds) for variant in self.variants)

class Regex(Variant):
    """use a regular expression for defining a variant"""
    def __init__(self, rule,  ignoreCase = False):
        Variant.__init__(self)
        self.rule = rule
        self.ignoreCase = ignoreCase
        self.compiled = re.compile(rule)

    def applies(self, hand, melds):
        """does this regex match?"""
        if len(melds) == 1:
            meldStrings = [melds[0].content]
        else:
            meldStrings = [hand.original,  hand.normalized]
        for meldString in meldStrings:
            if self.ignoreCase:
                match = self.compiled.match(meldString.lower() + hand.mjStr)
            else:
                match = self.compiled.match(meldString + hand.mjStr)
            if match:
                break
        return match

class Pattern(Variant):
    """a pattern representing combinations for a hand"""
    def __init__(self, slots=None ):
        Variant.__init__(self)
        self.expression = ''
        self.restSlot = None
        if slots is None:
            slots = [Slot()]
        else:
            slots = slots if isinstance(slots, list) else list([slots])
        self.slots = []
        self.isMahJonggPattern = False
        self.oneColor = False
        for slot in slots:
            if isinstance(slot, types.FunctionType):
                slot = slot()
            if isinstance(slot, Pattern):
                extent = slot.slots
                self.isMahJonggPattern = slot.isMahJonggPattern
                self.oneColor = slot.oneColor
            elif isinstance(slot, (int, str)):
                extent = [Slot(slot)]
            elif type(slot) == type:
                ancestor = slot()
                if isinstance(ancestor, Slot):
                    extent = [ancestor]
                else:
                    extent = ancestor.slots
            else:
                extent = [slot]
            self.slots.extend(extent)

    evalDict = dict()

    def buildEvalDict():
        """build an environment for eval:"""
        thisModule = __import__(__name__)
        for attrName in globals():
            obj = getattr(thisModule, attrName)
            if isclass(obj) and Pattern in obj.__mro__:
                cName = obj.__name__
                if cName not in ('SlotChanger', 'PairChanger'):
                    Pattern.evalDict[cName] = obj

    buildEvalDict = staticmethod(buildEvalDict)

    @staticmethod   # quieten pylint
    def normalizePatternArg(pattern=None):
        """we accept many different forms for the parameter,
        convert them all to a Pattern"""
        if not isinstance(pattern, Pattern):
            if pattern is None:
                pattern = Pattern()
            elif isinstance(pattern, str):
                value = pattern
                pattern = Pattern()
                slot = pattern.slots[0]
                if isinstance(value, int):
                    slot.content = 's%db%dc%d' % (value, value, value)
                elif value in '123456789':
                    slot.content = 's%sb%sc%s' % (value, value, value)
                elif value in 'eswn':
                    slot.content = 'w'+value
                elif value in 'bgr':
                    slot.content = 'd'+value
            elif isinstance(pattern, Slot):
                pattern = Pattern(pattern)
            elif type(pattern) == type:
                pattern = pattern()
                if isinstance(pattern, Slot):
                    pattern = Pattern(pattern)
            elif isinstance(pattern, types.FunctionType):
                pattern = pattern()
        return pattern

    def __str__(self):
        """printable form of pattern"""
        result = self.expression
        if self.oneColor:
            result = 'oneColor'
        for slot in self.slots:
            result += ' ' + slot.__str__()
        return result

    def __add__(self, other):
        """adds the slots of other pattern"""
        other = self.normalizePatternArg(other)
        self.slots.extend(copy.deepcopy(other.slots))
        return self

    def __mul__(self, other):
        """appends own slots multiple times"""
        origSlots = len(self.slots)
        for idx in range(1, other):
            assert idx # quiten pylint
            self.slots.extend(copy.deepcopy(self.slots[:origSlots]))
        return self

    def clearSlots(self, melds):
        """remove all melds from the slots"""
        for slot in self.slots:
            slot.meld = None
        for meld in melds:
            meld.slot = None

    def __discard(self, melds):
        """discard still unassigned melds into the rest slot"""
        if not self.restSlot:
            return False
        for meld in melds:
            if meld.slot is None:
                meld.slot = self.restSlot
                self.restSlot.meld = meld
        return True

    def __assignMelds(self, melds, mjStr):
        """try to assign all melds to our slots"""
        if len(melds) == 0:
            return True
        self.restSlot = None
        for slot in self.slots:
            if slot.isRestSlot:
                slot.candidates = []
                self.restSlot = slot
            else:
                slot.candidates = [meld for meld in melds if slot.takes(meld, mjStr)]
        assignCount = 0
        for matchLevel in range(1, len(melds)+1):
            assigned = True
            while assigned:
                assigned = False
                for slot in self.slots:
                    if slot.isRestSlot:
                        continue
                    if slot.meld is not None:
                        continue
                    slot.candidates = list(meld for meld in slot.candidates if meld.slot is None)
                    if len(slot.candidates) == 0:
                        continue
                    if matchLevel >= len(slot.candidates):
                        slot.meld = slot.candidates[0]
                        slot.candidates[0].slot = slot
                        assigned = True
                        assignCount += 1
                        if assignCount == len(melds):
                            return True
        return self.__discard(melds)

    def applies(self, hand, melds):
        """does this pattern match the hand?"""
        if self.isMahJonggPattern and hand.mjStr[0] != 'M':
            return False
        if self.oneColor:
            foundColor = None
            for meld in melds:
                tileType = meld.content[0].lower()
                if tileType not in 'sbc':
                    continue
                if foundColor is None:
                    foundColor = tileType
                else:
                    if foundColor != tileType:
                        return False

        if not isinstance(melds, list):
            melds = list([melds])
        self.clearSlots(melds)
        if len(melds) == 1:
            return self.slots[0].takes(melds[0], hand.mjStr)
        if not self.__assignMelds(melds, hand.mjStr):
            return False
        result = True
        for slot in self.slots:
            result = result and slot.meld is not None
        for meld in melds:
            result = result and meld.slot is not None
        return result

class Splitter(object):
    """a regex with a name for splitting concealed and yet unsplitted tiles into melds"""
    def __init__(self, name,  rule):
        self.name = name
        self.rule = rule
        self.compiled = re.compile(rule)

    def apply(self, split):
        """work the found melds in reverse order because we remove them from the rest:"""
        if len(split) == 0:
            return []
        result = []
        for found in reversed(list(self.compiled.finditer(split))):
            operand = ''
            for group in found.groups():
                if group is not None:
                    operand += group
            if len(operand):
                result.append(operand)
                # remove the found meld from this split
                for group in range(len(found.groups()), 0, -1):
                    start = found.start(group)
                    end = found.end(group)
                    split = split[:start] + split[end:]
        result.reverse()
        result.append(split) # append always!!!
        return result


class Pairs(object):
    """base class for Meld and Slot"""
    def __init__(self):
        self.__content = ''
        self._contentPairs = None

    def getContent(self):
        """this getter sets the whole content in one string"""
        return self.__content

    def setContent(self, content):
        """this setter sets the whole content in one string"""
        self.__content = content
        self._contentPairs = None

    def getContentPairs(self):
        """this getter returns a list of the content pairs"""
        if self._contentPairs is None:
            self._contentPairs =  [self.__content[idx:idx+2] \
                        for idx in range(0, len(self.__content), 2)]
        return self._contentPairs

    content = property(getContent, setContent)
    contentPairs = property(getContentPairs)


class Meld(Pairs):
    """represents a meld"""

    tileNames = {'s': 'stone' , 'b': 'bamboo', 'c':'character', 'w':'wind',
    'd':'dragon', 'f':'flower', 'y':'season'}
    valueNames = {'b': 'white', 'r':'red', 'g':'green', 'e':'east', 's': 'south',
        'w':'west', 'n':'north', 'O':'own wind', 'R':'round wind'}
    for valNameIdx in range(1, 10):
        valueNames[str(valNameIdx)] = str(valNameIdx)

    def __init__(self, content):
        """init the meld: content is a single string with 2 chars for every meld"""
        Pairs.__init__(self)
        self.__valid = False
        self.basePoints = 0
        self.factor = 0
        self.name = None
        self.meldType = None
        self.slot = None
        self.tiles = []
        self.content = content

    def __len__(self):
        """how many tiles do we have?"""
        return len(self.tiles) if self.tiles else len(self.content)//2

    def __str__(self):
        """make meld printable"""
        which = Meld.tileNames[self.content[0].lower()]
        value = Meld.valueNames[self.content[1]]
        if not self.isColor():
            which, value = value, which
        pStr = ' points=%d' % self.basePoints if self.basePoints else ''
        fStr = ' factor=%d' % self.factor if self.factor else ''
        return '[%s %s of %s %s]%s%s' % (stateName(self.state),
                        meldName(self.meldType), which, value, pStr, fStr)

    def __getitem__(self, index):
        """Meld[x] returns Tile # x """
        return self.tiles[index]

    def isValid(self):
        """is it valid?"""
        return self.__valid

    def __isChow(self):
        """expensive, but this is only computed once per meld"""
        result = False
        if len(self) == 3:
            startChar = self.content[0].lower()
            if startChar in 'sbc':
                values = [int(self.content[x]) for x in (1, 3, 5)]
                if values[1] == values[0] + 1 and values[2] == values[0] + 2:
                    result = True
        return result

    def __getState(self):
        """compute state from self.content"""
        firsts = self.content[0::2]
        if firsts.islower():
            return EXPOSED
        elif len(self) == 4 and firsts[1].isupper() and firsts[2].isupper():
            return CONCEALED
        elif len(self) == 4:
            return EXPOSED
        else:
            return CONCEALED

    def __setState(self, state):
        """change self.content to new state"""
        content = self.content
        print 'state,oldcontent:', state, self.content
        if state == EXPOSED:
            if self.meldType == CLAIMEDKONG:
                self.content = content[:6].lower() + content[6].upper() + content[7]
            else:
                self.content = content.lower()
        elif state == CONCEALED:
            self.content = ''.join(pair[0].upper()+pair[1] for pair in self.contentPairs)
            if len(self) == 4:
                self.content = self.content[0].lower() + self.content[1:6] + self.content[6:].lower()
        else:
            raise Exception('meld.setState: illegal state %d' % state)
        print 'state,newcontent:', state, self.content

    state = property(__getState, __setState)

    def _getMeldType(self):
        """compute meld type"""
        content = self.content # optimize access speed
        assert content[0].lower() in 'dwsbcfy'
        if len(self) == 1:
            result = SINGLE
        elif len(self) == 2:
            result = PAIR
        elif len(self)== 4:
            if content.upper() == content:
                result = PUNG
                self.__valid = False
            elif content[:6].lower() + content[6].upper() + content[7] == content:
                result = CLAIMEDKONG
            else:
                result = KONG
        elif self.__isChow():
            result = CHOW
        elif len(self) == 3:
            result = PUNG
        else:
            raise Exception('invalid meld:'+content)
        if result == CHOW:
            assert content[::2] == content[0] * 3
        else:
            assert (content[:2] * len(self)).lower() == content.lower()
        return result

    def tileType(self):
        """return one of d w s b c f y"""
        return self.content[0].lower()

    def isDragon(self):
        """is it a meld of dragons?"""
        return self.content[0] in 'dD'

    def isWind(self):
        """is it a meld of winds?"""
        return self.content[0] in 'wW'

    def isColor(self):
        """is it a meld of colors?"""
        return self.content[0] in 'sSbBcC'

    def isKong(self):
        """is it a kong?"""
        return self.meldType in (KONG,  CLAIMEDKONG)

    def isClaimedKong(self):
        """is it a kong?"""
        return self.meldType == CLAIMEDKONG

    def isPung(self):
        """is it a pung?"""
        return self.meldType == PUNG

    def isChow(self):
        """is it a chow?"""
        return self.meldType == CHOW

    def isPair(self):
        """is it a pair?"""
        return self.meldType == PAIR

    def regex(self):
        """a string containing the tile type, the meld size and its value. For Chow, return size 0.
        Example: C304 is a concealed pung of characters with 4 base points
        """
        myLen = 0 if self.meldType == CHOW else len(self)
        str0 = self.content[2 if self.meldType == KONG else 0]
        return '%s%s%02d' % (str0,  str(myLen), self.basePoints)

    def getContent(self):
        """getter for content"""
        return Pairs.getContent(self)

    def setContent(self, content):
        """assign new content to this meld"""
        if not content:
            raise Exception('Meld.content = ""')
        Pairs.setContent(self, content)
        self.__valid = True
        self.name = 'not a meld'
        if len(content) not in (2, 4, 6, 8):
            raise Exception('contentlen not in 2468: %s' % content)
            self.__valid = False
            return
        self.meldType = self._getMeldType()
        self.name = meldName(self.meldType)

    content = property(getContent, setContent)

class Slot(Pairs):
    """placeholder for a meld (from single to kong)"""
    def __init__(self, value=None):
        Pairs.__init__(self)
        self.meldType =  ALLMELDS
        self.content = 'd.w.s.b.c.'
        self.state = ALLSTATES
        self.candidates = []
        self.meld = None
        self.isRestSlot = False
        self.claimedKongAsConcealed = False
        if value:
            if isinstance(value, int):
                self.content = 's%db%dc%d' % (value, value, value)
            elif value in '123456789':
                self.content = 's%sb%sc%s' % (value, value, value)
            elif value in 'eswn':
                self.content = 'w'+value
            elif value in 'bgr':
                self.content = 'd'+value

    def __str__(self):
        """printable form of this meld"""
        return '[%s %s %s%s%s]%s' % (stateName(self.state),
                    meldName(self.meldType), self.content, ' rest' if self.isRestSlot else '',
                    'claimedKongAsConcealed' if self.claimedKongAsConcealed else '',
                    ' holding %s' % (self.meld.__str__()) if self.meld else '')

    def minSize(self):
        """the minimum meld size for this slot"""
        if SINGLE & self.meldType: # smallest first
            return 1
        if PAIR & self.meldType:
            return 2
        if CHOW & self.meldType:
            return 3
        if PUNG & self.meldType:
            return 3
        if KONG & self.meldType:
            return 4
        if CLAIMEDKONG & self.meldType:
            return 4
        raise Exception('minSize: unknown meldType %d' % self.meldType)

    def maxSize(self):
        """the maximum meld size for this slot"""
        if KONG & self.meldType: # biggest first
            return 4
        if CLAIMEDKONG & self.meldType:
            return 4
        if PUNG & self.meldType:
            return 3
        if CHOW & self.meldType:
            return 3
        if PAIR & self.meldType:
            return 2
        if SINGLE & self.meldType:
            return 1
        raise Exception('maxSize: unknown meldType %d' % self.meldType)

    def takes(self, meld, mjStr):
        """does the slot take this meld?"""
        if not self.minSize() <= len(meld) <= self.maxSize() :
            return False
        meldstr = meld.content[0].lower() + meld.content[1]
        if 'wO' in self.content:
            if meldstr == 'w' + mjStr[1]:
                return True
        if 'wR' in self.content:
            if meldstr == 'w' + mjStr[2]:
                return True
        takesValues = self.content[::2]
        if meldstr[0] not in takesValues:
            return False
        if meldstr not in self.content and meldstr[0] + '.' not in self.content:
            return False
        if self.claimedKongAsConcealed and meld.meldType & CLAIMEDKONG:
            meldState = CONCEALED
            meldType = KONG
        else:
            meldState = meld.state
            meldType = meld.meldType
        return meldState & self.state and meldType & self.meldType

class MJHiddenTreasure(Variant):
    """just an example for a special variant"""

    def applies(self, hand, melds):
        """is this a hidden treasure?"""
        if hand.mjStr[5] != 'w':  # last tile from wall
            return False
        matchingMelds = 0
        for meld in melds:
            if ((meld.isPung() or meld.isKong()) and meld.state == CONCEALED) \
                or meld.isClaimedKong():
                matchingMelds += 1
        return matchingMelds == 4

class Rest(Pattern):
    """a special slot holding all unused tiles"""
    def __init__(self, other=None):
        Pattern.__init__(self, other)
        assert len(self.slots) == 1
        self.slots[0].isRestSlot = True

class SlotChanger(Pattern):
    """a helper class letting us write shorter classes"""
    def __init__(self, other=None):
        Pattern.__init__(self, other)
        for slot in self.slots:
            self.changeSlot(slot)

    def changeSlot(self, slot):
        """override this in the derived classes"""
        pass

class Single(SlotChanger):
    """only allow singles for all slots in this pattern"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self     # quieten pylint about 'method could be a function'
        slot.meldType = SINGLE

class Pair(SlotChanger):
    """only allow pairs for all slots in this pattern"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.meldType = PAIR

class AllGreen(SlotChanger):
    """only allow real greens for all slots in this pattern. Used for the limit hand 'All Greens'"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.content = 'b2b3b4b6b8dg'

class ChowPungKong(SlotChanger):
    """only allow chow,pung,kong for all slots in this pattern"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.meldType = CHOW | PUNG | KONG | CLAIMEDKONG

class PungKong(SlotChanger):
    """only allow pung,kong for all slots in this pattern"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.meldType = PUNG | KONG | CLAIMEDKONG

class Pung(SlotChanger):
    """only allow pung for all slots in this pattern"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.meldType = PUNG

class Kong(SlotChanger):
    """only allow kong for all slots in this pattern"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.meldType = KONG|CLAIMEDKONG

class ClaimedKong(SlotChanger):
    """only allow claimed kong for all slots in this pattern"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.meldType = CLAIMEDKONG

class Chow(SlotChanger):
    """only allow chow for all slots in this pattern"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.meldType = CHOW

class NoChow(SlotChanger):
    """no chow in any slot"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.meldType &= SINGLE|PAIR|PUNG|KONG|CLAIMEDKONG

class Concealed(SlotChanger):
    """only allow concealed melds in all slots"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.state = CONCEALED

class Exposed(SlotChanger):
    """only allow exposed melds in all slots"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.state = EXPOSED

class Honours(SlotChanger):
    """only allow honours in all slots"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.content = ''.join(pair for pair in slot.contentPairs if pair[0] in 'dw')

class NoHonours(SlotChanger):
    """no honours in any slot"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.content = ''.join(pair for pair in slot.contentPairs if pair[0] not in 'dw')

class Winds(SlotChanger):
    """only allow winds in all slots"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.content = ''.join(pair for pair in slot.contentPairs if pair[0] == 'w')

class Dragons(SlotChanger):
    """only allow dragons in all slots"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.content = ''.join(pair for pair in slot.contentPairs if pair[0]  == 'd')

class OwnWind(SlotChanger):
    """only allow own wind in all slots"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.content = ''.join('wO' for pair in slot.contentPairs if pair[0]  == 'w')

class RoundWind(SlotChanger):
    """only allow round wind in all slots"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.content = ''.join('wR' for pair in slot.contentPairs if pair[0]  == 'w')

class Stone(SlotChanger):
    """no stone in any slot"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.content = ''.join(pair for pair in slot.contentPairs if pair[0] =='s')

class OneColor(Pattern):
    """disables all  but stones"""
    def __init__(self, other=None):
        Pattern.__init__(self, other)
        self.oneColor = True

class Bamboo(SlotChanger):
    """disables all  but bamboos"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.content = ''.join(pair for pair in slot.contentPairs if pair[0] =='b')

class Character(SlotChanger):
    """disables all  but characters"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.content = ''.join(pair for pair in slot.contentPairs if pair[0] =='c')

class NoBamboo(SlotChanger):
    """disables all  bamboos"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.content = ''.join(pair for pair in slot.contentPairs if pair[0]!='b')

class NoCharacter(SlotChanger):
    """disables all  characters"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.content = ''.join(pair for pair in slot.contentPairs if pair[0]!='c')

class NoStone(SlotChanger):
    """disables all  stones"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self     # quieten pylint about 'method could be a function'
        slot.content = ''.join(pair for pair in slot.contentPairs if pair[0]!='s')

class PairChanger(SlotChanger):
    """virtual abstract helper function for slot changers exetensively working on pairs"""

    def changeSlot(self, slot):
        """change a slot"""
        assert self
        slot.content = ''.join(self.changePair(pair) for pair in slot.contentPairs)

    def changePair(self, pair):
        """override this in derivations"""
        pass

class Terminals(PairChanger):
    """only terminals"""
    def changePair(self, pair):
        """change this pair"""
        assert self
        if pair[1] in '19':
            return pair
        elif pair[1] == '.' and pair[0] in 'sbc':
            return pair[0]+'1' + pair[0]+'9'
        return ''

class Simple(PairChanger):
    """only simples"""
    def changePair(self, pair):
        """change this pair"""
        assert self
        if pair[1] in '2345678':
            return pair
        elif pair[1] == '.' and pair[0] in 'sbc':
            return ''.join(pair[0]+str(val) for val in range(2, 9))
        return ''

class NoSimple(PairChanger):
    """disables all  simples"""
    def changePair(self, pair):
        """change this pair"""
        assert self
        if pair[1] not in '.2345678':
            return pair
        elif pair[0] not in 'sbc':
            return pair
        elif pair[0] in 'sbc' and pair[1] == '.':
            return pair[0]+'1' + pair[0]+'9'
        return ''

class LastTileCompletes(Pattern):
    """has its own applies method"""
    def applies(self, hand, melds):
        """does this rule apply?"""
        assert melds        # quieten pylint about unused argument
        if hand.mjStr[0] != 'M':
            return
        assert len(self.slots) == 1
        slot = self.slots[0]
        for meld in hand.melds:
            result = meld.content == hand.mjStr[3:5]*2 and slot.takes(meld, hand.mjStr)
            if result:
                break
        return result

class MahJongg(Pattern):
    """defines slots for a standard mah jongg"""
    def __init__(self):
        slots = [ChowPungKong, ChowPungKong, ChowPungKong, ChowPungKong, Pair]
        Pattern.__init__(self, slots)
        self.isMahJonggPattern = True

class ClaimedKongAsConcealed(SlotChanger):
    """slots treat claimed kong as concealed"""
    def changeSlot(self, slot):
        """change a slot"""
        assert self     # quieten pylint about 'method could be a function'
        slot.claimedKongAsConcealed = True

Pattern.buildEvalDict()
