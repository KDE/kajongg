#!/usr/bin/env python3

"""
Copyright (c) 2010,2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>
Redistribution and use is allowed according to the terms of the BSD license.
For details see the accompanying COPYING-CMAKE-SCRIPTS file.
"""

import sys

try:
    from twisted.spread import pb
except:
    print('twisted_version:{}'.format('0.0.0'))
    sys.exit(0)
from twisted import __version__
print('twisted_version:{}'.format(__version__))
