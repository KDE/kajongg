# -*- coding: utf-8 -*-

"""Copyright (C) 2009-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

Read the user manual for a description of the interface to this scoring engine
"""

import types
from hashlib import md5
from typing import Any, List, Tuple, Dict, Type, Union, Optional, TYPE_CHECKING
from typing import Sequence, Set
import sqlite3

from common import Internal, Debug
from common import ReprMixin
from log import logException, logDebug
from mi18n import i18n, i18nc, i18nE, i18ncE, english
from query import Query

if TYPE_CHECKING:
    from tile import Meld
    from rulecode import MJRule
    from hand import Hand
    from login import Url


class Score(ReprMixin):

    """holds all parts contributing to a score. It has two use cases:
    1. for defining what a rules does: either points or doubles or limits, holding never more than one unit
    2. for summing up the scores of all rules: Now more than one of the units can be in use. If a rule
    should want to set more than one unit, split it into two rules.
    For the first use case only we have the attributes value and unit"""

    __hash__ = None  # type: ignore

    def __init__(self, points:int=0, doubles:int=0, limits:float=0, ruleset:Optional['Ruleset']=None):
        self.points:int = 0  # define the types for those values
        self.doubles:int = 0
        self.limits:float = 0.0
        self.ruleset:Optional['Ruleset'] = ruleset
        self.points = type(self.points)(points)
        self.doubles = type(self.doubles)(doubles)
        self.limits = type(self.limits)(limits)

    unitNames = {i18nE(
        'points'): 0,
                 i18ncE('kajongg', 'doubles'): 50,
                 i18ncE('kajongg', 'limits'): 9999}

    def clear(self) ->None:
        """set all to 0"""
        self.points = self.doubles = self.limits = 0

    def change(self, unitName:str, value:Union[int, float]) ->Tuple[bool, Optional[str]]:
        """set value for unitName. If changed, return True"""
        oldValue = getattr(self, unitName)
        try:
            newValue = type(oldValue)(value)
        except ValueError:
            return False, f'{value} is not of type {type(oldValue)}'
        if newValue == oldValue:
            return False, None
        if newValue:
            if unitName == 'points':
                if self.doubles:
                    return False, 'Cannot have points and doubles'
            if unitName == 'doubles':
                if self.points:
                    return False, 'Cannot have points and doubles'
        setattr(self, unitName, newValue)
        return True, None

    def __str__(self) ->str:
        """make score printable"""
        parts = []
        if self.points:
            parts.append(f'points={int(self.points)}')
        if self.doubles:
            parts.append(f'doubles={int(self.doubles)}')
        if self.limits:
            parts.append(f'limits={self.limits:f}')
        return ' '.join(parts)

    def i18nStr(self) ->str:
        """make score readable for humans, i18n"""
        parts = []
        if self.points:
            parts.append(i18nc('Kajongg', '%1 points', self.points))
        if self.doubles:
            parts.append(i18nc('Kajongg', '%1 doubles', self.doubles))
        if self.limits:
            limits = str(self.limits)
            if limits.endswith('.0'):
                limits = limits[-2:]
            parts.append(i18nc('Kajongg', '%1 limits', limits))
        return ' '.join(parts)

    def __eq__(self, other:Any) ->bool:
        """ == comparison """
        assert isinstance(other, Score)
        return self.points == other.points and self.doubles == other.doubles and self.limits == other.limits

    def __ne__(self, other:Any) ->bool:
        """ != comparison """
        assert isinstance(other, Score)
        return self.points != other.points or self.doubles != other.doubles or self.limits != other.limits

    def __lt__(self, other:Any) ->bool:
        assert isinstance(other, Score)
        return self.total() < other.total()

    def __le__(self, other:Any) ->bool:
        assert isinstance(other, Score)
        return self.total() <= other.total()

    def __gt__(self, other:Any) ->bool:
        assert isinstance(other, Score)
        return self.total() > other.total()

    def __ge__(self, other:Any) ->bool:
        assert isinstance(other, Score)
        return self.total() >= other.total()

    def __add__(self, other:Any) ->'Score':
        """implement adding Score"""
        assert isinstance(other, Score)
        return Score(self.points + other.points, self.doubles + other.doubles,
                     max(self.limits, other.limits), self.ruleset or other.ruleset)

    def total(self) ->int:
        """the total score"""
        result = int(self.points * (2 ** self.doubles))
        if self.limits:
            assert self.ruleset is not None
            if self.limits >= 1:
                self.points = self.doubles = 0
            elif self.limits * self.ruleset.limit >= result:
                self.points = self.doubles = 0
            else:
                self.limits = 0.0
        if self.limits:
            assert self.ruleset is not None
            return int(round(self.limits * self.ruleset.limit))
        if result and self.ruleset:
            if not self.ruleset.roofOff:
                result = int(min(result, self.ruleset.limit))
        return result

    def __int__(self) ->int:
        """the total score"""
        return self.total()

    def __bool__(self) ->bool:
        """for bool() conversion"""
        return self.points != 0 or self.doubles != 0 or self.limits != 0


