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



Read the user manual for a description of the interface to this scoring engine
"""

import re
from hashlib import md5
from PyKDE4.kdecore import i18n
from PyQt4.QtCore import QString

from util import m18n, m18nc, english, logException
from query import Query

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
    """to be used in sort() and sorted() as key=.
    Sorts by tile (dwsbc), then by the whole meld, ignoring case"""
    return tileKey(meld.content)

def meldContent(meld):
    """to be used in sort() and sorted() as key="""
    return meld.content

class NamedList(list):
    """a list with a name and a description (to be used as hint)"""

    def __init__(self, listId, name, description):
        list.__init__(self)
        self.listId = listId
        self.name = name
        self.description = description

class Ruleset(object):
    """holds a full set of rules: splitRules,meldRules,handRules,mjRules.

        predefined rulesets are preinstalled together with kmj. They can be customized by the user:
        He can copy them and modify the copies in any way. If a game uses a specific ruleset, it
        checks the used rulesets for an identical ruleset and refers to that one, or it generates
        a new used ruleset.

        The user can select any predefined or customized ruleset for a new game, but she can
        only modify customized rulesets.

        For fast comparison for equality of two rulesets, each ruleset has a hash built from
        all of its rules. This excludes the splitting rules, IOW exactly the rules saved in the table
        rule will be used for computation.

        used rulesets and rules are stored in separate tables - this makes handling them easier.
        In table usedruleset the name is not unique.
    """

    def __init__(self, name, used=False):
        self.name = name
        self.__used = used
        self.orgUsed = used
        self.savedHash = None
        self.rulesetId = 0
        self.hash = None
        self.__loaded = False
        self.description = None
        self.splitRules = []
        self.meldRules = NamedList(1, m18n('Meld Rules'),
            m18n('Meld rules are applied to single melds independent of the rest of the hand'))
        self.handRules = NamedList(2, m18n('Hand Rules'),
            m18n('Hand rules are applied to the entire hand, for all players'))
        self.mjRules = NamedList(3, m18n('Winner Rules'),
            m18n('Winner rules are applied to the entire hand but only for the winner'))
        self.manualRules = NamedList(99, m18n('Manual Rules'),
            m18n('Manual rules are applied manually by the user. We would prefer to live ' \
                'without them but sometimes the program has not yet enough information ' \
                'or is not intelligent enough to automatically apply them when appropriate'))
            # manual rules: Rule.appliesToHand() is used to determine if a manual rule can be selected.
        self.intRules = NamedList(998, m18n('Numbers'),
            m18n('Numbers are several special parameters like points for a limit hand'))
        self.strRules = NamedList(999,  m18n('Strings'),
            m18n('Strings are several special parameters - none yet defined'))
        self.penaltyRules = NamedList(9999, m18n('Penalties'), m18n('Penalties are applied manually by the user'))
        self.ruleLists = list([self.meldRules, self.handRules, self.mjRules, self.manualRules,
            self.intRules, self.strRules, self.penaltyRules])
        # the order of ruleLists is the order in which the lists appear in the ruleset editor
        # if you ever want to remove an entry from ruleLists: make sure its listId is not reused or you get
        # in trouble when updating
        self.initRuleset()

    def initRuleset(self):
        """load ruleset headers but not the rules"""
        if isinstance(self.name, int):
            query = Query("select id,name,hash,description from %s where id = %d" % \
                          (self.__rulesetTable(), self.name))
        else:
            query = Query("select id,name,hash,description from %s where name = '%s'" % \
                          (self.__rulesetTable(), self.name))
        if len(query.data):
            (self.rulesetId, self.name, self.savedHash, self.description) = query.data[0]
        else:
            raise Exception(m18n('ruleset "%1" not found', self.name))

    def load(self):
        """load the ruleset from the data base and compute the hash"""
        if self.__loaded:
            return
        self.__loaded = True
        self.loadSplitRules()
        self.rules()
        for par in self.intRules:
            self.__dict__[par.name] = int(par.value)
        for par in self.strRules:
            self.__dict__[par.name] = par.value
        self.hash = self.computeHash()
        assert isinstance(self, PredefinedRuleset) or self.hash == self.savedHash

    def rules(self):
        """load rules from data base"""
        query = Query("select name, list, value,points, doubles, limits from %s ' \
                'where ruleset=%d order by list,position" % \
                      (self.__ruleTable(), self.rulesetId))
        for record in query.data:
            (name, listNr, value, points, doubles, limits) = record
            rule = Rule(name, value, points, doubles, limits)
            for ruleList in self.ruleLists:
                if ruleList.listId == listNr:
                    ruleList.append(rule)
                    break

    def findManualRuleByName(self, name):
        """return the manual rule named 'name'"""
        for rule in self.manualRules:
            if rule.name == name:
                return rule
        raise Exception('no manual rule found:' + name)

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

    def newId(self, used=None):
        """returns an unused ruleset id. This is not multi user safe."""
        if used is not None:
            self.__used = used
        data = Query("select max(id)+1 from %s" % self.__rulesetTable()).data
        try:
            return int(data[0][0])
        except ValueError:
            return 1

    @staticmethod
    def nameIsDuplicate(name):
        """show message and raise Exception if ruleset name is already in use"""
        return bool(Query('select id from ruleset where name = "%s"' % name).data)

    def _newKey(self):
        """returns a new key and a new name for a copy of self"""
        newId = self.newId()
        for copyNr in range(1, 100):
            copyStr = ' ' + str(copyNr) if copyNr > 1 else ''
            newName = m18nc('Ruleset._newKey:%1 is empty or space plus number',
                'Copy%1 of %2', copyStr, m18n(self.name))
            if not self.nameIsDuplicate(newName):
                return newId, newName
        logException(Exception(i18n('You already have the maximum number of copies, please rename some')))

    def ruleNameIsDuplicate(self, name):
        """True if a rule with name already exists"""
        for ruleList in self.ruleLists:
            for rule in ruleList:
                if rule.name == name:
                    return True
        return False

    def clone(self):
        """returns a clone of self, unloaded"""
        return Ruleset(self.rulesetId)

    def __str__(self):
        return 'type=%s, id=%d,rulesetId=%d,name=%s,used=%d' % (
                type(self), id(self), self.rulesetId, self.name, self.__used)

    def copy(self):
        """make a copy of self and return the new ruleset id. Returns a new ruleset Id or None"""
        newRuleset = self.clone()
        newRuleset.load()
        if newRuleset.saveCopy():
            if isinstance(newRuleset, PredefinedRuleset):
                newRuleset = Ruleset(newRuleset.rulesetId)
            return newRuleset

    def saveCopy(self):
        """give this ruleset a new id and a new name and save it"""
        assert not self.__used
        self.rulesetId,  self.name = self._newKey()
        return self.save()

    def __ruleList(self, rule):
        """return the list containg rule. We could make the list
        an attribute of the rule but then we rarely
        need this, and it is not time critical"""
        for ruleList in self.ruleLists:
            if rule in ruleList:
                return ruleList
        assert False

    def copyRule(self, rule):
        """insert a copy of rule behind rule, give it a unique name.
        returns the  new copy."""
        result = rule.copy()
        for copyNr in range(1, 100):
            copyStr = ' ' + str(copyNr) if copyNr > 1 else ''
            result.name = m18nc('Ruleset.copyRule:%1 is empty or space plus number',
                'Copy%1 of %2', copyStr, m18n(rule.name))
            if not self.ruleNameIsDuplicate(result.name):
                ruleList = self.__ruleList(rule)
                ruleList.insert(ruleList.index(rule) + 1, result)
                return result
        logException(Exception(i18n('You already have the maximum number of copies, please rename some')))

    def __rulesetTable(self):
        """the table name for the ruleset"""
        return 'usedruleset' if self.__used else 'ruleset'

    def __ruleTable(self):
        """the table name for the rule"""
        return 'usedrule' if self.__used else 'rule'

    def rename(self, newName):
        """renames the ruleset. returns True if done, False if not"""
        if self.nameIsDuplicate(newName):
            return False
        newHash = self.computeHash(newName)
        query = Query("update ruleset set name = '%s', hash='%s' where name = '%s'" % \
            (newName, newHash, self.name))
        if query.success:
            self.name = newName
            self.hash = newHash
            self.savedHash = self.hash
        return query.success

    def remove(self):
        """remove this ruleset from the data base."""
        Query(["DELETE FROM %s WHERE ruleset=%d" % (self.__ruleTable(), self.rulesetId),
                   "DELETE FROM %s WHERE id=%d" % (self.__rulesetTable(), self.rulesetId)])

    @staticmethod
    def ruleKey(rule):
        """needed for sorting the rules"""
        return rule.__str__()

    def computeHash(self, name=None):
        """compute the hash for this ruleset using all rules"""
        if name is None:
            name = self.name
        rules = []
        for ruleList in self.ruleLists:
            rules.extend(ruleList)
        result = md5(name.encode('utf-8'))
        result.update(self.description.encode('utf-8'))
        for rule in sorted(rules, key=Ruleset.ruleKey):
            result.update(rule.__str__())
        return result.hexdigest()

    def save(self, rulesetId=None, name=None):
        """save the ruleset to the data base"""
        if rulesetId is None:
            rulesetId = self.rulesetId
        if name is None:
            name = self.name
        assert rulesetId
        self.hash = self.computeHash(name)
        if self.hash == self.savedHash and self.__used == self.orgUsed:
            # same content in same table
            return True
        self.remove()
        cmdList = ['INSERT INTO %s(id,name,hash,description) VALUES(%d,"%s","%s","%s")' % \
            (self.__rulesetTable(), rulesetId, english.get(name, name), self.hash, self.description)]
        for ruleList in self.ruleLists:
            for ruleIdx, rule in enumerate(ruleList):
                score = rule.score
                cmdList.append('INSERT INTO %s(ruleset, list, position, name, value, points, doubles, limits)'
                ' VALUES(%d,%d,%d,"%s","%s",%d,%d,%f) ' % \
                    (self.__ruleTable(), rulesetId, ruleList.listId, ruleIdx, english.get(rule.name, rule.name),
                    rule.value,  score.points, score.doubles, score.limits))
        return Query(cmdList).success

    @staticmethod
    def availableRulesetNames():
        """returns all ruleset names defined in the data base"""
        return list(x[0] for x in Query("SELECT name FROM ruleset").data)

    @staticmethod
    def availableRulesets():
        """returns all rulesets defined in the data base"""
        return [Ruleset(x) for x in Ruleset.availableRulesetNames()]

def meldsContent(melds):
    """return content of melds"""
    return ' '.join([meld.content for meld in melds])

class Score(object):
    """holds all parts contributing to a score. It has two use cases:
    1. for defining what a rules does: either points or doubles or limits, holding never more than one unit
    2. for summing up the scores of all rules: Now more than one of the units can be in use. If a rule
    should want to set more than one unit, split it into two rules.
    For the first use case only we have the attributes value and unit"""


    def __init__(self, points=0, doubles=0, limits=0):
        if not isinstance(points, int):
            raise Exception('Score: points is not an integer')
        self.points = points
        self.doubles = doubles
        self.limits = limits

    unitNames = [m18n('points'), m18n('doubles'), m18n('limits')]

    @staticmethod
    def unitName(unit):
        """maps the index to the name"""
        return m18n(Score.unitNames[unit])

    def clear(self):
        """set all to 0"""
        self.points = self.doubles = self.limits = 0

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

    def assertSingleUnit(self):
        """make sure only one unit is used"""
        if sum(1 for x in [self.points, self.doubles, self.limits] if x) > 1:
            raise Exception('this score must not hold more than one unit: %s' % self.__str__())

    def __getUnit(self):
        """for use in ruleset tree view. returns an index into Score.units."""
        self.assertSingleUnit()
        if self.doubles:
            return 1
        elif self.limits:
            return 2
        else:
            return 0

    def __setUnit(self, unit):
        """for use in ruleset tree view"""
        self.assertSingleUnit()
        oldValue = self.value
        self.clear()
        self.__setattr__(Score.unitName(unit), oldValue)

    def __getValue(self):
        """getter for the virtual property 'value''"""
        self.assertSingleUnit()
        return self.points or self.doubles or self.limits

    def __setValue(self, value):
        """setter for the virtual property 'value''"""
        self.assertSingleUnit()
        self.__setattr__(self.unit, value)

    unit = property(__getUnit, __setUnit)
    value = property(__getValue, __setValue)

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
        self.string = string
        self.rules = []
        for rule in rules or []:
            if not isinstance(rule, Rule):
                rule = ruleset.findManualRuleByName(rule)
            self.rules.append(rule)
        self.original = None
        self.won = False
        self.ownWind = None
        self.roundWind = None
        tileStrings = []
        mjStrings = []
        splits = string.split()
        for part in splits:
            partId = part[0]
            if partId in 'Mm':
                self.ownWind = part[1]
                self.roundWind = part[2]
                mjStrings.append(part)
                self.won = partId == 'M'
            elif partId == 'L':
                if len(part[1:]) > 8:
                    raise Exception('last tile cannot complete a kang:'+string)
                mjStrings.append(part)
            else:
                tileStrings.append(part)

        self.tiles = ' '.join(tileStrings)
        self.mjStr = ' '.join(mjStrings)
        self.melds = set()
        self.__summary = None
        self.normalized = None
        self.fsMelds = set()
        self.invalidMelds = set()
        self.separateMelds()
        self.usedRules = []
        if self.invalidMelds:
            raise Exception('has invalid melds: ' + ','.join(meld.str for meld in self.invalidMelds))

        for meld in self.melds:
            meld.score = Score()
        self.applyMeldRules()
        exclusive = self.__exclusiveRules(self.usedRules)
        if exclusive: # if a meld rule is exclusive: quite improbable but just in case...
            self.usedRules = exclusive
            self.score = self.__totalScore(exclusive)
        else:
            self.original += ' ' + self.summary
            self.normalized =  meldsContent(sorted(self.melds, key=meldKey))
            if self.fsMelds:
                self.normalized += ' ' + meldsContent(self.fsMelds)
            self.normalized += ' ' + self.summary
	    variants = [self.__score(x) for x in [self.original, self.normalized]]
            if self.won:
                wonVariants = [x for x in variants if x[2]]
                if wonVariants:
                    variants = wonVariants
                else:
                    self.won = False
            limitVariants = [x for x in variants if x[0].limits>=1.0]
            if len(limitVariants) == 1:
                variants = limitVariants
            chosenVariant = variants[0]
            if len(variants) > 1:
                if variants[1][0].total(self.ruleset.limit) > variants[0][0].total(self.ruleset.limit):
                    chosenVariant = variants[1]
            score, rules, won = chosenVariant
            exclusive = self.__exclusiveRules(rules)
            if exclusive:
                self.usedRules = exclusive
                self.score = self.__totalScore(exclusive)
            else:
                self.usedRules.extend(rules)
                self.score = score
        
    def ruleMayApply(self, rule):
        """returns True if rule applies to either original or normalized"""
        res1 = rule.appliesToHand(self, self.original)
        res2 = rule.appliesToHand(self, self.normalized)
	return res1 or res2

    def hasAction(self, action):
        """return rule with action from used rules"""
        for ruleTuple in self.usedRules:
            rule = ruleTuple[0]
            if action in rule.actions:
                return rule

    def handLenOffset(self):
        """return <0 for short hand, 0 for correct calling hand, >0 for long hand
        if there are no kongs, 13 tiles will return 0"""
        tileCount = sum(len(meld) for meld in self.melds)
        kongCount = self.countMelds(Meld.isKong)
        return tileCount - kongCount - 13

    def maybeMahjongg(self):
        """check if this hand can be a regular mah jongg"""
        return self.handLenOffset() == 1 and self.score >= self.ruleset.minMJPoints

    def split(self, rest):
        """split self.tiles into melds as good as possible"""
        melds = set()
        for rule in self.ruleset.splitRules:
            splits = rule.apply(rest)
            while len(splits) >1:
                for split in splits[:-1]:
                    melds.add(Meld(split))
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

    def matchingRules(self, melds, rules):
        """return all matching rules for this hand"""
        return list(rule for rule in rules if rule.appliesToHand(self, melds))

    def applyMeldRules(self):
        """apply all rules for single melds"""
        for  rule in self.ruleset.meldRules:
            for meld in self.melds:
                if rule.appliesToMeld(self, meld):
                    self.usedRules.append((rule, meld))
                    meld.score += rule.score

    def __totalScore(self, rules):
        """use all used rules to compute the score"""
        result = Score()
        for ruleTuple in rules:
            result += ruleTuple[0].score
        return result

    def total(self):
        """total points of hand"""
        return self.score.total(self.ruleset.limit)

    def separateMelds(self):
        """build a meld list from the hand string"""
        self.original = str(self.tiles)
        self.tiles = str(self.original)
        splits = self.tiles.split()
        rest = []
        for split in splits:
            if len(split) > 8:
                rest.append(split)
                continue
            meld = Meld(split)
            if split[0].islower() or split[0] in 'mM' or meld.isValid():
                self.melds.add(meld)
            else:
                rest.append(split)
        if len(rest) > 1:
            raise Exception('hand has more than 1 unsorted part: ', self.original)
        if rest:
            rest = rest[0]
            rest = ''.join(sorted([rest[x:x+2] for x in range(0, len(rest), 2)]))
            self.melds |= self.split(rest)

        for meld in self.melds:
            if not meld.isValid():
                self.invalidMelds.add(meld)
            if meld.tileType() in 'fy':
                self.fsMelds.add(meld)
        self.melds -= self.fsMelds

    def __score(self, handStr):
        """returns a tuple with the score of the hand, the used rules and the won flag.
           handStr contains either the original meld grouping or regrouped melds"""
        usedRules = list([(rule, None) for rule in self.matchingRules(handStr, self.ruleset.handRules + self.rules)])
        won = self.won
        if won and self.__totalScore(self.usedRules + usedRules).total(self.ruleset.limit) < self.ruleset.minMJPoints:
            won = False
        if won:
            for rule in self.matchingRules(handStr, self.ruleset.mjRules):
                usedRules.append((rule, None))
        return (self.__totalScore(self.usedRules + usedRules), usedRules, won)

    def __exclusiveRules(self, rules):
        """returns a list of applicable rules which exclude all others"""
        return list(x for x in rules if 'absolute' in x[0].actions) \
            or list(x for x in rules if x[0].score.limits>=1.0)

    def explain(self):
        return [x[0].explain() for x in self.usedRules]

    def getSummary(self):
        """returns a summarizing string for this hand"""
        if self.__summary is None:
            handlenOffs = self.handLenOffset()
            if handlenOffs < 0:
                handlenStatus = 's'
            elif handlenOffs > 0 and not self.won:
                handlenStatus = 'l'
            elif handlenOffs > 1: # cover winner with long hand - we should never get here
                handlenStatus = 'l'
            else:
                handlenStatus = 'n'
            self.__summary = ''.join(['/',
                    ''.join(sorted([meld.regex(False) for meld in self.melds], key=tileKey)),
                    ' -',
                    ''.join(sorted([meld.regex(True) for meld in self.melds], key=tileKey)),
                    ' %',
                     ''.join([handlenStatus])])
        return self.__summary

    summary = property(getSummary)

    def __str__(self):
        """hand as a string"""
        return ' '.join([meldsContent(self.melds), meldsContent(self.fsMelds), self.summary, self.mjStr])

