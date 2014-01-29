"""
##
## Copyright (C) 2007 Trolltech ASA. All rights reserved.
## Copyright (C) 2010-2014 Wolfgang Rohdewald <wolfgang@rohdewald.de>
##
## This file is part of the Qt Concurrent project on Trolltech Labs.
##
## This file may be used under the terms of the GNU General Public
## License version 2.0 as published by the Free Software Foundation
## and appearing in the file LICENSE.GPL included in the packaging of
## this file.  Please review the following information to ensure GNU
## General Public Licensing requirements will be met:
## http://www.trolltech.com/products/qt/opensource.html
##
## If you are unsure which license is appropriate for your use, please
## review the following information:
## http://www.trolltech.com/products/qt/licensing.html or contact the
## sales department at sales@trolltech.com.
##
## This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
## WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
##
#############################################################################
"""

import sip
from qt import QObject, Qt, QVariant, QAbstractItemModel, QModelIndex, \
    QPersistentModelIndex

class ModelTest(QObject):
    """tests a model"""
    def __init__(self, _model, parent):
        """
        Connect to all of the models signals, Whenever anything happens recheck everything.
        """
        QObject.__init__(self, parent)
        self._model = _model
        self.model = sip.cast(_model, QAbstractItemModel)
        self.insert = []
        self.remove = []
        self.changing = []
        self.fetchingMore = False
        assert(self.model)

        self.model.columnsAboutToBeInserted.connect(self.runAllTests)
        self.model.columnsAboutToBeRemoved.connect(self.runAllTests)
        self.model.columnsInserted.connect(self.runAllTests)
        self.model.columnsRemoved.connect(self.runAllTests)
        self.model.dataChanged.connect(self.runAllTests)
        self.model.headerDataChanged.connect(self.runAllTests)
        self.model.layoutAboutToBeChanged.connect(self.runAllTests)
        self.model.layoutChanged.connect(self.runAllTests)
        self.model.modelReset.connect(self.runAllTests)
        self.model.rowsAboutToBeInserted.connect(self.runAllTests)
        self.model.rowsAboutToBeRemoved.connect(self.runAllTests)
        self.model.rowsInserted.connect(self.runAllTests)
        self.model.rowsRemoved.connect(self.runAllTests)

        # Special checks for inserting/removing
        self.model.layoutAboutToBeChanged.connect(self.layoutAboutToBeChanged )
        self.model.layoutChanged.connect(self.layoutChanged )
        self.model.rowsAboutToBeInserted.connect(self.rowsAboutToBeInserted)
        self.model.rowsAboutToBeRemoved.connect(self.rowsAboutToBeRemoved)
        self.model.rowsInserted.connect(self.rowsInserted)
        self.model.rowsRemoved.connect(self.rowsRemoved)
        self.runAllTests()

    def nonDestructiveBasicTest(self):
        """
        nonDestructiveBasicTest tries to call a number of the basic functions (not all)
        to make sure the model doesn't outright segfault, testing the functions that makes sense.
        """
        assert(self.model.buddy(QModelIndex()) == QModelIndex())
        self.model.canFetchMore(QModelIndex())
        assert(self.model.columnCount(QModelIndex()) >= 0)
        assert(self.model.data(QModelIndex(), Qt.DisplayRole) == QVariant())
        self.fetchingMore = True
        self.model.fetchMore(QModelIndex())
        self.fetchingMore = False
        flags = self.model.flags(QModelIndex())
        assert( int(flags & Qt.ItemIsEnabled) == Qt.ItemIsEnabled or \
               int(flags & Qt.ItemIsEnabled ) == 0 )
        self.model.hasChildren(QModelIndex())
        self.model.hasIndex(0, 0)
        self.model.headerData(0, Qt.Horizontal, Qt.DisplayRole)
        self.model.index(0, 0, QModelIndex())
        self.model.itemData(QModelIndex())
        cache = QVariant()
        self.model.match(QModelIndex(), -1, cache)
        self.model.mimeTypes()
        assert(self.model.parent(QModelIndex()) == QModelIndex())
        assert(self.model.rowCount(QModelIndex()) >= 0)
        variant = QVariant()
        self.model.setData(QModelIndex(), variant, -1)
        self.model.setHeaderData(-1, Qt.Horizontal, QVariant())
        self.model.setHeaderData(0, Qt.Horizontal, QVariant())
        self.model.setHeaderData(999999, Qt.Horizontal, QVariant())
        self.model.sibling(0, 0, QModelIndex())
        self.model.span(QModelIndex())
        self.model.supportedDropActions()

    def rowCount(self):
        """
        Tests self.model's implementation of QAbstractItemModel::rowCount() and hasChildren()

        self.models that are dynamically populated are not as fully tested here.
        """
        # check top row
        topindex = self.model.index(0, 0, QModelIndex())
        rows = self.model.rowCount(topindex)
        assert(rows >= 0)
        if rows > 0:
            assert(self.model.hasChildren(topindex) == True )

        secondlvl = self.model.index(0, 0, topindex)
        if secondlvl.isValid():
            # check a row count where parent is valid
            rows = self.model.rowCount(secondlvl)
            assert(rows >= 0)
            if rows > 0:
                assert(self.model.hasChildren(secondlvl) == True)

        # The self.models rowCount() is tested more extensively in checkChildren,
        # but this catches the big mistakes

    def columnCount(self):
        """
        Tests self.model's implementation of QAbstractItemModel::columnCount() and hasChildren()
        """
        # check top row
        topidx = self.model.index(0, 0, QModelIndex())
        assert(self.model.columnCount(topidx) >= 0)

        # check a column count where parent is valid
        childidx = self.model.index(0, 0, topidx)
        if childidx.isValid() :
            assert(self.model.columnCount(childidx) >= 0)

        # columnCount() is tested more extensively in checkChildren,
        # but this catches the big mistakes

    def hasIndex(self):
        """
        Tests self.model's implementation of QAbstractItemModel::hasIndex()
        """
        # Make sure that invalid values returns an invalid index
        assert(self.model.hasIndex(-2, -2) == False)
        assert(self.model.hasIndex(-2, 0) == False)
        assert(self.model.hasIndex(0, -2) == False)

        rows = self.model.rowCount(QModelIndex())
        cols = self.model.columnCount(QModelIndex())

        # check out of bounds
        assert(self.model.hasIndex(rows, cols) == False)
        assert(self.model.hasIndex(rows+1, cols+1) == False)

        if rows > 0:
            assert(self.model.hasIndex(0, 0) == True)

        # hasIndex() is tested more extensively in checkChildren()
        # but this catches the big mistakes

    def index(self):
        """
        Tests self.model's implementation of QAbstractItemModel::index()
        """
        # Make sure that invalid values returns an invalid index
        assert(self.model.index(-2, -2, QModelIndex()) == QModelIndex())
        assert(self.model.index(-2, 0, QModelIndex()) == QModelIndex())
        assert(self.model.index(0, -2, QModelIndex()) == QModelIndex())

        rows = self.model.rowCount(QModelIndex())
        cols = self.model.columnCount(QModelIndex())

        if rows == 0:
            return

        # Catch off by one errors
        assert(self.model.index(rows, cols, QModelIndex()) == QModelIndex())
        assert(self.model.index(0, 0, QModelIndex()).isValid() == True)

        # Make sure that the same index is *always* returned
        idx1 = self.model.index(0, 0, QModelIndex())
        idx2 = self.model.index(0, 0, QModelIndex())
        assert(idx1==idx2)

        # index() is tested more extensively in checkChildren()
        # but this catches the big mistakes

    def parent(self):
        """
        Tests self.model's implementation of QAbstractItemModel::parent()
        """
        # Make sure the self.model wont crash and will return an invalid QModelIndex
        # when asked for the parent of an invalid index
        assert(self.model.parent(QModelIndex()) == QModelIndex())

        if self.model.rowCount(QModelIndex()) == 0:
            return

        # Column 0              | Column 1  |
        # QtCore.Qself.modelIndex()         |           |
        #    \- topidx          | topidx1   |
        #         \- childix    | childidx1 |

        # Common error test #1, make sure that a top level index has a parent
        # that is an invalid QtCore.Qself.modelIndex
        topidx = self.model.index(0, 0, QModelIndex())
        assert(self.model.parent(topidx) == QModelIndex())

        # Common error test #2, make sure that a second level index has a parent
        # that is the first level index
        if self.model.rowCount(topidx) > 0 :
            childidx = self.model.index(0, 0, topidx)
            assert(self.model.parent(childidx) == topidx)

        # Common error test #3, the second column should NOT have the same children
        # as the first column in a row
        # Usually the second column shouldn't have children
        topidx1 = self.model.index(0, 1, QModelIndex())
        if self.model.rowCount(topidx1) > 0:
            childidx = self.model.index(0, 0, topidx)
            childidx1 = self.model.index(0, 0, topidx1)
            assert(childidx != childidx1)

        # Full test, walk n levels deep through the self.model making sure that all
        # parent's children correctly specify their parent
        self.checkChildren(QModelIndex())

    def data(self):
        """
        Tests self.model's implementation of QAbstractItemModel::data()
        """
        # Invalid index should return an invalid qvariant
        assert( not self.model.data(QModelIndex(), Qt.DisplayRole).isValid())

        if self.model.rowCount(QModelIndex()) == 0:
            return

        # A valid index should have a valid QVariant data
        assert( self.model.index(0, 0, QModelIndex()).isValid())

        # shouldn't be able to set data on an invalid index
        assert( self.model.setData( QModelIndex(), QVariant("foo"), Qt.DisplayRole) == False)

        # General Purpose roles that should return a QString
        variant = self.model.data(self.model.index(0, 0, QModelIndex()), Qt.ToolTipRole)
        if variant.isValid():
            assert( variant.canConvert( QVariant.String ) )
        variant = self.model.data(self.model.index(0, 0, QModelIndex()), Qt.StatusTipRole)
        if variant.isValid():
            assert( variant.canConvert( QVariant.String ) )
        variant = self.model.data(self.model.index(0, 0, QModelIndex()), Qt.WhatsThisRole)
        if variant.isValid():
            assert( variant.canConvert( QVariant.String ) )

        # General Purpose roles that should return a QSize
        variant = self.model.data(self.model.index(0, 0, QModelIndex()), Qt.SizeHintRole)
        if variant.isValid():
            assert( variant.canConvert( QVariant.Size ) )

        # General Purpose roles that should return a QFont
        variant = self.model.data(self.model.index(0, 0, QModelIndex()), Qt.FontRole)
        if variant.isValid():
            assert( variant.canConvert( QVariant.Font ) )

        # Check that the alignment is one we know about
        variant = self.model.data(self.model.index(0, 0, QModelIndex()), Qt.TextAlignmentRole)
        if variant.isValid():
            alignment = variant.toInt()[0]
            assert( alignment == (alignment & int(Qt.AlignHorizontal_Mask | Qt.AlignVertical_Mask)))

        # General Purpose roles that should return a QColor
        variant = self.model.data(self.model.index(0, 0, QModelIndex()), Qt.BackgroundColorRole)
        if variant.isValid():
            assert( variant.canConvert( QVariant.Color ) )
        variant = self.model.data(self.model.index(0, 0, QModelIndex()), Qt.TextColorRole)
        if variant.isValid():
            assert( variant.canConvert( QVariant.Color ) )

        # Check that the "check state" is one we know about.
        variant = self.model.data(self.model.index(0, 0, QModelIndex()), Qt.CheckStateRole)
        if variant.isValid():
            state = variant.toInt()[0]
            assert( state == Qt.Unchecked or
                state == Qt.PartiallyChecked or
                state == Qt.Checked )


    def runAllTests(self):
        """run all tests after the model changed"""
        if self.fetchingMore:
            return
        self.nonDestructiveBasicTest()
        self.rowCount()
        self.columnCount()
        self.hasIndex()
        self.index()
        self.parent()
        self.data()

    def rowsAboutToBeInserted(self, parent, start, dummyEnd):
        """
        Store what is about to be inserted to make sure it actually happens
        """
        item = {}
        item['parent'] = parent
        item['oldSize'] = self.model.rowCount(parent)
        item['last'] = self.model.data(self.model.index(start-1, 0, parent))
        item['next'] = self.model.data(self.model.index(start, 0, parent))
        self.insert.append(item)

    def rowsInserted(self, parent, start, end):
        """
        Confirm that what was said was going to happen actually did
        """
        item = self.insert.pop()
        assert(item['parent'] == parent)
        assert(item['oldSize'] + (end - start + 1) == self.model.rowCount(parent))
        assert(item['last'] == self.model.data(self.model.index(start-1, 0, item['parent'])))

        # if item['next'] != self.model.data(self.model.index(end+1, 0, item['parent'])):
        #   qDebug << start << end
        #   for i in range(0, self.model.rowCount(QModelIndex())):
        #       qDebug << self.model.index(i, 0).data().toString()
        #   qDebug() << item['next'] << self.model.data(model.index(end+1, 0, item['parent']))

        assert(item['next'] == self.model.data(self.model.index(end+1, 0, item['parent'])))

    def rowsAboutToBeRemoved(self, parent, start, end):
        """
        Store what is about to be inserted to make sure it actually happens
        """
        item = {}
        item['parent'] = parent
        item['oldSize'] = self.model.rowCount(parent)
        item['last'] = self.model.data(self.model.index(start-1, 0, parent))
        item['next'] = self.model.data(self.model.index(end+1, 0, parent))
        self.remove.append(item)

    def rowsRemoved(self, parent, start, end):
        """
        Confirm that what was said was going to happen actually did
        """
        item = self.remove.pop()
        assert(item['parent'] == parent)
        assert(item['oldSize'] - (end - start + 1) == self.model.rowCount(parent))
        assert(item['last'] == self.model.data(self.model.index(start-1, 0, item['parent'])))
        assert(item['next'] == self.model.data(self.model.index(start, 0, item['parent'])))

    def layoutAboutToBeChanged(self):
        """
        Store what is about to be changed
        """
        for i in range(0, max(0, min( self.model.rowCount(), 100))):
            self.changing.append(QPersistentModelIndex( self.model.index( i, 0)))

    def layoutChanged(self):
        """
        Confirm that what was said was going to happen actually did
        """
        for change in self.changing:
            assert(change == self.model.index( change.row(), change.column(), change.parent()))
        self.changing = []

    def checkChildren(self, parent, depth = 0):
        """
        Called from parent() test.

        A self.model that returns an index of parent X should also return X when asking
        for the parent of the index

        This recursive function does pretty extensive testing on the whole self.model in an
        effort to catch edge cases.

        This function assumes that rowCount(QModelIndex()), columnCount(QModelIndex()) and index() already work.
        If they have a bug it will point it out, but the above tests should have already
        found the basic bugs because it is easier to figure out the problem in
        those tests then this one
        """
        # First just try walking back up the tree.
        parentIdx = parent
        while parentIdx.isValid():
            parentIdx = parentIdx.parent()

        #For self.models that are dynamically populated
        if self.model.canFetchMore( parent ):
            self.fetchingMore = True
            self.model.fetchMore(parent)
            self.fetchingMore = False

        rows = self.model.rowCount(parent)
        cols = self.model.columnCount(parent)

        if rows > 0:
            assert(self.model.hasChildren(parent))

        # Some further testing against rows(), columns, and hasChildren()
        assert( rows >= 0 )
        assert( cols >= 0 )

        if rows > 0:
            assert(self.model.hasChildren(parent) == True)

        # qDebug() << "parent:" << self.model.data(parent).toString() << "rows:" << rows
        #          << "columns:" << cols << "parent column:" << parent.column()

        assert( self.model.hasIndex( rows+1, 0, parent) == False)
        for row in range(0, rows):
            if self.model.canFetchMore(parent):
                self.fetchingMore = True
                self.model.fetchMore(parent)
                self.fetchingMore = False
            assert(self.model.hasIndex(row, cols+1, parent) == False)
            for column in range(0, cols):
                assert(self.model.hasIndex(row, column, parent))
                index = self.model.index(row, column, parent)
                # rowCount(QModelIndex()) and columnCount(QModelIndex()) said that it existed...
                assert(index.isValid() == True)

                # index() should always return the same index when called twice in a row
                modIdx = self.model.index(row, column, parent)
                assert(index == modIdx)

                # Make sure we get the same index if we request it twice in a row
                idx1 = self.model.index(row, column, parent)
                idx2 = self.model.index(row, column, parent)
                assert( idx1 == idx2 )

                # Some basic checking on the index that is returned
                # assert( index.model() == self.model )
                # This raises an error that is not part of the qbzr code.
                # see http://www.opensubscriber.com/message/pyqt@riverbankcomputing.com/10335500.html
                assert( index.row() == row )
                assert( index.column() == column )
                # While you can technically return a QVariant usually this is a sign
                # if an bug in data() Disable if this really is ok in your self.model
                assert( self.model.data(index, Qt.DisplayRole).isValid() == True )

                #if the next test fails here is some somehwat useful debug you play with
                # if self.model.parent(index) != parent:
                #   qDebug() << row << column << depth << self.model.data(index).toString()
                #        << self.model.data(parent).toString()
                #   qDebug() << index << parent << self.model.parent(index)
                #   # And a view that you can even use to show the self.model
                #   # view = QtGui.QTreeView()
                #   # view.setself.model(model)
                #   # view.show()
                #

                # Check that we can get back our real parent
                parentIdx = self.model.parent( index )
                assert( parentIdx.internalId() == parent.internalId() )
                assert( parentIdx.row() == parent.row() )

                # recursively go down the children
                if self.model.hasChildren(index) and depth < 10:
                    # qDebug() << row << column << "hasChildren" << self.model.rowCount(index)
                    self.checkChildren(index, depth+1)
                #else:
                #   if depth >= 10:
                #       qDebug() << "checked 10 deep"

                # Make sure that after testing the children that the index doesn't change
                newIdx = self.model.index(row, column, parent)
                assert(index == newIdx)
