# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

from log import SERVERMARK

def srvMessage(*args):
    """
    concatenate all args needed for i18n encoded in one string.
    For an explanation see util.translateServerMessage.

    @returns: The string to be wired.
    @rtype: C{str}, utf-8 encoded
    """
    strArgs = []
    for arg in args:
        if isinstance(arg, str):
            arg = arg.encode('utf-8')
        else:
            arg = str(arg).encode('utf-8')
        strArgs.append(arg)
    mark = SERVERMARK.encode()
    return mark + mark.join(strArgs) + mark


def srvError(cls, *args):
    """raise an exception, passing args as a single string"""
    raise cls(srvMessage(*args))
