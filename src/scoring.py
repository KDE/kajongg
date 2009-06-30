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

"""

The scoring engine expects all information in one string.
This string consists of several parts:

1. one ore more strings with tiles. You should pass a separate string for
every meld and one string for all other tiles. That string will also be split
into melds if possible.

2. a string starting with M or m with additional information:
M stands for a won game, m for the others

3. a string starting with L containing information about the last tile

4. not implemented: A string starting with K holding all possible tiles to be checked for
if we give points for a calling limit hand (like the BMJA rules do).
We could use brute force and check with every tile but that might take
too much time

Tiles are represented by one letter followed by another letter or
by a digit. BIG letters stand for concealed, small letters for exposed.

You can find examples in scoringtest.pyqtProperty

Definition for a tile string:
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

 Definition of the M string:
   Moryd = said mah jongg,
        o is the own wind, r is the round wind,
        y defines where the last tile for the mah jongg comes from:
            e=dead end,
            z=last tile of living end
            Z=last tile of living end, discarded
            k=robbing the kong,
            1=blessing of  heaven/earth
        d defines the declarations a player made
            a=call at beginning

Definition of the m string:
   mor = did not say mah jongg
        o is the own wind, r is the round wind

Last tile:
    Lxxaabbccdd
        xx is the last tile
        aabbccdd is the meld that was built with the last tile, length varies
"""

"""TODO: make rulesets editable
- neue Regel
- Regel bearbeiten (regexp)
- Regel löschen
- Tab mit Begriffen: Werte, spez.Hände, Boni, Strafen
"""
import re, types, copy
from hashlib import md5
from inspect import isclass
from util import m18n, m18nc
from query import Query
from PyKDE4.kdeui import KMessageBox
from PyKDE4.kdecore import i18n

CONCEALED, EXPOSED, ALLSTATES = 1, 2, 3
EMPTY, SINGLE, PAIR, CHOW, PUNG, KONG, CLAIMEDKONG, ALLMELDS = 0, 1, 2, 4, 8, 16, 32, 63


def shortcuttedMeldName(meld):
    """convert int to speaking name with shortcut"""
    if meld == ALLMELDS or meld == 0:
        return ''
    parts = []
    if SINGLE & meld:
        parts.append(m18nc('kmj meld type','&single'))
    if PAIR & meld:
        parts.append(m18nc('kmj meld type','&pair'))
    if CHOW & meld:
        parts.append(m18nc('kmj meld type','&chow'))
    if PUNG & meld:
        parts.append(m18nc('kmj meld type','p&ung'))
    if KONG & meld:
        parts.append(m18nc('kmj meld type','k&ong'))
    if CLAIMEDKONG & meld:
        parts.append(m18nc('kmj meld type','c&laimed kong'))
    return '|'.join(parts)

def meldName(meld):
    """convert int to speaking name with shortcut"""
    return shortcuttedMeldName(meld).replace('&', '')

def stateName(state):
    """convert int to speaking name"""
    if state == ALLSTATES:
        return ''
    parts = []
    if CONCEALED & state:
        parts.append(m18nc('kmj','concealed'))
    if EXPOSED & state:
        parts.append(m18nc('kmj','exposed'))
    return '|'.join(parts)

def tileKey(tile):
    """to be used in sort() and sorted() as key="""
    tileOrder = 'dwsbc'
    aPos = tileOrder.index(tile[0].lower()) + ord('0')
    return ''.join([chr(aPos), tile.lower()])

def meldKey(meld):
    """to be used in sort() and sorted() as key="""
    return tileKey(meld.content)

def meldContent(meld):
    """to be used in sort() and sorted() as key="""
    return meld.content

