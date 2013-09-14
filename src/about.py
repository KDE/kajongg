# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2011 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
"""

from kde import ki18n, KAboutData

from common import Internal

class About(object):
    """we need persistancy but do not want to spoil global name space"""
    def __init__(self):
        self.appName = "kajongg"
        catalog = ""
        homePage = "http://kde.org/applications/games/kajongg/"
        version = Internal.version
        programName = ki18n ("Kajongg")
        description = ki18n ("Mah Jongg - the ancient Chinese board game for 4 players")
        kajongglicense = KAboutData.License_GPL
        kajonggcopyright = ki18n ("(C) 2008,2009,2010,2011,2012 Wolfgang Rohdewald")
        aboutText = ki18n("This is the classical Mah Jongg for four players. "
            "If you are looking for Mah Jongg solitaire please use the "
            "application kmahjongg.")

        self.about = KAboutData (self.appName, catalog, programName,
            version, description, kajongglicense, kajonggcopyright, aboutText, homePage)
        self.about.addAuthor(ki18n("Wolfgang Rohdewald"), ki18n("Original author"), "wolfgang@rohdewald.de")
