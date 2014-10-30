# -*- coding: utf-8 -*-

"""
Authors of original libkmahjongg in C++:
    Copyright (C) 1997 Mathias Mueller <in5y158@public.uni-hamburg.de>
    Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

this adapted python code:
    Copyright (C) 2008-2014 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from qt import QString, QSizeF, QSvgRenderer
from kde import KGlobal, KStandardDirs, KConfig
from log import logWarning, logException, m18n
from common import LIGHTSOURCES, Internal

TILESETVERSIONFORMAT = 1

class TileException(Exception):
    """will be thrown if the tileset cannot be loaded"""
    pass

def locateTileset(which):
    """locate the file with a tileset"""
    path = KStandardDirs.locate("kmahjonggtileset", QString(which))
    if path is None:
        logException(TileException('cannot find kmahjonggtileset %s' % \
                        (which)))
    return QString(path)

class Tileset(object):
    """represents a complete tileset"""
    # pylint: disable=too-many-instance-attributes
    catalogDefined = False
    __activeTileset = None

    @staticmethod
    def defineCatalog():
        """whatever this does"""
        if not Tileset.catalogDefined:
            KGlobal.dirs().addResourceType("kmahjonggtileset",
                "data", QString("kmahjongglib/tilesets"))
            KGlobal.locale().insertCatalog("libkmahjongglib")
            Tileset.catalogDefined = True

    @staticmethod
    def tilesAvailable():
        """returns all available tile sets"""
        Tileset.defineCatalog()
        tilesAvailableQ = KGlobal.dirs().findAllResources(
            "kmahjonggtileset", "*.desktop", KStandardDirs.Recursive)
        # now we have a list of full paths. Use the base name minus .desktop
        # put result into a set, avoiding duplicates
        tilesets = set(str(x).rsplit('/')[-1].split('.')[0] for x in tilesAvailableQ)
        if 'default' in tilesets:
            # we want default to be first in list
            sortedTilesets = ['default']
            sortedTilesets.extend(tilesets-set(['default']))
            tilesets = sortedTilesets
        for dontWant in ['alphabet', 'egypt']:
            if dontWant in tilesets:
                tilesets.remove(dontWant)
        return [Tileset(x) for x in tilesets]

    def __init__(self, desktopFileName=None):
        if desktopFileName is None:
            desktopFileName = 'default'
        self.tileSize = None
        self.faceSize = None
        self.__renderer = None
        self.__shadowOffsets = None
        self.defineCatalog()
        self.path = locateTileset(desktopFileName + '.desktop')
        if self.path.isEmpty():
            self.path = locateTileset('default.desktop')
            if self.path.isEmpty():
                directories = '\n\n' +'\n'.join(str(x) for x in KGlobal.dirs().resourceDirs("kmahjonggtileset"))
                logException(TileException(m18n( \
                'cannot find any tileset in the following directories, is libkmahjongg installed?') + directories))
            else:
                logWarning(m18n('cannot find tileset %1, using default', desktopFileName))
                self.desktopFileName = 'default'
        else:
            self.desktopFileName = desktopFileName
        self.darkenerAlpha = 120 if self.desktopFileName == 'jade' else 50
        tileconfig = KConfig(self.path, KConfig.SimpleConfig)
        group = tileconfig.group("KMahjonggTileset")

        self.name = group.readEntry("Name") or m18n("unknown tileset")
        self.author = group.readEntry("Author") or m18n("unknown author")
        self.description = group.readEntry("Description") or m18n("no description available")
        self.authorEmail = group.readEntry("AuthorEmail") or m18n("no E-Mail address available")

        #Version control
        tileversion = int(group.readEntry("VersionFormat")) or 0
        #Format is increased when we have incompatible changes, meaning that
        # older clients are not able to use the remaining information safely
        if tileversion > TILESETVERSIONFORMAT:
            logException(TileException('tileversion file / program: %d/%d' % \
                (tileversion, TILESETVERSIONFORMAT)))

        graphName = group.readEntry("FileName")
        self.__graphicspath = locateTileset(graphName)
        if self.__graphicspath.isEmpty():
            logException(TileException('cannot find kmahjongglib/tilesets/%s for %s' % \
                        (graphName, self.desktopFileName)))
        self.renderer() # now that we get the sizes from the svg, we need the renderer right away

        self.svgName = {'wn': 'WIND_1', 'ws': 'WIND_2', 'we': 'WIND_3', 'ww': 'WIND_4',
            'db': 'DRAGON_1', 'dg': 'DRAGON_2', 'dr': 'DRAGON_3'}
        for value in '123456789':
            self.svgName['s%s' % value] = 'ROD_%s' % value
            self.svgName['b%s' % value] = 'BAMBOO_%s' % value
            self.svgName['c%s' % value] = 'CHARACTER_%s' % value
        for idx, wind in enumerate('eswn'):
            self.svgName['f%s' % wind] = 'FLOWER_%d' % (idx + 1)
            self.svgName['y%s' % wind] = 'SEASON_%d' % (idx + 1)

    def __str__(self):
        return "tileset id=%d name=%s, name id=%d" % \
            (id(self), self.desktopFileName, id(self.desktopFileName))

    @staticmethod
    def activeTileset():
        prefName = Internal.Preferences.tilesetName
        if not Tileset.__activeTileset or Tileset.__activeTileset.desktopFileName != prefName:
            Tileset.__activeTileset = Tileset(prefName)
        return Tileset.__activeTileset

    def shadowWidth(self):
        """the size of border plus shadow"""
        return self.tileSize.width() - self.faceSize.width()

    def shadowHeight(self):
        """the size of border plus shadow"""
        return self.tileSize.height() - self.faceSize.height()

    def renderer(self):
        """initialise the svg renderer with the selected svg file"""
        if self.__renderer is None:
            self.__renderer = QSvgRenderer(self.__graphicspath)
            if not self.__renderer.isValid():
                logException(TileException( \
                m18n('file <filename>%1</filename> contains no valid SVG'), self.__graphicspath))
            distance = 0
            if self.desktopFileName == 'classic':
                distance = 2
            distanceSize = QSizeF(distance, distance)
            self.faceSize = self.__renderer.boundsOnElement('BAMBOO_1').size()+distanceSize
            self.tileSize = self.__renderer.boundsOnElement('TILE_2').size()+distanceSize
            if not Internal.scaleScene:
                self.faceSize /= 2
                self.tileSize /= 2
            shW = self.shadowWidth()
            shH = self.shadowHeight()
            self.__shadowOffsets = [[(-shW, 0), (0, 0), (0, shH), (-shH, shW)],
                [(0, 0), (shH, 0), (shW, shH), (0, shW)],
                [(0, -shH), (shH, -shW), (shW, 0), (0, 0)],
                [(-shW, -shH), (0, -shW), (0, 0), (-shH, 0)]]
        return self.__renderer

    def shadowOffsets(self, lightSource, rotation):
        """real offset of the shadow on the screen"""
        if not Internal.Preferences.showShadows:
            return (0, 0)
        lightSourceIndex = LIGHTSOURCES.index(lightSource)
        return self.__shadowOffsets[lightSourceIndex][rotation//90]

    def tileFaceRelation(self):
        """returns how much bigger the tile is than the face"""
        return self.tileSize.width() / self.faceSize.width(), self.tileSize.height() / self.faceSize.height()
