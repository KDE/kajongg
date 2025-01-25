# -*- coding: utf-8 -*-
"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

partially based on C++ code from:
Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

SPDX-License-Identifier: GPL-2.0-only

Here we define classes useful for tree views
"""

from typing import Any, List, Sequence, Optional, overload, Union, TYPE_CHECKING, cast

from qt import QAbstractItemModel, QModelIndex, QPersistentModelIndex

if TYPE_CHECKING:
    from qt import QObject


class TreeItem:

    """generic class for items in a tree"""

    def __init__(self, content: Any) ->None:
        self.__rawContent = content
        self.parent:Optional['TreeItem'] = None
        self.children:List['TreeItem'] = []

    def insert(self, row:int, child:'TreeItem') ->'TreeItem':
        """add a new child to this tree node"""
        assert isinstance(child, TreeItem)
        child.parent = self
        self.children.insert(row, child)
        return child

    def remove(self) ->None:
        """remove this item from the model and the database.
        This is an abstract method."""
        raise TypeError(
            'cannot remove this TreeItem. We should never get here.')

    def child(self, row:int) ->'TreeItem':
        """return a specific child item"""
        return self.children[row]

    def childCount(self) ->int:
        """how many children does this item have?"""
        return len(self.children)

    def content(self, column:int) ->Any:
        """content held by this item"""
        raise NotImplementedError("Virtual Method")

    def row(self) ->int:
        """the row of this item in parent"""
        if self.parent:
            return self.parent.children.index(self)
        return 0

    def columnCount(self) ->int:
        """Always return 1. Is 1 always correct? No, inherit from RootItem FIXME"""
        return 1

    @property
    def raw(self) ->Any:
        """make it read only"""
        return self.__rawContent


class RootItem(TreeItem):

    """an item for header data"""

    def __init__(self, content:Any) ->None:
        TreeItem.__init__(self, content)

    def content(self, column:int) ->Any:
        """content held by this item"""
        return self.raw[column]


class TreeModel(QAbstractItemModel):

    """a basic class for Kajongg tree views"""

    def __init__(self, parent:Optional['QObject']=None) ->None:
        super().__init__(parent)
        self.rootItem:Optional[RootItem] = None

    def columnCount(self, parent:Union[QModelIndex,QPersistentModelIndex]=QModelIndex()) ->int:
        """how many columns does this node have?"""
        return self.itemForIndex(cast(QModelIndex, parent)).columnCount()

    def rowCount(self, parent:Union[QModelIndex,QPersistentModelIndex]=QModelIndex()) ->int:
        """how many items?"""
        if parent.isValid() and parent.column():
            # all children have col=0 for parent
            return 0
        return self.itemForIndex(cast(QModelIndex, parent)).childCount()

    def index(self, row:int, column:int, parent:Union[QModelIndex,QPersistentModelIndex]=QModelIndex()) ->QModelIndex:
        """generate an index for this item"""
        if self.rootItem is None:
            return QModelIndex()
        if (row < 0
                or column < 0
                or row >= self.rowCount(parent)
                or column >= self.columnCount(parent)):
            return QModelIndex()
        parentItem = self.itemForIndex(cast(QModelIndex, parent))
        assert parentItem
        item = parentItem.child(row)
        if item:
            return self.createIndex(row, column, item)
        return QModelIndex()

    @overload  # type:ignore[override]
    def parent(self) ->'QObject': ...
    @overload
    def parent(self, index:Union[QModelIndex,QPersistentModelIndex]) ->QModelIndex: ...

    def parent(self, index:Optional[Union[QModelIndex,QPersistentModelIndex]]=None) ->Union[QModelIndex, 'QObject']:
        """find the parent for index"""
        assert isinstance(index, QModelIndex)  # we never use parent() for getting QObject
        if not index.isValid():
            return QModelIndex()
        childItem = self.itemForIndex(index)
        if childItem:
            parentItem = childItem.parent
            if parentItem:
                if parentItem != self.rootItem:
                    grandParentItem = parentItem.parent
                    if grandParentItem:
                        row = grandParentItem.children.index(parentItem)
                        return self.createIndex(row, 0, parentItem)
        return QModelIndex()

    def itemForIndex(self, index:QModelIndex) ->TreeItem:
        """return the item at index"""
        if index.isValid():
            item = cast(TreeItem, index.internalPointer())
            if item:
                return item
        assert self.rootItem
        return self.rootItem

    def insertRows(self, position:int, items:Sequence[TreeItem],  # type:ignore[override]
        parent:QModelIndex=QModelIndex()) ->bool:
        """inserts items into the model"""
        parentItem = self.itemForIndex(parent)
        self.beginInsertRows(parent, position, position + len(items) - 1)
        for row, item in enumerate(items):
            parentItem.insert(position + row, item)
        self.endInsertRows()
        return True

    def removeRows(self, position:int, rows:int=1,
        parent:Union[QModelIndex,QPersistentModelIndex]=QModelIndex()) ->bool:
        """reimplement QAbstractItemModel.removeRows"""
        assert isinstance(parent, QModelIndex)
        self.beginRemoveRows(parent, position, position + rows - 1)
        parentItem = self.itemForIndex(parent)
        for row in parentItem.children[position:position + rows]:
            row.remove()
        parentItem.children = parentItem.children[
            :position] + parentItem.children[
                position + rows:]
        self.endRemoveRows()
        return True