class Ruleset(object):
    """holds a full set of rules: splitRules,meldRules,handRules,mjRules,limitHands.
    rulesetId:
        1..9999 for predefined rulesets
        10000..99999 for customized rulesets
        1000000..upwards for used rulesets

        predefined rulesets are preinstalled together with kmj. They can be customized by the user:
        He can copy them and modify the copies in any way. If a game uses a specific ruleset, it
        checks the used rulesets range for an identical ruleset and refers to that one, or it generates
        a new entry for a used ruleset.findManualRuleByName

        The user can select any predefined or customized ruleset for a new game, but she can
        only modify customized rulesets.

        For fast comparison for equality of two rulesets, each ruleset has a hash built from
        all of its rules. This excludes the splitting rules, IOW exactly the rules saved in the table
        rule will be used for computation.

        used rulesets and rules are stored in separate tables - this makes handling them easier.
        In table usedruleset the name is not unique.
    """
    predefinedIds = (1, 9999)
    customizedIds = (predefinedIds[1]+1, 999999)
    usedIds = (customizedIds[1]+1, 99999999)

    def __init__(self, name):
        self.name = name
        self.rulesetId = 0
        self.hash = None
        self.description = None
        self.splitRules = []
        self.meldRules = []
        self.handRules = []
        self.mjRules = []
        self.manualRules = [] # the user manually selects among those rules.
                                    # Rule.applies() is used to determine if a rule can be selected.
        self.limitHands = []
        self.intRules = []
        self.strRules = []
        self.ruleLists = list([self.meldRules, self.handRules, self.mjRules, self.limitHands, self.manualRules, self.intRules, self.strRules])
        self.loadSplitRules()
        self._load()
        for par in self.intRules:
            self.__dict__[par.name] = int(par.value)
        for par in self.strRules:
            self.__dict__[par.name] = par.value
        self.computeHash()

    @staticmethod
    def rulelistNames():
        return list([m18n('Meld rules'), m18n('Hand rules'), m18n('Winner rules'), m18n('Limit hands'), m18n('Manual rules'), m18n('Numbers'), m18n('Strings')])

    @staticmethod
    def rulelistDescriptions():
        return list([m18n('Meld rules are applied to single melds independent of the rest of the hand'), m18n('Hand rules are applied to the entire hand, for all players'), m18n('Winner rules are applied to the entire hand but only for the winner'), m18n('Limit hands are special rules for the winner'), m18n('Manual rules are applied manually by the user. We would prefer to live without them but sometimes the program has not yet enough information or is not intelligent enough to auomatically apply them when appropriate'), m18n('Numbers are several special parameters like points for a limit hand'), m18n('Strings are several special parameters - none yet defined')])

    def findManualRuleByName(self, name):
        """return the manual rule named 'name'"""
        for rule in self.manualRules:
            if rule.name == name:
                return rule
        assert False,  'no rule found:' + name

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

    def _load(self):
        """load the ruleset from the data base"""
        if isinstance(self.name, int):
            query = Query("select id,name,hash,description from %s where id = %d" % \
                          (self.rulesetTable(), self.name))
        else:
            query = Query("select id,name,hash,description from %s where name = '%s'" % \
                          (self.rulesetTable(), self.name))
        if query.success:
            (self.rulesetId, self.name, self.hash, self.description) = query.data[0]
        else:
            raise Exception(m18n("ruleset %1 not found", self.name))
        query = Query("select name, list, value,points, doubles, limits from %s where ruleset=%d" % \
                      (self.ruleTable(), self.rulesetId))
        for record in query.data:
            (name, listNr, value, points, doubles, limits) = record
            rule = Rule(name, value, points, doubles, limits)
            self.ruleLists[listNr].append(rule)

    def newId(self, region):
        """returns an unused ruleset id. This is not multi user safe."""
        query = Query("select max(%d,max(id)+1) from %s" % (region[0], self.rulesetTable(region[0])))
        try:
            newId = int(query.data[0][0]) # sqlite3 returns string type for max() expression
        except Exception:
            newId = region[0] + 1
        assert newId < region[1]
        return newId

    def newCustomizedId(self):
        """returns an unused ruleset id. This is not multi user safe."""
        return self.newId(Ruleset.customizedIds)

    def newUsedId(self):
        """returns an unused ruleset id. This is not multi user safe."""
        return self.newId(Ruleset.usedIds)

    def assertNameUnused(self, name):
        q = Query('select id from ruleset where name = "%s"' % name)
        if len(q.data):
            msg = i18n('A ruleset with name "%1" already exists', name)
            KMessageBox.sorry(None, msg)
            raise Exception(msg)

    def _newKey(self):
        """returns a new key for a copy of self"""
        newId = self.newCustomizedId()
        newName = m18n('Copy of %1', m18n(self.name))
        self.assertNameUnused(newName)
        return newId, newName

    def copy(self):
        """make a copy of self and return the new ruleset id. Returns a new ruleset Id or None"""
        newId,  newName = self._newKey()
        query = Query(["insert into ruleset select %d,'%s',r.hash,null,r.description from ruleset r where r.id=%d" % \
                    (newId, newName, self.rulesetId),
                    "insert into rule select %d,r.name,r.list,r.value,r.points,r.doubles,r.limits from rule r where r.ruleset=%d" % \
                    (newId, self.rulesetId)])
        if  query.success:
            return Ruleset(newId)

    def isUsed(self, rulesetId=None):
        """is this a used ruleset?"""
        if rulesetId is None:
            rulesetId = self.rulesetId
        return Ruleset.usedIds[0] <= rulesetId < Ruleset.usedIds[1]

    def rulesetTable(self, rulesetId=None):
        """the table name for the ruleset"""
        return 'usedruleset' if self.isUsed(rulesetId) else 'ruleset'

    def ruleTable(self, rulesetId=None):
        """the table name for the rule"""
        return 'usedrule' if self.isUsed(rulesetId) else 'rule'

    def isCustomized(self, warn=False):
        """is this a customized or user defined ruleset?"""
        result = Ruleset.customizedIds[0] <= self.rulesetId < Ruleset.customizedIds[1]
        if not result and warn:
            KMessageBox.sorry(None,
                i18n('Only customized rulesets can be deleted or modified'))
        return result

    def rename(self, newName):
        """renames the ruleset. returns True if done, False if not"""
        self.assertNameUnused(newName)
        query = Query("update ruleset set name = '%s' where name = '%s'" % \
            (newName, self.name))
        if query.success:
            self.name = newName
        return query.success

    def remove(self):
        """remove this ruleset from the data base."""
        Query(["DELETE FROM rule WHERE ruleset=%d" % self.rulesetId,
                   "DELETE FROM ruleset WHERE id=%d" % self.rulesetId])

    def inUse(self):
        """returns True if any game uses this ruleset"""
        assert self.rulesetId >= Ruleset.usedIds[0]
        return len(Query('select 1 from game where ruleset=%d' % self.rulesetId).data) > 0

    @staticmethod
    def ruleKey(rule):
        """needed for sorting the rules"""
        return rule.__str__()

    def computeHash(self):
        """compute the hash for this ruleset using all rules"""
        rules = []
        for parameter in self.ruleLists:
            rules.extend(parameter)
        result = md5('')
        for rule in sorted(rules, key=Ruleset.ruleKey):
            result.update(rule.__str__())
        self.hash = result.hexdigest()

    def save(self, rulesetId=None, name=None):
        """save the ruleset to the data base"""
        if rulesetId is None:
            rulesetId = self.rulesetId
        if name is None:
            name = self.name
        assert rulesetId
        if self.isCustomized() or self.isUsed():
            self.remove()
        self.computeHash()
        cmdList = ['INSERT INTO %s(id,name,hash,description) VALUES(%d,"%s","%s","%s")' % \
            (self.rulesetTable(), rulesetId, name, self.hash, self.description)]
        for idx, parameter in enumerate(self.ruleLists):
            for rule in parameter:
                score = rule.score
                cmdList.append('INSERT INTO %s(ruleset, name, list, value, points, doubles, limits) VALUES(%d,"%s",%d,"%s",%d,%d,%f) ' % \
                    (self.ruleTable(), rulesetId, rule.name, idx, rule.value,  score.points, score.doubles, score.limits))
        return Query(cmdList).success


    @staticmethod
    def availableRulesetNames():
        """returns all ruleset names defined in the data base"""
        return list(x[0] for x in Query("SELECT name FROM ruleset").data)

    @staticmethod
    def availableRulesets():
        """returns all rulesets defined in the data base"""
        return [Ruleset(x) for x in Ruleset.availableRulesetNames()]

