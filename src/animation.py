# -*- coding: utf-8 -*-

"""
Copyright (C) 2010-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

import functools
import types

from typing import List, Any, Optional, Dict, Union, TYPE_CHECKING, Callable, Type, cast

from twisted.internet.defer import Deferred, succeed, fail

from qt import QPropertyAnimation, QParallelAnimationGroup, \
    QAbstractAnimation, QEasingCurve
from qt import Property, QGraphicsObject, QGraphicsItem, QPointF, QObject

from common import Internal, Debug, isAlive, ReprMixin, id4
from log import logDebug, logFailure

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
        self.debug |= f'T{id4(graphicsObject)}t' in Debug.animation
        Animation.clsUid += 1
        self.uid = Animation.clsUid
        assert isinstance(graphicsObject, QObject)
        _ = propName.encode()
        QPropertyAnimation.__init__(self, graphicsObject, _, parent)
        QPropertyAnimation.setEndValue(self, endValue)
        assert Internal.Preferences
        duration = Internal.Preferences.animationDuration()
        self.setDuration(duration)
        self.setEasingCurve(QEasingCurve.Type.InOutQuad)
        graphicsObject.queuedAnimations.append(self)
        Animation.nextAnimations.append(self)
        if self.debug:
            oldAnimation = graphicsObject.activeAnimation.get(propName, None)
            if isAlive(oldAnimation):
                assert isinstance(oldAnimation, Animation)
                logDebug(
                    f'new Animation({self}) (after {oldAnimation.ident()} is done)')
            else:
                logDebug(f'Animation({self})')

    def setEndValue(self, endValue:PropertyType) ->None:
        """wrapper with debugging code"""
        graphicsObject = self.targetObject()
        if not isAlive(graphicsObject):
            # may happen when aborting a game because animations are cancelled first,
            # before the last move from server is executed
            return
        if cast('AnimatedMixin', graphicsObject).debug_name() in Debug.animation or Debug.animation == 'all':
            logDebug(
                f'{self.ident()}: change endValue for {self.pName()}: '
                f'{self.formatValue(self.endValue())}->{self.formatValue(endValue)}  {graphicsObject}')
        QPropertyAnimation.setEndValue(self, endValue)

    def ident(self) ->str:
        """the identifier to be used in debug messages"""
        pGroup = self.group() if isAlive(self) else 'notAlive'
        if pGroup or not isAlive(self):
            return f'{pGroup}/A_{id4(self)}'
        return f"A_{id4(self)}-{cast('AnimatedMixin', self.targetObject()).debug_name()}"

    def pName(self) ->str:
        """
        Return self.propertyName() as a python string.

        @return: C{str}
        """
        if not isAlive(self):
            return 'notAlive'
        _ = self.propertyName()
        return bytes(_).decode()

    def formatValue(self, value:PropertyType) ->str:
        """string format the wanted value from qvariant"""
        pName = self.pName()
        if pName == 'pos':
            _ = cast(QPointF, value)
            return f'{_.x():.0f}/{_.y():.0f}'
        if pName == 'rotation':
            _ = cast(int, value)
            return str(_)
        if pName == 'scale':
            _ = cast(float, value)
            return f'{_:.2f}'
        return f'formatValue: unexpected {pName}={value}'

    def __str__(self) ->str:
        """for debug messages"""
        if not isAlive(self):
            return 'notAlive'
        if not isAlive(self.targetObject()):
            return f'{self.ident()} {self.pName()}: target notAlive'
        currentValue = getattr(self.targetObject(), self.pName())
        endValue = self.endValue()
        targetObject = None
        if _ := self.targetObject():
            targetObject = _
        return (f'{self.ident()} {self.pName()}: {self.formatValue(currentValue)}->'
                f'{self.formatValue(endValue)} for {targetObject} duration={int(self.duration())}ms')

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
        self.deferred.addErrback(logFailure)
        self.steps = 0
        self.debug = any(x.debug for x in self.animations)
        self.debug |= f'G{id4(self)}g' in Debug.animation
        self.doAfter:List[Deferred] = []
        if ParallelAnimationGroup.current:
            if self.debug or ParallelAnimationGroup.current.debug:
                logDebug(f'Chaining Animation group G_{id4(self)} to G{ParallelAnimationGroup.current}')
            self.doAfter = ParallelAnimationGroup.current.doAfter
            ParallelAnimationGroup.current.doAfter = []
            ParallelAnimationGroup.current.deferred.addCallback(self.start).addErrback(logFailure)
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
            logDebug(f'G{self.uid}: {self.stateName(oldState)} -> {self.stateName(newState)} isAlive:{isAlive(self)}')

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
                currValue = cast(float, animatedObject.rotation)
                if endValue - currValue > 180:
                    animation.setStartValue(currValue + 360)
                if currValue - endValue > 180:
                    animation.setStartValue(currValue - 360)
        for animation in self.animations:
            if target := animation.targetObject():
                target.setDrawingOrder()  # type:ignore[attr-defined]
        self.finished.connect(self.allFinished)
        scene = Internal.scene
        assert scene
        scene.focusRect.hide()
        QParallelAnimationGroup.start(
            self,
            QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        if self.debug:
            assert Internal.Preferences
            _ = ','.join(f'A_{id4(x)}' for x in self.animations)
            logDebug(f'{self} started with speed {int(Internal.Preferences.animationSpeed)} ({_})')
        return succeed(None).addErrback(logFailure)

    def allFinished(self) ->None:
        """all animations have finished. Cleanup and callback"""
        self.fixAllBoards()
        if self == ParallelAnimationGroup.current:
            ParallelAnimationGroup.current = None
            ParallelAnimationGroup.running = []
        if Debug.animationSpeed and self.duration():
            perSecond = self.steps * 1000.0 / self.duration()
            if perSecond < 50:
                logDebug(f'{int(self.steps)} steps for {len(self.children())} animations, {perSecond:.1f}/sec')
        # if we have a deferred, callback now
        assert self.deferred
        if self.debug:
            logDebug(f'Done: {self}')
        if self.deferred:
            self.deferred.callback(None)
        for after in self.doAfter:
            after.callback(None)

    def fixAllBoards(self) ->None:
        """set correct drawing order for all moved graphics objects"""
        for animation in self.children():
            if graphicsObject := animation.targetObject():  # type:ignore[attr-defined]
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
        return f'unknown state:{state}'

    def __str__(self) ->str:
        """for debugging"""
        return f'G{self.uid}({len(self.animations)}:{self.stateName()})'


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
            logDebug(f'shortcut {animation}: UTile {self.debug_name()}: clear queuedAnimations')
        setattr(self, animation.pName(), animation.endValue())
        self.queuedAnimations = []
        self.setDrawingOrder()  # type:ignore[attr-defined] # TODO: mypy protocol?

    def getValue(self, pName:str) ->Union[QPointF,int,float]:
        """get a current property value"""
        if pName == 'pos':
            return cast(QPointF, self.pos)
        if pName == 'rotation':
            return cast(int, self.rotation)
        if pName == 'scale':
            return cast(float, self.scale)
        assert False

    def setActiveAnimation(self, animation:'Animation') ->None:
        """the graphics object knows which of its properties are currently animated"""
        self.queuedAnimations = []
        propName = animation.pName()
        if self.debug_name() in Debug.animation:
            oldAnimation = self.activeAnimation.get(propName, None)
            if not isAlive(oldAnimation):
                oldAnimation = None
            if oldAnimation:
                logDebug(f'**** setActiveAnimation {self.debug_name()} {propName}: '
                         f'{animation} OVERRIDES {oldAnimation}')
            else:
                logDebug(f'setActiveAnimation {self.debug_name()} {propName}: set {animation}')
        self.activeAnimation[propName] = animation
        self.setCacheMode(QGraphicsItem.CacheMode.ItemCoordinateCache)  # type: ignore[attr-defined]

    def clearActiveAnimation(self, animation:'Animation') ->None:
        """an animation for this graphics object has ended.
        Finalize graphics object in its new position"""
        del self.activeAnimation[animation.pName()]
        if self.debug_name() in Debug.animation:
            logDebug(f'UITile {self.debug_name()}: clear activeAnimation_{animation.pName()}')
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
                        logDebug(f'setEndValue for {animation}: {pName}: '
                                 f'{animation.formatValue(curValue)}->{animation.formatValue(newValue)}')
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
                    logDebug(f'AnimationSpeed sets speed {int(speed)}')

    def __enter__(self) ->'AnimationSpeed':
        return self

    def __exit__(self, exc_type:Type[Exception], exc_value:Exception, trback:Any) ->None:
        """reset previous animation speed"""
        if Internal.Preferences:
            if self.__speed < 99:
                animate()
            if Internal.Preferences.animationSpeed != self.prevAnimationSpeed:
                if Debug.animationSpeed:
                    logDebug(f'AnimationSpeed restores speed '
                             f'{Internal.Preferences.animationSpeed} to {self.prevAnimationSpeed}')
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
            f'{doAfter.__qualname__} passed {varnames[1]} instead of deferredResult'  # type:ignore[attr-defined]
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
    return succeed(None).addErrback(logFailure)


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
            callback, *args, **kwargs).addErrback(logFailure)
    return result
