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

import re # the new regex is about 7% faster
from hashlib import md5 # pylint: disable=E0611

from PyQt4.QtCore import QString

from util import m18n, m18nc, english, logException
from query import Query
from meld import Meld, Score

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

    def pop(self, name):
        """find rule, return it, delete it from this list"""
        result = self.__getitem__(name)
        self.__delitem__(name)
        return result

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
        return m18n(self.name) + ': ' + self.score.contentStr()

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
