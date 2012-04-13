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

from util import m18n, m18nc, english, logException, logDebug
from query import Query
from meld import Meld, meldKey, Score, meldsContent, Pairs, CONCEALED
from common import Debug

import rulecode

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
        self.penaltyRules = RuleList(9999, m18n('Penalties'), m18n(
            """Penalties are applied manually by the user. They are only used for scoring games.
When playing against the computer or over the net, Kajongg will never let you get
into a situation where you have to pay a penalty"""))
        self.ruleLists = list([self.meldRules, self.handRules, self.mjRules, self.winnerRules,
            self.parameterRules, self.penaltyRules])
        # the order of ruleLists is the order in which the lists appear in the ruleset editor
        # if you ever want to remove an entry from ruleLists: make sure its listId is not reused or you get
        # in trouble when updating
        self.initRuleset()

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

    def minMJTotal(self):
        """the minimum score for Mah Jongg including all winner points. This is not accurate,
        the correct number is bigger in CC: 22 and not 20. But it is enough saveguard against
        entering impossible scores for manual games.
        We only use this for scoring games."""
        return self.minMJPoints + min(x.score.total() for x in self.mjRules)

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
        rulesWithAction = list(x for x in self.allRules if action in x.options)
        assert len(rulesWithAction) < 2, '%s has too many matching rules for %s' % (str(self), action)
        if rulesWithAction:
            return rulesWithAction[0]

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
        if Debug.handCache:
            logDebug('cache size:%d hits:%d misses:%d' % (len(HandContent.cache), HandContent.hits, HandContent.misses))
        HandContent.cache.clear()
        HandContent.hits = 0
        HandContent.misses = 0

    @staticmethod
    def cached(ruleset, string, computedRules=None, robbedTile=None):
        """since a HandContent instance is never changed, we can use a cache"""
        cRuleHash = '&&'.join([rule.name for rule in computedRules]) if computedRules else 'None'
        cacheKey = hash((id(ruleset), string, robbedTile, cRuleHash))
        cache = HandContent.cache
        if cacheKey in cache:
            if cache[cacheKey] is None:
                raise Exception('recursion: HandContent calls itself for same content')
            HandContent.hits += 1
            return cache[cacheKey]
        HandContent.misses += 1
        cache[cacheKey] = None
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
        if string.count('R') > 1:
            raise Exception('string has more than on R part:%s'%string)
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
        self.melds = []
        self.fsMelds = []
        self.invalidMelds = []
        self.__separateMelds()
        self.tileNames = []
        self.dragonMelds = [x for x in self.melds if x.pairs[0][0] in 'dD']
        self.windMelds = [x for x in self.melds if x.pairs[0][0] in 'wW']
        for meld in self.melds:
            self.tileNames.extend(meld.pairs)
        self.hiddenMelds = sorted(self.hiddenMelds, key=meldKey)
        self.suits = set(x[0].lower() for x in self.tileNames)
        self.values = ''.join(x[1] for x in self.tileNames)
        self.__setLastMeldAndTile()
        assert self.lastTile == 'xx' or self.lastTile in self.tileNames, 'lastTile %s is not in tiles %s' % (
            self.lastTile, ' '.join(self.tileNames))
        if self.lastTile != 'xx' and self.lastSource == 'k':
            assert self.tileNames.count(self.lastTile.lower()) + \
                self.tileNames.count(self.lastTile.capitalize()) == 1, \
                'Robbing kong: I cannot have lastTile %s more than once in %s' % (
                    self.lastTile, ' '.join(self.tileNames))

        self.usedRules = [] # a list of tuples: each tuple holds the rule and None or a meld
        if self.invalidMelds:
            raise Exception('has invalid melds: ' + ','.join(meld.joined for meld in self.invalidMelds))

        for meld in self.melds:
            meld.score = Score()
        self.applyMeldRules()
        self.sortedMeldsContent = meldsContent(self.melds)
        if self.fsMelds:
            self.sortedMeldsContent += ' ' + meldsContent(self.fsMelds)
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
        hidden = 'R' + ''.join(x.joined for x in self.hiddenMelds)
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
                        hidden += meld.joined
                        break
        for idx, meld in enumerate(exposed):
            if len(meld.pairs) < 3:
                del exposed[idx]
                meld.conceal()
                hidden += meld.joined
        mjStr = self.mjStr
        if self.lastTile in tiles:
            parts = mjStr.split()
            for idx, part in enumerate(parts):
                if part[0] == 'L':
                    parts[idx] = 'Lxx'
                if part[0] == 'M':
                    parts[idx] = 'm' + part[1:]
                    if len(part) > 3 and part[3] == 'k':
                        parts[idx] = parts[idx][:3]
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

    def callingHands(self, wanted=1, excludeTile=None):
        """the hand is calling if it only needs one tile for mah jongg.
        Returns up to 'wanted' hands which would only need one tile.
        Does NOT check if they are really available by looking at what
        has already been discarded!
        """
        result = []
        string = self.string
        if ' x' in string or self.handLenOffset():
            return result
        for rule in self.ruleset.mjRules:
            # sort only for reproducibility
            if not hasattr(rule, 'winningTileCandidates'):
                raise Exception('rule %s, code=%s has no winningTileCandidates' % (
                    rule.name, rule.function))
            candidates = sorted(x.capitalize() for x in rule.winningTileCandidates(self))
            for tileName in candidates:
                if excludeTile and tileName == excludeTile.capitalize():
                    continue
                thisOne = self.addTile(string, tileName).replace(' m', ' M')
                hand = HandContent.cached(self.ruleset, thisOne)
                if hand.maybeMahjongg():
                    result.append(hand)
                    if len(result) == wanted:
                        break
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
            matchingMJRules = [x for x in matchingMJRules if 'mayrobhiddenkong' in x.options]
        if not matchingMJRules:
            return False
        if self.ruleset.minMJPoints == 0:
            return True
        if self.won:
            checkHand = self
        else:
            checkHand = HandContent.cached(self.ruleset, self.string.replace(' m', ' M'),
                self.computedRules)
        return checkHand.total() >= self.ruleset.minMJTotal()

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

    def genVariants(self, original0, maxPairs=1):
        """generates all possible meld variants out of original
        where original is a list of tile values like ['1','1','2']"""
        color = original0[0][0]
        original = [x[1] for x in original0]
        def recurse(cVariants, foundMelds, rest):
            """build the variants recursively"""
            values = set(rest)
            melds = []
            for value in values:
                intValue = int(value)
                if rest.count(value) == 3:
                    melds.append([value] * 3)
                elif rest.count(value) == 2:
                    melds.append([value] * 2)
                if rest.count(str(intValue + 1)) and rest.count(str(intValue + 2)):
                    melds.append([value, str(intValue+1), str(intValue+2)])
            pairsFound = sum(len(x) == 2 for x in foundMelds)
            for meld in (m for m in melds if len(m) !=2 or pairsFound < maxPairs):
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
            gVariants.append(melds)
        if not gVariants:
            gVariants.append(self.splitRegex(''.join(original0))) # fallback: nothing useful found
        return gVariants

    def split(self, rest):
        """work hard to always return the variant with the highest Mah Jongg value."""
        pairs = Meld(rest).pairs
        if 'Xy' in pairs:
            # hidden tiles of other players:
            return self.splitRegex(rest)
        _ = [pair for pair in pairs if pair[0] in 'DWdw']
        honourResult = self.splitRegex(''.join(_)) # easy since they cannot have a chow
        splitVariants = {}
        for color in 'SBC':
            colorPairs = [pair for pair in pairs if pair[0] == color]
            if not colorPairs:
                splitVariants[color] = [None]
                continue
            splitVariants[color] = self.genVariants(colorPairs)
        bestHand = None
        bestVariant = None
        for combination in ((s, b, c)
                for s in splitVariants['S']
                for b in splitVariants['B']
                for c in splitVariants['C']):
            variantMelds = honourResult[:] + sum((x for x in combination if x is not None), [])
            melds = self.melds[:] + variantMelds
            melds.extend(self.fsMelds)
            _ = ' '.join(x.joined for x in melds) + ' ' + self.mjStr
            hand = HandContent.cached(self.ruleset, _,
                computedRules=self.computedRules)
            if not bestHand or hand.total() > bestHand.total():
                bestHand = hand
                bestVariant = variantMelds
        return bestVariant

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
        return sum([x[0].score for x in rules], Score()) if rules else Score()

    def total(self):
        """total points of hand"""
        return self.score.total()

    def __separateMelds(self):
        """build a meld list from the hand string"""
        # no matter how the tiles are grouped make a single
        # meld for every bonus tile
        boni = []
        # we need to remove spaces from the hand string first
        # for building only pairs with length 2
        for pair in Pairs(self.tiles.replace(' ', '').replace('R', '')):
            if pair[0] in 'fy':
                boni.append(pair)
                self.tiles = self.tiles.replace(pair, '', 1)
        splits = self.tiles.split()
        splits.extend(boni)
        rest = ''
        for split in splits:
            if split[0] == 'R':
                rest = split[1:]
            else:
                self.melds.append(Meld(split))
        if rest:
            rest = ''.join(sorted([rest[x:x+2] for x in range(0, len(rest), 2)]))
            self.melds.extend(self.split(rest))
        self.melds = sorted(self.melds, key=meldKey)
        self.__categorizeMelds()

    @staticmethod
    def addTile(string, tileName):
        """string is the encoded hand. Add tileName in the right place
        and return the new string. Use this only for a hand getting
        a claimed or discarded tile."""
        if not tileName:
            return string
        parts = string.split()
        mPart = ''
        rPart = 'R%s' % tileName
        unchanged = []
        for part in parts:
            if part[0] in 'SBCDW':
                rPart += part
            elif part[0] == 'R':
                rPart += part[1:]
            elif part[0].lower() == 'm':
                mPart = part
            elif part[0] == 'L':
                pass
            else:
                unchanged.append(part)
        # combine all parts about hidden tiles plus the new one to one part
        # because something like DrDrS8S9 plus S7 will have to be reordered
        # anyway
        parts = unchanged
        parts.append(rPart)
        parts.append('L%s' % tileName)
        parts.append(mPart.capitalize())
        return ' '.join(parts)

    def __categorizeMelds(self):
        """categorize: boni, hidden, declared, invalid"""
        self.fsMelds = []
        self.invalidMelds = []
        self.hiddenMelds = []
        self.declaredMelds = []
        for meld in self.melds:
            if not meld.isValid():
                self.invalidMelds.append(meld)
            elif meld.tileType() in 'fy':
                self.fsMelds.append(meld)
            elif meld.state == CONCEALED and not meld.isKong():
                self.hiddenMelds.append(meld)
            else:
                self.declaredMelds.append(meld)
        for meld in self.fsMelds:
            self.melds.remove(meld)

    def __score(self):
        """returns a tuple with the score of the hand, the used rules and the won flag."""
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
        return list(x for x in rules if 'absolute' in x[0].options) \
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

    def __init__(self, name, definition='', points = 0, doubles = 0, limits = 0, parameter = None,
            description=None, debug=False):
        self.options = {}
        self.function = None
        self.hasSelectable = False
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
            self.options = {}
            self.function = None
            self.hasSelectable = False
            for idx, variant in enumerate(variants):
                if isinstance(variant, (str, unicode)):
                    variant = str(variant)
                    if variant[0] == 'F':
                        assert idx == 0
                        self.function = rulecode.Function.functions[variant[1:]]()
                        # when executing code for this rule, we do not want
                        # to call those things indirectly
                        if hasattr(self.function, 'appliesToHand'):
                            self.appliesToHand = self.function.appliesToHand
                        if hasattr(self.function, 'appliesToMeld'):
                            self.appliesToMeld = self.function.appliesToMeld
                        if hasattr(self.function, 'selectable'):
                            self.hasSelectable = True
                            self.selectable = self.function.selectable
                        if hasattr(self.function, 'winningTileCandidates'):
                            self.winningTileCandidates = self.function.winningTileCandidates
                    elif variant[0] == 'O':
                        for action in variant[1:].split():
                            aParts = action.split('=')
                            if len(aParts) == 1:
                                aParts.append('None')
                            self.options[aParts[0]] = aParts[1]
                    elif variant == 'XEAST9X':
                        pass
                    else:
                        # TODO: Query.upgradedatabase should make sure
                        # this cannot happen
                        pass
#                        logDebug('%s is not implemented in %s' % (variant[0], variant))
            if self.function:
                self.function.options = self.options
            self.validate(prevDefinition)
        return property(**locals())

    def validate(self, prevDefinition):
        """check for validity. If wrong, restore prevDefinition."""
        payers = int(self.options.get('payers', 1))
        payees = int(self.options.get('payees', 1))
        if not 2 <= payers + payees <= 4:
            self.definition = prevDefinition
            logException(m18nc('%1 can be a sentence', '%4 have impossible values %2/%3 in rule "%1"',
                                  self.name, payers, payees, 'payers/payees'))

    def appliesToHand(self, dummyHand): # pylint: disable=R0201
        """does the rule apply to this hand?"""
        return False

    def selectable(self, dummyHand): # pylint: disable=R0201
        """does the rule apply to this hand?"""
        return False

    def appliesToMeld(self, dummyHand, dummyMeld): # pylint: disable=R0201
        """does the rule apply to this meld?"""
        return False

    def winningTileCandidates(self, dummyHand): # pylint: disable=R0201
        """those might be candidates for a calling hand"""
        return set()

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
        return bool(any(x not in ['lastsource', 'declaration'] for x in self.options))

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

if __name__ == "__main__":
    testScoring()