class DefaultRuleset(Ruleset):
    """special code for loading rules from program code instead of from the database"""

    name = 'please define a name for this default ruleset'

    def __init__(self, name):
        Ruleset.__init__(self, name)

    def rules(self):
        """here the default rulesets can define their rules"""
        pass

    def _load(self):
        """do not load from database but from program code but do
        not forget to compute the hash"""
        self.rules()
        self.computeHash()

    def copy(self):
        """make a copy of self and return the new ruleset id. Returns a new ruleset Id or None"""
        newId,  newName = self._newKey()
        if  self.save(newId, newName):
            return Ruleset(newId)

def meldsContent(melds):
    """return content of melds"""
    return ' '.join([meld.content for meld in melds])

class Score(object):
    """holds all parts contributing to a score"""
    def __init__(self, points=0, doubles=0, limits=0):
        self.points = points
        self.doubles = doubles
        self.limits = limits

    def __str__(self):
        """make score printable"""
        parts = []
        if self.points:
            parts.append('points=%d' % self.points)
        if self.doubles:
            parts.append('doubles=%d' % self.doubles)
        if self.limits:
            parts.append('limits=%f' % self.limits)
        return ' '.join(parts)

    def type(self):
        if self.doubles:
            assert self.points == 0 and self.limits == 0
            return 1
        elif self.limits:
            assert self.points == 0 and self.doubles == 0
            return 2
        else:
            assert self.doubles == 0 and self.limits == 0
            return 0

    def name(self):
        if self.doubles:
            return i18n('Doubles')
        elif self.limits:
            return i18n('Limits')
        else:
            return i18n('Points')

    def value(self):
        return self.points or self.doubles or self.limits

    def __eq__(self, other):
        """ == comparison """
        return self.points == other.points and self.doubles == other.doubles and self.limits == other.limits

    def __ne__(self, other):
        """ != comparison """
        return self.points != other.points or self.doubles != other.doubles or self.limits != other.limits

    def __add__(self, other):
        """implement adding Score"""
        return Score(self.points + other.points, self.doubles+other.doubles, max(self.limits, other.limits))

    def __radd__(self, other):
        """allows sum() to work"""
        if isinstance(other, Score):
            return self.__add__(self, other)
        else:
            self.points += other
            return self

    def total(self, limit):
        """the total score"""
        if self.limits:
            return round(self.limits * limit)
        else:
            return min(self.points * (2 ** self.doubles), limit)

