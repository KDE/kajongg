# -*- coding: utf-8 -*-

"""
Copyright (C) 2013-2014 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

# pylint: disable=unused-import, unused-wildcard-import, wildcard-import
# pylint: disable=invalid-name

import sip
import sys

from common import isPython3, Internal

usingQt4 = True  # Default for now
usingQt5 = False

if '--qt5' in sys.argv:
    try:
        from qt5 import *
        usingQt5 = True
        usingQt4 = False
    except ImportError as exc:
        Internal.logger.debug('{who}: Cannot import Qt5:{msg}, using Qt4 instead'.format(
            who='Server' if Internal.isServer else 'Client',
            msg=exc.message))
        from qt4 import *
else:
    from qt4 import *


class RealQVariant(object):

    """context helper, forcibly disabling QVariant autoconversion for Qt5.
    This makes it easier to write code supporting both Qt4 and Qt5"""

    def __init__(self):
        if usingQt5:
            sip.enableautoconversion(QVariant, False)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trback):
        """enable autoconversion again"""
        if usingQt5:
            sip.enableautoconversion(QVariant, True)

if isPython3:
    def toQVariant(obj=None):
        return obj
else:
    def toQVariant(obj=None):
        return QVariant(obj)