class RuleList(list):

    """a list with a name and a description (to be used as hint).
    Rules can be indexed by name or index.
    Adding a rule either replaces an existing rule or appends it."""

    def __init__(self, listId:int, name:str, description:str) ->None:
        list.__init__(self)
        self.listId = listId
        self.name:str = name
        self.description = description

    def pop(self, key:str) ->'RuleBase':  # type:ignore
        """find rule, return it, delete it from this list"""
        result = self[key]
        del self[key]
        return result  # type:ignore

    def __contains__(self, key:Any) ->bool:
        """do we know this rule?"""
        if isinstance(key, RuleBase):
            key = key.key()
        return any(x.key() == key for x in self)

#    @overload
#    def __getitem__(self, index: Union[SupportsIndex, str]) -> 'RuleBase': ...
#    @overload
#    def __getitem__(self, index: slice) -> Sequence['RuleBase']: ...
# see https://github.com/python/mypy/issues/10955

    def __getitem__(self, key:Union[int, str]) ->'RuleBase':  # type:ignore[override]
        """find rule by key"""
        if isinstance(key, int):
            return list.__getitem__(self, key)
        for rule in self:
            if rule.key() == key:
                return rule
        raise KeyError

    def __setitem__(self, key:str, rule:'RuleBase') ->None:  # type:ignore
        """set rule by key"""
        if isinstance(key, int):
            list.__setitem__(self, key, rule)
            return
        for idx, oldRule in enumerate(self):
            if oldRule.key() == key:
                list.__setitem__(self, idx, rule)
                return
        list.append(self, rule)

    def __delitem__(self, key:Union[int, str]) ->None:  # type:ignore
        """delete this rule"""
        if isinstance(key, int):
            list.__delitem__(self, key)
            return
        for idx, rule in enumerate(self):
            if rule.key() == key:
                list.__delitem__(self, idx)
                return
        raise KeyError

    def append(self, rule:'RuleBase') ->None:
        """do not append"""
        raise TypeError(f'do not append {rule}')

    def add(self, rule:'RuleBase') ->None:
        """use add instead of append"""
        if rule.key() in self:
            logException(f'{rule.key()} is already defined as {self[rule.key()].definition}, '
                         f'not accepting new rule {rule.name}/{rule.definition}')  # type:ignore
        self[rule.key()] = rule

    def createRule(self, name:str, definition:str='', **kwargs:Any) ->None:
        """shortcut for simpler definition of predefined rulesets"""
        defParts = definition.split('||')
        rule = None
        description = kwargs.get('description', '')
        cls:Type[ParameterRule]
        for cls in [IntRule, BoolRule, StrRule]:
            if defParts[0].startswith(cls.prefix):
                rule = cls(
                    name,
                    definition,
                    description=description,
                    parameter=kwargs['parameter'])
                break
        if not rule:
            if 'parameter' in kwargs:
                del kwargs['parameter']
            ruleType = type(ruleKey(name) + 'Rule', (Rule, ), {})
            rule = ruleType(name, definition, **kwargs)
            assert isinstance(rule, Rule)  # hint for mypy
            if defParts[0] == 'FCallingHand':
                parts1 = defParts[1].split('=')
                assert parts1[0] == 'Ohand', definition
                ruleClassName = parts1[1] + 'Rule'
                if ruleClassName not in RuleBase.ruleClasses:
                    logDebug(
                        f'we want {ruleClassName}, definition:{definition}')
                    logDebug(f'we have {RuleBase.ruleClasses.keys()}')
                ruleType.limitHand = RuleBase.ruleClasses[ruleClassName]
        self.add(rule)


class UsedRule(ReprMixin):

    """use this in scoring, never change class Rule.
    If the rule has been used for a meld, pass it"""

    def __init__(self, rule:'Rule', meld:Optional['Meld']=None) ->None:
        self.rule = rule
        self.meld = meld

    def __str__(self) ->str:
        result = self.rule.name
        if self.meld:
            result += ' ' + str(self.meld)
        return result


