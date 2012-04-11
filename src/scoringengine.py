# -*- coding: utf-8 -*-

"""Copyright (C) 2009-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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



Read the user manual for a description of the interface to this scoring engine
"""

# pylint: disable=C0302
# too many lines in module

import re # the new regex is about 7% faster
from hashlib import md5 # pylint: disable=E0611

from PyQt4.QtCore import QString

from util import m18n, m18nc, english, logException # , logDebug
from common import elements, elements
from query import Query
from tile import chiNext
from meld import Meld, meldKey, Score, meldsContent, Pairs, \
    REST, CONCEALED, EXPOSED, CLAIMEDKONG

class RuleList(list):
    """a list with a name and a description (to be used as hint).
    Rules can be indexed by name or index.
    Adding a rule either replaces an existing rule or appends it."""

    def __init__(self, listId, name, description):
        list.__init__(self)
        self.listId = listId
        self.name = name
        self.description = description

    def __getitem__(self, name):
        """find rule by name"""
        if isinstance(name, int):
            return self[name]
        for rule in self:
            if rule.name == name:
                return rule
        raise KeyError

    def __setitem__(self, name, rule):
        """set rule by name"""
        assert isinstance(rule, Rule)
        if isinstance(name, int):
            list.__setitem__(self, name, rule)
            return
        for idx, oldRule in enumerate(self):
            if oldRule.name == name:
                list.__setitem__(self, idx, rule)
                return
        list.append(self, rule)

    def __delitem__(self, name):
        """delete this rule"""
        if isinstance(name, int):
            list.__delitem__(self, name)
            return
        for idx, rule in enumerate(self):
            if rule.name == name:
                list.__delitem__(self, idx)
                return
        raise KeyError

    def append(self, rule):
        """do not append"""
        raise Exception('do not append %s' % rule)

    def add(self, rule):
        """use add instead of append"""
        self[rule.name] = rule

