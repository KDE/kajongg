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

from common import unicode
from log import SERVERMARK

def srvMessage(*args):
    """
    concatenate all args needed for m18n encoded in one string.
    For an explanation see util.translateServerMessage.

    @returns: The string to be wired.
    @rtype: C{str}, utf-8 encoded
    """
    strArgs = []
    for arg in args:
        if isinstance(arg, unicode):
            arg = arg.encode('utf-8')
        else:
            arg = str(arg).encode('utf-8')
        strArgs.append(arg)
    mark = SERVERMARK.encode()
    return mark + mark.join(strArgs) + mark


def srvError(cls, *args):
    """raise an exception, passing args as a single string"""
    raise cls(srvMessage(*args))


