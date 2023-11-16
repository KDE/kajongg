# -*- coding: utf-8 -*-
"""
Copyright (C) 2010-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

partially based on C++ code from:
Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

SPDX-License-Identifier: GPL-2.0

"""

import os

from qt import uic, QStandardPaths
from qt import QComboBox, QTableView, QSizePolicy, QAbstractItemView
from qt import QTransform

from kde import KIcon

from log import i18n


def loadUi(base):
    """load the ui file for class base, deriving the file name from
    the class name"""
    name = base.__class__.__name__.lower() + '.ui'
    if os.path.exists(name):
        directory = os.getcwd()
    elif os.path.exists('share/kajongg/{}'.format(name)):
        directory = 'share/kajongg'
    else:
        directory = os.path.dirname(QStandardPaths.locate(QStandardPaths.AppDataLocation, name))
    uic.loadUi(os.path.join(directory, name), base)


class MJTableView(QTableView):

    """a QTableView with app specific defaults"""

    def __init__(self, parent=None):
        QTableView.__init__(self, parent)
        self.horizontalHeader().setStretchLastSection(True)
        self.setAlternatingRowColors(True)
        pol = QSizePolicy()
        pol.setHorizontalPolicy(QSizePolicy.Expanding)
        pol.setVerticalPolicy(QSizePolicy.Expanding)
        self.setSizePolicy(pol)
        self.verticalHeader().hide()

    def initView(self):
        """set some app specific defaults"""
        self.selectRow(0)
        self.resizeColumnsToContents()
        self.setSelectionBehavior(QAbstractItemView.SelectRows)


class ListComboBox(QComboBox):

    """easy to use with a python list. The elements must have an
    attribute 'name'."""

    def __init__(self, items, parent=None):
        QComboBox.__init__(self, parent)
        self.items = items

    @property
    def items(self):
        """combo box items"""
        return [self.itemData(idx) for idx in range(self.count())]

    @items.setter
    def items(self, items):
        """combo box items"""
        self.clear()
        if items:
            for item in items:
                self.addItem(i18n(item.name), item)

    def findItem(self, search):
        """return the index or -1 of not found """
        for idx, item in enumerate(self.items):
            if item == search:
                return idx
        return -1

    def names(self):
        """a list with all item names"""
        return list(x.name for x in self.items)

    @property
    def current(self):
        """current item"""
        return self.itemData(self.currentIndex())

    @current.setter
    def current(self, item):
        """current item"""
        newIdx = self.findItem(item)
        if newIdx < 0:
            raise IndexError('%s not found in ListComboBox' % item.name)
        self.setCurrentIndex(newIdx)


class Painter:

    """a helper class for painting: saves/restores painter"""

    def __init__(self, painter):
        """painter is the painter to be saved/restored"""
        self.painter = painter

    def __enter__(self):
        self.painter.save()
        return self

    def __exit__(self, exc_type, exc_value, trback):
        """now check time passed"""
        self.painter.restore()


class BlockSignals:

    """a helper class for temporary blocking of Qt signals"""

    def __init__(self, qobjects):
        self.qobjects = qobjects

    def __enter__(self) ->None:
        for obj in self.qobjects:
            obj.blockSignals(True)

    def __exit__(self, exc_type, exc_value, trback):
        for obj in self.qobjects:
            obj.blockSignals(False)


def decorateWindow(window, name=''):
    """standard Kajongg window title and icon"""
    if name:
        window.setWindowTitle('{} – {}'.format(name, i18n('Kajongg')))
    else:
        window.setWindowTitle(i18n('Kajongg'))
    window.setWindowIcon(KIcon('kajongg'))


def rotateCenter(item, angle):
    """rotates a QGraphicsItem around its center
    rotateCenter and sceneRotation could be a mixin class but there are so many
    classes needing this. If and when more QGraphicsItem* classes are changed
    to QGraphicsObject, those could be moved to GraphicsObject(QGraphicsObject)"""
    center = item.boundingRect().center()
    centerX, centerY = center.x() * item.scale(), center.y() * item.scale()
    item.setTransform(QTransform().translate(
        centerX, centerY).rotate(angle).translate(-centerX, -centerY))

def sceneRotation(item):
    """the combined rotation of item and all parents in degrees: 0,90,180 or 270"""
    transform = item.sceneTransform()
    matrix = (
        round(transform.m11()),
        round(transform.m12()),
        round(transform.m21()),
        round(transform.m22()))
    matrix = tuple(1 if x > 0 else -1 if x < 0 else 0 for x in matrix)
    rotations = {(0, 0, 0, 0): 0, (1, 0, 0, 1): 0, (
        0, 1, -1, 0): 90, (-1, 0, 0, -1): 180, (0, -1, 1, 0): 270}
    if matrix not in rotations:
        raise ValueError('matrix unknown:%s' % str(matrix))
    return rotations[matrix]