class Hand(object):
    """represent the hand to be evaluated"""
    def __init__(self, ruleset, string, rules=None):
        """evaluate string using ruleset. rules are to be applied in any case."""
        self.ruleset = ruleset
        self.rules = []
        for rule in rules or []:
            if not isinstance(rule, Rule):
                rule = ruleset.findManualRuleByName(rule)
            self.rules.append(rule)
        self.original = None
        self.won = False
        self.lastTile = ''
        self.ownWind = None
        self.roundWind = None
        self.lastMeld = None
        tileStrings = []
        mjStrings = []
        splits = string.split()
        for part in splits:
            partId = part[0]
            if partId == 'M':
                self.won = True
                mjStrings.append(part)
            if partId in 'Mm':
                self.ownWind = part[1]
                self.roundWind = part[2]
                mjStrings.append(part)
            elif partId == 'L':
                self.lastTile = part[1:3]
                self.lastMeld = Meld(part[3:])
                mjStrings.append(part)
            else:
                tileStrings.append(part)

        self.tiles = ' '.join(tileStrings)
        self.mjStr = ' '.join(mjStrings)
        self.melds = None
        self.explain = None
        self.__summary = None
        self.normalized = None
        self.fsMelds = list()
        self.invalidMelds = list()
        self.separateMelds()
        self.usedRules = []

    def maybeMahjongg(self):
        """check if this hand can be a regular mah jongg"""
        tileCount = sum(len(meld) for meld in self.melds)
        kongCount = self.countMelds(Meld.isKong)
        return tileCount - kongCount == 14 and self.score() >= self.ruleset.minMJPoints

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
        return list(rule for rule in rules if rule.applies(self, self.melds))

    def applyMeldRules(self):
        """apply all rules for single melds"""
        for  rule in self.ruleset.meldRules:
            for meld in self.melds:
                if rule.applies(self, meld):
                    self.usedRules.append((rule, meld))
                    meld.score += rule.score

    def computePoints(self):
        """use all usedRules to compute the score"""
        if not self.usedRules:
            result = Score()
        else:
            result = sum(x.score for x, y in self.usedRules)
        return result

    def total(self):
        """total points of hand"""
        return self.score().total(self.ruleset.limit)

    def separateMelds(self):
        """build a meld list from the hand string"""
        self.explain = []
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

        for meld in self.melds:
            if not meld.isValid():
                self.invalidMelds.append(meld)
            if meld.tileType() in 'fy':
                self.fsMelds.append(meld)
        for meld in self.fsMelds:
            self.melds.remove(meld)

    def score(self):
        """returns the points of the hand. Also sets some attributes with intermediary results"""
        if self.invalidMelds:
            raise Exception('has invalid melds: ' + ','.join(meld.str for meld in self.invalidMelds))

        self.usedRules = []
        for meld in self.melds:
            meld.score = Score()
        self.explain = []
        self.applyMeldRules()
        self.original += ' ' + self.summary
        self.normalized =  meldsContent(sorted(self.melds, key=meldKey))
        if self.fsMelds:
            self.normalized += ' ' + meldsContent(self.fsMelds)
        self.normalized += ' ' + self.summary
        for rule in self.matchingRules(self.ruleset.handRules):
            self.usedRules.append((rule, None))
        for myRule in self.rules or []:
            self.usedRules.append((myRule, None))
        if self.won and self.computePoints().total(self.ruleset.limit) < self.ruleset.minMJPoints:
            self.won = False
        if self.won:
            for rule in self.matchingRules(self.ruleset.mjRules):
                self.usedRules.append((rule, None))
        if len(list(x for x in self.usedRules if x[0].score.limits)):
            self.usedRules = [x for x in self.usedRules if x[0].score.limits]
        for rule in list(x[0] for x in self.usedRules):
            self.explain.append(rule.explain())
        return self.computePoints()

    def getSummary(self):
        """returns a summarizing string for this hand"""
        if self.__summary is None:
            self.__summary = '/' + ''.join(sorted([meld.regex() for meld in self.melds], key=tileKey))
        return self.__summary

    summary = property(getSummary)

    def __str__(self):
        return ' '.join([meldsContent(self.melds), meldsContent(self.fsMelds), self.summary])

