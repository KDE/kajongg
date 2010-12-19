# this is not my code, do not pylintify - just disable pylint as needed
#pylint: disable=C0111
#pylint: disable=R0201
#pylint: disable=W0613
#pylint: disable=W0622

# Copyright (c) 2007-8 Qtrac Ltd. All rights reserved.
# Copyright (c) 2008-10 Wolfgang Rohdewald

# This program or module is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 2 of the License, or
# version 3 of the License, or (at your option) any later version. It is
# provided for educational purposes and is distributed in the hope that
# it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
# the GNU General Public License for more details.

from PyQt4.QtCore import Qt, QVariant, QDate, QString, QSize
from PyQt4.QtGui import QStyledItemDelegate, QSpinBox, QDateEdit, QColor, QApplication,  \
    QLineEdit, QLabel, QTextDocument, QStyle, QPalette

class IntegerColumnDelegate(QStyledItemDelegate):

    def __init__(self, minimum=0, maximum=100, parent=None):
        super(IntegerColumnDelegate, self).__init__(parent)
        self.minimum = minimum
        self.maximum = maximum

    def paint(self, painter, option, index):
        text = index.model().data(index, Qt.DisplayRole).toString()
        painter.save()
        painter.drawText(option.rect, Qt.AlignRight|Qt.AlignVCenter, text)
        painter.restore()

    def createEditor(self, parent, option, index):
        spinbox = QSpinBox(parent)
#        spinbox.setRange(self.minimum, self.maximum)
        spinbox.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        return spinbox


    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.DisplayRole).toInt()[0]
        editor.setValue(value)


    def setModelData(self, editor, model, index):
        editor.interpretText()
        model.setData(index, QVariant(editor.value()))


class DateColumnDelegate(QStyledItemDelegate):

    def __init__(self, minimum=QDate(), maximum=QDate.currentDate(),
                 format="yyyy-MM-dd", parent=None):
        super(DateColumnDelegate, self).__init__(parent)
        self.minimum = minimum
        self.maximum = maximum
        self.format = QString(format)


    def createEditor(self, parent, option, index):
        dateedit = QDateEdit(parent)
        dateedit.setDateRange(self.minimum, self.maximum)
        dateedit.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        dateedit.setDisplayFormat(self.format)
        dateedit.setCalendarPopup(True)
        return dateedit


    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.DisplayRole).toDate()
        editor.setDate(value)


    def setModelData(self, editor, model, index):
        model.setData(index, QVariant(editor.date()))


class PlainTextColumnDelegate(QStyledItemDelegate):

    def __init__(self, parent=None):
        super(PlainTextColumnDelegate, self).__init__(parent)

    def paint(self, painter, option, index):
        text = index.model().data(index, Qt.DisplayRole).toString()
        painter.save()
        palette = QApplication.palette()
        color = palette.highlight().color() \
            if option.state & QStyle.State_Selected \
            else QColor(index.model().data(index,
                    Qt.BackgroundColorRole))
        painter.fillRect(option.rect, color)
        painter.drawText(option.rect, Qt.AlignCenter|Qt.AlignVCenter, text)
        painter.restore()

    def createEditor(self, parent, option, index):
        lineedit = QLineEdit(parent)
        return lineedit

    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.DisplayRole).toString()
        editor.setText(value)

    def setModelData(self, editor, model, index):
        model.setData(index, QVariant(editor.text()))


class RichTextColumnDelegate(QStyledItemDelegate):

    label = QLabel()
    label.setIndent(5)
    label.setTextFormat(Qt.RichText)
    document = QTextDocument()

    def __init__(self, parent=None):
        super(RichTextColumnDelegate, self).__init__(parent)

    def paint(self, painter, option, index):
        if option.state & QStyle.State_Selected:
            role = QPalette.Highlight
        else:
            role = QPalette.AlternateBase if index.row() % 2 else QPalette.Base
        self.label.setBackgroundRole(role)
        text = index.model().data(index, Qt.DisplayRole).toString()
        self.label.setText(text)
        self.label.setFixedSize(option.rect.size())
        painter.save()
        painter.translate(option.rect.topLeft())
        self.label.render(painter)
        painter.restore()

    def sizeHint(self, option, index):
        text = index.model().data(index).toString()
        self.document.setDefaultFont(option.font)
        self.document.setHtml(text)
        return QSize(self.document.idealWidth() + 5,
                     option.fontMetrics.height() )
