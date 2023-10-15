# -*- coding: utf-8 -*-

"""
Authors of original libkmahjongg in C++:
    Copyright (C) 1997 Mathias Mueller <in5y158@public.uni-hamburg.de>
    Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

this adapted python code:
    Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

from typing import Optional, List, Tuple

from qt import QSizeF, QSvgRenderer
from log import logException, i18n
from mjresource import Resource

from common import LIGHTSOURCES, Internal
from wind import East, South, West, North


class Tileset(Resource):

    """represents a complete tileset"""

    resourceName : Optional[str] = 'tileset'
    configGroupName : str = 'KMahjonggTileset'
    cache = {}

    def __init__(self, name:Optional[str]=None) ->None:
        """continue __build"""
        super().__init__(name)
        self.tileSize:QSizeF
        self.faceSize:QSizeF
        self.__shadowOffsets:List[List[Tuple[int,int]]]
        self.darkenerAlpha = 120 if self.desktopFileName == 'jade' else 50

        graphName = str(self.group.readEntry("FileName"))
        self.graphicsPath = Tileset.locate(graphName)
        if not self.graphicsPath:
            logException(
                'cannot find kmahjongglib/tilesets/%s for %s' %
                (graphName, self.desktopFileName))
        self.renderer = QSvgRenderer(self.graphicsPath)
        if not self.renderer.isValid():
            logException(
                i18n(
                    'file <filename>%1</filename> contains no valid SVG',
                self.graphicsPath))
        distance = 0
        if self.desktopFileName == 'classic':
            distance = 2
        distanceSize = QSizeF(distance, distance)
        self.faceSize = self.renderer.boundsOnElement(
            'BAMBOO_1').size() + distanceSize
        self.tileSize = self.renderer.boundsOnElement(
            'TILE_2').size() + distanceSize
        shW = self.shadowWidth()
        shH = self.shadowHeight()
        self.__shadowOffsets = [
            [(-shW, 0), (0, 0), (0, shH), (-shH, shW)],
            [(0, 0), (shH, 0), (shW, shH), (0, shW)],
            [(0, -shH), (shH, -shW), (shW, 0), (0, 0)],
            [(-shW, -shH), (0, -shW), (0, 0), (-shH, 0)]]

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

    def __str__(self) ->str:
        return "tileset id=%d name=%s, name id=%d" % \
            (id(self), self.desktopFileName, id(self.desktopFileName))

    @staticmethod
    def current() ->'Tileset':
        """the currently wanted tileset. If not yet defined, do so"""
        assert Internal.Preferences
        return Tileset(str(Internal.Preferences.tilesetName))

    def shadowWidth(self) ->int:
        """the size of border plus shadow"""
        return int(self.tileSize.width() - self.faceSize.width())

    def shadowHeight(self) ->int:
        """the size of border plus shadow"""
        return int(self.tileSize.height() - self.faceSize.height())

    def shadowOffsets(self, lightSource:str, rotation:int) ->Tuple[int, int]:
        """real offset of the shadow on the screen"""
        assert Internal.Preferences
        if not Internal.Preferences.showShadows:
            return (0, 0)
        lightSourceIndex = LIGHTSOURCES.index(lightSource)
        return self.__shadowOffsets[lightSourceIndex][rotation // 90]

    def tileFaceRelation(self) ->Tuple[float,float]:
        """return how much bigger the tile is than the face"""
        return (self.tileSize.width() / self.faceSize.width(),
                self.tileSize.height() / self.faceSize.height())
