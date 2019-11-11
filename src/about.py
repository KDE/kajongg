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

from kde import KAboutData
from mi18n import i18n

from common import Internal


class About:

    """we need persistency but do not want to spoil global name space"""

    def __init__(self):
        self.appName = "kajongg"
        catalog = ""
        homePage = "https://kde.org/applications/games/kajongg/"
        version = str(Internal.defaultPort)
        programName = i18n("Kajongg")
        description = i18n(
            "Mah Jongg - the ancient Chinese board game for 4 players")
        kajongglicense = KAboutData.License_GPL
        kajonggcopyright = "(C) 2008-2016 Wolfgang Rohdewald"
        aboutText = i18n("This is the classical Mah Jongg for four players. "
                         "If you are looking for Mah Jongg solitaire please "
                         "use the application kmahjongg.")

        self.about = KAboutData(self.appName, catalog, programName,
                                version, description, kajongglicense,
                                kajonggcopyright, aboutText, homePage)
        self.about.addAuthor(
            "Wolfgang Rohdewald",
            i18n("Original author"),
            "wolfgang@rohdewald.de")
