# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

from typing import Any

from twisted.spread.pb import Error

from log import SERVERMARK


def srvMessage(*args: Any) ->str:
    """
    concatenate all args needed for i18n encoded in one string.
    For an explanation see log.translateServerMessage.

    @returns: The string to be wired.
    @rtype: C{str}, utf-8 encoded
    """
    strArgs = []
    for arg in args:
        if not isinstance(arg, str):
            arg = str(arg)
        strArgs.append(arg)
    return SERVERMARK + SERVERMARK.join(strArgs) + SERVERMARK


def srvError(*args: Any) ->'Error':
    """raise an exception, passing args as a single string"""
    return Error(srvMessage(*args))
