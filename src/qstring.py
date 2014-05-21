# -*- coding: utf-8 -*-

"""
Copyright (C) 2014-2014 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from common import isPython3
if isPython3:
    from common import unicode # pylint: disable=redefined-builtin

class QString(unicode):
    """If pyqt does not define it: We need something that looks like a QString"""
    # pylint: disable=too-many-public-methods
    def toString(self):
        """do nothing"""
        return self.decode('utf-8')
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