class Ruleset(object):
    """holds a full set of rules: splitRules,meldRules,handRules,winnerRules.

        predefined rulesets are preinstalled together with kajongg. They can be customized by the user:
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
    # pylint: disable=R0902
    # pylint we need more than 10 instance attributes

    cache = dict()
    hits = 0
    misses = 0

    @staticmethod
    def clearCache():
        """clears the cache with Rulesets"""
        Ruleset.cache.clear()

    @staticmethod
    def cached(name, used=False):
        """If a Ruleset instance is never changed, we can use a cache"""
        cache = Ruleset.cache
        cacheKey = str(name) + str(used)
        if cacheKey in cache:
            return cache[cacheKey]
        result = Ruleset(name, used)
        cache[cacheKey] = result
        return result


    def __init__(self, name, used=False):
        self.name = name
        self.__used = used
        self.orgUsed = used
        self.rulesetId = 0
        self.__hash = None
        self.allRules = []
        self.__dirty = False # only the ruleset editor is supposed to make us dirty
        self.__loaded = False
        self.description = None
        self.rawRules = None # used when we get the rules over the network
        self.splitRules = []
        self.meldRules = RuleList(1, m18n('Meld Rules'),
            m18n('Meld rules are applied to single melds independent of the rest of the hand'))
        self.handRules = RuleList(2, m18n('Hand Rules'),
            m18n('Hand rules are applied to the entire hand, for all players'))
        self.winnerRules = RuleList(3, m18n('Winner Rules'),
            m18n('Winner rules are applied to the entire hand but only for the winner'))
        self.mjRules = RuleList(4, m18n('Mah Jongg Rules'),
            m18n('Only hands matching a Mah Jongg rule can win'))
        self.parameterRules = RuleList(999, m18nc('kajongg','Options'),
            m18n('Here we have several special game related options'))
        self.penaltyRules = RuleList(9999, m18n('Penalties'), m18n('Penalties are applied manually by the user'))
        self.ruleLists = list([self.meldRules, self.handRules, self.mjRules, self.winnerRules,
            self.parameterRules, self.penaltyRules])
        # the order of ruleLists is the order in which the lists appear in the ruleset editor
        # if you ever want to remove an entry from ruleLists: make sure its listId is not reused or you get
        # in trouble when updating
        self.initRuleset()
        self.__minMJTotal = None

    @apply
    def dirty(): # pylint: disable=E0202
        """have we been modified since load or last save?"""
        def fget(self):
            # pylint: disable=W0212
            return self.__dirty
        def fset(self, dirty):
            # pylint: disable=W0212
            self.__dirty = dirty
            if dirty:
                self.__computeHash()
        return property(**locals())

    @apply
    def hash():
        """a md5sum computed from the rules but not name and description"""
        def fget(self):
            # pylint: disable=W0212
            if not self.__hash:
                self.__computeHash()
            return self.__hash
        return property(**locals())


    def __eq__(self, other):
        """two rulesets are equal if everything except name or description is identical.
        The name might be localized."""
        return self.hash == other.hash

    @apply
    def minMJTotal():
        """the minimum score for Mah Jongg including all winner points. This is not accurate,
        the correct number is bigger in CC: 22 and not 20. But it is enough saveguard against
        entering impossible scores for manual games."""
        def fget(self):
            # pylint: disable=W0212
            if self.__minMJTotal is None:
                self.__minMJTotal = self.minMJPoints + min(x.score.total() for x in self.mjRules)
            return self.__minMJTotal
        return property(**locals())

    def initRuleset(self):
        """load ruleset headers but not the rules"""
        if isinstance(self.name, int):
            query = Query("select id,name,description from %s where id=%d" % \
                          (self.__rulesetTable(), self.name))
        elif isinstance(self.name, list):
            # we got the rules over the wire
            self.rawRules = self.name[1:]
            (self.rulesetId, self.name, self.description) = self.name[0]
            return
        else:
            query = Query("select id,name,description from %s where name=?" % \
                          self.__rulesetTable(), list([self.name]))
        if len(query.records):
            (self.rulesetId, self.name, self.description) = query.records[0]
        else:
            raise Exception(m18n('ruleset "%1" not found', self.name))

    def load(self):
        """load the ruleset from the database and compute the hash"""
        if self.__loaded:
            return
        self.__loaded = True
        # we might have introduced new mandatory rules which do
        # not exist in the rulesets saved with the games, so preload
        # the default values from any predefined ruleset:
        # TODO: the ruleset should know from which predefined ruleset it
        # has been copied - use that one. For now use sorted() here to
        # avoid random differences
        if self.rulesetId: # a saved ruleset, do not do this for predefined rulesets
            predefRuleset = sorted(PredefinedRuleset.rulesets())[0]
            predefRuleset.load()
            for par in predefRuleset.parameterRules:
                self.__dict__[par.parName] = par.parameter
        self.loadSplitRules()
        self.loadRules()
        for par in self.parameterRules:
            self.__dict__[par.parName] = par.parameter
        for ruleList in self.ruleLists:
            for rule in ruleList:
                rule.score.limitPoints = self.limit
                self.allRules.append(rule)

    def loadQuery(self):
        """returns a Query object with loaded ruleset"""
        return Query("select ruleset, name, list, position, definition, points, doubles, limits, parameter from %s ' \
                'where ruleset=%d order by list,position" % \
                      (self.__ruleTable(), self.rulesetId))

    @staticmethod
    def fromList(source):
        """returns a Ruleset as defined by the list source"""
        result = Ruleset(source)
        for predefined in PredefinedRuleset.rulesets():
            if result == predefined:
                return predefined
        return result

    def toList(self):
        """returns entire ruleset encoded in a string"""
        self.load()
        result = [[self.rulesetId, self.name, self.description]]
        result.extend(self.ruleRecords())
        return result

    def loadRules(self):
        """load rules from database or from self.rawRules (got over the net)"""
        for record in self.rawRules or self.loadQuery().records:
            self.loadRule(record)

    def loadRule(self, record):
        """loads a rule into the correct ruleList"""
        (rulesetIdx, name, listNr, position, definition, points, doubles, limits, # pylint: disable=W0612
            parameter) = record
        for ruleList in self.ruleLists:
            if ruleList.listId == listNr:
                if ruleList is self.parameterRules:
                    rule = Rule(name, definition, parameter=parameter)
                else:
                    try:
                        pointValue = int(points)
                    except ValueError:
                        # this happens if the unit changed from limits to points but the value
                        # is not converted at the same time
                        pointValue = int(float(points))
                    rule = Rule(name, definition, pointValue, int(doubles), float(limits))
                ruleList.add(rule)
                break

    def findRule(self, name):
        """return the rule named 'name'. Also finds it if the rule definition starts with name"""
        for ruleList in self.ruleLists:
            for rule in ruleList:
                if rule.name == name or rule.definition.startswith(name):
                    return rule
        raise Exception('no rule found:' + name)

    def findAction(self, action):
        """return first rule with action"""
        matchingRules = list(x for x in self.allRules if action in x.actions)
        assert len(matchingRules) < 2, '%s has too many matching rules for %s' % (str(self), action)
        if matchingRules:
            return matchingRules[0]

    def loadSplitRules(self):
        """loads the split rules"""
        self.splitRules.append(Splitter('kong', r'([dwsbc][1-9eswnbrg])([DWSBC][1-9eswnbrg])(\2)(\2)', 4))
        self.splitRules.append(Splitter('pung', r'([XDWSBC][1-9eswnbrgy])(\1\1)', 3))
        for chi1 in xrange(1, 8):
            rule = r'(?P<g>[SBC])(%d)((?P=g)%d)((?P=g)%d) ' % (chi1, chi1+1, chi1+2)
            self.splitRules.append(Splitter('chow', rule, 3))
            # discontinuous chow:
            rule = r'(?P<g>[SBC])(%d).*((?P=g)%d).*((?P=g)%d)' % (chi1, chi1+1, chi1+2)
            self.splitRules.append(Splitter('chow', rule, 3))
            self.splitRules.append(Splitter('chow', rule, 3))
        self.splitRules.append(Splitter('pair', r'([DWSBCdwsbc][1-9eswnbrg])(\1)', 2))
        self.splitRules.append(Splitter('single', r'(..)', 1))

    def newId(self, used=None):
        """returns an unused ruleset id. This is not multi user safe."""
        if used is not None:
            self.__used = used
        records = Query("select max(id)+1 from %s" % self.__rulesetTable()).records
        try:
            return int(records[0][0])
        except ValueError:
            return 1

    @staticmethod
    def nameIsDuplicate(name):
        """show message and raise Exception if ruleset name is already in use"""
        return bool(Query('select id from ruleset where name=?', list([name])).records)

    def _newKey(self):
        """returns a new key and a new name for a copy of self"""
        newId = self.newId()
        for copyNr in range(1, 100):
            copyStr = ' ' + str(copyNr) if copyNr > 1 else ''
            newName = m18nc('Ruleset._newKey:%1 is empty or space plus number',
                'Copy%1 of %2', copyStr, m18n(self.name))
            if not self.nameIsDuplicate(newName):
                return newId, newName
        logException('You already have the maximum number of copies, please rename some')

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
        self.rulesetId, self.name = self._newKey()
        self.dirty = True # does not yet exist
        return self.save()

    def __ruleList(self, rule):
        """return the list containg rule. We could make the list
        an attribute of the rule but then we rarely
        need this, and it is not time critical"""
        for ruleList in self.ruleLists:
            if rule in ruleList:
                return ruleList
        assert False

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
        query = Query("update ruleset set name=? where name =?",
            list([newName, self.name]))
        if query.success:
            self.name = newName
        return query.success

    def remove(self):
        """remove this ruleset from the database."""
        Query(["DELETE FROM %s WHERE ruleset=%d" % (self.__ruleTable(), self.rulesetId),
                   "DELETE FROM %s WHERE id=%d" % (self.__rulesetTable(), self.rulesetId)])

    @staticmethod
    def ruleKey(rule):
        """needed for sorting the rules"""
        return rule.__str__()

    def __computeHash(self):
        """compute the hash for this ruleset using all rules but not name and
        description of the ruleset"""
        self.load()
        result = md5()
        for rule in sorted(self.allRules, key=Ruleset.ruleKey):
            result.update(rule.hashStr())
        self.__hash = result.hexdigest()

    def ruleRecords(self):
        """returns a list of all rules, prepared for use by sql"""
        parList = []
        for ruleList in self.ruleLists:
            for ruleIdx, rule in enumerate(ruleList):
                score = rule.score
                definition = rule.definition
                if rule.parType:
                    parTypeName = rule.parType.__name__
                    if parTypeName == 'unicode':
                        parTypeName = 'str'
                    definition = parTypeName + definition
                parList.append(list([self.rulesetId, english(rule.name), ruleList.listId, ruleIdx,
                    definition, score.points, score.doubles, score.limits, str(rule.parameter)]))
        return parList

    def save(self):
        """save the ruleset to the database"""
        if not self.dirty and self.__used == self.orgUsed:
            # same content in same table
            return True
        Query.dbhandle.transaction()
        self.remove()
        if not Query('INSERT INTO %s(id,name,hash,description) VALUES(?,?,?,?)' % self.__rulesetTable(),
            list([self.rulesetId, english(self.name), self.hash, self.description])).success:
            Query.dbhandle.rollback()
            return False
        result = Query('INSERT INTO %s(ruleset, name, list, position, definition, '
                'points, doubles, limits, parameter)'
                ' VALUES(?,?,?,?,?,?,?,?,?)' % self.__ruleTable(),
                self.ruleRecords()).success
        if result:
            Query.dbhandle.commit()
            self.dirty = False
        else:
            Query.dbhandle.rollback()
        return result

    @staticmethod
    def availableRulesetNames():
        """returns all ruleset names defined in the database"""
        return list(x[0] for x in Query("SELECT name FROM ruleset").records)

    @staticmethod
    def availableRulesets():
        """returns all rulesets defined in the database plus all predefined rulesets"""
        return [Ruleset(x) for x in Ruleset.availableRulesetNames()] + PredefinedRuleset.rulesets()

    @staticmethod
    def selectableRulesets(server=None):
        """returns all selectable rulesets for a new game.
        server is used to find the last ruleset used by us on that server, this
        ruleset will returned first in the list."""
        result = Ruleset.availableRulesets()
        # if we have a selectable ruleset with the same name as the last used ruleset
        # put that ruleset in front of the list. We do not want to use the exact same last used
        # ruleset because we might have made some fixes to the ruleset meanwhile
        if server is None: # scoring game
            # the exists clause is only needed for inconsistent data bases
            qData = Query("select ruleset from game where seed is null "
                " and exists(select id from usedruleset where game.ruleset=usedruleset.id)"
                "order by starttime desc limit 1").records
        else:
            qData = Query('select lastruleset from server where lastruleset is not null and url=?',
                list([server])).records
            if not qData:
                # we never played on that server
                qData = Query('select lastruleset from server where lastruleset is not null '
                    'order by lasttime desc limit 1').records
        if qData:
            qData = Query("select name from usedruleset where id=%d" % qData[0][0]).records
            if qData:
                lastUsed = qData[0][0]
                for idx, ruleset in enumerate(result):
                    if ruleset.name == lastUsed:
                        del result[idx]
                        return [ruleset ] + result
        return result

    def diff(self, other):
        """return a list of tuples. Every tuple holds one or two rules: tuple[0] is from self, tuple[1] is from other"""
        result = []
        leftDict = dict((x.name, x) for x in self.allRules)
        rightDict = dict((x.name, x) for x in other.allRules)
        left = set(leftDict.keys())
        right = set(rightDict.keys())
        for rule in left & right:
            leftRule, rightRule = leftDict[rule], rightDict[rule]
            if str(leftRule) != str(rightRule):
                result.append((leftRule, rightRule))
        for rule in left - right:
            result.append((leftDict[rule], None))
        for rule in right - left:
            result.append((None, rightDict[rule]))
        return result

class HandContent(object):
    """represent the hand to be evaluated"""

    # pylint: disable=R0902
    # pylint we need more than 10 instance attributes

    cache = dict()
    hits = 0
    misses = 0

    @staticmethod
    def clearCache():
        """clears the cache with HandContents"""
        #logDebug('cache hits:%d misses:%d' % (HandContent.hits, HandContent.misses))
        HandContent.cache.clear()
        HandContent.hits = 0
        HandContent.misses = 0

    @staticmethod
    def cached(ruleset, string, computedRules=None, robbedTile=None):
        """since a HandContent instance is never changed, we can use a cache"""
        cRuleHash = '&&'.join([rule.name for rule in computedRules]) if computedRules else 'None'
        cacheKey = hash((string, robbedTile, cRuleHash))
        cache = HandContent.cache
        if cacheKey in cache:
            HandContent.hits += 1
            return cache[cacheKey]
        HandContent.misses += 1
        result = HandContent(ruleset, string,
            computedRules=computedRules, robbedTile=robbedTile)
        cache[cacheKey] = result
        return result

    def __init__(self, ruleset, string, computedRules=None, robbedTile=None):
        """evaluate string using ruleset. rules are to be applied in any case."""
        # silence pylint. This method is time critical, so do not split it into smaller methods
        # pylint: disable=R0902,R0914,R0912,R0915
        self.ruleset = ruleset
        self.string = string
        self.robbedTile = robbedTile
        self.computedRules = computedRules or []
        self.won = False
        self.mayWin = True
        self.ownWind = None
        self.roundWind = None
        tileStrings = []
        mjStrings = []
        haveM = haveL = False
        splits = self.string.split()
        for part in splits:
            partId = part[0]
            if partId in 'Mmx':
                haveM = True
                self.ownWind = part[1]
                self.roundWind = part[2]
                mjStrings.append(part)
                self.won = partId == 'M'
                self.mayWin = partId != 'x'
            elif partId == 'L':
                haveL = True
                if len(part[1:]) > 8:
                    raise Exception('last tile cannot complete a kang:' + self.string)
                mjStrings.append(part)
            else:
                tileStrings.append(part)

        if not haveM:
            raise Exception('HandContent got string without mMx: %s', self.string)
        if not haveL:
            mjStrings.append('Lxx')
        self.tiles = ' '.join(tileStrings)
        self.mjStr = ' '.join(mjStrings)
        self.lastMeld = self.lastTile = self.lastSource = None
        self.announcements = ''
        self.hiddenMelds = []
        self.declaredMelds = []
        self.melds = set()
        self.sortedMelds = []
        self.fsMelds = set()
        self.invalidMelds = set()
        self.__separateMelds()
        self.tileNames = []
        self.dragonMelds = [x for x in self.melds if x.pairs[0][0] in 'dD']
        self.windMelds = [x for x in self.melds if x.pairs[0][0] in 'wW']
        for meld in self.melds:
            self.tileNames.extend(meld.pairs)
        self.hiddenMelds = sorted(self.hiddenMelds, key=meldKey)
        self.__setLastMeldAndTile()
        self.usedRules = [] # a list of tuples: each tuple holds the rule and None or a meld
        if self.invalidMelds:
            raise Exception('has invalid melds: ' + ','.join(meld.joined for meld in self.invalidMelds))

        for meld in self.melds:
            meld.score = Score()
        self.applyMeldRules()
        self.sortedMeldsContent = meldsContent(self.sortedMelds)
        if self.fsMelds:
            self.sortedMeldsContent += ' ' + meldsContent(sorted(list(self.fsMelds), key=meldKey))
        self.fsMeldNames = [x.pairs[0] for x in self.fsMelds]
        self.won = self.won and self.maybeMahjongg()
        ruleTuples = [(rule, None) for rule in self.computedRules]
        for rules in [ruleTuples, self.usedRules]:
            # explicitly passed rules have precedence
            exclusive = self.__exclusiveRules(rules)
            if exclusive: # if a meld rule is exclusive: like if east said 9 times MJ
                self.usedRules = exclusive
                self.score = self.__totalScore(exclusive)
                return
        score, rules, self.won = self.__score()
        exclusive = self.__exclusiveRules(rules)
        if exclusive:
            self.usedRules = exclusive
            self.score = self.__totalScore(exclusive)
        else:
            self.usedRules.extend(rules)
            self.score = score

    def isLimitHand(self):
        """are we?"""
        return any(x for x in self.usedRules if x[0].score.limits >= 1.0)

    def __setLastMeldAndTile(self):
        """returns Meld and Tile or None for both"""
        parts = self.mjStr.split()
        for part in parts:
            if part[0] == 'L':
                part = part[1:]
                if len(part) > 2:
                    self.lastMeld = Meld(part[2:])
                self.lastTile = part[:2]
            elif part[0] == 'M':
                if len(part) > 3:
                    self.lastSource = part[3]
                    if len(part) > 4:
                        self.announcements = part[4:]
        if self.lastTile and not self.lastMeld:
            self.lastMeld = self.computeLastMeld(self.lastTile)

    def __sub__(self, tiles):
        """returns a copy of self minus tiles. Case of tiles (hidden
        or exposed) is ignored. If the tile is not hidden
        but found in an exposed meld, this meld will be hidden with
        the tile removed from it. Exposed melds of length<3 will also
        be hidden."""
        # pylint: disable=R0912
        # pylint says too many branches
        if not isinstance(tiles, list):
            tiles = list([tiles])
        hidden = meldsContent(self.hiddenMelds)
        # exposed is a deep copy of declaredMelds. If lastMeld is given, it
        # must be first in the list.
        exposed = (Meld(x) for x in self.declaredMelds)
        if self.lastMeld:
            exposed = sorted(exposed, key=lambda x: (x.pairs != self.lastMeld.pairs, meldKey(x)))
        else:
            exposed = sorted(exposed, key=meldKey)
        for tile in tiles:
            assert isinstance(tile, str) and len(tile) == 2, 'HandContent.__sub__:%s' % tiles
            if tile.capitalize() in hidden:
                hidden = hidden.replace(tile.capitalize(), '', 1)
            else:
                for idx, meld in enumerate(exposed):
                    if tile.lower() in meld.pairs:
                        del meld.pairs[meld.pairs.index(tile.lower())]
                        del exposed[idx]
                        meld.conceal()
                        hidden += ' ' + meld.joined
                        break
        for idx, meld in enumerate(exposed):
            if len(meld.pairs) < 3:
                del exposed[idx]
                meld.conceal()
                hidden += ' ' + meld.joined
        mjStr = self.mjStr
        if self.lastTile in tiles:
            parts = mjStr.split()
            for idx, part in enumerate(parts):
                if part[0] == 'L':
                    parts[idx] = 'Lxx'
                if part[0] == 'M':
                    parts[idx] = 'm' + part[1:]
            mjStr = ' '.join(parts)
        newString = ' '.join([hidden, meldsContent(exposed), mjStr])
        return HandContent.cached(self.ruleset, newString, self.computedRules)

    def ruleMayApply(self, rule):
        """returns True if rule applies to this hand"""
        return rule.appliesToHand(self)

    def manualRuleMayApply(self, rule):
        """returns True if rule has selectable() and applies to this hand"""
        return rule.selectable(self) or self.ruleMayApply(rule) # needed for activated rules

    def handLenOffset(self):
        """return <0 for short hand, 0 for correct calling hand, >0 for long hand
        if there are no kongs, 13 tiles will return 0"""
        tileCount = sum(len(meld) for meld in self.melds)
        kongCount = self.countMelds(Meld.isKong)
        return tileCount - kongCount - 13

    def __candidatesForCallingHand(self):
        """returns a list of concealed tilenames which might complete this hand.
        Note the *might* - further checking is needed."""
# TODO: can we really exclude any tile or should we just test all rules for
# all tiles? Idea: If there is any dragon, test all dragons. Same for winds.
        result = []
        if self.handLenOffset():
            return []
        # here we assume things about the possible structure of a
        # winner hand. Recheck this when supporting new exotic hands.
        if len(self.melds) > 7:
            # only possibility is 13 orphans
            if any(x in self.tiles.lower() for x in '2345678'):
                # no minors allowed
                return []
            tiles = sum((x.pairs for x in self.sortedMelds), [])
            missing = elements.majors - set(x.lower() for x in tiles)
            if len(missing) == 0:
                # if all 13 tiles are there, we need any one of them:
                result = list(elements.majors)
            elif len(missing) == 1:
                result = list(missing)
        elif False: # if we have each wind just once, no dragon and one suit:
            pass # then test for wriggling snake
        else:
            # no other legal winner hand allows singles that are not adjacent
            # to any other tile, so we only try tiles on the hand and for the
            # suit tiles also adjacent tiles
            hiddenTiles = sum((x.pairs for x in self.hiddenMelds), [])
            result = set(x.lower() for x in hiddenTiles)
            for tile in (x.lower() for x in hiddenTiles if x[0] in 'SBC'):
                if tile[1] > '1':
                    result.add(chiNext(tile, -1))
                if tile[1] < '9':
                    result.add(chiNext(tile, 1))
            result = list(result)
        return sorted(x.capitalize() for x in result) # sort only for reproducibility

    def callingHands(self, wanted=1, doNotCheck=None):
        """the hand is calling if it only needs one tile for mah jongg.
        Returns up to 'wanted' hands which would only need one tile.
        Does NOT check if they are really available by looking at what
        has already been discarded!
        """
        tiles = self.__candidatesForCallingHand()
        result = []
        string = self.string
        if ' x' in string:
            # may not say Mahjongg
            return []
        for tileName in tiles:
            if doNotCheck and tileName == doNotCheck.capitalize():
                continue
            thisOne = HandContent.addTile(string, tileName)
            thisOne = thisOne.replace(' m', ' M')
            hand = HandContent.cached(self.ruleset, thisOne)
            if hand.maybeMahjongg():
                result.append(hand)
                if len(result) == wanted:
                    break
        return result

    def maybeMahjongg(self):
        """check if this hand can be a regular mah jongg."""
        if not self.mayWin:
            return False
        if self.handLenOffset() != 1:
            return False
        matchingMJRules = [x for x in self.ruleset.mjRules if self.ruleMayApply(x)]
        if self.robbedTile and self.robbedTile.lower() != self.robbedTile:
            # Millington 58: robbing hidden kong is only allowed for 13 orphans
            matchingMJRules = [x for x in matchingMJRules if 'mayrobhiddenkong' in x.actions]
        if not matchingMJRules:
            return False
        if self.ruleset.minMJPoints == 0:
            return True
        if self.won:
            checkHand = self
        else:
            checkHand = HandContent.cached(self.ruleset, self.string.replace(' m', ' M'),
                self.computedRules)
        return checkHand.total() >= self.ruleset.minMJTotal

    def computeLastMeld(self, lastTile):
        """returns the best last meld for lastTile"""
        if lastTile == 'xx':
            return
        if lastTile[0].isupper():
            checkMelds = self.hiddenMelds
        else:
            checkMelds = self.declaredMelds
        checkMelds = [x for x in checkMelds if len(x) < 4] # exclude kongs
        lastMelds = [x for x in checkMelds if lastTile in x.pairs]
        if not lastMelds:
            # lastTile was Xy or already discarded again
            self.lastTile = 'xx'
            return
        if len(lastMelds) > 1:
            for meld in lastMelds:
                if meld.isPair():       # completing pairs gives more points.
                    return meld
            for meld in lastMelds:
                if meld.isChow():       # if both chow and pung wins the game, call
                    return meld         # chow because hidden pung gives more points
        return lastMelds[0]             # default: the first possible last meld

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
        color = original[0][0]
        original = [x[1] for x in original]
        def recurse(cVariants, foundMelds, rest):
            """build the variants recursively"""
            values = set(rest)
            melds = []
            for value in values:
                intValue = int(value)
                if rest.count(value) == 3:
                    melds.append([value] * 3)
                if rest.count(value) == 2:
                    melds.append([value] * 2)
                if rest.count(str(intValue + 1)) and rest.count(str(intValue + 2)):
                    melds.append([value, str(intValue+1), str(intValue+2)])
            pairsFound = sum(len(x) == 2 for x in foundMelds)
            for meld in melds:
                if len(meld) == 2 and pairsFound >= maxPairs:
                    continue
                restCopy = rest[:]
                for value in meld:
                    restCopy.remove(value)
                newMelds = foundMelds[:]
                newMelds.append(meld)
                if restCopy:
                    recurse(cVariants, newMelds, restCopy)
                else:
                    for idx, newMeld in enumerate(newMelds):
                        newMelds[idx] = ''.join(color+x for x in newMeld)
                    cVariants.append(' '.join(sorted(newMelds )))
        cVariants = []
        recurse(cVariants, [], original)
        gVariants = []
        for cVariant in set(cVariants):
            melds = [Meld(x) for x in cVariant.split()]
            gVariants.append(set(melds))
        return gVariants

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
                            + ' ' + self.mjStr,
                            computedRules=self.computedRules)
                        if not bestHand:
                            bestHand = hand
                            bestVariant = splitVariant
                        else:
                            if hand.total() > bestHand.total():
                                bestHand = hand
                                bestVariant = splitVariant
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

    def matchingRules(self, rules):
        """return all matching rules for this hand"""
        return list(rule for rule in rules if rule.appliesToHand(self))

    def applyMeldRules(self):
        """apply all rules for single melds"""
        for rule in self.ruleset.meldRules:
            for meld in self.melds:
                if rule.appliesToMeld(self, meld):
                    self.usedRules.append((rule, meld))
                    meld.score += rule.score

    @staticmethod
    def __totalScore(rules):
        """use all used rules to compute the score"""
        return sum([x[0].score for x in rules]) if rules else Score()

    def total(self):
        """total points of hand"""
        return self.score.total()

    def __separateMelds(self):
        """build a meld list from the hand string"""
        # no matter how the tiles are grouped make a single
        # meld for every bonus tile
        boni = []
        if 'f' in self.tiles or 'y' in self.tiles: # optimize
            # we need to remove spaces from the hand string first
            # for building only pairs with length 2
            for pair in Pairs(self.tiles.replace(' ', '')):
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
            if (split[0].islower() or split[0] in 'mM') \
                or meld.meldType != REST:
                self.melds.add(meld)
            else:
                rest.append(split)
        if rest:
            rest = ''.join(rest)
            rest = ''.join(sorted([rest[x:x+2] for x in range(0, len(rest), 2)]))
            self.melds |= self.split(rest)
        self.sortedMelds = sorted(self.melds, key=meldKey)
        self.__categorizeMelds()

    @staticmethod
    def addTile(string, tileName):
        """string is the encoded hand. Add tileName in the right place
        and return the new string. Use this only for a hand getting
        a claimed or discarded tile."""
        if not tileName:
            return string
        parts = string.split()
        lPart = mPart = None
        candidates = []
        for idx, part in enumerate(parts):
            if part[0] in 'SBCDW':
                candidates.append(idx)
            elif part[0] == 'L':
                lPart = idx
            elif part[0].lower() == 'm':
                mPart = idx
        assert candidates, 'we have no concealed tiles in %s' % string
        # combine all parts about hidden tiles plus the new one to one part
        # because something like DrDrS8S9 plus S7 will have to be reordered
        # anyway
        parts[candidates[0]] = ''.join(parts[x] for x in candidates)
        parts[candidates[0]] += tileName
        if lPart:
            parts[lPart] = 'L%s' % tileName
        else:
            parts.append('L%s' % tileName)
        if mPart:
            parts[mPart] = parts[mPart].capitalize()
        for others in candidates[1:]:
            parts[others] = ''
        return ' '.join(parts)

    def __categorizeMelds(self):
        """categorize: boni, hidden, declared, invalid"""
        for meld in self.sortedMelds:
            if not meld.isValid():
                self.invalidMelds.add(meld)
            elif meld.tileType() in 'fy':
                self.fsMelds.add(meld)
            elif meld.state == CONCEALED and not meld.isKong():
                self.hiddenMelds.append(meld)
            else:
                self.declaredMelds.append(meld)
        self.melds -= self.fsMelds
        self.sortedMelds = sorted(list(self.melds), key=meldKey)

    def __score(self):
        """returns a tuple with the score of the hand, the used rules and the won flag."""
        # pylint: disable=W0613
        usedRules = list([(rule, None) for rule in self.matchingRules(
            self.ruleset.handRules + self.computedRules)])
        won = self.won
        if won and self.__totalScore(self.usedRules + usedRules).total() < self.ruleset.minMJPoints:
            won = False
        if won:
            for rule in self.matchingRules(self.ruleset.winnerRules + self.ruleset.mjRules):
                usedRules.append((rule, None))
        return (self.__totalScore(self.usedRules + usedRules), usedRules, won)

    @staticmethod
    def __exclusiveRules(rules):
        """returns a list of applicable rules which exclude all others"""
        return list(x for x in rules if 'absolute' in x[0].actions) \
            or list(x for x in rules if x[0].score.limits>=1.0)

    def explain(self):
        """explain what rules were used for this hand"""
        result = [x[0].explain() for x in self.usedRules]
        if any(x[0].debug for x in self.usedRules):
            result.append(str(self))
        return result

    def __str__(self):
        """hand as a string"""
        return u' '.join([self.sortedMeldsContent, self.mjStr])

class Rule(object):
    """a mahjongg rule with a name, matching variants, and resulting score.
    The rule applies if at least one of the variants matches the hand.
    For parameter rules, only use name, definition,parameter. definition must start with int or str
    which is there for loading&saving, but internally is stripped off."""
    # pylint: disable=R0913,R0902
    # pylint we need more than 10 instance attributes

    functions = {}

    def __init__(self, name, definition='', points = 0, doubles = 0, limits = 0, parameter = None,
            description=None, debug=False):
        self.actions = {}
        self.functionClass = None
        self.name = name
        self.description = description
        self.score = Score(points, doubles, limits)
        self._definition = None
        self.parName = ''
        self.parameter = ''
        self.debug = debug
        self.parType = None
        for parType in [int, unicode, bool]:
            typeName = parType.__name__
            if typeName == 'unicode':
                typeName = 'str'
            if definition.startswith(typeName):
                self.parType = parType
                if parType is bool and type(parameter) in (str, unicode):
                    parameter = parameter != 'False'
                self.parameter = parType(parameter)
                definition = definition[len(typeName):]
                break
        self.definition = definition

    @apply
    def definition(): # pylint: disable=E0202
        """the rule definition. See user manual about ruleset."""
        # pylint: disable=R0912
        def fget(self):
            # pylint: disable=W0212
            if isinstance(self._definition, list):
                return '||'.join(self._definition)
            return self._definition
        def fset(self, definition):
            """setter for definition"""
            assert not isinstance(definition, QString)
            prevDefinition = self.definition
            self._definition = definition
            if not definition:
                return # may happen with special programmed rules
            variants = definition.split('||')
            if self.parType:
                self.parName = variants[0]
                variants = variants[1:]
            self.actions = {}
            self.functionClass = None
            for idx, variant in enumerate(variants):
                if isinstance(variant, (str, unicode)):
                    variant = str(variant)
                    if variant[0] == 'F':
                        assert idx == 0
                        self.functionClass = Rule.functions[variant[1:]]()
                    elif variant[0] == 'A':
                        for action in variant[1:].split():
                            aParts = action.split('=')
                            if len(aParts) == 1:
                                aParts.append('None')
                            self.actions[aParts[0]] = aParts[1]
                    elif variant == 'XEAST9X':
                        pass
                    else:
                        # TODO: Query.upgradedatabase should make sure
                        # this cannot happen
                        pass
#                        logDebug('%s is not implemented in %s' % (variant[0], variant))
            self.validate(prevDefinition)
        return property(**locals())

    def validate(self, prevDefinition):
        """check for validity. If wrong, restore prevDefinition."""
        payers = int(self.actions.get('payers', 1))
        payees = int(self.actions.get('payees', 1))
        if not 2 <= payers + payees <= 4:
            self.definition = prevDefinition
            logException(m18nc('%1 can be a sentence', '%4 have impossible values %2/%3 in rule "%1"',
                                  self.name, payers, payees, 'payers/payees'))

    def appliesToHand(self, hand):
        """does the rule apply to this hand?"""
        if self.functionClass is None:
            return False
        return self.functionClass.appliesToHand(hand)

    def hasSelectable(self):
        """do we have a variant with selectable?"""
        return hasattr(self.functionClass, 'selectable')

    def selectable(self, hand):
        """does the rule apply to this hand?"""
        return self.hasSelectable() and self.functionClass.selectable(hand)

    def appliesToMeld(self, hand, meld):
        """does the rule apply to this meld?"""
        return self.functionClass.appliesToMeld(hand, meld)

    def explain(self):
        """use this rule for scoring"""
        result = [m18n(self.name) + ':']
        if self.score.points:
            result.append(m18nc('kajongg', '%1 base points', self.score.points))
        if self.score.doubles:
            result.append(m18nc('kajongg', '%1 doubles', self.score.doubles))
        if self.score.limits:
            result.append(m18nc('kajongg', '%1 limits', self.score.limits))
        return ' '.join(result)

    def hashStr(self):
        """all that is needed to hash this rule. Try not to change this to keep
        database congestion low"""
        return '%s: %s %s %s' % (self.name, self.parameter, self.definition, self.score)

    def __str__(self):
        return self.hashStr()

    def __repr__(self):
        return self.hashStr()

    def contentStr(self):
        """returns a human readable string with the content: score or option value"""
        if self.parType:
            return str(self.parameter)
        else:
            return self.score.contentStr()

    def copy(self):
        """returns a deep copy of self"""
        return Rule(self.name, self.definition, self.score.points, self.score.doubles,
            self.score.limits, self.parameter, self.description)

    @staticmethod
    def exclusive():
        """True if this rule can only apply to one player"""
        return False

    def hasNonValueAction(self):
        """Rule has a special action not changing the score directly"""
        return bool(any(x not in ['lastsource', 'declaration'] for x in self.actions))

class Function(object):
    """Parent for all Function classes. We need to implement
    those methods as in Regex:
    appliesToHand and appliesToMeld"""
    def __init__(self):
        self.timeSum = 0.0
        self.count = 0
        self.definition = ''

    @staticmethod
    def appliesToMeld(dummyHand, dummyMeld):
        """we normally do not use this one"""
        return False

class FunctionDragonPungKong(Function):
    """x"""
    @staticmethod
    def appliesToMeld(hand, meld):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return len(meld) >= 3 and meld in hand.dragonMelds

class FunctionRoundWindPungKong(Function):
    """x"""
    @staticmethod
    def appliesToMeld(hand, meld):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return len(meld) >= 3 and meld.pairs[0].lower() == 'w' + hand.roundWind

class FunctionExposedMinorPung(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return meld.isPung() and meld.pairs.isLower(0, 3) and meld.pairs[0][1] in '2345678'

class FunctionExposedTerminalsPung(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return meld.isPung() and meld.pairs.isLower(0, 3) and meld.pairs[0][1] in '19'

class FunctionExposedHonorsPung(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return meld.isPung() and meld.pairs[0][0] in 'wd'

class FunctionExposedMinorKong(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return len(meld) == 4 and meld.pairs.isLower(0, 3) and meld.pairs[0][1] in '2345678'

class FunctionExposedTerminalsKong(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return len(meld) == 4 and meld.pairs.isLower(0, 3) and meld.pairs[0][1] in '19'

class FunctionExposedHonorsKong(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return len(meld) == 4 and meld.pairs.isLower(0, 3) and meld.pairs[0][0] in 'wd'

class FunctionConcealedMinorPung(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return meld.isPung() and meld.pairs.isUpper(0, 3) and meld.pairs[0][1] in '2345678'

class FunctionConcealedTerminalsPung(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return meld.isPung() and meld.pairs.isUpper(0, 3) and meld.pairs[0][1] in '19'

class FunctionConcealedHonorsPung(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return meld.isPung() and meld.pairs[0][0] in 'WD'

class FunctionConcealedMinorKong(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return len(meld) == 4 and meld.state == CONCEALED and meld.pairs[0][1] in '2345678'

class FunctionConcealedTerminalsKong(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return len(meld) == 4 and meld.state == CONCEALED and meld.pairs[0][1] in '19'

class FunctionConcealedHonorsKong(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return len(meld) == 4 and meld.state == CONCEALED and meld.pairs[0][0] in 'wd'

class FunctionOwnWindPungKong(Function):
    """x"""
    @staticmethod
    def appliesToMeld(hand, meld):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return len(meld) >= 3 and meld.pairs[0].lower() == 'w' + hand.ownWind

class FunctionOwnWindPair(Function):
    """x"""
    @staticmethod
    def appliesToMeld(hand, meld):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return len(meld) == 2 and meld.pairs[0].lower() == 'w' + hand.ownWind

class FunctionRoundWindPair(Function):
    """x"""
    @staticmethod
    def appliesToMeld(hand, meld):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return len(meld) == 2 and meld.pairs[0].lower() == 'w' + hand.roundWind

class FunctionDragonPair(Function):
    """x"""
    @staticmethod
    def appliesToMeld(dummyHand, meld):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return len(meld) == 2 and meld.pairs[0][0].lower() == 'd'

class FunctionLastTileCompletesPairMinor(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return (hand.lastMeld and len(hand.lastMeld) == 2
            and hand.lastMeld.pairs[0][0] == hand.lastMeld.pairs[1][0]
            and hand.lastTile and hand.lastTile[1] in '2345678')

class FunctionFlower1(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return 'fe' in hand.fsMeldNames

class FunctionFlower2(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return 'fs' in hand.fsMeldNames

class FunctionFlower3(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return 'fw' in hand.fsMeldNames

class FunctionFlower4(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return 'fn' in hand.fsMeldNames

class FunctionSeason1(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return 'ye' in hand.fsMeldNames

class FunctionSeason2(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return 'ys' in hand.fsMeldNames

class FunctionSeason3(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return 'yw' in hand.fsMeldNames

class FunctionSeason4(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return 'yn' in hand.fsMeldNames

class FunctionLastTileCompletesPairMajor(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return (hand.lastMeld and len(hand.lastMeld) == 2
            and hand.lastMeld.pairs[0][0] == hand.lastMeld.pairs[1][0]
            and hand.lastTile and hand.lastTile[1] not in '2345678')

class FunctionLastFromWall(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return hand.lastTile and hand.lastTile[0].isupper()

class FunctionZeroPointHand(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return sum(x.score.points for x in hand.melds) == 0

class FunctionNoChow(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return not any(x.isChow() for x in hand.melds)

class FunctionOnlyConcealedMelds(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return not any((x.state == EXPOSED and x.meldType != CLAIMEDKONG) for x in hand.melds)

class FunctionFalseColorGame(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        suits = set(x[0].lower() for x in hand.tileNames)
        dwSet = set('dw')
        return dwSet & suits and len(suits - dwSet) == 1

class FunctionTrueColorGame(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        suits = set(x[0].lower() for x in hand.tileNames)
        return len(suits) == 1 and suits < set('sbc')

class FunctionConcealedTrueColorGame(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        suits = set(x[0].lower() for x in hand.tileNames)
        if len(suits) != 1 or not (suits < set('sbc')):
            return False
        return not any((x.state == EXPOSED and x.meldType != CLAIMEDKONG) for x in hand.melds)

class FunctionOnlyMajors(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        values = set(x[1] for x in hand.tileNames)
        return not values - set('grbeswn19')

class FunctionOnlyHonors(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        values = set(x[1] for x in hand.tileNames)
        return not values - set('grbeswn')

class FunctionHiddenTreasure(Function):
    """x"""
    # TODO: BMJA calls this Buried Treasure and does not require
    # the last tile to come from the wall. Parametrize.
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return (not any(((x.state == EXPOSED and x.meldType != CLAIMEDKONG) or x.isChow()) for x in hand.melds)
            and hand.lastTile and hand.lastTile[0].isupper()
            and len(hand.melds) == 5)

class FunctionAllTerminals(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        values = set(x[1] for x in hand.tileNames)
        return not values - set('19')

class FunctionSquirmingSnake(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        suits = set(x[0].lower() for x in hand.tileNames)
        if len(suits) != 1 or not suits < set('sbc'):
            return False
        values = ''.join(x[1] for x in hand.tileNames)
        if values.count('1') < 3 or values.count('9') < 3:
            return False
        pairs = [x for x in '258' if values.count(x) == 2]
        if len(pairs) != 1:
            return False
        return len(set(values)) == len(values) - 5

class FunctionWrigglingSnake(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        suits = set(x[0].lower() for x in hand.tileNames)
        if 'w' not in suits:
            return False
        suits -= set('w')
        if len(suits) != 1 or not suits < set('sbc'):
            return False
        values = ''.join(x[1] for x in hand.tileNames)
        if values.count('1') != 2:
            return False
        return len(set(values)) == 13

class FunctionTripleKnitting(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        if hand.windMelds or hand.dragonMelds:
            return False
        if len(hand.declaredMelds) > 1:
            return False
        tileNames = [x.lower() for x in hand.tileNames]
        suitCounts = sorted([len([x for x in tileNames if x[0] == y]) for y in 'sbc'])
        if suitCounts != [4, 5, 5]:
            return False
        values = list(x[1] for x in tileNames)
        return all(values.count(x) % 3 != 1 for x in set(values))

class FunctionKnitting(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        if hand.windMelds or hand.dragonMelds:
            return False
        if len(hand.declaredMelds) > 1:
            return False
        tileNames = [x.lower() for x in hand.tileNames]
        suitCounts = sorted([len([x for x in tileNames if x[0] == y]) for y in 'sbc'])
        if suitCounts != [0, 7, 7]:
            return False
        values = list(x[1] for x in tileNames)
        return all(values.count(x) % 2 == 0 for x in set(values))

class FunctionAllPairHonors(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        if any(x[1] in '2345678' for x in hand.tileNames):
            return False
        if len(hand.declaredMelds) > 1:
            return False
        values = list(x[1] for x in hand.tileNames)
        if len(set(values)) != 7:
            return False
        valueCounts = sorted([len([x for x in hand.tileNames if x[1] == y]) for y in set(values)])
        return set(valueCounts) == set([2])

class FunctionFourfoldPlenty(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return len(hand.tileNames) == 18

class FunctionThreeGreatScholars(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return (FunctionStandardMahJongg.appliesToHand(hand)
            and FunctionBigThreeDragons.appliesToHand(hand))

class FunctionBigThreeDragons(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return len([x for x in hand.dragonMelds if len(x) >= 3]) == 3

class FunctionBigFourJoys(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return len([x for x in hand.windMelds if len(x) >= 3]) == 4

class FunctionLittleFourJoys(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return (len([x for x in hand.windMelds if len(x) >= 3]) == 3
            and len([x for x in hand.windMelds if len(x) == 2]) == 1)

class FunctionLittleThreeDragons(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return (len([x for x in hand.dragonMelds if len(x) >= 3]) == 2
            and len([x for x in hand.dragonMelds if len(x) == 2]) == 1)

class FunctionFourBlessingsHoveringOverTheDoor(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return len([x for x in hand.melds if len(x) >= 3 and x.pairs[0][0] in 'wW']) == 4

class FunctionAllGreen(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        tiles = set(x.lower() for x in hand.tileNames)
        return hand.won and tiles < set(['b2', 'b3', 'b4', 'b5', 'b6', 'b8', 'dg'])

class FunctionLastTileFromWall(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return hand.won and hand.lastSource == 'w'

class FunctionLastTileFromDeadWall(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return hand.won and hand.lastSource == 'e'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return hand.lastSource == 'w'

class FunctionIsLastTileFromWall(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return hand.won and hand.lastSource == 'z'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return hand.won and hand.lastSource == 'w'

class FunctionIsLastTileFromWallDiscarded(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return hand.won and hand.lastSource == 'Z'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return hand.lastSource == 'd'

class FunctionRobbingKong(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return hand.won and hand.lastSource == 'k'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return (hand.lastSource and hand.lastSource in 'kwd'
            and hand.lastTile and hand.lastTile[0].islower()
            and [x.lower() for x in hand.tileNames].count(hand.lastTile.lower()) < 2)

class FunctionGatheringPlumBlossomFromRoof(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        if not hand.won:
            return False
        if FunctionLastTileFromDeadWall.appliesToHand(hand):
            return hand.lastTile and hand.lastTile == 'S5'
        return False

class FunctionPluckingMoon(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return hand.won and hand.lastSource == 'z' and hand.lastTile and hand.lastTile == 'S1'

class FunctionScratchingPole(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return hand.won and hand.lastSource and hand.lastSource == 'k' and hand.lastTile and hand.lastTile == 'b2'

class FunctionStandardMahJongg(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return (len(hand.melds) == 5
            and set(len(x) for x in hand.melds) <= set([2,3,4])
            and not any(x.meldType == REST for x in hand.melds)
            and hand.ruleset.maxChows >= len([x for x in hand.melds if x.isChow()]))

class FunctionNineGates(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return FunctionGatesOfHeaven.appliesToHand(hand, lastCompletesPair=True)

class FunctionGatesOfHeaven(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand, lastCompletesPair=False):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        suits = set(x[0].lower() for x in hand.tileNames)
        if len(suits) != 1 or not suits < set('sbc') or not hand.won or not hand.lastTile:
            return False
        values = ''.join(x[1] for x in hand.tileNames)
        if values.count('1') < 3 or values.count('9') < 3:
            return False
        values = values.replace('111','').replace('999','')
        for value in '2345678':
            values = values.replace(value, '', 1)
        if len(values) != 1:
            return False
        # the last tile must complete the pair
        return not lastCompletesPair or values == hand.lastTile[1]

class FunctionThirteenOrphans(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return set(x.lower() for x in hand.tileNames) == elements.majors

class FunctionOwnFlower(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        fsPairs = list(x.pairs[0] for x in hand.fsMelds)
        return 'f' + hand.ownWind in fsPairs

class FunctionOwnSeason(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        fsPairs = list(x.pairs[0] for x in hand.fsMelds)
        return 'y' + hand.ownWind in fsPairs

class FunctionOwnFlowerOwnSeason(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        return (FunctionOwnFlower.appliesToHand(hand)
            and FunctionOwnSeason.appliesToHand(hand))

class FunctionAllFlowers(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return len([x for x in hand.fsMelds if x.pairs[0][0] == 'f']) == 4

class FunctionAllSeasons(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return len([x for x in hand.fsMelds if x.pairs[0][0] == 'y']) == 4

class FunctionThreeConcealedPongs(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return len([x for x in hand.melds if (
            x.state == CONCEALED or x.meldType == CLAIMEDKONG) and (x.isPung() or x.isKong())]) >= 3

class FunctionMahJonggWithOriginalCall(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return (hand.won and 'a' in hand.announcements
            and len([x for x in hand.melds if x.state == EXPOSED]) < 3)

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        # one may be claimed before declaring OC and one for going MJ
        # the previous regex was too strict
        exp = [x for x in hand.melds if x.state == EXPOSED]
        return hand.won and len(exp) < 3

class FunctionTwofoldFortune(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return hand.won and 't' in hand.announcements

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        kungs = [x for x in hand.melds if len(x) == 4]
        return hand.won and len(kungs) >= 2

class FunctionBlessingOfHeaven(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return hand.won and hand.ownWind == 'e' and hand.lastSource == '1'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return (hand.won and hand.ownWind == 'e'
            and hand.lastSource and hand.lastSource in 'wd'
            and not (set(hand.announcements) - set('a')))

class FunctionBlessingOfEarth(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return hand.won and hand.ownWind != 'e' and hand.lastSource == '1'

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return (hand.won and hand.ownWind != 'e'
            and hand.lastSource and hand.lastSource in 'wd'
            and not (set(hand.announcements) - set('a')))

class FunctionLongHand(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        offset = hand.handLenOffset()
        return (not hand.won and offset > 0) or offset > 1

class FunctionDangerousGame(Function):
    """x"""
    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        return not hand.won

    @staticmethod
    def selectable(hand):
        """for scoring game"""
        return not hand.won

class FunctionLastOnlyPossible(Function):
    """check if the last tile was the only one possible for winning"""

    active = False

    @staticmethod
    def appliesToHand(hand):
        """see class docstring"""
        # pylint: disable=R0911
        # pylint: disable=R0912
        if FunctionLastOnlyPossible.active:
            return False
        if hand.lastMeld is None:
            # no last meld specified: This can happen in a scoring game
            # know if saying Mah Jongg is possible
            return False
        if hand.isLimitHand():
            # a limit hand, this rule does not matter anyway
            return False
        if hand.lastMeld.isPung():
            return False # we had two pairs...
        group, value = hand.lastTile
        group = group.lower()
        if group not in 'sbc':
            return True
        intValue = int(value)
        if hand.lastMeld.isChow():
            if hand.lastTile != hand.lastMeld.pairs[1]:
                # left or right tile of a chow:
                if not ((value == '3' and hand.lastMeld.pairs[0][1] == '1')
                        or (value == '7' and hand.lastMeld.pairs[2][1] == '9')):
                    return False
            # now the quick and easy tests are done. For more complex
            # hands we have to do a full test. Note: Always only doing
            # the full test really slows us down by a factor of 2
            shortHand = hand - hand.lastTile
            FunctionLastOnlyPossible.active = True
            try:
                otherCallingHands = shortHand.callingHands(doNotCheck=hand.lastTile)
            finally:
                FunctionLastOnlyPossible.active = False
            return len(otherCallingHands) == 0
        else:
            if not hand.lastMeld.isPair():
                # special hand like triple knitting
                return False
            for meld in hand.hiddenMelds:
                # look at other hidden melds of same color:
                if meld != hand.lastMeld and meld.pairs[0][0].lower() == group:
                    if meld.isChow():
                        if intValue in [int(meld.pairs[0][1]) - 1, int(meld.pairs[2][1]) + 1]:
                            # pair and adjacent Chow
                            return False
                    elif meld.isPung():
                        if abs(intValue - int(meld.pairs[0][1])) <= 2:
                            # pair and nearby Pung
                            return False
                    elif meld.isSingle():
                        # must be 13 orphans
                        return False
        return True

class Splitter(object):
    """a regex with a name for splitting concealed and yet unsplitted tiles into melds"""
    def __init__(self, name, definition, size):
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

class PredefinedRuleset(Ruleset):
    """special code for loading rules from program code instead of from the database"""

    classes = set()  # only those will be playable

    def __init__(self, name=None):
        Ruleset.__init__(self, name or 'general predefined ruleset')

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
    sc1 = Score(points=10, limitPoints=500)
    assert sc1
    sc2 = Score(limits=1, limitPoints=500)
    assert sc2
    scsum = sc1 + sc2
    assert int(sc1) == 10
    assert int(sc2) == 500
    assert isinstance(scsum, Score)
    assert int(scsum) == 500, scsum
    sc3 = Score(points=20, doubles=2, limitPoints=500)
    assert int(sum([sc1, sc3])) == 120, sum([sc1, sc3])

    meld1 = Meld('c1c1c1C1')
    pair1 = meld1.pairs
    pair2 = pair1.lower()
    assert pair1 != pair2
    pair1.toLower(3)
    assert pair1 == pair2
    null = Score()
    assert not null

def __scanSelf():
    """for every Function class defined in this module,
    generate an instance and add it to dict Rule.functions"""
    if not Rule.functions:
        for glob in globals().values():
            if hasattr(glob, "__mro__"):
                if glob.__mro__[-2] == Function and len(glob.__mro__) > 2:
                    name = glob.__name__.replace('Function', '')
                    Rule.functions[name] = glob

__scanSelf()

if __name__ == "__main__":
    testScoring()
