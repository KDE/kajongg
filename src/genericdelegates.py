"""Copyright (c) 2007-8 Qtrac Ltd. All rights reserved.
Copyright (C) 2008-2014 Wolfgang Rohdewald

 This program or module is free software: you can redistribute it and/or
 modify it under the terms of the GNU General Public License as published
 by the Free Software Foundation, either version 2 of the License, or
 version 3 of the License, or (at your option) any later version. It is
 provided for educational purposes and is distributed in the hope that
 it will be useful, but WITHOUT ANY WARRANTY; without even the implied
 warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
 the GNU General Public License for more details.
"""

from qt import usingQt5, Qt, RealQVariant, variantValue, QSize, QRect, QEvent
from qt import QStyledItemDelegate, QLabel, QTextDocument, QStyle, QPalette, \
    QStyleOptionViewItem, QApplication

from guiutil import Painter

class RichTextColumnDelegate(QStyledItemDelegate):
    """enables rich text in a view"""
    label = QLabel()
    label.setIndent(5)
    label.setTextFormat(Qt.RichText)
    document = QTextDocument()

    def __init__(self, parent=None):
        super(RichTextColumnDelegate, self).__init__(parent)

    def paint(self, painter, option, index):
        """paint richtext"""
        if option.state & QStyle.State_Selected:
            role = QPalette.Highlight
        else:
            role = QPalette.AlternateBase if index.row() % 2 else QPalette.Base
        self.label.setBackgroundRole(role)
        with RealQVariant():
            text = variantValue(index.model().data(index, Qt.DisplayRole))
        self.label.setText(text)
        self.label.setFixedSize(option.rect.size())
        with Painter(painter):
            painter.translate(option.rect.topLeft())
            self.label.render(painter)

    def sizeHint(self, option, index):
        """compute size for the final formatted richtext"""
        with RealQVariant():
            text = variantValue(index.model().data(index))
        self.document.setDefaultFont(option.font)
        self.document.setHtml(text)
        return QSize(self.document.idealWidth() + 5,
                     option.fontMetrics.height() )

class RightAlignedCheckboxDelegate(QStyledItemDelegate):
    """as the name says. From
    http://qt-project.org/faq/answer/how_can_i_align_the_checkboxes_in_a_view"""

    def __init__(self, parent, cellFilter):
        super(RightAlignedCheckboxDelegate, self).__init__(parent)
        self.cellFilter = cellFilter

    @staticmethod
    def __textMargin():
        """text margin"""
        return QApplication.style().pixelMetric(QStyle.PM_FocusFrameHMargin) + 1

    def paint(self, painter, option, index):
        """paint right aligned checkbox"""
        viewItemOption = QStyleOptionViewItem(option)
        if self.cellFilter(index):
            textMargin = self.__textMargin()
            newRect = QStyle.alignedRect(option.direction, Qt.AlignRight,
                 QSize(option.decorationSize.width() + 5, option.decorationSize.height()),
                 QRect(option.rect.x() + textMargin, option.rect.y(),
                 option.rect.width() - (2 * textMargin), option.rect.height()))
            viewItemOption.rect = newRect
        QStyledItemDelegate.paint(self, painter, viewItemOption, index)

    def editorEvent(self, event, model, option, index):
        """edit right aligned checkbox"""
        flags = model.flags(index)
        # make sure that the item is checkable
        if (not (flags & Qt.ItemIsUserCheckable) or not (flags & Qt.ItemIsEnabled)):
            return False
        # make sure that we have a check state
        value = index.data(Qt.CheckStateRole)
        if not value.isValid():
            return False
        # make sure that we have the right event type
        if event.type() == QEvent.MouseButtonRelease:
            textMargin = self.__textMargin()
            checkRect = QStyle.alignedRect(option.direction, Qt.AlignRight,
                  option.decorationSize,
                  QRect(option.rect.x() + (2 * textMargin), option.rect.y(),
                    option.rect.width() - (2 * textMargin),
                    option.rect.height()))
            if not checkRect.contains(event.pos()):
                return False
        elif event.type() == QEvent.KeyPress:
            if event.key() not in (Qt.Key_Space, Qt.Key_Select):
                return False
        else:
            return False
        if not usingQt5:
            value = value.toInt()[0]
        if value == Qt.Checked:
            state = Qt.Unchecked
        else:
            state = Qt.Checked
        return model.setData(index, state, Qt.CheckStateRole)
