#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

import syslog,  traceback

syslog.openlog('kmj')        
def logMessage(msg, prio=syslog.LOG_INFO):
    syslog.syslog(prio,  str(msg))
    print msg
    
def logException(e, prio=syslog.LOG_ERR):
    logMessage(e.message, prio)
    for line in traceback.format_stack()[:-2]:
        logMessage(line)
    raise e
