# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

Kajongg is free software you can redistribute it and/or modify
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
"""

from __future__ import print_function

import csv

class CsvWriter(object):
    """hide differences between Python 2 and 3"""
    def __init__(self, filename, mode='w'):
        self.outfile = open(filename, mode)
        self.__writer = csv.writer(self.outfile, delimiter=Csv.delimiter)

    def writerow(self, row):
        """write one row"""
        self.__writer.writerow(list(
            cell if isinstance(cell, str) else str(cell) for cell in row))

    def __del__(self):
        """clean up"""
        self.outfile.close()

class Csv(object):
    """hide differences between Python 2 and 3"""

    delimiter = ';'

    @staticmethod
    def reader(filename):
        """returns a generator for decoded strings"""
        return csv.reader(open(filename, 'r', encoding='utf-8'), delimiter=Csv.delimiter)