class Variant(object):
    """all classes derived from variant are allowed to be used
    as rule variants. Examples: Pattern and all its derivations, Regex, MJHiddenTreasure"""

    def __init__(self, rule):
        self.rule = rule

    def applies(self, hand, melds):
        """when deriving from variant, please override this. It should return bool."""
        pass

class Rule(object):
    """a mahjongg rule with a name, matching variants, and resulting score.
    The rule applies if at least one of the variants matches the hand"""
    def __init__(self, name, value, points = 0,  doubles = 0, limits = 0):
        self.name = name
        self.score = Score(points, doubles, limits)
        self.value = value
        if not value:
            return  # may happen with special programmed rules
        if not isinstance(value, list):
            if isinstance(value, (int, float)):
                value = list([value])
            else:
                value = value.split('||')
        self.variants = []
        for variant in value:
            if isinstance(variant, Variant):
                self.variants.append(variant)
            elif isinstance(variant, (str, unicode)):
                if isinstance(variant, unicode):
                    variant = str(variant)
                if variant[0] == 'P':
                    newVariant = eval(variant[1:], {"__builtins__":None}, Pattern.evalDict)
                    newVariant.expression = variant
                    self.variants.append(newVariant)
                elif variant[0] == 'I':
                    self.variants.append(RegexIgnoringCase(variant[1:]))
                else:
                    self.variants.append(Regex(variant))
            elif type(variant) == type:
                self.variants.append(variant())
            else:
                self.variants.append(Pattern(variant))

    def applies(self, hand, melds):
        """does the rule apply to this hand?"""
        return any(variant.applies(hand, melds) for variant in self.variants)

    def explain(self):
        """use this rule for scoring"""
        result = m18n(self.name) + ':'
        if self.score.points:
            result += m18nc('kmj', ' %1 base points',  self.score.points)
        if self.score.doubles:
            result += m18nc('kmj', ' %1 doubles', self.score.doubles)
        if self.score.limits:
            result += m18nc('kmj', ' %1 limits', self.score.limits)
        return result

    def __str__(self):
        """all that is needed to hash this rule"""
        return '%s: %s %s' % (self.name, self.value, self.score)

    def copy(self):
        """returns a deep copy of self with a new name"""
        return Rule(m18n('Copy of %1', m18n(self.name)), self.value,
                self.score.points, self.score.doubles, self.score.limits)

