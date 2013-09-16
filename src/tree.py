# -*- coding: utf-8 -*-
"""
    Copyright (C) 2008-2011 Wolfgang Rohdewald <wolfgang@rohdewald.de>

    partially based on C++ code from:
    Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

    Libkmahjongg is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.

Here we define classes useful for tree views
"""

from PyQt4.QtCore import QAbstractItemModel, QModelIndex

class TreeItem(object):  # pylint: disable=R0922
    """generic class for items in a tree"""
    def __init__(self, content):
        self.rawContent = content
        self.parent = None
        self.children = []

    def insert(self, row, child):
        """add a new child to this tree node"""
        assert isinstance(child, TreeItem)
        child.parent = self
        self.children.insert(row, child)
        return child

    def remove(self): # pylint: disable=R0201
        """remove this item from the model and the database.
        This is an abstract method."""
        raise Exception('cannot remove this TreeItem. We should never get here.')

    def child(self, row):
        """return a specific child item"""
        return self.children[row]

    def childCount(self):
        """how many children does this item have?"""
        return len(self.children)

    def content(self, column):
        """content held by this item"""
        raise NotImplementedError("Virtual Method")

    def row(self):
        """the row of this item in parent"""
        if self.parent:
            return self.parent.children.index(self)
        return 0

class RootItem(TreeItem):
    """an item for header data"""
    def __init__(self, content):
        TreeItem.__init__(self, content)

    def content(self, column):
        """content held by this item"""
        return self.rawContent[column]

    def columnCount(self): # pylint: disable=R0201
        """is 1 always correct? No, inherit from RootItem"""
        return 1

class TreeModel(QAbstractItemModel):
    """a basic class for Kajongg tree views"""

    def columnCount(self, parent):
        """how many columns does this node have?"""
        return self.itemForIndex(parent).columnCount()

    def rowCount(self, parent):
        """how many items?"""
        if parent.isValid() and parent.column():
            # all children have col=0 for parent
            return 0
        return self.itemForIndex(parent).childCount()

    def index(self, row, column, parent):
        """generate an index for this item"""
        if self.rootItem is None:
            return QModelIndex()
        if row < 0 or column < 0 or row >= self.rowCount(parent) or column >= self.columnCount(parent):
            return QModelIndex()
        parentItem = self.itemForIndex(parent)
        assert parentItem
        item = parentItem.child(row)
        if item:
            return self.createIndex(row, column, item)
        return QModelIndex()

    def parent(self, index):
        """find the parent index"""
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

    def itemForIndex(self, index):
        """returns the item at index"""
        if index.isValid():
            item = index.internalPointer()
            if item:
                return item
        return self.rootItem

    def insertRows(self, position, items, parent=QModelIndex()):
        """inserts items into the model"""
        parentItem = self.itemForIndex(parent)
        self.beginInsertRows(parent, position, position + len(items)- 1)
        for row, item in enumerate(items):
            parentItem.insert(position + row, item)
        self.endInsertRows()
        return True

    def removeRows(self, position, rows=1, parent=QModelIndex()):
        """reimplement QAbstractItemModel.removeRows"""
        self.beginRemoveRows(parent, position, position + rows - 1)
        parentItem = self.itemForIndex(parent)
        for row in parentItem.children[position:position + rows]:
            row.remove()
        parentItem.children = parentItem.children[:position] + parentItem.children[position + rows:]
        self.endRemoveRows()
        return True