class Ruleset:

    """holds a full set of rules: meldRules,handRules,winnerRules.

        predefined rulesets are preinstalled together with Kajongg. They can be customized by the user:
        He can copy them and modify the copies in any way. If a game uses a specific ruleset, it
        checks the used rulesets for an identical ruleset and refers to that one, or it generates
        a new used ruleset.

        The user can select any predefined or customized ruleset for a new game, but she can
        only modify customized rulesets.

        For fast comparison for equality of two rulesets, each ruleset has a hash built from
        all of its rules. This excludes the splitting rules, IOW exactly the rules saved in the table
        rule will be used for computation.

        Rulesets which are templates for new games have negative ids: The ruleset editor only reads
        and writes rulesets with negative id.
        Rulesets attached to a game have positive ids.
        This can lead to a situation where the same ruleset is twice in the table:
        1. clear database
        2. play ruleset X which saves it with id=1
        3. in the ruleset editor, copy X which saves it with id=-1 and name='Copy of X'

        The name is not unique. Different remote players might save different rulesets
        under the same name.
    """
    # pylint: disable=too-many-instance-attributes

    __hash__ = None  # type: ignore

    cache : Dict[Union[int, str], 'Ruleset'] = {}
    hits = 0
    misses = 0

    @staticmethod
    def cached(name:Union[int, str]) ->'Ruleset':
        """If a Ruleset instance is never changed, we can use a cache"""
        if isinstance(name, list):
            # we got the rules over the wire
            _, wiredHash, _, _ = name[0]
        else:
            wiredHash = None
        for predefined in PredefinedRuleset.rulesets():
            if predefined.hash in (name, wiredHash):
                return predefined
        cache = Ruleset.cache
        if not isinstance(name, list) and name in cache:
            return cache[name]
        result = Ruleset(name)
        cache[result.rulesetId] = result
        cache[result.hash] = result
        return result

    def __init__(self, raw_data:Union[int, List[str], str]) ->None:
        """raw_data may be:
            - an integer: ruleset.id from the sql table
            - a list: the full ruleset specification (probably sent from the server)
            - a string: The hash value of a ruleset"""
        Rule.importRulecode()
        self.raw_data = raw_data
        self.name:str
        self.rulesetId:int = 0
        self.__hash:str = ''
        self.allRules:List[Rule] = []
        self.__dirty = False  # only the ruleset editor is supposed to make us dirty
        self.__loaded = False
        self.__filteredLists:Dict[str, List[RuleBase]] = {}
        self.description = ''
        self.rawRules:Optional[List[List[str]]] = None  # used when we get the rules over the network
        self.doublingMeldRules:List[Rule] = []
        self.doublingHandRules:List[Rule] = []
        self.standardMJRule:Optional['Rule'] = None
        self.limit:int
        self.roofOff:bool
        self.mustDeclareCallingHand:bool
        self.minMJPoints:int
        self.minRounds:int
        self.withBonusTiles:bool
        self.claimTimeout:int
        self.maxChows:int
        self.minMJDoubles:int
        self.discardTilesOrdered:bool
        self.discardTilesOrderedLeaveHole:bool
        self.meldRules = RuleList(1, i18n('Meld Rules'),
                                  i18n('Meld rules are applied to single melds independent of the rest of the hand'))
        self.handRules = RuleList(2, i18n('Hand Rules'),
                                  i18n('Hand rules are applied to the entire hand, for all players'))
        self.winnerRules = RuleList(3, i18n('Winner Rules'),
                                    i18n('Winner rules are applied to the entire hand but only for the winner'))
        self.loserRules = RuleList(33, i18n('Loser Rules'),
                                   i18n('Loser rules are applied to the entire hand but only for non-winners'))
        self.mjRules = RuleList(4, i18n('Mah Jongg Rules'),
                                i18n('Only hands matching a Mah Jongg rule can win'))
        self.parameterRules = RuleList(999, i18nc('kajongg', 'Options'),
                                       i18n('Here we have several special game related options'))
        self.penaltyRules = RuleList(9999, i18n('Penalties'), i18n(
            """Penalties are applied manually by the user. They are only used for scoring games.
When playing against the computer or over the net, Kajongg will never let you get
into a situation where you have to pay a penalty"""))
        self.ruleLists = list(
            [self.meldRules, self.handRules, self.mjRules, self.winnerRules,
             self.loserRules, self.parameterRules, self.penaltyRules])
        # the order of ruleLists is the order in which the lists appear in the ruleset editor
        # if you ever want to remove an entry from ruleLists: make sure its listId is not reused or you get
        # in trouble when updating
        self._initRuleset()
        assert self.name

    @property
    def dirty(self) ->bool:
        """have we been modified since load or last save?"""
        return self.__dirty

    @dirty.setter
    def dirty(self, dirty:bool) ->None:
        """have we been modified since load or last save?"""
        self.__dirty = dirty
        if dirty:
            self.__computeHash()

    @property
    def hash(self) ->str:
        """a md5sum computed from the rules but not name and description"""
        if not self.__hash:
            self.__computeHash()
        return self.__hash

    def __eq__(self, other:Any) ->bool:
        """two rulesets are equal if everything except name or description is identical.
        The name might be localized."""
        return other and isinstance(other, Ruleset) and self.hash == other.hash

    def __ne__(self, other:Any) ->bool:
        """two rulesets are equal if everything except name or description is identical.
        The name might be localized."""
        return not other or not isinstance(other, Ruleset) or self.hash != other.hash

    def minMJTotal(self) ->int:
        """the minimum score for Mah Jongg including all winner points. This is not accurate,
        the correct number is bigger in CC: 22 and not 20. But it is enough saveguard against
        entering impossible scores for manual games.
        We only use this for scoring games."""
        return self.minMJPoints + min(x.score.total() for x in self.mjRules)

    @staticmethod
    def hashIsKnown(value:str) ->bool:
        """return False or True"""
        result = any(x.hash == value for x in PredefinedRuleset.rulesets())
        if not result:
            query = Query("select id from ruleset where hash=?", (value,))
            result = bool(query.records)
        return result

    def _initRuleset(self) ->None:
        """load ruleset headers but not the rules"""
        if isinstance(self.raw_data, int):
            query = Query(
                "select id,hash,name,description from ruleset where id=?", (self.raw_data,))
        elif isinstance(self.raw_data, list):
            # we got the rules over the wire
            self.rawRules = self.raw_data[1:]  # type:ignore
            (self.rulesetId, self.__hash, self.name,
             self.description) = self.raw_data[0]  # type:ignore
            self.load()
                      # load raw rules at once, rules from db only when needed
            return
        else:
            query = Query("select id,hash,name,description from ruleset where hash=?", (self.raw_data,))
        if query.records:
            (self.rulesetId, self.__hash, self.name,
             self.description) = query.records[0]
        else:
            raise ValueError(f'ruleset {self.raw_data} not found')

    def __setParametersFrom(self, fromRuleset:'Ruleset') ->None:
        """set attributes for parameters defined in fromRuleset.
        Does NOT overwrite already set parameters: Silently ignore them"""
        for par in fromRuleset.parameterRules:
            if isinstance(par, ParameterRule):
                if par.parName not in self.__dict__:
                    self.__dict__[par.parName] = par.parameter

    def load(self) ->'Ruleset':
        """load the ruleset from the database and compute the hash. Return self."""
        if self.__loaded:
            return self
        self.__loaded = True
        self.loadRules()
        self.__setParametersFrom(self)
        for ruleList in self.ruleLists:
            assert len(ruleList) == len({x.key()
                                         for x in ruleList}), f'{ruleList.name} has non-unique key'
            for rule in ruleList:
                if hasattr(rule, 'score'):
                    rule.score.ruleset = self
                self.allRules.append(rule)
        if self.rulesetId:  # a saved ruleset, do not do this for predefined rulesets
            # we might have introduced new parameter rules which do not exist in this ruleset saved with the game,
            # so add missing parameters from the predefined ruleset most
            # similar to this one
            self.__setParametersFrom(
                sorted(PredefinedRuleset.rulesets(),
                       key=lambda x: len(self.diff(x)))[0])
        self.doublingMeldRules = [x for x in self.meldRules if x.score.doubles]
        self.doublingHandRules = [x for x in self.handRules if x.score.doubles]
        for mjRule in self.mjRules:
            if mjRule.__class__.__name__ == 'StandardMahJonggRule':
                self.standardMJRule = mjRule
                break
        assert self.standardMJRule
        return self

    def __loadQuery(self) ->Query:
        """return a Query object with loaded ruleset"""
        return Query(
            "select ruleset, list, position, name, definition, points, doubles, limits, parameter from rule "
            "where ruleset=? order by list,position", (self.rulesetId,))

    def toList(self) -> List[List[Union[str, int, float]]]:
        """return entire ruleset in a list"""
        self.load()
        result:List[List[Union[str, int, float]]] = [[self.rulesetId, self.hash, self.name, self.description]]
        result.extend(self.ruleRecord(x) for x in self.allRules)
        return result

    def loadRules(self) ->None:
        """load rules from database or from self.rawRules (got over the net)"""
        if self.rawRules:
            for record in self.rawRules:
                self.__loadRule(record)
        else:
            for record in self.__loadQuery().records:
                self.__loadRule(record)

    def __loadRule(self, record:List[str]) ->None:
        """loads a rule into the correct ruleList"""
        _, listNr, _, name, definition, points_str, doubles, limits, parameter = record
        try:
            points = int(points_str)
        except ValueError:
            # this happens if the unit changed from limits to points but the value
            # is not converted at the same time
            points = int(float(points_str))
        for ruleList in self.ruleLists:
            if ruleList.listId == listNr:
                ruleList.createRule(
                    name, definition, points=points, doubles=int(doubles), limits=float(limits),
                    parameter=parameter)
                break

    def findUniqueOption(self, action:str) ->Optional['Rule']:
        """return first rule with option"""
        rulesWithAction = [x for x in self.allRules if action in x.options]
        assert len(rulesWithAction) < 2, f'{str(self)} has too many matching rules for {action}'
        if rulesWithAction:
            return rulesWithAction[0]
        return None

    def filterRules(self, attrName:str) ->List['RuleBase']:
        """return all my Rule classes having attribute attrName"""
        if attrName not in self.__filteredLists:
            self.__filteredLists[attrName] = [x for x in self.allRules if hasattr(x, attrName)]
        return self.__filteredLists[attrName]

    @staticmethod
    def newId(minus:bool=False) ->int:
        """return an unused ruleset id. This is not multi user safe."""
        func = 'min(id)-1' if minus else 'max(id)+1'
        result = -1 if minus else 1
        records = Query(f"select {func} from ruleset").records
        if records and records[0] and records[0][0]:
            try:
                result = int(records[0][0])
            except ValueError:
                pass
        return result

    @staticmethod
    def nameExists(name:str) ->bool:
        """return True if ruleset name is already in use"""
        result = any(x.name == name for x in PredefinedRuleset.rulesets())
        if not result:
            result = bool(
                Query('select id from ruleset where id<0 and name=?', (name,)).records)
        return result

    def _newKey(self, minus:bool=False) ->Tuple[int, str]:
        """generate a new id and a new name if the name already exists"""
        newId = self.newId(minus=minus)
        newName = str(self.name)
        if minus:
            copyNr = 1
            while self.nameExists(newName):
                copyStr = ' ' + str(copyNr) if copyNr > 1 else ''
                newName = i18nc(
                    'Ruleset._newKey:%1 is empty or space plus number',
                    'Copy%1 of %2', copyStr, i18n(str(self.name)))
                copyNr += 1
        return newId, newName

    def clone(self) ->'Ruleset':
        """return a clone of self, unloaded"""
        return Ruleset(self.rulesetId)

    def __str__(self) ->str:
        return f'type={type(self)}, id={int(id(self))},rulesetId={int(self.rulesetId)},name={self.name}'

    def copyTemplate(self) ->'Ruleset':
        """make a copy of self and return the new ruleset id. Returns the new ruleset.
        To be used only for ruleset templates"""
        newRuleset = self.clone().load()
        newRuleset.save(minus=True, forced=True)
        if isinstance(newRuleset, PredefinedRuleset):
            newRuleset = Ruleset(newRuleset.rulesetId)
        return newRuleset

    def rename(self, newName:str) ->bool:
        """renames the ruleset. returns True if done, False if not"""
        with Internal.db:
            if self.nameExists(newName):
                return False
            try:
                Query("update ruleset set name=? where id<0 and name=?", (newName, self.name))
                self.name = newName
                return True
            except sqlite3.Error:
                return False

    def remove(self) ->None:
        """remove this ruleset from the database."""
        with Internal.db:
            Query("DELETE FROM rule WHERE ruleset=?", (self.rulesetId,))
            Query("DELETE FROM ruleset WHERE id=?", (self.rulesetId,))

    def __computeHash(self) ->None:
        """compute the hash for this ruleset using all rules but not name and
        description of the ruleset"""
        self.load()
        result = md5()
        for rule in sorted(self.allRules, key=Rule.__str__):
            result.update(rule.hashStr().encode('utf-8'))
        self.__hash = result.hexdigest()

    def ruleRecord(self, rule:'RuleBase') ->List[Union[str, int, float]]:
        """return the rule as a list, prepared for use by sql. The first three
        fields are the primary key."""
        score = rule.score
        ruleList = None
        for ruleList in self.ruleLists:
            if rule in ruleList:
                ruleIdx = ruleList.index(rule)
                break
        assert rule in ruleList, f'{type(rule)}: {rule} not in list {ruleList.name}'
        return [self.rulesetId, ruleList.listId, ruleIdx, rule.name,
                rule.definition, score.points, score.doubles, score.limits, rule.parameter] # type:ignore

    def updateRule(self, rule:'RuleBase') ->None:
        """update rule in database"""
        self.__hash = ''  # invalidate, will be recomputed when needed
        with Internal.db:
            record = self.ruleRecord(rule)
            Query("UPDATE rule SET name=?, definition=?, points=?, doubles=?, limits=?, parameter=? "
                  "WHERE ruleset=? AND list=? AND position=?",
                  tuple(record[3:] + record[:3]))
            Query(
                "UPDATE ruleset SET hash=? WHERE id=?",
                (self.hash,
                 self.rulesetId))

    def save(self, minus:bool=False, forced:bool=False) ->None:
        """save the ruleset to the database.
        If it does not yet exist in database, give it a new id
        If the name already exists in the database, also give it a new name
        If the hash already exists in the database, only save if forced=True"""
        if not forced:
            if minus:
                # if we save a template, only check for existing templates. Otherwise this could happen:
                # clear kajongg.db, play game with DMJL, start ruleset editor, copy DMJL.
                # since play Game saved the used ruleset with id 1, id 1 is found here and no new
                # template is generated. Next the ruleset editor shows the original ruleset in italics
                # and the copy with normal font but identical name, and the
                # copy is never saved.
                qData = Query(
                    "select id from ruleset where hash=? and id<0", (self.hash,)).records
            else:
                qData = Query(
                    "select id from ruleset where hash=?", (self.hash,)).records
            if qData:
                # is already in database
                self.rulesetId = int(qData[0][0])
                return
        with Internal.db:
            self.rulesetId, self.name = self._newKey(minus)
            Query(
                'INSERT INTO ruleset(id,name,hash,description) VALUES(?,?,?,?)',
                (self.rulesetId, english(self.name),
                 self.hash, self.description),
                failSilent=True)
            cmd = 'INSERT INTO rule(ruleset, list, position, name, definition, ' \
                'points, doubles, limits, parameter) VALUES(?,?,?,?,?,?,?,?,?)'
            args = [self.ruleRecord(x) for x in self.allRules]
            Query(cmd, args)

    @staticmethod
    def availableRulesets() ->List['Ruleset']:
        """return all rulesets defined in the database plus all predefined rulesets"""
        templateIds = (x[0]
                       for x in Query("SELECT id FROM ruleset WHERE id<0").records)
        result = [Ruleset(x) for x in templateIds]
        for predefined in PredefinedRuleset.rulesets():
            if predefined not in result or predefined.name not in [x.name for x in result]:
                result.append(predefined)
        return result

    @staticmethod
    def selectableRulesets(server:Optional[str]=None) ->List['Ruleset']:
        """return all selectable rulesets for a new game.
        server is used to find the last ruleset used by us on that server, this
        ruleset will returned first in the list."""
        result = Ruleset.availableRulesets()
        # if we have a selectable ruleset with the same name as the last used ruleset
        # put that ruleset in front of the list. We do not want to use the exact same last used
        # ruleset because we might have made some fixes to the ruleset
        # meanwhile
        if server is None:  # scoring game
            # the exists clause is only needed for inconsistent data bases
            qData = Query("select ruleset from game where seed=0 "
                          " and exists(select id from ruleset where game.ruleset=ruleset.id)"
                          "order by starttime desc limit 1").records
        else:
            qData = Query(
                'select lastruleset from server where lastruleset is not null and url=?',
                (server,)).records
            if not qData:
                # we never played on that server
                qData = Query('select lastruleset from server where lastruleset is not null '
                              'order by lasttime desc limit 1').records
        if qData:
            lastUsedId = qData[0][0]
            qData = Query(
                "select name from ruleset where id=?",
                (lastUsedId,
                )).records
            if qData:
                lastUsed = qData[0][0]
                for idx, ruleset in enumerate(result):
                    if ruleset.name == lastUsed:
                        del result[idx]
                        return [ruleset] + result
        return result

    def diff(self, other:Any) ->List[Tuple[Optional['RuleBase'], Optional['RuleBase']]]:
        """return a list of tuples. Every tuple holds one or two rules: tuple[0] is from self, tuple[1] is from other"""
        result:List[Tuple[Optional[RuleBase], Optional[RuleBase]]] = []
        leftDict = {x.name: x for x in self.allRules}
        rightDict = {x.name: x for x in other.allRules}
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