class Regex(Variant):
    """use a regular expression for defining a variant"""
    def __init__(self, rule):
        Variant.__init__(self, rule)
        self.compiled = re.compile(rule)

    def applies(self, hand, melds):
        """does this regex match?"""
        if isinstance(melds, Meld):
            meldStrings = [melds.content]
        else:
            meldStrings = [hand.original,  hand.normalized]
        for meldString in meldStrings:
            if isinstance(self, RegexIgnoringCase):
                match = self.compiled.match(meldString.lower() + hand.mjStr)
            else:
                match = self.compiled.match(meldString + hand.mjStr)
            if match:
                break
        return match

class RegexIgnoringCase(Regex):
    """this Regex ignores case on the meld strings"""
    pass

class Pattern(Variant):
    """a pattern representing combinations for a hand"""
    def __init__(self, slots=None ):
        Variant.__init__(self, slots)
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

    def __assignMelds(self, hand,  melds):
        """try to assign all melds to our slots"""
        if len(melds) == 0:
            return True
        self.restSlot = None
        for slot in self.slots:
            if slot.isRestSlot:
                slot.candidates = []
                self.restSlot = slot
            else:
                slot.candidates = [meld for meld in melds if slot.takes(hand, meld)]
        if len(melds) < len(self.slots):
            return False
        if self.restSlot is None and len(melds) != len(self.slots):
            return False
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
        if self.isMahJonggPattern and not hand.won:
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
        if not self.__assignMelds(hand, melds):
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
    """represents a meld. Can be empty. Many Meld methods will
    raise exceptions if the meld is empty. But we do not care,
    those methods are not supposed to be called on empty melds"""

    tileNames = {'s': m18nc('kmj','stone') , 'b': m18nc('kmj','bamboo'), 'c':m18nc('kmj','character'),
        'w':m18nc('kmj','wind'), 'd':m18nc('kmj','dragon'),
        'f':m18nc('kmj','flower'), 'y':m18nc('kmj','season')}
    valueNames = {'b':m18nc('kmj','white'), 'r':m18nc('kmj','red'), 'g':m18nc('kmj','green'),
        'e':m18nc('kmj','east'), 's':m18nc('kmj','south'), 'w':m18nc('kmj','west'), 'n':m18nc('kmj','north'),
        'O':m18nc('kmj','own wind'), 'R':m18nc('kmj','round wind')}
    for valNameIdx in range(1, 10):
        valueNames[str(valNameIdx)] = str(valNameIdx)

    def __init__(self, content = None):
        """init the meld: content is a single string with 2 chars for every meld"""
        Pairs.__init__(self)
        self.__valid = False
        self.score = Score()
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
        pStr = m18nc('kmj', '%1 points',  self.score.points) if self.score.points else ''
        fStr = m18nc('kmj', '%1 doubles',  self.score.doubles) if self.score.doubles else ''
        score = ' '.join([pStr, fStr])
        return '%s %s %s %s:   %s' % (stateName(self.state),
                        meldName(self.meldType), which, value, score)

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

    state = property(__getState, __setState)

    def _getMeldType(self):
        """compute meld type"""
        content = self.content # optimize access speed
        if not content:
            return EMPTY
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
        return '%s%s%02d' % (str0,  str(myLen), self.score.points)

    def getContent(self):
        """getter for content"""
        return Pairs.getContent(self)

    def setContent(self, content):
        """assign new content to this meld"""
        if not content:
            content = ''
        Pairs.setContent(self, content)
        self.__valid = True
        self.name = m18nc('kmj','not a meld')
        if len(content) not in (0, 2, 4, 6, 8):
            raise Exception('contentlen not in 02468: %s' % content)
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

    def takes(self, hand, meld):
        """does the slot take this meld?"""
        if not self.minSize() <= len(meld) <= self.maxSize() :
            return False
        meldstr = meld.content[0].lower() + meld.content[1]
        if 'wO' in self.content:
            if meldstr == 'w' + hand.ownWind:
                return True
        if 'wR' in self.content:
            if meldstr == 'w' + hand.roundWind:
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

