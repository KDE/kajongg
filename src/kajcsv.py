# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

import csv
import subprocess
import datetime

from enum import IntEnum
from functools import total_ordering

from typing import Tuple, List, Any, Optional, Dict

from common import Options, ReprMixin
from player import Player, Players

class CsvWriter:
    """how we want it"""
    def __init__(self, filename:str, mode:str='w') ->None:
        self.outfile = open(filename, mode, encoding='utf-8')  # pylint: disable=consider-using-with
        self.__writer = csv.writer(self.outfile, delimiter=Csv.delimiter)

    def writerow(self, row:'CsvRow') ->None:
        """write one row"""
        self.__writer.writerow([str(cell) for cell in row])  # type:ignore[attr-defined]

    def __del__(self) ->None:
        """clean up"""
        self.outfile.close()


class Csv:
    """how we want it"""

    delimiter = ';'

    @staticmethod
    def reader(filename:str) ->Any:
        """return a generator for decoded strings"""
        # see https://stackoverflow.com/questions/51264355/how-to-type-annotate-object-returned-by-csv-writer
        return csv.reader(open(filename, 'r', encoding='utf-8'), delimiter=Csv.delimiter)

@total_ordering
class CsvRow(ReprMixin):
    """represent a row in kajongg.csv"""

    fields = IntEnum('Field', 'RULESET AI COMMIT PY_VERSION GAME TAGS PLAYERS', start=0)

    commitDates : Dict[str, datetime.datetime] = {}

    def __init__(self, row:List[str]) ->None:
        self.row = row
        self.ruleset, self.aiVariant, self.commit, self.py_version, self.game, self.tags = row[:6]
        self.winner = None
        rest = row[6:]
        players:List[Player] = []
        while rest:
            name, balance, wonCount, winner = rest[:4]
            player = Player(None, name)
            player.balance = int(balance)
            player.wonCount = int(wonCount)
            players.append(player)
            if winner:
                self.winner = player
            rest = rest[4:]
        self.players = Players(players)

    @property
    def commitDate(self) ->datetime.datetime:
        """return datetime"""
        if self.commit not in self.commitDates:
            try:
                self.commitDates[self.commit] = datetime.datetime.fromtimestamp(
                    int(subprocess.check_output(
                        'git show -s --format=%ct {}'.format(self.commit).split(), stderr=subprocess.DEVNULL)))
            except subprocess.CalledProcessError:
                self.commitDates[self.commit] = datetime.datetime.fromtimestamp(0)
        return self.commitDates[self.commit]

    @property
    def game(self) ->str:
        """return the game"""
        return self.row[self.fields.GAME]

    @game.setter
    def game(self, value:str) ->None:
        self.row[self.fields.GAME] = value

    @property
    def ruleset(self) ->str:
        """return the ruleset"""
        return self.row[self.fields.RULESET]

    @ruleset.setter
    def ruleset(self, value:str) ->None:
        self.row[self.fields.RULESET] = value

    @property
    def aiVariant(self) ->str:
        """return the AI used"""
        return self.row[self.fields.AI]

    @aiVariant.setter
    def aiVariant(self, value:str) ->None:
        self.row[self.fields.AI] = value

    @property
    def commit(self) ->str:
        """return the git commit"""
        return self.row[self.fields.COMMIT]

    @commit.setter
    def commit(self, value:str) ->None:
        self.row[self.fields.COMMIT] = value

    @property
    def py_version(self) ->str:
        """return the python version"""
        return self.row[self.fields.PY_VERSION]

    @py_version.setter
    def py_version(self, value:str) ->None:
        self.row[self.fields.PY_VERSION] = value

    @property
    def tags(self) ->str:
        """return the tags"""
        return self.row[self.fields.TAGS]

    @tags.setter
    def tags(self, value:str) ->None:
        self.row[self.fields.TAGS] = value

    def result(self) ->Tuple[str, ...]:
        """return a tuple with the fields holding the result"""
        return tuple(self.row[self.fields.PLAYERS:])

    def write(self) ->None:
        """write to Options.csv"""
        assert Options.csv
        writer = CsvWriter(Options.csv, mode='a')
        writer.writerow(self.row)
        del writer

    def __eq__(self, other:Any) ->bool:
        return self.row == other.row

    def sortkey(self) ->List[Any]:
        """return string for comparisons"""
        result = [self.game, self.ruleset, self.aiVariant,
                  self.commitDate or datetime.datetime.fromtimestamp(0), self.py_version]
        result.extend(self.row[self.fields.TAGS:])
        return result

    def __lt__(self, other:Any) ->bool:
        return self.sortkey() < other.sortkey()

    def __getitem__(self, field:int) ->str:
        """direct access to row"""
        return self.row[field]

    def __hash__(self) ->int:
        return hash(tuple(self.row))

    def data(self, field:int) ->str:
        """return a string representing this field for messages"""
        result = self.row[field]
        if field == self.fields.COMMIT:
            result = '{}({})'.format(result, self.commitDate)
        return result

    def differs_for(self, other:'CsvRow') ->Optional[Tuple[str, str]]:
        """return the field names for the source attributes causing a difference.
        Possible values are commit and py_version. If both rows are identical, return None."""
        if self.row[self.fields.PLAYERS:] != other.row[self.fields.PLAYERS:]:
            differing = []
            same = []
            for cause in (self.fields.COMMIT, self.fields.PY_VERSION):
                if self.row[cause] != other.row[cause]:
                    _ = '{} {} != {}'.format(cause.name, self.data(cause), other.data(cause))
                    differing.append(_)
                else:
                    _ = '{} {}'.format(cause.name, self.data(cause))
                    same.append(_)
            return ', '.join(differing), ', '.join(same)
        return None

    def neutralize(self) ->None:
        """for comparisons"""
        for idx, field in enumerate(self.row):
            field = field.replace(' ', '')
            if field.startswith('Tester ') or field.startswith('Tüster'):
                field = 'Tester'
            if 'MEM' in field:
                parts = field.split(',')
                for part in parts[:]:
                    if part.startswith('MEM'):
                        parts.remove(part)
                field = ','.join(parts)
            self.row[idx] = field

    def __str__(self) ->str:
        return 'Game {} {} AI={} commit={}({}) py={} {}'.format(
            self.game, self.ruleset, self.aiVariant, self.commit, self.commitDate, self.py_version, self.tags)