class RuleBase(ReprMixin):

    """a base for standard Rule and parameter rules IntRule, StrRule, BoolRule"""

    options : Dict[str, str] = {}
    ruleClasses : Dict[str, Type] = {}

    def __init__(self, name: str, definition: str, description: str):
        self.hasSelectable = False
        self.ruleClasses[self.__class__.__name__] = self.__class__
        self.__name = name
        self.definition = definition
        self.description = description
        self.score:Score

    @property
    def name(self) ->str:
        """name is readonly"""
        return self.__name

    def selectable(self, hand:Optional['Hand']) ->bool:  # pylint: disable=unused-argument
        """default, for mypy"""
        return False

    def appliesToHand(self, hand:'Hand') ->bool:  # pylint: disable=unused-argument
        """returns true if this applies to hand"""
        return False

    def appliesToMeld(self, hand:Optional['Hand'], meld:'Meld') ->bool:  # pylint: disable=unused-argument
        """for mypy"""
        return False

    def key(self) ->str:
        """for mypy"""
        return ''

    def validate(self) ->Optional[str]:
        """is the rule valid?"""

    def hashStr(self) ->str:
        """
        all that is needed to hash this rule

        @return: The unique hash string
        @rtype: str
        """
        return ''

    def __str__(self) ->str:
        return self.hashStr()


