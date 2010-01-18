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
from timeit import Timer
from PyQt4.QtCore import QString

from util import m18n, m18nc, english, logException
from query import Query
from tile import Tile

CONCEALED, EXPOSED, ALLSTATES = 1, 2, 3
EMPTY, SINGLE, PAIR, CHOW, PUNG, KONG, CLAIMEDKONG, ALLMELDS, REST = \
        0, 1, 2, 4, 8, 16, 32, 63, 128

def shortcuttedMeldName(meld):
    """convert int to speaking name with shortcut"""
    if meld == ALLMELDS or meld == REST or meld == 0:
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
    tileOrder = 'xdwsbc'
    aPos = tileOrder.index(tile[0].lower()) + ord('0')
    return ''.join([chr(aPos), tile.lower()])

def meldKey(meld):
    """to be used in sort() and sorted() as key=.
    Sorts by tile (dwsbc), then by the whole meld, ignoring case"""
    return tileKey(meld.pairs[0])

class NamedList(list):
    """a list with a name and a description (to be used as hint)"""

    def __init__(self, listId, name, description):
        list.__init__(self)
        self.listId = listId
        self.name = name
        self.description = description

class Ruleset(object):
    """holds a full set of rules: splitRules,meldRules,handRules,winnerRules.

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

    def __init__(self, name, used=False, profileIt = False):
        self.name = name
        self.__used = used
        self.orgUsed = used
        self.savedHash = None
        self.rulesetId = 0
        self.hash = None
        self.__loaded = False
        self.__profileIt = False
        self.description = None
        self.splitRules = []
        self.meldRules = NamedList(1, m18n('Meld Rules'),
            m18n('Meld rules are applied to single melds independent of the rest of the hand'))
        self.handRules = NamedList(2, m18n('Hand Rules'),
            m18n('Hand rules are applied to the entire hand, for all players'))
        self.winnerRules = NamedList(3, m18n('Winner Rules'),
            m18n('Winner rules are applied to the entire hand but only for the winner'))
        self.mjRules = NamedList(4, m18n('Mah Jongg Rules'),
            m18n('Only hands matching a Mah Jongg rule can win'))
        self.manualRules = NamedList(99, m18n('Manual Rules'),
            m18n('Manual rules are applied manually by the user. We would prefer to live ' \
                'without them but sometimes the program has not yet enough information ' \
                'or is not intelligent enough to automatically apply them when appropriate'))
            # manual rules: Rule.appliesToHand() is used to determine if a manual rule can be selected.
        self.parameterRules = NamedList(999,  m18nc('kmj','Options'),
            m18n('Here we have several special game related options'))
        self.penaltyRules = NamedList(9999, m18n('Penalties'), m18n('Penalties are applied manually by the user'))
        self.ruleLists = list([self.meldRules, self.handRules, self.mjRules, self.winnerRules, self.manualRules,
            self.parameterRules, self.penaltyRules])
        # the order of ruleLists is the order in which the lists appear in the ruleset editor
        # if you ever want to remove an entry from ruleLists: make sure its listId is not reused or you get
        # in trouble when updating
        self.initRuleset()
        self.profileIt = profileIt
        self.__minMJTotal = None

    @apply
    def minMJTotal():
        """the minimum score for Mah Jongg including all winner points. This is not accurate,
        the correct number is bigger in CC: 22 and not 20. But it is enough saveguard against
        entering impossible scores for manual games."""
        def fget(self):
            if self.__minMJTotal is None:
                self.__minMJTotal = self.minMJPoints + min(x.score.total(self.limit) for x in self.mjRules)
            return self.__minMJTotal
        return property(**locals())

    @apply
    def profileIt():
        def fget(self):
            return self.__profileIt
        def fset(self, profileIt):
            self.__profileIt = profileIt
            for lst in self.ruleLists:
                for rule in lst:
                    for variant in rule.variants:
                        if isinstance(variant,Regex):
                            variant.profileIt = self.profileIt
        return property(**locals())

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
        self.loadRules()
        # we might have introduced new mandatory rules which do
        # not exist in the rulesets saved with the games, so preload
        # the default values from any predefined ruleset:
        if self.rulesetId: # a saved ruleset, do not do this for predefined rulesets
            predefRuleset = PredefinedRuleset.rulesets()[0]
            predefRuleset.load()
            for par in predefRuleset.parameterRules:
                self.__dict__[par.parName] = par.parameter
        for par in self.parameterRules:
            self.__dict__[par.parName] = par.parameter
        self.hash = self.computeHash()
        assert isinstance(self, PredefinedRuleset) or self.hash == self.savedHash

    def loadRules(self):
        """load rules from data base"""
        query = Query("select name, list, definition, points, doubles, limits, parameter from %s ' \
                'where ruleset=%d order by list,position" % \
                      (self.__ruleTable(), self.rulesetId))
        for record in query.data:
            (name, listNr, definition, points, doubles, limits, parameter) = record
            for ruleList in self.ruleLists:
                if ruleList.listId == listNr:
                    if ruleList is self.parameterRules:
                        rule = Rule(name, definition, parameter=parameter)
                    else:
                        rule = Rule(name, definition, int(points), int(doubles), float(limits))
                    ruleList.append(rule)
                    break

    def findManualRule(self, name):
        """return the manual rule named 'name'. Also finds it if the rule definition starts with name"""
        for rule in self.manualRules:
            if rule.name == name or rule.definition.startswith(name):
                return rule
        raise Exception('no manual rule found:' + name)

    def loadSplitRules(self):
        """loads the split rules"""
        self.splitRules.append(Splitter('kong', r'([dwsbc][1-9eswnbrg])([DWSBC][1-9eswnbrg])(\2)(\2)', 4))
        self.splitRules.append(Splitter('pung', r'([XDWSBC][1-9eswnbrgy])(\1\1)', 3))
        for chi1 in xrange(1, 8):
            rule =  r'(?P<g>[SBC])(%d)((?P=g)%d)((?P=g)%d) ' % (chi1, chi1+1, chi1+2)
            self.splitRules.append(Splitter('chow', rule, 3))
            # discontinuous chow:
            rule =  r'(?P<g>[SBC])(%d).*((?P=g)%d).*((?P=g)%d)' % (chi1, chi1+1, chi1+2)
            self.splitRules.append(Splitter('chow', rule, 3))
            self.splitRules.append(Splitter('chow', rule, 3))
        self.splitRules.append(Splitter('pair', r'([DWSBCdwsbc][1-9eswnbrg])(\1)', 2))
        self.splitRules.append(Splitter('single', r'(..)', 1))

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
        logException(Exception(m18n('You already have the maximum number of copies, please rename some')))

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
        logException(Exception(m18n('You already have the maximum number of copies, please rename some')))

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
            if rule.parType is bool:
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
                definition = rule.definition
                if rule.parType:
                    definition = rule.parType.__name__ + definition
                cmdList.append('INSERT INTO %s(ruleset, list, position, name, definition, points, doubles, limits, parameter)'
                ' VALUES(%d,%d,%d,"%s","%s",%d,%d,%f,"%s") ' % \
                    (self.__ruleTable(), rulesetId, ruleList.listId, ruleIdx, english.get(rule.name, rule.name),
                    definition, score.points, score.doubles, score.limits,
                    str(rule.parameter)))
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
    return ' '.join([meld.joined for meld in melds])

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

    @apply
    def unit():
        """for use in ruleset tree view. returns an index into Score.units."""
        def fget(self):
            self.assertSingleUnit()
            if self.doubles:
                return 1
            elif self.limits:
                return 2
            else:
                return 0
        def fset(self, unit):
            self.assertSingleUnit()
            oldValue = self.value
            self.clear()
            self.__setattr__(Score.unitName(unit), oldValue)
        return property(**locals())

    @apply
    def value():
        """value without unit. Only one unit value may be set for this to be usable"""
        def fget(self):
            self.assertSingleUnit()
            # limits first because for all 0 we want to get 0, not 0.0
            return self.limits or self.points or self.doubles
        def fset(self, value):
            self.assertSingleUnit()
        return property(**locals())

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


class HandContent(object):
    """represent the hand to be evaluated"""

    cache = dict()
    cachedRulesetId = None

    @staticmethod
    def cached(ruleset, string, manuallyDefinedRules=None, computedRules=None):
        """since a HandContent instance is never changed, we can use a cache"""
        mRuleHash = '&&'.join([rule.name for rule in manuallyDefinedRules]) if manuallyDefinedRules else 'None'
        cRuleHash = '&&'.join([rule.name for rule in computedRules]) if computedRules else 'None'
        cacheKey = (string, mRuleHash, cRuleHash)
        cache = HandContent.cache
        if HandContent.cachedRulesetId != ruleset.rulesetId:
            cache.clear()
            HandContent.cachedRulesetId = ruleset.rulesetId
        if len(cache) > 1000:
            cache.clear() # brute force...
        if cacheKey in cache:
            return cache[cacheKey]
        result = HandContent(ruleset, string, manuallyDefinedRules=manuallyDefinedRules,
            computedRules=computedRules)
        cache[cacheKey] = result
        return result

    def __init__(self, ruleset, string, manuallyDefinedRules=None, computedRules=None):
        """evaluate string using ruleset. rules are to be applied in any case."""
        self.ruleset = ruleset
        self.string = string
        self.manuallyDefinedRules = []
        for rule in manuallyDefinedRules or []:
            if not isinstance(rule, Rule):
                rule = ruleset.findManualRule(rule)
            self.manuallyDefinedRules.append(rule)
        self.computedRules = []
        for rule in computedRules or []:
            if not isinstance(rule, Rule):
                rule = ruleset.findManualRule(rule)
            self.computedRules.append(rule)
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

        self.singleList = Pairs(''.join(tileStrings).replace(' ', ''))
        self.tiles = ' '.join(tileStrings)
        self.mjStr = ' '.join(mjStrings)
        self.melds = set()
        self.__summary = None
        self.normalized = None
        self.sortedMelds = None
        self.hiddenMelds = None
        self.fsMelds = set()
        self.invalidMelds = set()
        self.separateMelds()
        self.usedRules = [] # a list of tuples: each tuple hold the rule and None or a meld
        if self.invalidMelds:
            raise Exception('has invalid melds: ' + ','.join(meld.joined for meld in self.invalidMelds))

        for meld in self.melds:
            meld.score = Score()
        self.applyMeldRules()
        self.original += ' ' + self.summary
        self.sortedMelds =  meldsContent(sorted(self.melds, key=meldKey))
        if self.fsMelds:
            self.sortedMelds += ' ' + meldsContent(sorted(list(self.fsMelds)))
        self.hiddenMelds = [meld for meld in self.melds if meld.state == CONCEALED and not meld.isKong()]
        self.normalized = self.sortedMelds + ' ' + self.summary
        self.won &= self.maybeMahjongg(checkScore=False)
        ruleTuples = [(rule, None) for rule in self.manuallyDefinedRules + self.computedRules]
        for rules in [ruleTuples, self.usedRules]:
            # explicitly passed rules have precedence
            exclusive = self.__exclusiveRules(rules)
            if exclusive: # if a meld rule is exclusive: like if east said 9 times MJ
                self.usedRules = exclusive
                self.score = self.__totalScore(exclusive)
                return
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
        return rule.appliesToHand(self, self.original) or rule.appliesToHand(self, self.normalized)

    def hasAction(self, action):
        """return rule with action from used rules"""
        for ruleTuple in self.usedRules:
            rule = ruleTuple[0]
            if action in rule.actions:
                return rule

    def hasTiles(self, tileNames):
        for tileName in tileNames:
            if not tileName in self.singleList:
                return False
        return tileNames

    def handLenOffset(self):
        """return <0 for short hand, 0 for correct calling hand, >0 for long hand
        if there are no kongs, 13 tiles will return 0"""
        tileCount = sum(len(meld) for meld in self.melds)
        kongCount = self.countMelds(Meld.isKong)
        return tileCount - kongCount - 13

    def maybeMahjongg(self, checkScore=True):
        """check if this hand can be a regular mah jongg"""
        if self.handLenOffset() != 1:
            return False
        if not any(self.ruleMayApply(rule) for rule in self.ruleset.mjRules):
            return False
        if not checkScore or self.ruleset.minMJPoints == 0:
            return True
        if self.won:
            checkHand = self
        else:
            checkHand = HandContent(self.ruleset, self.string.replace(' m', ' M'), self.manuallyDefinedRules, self.computedRules)
        return checkHand.total() >= self.ruleset.minMJTotal

    def lastMeld(self, lastTile):
        lastMelds = [x for x in self.hiddenMelds if lastTile in x.pairs]
        lastMeld = lastMelds[0] # default: the first possible last meld
        if len(lastMelds) > 0:
            for meld in lastMelds:
                if meld.isPair():       # completing pairs gives more points.
                    lastMeld = meld
                    break
        return lastMeld

    def splitRegex(self, rest):
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

    @staticmethod
    def genVariants(original, maxPairs=1):
        """generates all possible meld variants out of original
        where original is a list of tile values like ['1','1','2']"""
        pairsFound = 0
        color = original[0][0]
        original = [x[1] for x in original]
        def x(cVariants,foundMelds,rest):
            values = set(rest)
            melds = []
            for value in values:
                intValue = int(value)
                if rest.count(value) == 3:
                    melds.append([value] * 3)
                if rest.count(value) == 2:
                    melds.append([value] * 2)
                if rest.count(str(intValue + 1)) and rest.count(str(intValue + 2)):
                    melds.append([value,str(intValue+1),str(intValue+2)])
            pairsFound = 0
            for meld in foundMelds:
                if len(meld) == 2:
                    pairsFound += 1
            for meld in melds:
                if len(meld) == 2 and pairsFound >= maxPairs:
                    continue
                restCopy = rest[:]
                for value in meld:
                    restCopy.remove(value)
                newMelds = foundMelds[:]
                newMelds.append(meld)
                if restCopy:
                    x(cVariants,newMelds,restCopy)
                else:
                    for idx, newMeld in enumerate(newMelds):
                        newMelds[idx] = ''.join(color+x for x in newMeld)
                    cVariants.append(' '.join(sorted(newMelds )))
        cVariants = []
        x(cVariants,[], original)
        variants = []
        for variant in set(cVariants):
            melds = [Meld(x) for x in variant.split()]
            variants.append(set(melds))
        return variants

    def split(self, rest):
        """work hard to always return the variant with the highest Mah Jongg value."""
        pairs = Meld(rest).pairs
        if 'Xy' in pairs:
            # hidden tiles of other players:
            return self.splitRegex(rest)
        honourPairs = [pair for pair in pairs if pair[0] in 'DWdw']
        result = self.splitRegex(''.join(honourPairs)) # easy since they cannot have a chow
        for color in 'SBC':
            colorPairs = [pair for pair in pairs if pair[0] == color]
            if not colorPairs:
                continue
            splitVariants = self.genVariants(colorPairs)
            if splitVariants:
                if len(splitVariants) > 1:
                    bestHand = None
                    bestVariant = None
                    for splitVariant in splitVariants:
                        hand = HandContent.cached(self.ruleset, \
                            ' '.join(x.joined for x in (self.melds | splitVariant | self.fsMelds)) \
                            + ' ' + self.mjStr, manuallyDefinedRules=self.manuallyDefinedRules,
                            computedRules=self.computedRules)
                        if not bestHand:
                            bestHand = hand
                            bestVariant =splitVariant
                        else:
                            if hand.total() > bestHand.total():
                                bestHand = hand
                                bestVariant =splitVariant
                    splitVariants[0] = bestVariant
                result |= splitVariants[0]
            else:
                result |= self.splitRegex(''.join(colorPairs)) # fallback: nothing useful found
        return result

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
        # no matter how the tiles are grouped make a single
        # meld for every bonus tile
        boni = []
        if 'f' in self.tiles or 'y' in self.tiles: # optimize
            for pair in Pairs(self.tiles):
                if pair[0] in 'fy':
                    boni.append(pair)
                    self.tiles = self.tiles.replace(pair, '', 1)
        splits = self.tiles.split()
        splits.extend(boni)
        rest = []
        for split in splits:
            if len(split) > 8:
                rest.append(split)
                continue
            meld = Meld(split)
            if (split[0].islower() or split[0] in 'mM') or meld.meldType != REST:
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
        usedRules = list([(rule, None) for rule in self.matchingRules(
            handStr, self.ruleset.handRules + self.manuallyDefinedRules + self.computedRules)])
        won = self.won
        if won and self.__totalScore(self.usedRules + usedRules).total(self.ruleset.limit) < self.ruleset.minMJPoints:
            won = False
        if won:
            for rule in self.matchingRules(handStr, self.ruleset.winnerRules + self.ruleset.mjRules):
                usedRules.append((rule, None))
        return (self.__totalScore(self.usedRules + usedRules), usedRules, won)

    def __exclusiveRules(self, rules):
        """returns a list of applicable rules which exclude all others"""
        return list(x for x in rules if 'absolute' in x[0].actions) \
            or list(x for x in rules if x[0].score.limits>=1.0)

    def explain(self):
        return [x[0].explain() for x in self.usedRules]

    @apply
    def summary():
        """returns a summarizing string for this hand"""
        def fget(self):
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
        return property(**locals())

    def __str__(self):
        """hand as a string"""
        return u' '.join([meldsContent(self.melds), meldsContent(sorted(list(self.fsMelds))), self.summary, self.mjStr])

class Rule(object):
    """a mahjongg rule with a name, matching variants, and resulting score.
    The rule applies if at least one of the variants matches the hand.
    For parameter rules, only use name, definition,parameter. definition must start with int or str
    which is there for loading&saving, but internally is stripped off."""
    english = {}
    def __init__(self, name, definition, points = 0,  doubles = 0, limits = 0, parameter = None):
        self.actions = {}
        self.variants = []
        self.name = name
        self.score = Score(points, doubles, limits)
        self._definition = None
        self.prevDefinition = None
        self.parName = ''
        self.parameter = ''
        self.parType = None
        for parType in [int, str, bool]:
            typeName = parType.__name__
            if definition.startswith(typeName):
                self.parType = parType
                if parType is bool and type(parameter) in (str, unicode):
                    parameter =  parameter != 'False'
                self.parameter = parType(parameter)
                definition = definition[len(typeName):]
                break
        self.definition = definition

    @apply
    def definition():
        def fget(self):
            if isinstance(self._definition, list):
                return '||'.join(self._definition)
            else:
                return self._definition
        def fset(self, definition):
            """setter for definition"""
            assert not isinstance(definition, QString)
            self.prevDefinition = self.definition
            self._definition = definition
            if not definition:
                return  # may happen with special programmed rules
            variants = definition.split('||')
            if self.parType:
                self.parName = variants[0]
                variants = variants[1:]
            self.actions = {}
            self.variants = []
            for variant in variants:
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
        return property(**locals())

    def validate(self):
        """check for validity"""
        payers = int(self.actions.get('payers', 1))
        payees = int(self.actions.get('payees', 1))
        if not 2 <= payers + payees <= 4:
            self.definition = self.prevDefinition
            logException(Exception(m18nc('%1 can be a sentence', '%4 have impossible values %2/%3 in rule "%1"',
                                  self.name, payers, payees, 'payers/payees')))

    def appliesToHand(self, hand, melds):
        """does the rule apply to this hand?"""
        result = any(variant.appliesToHand(hand, melds) for variant in self.variants)
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
        return '%s: %s %s %s' % (self.name, self.parameter, self.definition, self.score)

    def __repr__(self):
        return self.__str__()

    def copy(self):
        """returns a deep copy of self"""
        return Rule(self.name, self.definition, self.score.points, self.score.doubles, self.score.limits, self.parameter)

    def exclusive(self):
        """True if this rule can only apply to one player"""
        return 'payforall' in self.actions

    def hasNonValueAction(self):
        return any(x != 'lastsource' for x in self.actions)

class Regex(object):
    """use a regular expression for defining a variant"""
    def __init__(self, rule, definition):
        self.rule = rule
        self.definition = definition
        self.profileIt = False
        self.timeSum = 0.0
        self.count = 0
        try:
            self.compiled = re.compile(definition)
        except Exception, eValue:
            logException(Exception('%s %s: %s' % (rule.name, definition, eValue)))
            raise

    def appliesToHand(self, hand, melds):
        """does this regex match?"""
        meldStr = melds if melds else ''
        if isinstance(self, RegexIgnoringCase):
            checkStr = meldStr.lower() + ' ' + hand.mjStr
        else:
            checkStr = meldStr + ' ' + hand.mjStr
        str2 = ' ,,, '.join((checkStr, checkStr))
        if self.profileIt:
            self.timeSum += Timer(stmt='x.search("%s")'%str2,setup="""import re
