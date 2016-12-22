# -*- coding: utf-8 -*-

"""
Copyright (C) 2014-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from common import unicode, nativeString


class QString(unicode):

    """If pyqt does not define it: We need something that looks like a QString"""
    # pylint: disable=too-many-public-methods

    def __new__(cls, value=None):
        if value is None:
            return unicode.__new__(cls)
        elif isinstance(value, unicode):
            return unicode.__new__(cls, value)
        else:
            return unicode.__new__(cls, nativeString(value))

    def toString(self):
        """do nothing"""
        return self

    def toInt(self):
        """like QString.toInt"""
        try:
            result = int(self)
            valueOk = True
        except ValueError:
            result = None
            valueOk = False
        return result, valueOk

    def isEmpty(self):
        """is the QString empty?"""
        return len(self) == 0