def ruleKey(name:str) ->str:
    """the key is used for finding a rule in a RuleList"""
    return english(name).replace(' ', '').replace('.', '')


class Rule(RuleBase):

    """a mahjongg rule with a name, matching variants, and resulting score.
    The rule applies if at least one of the variants matches the hand.
    For parameter rules, only use name, definition,parameter. definition must start with int or str
    which is there for loading&saving, but internally is stripped off."""
    # pylint: disable=too-many-arguments

    ruleCode : Dict[str, 'Rule'] = {}
    limitHand = None

    @classmethod
    def memoize(cls, func, srcClass):  # type:ignore
        """cache results for func"""
        code = func.__code__
        clsMethod = code.co_varnames[0] == 'cls'

        def wrapper(*args:Any) ->Dict[Tuple[Type, str], Any]:
            """closure"""
            hand = args[1] if clsMethod else args[0]
            cacheKey = (cls, func.__name__)
            if cacheKey not in hand.ruleCache:
                result = func(*args)
                hand.ruleCache[cacheKey] = result
                if Debug.ruleCache:
                    hand.debug(
                        f'new ruleCache entry for hand {id(hand) % 10000}: {cacheKey}={result}')
                return result
            if Debug.ruleCache:
                if hand.ruleCache[cacheKey] != func(*args):
                    hand.player.game.debug(
                        f'cacheKey={cacheKey} rule={srcClass} func:{func} args:{args}')
                    hand.player.game.debug(
                        f'  hand:{id(hand)}/{hand}')
                    hand.player.game.debug(
                        f'  cached:{str(hand.ruleCache[cacheKey])} ')
                    hand.player.game.debug(
                        f'    real:{str(func(*args))} ')
            return hand.ruleCache[cacheKey]
        return classmethod(wrapper) if clsMethod else staticmethod(wrapper)

    def __init__(self, name:str, definition:str='', points:int=0, doubles:int=0, limits:float=0,
            description:str='', explainTemplate:str='', debug:bool=False) ->None:
        RuleBase.__init__(self, name, definition, description)
        self.hasSelectable = False
        self.explainTemplate = explainTemplate
        self.score = Score(points, doubles, limits)
        self.parameter = 0
        self.debug = debug
        self.__parseDefinition()

    @staticmethod
    def redirectTo(srcClass:Any, destClass:Any, memoize:bool=False) ->None:  # xype:ignore
        """inject my static and class methods into destClass,
        converting methods to staticmethod/classmethod as needed"""
        # also for inherited methods
        classes = list(reversed(srcClass.__mro__[:-2]))
        combinedDict = dict(classes[0].__dict__)
        for ancestor in classes[1:]:
            combinedDict.update(ancestor.__dict__)
        for funcName, method in combinedDict.items():
            if isinstance(method, (types.FunctionType, classmethod, staticmethod)):
                if hasattr(method, '__func__'):
                    method = method.__func__
                if memoize and method.__name__ in srcClass.cache:
                    method = destClass.memoize(method, srcClass)
                else:
                    if method.__code__.co_varnames[0] == 'cls':
                        method = classmethod(method)
                    else:
                        method = staticmethod(method)
                setattr(destClass, funcName, method)

    @classmethod
    def importRulecode(cls) ->None:
        """for every RuleCode class defined in this module,
        generate an instance and add it to dict Rule.ruleImpl.
        Also convert all RuleCode methods into classmethod or staticmethod"""
        if not cls.ruleCode:
            import rulecode
            for ruleClass in rulecode.__dict__.values():
                if hasattr(ruleClass, "__mro__"):
                    if ruleClass.__mro__[-2].__name__ == 'RuleCode' and len(ruleClass.__mro__) > 2:
                        cls.ruleCode[ruleClass.__name__] = ruleClass
                        # this changes all methods to classmethod or
                        # staticmethod
                        cls.redirectTo(ruleClass, ruleClass)

    def key(self) ->str:
        """the key is used for finding a rule in a RuleList"""
        return ruleKey(self.name)

    def __parseDefinition(self) ->None:
        """private setter for definition"""
        if not self.definition:
            return  # may happen with special programmed rules
        variants = self.definition.split('||')
        self.__class__.options = {}
        self.hasSelectable = False
        for idx, variant in enumerate(variants):
            variant = str(variant)
            if variant[0] == 'F':
                assert idx == 0
                code = self.ruleCode[variant[1:]]
                # when executing code for this rule, we do not want
                # to call those things indirectly
                self.redirectTo(code, self.__class__, memoize=True)
                if hasattr(code, 'selectable'):
                    self.hasSelectable = True
            elif variant[0] == 'O':
                for action in variant[1:].split():
                    aParts = action.split('=')
                    if len(aParts) == 1:
                        aParts.append('None')
                    self.options[aParts[0]] = aParts[1]
            else:
                pass
        self.validate()

    def validate(self) ->None:
        """check for validity"""
        payers = int(self.options.get('payers', 1))
        payees = int(self.options.get('payees', 1))
        if not 2 <= payers + payees <= 4:
            logException(
                i18nc(
                    '%1 can be a sentence', '%4 have impossible values %2/%3 in rule "%1"',
                    self.name, payers, payees, 'payers/payees'))

    def explain(self, meld:Optional['Meld']) ->str:
        """use this rule for scoring"""
        template = i18n(self.explainTemplate if self.explainTemplate else self.name)
        what = template.format(
                group=meld[0].groupName() if meld else '',
                value=meld[0].valueName() if meld else '',
                meldType=meld.typeName() if meld else '',
                meldName=meld.name() if meld else '',
                tileName=meld[0].name() if meld else '').replace(
                    '&', '').replace('  ', ' ').strip()
        return f'{what}: {self.score.i18nStr()}'

    def hashStr(self) ->str:
        """
        all that is needed to hash this rule. Try not to change this to keep
        database congestion low.

        @return: The unique hash string
        @rtype: str
        """
        return f'{self.name}: {self.definition} {self.score}'

    def i18nStr(self) ->str:
        """return a human readable string with the content"""
        return self.score.i18nStr()

    @staticmethod
    def exclusive() ->bool:
        """True if this rule can only apply to one player"""
        return False

    def hasNonValueAction(self) ->bool:
        """Rule has a special action not changing the score directly"""
        return bool(any(x not in ['lastsource', 'announcements'] for x in self.options))


