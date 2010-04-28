# this is not my code, do not pylintify - just disable pylint as needed
#pylint: disable-msg=C0111
#pylint: disable-msg=R0201
#pylint: disable-msg=W0613
#pylint: disable-msg=W0622

# Copyright (c) 2007-8 Qtrac Ltd. All rights reserved.
# This program or module is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 2 of the License, or
# version 3 of the License, or (at your option) any later version. It is
# provided for educational purposes and is distributed in the hope that
# it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
# the GNU General Public License for more details.

from PyQt4 import QtCore, QtGui


class GenericDelegate(QtGui.QItemDelegate):

    def __init__(self, parent=None):
        super(GenericDelegate, self).__init__(parent)
        self.delegates = {}


    def insertColumnDelegate(self, column, delegate):
        delegate.setParent(self)
        self.delegates[column] = delegate


    def removeColumnDelegate(self, column):
        if column in self.delegates:
            del self.delegates[column]


    def paint(self, painter, option, index):
        delegate = self.delegates.get(index.column())
        if delegate is not None:
            delegate.paint(painter, option, index)
        else:
            QtGui.QItemDelegate.paint(self, painter, option, index)


    def createEditor(self, parent, option, index):
        delegate = self.delegates.get(index.column())
        if delegate is not None:
            return delegate.createEditor(parent, option, index)
        else:
            return QtGui.QItemDelegate.createEditor(self, parent, option,
                                              index)


    def setEditorData(self, editor, index):
        delegate = self.delegates.get(index.column())
        if delegate is not None:
            delegate.setEditorData(editor, index)
        else:
            QtGui.QItemDelegate.setEditorData(self, editor, index)


    def setModelData(self, editor, model, index):
        delegate = self.delegates.get(index.column())
        if delegate is not None:
            delegate.setModelData(editor, model, index)
        else:
            QtGui.QItemDelegate.setModelData(self, editor, model, index)


class IntegerColumnDelegate(QtGui.QItemDelegate):

    def __init__(self, minimum=0, maximum=100, parent=None):
        super(IntegerColumnDelegate, self).__init__(parent)
        self.minimum = minimum
        self.maximum = maximum

    def paint(self, painter, option, index):
        text = index.model().data(index, QtCore.Qt.DisplayRole).toString()
        painter.save()
        painter.drawText(option.rect, QtCore.Qt.AlignRight|QtCore.Qt.AlignVCenter, text)
        painter.restore()

    def createEditor(self, parent, option, index):
        spinbox = QtGui.QSpinBox(parent)
#        spinbox.setRange(self.minimum, self.maximum)
        spinbox.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignVCenter)
        return spinbox


    def setEditorData(self, editor, index):
        value = index.model().data(index, QtCore.Qt.DisplayRole).toInt()[0]
        editor.setValue(value)


    def setModelData(self, editor, model, index):
        editor.interpretText()
        model.setData(index, QtCore.QVariant(editor.value()))


class DateColumnDelegate(QtGui.QItemDelegate):

    def __init__(self, minimum=QtCore.QDate(), maximum=QtCore.QDate.currentDate(),
                 format="yyyy-MM-dd", parent=None):
        super(DateColumnDelegate, self).__init__(parent)
        self.minimum = minimum
        self.maximum = maximum
        self.format = QtCore.QString(format)


    def createEditor(self, parent, option, index):
        dateedit = QtGui.QDateEdit(parent)
        dateedit.setDateRange(self.minimum, self.maximum)
        dateedit.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignVCenter)
        dateedit.setDisplayFormat(self.format)
        dateedit.setCalendarPopup(True)
        return dateedit


    def setEditorData(self, editor, index):
        value = index.model().data(index, QtCore.Qt.DisplayRole).toDate()
        editor.setDate(value)


    def setModelData(self, editor, model, index):
        model.setData(index, QtCore.QVariant(editor.date()))


class PlainTextColumnDelegate(QtGui.QItemDelegate):

    def __init__(self, parent=None):
        super(PlainTextColumnDelegate, self).__init__(parent)

    def paint(self, painter, option, index):
        text = index.model().data(index, QtCore.Qt.DisplayRole).toString()
        painter.save()
        palette = QtGui.QApplication.palette()
        color = palette.highlight().color() \
            if option.state & QtGui.QStyle.State_Selected \
            else QtGui.QColor(index.model().data(index,
                    QtCore.Qt.BackgroundColorRole))
        painter.fillRect(option.rect, color)
        painter.drawText(option.rect, QtCore.Qt.AlignCenter|QtCore.Qt.AlignVCenter, text)
        painter.restore()

    def createEditor(self, parent, option, index):
        lineedit = QtGui.QLineEdit(parent)
        return lineedit


    def setEditorData(self, editor, index):
        value = index.model().data(index, QtCore.Qt.DisplayRole).toString()
        editor.setText(value)

    def setModelData(self, editor, model, index):
        model.setData(index, QVariant(editor.text()))
