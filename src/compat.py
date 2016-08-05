# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2014 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from common import isPython3, unicode

class CsvWriter(object):
    """hide differences between Python 2 and 3"""
    def __init__(self, filename, mode='w'):
        self.outfile = open(filename, mode if isPython3 else mode+'b')
        self.__writer = csv.writer(self.outfile, delimiter=Csv.delimiter)

    def writerow(self, row):
        """write one row"""
        if isPython3:
            self.__writer.writerow(list(
                cell if isinstance(cell, unicode) else str(cell) for cell in row))
        else:
            self.__writer.writerow(list(
                cell.encode('utf-8') if isinstance(cell, unicode) else str(cell) for cell in row))

    def __del__(self):
        """clean up"""
        self.outfile.close()

class Csv(object):
    """hide differences between Python 2 and 3"""

    delimiter = ';'

    @staticmethod
    def unicode_reader(infile):
        """generator decoding utf-8 input"""
        for row in csv.reader(infile, delimiter=Csv.delimiter):
            yield list(cell.decode('utf-8') for cell in row)

    @staticmethod
    def reader(filename):
        """returns a generator for decoded strings"""
        if isPython3:
            return csv.reader(open(filename, 'r', encoding='utf-8'), delimiter=Csv.delimiter)
        else:
            return Csv.unicode_reader(open(filename, 'rb'))

