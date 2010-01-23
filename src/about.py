#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008,2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

kajongg is free software you can redistribute it and/or modify
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

from PyKDE4.kdecore import ki18n,  KAboutData

class About(object):
    """we need persistent data but do not want to spoil global name space"""
    def __init__(self):
        self.appName     = bytes("kajongg")
        self.catalog     = bytes('')
        self.homePage    = bytes('http://www.kde-apps.org/content/show.php/kajongg?content=103206')
        self.bugEmail    = bytes('wolfgang@rohdewald.de')
        self.version     = bytes('0.4.0')
        self.programName = ki18n ("kajongg")
        self.description = ki18n ("Mah Jongg - the ancient Chinese board game for 4 players")
        self.kajongglicense     = KAboutData.License_GPL
        self.kajonggcopyright   = ki18n ("(c) 2008,2009,2010 Wolfgang Rohdewald")
        self.aboutText        = ki18n("This is the classical Mah Jongg for four players. "
            "If you are looking for Mah Jongg solitaire please use the "
            "application kmahjongg.")

        self.about  = KAboutData (self.appName, self.catalog,
                        self.programName,
                        self.version, self.description,
                        self.kajongglicense, self.kajonggcopyright, self.aboutText,
                        self.homePage, self.bugEmail)