class ParameterRule(RuleBase):

    """for parameters"""
    prefix: str = ''

    def __init__(self, name:str, definition:str, description:str, parameter:Union[str, int, bool]):
        RuleBase.__init__(self, name, definition, description)
        defParts = definition.split('||')
        self.parName = defParts[0][len(self.prefix):]
        self.score = Score()
        self.parameter = parameter

    def key(self) ->str:
        """the key is used for finding a rule in a RuleList"""
        return self.parName

    def hashStr(self) ->str:
        """
        all that is needed to hash this rule. Try not to change this to keep
        database congestion low.

        @return: The unique hash string
        @rtype: str
        """
        result = f'{self.name}: {self.definition} {self.parameter}'
        return result

    def i18nStr(self) ->str:
        """return a human readable string with the content"""
        return str(self.parameter)


class IntRule(ParameterRule):

    """for int parameters. Duck typing with Rule"""
    prefix = 'int'

    def __init__(self, name:str, definition:str, description:str, parameter:int):
        ParameterRule.__init__(self, name, definition, description, int(parameter))
        self.minimum = 0
        for defPart in definition.split('||'):
            if defPart.startswith('Omin='):
                self.minimum = int(defPart[5:])

    def validate(self) ->Optional[str]:
        """is the rule valid?"""
        assert isinstance(self.parameter, int)
        if self.parameter < self.minimum:
            return i18nc(
                'wrong value for rule', '%1: %2 is too small, minimal value is %3',
                i18n(self.name), self.parName, self.minimum)
        return None


