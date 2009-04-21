#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Authors of original libkmahjongg in C++:
    Copyright (C) 1997 Mathias Mueller   <in5y158@public.uni-hamburg.de>
    Copyright (C) 2006 Mauricio Piacentini  <mauricio@tabuleiro.com>

this adapted python code:
    Copyright (C) 2008,2009 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from PyQt4.QtCore import QString,  QVariant,  QSizeF
from PyKDE4.kdecore import i18n, KStandardDirs, KGlobal, KConfig, KConfigGroup
from PyKDE4.kdeui import KSvgRenderer
from util import logException

TILESETVERSIONFORMAT = 1
LIGHTSOURCES = ['NE', 'NW', 'SW', 'SE']

class Element(object):
    def __init__(self, name, high, occurrence):
        self.name = name
        self.high = high
        self.occurrence = occurrence

class Elements(object):
    scoringName = dict()
    elementName = dict()
    generatorList = [('CHARACTER', 9, 4), ('BAMBOO', 9, 4),
                ('ROD', 9, 4),  ('WIND', 4, 4),
                ('DRAGON', 3, 4), ('SEASON', 4, 1), ('FLOWER', 4, 1)]
    def __init__(self):
        self.__available = [Element(name, high, occ)  for name, high, occ in Elements.generatorList]
        for value in '123456789':
            self.add('ROD', 's', value, value)
            self.add('BAMBOO', 'b', value, value)
            self.add('CHARACTER', 'c', value, value)
        self.add('WIND', 'w', '1', 'n')
        self.add('WIND', 'w', '2', 's')
        self.add('WIND', 'w', '3', 'e')
        self.add('WIND', 'w', '4', 'w')
        self.add('DRAGON','d', '1', 'b' )
        self.add('DRAGON','d', '2', 'g' )
        self.add('DRAGON','d', '3', 'r' )
        self.add('FLOWER', 'f', '1', 'e')
        self.add('FLOWER', 'f', '2', 's')
        self.add('FLOWER', 'f', '3', 'w')
        self.add('FLOWER', 'f', '4', 'n');
        self.add('SEASON', 'y', '1', 'e')
        self.add('SEASON', 'y', '2', 's')
        self.add('SEASON', 'y', '3', 'w')
        self.add('SEASON', 'y', '4', 'n');

    def getAvailable(self):
        return self.__available

    available = property(getAvailable)

    def add(self, tileName, meldChar, tileValue, meldValue):
        elName = '%s_%s' % (tileName , tileValue)
        scName = meldChar+meldValue
        Elements.scoringName[elName] = scName
        Elements.elementName[scName] = elName

    def all(self):
        result = []
        for element in self.available:
            for idx in range(1, element.high+1):
                result.extend([element.name + '_' + str(idx)]*element.occurrence)
        return result

elements = Elements()

class TileException(Exception):
    """will be thrown if the tileset cannot be loaded"""
    pass

def locateTileset(which):
    """locate the file with a tileset"""
    return QString(KStandardDirs.locate("kmahjonggtileset",
                QString(which)))

