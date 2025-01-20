"""
Copyright (c) 2007-2008 Qtrac Ltd <mark@qtrac.eu>
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

# mypy: disable_error_code="attr-defined,call-overload"
# Pyside6 does not seem to have complete/correct annotations for QStyleOptionViewItem

from typing import TYPE_CHECKING, Optional, Callable, Any, cast, Union

from qt import Qt, QSize, QRect, QEvent, QModelIndex
from qt import QStyledItemDelegate, QLabel, QTextDocument, QStyle, QPalette, \
    QStyleOptionViewItem, QApplication

from guiutil import Painter

if TYPE_CHECKING:
    from qt import QLocale, QObject, QPainter, QPersistentModelIndex, QAbstractItemModel
    from qt import QKeyEvent


class ZeroEmptyColumnDelegate(QStyledItemDelegate):

    """Display 0 or 0.00 as empty"""

    def displayText(self, value:Any, locale:'QLocale') ->str:  # type:ignore[override]
        """Display 0 or 0.00 as empty"""
        if isinstance(value, int) and value == 0:
            return ''
        if isinstance(value, float) and value == 0.0:
            return ''
        return super().displayText(value, locale)

class RichTextColumnDelegate(QStyledItemDelegate):

    """enables rich text in a view"""
    label:Optional[QLabel] = None
    document:QTextDocument

    def __init__(self, parent:Optional['QObject']=None) ->None:
        super().__init__(parent)
        if self.label is None:
            self.label = QLabel()
            self.label.setIndent(5)
            self.label.setTextFormat(Qt.TextFormat.RichText)
            self.document = QTextDocument()

    def paint(self, painter:Optional['QPainter'], option:QStyleOptionViewItem,
        index:Union[QModelIndex,'QPersistentModelIndex']) ->None:
        """paint richtext"""
        assert isinstance(index, QModelIndex)
        if option.state & QStyle.StateFlag.State_Selected:
            role = QPalette.ColorRole.Highlight
        else:
            role = QPalette.ColorRole.AlternateBase if index.row() % 2 else QPalette.ColorRole.Base
        assert self.label
        self.label.setBackgroundRole(role)
        if model := index.model():
            text = model.data(index, Qt.ItemDataRole.DisplayRole)
            self.label.setText(text)
        self.label.setFixedSize(option.rect.size())
        if painter:
            with Painter(painter):
                painter.translate(option.rect.topLeft())
                self.label.render(painter)

    def sizeHint(self, option:QStyleOptionViewItem, index:Union[QModelIndex,'QPersistentModelIndex']) ->QSize:
        """compute size for the final formatted richtext"""
        assert isinstance(index, QModelIndex)
        self.document.setDefaultFont(option.font)
        if model := index.model():
            self.document.setHtml(model.data(index))
        return QSize(int(self.document.idealWidth()) + 5,
                     option.fontMetrics.height())


class RightAlignedCheckboxDelegate(QStyledItemDelegate):

    """as the name says. From
https://wiki.qt.io/Technical_FAQ#How_can_I_align_the_checkboxes_in_a_view.3F"""

    def __init__(self, parent:'QObject', cellFilter:Callable) ->None:
        super().__init__(parent)
        self.cellFilter = cellFilter

    @staticmethod
    def __textMargin() ->int:
        """text margin"""
        if style := QApplication.style():
            return style.pixelMetric(
                QStyle.PixelMetric.PM_FocusFrameHMargin) + 1
        return 1

    def paint(self, painter:Optional['QPainter'], option:QStyleOptionViewItem,
        index:Union[QModelIndex,'QPersistentModelIndex']) ->None:
        """paint right aligned checkbox"""
        assert isinstance(index, QModelIndex)
        viewItemOption = QStyleOptionViewItem(option)
        if self.cellFilter(index):
            textMargin = self.__textMargin()
            newRect = QStyle.alignedRect(
                option.direction, Qt.AlignmentFlag.AlignRight,
                QSize(
                    option.decorationSize.width() + 5,
                    option.decorationSize.height()),
                QRect(
                    option.rect.x() + textMargin, option.rect.y(),
                    option.rect.width() - (2 * textMargin),
                    option.rect.height()))
            viewItemOption.rect = newRect
        if painter:
            super().paint(painter, viewItemOption, index)

    def editorEvent(self, event:Optional[QEvent], model:Optional['QAbstractItemModel'],
        option:QStyleOptionViewItem, index:Union[QModelIndex,'QPersistentModelIndex']) ->bool:
        """edit right aligned checkbox"""
        # pylint: disable=too-many-return-statements
        if not event or not model:
            return False
        assert isinstance(index, QModelIndex)
        flags = model.flags(index)
        # make sure that the item is checkable
        if not flags & Qt.ItemFlag.ItemIsUserCheckable or not flags & Qt.ItemFlag.ItemIsEnabled:
            return False
        # make sure that we have a check state
        value = index.data(Qt.ItemDataRole.CheckStateRole)
        if not isinstance(value, int):
            return False
        # make sure that we have the right event type
        if event.type() == QEvent.Type.MouseButtonRelease:
            textMargin = self.__textMargin()
            checkRect = QStyle.alignedRect(
                option.direction, Qt.AlignmentFlag.AlignRight,
                option.decorationSize,
                QRect(
                    option.rect.x() + (2 * textMargin), option.rect.y(),
                    option.rect.width() - (2 * textMargin),
                    option.rect.height()))
            if not checkRect.contains(event.pos()):  # type: ignore[attr-defined]
                return False
        elif event.type() == QEvent.Type.KeyPress:
            if cast('QKeyEvent', event).key() not in (Qt.Key.Key_Space, Qt.Key.Key_Select):
                return False
        else:
            return False
        if value == Qt.CheckState.Checked:
            state = Qt.CheckState.Unchecked
        else:
            state = Qt.CheckState.Checked
        return model.setData(index, state, Qt.ItemDataRole.CheckStateRole)
