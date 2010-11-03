# -*- coding: utf-8 -*-

"""
 (C) 2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from PyQt4.QtCore import QPropertyAnimation, QParallelAnimationGroup, \
    QSequentialAnimationGroup, QAbstractAnimation, QEasingCurve,  \
    SIGNAL

from common import InternalParameters, PREF, ZValues
from util import isAlive

class Animation(QPropertyAnimation):
    """a Qt4 animation with helper methods"""
    def __init__(self, target, propName, endValue, parent=None):
        QPropertyAnimation.__init__(self, target, propName, parent)
        self.setEndValue(endValue)
        duration = (99 - PREF.animationSpeed) * 100 / 4
        self.setDuration(duration)
        self.setEasingCurve(QEasingCurve.InOutQuad)
        target.queuedAnimations.append(self)

    def hasWaiter(self):
        """returns True if somebody wants to be called back after we are done"""
        pGroup = self.group()
        if pGroup:
            return bool(pGroup.group().deferred)
        return False

    def ident(self):
        """the identifier to be used in debug messages"""
        pGroup = self.group()
        if pGroup:
            sGroup = pGroup.group()
            groupIdx = sGroup.children().index(pGroup)
            return '%d/%d/A%d' % (id(sGroup)%10000, groupIdx, id(self) % 10000)
        else:
            return 'A%d' % (id(self) % 10000)

    def pName(self):
        """return self.propertyName() as a python string"""
        return str(self.propertyName())

    def unpackValue(self, qvariant):
        """get the wanted value from the QVariant"""
        pName = self.pName()
        if pName == 'pos':
            return qvariant.toPointF()
        if pName == 'rotation':
            return qvariant.toInt()[0]
        elif pName == 'scale':
            return qvariant.toFloat()[0]

    def formatValue(self, qvariant):
        """string format the wanted value from qvariant"""
        value = self.unpackValue(qvariant)
        pName = self.pName()
        if pName == 'pos':
            return '%.1f/%.1f' % (value.x(), value.y())
        if pName == 'rotation':
            return '%d' % value
        if pName == 'scale':
            return '%.2f' % value

    def __str__(self):
        """for debug messages"""
        pName = self.pName()
        tile = self.targetObject()
        return '%s: %s->%s for %s' % (self.ident(), pName, self.formatValue(self.endValue()), str(tile))

class ParallelAnimationGroup(QParallelAnimationGroup):
    """override __init__"""
    def __init__(self, animations, parent=None):
        QParallelAnimationGroup.__init__(self, parent)
        for animation in animations:
            self.addAnimation(animation)

class SequentialAnimationGroup(QSequentialAnimationGroup):
    """the Qt4 class with helper methods and a deferred callback.
    The structure to be expected is: The SequentialAnimationGroup
    holds only ParallelAnimationsGroups which hold only Animation items
    """
    def __init__(self, animations, deferred, parent=None):
        QSequentialAnimationGroup.__init__(self, parent)
        assert animations
        self.deferred = deferred
        for group in animations:
            self.addAnimation(group)
            for animation in group.children():
                tile = animation.targetObject()
                tile.queuedAnimations = []
                tile.setZValue(tile.zValue() + ZValues.moving)
                propName = animation.pName()
                assert propName not in tile.activeAnimation or not isAlive(tile.activeAnimation[propName])
                tile.activeAnimation[propName] = animation
        self.connect(self, SIGNAL('finished()'), self.allFinished)
        InternalParameters.field.centralScene.focusRect.hide()
        if self.deferred:
            # we have a waiter: Delete finished animations, making
            # it impossible that the next player action changes
            # existing animations
            opt = QAbstractAnimation.DeleteWhenStopped
        else:
            # such animations can be changed midway, like
            # moving a tile from player to player to player in
            # a scoring game
            opt = QAbstractAnimation.KeepWhenStopped
        scene = InternalParameters.field.centralScene
        scene.disableFocusRect = True
        self.start(opt)
        assert self.state() == QAbstractAnimation.Running

    def allFinished(self):
        """all animations have finished. Cleanup and callback"""
        self.fixAllBoards()
        # if we have a deferred, callback now
        if self.deferred:
            self.deferred.callback('done')

    def fixAllBoards(self):
        """set correct drawing order for all changed boards"""
        animations = sum([x.children() for x in self.children()], [])
        for animation in animations:
            tile = animation.targetObject()
            if tile:
                del tile.activeAnimation[animation.pName()]
                tile.setDrawingOrder()
        scene = InternalParameters.field.centralScene
        scene.disableFocusRect = False
        if isAlive(scene.focusBoard):
            scene.placeFocusRect()
        return