class Rule(object):
    """a mahjongg rule with a name, matching variants, and resulting score.
    The rule applies if at least one of the variants matches the hand"""
    english = {}
    def __init__(self, name, value, points = 0,  doubles = 0, limits = 0):
        self.actions = {}
        self.variants = []
        self.name = name
        self.score = Score(points, doubles, limits)
        self._value = None
        self.prevValue = None
        self.value = value

    def __getValue(self):
        """getter for value"""
        if isinstance(self._value, list):
            return '||'.join(self._value)
        else:
            return self._value

    def __setValue(self, value):
        """setter for value"""
        assert not isinstance(value, QString)
        self.prevValue = self.value
        self._value = value
        if not value:
            return  # may happen with special programmed rules
        if not isinstance(value, list):
            if isinstance(value, (int, float)):
                value = list([value])
            else:
                value = value.split('||')
        self.actions = {}
        self.variants = []
        for variant in value:
            if isinstance(variant, unicode):
                variant = str(variant)
            if isinstance(variant, str):
                if variant[0] == 'I':
                    self.variants.append(RegexIgnoringCase(self, variant[1:]))
                elif variant[0] == 'A':
                    aList = variant[1:].split()
                    for action in aList:
                        aParts = action.split('=')
                        if len(aParts) == 1:
                            aParts.append('None')
                        self.actions[aParts[0]] = aParts[1]
                else:
                    self.variants.append(Regex(self, variant))
        self.validate()

    value = property(__getValue, __setValue)

    def validate(self):
        """check for validity"""
        payers = int(self.actions.get('payers', 1))
        payees = int(self.actions.get('payees', 1))
        if not 2 <= payers + payees <= 4:
            self.value = self.prevValue
            logException(Exception(m18nc('%1 can be a sentence', '%4 have impossible values %2/%3 in rule "%1"',
                                  self.name, payers, payees, 'payers/payees')))

    def appliesToHand(self, hand, melds):
        """does the rule apply to this hand?"""
        result = any(variant.appliesToHand(hand, melds) for variant in self.variants)
