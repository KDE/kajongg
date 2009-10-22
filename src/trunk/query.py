#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008,2009 Wolfgang Rohdewald <wolfgang@rohdewald.de>

partially based on C++ code from:
    Copyright (C) 2006 Mauricio Piacentini  <mauricio@tabuleiro.com>

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
"""


from PyQt4.QtCore import QVariant
from util import logMessage
from syslog import LOG_ERR
from PyQt4.QtSql import QSqlQuery

class Query(object):
    """a more pythonic interface to QSqlQuery. We could instead use
    the python sqlite3 module but then we would either have to do
    more programming for the model/view tables, or we would have
    two connections to the same database.
    For selecting queries we read ALL records into a list of records.
    Every record is a list of all fields. q.data[0][1] is row 0, field 1.
    For select, we also convert to python data
    types - as far as we need them"""
    dbhandle = None
    lastError = None
    def __init__(self, cmdList):
        """we take a list of sql statements. Only the last one is allowed to be
        a select statement"""
        self.query = QSqlQuery(Query.dbhandle)
        self.msg = None
        self.data = []
        if not isinstance(cmdList, list):
            cmdList = list([cmdList])
        self.cmdList = cmdList
        for cmd in cmdList:
            print cmd
            self.success = self.query.exec_(cmd)
            if not self.success:
                Query.lastError = str(self.query.lastError().text())
                self.msg = 'ERROR: %s' % Query.lastError
                print self.msg
                logMessage(self.msg, prio=LOG_ERR)
                return
        if self.query.isSelect():
            self.data = []
            record = self.query.record()
            qFields = [record.field(x) for x in range(record.count())]
            while self.query.next():
                reclist = [None] * len(qFields)
                for idx in range(len(qFields)):
                    name = str(qFields[idx].name())
                    valType = qFields[idx].type()
                    if valType == QVariant.String:
                        value = unicode(self.query.value(idx).toString())
                    elif valType == QVariant.Double:
                        value = self.query.value(idx).toDouble()[0]
                    elif valType == QVariant.Int:
                        value = self.query.value(idx).toInt()[0]
                    elif valType == QVariant.UInt:
                        value = self.query.value(idx).toUInt()[0]
                    elif valType == QVariant.LongLong:
                        value = self.query.value(idx).toLongLong()[0]
                    elif valType == QVariant.ULongLong:
                        value = self.query.value(idx).toULongLong()[0]
                    else:
                        raise Exception('Query: variant type not implemented for field %s ' % name)
                    reclist[idx] = value
                self.data.append(reclist)
        else:
            self.data = None
