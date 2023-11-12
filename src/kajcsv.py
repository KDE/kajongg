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

from common import Options, ReprMixin
from player import Player, Players

class CsvWriter:
    """how we want it"""
    def __init__(self, filename, mode='w'):
        self.outfile = open(filename, mode, encoding='utf-8')  # pylint: disable=consider-using-with
        self.__writer = csv.writer(self.outfile, delimiter=Csv.delimiter)

    def writerow(self, row):
        """write one row"""
        self.__writer.writerow([str(cell) for cell in row])

    def __del__(self):
        """clean up"""
        self.outfile.close()


class Csv:
    """how we want it"""

    delimiter = ';'

    @staticmethod
    def reader(filename):
        """return a generator for decoded strings"""
        return csv.reader(open(filename, 'r', encoding='utf-8'), delimiter=Csv.delimiter)

@total_ordering
class CsvRow(ReprMixin):
    """represent a row in kajongg.csv"""

    fields = IntEnum('Field', 'RULESET AI COMMIT PY_VERSION GAME TAGS PLAYERS', start=0)

    commitDates = {}

    def __init__(self, row):
        self.row = row
        self.ruleset, self.aiVariant, self.commit, self.py_version, self.game, self.tags = row[:6]
        self.winner = None
        rest = row[6:]
        players = []
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
    def commitDate(self):
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
    def game(self):
        """return the game"""
        return self.row[self.fields.GAME]

    @game.setter
    def game(self, value):
        self.row[self.fields.GAME] = value

    @property
    def ruleset(self):
        """return the ruleset"""
        return self.row[self.fields.RULESET]

    @ruleset.setter
    def ruleset(self, value):
        self.row[self.fields.RULESET] = value

    @property
    def aiVariant(self):
        """return the AI used"""
        return self.row[self.fields.AI]

    @aiVariant.setter
    def aiVariant(self, value):
        self.row[self.fields.AI] = value

    @property
    def commit(self):
        """return the git commit"""
        return self.row[self.fields.COMMIT]

    @commit.setter
    def commit(self, value):
        self.row[self.fields.COMMIT] = value

    @property
    def py_version(self):
        """return the python version"""
        return self.row[self.fields.PY_VERSION]

    @py_version.setter
    def py_version(self, value):
        self.row[self.fields.PY_VERSION] = value

    @property
    def tags(self):
        """return the tags"""
        return self.row[self.fields.TAGS]

    @tags.setter
    def tags(self, value):
        self.row[self.fields.TAGS] = value

    def result(self):
        """return a tuple with the fields holding the result"""
        return tuple(self.row[self.fields.PLAYERS:])

    def write(self):
        """write to Options.csv"""
        assert Options.csv
        writer = CsvWriter(Options.csv, mode='a')
        writer.writerow(self.row)
        del writer

    def __eq__(self, other):
        return self.row == other.row

    def sortkey(self):
        """return string for comparisons"""
        result = [self.game, self.ruleset, self.aiVariant,
                  self.commitDate or datetime.datetime.fromtimestamp(0), self.py_version]
        result.extend(self.row[self.fields.TAGS:])
        return result

    def __lt__(self, other):
        return self.sortkey() < other.sortkey()

    def __getitem__(self, field):
        """direct access to row"""
        return self.row[field]

    def __hash__(self):
        return hash(tuple(self.row))

    def data(self, field):
        """return a string representing this field for messages"""
        result = self.row[field]
        if field == self.fields.COMMIT:
            result = '{}({})'.format(result, self.commitDate)
        return result

    def differs_for(self, other):
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

    def neutralize(self):
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

    def __str__(self):
        return 'Game {} {} AI={} commit={}({}) py={} {}'.format(
            self.game, self.ruleset, self.aiVariant, self.commit, self.commitDate, self.py_version, self.tags)