#	if self.name=='Robbing the Kong' and result:
#        if result:
#            print 'match for rule:', self.name, self.value
        return result

    def appliesToMeld(self, hand, meld):
        """does the rule apply to this meld?"""
        return any(variant.appliesToMeld(hand, meld) for variant in self.variants)

    def explain(self):
        """use this rule for scoring"""
        result = [m18n(self.name) + ':']
        if self.score.points:
            result.append(m18nc('kmj', '%1 base points',  self.score.points))
        if self.score.doubles:
            result.append(m18nc('kmj', '%1 doubles', self.score.doubles))
        if self.score.limits:
            result.append(m18nc('kmj', '%1 limits', self.score.limits))
        return ' '.join(result)

    def __str__(self):
        """all that is needed to hash this rule"""
        return '%s: %s %s' % (self.name, self.value, self.score)

    def copy(self):
        """returns a deep copy of self"""
        return Rule(self.name, self.value, self.score.points, self.score.doubles, self.score.limits)

    def exclusive(self):
        """True if this rule can only apply to one player"""
        return 'payforall' in self.actions

class Regex(object):
    """use a regular expression for defining a variant"""
    def __init__(self, rule, value):
        self.rule = rule
        self.value = value
        try:
            self.compiled = re.compile(value)
        except Exception, eValue:
            logException(Exception('%s %s: %s' % (rule.name, value, eValue)))
            raise

    def appliesToHand(self, hand, melds):
        """does this regex match?"""
        if isinstance(self, RegexIgnoringCase):
            checkStr = melds.lower() + ' ' + hand.mjStr
        else:
            checkStr = melds + ' ' + hand.mjStr
        match = self.compiled.match(checkStr)
