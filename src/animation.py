# -*- coding: utf-8 -*-

"""
Copyright (C) 2010-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

import functools
import types

from typing import List, Any, Optional, Dict, Union, TYPE_CHECKING, Callable, Type, cast

from twisted.internet.defer import Deferred, succeed, fail

from qt import QPropertyAnimation, QParallelAnimationGroup, \
    QAbstractAnimation, QEasingCurve
from qt import Property, QGraphicsObject, QGraphicsItem, QPointF, QObject

from common import Internal, Debug, isAlive, ReprMixin, id4
from log import logDebug, logException

if TYPE_CHECKING:
    from qt import QGraphicsScene

PropertyType = Union[QPointF,int,float]

class Animation(QPropertyAnimation, ReprMixin):

    """a Qt animation with helper methods"""

    nextAnimations : List['Animation'] = []
    clsUid = 0

    def __init__(self, graphicsObject:'AnimatedMixin', propName:str,
        endValue:PropertyType, parent:Optional['QObject']=None) ->None:
        self.debug = graphicsObject.debug_name() in Debug.animation or Debug.animation == 'all'
        self.debug |= 'T{}t'.format(id4(graphicsObject)) in Debug.animation
        Animation.clsUid += 1
        self.uid = Animation.clsUid
        assert isinstance(graphicsObject, QObject)
        QPropertyAnimation.__init__(self, graphicsObject, propName.encode(), parent)
        QPropertyAnimation.setEndValue(self, endValue)
        assert Internal.Preferences
        duration = Internal.Preferences.animationDuration()
        self.setDuration(duration)
        self.setEasingCurve(QEasingCurve.InOutQuad)
        graphicsObject.queuedAnimations.append(self)
        Animation.nextAnimations.append(self)
        if self.debug:
            oldAnimation = graphicsObject.activeAnimation.get(propName, None)
            if isAlive(oldAnimation):
                assert isinstance(oldAnimation, Animation)
                logDebug(
                    'new Animation(%s) (after %s is done)' %
                    (self, oldAnimation.ident()))
            else:
                logDebug('Animation(%s)' % self)

    def setEndValue(self, endValue:PropertyType) ->None:
        """wrapper with debugging code"""
        graphicsObject = self.targetObject()
        if not isAlive(graphicsObject):
            # may happen when aborting a game because animations are cancelled first,
            # before the last move from server is executed
            return
        if cast('AnimatedMixin', graphicsObject).debug_name() in Debug.animation or Debug.animation == 'all':
            logDebug(
                '%s: change endValue for %s: %s->%s  %s' % (
                    self.ident(), self.pName(),
                    self.formatValue(self.endValue()),
                    self.formatValue(endValue), graphicsObject))
        QPropertyAnimation.setEndValue(self, endValue)

    def ident(self) ->str:
        """the identifier to be used in debug messages"""
        pGroup = self.group() if isAlive(self) else 'notAlive'
        if pGroup or not isAlive(self):
            return '%s/A%s' % (pGroup, id4(self))
        return 'A%s-%s' % (id4(self), cast('AnimatedMixin', self.targetObject()).debug_name())

    def pName(self) ->str:
        """
        Return self.propertyName() as a python string.

        @return: C{str}
        """
        if not isAlive(self):
            return 'notAlive'
        return bytes(self.propertyName()).decode()

    def formatValue(self, value:PropertyType) ->str:
        """string format the wanted value from qvariant"""
        pName = self.pName()
        if pName == 'pos':
            assert isinstance(value, QPointF)
            return '%.0f/%.0f' % (value.x(), value.y())
        if pName == 'rotation':
            return '%d' % value
        if pName == 'scale':
            return '%.2f' % value
        return 'formatValue: unexpected {}={}'.format(pName, value)

    def __str__(self) ->str:
        """for debug messages"""
        if isAlive(self) and isAlive(self.targetObject()):
            currentValue = getattr(self.targetObject(), self.pName())
            endValue = self.endValue()
            targetObject:Union[QObject, str] = self.targetObject()
        else:
            currentValue = 'notAlive'
            endValue = 'notAlive'
            targetObject = 'notAlive'
        return '%s %s: %s->%s for %s duration=%dms' % (
            self.ident(), self.pName(),
            self.formatValue(currentValue),
            self.formatValue(endValue),
            targetObject,
            self.duration())

    @staticmethod
    def removeImmediateAnimations() ->None:
        """execute and remove immediate moves from the list
        We do not animate objects if
             - we are in a graphics object drag/drop operation
             - the user disabled animation
             - there are too many animations in the group so it would be too slow
             - the object has duration 0
        """
        if Animation.nextAnimations:
            needRefresh = False
            assert Internal.mainWindow
            assert Internal.Preferences
            shortcutAll = (Internal.scene is None
                           or Internal.mainWindow.centralView.dragObject
                           or Internal.Preferences.animationSpeed == 99
                           or len(Animation.nextAnimations) > 1000)
                    # change 1000 to 100 if we do not want to animate shuffling and
                    # initial deal
            for animation in Animation.nextAnimations[:]:
                if shortcutAll or animation.duration() == 0:
                    cast(AnimatedMixin, animation.targetObject()).shortcutAnimation(animation)
                    Animation.nextAnimations.remove(animation)
                    needRefresh = True
            if needRefresh and Internal.scene:
                Internal.scene.focusRect.refresh()


class ParallelAnimationGroup(QParallelAnimationGroup, ReprMixin):

    """
    current is the currently executed group
    doAfter is a list of Deferred to be called when this group
    is done. If another group is chained to this one, transfer
    doAfter to that other group.
    """

    running : List['ParallelAnimationGroup'] = []  # we need a reference to active animation groups
    current = None
    clsUid = 0
    def __init__(self, animations:List[Animation], parent:Optional['QObject']=None) ->None:
        QParallelAnimationGroup.__init__(self, parent)
        self.animations = animations
        self.uid = ParallelAnimationGroup.clsUid
        ParallelAnimationGroup.clsUid += 1
        self.deferred:Deferred = Deferred()
        self.deferred.addErrback(logException)
        self.steps = 0
        self.debug = any(x.debug for x in self.animations)
        self.debug |= 'G{}g'.format(id4(self)) in Debug.animation
        self.doAfter:List[Deferred] = []
        if ParallelAnimationGroup.current:
            if self.debug or ParallelAnimationGroup.current.debug:
                logDebug('Chaining Animation group G%s to G%s' %
                         (id4(self), ParallelAnimationGroup.current))
            self.doAfter = ParallelAnimationGroup.current.doAfter
            ParallelAnimationGroup.current.doAfter = []
            ParallelAnimationGroup.current.deferred.addCallback(self.start).addErrback(logException)
        else:
            self.start()
        ParallelAnimationGroup.running.append(self)
        ParallelAnimationGroup.current = self
        self.stateChanged.connect(self.showState)

    @staticmethod
    def cancelAll() ->None:
        """cancel all animations"""
        if Debug.quit:
            logDebug('Cancelling all animations')
        for group in ParallelAnimationGroup.running:
            if isAlive(group):
                group.clear()

    def showState(self, newState:int, oldState:int) ->None:
        """override Qt method"""
        if self.debug:
            logDebug('G{}: {} -> {} isAlive:{}'.format(
                self.uid, self.stateName(oldState), self.stateName(newState), isAlive(self)))

    def updateCurrentTime(self, value:int) ->None:
        """count how many steps an animation does."""
        self.steps += 1
        if self.steps % 50 == 0:
            # periodically check if the board still exists.
            # if not (game end), we do not want to go on
            for animation in self.animations:
                graphicsObject = cast(AnimatedMixin, animation.targetObject())
                if hasattr(graphicsObject, 'board') and not isAlive(graphicsObject.board):
                    graphicsObject.clearActiveAnimation(animation)
                    self.removeAnimation(animation)
        QParallelAnimationGroup.updateCurrentTime(self, value)

    def start(self, unusedResults:str='DIREKT') ->Deferred:  # type: ignore[override]
        """start the animation, returning its deferred"""
        if not isAlive(self):
            return fail()
        assert self.state() != QAbstractAnimation.State.Running
        for animation in self.animations:
            graphicsObject = animation.targetObject()
 #            graphicsObject = cast(AnimatedMixin, animation.targetObject())
            if not isAlive(animation) or not isAlive(graphicsObject):
                return fail()
            animatedObject = cast(AnimatedMixin, graphicsObject)
            animatedObject.setActiveAnimation(animation)
            self.addAnimation(animation)
            propName = animation.pName()
            animation.setStartValue(animatedObject.getValue(propName))
            if propName == 'rotation':
                # change direction if that makes the difference smaller
                endValue = animation.endValue()
                currValue = animatedObject.rotation
                if endValue - currValue > 180:
                    animation.setStartValue(currValue + 360)
                if currValue - endValue > 180:
                    animation.setStartValue(currValue - 360)
        for animation in self.animations:
            animation.targetObject().setDrawingOrder()  # type:ignore[attr-defined]
        self.finished.connect(self.allFinished)
        scene = Internal.scene
        assert scene
        scene.focusRect.hide()
        QParallelAnimationGroup.start(
            self,
            QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        if self.debug:
            assert Internal.Preferences
            logDebug('%s started with speed %d (%s)' % (
                self, int(Internal.Preferences.animationSpeed),
                ','.join('A%s' % id4(x) for x in self.animations)))
        return succeed(None).addErrback(logException)

    def allFinished(self) ->None:
        """all animations have finished. Cleanup and callback"""
        self.fixAllBoards()
        if self == ParallelAnimationGroup.current:
            ParallelAnimationGroup.current = None
            ParallelAnimationGroup.running = []
        if Debug.animationSpeed and self.duration():
            perSecond = self.steps * 1000.0 / self.duration()
            if perSecond < 50:
                logDebug('%d steps for %d animations, %.1f/sec' %
                         (self.steps, len(self.children()), perSecond))
        # if we have a deferred, callback now
        assert self.deferred
        if self.debug:
            logDebug('Done: {}'.format(self))
        if self.deferred:
            self.deferred.callback(None)
        for after in self.doAfter:
            after.callback(None)

    def fixAllBoards(self) ->None:
        """set correct drawing order for all moved graphics objects"""
        for animation in self.children():
            graphicsObject = animation.targetObject()  # type:ignore[attr-defined]
            if graphicsObject:
                graphicsObject.clearActiveAnimation(animation)
        if Internal.scene:
            Internal.scene.focusRect.refresh()

    def stateName(self, state:Any=None) ->str:
        """for debug output"""
        if not isAlive(self):
            return 'not alive'
        if state is None:
            state = self.state()
        if state == QAbstractAnimation.State.Stopped:
            return 'stopped'
        if state == QAbstractAnimation.State.Running:
            return 'running'
        return 'unknown state:{}'.format(state)

    def __str__(self) ->str:
        """for debugging"""
        return 'G{}({}:{})'.format(self.uid, len(self.animations), self.stateName())


class AnimatedMixin:
    """for UITile and WindDisc"""

    def __init__(self) ->None:
        super().__init__()
        self.activeAnimation:Dict[str, Animation]  = {}  # key is the property name
        self.queuedAnimations:List[Animation] = []

    def _get_pos(self) ->QPointF:
        """getter for property pos"""
        return QGraphicsObject.pos(cast(QGraphicsItem, self))

    def _set_pos(self, pos:QPointF) ->None:
        """setter for property pos"""
        QGraphicsObject.setPos(cast(QGraphicsItem, self), pos)

    pos = Property(QPointF, fget=_get_pos, fset=_set_pos)

    def _get_scale(self) ->float:
        """getter for property scale"""
        return QGraphicsObject.scale(cast(QGraphicsItem, self))

    def _set_scale(self, scale:float) ->None:
        """setter for property scale"""
        QGraphicsObject.setScale(cast(QGraphicsItem, self), scale)

    scale = Property(float, fget=_get_scale, fset=_set_scale)

    def _get_rotation(self) ->float:
        """getter for property rotation"""
        return QGraphicsObject.rotation(cast(QGraphicsItem, self))

    def _set_rotation(self, rotation:float) ->None:
        """setter for property rotation"""
        QGraphicsObject.setRotation(cast(QGraphicsItem, self), rotation)

    rotation = Property(float, fget=_get_rotation, fset=_set_rotation)

    def queuedAnimation(self, propertyName:str) ->Optional['Animation']:
        """return the last queued animation for this graphics object and propertyName"""
        for item in reversed(self.queuedAnimations):
            if item.pName() == propertyName:
                return item
        return None

    def debug_name(self) ->str:
        """for mypy"""
        return ''

#    this results in player names appearing BELOW their walls
#    def setDrawingOrder(self) ->None:
#        """for mypy"""
#

    def shortcutAnimation(self, animation:'Animation') ->None:
        """directly set the end value of the animation"""
        if animation.debug:
            logDebug('shortcut {}: UTile {}: clear queuedAnimations'.format(animation, self.debug_name()))
        setattr(self, animation.pName(), animation.endValue())
        self.queuedAnimations = []
        self.setDrawingOrder()  # type:ignore[attr-defined] # TODO: mypy protocol?

    def getValue(self, pName:str) ->PropertyType:
        """get a current property value"""
        return {'pos': self.pos, 'rotation': self.rotation,
                'scale': self.scale}[pName]

    def setActiveAnimation(self, animation:'Animation') ->None:
        """the graphics object knows which of its properties are currently animated"""
        self.queuedAnimations = []
        propName = animation.pName()
        if self.debug_name() in Debug.animation:
            oldAnimation = self.activeAnimation.get(propName, None)
            if not isAlive(oldAnimation):
                oldAnimation = None
            if oldAnimation:
                logDebug('**** setActiveAnimation {} {}: {} OVERRIDES {}'.format(
                    self.debug_name(), propName, animation, oldAnimation))
            else:
                logDebug('setActiveAnimation {} {}: set {}'.format(self.debug_name(), propName, animation))
        self.activeAnimation[propName] = animation
        self.setCacheMode(QGraphicsItem.CacheMode.ItemCoordinateCache)  # type: ignore[attr-defined]

    def clearActiveAnimation(self, animation:'Animation') ->None:
        """an animation for this graphics object has ended.
        Finalize graphics object in its new position"""
        del self.activeAnimation[animation.pName()]
        if self.debug_name() in Debug.animation:
            logDebug('UITile {}: clear activeAnimation_{}'.format(self.debug_name(), animation.pName()))
        self.setDrawingOrder()  # type:ignore[attr-defined] # TODO: mypy protocol?
        if not self.activeAnimation:
            self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)  # type: ignore[attr-defined]
            self.update()  # type: ignore[attr-defined]

    def setupAnimations(self) ->None:
        """move the item to its new place. This puts new Animation
        objects into the queue to be animated by calling animate()"""
        for pName, newValue in self.moveDict().items():  # type: ignore[attr-defined]
            if self.scene() != Internal.scene:  # type: ignore[attr-defined]
                # not part of the playing scene, like tiles in tilesetselector
                setattr(self, pName, newValue)
                continue
            animation = self.queuedAnimation(pName)
            if animation:
                curValue = animation.endValue()
                if curValue != newValue:
                    # change a queued animation
                    if self.debug_name() in Debug.animation:
                        logDebug('setEndValue for {}: {}: {}->{}'.format(
                            animation, pName, animation.formatValue(curValue), animation.formatValue(newValue)))
                    animation.setEndValue(newValue)
            else:
                animation = self.activeAnimation.get(pName, None)
                if isAlive(animation):
                    assert isinstance(animation, Animation)
                    curValue = animation.endValue()
                else:
                    curValue = self.getValue(pName)
                if pName != 'scale' or abs(curValue - newValue) > 0.00001:
                    # ignore rounding differences for scale
                    if curValue != newValue:
                        Animation(self, pName, newValue)


class AnimationSpeed:

    """a helper class for moving graphics with a given speed. 99=immediate."""

    def __init__(self, speed:Optional[int]=None) ->None:
        if speed is None:
            speed = 99
        if Internal.Preferences:
            self.__speed = speed
            self.prevAnimationSpeed = Internal.Preferences.animationSpeed
            if Internal.Preferences.animationSpeed != speed:
                Internal.Preferences.animationSpeed = speed
                if Debug.animationSpeed:
                    logDebug('AnimationSpeed sets speed %d' % speed)

    def __enter__(self) ->'AnimationSpeed':
        return self

    def __exit__(self, exc_type:Type[Exception], exc_value:Exception, trback:Any) ->None:
        """reset previous animation speed"""
        if Internal.Preferences:
            if self.__speed < 99:
                animate()
            if Internal.Preferences.animationSpeed != self.prevAnimationSpeed:
                if Debug.animationSpeed:
                    logDebug('AnimationSpeed restores speed {} to {}'.format(
                        Internal.Preferences.animationSpeed, self.prevAnimationSpeed))
                Internal.Preferences.animationSpeed = self.prevAnimationSpeed


def afterQueuedAnimations(doAfter:Deferred) ->Callable:
    """A decorator"""

    @functools.wraps(doAfter)  # type:ignore[arg-type]
    def doAfterQueuedAnimations(*args:Any, **kwargs:Any) ->None:
        """do this after all queued animations have finished"""
        method = types.MethodType(doAfter, args[0])  # type:ignore[arg-type]
        args = args[1:]
        varnames = doAfter.__code__.co_varnames  # type:ignore[attr-defined]
        assert varnames[1] in ('deferredResult', 'unusedDeferredResult'), \
            '{} passed {} instead of deferredResult'.format(
                doAfter.__qualname__, varnames[1])  # type:ignore[attr-defined]
        animateAndDo(method, *args, **kwargs)

    return doAfterQueuedAnimations


def animate() ->Deferred:
    """now run all prepared animations. Returns a Deferred
        so callers can attach callbacks to be executed when
        animation is over.
    """
    if Animation.nextAnimations:
        Animation.removeImmediateAnimations()
        animations = Animation.nextAnimations
        if animations:
            Animation.nextAnimations = []
            return ParallelAnimationGroup(animations).deferred
    elif ParallelAnimationGroup.current:
        return ParallelAnimationGroup.current.deferred
    return succeed(None).addErrback(logException)


def doCallbackWithSpeed(result:Any, speed:int, callback:Callable, *args:Any, **kwargs:Any) ->None:
    """as the name says"""
    with AnimationSpeed(speed):
        callback(result, *args, **kwargs)


def animateAndDo(callback:Callable, *args:Any, **kwargs:Any) ->Deferred:
    """if we want the next animations to have the same speed as the current group,
    do not use animate().addCallback() because speed would not be kept"""
    result = animate()
    if Internal.Preferences:
        # we might be called very early
        result.addCallback(
            doCallbackWithSpeed, Internal.Preferences.animationSpeed,
            callback, *args, **kwargs).addErrback(logException)
    return result
