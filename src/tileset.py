# -*- coding: utf-8 -*-

"""
Authors of original libkmahjongg in C++:
    Copyright (C) 1997 Mathias Mueller <in5y158@public.uni-hamburg.de>
    Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

this adapted python code:
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

import os
from qt import QSizeF, QSvgRenderer, QStandardPaths
from kde import KConfig
from log import logWarning, logException, m18n
from common import LIGHTSOURCES, Internal
from wind import East, South, West, North

TILESETVERSIONFORMAT = 1


class TileException(Exception):

    """will be thrown if the tileset cannot be loaded"""
    pass


class Tileset:

    """represents a complete tileset"""
    # pylint: disable=too-many-instance-attributes

    cache = {}

    def __new__(cls, name):
        return cls.cache.get(name) or cls.cache.get(cls.__name(name)) or cls.__build(name)

    @staticmethod
    def __directories():
        """where to look for backgrounds"""
        return QStandardPaths.locateAll(
            QStandardPaths.GenericDataLocation,
            'kmahjongglib/tilesets', QStandardPaths.LocateDirectory)

    @staticmethod
    def locate(which):
        """locate the file with a tileset"""
        for directory in Tileset.__directories():
            path = os.path.join(directory, which)
            if os.path.exists(path):
                return path
        logException(TileException('cannot find kmahjonggtileset %s' %
                                   (which)))

    @staticmethod
    def loadAll():
        """loads all available tile sets into cache"""
        tilesetDirectories = Tileset.__directories()
        for directory in tilesetDirectories:
            for name in os.listdir(directory):
                if name.endswith('.desktop'):
                    if not name.endswith('alphabet.desktop') and not name.endswith('egypt.desktop'):
                        Tileset(os.path.join(directory, name))

    @classmethod
    def available(cls):
        """ready for the selector dialog, default first"""
        cls.loadAll()
        return sorted(set(cls.cache.values()), key=lambda x: x.desktopFileName != 'default')

    @staticmethod
    def __noTilesetFound():
        """No tilesets found"""
        directories = '\n\n' + '\n'.join(Tileset.__directories())
        logException(
            TileException(m18n(
                'cannot find any tileset in the following directories, '
                'is libkmahjongg installed?') + directories))

    @staticmethod
    def __name(path):
        """extract the name from path: this is the filename minus the .desktop ending"""
        return os.path.split(path)[1].replace('.desktop', '')

    @classmethod
    def __build(cls, name):
        """build a new Tileset. name is either a full file path or a desktop tileset name. None stands for 'default'."""
        result = object.__new__(cls)
        if os.path.exists(name):
            result.path = name
            result.desktopFileName = cls.__name(name)
        else:
            result.desktopFileName = name or 'default'
            result.path = cls.locate(result.desktopFileName + '.desktop')
            if not result.path:
                result.path = cls.locate('default.desktop')
                result.desktopFileName = 'default'
                if not result.path:
                    cls.__noTilesetFound()
                else:
                    logWarning(m18n('cannot find tileset %1, using default', name))

        cls.cache[result.desktopFileName] = result
        cls.cache[result.path] = result
        return result

    def __init__(self, dummyName):
        """continue __build"""
        self.tileSize = None
        self.faceSize = None
        self.__renderer = None
        self.__shadowOffsets = None
        self.darkenerAlpha = 120 if self.desktopFileName == 'jade' else 50
        tileconfig = KConfig(self.path)
        group = tileconfig.group("KMahjonggTileset")

        self.name = group.readEntry("Name") or m18n("unknown tileset")
        self.author = group.readEntry("Author") or m18n("unknown author")
        self.description = group.readEntry(
            "Description") or m18n(
                "no description available")
        self.authorEmail = group.readEntry(
            "AuthorEmail") or m18n(
                "no E-Mail address available")

        # Version control
        tileversion = group.readInteger("VersionFormat", default=0)
        # Format is increased when we have incompatible changes, meaning that
        # older clients are not able to use the remaining information safely
        if tileversion > TILESETVERSIONFORMAT:
            logException(TileException('tileversion file / program: %d/%d' %
                                       (tileversion, TILESETVERSIONFORMAT)))

        graphName = group.readEntry("FileName")
        self.graphicsPath = Tileset.locate(graphName)
        if not self.graphicsPath:
            logException(
                TileException('cannot find kmahjongglib/tilesets/%s for %s' %
                              (graphName, self.desktopFileName)))
        self.renderer()
        # now that we get the sizes from the svg, we need the
        # renderer right away

        self.svgName = {
            'wn': North.svgName, 'ws': South.svgName, 'we': East.svgName, 'ww': West.svgName,
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
    def current():
        """the currently wanted tileset. If not yet defined, do so"""
        return Tileset(Internal.Preferences.tilesetName)

    def shadowWidth(self):
        """the size of border plus shadow"""
        return self.tileSize.width() - self.faceSize.width()

    def shadowHeight(self):
        """the size of border plus shadow"""
        return self.tileSize.height() - self.faceSize.height()

    def renderer(self):
        """initialise the svg renderer with the selected svg file"""
        if self.__renderer is None:
            self.__renderer = QSvgRenderer(self.graphicsPath)
            if not self.__renderer.isValid():
                logException(TileException(
                    m18n(
                        'file <filename>%1</filename> contains no valid SVG'),
                    self.graphicsPath))
            distance = 0
            if self.desktopFileName == 'classic':
                distance = 2
            distanceSize = QSizeF(distance, distance)
            self.faceSize = self.__renderer.boundsOnElement(
                'BAMBOO_1').size() + distanceSize
            self.tileSize = self.__renderer.boundsOnElement(
                'TILE_2').size() + distanceSize
            if not Internal.scaleScene:
                self.faceSize /= 2
                self.tileSize /= 2
            shW = self.shadowWidth()
            shH = self.shadowHeight()
            self.__shadowOffsets = [
                [(-shW, 0), (0, 0), (0, shH), (-shH, shW)],
                [(0, 0), (shH, 0), (shW, shH), (0, shW)],
                [(0, -shH), (shH, -shW), (shW, 0), (0, 0)],
                [(-shW, -shH), (0, -shW), (0, 0), (-shH, 0)]]
        return self.__renderer

    def shadowOffsets(self, lightSource, rotation):
        """real offset of the shadow on the screen"""
        if not Internal.Preferences.showShadows:
            return (0, 0)
        lightSourceIndex = LIGHTSOURCES.index(lightSource)
        return self.__shadowOffsets[lightSourceIndex][rotation // 90]

    def tileFaceRelation(self):
        """returns how much bigger the tile is than the face"""
        return (self.tileSize.width() / self.faceSize.width(),
                self.tileSize.height() / self.faceSize.height())