# only for testing
#        if match:
#            print 'MATCH:' if match else 'NO MATCH:', melds + ' ' + hand.mjStr + ' against ' + self.rule.name, self.rule.value
        return match

    def appliesToMeld(self, hand, meld):
        """does this regex match?"""
        if isinstance(self, RegexIgnoringCase):
            checkStr = meld.content.lower() + ' ' + hand.mjStr
        else:
            checkStr = meld.content + ' ' + hand.mjStr
        match = self.compiled.match(checkStr)
# only for testing
#        if self.rule.name =='Robbing the Kong':
#        if match:
#            print 'MATCH:' if match else 'NO MATCH:', meld.content + ' ' + hand.mjStr + ' against ' + self.rule.name, self.rule.value
        return match

class RegexIgnoringCase(Regex):
    """this Regex ignores case on the meld strings"""
    pass

class Splitter(object):
    """a regex with a name for splitting concealed and yet unsplitted tiles into melds"""
    def __init__(self, name,  value):
        self.name = name
        self.value = value
        self.compiled = re.compile(value)

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

    def regex(self, claimedKongAsConcealed=False):
        """a string containing the tile type, the meld size and its value. For Chow, return size 0.
        Example: C304 is a concealed pung of characters with 4 base points
        """
        myLen = 0 if self.meldType == CHOW else len(self)
        tileGroup = self.content[0]
        if self.meldType == KONG:
            tileGroup = self.content[2]
        elif self.meldType == CLAIMEDKONG and claimedKongAsConcealed:
            tileGroup = self.content[6]
        return '%s%s%02d' % (tileGroup,  str(myLen), self.score.points)

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

class PredefinedRuleset(Ruleset):
    """special code for loading rules from program code instead of from the database"""

    name = '' # only really usable classes may have a name, see predefinedRulesetClasses
    classes = set()

    def __init__(self, name):
        Ruleset.__init__(self, name)

    @staticmethod
    def rulesets():
        """a list of instances for all predefined rulesets"""
        return list(x() for x in PredefinedRuleset.classes)

    def rules(self):
        """here the predefined rulesets can define their rules"""
        pass

    def clone(self):
        """return a clone, unloaded"""
        return self.__class__()

def testScoring():
    """some simple tests"""
    testScore = Score(points=3)
    testScore.unit = 1
    assert testScore.doubles == 3
    assert testScore.value == 3

if __name__ == "__main__":
    testScoring()