class BoolRule(ParameterRule):

    """for bool parameters. Duck typing with Rule"""
    prefix = 'bool'

    def __init__(self, name:str, definition:str, description:str, parameter:str):
        _ = parameter not in ('false', 'False', False, 0, '0', None, '')
        ParameterRule.__init__(self, name, definition, description, _)


class StrRule(ParameterRule):

    """for str parameters. Duck typing with Rule. Currently not used."""
    prefix = 'str'

    def __init__(self, name:str, definition:str, description:str, parameter:str) ->None:
        ParameterRule.__init__(self, name, definition, description, parameter)


class PredefinedRuleset(Ruleset):

    """special code for loading rules from program code instead of from the database"""

    classes : Set[Type] = set()  # only those will be playable
    preRulesets : List['PredefinedRuleset'] = []

    def __init__(self, name:str='') ->None:
        Ruleset.__init__(self, name or 'general predefined ruleset')

    @staticmethod
    def rulesets() ->Sequence[Ruleset]:
        """a list of instances for all predefined rulesets"""
        if not PredefinedRuleset.preRulesets:
            PredefinedRuleset.preRulesets = [
                x() for x in sorted(PredefinedRuleset.classes, key=lambda x: x.__name__)]
        return PredefinedRuleset.preRulesets

    def rules(self) ->None:
        """here the predefined rulesets can define their rules"""

    def clone(self) ->Ruleset:
        """return a clone, unloaded"""
        return self.__class__()