x=re.compile(r"%s")"""%self.definition).timeit(50)
            self.count += 1
        match = self.compiled.search(str2)
# only for testing
#        print 'MATCH:' if match else 'NO MATCH:', str2 + ' against ' + self.rule.name, \
#              self.rule.definition
        return match

    def appliesToMeld(self, hand, meld):
        """does this regex match?"""
        if isinstance(self, RegexIgnoringCase):
            checkStr = meld.joined.lower() + ' ' + hand.mjStr
        else:
            checkStr = meld.joined + ' ' + hand.mjStr
        match = self.compiled.match(checkStr)
# only for testing
#        if match:
#            print 'MATCH:' if match else 'NO MATCH:', meld.joined + ' ' + hand.mjStr + ' against ' + self.rule.name, self.rule.definition
        return match

class RegexIgnoringCase(Regex):
    """this Regex ignores case on the meld strings"""
    pass

class Splitter(object):
    """a regex with a name for splitting concealed and yet unsplitted tiles into melds"""
    def __init__(self, name,  definition, size):
        self.name = name
        self.definition = definition
        self.size = size
        self.compiled = re.compile(definition)

    def apply(self, split):
        """work the found melds in reverse order because we remove them from the rest:"""
        result = []
        if len(split) >= self.size * 2:
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

class Pairs(list):
    """base class for Meld and Slot"""
    def __init__(self, newContent=None):
        if newContent:
            if isinstance(newContent, list):
                self.extend(newContent)
            else:
                self.extend([newContent[x:x+2] for x in range(0, len(newContent), 2)])

    def startChars(self, first=None, last=None):
        """use first and last as for ranges"""
        if first is not None:
            if last is None:
                return self[first][0]
        else:
            assert last is None
            first, last = 0, len(self)
        return list(x[0] for x in self[first:last])

    def values(self, first=None, last=None):
        """use first and last as for ranges"""
        if first is not None:
            if last is None:
                return int(self[first][1])
        else:
            assert last is None
            first, last = 0, len(self)
        return list(int(x[1]) for x in self[first:last])

    def toLower(self, first=None, last=None):
        """use first and last as for ranges"""
        if first is not None:
            if last is None:
                self[first] = self[first].lower()
                return
        else:
            assert last is None
            first, last = 0, len(self)
        for idx in range(first, last):
            self[idx] = self[idx].lower()
        return self

    def toUpper(self, first=None, last=None):
        """use first and last as for ranges"""
        if first is not None:
            if last is None:
                self[first] = self[first].capitalize()
                return
        else:
            assert last is None
            first, last = 0, len(self)
        for idx in range(first, last):
            self[idx] = self[idx].capitalize()
        return self

    def lower(self, first=None, last=None):
        """use first and last as for ranges"""
        return Pairs(self).toLower(first, last)

    def isLower(self, first=None, last=None):
        """use first and last as for ranges"""
        if first is not None:
            if last is None:
                return self[first].islower()
        else:
            assert last is None
            first, last = 0, len(self)
        return ''.join(self[first:last]).islower()

    def isUpper(self, first=None, last=None):
        """use first and last as for ranges"""
        if first is not None:
            if last is None:
                return self[first].istitle()
        else:
            assert last is None
            first, last = 0, len(self)
        return all(self[x].istitle() for x in range(first, last))

class Meld(object):
    """represents a meld. Can be empty. Many Meld methods will
    raise exceptions if the meld is empty. But we do not care,
    those methods are not supposed to be called on empty melds"""

    tileNames = {'x':m18nc('kmj','hidden'),'s': m18nc('kmj','stone') , 'b': m18nc('kmj','bamboo'), 'c':m18nc('kmj','character'),
        'w':m18nc('kmj','wind'), 'd':m18nc('kmj','dragon'),
        'f':m18nc('kmj','flower'), 'y':m18nc('kmj','season')}
    valueNames = {'Y':m18nc('kmj','tile'),'b':m18nc('kmj','white'), 'r':m18nc('kmj','red'), 'g':m18nc('kmj','green'),
        'e':m18nc('kmj','east'), 's':m18nc('kmj','south'), 'w':m18nc('kmj','west'), 'n':m18nc('kmj','north'),
        'O':m18nc('kmj','own wind'), 'R':m18nc('kmj','round wind')}
    for valNameIdx in range(1, 10):
        valueNames[str(valNameIdx)] = str(valNameIdx)

    def __init__(self, newContent = None):
        """init the meld: content is a single string with 2 chars for every tile
        or a list containing of such strings"""
        if isinstance(newContent, Meld):
            newContent = newContent.joined
        self.__pairs = []
        self.__valid = False
        self.score = Score()
        self.name = None
        self.meldType = None
        self.slot = None
        self.tiles = []
        self.joined = newContent

    def __len__(self):
        """how many tiles do we have?"""
        return len(self.tiles) if self.tiles else len(self.__pairs)

    def __str__(self):
        """make meld printable"""
        if not self.pairs:
            return 'EMPTY'
        which = Meld.tileNames[self.__pairs[0][0].lower()]
        value = Meld.valueNames[self.__pairs[0][1]]
        pStr = m18nc('kmj', '%1 points',  self.score.points) if self.score.points else ''
        fStr = m18nc('kmj', '%1 doubles',  self.score.doubles) if self.score.doubles else ''
        score = ' '.join([pStr, fStr])
        return u'%s %s %s %s:   %s' % (stateName(self.state),
                        self.name, which, value, score)

    def __getitem__(self, index):
        """Meld[x] returns Tile # x """
        return self.tiles[index]

    def __eq__(self, other):
        return self.pairs == other.pairs

    def isValid(self):
        """is it valid?"""
        return self.__valid

    def __isChow(self):
        """expensive, but this is only computed once per meld"""
        if len(self.__pairs) == 3:
            starts = set(self.__pairs.startChars())
            if len(starts) == 1:
                if starts & set('sbcSBC'):
                    values = self.__pairs.values()
                    if values[1] == values[0] + 1 and values[2] == values[0] + 2:
                        return True
        return False

    @apply
    def state():
        """meld state"""
        def fget(self):
            firsts = self.__pairs.startChars()
            if ''.join(firsts).islower():
                return EXPOSED
            elif len(self) == 4 and firsts[1].isupper() and firsts[2].isupper():
                return CONCEALED
            elif len(self) == 4:
                return EXPOSED
            else:
                return CONCEALED
        def fset(self, state):
            if state == EXPOSED:
                self.__pairs.toLower()
                if self.meldType == CLAIMEDKONG:
                    self.__pairs.toUpper(3)
            elif state == CONCEALED:
                self.__pairs.toUpper()
                if len(self.__pairs) == 4:
                    self.__pairs.toLower(0)
                    self.__pairs.toLower(3)
            else:
                raise Exception('meld.setState: illegal state %d' % state)
            for idx, tile in enumerate(self.tiles):
                tile.element = self.__pairs[idx]
        return property(**locals())

    def _getMeldType(self):
        """compute meld type"""
        length = len(self.__pairs)
        if not length:
            return EMPTY
        assert self.__pairs[0][0].lower() in 'xdwsbcfy', self.__pairs
        if length == 1:
            result = SINGLE
        elif length == 2:
            result = PAIR
        elif length== 4:
            if self.__pairs.isUpper():
                result = REST
                self.__valid = False
            elif self.__pairs.isLower(0, 3) and self.__pairs.isUpper(3):
                result = CLAIMEDKONG
            else:
                result = KONG
        elif self.__isChow():
            result = CHOW
        elif length == 3:
            result = PUNG
        else:
            result = REST
        if result == CHOW:
            assert len(set(self.__pairs.startChars())) == 1
        elif result != REST:
            if len(set(x.lower() for x in self.__pairs)) > 1:
                result = REST
        return result

    def tileType(self):
        """return one of d w s b c f y"""
        return self.__pairs[0][0].lower()

    def isDragon(self):
        """is it a meld of dragons?"""
        return self.__pairs[0][0] in 'dD'

    def isWind(self):
        """is it a meld of winds?"""
        return self.__pairs[0][0] in 'wW'

    def isColor(self):
        """is it a meld of colors?"""
        return self.__pairs[0][0] in 'sSbBcC'

    def isPair(self, tileName=None):
        if self.meldType != PAIR:
            return False
        if tileName and self.__pairs[0] != tileName:
            return False
        return True

    def isPung(self, tileName=None):
        if self.meldType != PUNG:
            return False
        if tileName and self.__pairs[0] != tileName:
            return False
        return True

    def isKong(self):
        """is it a kong?"""
        return self.meldType in (KONG,  CLAIMEDKONG)

    def regex(self, claimedKongAsConcealed=False):
        """a string containing the tile type, the meld size and its value. For Chow, return size 0.
        Example: C304 is a concealed pung of characters with 4 base points
        """
        myLen = 0 if self.meldType == CHOW else len(self)
        idx = 0
        if self.meldType == KONG:
            idx = 1
        elif self.meldType == CLAIMEDKONG and claimedKongAsConcealed:
            idx = 3
        return '%s%s%02d' % (self.__pairs[idx][0],  str(myLen), self.score.points)

    @apply
    def pairs():
        """make them readonly"""
        def fget(self):
            return self.__pairs
        return property(**locals())

    @apply
    def joined():
        """content"""
        def fget(self):
            return ''.join(self.__pairs)
        def fset(self, newContent):
            self.__pairs = Pairs(newContent)
            self.__valid = True
            self.name = m18nc('kmj','not a meld')
            self.meldType = self._getMeldType()
            self.name = meldName(self.meldType)
        return property(**locals())

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

    m1 = Meld('c1c1c1C1')
    p1 = m1.pairs
    p2 = p1.lower()
    assert p1 !=  p2
    p1.toLower(3)
    assert p1 ==  p2

if __name__ == "__main__":
    testScoring()