class MJHiddenTreasure(Pattern):
    """could we express this as a normal pattern or a regex? Probably not"""
    def applies(self, hand, melds):
        """could this hand be a hidden treasure?"""
        assert hand # quieten pylint
        self.isMahJonggPattern = True
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

class Terminals(PairChanger):
    """only terminals"""
    def __init__(self, other=None):
        PairChanger.__init__(self, other)
        # explicitly disallow chows
        for slot in self.slots:
            slot.meldType &= SINGLE|PAIR|PUNG|KONG|CLAIMEDKONG
    def changePair(self, pair):
        """change this pair"""
        assert self
        if pair[1] in '19':
            return pair
        elif pair[1] == '.' and pair[0] in 'sbc':
            return pair[0]+'1' + pair[0]+'9'
        return ''

class NoSimple(PairChanger):
    """disables all  simples"""
    def __init__(self, other=None):
        PairChanger.__init__(self, other)
        # explicitly disallow chows
        for slot in self.slots:
            slot.meldType &= SINGLE|PAIR|PUNG|KONG|CLAIMEDKONG
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
        if not hand.won or not hand.lastMeld:
            return False
        assert len(self.slots) == 1
        slot = self.slots[0]
        return slot.takes(hand, hand.lastMeld)

class LastTileOnlyPossible(Pattern):
    """has its own applies method"""
    def applies(self, hand, melds):
        """does this rule apply?"""
        assert melds        # quieten pylint about unused argument
        if not hand.won or not hand.lastMeld:
            return False
        return len(hand.lastMeld) < 3 or hand.lastMeld.content.find(hand.lastTile) == 2

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
