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

from qt import QSizeF, QSvgRenderer
from log import logException, i18n
from mjresource import Resource

from common import LIGHTSOURCES, Internal
from wind import East, South, West, North


class Tileset(Resource):

    """represents a complete tileset"""
    # pylint: disable=too-many-instance-attributes

    resourceName = 'tileset'
    configGroupName = 'KMahjonggTileset'
    cache = {}

    def __init__(self, name):
        """continue __build"""
        super(Tileset, self).__init__(name)
        self.tileSize = None
        self.faceSize = None
        self.__renderer = None
        self.__shadowOffsets = None
        self.darkenerAlpha = 120 if self.desktopFileName == 'jade' else 50

        graphName = self.group.readEntry("FileName")
        self.graphicsPath = Tileset.locate(graphName)
        if not self.graphicsPath:
            logException(
                'cannot find kmahjongglib/tilesets/%s for %s' %
                (graphName, self.desktopFileName))
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
                logException(
                    i18n(
                        'file <filename>%1</filename> contains no valid SVG'),
                    self.graphicsPath)
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
