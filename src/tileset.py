#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Authors of original libkmahjongg in C++:
    Copyright (C) 1997 Mathias Mueller   <in5y158@public.uni-hamburg.de>
    Copyright (C) 2006 Mauricio Piacentini  <mauricio@tabuleiro.com>

this adapted python code:
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

from PyQt4.QtCore import QString,  QVariant,  QSizeF
from PyKDE4.kdecore import KStandardDirs, KGlobal, KConfig, KConfigGroup
from PyKDE4.kdeui import KSvgRenderer
from util import logWarning, logException

TILESETVERSIONFORMAT = 1
LIGHTSOURCES = ['NE', 'NW', 'SW', 'SE']

class Element(object):
    def __init__(self, name, high, occ):
        self.svgName = name
        self.high = high
        self.occurrence = occ
        
class Elements(object):
    """represents all elements"""
    def __init__(self):
        self.name = dict()
        # we assume that svg names and internal names never overlap. For currently
        # existing tilesets they do not. So we can put both mappings into the same dict.
        generatorList = [('CHARACTER', 9, 4), ('BAMBOO', 9, 4),
                    ('ROD', 9, 4),  ('WIND', 4, 4),
                    ('DRAGON', 3, 4), ('SEASON', 4, 1), ('FLOWER', 4, 1)]
        self.__available = [Element(name, high, occ)  for name, high, occ in generatorList]
        for value in '123456789':
            self.__define('ROD', 's', value, value)
            self.__define('BAMBOO', 'b', value, value)
            self.__define('CHARACTER', 'c', value, value)
        self.__define('WIND', 'w', '1', 'n')
        self.__define('WIND', 'w', '2', 's')
        self.__define('WIND', 'w', '3', 'e')
        self.__define('WIND', 'w', '4', 'w')
        self.__define('DRAGON', 'd', '1', 'b' )
        self.__define('DRAGON', 'd', '2', 'g' )
        self.__define('DRAGON', 'd', '3', 'r' )
        self.__define('FLOWER', 'f', '1', 'e')
        self.__define('FLOWER', 'f', '2', 's')
        self.__define('FLOWER', 'f', '3', 'w')
        self.__define('FLOWER', 'f', '4', 'n')
        self.__define('SEASON', 'y', '1', 'e')
        self.__define('SEASON', 'y', '2', 's')
        self.__define('SEASON', 'y', '3', 'w')
        self.__define('SEASON', 'y', '4', 'n')

    def __filter(self, withBoni):
        return (x for x in self.__available if withBoni or (x.svgName not in ['FLOWER', 'SEASON']))

    def __define(self, tileName, meldChar, tileValue, meldValue):
        """define an element"""
        svgName = '%s_%s' % (tileName , tileValue)
        kajonggName = meldChar+meldValue
        self.name[svgName] = kajonggName
        self.name[kajonggName] = svgName

    def count(self, withBoni):
        """how many tiles are to be used by the game"""
        return sum(e.high * e.occurrence for e in self.__filter(withBoni))

    def all(self, withBoni):
        """a list of all elements, each of them occurrence times"""
        result = []
        for element in self.__filter(withBoni):
            for idx in range(1, element.high+1):
                result.extend([self.name[element.svgName + '_' + str(idx)]]*element.occurrence)
        return result

Elements = Elements()

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
        for dontWant in ['alphabet', 'egypt']:
            if dontWant in tilesets:
                tilesets.remove(dontWant)
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
                logException(TileException(m18n( \
                'cannot find any tileset, is libkmahjongg installed?')))
            else:
                logWarning(m18n('cannot find tileset %1, using default',  desktopFileName))
                self.desktopFileName = 'default'
        else:
            self.desktopFileName = desktopFileName
        self.darkenerAlpha = 230 if self.desktopFileName == 'jade' else 50
        tileconfig = KConfig(self.path, KConfig.SimpleConfig)
        group = KConfigGroup(tileconfig.group("KMahjonggTileset"))

        self.name = group.readEntry("Name",  "unknown tileset").toString() # Returns translated data
        self.author = group.readEntry("Author",  "unknown author").toString()
        self.description = group.readEntry("Description",  "no description available").toString()
        self.authorEmail = group.readEntry("AuthorEmail",  "no E-Mail address available").toString()

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
                m18n('file <filename>%1</filename> contains no valid SVG'), self.__graphicspath))
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
        """real offset of the shadow on the screen"""
        lightSourceIndex = LIGHTSOURCES.index(lightSource)
        return self.__shadowOffsets[lightSourceIndex][rotation//90]
