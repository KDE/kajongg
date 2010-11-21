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

from twisted.internet.defer import Deferred, succeed

from PyQt4.QtCore import QPropertyAnimation, QParallelAnimationGroup, \
    QAbstractAnimation, QEasingCurve, SIGNAL

from common import InternalParameters, PREF, Debug
from util import isAlive, debugMessage

class Animation(QPropertyAnimation):
    """a Qt4 animation with helper methods"""

    nextAnimations = []

    def __init__(self, target, propName, endValue, parent=None):
        QPropertyAnimation.__init__(self, target, propName, parent)
        if propName == 'rotation':
            # change direction if that makes the difference smaller
            currValue = target.rotation()
            if endValue - currValue > 180:
                self.setStartValue(currValue + 360)
            if currValue - endValue > 180:
                self.setStartValue(currValue - 360)
        self.setEndValue(endValue)
        duration = (99 - PREF.animationSpeed) * 100 / 4
        self.setDuration(duration)
        self.setEasingCurve(QEasingCurve.InOutQuad)
        target.queuedAnimations.append(self)
        Animation.nextAnimations.append(self)

    def ident(self):
        """the identifier to be used in debug messages"""
        pGroup = self.group()
        if pGroup:
            return '%d/A%d' % (id(pGroup)%10000, id(self) % 10000)
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

    running = [] # we need a reference to active animation groups
    current = None

    def __init__(self, parent=None):
        QParallelAnimationGroup.__init__(self, parent)
        assert Animation.nextAnimations
        self.animations = Animation.nextAnimations
        Animation.nextAnimations = []
        self.deferred = Deferred()
        self.steps = 0
        if ParallelAnimationGroup.current:
            if Debug.animation:
                debugMessage('Chaining Animation group %d to %d' % \
                        (id(self), id(ParallelAnimationGroup.current)))
            ParallelAnimationGroup.current.deferred.addCallback(self.start)
        else:
            self.start()
        ParallelAnimationGroup.running.append(self)
        ParallelAnimationGroup.current = self

    def updateCurrentTime(self, value):
        """count how many steps an animation does.
        This is only needed for debugging. Maybe we could
        remove this method from the object dict at runtime
        when not debugging?"""
        self.steps += 1
        QParallelAnimationGroup.updateCurrentTime(self, value)

    def start(self, dummyResults='DIREKT'):
        """start the animation, returning its deferred"""
        assert self.state() != QAbstractAnimation.Running
        for animation in self.animations:
            tile = animation.targetObject()
            tile.setActiveAnimation(animation)
            self.addAnimation(animation)
        self.connect(self, SIGNAL('finished()'), self.allFinished)
        InternalParameters.field.centralScene.focusRect.hide()
        scene = InternalParameters.field.centralScene
        scene.disableFocusRect = True
        QParallelAnimationGroup.start(self, QAbstractAnimation.DeleteWhenStopped)
        assert self.state() == QAbstractAnimation.Running
        if Debug.animation:
            debugMessage('Animation group %d started' % id(self))
        return succeed(None)

    def allFinished(self):
        """all animations have finished. Cleanup and callback"""
        self.fixAllBoards()
        if self == ParallelAnimationGroup.current:
            ParallelAnimationGroup.current = None
            ParallelAnimationGroup.running = []
        if Debug.animationSpeed:
            perSecond = self.steps * 1000.0 / self.duration()
            if perSecond < 50:
                debugMessage('%d steps for %d animations, %.1f/sec' % \
                (self.steps, len(self.children()), perSecond))
        # if we have a deferred, callback now
        assert self.deferred
        if Debug.animation:
            debugMessage('Animation group %d done' % id(self))
        if self.deferred:
            self.deferred.callback(None)

    def fixAllBoards(self):
        """set correct drawing order for all moved tiles"""
        for animation in self.children():
            tile = animation.targetObject()
            if tile:
                del tile.activeAnimation[animation.pName()]
                tile.setDrawingOrder()
        scene = InternalParameters.field.centralScene
        scene.disableFocusRect = False
        if isAlive(scene.focusBoard):
            scene.placeFocusRect()
        return

class Animated(object):
    """a helper class for moving tiles with or without animation"""
    def __init__(self, animateMe=True):
        self.__animateMe = animateMe
        self.prevAnimationSpeed = PREF.animationSpeed
        if not animateMe:
            PREF.animationSpeed = 99

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trback):
        """reset previous animation speed"""
        if not self.__animateMe:
            PREF.animationSpeed = self.prevAnimationSpeed

def afterCurrentAnimationDo(callback, *args, **kwargs):
    """a helper, delaying some action until all active
    animations have finished"""
    current = ParallelAnimationGroup.current
    if current:
        current.deferred.addCallback(callback, *args, **kwargs)
        if Debug.animation:
            debugMessage('after current animation %d do %s %s' % \
                (id(current), callback, ','.join(args) if args else ''))
    else:
        callback(None, *args, **kwargs)

def animate():
    """now run all prepared animations. Returns a Deferred
    so callers can attach callbacks to be executed when
    animation is over"""
    if Animation.nextAnimations:
        return ParallelAnimationGroup().deferred
    elif ParallelAnimationGroup.current:
        return ParallelAnimationGroup.current.deferred
    else:
        return succeed(None)
