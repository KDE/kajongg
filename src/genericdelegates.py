"""Copyright (c) 2007-8 Qtrac Ltd. All rights reserved.
Copyright (C) 2008-2011 Wolfgang Rohdewald

 This program or module is free software: you can redistribute it and/or
 modify it under the terms of the GNU General Public License as published
 by the Free Software Foundation, either version 2 of the License, or
 version 3 of the License, or (at your option) any later version. It is
 provided for educational purposes and is distributed in the hope that
 it will be useful, but WITHOUT ANY WARRANTY; without even the implied
 warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
 the GNU General Public License for more details.
"""

from PyQt4.QtCore import Qt, QSize
from PyQt4.QtGui import QStyledItemDelegate, QLabel, QTextDocument, QStyle, QPalette

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
        text = index.model().data(index, Qt.DisplayRole).toString()
        self.label.setText(text)
        self.label.setFixedSize(option.rect.size())
        painter.save()
        painter.translate(option.rect.topLeft())
        self.label.render(painter)
        painter.restore()

    def sizeHint(self, option, index):
        """compute size for the final formatted richtext"""
        text = index.model().data(index).toString()
        self.document.setDefaultFont(option.font)
        self.document.setHtml(text)
        return QSize(self.document.idealWidth() + 5,
                     option.fontMetrics.height() )