class Tileset(object):
    """represents a complete tileset"""
    catalogDefined = False

    @staticmethod
    def defineCatalog():
        """whatever this does"""
        if not Tileset.catalogDefined:
            KGlobal.dirs().addResourceType("kmahjonggtileset",
                "data", QString.fromLatin1("kmahjongglib/tilesets"))
            KGlobal.locale().insertCatalog("libkmahjongglib")
            Tileset.catalogDefined = True

    @staticmethod
    def tilesAvailable():
        """returns all available tile sets"""
        Tileset.defineCatalog()
        tilesAvailableQ = KGlobal.dirs().findAllResources(
            "kmahjonggtileset", "*.desktop", KStandardDirs.Recursive)
        # now we have a list of full paths. Use the base name minus .desktop:
        tilesets = [str(x).rsplit('/')[-1].split('.')[0] for x in tilesAvailableQ ]
        tilesets.remove('alphabet')
        return [Tileset(x) for x in tilesets]

    def __init__(self, desktopFileName=None):
        if desktopFileName is None:
            desktopFileName = 'default'
        self.sizeIncrement = 10
        self.tileSize = None
        self.faceSize = None
        self.__renderer = None
        self.__shadowOffsets = None
        self.defineCatalog()
        self.path = locateTileset(desktopFileName + '.desktop')
        if self.path.isEmpty():
            self.path = locateTileset('default.desktop')
            if self.path.isEmpty():
                logException(TileException(i18n( \
                'cannot find any tileset, is libkmahjongg installed?')))
            else:
                print('cannot find tileset %s, using default' % desktopFileName)
                self.desktopFileName = 'default'
        else:
            self.desktopFileName = desktopFileName
        self.darkenerAlpha = 230 if self.desktopFileName == 'jade' else 50
        tileconfig = KConfig(self.path, KConfig.SimpleConfig)
        group = KConfigGroup(tileconfig.group("KMahjonggTileset"))

        self.name = group.readEntry("Name",  "unknown tileset") # Returns translated data
        self.author = group.readEntry("Author",  "unknown author")
        self.description = group.readEntry("Description",  "no description available")
        self.authorEmail = group.readEntry("AuthorEmail",  "no E-Mail address available")

        #Version control
        tileversion,  entryOK = group.readEntry("VersionFormat", QVariant(0)).toInt()
        #Format is increased when we have incompatible changes, meaning that
        # older clients are not able to use the remaining information safely
        if not entryOK or tileversion > TILESETVERSIONFORMAT:
            logException(TileException('tileversion file / program: %d/%d' %  \
                (tileversion,  TILESETVERSIONFORMAT)))

        graphName = QString(group.readEntry("FileName"))
        self.__graphicspath = locateTileset(graphName)
        if self.__graphicspath.isEmpty():
            logException(TileException('cannot find kmahjongglib/tilesets/%s for %s' % \
                        (graphName,  self.desktopFileName )))
        self.renderer() # now that we get the sizes from the svg, we need the renderer right away

    def __str__(self):
        return "tileset id=%d name=%s, name id=%d" % \
            (id(self), self.desktopFileName, id(self.desktopFileName))

    def shadowWidth(self):
        """the size of border plus shadow"""
        return self.tileSize.width() - self.faceSize.width()

    def shadowHeight(self):
        """the size of border plus shadow"""
        return self.tileSize.height() - self.faceSize.height()

    def renderer(self):
        """initialise the svg renderer with the selected svg file"""
        if self.__renderer is None:
            self.__renderer = KSvgRenderer(self.__graphicspath)
            if not self.__renderer.isValid():
                logException(TileException( \
                i18n('file <filename>%1</filename> contains no valid SVG').arg(self.__graphicspath)))
            distance = 0
            if self.desktopFileName == 'classic':
                distance = 2
            distanceSize = QSizeF(distance, distance)
            self.faceSize = self.__renderer.boundsOnElement('BAMBOO_1').size()+distanceSize
            self.tileSize = self.__renderer.boundsOnElement('TILE_2').size()+distanceSize
            shW = self.shadowWidth()
            shH = self.shadowHeight()
            self.__shadowOffsets = [[(-shW, 0), (0, 0), (0, shH), (-shH, shW)],
                [(0, 0), (shH, 0), (shW, shH), (0, shW)],
                [(0, -shH), (shH, -shW), (shW, 0), (0, 0)],
                [(-shW, -shH), (0, -shW), (0, 0), (-shH, 0)]]
        return self.__renderer

    def shadowOffsets(self, lightSource, rotation):
        lightSourceIndex = LIGHTSOURCES.index(lightSource)
        return self.__shadowOffsets[lightSourceIndex][rotation//90]
